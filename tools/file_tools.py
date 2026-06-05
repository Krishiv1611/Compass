import os
from langchain_core.tools import tool

@tool
def read_file(path:str, offset: int =1, limit: int | None = None)-> str:
    """Read file contents with line numbers. Binary files rejected.
    
    Args:
        path: Path to the file to read.
        offset: The line number to start reading from (1-indexed). Defaults to 1.
        limit: The maximum number of lines to read. Defaults to reading the whole file.
    """
    if not os.path.exists(path):
        return f"Error: File not found: {path}"
    if not os.path.isfile(path):
        return f"Error: Path is not a file: {path}"
    try:
        with open(path,'r',encoding='utf-8') as f:
            lines=f.readlines()
    except UnicodeDecodeError:
        return f"Error: Binary file or unknown encoding. Not reading: {path}"
    except Exception as e:
        return f"Error reading file: {e}"
    start_idx=max(0,offset-1)
    end_idx=len(lines) if limit is None else min(len(lines),start_idx + limit)
    if start_idx >= len(lines) and len(lines)>0:
        return f"Error: Offset {offset} is beyond file length {len(lines)}"
    result_lines=[f"Showing lines {start_idx+1} to {end_idx} of {len(lines)} in {path}:\n"]
    for i in range(start_idx, end_idx):
        line_num=i+1
        result_lines.append(f"{line_num:4d}| {lines[i].strip('\\n')}")
    return "\n".join(result_lines)
@tool
def write_to_file(path:str,content:str):
    """Write content to a file. Overwrite existing file
    Args:
        path: Path to the file to write to.
        content: The content to write to the file.
    """
    if not os.path.exists(path):
        return f"Error: File not found: {path}"
    if not os.path.isfile(path):
        return f"Error: Path is not a file: {path}"
    try:
        with open(path,'w',encoding="='utf-8") as f:
            f.write(content)
    except Exception as e:
        return f"Error writing to file: {e}"
    return f"Successfully wrote {len(content)} characters to {path}"

@tool
def edit_file(path: str, old_content: str, new_content: str) -> str:
    """Replace a specific block of text in a file.

    The old_content must appear EXACTLY once in the file (including whitespace
    and indentation). It will be replaced with new_content.

    To insert new lines, include surrounding context in old_content and add
    the new lines in new_content. To delete lines, set new_content to "".

    Args:
        path: Path to the file to edit.
        old_content: The exact existing text to find (must be unique in the file).
        new_content: The text to replace it with.
    """
    if not os.path.exists(path):
        return f"Error: File not found: {path}"
    if not os.path.isfile(path):
        return f"Error: Path is not a file: {path}"

    try:
        with open(path, 'r', encoding='utf-8') as f:
            file_content = f.read()
    except UnicodeDecodeError:
        return f"Error: Binary file or unknown encoding: {path}"
    except Exception as e:
        return f"Error reading file: {e}"
    count = file_content.count(old_content)
    if count == 0:
        return (
            f"Error: old_content not found in {path}. "
            "Make sure it matches the file exactly, including whitespace."
        )
    if count > 1:
        return (
            f"Error: old_content appears {count} times in {path}. "
            "Include more surrounding context to make it unique."
        )

    updated_content = file_content.replace(old_content, new_content, 1)

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
    except Exception as e:
        return f"Error writing file: {e}"
        
    old_lines = old_content.count('\n') + 1
    new_lines = new_content.count('\n') + 1
    return (
        f"Successfully edited {path}: "
        f"replaced {old_lines} lines with {new_lines} lines."
    )

    

    

