"""dictdb 全量测试套件：CLI 全命令 / 输出协议 / git 全链路 / export-import / HTTP / 边界与大数据。

运行（项目根目录，使用 uv 管理的 .venv）：
    .venv/Scripts/python -m unittest tests.test_full -v

每个测试类使用独立的 DICTDB_HOME 临时目录，互相隔离、不污染真实数据。
注意：unittest 每个测试方法都是新实例——跨测试共享的数据一律放类属性并在
setUpClass 中初始化，避免重复添加触发 md5 去重拦截。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PY = sys.executable


# ---------- 模块级工具（setUpClass / 类方法中也能用，不走 TestCase 断言） ----------

def _run_cli(env, *args, stdin=subprocess.DEVNULL, env_extra=None):
    e = dict(env)
    if env_extra:
        e.update(env_extra)
    return subprocess.run(
        [PY, "-m", "dictdb", *[str(a) for a in args]],
        stdin=stdin, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        cwd=str(PROJECT), env=e, timeout=300,
    )


def _jrun(env, *args, expect=0, stdin=subprocess.DEVNULL, env_extra=None):
    p = _run_cli(env, *args, stdin=stdin, env_extra=env_extra)
    assert p.returncode == expect, (
        f"cmd={args}\nrc={p.returncode}\nstdout={p.stdout[:600]}\nstderr={p.stderr[:600]}"
    )
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        raise AssertionError(f"stdout 不是 JSON：{p.stdout[:400]!r} / stderr: {p.stderr[:400]!r}")


def _add(env, path, name, flags=(), **kw):
    args = ["add", str(path), "--name", name]
    args += [f"--{f}" for f in flags]
    for k, v in kw.items():
        args += [f"--{k.replace('_', '-')}", str(v)]
    return _jrun(env, *args)["data"]["id"]


def _make(fixtures, name, content: str) -> Path:
    p = Path(fixtures) / name
    p.write_bytes(content.encode("utf-8"))
    return p


class Base(unittest.TestCase):
    """测试基类：每类独立 DICTDB_HOME，进程外调用 CLI 并校验 JSON 信封。"""

    @classmethod
    def setUpClass(cls):
        cls.data_home = Path(tempfile.mkdtemp(prefix="dictdb-t-"))
        cls.fixtures = Path(tempfile.mkdtemp(prefix="dictdb-fix-"))
        cls.env = dict(os.environ)
        cls.env["DICTDB_HOME"] = str(cls.data_home)
        cls.env["PYTHONIOENCODING"] = "utf-8"
        cls.env["DICTDB_LANG"] = "zh"  # 默认中文（含既有中文文案断言）；英文用例见 TestI18n

    @classmethod
    def tearDownClass(cls):
        for d in (cls.data_home, cls.fixtures):
            shutil.rmtree(d, ignore_errors=True)

    # ---------- CLI 调用（实例便捷封装） ----------

    def run_cli(self, *args, stdin=subprocess.DEVNULL, env_extra=None):
        return _run_cli(self.env, *args, stdin=stdin, env_extra=env_extra)

    def jrun(self, *args, expect=0, env_extra=None):
        return _jrun(self.env, *args, expect=expect, env_extra=env_extra)

    def ecode(self, *args):
        return self.run_cli(*args).returncode

    def add(self, path, name, flags=(), **kw):
        return _add(self.env, path, name, flags, **kw)

    def make(self, name, content: str) -> Path:
        return _make(self.fixtures, name, content)

    def git(self, *args, cwd):
        p = subprocess.run(
            ["git", *[str(a) for a in args]], cwd=str(cwd),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, timeout=120,
        )
        self.assertEqual(p.returncode, 0, f"git {args} 失败：{p.stderr[:400]}")
        return p.stdout.strip()


class TestAdd(Base):
    def test_copy_mode_record_fields(self):
        src = self.make("dir.txt", "admin\nlogin\nbackup\n.php\nconfig\n")
        env = self.jrun("add", src, "--name", "目录字典", "--tags", "目录,fuzz",
                        "--instructions", "测试字典", "--source", "手工", "--category", "目录")
        self.assertTrue(env["ok"])
        self.assertEqual(env["command"], "add")
        self.assertEqual(env["schema_version"], 1)
        d = env["data"]
        for key in ("id", "name", "category", "tags", "instructions", "source",
                    "storage_mode", "path", "original_path", "size", "lines",
                    "md5", "git", "created_at", "updated_at"):
            self.assertIn(key, d)
        self.assertEqual(d["name"], "目录字典")
        self.assertEqual(d["tags"], ["目录", "fuzz"])
        self.assertEqual(d["lines"], 5)
        self.assertEqual(d["storage_mode"], "copy")
        self.assertTrue(os.path.isabs(d["path"]))
        self.assertTrue(Path(d["path"]).exists())
        self.assertIn("store", Path(d["path"]).parts)
        self.assertTrue(Path(d["path"]).name.startswith(f"{d['id']:04d}-"))
        self.assertEqual(len(d["md5"]), 32)
        self.assertTrue(d["created_at"] and d["updated_at"])
        self.assertIsNone(d["git"])

    def test_link_mode(self):
        src = self.make("link_dict.txt", "a\nb\n")
        before = len(list((self.data_home / "store").glob("*")))
        d = self.jrun("add", src, "--name", "链接字典", "--link")["data"]
        self.assertEqual(d["storage_mode"], "link")
        self.assertEqual(Path(d["path"]).resolve(), src.resolve())
        after = len(list((self.data_home / "store").glob("*")))
        self.assertEqual(after, before)  # link 不复制进 store

    def test_dedup_conflict_and_force(self):
        src = self.make("dup.txt", "same\ncontent\n")
        self.add(src, "第一份")
        p = self.run_cli("add", src, "--name", "第二份")
        self.assertEqual(p.returncode, 1)
        err = json.loads(p.stdout)["error"]
        self.assertEqual(err["code"], "CONFLICT")
        self.assertIn("md5", err["message"])
        self.jrun("add", src, "--name", "第二份", "--force")  # --force 放行

    def test_missing_name_validation(self):
        src = self.make("noname.txt", "x\n")
        p = self.run_cli("add", src)  # 非交互 stdin → 跳过提示 → VALIDATION
        self.assertEqual(p.returncode, 2)
        self.assertEqual(json.loads(p.stdout)["error"]["code"], "VALIDATION")

    def test_path_not_found(self):
        p = self.run_cli("add", "Z:\\不存在的路径\\nope.txt", "--name", "x")
        self.assertEqual(p.returncode, 1)
        self.assertEqual(json.loads(p.stdout)["error"]["code"], "NOT_FOUND")

    def test_tags_normalize(self):
        d = self.jrun("add", self.make("tags.txt", "t\n"),
                      "--name", "标签字典", "--tags", "目录, fuzz ,目录")["data"]
        self.assertEqual(d["tags"], ["目录", "fuzz"])

    def test_git_detection(self):
        repo = Path(tempfile.mkdtemp(prefix="dictdb-repo-"))
        try:
            self.git("init", "-q", "--bare", "-b", "master", "remote.git", cwd=repo)
            self.git("clone", "-q", "remote.git", "work", cwd=repo)
            work = repo / "work"
            (work / "wl.txt").write_text("a\nb\nc\n", encoding="utf-8")
            self.git("add", ".", cwd=work)
            self.git("-c", "user.email=t@t.local", "-c", "user.name=tester",
                     "commit", "-qm", "v1", cwd=work)
            self.git("push", "-q", "origin", "master", cwd=work)
            d = self.jrun("add", work / "wl.txt", "--name", "git字典")["data"]
            self.assertIsNotNone(d["git"])
            self.assertTrue(d["git"]["url"].endswith("remote.git"))
            self.assertEqual(d["git"]["branch"], "master")
            self.assertEqual(len(d["git"]["commit"]), 40)
            self.assertTrue(d["git"]["synced_at"])
        finally:
            shutil.rmtree(repo, ignore_errors=True)

    def test_crlf_and_no_trailing_newline(self):
        self.assertEqual(self.jrun("add", self.make("crlf.txt", "a\r\nb\r\n"),
                                   "--name", "crlf")["data"]["lines"], 2)
        self.assertEqual(self.jrun("add", self.make("notrail.txt", "x\ny"),
                                   "--name", "notrail")["data"]["lines"], 2)

    def test_empty_file(self):
        d = self.jrun("add", self.make("empty.txt", ""), "--name", "空字典")["data"]
        self.assertEqual(d["lines"], 0)
        self.assertEqual(d["size"], 0)

    def test_chinese_and_space_filename(self):
        src = self.make("测试 字典 01.txt", "内容\n")
        d = self.jrun("add", src, "--name", "中文空格名")["data"]
        self.assertTrue(Path(d["path"]).exists())
        self.assertNotIn(" ", Path(d["path"]).name)  # store 文件名已清洗


class TestV15(Base):
    """v1.5：select JSON 默认投影 / --full / show 缺省限流与 --head 0。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.did = _add(cls.env, _make(cls.fixtures, "p1.txt", "a\nb\nc\n"), "投影字典",
                       instructions="x" * 60)  # 60 字符说明，验证截断到 50

    def test_select_default_projection(self):
        d = self.jrun("select", "--id", str(self.did))["data"][0]
        self.assertEqual(set(d.keys()),
                         {"index", "id", "name", "category", "tags", "instructions",
                          "lines", "path", "updated_at"})
        self.assertEqual(len(d["instructions"]), 51)  # 截断 50 + 省略号
        self.assertTrue(d["instructions"].endswith("…"))
        self.assertTrue(os.path.isabs(d["path"]))
        for gone in ("md5", "git", "original_path", "size", "storage_mode",
                     "source", "created_at"):
            self.assertNotIn(gone, d)

    def test_full_flag_outputs_all_fields(self):
        d = self.jrun("select", "--id", str(self.did), "--full")["data"][0]
        self.assertIn("md5", d)
        self.assertIn("git", d)
        self.assertIn("original_path", d)
        self.assertIn("storage_mode", d)
        self.assertEqual(d["instructions"], "x" * 60)  # --full 不截断

    def test_show_head_zero_means_full(self):
        d = self.jrun("show", str(self.did), "--head", "0")["data"]
        self.assertEqual(d["mode"], "all")
        self.assertEqual(d["count"], 3)  # 全文 3 行
        self.assertFalse(d["default_limited"])

    def test_show_default_limited_and_hint(self):
        d = self.jrun("show", str(self.did))["data"]
        self.assertEqual(d["mode"], "head")
        self.assertEqual(d["count"], 3)  # 文件仅 3 行，20 行上限未触顶
        self.assertTrue(d["default_limited"])
        p = self.run_cli("--table", "show", str(self.did))
        self.assertIn("默认仅显示前 20 行", p.stdout)  # 中文环境的缺省限流提示


class TestSelect(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.id1 = _add(cls.env, _make(cls.fixtures, "s1.txt", "a\n"), "alpha密码",
                       instructions="目录爆破用", tags="目录", category="目录")
        _add(cls.env, _make(cls.fixtures, "s2.txt", "b\n"), "beta子域", tags="子域", category="子域")
        _add(cls.env, _make(cls.fixtures, "s3.txt", "c\n"), "gamma接口", tags="接口,api", category="接口")

    def test_list_all_with_index(self):
        env = self.jrun("select")
        self.assertEqual(env["count"], 3)
        self.assertEqual([r["index"] for r in env["data"]], [1, 2, 3])
        cache = json.loads((self.data_home / "last_search.json").read_text(encoding="utf-8"))
        self.assertEqual(cache["ids"], [r["id"] for r in env["data"]])

    def test_fuzzy_and_multi_keyword(self):
        self.assertEqual(self.jrun("select", "alpha")["count"], 1)
        self.assertEqual(self.jrun("select", "alpha 密码")["count"], 1)  # 多关键词 AND
        self.assertEqual(self.jrun("select", "alpha 子域")["count"], 0)
        self.assertEqual(self.jrun("select", "爆破")["count"], 1)  # 命中 instructions

    def test_tag_and_category(self):
        self.assertEqual(self.jrun("select", "--tag", "接口")["count"], 1)
        self.assertEqual(self.jrun("select", "--category", "子域")["count"], 1)
        self.assertEqual(self.jrun("select", "--category", "不存在的分类")["count"], 0)

    def test_id_leading_zero(self):
        d = self.jrun("select", "--id", f"{self.id1:06d}")["data"]
        self.assertEqual(d[0]["id"], self.id1)
        self.assertEqual(d[0]["index"], 1)

    def test_id_missing(self):
        p = self.run_cli("select", "--id", "99999")
        self.assertEqual(p.returncode, 1)
        self.assertEqual(json.loads(p.stdout)["error"]["code"], "NOT_FOUND")

    def test_empty_result_breaks_cache(self):
        self.jrun("select", "alpha")
        self.jrun("select", "绝对不存在xyz")  # 覆盖缓存为空
        self.assertEqual(self.ecode("delete", "@1"), 1)


class TestShow(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        src = _make(cls.fixtures, "show_dict.txt", "\n".join(f"line{i}" for i in range(1, 31)) + "\n")
        cls.did = _add(cls.env, src, "show字典")
        big = "\n".join(f"needle{i}" for i in range(1200)) + "\n"
        cls.big_id = _add(cls.env, _make(cls.fixtures, "grep_big.txt", big), "grep大文件")

    def test_range(self):
        d = self.jrun("show", str(self.did), "--lines", "5-8")["data"]
        self.assertEqual(d["mode"], "range")
        self.assertEqual([(l["n"], l["text"]) for l in d["lines"]],
                         [(5, "line5"), (6, "line6"), (7, "line7"), (8, "line8")])

    def test_single_line(self):
        d = self.jrun("show", str(self.did), "--lines", "3")["data"]
        self.assertEqual([l["text"] for l in d["lines"]], ["line3"])

    def test_head_default_and_custom(self):
        self.assertEqual(self.jrun("show", str(self.did))["data"]["count"], 20)
        self.assertEqual(self.jrun("show", str(self.did), "--head", "3")["data"]["count"], 3)

    def test_tail(self):
        d = self.jrun("show", str(self.did), "--tail", "2")["data"]
        self.assertEqual([l["text"] for l in d["lines"]], ["line29", "line30"])

    def test_grep_case_insensitive(self):
        d = self.jrun("show", str(self.did), "--grep", "LINE29")["data"]
        self.assertEqual(d["mode"], "grep")
        self.assertEqual([l["text"] for l in d["lines"]], ["line29"])

    def test_grep_limit_truncated(self):
        d = self.jrun("show", str(self.big_id), "--grep", "needle")["data"]
        self.assertEqual(d["count"], 1000)
        self.assertTrue(d["truncated"])

    def test_list_selector(self):
        self.jrun("select", "show字典")
        d = self.jrun("show", "@1", "--head", "1")["data"]
        self.assertEqual(d["id"], self.did)

    def test_missing_cache(self):
        # 本类未执行过 select 的新实例仍共享类级缓存？缓存文件由其它命令覆写前存在，
        # 这里用全新数据目录验证「无缓存」路径。
        with tempfile.TemporaryDirectory() as home:
            p = self.run_cli("show", "@1", env_extra={"DICTDB_HOME": home})
            self.assertEqual(p.returncode, 1)

    def test_file_lost(self):
        did = self.add(self.make("lost.txt", "z\n"), "丢失字典")
        target = Path(self.jrun("select", "--id", did)["data"][0]["path"])
        os.remove(target)
        p = self.run_cli("show", str(did))
        self.assertEqual(p.returncode, 1)
        self.assertIn("丢失", json.loads(p.stdout)["error"]["message"])


class TestDelete(Base):
    def test_copy_delete_removes_store_file(self):
        did = self.add(self.make("del1.txt", "a\n"), "待删字典")
        path = Path(self.jrun("select", "--id", did)["data"][0]["path"])
        self.assertTrue(path.exists())
        p = self.run_cli("delete", str(did))  # 非交互无 --yes → CONFIRM_REQUIRED
        self.assertEqual(p.returncode, 3)
        self.assertEqual(json.loads(p.stdout)["error"]["code"], "CONFIRM_REQUIRED")
        self.assertTrue(path.exists())  # 未确认前不动文件
        d = self.jrun("delete", f"{did:06d}", "--yes")["data"]  # 前导零主键
        self.assertTrue(d["deleted"])
        self.assertEqual(d["id"], did)
        self.assertFalse(path.exists())
        self.assertEqual(self.ecode("select", "--id", did), 1)

    def test_link_delete_keeps_original(self):
        src = self.make("keepme.txt", "keep\n")
        did = self.add(src, "链接待删", flags=("link",))
        self.jrun("delete", str(did), "--yes")
        self.assertTrue(src.exists())  # link 只删记录不删原文件
        self.assertEqual(self.ecode("select", "--id", did), 1)

    def test_id_not_found(self):
        self.assertEqual(self.ecode("delete", "424242"), 1)

    def test_list_out_of_range(self):
        did = self.add(self.make("del2.txt", "b\n"), "范围字典")
        self.jrun("select", "范围字典")  # 缓存仅 1 条
        self.assertEqual(self.ecode("delete", "@5"), 1)
        self.assertEqual(self.ecode("select", "--id", did), 0)

    def test_list_selector_ok(self):
        did = self.add(self.make("del3.txt", "c\n"), "序号删除")
        self.jrun("select", "序号删除")
        d = self.jrun("delete", "@1", "--yes")["data"]
        self.assertEqual(d["id"], did)


class TestUpdate(Base):
    # 注意：各 fixture 内容必须互不相同，否则触发 md5 去重拦截
    def test_append_text(self):
        did = self.add(self.make("u_app_text.txt", "a1\nb2\nc3\nd4\ne5\nf6\n"), "追加文本")
        d = self.jrun("update", str(did), "--text", "追加的一行", "--yes")["data"]
        self.assertTrue(d["summary"]["changed_file"])
        self.assertEqual(d["record"]["lines"], 7)
        self.assertIsNotNone(d["summary"]["backup"])
        self.assertTrue(Path(d["summary"]["backup"]).exists())
        tail = self.jrun("show", str(did), "--tail", "1")["data"]["lines"]
        self.assertEqual(tail[0]["text"], "追加的一行")

    def test_append_file(self):
        did = self.add(self.make("u_app_file.txt", "a2\nb3\nc4\nd5\ne6\nf7\n"), "追加文件")
        src = self.make("u_more.txt", "x1\nx2\n")
        d = self.jrun("update", str(did), "--append", src, "--yes")["data"]
        self.assertEqual(d["record"]["lines"], 8)

    def test_replace_with_bak(self):
        did = self.add(self.make("u_repl.txt", "a3\nb4\nc5\nd6\ne7\nf8\n"), "替换字典")
        new = self.make("u_new_content.txt", "n1\nn2\nn3\n")
        d = self.jrun("update", str(did), "--replace", new, "--yes")["data"]
        self.assertEqual(d["record"]["lines"], 3)
        self.assertTrue(Path(d["summary"]["backup"]).exists())
        self.assertTrue(Path(d["summary"]["backup"]).name.endswith(".bak"))
        d2 = self.jrun("update", str(did), "--text", "n4", "--yes")["data"]
        self.assertEqual(d2["record"]["lines"], 4)

    def test_replace_missing_source(self):
        did = self.add(self.make("u_rmiss.txt", "r1\n"), "替换缺失")
        self.assertEqual(self.ecode("update", str(did), "--replace", "Z:\\nope.txt", "--yes"), 1)

    def test_append_text_no_trailing_newline(self):
        did = self.add(self.make("u_notrail.txt", "a\nb\nc"), "无尾行")
        d = self.jrun("update", str(did), "--text", "d", "--yes")["data"]
        self.assertEqual(d["record"]["lines"], 4)
        lines = self.jrun("show", str(did), "--lines", "3-4")["data"]["lines"]
        self.assertEqual([l["text"] for l in lines], ["c", "d"])  # 追加不与原末行粘连

    def test_meta(self):
        did = self.add(self.make("u_meta.txt", "m1\n"), "元数据字典")
        d = self.jrun("edit", str(did), "-n", "改名后", "-t", "新标签,测试",
                      "-i", "新说明", "-s", "新来源", "-c", "密码", "--yes")["data"]
        r = d["record"]
        self.assertEqual(r["name"], "改名后")
        self.assertEqual(r["tags"], ["新标签", "测试"])
        self.assertEqual(r["instructions"], "新说明")
        self.assertEqual(r["source"], "新来源")
        self.assertEqual(r["category"], "password")  # 中文别名归一为英文 slug

    def test_meta_invalid_key(self):
        did = self.add(self.make("u_badmeta.txt", "m2\n"), "非法元数据")
        p = self.run_cli("update", str(did), "--meta", "hacker=1", "--yes")
        self.assertEqual(p.returncode, 2)  # --meta 旧旗标已移除 → argparse 参数错误

    def test_noop_and_usage(self):
        did = self.add(self.make("u_noop.txt", "n1\n"), "空更新")
        self.assertEqual(self.ecode("update", str(did)), 2)  # 无操作
        self.assertEqual(self.ecode("update"), 2)  # 无选择器
        self.assertEqual(self.ecode("update", "424242", "--text", "x", "--yes"), 1)


class TestGit(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.repo = Path(tempfile.mkdtemp(prefix="dictdb-git-"))
        cls.git("init", "-q", "--bare", "-b", "master", "remote.git", cwd=cls.repo)
        cls.git("clone", "-q", "remote.git", "work", cwd=cls.repo)
        cls.work = cls.repo / "work"
        (cls.work / "wordlist.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
        cls.git("add", ".", cwd=cls.work)
        cls._commit(cls.work, "v1")
        cls.git("push", "-q", "origin", "master", cwd=cls.work)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(cls.repo, ignore_errors=True)

    @classmethod
    def git(cls, *args, cwd):
        p = subprocess.run(["git", *[str(a) for a in args]], cwd=str(cwd),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        if p.returncode != 0:
            raise AssertionError(f"git {args}: {p.stderr[:300]}")
        return p.stdout.strip()

    @classmethod
    def _commit(cls, repo, message):
        cls.git("-c", "user.email=t@t.local", "-c", "user.name=tester",
                "commit", "-qm", message, cwd=repo)

    def _push_version(self, lines, message):
        (self.work / "wordlist.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.git("add", ".", cwd=self.work)
        self._commit(self.work, message)
        self.git("push", "-q", "origin", "master", cwd=self.work)
        return self.git("rev-parse", "HEAD", cwd=self.work)

    def _git_dict_id(self):
        ids = [r["id"] for r in self.jrun("select", "--full")["data"] if r["git"]]
        self.assertTrue(ids, "库中应有 git 来源字典")
        return ids[0]

    def test_01_check_and_pull(self):
        did = self.add(self.work / "wordlist.txt", "git字典")
        md5_before = self.jrun("select", "--id", did, "--full")["data"][0]["md5"]
        v2 = self._push_version(["alpha", "beta", "gamma", "delta", "epsilon-新增行"], "v2")
        # --check 只比对不改动
        d = self.jrun("git", "check", str(did))["data"]
        self.assertTrue(d["git_check"]["has_update"])
        self.assertEqual(d["git_check"]["remote_commit"], v2)
        self.assertEqual(self.jrun("select", "--id", did, "--full")["data"][0]["md5"], md5_before)
        # 拉取覆盖副本
        d = self.jrun("git", "pull", str(did), "--yes")["data"]
        self.assertEqual(d["record"]["lines"], 5)
        self.assertEqual(d["record"]["git"]["commit"], v2)
        self.assertIsNotNone(d["summary"]["backup"])
        # outdated 归零；无更新时再次拉取内容不变
        outdated = [r for r in self.jrun("git", "status")["data"] if r["id"] == did]
        self.assertEqual(outdated[0]["git"]["has_update"], False)
        d = self.jrun("git", "pull", str(did), "--yes")["data"]
        self.assertFalse(d["updated"])  # 无更新，内容不变

    def test_02_git_all(self):
        did = self._git_dict_id()
        v3 = self._push_version([f"word{i}" for i in range(6)], "v3")
        p = self.run_cli("git", "pull")  # 有更新、非交互无 --yes
        self.assertEqual(
            p.returncode, 3,
            f"rc={p.returncode}\nstdout={p.stdout[:500]}\nstderr={p.stderr[:500]}",
        )
        d = self.jrun("git", "pull", "--yes")["data"]
        self.assertEqual(len(d["updated"]), 1)
        self.assertEqual(d["updated"][0]["id"], did)
        self.assertEqual(d["updated"][0]["lines"], 6)
        self.assertEqual(d["updated"][0]["git"]["commit"], v3)
        self.assertEqual(d["unchanged"], 0)
        d = self.jrun("git", "pull", "--yes")["data"]
        self.assertEqual(len(d["updated"]), 0)
        self.assertEqual(d["unchanged"], 1)

    def test_03_link_pull(self):
        # 用独立文件 linklist.txt，避免与 wordlist.txt 字典内容相同触发 md5 去重
        self.git("clone", "-q", "remote.git", "work3", cwd=self.repo)
        work3 = self.repo / "work3"
        (work3 / "linklist.txt").write_text("l0\nl1\nl2\n", encoding="utf-8")
        self.git("add", ".", cwd=work3)
        self._commit(work3, "v4-linkfile")
        self.git("push", "-q", "origin", "master", cwd=work3)
        did = self.add(work3 / "linklist.txt", "链接git字典", flags=("link",))
        # 远端推进新版本：work 先 ff 拉下 v4，再叠加 v5 推送（避免 add/add 冲突）
        self.git("pull", "-q", "origin", "master", cwd=self.work)
        (self.work / "linklist.txt").write_text(
            "\n".join(f"L{i}" for i in range(7)) + "\n", encoding="utf-8")
        self.git("add", ".", cwd=self.work)
        self._commit(self.work, "v5-linkfile")
        self.git("push", "-q", "origin", "master", cwd=self.work)
        v5 = self.git("rev-parse", "HEAD", cwd=self.work)
        # link 模式：在原仓库内执行 pull
        d = self.jrun("git", "pull", str(did), "--yes")["data"]
        self.assertEqual(d["record"]["storage_mode"], "link")
        self.assertEqual(d["record"]["lines"], 7)
        self.assertEqual(d["record"]["git"]["commit"], v5)
        self.assertIn("L6", (work3 / "linklist.txt").read_text(encoding="utf-8"))

    def test_04_non_git_dict_rejected(self):
        did = self.add(self.make("plain.txt", "p\n"), "普通字典")
        p = self.run_cli("git", "pull", str(did), "--yes")
        self.assertEqual(p.returncode, 2)
        self.assertEqual(json.loads(p.stdout)["error"]["code"], "VALIDATION")

    def test_05_outdated_human_table(self):
        # 回归：--table 模式下 outdated 表格需要 index 字段（曾因缺失 KeyError）
        p = self.run_cli("--table", "git", "status")
        self.assertEqual(p.returncode, 0, p.stderr[:300])
        self.assertIn("序号", p.stdout)
        self.assertIn("有更新", p.stdout)

    def test_06_git_command_group(self):
        did = self._git_dict_id()
        # 先把基线拉平：批量拉取全部落后项
        d = self.jrun("git", "pull", "--yes")["data"]
        self.assertGreaterEqual(len(d["updated"]) + d["unchanged"], 1)
        # status 表格视图
        p = self.run_cli("--table", "git", "status")
        self.assertEqual(p.returncode, 0, p.stderr[:300])
        self.assertIn("git字典", p.stdout)
        # 已最新时单条 pull：updated False
        d = self.jrun("git", "pull", str(did), "--yes")
        self.assertEqual(d["command"], "git_pull")
        self.assertFalse(d["data"]["updated"])
        # 推进远端 → check 有更新 → pull 拉取
        v6 = self._push_version([f"gg{i}" for i in range(8)], "v6")
        d = self.jrun("git", "check", str(did))["data"]
        self.assertTrue(d["git_check"]["has_update"])
        self.assertEqual(d["git_check"]["remote_commit"], v6)
        d = self.jrun("git", "pull", str(did), "--yes")["data"]
        self.assertEqual(d["record"]["lines"], 8)
        self.assertEqual(d["record"]["git"]["commit"], v6)
        # 批量：链接git字典落后 → 非交互确认拦截 → --yes 拉平 → 再跑全为最新
        p = self.run_cli("git", "pull")
        self.assertEqual(p.returncode, 3)
        self.jrun("git", "pull", "--yes")
        d = self.jrun("git", "pull", "--yes")["data"]
        self.assertEqual(len(d["updated"]), 0)


class TestExportImport(Base):
    def test_roundtrip_and_merge(self):
        i1 = self.add(self.make("e1.txt", "a\nb\n"), "导出字典一")
        i2 = self.add(self.make("e2.txt", "c\n"), "导出字典二")
        d = self.jrun("export")["data"]
        export_path = Path(d["path"])
        self.assertEqual(d["count"], 2)
        raw = json.loads(export_path.read_text(encoding="utf-8"))
        self.assertEqual(raw["count"], 2)
        self.assertEqual(len(raw["dicts"]), 2)
        # 删除后整库恢复（主键保留）
        self.jrun("delete", str(i1), "--yes")
        self.assertEqual(self.jrun("select")["count"], 1)
        d = self.jrun("import", export_path, "--replace", "--yes")["data"]
        self.assertTrue(d["replaced"])
        self.assertEqual(d["total_after"], 2)
        self.assertEqual(self.jrun("select", "--id", i1)["data"][0]["name"], "导出字典一")
        # 合并导入到全新数据目录：主键空闲则保留
        home2 = tempfile.mkdtemp(prefix="dictdb-imp-")
        try:
            env2 = self.jrun("import", export_path, env_extra={"DICTDB_HOME": home2})
            self.assertEqual(env2["data"]["imported"], 2)
            got = self.jrun("select", "--id", i2, env_extra={"DICTDB_HOME": home2})
            self.assertEqual(got["data"][0]["name"], "导出字典二")
        finally:
            shutil.rmtree(home2, ignore_errors=True)
        # 旧内容兼容：--replace 导入含中文分类的旧导出文件 → 自动归一为英文 slug
        old = json.loads(export_path.read_text(encoding="utf-8"))
        old["dicts"][0]["category"] = "目录"
        old_path = self.fixtures / "old_export.json"
        old_path.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        self.jrun("import", old_path, "--replace", "--yes")
        self.assertEqual(self.jrun("select", "--id", i1)["data"][0]["category"], "dir")

    def test_invalid_json(self):
        bad = self.fixtures / "bad.json"
        bad.write_text("{不是json", encoding="utf-8")
        p = self.run_cli("import", bad)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(json.loads(p.stdout)["error"]["code"], "VALIDATION")


class TestOutputProtocol(Base):
    def test_envelope_shape(self):
        env = self.jrun("select")
        self.assertEqual(set(env.keys()),
                         {"ok", "command", "count", "schema_version", "data", "error"})
        self.assertEqual(env["schema_version"], 1)
        self.assertIsNone(env["error"])

    def test_error_envelope_shape(self):
        env = self.jrun("select", "--id", "777777", expect=1)
        self.assertFalse(env["ok"])
        self.assertIsNone(env["data"])
        self.assertEqual(env["error"]["code"], "NOT_FOUND")
        self.assertTrue(env["error"]["message"])

    def test_table_mode(self):
        self.add(self.make("tbl.txt", "t\n"), "表格字典")
        p = self.run_cli("--table", "select")
        self.assertEqual(p.returncode, 0)
        self.assertIn("序号", p.stdout)
        self.assertFalse(p.stdout.lstrip().startswith("{"))

    def test_json_flag_in_pipe_equals_auto(self):
        self.assertEqual(self.jrun("select"), self.jrun("--json", "select"))

    def test_json_table_conflict(self):
        self.assertEqual(self.ecode("--json", "--table", "select"), 2)

    def test_exit_codes(self):
        did = self.add(self.make("exit.txt", "e\n"), "退出码字典")
        self.assertEqual(self.ecode("select", "--id", "888888"), 1)      # 未找到
        self.assertEqual(self.ecode("definitely-not-a-command"), 2)      # 参数错误
        self.assertEqual(self.ecode("delete", str(did)), 3)             # 非交互需 --yes
        self.assertEqual(self.ecode("--version"), 0)


class TestNewSyntax(Base):
    """v1.1 新命令体系：统一选择器 / edit / 短选项 / 分类归一 / 旧语法兼容。"""

    def test_category_normalization_and_short_opts(self):
        # 短选项 -n/-t/-c；中文分类别名 → 英文 slug
        src = self.make("ns1.txt", "a\nb\nc\n")
        d = self.jrun("add", src, "-n", "新语法字典", "-c", "目录", "-t", "dir,web")["data"]
        self.assertEqual(d["category"], "dir")
        # 未知分类：小写化、空白转下划线后保留（允许自定义）
        d2 = self.jrun("add", self.make("ns2.txt", "x\n"),
                       "-n", "自定义分类", "-c", "My Cat")["data"]
        self.assertEqual(d2["category"], "my_cat")
        # select --category 中文别名筛选已归一的数据
        self.assertEqual(self.jrun("select", "--category", "目录")["count"], 1)
        self.assertEqual(self.jrun("select", "--category", "dir")["count"], 1)

    def test_unified_selector_edit_and_rm(self):
        did = self.add(self.make("ns3.txt", "m1\nm2\nm3\n"), "选择器字典")
        # show 直接写主键
        self.assertEqual(self.jrun("show", str(did), "--head", "1")["data"]["id"], did)
        # @序号：先 select 建缓存，再 edit @1
        self.jrun("select", "选择器")
        d = self.jrun("edit", "@1", "-t", "dir,web", "-c", "密码", "--yes")["data"]["record"]
        self.assertEqual(d["id"], did)
        self.assertEqual(d["tags"], ["dir", "web"])
        self.assertEqual(d["category"], "password")
        # 归一后英文/中文别名都能筛
        self.assertEqual(self.jrun("select", "--category", "password")["count"], 1)
        self.assertEqual(self.jrun("select", "--category", "密码")["count"], 1)
        # edit 缺字段 → VALIDATION
        self.assertEqual(self.ecode("edit", str(did)), 2)
        # rm @n 删除
        did2 = self.add(self.make("ns4.txt", "z\n"), "序号删除目标")
        self.jrun("select", "序号删除")
        d = self.jrun("delete", "@1", "--yes")["data"]
        self.assertEqual(d["id"], did2)
        # select 无条件列出全部
        self.assertEqual(self.jrun("select")["command"], "select")

    def test_info(self):
        did = self.add(self.make("ns_info.txt", "i\n"), "详情字典")
        # 人类视图：一屏完整详情，含绝对路径
        p = self.run_cli("--table", "info", str(did))
        self.assertEqual(p.returncode, 0, p.stderr[:300])
        self.assertIn("路径", p.stdout)
        self.assertIn("store", p.stdout)
        # JSON 视图：path 为绝对路径
        d = self.jrun("info", str(did))["data"]
        self.assertEqual(d["id"], did)
        self.assertTrue(os.path.isabs(d["path"]))
        # @序号选择器同样可用
        self.jrun("select", "详情")
        self.assertEqual(self.jrun("info", "@1")["data"]["id"], did)

    def test_legacy_syntax_removed(self):
        did = self.add(self.make("ns5.txt", "o\n"), "旧语法字典")
        self.jrun("select", "旧语法")
        # v1.3 拆除兼容层：旧 id/list 选择器与全部别名一律报参数错误
        self.assertEqual(self.ecode("show", "id", str(did)), 2)
        self.assertEqual(self.ecode("delete", "list", "1"), 2)
        self.assertEqual(self.ecode("rm", str(did)), 2)
        self.assertEqual(self.ecode("ls"), 2)
        self.assertEqual(self.ecode("list"), 2)
        self.assertEqual(self.ecode("serve"), 2)


class TestI18n(Base):
    """界面语言：默认英文，DICTDB_LANG=zh / --lang zh 可切中文。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.did = _add(cls.env, _make(cls.fixtures, "i18n.txt", "a\n"), "i18n字典")

    def test_default_is_english(self):
        p = self.run_cli("--help", env_extra={"DICTDB_LANG": "en"})
        self.assertEqual(p.returncode, 0)
        self.assertIn("pentest wordlist manager", p.stdout)
        self.assertIn("cheatsheet", p.stdout)
        p = self.run_cli("--table", "select", env_extra={"DICTDB_LANG": "en"})
        self.assertIn("name", p.stdout)
        self.assertNotIn("名称", p.stdout)

    def test_env_switch_to_chinese(self):
        p = self.run_cli("--help", env_extra={"DICTDB_LANG": "zh"})
        self.assertEqual(p.returncode, 0)
        self.assertIn("渗透字典管理工具", p.stdout)
        self.assertIn("速查", p.stdout)
        p = self.run_cli("--table", "select", env_extra={"DICTDB_LANG": "zh"})
        self.assertIn("名称", p.stdout)

    def test_lang_flag_overrides_env(self):
        p = self.run_cli("--lang", "en", "--table", "select",
                         env_extra={"DICTDB_LANG": "zh"})
        self.assertIn("name", p.stdout)
        p = self.run_cli("--lang=zh", "--table", "select",
                         env_extra={"DICTDB_LANG": "en"})
        self.assertIn("名称", p.stdout)

    def test_lang_flag_after_subcommand(self):
        # --lang 与 --json/--table 一样，放子命令后面也要生效
        p = self.run_cli("select", "--table", "--lang", "zh", env_extra={"DICTDB_LANG": "en"})
        self.assertIn("名称", p.stdout)
        p = self.run_cli("select", "--table", "--lang=en", env_extra={"DICTDB_LANG": "zh"})
        self.assertIn("name", p.stdout)
        self.assertNotIn("名称", p.stdout)

    def test_error_message_language(self):
        env_en = {"DICTDB_LANG": "en"}
        env_zh = {"DICTDB_LANG": "zh"}
        p = self.run_cli("select", "--id", "424242", env_extra=env_en)
        self.assertIn("not found", json.loads(p.stdout)["error"]["message"])
        p = self.run_cli("select", "--id", "424242", env_extra=env_zh)
        self.assertIn("不存在", json.loads(p.stdout)["error"]["message"])

    def test_invalid_lang_falls_back_to_english(self):
        p = self.run_cli("--table", "select", env_extra={"DICTDB_LANG": "jp"})
        self.assertIn("name", p.stdout)


class TestLargeFile(Base):
    def test_200k_lines(self):
        content = "\n".join(f"path{i}/admin{'x' * 10}" for i in range(200_000)) + "\n"
        src = self.make("big.txt", content)
        t0 = time.time()
        d = self.jrun("add", src, "--name", "大文件字典")["data"]
        elapsed = time.time() - t0
        self.assertEqual(d["lines"], 200_000)
        self.assertEqual(d["size"], len(content.encode("utf-8")))
        self.assertLess(elapsed, 60, f"添加耗时过长：{elapsed:.1f}s")
        d = self.jrun("show", str(d["id"]), "--tail", "2")["data"]
        self.assertTrue(d["lines"][1]["text"].startswith("path199999"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
