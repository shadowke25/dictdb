"""数据模型、字段规范与统一错误类型。"""
from __future__ import annotations

import json
import re
from datetime import datetime

from ..i18n import t

SCHEMA_VERSION = 1

# 机器可读错误码（对应 JSON 信封 error.code）
NOT_FOUND = "NOT_FOUND"
VALIDATION = "VALIDATION"
CONFLICT = "CONFLICT"
GIT_ERROR = "GIT_ERROR"
IO_ERROR = "IO_ERROR"
CANCELLED = "CANCELLED"
CONFIRM_REQUIRED = "CONFIRM_REQUIRED"
SERVER_ERROR = "SERVER_ERROR"

# 分类英文枚举与别名映射（存储与筛选统一为英文 slug，中文输入自动转换）
CATEGORY_ALIASES = {
    "dir": ("dir", "directory", "目录", "目录爆破", "路径"),
    "api": ("api", "接口", "api路径"),
    "password": ("password", "pass", "pwd", "密码", "弱口令"),
    "username": ("username", "user", "用户名", "账户", "账号"),
    "subdomain": ("subdomain", "sub", "子域", "子域名"),
    "param": ("param", "参数", "参数fuzz"),
    "fuzz": ("fuzz", "模糊测试"),
    "other": ("other", "其他", "其它"),
}
CATEGORY_SLUGS = tuple(CATEGORY_ALIASES)


def normalize_category(value) -> str:
    """分类归一：别名/大小写 → 英文 slug；未知值小写、空白转下划线后保留（允许自定义）。"""
    if value is None:
        return ""
    v = str(value).strip().lower()
    if not v:
        return ""
    for slug, aliases in CATEGORY_ALIASES.items():
        if v in aliases:
            return slug
    return re.sub(r"\s+", "_", v)


class DictError(Exception):
    """业务错误：携带机器可读 code，供 JSON 信封与退出码使用。"""

    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_tags(value) -> list:
    """兼容 "a,b" 字符串 / list / None，去空去重保序。"""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [t.strip() for t in value.replace("，", ",").split(",")]
    else:
        parts = [str(t).strip() for t in value]
    seen, out = set(), []
    for t in parts:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def tags_to_json(tags) -> str:
    return json.dumps(normalize_tags(tags), ensure_ascii=False)


def parse_id(value) -> int:
    """主键/序号统一按整数解析，接受 072111 这类前导零形式。"""
    try:
        return int(str(value).strip())
    except ValueError:
        raise DictError(VALIDATION, t("err.bad_number", value=value))


def parse_target(value) -> tuple:
    """统一选择器：'7' → ('id', 7) 主键；'@2' → ('index', 2) 最近搜索序号。"""
    v = str(value).strip()
    if v.startswith("@"):
        n = parse_id(v[1:])
        if n < 1:
            raise DictError(VALIDATION, t("err.bad_at_index", value=value))
        return ("index", n)
    return ("id", parse_id(v))


def record_to_public(rec: dict, abs_path: str, index=None, has_update=None, check_error=None) -> dict:
    """SQLite 行记录 -> 对外 JSON 表示（AI/工具直接可用，path 为绝对路径）。"""
    git = None
    if rec.get("git_url"):
        git = {
            "url": rec["git_url"],
            "branch": rec.get("git_branch", ""),
            "commit": rec.get("git_commit", ""),
            "synced_at": rec.get("git_synced_at", ""),
            "has_update": has_update,
        }
        if check_error:
            git["check_error"] = check_error
    out = {
        "id": rec["id"],
        "name": rec["name"],
        "category": rec.get("category", ""),
        "tags": rec.get("tags", []),
        "instructions": rec.get("instructions", ""),
        "source": rec.get("source", ""),
        "storage_mode": rec.get("storage_mode", "copy"),
        "path": abs_path,
        "original_path": rec.get("original_path", ""),
        "size": rec.get("size", 0),
        "lines": rec.get("lines", 0),
        "md5": rec.get("md5", ""),
        "git": git,
        "created_at": rec.get("created_at", ""),
        "updated_at": rec.get("updated_at", ""),
    }
    if index is not None:
        out["index"] = index
    return out
