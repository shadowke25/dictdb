"""托管存储：store 副本目录、路径解析、备份、last_search 序号缓存。"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from ..i18n import t
from .models import NOT_FOUND, DictError, now_str

# 文件名安全字符：字母数字下划线点横线 + 中文
_SAFE_NAME = re.compile(r"[^\w.\-]+", re.UNICODE)


class Storage:
    def __init__(self, data_home):
        self.data_home = Path(data_home)
        self.store_dir = self.data_home / "store"
        self.export_dir = self.data_home / "export"
        self.db_path = self.data_home / "dictdb.db"
        self.last_search_path = self.data_home / "last_search.json"
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def store_filename(self, item_id: int, name: str, ext: str) -> str:
        base = _SAFE_NAME.sub("_", name).strip("._") or "dict"
        return f"{item_id:04d}-{base}{ext}"

    def import_file(self, src: Path, item_id: int, name: str) -> str:
        """把源文件复制进 store，返回相对路径（正斜杠，便于跨平台记录）。"""
        dst = self.store_dir / self.store_filename(item_id, name, Path(src).suffix)
        shutil.copy2(src, dst)
        return f"store/{dst.name}"

    def abs_path(self, rec: dict) -> Path:
        """copy 模式 -> store 内副本；link 模式 -> 原文件绝对路径。"""
        if rec.get("storage_mode") == "link":
            return Path(rec.get("file_path") or rec.get("original_path") or "")
        return self.data_home / rec.get("file_path", "")

    def backup(self, abs_file: Path):
        """修改前留 .bak，返回备份路径；文件不存在返回 None。"""
        if abs_file.exists():
            bak = Path(str(abs_file) + ".bak")
            shutil.copy2(abs_file, bak)
            return bak
        return None

    def delete_copy(self, rec: dict):
        if rec.get("storage_mode") != "copy":
            return
        p = self.abs_path(rec)
        for f in (p, Path(str(p) + ".bak")):
            try:
                f.unlink()
            except FileNotFoundError:
                pass

    # ---------- last_search 序号缓存 ----------

    def save_last_search(self, ids, query: str = ""):
        data = {"command": "select", "ids": list(ids), "query": query, "saved_at": now_str()}
        self.last_search_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load_last_search(self) -> list:
        try:
            data = json.loads(self.last_search_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise DictError(NOT_FOUND, t("err.no_search_cache"))
        except json.JSONDecodeError:
            return []
        return data.get("ids", [])
