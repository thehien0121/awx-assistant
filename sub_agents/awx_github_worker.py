import os
from agents import Agent, mcp, function_tool
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict

load_dotenv(Path(__file__).parent.parent / ".env")
# 1. Khai báo MCP Server nếu được enable
mcp_servers = []
if os.getenv("ENABLE_GITHUB_MCP", "false").lower() == "true":
    github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if github_token:
        # Tạo tool filter để giới hạn quyền
        tool_filter = mcp.create_static_tool_filter(
            blocked_tool_names=["delete_repository", "create_repository", "delete_file", "switch_branch"]
        )

        # Gom các tham số kết nối vào một dictionary - GitHub Copilot MCP endpoint
        params = {
            "url": "https://api.githubcopilot.com/mcp/",  # Thêm trailing slash
            "headers": {
                "Authorization": f"Bearer {github_token}",  # GitHub Copilot API format
                "Content-Type": "application/json",
                "User-Agent": "AWX-Assistant",
                # "Accept": "application/vnd.github+json",
                # "X-GitHub-Api-Version": "2022-11-28"
            },
            "timeout": 30.0  # Tăng timeout lên 30 giây
        }

        # Khai báo server và truyền dict `params` vào
        github_mcp_server = mcp.server.MCPServerStreamableHttp(
            params=params,
            # tool_filter=tool_filter,  # Enabled tool filter để giới hạn quyền
            cache_tools_list=True  # Cache để tăng tốc
        )
        mcp_servers.append(github_mcp_server)
        print("✅ GitHub Copilot MCP integration configured for GitHub worker.")
    else:
        print("⚠️  ENABLE_GITHUB_MCP is true, but GITHUB_PERSONAL_ACCESS_TOKEN is not set for the GitHub worker.")

async def connect_github_server():
    """Connect GitHub MCP server"""
    for server in mcp_servers:
        await server.connect()

# 2. Định nghĩa Pydantic output model
class github_worker_output(BaseModel):
    """
    Represents the result of a GitHub operation, containing the result and an explanation.
    """
    result: str = Field(description="The raw result from the GitHub API call.")
    explanation: str = Field(description="A user-friendly explanation of the result.")
    tool_name: str = Field(description="The name of the GitHub tool used.")

# 3. Function để tạo repository config dựa trên user_id
def get_user_repository_config(user_id: str = None):
    """Load repository configuration for specific user"""
    # Reload environment variables to get latest values
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
    
    # Build config keys with user_id suffix if provided
    if user_id:
        allowed_repo_key = f"ALLOWED_REPOSITORY_{user_id}"
        allowed_branch_key = f"ALLOWED_BRANCH_{user_id}"
        repo_url_key = f"REPOSITORY_URL_{user_id}"
        repo_ref_key = f"REPOSITORY_REF_{user_id}"
        repo_owner_key = f"REPOSITORY_OWNER_{user_id}"
    else:
        # Fallback to default keys
        allowed_repo_key = "ALLOWED_REPOSITORY"
        allowed_branch_key = "ALLOWED_BRANCH"
        repo_url_key = "REPOSITORY_URL"
        repo_ref_key = "REPOSITORY_REF"
        repo_owner_key = "REPOSITORY_OWNER"
    
    config = {
        'ALLOWED_REPOSITORY': os.getenv(allowed_repo_key, os.getenv("ALLOWED_REPOSITORY")),
        'ALLOWED_BRANCH': os.getenv(allowed_branch_key, os.getenv("ALLOWED_BRANCH")),
        'REPOSITORY_URL': os.getenv(repo_url_key, os.getenv("REPOSITORY_URL")),
        'REPOSITORY_REF': os.getenv(repo_ref_key, os.getenv("REPOSITORY_REF")),
        'REPOSITORY_OWNER': os.getenv(repo_owner_key, os.getenv("REPOSITORY_OWNER"))
    }
    
    print(f"🔧 GitHub Config for user '{user_id}':")
    print(f"   - Repository: {config['REPOSITORY_OWNER']}/{config['ALLOWED_REPOSITORY']}")
    print(f"   - Branch: {config['ALLOWED_BRANCH']}")
    print(f"   - URL: {config['REPOSITORY_URL']}")
    
    return config

# Tool function for agent to load user config
@function_tool
def load_user_github_config(user_id: str) -> Dict:
    """
    Load GitHub repository configuration for a specific user.
    This function is available as a tool for the GitHub worker agent.
    
    Args:
        user_id: The user ID to load configuration for
        
    Returns:
        Dict containing repository configuration for the user
    """
    return get_user_repository_config(user_id)

# 4. Instructions cho agent - sẽ load config dynamic
github_worker_instructions = """
You are a specialized GitHub worker agent with RESTRICTED ACCESS. You ALWAYS operate exclusively on a single, pre-defined GitHub repository and branch.

IMPORTANT: Before performing any GitHub operations, you must:
1. Extract the user_id from the message content (look for "[USER_ID: xxx]" pattern at the beginning of user messages)
2. Use the load_user_github_config tool with that user_id to get the repository configuration
3. Use that configuration for all subsequent GitHub operations (owner, repo, branch, ref, etc.)

CRITICAL RESTRICTIONS:
- You are STRICTLY LIMITED to working on the single branch specified in the user's configuration
- You MUST NOT switch branches or work on any other branch
- If user requests to switch branch, checkout another branch, or work on different branch, REFUSE and explain that you can only work on their designated branch
- All operations must be performed on the configured branch only

## Tool Usage Guidelines:

* When using `get_file_contents`:
  - For root directory: omit the `path` parameter or use empty string
  - For specific files: use the file path (e.g., "README.md", "src/main.py")
  - For directories: use the directory path (e.g., "src", "docs")
  - Always use the correct `ref` based on user's repository configuration
  - If there is no specific file path, use path = "/"
* When using `search_code`: use specific search terms, not broad queries

## Error Handling:

* If a tool call times out (especially search_code), explain the timeout and suggest trying again with more specific search terms.
* For API rate limiting errors, explain the limitation and suggest waiting before retrying.
* If GitHub API is unavailable, provide a clear explanation of the service status.
* For 404 errors, check if the repository is private and token has correct permissions.
* Always include the specific error details in your response for debugging purposes.

## Repository Configuration:

You must dynamically load repository configuration based on the user_id from the conversation context.
Use the load_user_github_config tool to get the appropriate configuration for each user.

Example workflow:
1. User message: "[USER_ID: john] hiện tôi đang ở branch nào?" → extract user_id="john"
2. Call load_user_github_config(user_id="john") → get config  
3. Use returned config for GitHub operations (owner, repo, ref, etc.)
4. Answer user's question using the correct repository/branch information

Example of REFUSING branch switch requests:
- User: "switch to main branch" → Answer: "I can only work on your designated branch: [user's configured branch]. I cannot switch branches."
- User: "checkout develop branch" → Answer: "Access denied. I am restricted to working on branch: [user's configured branch] only."
- User: "create branch feature/new" → Answer: "I cannot create or switch branches. All operations must be performed on your configured branch: [user's configured branch]."
"""

# 5. Tạo Agent
awx_github_agent = Agent(
    name="GitHub Worker Agent",
    instructions=github_worker_instructions,
    output_type=github_worker_output,
    model=os.getenv("AI_MODEL"),
    handoff_description="Use this agent for all operations related to GitHub, such as managing repositories, issues, pull requests, and searching code.",
    mcp_servers=mcp_servers,
    tools=[load_user_github_config]  # Thêm custom tool để load config
)

print(f"Agent '{awx_github_agent.name}' initialized with {len(mcp_servers)} MCP server(s).")