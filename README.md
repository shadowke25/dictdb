# dictdb —— 字典数据库

**A zero-dependency local wordlist manager for pentesters — CLI.**
**当前版本：v1.5.0**

渗透测试字典（wordlist）统一管理工具：纯本地命令行，为"人"提供对齐表格，为"AI 和其他工具"提供零转换 JSON。

- **Python 标准库零依赖**，无需下载任何第三方包
- **SQLite 存储 + JSON 导出**，中文对齐表格输出
- **统一选择器**：数字 = 主键，`@n` = 最近搜索序号，全命令通用
- **职责分离**：`update` 纯内容 / `edit` 纯元数据 / `git status|check|pull` 版本管理
- **git 字典版本管理**：自动探测仓库、远端比对、单条或一键批量拉取更新
- **防误操作**：删除/更新强制二次确认，替换自动留 `.bak`
- **为 AI 而设计**：统一 JSON 信封、绝对路径直出、结构化错误、语义化退出码

---

## 目录

- [环境安装](#环境安装)
- [快速上手](#快速上手)
- [命令详解](#命令详解)
- [选择器与分类规则](#选择器与分类规则)
- [输出协议（AI / 工具对接）](#输出协议ai--工具对接)
- [数据与存储布局](#数据与存储布局)
- [git 字典说明](#git-字典说明)
- [样例数据](#样例数据)
- [界面语言](#界面语言)
- [测试](#测试)
- [架构](#架构)
- [路线图](#路线图)
- [注意事项](#注意事项)

---

## 环境安装

要求：Python ≥ 3.11、git（git 字典功能需要）。推荐使用 [uv](https://docs.astral.sh/uv/) 管理环境：

```bash
# 1. 创建虚拟环境并安装本项目（可编辑模式）
uv venv .venv
uv pip install -e .

# 2. 运行（三种方式等价）
uv run dictdb --version              # uv 统一入口
.venv\Scripts\dictdb --version       # venv 内命令（Windows）
python -m dictdb --version           # 无需安装，项目根目录下直接跑
```

不使用 uv 也可以：项目零依赖，在项目根目录 `python -m dictdb` 即可运行；
Windows 全局命令可将 [dictdb.cmd](dictdb.cmd) 所在目录加入 PATH（或复制到任一 PATH 目录）。

数据默认存放在本项目根目录，用环境变量 `DICTDB_HOME` 可重定向到任意位置：

```bash
set DICTDB_HOME=D:\dictdb_data       # cmd
export DICTDB_HOME=/d/dictdb_data    # git bash / linux
```

---

## 快速上手

```bash
# ① 添加（-n 必填；-t 标签 / -c 分类建议英文）
dictdb add D:\dicts\dirsearch.txt -n 目录字典 -t dir,web -c dir \
           -i "dirsearch 主字典" -s "github.com/maurosoria/dirsearch"

# ② 搜索（结果带序号 1、2、3）
dictdb select dir              # 模糊匹配 名称/说明/来源/分类/标签
dictdb select --tag web        # 按标签
dictdb select --category dir   # 按分类（写中文「目录」也行，自动转换）
dictdb select                  # 列出全部

# ③ 统一选择器：数字=主键，@n=最近搜索序号
dictdb show 1 --lines 100-200  # 主键 1 的第 100~200 行
dictdb show @1                 # 最近搜索第 1 条（缺省只看前 20 行）
dictdb show 1 --head 0         # 输出完整内容（不限制）
dictdb info 1                  # 单条完整详情（含绝对路径、md5、git 锚点）

# ④ 三种修改各司其职
dictdb edit 1 -t dir,top100 -c dir          # 改元数据（二次确认）
dictdb update 1 --append more.txt           # 追加内容（二次确认，留 .bak）
dictdb delete @2                           # 删除（二次确认）

# ⑤ git 字典版本管理
dictdb git status              # 谁落后于远端？
dictdb git check 7             # 单条版本比对（只读）
dictdb git pull 7              # 单条拉取
dictdb git pull                # 一键批量：列出→确认→逐个拉取→汇总

# ⑥ 备份 / 迁移
dictdb export -o D:\backup\db.json
dictdb import D:\backup\db.json --replace
```

---

## 命令详解

### add —— 添加字典

```bash
dictdb add <绝对路径> -n <字典名> [选项]
```

| 选项 | 说明 |
|---|---|
| `-n` / `--name` | **必填**。缺失时在真实终端会交互补问，非交互环境直接报错 |
| `-t` / `--tags` | 标签，逗号分隔（建议英文）：`dir,web` |
| `-c` / `--category` | 分类，英文枚举（中文别名自动转换），见[分类规则](#选择器与分类规则) |
| `-i` / `--instructions` | 说明 |
| `-s` / `--source` | 来源（URL / 项目名 / 手工整理） |
| `--link` | 引用原路径而不复制进 `store\`（原文件被移动/删除后失效） |
| `--force` | 内容 md5 与已有条目重复时仍强制添加 |

自动完成：复制进 `store\`（0001-名称.txt）、统计 行数/大小/md5、探测所在
git 仓库并记录 url/分支/commit 锚点。

### select —— 搜索字典

```bash
dictdb select [关键词] [--id N] [--tag x] [--category x]
```

- 关键词对 name / instructions / source / category / tags 做 LIKE 模糊匹配；
  多个关键词之间 AND（每个关键词命中任意字段即可）
- 结果输出带 **序号**（1、2、3）并写入 `last_search.json` 缓存，
  供后续 `@n` 选择器使用
- `--id` 按主键查询（接受 `072111` 前导零形式）

### show —— 查看字典内容

```bash
dictdb show <主键|@序号> [--lines 100-200] [--head 20] [--tail 50] [--grep 关键词] [--head 0]
```

- **缺省限流**：不带任何范围选项时只输出**前 20 行**（大字典防刷屏），
  人类视图会附提示；`--head 0` 输出**完整内容**（超大文件建议改用 `--lines` 分段）
- `--grep` 大小写不敏感，最多返回前 1000 条匹配（`truncated: true` 表示已截断）
- 按字节流式读取，GB 级字典内存占用恒定

### info —— 查看单条完整详情（人类视图）

```bash
dictdb info <主键|@序号>
```

一屏展示全部字段：**绝对路径**、模式、大小/行数/md5、git 版本锚点、时间戳。
搜索表格里刻意不放长路径，需要复制路径给其他工具时用 `info` 查看。

### edit —— 修改元数据

```bash
dictdb edit <主键|@序号> [-n 新名] [-t 标签] [-c 分类] [-i 说明] [-s 来源] [--yes]
```

只改元数据，不动字典内容；至少给一个字段，二次确认后生效。

### update —— 更新内容

```bash
dictdb update <主键|@序号> [--replace 文件] [--append 文件] [--text "一行"] [--yes]
```

| 操作 | 说明 |
|---|---|
| `--replace <文件>` | 用指定文件整体替换内容（旧文件自动备份 `.bak`） |
| `--append <文件>` | 把指定文件追加到字典尾部（自动补分隔换行） |
| `--text "一行"` | 追加一行文本 |

任何改动都会重算 行数/大小/md5 并刷新 `updated_at`；执行前回显变更摘要
（动作清单 + 前后行数）并要求确认。

### delete —— 删除字典

```bash
dictdb delete <主键|@序号> [--yes]
```

- copy 模式：记录与 `store\` 副本一并删除
- link 模式：只删记录，原文件保留
- **强制二次确认**（回显详情）；`--yes` 供脚本跳过

### git —— 字典版本管理

```bash
dictdb git status              # 全部 git 字典的远端更新状态（有更新排前面）
dictdb git check <主键|@序号>   # 单条版本比对（本地 commit vs 远端，只读）
dictdb git pull <主键|@序号>   # 单条拉取最新版本
dictdb git pull                # 批量：检查全部 → 列出有更新 → 确认 → 逐个拉取 → 汇总
```

### export / import —— 备份与恢复

```bash
dictdb export [-o 输出路径]        # 默认 export\db.json，全字段含主键
dictdb import <db.json> [--replace] [--yes]
```

- 默认合并导入：主键空闲则保留原主键，冲突则走自增
- `--replace`：清空现有库后整库恢复（二次确认）

---

## 选择器与分类规则

**选择器**（show / edit / update / delete / git check / git pull 全部通用）：

| 写法 | 含义 |
|---|---|
| `3` | 主键 id=3 |
| `@1` | 最近一次 select 结果的第 1 条 |

**分类 category**（存储与筛选统一为英文 slug）：

| slug | 接受的输入（自动转换） |
|---|---|
| `dir` | dir / directory / 目录 / 目录爆破 / 路径 |
| `api` | api / 接口 |
| `password` | password / pass / pwd / 密码 / 弱口令 |
| `username` | username / user / 用户名 / 账户 / 账号 |
| `subdomain` | subdomain / sub / 子域 / 子域名 |
| `param` | param / 参数 / 参数fuzz |
| `fuzz` | fuzz / 模糊测试 |
| `other` | other / 其他 / 其它 |

不在表中的值会小写化、空白转下划线后原样保留，允许自定义分类。
**tags 建议使用英文**（如 `dir,web,top100`），便于脚本与 AI 检索。

---

## 输出协议（AI / 工具对接）

**自动适配**：终端交互 → 人类对齐表格；被管道 / 程序调用 → 自动输出 JSON，
无需加参数。`--json` / `--table` 可强制指定（全局选项，放命令前后均可，
二者互斥）。

统一 JSON 信封（`select` 默认返回 **9 字段投影**，按"决策价值"筛选字段）：

```json
{
  "ok": true,
  "command": "select",
  "count": 1,
  "schema_version": 1,
  "data": [{
    "index": 1,
    "id": 1,
    "name": "目录字典",
    "category": "dir",
    "tags": ["dir", "web"],
    "instructions": "dirsearch 主字典",
    "lines": 10230,
    "path": "D:\\dictdb\\store\\0001-目录字典.txt",
    "updated_at": "2026-09-27 21:30:00"
  }],
  "error": null
}
```

投影规则：

| 保留字段 | 理由 |
|---|---|
| `index` / `id` / `name` | 选择器与标识 |
| `category` / `tags` / `instructions` | **agent 判断"用哪个字典"的决策依据**（instructions 截断到 50 字符） |
| `lines` | 规模参考 |
| `path` | **最终产物**，直接喂给 ffuf / dirsearch 的 `-w` |
| `updated_at` | 时效性 |

丢弃字段（`md5` / `git` / `original_path` / `size` / `storage_mode` / `source` /
`created_at`）：选字典场景用不到，需要时用 `dictdb info`（始终全字段）或加
**`--full`** 全局开关恢复完整输出。`git status` 列表同样投影，额外保留
`git{branch, commit, has_update}` 子集。

为 AI / 工具集成设计的关键点：

- **`path` 为绝对路径**：拿到即可直接喂给 ffuf / dirsearch / hydra 等工具，
  "查字典 → 拿路径 → 调工具"零转换闭环
- **`index` 序号**：可接着用 `@n` 选择器（如 `dictdb delete @1`）
- **错误也结构化**：`{"ok": false, "error": {"code": "NOT_FOUND", "message": "…"}}`
- **退出码**：`0` 成功 / `1` 未找到或运行错误 / `2` 参数错误 / `3` 取消或需确认
- **非交互环境安全**：stdin 非终端时，删除/更新必须显式 `--yes`，
  否则返回 `CONFIRM_REQUIRED`（exit 3），杜绝脚本误删

错误码一览：`NOT_FOUND` / `VALIDATION` / `CONFLICT` / `GIT_ERROR` /
`IO_ERROR` / `CANCELLED` / `CONFIRM_REQUIRED` / `SERVER_ERROR`。

AI 调用示例（任意语言/Agent 均可）：

```bash
dictdb select --category dir --json
# 解析 data[*].path，直接作为 -w 参数
ffuf -w "D:\dictdb\store\0001-目录字典.txt" -u https://target/FUZZ
```

> 需要 md5 / git 锚点等完整字段时（如自写脚本做变更检测），加 `--full`：
> `dictdb select --json --full`。这是 v1.5 的**有意破坏性变更**（默认投影省 token）。

---

## 数据与存储布局

```
DICTDB_HOME（默认项目根）
├── dictdb.db          SQLite 元数据库（WAL 模式，自动建库建索引）
├── store\             托管字典副本：0001-名称.txt
├── export\            export 默认输出目录
└── last_search.json   最近一次 select 的序号缓存（@n 选择器依赖）
```

### 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| id | 自动 | 主键，自增整数（输入接受 `072111` 前导零形式） |
| name | **手动必填** | 字典名 |
| tags | 可选 | 标签数组（建议英文），逗号分隔输入 |
| instructions | 可选 | 说明 |
| source | 可选 | 来源 |
| category | 自动归一 | 英文 slug 枚举，中文别名自动转换 |
| storage_mode | 自动 | `copy` 托管副本 / `link` 引用原路径 |
| path | 自动 | 字典文件绝对路径（对外输出的核心字段） |
| lines / size / md5 | 自动 | 行数 / 字节数 / 内容指纹（去重与变更检测） |
| git.* | 自动 | add 时探测 .git 记录：url / branch / commit / 同步时间 |
| created_at / updated_at | 自动 | 时间戳 |

---

## git 字典说明

- **add 时**：从文件所在目录向上逐级探测 `.git`，记录 remote url、分支、
  当前 commit、文件在仓库内的相对路径
- **copy 模式更新**：`git clone --depth 1 --filter=blob:none` 到临时目录，
  取出目标文件覆盖 store 副本——**完全不碰你自己的仓库**
- **link 模式更新**：在原仓库执行 `git pull --ff-only`（确认页有显著警告）
- **版本比对**：`git ls-remote` 只读查询，`git check` / `git status`
  均不产生任何写入

---

## 样例数据

项目自带一套测试字典（源文件在 `samples\`，均已示例化入库）：

```
samples\
├── dirs\common-dir.txt         常见目录字典      -c dir      -t dir,web,common
├── dirs\api-paths.txt          API路径字典       -c api      -t api,rest
├── passwords\top-weak.txt      弱口令Top         -c password -t password,weak
│                                                                  （含中文弱密码）
├── usernames\default-users.txt 默认用户名字典    -c username -t username,default
├── subdomains\sub-prefix.txt   子域名前缀        -c subdomain -t subdomain
├── fuzz\params.txt             参数Fuzz字典      -c param    -t fuzz,param
└── git\                        git 演示仓库（内含嵌套 .git，已 gitignore）
    ├── remote.git              模拟远端（bare 仓库，已推到 v2）
    ├── demo-copy               停在 v1 的工作副本 —— 用它 add 即可体验「有更新」
    └── demo-repo               开发用工作副本（当前在 v2）
```

git 演示完全本地、不联网：删除过红队演示字典可用下面命令恢复，加回来它停在
v1 而远端是 v2，`dictdb git status` 即显示「有更新」，`dictdb git pull <id>`
拉取后行数 10 → 14：

```bash
dictdb add samples\git\demo-copy\red-team-dict.txt --name 红队演示字典 \
           --category dir --tags demo,git
```

想加自己的测试字典：往 `samples\` 任意子目录放文本文件，`dictdb add` 即可
（copy 模式会复制进 `store\`，源文件保持不动）。

---

## 界面语言

**默认英文**，`--lang zh` 或环境变量 `DICTDB_LANG=zh` 切换中文——help、报错、
确认提示、表格表头、人类输出全部跟随切换（JSON 信封的字段名不变）：

```bash
dictdb --lang zh --help          # 中文速查
set DICTDB_LANG=zh               # cmd 永久切中文（写入环境即可）
export DICTDB_LANG=zh            # git bash / linux

dictdb --lang en select --json   # 临时切回英文；优先级：--lang > DICTDB_LANG > en
```

说明：`--lang` 在帮助渲染前生效（`--help` 自身即随语言切换）；
argparse 内建的 "usage:/options:" 等框架词保持英文。

---

## 测试

全量测试套件 [tests/test_full.py](tests/test_full.py)：67 项用例，覆盖全部
CLI 命令、界面语言（默认英文/中文切换）、JSON 协议、git 全链路（本地裸仓库
模拟远端）、export/import 闭环、边界条件（空文件 / CRLF / 无尾行 / 中文
文件名）与 20 万行大数据。每个测试类使用独立临时 `DICTDB_HOME`，
不污染真实数据。

```bash
# 使用 uv 管理的环境运行
uv run python -m unittest tests.test_full -v

# 或直接用 venv
.venv\Scripts\python -m unittest tests.test_full -v
```

---

## 版本与发布

- git 管理，主分支 `main`，里程碑打 tag（当前 `v1.5.0`）
- 从 GitHub 安装：

```bash
uv pip install git+https://github.com/shadowke/dictdb.git
```

- 下一步开发方向：**TUI 终端交互版**（见路线图）

---

## 架构

```
dictdb/
├── __main__.py        python -m dictdb 入口
├── cli.py             CLI 适配器：argparse + 统一选择器 + 二次确认 + 退出码
├── output.py          输出层：JSON 信封 / 中文对齐表格 / stderr 确认
└── core/              业务层 —— CLI 唯一入口共用
    ├── models.py      字段规范 / 分类归一 / 选择器解析 / 错误码 / 公共 JSON 表示
    ├── database.py    SQLite：WAL、索引、CRUD、导出导入（短连接，线程安全）
    ├── storage.py     store 副本 / link 解析 / .bak 备份 / 序号缓存
    ├── fileops.py     流式 md5 / 行数 / 替换 / 追加 / 行读取（字节级，不转码）
    ├── gitops.py      .git 探测 / ls-remote / 浅克隆取文件
    └── service.py     业务编排：plan（只读预检）→ execute（执行）两段式
```

性能设计：元数据查询走 SQLite 索引（几千条毫秒级；数据量上万时在 search
层升级 FTS5 trigram 中文全文索引，接口不变）；文件统计与内容读取全部流式
分块，内存占用与字典体积无关。

---

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| v1 | CLI + JSON 协议 + export/import | ✅ 已完成 |
| v1.1 | 命令体系重构：统一选择器 / git 命令组 / edit / info / 分类归一 | ✅ 已完成 |
| v1.2 | 界面语言：英文默认 + `--lang zh` / `DICTDB_LANG` 切中文（双语消息目录） | ✅ 已完成 |
| v1.3 | 拆除兼容层：移除全部别名与旧语法，单一命令面 | ✅ 已完成 |
| v1.4 | 收缩定位：移除 HTTP API 与 MCP，专注本地字典管理 | ✅ 已完成 |
| v1.5 | AI 消费优化：select JSON 默认 9 字段投影 + `--full`；show 缺省限流 20 行 + `--head 0` 全文 | ✅ 已完成（67 项测试通过） |
| 下一步 | **TUI 终端交互版**（Textual）：方向键选字典、实时模糊搜索、右侧内容预览 | 优先开发 |
| ~~Web GUI~~ / ~~MCP~~ | 本地使用场景下收益不足 | ❌ 已放弃 |

---

## 注意事项

- **link 模式会直接修改原文件**（update/追加/git pull），确认页有显著警告；
  不确定时用默认 copy 模式
- 字典文件按字节处理、不做转码，GBK / UTF-8 字典均可；行数按 `\n` 统计
- replace / git 拉取前自动在文件旁留 `.bak`；删除前强制确认
- md5 相同的内容重复 add 会被拦截（`--force` 跳过），这是特性不是故障
- 分类和标签建议保持英文（`-c dir -t dir,web`），中文输入会自动转换但存储统一为英文
- 中文界面（`--lang zh`）下 cmd 控制台乱码时先执行 `chcp 65001`，或使用 Windows Terminal / Git Bash

---

## License

[MIT](LICENSE) © shadowke
