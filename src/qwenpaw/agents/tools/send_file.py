# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long,too-many-return-statements
import csv
import io
import os
import mimetypes
import unicodedata
from pathlib import Path
from urllib.parse import quote

from agentscope.tool import ToolResponse
from agentscope.message import (
    TextBlock,
    ImageBlock,
    AudioBlock,
    VideoBlock,
)

from ..schema import FileBlock
from .file_io import _resolve_file_path
from .utils import read_file_safe

# Maximum file size (bytes) to generate a text preview for.
_PREVIEW_MAX_BYTES = 100 * 1024  # 100 KB

# Maximum number of CSV data rows to include in the preview table.
_PREVIEW_CSV_MAX_ROWS = 50

# File extensions that support inline text preview.
_PREVIEWABLE_EXTENSIONS = frozenset({".md", ".txt", ".csv"})

# MIME types that support inline text preview.
_PREVIEWABLE_MIME_TYPES = frozenset(
    {"text/markdown", "text/plain", "text/csv"},
)


def _path_to_file_url(path: str) -> str:
    """Convert a local file path to a proper file:// URL (RFC 8089).

    On Windows, converts:
      C:\\path\\file.txt      →  file:///C:/path/file.txt
      \\\\server\\share\\f.txt  →  file://server/share/f.txt

    Non-ASCII characters and ``%`` are percent-encoded so the URL is
    always valid ASCII and round-trips correctly through url2pathname.
    """
    # Normalize to absolute path
    abs_path = os.path.abspath(path)

    # Convert backslashes to forward slashes (Windows)
    if os.name == "nt":
        abs_path = abs_path.replace("\\", "/")

    # Percent-encode non-ASCII and special characters.
    # ``%`` must NOT be in *safe* — otherwise a literal ``%25`` in a
    # filename would survive un-encoded and be mis-decoded later.
    encoded_path = quote(abs_path, safe="/:@")

    # RFC 8089: file:///  (authority is empty → three slashes)
    if os.name == "nt":
        # UNC path: //server/share/… → file://server/share/…
        if encoded_path.startswith("//"):
            return f"file:{encoded_path}"
        # Local drive: C:/… → file:///C:/…
        return f"file:///{encoded_path}"
    # POSIX: abs_path already starts with "/" → file:///…
    return f"file://{encoded_path}"


def _auto_as_type(mt: str) -> str:
    if mt.startswith("image/"):
        return "image"
    if mt.startswith("audio/"):
        return "audio"
    if mt.startswith("video/"):
        return "video"
    return "file"


def _is_text_previewable(file_path: str, mime_type: str) -> bool:
    """Check if a file should get an inline text preview."""
    ext = Path(file_path).suffix.lower()
    if ext in _PREVIEWABLE_EXTENSIONS:
        return True
    return mime_type in _PREVIEWABLE_MIME_TYPES


def _csv_to_markdown_table(content: str, max_rows: int = _PREVIEW_CSV_MAX_ROWS) -> str:
    """Convert CSV text to a markdown table, limited to *max_rows* data rows."""
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return ""

    header = rows[0]
    data_rows = rows[1 : max_rows + 1]
    truncated = len(rows) - 1 > max_rows

    # Column widths (account for header and all visible data rows)
    col_widths = [len(str(h)) for h in header]
    for row in data_rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    def _fmt_row(cells: list, widths: list) -> str:
        padded = [
            str(cells[i]).ljust(widths[i]) if i < len(cells) else "".ljust(widths[i] if i < len(widths) else 0)
            for i in range(len(widths))
        ]
        return "| " + " | ".join(padded) + " |"

    lines = [_fmt_row(header, col_widths)]
    lines.append("| " + " | ".join("-" * w for w in col_widths) + " |")
    for row in data_rows:
        lines.append(_fmt_row(row, col_widths))
    if truncated:
        lines.append(f"\n... ({len(rows) - 1 - max_rows} more rows)")

    return "\n".join(lines)


def _is_likely_binary(content: str) -> bool:
    """Heuristic: if >10% of first 8KB are control chars, treat as binary."""
    sample = content[:8192]
    if not sample:
        return False
    control_count = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\n\r\t")
    return control_count / len(sample) > 0.1


async def _format_preview_content(file_path: str, mime_type: str) -> str | None:
    """Read a text-previewable file and return formatted preview content.

    Returns ``None`` if preview should be skipped (too large, binary, read error).
    """
    try:
        if os.path.getsize(file_path) > _PREVIEW_MAX_BYTES:
            return None

        content = await read_file_safe(file_path, max_bytes=_PREVIEW_MAX_BYTES)
        if not content or _is_likely_binary(content):
            return None

        ext = Path(file_path).suffix.lower()

        if ext == ".csv" or mime_type == "text/csv":
            table = _csv_to_markdown_table(content)
            return table if table else None

        if ext == ".txt" or mime_type == "text/plain":
            return f"```\n{content}\n```"

        # .md / text/markdown — raw content, will render as markdown
        return content
    except Exception:  # noqa: BLE001
        return None


async def send_file_to_user(
    file_path: str,
) -> ToolResponse:
    """Send a file to the user.

    Args:
        file_path (`str`):
            Path to the file to send.

    Returns:
        `ToolResponse`:
            The tool response containing the file or an error message.
    """

    # Normalize the path: expand ~ and fix Unicode normalization differences
    # (e.g. macOS stores filenames as NFD but paths from the LLM arrive as NFC,
    # causing os.path.exists to return False for files that do exist).
    file_path = os.path.expanduser(unicodedata.normalize("NFC", file_path))

    # Resolve relative paths to absolute paths based on workspace directory
    file_path = _resolve_file_path(file_path)

    if not os.path.exists(file_path):
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: The file {file_path} does not exist.",
                ),
            ],
        )

    if not os.path.isfile(file_path):
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: The path {file_path} is not a file.",
                ),
            ],
        )

    # Detect MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        # Default to application/octet-stream for unknown types
        mime_type = "application/octet-stream"
    as_type = _auto_as_type(mime_type)

    try:
        # Use local file URL instead of base64
        file_url = _path_to_file_url(file_path)
        source = {"type": "url", "url": file_url}

        if as_type == "image":
            return ToolResponse(
                content=[
                    ImageBlock(type="image", source=source),
                    TextBlock(type="text", text="File sent successfully."),
                ],
            )
        if as_type == "audio":
            return ToolResponse(
                content=[
                    AudioBlock(type="audio", source=source),
                    TextBlock(type="text", text="File sent successfully."),
                ],
            )
        if as_type == "video":
            return ToolResponse(
                content=[
                    VideoBlock(type="video", source=source),
                    TextBlock(type="text", text="File sent successfully."),
                ],
            )

        # File type: include text preview when applicable
        content_blocks: list = []

        if _is_text_previewable(file_path, mime_type):
            preview = await _format_preview_content(file_path, mime_type)
            if preview:
                content_blocks.append(TextBlock(type="text", text=preview))

        content_blocks.append(
            FileBlock(
                type="file",
                source=source,
                filename=os.path.basename(file_path),
            ),
        )
        content_blocks.append(
            TextBlock(type="text", text="File sent successfully."),
        )

        return ToolResponse(content=content_blocks)

    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Send file failed due to \n{e}",
                ),
            ],
        )
