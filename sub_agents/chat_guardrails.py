from pydantic import BaseModel, Field
from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    input_guardrail,
)
import os

# 1. Define the structured output for our guardrail agent.
# This model will hold the result of the UI request check.
class SecurityRequestCheck(BaseModel):
    is_valid_request: bool = Field(
        description="Set to True if the user's request is about creating, modifying, or discussing anything about Ansible and related server knowledge. Otherwise, set to False."
    )
    reasoning: str = Field(
        description="A brief explanation for the decision on whether the request is valid."
    )

# 2. Create the specialized agent that performs the check.
# This agent's only job is to classify the user's instruction.
the_security_agent = Agent(
    name="Request Validator Agent",
    instructions="""
    You are a domain guardrail agent for an AI-powered AWX support system. Your task is to review each user question and determine if it is relevant to Ansible, AWX, DevOps, IT automation, infrastructure management, Linux/Unix system administration, or related technical topics.

    Accept and allow questions about:
    - Your information as an AI agent like tools, functions, etc.
    - Ansible, AWX, Tower, automation, playbooks, inventories, projects, and job templates.
    - System and server configuration, Linux/Unix commands, infrastructure best practices.
    - Technical troubleshooting, scripting, CI/CD, cloud, DevOps pipelines, and related tools.

    Reject or redirect questions that are:
    - Not technical in nature.
    - Unrelated to IT, automation, DevOps, or system administration.
    - About celebrities, sports, entertainment, personal life, or unrelated knowledge.

    For rejected questions, politely inform the user that the assistant only supports technical topics related to Ansible, AWX, and system operations.
    """,
    output_type=SecurityRequestCheck,
    model=os.getenv("AI_MODEL"),
)

# 3. Implement the guardrail function.
# This function is decorated with @input_guardrail and will be attached to our main agent.
@input_guardrail
async def security_request_guardrail(
    ctx: RunContextWrapper[None], agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    """
    This guardrail checks if a user's request is related to Ansible and related server knowledge.
    """
    conversation_message = ""
    if isinstance(input, list) and input and isinstance(input[-2], dict):
        conversation_message += "Bot: " + input[-2].get("content", "") + "\n"
    # The input from our main.py is a list containing a single dictionary.
    if isinstance(input, list) and input and isinstance(input[-1], dict):
        conversation_message += "User: " + input[-1].get("content", "")
    # Run the checker agent on the user's full instruction.
    result = await Runner.run(the_security_agent, conversation_message, context=ctx.context)
    check_result = result.final_output_as(SecurityRequestCheck)
    
    # Log the guardrail check result
    print(f"[GUARDRAIL] Request check result: valid={check_result.is_valid_request}, reason={check_result.reasoning}")

    # The "tripwire" is triggered if the request is NOT valid.
    # This will stop the main agent from running and raise an exception.
    tripwire_triggered = not check_result.is_valid_request

    return GuardrailFunctionOutput(
        output_info=check_result,
        tripwire_triggered=tripwire_triggered,
    )