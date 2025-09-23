import os 
from google.genai import types

def get_files_info(working_directory, directory="."):
    # Construct the absolute working dir from the provided path
    abs_working_directory = os.path.realpath(working_directory)

    # This line normalizes the directory path to be a full path
    abs_directory = os.path.realpath(os.path.join(abs_working_directory, directory))
    if not abs_directory.startswith(abs_working_directory):
        return f'Error: Cannot list "{directory}" as it is outside the permitted working directory'

    if not os.path.isdir(abs_directory):
        return f'Error: "{directory}" is not a directory'
    
    final_response = ""
    #contents of the directory: 
    contents = os.listdir(abs_directory)
    for item in contents: 
        item_path = os.path.join(abs_directory, item)
        if os.path.isdir(item_path): 
            final_response += f'- {item}: file_size={os.path.getsize(item_path)} bytes, is_dir=True\n'
        else:
            final_response += f'- {item}: file_size={os.path.getsize(item_path)} bytes, is_dir=False\n'
    return final_response
    
schema_get_files_info = types.FunctionDeclaration(
    name="get_files_info",
    description="Lists files in the specified directory along with their sizes, constrained to the working directory.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "directory": types.Schema(
                type=types.Type.STRING,
                description="The directory to list files from, relative to the working directory. If not provided, lists files in the working directory itself.",
            ),
        },
    ),
)