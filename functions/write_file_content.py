import os
from google.genai import types


def write_file_content(working_directory, file_path, content):
    # Validate required parameters
    if not file_path:
        return "Error: file_path is required"
    if content is None:
        return "Error: content is required"
    
    # Check file size limits to prevent truncation issues
    if len(content) > 50000:  # 50KB limit
        return f'Error: Content too large ({len(content)} chars). Use edit_file_content for large files or break into smaller parts.'
    
    try:
        abs_working_dir = os.path.realpath(working_directory)
        abs_file_path = os.path.realpath(os.path.join(abs_working_dir, file_path))
        
        # Debug logging
        print(f"DEBUG: working_directory={working_directory}")
        print(f"DEBUG: abs_working_dir={abs_working_dir}")
        print(f"DEBUG: file_path={file_path}")
        print(f"DEBUG: abs_file_path={abs_file_path}")
        
        # Security check: ensure file is within workspace
        if not abs_file_path.startswith(abs_working_dir + os.sep) and abs_file_path != abs_working_dir:
            return f'Error: Cannot write to "{file_path}" as it is outside the permitted working directory. abs_file_path={abs_file_path}, abs_working_dir={abs_working_dir}'
        
        # Check if working directory exists
        if not os.path.exists(abs_working_dir):
            return f'Error: Working directory does not exist: {abs_working_dir}'
        
        # Create parent directories if they don't exist
        parent_dir = os.path.dirname(abs_file_path)
        if parent_dir and parent_dir != abs_working_dir:
            print(f"DEBUG: Creating parent directory: {parent_dir}")
            os.makedirs(parent_dir, exist_ok=True)
        
        # Check if target is a directory
        if os.path.exists(abs_file_path) and os.path.isdir(abs_file_path):
            return f'Error: "{file_path}" is a directory, not a file'
        
        # Write the file
        print(f"DEBUG: Writing to file: {abs_file_path}")
        with open(abs_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f'Successfully wrote to "{file_path}" ({len(content)} characters written)'
        
    except PermissionError as e:
        return f"Error: Permission denied writing to file: {e}. Check container permissions for {abs_file_path}"
    except OSError as e:
        return f"Error: OS error writing to file: {e}. Path: {abs_file_path}"
    except Exception as e:
        return f"Error: Unexpected error writing to file: {e}. Type: {type(e).__name__}"

schema_write_file_content = types.FunctionDeclaration(
    name="write_file_content",
    description="Writes to a file in the speci fied directory,and create the file and its parent directories if they don't exist, constrained to the working directory. Accepts a string of content to write to the file.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="The file path to write to, relative to the working directory.",
            ),
            "content": types.Schema(
                type=types.Type.STRING,
                description="The content to write to the file.",    
            ),
        },
    ),
)