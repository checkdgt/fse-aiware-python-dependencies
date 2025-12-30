# Base file for Ollama helper
# Holds the strings needed for requests

from langchain_community.chat_models import ChatOllama
# from langchain_community.chat_models import ChatOpenAI
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

class OllamaHelperBase():
    
    def __init__(self, base_url="http://localhost:11434", model='llama3', temp=0.7, logging=False) -> None:
        self.logging = logging
        if 'gpt' in model:
            load_dotenv()
            OPENAI_KEY = os.getenv('OPENAI_KEY')
            self.model = ChatOpenAI(model=model, api_key=OPENAI_KEY, temperature=temp)
        else:
            self.model = ChatOllama(base_url=base_url, model=model, format="json", temperature=temp)
    
    # Reads the contents of the given file
    def read_python_file(self, file):
        with open(file, 'r') as file:
            data = file.read().replace('\n', '')
        return data