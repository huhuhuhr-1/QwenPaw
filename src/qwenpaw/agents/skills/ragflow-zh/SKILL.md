---
name: ragflow
description: Universal Ragflow API client for RAG operations. Create datasets, upload documents, run chat queries against knowledge bases. Self-hosted RAG platform integration.
version: 1.0.2
author: Ania
env:
  RAGFLOW_URL:
    description: Ragflow instance URL (e.g., https://rag.example.com)
    required: true
  RAGFLOW_API_KEY:
    description: Ragflow API key (use least-privilege key, can manage datasets/upload files)
    required: true
metadata:
  clawdbot:
    emoji: "📚"
    requires:
      bins: ["node"]
---

# Ragflow API 客户端

Ragflow 的通用客户端——自托管 RAG（检索增强生成）平台。

## 功能

- **数据集管理**——创建、列出、删除知识库
- **文档上传**——上传文件或文本内容
- **聊天查询**——对知识库运行 RAG 查询
- **分块管理**——触发解析、列出分块

## 使用方法

```bash
# 列出数据集
node {baseDir}/scripts/ragflow.js datasets

# 创建数据集
node {baseDir}/scripts/ragflow.js create-dataset --name "我的知识库"

# 上传文档
node {baseDir}/scripts/ragflow.js upload --dataset DATASET_ID --file article.md

# 聊天查询
node {baseDir}/scripts/ragflow.js chat --dataset DATASET_ID --query "什么是中风？"

# 列出数据集中的文档
node {baseDir}/scripts/ragflow.js documents --dataset DATASET_ID
```

## 配置

在 `.env` 中设置环境变量：

```bash
RAGFLOW_URL=https://your-ragflow-instance.com
RAGFLOW_API_KEY=your-api-key
```

## API

此 skill 封装了 Ragflow 的 REST API：

- `GET /api/v1/datasets` — 列出数据集
- `POST /api/v1/datasets` — 创建数据集
- `DELETE /api/v1/datasets/{id}` — 删除数据集
- `POST /api/v1/datasets/{id}/documents` — 上传文档
- `POST /api/v1/datasets/{id}/chunks` — 触发解析
- `POST /api/v1/datasets/{id}/retrieval` — RAG 查询

完整 API 文档：https://ragflow.io/docs

## 示例

```javascript
// 编程式使用
const ragflow = require('{baseDir}/lib/api.js');

// 上传并解析
await ragflow.uploadDocument(datasetId, './article.md', { filename: 'article.md' });
await ragflow.triggerParsing(datasetId, [documentId]);

// 查询
const answer = await ragflow.chat(datasetId, '中风指南有哪些？');
```