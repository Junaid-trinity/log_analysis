import os
import re
import time
import pandas as pd
from dotenv import load_dotenv
from openai_client import OpenAIClient
from langfuse_client import LangfuseClient
from prompts import ERROR_SCREENSHOTS_ANALYSIS_SYSTEM_PROMPT, LOG_FILES_ANALYSIS_SYSTEM_PROMPT_LOGS_CSV , LOG_FILES_ANALYSIS_SYSTEM_PROMPT_LOGS
from schemas import  AgentResponse , DetailedResponseFull , Conversation
import asyncio
from data_processing import DataProcessing_csv , DataProcessing_Log
import tiktoken
import json
import streamlit as st


# Load environment variables
load_dotenv(override=True)

class ImageerrorAnalysisagent():
    
    def __init__(self):
        self.langfuse_client = LangfuseClient()
        self.openai_client = OpenAIClient()

        
    async def execute_agent(self,base64_images):
        """Main method to execute Image_error_Analysis_agent."""

        trace_id = self._start_trace(base64_images)
        
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
                    trace_id=trace_id,
                    request_name="Screenshot error analysis",response_format=DetailedResponseFull)
                
                
                return response.message
            except Exception as e:
                self.langfuse_client.log_and_raise_error(f"ImageanalysisAgent -> _get_response_from_openai: An error occurred: {e}", trace_id)
            
        
        
        txts_frm_images = [extract_text_frm_image(base64_image) for base64_image in base64_images]
        responses = await asyncio.gather(*txts_frm_images)
        update_trace_output = self.langfuse_client.langfuse.trace(id=trace_id, output = responses, status_message="Success")
        return  responses
    def _start_trace(self,base64_images):
        """Helper method to start a new trace and return its ID."""
        if self.langfuse_client.langfuse:
            trace = self.langfuse_client.langfuse.trace(
                name="Image-Files-Analysis-Agent",
                input=base64_images,
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


            trace_id = self._start_trace(dataframe)
            
            
            parsed_data = await self.data_processing.parse_logs(dataframe)
            cleaned_data = await self.data_processing.clean_data(parsed_data)
            table_header = cleaned_data.columns.tolist()
            batches = []
            batch_size = 5
            total_rows = len(cleaned_data)

            for start in range(0, total_rows, batch_size):
                batch_data = cleaned_data.iloc[start:start + batch_size]
                
                # Create a task for each batch to be processed in parallel
                batch =  self.data_processing.generate_markdown_report(table_header, batch_data)
                span = self.langfuse_client.langfuse.span(trace_id=trace_id,
                                    name="generate_markdown_report",
                                    metadata={"table_header": table_header},
                                    input = batch_data.to_dict(orient="records"),output="Batch processing initiated",status_message="Success")

                batches.append(batch)
            
            # Run all tasks concurrently and gather the results
            markdown_reports = await asyncio.gather(*batches)
            results = [error_analysis_genai(markdown_report,trace_id) for markdown_report in markdown_reports]
            responses = await asyncio.gather(*results)
            combined_responses = []
            for response in responses:
                error_analyzed = json.loads(response).get('DetailedResponseFull',[])
                for error in error_analyzed:
                    combined_responses.append(error)
            
            update_trace_output = self.langfuse_client.langfuse.trace(id=trace_id, output = combined_responses, status_message="Success")
            return combined_responses
        
        async def error_analysis_genai(markdown_report,trace_id):
            """Analyze the error messages and return a report"""
            
            try : 
                messages = [
                    {"role": "system", "content": LOG_FILES_ANALYSIS_SYSTEM_PROMPT_LOGS_CSV},
                    {"role": "user", "content": markdown_report}
                ]
                response = await self.openai_client.chat_completion_request(
                    messages=messages,
                    trace_id=trace_id,
                    request_name="csv log files error analysis",response_format=DetailedResponseFull)
                
                return response.message
            except Exception as e:
                self.langfuse_client.log_and_raise_error(f"LogfileanalysisAgent_csv -> _get_response_from_openai: An error occurred: {e}", trace_id)
              
        
        """Main part to execute log analysis agent."""
        
        # Process each dataframe and gather results
        markdown_reports_form = [process_data(df) for df in dataframes]
        markdown_reports_forms = await asyncio.gather(*markdown_reports_form)

#        results = [error_analysis_genai(markdown_report) for markdown_report in markdown_reports_forms]
        
        
        return markdown_reports_forms
        
    def _start_trace(self,dataframe):
        """Helper method to start a new trace and return its ID."""
        dataframe_summary = dataframe.head(5).to_dict()  # Sample of first 5 rows as a dictionary
        if self.langfuse_client.langfuse:
            trace = self.langfuse_client.langfuse.trace(
                name="csv-Files-Analysis-Agent",
                input=dataframe_summary,
                start_time=time.time(),
                tags=["development"],
                public=False,
            )
            return trace.id
        else:
            return None 

class LogFilesAnalysisAgentLog:
    def __init__(self):
        self.langfuse_client = LangfuseClient()
        self.openai_client = OpenAIClient()
        self.conversation = Conversation()

        
        
    async def execute_agent(self, log_file_paths):
        """Main method to execute log analysis agent."""
         # Start trace if not already set
        

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
            if self.conversation.trace_id is None:
                self.conversation.trace_id = self._start_trace(markdown_report)
            
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

                update_trace_output = self.langfuse_client.langfuse.trace(id=self.conversation.trace_id, output = response.message, status_message="Success")
                return response.message 
            except Exception as e:
                self.langfuse_client.log_and_raise_error(f"LogfileanalysisAgent_log -> _get_response_from_openai: An error occurred: {e}", self.conversation.trace_id)
                
        
        markdown_reports , log_file_names = await process_data(log_file_paths)
        
        # Perform error analysis on each markdown report
        analysis_tasks = [error_analysis_genai(report) for report in markdown_reports]
        error_analysis_reports = await asyncio.gather(*analysis_tasks)
        
        return list(zip(error_analysis_reports, log_file_names))
    
    
    def _start_trace(self,markdown_report):
        """Helper method to start a new trace and return its ID."""
        if self.langfuse_client.langfuse:
            trace = self.langfuse_client.langfuse.trace(
                name="Log-Files-Analysis-Agent",
                input=markdown_report,
                start_time=time.time(),
                tags=["development"],
                public=False,
            )
            return trace.id
        else:
            return None