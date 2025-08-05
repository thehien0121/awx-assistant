import os
import uvicorn
import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List
from pydantic import BaseModel, Field
# Necessary import for checking the type of streaming event data
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
import traceback  # Import traceback for detailed error logging
from contextlib import asynccontextmanager
import logfire
import redis
import json

# --- Load Environment Variables ---
dotenv_file = Path(__file__).parent / ".env"
print("DEBUG load_dotenv file:", dotenv_file)
load_dotenv(dotenv_file)

# --- Redis Client Initialization ---
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT", 6379)),      # ép int và default nếu thiếu
    db=int(os.getenv("REDIS_DB", 0)),             # ép int và default nếu thiếu
    password=os.getenv("REDIS_PASSWORD")
)

# --- SDK Configuration for Non-OpenAI Providers ---
from agents import (
    Agent,
    Runner,
    InputGuardrailTripwireTriggered,
    set_tracing_disabled, 
    set_default_openai_api,
    set_default_openai_client   
)
try:
    from openai import AsyncAzureOpenAI
    client = AsyncAzureOpenAI(
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    )
    set_default_openai_client(client, use_for_tracing=False)
    print("AZURE OpenAI client set up successfully")
except Exception as e:
    print(f"Error setting up AZURE OpenAI client: {e}")
    raise e

set_tracing_disabled(True)
set_default_openai_api("chat_completions")


# --- Import Specialist Agents & Data Models ---
# --- Import Guardrails ---
from sub_agents.chat_guardrails import security_request_guardrail
from sub_agents.chat_agent import chat_agent
from sub_agents.awx_worker import awx_worker_agent
from sub_agents.awx_github_worker import awx_github_agent, connect_github_server

# Global variable for leader agent
the_leader_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global the_leader_agent
    
    # This code runs on startup.
    logfire.configure(environment=os.getenv("LOGFIRE_ENVIRONMENT", "local"))
    logfire.instrument_fastapi(app)
    logfire.instrument_openai_agents()
    logfire.instrument_openai()

    print("--- Logfire configured and instrumented for FastAPI and Agents ---")
    
    # Connect GitHub server
    await connect_github_server()
    
    # Initialize leader agent
    the_leader_agent = Agent(
        name="The leader",
        instructions=the_leader_instructions,
        handoffs=[chat_agent, awx_worker_agent, awx_github_agent],
        model=os.getenv("AI_MODEL"),
        # Attach the input guardrail here. It will run before the agent's logic.
        # input_guardrails=[security_request_guardrail],
        output_type=leader_output,
    )
    
    yield
    # This code runs on shutdown.
    print("--- Flushing logs before shutdown ---")
    logfire.force_flush()

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Design Agents WebSocket API",
    description="A real-time API for interacting with design agents via WebSockets.",
    version="2.0.0", # Version bump for new architecture
    lifespan=lifespan # Use the lifespan context manager
)

# --- Define the Project Manager Agent ---
# This agent's job is to receive user request and delegate it to the correct specialist or direct answer to the user.
class leader_output(BaseModel):
    """
    Represents the result of a chat, containing the answer to the question.
    """
    explanation: str = Field(
        description="A brief, user-friendly explanation of the question user asked."
    )

class ChatRequest(BaseModel):
    """
    Request model for POST /api/chat endpoint
    """
    user_id: str = Field(description="User ID for the chat session")
    content: str = Field(description="User message content")
    request_type: str = Field(default="awx-chat", description="Type of request")

the_leader_instructions = f"""
You are the primary orchestrator agent in an AI-powered AWX support system. Your role is to act as the main point of contact for user requests.
Carefully analyze each user request, determine the required expertise or action, and delegate the task to the most appropriate sub-agent in the system.
- If the request involves technical explanation or general Ansible/system knowledge, hand it off to the chat_agent.
- If the request requires executing actions on AWX via API tools, assign it to the awx_worker agent.
- If the request requires executing actions on GitHub, assign it to the awx_github_agent.

**Before handing off any execution task to the awx_worker or awx_github_agent, you must:**
***For tasks that do not modify data (read-only operations):***
- You may execute the task immediately without requiring user confirmation.
- Examples: retrieving job lists, reading configurations, querying status, etc.

***For tasks that modify data (write operations):***
- Request the user to provide all required information for the operation (such as name, ID, parameters, or details of the changes).
- Once all necessary information is collected, generate a concise, step-by-step summary of the planned actions (including which AWX API endpoints will be called, what resources will be affected, and the expected results).
- Present this summary to the user and request their explicit confirmation before proceeding.
- Only after the user confirms, you may hand off the execution to the awx_worker agent.
- If the user asks for clarification or changes, update the plan and repeat the confirmation process.

Always ensure that the user receives a clear and concise answer or result. Coordinate between agents as necessary, and maintain the flow of conversation or task completion.

### IMPORTANT:
1. Your final output must be the answer to the question, wrapped in a structured `leader_output` format.
2. You are prefer to delegate the task to the sub-agent, but if the task is simple and you think you can handle it yourself, you can directly answer the user, but in most case, you should delegate the task to the sub-agent.

"""


def get_history(user_id: str, all_fields: bool = False) -> List[Dict]:
    """
    Get the saved history of the conversation for a given user and project from Redis.
    If the history contains more than 20 items, only the last 20 are returned.
    """
    if redis_client is None:
        print("Redis not available, returning empty history")
        return []
        
    redis_key = f"awx_chat_{user_id}"
    try:
        user_data = redis_client.get(redis_key)
        if user_data is None:
            return []
        user_data = json.loads(user_data)
        if not isinstance(user_data, list):
            return []
        if all_fields:
            return user_data[-20:]
        else:
            result = []
            for item in user_data:
                result.append({
                    "role": item["role"],
                    "content": item["content"]
                })
            return result[-20:]
    except (redis.RedisError, json.JSONDecodeError) as e:
        print(f"Error getting history from Redis: {e}")
    return []

def save_history(user_id: str, new_history: List[Dict]):
    """
    Save the updated conversation history back to Redis.
    """
    if redis_client is None:
        print("Redis not available, skipping history save")
        return
        
    redis_key = f"awx_chat_{user_id}"
    try:
        # Start a transaction
        with redis_client.pipeline() as pipe:
            # Watch the key for changes
            pipe.watch(redis_key)
            # Get current data
            user_data = pipe.get(redis_key)
            user_data = json.loads(user_data) if user_data else {}
            # Update the history for the specific project
            user_data = new_history
            # Start MULTI block
            pipe.multi()
            # Set the new value
            pipe.set(redis_key, json.dumps(user_data))
            # Execute the transaction
            pipe.execute()
    except redis.WatchError:
        # Handle the case where the key was modified by another client
        print(f"WatchError: chat_{user_id} was modified, retrying transaction...")
        save_history(user_id, new_history) # Simple retry
    except (redis.RedisError, json.JSONDecodeError) as e:
        print(f"Error saving history to Redis: {e}")


# ==========================================================
# --- WebSocket Connection Management ---
# This dictionary will hold active connections, allowing us to manage them if needed.
# ==========================================================
active_connections: Dict[str, WebSocket] = {}
socket_request_type = {
    "chat": "awx-chat",
    "chat_token": "awx-chat-token",
    "chat_history": "conversation-history",
    "error": "error",
}
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    This is the main WebSocket endpoint for handling all real-time chat interactions.
    It maintains a stateful connection for each user/project session.
    It acts as a dispatcher, routing requests to the appropriate handler based on the 'request_type' parameter.
    """
    connection_id = f"{user_id}"
    await websocket.accept()
    active_connections[connection_id] = websocket
    print(f"WebSocket connection established for: {connection_id}")

    try:
        while True:
            # 1. Wait for a new message from the client and determine the target request_type.
            print("\n" + "="*50)
            print("[WORKFLOW] Waiting for message from client...")
            data = await websocket.receive_json()
            # Inject user/project ids for the handlers to use
            data['user_id'] = user_id
            # print(f"[WORKFLOW] Received data: {data}")

            request_type = data.get("request_type", socket_request_type["chat"])

            # 2. Get history from Redis. This is now the source of truth for conversation state.
            history = get_history(user_id)
            # 3. Dispatch the request to the correct handler based on the request_type.
            if request_type == socket_request_type["chat_history"]:
                print(f"[WORKFLOW] Sending conversation history to client")
                await websocket.send_json({"request_type": socket_request_type["chat_history"], "content": history})
            elif request_type == socket_request_type["chat"]: 
                await handle_awx_chat(websocket, data, history)
            else:
                # Placeholder for other request_types you will add.
                print(f"[WORKFLOW] [ERROR] Unknown request_type: '{request_type}'")
                await websocket.send_json({"request_type": socket_request_type["error"], "content": f"Unknown request_type received: {request_type}"})
                continue # Wait for the next message

    except WebSocketDisconnect:
        print(f"WebSocket connection closed for: {connection_id}")
    except Exception as e:
        print(f"!!! [ERROR] An unexpected error occurred for {connection_id}: {e}")
        traceback.print_exc()
        await websocket.send_json({"request_type": socket_request_type["error"], "content": str(e)})
    finally:
        if connection_id in active_connections:
            del active_connections[connection_id]


# ==========================================================
# AWX Chat Module Handler
# ==========================================================
async def handle_awx_chat(websocket: WebSocket, data: Dict, history: List[Dict]):
    """
    Handle the AWX chat module.
    """
    try:
        user_id = data.get("user_id", "")
        user_message = data.get("content", "")
        
        # Embed user_id in the message content for agent to extract
        enhanced_message = f"[USER_ID: {user_id}] {user_message}"
        
        prompt_input = history.copy()
        prompt_input.append({"role": "user", "content": enhanced_message})
        
        print(f"[WORKFLOW] Executing agent: {the_leader_agent.name}")
        stream = Runner.run_streamed(the_leader_agent, prompt_input, max_turns=40)
        final_text_content = ""
        async for event in stream.stream_events():
            if event.type == "raw_response_event" and hasattr(event.data, 'delta'):
                token = event.data.delta or ""
                final_text_content += token
                await websocket.send_json({"request_type": socket_request_type["chat_token"], "content": token})
            elif event.type == "tool_call_created":
                await websocket.send_json({
                    "request_type": socket_request_type["chat"], 
                    "content": f"I will use the `{event.data.name}` tool to perform your request, please wait for the result"
                })
            # elif event.type == "tool_call_result_created":
            #     # Có thể xử lý kết quả tool nếu cần
            #     pass
        print("[WORKFLOW]   - Streaming complete.")

        if stream.final_output:
            final_data = stream.final_output.model_dump()
            print(f"[WORKFLOW] Agent produced final output.")
            print(f"[WORKFLOW]   - Last agent run: {stream.last_agent.name}")
            print(f"[WORKFLOW]   - Output data type: {type(stream.final_output).__name__}")
            assistant_result = getattr(stream.final_output, 'result', '')
            assistant_explanation = getattr(stream.final_output, 'explanation', '')
            assistant_tool_name = getattr(stream.final_output, 'tool_name', '')
            if assistant_explanation:
                assistant_message = {"role": "assistant", "content": assistant_explanation, "tool_result": assistant_result, "tool_name": assistant_tool_name}
                # Save original user message without [USER_ID: xxx] prefix
                updated_history = history + [{"role": "user", "content": user_message}, assistant_message]
                save_history(user_id, updated_history)
                print("[WORKFLOW]   - Conversation history saved to Redis.")
        print("[WORKFLOW]   - Sending final 'awx-chat' payload.")
        await websocket.send_json({"request_type": socket_request_type["chat"], "content": final_data})
    except InputGuardrailTripwireTriggered as e:
        # This block catches the exception when our ui_request_guardrail triggers the tripwire.
        # This failed turn is NOT saved to history.
        
        # Safely get the reasoning from the guardrail's output.
        reasoning = "No specific reason provided."
        if (hasattr(e, 'guardrail_result') and e.guardrail_result and
            hasattr(e.guardrail_result, 'output') and e.guardrail_result.output and
            hasattr(e.guardrail_result.output, 'output_info') and e.guardrail_result.output.output_info and
            hasattr(e.guardrail_result.output.output_info, 'reasoning')):
            reasoning = e.guardrail_result.output.output_info.reasoning
        
        print(f"[WORKFLOW] [GUARDRAIL] Request blocked. Reason: {reasoning}")
        # Inform the client that the request was blocked, including the reason.
        await websocket.send_json({
            "request_type": socket_request_type["chat"],
            "content": {"explanation": "I am here to help you with Ansible AWX so right now I can't help you with that."}
        })
        # Save original user message without [USER_ID: xxx] prefix
        updated_history = history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": "I am here to help you with Ansible AWX so right now I can't help you with that."}]
        save_history(user_id, updated_history)
        # This turn failed, so we don't return anything or modify history.
        return




# ==========================================================
# --- HTTP POST Chat Endpoint ---
# ==========================================================
@app.post("/api/chat")
async def api_chat(request: ChatRequest):
    """
    HTTP POST endpoint with same functionality as WebSocket chat.
    Accepts same parameters as WebSocket but returns JSON response instead of streaming.
    """
    try:
        if request.get('type') == 'url_verification':
            return {'challenge': request.get('challenge')}
        user_id = request.user_id
        user_message = request.content
        
        # Get history from Redis
        history = get_history(user_id)
        
        # Embed user_id in the message content for agent to extract
        enhanced_message = f"[USER_ID: {user_id}] {user_message}"
        
        prompt_input = history.copy()
        prompt_input.append({"role": "user", "content": enhanced_message})
        
        print(f"[API] Executing agent: {the_leader_agent.name}")
        result = await Runner.run(the_leader_agent, prompt_input, max_turns=40)
        
        print("[API]   - Processing complete.")
        
        if result.final_output:
            final_data = result.final_output.model_dump()
            print(f"[API] Agent produced final output.")
            print(f"[API]   - Last agent run: {result.last_agent.name}")
            print(f"[API]   - Output data type: {type(result.final_output).__name__}")
            
            assistant_result = getattr(result.final_output, 'result', '')
            assistant_explanation = getattr(result.final_output, 'explanation', '')
            assistant_tool_name = getattr(result.final_output, 'tool_name', '')
            
            if assistant_explanation:
                assistant_message = {"role": "assistant", "content": assistant_explanation, "tool_result": assistant_result, "tool_name": assistant_tool_name}
                # Save original user message without [USER_ID: xxx] prefix
                updated_history = history + [{"role": "user", "content": user_message}, assistant_message]
                save_history(user_id, updated_history)
                print("[API]   - Conversation history saved to Redis.")
            
            return {
                "status": "success",
                "user_id": user_id,
                "response": final_data,
                "message": assistant_explanation or "Task completed"
            }
        else:
            return {
                "status": "error", 
                "user_id": user_id,
                "message": "No response generated"
            }
            
    except InputGuardrailTripwireTriggered as e:
        # Handle guardrail blocks same as WebSocket
        reasoning = "No specific reason provided."
        if (hasattr(e, 'guardrail_result') and e.guardrail_result and
            hasattr(e.guardrail_result, 'output') and e.guardrail_result.output and
            hasattr(e.guardrail_result.output, 'output_info') and e.guardrail_result.output.output_info and
            hasattr(e.guardrail_result.output.output_info, 'reasoning')):
            reasoning = e.guardrail_result.output.output_info.reasoning
        
        print(f"[API] [GUARDRAIL] Request blocked. Reason: {reasoning}")
        
        # Save blocked interaction to history
        updated_history = history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": "I am here to help you with Ansible AWX so right now I can't help you with that."}]
        save_history(user_id, updated_history)
        
        return {
            "status": "blocked",
            "user_id": user_id,
            "message": "I am here to help you with Ansible AWX so right now I can't help you with that.",
            "reason": reasoning
        }
        
    except Exception as e:
        print(f"[API] [ERROR] An unexpected error occurred: {e}")
        return {
            "status": "error",
            "user_id": user_id, 
            "message": f"An error occurred: {str(e)}"
        }

# ==========================================================
# --- Health Check Endpoint ---
# ==========================================================
@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify server status and dependencies.
    """
    try:
        # Check Redis connection
        redis_status = "healthy"
        if redis_client is None:
            redis_status = "not available"
        else:
            try:
                redis_client.ping()
            except Exception as e:
                redis_status = f"unhealthy: {str(e)}"
        
        # Check active WebSocket connections
        active_ws_count = len(active_connections)
        
        return {
            "status": "healthy",
            "timestamp": str(datetime.datetime.now()),
            "version": "2.0.0",
            "services": {
                "redis": redis_status,
                "websocket_connections": active_ws_count
            },
            "uptime": "running"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": str(datetime.datetime.now()),
            "error": str(e)
        }


# --- Uvicorn Server Runner ---
# This block allows you to run the server directly with `python main.py`
if __name__ == "__main__":
    port = int(os.getenv("MAIN_PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)