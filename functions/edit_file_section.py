import os
from google.genai import types

def edit_file_section(working_directory, file_path, line_start, line_end, new_content):
    """Edit specific lines in a file, replacing content between line_start and line_end"""
    abs_working_dir = os.path.realpath(working_directory)
    abs_file_path = os.path.realpath(os.path.join(abs_working_dir, file_path))
    
    # Security check
    if not abs_file_path.startswith(abs_working_dir + os.sep):
        return f'Error: Cannot edit "{file_path}" as it is outside the permitted working directory'
    
    # Validate parameters
    if not isinstance(line_start, int) or not isinstance(line_end, int):
        return "Error: line_start and line_end must be integers"
    
    if line_start < 1:
        return "Error: line_start must be >= 1"
    
    if line_end < line_start:
        return "Error: line_end must be >= line_start"
    
    if new_content is None:
        new_content = ""
    
    # Check if file exists
    if not os.path.isfile(abs_file_path):
        return f'Error: File "{file_path}" not found'
    
    try:
        # Read the file
        with open(abs_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # Validate line numbers
        if line_start > total_lines + 1:
            return f"Error: line_start ({line_start}) is beyond file end (file has {total_lines} lines)"
        
        # Adjust line numbers to 0-based indexing
        start_idx = line_start - 1
        end_idx = min(line_end, total_lines)  # Don't go beyond file end
        
        # Prepare new content - ensure it ends with newline if replacing entire lines
        if new_content and not new_content.endswith('\n'):
            new_content += '\n'
        
        # Split new content into lines for proper handling
        new_lines = new_content.splitlines(keepends=True) if new_content else []
        
        # Perform the replacement
        lines[start_idx:end_idx] = new_lines
        
        # Write back to file
        with open(abs_file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        lines_replaced = end_idx - start_idx
        lines_added = len(new_lines)
        net_change = lines_added - lines_replaced
        
        return f'Successfully edited "{file_path}": replaced {lines_replaced} lines (lines {line_start}-{end_idx}) with {lines_added} lines. Net change: {net_change:+d} lines.'
        
    except Exception as e:
        return f'Error editing file "{file_path}": {e}'

def append_to_file(working_directory, file_path, content):
    """Append content to the end of an existing file"""
    abs_working_dir = os.path.realpath(working_directory)
    abs_file_path = os.path.realpath(os.path.join(abs_working_dir, file_path))
    
    # Security check
    if not abs_file_path.startswith(abs_working_dir + os.sep):
        return f'Error: Cannot append to "{file_path}" as it is outside the permitted working directory'
    
    if content is None:
        return "Error: content parameter is required"
    
    # Check if file exists
    if not os.path.isfile(abs_file_path):
        return f'Error: File "{file_path}" not found. Use write_file_content to create new files.'
    
    try:
        # Ensure content ends with newline for proper appending
        if content and not content.endswith('\n'):
            content += '\n'
        
        with open(abs_file_path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        lines_added = content.count('\n')
        return f'Successfully appended {len(content)} characters ({lines_added} lines) to "{file_path}"'
        
    except Exception as e:
        return f'Error appending to file "{file_path}": {e}'

# Schema definitions
schema_edit_file_section = types.FunctionDeclaration(
    name="edit_file_section",
    description="Edit specific lines in a file by replacing content between line_start and line_end (inclusive) with new content. Use this for precise modifications instead of rewriting entire files.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="The file path to edit, relative to the working directory.",
            ),
            "line_start": types.Schema(
                type=types.Type.INTEGER,
                description="The starting line number to replace (1-based indexing).",
            ),
            "line_end": types.Schema(
                type=types.Type.INTEGER,
                description="The ending line number to replace (1-based indexing, inclusive).",
            ),
            "new_content": types.Schema(
                type=types.Type.STRING,
                description="The new content to replace the specified lines. Can be empty string to delete lines.",
            ),
        },
        required=["file_path", "line_start", "line_end", "new_content"],
    ),
)

schema_append_to_file = types.FunctionDeclaration(
    name="append_to_file",
    description="Append content to the end of an existing file. Useful for adding new content without modifying existing content.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="The file path to append to, relative to the working directory.",
            ),
            "content": types.Schema(
                type=types.Type.STRING,
                description="The content to append to the file.",
            ),
        },
        required=["file_path", "content"],
    ),
)
