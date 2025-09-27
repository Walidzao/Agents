from functions.get_files_info import get_files_info
from functions.get_file_content import get_file_content
from functions.write_file_content import write_file_content
from functions.run_python_file import run_python_file
from functions.search_files import search_files, find_files
from functions.edit_file_section import edit_file_section, append_to_file
from functions.dev_tools import install_package, run_tests, check_syntax, get_project_info
from google.genai import types
from config import WORKING_DIRECTORY, LOCAL_MODE

from functions.get_files_info import schema_get_files_info
from functions.get_file_content import schema_get_file_content
from functions.write_file_content import schema_write_file_content
from functions.run_python_file import schema_run_python_file
from functions.search_files import schema_search_files, schema_find_files
from functions.edit_file_section import schema_edit_file_section, schema_append_to_file
from functions.dev_tools import schema_install_package, schema_run_tests, schema_check_syntax, schema_get_project_info

available_functions = types.Tool(
    function_declarations=[
    schema_get_files_info,
    schema_get_file_content,
    schema_write_file_content,
    schema_run_python_file,
    schema_search_files,
    schema_find_files,
    schema_edit_file_section,
    schema_append_to_file,
    schema_install_package,
    schema_run_tests,
    schema_check_syntax,
    schema_get_project_info,
    ]
)
def call_function(function_call_part, verbose=False,workspace_root="" ):
    
    if LOCAL_MODE:
        working_directory = WORKING_DIRECTORY
    else:
        if not workspace_root:
            return types.Content(
                role="tool",
                parts=[types.Part.from_function_response(
                    name=function_call_part.name,
                    response={"error": "workspace_root not set in server mode"}
                )],
            )
        working_directory = workspace_root
    function_name = function_call_part.name
    function_map = {
        "get_files_info": get_files_info,
        "get_file_content": get_file_content,
        "run_python_file": run_python_file,
        "write_file_content": write_file_content,
        "search_files": search_files,
        "find_files": find_files,
        "edit_file_section": edit_file_section,
        "append_to_file": append_to_file,
        "install_package": install_package,
        "run_tests": run_tests,
        "check_syntax": check_syntax,
        "get_project_info": get_project_info,
    }
    if function_name not in function_map:
        return types.Content(
            role="tool",
            parts=[
                types.Part.from_function_response(
                    name=function_name,
                    response={"error": f"Unknown function: {function_name}"},
                )
            ],
        )

    args = dict(function_call_part.args)
    args["working_directory"] = working_directory

    print(f"Calling funtion: {function_call_part.name}(args_dict:{args})")

    function_result = function_map[function_name](**args)

    return types.Content(
        role='tool',
        parts=[
            types.Part.from_function_response(
                name=function_name,

                response={"result": function_result},
            )
        ],
    )