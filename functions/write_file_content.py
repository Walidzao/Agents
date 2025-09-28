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
    
    abs_working_dir = os.path.realpath(working_directory)
    abs_file_path = os.path.realpath(os.path.join(abs_working_dir, file_path))
    
    # Security check: ensure file is within workspace
    if not abs_file_path.startswith(abs_working_dir + os.sep):
        return f'Error: Cannot write to "{file_path}" as it is outside the permitted working directory'
    
    # Create parent directories if they don't exist
    try:
        os.makedirs(os.path.dirname(abs_file_path), exist_ok=True)
    except Exception as e:
        return f"Error: creating directory: {e}"
    
    # Check if target is a directory
    if os.path.exists(abs_file_path) and os.path.isdir(abs_file_path):
        return f'Error: "{file_path}" is a directory, not a file'
    
    # Write the file
    try:
        with open(abs_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f'Successfully wrote to "{file_path}" ({len(content)} characters written)'
    except Exception as e:
        return f"Error: writing to file: {e}"

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