"""Batch-convert txt files in data/ to standardized markdown files."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

INPUT_DIR = Path("data")
OUTPUT_ROOT = Path("knowledge") / "data"
ERROR_LOG_PATH = Path("convert_errors.log")
CATEGORIES = ("policy", "procedure", "notice", "service")

PROCEDURE_KEYWORDS = ("办理流程", "受理条件", "办理时限", "窗口办理", "行政许可", "行政奖励")
POLICY_KEYWORDS = ("管理办法", "实施细则", "管理规定", "条例", "章程")
SERVICE_KEYWORDS = ("开放时间", "服务指南", "借阅", "校园卡", "宿舍", "食堂")

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "]",
    flags=re.UNICODE,
)
PUNCTUATION_PATTERN = re.compile(r"[，。！？；：、“”‘’,.!?;:()（）【】《》—-]")


@dataclass(frozen=True)
class ParsedDocument:
    """Structured document parsed from source txt content."""

    title: str
    date: str
    source: str
    source_url: str
    body: str
    format_type: Literal["A", "B"]


def read_text_with_fallback(path: Path) -> str:
    """Read file using UTF-8 first, then GBK/GB2312 fallback."""
    encodings = ("utf-8", "utf-8-sig", "gbk", "gb2312")
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError(f"文件编码无法识别: {last_error}")


def strip_emoji(text: str) -> str:
    """Remove emoji symbols from text."""
    cleaned = EMOJI_PATTERN.sub("", text)
    for marker in ("📄", "📅", "🔗", "📃"):
        cleaned = cleaned.replace(marker, "")
    return cleaned


def normalize_date(raw: str) -> str:
    """Normalize date text to YYYY-MM-DD."""
    text = strip_emoji(raw).strip()
    date_patterns = (
        re.compile(r"(\d{4})[年/\-.](\d{1,2})[月/\-.](\d{1,2})"),
        re.compile(r"(\d{4})(\d{2})(\d{2})"),
    )
    for pattern in date_patterns:
        match = pattern.search(text)
        if not match:
            continue
        year, month, day = (int(part) for part in match.groups())
        normalized = dt.date(year, month, day)
        return normalized.strftime("%Y-%m-%d")
    raise ValueError(f"无法解析日期: {raw}")


def is_trailing_caption_line(line: str) -> bool:
    """Check whether a line looks like an image caption at document tail."""
    stripped = line.strip()
    if not stripped:
        return False
    if len(stripped) >= 20:
        return False
    if PUNCTUATION_PATTERN.search(stripped):
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9]", stripped))


def remove_trailing_captions(text: str) -> str:
    """Remove consecutive short caption-like lines at the end of body."""
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and is_trailing_caption_line(lines[-1]):
        lines.pop()
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def clean_body(text: str) -> str:
    """Normalize body text while preserving paragraph structure."""
    normalized = strip_emoji(text).replace("\r\n", "\n").replace("\r", "\n")
    trimmed = remove_trailing_captions(normalized)
    return trimmed.strip()


def detect_format(raw_text: str) -> Literal["A", "B"]:
    """Detect input format type A or B based on required signatures."""
    if "📄 标题：" in raw_text or "📃 正文内容：" in raw_text:
        return "A"
    if "基本信息" in raw_text and "部门信息" in raw_text:
        return "B"
    raise ValueError("无法识别文件格式（既不是格式 A 也不是格式 B）")


def parse_format_a(raw_text: str) -> ParsedDocument:
    """Parse campus news/notice style format."""
    lines = raw_text.splitlines()
    title = ""
    raw_date = ""
    source_url = ""
    body = ""

    for index, line in enumerate(lines):
        normalized = strip_emoji(line).strip()
        title_match = re.match(r"^标题[:：]\s*(.+?)\s*$", normalized)
        if title_match:
            title = title_match.group(1).strip()
            continue

        date_match = re.match(r"^发布时间[:：]\s*(.+?)\s*$", normalized)
        if date_match:
            raw_date = date_match.group(1).strip()
            continue

        url_match = re.match(r"^链接[:：]\s*(.+?)\s*$", normalized)
        if url_match:
            source_url = url_match.group(1).strip()
            continue

        body_match = re.match(r"^正文内容[:：]\s*(.*)$", normalized)
        if body_match:
            first_line = body_match.group(1).strip()
            body_parts = [first_line] if first_line else []
            body_parts.extend(lines[index + 1 :])
            body = "\n".join(body_parts)
            break

    if not title:
        raise ValueError("格式 A 解析失败：缺少标题字段")
    if not raw_date:
        raise ValueError("格式 A 解析失败：缺少发布时间字段")
    if not body.strip():
        raise ValueError("格式 A 解析失败：缺少正文内容")

    return ParsedDocument(
        title=strip_emoji(title).strip(),
        date=normalize_date(raw_date),
        source="南京工业大学官网",
        source_url=strip_emoji(source_url).strip(),
        body=clean_body(body),
        format_type="A",
    )


def parse_format_b(raw_text: str) -> ParsedDocument:
    """Parse government-service style format."""
    lines = raw_text.splitlines()
    title = ""
    for line in lines:
        normalized = strip_emoji(line).strip()
        if normalized:
            title = normalized
            break

    if not title:
        raise ValueError("格式 B 解析失败：缺少标题")

    source = ""
    for line in lines:
        normalized = strip_emoji(line).strip()
        source_match = re.match(r"^实施主体[:：]\s*(.+?)\s*$", normalized)
        if source_match:
            source = source_match.group(1).strip()
            break

    if not source:
        raise ValueError("格式 B 解析失败：缺少实施主体字段")

    return ParsedDocument(
        title=title,
        date="未标注",
        source=source,
        source_url="",
        body=clean_body(raw_text),
        format_type="B",
    )


def classify_document(title: str, body: str) -> Literal["policy", "procedure", "notice", "service"]:
    """Classify document with keyword rules and fixed priority."""
    if any(keyword in body for keyword in PROCEDURE_KEYWORDS):
        return "procedure"
    if any(keyword in body for keyword in POLICY_KEYWORDS) or any(
        keyword in title for keyword in ("办法", "规定", "条例")
    ):
        return "policy"
    if any(keyword in body for keyword in SERVICE_KEYWORDS):
        return "service"
    return "notice"


def shorten_title_for_filename(title: str) -> str:
    """Create a safe short title token for output filename."""
    snippet = strip_emoji(title).strip()[:20]
    safe = re.sub(r"[^\w\u4e00-\u9fff]+", "_", snippet, flags=re.UNICODE)
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe or "untitled"


def yaml_escape(text: str) -> str:
    """Escape text for YAML double-quoted values."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def build_markdown(doc: ParsedDocument, category: str) -> str:
    """Build standardized markdown output."""
    return "\n".join(
        [
            "---",
            f'title: "{yaml_escape(doc.title)}"',
            f"category: {category}",
            f'source: "{yaml_escape(doc.source)}"',
            f'source_url: "{yaml_escape(doc.source_url)}"',
            f'date: "{yaml_escape(doc.date)}"',
            f"format_type: {doc.format_type}",
            "---",
            "",
            f"# {doc.title}",
            "",
            doc.body,
            "",
        ]
    )


def convert_one_file(
    file_path: Path,
    output_root: Path,
    sequence_map: dict[str, int],
) -> tuple[bool, str | None, str | None]:
    """Convert one txt file and return success status, category, error."""
    try:
        raw_text = read_text_with_fallback(file_path)
        format_type = detect_format(raw_text)
        document = parse_format_a(raw_text) if format_type == "A" else parse_format_b(raw_text)
        category = classify_document(document.title, document.body)
        sequence_map[category] += 1
        seq = sequence_map[category]
        short_title = shorten_title_for_filename(document.title)
        output_name = f"{category}_{seq:03d}_{short_title}.md"
        output_path = output_root / category / output_name
        markdown = build_markdown(document, category)
        output_path.write_text(markdown, encoding="utf-8")
        return True, category, None
    except Exception as exc:
        return False, None, f"{file_path.name}: {exc}"


def append_error_log(error_log_path: Path, message: str) -> None:
    """Append one conversion error line to log file."""
    with error_log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")


def ensure_output_dirs(output_root: Path) -> None:
    """Create required output category directories."""
    for category in CATEGORIES:
        (output_root / category).mkdir(parents=True, exist_ok=True)


def print_report(total: int, success: int, counts: dict[str, int]) -> None:
    """Print conversion summary report to console."""
    failed = total - success
    print("=== 批量转换报告 ===")
    print(f"总文件数：{total}")
    print(f"成功转换：{success}")
    print(f"转换失败：{failed}（详见 convert_errors.log）")
    print()
    print("各类别分布：")
    print(f"  policy:    {counts['policy']} 篇")
    print(f"  procedure: {counts['procedure']} 篇")
    print(f"  notice:    {counts['notice']} 篇")
    print(f"  service:   {counts['service']} 篇")
    print()
    print("转换完成。输出目录：knowledge/data/")


def main() -> int:
    """Program entry point."""
    ensure_output_dirs(OUTPUT_ROOT)
    ERROR_LOG_PATH.write_text("", encoding="utf-8")

    txt_files = sorted(path for path in INPUT_DIR.rglob("*.txt") if path.is_file())
    sequence_map = {category: 0 for category in CATEGORIES}
    success_count = 0

    for file_path in txt_files:
        ok, _, error_message = convert_one_file(file_path, OUTPUT_ROOT, sequence_map)
        if ok:
            success_count += 1
            continue
        if error_message:
            append_error_log(ERROR_LOG_PATH, error_message)

    print_report(len(txt_files), success_count, sequence_map)
    return 0 if success_count == len(txt_files) else 1


if __name__ == "__main__":
    raise SystemExit(main())
