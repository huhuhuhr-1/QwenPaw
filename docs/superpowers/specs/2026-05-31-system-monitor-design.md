# System Monitor Plugin - 设计文档

**版本**：1.0.0  
**日期**：2026-05-31  
**状态**：已批准

---

## 1. 概述

**插件名称**：`system-monitor`  
**类型**：Bundle 插件（frontend）  
**端口**：7900

系统监控插件用于采集、分析、展示主机系统的运行状态，帮助用户了解当前系统的可行性，定位资源占用异常的服务。

---

## 2. 技术栈

| 层级 | 技术选型 |
|------|----------|
| 后端框架 | FastAPI |
| 数据采集 | psutil |
| 数据存储 | SQLite |
| 前端框架 | React + Ant Design |
| 图表库 | ECharts |
| 端口 | 7900 |

---

## 3. 采集指标

### 3.1 系统级指标

| 指标类型 | 采集内容 | 单位 |
|----------|----------|------|
| CPU | 使用率、核心数、负载 (1/5/15min) | % |
| 内存 | 总量、使用量、使用率 | % / GB |
| 磁盘 | 各分区总量/使用量/使用率 | GB / % |
| 句柄 | 系统级文件描述符总数 | count |
| 负载 | 1min/5min/15min 负载均值 | float |

### 3.2 进程级指标

| 指标类型 | 采集内容 | 单位 |
|----------|----------|------|
| CPU | 各进程 CPU 占用率 | % |
| 内存 | 各进程内存占用 | MB |
| 句柄 | 各进程文件描述符数 | count |

---

## 4. 数据模型

### 4.1 系统级指标表

```sql
CREATE TABLE system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    metric_type TEXT NOT NULL,  -- cpu/memory/disk/handle/load
    name TEXT,                   -- 分区名/负载类型等
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    INDEX idx_timestamp (timestamp),
    INDEX idx_metric_type (metric_type),
    INDEX idx_timestamp_type (timestamp, metric_type)
);
```

### 4.2 进程级指标表

```sql
CREATE TABLE process_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    pid INTEGER NOT NULL,
    name TEXT NOT NULL,           -- 进程名
    cpu_percent REAL NOT NULL,
    memory_mb REAL NOT NULL,
    num_fds INTEGER NOT NULL,
    INDEX idx_timestamp (timestamp),
    INDEX idx_name (name),
    INDEX idx_timestamp_name (timestamp, name)
);
```

### 4.3 配置表

```sql
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

---

## 5. 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `interval` | int | 5 | 采集频率（秒） |
| `enabled_metrics` | dict | 全部开启 | 各指标开关 |
| `retention_days` | int | 7 | 数据保留天数 |
| `disk_partitions` | list | 全部 | 监控的分区 |

---

## 6. API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/config` | 获取配置 |
| PUT | `/api/config` | 更新配置 |
| POST | `/api/cleanup` | 手动清理数据 |
| GET | `/api/metrics/current` | 当前系统指标 |
| GET | `/api/metrics/trend/{type}` | 趋势数据 (cpu/memory/disk/handle/load) |
| GET | `/api/metrics/top/{type}` | Top N 实时排名 (cpu/memory/handle) |
| GET | `/api/metrics/process/top` | 进程 Top N（支持时间段筛选） |
| GET | `/api/metrics/services` | 服务汇总状态 |

### 6.1 API 详情

#### GET /api/metrics/current
返回当前系统指标。

**响应**：
```json
{
  "cpu": { "percent": 45.2, "cores": 8, "load": [0.52, 0.48, 0.41] },
  "memory": { "total": 32.0, "used": 20.1, "percent": 62.8 },
  "disk": [{ "mount": "/", "total": 500.0, "used": 234.5, "percent": 46.9 }],
  "handles": { "total": 12345 },
  "load": { "1min": 0.52, "5min": 0.48, "15min": 0.41 }
}
```

#### GET /api/metrics/process/top
进程 Top N，支持时间段筛选。

**参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `type` | string | cpu/memory/handle |
| `start` | datetime | 开始时间（可选） |
| `end` | datetime | 结束时间（可选） |
| `limit` | int | 返回数量，默认 20 |

**响应**：
```json
{
  "type": "cpu",
  "start": "2026-05-31T00:00:00",
  "end": "2026-05-31T01:00:00",
  "data": [
    { "name": "chrome", "pid": 1234, "avg_value": 15.2, "max_value": 45.6 },
    { "name": "python", "pid": 5678, "avg_value": 8.5, "max_value": 22.1 }
  ]
}
```

---

## 7. 目录结构

```
plugins/system-monitor/
├── plugin.json
├── plugin.py              # 插件入口
├── requirements.txt
├── app/
│   ├── main.py            # FastAPI 入口
│   ├── config.py          # 配置管理
│   ├── db/
│   │   ├── sqlite.py      # SQLite 操作封装
│   │   └── models.py      # 数据模型
│   ├── routers/
│   │   ├── metrics.py     # 指标数据 API
│   │   ├── config_api.py  # 配置 API
│   │   └── health.py      # 健康检查 API
│   └── services/
│       ├── collector_cpu.py     # CPU 采集
│       ├── collector_memory.py  # 内存采集
│       ├── collector_disk.py    # 磁盘采集
│       ├── collector_handle.py  # 句柄采集
│       ├── collector_process.py # 进程采集
│       ├── scheduler.py    # 采集调度器
│       └── cleaner.py      # 数据清理
├── frontend/
│   ├── src/
│   │   └── plugin-entry.ts
│   └── dist/
│       └── index.js
└── skills/
    └── SKILL.md
```

---

## 8. 前端页面布局

### 8.1 主监控页面

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo] 系统监控        [时间范围 ▼] [刷新频率] [⚙ 设置]     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │   CPU   │ │   内存   │ │   负载   │ │  句柄   │ │  磁盘   │ │
│  │  45%   │ │  62%   │ │  0.52  │ │ 12345  │ │  47%   │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │
├─────────────────────────────────────────────────────────────┤
│  视图: [●图表] [○列表]                                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐   │
│  │            CPU 变更趋势 (ECharts 折线图)              │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            内存变更趋势 (ECharts 折线图)              │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            负载趋势 (ECharts 折线图)                  │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  进程排名: [●CPU] [○内存] [○句柄]  时间: [最近1小时 ▼]    │
├─────────────────────────────────────────────────────────────┤
│  进程名          PID       CPU%    内存     句柄数        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ chrome         1234     15.2%   512MB    256        │   │
│  │ python         5678     8.5%    256MB    128        │   │
│  │ ...                                                    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 配置页面

```
┌─────────────────────────────────────────────┐
│  ◀ 返回监控                                 │
├─────────────────────────────────────────────┤
│  系统监控设置                                │
├─────────────────────────────────────────────┤
│  采集频率    [5] 秒                         │
│                                             │
│  指标开关                                    │
│  ☑ CPU                                     │
│  ☑ 内存                                    │
│  ☑ 磁盘                                    │
│  ☑ 句柄                                    │
│  ☑ 进程级指标                              │
│                                             │
│  数据保留    [7] 天                         │
│                                             │
│  [保存配置]                                 │
├─────────────────────────────────────────────┤
│  数据管理                                    │
│  当前数据: 12,345 条记录 (约 45MB)          │
│  最早记录: 2026-05-24                       │
│  最新记录: 2026-05-31                       │
│                                             │
│  [立即清理全部] [按日期范围清理]             │
└─────────────────────────────────────────────┘
```

---

## 9. 采集策略

### 9.1 调度策略

- 使用 `asyncio` + `aiofiles` 实现定时采集
- 默认采集间隔：5 秒（可配置）
- 系统级指标和进程级指标同时采集
- 采集器独立运行，异常不影响整体

### 9.2 缓存策略

- Top N 计算结果缓存 5 秒
- 避免频繁查询数据库

### 9.3 数据清理

- 启动时检查并清理超过保留期限的数据
- 提供手动清理 API
- 清理时显示影响的数据量

---

## 10. 依赖项

```
# requirements.txt
psutil>=5.9.0
fastapi>=0.104.0
uvicorn>=0.24.0
apsw>=3.42.0
pydantic>=2.0.0
```

---

## 11. 验收标准

1. ✅ 配置页面可调整采集频率、指标开关、保留天数
2. ✅ 实时显示 CPU、内存、负载、句柄、磁盘使用率
3. ✅ 趋势图展示各指标随时间变化
4. ✅ 列表视图展示各指标明细
5. ✅ 支持时间范围筛选历史数据
6. ✅ 进程 Top20 支持按时间段查询
7. ✅ 手动清理数据功能
8. ✅ 配置持久化到 SQLite
