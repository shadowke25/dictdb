"""git 集成：仓库探测、远端版本比对、浅克隆取文件。全部通过系统 git 完成。

copy 模式的字典更新走「临时浅克隆 + 取目标文件」，不碰用户自己的仓库；
link 模式才会在用户仓库内执行 pull。
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..i18n import t
from .models import DictError, GIT_ERROR


def git_available() -> bool:
    return shutil.which("git") is not None


def _run(args, cwd=None, timeout=120):
    try:
        p = subprocess.run(
            [str(a) for a in args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise DictError(GIT_ERROR, t("err.git_missing"), http_status=500)
    except subprocess.TimeoutExpired:
        raise DictError(GIT_ERROR, t("err.git_timeout", cmd=" ".join(str(a) for a in args[:3])),
                        http_status=504)
    out = p.stdout.decode("utf-8", errors="replace").strip()
    err = p.stderr.decode("utf-8", errors="replace").strip()
    return p.returncode, out, err


def find_repo(start_dir) -> Path | None:
    """从文件所在目录向上逐级查找 .git，返回仓库根目录。"""
    d = Path(start_dir).resolve()
    while True:
        if (d / ".git").exists():
            return d
        parent = d.parent
        if parent == d:
            return None
        d = parent


def repo_info(repo, file_abs) -> dict:
    repo, file_abs = Path(repo).resolve(), Path(file_abs).resolve()
    rel_path = ""
    try:
        rel_path = file_abs.relative_to(repo).as_posix()
    except ValueError:
        pass

    url = ""
    rc, out, _ = _run(["git", "-C", repo, "remote", "get-url", "origin"])
    if rc == 0:
        url = out
    else:
        _, remotes, _ = _run(["git", "-C", repo, "remote"])
        for name in remotes.splitlines():
            name = name.strip()
            if not name:
                continue
            rc2, out2, _ = _run(["git", "-C", repo, "remote", "get-url", name])
            if rc2 == 0:
                url = out2
                break

    _, branch, _ = _run(["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"])
    _, commit, _ = _run(["git", "-C", repo, "rev-parse", "HEAD"])
    return {"url": url, "branch": branch, "commit": commit, "rel_path": rel_path}


def ls_remote_commit(url: str, branch: str = "") -> str:
    spec = f"refs/heads/{branch}" if branch else "HEAD"
    rc, out, err = _run(["git", "ls-remote", url, spec], timeout=60)
    if rc != 0:
        raise DictError(GIT_ERROR, t("err.ls_remote_failed", detail=err or out))
    return out.split()[0] if out else None


def check_update(url: str, branch: str, local_commit: str) -> dict:
    remote = ls_remote_commit(url, branch)
    return {
        "remote_commit": remote,
        "local_commit": local_commit or "",
        "has_update": bool(remote and local_commit and remote != local_commit) if remote is not None else None,
    }


def clone_file(url: str, branch: str, rel_path: str, dest, timeout=600):
    """浅克隆到临时目录并取出 rel_path 文件复制到 dest，不动用户自己的仓库。"""
    with tempfile.TemporaryDirectory(prefix="dictdb-git-") as tmp:
        args = ["git", "clone", "--depth", "1", "--single-branch"]
        if branch:
            args += ["--branch", branch]
        args += [url, tmp]
        rc, _, err = _run(args, timeout=timeout)
        if rc != 0:
            raise DictError(GIT_ERROR, t("err.clone_failed", detail=err[:300]))
        src = Path(tmp) / rel_path
        if not src.exists():
            raise DictError(GIT_ERROR, t("err.clone_file_missing", url=url, rel=rel_path))
        shutil.copy2(src, dest)


def pull(repo, timeout=600):
    rc, _, err = _run(["git", "-C", str(repo), "pull", "--ff-only"], timeout=timeout)
    if rc != 0:
        raise DictError(GIT_ERROR, t("err.pull_failed", detail=err[:300]))
