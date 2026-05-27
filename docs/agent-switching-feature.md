# 智能体切换功能 — 设计实现文档

## 概述

QwenPaw 前端支持**多智能体切换**，用户可在不同智能体工作区间无缝切换。该功能通过**双模式布局系统**实现：智能体模式（Agent Mode）面向终端用户的简洁聊天体验，全配置模式（Config Mode）面向管理员的完整功能面板。

两个模式共享同一套后端 API（`/agents` 路由、`MultiAgentManager`、`X-Agent-Id` 中间件），差异仅在前端 UI 层。

---

## 整体架构

### 双模式布局

```
App.tsx
  └── AgentModeProvider (Context)
        ├── Header  ← 根据 isAgentMode 渲染不同内容
        └── MainLayout  ← 根据 isAgentMode 切换布局
              ├── Agent Mode (isAgentMode=true)
              │     ├── AgentSidebar   卡片式智能体列表
              │     └── AgentChatView  聊天页 + 智能体头部
              └── Config Mode (isAgentMode=false)
                    ├── Sidebar        完整管理菜单
                    │     └── AgentSelector  下拉式智能体选择
                    └── Routes         所有管理页面路由
```

### 状态流转

```
用户点击切换按钮
  → AgentModeContext.toggleAgentMode()
    → localStorage.setItem("qwenpaw_agent_mode", ...)
      → isAgentMode 变更
        → Header 条件渲染刷新
        → MainLayout 切换布局分支
```

### localStorage 持久化策略

| Key | 存储位置 | 用途 |
|-----|---------|------|
| `qwenpaw_agent_mode` | localStorage | 当前模式（true=智能体模式, false=全配置模式），默认 true |
| `qwenpaw-agent-storage` | sessionStorage + localStorage | Zustand 智能体状态（selectedAgent, agents 列表, lastChatIdByAgent） |
| `qwenpaw-last-used-agent` | localStorage | 最近使用的智能体 ID，新标签页自动继承 |

---

## 逐文件说明

### 1. AgentModeContext.tsx — 模式开关

**路径**: `console/src/contexts/AgentModeContext.tsx`

整个双模式系统的核心。一个 React Context，提供 `isAgentMode` 布尔值 + `toggleAgentMode()` 切换方法。

```tsx
// 核心逻辑
const [isAgentMode, setIsAgentModeState] = useState<boolean>(() => {
  const stored = localStorage.getItem("qwenpaw_agent_mode");
  return stored !== null ? stored === "true" : true;  // 默认智能体模式
});

useEffect(() => {
  localStorage.setItem("qwenpaw_agent_mode", String(isAgentMode));
}, [isAgentMode]);

const toggleAgentMode = () => setIsAgentModeState((prev) => !prev);
```

**导出接口**:
- `AgentModeProvider` — 包裹整个应用的 Provider 组件，在 `App.tsx` 中使用
- `useAgentMode()` — 消费 hook，返回 `{ isAgentMode, setIsAgentMode, toggleAgentMode }`

**消费方**:
- `Header.tsx` — 控制 Logo/导航/切换按钮
- `MainLayout/index.tsx` — 控制布局分支

---

### 2. Header.tsx — 双模式差异集中地

**路径**: `console/src/layouts/Header.tsx`

这是双模式差异**最集中**的文件，三处条件渲染：

**差异 A — Logo 区域** (第 158-187 行)：

```
isAgentMode=true  → 显示文字 "智能体团队"
isAgentMode=false → 显示 Logo 图片 + 版本号 vX.X.X（带更新红点）
```

```tsx
{isAgentMode ? (
  <span className={styles.agentTeamTitle}>智能体团队</span>
) : (
  <>
    <img src={isDark ? "/logo-dark.svg" : "/logo-light.svg"} ... />
    <div className={styles.logoDivider} />
    {version && (
      <Badge dot={!!hasUpdate} ...>
        <span ...>v{version}</span>
      </Badge>
    )}
  </>
)}
```

**差异 B — 导航链接** (第 190-222 行)：

```
isAgentMode=true  → 不显示任何导航链接
isAgentMode=false → 显示 changelog / docs / faq / github 四个链接
```

```tsx
{!isAgentMode && (
  <>
    <Button ...>{t("header.changelog")}</Button>
    <Button ...>{t("header.docs")}</Button>
    <Button ...>{t("header.faq")}</Button>
    <Button ...>{t("header.github")}</Button>
  </>
)}
```

**差异 C — 模式切换开关** (第 224-240 行)：

两种模式下都显示，用于在两个模式间切换。是一个 iOS 风格的 toggle 按钮，左侧 "全配置"，右侧 "智能体"。

```tsx
<div className={styles.modeSwitch}>
  <span className={`${styles.modeLabel} ${!isAgentMode ? styles.modeLabelActive : ""}`}>
    全配置
  </span>
  <button className={`${styles.modeToggle} ${isAgentMode ? styles.modeToggleActive : ""}`}
          onClick={toggleAgentMode}>
    <span className={styles.modeToggleKnob} />
  </button>
  <span className={`${styles.modeLabel} ${isAgentMode ? styles.modeLabelActive : ""}`}>
    智能体
  </span>
</div>
```

**除上述三处外**，Header 其余部分（版本检查、更新弹窗、语言切换、主题切换）两种模式共用。

---

### 3. MainLayout/index.tsx — 双模式布局分支

**路径**: `console/src/layouts/MainLayout/index.tsx`

根据 `isAgentMode` 渲染完全不同的布局：

```tsx
// Agent Mode: 简化布局
if (isAgentMode) {
  return (
    <Layout>
      <Header />
      <Layout>
        <AgentSidebar />
        <div>
          <ConsolePollService />
          <AgentChatView />
        </div>
      </Layout>
    </Layout>
  );
}

// Config Mode: 完整功能布局
return (
  <Layout>
    <Header />
    <Layout>
      <Sidebar selectedKey={selectedKey} />
      <Content>
        <ConsolePollService />
        <Suspense>
          <Routes>
            {/* 20+ 管理页面路由 */}
          </Routes>
        </Suspense>
      </Content>
    </Layout>
  </Layout>
);
```

**关键差异**：
| | Agent Mode | Config Mode |
|---|---|---|
| 侧边栏 | `AgentSidebar`（卡片式智能体列表） | `Sidebar`（完整管理菜单 + AgentSelector） |
| 主内容区 | `AgentChatView`（聊天 + 智能体头部） | `Routes`（所有管理页面路由） |
| 可用页面 | 仅聊天 | 聊天 + 所有管理页面 |

---

### 4. AgentSelector — 下拉式智能体选择器

**路径**: `console/src/components/AgentSelector/index.tsx`

用于 **Config Mode** 的 Sidebar 中，渲染为一个 Ant Design `Select` 下拉框。

**核心行为**:
- 挂载时调用 `agentsApi.listAgents()`，启用智能体排前面
- `handleChange` 阻止切换到已禁用智能体
- `useEffect` 自动回退：当前选中的智能体被删除/禁用时自动切回 `"default"`
- 折叠模式（`collapsed=true`）：仅显示 Bot 图标 + Tooltip
- 展开模式：显示完整下拉框，包含智能体名称、描述、启用/禁用标签、当前选中标记
- 下拉框头部有 "管理" 链接跳转到 `/agents` 页面

**使用位置**: `Sidebar.tsx` 第 577 行
```tsx
<AgentSelector collapsed={collapsed} />
```

---

### 5. AgentSidebar — 卡片式智能体侧边栏

**路径**: `console/src/components/AgentSidebar.tsx`

用于 **Agent Mode**，渲染为一个 280px 宽的垂直侧边栏。

**核心行为**:
- 每个智能体显示为一张卡片：彩色头像（名称前两字）+ 名称 + 描述 + 在线状态圆点
- 支持搜索过滤（按名称或描述）
- 点击卡片 → `setSelectedAgent(agent.id)` → `clearUnread(agent.id)`
- 未读消息数角标（超过 99 显示 "99+"）
- 7 种渐变色头像，根据名称 hash 分配

---

### 6. AgentChatView — 智能体模式聊天包装

**路径**: `console/src/components/AgentChatView.tsx`

用于 **Agent Mode**，在 ChatPage 上方添加智能体信息头部。

**头部内容**: 当前智能体名称 + 在线/离线状态圆点（绿色/灰色）

**智能体切换逻辑**:
- `useEffect` 监听 `selectedAgent` 变化
- 切换时保存当前聊天 ID 给旧智能体 (`setLastChatId`)
- 恢复新智能体的最近聊天 ID (`getLastChatId`)
- 自动导航到对应聊天页

```tsx
useEffect(() => {
  const prevAgent = prevAgentRef.current;
  if (prevAgent === selectedAgent) return;
  // 保存旧智能体聊天
  if (currentChatId && prevAgent) setLastChatId(prevAgent, currentChatId);
  // 恢复新智能体聊天
  const lastChatId = getLastChatId(selectedAgent);
  navigate(lastChatId ? `/chat/${lastChatId}` : "/chat", { replace: true });
}, [selectedAgent]);
```

---

### 7. agentStore.ts — 智能体状态管理

**路径**: `console/src/stores/agentStore.ts`

Zustand + persist 实现，双层存储策略。

**状态字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `selectedAgent` | string | 当前选中的智能体 ID，默认 `"default"` |
| `agents` | AgentSummary[] | 所有智能体列表 |
| `lastChatIdByAgent` | Record<string, string> | 每个智能体的最近聊天 ID |
| `unreadCountByAgent` | Record<string, number> | 每个智能体的未读消息数 |

**存储机制**:
- `sessionStorage` → 每个标签页独立的 `selectedAgent`
- `localStorage` → 跨标签页共享的 `agents` 列表 + `lastChatIdByAgent`
- `localStorage` 额外 key `qwenpaw-last-used-agent` → 新标签页继承最近的智能体选择

**优先级链** (初始化 selectedAgent):
```
sessionStorage → localStorage(lastUsed) → localStorage(shared) → "default"
```

---

### 8. authHeaders.ts — X-Agent-Id 请求头注入

**路径**: `console/src/api/authHeaders.ts`

每次 API 请求自动附加当前选中的智能体 ID：

```tsx
export function buildAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  // ... token ...
  const agentStorage =
    sessionStorage.getItem("qwenpaw-agent-storage") ||
    localStorage.getItem("qwenpaw-agent-storage");
  if (agentStorage) {
    const parsed = JSON.parse(agentStorage);
    const selectedAgent = parsed?.state?.selectedAgent;
    if (selectedAgent) headers["X-Agent-Id"] = selectedAgent;
  }
  return headers;
}
```

后端 `AgentContextMiddleware` 读取 `X-Agent-Id` 头，将请求路由到对应的智能体 Workspace。

---

### 9. Sidebar.tsx — 侧边栏集成点

**路径**: `console/src/layouts/Sidebar.tsx`

在 Config Mode 侧边栏中集成 AgentSelector。关键代码（第 575-590 行）：

```tsx
<div className={styles.agentScopedSection}>
  <div className={styles.agentSelectorContainer}>
    <AgentSelector collapsed={collapsed} />
    <button className={styles.stickyChatButton} onClick={() => navigate(chatPath)}>
      <SparkChatTabFill size={16} />
      <span>{t("nav.chat")}</span>
    </button>
  </div>
  <Menu items={agentMenuItems} ... />
</div>
```

AgentSelector 和 Chat 按钮被包裹在 `agentScopedSection` 中，视觉上分组在一起。折叠模式下整个 section 隐藏，替换为扁平图标列表。

---

### 10. Chat/index.tsx — 智能体切换时的会话管理

**路径**: `console/src/pages/Chat/index.tsx`

ChatPage 中有两处智能体切换相关逻辑：

**a) 初始挂载恢复** (第 967-982 行)：首次渲染时，如果 URL 不包含会话 ID，从 `getLastChatId(selectedAgent)` 恢复上次聊天。

**b) 智能体切换处理** (第 984-1007 行)：
- 保存当前聊天 ID 给旧智能体
- 恢复新智能体的最近聊天
- `setRefreshKey(prev => prev + 1)` 强制重新挂载聊天组件

---

## 移除步骤

以下步骤将**移除智能体切换 UI**，使主页面仅保留 Config Mode（全配置模式），与上游 main 分支对齐。

**原则**：
- 不删除组件文件（AgentSelector、AgentSidebar、AgentChatView），仅移除引用
- agentStore.ts 和 authHeaders.ts 保留不动（X-Agent-Id 注入逻辑仍需要，只是不暴露 UI 切换）
- 后端完全不动

### 步骤 1：Header.tsx — 移除模式切换

1. **删除** `import { useAgentMode } from "../contexts/AgentModeContext";`
2. **删除** `const { isAgentMode, toggleAgentMode } = useAgentMode();`
3. **修改 Logo 区域**：删除 `isAgentMode ? ... : ...` 三元表达式，直接保留 Config Mode 分支（Logo + 版本号）
4. **删除导航链接的条件包裹**：移除 `{!isAgentMode && ( ... )}` 外层，直接保留四个导航链接
5. **删除**整个 `modeSwitch` div（模式切换开关，约 15 行）

### 步骤 2：MainLayout/index.tsx — 移除布局分支

1. **删除** `import { useAgentMode } from "../../contexts/AgentModeContext";`
2. **删除** `import AgentSidebar from "../../components/AgentSidebar";`
3. **删除** `import AgentChatView from "../../components/AgentChatView";`
4. **删除** `const { isAgentMode } = useAgentMode();`
5. **删除**整个 `if (isAgentMode) { return (...); }` 分支（第 98-111 行）

### 步骤 3：AgentModeContext.tsx — 删除文件

直接删除 `console/src/contexts/AgentModeContext.tsx`。

### 步骤 4：Sidebar.tsx — 移除 AgentSelector

1. **删除** `import AgentSelector from "../components/AgentSelector";`
2. **删除** `{/* Agent-scoped section */}` 注释下方的 `<AgentSelector collapsed={collapsed} />` 调用（第 577 行，保留其容器 `<div className={styles.agentSelectorContainer}>` 的其余部分，Chat 按钮不动）

### 步骤 5：App.tsx — 移除 Provider 包裹

在 `console/src/App.tsx` 中：
1. **删除** `import { AgentModeProvider } from "./contexts/AgentModeContext";`
2. **移除** `<AgentModeProvider>` 包裹标签（保留 children 直接渲染）

### 步骤 6：验证

```bash
cd console && npm run build  # 应通过编译，无 AgentMode 相关引用报错
```

---

## 还原步骤

按以下顺序从空白状态恢复智能体切换功能。

### 步骤 1：还原 AgentModeContext.tsx

创建 `console/src/contexts/AgentModeContext.tsx`：

```tsx
import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

interface AgentModeContextValue {
  isAgentMode: boolean;
  setIsAgentMode: (v: boolean) => void;
  toggleAgentMode: () => void;
}

const AgentModeContext = createContext<AgentModeContextValue | null>(null);

const STORAGE_KEY = "qwenpaw_agent_mode";

export function AgentModeProvider({ children }: { children: ReactNode }) {
  const [isAgentMode, setIsAgentModeState] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored !== null ? stored === "true" : true;
    } catch {
      return true;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(isAgentMode));
    } catch {}
  }, [isAgentMode]);

  const setIsAgentMode = (v: boolean) => setIsAgentModeState(v);
  const toggleAgentMode = () => setIsAgentModeState((prev) => !prev);

  return (
    <AgentModeContext.Provider value={{ isAgentMode, setIsAgentMode, toggleAgentMode }}>
      {children}
    </AgentModeContext.Provider>
  );
}

export function useAgentMode(): AgentModeContextValue {
  const ctx = useContext(AgentModeContext);
  if (!ctx) throw new Error("useAgentMode must be used inside AgentModeProvider");
  return ctx;
}
```

### 步骤 2：还原 App.tsx

在 `console/src/App.tsx` 中：
1. 添加 `import { AgentModeProvider } from "./contexts/AgentModeContext";`
2. 用 `<AgentModeProvider>` 包裹应用根组件

### 步骤 3：还原 Header.tsx

1. 添加 `import { useAgentMode } from "../contexts/AgentModeContext";`
2. 添加 `const { isAgentMode, toggleAgentMode } = useAgentMode();`
3. Logo 区域恢复三元表达式（Agent Mode 显示 "智能体团队"，Config Mode 显示 Logo + 版本号）
4. 导航链接用 `{!isAgentMode && ( ... )}` 包裹
5. 添加模式切换开关（`modeSwitch` div）

### 步骤 4：还原 MainLayout/index.tsx

1. 添加三个 import：
   ```tsx
   import { useAgentMode } from "../../contexts/AgentModeContext";
   import AgentSidebar from "../../components/AgentSidebar";
   import AgentChatView from "../../components/AgentChatView";
   ```
2. 添加 `const { isAgentMode } = useAgentMode();`
3. 在 return 之前添加 Agent Mode 布局分支（`if (isAgentMode) { return ... }`）

### 步骤 5：还原 Sidebar.tsx

1. 添加 `import AgentSelector from "../components/AgentSelector";`
2. 在 `agentSelectorContainer` div 中，Chat 按钮上方添加 `<AgentSelector collapsed={collapsed} />`

### 步骤 6：验证

```bash
cd console && npm run build     # 编译通过
npm run dev                      # 启动开发服务器
# 浏览器验证：
#   - Header 显示模式切换按钮
#   - 切换到智能体模式 → 显示 AgentSidebar + AgentChatView
#   - 切换到全配置模式 → 显示完整侧边栏 + 管理页面
#   - 切换智能体后刷新页面 → 状态保持
```

---

## 涉及文件清单

### 需修改/删除的文件（移除时）

| 文件 | 操作 |
|------|------|
| `console/src/contexts/AgentModeContext.tsx` | **删除** |
| `console/src/App.tsx` | 修改：移除 Provider 包裹和 import |
| `console/src/layouts/Header.tsx` | 修改：移除 AgentMode 相关逻辑 |
| `console/src/layouts/MainLayout/index.tsx` | 修改：移除 Agent Mode 分支 |
| `console/src/layouts/Sidebar.tsx` | 修改：移除 AgentSelector |

### 保留不动的文件

| 文件 | 说明 |
|------|------|
| `console/src/stores/agentStore.ts` | 仍用于 X-Agent-Id 注入和智能体状态管理 |
| `console/src/api/authHeaders.ts` | X-Agent-Id 请求头注入保持不变 |
| `console/src/components/AgentSelector/` | 组件保留，仅不再被引用 |
| `console/src/components/AgentSidebar.tsx` | 组件保留，仅不再被引用 |
| `console/src/components/AgentChatView.tsx` | 组件保留，仅不再被引用 |
| `console/src/pages/Chat/index.tsx` | ChatPage 中的智能体切换逻辑保留 |
| `console/src/pages/Settings/Agents/` | 智能体管理页面保留 |
| `src/qwenpaw/app/routers/agents.py` | 后端 API 不变 |
| `src/qwenpaw/app/agent_context.py` | 后端中间件不变 |
| `src/qwenpaw/app/multi_agent_manager.py` | 后端管理器不变 |