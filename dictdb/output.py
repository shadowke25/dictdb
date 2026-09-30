"""输出层：JSON 信封 / 人类表格（中文显示宽度对齐）/ 交互二次确认。

JSON 信封统一为 {ok, command, count, schema_version, data, error}，
字段名小写 snake_case，保证 AI 与其他工具零转换消费。
人类文案经 i18n.t() 输出（默认英文，DICTDB_LANG=zh / --lang zh 切中文）。
"""
from __future__ import annotations

import json
import sys
import unicodedata

from .core.models import CONFIRM_REQUIRED, SCHEMA_VERSION, DictError
from .i18n import t

_WIDE = ("W", "F")


def disp_width(s: str) -> int:
    """终端显示宽度：全角/中文按 2 列计。"""
    return sum(2 if unicodedata.east_asian_width(ch) in _WIDE else 1 for ch in s)


def _truncate(s: str, w: int) -> str:
    if disp_width(s) <= w:
        return s
    cw = 0
    for i, ch in enumerate(s):
        cw += 2 if unicodedata.east_asian_width(ch) in _WIDE else 1
        if cw > w - 1:
            return s[:i] + "…"
    return s


def _pad(s: str, w: int) -> str:
    return s + " " * max(0, w - disp_width(s))


def format_size(n) -> str:
    n = int(n or 0)
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"


def render_table(headers, rows, caps=None) -> str:
    caps = caps or {}
    cells = [[str(c) for c in row] for row in rows]
    widths = [disp_width(h) for h in headers]
    for row in cells:
        for i, c in enumerate(row):
            cap = caps.get(i)
            if cap and disp_width(c) > cap:
                row[i] = _truncate(c, cap)
            widths[i] = max(widths[i], disp_width(row[i]))
    out = ["  ".join(_pad(h, widths[i]) for i, h in enumerate(headers)),
           "  ".join("-" * w for w in widths)]
    for row in cells:
        out.append("  ".join(_pad(row[i], widths[i]) for i in range(len(headers))))
    return "\n".join(out)


class UI:
    """按 json_mode 决定输出形态；确认提示一律走 stderr，保持 stdout 可管道。"""

    def __init__(self, json_mode: bool):
        self.json_mode = json_mode

    def emit(self, command, data=None, count=None, human=None):
        if self.json_mode:
            if count is None:
                count = len(data) if isinstance(data, list) else (0 if data is None else 1)
            print(json.dumps({
                "ok": True, "command": command, "count": count,
                "schema_version": SCHEMA_VERSION, "data": data, "error": None,
            }, ensure_ascii=False, indent=2))
        elif human:
            human()

    def error(self, command, err: DictError):
        if self.json_mode:
            print(json.dumps({
                "ok": False, "command": command, "count": 0,
                "schema_version": SCHEMA_VERSION, "data": None,
                "error": {"code": err.code, "message": err.message},
            }, ensure_ascii=False, indent=2))
        else:
            sys.stderr.write(f"[{err.code}] {err.message}\n")

    def confirm(self, prompt: str, detail: str | None = None) -> bool:
        """二次确认。详情与提示一律走 stderr。

        stdin 读到 EOF（管道、NUL 设备、已关闭）视为非交互——注意 Windows 上
        isatty() 对 NUL 返回 True，不能依赖 isatty 判断，必须以实际读取结果为准。
        非交互环境抛 CONFIRM_REQUIRED，脚本必须显式 --yes。
        """
        if detail:
            sys.stderr.write(detail.rstrip() + "\n")
        sys.stderr.write(f"{prompt} [y/N] ")
        sys.stderr.flush()
        line = sys.stdin.readline()
        if line == "":
            raise DictError(CONFIRM_REQUIRED, t("confirm.required"))
        return line.strip().lower() in ("y", "yes", "是")


# ---------- 人类视图 ----------

def human_select(records):
    if not records:
        print(t("ui.no_match"))
        return
    headers = [t("hdr.index"), t("hdr.id"), t("hdr.name"), t("hdr.category"),
               t("hdr.tags"), t("hdr.lines"), t("hdr.instructions"), t("hdr.updated")]
    rows = [[r["index"], r["id"], r["name"], r["category"] or "-",
             ",".join(r["tags"]) or "-", r["lines"], r["instructions"] or "-",
             (r["updated_at"] or "-")[:10]] for r in records]
    print(render_table(headers, rows, caps={2: 24, 4: 18, 6: 24}))
    print(f"\n{t('ui.select_total', n=len(records))}")


def _outdated_status(r):
    g = r.get("git") or {}
    if g.get("check_error"):
        return t("ui.status_check_failed")
    if g.get("has_update"):
        return t("ui.status_outdated")
    if g.get("has_update") is False:
        return t("ui.status_up_to_date")
    return t("ui.status_unknown")


def outdated_table(records) -> str:
    if not records:
        return t("ui.no_git_dicts")
    headers = [t("hdr.index"), t("hdr.id"), t("hdr.name"), t("hdr.branch"),
               t("hdr.local_commit"), t("hdr.status")]
    rows = [[r["index"], r["id"], r["name"], r["git"]["branch"] or "-",
             (r["git"]["commit"] or "-")[:8], _outdated_status(r)] for r in records]
    body = render_table(headers, rows, caps={2: 24})
    n = sum(1 for r in records if _outdated_status(r) == t("ui.status_outdated"))
    return f"{body}\n\n{t('ui.git_total', n=len(records), m=n)}"


def human_outdated(records):
    print(outdated_table(records))


def human_show(result):
    print(t("ui.show_header", id=result["id"], name=result["name"],
            lines=result["total_lines"], path=result["path"]))
    extra = t("ui.show_truncated") if result["truncated"] else ""
    mode, rng = result["mode"], str(result["range"])
    if mode == "head":
        label = t("ui.mode_head", n=rng)
    elif mode == "tail":
        label = t("ui.mode_tail", n=rng)
    elif mode == "grep":
        label = t("ui.mode_grep", q=rng)
    elif mode == "all":
        label = t("ui.mode_all", n=rng)
    else:  # range: "100-200" / "100"
        a, _, b = rng.partition("-")
        label = t("ui.mode_range", a=a, b=b or a)
    print(t("ui.show_range_line", label=label, count=result["count"], extra=extra))
    if result.get("default_limited"):
        print(t("ui.show_default_hint"))
    print("-" * 48)
    for item in result["lines"]:
        print(f"{item['n']:>8}: {item['text']}")


# ---------- select JSON 投影（默认 9 字段，--full 输出全部） ----------

_SELECT_FIELDS = ("index", "id", "name", "category", "tags", "instructions",
                  "lines", "path", "updated_at")
_INSTRUCTIONS_LIMIT = 50
_GIT_STATUS_FIELDS = ("branch", "commit", "has_update", "check_error")


def project_select(rec: dict) -> dict:
    """按决策价值投影 select 记录：字段保留理由见 README 输出协议章节。"""
    out = {k: rec[k] for k in _SELECT_FIELDS if k in rec}
    ins = out.get("instructions") or ""
    if len(ins) > _INSTRUCTIONS_LIMIT:
        out["instructions"] = ins[:_INSTRUCTIONS_LIMIT] + "…"
    return out


def project_git_status(rec: dict) -> dict:
    """git status 列表投影：select 9 字段 + 版本比对所需的最小 git 子集。"""
    out = project_select(rec)
    git = rec.get("git") or {}
    out["git"] = {k: git.get(k) for k in _GIT_STATUS_FIELDS if git}
    return out


def detail_text(rec) -> str:
    """单条字典详情（info 命令与确认页共用），返回字符串由调用方决定去向。"""
    def kv(label_key, value):
        return f"{t(label_key)}={value}"
    lines = [
        f"id={rec['id']}  {kv('ui.detail_name', rec['name'])}",
        f"{kv('ui.detail_category', rec['category'] or '-')}  "
        f"{kv('ui.detail_tags', ','.join(rec['tags']) or '-')}",
        f"{kv('ui.detail_instructions', rec['instructions'] or '-')}",
        f"{kv('ui.detail_source', rec['source'] or '-')}",
        f"{kv('ui.detail_mode', rec['storage_mode'])}  {kv('ui.detail_path', rec['path'])}",
        f"{kv('ui.detail_size', format_size(rec['size']))}  "
        f"{kv('ui.detail_lines', rec['lines'])}  md5={rec['md5'][:12]}",
    ]
    if rec.get("git"):
        g = rec["git"]
        lines.append(f"git={g['url']} @ {g['branch'] or '-'} {g['commit'][:8]}  "
                     f"{t('ui.detail_git_synced')}={g['synced_at'] or '-'}")
    lines.append(f"{t('ui.detail_created')}={rec['created_at']}  "
                 f"{t('ui.detail_updated')}={rec['updated_at']}")
    return "\n".join(lines)


def human_add(rec):
    print(t("ui.add_done", id=rec["id"], name=rec["name"]))
    if rec.get("git"):
        print(t("ui.add_git_detected", url=rec["git"]["url"], commit=rec["git"]["commit"][:8]))
    print(t("ui.add_path", path=rec["path"]))
    print(t("ui.add_stats", lines=rec["lines"], size=format_size(rec["size"]), md5=rec["md5"][:12]))


def human_delete_done(rec):
    print(t("ui.delete_done", id=rec["id"], name=rec["name"]))


def confirm_text(plan, rec) -> str:
    """更新确认页文本：详情 + 动作清单 + git 比对 + 告警。"""
    parts = [detail_text(rec), "", t("ui.confirm_actions")]
    for a in plan["actions"]:
        if a["type"] == "replace":
            parts.append(t("ui.act_replace", src=a["source"], lines=a["new_lines"],
                           size=format_size(a["new_size"]), backup=a["backup"]))
        elif a["type"] == "append_file":
            parts.append(t("ui.act_append_file", src=a["source"], lines=a["append_lines"]))
        elif a["type"] == "append_text":
            parts.append(t("ui.act_append_text", lines=a["append_lines"], text=a["text"][:40]))
        elif a["type"] == "git_pull":
            parts.append(t("ui.act_git_pull", url=a["url"],
                           branch=a["branch"] or t("ui.default_branch"), rel=a["rel_path"]))
        elif a["type"] == "meta":
            parts.append(t("ui.act_meta", fields=", ".join(a["fields"])))
    if plan.get("git_check"):
        c = plan["git_check"]
        state = (t("ui.state_outdated") if c["has_update"]
                 else t("ui.state_up_to_date") if c["has_update"] is False
                 else t("ui.state_unknown"))
        parts.append(t("ui.git_compare", local=c["local_commit"][:8] or "-",
                       remote=c["remote_commit"][:8] if c["remote_commit"] else "-", state=state))
    for w in plan["warnings"]:
        parts.append(f"⚠ {w}")
    return "\n".join(parts)


def human_update_done(result):
    rec = result["record"]
    print(t("ui.update_done", id=rec["id"], name=rec["name"], lines=rec["lines"],
            updated=rec["updated_at"]))
    if result["summary"].get("backup"):
        print(t("ui.update_backup", backup=result["summary"]["backup"]))


def human_check_only(rec, data):
    c = data.get("git_check") or {}
    print(t("ui.check_header", id=rec["id"], name=rec["name"]))
    print(t("ui.check_local", c=c.get("local_commit") or "-"))
    print(t("ui.check_remote", c=c.get("remote_commit") or "-"))
    state = (t("ui.state_outdated") if c.get("has_update")
             else t("ui.state_up_to_date") if c.get("has_update") is False
             else t("ui.state_unknown"))
    print(t("ui.check_status", state=state))


def human_git_all_done(result):
    print(t("ui.git_all_done", a=len(result["updated"]), b=result["unchanged"],
            c=len(result["failed"]), d=len(result.get("check_errors", []))))
    for r in result["updated"]:
        c = (r.get("git") or {}).get("commit") or "-"
        print(f"  ✓ id={r['id']} {r['name']} -> {r['lines']} @ {c[:8]}")
    for f in result["failed"]:
        print(f"  ✗ id={f['id']} {f['name']}: {f['error']}")
    for f in result.get("check_errors", []):
        print(f"  ! id={f['id']} {f['name']}: {f['error']}")
    if not result["updated"] and not result["failed"] and not result.get("check_errors"):
        print(t("ui.git_all_none"))
