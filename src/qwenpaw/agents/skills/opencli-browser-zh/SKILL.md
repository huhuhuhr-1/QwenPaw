---
name: opencli-browser
description: Use when an agent needs to drive a real Chrome window via opencli — inspect a page, fill forms, click through logged-in flows, or extract data ad-hoc. Covers the selector-first target contract, compound form fields, stale-ref handling, network capture, and the agent-native envelopes the CLI returns. Not for writing adapters — see opencli-adapter-author for that.
allowed-tools: Bash(opencli:*), Read, Edit, Write
---

# opencli-browser

这个 CLI 的第一个读者是代理，不是人。每个子命令都返回一个结构化的信封，准确告诉你匹配了什么、匹配置信度如何，以及如果不匹配该怎么办。利用这些信封——不要猜测。

这个 skill 是用于**驱动实时浏览器**来完成代理任务的。如果你要在 `~/.opencli/clis/<site>/` 下构建可复用的适配器，请使用 `opencli-adapter-author`。

---

## 先决条件

```bash
opencli doctor
```

在 `doctor` 变绿之前，其他都不可用。典型失败：Chrome 未运行、扩展未安装、调试端口被 1Password / 其他扩展阻止。doctor 输出会告诉你哪个出了问题。

---

## 会话生命周期

- `opencli browser *` 命令需要 `--session <name>`。多步流程使用相同的会话名；使用不同的名称来隔离并行浏览器工作。
- 拥有的浏览器会话在调用之间保持标签页租约。使用 `opencli browser --session <name> close` 或让空闲超时过期来释放它。
- `opencli browser bind --session <name>` 将你已经打开/登录的 Chrome 标签页绑定到该浏览器会话。用于已登录页面、SSO 流程，或在将控制权交给代理之前你手动定位好的页面。
- `--window foreground|background`（或 `OPENCLI_WINDOW=foreground|background`）选择 OpenCLI 是否为拥有的会话创建/聚焦前台浏览器窗口或使用后台浏览器窗口。

### 绑定标签页

```bash
opencli browser bind --session gmail
opencli browser --session gmail state
opencli browser --session gmail click "Search"
opencli browser --session gmail network
opencli browser unbind --session gmail
```

绑定永远不会拥有用户窗口，也永远不会关闭用户标签页。如果标签页关闭或变得不可调试，绑定会失败关闭。当切换到不同的真实标签页时，重新运行 `bind --session <name>`。

绑定会话上允许导航，因为会话现在代表该标签页的显式代理所有权。标签页变更（`tab new`、`tab select`、`tab close`）仍然对绑定会话阻止。当你想让 OpenCLI 管理标签页生命周期时，使用拥有的会话。

`opencli browser sessions` 对绑定会话返回 `idleMsRemaining: null`。这意味着没有 OpenCLI 空闲关闭计时器；绑定持续到 `unbind`、标签页关闭、窗口关闭或守护进程重启。

---

## 思维模型

1. **选择器优先目标契约。** 每个交互命令（`click`、`type`、`select`、`get text/value/attributes`）接受一个 `<target>`，它*要么*是 `state`/`find` 的数字引用，*要么*是 CSS 选择器。使用 `--nth <n>` 来消除多个 CSS 匹配的歧义。
2. **每个信封都报告 `matches_n` 和 `match_level`。** `match_level` 是 `exact`、`stable` 或 `reidentified`——CLI 已经为你抢救了适度的 DOM 漂移，但级别告诉你置信度如何。
3. **先紧凑输出，按需全量。** `state` 是预算感知的快照；`get html --as json` 支持 `--depth/--children-max/--text-max`；`network` 返回形状预览，你用 `--detail <key>` 重新获取单个 body。如果你发出巨大的 payload，你是在燃烧你不需要的上下文。
4. **结构化错误是机器可读的。** 失败时 CLI 发出 `{error: {code, message, hint?, candidates?}}`。基于 `code` 分支，而不是消息字符串。

---

## 关键规则

1. **行动前先检查。** 先运行 `state` 或 `find`。永远不要跨会话硬编码来自记忆的引用或选择器——索引是按快照的。
2. **一旦有了数字引用就优先使用它。** 数字引用能承受轻微的 DOM 漂移，因为 CLI 会对每个标记元素进行指纹识别。手写的 CSS 选择器会在站点重新渲染的第一次就坏掉。
3. **每次写操作后读取 `match_level`。** `exact` = 一切正常。`stable` = 元素相同但一些软属性漂移了——你的操作仍然适用。`reidentified` = 原始引用已消失，CLI 找到了匹配的唯一实时元素并用旧引用重新标记；在链接更多写操作之前，仔细检查你击中了正确的元素。
4. **使用 `compound` 字段处理表单控件。** 不要 regex 猜测日期格式，不要 `state` 两次来获取完整的 `<select>` 选项列表。compound 信封有格式字符串、最多 50 个完整选项列表、`options_total` 用于溢出，以及 `<input type=file>` 的 `accept`/`multiple`。
5. **验证重要的写操作。** 在 `type <target> <text>` 后，运行 `get value <target>`。在 `select` 后，运行 `get value`。自动完成小组件、React 受控输入和掩码字段都会静默吞掉字符。CLI 无法为你检测到这一点。
6. **`state` → 动作 → 页面改变后 `state`。** 导航、表单提交和 SPA 路由更改会使引用失效。获取新的快照。不要重用转换前的引用。
7. **用 `&&` 链接。** 链接的序列在一个 shell 中运行，因此第一个命令获取的引用对第二个保持活动。单独的 shell 调用会丢失你刚刚设置的会话上下文。
8. **`eval` 是只读的。** 将 JS 包装在 IIFE 中并返回 JSON。如果需要*改变*页面，使用结构化的 `click` / `type` / `select` / `keys` 命令——它们产生结构化输出和指纹，`eval` 不会。
9. **优先使用 `network` 而不是屏幕抓取。** 如果你关心的页面从 JSON API 获取数据，API 几乎总是比刮取渲染 DOM 更可靠。捕获一次，检查形状，然后 `--detail <key>` 你需要的 body。

---

## 目标契约（`click / type / select / get text|value|attributes` 的 `<target>`）

```
<target> ::= <numeric-ref> | <css-selector>
```

- **数字引用**——来自 `state` 或 `find` 的 `[N]` 索引。便宜，能承受软 DOM 漂移。
- **CSS 选择器**——`querySelectorAll` 接受的任何东西。写操作必须无歧义，或配合 `--nth <n>`。

### 成功时的信封

```json
{ "clicked": true, "target": "3", "matches_n": 1, "match_level": "exact" }
```

```json
{ "value": "kalevin@example.com", "matches_n": 1, "match_level": "stable" }
```

### match_level

| 级别 | 含义 | 你应该 |
|-------|---------|------------|
| `exact` | 指纹同意 tag + 强 ID，最多一个软漂移 | 继续。 |
| `stable` | Tag + 强 ID 仍然一致，软信号（aria-label、role、text）漂移了 | 继续，但如果*你*输入/点击的内容很重要，用 `get value` 或 `state` 重新检查。 |
| `reidentified` | 原始引用已消失；唯一实时元素匹配指纹并用旧引用重新标记 | 在链接更多写操作之前，仔细检查你击中了正确的元素。 |

### 结构化错误码

基于这些分支，而不是人类消息：

| 代码 | 含义 |
|------|------|
| `not_found` | 数字引用已不在 DOM 中。重新 `state`。 |
| `stale_ref` | 引用存在但该引用的元素改变了身份。重新 `state`。 |
| `invalid_selector` | CSS 被 `querySelectorAll` 拒绝。修复选择器。 |
| `selector_not_found` | CSS 匹配 0 个元素。用更宽松的选择器尝试 `find`。 |
| `selector_ambiguous` | CSS 匹配 >1 个且没有 `--nth`。添加 `--nth` 或缩小选择器。 |
| `selector_nth_out_of_range` | `--nth` 超出匹配数量。 |
| `option_not_found` | `select` 找不到匹配该 label/value 的选项。错误信封包含真实选项标签的 `available: string[]`。 |
| `not_a_select` | `select` 被调用在非 `<select>` 元素上。 |

错误信封总是包含 `error.code` 和 `error.message`。目标错误（`selector_not_found`、`selector_ambiguous` 等）经常添加 `error.candidates: string[]` 包含建议的选择器。`option_not_found` 改为添加 `error.available: string[]`。

---

## 命令参考

### 检查

| 命令 | 用途 |
|---------|---------|
| `browser state` | 快照：带 `[N]` 引用的文本树、滚动提示、隐藏交互提示、`compounds (N):` 日期/select/file 引用的边车。 |
| `browser state --source ax` | 可选的辅助功能树快照。当自定义控件、portal 或 iframe 内容在正常 `state` 中难以识别时使用。AX 引用可以通过 role/name/nth 恢复陈旧的 React 重渲染，并可以路由同源 iframe 引用。跨域 iframe 引用是尽力的，因为 Chrome 可能不会向扩展暴露可附加的 OOPIF 目标。 |
| `browser state --compare-sources` | 仅指标的 DOM vs AX 比较，用于决定 AX 是否应成为默认。它打印计数和大小，不是页面文本，因此对于验证更安全共享。 |
| `browser find --css <sel> [--limit N] [--text-max N]` | 运行 CSS 查询并为每个匹配返回一个条目，包含 `{nth, ref, tag, role, text, attrs, visible, compound?}`。为之前快照未标记的匹配分配引用。当你已经知道选择器时，廉价的 `state` 替代方案。 |
| `browser find --role button --name Save` | 语义定位器查询。也支持 `--label`、`--text` 和 `--testid`。当控件有可访问标签时，在原始 CSS 之前使用。 |
| `browser frames` | 列出跨域 iframe 目标。传递索引到 `eval` 的 `--frame`。 |
| `browser screenshot [path]` | 视口 PNG。无路径 → base64 到 stdout。需要结构时优先 `state`。 |
| `browser screenshot --annotate [path]` | 视觉引用地图。刷新 DOM 引用并覆盖可见 `[N]` 标签，以便截图映射回 `browser click <ref>` 目标。用于仅图标控件、视觉布局、图表，或当文本状态不明确时。 |

### 获取（只读）

| 命令 | 返回 |
|---------|---------|
| `browser get title` | 纯文本 |
| `browser get url` | 纯文本 |
| `browser get text <target> [--nth N]` | `{value, matches_n, match_level}` |
| `browser get value <target> [--nth N]` | `{value, matches_n, match_level}` |
| `browser get attributes <target> [--nth N]` | `{value: {attr: val, ...}, matches_n, match_level}` |
| `browser get text --role option --name Travel` | 语义定位器读取，无需先调用 `state`。与 `browser find` 相同的标志。 |
| `browser get html [--selector <css>] [--as html\|json] [--depth N] [--children-max N] [--text-max N] [--max N]` | 原始 HTML 或结构化树。JSON 树节点有 `{tag, attrs, text, children[], compound?}`。通过 `truncated: {depth?, children_dropped?, text_truncated?}` 报告截断。 |

### 交互

| 命令 | 备注 |
|---------|---------|
| `browser click <target> [--nth N]` | 返回 `{clicked, target, matches_n, match_level}`。 |
| `browser click --role button --name Submit` | 语义点击。写操作需要唯一匹配；歧义定位器返回候选而不是点击第一个匹配。 |
| `browser hover [target] [--role R --name N] [--nth N]` | 将鼠标移到元素上。用于悬停菜单/工具提示，然后获取 `state` 或点击子菜单项。返回 `{hovered, target, matches_n, match_level}`。 |
| `browser focus [target] [--role R --name N] [--nth N]` | 聚焦元素但不输入。在 `keys` 之前或页面响应 focus/blur 时有用。返回 `{focused, target, matches_n, match_level}`。 |
| `browser dblclick [target] [--role R --name N] [--nth N]` | 通过原生鼠标事件双击元素（如果有）。返回 `{dblclicked, target, matches_n, match_level}`。 |
| `browser check [target] [--role R --name N] [--nth N]` | 确保 checkbox/radio/aria-checked 控件被选中。返回 `{checked, changed, target, matches_n, match_level, kind}`。当目标状态重要时优先使用这个，而不是盲目 `click`。 |
| `browser uncheck [target] [--role R --name N] [--nth N]` | 确保 checkbox/aria-checked 控件未选中。Radio 按钮不能直接取消选中；选择同组的另一个。 |
| `browser upload [target] <file...> [--role R --name N] [--nth N]` | 通过 CDP 将本地文件路径附加到 `input[type=file]`。使用语义标志时，省略 `target` 并将文件作为位置参数传递。返回 `{uploaded, files, file_names, target, matches_n, match_level, multiple?, accept?}`。 |
| `browser drag [source] [target] [--from-role R --from-name N] [--to-role R --to-name N] [--from-nth N] [--to-nth N]` | 从一个解析元素中心到另一个的基于鼠标的拖动。适用于鼠标监听器拖动库；原生 HTML5 `dataTransfer` 拖放可能需要特定于站点的回退。返回 `{dragged, source, target, source_matches_n, target_matches_n, ...}`。 |
| `browser type [target] <text> [--role R --name N] [--nth N]` | 先点击再输入。使用语义标志时，省略 `target` 并将文本作为唯一位置参数传递。返回 `{typed, text, target, matches_n, match_level, autocomplete}`。`autocomplete: true` 意味着在输入后出现了组合框/datalist 弹出——你几乎总是需要 `keys Enter` 或后续 `click` 来提交值。 |
| `browser fill [target] <text> [--role R --name N] [--nth N]` | input、textarea 和 contenteditable 目标的精确替换。使用语义标志时，省略 `target` 并将文本作为唯一位置参数传递。返回 `{filled, verified, text, actual, matches_n, match_level}`。当你需要设置并验证原始文本，而不是键盘/自动完成行为时使用这个。管道表单支持 `{ fill: { ref, text, submit: true } }`。 |
| `browser select [target] <option> [--role R --name N] [--nth N]` | 先按 label 再按 value 匹配原生 `<select>` 选项。使用语义标志时，省略 `target` 并将选项作为唯一位置参数传递。使用 `find`/`state` 的 `compound` 查看确切可用的标签。 |
| `browser keys <key>` | `Enter`、`Escape`、`Tab`、`Control+a` 等。针对焦点元素运行。 |
| `browser scroll <direction> [--amount px]` | `up` / `down`。默认量 `500`。 |

### 等待

```bash
browser wait selector "<css>" [--timeout ms]    # 等待选择器匹配
browser wait text "<substring>" [--timeout ms]  # 等待文本出现
browser wait download [pattern] [--timeout ms]  # 等待 Chrome 下载（文件名/URL/mime 包含 pattern）
browser wait time <seconds>                     # 硬睡眠，最后手段
```

默认超时 `10000` ms。SPA 路由、登录重定向和懒加载列表需要在 `state`/`get` 之前 `wait`。

`browser wait download` 需要 Browser Bridge 扩展 1.0.8+，因为它使用 Chrome 的下载生命周期 API。尽可能传递窄的文件名或 URL 子字符串（如 `receipt.pdf`）；空 pattern 在超时窗口内等待下一个/最近的下载。命令在成功时报告 `{downloaded, filename, url, state, elapsedMs}`，在超时/失败时报告 JSON 错误信封。

### 提取

- **`web read --url <url>`**——任意页面的一次性 Markdown 阅读器。默认展开相关同源 iframe，因此旧的 iframe-shell 站点比仅顶部文档抓取效果更好。当完整性比 Markdown 噪音更重要时使用 `--frames all-same-origin`。对于 AJAX shell 页面使用 `opencli web read --url <url> --wait-for "<selector>" --wait-until networkidle --diagnose`；诊断显示 frame URL、空容器和 API 类 XHR。如果你需要的是 table/API 数据，切换到 `browser network` 或专用适配器，而不是依赖 Markdown。
- **`browser eval <js> [--frame N]`**——在页面中运行表达式（通过 `--frame` 进入跨域 frame）。包装在 IIFE 中并返回 JSON。只读：不要 `document.forms[0].submit()`、不要 clicks、不要 导航。如果结果是字符串，stdout 是原始字符串；否则是 JSON。
- **`browser extract [--selector <css>] [--chunk-size N] [--start N]`**——带续游标的长格式内容 Markdown 提取。返回 `{url, title, selector, total_chars, chunk_size, start, end, next_start_char, content}`。循环 `next_start_char` 直到它是 `null`。如果不传 `--selector`，自动作用域到 `<main>`/`<article>`/`<body>`。

### 网络

```bash
browser network                        # 形状预览 + 缓存 key 列表
browser network --detail <key>         # 一个缓存条目的完整 body
browser network --filter "field1,field2"  # 只保留 body 形状对所有字段作为路径段匹配的条目
browser network --all                  # 包含静态资源（通常是噪音）
browser network --raw                  # 内联完整 body——大；谨慎使用
browser network --ttl <ms>             # 缓存 TTL（默认 24h）
```

列表条目看起来像 `{key, method, status, url, ct, size, shape, body_truncated?}`。详情信封是 `{key, url, method, status, ct, size, shape, body, body_truncated?, body_full_size?, body_truncation_reason}`。缓存位于 `~/.opencli/cache/browser-network/`，因此你可以重新检查而无需重新触发请求。

默认输出保留 JSON/XML/plain-text 和 JS 类 API 响应，然后通过 URL 删除明显的静态资源和遥测。如果预期端点缺失，运行 `browser network --all` 一次并检查是否是不寻常的内容类型或 URL 过滤将其隐藏。

### 标签页和会话

| 命令 | 用途 |
|---------|---------|
| `browser tab list` | JSON 数组 `{index, page, url, title, active}`。`page` 字符串是你传递给 `tab select` / `tab close` 的标签页标识，或传递给任何子命令的 `--tab <targetId>`。（`--tab` 的占位符是历史上的——值始终是 `page`。） |
| `browser tab new [url]` | 打开新标签页。打印新的 `page` 字符串。 |
| `browser tab select [targetId]` | 使标签页成为默认。所有子命令接受 `--tab <targetId>` 以在不更改默认的情况下定位一个。 |
| `browser tab close [targetId]` | 按 `page` 关闭。 |
| `browser back` | 活动标签页的历史后退。 |
| `browser close` | 完成后释放当前拥有的浏览器会话。 |
| `browser bind --session <name>` | 将当前 Chrome 标签页绑定到浏览器会话。 |
| `browser unbind --session <name>` | 分离绑定会话而不关闭用户标签页/窗口。 |

---

## 复合表单控件

每个日期/时间、select 和 file input 都带有一个 `compound` 字段。使用它——不要 regex 属性。

### 日期系列

```json
{
  "control": "date",
  "format": "YYYY-MM-DD",
  "current": "2026-04-21",
  "min": "2026-01-01",
  "max": "2026-12-31"
}
```

`control` 是 `date | time | datetime-local | month | week` 之一。`format` 是一个具体的模板字符串——使用该确切的格式输入字段，或者如果站点将原生 input 包装在自定义小部件中则按 label `select`。

### Select

```json
{
  "control": "select",
  "multiple": false,
  "current": "United States",
  "options": [
    { "label": "United States", "value": "us", "selected": true },
    { "label": "Canada", "value": "ca" }
  ],
  "options_total": 137
}
```

`options[]` 最多 50 个条目上限。**`current` 始终正确**——即使所选选项past the cap——因为它是通过扫描每个选项计算的，而不是从截断列表中获取的。如果 `options_total > options.length` 且你需要的选项不在 `options[]` 中，直接调用 `browser select <target> "<label>"`——CLI 匹配实时 DOM，而不是截断列表。

### 文件

```json
{
  "control": "file",
  "multiple": true,
  "current": ["report.pdf", "cover.png"],
  "accept": "application/pdf,image/*"
}
```

不要编造文件路径。上传通过正常 click 流程完成——在告诉用户要上传什么时遵守 `accept`。

### Compound 出现在哪里

- `browser find --css <sel>` 条目：每个匹配的 inline。
- `browser get html --as json` 树节点：匹配节点的 inline。
- `browser state` 快照：在 `compounds (N):` 边车中按键numeric ref 键入，这样你一眼就能看出哪个 `[N]` 条目有丰富的元数据。

---

## 成本指南

每次调用考虑 payload 大小。预算是有原因的。

| 命令 | 大概成本 | 何时使用 |
|---------|-----------|-------------|
| `state` | 中（受内部预算限制） | 任何页面上的第一次调用，每次导航后，需要引用时。 |
| `find --css <sel>` | 小 | 你已经知道选择器——一个查询，紧凑条目。 |
| `get title` / `get url` | 微 | 步骤之间的理智检查。 |
| `get text/value/attributes` | 每次调用微 | 验证一个特定字段。 |
| `get html`（原始） | 可能很大 | 在无界页面上避免。总配合 `--selector` 和预算。 |
| `get html --as json --depth 3 --children-max 20` | 中 | 当你需要推理结构而不是特定字段时。 |
| `screenshot` | 大 | 仅当页面是视觉的（CAPTCHA、图表）。优先 `state`。 |
| `extract` | 每块中 | 长格式阅读。通过 `next_start_char` 循环。 |
| `network`（默认） | 小 | 第一次看 API。 |
| `network --detail <key>` | 变化 | 拉取一个 body。 |
| `network --raw` | 大 | 仅在 `--filter` 缩小候选集之后。 |
| `eval "JSON.stringify(...)"` | 受控 | 当上述都不适合时的目标提取。 |

经验法则：**每次页面转换一次 `state`，每次后续查询一次 `find`，每次动作一次 `get`/`click`/`type`。** 如果你的计划涉及每页 >10 次调用，你可能是在抓取而不是交互——考虑 `extract` 或 `network`。

---

## 链接规则

**好——一个 shell，活动会话：**

```bash
opencli browser --session hn open "https://news.ycombinator.com" \
  && opencli browser --session hn state \
  && opencli browser --session hn click 3
```

**坏——每行是一个新的 shell，call 1 的引用在 call 2 运行时已经被遗忘。**（只有当你依赖 shell 作用域状态时才是问题；浏览器引用本身在页面内持久化，但交错无关 shell 会引入竞态。）当步骤意味着原子性时优先使用 `&&`。

**永远不要**在写操作后立即链 `state` 而不 `wait` 如果动作导致网络往返——你会 snapshot 预响应 DOM 并基于过时数据做出糟糕决策。

---

## 配方

### 填写登录表单

```bash
opencli browser --session login open "https://example.com/login"
opencli browser --session login state                          # 找到 [N] 用于 email、password、submit
opencli browser --session login type 4 "me@example.com"
opencli browser --session login type 5 "hunter2"
opencli browser --session login get value 4                    # 验证（自动完成可能吃掉字符）
opencli browser --session login click 6                        # 提交
opencli browser --session login wait selector "[data-testid=account-menu]" --timeout 15000
opencli browser --session login state                          # 登录页面上的新引用
```

### 从长下拉菜单选择

```bash
opencli browser --session form state                          # 侧边栏显示 [12] <select name=country>
opencli browser --session form find --css "select[name=country]"
# compound.options_total 是 137，但 compound.current 是 "" —— 未选择。
opencli browser --session form select 12 "Uruguay"
opencli browser --session form get value 12                   # { value: "uy", match_level: "exact" }
```

### 从自定义 React 下拉菜单选择

用于 Radix、shadcn、Material UI、Mercury 风格类别字段以及其他非原生 `<select>` 的控件。

```bash
opencli browser --session mercury state                          # 找到类别触发器引用
# 如果触发器/选项不清晰，使用 AX：
opencli browser --session mercury state --source ax              # 查找 combobox/button/listbox/option names
opencli browser --session mercury click 7                        # 点击类别触发器
opencli browser --session mercury state --source ax              # portal/listbox 打开后的新引用
opencli browser --session mercury click 12                       # 点击选项
opencli browser --session mercury get text 7                     # 验证可见的选定标签
```

不要对这些小组件使用 `browser select`。`browser select` 仅适用于原生 `<select>` 元素。自定义下拉菜单应该用 `state -> click trigger -> state -> click option -> verify` 驱动。

### 比较 DOM vs AX 观察

在决定 AX 引用是否更适合页面时，收集指标但不共享页面内容：

```bash
opencli browser --session compare state --compare-sources
```

报告 `sources.dom.refs`、`sources.ax.refs`、`frame_sections`、`approx_tokens`、`elapsed_ms` 和每个源的 `error`。在你论证 AX 应该成为站点默认之前使用这个。

### 通过网络而不是 DOM 抓取列表

```bash
opencli browser --session hn open "https://news.ycombinator.com"
opencli browser --session hn network --filter "title,score"
# -> 找到 /topstories 条目，记下它的 key
opencli browser --session hn network --detail topstories-a1b2
```

### 分块读取长文章

```bash
opencli browser --session article open "https://blog.example.com/long-post"
opencli browser --session article extract --chunk-size 8000
# -> content + next_start_char: 8000
opencli browser --session article extract --start 8000 --chunk-size 8000
# ...直到 next_start_char 是 null
```

### 跨域 iframe

```bash
opencli browser --session checkout frames
# -> [{"index": 0, "url": "https://checkout.stripe.com/...", ...}]
opencli browser --session checkout eval "(() => document.querySelector('input[name=cardnumber]')?.value)()" --frame 0
```

`browser state --source ax` 可能省略跨域 iframe 内容，或在 Chrome 不向扩展暴露可附加 OOPIF 目标时无法路由操作到其中。在这种情况下使用 `browser frames` + `browser eval --frame`、正常 DOM `state`，或直接导航/绑定到 iframe URL。

---

## 陷阱

- **不要通过 `eval "document.forms[0].submit()"` 提交表单**——现代站点用 JS 处理程序拦截并静默丢弃调用。要么通过其引用 `click` 提交按钮，要么（如果你知道 GET URL）直接 `open` 它。
- **不要在页面转换后重用引用。** `wait` 新状态，然后重新 `state`。旧引用要么 404，要么（更糟）重新识别到新页面上相似形状的元素。
- **`match_level: reidentified` 是警告，不是错误。** 操作成功了，但如果你链接了 5 个更多都依赖于那是正确元素的写操作，在继续之前用 `get text` 或 `get value` 验证。
- **预算感知命令静默截断。** 默认预算的 `get html --as json` 将返回 `truncated: {...}`。如果你的下游逻辑需要整个子树，提高 `--depth` / `--children-max` 或缩小选择器。
- **`type` 响应上的 `autocomplete: true` 不是错误。** 这意味着弹出了建议弹出框，你的值还没提交。通常需要 `keys Enter` 或后续 `click` 你想要的建议。
- **`network --filter` 是路径段上的 AND 语义。** `--filter "title,score"` 保留 body 形状*同时*包含 `title` 和 `score` 作为路径段的条目，任意深度。这不是 regex。
- **截图是给人类的，不是给代理的。** 使用 `state` + `find` 除非页面真的是视觉的（captcha、图表）。截图燃烧 token，很少能为代理添加可操作的信号。

---

## 故障排除

| 症状 | 修复 |
|--------|------|
| `opencli doctor` 红色："Browser not connected" | 用 `--remote-debugging-port=9222` 启动 Chrome，或从 [Chrome Web Store](https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk) 安装扩展。 |
| `attach failed: chrome-extension://...` | 暂时禁用 1Password / 其他 CDP 占用扩展。 |
| `state` 后立即 `selector_not_found` | 页面已突变。`wait selector "..."` 然后重试。 |
| 每个命令都 `stale_ref` | 你在重用之前页面的引用。重新 `state`。 |
| `click` 成功但什么都没发生 | 元素可能是一个装饰性包装器，偷走了对真实目标的点击。用更窄的选择器 `find --css "..."` 并在内元素上重试。 |
| `type` 似乎完成但值错误 | 自动完成、掩码输入或 React 受控重新渲染。用 `get value` 验证。添加 `keys Enter` 或重新输入。 |
| 巨大的 `get html` 输出 | 传递 `--selector` + `--as json --depth 3 --children-max 20 --text-max 200`。 |
| 网络缓存似乎过时 | 降低 `--ttl`，或让它过期。缓存位于 `~/.opencli/cache/browser-network/`。 |

---

## 另见

- `opencli-adapter-author`——把你刚刚发现的东西变成可复用的 `~/.opencli/clis/<site>/<command>.js`。
- `opencli-autofix`——当现有适配器损坏时，这个 skill 引导你收集 `--trace retain-on-failure` 证据并提交修复。