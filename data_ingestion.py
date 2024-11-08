# data_ingestion.py
import pandas as pd
import aiohttp
import asyncio
import streamlit as st
from dotenv import load_dotenv
import os
import gitlab
from langfuse_client import LangfuseClient
import time 
from schemas import   Conversation

class DataIngestion:
    def __init__(self):
        load_dotenv(override=True)  # Load environment variables from .env file
        self.langfuse_client = LangfuseClient()
        self.conversation = Conversation()
        
    

    async def load_error_log(self, uploaded_files):
        """Asynchronously processes multiple error log files in parallel."""
        
        async def load_single_file(file):
            """Asynchronously loads a single CSV file."""
           
            try:
                data = pd.read_csv(file)
                return data
            except Exception as e:
                self.langfuse_client.log_and_raise_error(f"DataIngestion_pipeline -> Error loading file {file.name}: {e}", self.conversation.trace_id)

                return None
        
        # Process all files concurrently
        tasks = [load_single_file(file) for file in uploaded_files]
        return await asyncio.gather(*tasks)

    async def get_gitlab_projects(self):
        """Fetches a list of GitLab projects owned by the authenticated user."""
        try:
            GITLAB_URL = os.getenv("GITLAB_URL")
            ACCESS_TOKEN = os.getenv("gitlab_key")
            gl = gitlab.Gitlab(GITLAB_URL, private_token=ACCESS_TOKEN)
            projects = gl.projects.list(membership=True, as_list=False)
            return [(project.id, project.name) for project in projects]
        except Exception as e:
            self.langfuse_client.log_and_raise_error(f"DataIngestion_pipeline -> Error fetching GitLab projects: {str(e)}", self.conversation.trace_id)
            return []
    
    
        # Additional helper functions for data_ingestion
    async def get_gitlab_branches(self, project_id):
        """Fetches branches for a given GitLab project."""
        try:
            GITLAB_URL = os.getenv("GITLAB_URL")
            ACCESS_TOKEN = os.getenv("gitlab_key")
            gl = gitlab.Gitlab(GITLAB_URL, private_token=ACCESS_TOKEN)
            project = gl.projects.get(project_id)
            branches = project.branches.list()
            return [(branch.name, branch.name) for branch in branches]
        except Exception as e:
            self.langfuse_client.log_and_raise_error(f"DataIngestion_pipeline -> Error fetching branches: {str(e)}", self.conversation.trace_id)
            return []

    async def get_gitlab_log_files(self, project_id, branch_name, log_path):
        """Fetches log files (names and contents) asynchronously from a specific path in a GitLab project branch."""
        try:
            GITLAB_URL = os.getenv("GITLAB_URL")
            ACCESS_TOKEN = os.getenv("gitlab_key")
            gl = gitlab.Gitlab(GITLAB_URL, private_token=ACCESS_TOKEN)
            project = gl.projects.get(project_id)
            try :
                # Use an empty string to fetch from the root directory if log_path is "/"
                effective_path = None if log_path == "/" else log_path
                
                if log_path == "/":
                    items = project.repository_tree(ref=branch_name,recursive=False)
                else :
                    # Fetch the file list from the specified path and branch
                    items = project.repository_tree(path=effective_path, ref=branch_name, recursive=True)
                
                # Filter for log files (e.g., .log or .txt files)
                log_files = [item for item in items if item['type'] == 'blob' and (item['name'].endswith('.log') or item['name'].endswith('.txt'))]
                # If no log files are found, return a message
                if not log_files:
                    return [{"name": "No log files in the specified path", "content": "No log files in the specified path"}]
                # Define a helper function to fetch file content asynchronously
                async def fetch_file_content(file):
                    file_path = file['path']
                    file_content = await asyncio.to_thread(project.files.get, file_path=file_path, ref=branch_name)
                    return {"name": file['name'], "content": file_content.decode()}  # Decode content to string
                
                # Asynchronously fetch all file contents
                log_file_data = await asyncio.gather(*(fetch_file_content(file) for file in log_files))
                
                return log_file_data
            except Exception as e:
                return [{"name": "No log files in the specified path", "content": "No log files in the specified path"}]
        except Exception as e:
            self.langfuse_client.log_and_raise_error(f"DataIngestion_pipeline -> Error fetching log files from gitlab: {str(e)}", self.conversation.trace_id)
            return [{"name": "No log files in the specified path", "content": "No log files in the specified path"}]
    
    
    
    
    async def fetch_log_files(self, project_id):
        """Fetches log file paths in a GitLab project repository."""
        try:
            GITLAB_URL = os.getenv("GITLAB_URL")
            ACCESS_TOKEN = os.getenv("gitlab_key")
            gl = gitlab.Gitlab(GITLAB_URL, private_token=ACCESS_TOKEN)
            project = gl.projects.get(project_id)

            log_file_paths = []

            # Asynchronously search within each folder
            async def async_recursive_search(path=''):
                tree = project.repository_tree(path=path, recursive=False)
                for item in tree:
                    if item['type'] == 'tree':
                        await async_recursive_search(item['path'])  # Recursive async search for sub-folders
                    elif item['type'] == 'blob' and item['name'].endswith('.log'):
                        log_file_paths.append(item['path'])

            # Step 1: Check the root directory
            root_tree = project.repository_tree(recursive=False)
            for item in root_tree:
                if item['type'] == 'blob' and item['name'].endswith('.log'):
                    log_file_paths.append(item['path'])

            # Step 2: Check for a folder named 'logs'
            logs_folder = next((item for item in root_tree if item['type'] == 'tree' and item['name'] == 'logs'), None)
            if logs_folder:
                await async_recursive_search(logs_folder['path'])  # If 'logs' exists, search it
            else:
                # Step 3: Asynchronously search each top-level folder if 'logs' is absent
                top_level_folders = [item for item in root_tree if item['type'] == 'tree']
                await asyncio.gather(*(async_recursive_search(folder['path']) for folder in top_level_folders))

            return log_file_paths

        except Exception as e:
            self.langfuse_client.log_and_raise_error(f"DataIngestion_pipeline -> Error fetching log files from gitlab: {str(e)}", self.conversation.trace_id)
            return []

