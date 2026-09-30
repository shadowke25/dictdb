"""业务编排层：add / select / show / delete / update / git / export / import。

供 CLI 复用，不含任何终端交互。删除/更新走「plan(只读预检) ->
execute(执行)」两段式，二次确认由调用方基于 plan 内容展示真实变更。
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ..i18n import t
from . import fileops, gitops
from .database import Database
from .models import (CONFLICT, GIT_ERROR, NOT_FOUND, VALIDATION,
                     DictError, normalize_tags, now_str, parse_id,
                     parse_target, record_to_public)
from .storage import Storage


def get_context(data_home=None):
    home = Path(data_home or os.environ.get("DICTDB_HOME")
                or Path(__file__).resolve().parent.parent)
    storage = Storage(home)
    db = Database(storage.db_path)
    db.init_schema()
    return db, storage


def public_of(db, storage, rec, index=None, has_update=None, check_error=None):
    if rec is None:
        return None
    return record_to_public(rec, str(storage.abs_path(rec)), index=index,
                            has_update=has_update, check_error=check_error)


# ---------- add ----------

def add_dictionary(db, storage, src_path, name, tags=None, instructions="",
                   source="", category="", link=False, force=False):
    src = Path(src_path).expanduser().resolve()
    if not src.is_file():
        raise DictError(NOT_FOUND, t("err.path_not_found", src=src), http_status=404)
    if not name or not str(name).strip():
        raise DictError(VALIDATION, t("err.name_required"))
    name = str(name).strip()

    stats = fileops.file_stats(src)
    dups = db.find_by_md5(stats["md5"])
    if dups and not force:
        dup = dups[0]
        raise DictError(
            CONFLICT,
            t("err.dup_md5", id=dup["id"], name=dup["name"]),
            http_status=409,
        )

    git = None
    if gitops.git_available():
        repo = gitops.find_repo(src.parent)
        if repo:
            git = gitops.repo_info(repo, src)

    now = now_str()
    item_id = db.insert({
        "name": name,
        "tags": normalize_tags(tags),
        "instructions": instructions or "",
        "source": source or "",
        "category": category or "",
        "storage_mode": "link" if link else "copy",
        "file_path": str(src) if link else "",
        "original_path": str(src),
        "size": stats["size"], "lines": stats["lines"], "md5": stats["md5"],
        "git_url": git["url"] if git else "",
        "git_branch": git["branch"] if git else "",
        "git_commit": git["commit"] if git else "",
        "git_rel_path": git["rel_path"] if git else "",
        "git_synced_at": now if git else "",
        "created_at": now, "updated_at": now,
    })
    if not link:
        db.update(item_id, {"file_path": storage.import_file(src, item_id, name)})
    return public_of(db, storage, db.get(item_id))


# ---------- select / show ----------

def search_dictionaries(db, storage, keyword=None, tag=None, category=None):
    raws = db.search(keyword=keyword, tag=tag, category=category)
    return [public_of(db, storage, r, index=i + 1) for i, r in enumerate(raws)]


def get_by_id(db, storage, item_id):
    rec = db.get(parse_id(item_id))
    if rec is None:
        raise DictError(NOT_FOUND, t("err.target_not_found", n=item_id), http_status=404)
    return public_of(db, storage, rec, index=1)  # 与 select 序号缓存保持一致


def outdated_report(db, storage):
    """对所有 git 来源字典做远端版本比对（ls-remote，只读），有更新的排前面。"""
    out = []
    for rec in db.all():
        if not rec.get("git_url"):
            continue
        has_update, check_error = None, None
        try:
            has_update = gitops.check_update(
                rec["git_url"], rec.get("git_branch", ""), rec.get("git_commit", "")
            )["has_update"]
        except DictError as e:
            check_error = e.message
        out.append(public_of(db, storage, rec, has_update=has_update, check_error=check_error))
    out.sort(key=lambda r: (r["git"]["has_update"] is not True, r["id"]))
    # 补序号：人类表格与 last_search 缓存（delete list N）都依赖它
    return [dict(r, index=i + 1) for i, r in enumerate(out)]


def resolve_target(db, storage, target):
    """统一选择器：'7' = 主键 7；'@2' = 最近 select 结果第 2 条。"""
    kind, n = parse_target(target)
    if kind == "id":
        rec = db.get(n)
        if rec is None:
            raise DictError(NOT_FOUND, t("err.target_not_found", n=n), http_status=404)
        return rec
    ids = storage.load_last_search()
    if n < 1 or n > len(ids):
        raise DictError(NOT_FOUND,
                        t("err.index_out_of_range", n=n, total=len(ids)))
    rec = db.get(ids[n - 1])
    if rec is None:
        raise DictError(NOT_FOUND, t("err.index_gone", n=n))
    return rec


def git_check(rec):
    if not rec.get("git_url"):
        raise DictError(VALIDATION, t("err.not_git_dict"))
    return {"id": rec["id"], "name": rec["name"],
            "git_check": gitops.check_update(rec["git_url"], rec.get("git_branch", ""),
                                             rec.get("git_commit", ""))}


def show_content(storage, rec, lines=None, head=None, tail=None, grep=None):
    p = storage.abs_path(rec)
    if not p.exists():
        raise DictError(NOT_FOUND, t("err.file_lost", p=p), http_status=404)
    truncated = False
    if lines:
        a, b = lines
        rows = fileops.read_line_range(p, a, b)
        mode = "range"
        # JSON 的 range 保持机器形态（本地化描述由人类视图负责）
        rng = f"{a}" if a == b else f"{a}-{b}"
    elif grep:
        rows, truncated = fileops.grep_lines(p, grep)
        mode, rng = "grep", grep
    elif tail:
        rows = fileops.tail_lines(p, tail)
        mode, rng = "tail", str(tail)
    elif head is not None and head > 0:
        rows = fileops.head_lines(p, head)
        mode, rng = "head", str(head)
    elif head is not None:  # --head 0/负数 = 不限制（完整内容）
        rows = fileops.read_line_range(p, 1, None)
        mode, rng = "all", str(len(rows))
    else:  # 缺省限流：前 20 行（大字典防刷屏）
        rows = fileops.head_lines(p, 20)
        mode, rng = "head", "20"
    # 缺省限流标记：人类视图据此提示查看全文的方式；JSON 消费方可据此判断截断
    default_limited = lines is None and grep is None and tail is None and head is None
    return {
        "id": rec["id"], "name": rec["name"], "path": str(p),
        "total_lines": rec.get("lines", 0),
        "mode": mode, "range": rng, "count": len(rows), "truncated": truncated,
        "default_limited": default_limited,
        "lines": [{"n": n, "text": tx} for n, tx in rows],
    }


# ---------- delete ----------

def delete_dictionary(db, storage, rec):
    storage.delete_copy(rec)
    db.delete(rec["id"])
    return public_of(db, storage, rec)


# ---------- update ----------

def plan_update(db, storage, rec, opts):
    """只读预检，产出变更计划；git --check 在此完成比对供确认页展示。"""
    target = storage.abs_path(rec)
    plan = {
        "id": rec["id"], "name": rec["name"], "target": str(target),
        "storage_mode": rec.get("storage_mode", "copy"),
        "actions": [], "warnings": [], "git_check": None, "meta": {},
    }
    has_file_op = bool(opts.get("replace") or opts.get("append")
                       or opts.get("append_text") or opts.get("git"))
    if not (has_file_op or opts.get("meta") or opts.get("check")):
        raise DictError(VALIDATION, t("err.no_update_ops"))

    if has_file_op and not target.exists():
        raise DictError(NOT_FOUND, t("err.file_lost", p=target), http_status=404)

    if opts.get("replace"):
        src = Path(opts["replace"]).expanduser().resolve()
        if not src.is_file():
            raise DictError(NOT_FOUND, t("err.replace_src_missing", src=src), http_status=404)
        stats = fileops.file_stats(src)
        plan["actions"].append({"type": "replace", "source": str(src),
                                "backup": str(target) + ".bak",
                                "new_lines": stats["lines"], "new_size": stats["size"]})
    if opts.get("append"):
        src = Path(opts["append"]).expanduser().resolve()
        if not src.is_file():
            raise DictError(NOT_FOUND, t("err.append_src_missing", src=src), http_status=404)
        plan["actions"].append({"type": "append_file", "source": str(src),
                                "append_lines": fileops.count_lines(src)})
    text = opts.get("append_text")
    if text:
        n = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        plan["actions"].append({"type": "append_text", "text": str(text), "append_lines": n})

    if opts.get("git") or opts.get("check"):
        if not rec.get("git_url"):
            raise DictError(VALIDATION, t("err.not_git_dict"))
        plan["git_check"] = gitops.check_update(
            rec["git_url"], rec.get("git_branch", ""), rec.get("git_commit", ""))
        if opts.get("git") and not opts.get("check"):  # --check 只比对，抑制拉取
            if plan["git_check"]["has_update"] is False:
                plan["warnings"].append(t("warn.git_no_update"))
            else:
                plan["actions"].append({"type": "git_pull", "url": rec["git_url"],
                                        "branch": rec.get("git_branch", ""),
                                        "rel_path": rec.get("git_rel_path", "")})

    if rec.get("storage_mode") == "link" and has_file_op:
        plan["warnings"].append(t("warn.link_modify", target=target))

    if opts.get("meta"):
        plan["meta"] = opts["meta"]
        plan["actions"].append({"type": "meta", "fields": sorted(opts["meta"])})
    return plan


def execute_update(db, storage, rec, plan):
    target = storage.abs_path(rec)
    backup = None
    changed_file = False
    git_fields = {}

    file_ops = [a for a in plan["actions"]
                if a["type"] in ("replace", "append_file", "append_text", "git_pull")]
    if file_ops:
        backup = storage.backup(target)  # 首次改动前只备份一次

    for act in plan["actions"]:
        t = act["type"]
        if t == "replace":
            fileops.replace_file(target, act["source"])
            changed_file = True
        elif t == "append_file":
            fileops.append_file(target, act["source"])
            changed_file = True
        elif t == "append_text":
            fileops.append_text(target, act["text"])
            changed_file = True
        elif t == "git_pull":
            if rec.get("storage_mode") == "link":
                repo = gitops.find_repo(target.parent)
                if repo is None:
                    raise DictError(GIT_ERROR, t("err.repo_lost", target=target))
                gitops.pull(repo)
                info = gitops.repo_info(repo, target)
                git_fields = {"git_commit": info["commit"], "git_synced_at": now_str()}
            else:
                with tempfile.TemporaryDirectory(prefix="dictdb-git-") as tmp:
                    tmp_file = Path(tmp) / "fetch.bin"
                    gitops.clone_file(rec["git_url"], rec.get("git_branch", ""),
                                      rec.get("git_rel_path", ""), tmp_file)
                    fileops.replace_file(target, tmp_file)
                try:
                    new_commit = gitops.ls_remote_commit(rec["git_url"], rec.get("git_branch", ""))
                except DictError:
                    new_commit = (plan.get("git_check") or {}).get("remote_commit")
                if new_commit:
                    git_fields = {"git_commit": new_commit, "git_synced_at": now_str()}
            changed_file = True

    fields = dict(plan.get("meta") or {})
    fields.update(git_fields)
    if changed_file:
        stats = fileops.file_stats(target)
        fields.update({"size": stats["size"], "lines": stats["lines"], "md5": stats["md5"]})
    if fields:
        fields["updated_at"] = now_str()
        db.update(rec["id"], fields)
    return {
        "record": public_of(db, storage, db.get(rec["id"])),
        "summary": {"backup": str(backup) if backup else None,
                    "changed_file": changed_file,
                    "meta_changed": bool(plan.get("meta"))},
    }


def plan_git_all(db, storage):
    outdated, up_to_date, errors = [], 0, []
    for rec in db.all():
        if not rec.get("git_url"):
            continue
        try:
            chk = gitops.check_update(rec["git_url"], rec.get("git_branch", ""),
                                      rec.get("git_commit", ""))
        except DictError as e:
            errors.append({"id": rec["id"], "name": rec["name"], "error": e.message})
            continue
        if chk["has_update"]:
            # 带序号供确认页表格（outdated_table）使用
            outdated.append(public_of(db, storage, rec,
                                      index=len(outdated) + 1, has_update=True))
        else:
            up_to_date += 1
    return {"outdated": outdated, "up_to_date": up_to_date, "errors": errors}


def execute_git_all(db, storage, plan):
    updated, failed = [], []
    for item in plan["outdated"]:
        rec = db.get(item["id"])
        if rec is None:
            continue
        try:
            p = plan_update(db, storage, rec, {"git": True})
            updated.append(execute_update(db, storage, rec, p)["record"])
        except DictError as e:
            failed.append({"id": item["id"], "name": item["name"], "error": e.message})
    return {"updated": updated, "failed": failed,
            "unchanged": plan["up_to_date"], "check_errors": plan["errors"]}


# ---------- export / import ----------

def export_database(db, storage, out_path=None):
    data = db.export_all()
    out = Path(out_path) if out_path else storage.export_dir / "db.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(out.resolve()), "count": data["count"]}


def import_database(db, storage, json_path, replace=False):
    p = Path(json_path)
    if not p.is_file():
        raise DictError(NOT_FOUND, t("err.import_file_missing", p=p), http_status=404)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise DictError(VALIDATION, t("err.import_bad_json", e=e))
    return db.import_data(data, replace=replace)
