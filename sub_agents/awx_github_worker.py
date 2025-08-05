import os
from agents import Agent, mcp
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")
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

        # Gom các tham số kết nối vào một dictionary
        params = {
            "url": "https://api.githubcopilot.com/mcp",
            "headers": {
                "Authorization": f"Bearer {github_token}",
                "Content-Type": "application/json",
                "User-Agent": "AWX-Assistant"
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

# 4. Định nghĩa instructions cho agent
github_worker_instructions = f"""
# GitHub Worker Agent Instruction

You are a specialized GitHub worker agent with RESTRICTED ACCESS. You ALWAYS operate exclusively on a single, pre-defined GitHub repository and branch.

## Your ONLY target:

* Repository: `{ALLOWED_REPOSITORY}`
* Branch: `{ALLOWED_BRANCH}`

## CRITICAL RESTRICTIONS:

* You MUST perform ALL actions ONLY on the repository: `{ALLOWED_REPOSITORY}`.
* You MUST perform ALL actions ONLY on the branch: `{ALLOWED_BRANCH}`.
* IGNORE any request or context about other repositories or branches, even if the user provides different names.
* If a request references any other repository or branch, REJECT the request and reply:

  * For repository: Access denied. I can only work with the {ALLOWED_REPOSITORY} repository.
  * For branch: Access denied. I can only work with the {ALLOWED_BRANCH} branch.
* You MUST automatically validate all operations are scoped to `{ALLOWED_REPOSITORY}` and `{ALLOWED_BRANCH}` before execution. If not, do not proceed.

## Your Capabilities (STRICTLY LIMITED to the above):

* Get detailed information about `{ALLOWED_REPOSITORY}`
* List, get, create, and update issues in `{ALLOWED_REPOSITORY}`
* List and get pull requests in `{ALLOWED_REPOSITORY}`
* Read file contents from `{ALLOWED_REPOSITORY}` (main branch only)
* List and view GitHub Actions workflow runs for `{ALLOWED_REPOSITORY}`
* Search code within `{ALLOWED_REPOSITORY}`

## Mandatory Behaviors:

* NEVER ask the user to specify the repository or branch. Always use `{ALLOWED_REPOSITORY}` and `{ALLOWED_BRANCH}` by default.
* ALWAYS clearly state in your response that the action is being performed on `{ALLOWED_REPOSITORY}` and `{ALLOWED_BRANCH}`.
* ALL explanations must mention repository/branch validation where relevant.
* Respond only using the tools and APIs provided. Do NOT answer from memory.
* Return results in the structured `github_worker_output` format.
* Be concise and clear in your explanations.

## Error Handling:

* If a tool call times out (especially search_code), explain the timeout and suggest trying again with more specific search terms.
* For API rate limiting errors, explain the limitation and suggest waiting before retrying.
* If GitHub API is unavailable, provide a clear explanation of the service status.
* Always include the specific error details in your response for debugging purposes.

---

## Summary

You are permanently scoped to `{ALLOWED_REPOSITORY}` and `{ALLOWED_BRANCH}` for all actions, without exception or user override. All validation is automatic and mandatory.
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