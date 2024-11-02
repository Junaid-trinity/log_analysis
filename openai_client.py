import os
from dotenv import load_dotenv
import logging
import time
import json
import tiktoken
from openai import OpenAI, AsyncOpenAI, AzureOpenAI, AsyncAzureOpenAI
from schemas import ChatCompletionsResponseSchema, ResponseType
from langfuse_client import LangfuseClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConfigLoader:
    def __init__(self, required_vars):
        load_dotenv()
        self.required_vars = required_vars
        self._check_env_vars()

    def _check_env_vars(self):
        missing_vars = [var for var in self.required_vars if not os.getenv(var)]
        if missing_vars:
            raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def get(self, var_name):
        return os.getenv(var_name)
    

class OpenAIClient:
    def __init__(self, use_azure=False):
        if use_azure:
            self.config_loader = ConfigLoader([
                "DEFAULT_COMPLETIONS_MODEL", "DEFAULT_EMBEDDINGS_MODEL",
                "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"
            ])
        else:
            self.config_loader = ConfigLoader([
                "DEFAULT_COMPLETIONS_MODEL", "DEFAULT_EMBEDDINGS_MODEL",
                "OPENAI_API_KEY"
            ])
        self.langfuse_client = LangfuseClient()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.client, self.async_client = self._initialize_clients(use_azure)

    def _initialize_clients(self, use_azure):
        if use_azure:
            return (
                AzureOpenAI(
                    api_key=self.config_loader.get("AZURE_OPENAI_API_KEY"),
                    api_version="2024-07-01-preview",
                    azure_endpoint=self.config_loader.get("AZURE_OPENAI_ENDPOINT")
                ),
                AsyncAzureOpenAI(
                    api_key=self.config_loader.get("AZURE_OPENAI_API_KEY"),
                    api_version="2024-07-01-preview",
                    azure_endpoint=self.config_loader.get("AZURE_OPENAI_ENDPOINT")
                )
            )
        else:
            return (
                OpenAI(api_key=self.config_loader.get("OPENAI_API_KEY")),
                AsyncOpenAI(api_key=self.config_loader.get("OPENAI_API_KEY"))
            )

    def embedding_request(self, text, trace_id=None, request_name="embedding_request"):
        try:
            response = self.client.embeddings.create(
                input=text, model=self.config_loader.get("DEFAULT_EMBEDDINGS_MODEL")
            ).data[0].embedding
            self.langfuse_client.log_generation_trace(trace_id, request_name, text, response, "Success")
            return response
        except Exception as e:
            self.langfuse_client.log_and_raise_error(
                f"OpenAI Client -> embedding_request: Failed to create embedding: {e}",
                trace_id,
            )

    async def chat_completion_request(self, messages, trace_id=None, request_name="chat_completion_request", **kwargs):
        params = self._build_params(messages, **kwargs)
        if params.get("response_format", None):
            return await self._handle_request(self.async_client.beta.chat.completions.parse, params, trace_id, request_name)
        return await self._handle_request(self.async_client.chat.completions.create, params, trace_id, request_name)

    def _build_params(self, messages, **kwargs):
        default_params = {
            "model": self.config_loader.get("DEFAULT_COMPLETIONS_MODEL"),
            "temperature": 0.2,
        }
        default_params.update(kwargs)
        default_params["messages"] = messages
        return default_params

    async def _handle_request(self, request_func, params, trace_id, request_name):
        try:
            start_time = time.time()
            response = await request_func(**params)
            end_time = time.time()
            output_message = self._extract_output_message(response, params, trace_id)
            usage = response.usage if hasattr(response, "usage") else None
            output_message.generation_trace = self.langfuse_client.log_generation_trace(trace_id, request_name, params, output_message, "Success", usage, start_time, end_time)
            return output_message
        except Exception as e:
            self.langfuse_client.log_and_raise_error(
                f"OpenAI Client -> _handle_request: {request_name}: An error occurred: {e}",
                trace_id,
            )

    def _extract_output_message(self, response, params, trace_id=None):
        try:
            if params.get("stream", False):
                response, is_tool_call = self.process_streaming_responses(response, params)
                if is_tool_call:
                    return ChatCompletionsResponseSchema(
                        message=None,
                        response_type=ResponseType.TOOL_CALL,
                        tool_calls=response,
                        structured_output=None,
                        streaming_response=None
                    )
                else:
                    return ChatCompletionsResponseSchema(
                        message=response if not is_tool_call else None,
                        streaming_response=response if is_tool_call else None,
                        response_type=ResponseType.STREAMING_RESPONSE if is_tool_call else ResponseType.TEXT,
                        tool_calls=response if is_tool_call else None,
                        structured_output=None
                    )
            elif params.get("response_format", None):
                response_schema = ChatCompletionsResponseSchema(
                    message=response.choices[0].message.content,
                    response_type=ResponseType.STRUCTURED_OUTPUT,
                    tool_calls=response.choices[0].message.tool_calls,
                    structured_output=response.choices[0].message.parsed,
                    streaming_response=None
                )
                return response_schema
            else:
                is_tool_call = False
                if response.choices[0].finish_reason == "stop":
                    response_message = response.choices[0].message.content
                    return ChatCompletionsResponseSchema(
                        message=response_message,
                        response_type=ResponseType.TEXT,
                        tool_calls=None,
                        structured_output=None,
                        streaming_response=None
                    )
                elif response.choices[0].finish_reason == "tool_calls":
                    is_tool_call = True
                    tool_calls_info = []
                    for tool_call in response.choices[0].message.tool_calls:
                        tool_calls_info.append(
                            {"function_name": tool_call.function.name, "function_arguments": json.loads(tool_call.function.arguments)}
                        )
                    return ChatCompletionsResponseSchema(
                        message=None,
                        response_type=ResponseType.TOOL_CALL,
                        tool_calls=tool_calls_info,
                        structured_output=None,
                        streaming_response=None
                    )
                return None
        except Exception as e:
            self.langfuse_client.log_and_raise_error(
                f"OpenAI Client -> _extract_output_message: Failed to extract output message: {e}",
                trace_id,
            )

    def process_streaming_responses(self, response, params):
        tool_calls_info = []
        current_tool_call_arguments = ""
        current_index = -1
        is_tool_call = False

        for response_chunk in response:
            choice = response_chunk.choices[0]
            delta = choice.delta

            if delta.content is not None:
                return response, is_tool_call
            else:
                is_tool_call = True

            if delta.tool_calls:
                tool_call = delta.tool_calls[0]
                tool_call_index = tool_call.index
                tool_call_name = tool_call.function.name
                tool_call_arguments = tool_call.function.arguments

                if tool_call_index > current_index:
                    if current_index >= 0:
                        tool_calls_info.append(
                            {"function_name": function_name, "function_arguments": json.loads(current_tool_call_arguments)}
                        )
                        current_tool_call_arguments = ""

                    current_index = tool_call_index
                    function_name = tool_call_name

                current_tool_call_arguments += tool_call_arguments

        if current_index >= 0:
            tool_calls_info.append({"function_name": function_name, "function_arguments": json.loads(current_tool_call_arguments)})
        return tool_calls_info, is_tool_call