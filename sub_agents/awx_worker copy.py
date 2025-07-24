import os
from agents import Agent
from pydantic import BaseModel, Field
from agents.tool import WebSearchTool


# Import the function tools from the updated awx_mcp.py
from agent_tools.awx_mcp import (
    document_search,
    list_inventories,
    get_inventory,
    create_inventory,
    update_inventory,
    delete_inventory,
    list_hosts,
    create_host,
    get_host,
    update_host,
    delete_host,
    list_job_templates,
    get_job_template,
    create_job_template,
    launch_job,
    list_jobs,
    get_job,
    cancel_job,
    get_job_stdout,
    list_projects,
    get_project,
    create_project,
    list_organizations,
    get_organization,
    create_organization,
    list_credentials,
    get_credential,
    create_credential,
    update_credential,
    list_users,
    get_user,
    get_ansible_version,
    get_dashboard_stats
)

class awx_worker_output(BaseModel):
    """
    Represents the result of a Function calling, containing the result of the function calling and the explanation of the result.
    """
    result: str = Field(
        description="This field only use for the result of the function calling, other information should be in the explanation field."
    )
    explanation: str = Field(
        description="A brief, user-friendly explanation of the result of the function calling, or the response to the user question."
    )
    tool_name: str = Field(
        description="The name of the tool that was used to perform the action."
    )
    
# Define the instructions for the AWX worker agent
awx_worker_instructions = """
You are a technical operations agent specialized in interacting with the Ansible AWX system via its API (api/v2). 
Your primary responsibility is to accurately execute user requests that involve performing operations, retrieving information, or making changes in AWX, as directed by the leader agent. 
Always ensure safe, secure, and efficient execution of tasks, and return structured, actionable results. 
If a user's request is outside the scope of direct AWX operations or requires broader explanation, notify the leader agent so it can be delegated to the appropriate agent.
### IMPORTANT: 
# 1. ALWAYS use the `document_search` tool to read the documentation of the AWX API first - THIS STEP IS VERY IMPORTANT.
# 2. Your final output must be the result and the explanation of the function calling, wrapped in a structured `awx_worker_output` format.
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
        
        # Inventory tools
        list_inventories,
        get_inventory,
        create_inventory,
        update_inventory,
        delete_inventory,
        
        # Host tools
        list_hosts,
        create_host,
        get_host,
        update_host,
        delete_host,
        
        # Job Template tools
        list_job_templates,
        get_job_template,
        create_job_template,
        launch_job,
        
        # Job tools
        list_jobs,
        get_job,
        cancel_job,
        get_job_stdout,
        
        # Project tools
        list_projects,
        get_project,
        create_project,
        
        # Organization tools
        list_organizations,
        get_organization,
        create_organization,
        
        # Credential tools
        list_credentials,
        get_credential,
        create_credential,
        update_credential,
        
        # User tools
        list_users,
        get_user,
        
        # System tools
        get_ansible_version,
        get_dashboard_stats
    ]
) 