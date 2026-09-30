"""字典文件流式操作：统计、替换、追加、按行读取。

一律按字节处理、不做转码（兼容 GBK 等任意编码的字典）；显示时才尝试 UTF-8 解码。
所有函数流式处理，GB 级文件内存占用恒定。
"""
from __future__ import annotations

import hashlib
import os
import shutil
from collections import deque

CHUNK = 1 << 20  # 1MB

WORDLIST_SEPARATORS = b"\r\n"


def stream_md5(path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def count_lines(path) -> int:
    total, last = 0, b""
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            total += chunk.count(b"\n")
            last = chunk[-1:]
    # 末尾无换行符的最后一行也算一行；空文件为 0 行
    if last and last != b"\n":
        total += 1
    return total


def file_stats(path) -> dict:
    return {
        "size": os.path.getsize(path),
        "lines": count_lines(path),
        "md5": stream_md5(path),
    }


def _ends_with_newline(path, size: int) -> bool:
    if size <= 0:
        return True
    with open(path, "rb") as f:
        f.seek(size - 1)
        return f.read(1) == b"\n"


def append_bytes(path, data: bytes):
    size = os.path.getsize(path) if os.path.exists(path) else 0
    with open(path, "ab") as f:
        if size > 0 and not _ends_with_newline(path, size):
            f.write(b"\n")  # 保证追加内容独立成行，不与原最后一行粘连
        f.write(data)


def append_text(path, text: str):
    text = text.replace("\r\n", "\n")
    if not text.endswith("\n"):
        text += "\n"
    append_bytes(path, text.encode("utf-8"))


def append_file(path, src):
    with open(src, "rb") as s:
        append_bytes(path, s.read())


def replace_file(dst, src):
    shutil.copy2(src, dst)


def _decode(line: bytes) -> str:
    return line.decode("utf-8", errors="replace").rstrip("\r\n")


def iter_binary_lines(path):
    with open(path, "rb") as f:
        yield from f


def read_line_range(path, start: int, end) -> list:
    """1-based 闭区间 [start, end]；end 为 None 时到文件尾。"""
    if end is not None and end < start:
        start, end = end, start
    start = max(1, start)
    out = []
    for i, line in enumerate(iter_binary_lines(path), 1):
        if i < start:
            continue
        if end is not None and i > end:
            break
        out.append((i, _decode(line)))
    return out


def head_lines(path, n: int) -> list:
    out = []
    for i, line in enumerate(iter_binary_lines(path), 1):
        if i > n:
            break
        out.append((i, _decode(line)))
    return out


def tail_lines(path, n: int) -> list:
    d = deque(maxlen=max(1, n))
    for i, line in enumerate(iter_binary_lines(path), 1):
        d.append((i, _decode(line)))
    return list(d)


def grep_lines(path, needle: str, limit: int = 1000):
    """大小写不敏感的子串匹配，返回 (matches, truncated)。"""
    needle_l = needle.lower()
    out, truncated = [], False
    for i, line in enumerate(iter_binary_lines(path), 1):
        t = _decode(line)
        if needle_l in t.lower():
            if len(out) >= limit:
                truncated = True
                break
            out.append((i, t))
    return out, truncated
