import os
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

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

def chunk_file(filepath: str, content: str) -> List[Document]:
    """
    Chunk a file's content into smaller, code-aware chunks using Langchain.
    Returns a list of Document objects with metadata.
    """
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    
    # Check if the file type supports code-aware splitting
    if ext in EXTENSION_MAPPING:
        language = EXTENSION_MAPPING[ext]
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=language,
            chunk_size=1000,
            chunk_overlap=200
        )
    else:
        # Fallback for generic text splitting
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
    documents = splitter.create_documents(
        texts=[content],
        metadatas=[{"source": filepath}]
    )
    return documents