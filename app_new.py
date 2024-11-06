
import streamlit as st
import asyncio
from data_ingestion import DataIngestion
from data_processing import DataProcessing_csv
from agents import  LogFilesAnalysisAgentLog2
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image
import base64
import os
import tempfile
import json
load_dotenv(override=True)

async def main():
    # Initialize classes
    data_ingestion = DataIngestion()
    data_processing = DataProcessing_csv()
    
    LogFilesAnalysisagent_log = LogFilesAnalysisAgentLog2()

    uploaded_files = st.file_uploader("Upload your error log (CSV or LOG)", type=["csv", "log"], accept_multiple_files=True)
    if uploaded_files:
                    csv_files = [file for file in uploaded_files if file.name.endswith(".csv")]
                    log_files = [file for file in uploaded_files if file.name.endswith(".log")]
                    
                    
                    if log_files:
                        temp_log_files = {}
                        file_number = 1
                        
                        for log_file in log_files:
                            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                                temp_file.write(log_file.read())
                                temp_log_files[temp_file.name] = log_file.name
                        
                        temp_file_paths = list(temp_log_files.keys())
                        analysis_responses = await LogFilesAnalysisAgentLog2().execute_agent(temp_file_paths)
                        count = 1
                        for i in analysis_responses:
                            st.write(count)
                            count += 1
                            st.write(i)
                            
                        
# Run the Streamlit app
if __name__ == "__main__":
    asyncio.run(main())