import os
import re

def edit_file_content(working_directory, file_path, search_pattern, replacement_text, mode="replace"):
    """
    Edit specific parts of a file instead of rewriting the entire file.
    
    Args:
        working_directory: The base directory
        file_path: Path to the file to edit
        search_pattern: Pattern to find (can be regex if mode='regex')
        replacement_text: Text to replace with
        mode: 'replace' (exact match), 'regex' (regex pattern), 'insert_after', 'insert_before'
    
    Returns:
        Success message or error
    """
    if not file_path:
        return "Error: file_path is required"
    
    if not search_pattern:
        return "Error: search_pattern is required"
    
    if replacement_text is None:
        replacement_text = ""
    
    # Resolve paths securely
    abs_working_dir = os.path.realpath(working_directory)
    abs_file_path = os.path.realpath(os.path.join(abs_working_dir, file_path))
    
    # Security check
    if not abs_file_path.startswith(abs_working_dir + os.sep):
        return f'Error: Cannot edit "{file_path}" as it is outside the permitted working directory'
    
    # Check if file exists
    if not os.path.isfile(abs_file_path):
        return f'Error: File "{file_path}" does not exist'
    
    try:
        # Read the file
        with open(abs_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply the edit based on mode
        if mode == "replace":
            if search_pattern not in content:
                return f'Error: Pattern "{search_pattern[:50]}..." not found in file'
            content = content.replace(search_pattern, replacement_text)
            
        elif mode == "regex":
            if not re.search(search_pattern, content):
                return f'Error: Regex pattern "{search_pattern}" not found in file'
            content = re.sub(search_pattern, replacement_text, content)
            
        elif mode == "insert_after":
            if search_pattern not in content:
                return f'Error: Pattern "{search_pattern[:50]}..." not found in file'
            content = content.replace(search_pattern, search_pattern + replacement_text)
            
        elif mode == "insert_before":
            if search_pattern not in content:
                return f'Error: Pattern "{search_pattern[:50]}..." not found in file'
            content = content.replace(search_pattern, replacement_text + search_pattern)
            
        else:
            return f'Error: Invalid mode "{mode}". Use: replace, regex, insert_after, insert_before'
        
        # Check if any changes were made
        if content == original_content:
            return f'Warning: No changes made to "{file_path}". Pattern may not have matched.'
        
        # Write the modified content back
        with open(abs_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Count changes
        lines_changed = len([line for line in content.split('\n') if line not in original_content.split('\n')])
        
        return f'Success: Edited "{file_path}" - {lines_changed} lines modified using {mode} mode'
        
    except UnicodeDecodeError:
        return f'Error: Cannot edit binary file "{file_path}"'
    except PermissionError:
        return f'Error: Permission denied writing to "{file_path}"'
    except Exception as e:
        return f'Error editing "{file_path}": {str(e)}'

# Schema for the function
from google.genai import types

schema_edit_file_content = types.FunctionDeclaration(
    name="edit_file_content",
    description="Edit specific parts of a file without rewriting the entire file. Use this instead of write_file_content for existing files to avoid truncation.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="The file path to edit, relative to the working directory.",
            ),
            "search_pattern": types.Schema(
                type=types.Type.STRING,
                description="The exact text pattern to find in the file (or regex if mode='regex').",
            ),
            "replacement_text": types.Schema(
                type=types.Type.STRING,
                description="The text to replace with, or text to insert (can be empty string to delete).",
            ),
            "mode": types.Schema(
                type=types.Type.STRING,
                description="Edit mode: 'replace' (exact match), 'regex' (regex pattern), 'insert_after', 'insert_before'. Default: 'replace'",
            ),
        },
        required=["file_path", "search_pattern", "replacement_text"],
    ),
)
