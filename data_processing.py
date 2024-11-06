# data_processing.py
import pandas as pd
import streamlit as st
import textwrap
import base64
import asyncio
import re
import aiofiles
import textwrap
import tiktoken


class DataProcessing_csv:
    async def parse_logs(self, data):
        """Parses log data without filtering specific columns."""
        return data

    async def clean_data(self, data):
        data = data.fillna('None')
        return data
    import textwrap

    async def generate_markdown_report(self, table_header, batch_data, char_limit=50):
        """Generates a markdown report for a batch of 1000 rows with text formatting for long values."""
        report = ["#**Error Log Data**:\n"]
        report.append("-------------------------------------------------")
        
        # Use the provided table_header for the header row
        headers = "| " + " | ".join(table_header) + " |"
        separator = "| " + " | ".join(["---"] * len(table_header)) + " |"
        report.append(headers)
        report.append(separator)

        # Function to wrap text for columns that exceed the char limit
        def format_cell(cell_value):
            if len(str(cell_value)) > char_limit:
                return "<br>".join(textwrap.wrap(str(cell_value), char_limit))
            return str(cell_value)

        # Append each row of data to the markdown report
        for _, row in batch_data.iterrows():
            row_data = "| " + " | ".join(format_cell(value) for value in row) + " |"
            report.append(row_data)

        report.append("-------------------------------------------------")
        return "\n".join(report)

    
    async def image_to_base64(self,files):
        async def encode_file(file_obj):
            file_obj.seek(0)  # Ensure the file pointer is at the start
            return base64.b64encode(file_obj.read()).decode("utf-8")

        # Process all files in parallel
        return await asyncio.gather(*[encode_file(file) for file in files])
    
    



import pandas as pd

class DataProcessing_Log:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path

    async def convert_to_df(self):
        with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as log_file:
            # Read each line from the log file into a list
            lines = [line.strip() for line in log_file]

        # Convert the list of lines to a DataFrame with each line as a row
        df = pd.DataFrame(lines, columns=['Logs'])
        df = df[df['Logs'].notna()]  # Remove rows with NaN values in the 'Logs' column
        df = df[df['Logs'].str.strip() != ""]  # Remove rows where 'Logs' is empty or whitespace
        return df

    async def convert_log_to_markdown(self):
        df = await self.convert_to_df()
        report = ["# **Error Log Data**:\n"]

        for log in df['Logs']:
            # Each log entry is simply enclosed within "|"
            report.append(f"| {log} |")
        
        return "\n".join(report)






