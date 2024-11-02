# data_ingestion.py
import pandas as pd
import aiohttp
import asyncio
import streamlit as st
from dotenv import load_dotenv
import os
import gitlab

class DataIngestion:
    def __init__(self):
        load_dotenv(override=True)  # Load environment variables from .env file

    async def load_error_log(self, uploaded_files):
        """Asynchronously processes multiple error log files in parallel."""
        
        async def load_single_file(file):
            """Asynchronously loads a single CSV file."""
            try:
                data = pd.read_csv(file)
                return data
            except Exception as e:
                print(f"Error loading file {file.name}: {e}")
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
            st.error(f"Error fetching GitLab projects: {str(e)}")
            return []

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
            st.error(f"Error fetching log files: {str(e)}")
            return []
