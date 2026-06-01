---
name: transcribe
description: "Use when the user wants to transcribe audio or video files to text/markdown. Handles transcription via Whisper (local GPU/CPU), DashScope Paraformer/SenseVoice, or OpenAI Whisper API. Supports language specification. Also use when user provides audio files (.mp3/.wav/.m4a/.flac/.ogg/.aac) and asks for text transcription."
version: 0.2.0
author: MediaStudio Team
metadata:
  source: plugin:media-studio
  clawdbot:
    emoji: "📝"
env:
  DASHSCOPE_API_KEY:
    description: API key for DashScope ASR (Paraformer/SenseVoice)
    required: false
  OPENAI_API_KEY:
    description: API key for OpenAI Whisper API
    required: false
  MEDIA_STUDIO_TRANSCRIBE_DEFAULT_LANE:
    description: Default transcription lane (fast/slow/external)
    required: false
---

> **Important:** All API calls go to `http://localhost:7899`. The media-studio plugin backend must be running.

# Transcribe Skill — Audio/Video to Text

Transcribe audio or video files to text using Whisper (local), DashScope (cloud), or OpenAI ASR.

## Prerequisites

- **Media Studio backend**: running on port 7899
- **At least one backend configured**: local Whisper model, DashScope API key, or OpenAI API key

## When to Use

**Activate this skill when:**
- User provides audio (.mp3/.wav/.m4a/.flac/.ogg/.aac) and wants text
- User provides video and wants the spoken content as text
- User says "transcribe this file", "convert speech to text", "get the text from this audio"
- User wants to extract subtitles or captions from media
- User specifies a language for transcription

**Don't use this skill for:**
- Audio extraction from video (use `media` skill first)
- Text polishing (use `polish` skill)

## Transcription Lanes

| Lane | Backend | Hardware | Best For |
|------|---------|----------|----------|
| `fast` | Local Whisper | GPU (CUDA) | Speed, privacy |
| `slow` | Local Whisper | CPU | Fallback when no GPU |
| `external` | DashScope / OpenAI | Cloud | No local model needed |

The system auto-routes based on availability. Default lane is configurable.

## API Usage

### 1. Upload audio/video file

```bash
curl -X POST http://localhost:7899/upload \
  -F "file=@/path/to/audio.mp3"
```

Response:
```json
{ "file_id": "abc123", "file_type": "audio", "original_name": "audio.mp3" }
```

### 2. Transcribe directly

```bash
curl -X POST http://localhost:7899/transcribe/to-document \
  -H "Content-Type: application/json" \
  -d '{"file_id": "abc123", "language": "zh"}'
```

Response:
```json
{ "file_id": "doc456", "name": "audio.md", "text": "转录后的文本内容..." }
```

### 3. Read transcribed text

```bash
curl http://localhost:7899/document/doc456
```

## Parameters

| Parameter | Values | Description |
|-----------|--------|-------------|
| `language` | zh, en, ja, auto (default) | Audio language |
| `lane` | fast, slow, external | Which backend to use (optional, auto) |
| `output_format` | txt, md, srt, vtt | Output format (default: md) |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `DASHSCOPE_API_KEY` | Required for DashScope ASR backend |
| `OPENAI_API_KEY` | Required for OpenAI Whisper backend |
| `MEDIA_STUDIO_TRANSCRIBE_DEFAULT_LANE` | Default: `fast`, `slow`, or `external` |

## Example Pipeline (media → transcribe)

```bash
# 1. Upload video
UPLOAD=$(curl -s -X POST http://localhost:7899/upload -F "file=@video.mp4")
FILE_ID=$(echo "$UPLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin)['file_id'])")

# 2. Extract audio
AUDIO=$(curl -s -X POST http://localhost:7899/media/to-audio \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$FILE_ID\", \"format\": \"mp3\"}")
AUDIO_ID=$(echo "$AUDIO" | python3 -c "import sys,json; print(json.load(sys.stdin)['file_id'])")

# 3. Transcribe
curl -s -X POST http://localhost:7899/transcribe/to-document \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$AUDIO_ID\", \"language\": \"zh\"}"

# 4. Get text
curl -s http://localhost:7899/document/<doc_id>
```
