import subprocess
import json
import requests
import time

class GithubCruiserCore:
    
    def __init__(self, logging=False) -> None:
        self.logging = logging
    
    # Calls the subprocess command to run a specific command line tool
    # Returns both the standard message as well as error messages
    # These are separate for validation
    def call_subprocess(self, cmd=""):
        try:
            if self.logging: print(f"calling process: {cmd}")
            limit_reached = True
            process = None
            while limit_reached:
                process = subprocess.run(
                    cmd,
                    shell=True,
                    stdout = subprocess.PIPE,
                    stderr = subprocess.PIPE,
                    universal_newlines = True
                )
                if self.logging: print(process.stdout)
                
                # Check to see if we've reached our API limit and sleep for 5 minutes if we have
                if 'API rate limit exceeded' in process.stdout:
                    time.sleep(300)
                else:
                    # Set limit reached to False as we're good to progress still
                    limit_reached = False
            # Return the process details
            return process
        except Exception as e:
            print(e)

    def file_exists(self, file_name):
        files_to_look_for = [
            'requirements.txt',
            'Requirements.txt',
            'REQUIREMENTS.txt',
            'Pipfile',
            'setup.py',
            'Setup.py',
            'SETUP.py',
        ]
        found = False
        if file_name in files_to_look_for:
            found = True
        return found, file_name

    # Find files- Given a list of files from parsed json
    # Loop through to see if the file we're looking for exists
    # If it's a directory, store the name for further checks
    # Return if we found a file and the directories
    def find_files(self, list_of_files):
        directory = []
        found = False
        file_name = ''
        for file in list_of_files:
            if self.logging: print(f"file: {file['name']}")
            if 'dir' in file['type']:
                directory.append(file['name'])
            else:
                found, file_name = self.file_exists(file['name'])
            if found: break
        return found, directory, file_name

    # Call the given subprocess and load it as JSON
    # Return the converted JSON output to a usable dict
    def call_process_convert_json(self, file_name, process):
        try:
            # print("calling process")
            contents = self.call_subprocess(process)
        except Exception as e:
            print(contents.stderr)
            print(e)
        
        return json.loads(contents.stdout)
    
    def load_json_from_file(self, file):
        open_file = open(file)
        return json.load(open_file)
    
    def get_repo_api_data(self, repo):
        # Make a GET request to the GitHub API
        repo_url = f"https://api.github.com/repos/{repo}"
        
        response = requests.get(repo_url)

        repo_data = None
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the JSON response
            repo_data = response.json()
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
        
        return repo_data
