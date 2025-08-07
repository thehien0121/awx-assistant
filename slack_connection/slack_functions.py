import os
import asyncio
import json
import requests
from requests.auth import HTTPBasicAuth
import redis
from fastapi import Request
from conversations.conversation import redis_client, get_history, save_history

# ==========================================================
# --- Background Slack Response Function ---
# ==========================================================
async def background_slack_response(channel: str, slack_user_id: str, user_message: str, event_type: str, the_leader_agent):
    """
    Background function to process Slack message and send response.
    """
    # Check if user from slack has been provided awx_user_id
    awx_user_id = get_user_id_from_slack_id(slack_user_id)
    if awx_user_id != False:
        try:
            # Get history from Redis
            history = get_history(awx_user_id)
            
            # Embed user_id in the message content for agent to extract
            enhanced_message = f"[USER_ID: {awx_user_id}] {user_message}"
            
            prompt_input = history.copy()
            prompt_input.append({"role": "user", "content": enhanced_message})
            
            print(f"[API] Executing agent: {the_leader_agent.name}")
            from agents import Runner
            result = await Runner.run(the_leader_agent, prompt_input, max_turns=40)
            
            if result.final_output:
                final_data = result.final_output.model_dump()
                print(f"[API] Agent responsed with final output.")
                
                assistant_result = getattr(result.final_output, 'result', '')
                assistant_explanation = getattr(result.final_output, 'explanation', '')
                assistant_tool_name = getattr(result.final_output, 'tool_name', '')
                
                if assistant_explanation:
                    assistant_message = {"role": "assistant", "content": assistant_explanation, "tool_result": assistant_result, "tool_name": assistant_tool_name}
                    # Save original user message without [USER_ID: xxx] prefix
                    updated_history = history + [{"role": "user", "content": user_message}, assistant_message]
                    save_history(awx_user_id, updated_history)
                    print("[API]   - Conversation history saved to Redis.")
                slack_response = assistant_explanation + "\n\n" + assistant_result or "Task completed"
                if event_type == "app_mention":
                    slack_response = f"Hi <@{slack_user_id}>, {slack_response}"
                await send_reply(channel, slack_response)
            else:
                await send_reply(channel, "No response generated")
        except Exception as e:
            print(f"[API] [ERROR] Background task failed: {e}")
            await send_reply(channel, "Sorry, an error occurred while processing your request.")
    else:
        await send_reply(channel, "", button=True, tagName=slack_user_id)

# ==========================================================
# --- Slack reply to user ---
# ==========================================================
async def send_reply(channel, text, button: bool = False, tagName: str = ""):
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN')}",
        "Content-Type": "application/json; charset=utf-8"
    }
    if button:
        login_button_block = [
           {
                "type": "section",
                "text": {
                    "type": "mrkdwn", 
                    "text": f"<@{tagName}> Please login your LDAP account to continue."
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "open_login_modal",    # callback_id cho action
                        "text": {"type": "plain_text", "text": "Login"},
                        "value": "login_request"
                    }
                ]
            }
        ]
        payload = {
            "channel": channel,
            "blocks": login_button_block,
            "text": f"<@{tagName}> Please login your LDAP account to continue."  # fallback text
        }
    else:
        payload = {
            "channel": channel,
            "text": text,
            # "thread_ts": event_ts,  # Nếu muốn trả lời vào thread
        }
    response = requests.post(url, headers=headers, json=payload)
    return {'ok': True}

# ==========================================================
# --- Check LDAP user from Redis ---
# ==========================================================
def get_user_id_from_slack_id(slack_user_id: str) -> str:
    """
    Get the real user id from Slack user id
    """
    if redis_client is None:
        print("Redis not available, returning empty history")
        return False
    redis_slack_key = f"slack_user_{slack_user_id}"
    user_data = redis_client.get(redis_slack_key)
    if user_data is None:
        return False
    user_data = json.loads(user_data)
    user_id = user_data.get("awx_user_id", "")
    if user_id == "":
        return False
    return user_id

# ==========================================================
# --- Get user info from LDAP ---
# This function use to login with LDAP user via API and save the user_id to Redis
# ==========================================================
async def login_ldap_from_slack(data: dict):
    """
    Get user info from LDAP and save the user_id to Redis
    """
    try:
        username = data["view"]["state"]["values"]["username_block"]["username_input"]["value"]
        password = data["view"]["state"]["values"]["password_block"]["password_input"]["value"]
        slack_user_id = data["user"]["id"]
        channel_id = data["view"]["private_metadata"]
        try:
            awx_host = os.getenv("ANSIBLE_BASE_URL")

            url = f"{awx_host}/api/v2/me/"
            response = requests.get(url, auth=HTTPBasicAuth(username, password), verify=False)

            if response.status_code == 200:
                info = response.json()
                redis_client.set(f"slack_user_{slack_user_id}", json.dumps({"awx_user_id": info["results"][0]["id"]}))
                await send_reply(channel_id, f"Login with LDAP success, now you can use AWX assistant.")
            else:
                await send_reply(channel_id, f"Login with LDAP failed, please try again.")
                print("login_ldap_from_slack() API call failed, status code: ", response.status_code, " - response: ", response.text)
        except Exception as e:
            print(f"Error parsing request JSON in login_ldap_from_slack(): {e} \n data: {data}")
            data = {}
    except Exception as e:
        print(f"Error parsing request JSON in login_ldap_from_slack(): {e} \n data: {data}")
        data = {}
    
    


# ==========================================================
# --- Open login modal ---
# ==========================================================
def open_login_modal(trigger_id, channel_id):
    url = "https://slack.com/api/views.open"
    headers = {
        "Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN')}",
        "Content-Type": "application/json"
    }
    modal_view = {
        "type": "modal",
        "callback_id": "login_form",
        "title": {"type": "plain_text", "text": "Login to AWX"},
        "submit": {"type": "plain_text", "text": "Login"},
        "private_metadata": channel_id,
        "blocks": [
            {
                "type": "input",
                "block_id": "username_block",
                "element": {"type": "plain_text_input", "action_id": "username_input"},
                "label": {"type": "plain_text", "text": "Username"}
            },
            {
                "type": "input",
                "block_id": "password_block",
                "element": {"type": "plain_text_input", "action_id": "password_input"},
                "label": {"type": "plain_text", "text": "Password"}
            }
        ]
    }
    payload = {
        "trigger_id": trigger_id,
        "view": modal_view,
    }
    requests.post(url, headers=headers, json=payload)