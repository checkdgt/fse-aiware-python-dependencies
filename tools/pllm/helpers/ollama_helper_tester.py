# Ollama helper, handles requests.
# TESTER FILE FOR PLAYING WITH NEW IDEAS
import argparse
import re

from helpers.ollama_helper_base import OllamaHelperBase
from helpers.py_pi_query import PyPIQuery

from langchain_core.messages import SystemMessage, HumanMessage

from langchain_core.pydantic_v1 import BaseModel, Field
from typing import Dict, List
from langchain_core.output_parsers import JsonOutputParser

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import PromptTemplate

# PYDANTIC classes for JSON output
class Module(BaseModel):
    module: str = Field(description="Name of the module")

class ModuleVersion(BaseModel):
    module: str = Field(description="Name of the module")
    version: str = Field(description="The version of the module to use")

class PythonModules(BaseModel):
    python_modules: Dict[str, ModuleVersion]

class PythonFile(BaseModel):
    python_version: str = Field(description="Name of the Python version required for this file")
    python_modules: List[str]

class ModuleVersions(BaseModel):
    module_versions: List[str] = Field(description="List of Module versions")

# Main Ollama helper class
class OllamaHelper(OllamaHelperBase):
    # Init defines the url to the Ollama API, the model, temp, logging and where the module information is stored
    def __init__(self, base_url="http://localhost:11434", model='llama3', temp=1.0, logging=False, base_modules='./modules', rag=True) -> None:
        super().__init__(base_url, model, temp, logging)
        self.base_modules = base_modules
        self.rag = rag
        self.pypi = PyPIQuery(logging=logging, base_modules=base_modules)

    """_summary_
    Validates the json from the model using pydantic to parse it
    This validates against the same schema used when calling the model
    """
    def pydantic_validate(self, model, json):
        try:
            model.parse_obj(json)
            return True
        except Exception as e:
            return False


    # Initial Python file handler, gets first set of modules and Python version
    def evaluate_file(self, python_file):
        raw_file = self.read_python_file(python_file)
        
        parser = JsonOutputParser(pydantic_object=PythonFile)

        prompt = PromptTemplate(
            template="Given a python file:{raw_file}\nReturn just a list of Python modules and python version required to run. Output JSON based on the schema {format_instructions}",
            input_variables=[],
            partial_variables={"raw_file": raw_file, "format_instructions": parser.get_format_instructions()}
        )
        
        chain = prompt | self.model | parser

        out = chain.invoke({})
        
        print(out)
        return out


    # Gets the details for the modules
    def get_module_specifics(self, llm_eval):
        # Uses the modules from the LLM output to get a specific set of versions for the inferred Python version
        # Also returns an updated python version, based on what the model had provided
        llm_eval['python_modules'], llm_eval['python_version'] = self.pypi.get_module_specifics(llm_eval)
        
        module_versions = self.get_module_versions(llm_eval)
        llm_eval['python_modules'] = module_versions

        return llm_eval

    # Loops through the modules and request a version for each
    def get_module_versions(self, details):
        modules = details['python_modules']

        if len(modules) <= 0:
            return {}
        
        # Define the parser
        parser = JsonOutputParser(pydantic_object=ModuleVersion)

        updated_modules = {}

        attempts = 5
        completed = False
        # Loop to ensure we get a version.
        # If the LLM returns a bad version or bad information then we need to loop and try again
        while not completed:
            try:
                for idx, module in enumerate(modules):
                    versions = self.read_python_file(f"{self.base_modules}/{module}_{details['python_version']}.txt")

                    tp = "Infer a possible working version of the '{module}' module for Python {python_version}.\nReturn the information with the format {format_instructions}"
                    pv = {"version_details": versions, "module": module, "python_version": details['python_version'], "format_instructions": parser.get_format_instructions()}
                    if self.rag:
                        tp = "Given a comma separated list of '{version_details}', for the '{module}' module, from oldest to newest.\nSelect a recent version for us to use that isn't previously used: 'Previously used: {previous}, and return the information with the format {format_instructions}"
                        pv = {"version_details": versions, "module": module, "previous": [], "format_instructions": parser.get_format_instructions()}

                    prompt = PromptTemplate(
                        template=tp,
                        input_variables=[],
                        partial_variables=pv
                    )

                    chain = prompt | self.model | parser

                    out = chain.invoke({})

                    updated_modules[out['module']] = out['version'].split(' ')[0]
                completed = True
            except Exception as e:
                completed = False
                attempts -= 1
            
            if attempts <= 0:
                print("Failed to find versions")
                exit(0)

        print(updated_modules)

        return updated_modules


    # NOTE: Deprecated, update instances that use this!
    def execute_chain(self, chain, pydantic_model):
        loop = 5
        passed = False
        
        while not passed or loop > 0:
            out = chain.invoke({})
            if self.logging: print(out)
            passed = self.pydantic_validate(pydantic_model, out)
            if passed: return passed, out
            loop -= 1
        
        return passed, None
        
    # Ensures the version details are correct
    def is_valid_version(self, version):
        # Regular expression pattern to match versions like 1.0, 1.0.0, 1.0.0rc1, etc.
        pattern = r"^\d+(\.\d+){1,2}([a-zA-Z0-9]+)?$"
        
        # Check if the version matches the pattern
        return bool(re.match(pattern, version))

    # Generic method to get the details from the error
    # Takes the prompt from the the error handler and the parser to ensure the information is returned correctly
    def generic_get_module_from_error(self, prompt, parser):

        bad_module = None

        # Loop to ensure the model returns a decent response from the error message
        # We want it to extract a module name which we can work with later
        for loop in range(0, 5):
            try:
                chain = prompt | self.model | parser

                out = chain.invoke({})
                # Get the name of the offending module from the error message        
                bad_module = self.pypi.check_module_name(out['module'])[0]

                if bad_module: break
            except Exception as e:
                print(f'could not find version: Error getting module name from error: {e}')

        return bad_module

    # Generic method to prompt for a version
    # Uses the targeted prompt and parser plus the previous failing versions
    def generic_get_version_with_bad_modules(self, prompt, parser, previous_versions):
        out = None

        for loop in range(0, 5):
            try:
                chain = prompt | self.model | parser

                out = chain.invoke({})

                print(out)

                # If the same version is chosen by the model then there's a chance the module is exhausted
                # We should remove and only re-add if requested during build.
                for version in previous_versions.split(', '):
                    if version == out['version']:
                        out = None
                            
                if out['version'] == None or self.is_valid_version(out['version']): return out
                # return out
            except Exception as e:
                print(f'could not find version: Error getting versions from error message: {e}')
        
        for version in previous_versions.split(', '):
            if version == out['version']:
                out['version'] = None

        return out


    # Generic method for multiple occasions
    # Gets the module versions from file as well as the error_modules.
    def get_versions_previous_versions(self, bad_module, previous_versions, details):
        versions = self.pypi.read_module_file(bad_module, details['python_version'])

        error_modules = ''
        if bad_module in previous_versions['error_modules']:
            error_modules = ', '.join(previous_versions['error_modules'][bad_module])
        else:
            error_modules = ''
        
        if bad_module in details['python_modules']:
            error_modules += f"{details['python_modules'][bad_module]}" if error_modules == '' else f", {details['python_modules'][bad_module]}"
        
        return versions, error_modules


    def could_not_find_version(self, error, previous_versions, details):
        parser = JsonOutputParser(pydantic_object=Module)
        get_module_prompt = PromptTemplate(
                    template="Given a docker build error where a version could not be found:\n{error}\nIdentify the module causing the error, which is likely in the form 'from module_name==version'.\nReturn the just the name of the module using the format instructions.\n{format_instructions}",
                    input_variables=[],
                    partial_variables={"error": error, "format_instructions": parser.get_format_instructions()}
                )
        
        # Generic method for handling a try loop for getting a module name
        bad_module = self.generic_get_module_from_error(get_module_prompt, parser)
        # If we failed to get a module then we return None
        if bad_module == None: return bad_module

        versions, error_modules = self.get_versions_previous_versions(bad_module, previous_versions, details)

        parser = JsonOutputParser(pydantic_object=ModuleVersion)

        tp = "Given a could not find a version error for the '{module}' module:\n{error}\nInfer a possible working version for Python {python_version}.\nReturn the information with the format {format_instructions}, use None for version if no version could be found!"
        pv = {"module": bad_module, "error": error, "python_version": details['python_version'], "format_instructions": parser.get_format_instructions()}
        if self.rag:
            tp = "Given a could not find a version error for the '{module}' module:\n{error}\nExcluding previous versions: ({previous_versions}), perform a distributed search over the recommended versions in the error message!\nReturn the information with the format {format_instructions}, use None for version if no version could be found!"
            pv = {"module": bad_module, "error": error, "previous_versions": error_modules, "format_instructions": parser.get_format_instructions()}

        get_version_prompt = PromptTemplate(
                # template="Given a set of versions from oldest to newest ({versions}) for the '{module}' module. Perform a distributed search to retrieve a new version, excluding previously used versions ({previous_versions}).\nReturn the information with the format {format_instructions}",
                # template="Given a could not find a version error for the '{module}' module:\{error}\nFrom the error message and excluding previous versions: ({previous_versions}), locate and select a random version, which would be in the form 'from versions: version'. \nReturn the information with the format {format_instructions} using None as version if no version was found.",
                template=tp,
                input_variables=[],
                partial_variables=pv
            )
        
        out = self.generic_get_version_with_bad_modules(get_version_prompt, parser, error_modules)

        if out['module'] != bad_module:
            parser = JsonOutputParser(pydantic_object=ModuleVersion)

            tp = "Infer a possible working version of the '{module}' module for Python {python_version}.\nReturn the information with the format {format_instructions}"
            pv = {"module": bad_module, "python_version": details['python_version'], "format_instructions": parser.get_format_instructions()}
            if self.rag:
                tp = "Excluding previous versions: ({previous_versions}). Perform a distributed search over the '{module}' module versions: {versions}, selecting one to install.\nReturn the information with the format {format_instructions}"
                pv = {"versions": versions, "module": bad_module, "previous_versions": error_modules, "format_instructions": parser.get_format_instructions()}

            get_version_prompt = PromptTemplate(
                # template="Given a set of versions from oldest to newest ({versions}) for the '{module}' module. Perform a distributed search to retrieve a new version, excluding previously used versions ({previous_versions}).\nReturn the information with the format {format_instructions}",
                template=tp,
                input_variables=[],
                partial_variables=pv
            )
        
            out = self.generic_get_version_with_bad_modules(get_version_prompt, parser, error_modules)

        if 'module' in out and 'version' in out:
            return out
        else:
            return None
        

    def dependency_conflict(self, error):
        parser = JsonOutputParser(pydantic_object=ModuleVersion)

        prompt = PromptTemplate(
            template="Given a dependency conflict error:\n{error}\nReturn the module and a working version that would fix the error using the format {format_instructions}",
            input_variables=[],
            partial_variables={"error": error, "format_instructions": parser.get_format_instructions()}
        )

        chain = prompt | self.model | parser

        passed, json_out = self.execute_chain(chain, ModuleVersion)
        
        print(json_out)
        return json_out
    

    def import_error(self, error, previous_versions, details):
        parser = JsonOutputParser(pydantic_object=Module)
        get_module_prompt = PromptTemplate(
                    template="Given an ImportError:\n{error}\n Identify the import which is causing the error.\nFor this type of error, the module is normally in the text 'from x import y', where x and y are the module to import and the offending method.\nReturn the name of the module using the format instructions.\n{format_instructions}",
                    input_variables=[],
                    partial_variables={"error": error, "format_instructions": parser.get_format_instructions()}
                )
        
        # Generic method for handling a try loop for getting a module name
        bad_module = self.generic_get_module_from_error(get_module_prompt, parser)
        # If we failed to get a module then we return None
        if bad_module == None: return bad_module

        versions, error_modules = self.get_versions_previous_versions(bad_module, previous_versions, details)

        parser = JsonOutputParser(pydantic_object=ModuleVersion)

        tp = "Infer a possible working version of the '{module}' module for Python {python_version}.\nReturn the information with the format {format_instructions}"
        pv = {"error": error, "module": bad_module, "python_version": details['python_version'], "format_instructions": parser.get_format_instructions()}
        if self.rag:
            tp = "Given a comma separated list of 'Module versions' for the '{module}' module, from oldest to newest:\n{module_versions}\nPerform equally distanced sampling to return a version from the given versions, excluding previously used versions ({previous_versions}).\nReturn the information with the format {format_instructions}"
            pv = {"error": error, "module": bad_module, "module_versions": versions, "previous_versions": error_modules, "format_instructions": parser.get_format_instructions()}
            
        get_version_prompt = PromptTemplate(
                template=tp,
                input_variables=[],
                partial_variables=pv
            )
        
        out = self.generic_get_version_with_bad_modules(get_version_prompt, parser, error_modules)

        if 'module' in out and 'version' in out:
            return out
        else:
            return None


    def module_not_found(self, error, previous_versions, details):
        parser = JsonOutputParser(pydantic_object=Module)
        get_module_prompt = PromptTemplate(
                    template="Given a ModuleNotFound:\n{error}\nIdentify the module being imported which is causing this error.\nReturn the name of the module using the format instructions.\n{format_instructions}",
                    # template="Given an AttributeError:\n{error}\n Use your knowledge of Python to identify which of the existing modules ({python_modules}) is causing the error.\nReturn the name of the module using the format instructions.\n{format_instructions}",
                    input_variables=[],
                    partial_variables={"error": error, "format_instructions": parser.get_format_instructions()}
                )
        
        # Generic method for handling a try loop for getting a module name
        bad_module = self.generic_get_module_from_error(get_module_prompt, parser)
        # If we failed to get a module then we return None
        if bad_module == None: return bad_module

        versions, error_modules = self.get_versions_previous_versions(bad_module, previous_versions, details)

        parser = JsonOutputParser(pydantic_object=ModuleVersion)

        tp = "Infer a possible working version of the '{module}' module for Python {python_version}.\nReturn the information with the format {format_instructions}"
        pv = {"error": error, "module": bad_module, "python_version": details['python_version'], "format_instructions": parser.get_format_instructions()}
        if self.rag:
            tp = "Given a comma separated list of 'Module versions' for the '{module}' module, from oldest to newest:\n{module_versions}\nPerform equally distanced sampling to return a version from the given versions, excluding previously used versions ({previous_versions}). Return the information with the format {format_instructions}"
            pv = {"error": error, "module": bad_module, "module_versions": versions, "previous_versions": error_modules, "format_instructions": parser.get_format_instructions()}

        get_version_prompt = PromptTemplate(
                # template="Given a comma separated list of 'Module versions' for the '{module}' module, from oldest to newest:\n{module_versions}\nExcluding previously used versions:\n{previous_versions}\nSelect a version from the other side of the version list, depending on the last previous version. Return the information with the format {format_instructions}",
                template=tp,
                input_variables=[],
                partial_variables=pv
            )
        
        out = self.generic_get_version_with_bad_modules(get_version_prompt, parser, error_modules)

        if 'module' in out and 'version' in out:
            return out
        else:
            return None
        

    def attribute_error(self, error, previous_versions, details):
        python_modules = []
        for module in details['python_modules']:
            python_modules.append(module)

        parser = JsonOutputParser(pydantic_object=Module)
        get_module_prompt = PromptTemplate(
                    template="Given an AttributeError:\n{error}\n Use your knowledge of Python to identify which of the existing modules ({python_modules}) is causing the error.\nReturn the name of the module using the format instructions.\n{format_instructions}",
                    input_variables=[],
                    partial_variables={"error": error, 'python_modules': ', '.join(python_modules), "format_instructions": parser.get_format_instructions()}
                )
        
        # Generic method for handling a try loop for getting a module name
        bad_module = self.generic_get_module_from_error(get_module_prompt, parser)
        # If we failed to get a module then we return None
        if bad_module == None: return bad_module

        versions, error_modules = self.get_versions_previous_versions(bad_module, previous_versions, details)

        parser = JsonOutputParser(pydantic_object=ModuleVersion)

        tp = "Given an AttributeError for the '{module}' module: {error}\nIf you know a version that would fix this error, then return this for Python {python_version}.\nReturn the information with the format {format_instructions}"
        pv = {"error": error, "module": bad_module, "python_version": details['python_version'], "format_instructions": parser.get_format_instructions()}
        if self.rag:
            tp = "Given an AttributeError for the '{module}' module: {error}\nIf you know a version that would fix this error, then return this, otherwise perform equally distanced sampling to return a version from the given versions ({module_versions}).\nDO NOT return any previous ({previous_versions})!\nReturn JSON using format {format_instructions}"
            pv = {"error": error, "module": bad_module, "python_version": details['python_version'], "module_versions": versions, "previous_versions": error_modules, "format_instructions": parser.get_format_instructions()}

        get_version_prompt = PromptTemplate(
                # template="Given a comma separated list of 'Module versions' for the '{module}' module, from oldest to newest:\n{module_versions}\nExcluding previously used versions:\n{previous_versions}\nSelect a version from the other side of the version list, depending on the last previous version. Return the information with the format {format_instructions}",
                # template="Given a comma separated list of 'Module versions' for the '{module}' module, from oldest to newest:\n{module_versions}\nExcluding previously used versions:\n{previous_versions}\nIf you know a version that would fix this error, then return this.\nOtherwise perform equally distanced sampling to return a version from the given versions. Return the information with the format {format_instructions}",
                template=tp,
                input_variables=[],
                partial_variables=pv
            )
        
        out = self.generic_get_version_with_bad_modules(get_version_prompt, parser, error_modules)

        if 'module' in out and 'version' in out:
            return out
        else:
            return None


    def invalid_version(self, error):
        parser = JsonOutputParser(pydantic_object=ModuleVersion)

        prompt = PromptTemplate(
            template="Given a docker invalid versions error\n{error}\nReturn the Python module (not pip) and a working version that would fix the error using the format {format_instructions}",
            input_variables=[],
            partial_variables={"error": error, "format_instructions": parser.get_format_instructions()}
        )

        chain = prompt | self.model | parser

        passed, json_out = self.execute_chain(chain, ModuleVersion)
        
        print(json_out)
        return json_out
    

    def non_zero_error(self, error):
        parser = JsonOutputParser(pydantic_object=Module)

        get_module_prompt = PromptTemplate(
            template="Given a docker build non-zero error:\n{error}\n Identify the module which failed to install with pip, this will typically be in the form module==version, where module is the module we want.\nReturn the name of the module using the format instructions.\n{format_instructions}",
            input_variables=[],
            partial_variables={"error": error, "format_instructions": parser.get_format_instructions()}
        )
        
        # Generic method for handling a try loop for getting a module name
        bad_module = self.generic_get_module_from_error(get_module_prompt, parser)

        return bad_module
    

    def non_zero_error_version(self, error, module, previous_versions, details):
        versions, error_modules = self.get_versions_previous_versions(module, previous_versions, details)

        parser = JsonOutputParser(pydantic_object=ModuleVersion)

        tp = "Infer a possible working version of the '{module}' module for Python {python_version}.\nReturn the information with the format {format_instructions}"
        pv = {"error": error, "module": module, "python_version": details['python_version'], "format_instructions": parser.get_format_instructions()}
        if self.rag:
            tp = "Given a comma separated list of 'Module versions' for the '{module}' module, from oldest to newest ({module_versions})\nPerform equally distanced sampling to return a version from the given versions, excluding previously used versions ({previous_versions}). Return the information with the format {format_instructions}"
            pv = {"error": error, "module": module, "python_version": details['python_version'], "module_versions": versions, "previous_versions": error_modules, "format_instructions": parser.get_format_instructions()}

        get_version_prompt = PromptTemplate(
            # template="Given a comma separated list of 'Module versions' for the '{module}' module, from oldest to newest:\n{module_versions}\nPerform equally distanced sampling to return a version from the given versions, excluding previously used versions ({previous_versions}). Return the information with the format {format_instructions}",
                template=tp,
                # template="Given a comma separated list of 'Module versions' for the '{module}' module, from oldest to newest ({module_versions})\nExcluding previously used versions ({previous_versions}), Select a version from the other side of the version list, depending on the last previous version. Return the information with the format {format_instructions}",
                # template="Given a Non Zero Error message for the '{module}' Python module. Perform random sampling from the given versions ({module_versions}), excluding any previously used versions ({previous_versions}). Ensure the new version is different from the last previous version.\nReturn the information with the format {format_instructions}",
                input_variables=[],
                partial_variables=pv
            )
        
        out = self.generic_get_version_with_bad_modules(get_version_prompt, parser, error_modules)

        if 'module' in out and 'version' in out:
            return out
        else:
            return None


    def syntax_error_helper(self, error, previous_versions, details):
        parser = JsonOutputParser(pydantic_object=Module)
        get_module_prompt = PromptTemplate(
                    template="Given a Docker build error message: {error}\nIdentify the offending Python module and output the module name using the following format instruction {format_instructions}.",
                    input_variables=[],
                    partial_variables={"error": error, "format_instructions": parser.get_format_instructions()}
                )
        
        # Generic method for handling a try loop for getting a module name
        bad_module = self.generic_get_module_from_error(get_module_prompt, parser)
        # If we failed to get a module then we return None
        if bad_module == None: return bad_module

        versions, error_modules = self.get_versions_previous_versions(bad_module, previous_versions, details)

        parser = JsonOutputParser(pydantic_object=ModuleVersion)

        tp = "Infer a possible working version of the '{module}' module for Python {python_version}.\nReturn the information with the format {format_instructions}"
        pv = {"error": error, "module": bad_module, "python_version": details['python_version'], "format_instructions": parser.get_format_instructions()}
        if self.rag:
            tp = "Given a comma separated list of 'Module versions' for the '{module}' module, from oldest to newest:\n{module_versions}\nExcluding previously used versions:\n{previous_versions}\nSelect a version from the other side of the version list, depending on the last previous version. Return the information with the format {format_instructions}"
            pv = {"error": error, "module": bad_module, "python_version": details['python_version'], "module_versions": versions, "previous_versions": previous_versions, "format_instructions": parser.get_format_instructions()}

        get_version_prompt = PromptTemplate(
                template=tp,
                input_variables=[],
                partial_variables=pv
            )
        
        out = self.generic_get_version_with_bad_modules(get_version_prompt, parser, error_modules)

        if 'module' in out and 'version' in out:
            return out
        else:
            return None
 

    # Process error, makes sure we call the correct method to call the LLM with
    def process_error(self, message, error_details, llm_eval):
        error_type = None
        output = None
        
        if 'Could not find a version' in message:
            if self.logging: print("Could not find a version")
            error_type = 'VersionNotFound'
            output = self.could_not_find_version(message, error_details, llm_eval)
        elif 'dependency conflicts' in message:
            if self.logging: print("Dependency conflict")
            error_type = 'DependencyConflict'
            output = self.dependency_conflict(message)
        elif 'ImportError' in message:
            if self.logging: print('Import Error')
            error_type = 'ImportError'
            if 'DJANGO_SETTINGS_MODULE is undefined' in message:
                output = None
            else:
                output = self.import_error(message, error_details, llm_eval)
        elif 'ModuleNotFoundError' in message:
            if self.logging: print("Module not found")
            error_type = 'ModuleNotFound'
            output = self.module_not_found(message, error_details, llm_eval)
        elif 'AttributeError' in message:
            if self.logging: print("Attribute error")
            error_type = 'AttributeError'
            output = self.attribute_error(message, error_details, llm_eval)
        elif 'InvalidVersion' in message:
            if self.logging: print('Invalid Version')
            error_type = 'InvalidVersion'
            output = self.invalid_version(message)
        elif 'non-zero code' in message: # Docker specific error message
            if self.logging: print('Non-zero error code from docker build')
            error_type = 'NonZeroCode'
            output = self.non_zero_error(message)
            output = self.non_zero_error_version(message, output, error_details, llm_eval)
        elif 'SyntaxError' in message:
            if self.logging: print('Syntax Error: Python specific error that needs more information')
            error_type = 'SyntaxError'
            output = self.syntax_error_helper(message, error_details, llm_eval)
        else:
            if self.logging: print('No error type found')
            error_type = 'None'

        return output, error_type

# Handle argument parsing
def process_args():
    def str2bool(value):
        """Convert a string representation of a boolean to an actual boolean value."""
        if isinstance(value, bool):
            return value
        if value.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        elif value.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        else:
            raise argparse.ArgumentTypeError(f'Boolean value expected, got "{value}".')
        
    parser = argparse.ArgumentParser(description='File to evaluate')
    parser.add_argument('-f', '--file', type=str, help="The full path and name of the file to evaluate")
    parser.add_argument('-b', '--base', type=str, nargs="?", default='http://localhost:11434', const='http://localhost:11434', help="The ollama URL can vary depending on the system")
    parser.add_argument('-m', '--model', type=str, nargs="?", default='phi3:medium', const='phi3:medium', help="The name of the model to use for evaluation")
    parser.add_argument('-t', '--temp', type=str, nargs="?", default='0.7', const='0.7', help="The temperature for the models predictive output. Typically a range from 0-2, default is 0.7")
    parser.add_argument('-l', '--loop', type=int, nargs="?", default=5, const=5, help="How many times we will loop to find a solution")
    parser.add_argument('-r', '--range', type=int, nargs="?", default=0, const=0, help="The search range, expands out above and below the found Python version, defaults to 0")
    parser.add_argument('-ra', '--rag', type=str2bool, nargs="?", default=True, const=True, help="Flag to enable RAG in the system.")
    parser.add_argument('-v', '--verbose', action="store_true", help="Verbose logging of information")
    return parser.parse_args()

def main():
    args = process_args()
    file_path = '/'.join(args.file.split('/')[:-1])
    # ollama_helper = OllamaHelper(model='gpt-4o-2024-05-13', logging=True)
    ollama_helper = OllamaHelper(base_url=args.base, model=args.model, logging=True, temp=args.temp, base_modules=file_path+"/modules")

    meow = {'python_version': '2.7', 'python_modules': {'sqlalchemy': '1.4.49', 'redis': '3.5.3', 'requests': '2.27.1', 'python-memcached': '1.62'}}

    syntaxerror = """
Traceback (most recent call last):
  File "/app/snippet.py", line 6, in <module>
    import memcache
  File "/usr/local/lib/python2.7/site-packages/memcache.py", line 374
    def quit_all(self) -> None:
                       ^
SyntaxError: invalid syntax
"""

    could_not_error = """
{"stream":"\u001b[91mERROR: Could not find a version that satisfies the requirement djangorestframework==3.15.2 (from versions: 0.1, 0.1.1, 0.2.0, 0.2.1, 0.2.2, 0.2.3, 0.2.4, 0.3.0, 0.3.1, 0.3.2, 0.3.3, 0.4.0, 2.0.0, 2.0.1, 2.0.2, 2.1.0, 2.1.1, 2.1.2, 2.1.3, 2.1.4, 2.1.5, 2.1.6, 2.1.7, 2.1.8, 2.1.9, 2.1.10, 2.1.11, 2.1.12, 2.1.13, 2.1.14, 2.1.15, 2.1.16, 2.1.17, 2.2.0, 2.2.1, 2.2.2, 2.2.3, 2.2.4, 2.2.5, 2.2.6, 2.2.7, 2.3.0, 2.3.1, 2.3.2, 2.3.3, 2.3.4, 2.3.5, 2.3.6, 2.3.7, 2.3.8, 2.3.9, 2.3.10, 2.3.11, 2.3.12, 2.3.13, 2.3.14, 2.4.0, 2.4.1, 2.4.2, 2.4.3, 2.4.4, 2.4.5, 2.4.6, 2.4.8, 3.0.0, 3.0.1, 3.0.2, 3.0.3, 3.0.4, 3.0.5, 3.1.0, 3.1.1, 3.1.2, 3.1.3, 3.2.0, 3.2.1, 3.2.2, 3.2.3, 3.2.4, 3.2.5, 3.3.0, 3.3.1, 3.3.2, 3.3.3, 3.4.0, 3.4.1, 3.4.2, 3.4.3, 3.4.4, 3.4.5, 3.4.6, 3.4.7, 3.5.0, 3.5.1, 3.5.2, 3.5.3, 3.5.4, 3.6.0, 3.6.1, 3.6.2, 3.6.3, 3.6.4, 3.7.0, 3.7.1, 3.7.2, 3.7.3, 3.7.4, 3.7.5, 3.7.6, 3.7.7, 3.8.0, 3.8.1, 3.8.2, 3.9.0, 3.9.1, 3.9.2, 3.9.3, 3.9.4, 3.10.0, 3.10.1, 3.10.2, 3.10.3, 3.11.0, 3.11.1, 3.11.2, 3.12.0, 3.12.1, 3.12.2, 3.12.3, 3.12.4, 3.13.0, 3.13.1, 3.14.0, 3.15.0, 3.15.1)\nERROR: No matching distribution found for djangorestframework==3.15.2\n\u001b[0m"}
{"errorDetail":{"code":1,"message":"The command 'pip install --trusted-host pypi.python.org --default-timeout=100 djangorestframework==3.15.2' returned a non-zero code: 1"},"error":"The command 'pip install --trusted-host pypi.python.org --default-timeout=100 djangorestframework==3.15.2' returned a non-zero code: 1"}
"""

    import_error = """
Traceback (most recent call last):
  File "/app/snippet.py", line 1, in <module>
    from django.test.simple import DjangoTestSuiteRunner
ImportError: No module named simple
"""

    attribute_error = """
Traceback (most recent call last):
          File "/app/snippet.py", line 13, in <module>
            driver = webdriver.PhantomJS(executable_path="node_modules/phantomjs/bin/phantomjs")
        AttributeError: 'module' object has no attribute 'PhantomJS'
"""

    non_zero_error = """
{"stream":"\u001b[91m    ERROR: Command errored out with exit status 1:\n     command: /usr/local/bin/python -c 'import sys, setuptools, tokenize; sys.argv[0] = '\"'\"'/tmp/pip-install-an7_hj/word2vec/setup.py'\"'\"'; __file__='\"'\"'/tmp/pip-install-an7_hj/word2vec/setup.py'\"'\"';f=getattr(tokenize, '\"'\"'open'\"'\"', open)(__file__);code=f.read().replace('\"'\"'\\r\\n'\"'\"', '\"'\"'\\n'\"'\"');f.close();exec(compile(code, __file__, '\"'\"'exec'\"'\"'))' egg_info --egg-base /tmp/pip-pip-egg-info-NOriAn\n         cwd: /tmp/pip-install-an7_hj/word2vec/\n    Complete output (5 lines):\n    Traceback (most recent call last):\n      File \"\u003cstring\u003e\", line 1, in \u003cmodule\u003e\n      File \"/tmp/pip-install-an7_hj/word2vec/setup.py\", line 23, in \u003cmodule\u003e\n        from Cython.Build import cythonize\n    ImportError: No module named Cython.Build\n    ----------------------------------------\n\u001b[0m"}
{"stream":"\u001b[91mERROR: Command errored out with exit status 1: python setup.py egg_info Check the logs for full command output.\n\u001b[0m"}
{"errorDetail":{"code":1,"message":"The command 'pip install --trusted-host pypi.python.org --default-timeout=100 word2vec==0.9.1' returned a non-zero code: 1"},"error":"The command 'pip install --trusted-host pypi.python.org --default-timeout=100 word2vec==0.9.1' returned a non-zero code: 1"}
"""
    previous_versions = {'error_modules': {'django': ['1.9rc2']}}

    versions = ollama_helper.pypi.read_python_file('cython', '2.7')
    print(versions)

    pass
    
if __name__ == "__main__":
    main()
