import streamlit as st
import asyncio
from data_ingestion import DataIngestion
from data_processing import DataProcessing_csv
from agents import ImageerrorAnalysisagent , LogFilesAnalysisagentCSV , LogFilesAnalysisAgentLog
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
    Image_error_Analysis_agent = ImageerrorAnalysisagent()
    LogFilesAnalysisagent_csv = LogFilesAnalysisagentCSV()
    LogFilesAnalysisagent_log = LogFilesAnalysisAgentLog()
    # Set Streamlit layout options
    st.set_page_config(page_title="GenAI Error Log Analysis", layout="wide")
    # Sidebar Configuration
    with st.sidebar:
        st.title("Upload Options")
        # Fetch projects asynchronously
        # File uploader for error log
        uploaded_files = st.file_uploader("Upload your error log (CSV or LOG)", type=["csv", "log"], accept_multiple_files=True)

        
        # Display "OR" separator
        st.markdown("<style>.separator {display: flex; align-items: center; text-align: center; color: #888; margin: 20px 0;} .separator::before, .separator::after {content: ''; flex: 1; border-bottom: 1px solid #ccc;} .separator::before {margin-right: 10px;} .separator::after {margin-left: 10px;}</style><div class='separator'>OR</div>", unsafe_allow_html=True)

        projects = await data_ingestion.get_gitlab_projects()
        projects = [(None, None)] + projects
        # Add a project selection dropdown
        selected_project_id = st.selectbox("Select a Project", options=projects, format_func=lambda x: x[1] if x[1] else None)
        
        # Display "OR" separator
        st.markdown("<style>.separator {display: flex; align-items: center; text-align: center; color: #888; margin: 20px 0;} .separator::before, .separator::after {content: ''; flex: 1; border-bottom: 1px solid #ccc;} .separator::before {margin-right: 10px;} .separator::after {margin-left: 10px;}</style><div class='separator'>OR</div>", unsafe_allow_html=True)
        
        # Screenshot uploader for multiple files
        screenshot_files = st.file_uploader("Upload screenshots (PNG or JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    
    # Main Window
    st.title("Automated Error Log Analysis")
    st.write(
        "Use this tool to automate the analysis of error logs with GenAI. "
        "Upload a log file and optionally provide additional info for contextual information."
    )
    if uploaded_files:
        csv_files = [file for file in uploaded_files if file.name.endswith(".csv")]
        log_files = [file for file in uploaded_files if file.name.endswith(".log")]
        
        if csv_files:
            data_frames = await data_ingestion.load_error_log(uploaded_files)
            log_file_responses = await LogFilesAnalysisagent_csv.execute_agent(data_frames)
        
            # Display each result
            for i, data in enumerate(log_file_responses):
                for batch_report in data:  # Each 'data' item is a list of batch reports
                    st.write(batch_report)
        
        if log_files:
            temp_log_files = {}
            file_number = 1  # File counter
            for log_file in log_files:
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(log_file.read())
                    temp_log_files[temp_file.name] = log_file.name
            
            temp_file_paths = list(temp_log_files.keys())
            analysis_responses  = await LogFilesAnalysisagent_log.execute_agent(temp_file_paths)
            
            st.markdown("""
                    <style>
                        .custom-box {
                            background-color: #f0f4f8;  /* Light grey-blue background */
                            padding: 15px;
                            border-radius: 8px;
                            margin-bottom: 10px;
                        }
                        .custom-heading {
                            color: #333333;  /* Darker text color for better readability */
                            font-weight: bold;
                            font-size: 24px;  /* Increase font size for the heading */
                            margin-bottom: 10px;
                        }
                    </style>
                """, unsafe_allow_html=True)
            for  result in analysis_responses:
                response = result[0]
                original_file_name = temp_log_files[result[1]]
                # Display the file name as a subheader
                st.subheader(f"**File {file_number}:** {original_file_name}")
                file_number += 1

                # Parse and display the detailed response
                error_analyzed = json.loads(response).get('DetailedResponseFull', [])
                st.write("### Error Report")
                error_number = 1  # Error counter within the file
                for error in error_analyzed:
                     st.markdown(f"<div class='custom-box'><div class='custom-heading'> {error_number}: {error.get('heading', 'N/A')}</div></div>", unsafe_allow_html=True)
                     error_number += 1
                     st.write(f"**Error Message:** {error.get('error_message', 'N/A')}")
                     st.write(f"**Line Number:** {error.get('line_number', 'N/A')}")
                     st.write(f"**File Impacted:** {error.get('file_impacted', 'N/A')}")
                     st.write(f"**Possible Cause(s):** {error.get('possible_cause', 'N/A')}")
#                     st.write(f"**Suggested Solutions:** {error.get('suggested_solutions', 'N/A')}")
#                     st.write(f"**Associated Merge Requests:** {error.get('associated_merge_requests', 'N/A')}")
                     suggested_solution = error.get('suggested_solutions', {})
                     st.write(f"**Suggested Solution:** {suggested_solution.get('suggested_solution', 'N/A')}")
        
                    # Display Original and Corrected Code only if they exist
                     code_fix = suggested_solution.get('code_fix')
                     if code_fix:
                            original_code = code_fix.get('original_code', None)
                            corrected_code = code_fix.get('corrected_code', None)
                            
                            if original_code:
                                st.write("**Original Code:**")
                                st.code(original_code, language='python')
                                
                            if corrected_code:
                                st.write("**Corrected Code:**")
                                st.code(corrected_code, language='python')
                        
                     st.write(f"**Associated Merge Requests:** {error.get('associated_merge_requests', 'N/A')}")
                    
                
                

                        
            
            
        
        
    # Check if a project is selected and fetch log files
    if  selected_project_id[0] is not None:
        st.session_state.selected_project_id = selected_project_id[0]  # Store only the ID
        
        # Fetch log files only if a valid project is selected
        log_file_paths = await data_ingestion.fetch_log_files(st.session_state.selected_project_id)
        
        if log_file_paths:
            for log_file in log_file_paths:
                st.write(log_file)  # Display the full path of each log file
        else:
            st.write("No log files found in the selected project.")
    
    if screenshot_files:
        base_64_files = await data_processing.image_to_base64(screenshot_files)
         # Display each image using its base64 representation
        image_responses = await Image_error_Analysis_agent.execute_agent(base_64_files)
        for file_name, response in zip(screenshot_files, image_responses):
            st.subheader(f"**File Name:** {file_name.name}")  # Display the file name
            error_anlaysed = json.loads(response).get('DetailedResponseFull')
            st.markdown("""
    <style>
        .custom-box {
            background-color: #f0f4f8;  /* Light grey-blue background */
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .custom-heading {
            color: #333333;  /* Darker text color for better readability */
            font-weight: bold;
            font-size: 24px;  /* Increase font size for the heading */
            margin-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)
            for error in error_anlaysed:
                st.write("### Error Report")
    # Heading inside the custom box
                st.markdown(f"<div class='custom-box'><div class='custom-heading'>{error.get('heading', 'N/A')}</div></div>", unsafe_allow_html=True)
                st.write(f"**Error Message:** {error.get('error_message', 'N/A')}")
                st.write(f"**Line Number:** {error.get('line_number', 'N/A')}")
                st.write(f"**File Impacted:** {error.get('file_impacted', 'N/A')}")
                st.write(f"**Possible Cause(s):** {error.get('possible_cause', 'N/A')}")
                
                suggested_solution = error.get('suggested_solutions', {})
                st.write(f"**Suggested Solution:** {suggested_solution.get('suggested_solution', 'N/A')}")
                
                # Display Original and Corrected Code only if they exist
                code_fix = suggested_solution.get('code_fix')
                if code_fix:
                    original_code = code_fix.get('original_code', None)
                    corrected_code = code_fix.get('corrected_code', None)
                    
                    if original_code:
                        st.write("**Original Code:**")
                        st.code(original_code, language='python')
                    
                    if corrected_code:
                        st.write("**Corrected Code:**")
                        st.code(corrected_code, language='python')
                
                st.write(f"**Associated Merge Requests:** {error.get('associated_merge_requests', 'N/A')}")
                st.markdown('</div>', unsafe_allow_html=True)  # Close custom div
                    
                
                
                
                
#                with st.chat_message("user"):
#                    st.subheader(error.get('heading', 'N/A'))
#                    st.write(f"**Error Message:** {error.get('error_message', 'N/A')}")
#                    st.write(f"**Line Number:** {error.get('line_number', 'N/A')}")
#                    st.write(f"**File Impacted:** {error.get('file_impacted', 'N/A')}")
#                    st.write(f"**Possible Cause(s):** {error.get('possible_cause', 'N/A')}")
#    #                     st.write(f"**Suggested Solutions:** {error.get('suggested_solutions', 'N/A')}")
#    #                     st.write(f"**Associated Merge Requests:** {error.get('associated_merge_requests', 'N/A')}")
#                    suggested_solution = error.get('suggested_solutions', {})
#                    st.write(f"**Suggested Solution:** {suggested_solution.get('suggested_solution', 'N/A')}")
            
                        # Display Original and Corrected Code only if they exist
#                    code_fix = suggested_solution.get('code_fix')
#                    if code_fix:
#                        original_code = code_fix.get('original_code', None)
#                        corrected_code = code_fix.get('corrected_code', None)
                                
#                        if original_code:
#                                    st.write("**Original Code:**")
#                                    st.code(original_code, language='python')
                                    
#                        if corrected_code:
#                                    st.write("**Corrected Code:**")
#                                    st.code(corrected_code, language='python')
                            
#                    st.write(f"**Associated Merge Requests:** {error.get('associated_merge_requests', 'N/A')}")
                
                    
            
    
        
        
# Run the Streamlit app
if __name__ == "__main__":
    asyncio.run(main())