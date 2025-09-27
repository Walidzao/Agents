import os
import subprocess
import ast
import glob
from google.genai import types
from config import FUNCTION_CONFIGS

def install_package(working_directory, package_name, version=None):
    """Install a Python package using pip"""
    abs_working_dir = os.path.realpath(working_directory)
    
    # Validate package name (basic validation)
    if not package_name or not package_name.replace('-', '').replace('_', '').replace('.', '').isalnum():
        return f"Error: Invalid package name '{package_name}'"
    
    try:
        # Build pip command
        cmd = ["python", "-m", "pip", "install"]
        
        if version:
            package_spec = f"{package_name}=={version}"
        else:
            package_spec = package_name
        
        cmd.append(package_spec)
        
        # Get timeout from config
        timeout = FUNCTION_CONFIGS.get("install_package", {}).get("timeout", 120)
        
        result = subprocess.run(
            cmd,
            cwd=abs_working_dir,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = []
        if result.stdout:
            output.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            output.append(f"STDERR:\n{result.stderr}")
        
        if result.returncode == 0:
            output.append(f"Successfully installed {package_spec}")
        else:
            output.append(f"Installation failed with exit code {result.returncode}")
        
        return "\n".join(output) if output else f"Package {package_spec} installation completed"
        
    except subprocess.TimeoutExpired:
        return f"Error: Package installation timed out after {timeout} seconds"
    except Exception as e:
        return f"Error installing package '{package_name}': {e}"

def run_tests(working_directory, test_pattern="test_*.py", framework="auto"):
    """Run test files matching the specified pattern"""
    abs_working_dir = os.path.realpath(working_directory)
    
    try:
        # Find test files
        pattern_path = os.path.join(abs_working_dir, "**", test_pattern)
        test_files = glob.glob(pattern_path, recursive=True)
        
        # Filter to only include files within working directory
        valid_test_files = []
        for test_file in test_files:
            abs_test_file = os.path.realpath(test_file)
            if abs_test_file.startswith(abs_working_dir + os.sep):
                rel_path = os.path.relpath(abs_test_file, abs_working_dir)
                valid_test_files.append(rel_path)
        
        if not valid_test_files:
            return f"No test files found matching pattern '{test_pattern}'"
        
        # Determine test framework
        if framework == "auto":
            # Check for pytest first, then unittest
            try:
                subprocess.run(["python", "-m", "pytest", "--version"], 
                             capture_output=True, check=True, cwd=abs_working_dir)
                framework = "pytest"
            except (subprocess.CalledProcessError, FileNotFoundError):
                framework = "unittest"
        
        # Run tests based on framework
        if framework == "pytest":
            cmd = ["python", "-m", "pytest", "-v"] + valid_test_files
        else:  # unittest
            cmd = ["python", "-m", "unittest", "-v"] + [
                f.replace('.py', '').replace('/', '.').replace('\\', '.') 
                for f in valid_test_files
            ]
        
        result = subprocess.run(
            cmd,
            cwd=abs_working_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for tests
        )
        
        output = [f"Running tests with {framework}:"]
        output.append(f"Test files: {', '.join(valid_test_files)}")
        output.append("")
        
        if result.stdout:
            output.append("STDOUT:")
            output.append(result.stdout)
        
        if result.stderr:
            output.append("STDERR:")
            output.append(result.stderr)
        
        if result.returncode == 0:
            output.append("✓ All tests passed!")
        else:
            output.append(f"✗ Tests failed with exit code {result.returncode}")
        
        return "\n".join(output)
        
    except subprocess.TimeoutExpired:
        return "Error: Test execution timed out after 5 minutes"
    except Exception as e:
        return f"Error running tests: {e}"

def check_syntax(working_directory, file_path):
    """Check Python file syntax using AST parsing"""
    abs_working_dir = os.path.realpath(working_directory)
    abs_file_path = os.path.realpath(os.path.join(abs_working_dir, file_path))
    
    # Security check
    if not abs_file_path.startswith(abs_working_dir + os.sep):
        return f'Error: Cannot check "{file_path}" as it is outside the permitted working directory'
    
    # Validate file
    if not os.path.isfile(abs_file_path):
        return f'Error: File "{file_path}" not found'
    
    if not file_path.endswith('.py'):
        return f'Error: "{file_path}" is not a Python file'
    
    try:
        with open(abs_file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # Parse the AST
        try:
            ast.parse(source_code, filename=file_path)
            return f'✓ Syntax check passed for "{file_path}" - no syntax errors found'
        except SyntaxError as e:
            return f'✗ Syntax error in "{file_path}":\nLine {e.lineno}: {e.msg}\n{e.text.strip() if e.text else ""}'
        except Exception as e:
            return f'✗ Error parsing "{file_path}": {e}'
    
    except Exception as e:
        return f'Error reading file "{file_path}": {e}'

def get_project_info(working_directory):
    """Get information about the project structure and dependencies"""
    abs_working_dir = os.path.realpath(working_directory)
    
    try:
        info = {
            "project_type": "unknown",
            "dependencies": [],
            "test_files": [],
            "python_files": [],
            "config_files": []
        }
        
        # Check for common project files
        project_indicators = {
            "requirements.txt": "pip",
            "pyproject.toml": "poetry/modern",
            "setup.py": "setuptools",
            "Pipfile": "pipenv",
            "environment.yml": "conda",
            "package.json": "node.js"
        }
        
        for file_name, project_type in project_indicators.items():
            if os.path.isfile(os.path.join(abs_working_dir, file_name)):
                info["project_type"] = project_type
                break
        
        # Find Python files
        for py_file in glob.glob(os.path.join(abs_working_dir, "**", "*.py"), recursive=True):
            rel_path = os.path.relpath(py_file, abs_working_dir)
            info["python_files"].append(rel_path)
            
            # Check if it's a test file
            if "test" in rel_path.lower() or rel_path.startswith("test_"):
                info["test_files"].append(rel_path)
        
        # Find config files
        config_patterns = ["*.ini", "*.cfg", "*.yaml", "*.yml", "*.json", "*.toml"]
        for pattern in config_patterns:
            for config_file in glob.glob(os.path.join(abs_working_dir, pattern)):
                rel_path = os.path.relpath(config_file, abs_working_dir)
                info["config_files"].append(rel_path)
        
        # Try to read dependencies
        req_file = os.path.join(abs_working_dir, "requirements.txt")
        if os.path.isfile(req_file):
            try:
                with open(req_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            info["dependencies"].append(line)
            except Exception:
                pass
        
        # Format output
        output = [f"Project Analysis for {os.path.basename(abs_working_dir)}:"]
        output.append(f"Type: {info['project_type']}")
        output.append(f"Python files: {len(info['python_files'])}")
        output.append(f"Test files: {len(info['test_files'])}")
        output.append(f"Config files: {len(info['config_files'])}")
        
        if info["dependencies"]:
            output.append(f"Dependencies ({len(info['dependencies'])}):")
            for dep in info["dependencies"][:10]:  # Show first 10
                output.append(f"  - {dep}")
            if len(info["dependencies"]) > 10:
                output.append(f"  ... and {len(info['dependencies']) - 10} more")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error analyzing project: {e}"

# Schema definitions
schema_install_package = types.FunctionDeclaration(
    name="install_package",
    description="Install a Python package using pip. Useful for adding dependencies to the project.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "package_name": types.Schema(
                type=types.Type.STRING,
                description="The name of the package to install (e.g., 'numpy', 'requests')",
            ),
            "version": types.Schema(
                type=types.Type.STRING,
                description="Optional specific version to install (e.g., '1.21.0')",
            ),
        },
        required=["package_name"],
    ),
)

schema_run_tests = types.FunctionDeclaration(
    name="run_tests",
    description="Run test files matching a pattern. Automatically detects pytest or unittest framework.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "test_pattern": types.Schema(
                type=types.Type.STRING,
                description="Glob pattern to match test files (default: 'test_*.py')",
            ),
            "framework": types.Schema(
                type=types.Type.STRING,
                description="Test framework to use: 'auto', 'pytest', or 'unittest' (default: 'auto')",
            ),
        },
    ),
)

schema_check_syntax = types.FunctionDeclaration(
    name="check_syntax",
    description="Check Python file syntax using AST parsing. Use this before running code to catch syntax errors.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="The Python file path to check, relative to the working directory.",
            ),
        },
        required=["file_path"],
    ),
)

schema_get_project_info = types.FunctionDeclaration(
    name="get_project_info",
    description="Get information about the project structure, type, dependencies, and files. Useful for understanding a new codebase.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={},
    ),
)
