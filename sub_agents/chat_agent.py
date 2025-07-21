import os
from agents import Agent
from pydantic import BaseModel, Field

class chat_output(BaseModel):
    """
    Represents the result of a chat, containing the answer to the question.
    """
    explanation: str = Field(
        description="A brief, user-friendly explanation of the question user asked."
    )
    
# 1. Define the instructions for the new agent.
# It's crucial to tell the agent to use the tools available to it.
chat_agent_instructions = """
You are an expert assistant specializing in Ansible, AWX, and related system operations. Your role is to provide accurate, clear, and user-friendly explanations or advice regarding Ansible concepts, AWX workflows, configuration, troubleshooting, and best practices. 
When handed a user question by the leader agent, analyze it carefully and respond in a way that educates and supports the user, regardless of their technical level. 
If the user's question requires performing actions or retrieving specific information from the AWX system, escalate the task back to the leader agent for further handling.
### IMPORTANT: Your final output must be the answer to the question, wrapped in a structured `chat_output` format.
"""

# 3. Create the new agent instance.
# We attach the MCP server to this agent via the `mcp_servers` list.
chat_agent = Agent(
    name="Chat Agent",
    instructions=chat_agent_instructions,
    # This agent will output the same format as our main design agent.
    output_type=chat_output,
    model=os.getenv("AI_MODEL"),
    handoff_description="Use this agent when the user just wants to chat with you."
) 