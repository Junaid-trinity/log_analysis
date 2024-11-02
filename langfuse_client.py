import sys
sys.path.append('schemas.py')
from langfuse import Langfuse
import os
from dotenv import load_dotenv
import traceback
import logging
from schemas import ResponseType

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LangfuseClient:
    def __init__(self):
        self.logger = logger
        self.langfuse = self._initialize_langfuse()

    def _initialize_langfuse(self):
        try:
            return Langfuse(
                secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                host=os.getenv("LANGFUSE_HOST"),
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize Langfuse: {e}")
            return None

    def log_and_raise_error(self, error_message, trace_id=None):
        self.logger.error(error_message)
        self.logger.error(traceback.format_exc())
        if self.langfuse and trace_id:
            self.langfuse.event(trace_id=trace_id, name="Error", input=error_message)
        raise Exception(error_message)

    def log_generation_trace(self, trace_id, request_name, params, output_data, status_message, usage=None, start_time=None, end_time=None):
        if trace_id:
            trace = self.langfuse.trace(id=trace_id)
            output_message = self._extract_output_message(output_data)
            generation_trace = trace.generation(
                name=request_name,
                model=os.getenv("DEFAULT_COMPLETIONS_MODEL"),
                model_parameters=self._build_model_parameters(params),
                input=params["messages"],
                metadata={k: v for k, v in params.items() if k == "tools"},
                output=output_message,
                status_message=status_message,
                usage=usage,
                start_time=start_time,
                end_time=end_time,
            )
            return generation_trace

    def _extract_output_message(self, output_data):
        if output_data.response_type == ResponseType.TEXT:
            return output_data.message
        elif output_data.response_type == ResponseType.TOOL_CALL:
            return output_data.tool_calls
        elif output_data.response_type == ResponseType.STRUCTURED_OUTPUT:
            return output_data.structured_output
        elif output_data.response_type == ResponseType.STREAMING_RESPONSE:
            return "streamsing response..."
        return None

    def _build_model_parameters(self, params):
        return {
            "maxTokens": params.get("max_tokens", 2048),
            "temperature": params.get("temperature", 1.00),
            "topP": params.get("top_p", 1.00),
            "frequencyPenalty": params.get("frequency_penalty", 0.00),
            "presencePenalty": params.get("presence_penalty", 0.00),
            "stop": params.get("stop", ""),
            "stream": params.get("stream", False),
            "tool_choice": params.get("tool_choice", "auto"),
        }
