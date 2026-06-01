---
name: media
description: "Use when the user wants to extract audio from video files, convert between audio formats, or process media files. Supports extraction of audio tracks from video in various formats (mp3, m4a, wav, flac, ogg). Also use when user provides any video file (.mp4/.webm/.mkv/.avi/.mov) and asks for the audio track."
version: 0.2.0
author: MediaStudio Team
metadata:
  source: plugin:media-studio
  clawdbot:
    emoji: "🎬"
    requires:
      bins: ["ffmpeg"]
---

> **Important:** All API calls go to `http://localhost:7899`. The media-studio plugin backend must be running.

# Media Skill — Audio Extraction

Extract audio from video files using ffmpeg.

## Prerequisites

- **ffmpeg**: `ffmpeg -version` to verify
- **Media Studio backend**: running on `http://localhost:7899`

## When to Use

**Activate this skill when:**
- User wants to "extract audio from video"
- User wants to "convert video to mp3/audio"
- User says "get the audio track from this video"
- User provides a video file (.mp4/.webm/.mkv/.avi/.mov) and asks for the audio track

**Don't use this skill for:**
- Transcription of audio (use `transcribe` skill)
- Text polishing (use `polish` skill)
- Video editing or cutting
- Downloading online media

## Workflow

```
User provides video file
  → POST /upload (upload video)
  → POST /media/to-audio (extract audio)
  → Return audio file to user
  → Optionally pass to transcribe skill
```

## API Usage

### 1. Upload video

```bash
curl -X POST http://localhost:7899/upload \
  -F "file=@/path/to/video.mp4"
```

Response:
```json
{ "file_id": "abc123", "file_type": "video", "original_name": "video.mp4" }
```

### 2. Extract audio

```bash
curl -X POST http://localhost:7899/media/to-audio \
  -H "Content-Type: application/json" \
  -d '{"file_id": "abc123", "format": "mp3", "quality": "high"}'
```

Response:
```json
{ "file_id": "audio456", "name": "video.mp3", "size_bytes": 1234567 }
```

### 3. Download audio

```bash
curl -o audio.mp3 http://localhost:7899/audio/audio456
```

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `format` | mp3, m4a, wav, flac, ogg | mp3 | Output audio format |
| `quality` | high, medium, low | high | Audio quality |
| `sample_rate` | 44100, 48000, 22050 | 44100 | Sample rate in Hz |

## Audio Format Comparison

| Format | Best For | Typical Size |
|--------|----------|-------------|
| MP3 | General purpose | Small |
| M4A | Good quality/size | Medium |
| WAV | Maximum quality | Large |
| FLAC | Lossless archive | Medium-Large |
| OGG | Open format | Small-Medium |

## Quality Levels

- `high`: ~192 kbps
- `medium`: ~128 kbps
- `low`: ~64 kbps
