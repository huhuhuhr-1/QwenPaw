---
name: opencli-usage
description: Use at the start of any OpenCLI session — this is the top-level map of what `opencli` can do, how to discover adapters, what flags and output formats are universal, and which specialized skill to load next. Point here when an agent asks "what can opencli do?" or "how do I find the right command?".
allowed-tools: Bash(opencli:*), Read
---

# opencli-usage

OpenCLI 将任何网站、Electron 桌面应用或外部 CLI 转换为统一的 `opencli <site> <command>` 界面，代理可以无需屏幕抓取即可驱动。本 skill 是入门指南——了解你想做什么后，加载下面相应的专业 skill。

## 三大支柱

- **适配器命令** — `opencli <site> <command> [...]`。内置适配器位于 `clis/`，用户适配器位于 `~/.opencli/clis/`。每个适配器都有策略标签（`PUBLIC | COOKIE | INTERCEPT | UI | LOCAL`），告诉你是否需要 Chrome 会话。
- **浏览器驱动** — `opencli browser *` 子命令（`open`、`state`、`click`、`type`、`select`、`find`、`extract`、`network` 等），用于当没有适配器覆盖任务时的临时浏览器交互和抓取。详见 `opencli-browser`。
- **当前标签页绑定** — `opencli browser bind --session <name>` 将用户已打开/登录的 Chrome 标签页绑定到该浏览器会话。后续命令使用 `opencli browser --session <name> ...`。使用前请先阅读 `opencli-browser`；绑定会话仍会阻止标签页变更。
- **外部 CLI 直通** — `opencli gh`、`opencli docker`、`opencli vercel` 等。通过 `opencli external install <name>`（从 `external-clis.yaml` 自动安装）或 `opencli external register <name>`（自备 CLI）管理。

## 安装

```bash
# npm 全局安装
npm install -g @jackwener/opencli          # 二进制文件：opencli，需要 Node >= 21
opencli doctor                              # 浏览器相关工作前运行（见下方说明）

# 从源码安装
git clone git@github.com:jackwener/OpenCLI.git
cd OpenCLI && npm install
npx tsx src/main.ts <command>               # 相同界面，无需全局安装
```

`opencli doctor` 输出结构化的 `DoctorReport`——守护进程状态、扩展连接、版本检查和实时浏览器连接探测。范围明确：诊断的是**浏览器桥**（守护进程 + 扩展 + Chrome 接线）。`PUBLIC` / `LOCAL` 适配器、`opencli list`、`validate`、`verify`、插件命令和外部 CLI 直通不需要此检查通过——只有 `COOKIE` / `INTERCEPT` / `UI` 适配器和 `opencli browser *` 子命令需要。标志：`-v`（详细）。

## 按命令类型的先决条件

| `opencli list` 上的策略标签 | 需要什么 |
|--------------------------------|------------|
| `PUBLIC` | 无——纯 HTTP，无需浏览器。 |
| `COOKIE` | Chrome 已登录目标站点 + **OpenCLI** 扩展已从 [Chrome Web Store](https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk) 安装。命令从你的实时会话中获取凭据——无需重新登录。 |
| `INTERCEPT` | 同 COOKIE，外加 opencli 打开自动化窗口以捕获签名请求。 |
| `UI` | 同 COOKIE，完全 DOM 交互。 |
| `LOCAL` | 无浏览器；连接本地/开发端点。 |

Electron 桌面应用（cursor、codex、chatwise、notion、discord-app、doubao-app、antigravity、chatgpt-app）通过 CDP 路由到运行中的应用——与登录浏览器相同的无 cookie 流程。调用前确保应用正在运行。

## 发现已安装内容——不要读本文档，运行命令

```bash
opencli list                    # 表格，按站点分组
opencli list -f json            # 机器可读；通过管道传给 jq 或你的代理
opencli list | grep -i twitter  # 查找特定站点的命令
opencli <site> --help           # 查看该站点的命令 + 标志
opencli <site> <command> --help # 查看位置参数和命令特定的标志
```

不要硬编码适配器列表——有 100+ 个站点且数量每周都在变化。`opencli list -f json` 是真实来源；它为每个命令发出一条记录，包含 `{site, name, aliases, description, strategy, browser, args, columns, ...}`。对于代理，这总比 grep 文档要好。

## 通用标志（适用于每个适配器命令）

| 标志 | 效果 |
|------|------|
| `-f, --format <fmt>` | `table`（TTY 默认）· `yaml`（非 TTY 默认）· `json` · `plain` · `md` · `csv`。需要特定格式时显式传递；代理几乎总是想要 `-f json`。 |
| `-v, --verbose` | 失败时的调试日志 + 堆栈跟踪；也为进程设置 `OPENCLI_VERBOSE=1`。 |

命令特定标志（`--limit`、`--tab`、`--filter` 等）不是通用的——查阅 `<site> <command> --help`。

## 输出格式

- `json` — pretty-printed，2 空格缩进。代理的默认选择。
- `plain` — 为聊天风格命令打印单个主字段（`response`/`content`/`text`/`value`）。适合传递给另一个工具。
- `yaml` — 非 TTY 输出且未显式指定 `-f` 时的默认格式。
- `table` — 彩色，按站点分组；面向人类。
- `md`、`csv` — 简单的表格转储。

少数命令通过 `cmd.defaultFormat` 覆盖默认格式（例如聊天命令默认为 `plain`），因此不读 `--help` 不要假设。

## 环境变量

| 变量 | 默认值 | 用途 |
|----------|---------|---------|
| `OPENCLI_DAEMON_PORT` | `19825` | 守护进程 ↔ 扩展桥接端口。 |
| `OPENCLI_BROWSER_CONNECT_TIMEOUT` | `30` | 等待浏览器桥接的秒数。 |
| `OPENCLI_BROWSER_COMMAND_TIMEOUT` | `60` | 每个命令的超时时间。 |
| `OPENCLI_CDP_ENDPOINT` | — | 手动 CDP 端点覆盖（开发 / 远程 Chrome / Electron）。 |
| `OPENCLI_CACHE_DIR` | `~/.opencli/cache` | 网络捕获 + 浏览器状态缓存。 |
| `OPENCLI_WINDOW` | 命令特定 | `foreground` 或 `background` 浏览器窗口模式。 |
| `OPENCLI_KEEP_TAB` | 命令特定 | `true` 或 `false`；控制命令后是否保持浏览器标签页租约。 |
| `OPENCLI_VERBOSE` | `false` | 详细日志（也由 `-v` 触发）。 |

## 自动修复

当适配器命令因网站更改（选择器漂移、API 轮换、响应模式改变）而失败时，使用 `--trace retain-on-failure` 重新运行。错误信封包含一个 `trace` 块，指向 `summary.md`；只修补该摘要中的 `adapterSourcePath` 并重试。最多 3 轮修复。完整流程见 `opencli-autofix`。

## 编写自己的适配器

两条存储路径：

- **私有**：`~/.opencli/clis/<site>/<command>.js`——无需构建步骤，热加载，不在公共包中可见。
- **公共 / PR**：`clis/<site>/<command>.js`——供上游贡献；需要构建。

脚手架和验证：

```bash
opencli browser init <site>/<command>   # 生成骨架
opencli validate [target]               # 对加载的注册表进行语义检查（描述、域名、管道步骤名称、func|pipeline|_lazy 存在性、参数重复）——无网络、无浏览器
opencli verify [target] [--smoke]       # 用合成参数运行命令
opencli browser verify <site>/<command> # 在桥内进行端到端冒烟测试
```

适配器只导入 `@jackwener/opencli/registry` 和 `@jackwener/opencli/errors`。`columns` 必须与 `func` 返回对象的键完全对齐（名称和顺序）。完整工作流程见 `opencli-adapter-author`。

## 插件

插件是从 git 拉取的第三方扩展，与主适配器注册表分离：

```bash
opencli plugin install github:user/repo    # 安装
opencli plugin list [-f json]              # 查看已安装
opencli plugin update [name] | --all       # 保持当前版本
opencli plugin uninstall <name>
opencli plugin create <name>               # 脚手架新插件
```

## 外部 CLI 直通

包装外部命令行工具，以便你可以通过相同的 `opencli …` 入口点发现和调用：

```bash
opencli external install gh    # 通过 brew/apt/npm 按 external-clis.yaml 自动安装
opencli external register my-tool \
    --binary my-tool \
    --install "npm i -g my-tool" \
    --desc "My internal CLI"
opencli external list
opencli gh pr list --limit 5   # 直通；stdio 被继承，退出码传播
opencli docker ps
```

内置条目位于 `src/external-clis.yaml`；用户覆盖和添加位于 `~/.opencli/external-clis.yaml`。通常包含：`gh`、`docker`、`vercel`、`lark-cli`、`dws`、`wecom-cli`、`obsidian`、`tg-cli`、`discord-cli`、`wx-cli`。

## Shell 补全

```bash
opencli completion bash   # 也支持：zsh、fish
# -> 输出脚本；按你的 shell 约定 source 或保存
```

## 下一步去哪

| 如果你要… | 加载此 skill |
|---------------------|-----------------|
| 临时驱动实时浏览器（无适配器可用，或原型） | `opencli-browser` |
| 编写新适配器，或向现有站点添加命令 | `opencli-adapter-author` |
| 命令失败后修复损坏的适配器 | `opencli-autofix` |
| 将搜索 / 查找 / 研究请求路由到正确的适配器 | `smart-search` |

## 已不存在的命令

以下在 PR #1094 合并中被移除——不要尝试调用：

- `opencli explore <url>` ——已被 `opencli browser network` + `opencli browser find` 取代，用于实时 API 发现，以及用于捕获的 `opencli-adapter-author` 工作流程。
- `opencli record <url>` ——已移除；手动捕获现位于 `opencli browser network --detail`。
- `opencli web read` / `opencli desktop *` 作为顶级组——已合并到各自的适配器中（`opencli web read` 仍作为 `web` 适配器的 `read` 命令存在，但没有独立的 `web` / `desktop` 顶级组命令）。

## 不要

- 不要将本 skill 的命令列表粘贴到你的计划中；它会过时。在任务开始时调用 `opencli list -f json`。
- 不要假设每个适配器都需要浏览器——`PUBLIC` 和 `LOCAL` 策略不需要。检查 `strategy` 字段。
- 不要在适配器失败时静默回退到手写的 `fetch`——`--trace retain-on-failure` 提供浏览器证据和适配器源路径。先这样做。
