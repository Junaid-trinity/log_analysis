import os
import re
import time
import pandas as pd
from dotenv import load_dotenv
from openai_client import OpenAIClient
from langfuse_client import LangfuseClient
from prompts import ERROR_SCREENSHOTS_ANALYSIS_SYSTEM_PROMPT, LOG_FILES_ANALYSIS_SYSTEM_PROMPT , LOG_FILES_ANALYSIS_SYSTEM_PROMPT_LOGS
from schemas import  AgentResponse , DetailedResponseFull , Conversation
import asyncio
from data_processing import DataProcessing_csv , DataProcessing_Log



# Load environment variables
load_dotenv(override=True)

class ImageerrorAnalysisagent():
    
    def __init__(self):
        self.langfuse_client = LangfuseClient()
        self.openai_client = OpenAIClient()
        self.conversation = Conversation()
        
    async def execute_agent(self,base64_images):
        """Main method to execute Image_error_Analysis_agent."""
        if self.conversation.trace_id is None:
            self.conversation.trace_id = self._start_trace()
        
        async def extract_text_frm_image(base64_image):
            try:
            
                messages = [
                    {"role": "system", "content": ERROR_SCREENSHOTS_ANALYSIS_SYSTEM_PROMPT },
                    {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}", "detail": "high"}}
            ]}
                ]

                response = await self.openai_client.chat_completion_request(
                    messages=messages,
                    trace_id=self.conversation.trace_id,
                    request_name="Screenshot error analysis",response_format=DetailedResponseFull)
                
                return response.message
            except Exception as e:
                return e
        
        
        txts_frm_images = [extract_text_frm_image(base64_image) for base64_image in base64_images]
        
        
        return  await asyncio.gather(*txts_frm_images)
    def _start_trace(self):
        """Helper method to start a new trace and return its ID."""
        if self.langfuse_client.langfuse:
            trace = self.langfuse_client.langfuse.trace(
                name="Image-Files-Analysis-Agent",
                input=self.conversation.query,
                start_time=time.time(),
                tags=["development"],
                public=False,
            )
            return trace.id
        else:
            return None    
        
class LogFilesAnalysisagentCSV():
    def __init__(self):
        self.langfuse_client = LangfuseClient()
        self.openai_client = OpenAIClient()
        self.data_processing = DataProcessing_csv()
    
    async def execute_agent(self, dataframes):
        """Main method to execute log analysis agent."""
        
        async def process_data(dataframe): 
            parsed_data = await self.data_processing.parse_logs(dataframe)
            cleaned_data = await self.data_processing.clean_data(parsed_data)
            table_header = cleaned_data.columns.tolist()
            batches = []
            batch_size = 100
            total_rows = len(cleaned_data)

            for start in range(0, total_rows, batch_size):
                batch_data = cleaned_data.iloc[start:start + batch_size]
                
                # Create a task for each batch to be processed in parallel
                batch = self.data_processing.generate_markdown_report(table_header, batch_data)
                batches.append(batch)
            
            # Run all tasks concurrently and gather the results
            return await asyncio.gather(*batches)
        
        async def error_analysis_genai(markdown_report):
            """Analyze the error messages and return a report"""
            try : 
                messages = [
                    {"role": "system", "content": LOG_FILES_ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": markdown_report}
                ]
                response = await self.openai_client.chat_completion_request(
                    messages=messages,
                    trace_id=0,
                    request_name="Screenshot error analysis",)
                
                return response.message
            except Exception as e:
                return e
        
        """Main part to execute log analysis agent."""
        
        # Process each dataframe and gather results
        markdown_reports_form = [process_data(df) for df in dataframes]
        markdown_reports_forms = await asyncio.gather(*markdown_reports_form)

#        results = [error_analysis_genai(markdown_report) for markdown_report in markdown_reports_forms]
        
        
        return markdown_reports_forms
        


class LogFilesAnalysisAgentLog:
    def __init__(self):
        self.langfuse_client = LangfuseClient()
        self.openai_client = OpenAIClient()
        self.conversation = Conversation()

        
        
    async def execute_agent(self, log_file_paths):
        """Main method to execute log analysis agent."""
         # Start trace if not already set
        if self.conversation.trace_id is None:
            self.conversation.trace_id = self._start_trace()

        async def process_data(log_file_paths):
            tasks = []
            log_file_names = []
            # Parse each log file and add parsing tasks to the list
            for log_file_path in log_file_paths:
                log_file_names.append(log_file_path)  # Store file name
                log_processor = DataProcessing_Log(log_file_path)
                
                # Convert log file to markdown asynchronously
                convert_task = log_processor.convert_log_to_markdown()
                tasks.append(convert_task)
            
            # Wait for all conversion tasks to complete
            markdown_reports = await asyncio.gather(*tasks)
            
            return markdown_reports , log_file_names
        
        async def error_analysis_genai(markdown_report):
            """Analyze the error messages and return a report"""
            try:
                messages = [
                    {"role": "system", "content": LOG_FILES_ANALYSIS_SYSTEM_PROMPT_LOGS},
                    {"role": "user", "content": f"Analyse the following error logs file: {markdown_report}"}
                ]
                response = await self.openai_client.chat_completion_request(
                    messages=messages,
                    trace_id=self.conversation.trace_id,
                    request_name="log file error analysis",response_format=DetailedResponseFull
                )
                
                return response.message 
            except Exception as e:
                return str(e)
        
        markdown_reports , log_file_names = await process_data(log_file_paths)
        
        # Perform error analysis on each markdown report
        analysis_tasks = [error_analysis_genai(report) for report in markdown_reports]
        error_analysis_reports = await asyncio.gather(*analysis_tasks)
        
        return list(zip(error_analysis_reports, log_file_names))
    
    
    def _start_trace(self):
        """Helper method to start a new trace and return its ID."""
        if self.langfuse_client.langfuse:
            trace = self.langfuse_client.langfuse.trace(
                name="Log-Files-Analysis-Agent",
                input=self.conversation.query,
                start_time=time.time(),
                tags=["development"],
                public=False,
            )
            return trace.id
        else:
            return None