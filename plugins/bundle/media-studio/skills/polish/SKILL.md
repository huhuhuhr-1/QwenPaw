---
name: polish
description: "Use when the user wants to polish, refine, or improve written text. Applies MiniMax text polishing to markdown or plain text documents for better clarity, coherence, and professionalism. Also use when user says 'make this better', 'rewrite this', 'improve this text', or 'polish this document'."
version: 0.2.0
author: MediaStudio Team
metadata:
  source: plugin:media-studio
  clawdbot:
    emoji: "✨"
env:
  MINIMAX_API_KEY:
    description: MiniMax API key for text polishing service
    required: true
---

> **Important:** All API calls go to `http://localhost:7899`. This skill requires a valid `MINIMAX_API_KEY`.

# Polish Skill — Text Refinement

Polish and refine text documents using MiniMax LLM for improved clarity, coherence, and professionalism.

## Prerequisites

- **MiniMax API key**: configured in the Media Studio settings page
- **Media Studio backend**: running on port 7899

## When to Use

**Activate this skill when:**
- User asks to "polish", "refine", "improve", "rewrite", or "enhance" a text
- User wants to make writing more professional or clear
- User provides a markdown or text file and asks for improvement
- User says "make this sound better" or "fix the writing"

**Don't use this skill for:**
- Pure transcription tasks (use `transcribe` skill)
- Media conversion tasks (use `media` skill)
- Translation (the LLM handles this natively)

## Capabilities

- Markdown-aware polishing (preserves headers, lists, code blocks)
- Custom prompt override for specific polish styles
- Bilingual support (Chinese/English)
- Produces clean, well-formatted output

## API Usage

### 1. Upload text file

```bash
curl -X POST http://localhost:7899/upload \
  -F "file=@/path/to/document.md"
```

Response:
```json
{ "file_id": "abc123", "file_type": "document", "original_name": "document.md" }
```

### 2. Polish

```bash
curl -X POST http://localhost:7899/polish \
  -H "Content-Type: application/json" \
  -d '{"file_id": "abc123", "prompt": "Make this more professional and concise"}'
```

Response:
```json
{ "file_id": "pol456", "name": "document.polished.md" }
```

### 3. Read result

```bash
curl http://localhost:7899/polished/pol456
```

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `file_id` | Yes | — | File ID of the document to polish |
| `prompt` | No | — | Custom polish instructions (e.g., "academic style", "simplify for beginners") |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `MINIMAX_API_KEY` | Required. MiniMax API key for text polishing. |

## Notes

- The polish step preserves markdown structure (headings, lists, code blocks, tables)
- Without a custom `prompt`, the default style is general improvement for clarity and professionalism
- Polished output is a new file; original is unchanged
