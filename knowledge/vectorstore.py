"""Vector store utilities for RAG document indexing and retrieval."""

from __future__ import annotations

import logging
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

import frontmatter
from langchain_chroma import Chroma
from langchain_core.documents import Document

from config.settings import get_embedding

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

KNOWLEDGE_DATA_DIR = "knowledge/data"
CHROMA_PERSIST_DIR = "knowledge/chroma_db"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
SEARCH_TOP_K = 5

_BATCH_SIZE = 100
_EMBEDDING_REQUEST_BATCH_SIZE = 10
_SEPARATORS = ["\n\n", "\n", "。", "；", "，", " ", ""]


def _as_text(value: object) -> str:
    """Convert metadata values to plain strings accepted by vector stores."""
    if value is None:
        return ""
    return str(value)


def _infer_category(file_path: Path, data_root: Path) -> str:
    """Infer category from folder name when front matter category is missing."""
    try:
        return file_path.parent.relative_to(data_root).parts[0]
    except Exception:
        return file_path.parent.name


def _get_embedding_client():
    """Return embedding client configured for DashScope-compatible input format."""
    embedding = get_embedding()

    # DashScope-compatible embeddings endpoint expects text input instead of token ids.
    # Disable langchain-openai's length-safe token batching path that sends token arrays.
    if hasattr(embedding, "check_embedding_ctx_length"):
        embedding.check_embedding_ctx_length = False

    # DashScope embedding API enforces max 10 inputs per request.
    if hasattr(embedding, "chunk_size"):
        embedding.chunk_size = _EMBEDDING_REQUEST_BATCH_SIZE
    return embedding


def load_documents() -> list[Document]:
    """Load markdown documents with YAML front matter metadata."""
    data_root = Path(KNOWLEDGE_DATA_DIR)
    if not data_root.exists():
        logger.warning("Knowledge data directory does not exist: %s", data_root)
        return []

    documents: list[Document] = []
    category_counter: Counter[str] = Counter()

    for md_file in sorted(data_root.rglob("*.md")):
        try:
            post = frontmatter.load(md_file)
        except Exception as exc:
            logger.warning("Skip parse-failed file: %s (%s)", md_file, exc)
            continue

        content = (post.content or "").strip()
        if not content:
            logger.warning("Skip empty document: %s", md_file)
            continue

        metadata = post.metadata if isinstance(post.metadata, dict) else {}
        category = _as_text(metadata.get("category")) or _infer_category(md_file, data_root)

        doc_metadata = {
            "title": _as_text(metadata.get("title")) or md_file.stem,
            "category": category,
            "source": _as_text(metadata.get("source")) or md_file.name,
            "source_url": _as_text(metadata.get("source_url")),
            "date": _as_text(metadata.get("date")),
            "format_type": _as_text(metadata.get("format_type")),
        }
        documents.append(Document(page_content=content, metadata=doc_metadata))
        category_counter[category] += 1

    logger.info("Loaded documents: total=%d", len(documents))
    for category, count in sorted(category_counter.items()):
        logger.info("Category count: %s=%d", category, count)
    return documents


def split_documents(docs: list[Document]) -> list[Document]:
    """Split documents into retrieval chunks with inherited metadata."""
    if not docs:
        logger.info("Split skipped: no documents.")
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=_SEPARATORS,
    )
    chunks = splitter.split_documents(docs)
    logger.info("Split documents: %d -> %d chunks", len(docs), len(chunks))
    return chunks


def build_vectorstore(force_rebuild: bool = False) -> Chroma:
    """Build and persist Chroma vector store from markdown knowledge base."""
    persist_dir = Path(CHROMA_PERSIST_DIR)
    if persist_dir.exists() and not force_rebuild:
        logger.info("Using existing vector store at %s", persist_dir)
        return load_vectorstore()

    if force_rebuild and persist_dir.exists():
        shutil.rmtree(persist_dir)
        logger.info("Removed existing vector store at %s", persist_dir)

    docs = load_documents()
    chunks = split_documents(docs)
    if not chunks:
        raise ValueError("No chunks generated. Check knowledge markdown files.")

    embedding = _get_embedding_client()
    persist_dir.mkdir(parents=True, exist_ok=True)

    if len(chunks) <= _BATCH_SIZE:
        vectorstore = Chroma.from_documents(
            chunks,
            embedding=embedding,
            persist_directory=CHROMA_PERSIST_DIR,
        )
    else:
        logger.info(
            "Building vector store in batches: total_chunks=%d, batch_size=%d",
            len(chunks),
            _BATCH_SIZE,
        )
        first_batch = chunks[:_BATCH_SIZE]
        vectorstore = Chroma.from_documents(
            first_batch,
            embedding=embedding,
            persist_directory=CHROMA_PERSIST_DIR,
        )
        logger.info("Indexed batch: %d/%d", len(first_batch), len(chunks))

        for start in range(_BATCH_SIZE, len(chunks), _BATCH_SIZE):
            end = min(start + _BATCH_SIZE, len(chunks))
            vectorstore.add_documents(chunks[start:end])
            logger.info("Indexed batch: %d/%d", end, len(chunks))
            time.sleep(1)

    if hasattr(vectorstore, "persist"):
        vectorstore.persist()

    logger.info(
        "Vector store build complete: chunks=%d, persist_dir=%s",
        len(chunks),
        CHROMA_PERSIST_DIR,
    )
    return vectorstore


def load_vectorstore() -> Chroma:
    """Load persisted Chroma vector store."""
    persist_dir = Path(CHROMA_PERSIST_DIR)
    if not persist_dir.exists():
        raise FileNotFoundError(
            f"Vector store not found at '{CHROMA_PERSIST_DIR}'. "
            "Please run build_vectorstore() first."
        )
    embedding = _get_embedding_client()
    return Chroma(
        persist_directory=CHROMA_PERSIST_DIR,
        embedding_function=embedding,
    )


def search(
    query: str,
    k: int = SEARCH_TOP_K,
    category_filter: str | None = None,
) -> list[Document]:
    """Run similarity search with optional category filter."""
    if not query.strip():
        logger.warning("Empty query provided to search().")
        return []

    vectorstore = load_vectorstore()
    if category_filter is not None:
        return vectorstore.similarity_search(
            query,
            k=k,
            filter={"category": category_filter},
        )
    return vectorstore.similarity_search(query, k=k)


def format_search_results(docs: list[Document]) -> str:
    """Format retrieved documents as prompt-ready text blocks."""
    if not docs:
        return ""

    blocks: list[str] = []
    for doc in docs:
        title = _as_text(doc.metadata.get("title")) or "Untitled"
        category = _as_text(doc.metadata.get("category")) or "unknown"
        content = doc.page_content.strip()
        blocks.append(f"---\n[来源] {title}（{category}）\n{content}\n---")
    return "\n".join(blocks)


def _print_usage() -> None:
    print("Usage:")
    print("  python -m knowledge.vectorstore build")
    print('  python -m knowledge.vectorstore search "查询内容"')


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    if len(sys.argv) < 2:
        _print_usage()
        raise SystemExit(1)

    command = sys.argv[1].lower()
    if command == "build":
        build_vectorstore(force_rebuild=True)
    elif command == "search":
        if len(sys.argv) < 3:
            _print_usage()
            raise SystemExit(1)
        query_text = " ".join(sys.argv[2:])
        results = search(query_text)
        print(format_search_results(results))
    else:
        _print_usage()
        raise SystemExit(1)
