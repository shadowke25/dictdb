"""i18n 消息目录：英文默认，DICTDB_LANG=zh 或 --lang zh 切换中文。

t(key, **kw) 取当前语言文案并做 {占位符} 格式化；
键缺失时回退英文，目录里完全没有该键时原样返回键名（便于发现漏翻）。
"""
from __future__ import annotations

_LANG = "en"
_LANGS = ("en", "zh")

STRINGS: dict[str, dict[str, str]] = {
    # ---------- 错误消息（core） ----------
    "err.bad_number": {
        "en": "id/index must be a number, got: {value!r}",
        "zh": "主键/序号必须是数字，收到：{value!r}",
    },
    "err.bad_at_index": {
        "en": "@index must be a positive integer, got: {value!r}",
        "zh": "@序号必须是正整数，收到：{value!r}",
    },
    "err.no_search_cache": {
        "en": "no search cache yet; run select first",
        "zh": "尚无搜索缓存，请先执行 select 生成序号",
    },
    "err.git_missing": {
        "en": "git command not found; make sure git is installed and on PATH",
        "zh": "未找到 git 命令，请确认已安装并加入 PATH",
    },
    "err.git_timeout": {
        "en": "git command timed out: {cmd}...",
        "zh": "git 命令超时：{cmd}...",
    },
    "err.ls_remote_failed": {
        "en": "git ls-remote failed: {detail}",
        "zh": "git ls-remote 失败：{detail}",
    },
    "err.clone_failed": {
        "en": "git clone failed: {detail}",
        "zh": "git clone 失败：{detail}",
    },
    "err.clone_file_missing": {
        "en": "file {rel} not found in repository {url}",
        "zh": "仓库 {url} 中不存在文件 {rel}",
    },
    "err.pull_failed": {
        "en": "git pull failed: {detail}",
        "zh": "git pull 失败：{detail}",
    },
    "err.path_not_found": {
        "en": "path does not exist or is not a file: {src}",
        "zh": "路径不存在或不是文件：{src}",
    },
    "err.name_required": {
        "en": "missing -n/--name (dictionary name is required)",
        "zh": "缺少 -n/--name（字典名必填）",
    },
    "err.dup_md5": {
        "en": "a dictionary with identical content (same md5) already exists: "
              "id={id} name={name}; use --force to add anyway",
        "zh": "已存在相同内容(md5 相同)的字典：id={id} name={name}；如仍要添加请加 --force",
    },
    "err.target_not_found": {
        "en": "primary key {n} not found",
        "zh": "主键 {n} 不存在",
    },
    "err.index_out_of_range": {
        "en": "index @{n} is not in the last select result ({total} items); run select first",
        "zh": "序号 @{n} 不在最近 select 结果中（共 {total} 条），请先执行 select",
    },
    "err.index_gone": {
        "en": "the dictionary at index @{n} no longer exists; run select again",
        "zh": "序号 @{n} 对应的字典已不存在，请重新 select",
    },
    "err.file_lost": {
        "en": "dictionary file is missing: {p}",
        "zh": "字典文件丢失：{p}",
    },
    "err.no_update_ops": {
        "en": "no update action specified: --replace / --append / --text",
        "zh": "未指定更新操作：--replace / --append / --text",
    },
    "err.replace_src_missing": {
        "en": "replacement source file not found: {src}",
        "zh": "替换源文件不存在：{src}",
    },
    "err.append_src_missing": {
        "en": "append source file not found: {src}",
        "zh": "追加源文件不存在：{src}",
    },
    "err.not_git_dict": {
        "en": "not a git-sourced dictionary (no git_url); git features unavailable",
        "zh": "该字典不是 git 来源（无 git_url），无法使用 git 功能",
    },
    "err.repo_lost": {
        "en": "the original file's directory is no longer inside a git repository: {target}",
        "zh": "原文件所在目录已不在 git 仓库内：{target}",
    },
    "err.import_file_missing": {
        "en": "file not found: {p}",
        "zh": "文件不存在：{p}",
    },
    "err.import_bad_json": {
        "en": "failed to parse JSON: {e}",
        "zh": "JSON 解析失败：{e}",
    },
    "err.import_invalid": {
        "en": "invalid JSON structure: missing 'dicts' array",
        "zh": "JSON 结构无效：缺少 dicts 数组",
    },
    "err.body_not_json": {
        "en": "request body is not valid JSON",
        "zh": "请求体不是合法 JSON",
    },
    "err.body_not_object": {
        "en": "request body must be a JSON object",
        "zh": "请求体必须是 JSON 对象",
    },
    "err.missing_path": {
        "en": "request body missing 'path' field",
        "zh": "请求体缺少 path 字段",
    },
    "err.confirm_required_api": {
        "en": "deletion requires explicit confirmation: pass ?confirm=true "
              "(aligned with the CLI double-confirm)",
        "zh": "删除需显式确认：请携带 ?confirm=true（与 CLI 二次确认对齐）",
    },
    "err.unknown_route": {
        "en": "unknown route: {path}",
        "zh": "未知路由：{path}",
    },
    "err.internal": {
        "en": "internal error: {e}",
        "zh": "内部错误：{e}",
    },
    "err.cancelled": {
        "en": "cancelled by user",
        "zh": "已取消操作",
    },
    "err.interrupted": {
        "en": "interrupted by user",
        "zh": "用户中断",
    },
    # ---------- 确认 / 交互 ----------
    "confirm.required": {
        "en": "cannot read confirmation input (pass --yes explicitly in non-interactive environments)",
        "zh": "无法读取确认输入（非交互环境需显式加 --yes 跳过二次确认）",
    },
    "confirm.add_name_prompt": {
        "en": "dictionary name (required): ",
        "zh": "请输入字典名称（必填）: ",
    },
    "confirm.delete": {
        "en": "delete dictionary id={id} {name}?",
        "zh": "确认删除字典 id={id} {name}?",
    },
    "confirm.update": {
        "en": "execute the update above (id={id})?",
        "zh": "确认执行以上更新（id={id}）?",
    },
    "confirm.edit": {
        "en": "apply metadata change (id={id})?",
        "zh": "确认修改元数据（id={id}）?",
    },
    "confirm.git_pull": {
        "en": "pull update for id={id}?",
        "zh": "确认拉取更新（id={id}）?",
    },
    "confirm.git_pull_batch": {
        "en": "batch-update the {n} dictionary(s) above?",
        "zh": "确认一键更新以上 {n} 个字典?",
    },
    "confirm.import_replace": {
        "en": "wipe the current database and restore from {file}?",
        "zh": "确认清空现有数据库并从 {file} 整库恢复?",
    },
    "confirm.cancelled_delete": {
        "en": "delete cancelled",
        "zh": "已取消删除",
    },
    "confirm.cancelled_update": {
        "en": "update cancelled",
        "zh": "已取消更新",
    },
    "confirm.cancelled_edit": {
        "en": "edit cancelled",
        "zh": "已取消修改",
    },
    "confirm.cancelled_pull": {
        "en": "pull cancelled",
        "zh": "已取消拉取",
    },
    "confirm.cancelled_import": {
        "en": "import cancelled",
        "zh": "已取消导入",
    },
    # ---------- 警告 ----------
    "warn.git_no_update": {
        "en": "remote has no new version; the pull will be skipped",
        "zh": "远端无新版本，--git 将跳过拉取",
    },
    "warn.link_modify": {
        "en": "link mode: the ORIGINAL file will be modified: {target}",
        "zh": "link 模式：将直接修改原文件 {target}",
    },
    # ---------- 人类视图（output.py） ----------
    "ui.no_match": {
        "en": "no matching dictionaries",
        "zh": "未找到匹配的字典",
    },
    "ui.select_total": {
        "en": "{n} dictionaries",
        "zh": "共 {n} 条字典",
    },
    "ui.no_git_dicts": {
        "en": "no git-sourced dictionaries",
        "zh": "库中没有 git 来源的字典",
    },
    "ui.git_total": {
        "en": "{n} git dictionaries, {m} outdated",
        "zh": "共 {n} 个 git 字典，{m} 个有更新",
    },
    "ui.status_check_failed": {
        "en": "check failed",
        "zh": "检查失败",
    },
    "ui.status_outdated": {
        "en": "outdated",
        "zh": "有更新",
    },
    "ui.status_up_to_date": {
        "en": "up to date",
        "zh": "最新",
    },
    "ui.status_unknown": {
        "en": "unknown",
        "zh": "未知",
    },
    "ui.show_header": {
        "en": "dict {id} {name} | {lines} lines | {path}",
        "zh": "字典 {id} {name} | 共 {lines} 行 | {path}",
    },
    "ui.show_range": {
        "en": "[{mode}] {range}, showing {count} lines{extra}",
        "zh": "[{mode}] {range}，显示 {count} 行{extra}",
    },
    "ui.show_truncated": {
        "en": " (limit reached, truncated)",
        "zh": "（已达显示上限，已截断）",
    },
    "ui.mode_range": {
        "en": "lines {a}-{b}",
        "zh": "第 {a}-{b} 行",
    },
    "ui.mode_head": {
        "en": "first {n} lines",
        "zh": "前 {n} 行",
    },
    "ui.mode_all": {
        "en": "all {n} lines",
        "zh": "全部 {n} 行",
    },
    "ui.show_default_hint": {
        "en": "hint: first 20 lines by default; use --head 0 for the full file, or --lines/--tail/--grep",
        "zh": "提示：默认仅显示前 20 行；--head 0 查看全部，或用 --lines/--tail/--grep 精确取段",
    },
    "ui.mode_tail": {
        "en": "last {n} lines",
        "zh": "末尾 {n} 行",
    },
    "ui.mode_grep": {
        "en": "matching '{q}'",
        "zh": "匹配「{q}」",
    },
    "ui.show_range_line": {
        "en": "{label}, showing {count} lines{extra}",
        "zh": "{label}，显示 {count} 行{extra}",
    },
    "ui.detail_name": {
        "en": "name",
        "zh": "名称",
    },
    "ui.detail_category": {
        "en": "category",
        "zh": "分类",
    },
    "ui.detail_tags": {
        "en": "tags",
        "zh": "标签",
    },
    "ui.detail_instructions": {
        "en": "instructions",
        "zh": "说明",
    },
    "ui.detail_source": {
        "en": "source",
        "zh": "来源",
    },
    "ui.detail_mode": {
        "en": "mode",
        "zh": "模式",
    },
    "ui.detail_path": {
        "en": "path",
        "zh": "路径",
    },
    "ui.detail_size": {
        "en": "size",
        "zh": "大小",
    },
    "ui.detail_lines": {
        "en": "lines",
        "zh": "行数",
    },
    "ui.detail_created": {
        "en": "created",
        "zh": "添加",
    },
    "ui.detail_updated": {
        "en": "updated",
        "zh": "更新",
    },
    "ui.detail_git_synced": {
        "en": "synced",
        "zh": "同步",
    },
    "ui.add_done": {
        "en": "added: id={id}  name={name}",
        "zh": "已添加：id={id}  名称={name}",
    },
    "ui.add_git_detected": {
        "en": "git repo detected: {url} @ {commit}",
        "zh": "检测到 git 仓库：{url} @ {commit}",
    },
    "ui.add_path": {
        "en": "path: {path}",
        "zh": "路径：{path}",
    },
    "ui.add_stats": {
        "en": "lines={lines}  size={size}  md5={md5}",
        "zh": "行数={lines}  大小={size}  md5={md5}",
    },
    "ui.delete_done": {
        "en": "deleted: id={id}  name={name}",
        "zh": "已删除：id={id}  名称={name}",
    },
    "ui.confirm_actions": {
        "en": "actions to be executed:",
        "zh": "将执行的操作：",
    },
    "ui.act_replace": {
        "en": "  - replace content <- {src} (new {lines} lines / {size}, old file backed up as {backup})",
        "zh": "  - 替换内容 ← {src}（新 {lines} 行 / {size}，旧文件备份为 {backup}）",
    },
    "ui.act_append_file": {
        "en": "  - append file <- {src} (+{lines} lines)",
        "zh": "  - 追加文件 ← {src}（+{lines} 行）",
    },
    "ui.act_append_text": {
        "en": "  - append text (+{lines} lines): {text}",
        "zh": "  - 追加文本（+{lines} 行）：{text}",
    },
    "ui.act_git_pull": {
        "en": "  - pull latest from git <- {url} ({branch}) {rel}",
        "zh": "  - 拉取 git 最新版本 ← {url}（{branch}）{rel}",
    },
    "ui.default_branch": {
        "en": "default branch",
        "zh": "默认分支",
    },
    "ui.act_meta": {
        "en": "  - update metadata fields: {fields}",
        "zh": "  - 更新元数据字段：{fields}",
    },
    "ui.git_compare": {
        "en": "git compare: local {local} -> remote {remote} ({state})",
        "zh": "git 版本比对：本地 {local} → 远端 {remote}（{state}）",
    },
    "ui.state_outdated": {
        "en": "outdated",
        "zh": "有更新",
    },
    "ui.state_up_to_date": {
        "en": "up to date",
        "zh": "无更新",
    },
    "ui.state_unknown": {
        "en": "unknown",
        "zh": "未知",
    },
    "ui.update_done": {
        "en": "update done: id={id}  name={name}  lines={lines}  updated={updated}",
        "zh": "更新完成：id={id}  名称={name}  行数={lines}  更新时间={updated}",
    },
    "ui.update_backup": {
        "en": "old file backed up: {backup}",
        "zh": "旧文件备份：{backup}",
    },
    "ui.check_header": {
        "en": "dict {id} {name}",
        "zh": "字典 {id} {name}",
    },
    "ui.check_local": {
        "en": "local commit: {c}",
        "zh": "本地 commit: {c}",
    },
    "ui.check_remote": {
        "en": "remote commit: {c}",
        "zh": "远端 commit: {c}",
    },
    "ui.check_status": {
        "en": "status: {state}",
        "zh": "状态: {state}",
    },
    "ui.git_pull_fresh": {
        "en": "id={id} {name} is already up to date; nothing to pull",
        "zh": "id={id} {name} 已是最新，无需拉取",
    },
    "ui.git_all_done": {
        "en": "batch update done: {a} updated, {b} up to date, {c} failed, {d} check errors",
        "zh": "一键更新完成：更新 {a} 个，已最新 {b} 个，失败 {c} 个，检查失败 {d} 个",
    },
    "ui.git_all_none": {
        "en": "all git dictionaries are up to date",
        "zh": "所有 git 字典均已是最新",
    },
    "ui.export_done": {
        "en": "exported {n} dictionaries -> {path}",
        "zh": "已导出 {n} 条字典 → {path}",
    },
    "ui.import_done": {
        "en": "import done: {mode} {n} items, {total} in database",
        "zh": "导入完成：{mode}{n} 条，现有 {total} 条",
    },
    "ui.import_mode_replace": {
        "en": "full restore, ",
        "zh": "整库恢复",
    },
    "ui.import_mode_merge": {
        "en": "merged ",
        "zh": "合并",
    },
    # ---------- 表头 ----------
    "hdr.index": {"en": "#", "zh": "序号"},
    "hdr.id": {"en": "id", "zh": "id"},
    "hdr.name": {"en": "name", "zh": "名称"},
    "hdr.category": {"en": "category", "zh": "分类"},
    "hdr.tags": {"en": "tags", "zh": "标签"},
    "hdr.lines": {"en": "lines", "zh": "行数"},
    "hdr.instructions": {"en": "instructions", "zh": "说明"},
    "hdr.updated": {"en": "updated", "zh": "更新时间"},
    "hdr.branch": {"en": "branch", "zh": "分支"},
    "hdr.local_commit": {"en": "local commit", "zh": "本地commit"},
    "hdr.status": {"en": "status", "zh": "状态"},
    # ---------- CLI：usage / 校验 ----------
    "cli.target_usage": {
        "en": "usage: dictdb <command> <id|@index>, e.g.: dictdb show 3 / dictdb rm @1",
        "zh": "用法：dictdb <命令> <主键|@序号>，如：dictdb show 3 / dictdb rm @1",
    },
    "cli.update_usage": {
        "en": "usage: dictdb update <id|@index> [--replace FILE] [--append FILE] [--text LINE]; "
              "for git updates use dictdb git pull",
        "zh": "用法：dictdb update <主键|@序号> [--replace 文件] [--append 文件] [--text 一行]；"
              "git 更新用 dictdb git pull",
    },
    "cli.edit_missing_fields": {
        "en": "no fields to modify: -n/-t/-c/-i/-s",
        "zh": "未指定要修改的字段：-n/-t/-c/-i/-s",
    },
    "cli.lines_format": {
        "en": "--lines expects 100 or 100-200: {s}",
        "zh": "--lines 格式应为 100 或 100-200：{s}",
    },
    "cli.json_table_conflict": {
        "en": "--json and --table cannot be used together",
        "zh": "--json 与 --table 不能同时使用",
    },
    # ---------- CLI help ----------
    "help.description": {
        "en": "dictdb —— pentest wordlist manager",
        "zh": "dictdb —— 渗透字典管理工具",
    },
    "help.epilog": {
        "en": (
            "cheatsheet:\n"
            "  dictdb add D:\\dicts\\x.txt -n dirlist -t dir,web -c dir\n"
            "  dictdb select keyword            # alias ls; results are indexed\n"
            "  dictdb show @1 --lines 5-10      # @1 = 1st of last select; bare number = primary key\n"
            "  dictdb info 3                    # full details of one dict (absolute path)\n"
            "  dictdb edit 1 -t dir,top100      # modify metadata\n"
            "  dictdb update 1 --append more.txt --text \"one line\"   # content update\n"
            "  dictdb git status | git check 7 | git pull [id|@n]\n"
            "  dictdb rm @2                     # delete (alias rm)\n"
            "categories (English slugs; Chinese aliases auto-converted): "
            "dir/api/password/username/subdomain/param/fuzz/other\n"
            "language: --lang en|zh  (env DICTDB_LANG, default en)"
        ),
        "zh": (
            "速查：\n"
            "  dictdb add D:\\dicts\\x.txt -n 目录字典 -t dir,web -c dir\n"
            "  dictdb select 关键词            # 别名 ls；结果带序号\n"
            "  dictdb show @1 --lines 5-10     # @1=最近搜索第1条；数字=主键\n"
            "  dictdb info 3                   # 单条完整详情（含绝对路径）\n"
            "  dictdb edit 1 -t dir,top100     # 改元数据\n"
            "  dictdb update 1 --append more.txt --text \"一行\"   # 内容更新\n"
            "  dictdb git status | git check 7 | git pull [主键|@n]\n"
            "  dictdb rm @2                    # 删除（别名 rm）\n"
            "分类（英文枚举，中文别名自动转换）：dir/api/password/username/subdomain/param/fuzz/other\n"
            "语言：--lang en|zh（环境变量 DICTDB_LANG，默认英文）"
        ),
    },
    "help.add": {"en": "add a dictionary (absolute path)", "zh": "添加字典（绝对路径）"},
    "help.add.path": {"en": "absolute path of the dictionary file", "zh": "字典文件绝对路径"},
    "help.add.name": {"en": "dictionary name (required; prompted on a real terminal if omitted)",
                      "zh": "字典名（必填，缺失时在交互终端提示输入）"},
    "help.add.tags": {"en": "tags, comma separated (English recommended): dir,web",
                      "zh": "标签，逗号分隔（建议英文）：dir,web"},
    "help.add.category": {"en": "category: dir/api/password/username/subdomain/param/fuzz/other "
                               "(Chinese aliases auto-converted)",
                          "zh": "分类：dir/api/password/username/subdomain/param/fuzz/other（中文别名自动转换）"},
    "help.add.instructions": {"en": "instructions", "zh": "说明"},
    "help.add.source": {"en": "source (URL / project / manual)", "zh": "来源（URL / 项目名 / 手工整理）"},
    "help.add.link": {"en": "reference the original path instead of copying into store",
                      "zh": "引用原路径，不复制进 store"},
    "help.add.force": {"en": "add anyway when md5 duplicates an existing entry",
                       "zh": "md5 与已有条目重复时仍强制添加"},
    "help.select": {"en": "search dictionaries (fuzzy/id/tag/category; alias ls)",
                    "zh": "搜索字典（模糊/主键/标签/分类；别名 ls）"},
    "help.select.keyword": {"en": "fuzzy keyword (matches name/instructions/source/category/tags)",
                            "zh": "模糊关键词（名称/说明/来源/分类/标签）"},
    "help.select.id": {"en": "query by primary key (leading zeros ok, e.g. 072111)",
                       "zh": "按主键查询（接受 072111 前导零形式）"},
    "help.select.tag": {"en": "filter by tag", "zh": "按标签过滤"},
    "help.select.category": {"en": "filter by category (Chinese aliases accepted)",
                             "zh": "按分类过滤（接受中文别名）"},
    "help.show": {"en": "view specific lines of a dictionary", "zh": "查看字典特定行内容"},
    "help.show.target": {"en": "primary key or @index, e.g. 3 / @1", "zh": "主键或 @序号，如 3 / @1"},
    "help.show.lines": {"en": "line range: 100 or 100-200", "zh": "行段：100 或 100-200"},
    "help.show.head": {"en": "first N lines (default: 20 when omitted; 0 = full file)",
                       "zh": "前 N 行（缺省时取前 20 行；0 = 输出全部）"},
    "help.show.tail": {"en": "last N lines", "zh": "末尾 N 行"},
    "help.show.grep": {"en": "search lines by keyword (case-insensitive, max 1000)",
                       "zh": "按关键词搜行（大小写不敏感，最多 1000 条）"},
    "help.info": {"en": "full details of one dict (absolute path/size/md5/git)",
                  "zh": "查看单条完整详情（绝对路径/大小/md5/git 等）"},
    "help.edit": {"en": "modify metadata (name/tags/category/instructions/source; double-confirm)",
                  "zh": "修改元数据（名称/标签/分类/说明/来源，二次确认）"},
    "help.edit.name": {"en": "new name", "zh": "新名称"},
    "help.edit.tags": {"en": "new tags, comma separated", "zh": "新标签，逗号分隔"},
    "help.edit.category": {"en": "new category (English slug; Chinese aliases auto-converted)",
                           "zh": "新分类（英文枚举，中文别名自动转换）"},
    "help.edit.instructions": {"en": "new instructions", "zh": "新说明"},
    "help.edit.source": {"en": "new source", "zh": "新来源"},
    "help.edit.yes": {"en": "skip double-confirm (for scripts)", "zh": "跳过二次确认（脚本用）"},
    "help.update": {"en": "update dictionary content: replace/append (double-confirm)",
                    "zh": "更新字典内容：替换/追加（二次确认）"},
    "help.update.replace": {"en": "replace content with the given file (old file kept as .bak)",
                            "zh": "用指定文件整体替换内容（旧文件留 .bak）"},
    "help.update.append": {"en": "append the given file to the dictionary tail",
                           "zh": "把指定文件追加到字典尾部"},
    "help.update.text": {"en": "append one line of text", "zh": "追加一行文本"},
    "help.delete": {"en": "delete a dictionary (double-confirm; alias rm)",
                    "zh": "删除字典（二次确认；别名 rm）"},
    "help.git": {"en": "git version management for git-sourced dictionaries",
                 "zh": "git 字典版本管理"},
    "help.git.status": {"en": "remote update status of all git dictionaries",
                        "zh": "全部 git 字典的远端更新状态"},
    "help.git.check": {"en": "compare one dictionary against the remote (read-only)",
                       "zh": "单条版本比对（只读）"},
    "help.git.pull": {"en": "pull updates; without target = batch-pull all outdated (double-confirm)",
                      "zh": "拉取更新；无参数 = 批量拉取全部有更新的（二次确认）"},
    "help.git.pull_target": {"en": "primary key or @index (omit for batch)", "zh": "主键或 @序号（缺省批量）"},
    "help.export": {"en": "export the whole database to JSON", "zh": "全库导出 JSON"},
    "help.export.out": {"en": "output path (default export/db.json)", "zh": "输出路径（默认 export/db.json）"},
    "help.import": {"en": "import/restore from JSON", "zh": "从 JSON 导入/恢复"},
    "help.import.file": {"en": "JSON file produced by export", "zh": "export 生成的 JSON 文件"},
    "help.import.replace": {"en": "wipe current data then restore (double-confirm)",
                            "zh": "清空现有数据后整库恢复（二次确认）"},
    "help.yes": {"en": "skip double-confirm (for scripts)", "zh": "跳过二次确认（脚本用）"},
    "help.json": {"en": "force JSON output", "zh": "强制 JSON 输出"},
    "help.full": {"en": "output all fields for select (default: 9-field projection)",
                  "zh": "select 输出全部字段（默认 9 字段投影）"},
    "help.table": {"en": "force table output", "zh": "强制表格输出"},
    "help.lang": {"en": "interface language (default: env DICTDB_LANG, fallback en)",
                  "zh": "界面语言（默认取环境变量 DICTDB_LANG，缺省 en）"},
}


def set_lang(lang: str):
    global _LANG
    _LANG = lang if lang in _LANGS else "en"


def get_lang() -> str:
    return _LANG


def t(key: str, **kw) -> str:
    """取当前语言文案；缺键回退英文，再缺则返回键名。"""
    s = STRINGS.get(key, {})
    text = s.get(_LANG) or s.get("en") or key
    if kw:
        try:
            text = text.format(**kw)
        except (KeyError, IndexError, ValueError):
            pass
    return text
