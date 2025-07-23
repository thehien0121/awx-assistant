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

    **Very important:**  
    - If the user's message does not explicitly mention AWX/Ansible or technical terms, but is part of an ongoing technical conversation (e.g., follow-up questions, clarifications, requests for more detail), you must allow it as valid.  
    - Examples: "thông tin đâu?", "còn nữa không?", "show more", "tiếp tục đi", "what else?", etc. – these are valid if they follow a technical question or answer about AWX/Ansible.

    Reject or redirect questions that are:
    - Not technical in nature.
    - Unrelated to IT, automation, DevOps, or system administration.
    - About celebrities, sports, entertainment, personal life, or unrelated knowledge.

    For rejected questions, politely inform the user that the assistant only supports technical topics related to Ansible, AWX, and system operations.
    
    Example valid sequences:
    User: Cho tôi xem thông tin job template
    Assistant: Dưới đây là thông tin...
    User: thông tin đâu?
    => This follow-up is valid because it follows a technical conversation.

    Example invalid:
    User: Bạn thích ăn gì?
    => This is invalid.
    """,
    output_type=SecurityRequestCheck,
    model=os.getenv("AI_MODEL"),
)

def build_context(messages, n=4):
    if len(messages) < n:
        n = len(messages)
    # Get the last n messages (or all if less than n)
    selected = messages[-n:]
    chat = ""
    for m in selected:
        if m["role"] == "user":
            chat += f"User: {m['content']}\n"
        else:
            chat += f"Assistant: {m['content']}\n"
    return chat.strip()


# 3. Implement the guardrail function.
# This function is decorated with @input_guardrail and will be attached to our main agent.
@input_guardrail
async def security_request_guardrail(
    ctx: RunContextWrapper[None], agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    """
    Guardrail checks context, not just last message.
    """
    # If input is a list of messages (OpenAI/chatgpt format)
    if isinstance(input, list) and all(isinstance(m, dict) and "role" in m for m in input):
        # Wrap the list of messages into a conversation format, get the last 4-6 messages
        conversation_message = build_context(input, n=6)
    else:
        # If input is a string, send it as is
        conversation_message = str(input)
        if not conversation_message.strip():
            conversation_message = "User: Hello"
    
    # Run guardrail agent on the entire conversation
    result = await Runner.run(the_security_agent, conversation_message, context=ctx.context)
    check_result = result.final_output_as(SecurityRequestCheck)

    print(f"[GUARDRAIL] Request check result: valid={check_result.is_valid_request}, reason={check_result.reasoning}")

    tripwire_triggered = not check_result.is_valid_request
    return GuardrailFunctionOutput(
        output_info=check_result,
        tripwire_triggered=tripwire_triggered,
    )
