"""Verify converted knowledge markdown files and generate an index."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_ROOT = Path("knowledge") / "data"
INDEX_PATH = KNOWLEDGE_ROOT / "index.md"
REQUIRED_FIELDS = ("title", "category", "source", "date", "format_type")
KNOWN_CATEGORIES = ("policy", "procedure", "notice", "service")
SHORT_BODY_THRESHOLD = 50


@dataclass(frozen=True)
class DocumentRecord:
    """Structured information extracted from a markdown document."""

    path: Path
    metadata: dict[str, str]
    body_char_count: int
    missing_fields: list[str]


def read_text_with_fallback(path: Path) -> str:
    """Read text with common encoding fallbacks."""
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb2312"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别文件编码")


def parse_front_matter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML front matter from markdown content."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content

    end_line = -1
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_line = index
            break

    if end_line < 0:
        return {}, content

    metadata: dict[str, str] = {}
    for raw_line in lines[1:end_line]:
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
            value = value[1:-1]
        metadata[key] = value

    body = "\n".join(lines[end_line + 1 :])
    return metadata, body


def normalize_body_for_count(body: str) -> str:
    """Normalize markdown body and exclude title heading from count."""
    lines = body.splitlines()
    if lines and lines[0].lstrip().startswith("# "):
        lines = lines[1:]
    text = "\n".join(lines).strip()
    return re.sub(r"\s+", "", text)


def inspect_document(path: Path) -> DocumentRecord:
    """Inspect one markdown file and return extracted quality data."""
    content = read_text_with_fallback(path)
    metadata, body = parse_front_matter(content)
    missing_fields = [field for field in REQUIRED_FIELDS if not metadata.get(field, "").strip()]
    body_char_count = len(normalize_body_for_count(body))
    return DocumentRecord(
        path=path,
        metadata=metadata,
        body_char_count=body_char_count,
        missing_fields=missing_fields,
    )


def markdown_cell(text: str) -> str:
    """Escape table cell text for markdown table."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def build_index(records: list[DocumentRecord]) -> str:
    """Build index markdown content."""
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = [
        "# 知识库文档索引",
        "",
        f"生成时间：{generated_at}",
        f"文档总数：{len(records)}",
        "",
        "| 序号 | 文件名 | 类别 | 标题 | 来源 | 日期 | 字符数 |",
        "|------|--------|------|------|------|------|--------|",
    ]

    for index, record in enumerate(records, start=1):
        metadata = record.metadata
        row = [
            str(index),
            markdown_cell(record.path.name),
            markdown_cell(metadata.get("category", "")),
            markdown_cell(metadata.get("title", "")),
            markdown_cell(metadata.get("source", "")),
            markdown_cell(metadata.get("date", "")),
            str(record.body_char_count),
        ]
        lines.append(f"| {' | '.join(row)} |")

    lines.append("")
    return "\n".join(lines)


def print_report(
    records: list[DocumentRecord],
    category_counts: dict[str, int],
    missing_metadata_docs: list[DocumentRecord],
    short_body_docs: list[DocumentRecord],
) -> None:
    """Print verification report to console."""
    print("=== 知识库数据检查报告 ===")
    print(f"总文档数：{len(records)}")
    print("各类别文档数：")
    for category in KNOWN_CATEGORIES:
        print(f"  {category}: {category_counts.get(category, 0)}")

    print("缺失元数据字段的文档列表：")
    if not missing_metadata_docs:
        print("  无")
    else:
        for doc in missing_metadata_docs:
            print(f"  {doc.path.as_posix()} -> 缺失字段: {', '.join(doc.missing_fields)}")

    print(f"正文字符数过短（< {SHORT_BODY_THRESHOLD}）的文档列表：")
    if not short_body_docs:
        print("  无")
    else:
        for doc in short_body_docs:
            print(f"  {doc.path.as_posix()} -> 字符数: {doc.body_char_count}")


def main() -> int:
    """Program entry point."""
    if not KNOWLEDGE_ROOT.exists():
        print(f"目录不存在：{KNOWLEDGE_ROOT.as_posix()}")
        print("验证未通过")
        return 1

    md_files = sorted(
        path
        for path in KNOWLEDGE_ROOT.rglob("*.md")
        if path.is_file() and path != INDEX_PATH
    )

    records: list[DocumentRecord] = []
    inspection_errors: list[str] = []
    for path in md_files:
        try:
            records.append(inspect_document(path))
        except Exception as exc:
            inspection_errors.append(f"{path.as_posix()}: {exc}")

    records.sort(key=lambda record: (record.metadata.get("category", ""), record.path.name))

    category_counts = {category: 0 for category in KNOWN_CATEGORIES}
    for record in records:
        category = record.metadata.get("category", "").strip()
        if category in category_counts:
            category_counts[category] += 1

    missing_metadata_docs = [record for record in records if record.missing_fields]
    short_body_docs = [record for record in records if record.body_char_count < SHORT_BODY_THRESHOLD]

    print_report(records, category_counts, missing_metadata_docs, short_body_docs)

    index_markdown = build_index(records)
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(index_markdown, encoding="utf-8")
    print(f"索引已生成：{INDEX_PATH.as_posix()}")

    problems: list[str] = []
    if len(records) < 30:
        problems.append(f"文档总数不足 30（当前 {len(records)}）")
    if missing_metadata_docs:
        problems.append(f"存在 {len(missing_metadata_docs)} 篇文档元数据不完整")
    if inspection_errors:
        problems.append(f"存在 {len(inspection_errors)} 个文档解析异常")

    if not problems:
        print("知识库素材验证通过")
        return 0

    print("验证未通过")
    for problem in problems:
        print(f"- {problem}")
    if inspection_errors:
        print("解析异常列表：")
        for item in inspection_errors:
            print(f"  {item}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
