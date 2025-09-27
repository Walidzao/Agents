import os
import subprocess
from google.genai import types

def run_python_file(working_directory, file_path, args=None):
    abs_working_dir = os.path.realpath(working_directory)
    abs_file_path = os.path.realpath(os.path.join(abs_working_dir, file_path))
    if not abs_file_path.startswith(abs_working_dir + os.sep):
        return f'Error: Cannot execute "{file_path}" as it is outside the permitted working directory'
    if not os.path.exists(abs_file_path):
        return f'Error: File "{file_path}" not found.'
    if not file_path.endswith(".py"):
        return f'Error: "{file_path}" is not a Python file.'
    try:
        commands = ["python", abs_file_path]
        if args:
            commands.extend(args)
        # Get timeout from config
        from config import FUNCTION_CONFIGS
        timeout = FUNCTION_CONFIGS.get("run_python_file", {}).get("timeout", 60)
        
        result = subprocess.run(
            commands,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=abs_working_dir,
        )
        output = []
        if result.stdout:
            output.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            output.append(f"STDERR:\n{result.stderr}")

        if result.returncode != 0:
            output.append(f"Process exited with code {result.returncode}")

        return "\n".join(output) if output else "No output produced."
    except subprocess.TimeoutExpired:
        return f"Error: Python file execution timed out after {timeout} seconds"
    except Exception as e:
        return f"Error: executing Python file: {e}"

schema_run_python_file = types.FunctionDeclaration(
    name="run_python_file",
    description="Runs a Python file in the specified directory with the python3 interpreter, Acceps aditional CLI Args as an array of strings.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="The file path to run, relative to the working directory.",
            ),
            "args": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(
                    type=types.Type.STRING,
                ),
                description="The arguments to pass to the Python file as an array of strings.",
            ),
        },
    ),
) 