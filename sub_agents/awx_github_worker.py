import os
from agents import Agent, mcp
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")
# 1. Khai báo MCP Server nếu được enable
mcp_servers = []
if os.getenv("ENABLE_GITHUB_MCP", "false").lower() == "true":
    github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if github_token:
        # Tạo tool filter để giới hạn quyền
        tool_filter = mcp.create_static_tool_filter(
            allowed_tool_names=[
                "search_repositories", "get_repository", "list_issues",
                "get_issue", "create_issue", "update_issue",
                "list_pull_requests", "get_pull_request", "search_code",
                "get_file_contents", "list_workflow_runs"
            ],
            blocked_tool_names=["delete_repository", "create_repository", "delete_file"]
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

# 3. Định nghĩa thông tin repository được phép truy cập
ALLOWED_REPOSITORY = os.getenv("ALLOWED_REPOSITORY")
ALLOWED_BRANCH = os.getenv("ALLOWED_BRANCH")
REPOSITORY_URL = os.getenv("REPOSITORY_URL")
REPOSITORY_REF = os.getenv("REPOSITORY_REF")
REPOSITORY_OWNER = os.getenv("REPOSITORY_OWNER")
# 4. Định nghĩa instructions cho agent
github_worker_instructions = f"""
# GitHub Worker Agent Instruction

You are a specialized GitHub worker agent with RESTRICTED ACCESS. You ALWAYS operate exclusively on a single, pre-defined GitHub repository and branch.

## Tool Usage Guidelines:

* When using `get_file_contents`:
  - For root directory: omit the `path` parameter or use empty string
  - For specific files: use the file path (e.g., "README.md", "src/main.py")
  - For directories: use the directory path (e.g., "src", "docs")
  - Always use `ref: {REPOSITORY_REF}` for the main branch
* When using `search_code`: use specific search terms, not broad queries

## Error Handling:

* If a tool call times out (especially search_code), explain the timeout and suggest trying again with more specific search terms.
* For API rate limiting errors, explain the limitation and suggest waiting before retrying.
* If GitHub API is unavailable, provide a clear explanation of the service status.
* For 404 errors, check if the repository is private and token has correct permissions.
* Always include the specific error details in your response for debugging purposes.

---

## Repository Information

* Repository: `{REPOSITORY_OWNER}/{ALLOWED_REPOSITORY}`
* Branch: `{ALLOWED_BRANCH}`
* Repository URL: `{REPOSITORY_URL}`
* Repository Ref: `{REPOSITORY_REF}`
"""

# 5. Tạo Agent và truyền MCP server
awx_github_agent = Agent(
    name="GitHub Worker Agent",
    instructions=github_worker_instructions,
    output_type=github_worker_output,
    model=os.getenv("AI_MODEL"),
    handoff_description="Use this agent for all operations related to GitHub, such as managing repositories, issues, pull requests, and searching code.",
    mcp_servers=mcp_servers  # Gắn MCP server với các tools của GitHub
)

print(f"Agent '{awx_github_agent.name}' initialized with {len(mcp_servers)} MCP server(s).")