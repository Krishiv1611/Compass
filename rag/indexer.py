import json
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from rag.chunker import chunk_file

load_dotenv()

# Embedding configuration mirroring memory_tool
_embeddings = OpenAIEmbeddings(
    model="nvidia/llama-nemotron-embed-vl-1b-v2:free",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
    check_embedding_ctx_length=False,
    chunk_size=16
)

# Configuration
WORKSPACE_DIR = os.getcwd() # Default to cwd
CHROMA_PERSIST_DIR = os.path.join(WORKSPACE_DIR, ".compass", "chroma")
INDEX_STATE_FILE = os.path.join(WORKSPACE_DIR, ".compass", "index_state.json")

# Directories to ignore during traversal
IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", ".compass", "node_modules"}

def load_index_state() -> dict:
    """Load the index state holding file modification timestamps."""
    if os.path.exists(INDEX_STATE_FILE):
        try:
            with open(INDEX_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading index state: {e}")
            return {}
    return {}

def save_index_state(state: dict):
    """Save the index state."""
    os.makedirs(os.path.dirname(INDEX_STATE_FILE), exist_ok=True)
    with open(INDEX_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)

def is_text_file(filepath: str) -> bool:
    """Basic check if a file is likely to be text-based."""
    # List of valid text extensions to index
    valid_extensions = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".md", ".txt", ".html", ".css", 
        ".json", ".yml", ".yaml", ".toml", ".ini", ".c", ".cpp", ".h", ".hpp", 
        ".java", ".go", ".rs", ".rb", ".php", ".sh", ".bash", ".zsh"
    }
    _, ext = os.path.splitext(filepath)
    return ext.lower() in valid_extensions

def index_workspace(workspace_path: str = WORKSPACE_DIR):
    """
    Traverse the workspace, chunk modified files, and index them into ChromaDB.
    """
    print(f"Indexing workspace: {workspace_path}...")
    
    state = load_index_state()
    new_state = {}
    
    documents_to_index: List[Document] = []
    
    # Traverse directory
    for root, dirs, files in os.walk(workspace_path):
        # Modify dirs in-place to ignore specified directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            filepath = os.path.join(root, file)
            
            if not is_text_file(filepath):
                continue
                
            try:
                mtime = os.path.getmtime(filepath)
                # Check for incremental updates
                if filepath in state and state[filepath] == mtime:
                    # File hasn't changed
                    new_state[filepath] = mtime
                    continue
                    
                # Read and chunk the file
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                chunks = chunk_file(filepath, content)
                # Filter out empty chunks to prevent OpenRouter API errors
                chunks = [c for c in chunks if c.page_content.strip()]
                documents_to_index.extend(chunks)
                
                # Update the new state
                new_state[filepath] = mtime
                print(f"Prepared {len(chunks)} chunks for: {os.path.relpath(filepath, workspace_path)}")
                
            except Exception as e:
                print(f"Skipping {filepath} due to error: {e}")

    if documents_to_index:
        print(f"Adding {len(documents_to_index)} new/updated document chunks to ChromaDB...")
        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        vector_store = Chroma(
            collection_name="compass_workspace",
            embedding_function=_embeddings,
            persist_directory=CHROMA_PERSIST_DIR
        )
        vector_store.add_documents(documents=documents_to_index)
        print("Indexing complete.")
    else:
        print("No new or modified files found. Index is up to date.")
        
    save_index_state(new_state)

if __name__ == "__main__":
    index_workspace("d:\\projects\\compass")
