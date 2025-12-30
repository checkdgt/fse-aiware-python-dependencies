# # Get all the python files in a project
import os
import sys
import importlib.util
import sysconfig
import requests

class DepsScraper():

    def __init__(self, logging=False) -> None:
        self.logging = logging


    # Method to check if a module is part of the standard library
    # If it is, then it doesn't exist as a regular import
    # and shouldn't be included.
    # Takes module name as an import
    def is_module_in_standard_library(self, module_name):
        # spec = importlib.util.find_spec(module_name)
        # return spec is not None #and spec.origin == "built-in"
        
        # Check if the module is built-in
        if module_name in sys.builtin_module_names:
            return True
        elif module_name == 'io' or module_name == 'stringio' or module_name == 'os':
            return True
        
        # Check if the module is part of the standard library
        module_spec = importlib.util.find_spec(module_name)
        if module_spec is None or module_spec.origin is None:
            return False
        std_lib_path = sysconfig.get_paths()['stdlib']
        return module_spec.origin.startswith(std_lib_path)

        # # Try to find the module specification
        # module_spec = importlib.util.find_spec(module_name)
        # if module_spec is None or module_spec.origin is None:
        #     return False

        # # Get the standard library paths
        # std_lib_path = sysconfig.get_paths()['stdlib']
        # purelib_path = sysconfig.get_paths()['purelib']
        # platlib_path = sysconfig.get_paths()['platlib']

        # # Normalize paths for comparison
        # module_origin = os.path.normcase(module_spec.origin)
        # std_lib_path = os.path.normcase(std_lib_path)
        # purelib_path = os.path.normcase(purelib_path)
        # platlib_path = os.path.normcase(platlib_path)

        # # Check if the module's origin is within any of the standard library paths
        # return (module_origin.startswith(std_lib_path) or 
        #         module_origin.startswith(purelib_path) or 
        #         module_origin.startswith(platlib_path))

    # Check to see if a package is on pypi
    # If it is then it's something we can install
    def is_package_on_pypi(self, package_name):
        pypi_url = f"https://pypi.org/pypi/{package_name}/json"

        try:
            response = requests.get(pypi_url)
            response.raise_for_status()  # Raise an HTTPError for bad responses (e.g., 404 Not Found)
            # If the module is on pypi then we know we can import it
            # We then check if it's standard library
            if self.is_module_in_standard_library(package_name):
                return False
            else:
                return True
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return False  # Package not found on PyPI
            else:
                raise  # Re-raise other HTTP errors

    
    # Walk a given folder path
    # And return the python files in the folder
    def print_files_in_folder(self, folder_path):
        project_dirs = []
        python_files = []
        for root, dirs, files in os.walk(folder_path):
            for dir in dirs:
                print(dir)
                project_dirs.append(dir)
            for file_name in files:
                print(file_name)
                file_path = os.path.join(root, file_name)
                
                file = file_path.split('/')[-1:][0]
                if '.py' in file and not '.pyc' in file:
                    # print(file)
                    python_files.append(file_path)
        
        return python_files, project_dirs


    # Checks for dot notation in an import and cleans it up
    def dot_notation(self, word, folders):
        if '.' in word:
            for folder in folders:
                if folder in word:
                    print(f"folder '{folder}' is in import '{word}'")
                    return None
            module = word.strip().split('.')
            return module[0]
        else:
            return word


    # Appends a dependency to the list if it doesn't already exist there
    def append_to_list(self, list, dep):
        if not dep in list:
            list.append(dep)
        return list

    # Checks if a line is a blockquote and flips the flag
    def block_quote(self, block, line):
        if '"""' in line:
            block = not block
        return block

    """
        Cleans the dependency list. Removes dot notation and Uppercase modules
        dep_list: List of dependencies to clean
        return: returns the clean set of modules
    """
    def clean_deps(self, dep_list):
        imports = []
        for dep in dep_list:
            # import_name = self.dot_notation(dep, [])
            if dep:
                if dep.istitle():
                    pass
                elif dep[0].isdigit():
                    pass
                else:
                    if not self.is_module_in_standard_library(dep):
                        imports = self.append_to_list(imports, dep)
        return imports

    # Looks for specific words in an file
    # file_path: path to the file we're crawling
    # target_word: the word we're looking for in the file
    def find_word_in_file(self, file_path, target_word, folders):
        imports = []
        block_quote = False
        try:
            with open(file_path, 'r') as file:
                for line_number, line in enumerate(file, start=1):
                    block_quote = self.block_quote(block_quote, line)
                    if not block_quote:
                        if target_word in line:
                            if self.logging: print(f'Found "{target_word}" in {file_path} at line {line_number}:')
                            # if self.logging: print(line.strip())  # Print the entire line
                            if not '#' in line:
                                stripped = line.strip().split(' ')
                                for i in range(0, len(stripped)):
                                    if i == 0 and stripped[i] == 'import':
                                        # if self.logging: print(f"A: {stripped}")
                                        # # if stripped[i+1] == '': print(f"BAD_WORD: {file_path}")
                                        # import_name = self.dot_notation(stripped[i+1], folders)
                                        # if import_name:
                                        #     if 'models' in stripped:
                                        #         print(stripped)
                                        #         print('woof')
                                        imports = self.append_to_list(imports, stripped[i+1])
                                    elif i > 0 and stripped[i] == 'import':
                                        if self.logging: print(f"B: {stripped}")
                                        # if stripped[i-1] == '': print(f"BAD_WORD: {file_path}")
                                        # import_name = self.dot_notation(stripped[i-1], folders)
                                        # if import_name:
                                        #     if 'models' in stripped:
                                        #         print(stripped)
                                        #         print('meow')
                                        #     if import_name.istitle():
                                        #         pass
                                        #     else:
                                        imports = self.append_to_list(imports, stripped[i-1])

        except FileNotFoundError:
            print(f"File not found: {file_path}")
        except Exception as e:
            print(f"An error occurred: {e}")
        return imports
