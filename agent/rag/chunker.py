import os
from typing import Any, List

from langchain_core.documents import Document
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter
from agent.config import settings

# Map file extensions to LangChain Language enums
EXTENSION_MAPPING = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".ts": Language.TS,
    ".md": Language.MARKDOWN,
    ".html": Language.HTML,
    ".java": Language.JAVA,
    ".go": Language.GO,
    ".cpp": Language.CPP,
    ".c": Language.C,
    ".cs": Language.CSHARP,
    ".rb": Language.RUBY,
    ".rs": Language.RUST,
}


def chunk_file(
    filepath: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    chunk_size: int | None = None,
) -> List[Document]:
    """
    Chunk a file's content into smaller, code-aware chunks using Langchain.
    Returns a list of Document objects with metadata.
    """
    chunk_size = chunk_size or int(settings.get("rag.chunk_size", 1000))
    chunk_overlap = min(200, max(0, chunk_size // 5))
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    # Check if the file type supports code-aware splitting
    if ext in EXTENSION_MAPPING:
        language = EXTENSION_MAPPING[ext]
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=language,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    else:
        # Fallback for generic text splitting
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    doc_metadata = {"source": filepath}
    if metadata:
        doc_metadata.update(metadata)

    documents = splitter.create_documents(
        texts=[content],
        metadatas=[doc_metadata],
    )
    return documents
