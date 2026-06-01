# 自定义插件规范审计

**日期**: 2026-05-31
**审计范围**: github-trending、media-studio、system-monitor、todo
**参考基准**: docker-search、time_now（官方 tool 插件）

---

## 审计结论

| 插件 | type 错误 | deps 缺失 | 前端未构建 | 脏文件 | 阻断安装？ |
|------|-----------|-----------|------------|--------|------------|
| github-trending | ❌ frontend → general | ✅ | ✅ | ⚠️ pycache, .db | ⚠️ type 可能跳过 register |
| media-studio | ❌ frontend → general | 🔴 缺 8 个 | ✅ | 🔴 .venv | 🔴 |
| system-monitor | ❌ frontend → general | 🔴 缺 4 个 | ✅ | ⚠️ .db | 🔴 |
| todo (bundle) | ✅ general | 🔴 缺 3 个 | ❌ 无 dist | ⚠️ pycache | 🔴 |

---

## 逐项详情

### 一、github-trending

#### plugin.json
- `type: "frontend"` — **应改为 `"general"`**。理由：注册了 13 个 agent tool + 有后端子进程 + 有前端页面
- `dependencies: ["httpx>=0.26.0"]` — 与 requirements.txt 一致 ✅

#### plugin.py
- 注册了 13 个 tool + startup/shutdown hook ✅
- 使用 `sys.path.insert(0, ...)` 实现导入（不够优雅但可以工作）
- **缺少 skill 安装逻辑**（media-studio 和 system-monitor 都有 `_install_plugin_skills()`）

#### skills/
- 只有一个 `skills/SKILL.md`，不是标准的 skill 子目录结构
- SKILL.md 内容问题：
  - 硬编码路径 `/home/hr/.qwenpaw/plugins/github-trending/`（不可移植）
  - BOM 排查说明引用了 fastapi（github-trending 不需要 fastapi，疑似从 media-studio 抄来的）

#### 前端
- `frontend/dist/index.js` 已构建 ✅

---

### 二、media-studio

#### plugin.json — 🔴 阻断
- `type: "frontend"` — **应改为 `"general"`**
- `dependencies: ["httpx>=0.26.0"]` — **严重不对等！**

requirements.txt 实际需要：
```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
aiosqlite>=0.20.0
openai>=1.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-multipart>=0.0.9
httpx>=0.28.0
```

#### plugin.py
- 有完整 skill 安装 + 后端子进程管理 ✅
- 不注册 agent tool（全靠后端 API）— 这其实合理

#### skills/
- 4 个标准子目录：media / polish / transcribe / workflow ✅
- SKILL.md frontmatter 格式正确（有 name/description） ✅

#### 前端
- `frontend/dist/index.js` 已构建 ✅
- vite config 中 `external: []` 为空 — IIFE 模式应 external React/antd

#### 脏文件 — 🔴
- 源码中含有 `.venv/` 虚拟环境目录
- 含有 `uv.lock`、`pyproject.toml`、`.dockerignore` 等项目管理文件

---

### 三、system-monitor

#### plugin.json — 🔴 阻断
- `type: "frontend"` — **应改为 `"general"`**
- `dependencies: []` — **空数组！**

requirements.txt 实际需要：
```
psutil>=5.9.0
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.0.0
```

#### plugin.py
- 有完整 skill 安装 + 后端子进程管理 ✅
- 声明 `_PLUGIN_SKILLS = ("sysmon",)` 但 skills 目录下是 `SKILL.md` 文件而非 `sysmon/` 子目录

#### 前端
- `frontend/dist/index.iife.js` 已构建 ✅
- vite config 正确 external 了 react/react-dom ✅

---

### 四、todo (bundle)

#### plugin.json — 🔴 阻断
- `type: "general"` ✅
- `dependencies: []` — **空数组！** 实际 import 了 fastapi/pydantic/agentscope
- `entry.frontend: "dist/index.js"` — vite 构建输出到 `../dist`（即插件根目录的 dist/index.js），路径匹配正确

#### plugin.py
- 注册了 4 个 tool + HTTP router + startup hook ✅
- 使用相对导入 `.api.routes` ✅
- 缺少 `__all__ = ["plugin"]`

#### 前端 — 🔴
- **未构建！** `frontend/` 有源码但没有 `dist/`
- 构建命令：`cd frontend && npm install && npm run build`

#### skills/
- 完全没有 ❌

---

## 修复优先级

### 第一批（阻断安装的 bug）
1. **media-studio**: 补充 `dependencies`、改 `type`、删除 `.venv`
2. **system-monitor**: 补充 `dependencies`、改 `type`
3. **todo**: 补充 `dependencies`、构建前端

### 第二批（规范性问题）
4. **github-trending**: 改 `type`、修复 SKILL.md、添加 skill 安装逻辑

### 第三批（清理）
5. 所有插件清理 `__pycache__`、`*.pyc`、`*.db`
