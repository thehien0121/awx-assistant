import os
from agents import Agent
from pydantic import BaseModel, Field
from agents.tool import WebSearchTool


# Import the function tools from the updated awx_mcp.py
from agent_tools.awx_mcp import (
    document_search,
    call_awx_api,
    list_api_paths,
    check_project_manual_path
)

class awx_worker_output(BaseModel):
    """
    Represents the result of a Function calling, containing the result of the function calling and the explanation of the result.
    """
    tool_result: str = Field(
        description="This field only use for the result of the function calling, other information should be in the explanation field."
    )
    result: str = Field(
        description="This field is a nicer, more readable, friendly version of tool_result."
    )
    explanation: str = Field(
        description="A brief, user-friendly explanation of the result of the function calling, or the response to the user question."
    )
    tool_name: str = Field(
        description="The name of the tool that was used to perform the action."
    )
    
# Define the instructions for the AWX worker agent
awx_worker_instructions = """
    You are an AWX worker agent responsible for interacting with the Ansible AWX system through its API (api/v2).
    You do NOT use a separate function for each endpoint. Instead, you operate by leveraging three meta-tools:
    - `list_api_paths`: to discover all available API endpoints and their brief descriptions.
    - `document_search`: to retrieve the official documentation (parameters, allowed methods, schema, examples, etc.) for any given endpoint.
    - `call_awx_api`: to make requests to the selected endpoint, using the appropriate method and parameters as specified in the documentation and as required by the user's request.
    - `check_project_manual_path`: this is only for the project manual path, to check the project manual path.

    Your workflow for every operation is STRICTLY as follows:
    1. **Document**: Use `document_search` to fetch and read the documentation of the intended endpoint(s). Make sure you understand the required/optional parameters, allowed HTTP methods, response formats, and any constraints.
    2. **Pre-request Check**: For endpoints related to projects (/api/v2/projects/), and the scm_type is manual, you MUST:
       - Ask the user to provide the path of the project, and the filename of the project, and the content of the project. If the user not provide it, do not doing anything.
       - Call `check_project_manual_path()` first with appropriate parameters:
       - For POST requests (creating projects): call with type="add", path, filename, and content
       - For DELETE requests (removing projects): call with type="remove" and path.
    3. **Make Request**: Use `call_awx_api` to perform the actual request, with method and parameters precisely matched to both the documentation and the user's intent.

    **Absolutely NEVER skip any step in this process, even if the operation seems simple. Always document your reasoning if you must make a choice between endpoints or parameters.**

    You must return all results in the structured `awx_worker_output` format:
    - result: The raw result from the AWX API.
    - explanation: A user-friendly explanation or summary of what was done and the meaning of the result.
    - tool_name: The name of the tool you used for the action.

    If a request is outside the scope of direct AWX API operations, or if you are unable to find a suitable endpoint, escalate to the leader agent for further handling.

    Always ensure safe, secure, and accurate execution of all tasks.
"""

# Create the AWX worker agent instance
awx_worker_agent = Agent(
    name="AWX Worker Agent",
    instructions=awx_worker_instructions,
    output_type=awx_worker_output,
    model=os.getenv("AI_MODEL"),
    handoff_description="Use this agent when the user wants to perform operations on AWX.",
    tools=[
        # Special tool for read the documentation of the AWX API
        document_search,
        list_api_paths,
        call_awx_api,
        check_project_manual_path
    ]
)
