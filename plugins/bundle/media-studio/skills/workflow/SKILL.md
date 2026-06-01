---
name: workflow
description: "Use when the user wants to run multi-step data processing pipelines. Orchestrates sequences like video → audio extraction → transcription → text polishing as a single coordinated workflow with progress tracking and error handling. Also use when user says 'process this file', 'run the pipeline', 'transcribe and polish', or 'extract audio then transcribe'."
version: 0.2.0
author: MediaStudio Team
metadata:
  source: plugin:media-studio
  clawdbot:
    emoji: "⚙️"
---

> **Important:** All API calls go to `http://localhost:7899`. The media-studio plugin backend must be running.

# Workflow Skill — Multi-Step Pipeline

Orchestrate multi-step data processing pipelines with progress tracking and error handling.

## Prerequisites

- **Media Studio backend**: running on port 7899
- **Required backends**: appropriate backends for each step (ffmpeg for extract_audio, Whisper/API for transcribe, MiniMax for polish)

## When to Use

**Activate this skill when:**
- User wants to process a file through multiple steps
- User says "transcribe and polish", "extract audio then transcribe"
- User wants to run a batch of files through a pipeline
- User says "process this video all the way to polished text"
- User wants to see progress of running tasks

**Don't use this skill for:**
- Single-step operations (use specific skills instead: media, transcribe, polish)
- Real-time streaming processing

## Pipeline Flow

```
Upload file
  → Create workflow (auto-detects steps based on file type)
    → [video]  extract_audio → transcribe → [optional] polish
    → [audio]                → transcribe → [optional] polish
    → [text]                             → [optional] polish
```

## API Usage

### 1. Upload a file

```bash
curl -X POST http://localhost:7899/upload \
  -F "file=@/path/to/video.mp4"
```

### 2. Create a workflow

```bash
curl -X POST http://localhost:7899/workflows \
  -H "Content-Type: application/json" \
  -d '{"file_id": "abc123"}'
```

Response:
```json
{
  "workflow_id": "wf456",
  "status": "pending",
  "steps": [
    { "step_type": "extract_audio", "status": "pending" },
    { "step_type": "transcribe", "status": "pending" },
    { "step_type": "polish", "status": "pending" }
  ]
}
```

### 3. Check progress

```bash
curl http://localhost:7899/workflows/wf456
```

Response:
```json
{
  "workflow_id": "wf456",
  "status": "processing",
  "completed_count": 1,
  "step_count": 3,
  "steps": [
    { "step_type": "extract_audio", "status": "completed" },
    { "step_type": "transcribe", "status": "running" },
    { "step_type": "polish", "status": "pending" }
  ]
}
```

### 4. List all workflows

```bash
curl "http://localhost:7899/workflows?page=1&page_size=20"
```

Response:
```json
{
  "items": [{ "workflow_id": "wf456", "status": "completed", ... }],
  "total": 1
}
```

## Step Types

| Step Type | Input | Output | Backend Required |
|-----------|-------|--------|-----------------|
| `extract_audio` | Video file | Audio file | ffmpeg |
| `transcribe` | Audio/video | Markdown text | Whisper / DashScope / OpenAI |
| `polish` | Markdown text | Polished text | MiniMax |

## Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Waiting to start |
| `processing` | Currently executing |
| `completed` | Finished successfully |
| `failed` | Error occurred |
| `paused` | Suspended by user |

## Error Recovery

If a workflow step fails:
1. Check the error message in the step details
2. Fix the underlying issue (e.g., configure API key)
3. Retry: `POST /workflows/{id}/steps/{step_id}/retry`
4. Or delete and recreate: `DELETE /workflows/{id}`

## Batch Operations

- **Batch delete**: `POST /workflows/batch-delete` with `{ "workflow_ids": [...] }`
- **Batch export**: `POST /workflows/batch-export` with `{ "workflow_ids": [...] }`
