"""SQLite 存储层：建表、CRUD、查询、导出导入。

每个方法独立建短连接，天然线程安全；WAL 模式支持并发读。
"""
from __future__ import annotations

import json
import sqlite3

from ..i18n import t
from .models import SCHEMA_VERSION, VALIDATION, DictError, normalize_category, normalize_tags, now_str, tags_to_json

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dicts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    tags          TEXT DEFAULT '[]',
    instructions  TEXT DEFAULT '',
    source        TEXT DEFAULT '',
    category      TEXT DEFAULT '',
    storage_mode  TEXT NOT NULL DEFAULT 'copy',
    file_path     TEXT NOT NULL DEFAULT '',
    original_path TEXT DEFAULT '',
    size          INTEGER DEFAULT 0,
    lines         INTEGER DEFAULT 0,
    md5           TEXT DEFAULT '',
    git_url       TEXT DEFAULT '',
    git_branch    TEXT DEFAULT '',
    git_commit    TEXT DEFAULT '',
    git_rel_path  TEXT DEFAULT '',
    git_synced_at TEXT DEFAULT '',
    created_at    TEXT DEFAULT '',
    updated_at    TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_dicts_name ON dicts(name);
CREATE INDEX IF NOT EXISTS idx_dicts_category ON dicts(category);
CREATE INDEX IF NOT EXISTS idx_dicts_md5 ON dicts(md5);
"""

_COLS = (
    "name", "tags", "instructions", "source", "category", "storage_mode",
    "file_path", "original_path", "size", "lines", "md5",
    "git_url", "git_branch", "git_commit", "git_rel_path", "git_synced_at",
    "created_at", "updated_at",
)


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _row_to_dict(row) -> dict:
    d = {k: row[k] for k in row.keys()}
    try:
        d["tags"] = json.loads(d.get("tags") or "[]")
    except json.JSONDecodeError:
        d["tags"] = []
    return d


class Database:
    def __init__(self, path):
        self.path = str(path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def init_schema(self):
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # ---------- 写 ----------

    def insert(self, rec: dict, item_id: int | None = None) -> int:
        rec = dict(rec)
        rec.setdefault("tags", [])
        rec.setdefault("instructions", "")
        rec.setdefault("source", "")
        rec.setdefault("category", "")
        rec.setdefault("storage_mode", "copy")
        rec.setdefault("file_path", "")
        rec.setdefault("original_path", "")
        rec.setdefault("size", 0)
        rec.setdefault("lines", 0)
        rec.setdefault("md5", "")
        rec["category"] = normalize_category(rec["category"])
        for g in ("git_url", "git_branch", "git_commit", "git_rel_path", "git_synced_at"):
            rec.setdefault(g, "")
        rec.setdefault("created_at", now_str())
        rec.setdefault("updated_at", rec["created_at"])
        cols, vals = [], []
        for c in _COLS:
            v = rec[c]
            if c == "tags":
                v = tags_to_json(normalize_tags(v))
            cols.append(c)
            vals.append(v)
        if item_id is not None:
            cols.append("id")
            vals.append(item_id)
        conn = self._connect()
        try:
            cur = conn.execute(
                f"INSERT INTO dicts ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                vals,
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def update(self, item_id: int, fields: dict):
        sets, vals = [], []
        for k, v in fields.items():
            if k not in _COLS or k == "id":
                continue
            if k == "tags":
                v = tags_to_json(normalize_tags(v))
            elif k == "category":
                v = normalize_category(v)
            sets.append(f"{k} = ?")
            vals.append(v)
        if not sets:
            return
        conn = self._connect()
        try:
            conn.execute(f"UPDATE dicts SET {', '.join(sets)} WHERE id = ?", [*vals, item_id])
            conn.commit()
        finally:
            conn.close()

    def delete(self, item_id: int):
        conn = self._connect()
        try:
            conn.execute("DELETE FROM dicts WHERE id = ?", (item_id,))
            conn.commit()
        finally:
            conn.close()

    def replace_all(self, recs: list):
        """import --replace：清空后整批写入（保留原 id）。"""
        conn = self._connect()
        try:
            conn.execute("DELETE FROM dicts")
            try:
                conn.execute("DELETE FROM sqlite_sequence WHERE name = 'dicts'")
            except sqlite3.OperationalError:
                pass
            for rec in recs:
                row = dict(rec)
                row["tags"] = tags_to_json(normalize_tags(row.get("tags")))
                row["category"] = normalize_category(row.get("category"))  # 旧导出里的中文分类自动归一
                cols = [c for c in _COLS if c in row] + (["id"] if "id" in row else [])
                vals = [row[c] for c in cols]
                conn.execute(
                    f"INSERT INTO dicts ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                    vals,
                )
            conn.commit()
        finally:
            conn.close()

    # ---------- 读 ----------

    def get(self, item_id: int):
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM dicts WHERE id = ?", (item_id,)).fetchone()
            return _row_to_dict(row) if row else None
        finally:
            conn.close()

    def find_by_md5(self, md5: str) -> list:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM dicts WHERE md5 = ? ORDER BY id", (md5,)).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def search(self, keyword=None, tag=None, category=None) -> list:
        """模糊查询：多个关键词 AND，单关键词对 name/instructions/source/category/tags 取 OR。"""
        where, params = [], []
        if keyword:
            for kw in str(keyword).split():
                pat = f"%{_escape_like(kw)}%"
                where.append(
                    "(name LIKE ? ESCAPE '\\' OR instructions LIKE ? ESCAPE '\\'"
                    " OR source LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\'"
                    " OR tags LIKE ? ESCAPE '\\')"
                )
                params += [pat] * 5
        if tag:
            where.append("tags LIKE ? ESCAPE '\\'")
            params.append(f'%"{_escape_like(tag)}"%')
        if category:
            where.append("category = ?")
            params.append(normalize_category(category))
        sql = "SELECT * FROM dicts"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id"
        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def all(self) -> list:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM dicts ORDER BY id").fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def count(self) -> int:
        conn = self._connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM dicts").fetchone()[0]
        finally:
            conn.close()

    # ---------- 导出/导入 ----------

    def export_all(self) -> dict:
        recs = self.all()
        return {
            "schema_version": SCHEMA_VERSION,
            "exported_at": now_str(),
            "count": len(recs),
            "dicts": recs,
        }

    def import_data(self, data: dict, replace: bool = False) -> dict:
        dicts = data.get("dicts")
        if dicts is None and isinstance(data.get("data"), dict):
            dicts = data["data"].get("dicts")
        if not isinstance(dicts, list):
            raise DictError(VALIDATION, t("err.import_invalid"))
        if replace:
            self.replace_all(dicts)
            return {"imported": len(dicts), "replaced": True, "total_after": self.count()}
        imported = 0
        for rec in dicts:
            if not isinstance(rec, dict) or not rec.get("name"):
                continue
            row = dict(rec)
            row["tags"] = normalize_tags(row.get("tags"))
            explicit_id = row.pop("id", None)
            if explicit_id is not None and self.get(explicit_id) is None:
                self.insert(row, item_id=explicit_id)  # 原主键空闲则保留
            else:
                self.insert(row)  # 冲突或缺失时走自增
            imported += 1
        return {"imported": imported, "replaced": False, "total_after": self.count()}
