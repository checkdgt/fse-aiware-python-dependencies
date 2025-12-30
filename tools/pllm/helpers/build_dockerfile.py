# Helper file to build a docker file based off of our model intuitions
import docker
from time import sleep
import os
import sys
# from docker import APIClient
from io import BytesIO

class DockerHelper():
    def __init__(self, logging=False, image_name="", dockerfile_name="", container_name = "") -> None:
        # Stores the dockerfile information for output
        self.dockerfile_out = ""
        # The name of the docker image- This is unique based on snippet name and python version
        self.image_name = image_name
        # Dockerfile name usually Dockerfile-llm-<python version>
        self.dockerfile_name = dockerfile_name
        self.container_name = container_name
        # Connection for docker client
        try:
            self.client = docker.from_env()
        except docker.errors.DockerException as e:
            if "Permission denied" in str(e):
                print("\n" + "="*80)
                print("ERROR: Cannot access Docker socket - Permission Denied")
                print("="*80)
                print("\nYou're running inside a dev container without proper Docker socket permissions.")
                print("\nTo fix this, you need to:")
                print("1. Exit and rebuild the container with Docker socket access")
                print("2. On your host, run:")
                print(f"   docker run -v /var/run/docker.sock:/var/run/docker.sock:rw \\")
                print(f"              --group-add $(stat -c '%g' /var/run/docker.sock) \\")
                print(f"              ... <rest of your docker run command>")
                print("\nOr add this to your docker-compose.yml:")
                print("   volumes:")
                print("     - /var/run/docker.sock:/var/run/docker.sock:rw")
                print("   group_add:")
                print("     - $(stat -c '%g' /var/run/docker.sock)")
                print("\nAlternatively, on the host, run:")
                print(f"   chmod 666 /var/run/docker.sock  # (not recommended for production)")
                print("="*80 + "\n")
                raise
            else:
                raise
        # Logging for output
        self.logging = logging
        # When an error occurs, we want to know what it was on a previous run
        self.previous_error = {"error_message": '', "module": ''}

    def query_docker(self):
        return self.client.api.images()

    # Breaks down the file path to get the folder and the file name
    # file: The path to the file
    def get_project_dir(self, file):
        split_path = file.split('/')
        file_path = '/'.join(split_path[:-1])
        file_name = split_path[-1]
        dir_name = split_path[-2]
        return file_path, dir_name, file_name
    
    # Creates the dockerfile based on the llm information
    # llm_out: contains the python version and modules
    # file: The provided file with path
    def create_dockerfile(self, llm_out, file):
        # Get the directory and file name
        project_dir, dir_name, project_file = self.get_project_dir(file)
        self.dockerfile_out = "" # RESET THE FILE!
        self.dockerfile_out += f"""# FROM is the found expected Python version\n"""
        self.dockerfile_out += f"""FROM python:{llm_out['python_version']}\n"""
        self.dockerfile_out += f"""# Set the working directory to /app\n"""
        self.dockerfile_out += f"""WORKDIR /app\n"""

        self.dockerfile_out += f"""# Add install commands for all of the python modules\n"""
        self.dockerfile_out += f"""RUN ["pip","install","--upgrade","pip"]\n"""
        # Loop through the modules and add these to the docker file as pip installs
        python_modules = llm_out['python_modules']
        if self.logging: print(python_modules)
        for module in python_modules:
            if type(module) == dict:
                name = module['module']
                version = module['version']
            else:
                name = module
                version = python_modules[module]

            # if self.logging: print(type(data))
            # if self.logging: print(data)
            if type(version) == str:
                self.dockerfile_out += f"""RUN ["pip","install","--trusted-host","pypi.python.org","--default-timeout=100","{name}=={version}"]\n"""
            else:
                self.dockerfile_out += f"""RUN ["pip","install","--trusted-host","pypi.python.org","--default-timeout=100","{name}=={version[0]}"]\n"""

        # Copys the snippet to the app dir for running
        self.dockerfile_out += f"""# Copy the specified directory to /app\n"""
        self.dockerfile_out += f"""COPY {project_file} /app\n"""
        self.dockerfile_out += f"""# Run the specified python file\n"""
        self.dockerfile_out += f"""CMD ["python", "/app/{project_file}"]"""

        # Create the image name based on the file name and the python version
        self.image_name = f"test/pllm:{dir_name}_{llm_out['python_version']}"
        self.container_name = f"{dir_name}_{llm_out['python_version']}"
        self.dockerfile_name = f"Dockerfile-llm-{llm_out['python_version']}"
        with open(f"{project_dir}/{self.dockerfile_name}", "w") as file:
            file.write(self.dockerfile_out)

    # Uses the docker api to build the created dockerfiles
    # Returns true if good and false with the error message if there was an issue
    def build_dockerfile(self, path, dockerfile=None):
        if not dockerfile: dockerfile = self.dockerfile_name
        error_lines = ""
        project_dir, dir_name, project_file = self.get_project_dir(path)
        for line in self.client.api.build(path=project_dir, dockerfile=dockerfile, forcerm=True, tag=self.image_name):
            decoded_line = line.decode('utf-8')
            if 'ERROR' in decoded_line or 'Could not fetch URL' in decoded_line or 'errorDetail' in decoded_line:
                error_lines += decoded_line
            if self.logging: print(decoded_line)
        
        if error_lines == "":
            return True, ""
        else:
            return False, error_lines

    def delete_container(self):
        try:
            self.client.containers.get(self.container_name).remove(v=True, force=True)
        except Exception as e:
            if self.logging: print(e)

    def delete_image(self):
        try:
            self.client.images.remove(image=self.image_name, force=True)
        except Exception as e:
            if self.logging: print(e)

    # Runs the container we built to see if the python snippet runs
    # Returns the logs for analysis
    def run_container_test(self):
        self.delete_container()
        logs = ''
        try:
            self.container = self.client.containers.create(self.image_name, name=self.container_name)
            self.container.start()
            sleep(10)
            while(self.container.status == 'running'):
                # container.logs()
                sleep(5)
            if self.logging: print(self.container.status)
            logs = self.container.logs()
            self.container.remove(v=True, force=True)
            self.container = None
        except docker.errors.ContainerError as e:
            if self.logging: print(e)
            if self.container:
                while(self.container.status == 'running'):
                    sleep(5)
                if self.logging: print(self.container.status)
                logs = self.container.logs()
                self.container.remove(v=True, force=True)
                self.container = None

        return logs.decode('utf-8')

def main():
    dh = DockerHelper(logging=True, image_name="woof:meow", dockerfile_name="", container_name="")
    dh.run_container_test()
    # print(dh.query_docker())

if __name__ == "__main__":
    main()

    print(f"Done")
