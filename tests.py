from functions.get_files_info import *
from functions.get_file_content import *
from functions.run_python_file import *
def main(): 
    working_dir = "calculator"
    result = run_python_file(working_dir, "main.py", "3 * 5")
    print(result)
if __name__ == "__main__":
    main()

  
