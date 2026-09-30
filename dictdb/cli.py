"""命令行适配层：argparse 解析、二次确认、退出码、界面语言。

命令体系（v1.4）：
  选择器统一 <主键|@序号>：数字 = 主键，@n = 最近 select 结果第 n 条
  职责分离：update 纯内容 / edit 纯元数据 / info 详情 / git status|check|pull 版本管理
  无别名：add/select/show/info/edit/update/delete/git/export/import
  纯本地定位：专注管理本地字典；MCP 与 HTTP 服务方案均已放弃（2026-09 决策）
界面语言：默认英文，--lang zh 或环境变量 DICTDB_LANG=zh 切换中文（help 同步切换）。

全局选项 --json / --table / --lang 放命令前后均可。
默认输出：stdout 为 TTY → 人类表格；被管道/工具调用 → 自动 JSON。
退出码：0 成功 / 1 未找到或运行错误 / 2 参数错误 / 3 用户取消或需确认。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import traceback
from pathlib import Path

from . import __version__
from .core import service
from .core.models import (CANCELLED, SERVER_ERROR, VALIDATION,
                          DictError, normalize_tags)
from .i18n import set_lang, t
from .output import (UI, human_add, human_check_only, human_delete_done,
                     human_git_all_done, human_outdated, human_select,
                     human_show, human_update_done, confirm_text,
                     detail_text, outdated_table, project_select,
                     project_git_status)

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_CANCELLED = 0, 1, 2, 3
_CODE_EXIT = {"VALIDATION": EXIT_USAGE, "CONFIRM_REQUIRED": EXIT_CANCELLED,
              "CANCELLED": EXIT_CANCELLED}


def _data_home() -> Path:
    return Path(os.environ.get("DICTDB_HOME")
                or Path(__file__).resolve().parent.parent)


def _detect_lang(argv) -> str:
    """语言探测优先级：--lang 旗标 > DICTDB_LANG > en。在构建 parser 前调用，
    这样 --help 本身就能按目标语言渲染。"""
    lang = (os.environ.get("DICTDB_LANG") or "en").strip().lower()
    a = list(argv if argv is not None else sys.argv[1:])
    for i, x in enumerate(a):
        if x == "--lang" and i + 1 < len(a):
            lang = a[i + 1].strip().lower()
        elif x.startswith("--lang="):
            lang = x.split("=", 1)[1].strip().lower()
    return lang if lang in ("en", "zh") else "en"


def _common_parent():
    """挂在主命令与全部子命令上的全局选项（default=SUPPRESS 使先后位置均可）。"""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=t("help.json"))
    p.add_argument("--table", action="store_true", default=argparse.SUPPRESS, help=t("help.table"))
    p.add_argument("--lang", choices=["en", "zh"], default=argparse.SUPPRESS, help=t("help.lang"))
    p.add_argument("--full", action="store_true", default=argparse.SUPPRESS, help=t("help.full"))
    return p


def build_parser() -> argparse.ArgumentParser:
    common = _common_parent()
    p = argparse.ArgumentParser(
        prog="dictdb", parents=[common],
        description=t("help.description"),
        formatter_class=argparse.RawDescriptionHelpFormatter,  # 速查表保留换行
        epilog=t("help.epilog"),
    )
    p.add_argument("--version", action="version", version=f"dictdb {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("add", parents=[common], help=t("help.add"))
    sp.add_argument("path", help=t("help.add.path"))
    sp.add_argument("-n", "--name", help=t("help.add.name"))
    sp.add_argument("-t", "--tags", help=t("help.add.tags"))
    sp.add_argument("-c", "--category", help=t("help.add.category"))
    sp.add_argument("-i", "--instructions", help=t("help.add.instructions"))
    sp.add_argument("-s", "--source", help=t("help.add.source"))
    sp.add_argument("--link", action="store_true", help=t("help.add.link"))
    sp.add_argument("--force", action="store_true", help=t("help.add.force"))
    sp.set_defaults(func=cmd_add)

    sp = sub.add_parser("select", parents=[common], help=t("help.select"))
    sp.add_argument("keyword", nargs="?", help=t("help.select.keyword"))
    sp.add_argument("--id", help=t("help.select.id"))
    sp.add_argument("--tag", help=t("help.select.tag"))
    sp.add_argument("--category", help=t("help.select.category"))
    sp.set_defaults(func=cmd_select)

    sp = sub.add_parser("show", parents=[common], help=t("help.show"))
    _add_target_args(sp)
    sp.add_argument("--lines", help=t("help.show.lines"))
    sp.add_argument("--head", type=int, help=t("help.show.head"))
    sp.add_argument("--tail", type=int, help=t("help.show.tail"))
    sp.add_argument("--grep", help=t("help.show.grep"))
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("info", parents=[common], help=t("help.info"))
    _add_target_args(sp)
    sp.set_defaults(func=cmd_info)

    sp = sub.add_parser("edit", parents=[common], help=t("help.edit"))
    _add_target_args(sp)
    sp.add_argument("-n", "--name", help=t("help.edit.name"))
    sp.add_argument("-t", "--tags", help=t("help.edit.tags"))
    sp.add_argument("-c", "--category", help=t("help.edit.category"))
    sp.add_argument("-i", "--instructions", help=t("help.edit.instructions"))
    sp.add_argument("-s", "--source", help=t("help.edit.source"))
    sp.add_argument("--yes", action="store_true", help=t("help.yes"))
    sp.set_defaults(func=cmd_edit)

    sp = sub.add_parser("update", parents=[common], help=t("help.update"))
    _add_target_args(sp)
    sp.add_argument("--replace", help=t("help.update.replace"))
    sp.add_argument("--append", help=t("help.update.append"))
    sp.add_argument("--text", dest="append_text", help=t("help.update.text"))
    sp.add_argument("--yes", action="store_true", help=t("help.yes"))
    sp.set_defaults(func=cmd_update)

    sp = sub.add_parser("delete", parents=[common], help=t("help.delete"))
    _add_target_args(sp)
    sp.add_argument("--yes", action="store_true", help=t("help.yes"))
    sp.set_defaults(func=cmd_delete)

    gp = sub.add_parser("git", parents=[common], help=t("help.git"))
    git_sub = gp.add_subparsers(dest="git_command", required=True)
    gsp = git_sub.add_parser("status", parents=[common], help=t("help.git.status"))
    gsp.set_defaults(func=cmd_git_status)
    gsp = git_sub.add_parser("check", parents=[common], help=t("help.git.check"))
    gsp.add_argument("target", help=t("help.show.target"))
    gsp.set_defaults(func=cmd_git_check)
    gsp = git_sub.add_parser("pull", parents=[common], help=t("help.git.pull"))
    gsp.add_argument("target", nargs="?", help=t("help.git.pull_target"))
    gsp.add_argument("--yes", action="store_true", help=t("help.yes"))
    gsp.set_defaults(func=cmd_git_pull)

    sp = sub.add_parser("export", parents=[common], help=t("help.export"))
    sp.add_argument("-o", "--out", help=t("help.export.out"))
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("import", parents=[common], help=t("help.import"))
    sp.add_argument("file", help=t("help.import.file"))
    sp.add_argument("--replace", action="store_true", help=t("help.import.replace"))
    sp.add_argument("--yes", action="store_true", help=t("help.yes"))
    sp.set_defaults(func=cmd_import)

    return p


def _add_target_args(sp):
    """选择器参数：单一 <主键|@序号>。"""
    sp.add_argument("target", nargs="?", help=t("help.show.target"))


def _resolve_target(args, db, storage):
    if not args.target:
        raise DictError(VALIDATION, t("cli.target_usage"))
    return service.resolve_target(db, storage, args.target)


def parse_range(s: str):
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", s.strip())
    if not m:
        raise DictError(VALIDATION, t("cli.lines_format", s=s))
    a, b = int(m.group(1)), int(m.group(2) or m.group(1))
    return (a, b) if a <= b else (b, a)


# ---------- 添加 / 搜索 / 查看 ----------

def cmd_add(args, ui, db, storage):
    name = args.name
    if not name and sys.stdin.isatty() and sys.stdout.isatty():
        # 仅真实终端才交互补问；提示走 stderr 保持 stdout 可管道。
        # 注意 Windows 上 NUL 设备 isatty() 为 True，必须同时校验 stdout。
        sys.stderr.write(t("confirm.add_name_prompt"))
        sys.stderr.flush()
        try:
            name = sys.stdin.readline().strip()
        except EOFError:
            name = ""
    rec = service.add_dictionary(
        db, storage, args.path, name,
        tags=args.tags, instructions=args.instructions, source=args.source,
        category=args.category, link=args.link, force=args.force,
    )
    ui.emit("add", rec, 1, human=lambda: human_add(rec))
    return EXIT_OK


def cmd_select(args, ui, db, storage):
    if args.id is not None:
        records = [service.get_by_id(db, storage, args.id)]
    else:
        records = service.search_dictionaries(db, storage, keyword=args.keyword,
                                              tag=args.tag, category=args.category)
    storage.save_last_search([r["id"] for r in records], query=args.keyword or "")
    if not getattr(args, "full", False):
        records = [project_select(r) for r in records]  # 默认 9 字段投影
    ui.emit("select", records, len(records), human=lambda: human_select(records))
    return EXIT_OK


def cmd_show(args, ui, db, storage):
    rec = _resolve_target(args, db, storage)
    result = service.show_content(storage, rec, lines=parse_range(args.lines) if args.lines else None,
                                  head=args.head, tail=args.tail, grep=args.grep)
    ui.emit("show", result, result["count"], human=lambda: human_show(result))
    return EXIT_OK


# ---------- 详情 / 修改：info / edit / update / delete ----------

def cmd_info(args, ui, db, storage):
    rec = _resolve_target(args, db, storage)
    pub = service.public_of(db, storage, rec)
    ui.emit("info", pub, 1, human=lambda: print(detail_text(pub)))
    return EXIT_OK


def cmd_edit(args, ui, db, storage):
    meta = {}
    if args.name is not None:
        meta["name"] = args.name
    if args.tags is not None:
        meta["tags"] = normalize_tags(args.tags)
    if args.category is not None:
        meta["category"] = args.category
    if args.instructions is not None:
        meta["instructions"] = args.instructions
    if args.source is not None:
        meta["source"] = args.source
    if not args.target and not meta:
        raise DictError(VALIDATION, t("cli.target_usage"))
    rec = _resolve_target(args, db, storage)
    if not meta:
        raise DictError(VALIDATION, t("cli.edit_missing_fields"))
    plan = {
        "id": rec["id"], "name": rec["name"], "target": str(storage.abs_path(rec)),
        "storage_mode": rec.get("storage_mode", "copy"),
        "actions": [{"type": "meta", "fields": sorted(meta)}],
        "warnings": [], "git_check": None, "meta": meta,
    }
    if not args.yes:
        detail = confirm_text(plan, service.public_of(db, storage, rec))
        if not ui.confirm(t("confirm.edit", id=rec["id"]), detail=detail):
            raise DictError(CANCELLED, t("confirm.cancelled_edit"))
    result = service.execute_update(db, storage, rec, plan)
    ui.emit("edit", result, 1, human=lambda: human_update_done(result))
    return EXIT_OK


def cmd_update(args, ui, db, storage):
    if not args.target:
        raise DictError(VALIDATION, t("cli.update_usage"))
    rec = _resolve_target(args, db, storage)
    opts = {"replace": args.replace, "append": args.append,
            "append_text": args.append_text}
    plan = service.plan_update(db, storage, rec, opts)

    if not args.yes:
        detail = confirm_text(plan, service.public_of(db, storage, rec))
        if not ui.confirm(t("confirm.update", id=rec["id"]), detail=detail):
            raise DictError(CANCELLED, t("confirm.cancelled_update"))
    result = service.execute_update(db, storage, rec, plan)
    ui.emit("update", result, 1, human=lambda: human_update_done(result))
    return EXIT_OK


def cmd_delete(args, ui, db, storage):
    rec = _resolve_target(args, db, storage)
    if not args.yes:
        pub = service.public_of(db, storage, rec)
        if not ui.confirm(t("confirm.delete", id=rec["id"], name=rec["name"]),
                          detail=detail_text(pub)):
            raise DictError(CANCELLED, t("confirm.cancelled_delete"))
    deleted = service.delete_dictionary(db, storage, rec)
    ui.emit("delete", {"deleted": True, "id": rec["id"], "record": deleted}, 1,
            human=lambda: human_delete_done(deleted))
    return EXIT_OK


# ---------- git 命令组 ----------

def cmd_git_status(args, ui, db, storage):
    records = service.outdated_report(db, storage)
    storage.save_last_search([r["id"] for r in records], query="git status")
    if not getattr(args, "full", False):
        records = [project_git_status(r) for r in records]
    ui.emit("git_status", records, len(records), human=lambda: human_outdated(records))
    return EXIT_OK


def cmd_git_check(args, ui, db, storage):
    rec = service.resolve_target(db, storage, args.target)
    data = service.git_check(rec)
    ui.emit("git_check", data, 1, human=lambda: human_check_only(rec, data))
    return EXIT_OK


def cmd_git_pull(args, ui, db, storage):
    if args.target:
        return _do_git_pull_single(args.target, args.yes, ui, db, storage)
    return _do_git_pull_batch(args.yes, ui, db, storage)


def _do_git_pull_single(target, yes, ui, db, storage):
    rec = service.resolve_target(db, storage, target)
    plan = service.plan_update(db, storage, rec, {"git": True})
    if not plan["actions"]:
        data = {"id": rec["id"], "name": rec["name"], "updated": False,
                "git_check": plan["git_check"]}
        ui.emit("git_pull", data, 0,
                human=lambda: print(t("ui.git_pull_fresh", id=rec["id"], name=rec["name"])))
        return EXIT_OK
    if not yes:
        detail = confirm_text(plan, service.public_of(db, storage, rec))
        if not ui.confirm(t("confirm.git_pull", id=rec["id"]), detail=detail):
            raise DictError(CANCELLED, t("confirm.cancelled_pull"))
    result = service.execute_update(db, storage, rec, plan)
    ui.emit("git_pull", result, 1, human=lambda: human_update_done(result))
    return EXIT_OK


def _do_git_pull_batch(yes, ui, db, storage):
    plan = service.plan_git_all(db, storage)
    if not plan["outdated"]:
        result = {"updated": [], "failed": plan["errors"],
                  "unchanged": plan["up_to_date"], "check_errors": plan["errors"]}
        ui.emit("git_pull", result, 0, human=lambda: human_git_all_done(result))
        return EXIT_OK
    if not yes:
        if not ui.confirm(t("confirm.git_pull_batch", n=len(plan["outdated"])),
                          detail=outdated_table(plan["outdated"])):
            raise DictError(CANCELLED, t("confirm.cancelled_pull"))
    result = service.execute_git_all(db, storage, plan)
    ui.emit("git_pull", result, len(result["updated"]), human=lambda: human_git_all_done(result))
    return EXIT_OK


# ---------- 备份 / 服务 ----------

def cmd_export(args, ui, db, storage):
    result = service.export_database(db, storage, args.out)
    ui.emit("export", result, result["count"],
            human=lambda: print(t("ui.export_done", n=result["count"], path=result["path"])))
    return EXIT_OK


def cmd_import(args, ui, db, storage):
    if args.replace and not args.yes:
        if not ui.confirm(t("confirm.import_replace", file=args.file)):
            raise DictError(CANCELLED, t("confirm.cancelled_import"))
    result = service.import_database(db, storage, args.file, replace=args.replace)
    mode = t("ui.import_mode_replace") if result["replaced"] else t("ui.import_mode_merge")
    ui.emit("import", result, result["imported"],
            human=lambda: print(t("ui.import_done", mode=mode, n=result["imported"],
                                  total=result["total_after"])))
    return EXIT_OK


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # 语言在构建 parser 前确定：--help 本身就能按目标语言渲染
    set_lang(_detect_lang(argv))
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "lang", None):
        set_lang(args.lang)
    if getattr(args, "json", False) and getattr(args, "table", False):
        parser.error(t("cli.json_table_conflict"))

    json_mode = (True if getattr(args, "json", False)
                 else False if getattr(args, "table", False)
                 else not sys.stdout.isatty())
    ui = UI(json_mode)

    try:
        db, storage = service.get_context(_data_home())
        return args.func(args, ui, db, storage)
    except DictError as e:
        ui.error(getattr(args, "command", "dictdb"), e)
        return _CODE_EXIT.get(e.code, EXIT_ERROR)
    except KeyboardInterrupt:
        ui.error(getattr(args, "command", "dictdb"), DictError(CANCELLED, t("err.interrupted")))
        return EXIT_CANCELLED
    except Exception as e:  # 未预期错误：栈跟踪给 stderr，信封给 stdout
        traceback.print_exc()
        ui.error(getattr(args, "command", "dictdb"),
                 DictError(SERVER_ERROR, t("err.internal", e=e), http_status=500))
        return EXIT_ERROR
