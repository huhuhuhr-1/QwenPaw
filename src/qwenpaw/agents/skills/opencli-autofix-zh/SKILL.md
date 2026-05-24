---
name: opencli-autofix
description: Automatically fix broken OpenCLI adapters when commands fail. Load this skill when an opencli command fails — it guides you through collecting a trace artifact, patching the adapter, retrying, and filing an upstream GitHub issue after a verified fix. Works with any AI agent.
allowed-tools: Bash(opencli:*), Bash(gh:*), Read, Edit, Write
---

# OpenCLI AutoFix — 适配器自动修复

当 `opencli` 命令因网站更改了 DOM、API 或响应模式而失败时，**自动诊断、修复适配器并重试**——不要只是报告错误。

## 安全边界

**开始任何修复前，检查这些硬性停止点：**

- **`AUTH_REQUIRED`**（退出码 77）——**停止。** 不要修改代码。告诉用户在 Chrome 中登录该站点。
- **`BROWSER_CONNECT`**（退出码 69）——**停止。** 不要修改代码。告诉用户运行 `opencli doctor`。
- **CAPTCHA / 速率限制**——**停止。** 不是适配器问题。

**范围约束：**
- **只修改 trace `summary.md` front matter 中 `adapterSourcePath` 对应的文件**——这是权威的适配器位置（可能是仓库中的 `clis/<site>/` 或 npm 安装的 `~/.opencli/clis/<site>/`）
- **永远不要修改** `src/`、`extension/`、`tests/`、`package.json` 或 `tsconfig.json`

**重试预算：** 每失败一次最多 **3 轮修复**。如果 3 轮诊断 → 修复 → 重试都无法解决，停止并报告已尝试的内容。

## 先决条件

```bash
opencli doctor    # 验证扩展 + 守护进程连接
```

## 何时使用此 Skill

当 `opencli <site> <command>` 因可修复的错误而失败时使用：
- **SELECTOR**——元素未找到（DOM 已更改）
- **EMPTY_RESULT**——无数据返回（API 响应已更改）
- **API_ERROR / NETWORK**——端点移动或损坏
- **PAGE_CHANGED**——页面结构不再匹配
- **COMMAND_EXEC**——适配器逻辑中的运行时错误
- **TIMEOUT**——页面加载方式不同，适配器等待了错误的内容

## 进入修复前："空" ≠ "坏了"

`EMPTY_RESULT`——有时结构有效的 `SELECTOR` 返回空——通常是**不是适配器 bug**。平台会主动在反爬 heuristics 下降级结果，网站的"未找到"响应并不意味着内容真的丢失。在提交修复轮次前**先排除这种情况**：

- **使用替代查询或入口重试。** 如果 `opencli xiaohongshu search "X"` 返回 0，但 `opencli xiaohongshu search "X 攻略"` 返回 20，适配器没问题——平台在塑造第一个查询的结果。
- **在正常 Chrome 标签页中抽查。** 如果数据在用户自己的浏览器中可见，但适配器返回空，问题通常是认证状态、速率限制或软阻止——不是代码 bug。修复方法是 `opencli doctor` / 重新登录，而不是编辑源码。
- **寻找软 404。** 像小红书 / 微博 / 抖音这样的网站在内容被隐藏或删除时返回 HTTP 200 和空负载，而不是真正的 404。快照在结构上看起来是正确的。2-3 秒后重试通常能区分"暂时隐藏"和"真的没了"。
- **"0 结果"是搜索的答案。** 如果适配器成功到达搜索端点，获得 HTTP 200，且平台返回 `results: []`，这是有效的答案——向用户报告"此查询无匹配"，而不是修补适配器。

只有当空/选择器缺失的结果**在重试和替代入口中可复现**时才进入第 1 步。否则你是在修补一个正常工作的适配器来追逐噪音，修补后的版本会破坏下一个正常工作的路径。

## 第 1 步：收集 Trace 上下文

使用保留失败 trace 的方式运行失败的命令：

```bash
opencli <site> <command> [args...] --trace retain-on-failure 2>trace-error.yaml
```

失败时，stderr 包含正常错误信封加一个小的 `trace` 块：

```yaml
ok: false
error:
  code: SELECTOR
  message: "Could not find element: .old-selector"
trace:
  schemaVersion: 1
  opencliVersion: "..."
  traceId: "..."
  dir: "/path/to/.opencli/profiles/default/traces/..."
  summaryPath: "/path/to/.opencli/profiles/default/traces/.../summary.md"
  receiptPath: "/path/to/.opencli/profiles/default/traces/.../receipt.json"
```

首先阅读 `summaryPath`。这是面向 LLM 的入口点，包含 front matter：

```yaml
---
schemaVersion: 1
opencliVersion: "..."
traceId: "..."
status: failure
site: "example"
command: "example/search"
adapterSourcePath: "/path/to/clis/example/search.js"
errorCode: "SELECTOR"
errorMessage: "Could not find element: .old-selector"
---
```

artifact 目录包含：

```text
summary.md      # 从这里开始
receipt.json    # 机器可读的 trace 收据
trace.jsonl     # 完全编辑的时间线
network.jsonl   # 编辑后的网络事件
console.jsonl   # 编辑后的控制台事件
state/          # 最终快照（如果有）
screenshots/    # 最终截图（如果有）
```

如果重定向了 stderr 到文件，阅读该文件并复制 `trace.summaryPath`。

不要让用户使用旧诊断环境变量重新运行。Trace 是修复证据路径。

## 第 2 步：分析失败

阅读 trace 摘要和适配器源码。分类根本原因：

| 错误码 | 可能原因 | 修复策略 |
|-----------|-------------|-----------------|
| SELECTOR | DOM 重组，class/id 重命名 | 探索当前 DOM → 找到新选择器 |
| EMPTY_RESULT | API 响应模式改变，或数据移动 | 检查网络 → 找到新响应路径 |
| API_ERROR | 端点 URL 改变，需要新参数 | 通过网络拦截发现新 API |
| AUTH_REQUIRED | 登录流程改变，cookie 过期 | **停止**——告诉用户登录，不要修改代码 |
| TIMEOUT | 页面加载方式不同，spinner/lazy-load | 添加/更新等待条件 |
| PAGE_CHANGED | 重大重新设计 | 可能需要完整适配器重写 |

**需要回答的关键问题：**
1. 适配器在尝试做什么？（阅读 `adapterSourcePath` 对应的文件）
2. 失败时页面是什么样子？（阅读 `summary.md`，然后如果需要阅读 `state/`）
3. 发生了什么网络请求？（阅读 `summary.md` 中的 `Failed Network`，然后如果需要阅读 `network.jsonl`）
4. 适配器期望的和页面提供的内容之间有什么差距？

## 第 3 步：探索当前网站

使用 `opencli browser` 检查实时网站。**永远不要使用损坏的适配器**——它只会再次失败。

### DOM 改变了（SELECTOR 错误）

```bash
# 打开页面并检查当前 DOM
opencli browser open https://example.com/target-page && opencli browser state

# 查找匹配适配器意图的元素
# 将快照与适配器期望的内容进行比较
```

### API 改变了（API_ERROR、EMPTY_RESULT）

```bash
# 打开页面并使用网络拦截器，然后手动触发操作
opencli browser open https://example.com/target-page && opencli browser state

# 交互以触发 API 调用
opencli browser click <N> && opencli browser network

# 通过其 body 应有的字段缩小你关心的请求
opencli browser network --filter author,text,likes

# 检查特定 API 响应（key 是默认 JSON 输出中的 `key` 字段）
opencli browser network --detail <key>
```

## 第 4 步：修补适配器

阅读 trace 摘要 front matter 中 `adapterSourcePath` 对应的适配器源文件，并进行有针对性的修复。这个路径是权威的——可能在仓库（`clis/`）或用户本地（`~/.opencli/clis/`）。

使用 `Read` 工具读取 summary.md front matter 中的确切路径。

### 常见修复

**选择器更新：**
```typescript
// 之前：page.evaluate('document.querySelector(".old-class")...')
// 之后：page.evaluate('document.querySelector(".new-class")...')
```

**API 端点变更：**
```typescript
// 之前：const resp = await page.evaluate(`fetch('/api/v1/old-endpoint')...`)
// 之后：const resp = await page.evaluate(`fetch('/api/v2/new-endpoint')...`)
```

**响应模式变更：**
```typescript
// 之前：const items = data.results
// 之后：const items = data.data.items  // API 现在嵌套在 "data" 下
```

**等待条件更新：**
```typescript
// 之前：await page.wait({ selector: '.loading-spinner', hidden: true })
// 之后：await page.wait({ selector: '[data-loaded="true"]' })
```

### 修补规则

1. **做最小更改**——只修复坏的部分，不要重构
2. **保持相同的输出结构**——`columns` 和返回格式必须保持兼容
3. **优先使用 API 而不是 DOM 抓取**——如果在探索期间发现了 JSON API，切换到它
4. **只使用 `@jackwener/opencli/*` 导入**——永远不要添加第三方包导入
5. **修补后测试**——再次运行命令验证
6. **永远不要为了消除失败而放宽 `verify/<cmd>.json` fixtures。** 失败的 `patterns` / `notEmpty` / `mustNotContain` / `mustBeTruthy` 规则意味着适配器输出已损坏。收紧适配器使其产生正确的值；不要放宽 fixture 来接受损坏的值。编辑 fixture 的唯一合法原因是**网站本身**改变了形状（例如 URL 格式迁移）——在这种情况下更新 fixture 并在 `~/.opencli/sites/<site>/notes.md` 中注明变更。否则编辑 fixture 就是在掩盖静默的正确性回归。

## 第 5 步：验证修复

```bash
# 正常运行命令
opencli <site> <command> [args...]
```

如果仍然失败，回到第 1 步收集新的 trace。你有 **3 轮修复**的预算（trace → 修复 → 重试）。如果相同错误在修复后仍然存在，尝试不同的方法。3 轮后，停止并报告已尝试的内容。

## 第 6 步：提交上游 Issue

如果重试**通过**了，本地适配器已与上游漂移。提交 GitHub issue 以便修复流回 `jackwener/OpenCLI`。

**不要为此提交：**
- `AUTH_REQUIRED`、`BROWSER_CONNECT`、`ARGUMENT`、`CONFIG`——环境/使用问题，不是适配器 bug
- CAPTCHA 或速率限制——无法通过上游修复
- 你实际无法修复的失败（3 轮耗尽）

**只有在本地修复验证通过后才提交**——重试必须先通过。

**流程：**

1. 从你已有的 trace 摘要准备 issue 内容：
   - **标题：** `[autofix] <site>/<command>: <error_code>`（例如 `[autofix] zhihu/hot: SELECTOR`）
   - **正文**（使用此模板）：

```markdown
## 摘要
OpenCLI autofix 在本地修复了此适配器，重试通过。

## 适配器
- 站点：`<site>`
- 命令：`<command>`
- OpenCLI 版本：`<version from opencli --version>`

## 原始失败
- 错误码：`<error_code>`

~~~
<error_message>
~~~

## 本地修复摘要

~~~
<1-2 句描述你改变了什么以及为什么>
~~~

_由 OpenCLI autofix 在验证本地修复后提交的 issue。_
```

2. **提交前询问用户。** 展示草稿标题和正文。只有在用户确认后才继续。

3. 如果用户批准且 `gh auth status` 成功：

```bash
gh issue create --repo jackwener/OpenCLI \
  --title "[autofix] <site>/<command>: <error_code>" \
  --body "<上述正文>"
```

如果 `gh` 未安装或未认证，告诉用户并跳过——不要报错。

## 何时停止

**硬性停止（不要修改代码）：**
- **AUTH_REQUIRED / BROWSER_CONNECT**——环境问题，不是适配器 bug
- **网站需要 CAPTCHA**——无法自动化
- **速率限制 / IP 被阻止**——不是适配器问题

**软性停止（尝试后报告）：**
- **3 轮修复耗尽**——停止，报告已尝试的内容和失败的内容
- **功能完全移除**——数据不再存在
- **重大重新设计**——需要通过 `opencli-adapter-author` skill 完整重写适配器

在所有停止情况下，清楚地与用户沟通情况，而不是做无意义的修补。

## 修复会话示例

```
1. 用户运行：opencli zhihu hot
   → 失败：SELECTOR "Could not find element: .HotList-item"

2. AI 运行：opencli zhihu hot --trace retain-on-failure 2>trace-error.yaml
   → 获取带有最终状态和失败动作证据的 trace 摘要

3. AI 阅读摘要/state：页面加载了但使用 ".HotItem" 而不是 ".HotList-item"

4. AI 探索：opencli browser open https://www.zhihu.com/hot && opencli browser state
   → 确认新的类名 ".HotItem" 及其子元素 ".HotItem-content"

5. AI 修补：在 `adapterSourcePath` 编辑适配器——将 ".HotList-item" 替换为 ".HotItem"

6. AI 验证：opencli zhihu hot
   → 成功：返回热门话题

7. AI 准备上游 issue 草稿，展示给用户

8. 用户批准 → AI 运行：gh issue create --repo jackwener/OpenCLI --title "[autofix] zhihu/hot: SELECTOR" --body "..."
```