import os
import re
import glob
from google.genai import types
from config import FUNCTION_CONFIGS

def search_files(working_directory, pattern, file_types=None, case_sensitive=False, max_results=None):
    """Search for text patterns across files in the working directory"""
    abs_working_dir = os.path.realpath(working_directory)
    
    if max_results is None:
        max_results = FUNCTION_CONFIGS.get("search_files", {}).get("max_results", 100)
    
    # Validate pattern
    try:
        regex_flags = 0 if case_sensitive else re.IGNORECASE
        compiled_pattern = re.compile(pattern, regex_flags)
    except re.error as e:
        return f"Error: Invalid regex pattern '{pattern}': {e}"
    
    results = []
    files_searched = 0
    
    # Determine file extensions to search
    if file_types:
        if isinstance(file_types, str):
            file_types = [file_types]
        extensions = [f"*.{ext.lstrip('.')}" for ext in file_types]
    else:
        # Default to common text file types
        extensions = ["*.py", "*.txt", "*.md", "*.json", "*.yaml", "*.yml", "*.cfg", "*.ini", "*.log"]
    
    try:
        for extension in extensions:
            pattern_path = os.path.join(abs_working_dir, "**", extension)
            for file_path in glob.glob(pattern_path, recursive=True):
                abs_file_path = os.path.realpath(file_path)
                
                # Security check
                if not abs_file_path.startswith(abs_working_dir + os.sep):
                    continue
                
                # Skip if file is too large
                try:
                    file_size = os.path.getsize(abs_file_path)
                    max_size = FUNCTION_CONFIGS.get("search_files", {}).get("max_file_size", "10MB")
                    max_bytes = int(max_size.replace("MB", "")) * 1024 * 1024
                    if file_size > max_bytes:
                        continue
                except OSError:
                    continue
                
                files_searched += 1
                rel_path = os.path.relpath(abs_file_path, abs_working_dir)
                
                try:
                    with open(abs_file_path, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            matches = compiled_pattern.finditer(line)
                            for match in matches:
                                results.append({
                                    "file": rel_path,
                                    "line": line_num,
                                    "content": line.strip(),
                                    "match": match.group(),
                                    "start": match.start(),
                                    "end": match.end()
                                })
                                
                                if len(results) >= max_results:
                                    break
                            if len(results) >= max_results:
                                break
                except (UnicodeDecodeError, OSError):
                    # Skip binary or unreadable files
                    continue
                
                if len(results) >= max_results:
                    break
            
            if len(results) >= max_results:
                break
    
    except Exception as e:
        return f"Error during search: {e}"
    
    if not results:
        return f"No matches found for pattern '{pattern}' in {files_searched} files searched"
    
    # Format results
    output = [f"Found {len(results)} matches for pattern '{pattern}' (searched {files_searched} files):"]
    output.append("")
    
    current_file = None
    for result in results:
        if result["file"] != current_file:
            current_file = result["file"]
            output.append(f"=== {current_file} ===")
        
        output.append(f"Line {result['line']}: {result['content']}")
        if len(results) > 20:  # Truncate very long results
            output.append(f"... and {len(results) - 20} more matches")
            break
    
    return "\n".join(output)

def find_files(working_directory, name_pattern):
    """Find files by name pattern using glob syntax"""
    abs_working_dir = os.path.realpath(working_directory)
    
    try:
        # Handle both simple patterns and glob patterns
        if not any(char in name_pattern for char in ['*', '?', '[', ']']):
            # Simple name - add wildcards
            search_pattern = f"**/*{name_pattern}*"
        else:
            search_pattern = f"**/{name_pattern}"
        
        pattern_path = os.path.join(abs_working_dir, search_pattern)
        matches = []
        
        for file_path in glob.glob(pattern_path, recursive=True):
            abs_file_path = os.path.realpath(file_path)
            
            # Security check
            if not abs_file_path.startswith(abs_working_dir + os.sep):
                continue
            
            rel_path = os.path.relpath(abs_file_path, abs_working_dir)
            is_dir = os.path.isdir(abs_file_path)
            
            try:
                size = os.path.getsize(abs_file_path) if not is_dir else 0
                matches.append({
                    "path": rel_path,
                    "is_directory": is_dir,
                    "size": size
                })
            except OSError:
                continue
        
        if not matches:
            return f"No files found matching pattern '{name_pattern}'"
        
        # Sort by type (directories first) then by name
        matches.sort(key=lambda x: (not x["is_directory"], x["path"]))
        
        output = [f"Found {len(matches)} files/directories matching '{name_pattern}':"]
        output.append("")
        
        for match in matches:
            type_indicator = "[DIR]" if match["is_directory"] else "[FILE]"
            size_info = "" if match["is_directory"] else f" ({match['size']} bytes)"
            output.append(f"{type_indicator} {match['path']}{size_info}")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error searching for files: {e}"

# Schema definitions
schema_search_files = types.FunctionDeclaration(
    name="search_files",
    description="Search for text patterns across files in the working directory using regex. Useful for finding specific code, functions, or text content.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "pattern": types.Schema(
                type=types.Type.STRING,
                description="The regex pattern to search for (e.g., 'def calculate', 'import.*numpy', 'TODO.*bug')",
            ),
            "file_types": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(type=types.Type.STRING),
                description="Optional list of file extensions to search (e.g., ['py', 'txt']). If not provided, searches common text files.",
            ),
            "case_sensitive": types.Schema(
                type=types.Type.BOOLEAN,
                description="Whether the search should be case sensitive. Defaults to false.",
            ),
            "max_results": types.Schema(
                type=types.Type.INTEGER,
                description="Maximum number of matches to return. Defaults to 100.",
            ),
        },
        required=["pattern"],
    ),
)

schema_find_files = types.FunctionDeclaration(
    name="find_files",
    description="Find files and directories by name pattern using glob syntax. Useful for locating specific files or file types.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "name_pattern": types.Schema(
                type=types.Type.STRING,
                description="The name pattern to search for. Can use glob syntax like '*.py', 'test_*', or simple names like 'config'",
            ),
        },
        required=["name_pattern"],
    ),
)
