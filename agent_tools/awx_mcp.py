"""
Ansible AWX Tools

This module provides function tools for interacting with the Ansible AWX API through the OpenAI Agents SDK.
"""

import os
import json
import requests
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urljoin
from dotenv import load_dotenv
from agents import function_tool

load_dotenv()

# Configuration
ANSIBLE_BASE_URL = os.getenv("ANSIBLE_BASE_URL")
ANSIBLE_USERNAME = os.getenv("ANSIBLE_USERNAME")
ANSIBLE_PASSWORD = os.getenv("ANSIBLE_PASSWORD")
ANSIBLE_TOKEN = os.getenv("ANSIBLE_TOKEN")

# API Client
class AnsibleClient:
    def __init__(self, base_url: str, username: str = None, password: str = None, token: str = None):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.token = token
        self.session = requests.Session()
        self.session.verify = False
    
    def __enter__(self):
        if not self.token and self.username and self.password:
            self.get_token()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
    
    def get_token(self) -> str:
        """Authenticate and get token using web session approach."""
        login_page = self.session.get(f"{self.base_url}/api/login/")
        
        csrf_token = None
        if 'csrftoken' in login_page.cookies:
            csrf_token = login_page.cookies['csrftoken']
        else:
            import re
            match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login_page.text)
            if match:
                csrf_token = match.group(1)
                
        if not csrf_token:
            raise Exception("Could not obtain CSRF token")
            
        headers = {
            'Referer': f"{self.base_url}/api/login/",
            'X-CSRFToken': csrf_token
        }
        
        login_data = {
            "username": self.username,
            "password": self.password,
            "next": "/api/v2/"
        }
        
        login_response = self.session.post(
            f"{self.base_url}/api/login/",
            data=login_data,
            headers=headers
        )
        
        if login_response.status_code >= 400:
            raise Exception(f"Login failed: {login_response.status_code} - {login_response.text}")
            
        token_headers = {
            'Content-Type': 'application/json',
            'Referer': f"{self.base_url}/api/v2/",
        }
        
        if 'csrftoken' in self.session.cookies:
            token_headers['X-CSRFToken'] = self.session.cookies['csrftoken']
            
        token_data = {
            "description": "MCP Server Token",
            "application": None,
            "scope": "write"
        }
        
        token_response = self.session.post(
            f"{self.base_url}/api/v2/tokens/",
            json=token_data,
            headers=token_headers
        )
        
        if token_response.status_code == 201:
            token_data = token_response.json()
            self.token = token_data.get('token')
            return self.token
        else:
            raise Exception(f"Token creation failed: {token_response.status_code} - {token_response.text}")
    
    def get_headers(self) -> Dict[str, str]:
        """Get request headers with authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    def request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """Make a request to the Ansible API."""
        url = urljoin(self.base_url, endpoint)
        headers = self.get_headers()
        
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=data
        )
        
        if response.status_code >= 400:
            error_message = f"Ansible API error: {response.status_code} - {response.text}"
            raise Exception(error_message)
            
        if response.status_code == 204:
            return {"status": "success"}
        
        if not response.text.strip():
            return {"status": "success", "message": "Empty response"}
            
        try:
            return response.json()
        except json.JSONDecodeError:
            return {
                "status": "success",
                "content_type": response.headers.get("Content-Type", "unknown"),
                "text": response.text[:1000]
            }

def get_ansible_client() -> AnsibleClient:
    """Get an initialized Ansible API client."""
    client = AnsibleClient(
        base_url=ANSIBLE_BASE_URL,
        username=ANSIBLE_USERNAME, 
        password=ANSIBLE_PASSWORD,
        token=ANSIBLE_TOKEN
    )
    return client

def handle_pagination(client: AnsibleClient, endpoint: str, params: Dict = None) -> List[Dict]:
    """Handle paginated results from Ansible API."""
    if params is None:
        params = {}
    
    results = []
    next_url = endpoint
    
    while next_url:
        response = client.request("GET", next_url, params=params)
        if "results" in response:
            results.extend(response["results"])
        else:
            return [response]
            
        next_url = response.get("next")
        if next_url:
            params = None
            
    return results

# Function Tools - Inventory Management

@function_tool
def list_inventories(page_size: int = 100, page: int = 1) -> str:
    """List all inventories.
    
    Args:
        page_size: Number of items in a page
        page: The page index (starts from 1)
    """
    with get_ansible_client() as client:
        params = {"limit": page_size, "page": page}
        inventories = handle_pagination(client, "/api/v2/inventories/", params)
        return json.dumps(inventories, indent=2)

@function_tool
def get_inventory(inventory_id: int) -> str:
    """Get details about a specific inventory.
    
    Args:
        inventory_id: ID of the inventory
    """
    with get_ansible_client() as client:
        inventory = client.request("GET", f"/api/v2/inventories/{inventory_id}/")
        return json.dumps(inventory, indent=2)

@function_tool
def create_inventory(name: str, organization_id: int, description: str = "") -> str:
    """Create a new inventory.
    
    Args:
        name: Name of the inventory
        organization_id: ID of the organization
        description: Description of the inventory
    """
    with get_ansible_client() as client:
        data = {
            "name": name,
            "description": description,
            "organization": organization_id
        }
        response = client.request("POST", "/api/v2/inventories/", data=data)
        return json.dumps(response, indent=2)

@function_tool
def update_inventory(inventory_id: int, name: str = None, description: str = None) -> str:
    """Update an existing inventory.
    
    Args:
        inventory_id: ID of the inventory
        name: New name for the inventory
        description: New description for the inventory
    """
    with get_ansible_client() as client:
        data = {}
        if name:
            data["name"] = name
        if description:
            data["description"] = description
            
        response = client.request("PATCH", f"/api/v2/inventories/{inventory_id}/", data=data)
        return json.dumps(response, indent=2)

@function_tool
def delete_inventory(inventory_id: int) -> str:
    """Delete an inventory."""
    with get_ansible_client() as client:
        try:
            response = client.session.delete(
                f"{client.base_url}/api/v2/inventories/{inventory_id}/",
                headers=client.get_headers()
            )
            if response.status_code == 204:
                return json.dumps({"status": "success", "message": f"Inventory {inventory_id} deleted"})
            elif response.text:
                try:
                    return json.dumps(response.json(), indent=2)
                except json.JSONDecodeError:
                    return json.dumps({"status": "success", "message": f"Inventory {inventory_id} deleted"})
            else:
                return json.dumps({"status": "success", "message": f"Inventory {inventory_id} deleted"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

# Function Tools - Host Management

@function_tool
def list_hosts(inventory_id: int = None, page_size: int = 100, page: int = 1) -> str:
    """List hosts, optionally filtered by inventory.
    
    Args:
        inventory_id: Optional ID of inventory to filter hosts
        page_size: Number of items in a page
        page: The page index (starts from 1)
    """
    with get_ansible_client() as client:
        params = {"limit": page_size, "page": page}
        
        if inventory_id:
            endpoint = f"/api/v2/inventories/{inventory_id}/hosts/"
        else:
            endpoint = "/api/v2/hosts/"
            
        hosts = handle_pagination(client, endpoint, params)
        return json.dumps(hosts, indent=2)

@function_tool
def get_host(host_id: int) -> str:
    """Get details about a specific host.
    
    Args:
        host_id: ID of the host
    """
    with get_ansible_client() as client:
        host = client.request("GET", f"/api/v2/hosts/{host_id}/")
        return json.dumps(host, indent=2)

@function_tool
def create_host(name: str, inventory_id: int, variables: str = "{}", description: str = "") -> str:
    """Create a new host in an inventory.
    
    Args:
        name: Name or IP address of the host
        inventory_id: ID of the inventory to add the host to
        variables: JSON string of host variables
        description: Description of the host
    """
    try:
        json.loads(variables)
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "message": "Invalid JSON in variables"})
    
    with get_ansible_client() as client:
        data = {
            "name": name,
            "inventory": inventory_id,
            "variables": variables,
            "description": description
        }
        response = client.request("POST", "/api/v2/hosts/", data=data)
        return json.dumps(response, indent=2)

@function_tool
def update_host(host_id: int, name: str = None, variables: str = None, description: str = None) -> str:
    """Update an existing host.
    
    Args:
        host_id: ID of the host
        name: New name for the host
        variables: JSON string of host variables
        description: New description for the host
    """
    if variables:
        try:
            json.loads(variables)
        except json.JSONDecodeError:
            return json.dumps({"status": "error", "message": "Invalid JSON in variables"})
    
    with get_ansible_client() as client:
        data = {}
        if name:
            data["name"] = name
        if variables:
            data["variables"] = variables
        if description:
            data["description"] = description
            
        response = client.request("PATCH", f"/api/v2/hosts/{host_id}/", data=data)
        return json.dumps(response, indent=2)

@function_tool
def delete_host(host_id: int) -> str:
    """Delete a host.
    
    Args:
        host_id: ID of the host
    """
    with get_ansible_client() as client:
        client.request("DELETE", f"/api/v2/hosts/{host_id}/")
        return json.dumps({"status": "success", "message": f"Host {host_id} deleted"})

# Function Tools - Job Template Management

@function_tool
def list_job_templates(page_size: int = 100, page: int = 1) -> str:
    """List all job templates.
    
    Args:
        page_size: Number of items in a page
        page: The page index (starts from 1)
    """
    with get_ansible_client() as client:
        params = {"limit": page_size, "page": page}
        templates = handle_pagination(client, "/api/v2/job_templates/", params)
        return json.dumps(templates, indent=2)

@function_tool
def get_job_template(template_id: int) -> str:
    """Get details about a specific job template.
    
    Args:
        template_id: ID of the job template
    """
    with get_ansible_client() as client:
        template = client.request("GET", f"/api/v2/job_templates/{template_id}/")
        return json.dumps(template, indent=2)

@function_tool
def create_job_template(
    name: str, 
    inventory_id: int,
    project_id: int,
    playbook: str,
    credential_id: int = None,
    description: str = "",
    extra_vars: str = "{}"
) -> str:
    """Create a new job template.
    
    Args:
        name: Name of the job template
        inventory_id: ID of the inventory
        project_id: ID of the project
        playbook: Name of the playbook (e.g., "playbook.yml")
        credential_id: Optional ID of the credential
        description: Description of the job template
        extra_vars: JSON string of extra variables
    """
    try:
        json.loads(extra_vars)
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "message": "Invalid JSON in extra_vars"})
    
    with get_ansible_client() as client:
        data = {
            "name": name,
            "inventory": inventory_id,
            "project": project_id,
            "playbook": playbook,
            "description": description,
            "extra_vars": extra_vars,
            "job_type": "run",
            "verbosity": 0
        }
        
        if credential_id:
            data["credential"] = credential_id
            
        response = client.request("POST", "/api/v2/job_templates/", data=data)
        return json.dumps(response, indent=2)

@function_tool
def launch_job(template_id: int, extra_vars: str = None) -> str:
    """Launch a job from a job template.
    
    Args:
        template_id: ID of the job template
        extra_vars: JSON string of extra variables to override the template's variables
    """
    if extra_vars:
        try:
            json.loads(extra_vars)
        except json.JSONDecodeError:
            return json.dumps({"status": "error", "message": "Invalid JSON in extra_vars"})
    
    with get_ansible_client() as client:
        data = {}
        if extra_vars:
            data["extra_vars"] = extra_vars
            
        response = client.request("POST", f"/api/v2/job_templates/{template_id}/launch/", data=data)
        return json.dumps(response, indent=2)

# Function Tools - Job Management

@function_tool
def list_jobs(status: str = None, page_size: int = 100, page: int = 1) -> str:
    """List all jobs, optionally filtered by status.
    
    Args:
        status: Filter by job status (pending, waiting, running, successful, failed, canceled)
        page_size: Number of items in a page
        page: The page index (starts from 1)
    """
    with get_ansible_client() as client:
        params = {"limit": page_size, "page": page}
        if status:
            params["status"] = status
            
        jobs = handle_pagination(client, "/api/v2/jobs/", params)
        return json.dumps(jobs, indent=2)

@function_tool
def get_job(job_id: int) -> str:
    """Get details about a specific job.
    
    Args:
        job_id: ID of the job
    """
    with get_ansible_client() as client:
        job = client.request("GET", f"/api/v2/jobs/{job_id}/")
        return json.dumps(job, indent=2)

@function_tool
def cancel_job(job_id: int) -> str:
    """Cancel a running job.
    
    Args:
        job_id: ID of the job
    """
    with get_ansible_client() as client:
        response = client.request("POST", f"/api/v2/jobs/{job_id}/cancel/")
        return json.dumps(response, indent=2)

@function_tool
def get_job_stdout(job_id: int, format: str = "txt") -> str:
    """Get the standard output of a job."""
    if format not in ["txt", "html", "json", "ansi"]:
        return json.dumps({"status": "error", "message": "Invalid format"})
    
    with get_ansible_client() as client:
        if format != "json":
            url = f"{client.base_url}/api/v2/jobs/{job_id}/stdout/?format={format}"
            response = client.session.get(url, headers=client.get_headers())
            return json.dumps({"status": "success", "stdout": response.text})
        else:
            response = client.request("GET", f"/api/v2/jobs/{job_id}/stdout/?format={format}")
            return json.dumps(response, indent=2)

# Function Tools - Project Management

@function_tool
def list_projects(page_size: int = 100, page: int = 1) -> str:
    """List all projects.
    
    Args:
        page_size: Number of items in a page
        page: The page index (starts from 1)
    """
    with get_ansible_client() as client:
        params = {"limit": page_size, "page": page}
        projects = handle_pagination(client, "/api/v2/projects/", params)
        return json.dumps(projects, indent=2)

@function_tool
def get_project(project_id: int) -> str:
    """Get details about a specific project.
    
    Args:
        project_id: ID of the project
    """
    with get_ansible_client() as client:
        project = client.request("GET", f"/api/v2/projects/{project_id}/")
        return json.dumps(project, indent=2)

@function_tool
def create_project(
    name: str,
    organization_id: int,
    scm_type: str,
    scm_url: str = None,
    scm_branch: str = None,
    credential_id: int = None,
    description: str = ""
) -> str:
    """Create a new project.
    
    Args:
        name: Name of the project
        organization_id: ID of the organization
        scm_type: SCM type (git, hg, svn, manual)
        scm_url: URL for the repository
        scm_branch: Branch/tag/commit to checkout
        credential_id: ID of the credential for SCM access
        description: Description of the project
    """
    if scm_type not in ["", "git", "hg", "svn", "manual"]:
        return json.dumps({"status": "error", "message": "Invalid SCM type. Must be one of: git, hg, svn, manual"})
    
    if scm_type != "manual" and not scm_url:
        return json.dumps({"status": "error", "message": "SCM URL is required for non-manual SCM types"})
    
    with get_ansible_client() as client:
        data = {
            "name": name,
            "organization": organization_id,
            "scm_type": scm_type,
            "description": description
        }
        
        if scm_url:
            data["scm_url"] = scm_url
        if scm_branch:
            data["scm_branch"] = scm_branch
        if credential_id:
            data["credential"] = credential_id
            
        response = client.request("POST", "/api/v2/projects/", data=data)
        return json.dumps(response, indent=2)

# Function Tools - Organization Management

@function_tool
def list_organizations(page_size: int = 100, page: int = 1) -> str:
    """List all organizations.
    
    Args:
        page_size: Number of items in a page
        page: The page index (starts from 1)
    """
    with get_ansible_client() as client:
        params = {"limit": page_size, "page": page}
        organizations = handle_pagination(client, "/api/v2/organizations/", params)
        return json.dumps(organizations, indent=2)

@function_tool
def get_organization(organization_id: int) -> str:
    """Get details about a specific organization.
    
    Args:
        organization_id: ID of the organization
    """
    with get_ansible_client() as client:
        organization = client.request("GET", f"/api/v2/organizations/{organization_id}/")
        return json.dumps(organization, indent=2)

@function_tool
def create_organization(name: str, description: str = "") -> str:
    """Create a new organization.
    
    Args:
        name: Name of the organization
        description: Description of the organization
    """
    with get_ansible_client() as client:
        data = {
            "name": name,
            "description": description
        }
        response = client.request("POST", "/api/v2/organizations/", data=data)
        return json.dumps(response, indent=2)

# Function Tools - Credential Management

@function_tool
def list_credentials(page_size: int = 100, page: int = 1) -> str:
    """List all credentials.
    
    Args:
        page_size: Number of items in a page
        page: The page index (starts from 1)
    """
    with get_ansible_client() as client:
        params = {"limit": page_size, "page": page}
        credentials = handle_pagination(client, "/api/v2/credentials/", params)
        return json.dumps(credentials, indent=2)

@function_tool
def get_credential(credential_id: int) -> str:
    """Get details about a specific credential.
    
    Args:
        credential_id: ID of the credential
    """
    with get_ansible_client() as client:
        credential = client.request("GET", f"/api/v2/credentials/{credential_id}/")
        return json.dumps(credential, indent=2)

@function_tool
def create_credential(
    name: str,
    credential_type: int,
    inputs: str = "{}",
    organization: int = None,
    user: int = None,
    team: int = None,
    description: str = ""
) -> str:
    """Create a new credential.
    
    Args:
        name: Name of this credential (required)
        credential_type: Specify the type of credential you want to create (required)
        inputs: Enter inputs using JSON syntax (default: {})
        organization: Inherit permissions from organization roles (default: None)
        user: Write-only field used to add user to owner role (default: None)
        team: Write-only field used to add team to owner role (default: None)
        description: Optional description of this credential (default: "")
    """
    try:
        # Validate that inputs is a proper JSON string
        json.loads(inputs)
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "message": "Invalid JSON in inputs"})
    
    # Validate that only one of organization, user, or team is provided
    owner_fields = [organization, user, team]
    provided_owners = [field for field in owner_fields if field is not None]
    if len(provided_owners) > 1:
        return json.dumps({"status": "error", "message": "Only one of organization, user, or team can be provided"})
    
    with get_ansible_client() as client:
        data = {
            "name": name,
            "credential_type": credential_type,
            "inputs": json.loads(inputs),
            "description": description
        }
        
        # Add owner field if provided
        if organization is not None:
            data["organization"] = organization
        elif user is not None:
            data["user"] = user
        elif team is not None:
            data["team"] = team
            
        response = client.request("POST", "/api/v2/credentials/", data=data)
        return json.dumps(response, indent=2)

@function_tool
def update_credential(
    credential_id: int,
    name: str = None,
    credential_type: int = None,
    inputs: str = None,
    organization: int = None,
    description: str = None
) -> str:
    """Update an existing credential.
    
    Args:
        credential_id: ID of the credential to update (required)
        name: Name of this credential
        credential_type: Specify the type of credential
        inputs: Enter inputs using JSON syntax
        organization: Organization ID for permissions
        description: Optional description of this credential
    """
    if inputs:
        try:
            # Validate that inputs is a proper JSON string
            json.loads(inputs)
        except json.JSONDecodeError:
            return json.dumps({"status": "error", "message": "Invalid JSON in inputs"})
    
    with get_ansible_client() as client:
        data = {}
        
        # Add fields that are provided
        if name is not None:
            data["name"] = name
        if credential_type is not None:
            data["credential_type"] = credential_type
        if inputs is not None:
            data["inputs"] = json.loads(inputs)
        if organization is not None:
            data["organization"] = organization
        if description is not None:
            data["description"] = description
            
        # If no data to update, return error
        if not data:
            return json.dumps({"status": "error", "message": "No fields provided for update"})
            
        response = client.request("PATCH", f"/api/v2/credentials/{credential_id}/", data=data)
        return json.dumps(response, indent=2)

# Function Tools - User Management

@function_tool
def list_users(page_size: int = 100, page: int = 1) -> str:
    """List all users.
    
    Args:
        page_size: Number of items in a page
        page: The page index (starts from 1)
    """
    with get_ansible_client() as client:
        params = {"limit": page_size, "page": page}
        users = handle_pagination(client, "/api/v2/users/", params)
        return json.dumps(users, indent=2)

@function_tool
def get_user(user_id: int) -> str:
    """Get details about a specific user.
    
    Args:
        user_id: ID of the user
    """
    with get_ansible_client() as client:
        user = client.request("GET", f"/api/v2/users/{user_id}/")
        return json.dumps(user, indent=2)

# Function Tools - System Information

@function_tool
def get_ansible_version() -> str:
    """Get Ansible Tower/AWX version information."""
    with get_ansible_client() as client:
        info = client.request("GET", "/api/v2/ping/")
        return json.dumps(info, indent=2)

@function_tool
def get_dashboard_stats() -> str:
    """Get dashboard statistics."""
    with get_ansible_client() as client:
        stats = client.request("GET", "/api/v2/dashboard/")
        return json.dumps(stats, indent=2) 