"""Unit tests for ui utility functions."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from docx import Document

from ui import extract_file_text, invoke_with_timeout


def create_minimal_pdf(path: Path, text: str) -> None:
    """Create a minimal valid PDF that contains one ASCII text line."""
    if not text.isascii():
        raise ValueError("create_minimal_pdf only supports ASCII text.")

    stream = f"BT /F1 12 Tf 100 700 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n"
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\n"
            b"endobj\n"
        ),
        (
            b"4 0 obj\n"
            + f"<< /Length {len(stream)} >>\n".encode("ascii")
            + b"stream\n"
            + stream
            + b"\nendstream\nendobj\n"
        ),
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    header = b"%PDF-1.4\n"
    pdf_data = bytearray(header)
    offsets = [0]

    for obj in objects:
        offsets.append(len(pdf_data))
        pdf_data.extend(obj)

    xref_offset = len(pdf_data)
    pdf_data.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf_data.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf_data.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf_data.extend(b"trailer\n")
    pdf_data.extend(f"<< /Size {len(offsets)} /Root 1 0 R >>\n".encode("ascii"))
    pdf_data.extend(b"startxref\n")
    pdf_data.extend(f"{xref_offset}\n".encode("ascii"))
    pdf_data.extend(b"%%EOF\n")

    path.write_bytes(pdf_data)


def create_test_docx(path: Path, text: str) -> None:
    """Create a DOCX file containing one paragraph."""
    document = Document()
    document.add_paragraph(text)
    document.save(path)


class MockGraph:
    """Simple graph mock for invoke_with_timeout tests."""

    def __init__(self, delay: float = 0, result: dict[str, Any] | None = None) -> None:
        self.delay = delay
        self.result = result or {}

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        if self.delay > 0:
            time.sleep(self.delay)
        return self.result if self.result else state


def test_extract_file_text_from_txt(tmp_path: Path) -> None:
    """A1: Extract text from a txt file."""
    file_path = tmp_path / "sample.txt"
    content = "这是一个 txt 测试。"
    file_path.write_text(content, encoding="utf-8")

    result = extract_file_text(str(file_path))

    assert content in result


def test_extract_file_text_from_md(tmp_path: Path) -> None:
    """A2: Extract text from a markdown file."""
    file_path = tmp_path / "sample.md"
    content = "# 标题\n\n这是 markdown 测试内容。"
    file_path.write_text(content, encoding="utf-8")

    result = extract_file_text(str(file_path))

    assert "这是 markdown 测试内容。" in result


def test_extract_file_text_from_pdf(tmp_path: Path) -> None:
    """A3: Extract text from a minimal ASCII PDF."""
    file_path = tmp_path / "sample.pdf"
    content = "Hello PDF Test"
    create_minimal_pdf(file_path, content)

    result = extract_file_text(str(file_path))

    assert content in result


def test_extract_file_text_from_docx(tmp_path: Path) -> None:
    """A4: Extract text from a docx file."""
    file_path = tmp_path / "sample.docx"
    content = "This is a DOCX test paragraph."
    create_test_docx(file_path, content)

    result = extract_file_text(str(file_path))

    assert content in result


def test_extract_file_text_unsupported_extension(tmp_path: Path) -> None:
    """B1: Return unsupported-format tip for unknown extension."""
    file_path = tmp_path / "sample.csv"
    file_path.write_text("a,b,c\n1,2,3\n", encoding="utf-8")

    result = extract_file_text(str(file_path))

    assert "不支持的文件格式" in result


def test_extract_file_text_empty_txt(tmp_path: Path) -> None:
    """B2: Return empty string for an empty txt file."""
    file_path = tmp_path / "empty.txt"
    file_path.write_text("", encoding="utf-8")

    result = extract_file_text(str(file_path))

    assert result == ""


def test_extract_file_text_truncates_long_content(tmp_path: Path) -> None:
    """B3: Truncate content longer than 50000 characters."""
    file_path = tmp_path / "long.txt"
    content = "a" * 60000
    file_path.write_text(content, encoding="utf-8")

    result = extract_file_text(str(file_path))

    assert result.startswith("a" * 100)
    assert "已截取前 50000 字符" in result
    assert 50000 < len(result) < 50200


def test_extract_file_text_missing_file() -> None:
    """B4: Return readable error text for missing file path."""
    result = extract_file_text("this_file_should_not_exist_123456.txt")

    assert any(keyword in result for keyword in ("失败", "错误", "读取"))


def test_invoke_with_timeout_returns_state() -> None:
    """C1: Return state normally when invoke finishes before timeout."""
    graph = MockGraph()
    state = {"user_input": "hello", "messages": []}

    result = invoke_with_timeout(graph, state, timeout=1)

    assert result == state


def test_invoke_with_timeout_raises_timeout_error() -> None:
    """C2: Raise TimeoutError when invoke execution exceeds timeout."""
    graph = MockGraph(delay=1.2)
    state = {"user_input": "timeout-test"}

    with pytest.raises(TimeoutError):
        invoke_with_timeout(graph, state, timeout=1)
