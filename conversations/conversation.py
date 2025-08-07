import redis
import json
import os
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()
# --- Redis Client Initialization ---
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    password=os.getenv("REDIS_PASSWORD")
)

def get_history(user_id: str, all_fields: bool = False):
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

def save_history(user_id: str, new_history):
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