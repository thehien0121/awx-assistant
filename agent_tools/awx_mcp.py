import os
import httpx
from typing import Any, Dict, List, Optional
from agents import function_tool

# Environment variables for authentication
AAP_URL = os.getenv("AWX_AAP_URL", "http://192.168.10.46:32000")
AAP_TOKEN = os.getenv("AWX_AAP_TOKEN")

if not AAP_TOKEN:
    raise ValueError("AAP_TOKEN is required")

# Headers for API authentication
HEADERS = {
    "Authorization": f"Bearer {AAP_TOKEN}",
    "Content-Type": "application/json"
}

async def make_request(url: str, method: str = "GET", json: dict = None) -> Any:
    """Helper function to make authenticated API requests to AAP."""
    async with httpx.AsyncClient() as client:
        response = await client.request(method, url, headers=HEADERS, json=json)
    if response.status_code not in [200, 201]:
        return f"Error {response.status_code}: {response.text}"
    return response.json() if "application/json" in response.headers.get("Content-Type", "") else response.text

@function_tool
async def list_inventories() -> Any:
    """List all inventories in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/inventories/")

@function_tool
async def get_inventory(inventory_id: str) -> Any:
    """Get details of a specific inventory by ID."""
    return await make_request(f"{AAP_URL}/inventories/{inventory_id}/")

@function_tool
async def run_job(template_id: int, extra_vars: dict = {}) -> Any:
    """Run a job template by ID, optionally with extra_vars."""
    return await make_request(f"{AAP_URL}/job_templates/{template_id}/launch/", method="POST", json={"extra_vars": extra_vars})

@function_tool
async def job_status(job_id: int) -> Any:
    """Check the status of a job by ID."""
    return await make_request(f"{AAP_URL}/jobs/{job_id}/")

@function_tool
async def job_logs(job_id: int) -> str:
    """Retrieve logs for a job."""
    return await make_request(f"{AAP_URL}/jobs/{job_id}/stdout/")

@function_tool
async def create_job_template(
    name: str,
    project_id: int,
    playbook: str,
    inventory_id: int,
    job_type: str = "run",
    description: str = "",
    credential_id: int = None,
    execution_environment_id: int = None,
    labels: list[str] = None,
    forks: int = 0,
    limit: str = "",
    verbosity: int = 0,
    timeout: int = 0,
    job_tags: list[str] = None,
    skip_tags: list[str] = None,
    extra_vars: dict = None,
    privilege_escalation: bool = False,
    concurrent_jobs: bool = False,
    provisioning_callback: bool = False,
    enable_webhook: bool = False,
    prevent_instance_group_fallback: bool = False,
) -> Any:
    """Create a new job template in Ansible Automation Platform."""

    payload = {
        "name": name,
        "description": description,
        "job_type": job_type,
        "project": project_id,
        "playbook": playbook,
        "inventory": inventory_id,
        "forks": forks,
        "limit": limit,
        "verbosity": verbosity,
        "timeout": timeout,
        "ask_variables_on_launch": bool(extra_vars),
        "ask_tags_on_launch": bool(job_tags),
        "ask_skip_tags_on_launch": bool(skip_tags),
        "ask_credential_on_launch": credential_id is None,
        "ask_execution_environment_on_launch": execution_environment_id is None,
        "ask_labels_on_launch": labels is None,
        "ask_inventory_on_launch": False,  # Inventory is required, so not prompting
        "ask_job_type_on_launch": False,  # Job type is required, so not prompting
        "become_enabled": privilege_escalation,
        "allow_simultaneous": concurrent_jobs,
        "scm_branch": "",
        "webhook_service": "github" if enable_webhook else "",
        "prevent_instance_group_fallback": prevent_instance_group_fallback,
    }

    if credential_id:
        payload["credential"] = credential_id
    if execution_environment_id:
        payload["execution_environment"] = execution_environment_id
    if labels:
        payload["labels"] = labels
    if job_tags:
        payload["job_tags"] = job_tags
    if skip_tags:
        payload["skip_tags"] = skip_tags
    if extra_vars:
        payload["extra_vars"] = extra_vars

    return await make_request(f"{AAP_URL}/job_templates/", method="POST", json=payload)

@function_tool
async def list_inventory_sources() -> Any:
    """List all inventory sources in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/inventory_sources/")

@function_tool
async def get_inventory_source(inventory_source_id: int) -> Any:
    """Get details of a specific inventory source."""
    return await make_request(f"{AAP_URL}/inventory_sources/{inventory_source_id}/")

@function_tool
async def create_inventory_source(
    name: str,
    inventory_id: int,
    source: str,
    credential_id: int,
    source_vars: dict = None,
    update_on_launch: bool = True,
    timeout: int = 0,
) -> Any:
    """Create a dynamic inventory source. Claude will ask for the source type and credential before proceeding."""
    valid_sources = [
        "file", "constructed", "scm", "ec2", "gce", "azure_rm", "vmware", "satellite6", "openstack", 
        "rhv", "controller", "insights", "terraform", "openshift_virtualization"
    ]
    
    if source not in valid_sources:
        return f"Error: Invalid source type '{source}'. Please select from: {', '.join(valid_sources)}"
    
    if not credential_id:
        return "Error: Credential is required to create an inventory source."
    
    payload = {
        "name": name,
        "inventory": inventory_id,
        "source": source,
        "credential": credential_id,
        "source_vars": source_vars,
        "update_on_launch": update_on_launch,
        "timeout": timeout,
    }
    return await make_request(f"{AAP_URL}/inventory_sources/", method="POST", json=payload)

@function_tool
async def update_inventory_source(inventory_source_id: int, update_data: dict) -> Any:
    """Update an existing inventory source."""
    return await make_request(f"{AAP_URL}/inventory_sources/{inventory_source_id}/", method="PUT", json=update_data)

@function_tool
async def delete_inventory_source(inventory_source_id: int) -> Any:
    """Delete an inventory source.
    
    Args:
        inventory_source_id: ID of the inventory source to delete
    """
    return await make_request(f"{AAP_URL}/inventory_sources/{inventory_source_id}/", method="DELETE")

@function_tool
async def sync_inventory_source(inventory_source_id: int) -> Any:
    """Manually trigger a sync for an inventory source."""
    return await make_request(f"{AAP_URL}/inventory_sources/{inventory_source_id}/update/", method="POST")

@function_tool
async def create_inventory(
    name: str,
    organization_id: int,
    description: str = "",
    kind: str = "",
    host_filter: str = "",
    variables: dict = None,
    prevent_instance_group_fallback: bool = False,
) -> Any:
    """Create an inventory in Ansible Automation Platform."""
    payload = {
        "name": name,
        "organization": organization_id,
        "description": description,
        "kind": kind,
        "host_filter": host_filter,
        "variables": variables,
        "prevent_instance_group_fallback": prevent_instance_group_fallback,
    }
    return await make_request(f"{AAP_URL}/inventories/", method="POST", json=payload)

@function_tool
async def delete_inventory(inventory_id: int) -> Any:
    """Delete an inventory from Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/inventories/{inventory_id}/", method="DELETE")

@function_tool
async def list_job_templates() -> Any:
    """List all job templates available in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/job_templates/")

@function_tool
async def get_job_template(template_id: int) -> Any:
    """Retrieve details of a specific job template."""
    return await make_request(f"{AAP_URL}/job_templates/{template_id}/")

@function_tool
async def list_jobs() -> Any:
    """List all jobs available in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/jobs/")

@function_tool
async def list_recent_jobs(hours: int = 24) -> Any:
    """List all jobs executed in the last specified hours (default 24 hours)."""
    from datetime import datetime, timedelta
    
    time_filter = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
    return await make_request(f"{AAP_URL}/jobs/?created__gte={time_filter}")

# Thêm tool để liệt kê danh sách các tổ chức
@function_tool
async def list_organizations() -> Any:
    """List all organizations in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/organizations/")

# Thêm tool để xem thông tin chi tiết về tổ chức
@function_tool
async def get_organization(organization_id: int) -> Any:
    """Get details of a specific organization."""
    return await make_request(f"{AAP_URL}/organizations/{organization_id}/")

# Thêm tool để liệt kê danh sách các credentials
@function_tool
async def list_credentials() -> Any:
    """List all credentials in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/credentials/")

# Thêm tool để xem thông tin chi tiết về credential
@function_tool
async def get_credential(credential_id: int) -> Any:
    """Get details of a specific credential."""
    return await make_request(f"{AAP_URL}/credentials/{credential_id}/")

# Versioning API Functions
@function_tool
async def list_api_versions() -> Any:
    """List supported API versions in Ansible Automation Platform.
    
    Returns information about available API versions including:
    - available_versions: Dictionary of version numbers and their URLs
    - current_version: URL of the current API version
    - description: API description
    - oauth2: OAuth2 endpoint URL
    """
    return await make_request(f"{AAP_URL}/api/")

@function_tool
async def list_top_level_resources() -> Any:
    """List top level resources available in the current API version (v2).
    
    Returns a list of all available top-level API endpoints and resources
    that can be accessed in the current API version.
    """
    return await make_request(f"{AAP_URL}/")

# Authentication API Functions
@function_tool
async def get_oauth2_info() -> Any:
    """Get OAuth2 token handling information.
    
    Returns information about OAuth2 endpoints and token handling
    capabilities in Ansible Automation Platform.
    """
    return await make_request(f"{AAP_URL}/api/o/")

@function_tool
async def list_applications() -> Any:
    """List all OAuth2 applications in Ansible Automation Platform.
    
    Returns a list of all registered OAuth2 applications that can be used
    for API authentication and token management.
    """
    return await make_request(f"{AAP_URL}/applications/")

@function_tool
async def create_application(
    name: str,
    user_id: int,
    client_type: str = "confidential",
    authorization_grant_type: str = "password",
    redirect_uris: str = "",
    client_id: str = "",
    client_secret: str = "",
    skip_authorization: bool = False,
) -> Any:
    """Create a new OAuth2 application in Ansible Automation Platform.
    
    Args:
        name: Name of the application
        user_id: ID of the user who owns the application
        client_type: Type of client (public or confidential)
        authorization_grant_type: Grant type (password, authorization-code, etc.)
        redirect_uris: Comma-separated list of redirect URIs
        client_id: Custom client ID (optional)
        client_secret: Custom client secret (optional)
        skip_authorization: Whether to skip authorization for this app
    """
    payload = {
        "name": name,
        "user": user_id,
        "client_type": client_type,
        "authorization_grant_type": authorization_grant_type,
        "redirect_uris": redirect_uris,
        "skip_authorization": skip_authorization,
    }
    
    if client_id:
        payload["client_id"] = client_id
    if client_secret:
        payload["client_secret"] = client_secret
    
    return await make_request(f"{AAP_URL}/applications/", method="POST", json=payload)

@function_tool
async def get_application(application_id: int) -> Any:
    """Get details of a specific OAuth2 application.
    
    Args:
        application_id: ID of the application to retrieve
    """
    return await make_request(f"{AAP_URL}/applications/{application_id}/")

@function_tool
async def update_application(application_id: int, update_data: dict) -> Any:
    """Update an existing OAuth2 application.
    
    Args:
        application_id: ID of the application to update
        update_data: Dictionary containing fields to update
    """
    return await make_request(f"{AAP_URL}/applications/{application_id}/", method="PUT", json=update_data)

@function_tool
async def delete_application(application_id: int) -> Any:
    """Delete an OAuth2 application.
    
    Args:
        application_id: ID of the application to delete
    """
    return await make_request(f"{AAP_URL}/applications/{application_id}/", method="DELETE")

@function_tool
async def list_access_tokens() -> Any:
    """List all access tokens in Ansible Automation Platform.
    
    Returns a list of all access tokens that can be used for API authentication.
    """
    return await make_request(f"{AAP_URL}/tokens/")

@function_tool
async def create_access_token(
    user_id: int,
    application_id: int = None,
    scope: str = "write",
    expires: str = None,
) -> Any:
    """Create a new access token for API authentication.
    
    Args:
        user_id: ID of the user for whom to create the token
        application_id: ID of the OAuth2 application (optional)
        scope: Token scope (read, write, etc.)
        expires: Expiration date in ISO format (optional)
    """
    payload = {
        "user": user_id,
        "scope": scope,
    }
    
    if application_id:
        payload["application"] = application_id
    if expires:
        payload["expires"] = expires
    
    return await make_request(f"{AAP_URL}/tokens/", method="POST", json=payload)

@function_tool
async def get_access_token(token_id: int) -> Any:
    """Get details of a specific access token.
    
    Args:
        token_id: ID of the token to retrieve
    """
    return await make_request(f"{AAP_URL}/tokens/{token_id}/")

@function_tool
async def update_access_token(token_id: int, update_data: dict) -> Any:
    """Update an existing access token.
    
    Args:
        token_id: ID of the token to update
        update_data: Dictionary containing fields to update
    """
    return await make_request(f"{AAP_URL}/tokens/{token_id}/", method="PUT", json=update_data)

@function_tool
async def delete_access_token(token_id: int) -> Any:
    """Delete an access token.
    
    Args:
        token_id: ID of the token to delete
    """
    return await make_request(f"{AAP_URL}/tokens/{token_id}/", method="DELETE")

# Instances API Functions
@function_tool
async def list_instances() -> Any:
    """List all instances in Ansible Automation Platform.
    
    Returns a list of all AWX instances including their status,
    capacity, and configuration information.
    """
    return await make_request(f"{AAP_URL}/instances/")

@function_tool
async def create_instance(
    hostname: str,
    node_type: str = "execution",
    node_state: str = "installed",
    capacity: int = 100,
    enabled: bool = True,
    managed_by_policy: bool = True,
) -> Any:
    """Create a new AWX instance.
    
    Args:
        hostname: Hostname of the instance
        node_type: Type of node (execution, hop, control)
        node_state: State of the node (installed, ready, etc.)
        capacity: Capacity of the instance (0-100)
        enabled: Whether the instance is enabled
        managed_by_policy: Whether the instance is managed by policy
    """
    payload = {
        "hostname": hostname,
        "node_type": node_type,
        "node_state": node_state,
        "capacity": capacity,
        "enabled": enabled,
        "managed_by_policy": managed_by_policy,
    }
    
    return await make_request(f"{AAP_URL}/instances/", method="POST", json=payload)

@function_tool
async def get_instance(instance_id: int) -> Any:
    """Get details of a specific AWX instance.
    
    Args:
        instance_id: ID of the instance to retrieve
    """
    return await make_request(f"{AAP_URL}/instances/{instance_id}/")

@function_tool
async def update_instance(instance_id: int, update_data: dict) -> Any:
    """Update an existing AWX instance.
    
    Args:
        instance_id: ID of the instance to update
        update_data: Dictionary containing fields to update
    """
    return await make_request(f"{AAP_URL}/instances/{instance_id}/", method="PUT", json=update_data)

@function_tool
async def patch_instance(instance_id: int, update_data: dict) -> Any:
    """Partially update an existing AWX instance.
    
    Args:
        instance_id: ID of the instance to update
        update_data: Dictionary containing fields to update
    """
    return await make_request(f"{AAP_URL}/instances/{instance_id}/", method="PATCH", json=update_data)

@function_tool
async def get_instance_health_check(instance_id: int) -> Any:
    """Get health check data for a specific AWX instance.
    
    Args:
        instance_id: ID of the instance to check health for
    """
    return await make_request(f"{AAP_URL}/instances/{instance_id}/health_check/")

@function_tool
async def initiate_instance_health_check(instance_id: int) -> Any:
    """Manually initiate a health check for a specific AWX instance.
    
    Args:
        instance_id: ID of the instance to perform health check on
    """
    return await make_request(f"{AAP_URL}/instances/{instance_id}/health_check/", method="POST")

@function_tool
async def get_instance_install_bundle(instance_id: int) -> Any:
    """Get install bundle information for a specific AWX instance.
    
    Args:
        instance_id: ID of the instance to get install bundle for
    """
    return await make_request(f"{AAP_URL}/instances/{instance_id}/install_bundle/")

@function_tool
async def list_instance_instance_groups(instance_id: int) -> Any:
    """List instance groups associated with a specific AWX instance.
    
    Args:
        instance_id: ID of the instance to get instance groups for
    """
    return await make_request(f"{AAP_URL}/instances/{instance_id}/instance_groups/")

@function_tool
async def add_instance_to_instance_group(instance_id: int, instance_group_id: int) -> Any:
    """Add an instance to an instance group.
    
    Args:
        instance_id: ID of the instance to add
        instance_group_id: ID of the instance group to add to
    """
    payload = {"id": instance_group_id}
    return await make_request(f"{AAP_URL}/instances/{instance_id}/instance_groups/", method="POST", json=payload)

@function_tool
async def list_instance_jobs(instance_id: int) -> Any:
    """List unified jobs associated with a specific AWX instance.
    
    Args:
        instance_id: ID of the instance to get jobs for
    """
    return await make_request(f"{AAP_URL}/instances/{instance_id}/jobs/")

@function_tool
async def list_instance_peers(instance_id: int) -> Any:
    """List peer instances for a specific AWX instance.
    
    Args:
        instance_id: ID of the instance to get peers for
    """
    return await make_request(f"{AAP_URL}/instances/{instance_id}/peers/")

@function_tool
async def delete_instance(instance_id: int) -> Any:
    """Delete an instance.
    
    Args:
        instance_id: ID of the instance to delete
    """
    return await make_request(f"{AAP_URL}/instances/{instance_id}/", method="DELETE")

# Instance Groups API Functions
@function_tool
async def list_instance_groups() -> Any:
    """List all instance groups in Ansible Automation Platform.
    
    Returns a list of all instance groups including their configuration,
    capacity, and associated instances.
    """
    return await make_request(f"{AAP_URL}/instance_groups/")

@function_tool
async def create_instance_group(
    name: str,
    policy_instance_minimum: int = 0,
    policy_instance_percentage: int = 0,
    max_concurrent_jobs: int = 0,
    max_forks: int = 0,
    policy_instance_list: list = None,
) -> Any:
    """Create a new instance group.
    
    Args:
        name: Name of the instance group
        policy_instance_minimum: Minimum number of instances to maintain
        policy_instance_percentage: Percentage of instances to maintain
        max_concurrent_jobs: Maximum number of concurrent jobs
        max_forks: Maximum number of forks
        policy_instance_list: List of instance IDs to include
    """
    data = {
        "name": name,
        "policy_instance_minimum": policy_instance_minimum,
        "policy_instance_percentage": policy_instance_percentage,
        "max_concurrent_jobs": max_concurrent_jobs,
        "max_forks": max_forks,
    }
    if policy_instance_list:
        data["policy_instance_list"] = policy_instance_list
    
    return await make_request(f"{AAP_URL}/instance_groups/", method="POST", json=data)

@function_tool
async def get_instance_group(instance_group_id: int) -> Any:
    """Get details of a specific instance group.
    
    Args:
        instance_group_id: ID of the instance group to retrieve
    """
    return await make_request(f"{AAP_URL}/instance_groups/{instance_group_id}/")

@function_tool
async def update_instance_group(
    instance_group_id: int,
    name: str = None,
    policy_instance_minimum: int = None,
    policy_instance_percentage: int = None,
    max_concurrent_jobs: int = None,
    max_forks: int = None,
    policy_instance_list: list = None,
) -> Any:
    """Update an instance group.
    
    Args:
        instance_group_id: ID of the instance group to update
        name: New name for the instance group
        policy_instance_minimum: New minimum number of instances
        policy_instance_percentage: New percentage of instances
        max_concurrent_jobs: New maximum concurrent jobs
        max_forks: New maximum forks
        policy_instance_list: New list of instance IDs
    """
    data = {}
    if name is not None:
        data["name"] = name
    if policy_instance_minimum is not None:
        data["policy_instance_minimum"] = policy_instance_minimum
    if policy_instance_percentage is not None:
        data["policy_instance_percentage"] = policy_instance_percentage
    if max_concurrent_jobs is not None:
        data["max_concurrent_jobs"] = max_concurrent_jobs
    if max_forks is not None:
        data["max_forks"] = max_forks
    if policy_instance_list is not None:
        data["policy_instance_list"] = policy_instance_list
    
    return await make_request(f"{AAP_URL}/instance_groups/{instance_group_id}/", method="PUT", json=data)

@function_tool
async def patch_instance_group(
    instance_group_id: int,
    name: str = None,
    policy_instance_minimum: int = None,
    policy_instance_percentage: int = None,
    max_concurrent_jobs: int = None,
    max_forks: int = None,
    policy_instance_list: list = None,
) -> Any:
    """Partially update an instance group.
    
    Args:
        instance_group_id: ID of the instance group to update
        name: New name for the instance group
        policy_instance_minimum: New minimum number of instances
        policy_instance_percentage: New percentage of instances
        max_concurrent_jobs: New maximum concurrent jobs
        max_forks: New maximum forks
        policy_instance_list: New list of instance IDs
    """
    data = {}
    if name is not None:
        data["name"] = name
    if policy_instance_minimum is not None:
        data["policy_instance_minimum"] = policy_instance_minimum
    if policy_instance_percentage is not None:
        data["policy_instance_percentage"] = policy_instance_percentage
    if max_concurrent_jobs is not None:
        data["max_concurrent_jobs"] = max_concurrent_jobs
    if max_forks is not None:
        data["max_forks"] = max_forks
    if policy_instance_list is not None:
        data["policy_instance_list"] = policy_instance_list
    
    return await make_request(f"{AAP_URL}/instance_groups/{instance_group_id}/", method="PATCH", json=data)

@function_tool
async def delete_instance_group(instance_group_id: int) -> Any:
    """Delete an instance group.
    
    Args:
        instance_group_id: ID of the instance group to delete
    """
    return await make_request(f"{AAP_URL}/instance_groups/{instance_group_id}/", method="DELETE")

# System Configuration API Functions
@function_tool
async def list_enabled_sso_endpoints() -> Any:
    """List enabled single-sign-on endpoints in Ansible Automation Platform.
    
    Returns information about configured SSO authentication methods
    and their endpoints.
    """
    return await make_request(f"{AAP_URL}/auth/")

@function_tool
async def get_sitewide_config() -> Any:
    """Return various sitewide configuration settings.
    
    Returns current system configuration including license information,
    feature flags, and system settings.
    """
    return await make_request(f"{AAP_URL}/config/")

@function_tool
async def install_license(license_data: str) -> Any:
    """Install or update an existing license.
    
    Args:
        license_data: License data to install
    """
    return await make_request(f"{AAP_URL}/config/", method="POST", data={"license_data": license_data})

@function_tool
async def delete_license() -> Any:
    """Delete an existing license."""
    return await make_request(f"{AAP_URL}/config/", method="DELETE")

@function_tool
async def attach_configuration(config_data: str) -> Any:
    """Attach configuration to the system.
    
    Args:
        config_data: Configuration data to attach
    """
    return await make_request(f"{AAP_URL}/config/attach/", method="POST", data={"config_data": config_data})

@function_tool
async def manage_subscriptions(subscription_data: str) -> Any:
    """Manage subscriptions.
    
    Args:
        subscription_data: Subscription data to manage
    """
    return await make_request(f"{AAP_URL}/config/subscriptions/", method="POST", data={"subscription_data": subscription_data})

@function_tool
async def get_mesh_visualizer() -> Any:
    """Get a list of all Receptor Nodes and their links.
    
    Returns information about the mesh network topology including
    all nodes and their connections.
    """
    return await make_request(f"{AAP_URL}/mesh_visualizer/")

@function_tool
async def ping_instance() -> Any:
    """Return some basic information about this instance.
    
    Returns basic system information including version, status,
    and instance details.
    """
    return await make_request(f"{AAP_URL}/ping/")

@function_tool
async def get_instance_group_instances(instance_group_id: int) -> Any:
    """Get all instances associated with an instance group.
    
    Args:
        instance_group_id: ID of the instance group
    """
    return await make_request(f"{AAP_URL}/instance_groups/{instance_group_id}/instances/")

@function_tool
async def add_instance_to_group(instance_group_id: int, instance_id: int) -> Any:
    """Add an instance to an instance group.
    
    Args:
        instance_group_id: ID of the instance group
        instance_id: ID of the instance to add
    """
    data = {"id": instance_id}
    return await make_request(f"{AAP_URL}/instance_groups/{instance_group_id}/instances/", method="POST", json=data)

@function_tool
async def get_instance_group_jobs(instance_group_id: int) -> Any:
    """Get all jobs associated with an instance group.
    
    Args:
        instance_group_id: ID of the instance group
    """
    return await make_request(f"{AAP_URL}/instance_groups/{instance_group_id}/jobs/")

# Settings API Functions
@function_tool
async def list_settings() -> Any:
    """List all settings in Ansible Automation Platform.
    
    Returns a list of all available system settings organized by categories.
    """
    return await make_request(f"{AAP_URL}/settings/")

@function_tool
async def list_settings_by_category(category: str) -> Any:
    """List settings for a specific category.
    
    Args:
        category: The settings category (e.g., 'system', 'ui', 'logging', etc.)
    """
    return await make_request(f"{AAP_URL}/settings/{category}/")

@function_tool
async def get_setting(category: str, setting_name: str) -> Any:
    """Retrieve a specific setting.
    
    Args:
        category: The settings category
        setting_name: The name of the specific setting
    """
    return await make_request(f"{AAP_URL}/settings/{category}/{setting_name}/")

@function_tool
async def update_setting(category: str, setting_name: str, value: Any) -> Any:
    """Update a specific setting.
    
    Args:
        category: The settings category (e.g., 'system', 'ui', 'logging', etc.)
        setting_name: The name of the setting to update
        value: The new value for the setting
    """
    return await make_request(f"{AAP_URL}/settings/{category}/{setting_name}/", method="PUT", data={"value": value})

# Dashboard API Functions
@function_tool
async def get_dashboard() -> Any:
    """Get dashboard information in Ansible Automation Platform.
    
    Returns overview information about the system including
    counts of various resources and system status.
    """
    return await make_request(f"{AAP_URL}/dashboard/")

@function_tool
async def get_dashboard_graphs() -> Any:
    """Get dashboard graphs information.
    
    Returns information about available dashboard graphs and their data.
    """
    return await make_request(f"{AAP_URL}/dashboard/graphs/")

@function_tool
async def get_jobs_graph() -> Any:
    """Get jobs graph data for dashboard.
    
    Returns job statistics and graph data for dashboard visualization.
    """
    return await make_request(f"{AAP_URL}/dashboard/graphs/jobs/")

@function_tool
async def get_inventory_graph() -> Any:
    """Get inventory graph data for dashboard.
    
    Returns inventory statistics and graph data for dashboard visualization.
    """
    return await make_request(f"{AAP_URL}/dashboard/graphs/inventory/")

@function_tool
async def get_projects_graph() -> Any:
    """Get projects graph data for dashboard.
    
    Returns project statistics and graph data for dashboard visualization.
    """
    return await make_request(f"{AAP_URL}/dashboard/graphs/projects/")

@function_tool
async def get_credential_types_graph() -> Any:
    """Get credential types graph data for dashboard.
    
    Returns credential type statistics and graph data for dashboard visualization.
    """
    return await make_request(f"{AAP_URL}/dashboard/graphs/credential_types/")

# Organizations API Functions
@function_tool
async def list_organizations() -> Any:
    """List all organizations in Ansible Automation Platform.
    
    Returns a list of all organizations including their basic information
    such as name, description, and creation details.
    """
    return await make_request(f"{AAP_URL}/organizations/")

@function_tool
async def create_organization(
    name: str,
    description: str = "",
    max_hosts: int = 0,
    custom_virtualenv: str = None,
    default_environment: int = None,
) -> Any:
    """Create a new organization.
    
    Args:
        name: Name of the organization
        description: Description of the organization
        max_hosts: Maximum number of hosts allowed in this organization
        custom_virtualenv: Custom virtual environment path
        default_environment: Default environment ID for this organization
    """
    data = {
        "name": name,
        "description": description,
        "max_hosts": max_hosts
    }
    if custom_virtualenv:
        data["custom_virtualenv"] = custom_virtualenv
    if default_environment:
        data["default_environment"] = default_environment
    
    return await make_request(f"{AAP_URL}/organizations/", method="POST", json=data)

@function_tool
async def get_organization(organization_id: int) -> Any:
    """Get details of a specific organization.
    
    Args:
        organization_id: ID of the organization to retrieve
    """
    return await make_request(f"{AAP_URL}/organizations/{organization_id}/")

@function_tool
async def update_organization(
    organization_id: int,
    name: str = None,
    description: str = None,
    max_hosts: int = None,
    custom_virtualenv: str = None,
    default_environment: int = None,
) -> Any:
    """Update an organization.
    
    Args:
        organization_id: ID of the organization to update
        name: New name for the organization
        description: New description for the organization
        max_hosts: New maximum number of hosts
        custom_virtualenv: New custom virtual environment path
        default_environment: New default environment ID
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if max_hosts is not None:
        data["max_hosts"] = max_hosts
    if custom_virtualenv is not None:
        data["custom_virtualenv"] = custom_virtualenv
    if default_environment is not None:
        data["default_environment"] = default_environment
    
    return await make_request(f"{AAP_URL}/organizations/{organization_id}/", method="PUT", json=data)

@function_tool
async def patch_organization(
    organization_id: int,
    name: str = None,
    description: str = None,
    max_hosts: int = None,
    custom_virtualenv: str = None,
    default_environment: int = None,
) -> Any:
    """Update an organization using PATCH method.
    
    Args:
        organization_id: ID of the organization to update
        name: New name for the organization
        description: New description for the organization
        max_hosts: New maximum number of hosts
        custom_virtualenv: New custom virtual environment path
        default_environment: New default environment ID
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if max_hosts is not None:
        data["max_hosts"] = max_hosts
    if custom_virtualenv is not None:
        data["custom_virtualenv"] = custom_virtualenv
    if default_environment is not None:
        data["default_environment"] = default_environment
    
    return await make_request(f"{AAP_URL}/organizations/{organization_id}/", method="PATCH", json=data)

@function_tool
async def delete_organization(organization_id: int) -> Any:
    """Delete an organization.
    
    Args:
        organization_id: ID of the organization to delete
    """
    return await make_request(f"{AAP_URL}/organizations/{organization_id}/", method="DELETE")

# Users API Functions
@function_tool
async def list_users() -> Any:
    """List all users in Ansible Automation Platform.
    
    Returns a list of all users including their basic information
    such as username, email, first name, last name, and roles.
    """
    return await make_request(f"{AAP_URL}/users/")

@function_tool
async def create_user(
    username: str,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    password: str = "",
    is_superuser: bool = False,
    is_system_auditor: bool = False,
) -> Any:
    """Create a new user.
    
    Args:
        username: Unique username for the user
        first_name: User's first name
        last_name: User's last name
        email: User's email address
        password: User's password
        is_superuser: Whether the user is a superuser
        is_system_auditor: Whether the user is a system auditor
    """
    data = {
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "password": password,
        "is_superuser": is_superuser,
        "is_system_auditor": is_system_auditor,
    }
    return await make_request(f"{AAP_URL}/users/", method="POST", json=data)

@function_tool
async def get_user(user_id: int) -> Any:
    """Get details of a specific user.
    
    Args:
        user_id: ID of the user to retrieve
    """
    return await make_request(f"{AAP_URL}/users/{user_id}/")

@function_tool
async def update_user(
    user_id: int,
    username: str = None,
    first_name: str = None,
    last_name: str = None,
    email: str = None,
    is_superuser: bool = None,
    is_system_auditor: bool = None,
) -> Any:
    """Update a user.
    
    Args:
        user_id: ID of the user to update
        username: New username (optional)
        first_name: New first name (optional)
        last_name: New last name (optional)
        email: New email address (optional)
        is_superuser: Whether the user is a superuser (optional)
        is_system_auditor: Whether the user is a system auditor (optional)
    """
    data = {}
    if username is not None:
        data["username"] = username
    if first_name is not None:
        data["first_name"] = first_name
    if last_name is not None:
        data["last_name"] = last_name
    if email is not None:
        data["email"] = email
    if is_superuser is not None:
        data["is_superuser"] = is_superuser
    if is_system_auditor is not None:
        data["is_system_auditor"] = is_system_auditor
    
    return await make_request(f"{AAP_URL}/users/{user_id}/", method="PUT", json=data)

@function_tool
async def delete_user(user_id: int) -> Any:
    """Delete a user.
    
    Args:
        user_id: ID of the user to delete
    """
    return await make_request(f"{AAP_URL}/users/{user_id}/", method="DELETE")

# Projects API Functions
@function_tool
async def list_projects() -> Any:
    """List all projects in Ansible Automation Platform.
    
    Returns a list of all projects including their basic information
    such as name, description, SCM type, and status.
    """
    return await make_request(f"{AAP_URL}/projects/")

@function_tool
async def create_project(
    name: str,
    description: str = "",
    scm_type: str = "",
    scm_url: str = "",
    scm_branch: str = "",
    scm_clean: bool = False,
    scm_delete_on_update: bool = False,
    scm_update_on_launch: bool = False,
    scm_update_cache_timeout: int = 0,
    scm_revision: str = "",
    organization: int = None,
    credential: int = None,
) -> Any:
    """Create a new project.
    
    Args:
        name: Name of the project
        description: Description of the project
        scm_type: SCM type (git, svn, archive), default is "", "" means manual
        scm_url: SCM URL for the project
        scm_branch: SCM branch to use
        scm_clean: Whether to clean the project before each update
        scm_delete_on_update: Whether to delete the project before each update
        scm_update_on_launch: Whether to update the project when launching a job
        scm_update_cache_timeout: Cache timeout for SCM updates
        scm_revision: SCM revision to use
        organization: ID of the organization this project belongs to
        credential: ID of the credential to use for SCM operations
    """
    data = {
        "name": name,
        "description": description,
        "scm_type": scm_type,
        "scm_url": scm_url,
        "scm_branch": scm_branch,
        "scm_clean": scm_clean,
        "scm_delete_on_update": scm_delete_on_update,
        "scm_update_on_launch": scm_update_on_launch,
        "scm_update_cache_timeout": scm_update_cache_timeout,
        "scm_revision": scm_revision,
    }
    if organization:
        data["organization"] = organization
    if credential:
        data["credential"] = credential
    
    return await make_request(f"{AAP_URL}/projects/", method="POST", json=data)

@function_tool
async def get_project(project_id: int) -> Any:
    """Get details of a specific project.
    
    Args:
        project_id: ID of the project to retrieve
    """
    return await make_request(f"{AAP_URL}/projects/{project_id}/")

@function_tool
async def update_project(
    project_id: int,
    name: str = None,
    description: str = None,
    scm_type: str = None,
    scm_url: str = None,
    scm_branch: str = None,
    scm_clean: bool = None,
    scm_delete_on_update: bool = None,
    scm_update_on_launch: bool = None,
    scm_update_cache_timeout: int = None,
    scm_revision: str = None,
    organization: int = None,
    credential: int = None,
) -> Any:
    """Update a project.
    
    Args:
        project_id: ID of the project to update
        name: Name of the project
        description: Description of the project
        scm_type: SCM type (git, svn, archive, manual)
        scm_url: SCM URL for the project
        scm_branch: SCM branch to use
        scm_clean: Whether to clean the project before each update
        scm_delete_on_update: Whether to delete the project before each update
        scm_update_on_launch: Whether to update the project when launching a job
        scm_update_cache_timeout: Cache timeout for SCM updates
        scm_revision: SCM revision to use
        organization: ID of the organization this project belongs to
        credential: ID of the credential to use for SCM operations
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if scm_type is not None:
        data["scm_type"] = scm_type
    if scm_url is not None:
        data["scm_url"] = scm_url
    if scm_branch is not None:
        data["scm_branch"] = scm_branch
    if scm_clean is not None:
        data["scm_clean"] = scm_clean
    if scm_delete_on_update is not None:
        data["scm_delete_on_update"] = scm_delete_on_update
    if scm_update_on_launch is not None:
        data["scm_update_on_launch"] = scm_update_on_launch
    if scm_update_cache_timeout is not None:
        data["scm_update_cache_timeout"] = scm_update_cache_timeout
    if scm_revision is not None:
        data["scm_revision"] = scm_revision
    if organization is not None:
        data["organization"] = organization
    if credential is not None:
        data["credential"] = credential
    
    return await make_request(f"{AAP_URL}/projects/{project_id}/", method="PUT", json=data)

@function_tool
async def delete_project(project_id: int) -> Any:
    """Delete a project.
    
    Args:
        project_id: ID of the project to delete
    """
    return await make_request(f"{AAP_URL}/projects/{project_id}/", method="DELETE")

# Credentials API Functions
@function_tool
async def list_credentials() -> Any:
    """List all credentials in Ansible Automation Platform.
    
    Returns a list of all credentials including their basic information
    such as name, credential type, and associated organization.
    """
    return await make_request(f"{AAP_URL}/credentials/")

@function_tool
async def create_credential(
    name: str,
    credential_type: int,
    organization: int = None,
    inputs: dict = None,
    description: str = "",
) -> Any:
    """Create a new credential.
    
    Args:
        name: Name of the credential
        credential_type: ID of the credential type
        organization: ID of the organization (optional)
        inputs: Dictionary of credential inputs (optional)
        description: Description of the credential (optional)
    """
    data = {
        "name": name,
        "credential_type": credential_type,
        "description": description
    }
    if organization:
        data["organization"] = organization
    if inputs:
        data["inputs"] = inputs
    
    return await make_request(f"{AAP_URL}/credentials/", method="POST", json=data)

@function_tool
async def get_credential(credential_id: int) -> Any:
    """Get details of a specific credential.
    
    Args:
        credential_id: ID of the credential to retrieve
    """
    return await make_request(f"{AAP_URL}/credentials/{credential_id}/")

@function_tool
async def update_credential(
    credential_id: int,
    name: str = None,
    credential_type: int = None,
    organization: int = None,
    inputs: dict = None,
    description: str = None,
) -> Any:
    """Update a credential.
    
    Args:
        credential_id: ID of the credential to update
        name: New name for the credential (optional)
        credential_type: New credential type ID (optional)
        organization: New organization ID (optional)
        inputs: New credential inputs (optional)
        description: New description (optional)
    """
    data = {}
    if name is not None:
        data["name"] = name
    if credential_type is not None:
        data["credential_type"] = credential_type
    if organization is not None:
        data["organization"] = organization
    if inputs is not None:
        data["inputs"] = inputs
    if description is not None:
        data["description"] = description
    
    return await make_request(f"{AAP_URL}/credentials/{credential_id}/", method="PUT", json=data)

@function_tool
async def patch_credential(
    credential_id: int,
    name: str = None,
    credential_type: int = None,
    organization: int = None,
    inputs: dict = None,
    description: str = None,
) -> Any:
    """Update a credential using PATCH method.
    
    Args:
        credential_id: ID of the credential to update
        name: New name for the credential (optional)
        credential_type: New credential type ID (optional)
        organization: New organization ID (optional)
        inputs: New credential inputs (optional)
        description: New description (optional)
    """
    data = {}
    if name is not None:
        data["name"] = name
    if credential_type is not None:
        data["credential_type"] = credential_type
    if organization is not None:
        data["organization"] = organization
    if inputs is not None:
        data["inputs"] = inputs
    if description is not None:
        data["description"] = description
    
    return await make_request(f"{AAP_URL}/credentials/{credential_id}/", method="PATCH", json=data)

@function_tool
async def delete_credential(credential_id: int) -> Any:
    """Delete a credential.
    
    Args:
        credential_id: ID of the credential to delete
    """
    return await make_request(f"{AAP_URL}/credentials/{credential_id}/", method="DELETE")

# Inventories API Functions
@function_tool
async def list_inventories() -> Any:
    """List all inventories in Ansible Automation Platform.
    
    Returns a list of all inventories including their basic information
    such as name, description, organization, and type.
    """
    return await make_request(f"{AAP_URL}/inventories/")

@function_tool
async def create_inventory(
    name: str,
    description: str = "",
    organization: int = None,
    variables: str = "",
    host_filter: str = "",
    insights_credential: int = None,
    update_on_launch: bool = False,
) -> Any:
    """Create a new inventory.
    
    Args:
        name: Name of the inventory
        description: Description of the inventory
        organization: ID of the organization this inventory belongs to
        variables: Variables in JSON format
        host_filter: Filter that will be applied to the hosts of this inventory
        insights_credential: ID of the credential to use for insights
        update_on_launch: Update inventory on launch
    """
    data = {
        "name": name,
        "description": description,
        "variables": variables,
        "host_filter": host_filter,
        "update_on_launch": update_on_launch
    }
    if organization:
        data["organization"] = organization
    if insights_credential:
        data["insights_credential"] = insights_credential
    
    return await make_request(f"{AAP_URL}/inventories/", method="POST", json=data)

@function_tool
async def get_inventory(inventory_id: int) -> Any:
    """Get details of a specific inventory.
    
    Args:
        inventory_id: ID of the inventory to retrieve
    """
    return await make_request(f"{AAP_URL}/inventories/{inventory_id}/")

@function_tool
async def update_inventory(
    inventory_id: int,
    name: str = None,
    description: str = None,
    organization: int = None,
    variables: str = None,
    host_filter: str = None,
    insights_credential: int = None,
    update_on_launch: bool = None,
) -> Any:
    """Update an inventory.
    
    Args:
        inventory_id: ID of the inventory to update
        name: Name of the inventory
        description: Description of the inventory
        organization: ID of the organization this inventory belongs to
        variables: Variables in JSON format
        host_filter: Filter that will be applied to the hosts of this inventory
        insights_credential: ID of the credential to use for insights
        update_on_launch: Update inventory on launch
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if organization is not None:
        data["organization"] = organization
    if variables is not None:
        data["variables"] = variables
    if host_filter is not None:
        data["host_filter"] = host_filter
    if insights_credential is not None:
        data["insights_credential"] = insights_credential
    if update_on_launch is not None:
        data["update_on_launch"] = update_on_launch
    
    return await make_request(f"{AAP_URL}/inventories/{inventory_id}/", method="PUT", json=data)

@function_tool
async def patch_inventory(
    inventory_id: int,
    name: str = None,
    description: str = None,
    organization: int = None,
    variables: str = None,
    host_filter: str = None,
    insights_credential: int = None,
    update_on_launch: bool = None,
) -> Any:
    """Update an inventory (PATCH method).
    
    Args:
        inventory_id: ID of the inventory to update
        name: Name of the inventory
        description: Description of the inventory
        organization: ID of the organization this inventory belongs to
        variables: Variables in JSON format
        host_filter: Filter that will be applied to the hosts of this inventory
        insights_credential: ID of the credential to use for insights
        update_on_launch: Update inventory on launch
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if organization is not None:
        data["organization"] = organization
    if variables is not None:
        data["variables"] = variables
    if host_filter is not None:
        data["host_filter"] = host_filter
    if insights_credential is not None:
        data["insights_credential"] = insights_credential
    if update_on_launch is not None:
        data["update_on_launch"] = update_on_launch
    
    return await make_request(f"{AAP_URL}/inventories/{inventory_id}/", method="PATCH", json=data)

@function_tool
async def delete_inventory(inventory_id: int) -> Any:
    """Delete an inventory.
    
    Args:
        inventory_id: ID of the inventory to delete
    """
    return await make_request(f"{AAP_URL}/inventories/{inventory_id}/", method="DELETE")

# Job Templates API Functions
@function_tool
async def list_job_templates() -> Any:
    """List all job templates in Ansible Automation Platform.
    
    Returns a list of all job templates including their basic information
    such as name, description, project, inventory, and playbook.
    """
    return await make_request(f"{AAP_URL}/job_templates/")

@function_tool
async def create_job_template(
    name: str,
    job_type: str = "run",
    project: int = None,
    inventory: int = None,
    playbook: str = "",
    credential: int = None,
    vault_credential: int = None,
    description: str = "",
    extra_vars: str = "",
    limit: str = "",
    tags: str = "",
    skip_tags: str = "",
    start_at_task: str = "",
    timeout: int = 0,
    use_fact_cache: bool = False,
    host_config_key: str = "",
    ask_diff_mode_on_launch: bool = False,
    ask_variables_on_launch: bool = False,
    ask_limit_on_launch: bool = False,
    ask_tags_on_launch: bool = False,
    ask_skip_tags_on_launch: bool = False,
    ask_job_type_on_launch: bool = False,
    ask_verbosity_on_launch: bool = False,
    ask_inventory_on_launch: bool = False,
    ask_credential_on_launch: bool = False,
    survey_enabled: bool = False,
    become_enabled: bool = False,
    diff_mode: bool = False,
    allow_simultaneous: bool = False,
    custom_virtualenv: str = None,
    job_slice_count: int = 1,
    webhook_service: str = "",
    webhook_credential: int = None,
) -> Any:
    """Create a new job template.
    
    Args:
        name: Name of the job template
        job_type: Type of job (run, check, scan)
        project: ID of the associated project
        inventory: ID of the associated inventory
        playbook: Path to the playbook file
        credential: ID of the associated credential
        vault_credential: ID of the vault credential
        description: Description of the job template
        extra_vars: Extra variables in YAML format
        limit: Host limit pattern
        tags: Tags to run
        skip_tags: Tags to skip
        start_at_task: Task to start at
        timeout: Job timeout in seconds
        use_fact_cache: Whether to use fact cache
        host_config_key: Host configuration key
        ask_diff_mode_on_launch: Ask for diff mode on launch
        ask_variables_on_launch: Ask for variables on launch
        ask_limit_on_launch: Ask for limit on launch
        ask_tags_on_launch: Ask for tags on launch
        ask_skip_tags_on_launch: Ask for skip tags on launch
        ask_job_type_on_launch: Ask for job type on launch
        ask_verbosity_on_launch: Ask for verbosity on launch
        ask_inventory_on_launch: Ask for inventory on launch
        ask_credential_on_launch: Ask for credential on launch
        survey_enabled: Enable survey
        become_enabled: Enable privilege escalation
        diff_mode: Enable diff mode
        allow_simultaneous: Allow simultaneous jobs
        custom_virtualenv: Custom virtual environment path
        job_slice_count: Number of job slices
        webhook_service: Webhook service type
        webhook_credential: ID of webhook credential
    """
    data = {
        "name": name,
        "job_type": job_type,
        "playbook": playbook,
        "description": description,
        "extra_vars": extra_vars,
        "limit": limit,
        "tags": tags,
        "skip_tags": skip_tags,
        "start_at_task": start_at_task,
        "timeout": timeout,
        "use_fact_cache": use_fact_cache,
        "host_config_key": host_config_key,
        "ask_diff_mode_on_launch": ask_diff_mode_on_launch,
        "ask_variables_on_launch": ask_variables_on_launch,
        "ask_limit_on_launch": ask_limit_on_launch,
        "ask_tags_on_launch": ask_tags_on_launch,
        "ask_skip_tags_on_launch": ask_skip_tags_on_launch,
        "ask_job_type_on_launch": ask_job_type_on_launch,
        "ask_verbosity_on_launch": ask_verbosity_on_launch,
        "ask_inventory_on_launch": ask_inventory_on_launch,
        "ask_credential_on_launch": ask_credential_on_launch,
        "survey_enabled": survey_enabled,
        "become_enabled": become_enabled,
        "diff_mode": diff_mode,
        "allow_simultaneous": allow_simultaneous,
        "job_slice_count": job_slice_count,
        "webhook_service": webhook_service,
    }
    
    if project:
        data["project"] = project
    if inventory:
        data["inventory"] = inventory
    if credential:
        data["credential"] = credential
    if vault_credential:
        data["vault_credential"] = vault_credential
    if custom_virtualenv:
        data["custom_virtualenv"] = custom_virtualenv
    if webhook_credential:
        data["webhook_credential"] = webhook_credential
    
    return await make_request(f"{AAP_URL}/job_templates/", method="POST", json=data)

@function_tool
async def get_job_template(job_template_id: int) -> Any:
    """Get details of a specific job template.
    
    Args:
        job_template_id: ID of the job template
    """
    return await make_request(f"{AAP_URL}/job_templates/{job_template_id}/")

@function_tool
async def update_job_template(job_template_id: int, **kwargs) -> Any:
    """Update a job template.
    
    Args:
        job_template_id: ID of the job template to update
        **kwargs: Fields to update
    """
    return await make_request(f"{AAP_URL}/job_templates/{job_template_id}/", method="PUT", data=kwargs)

@function_tool
async def patch_job_template(job_template_id: int, **kwargs) -> Any:
    """Update a job template (partial update).
    
    Args:
        job_template_id: ID of the job template to update
        **kwargs: Fields to update
    """
    return await make_request(f"{AAP_URL}/job_templates/{job_template_id}/", method="PATCH", data=kwargs)

@function_tool
async def delete_job_template(job_template_id: int) -> Any:
    """Delete a job template.
    
    Args:
        job_template_id: ID of the job template to delete
    """
    return await make_request(f"{AAP_URL}/job_templates/{job_template_id}/", method="DELETE")

# Jobs API Functions
@function_tool
async def list_jobs() -> Any:
    """List all jobs in Ansible Automation Platform.
    
    Returns a list of all jobs including their basic information
    such as name, status, job template, and execution details.
    """
    return await make_request(f"{AAP_URL}/jobs/")

@function_tool
async def create_job(
    job_template: int,
    name: str = "",
    description: str = "",
    extra_vars: str = "",
    inventory: int = None,
    project: int = None,
    playbook: str = "",
    credential: int = None,
    limit: str = "",
    tags: str = "",
    skip_tags: str = "",
    job_type: str = "run",
    verbosity: int = 0,
    diff_mode: bool = False,
    allow_simultaneous: bool = False,
    scm_branch: str = "",
    timeout: int = 0,
    forks: int = 0,
    job_slice_count: int = 1,
    webhook_service: str = "",
    webhook_credential: int = None,
    webhook_headers: str = "",
) -> Any:
    """Create a new job.
    
    Args:
        job_template: ID of the job template to use
        name: Name of the job
        description: Description of the job
        extra_vars: Extra variables for the job
        inventory: ID of the inventory to use
        project: ID of the project to use
        playbook: Playbook to run
        credential: ID of the credential to use
        limit: Host limit for the job
        tags: Tags to run
        skip_tags: Tags to skip
        job_type: Type of job (run, check, scan)
        verbosity: Verbosity level (0-4)
        diff_mode: Whether to show differences
        allow_simultaneous: Whether to allow simultaneous runs
        scm_branch: SCM branch to use
        timeout: Job timeout in seconds
        forks: Number of forks
        job_slice_count: Number of job slices
        webhook_service: Webhook service to use
        webhook_credential: ID of the webhook credential
        webhook_headers: Webhook headers
    """
    data = {
        "job_template": job_template,
        "name": name,
        "description": description,
        "extra_vars": extra_vars,
        "inventory": inventory,
        "project": project,
        "playbook": playbook,
        "credential": credential,
        "limit": limit,
        "tags": tags,
        "skip_tags": skip_tags,
        "job_type": job_type,
        "verbosity": verbosity,
        "diff_mode": diff_mode,
        "allow_simultaneous": allow_simultaneous,
        "scm_branch": scm_branch,
        "timeout": timeout,
        "forks": forks,
        "job_slice_count": job_slice_count,
        "webhook_service": webhook_service,
        "webhook_credential": webhook_credential,
        "webhook_headers": webhook_headers,
    }
    return await make_request(f"{AAP_URL}/jobs/", method="POST", json=data)

@function_tool
async def get_job(job_id: int) -> Any:
    """Get details of a specific job.
    
    Args:
        job_id: ID of the job to retrieve
    """
    return await make_request(f"{AAP_URL}/jobs/{job_id}/")

@function_tool
async def update_job(
    job_id: int,
    name: str = None,
    description: str = None,
    extra_vars: str = None,
    inventory: int = None,
    project: int = None,
    playbook: str = None,
    credential: int = None,
    limit: str = None,
    tags: str = None,
    skip_tags: str = None,
    job_type: str = None,
    verbosity: int = None,
    diff_mode: bool = None,
    allow_simultaneous: bool = None,
    scm_branch: str = None,
    timeout: int = None,
    forks: int = None,
    job_slice_count: int = None,
    webhook_service: str = None,
    webhook_credential: int = None,
    webhook_headers: str = None,
) -> Any:
    """Update a job.
    
    Args:
        job_id: ID of the job to update
        name: Name of the job
        description: Description of the job
        extra_vars: Extra variables for the job
        inventory: ID of the inventory to use
        project: ID of the project to use
        playbook: Playbook to run
        credential: ID of the credential to use
        limit: Host limit for the job
        tags: Tags to run
        skip_tags: Tags to skip
        job_type: Type of job (run, check, scan)
        verbosity: Verbosity level (0-4)
        diff_mode: Whether to show differences
        allow_simultaneous: Whether to allow simultaneous runs
        scm_branch: SCM branch to use
        timeout: Job timeout in seconds
        forks: Number of forks
        job_slice_count: Number of job slices
        webhook_service: Webhook service to use
        webhook_credential: ID of the webhook credential
        webhook_headers: Webhook headers
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if extra_vars is not None:
        data["extra_vars"] = extra_vars
    if inventory is not None:
        data["inventory"] = inventory
    if project is not None:
        data["project"] = project
    if playbook is not None:
        data["playbook"] = playbook
    if credential is not None:
        data["credential"] = credential
    if limit is not None:
        data["limit"] = limit
    if tags is not None:
        data["tags"] = tags
    if skip_tags is not None:
        data["skip_tags"] = skip_tags
    if job_type is not None:
        data["job_type"] = job_type
    if verbosity is not None:
        data["verbosity"] = verbosity
    if diff_mode is not None:
        data["diff_mode"] = diff_mode
    if allow_simultaneous is not None:
        data["allow_simultaneous"] = allow_simultaneous
    if scm_branch is not None:
        data["scm_branch"] = scm_branch
    if timeout is not None:
        data["timeout"] = timeout
    if forks is not None:
        data["forks"] = forks
    if job_slice_count is not None:
        data["job_slice_count"] = job_slice_count
    if webhook_service is not None:
        data["webhook_service"] = webhook_service
    if webhook_credential is not None:
        data["webhook_credential"] = webhook_credential
    if webhook_headers is not None:
        data["webhook_headers"] = webhook_headers
    
    return await make_request(f"{AAP_URL}/jobs/{job_id}/", method="PUT", json=data)

@function_tool
async def delete_job(job_id: int) -> Any:
    """Delete a job.
    
    Args:
        job_id: ID of the job to delete
    """
    return await make_request(f"{AAP_URL}/jobs/{job_id}/", method="DELETE")

# Workflow Job Templates API Functions
@function_tool
async def list_workflow_job_templates() -> Any:
    """List all workflow job templates in Ansible Automation Platform.
    
    Returns a list of all workflow job templates including their basic information
    such as name, description, and workflow configuration.
    """
    return await make_request(f"{AAP_URL}/workflow_job_templates/")

@function_tool
async def create_workflow_job_template(
    name: str,
    description: str = "",
    organization: int = None,
    extra_vars: str = "",
    survey_enabled: bool = False,
    allow_simultaneous: bool = False,
    ask_variables_on_launch: bool = False,
    ask_inventory_on_launch: bool = False,
    ask_credential_on_launch: bool = False,
    ask_scm_branch_on_launch: bool = False,
    ask_limit_on_launch: bool = False,
    ask_tags_on_launch: bool = False,
    ask_skip_tags_on_launch: bool = False,
    ask_job_type_on_launch: bool = False,
    ask_verbosity_on_launch: bool = False,
    ask_diff_mode_on_launch: bool = False,
    webhook_service: str = "",
    webhook_credential: int = None,
) -> Any:
    """Create a new workflow job template.
    
    Args:
        name: Name of the workflow job template
        description: Description of the workflow job template
        organization: ID of the organization this template belongs to
        extra_vars: Extra variables for the workflow
        survey_enabled: Whether to enable survey for this template
        allow_simultaneous: Whether to allow simultaneous executions
        ask_variables_on_launch: Whether to ask for variables on launch
        ask_inventory_on_launch: Whether to ask for inventory on launch
        ask_credential_on_launch: Whether to ask for credential on launch
        ask_scm_branch_on_launch: Whether to ask for SCM branch on launch
        ask_limit_on_launch: Whether to ask for limit on launch
        ask_tags_on_launch: Whether to ask for tags on launch
        ask_skip_tags_on_launch: Whether to ask for skip tags on launch
        ask_job_type_on_launch: Whether to ask for job type on launch
        ask_verbosity_on_launch: Whether to ask for verbosity on launch
        ask_diff_mode_on_launch: Whether to ask for diff mode on launch
        webhook_service: Webhook service configuration
        webhook_credential: ID of the webhook credential
    """
    data = {
        "name": name,
        "description": description,
        "extra_vars": extra_vars,
        "survey_enabled": survey_enabled,
        "allow_simultaneous": allow_simultaneous,
        "ask_variables_on_launch": ask_variables_on_launch,
        "ask_inventory_on_launch": ask_inventory_on_launch,
        "ask_credential_on_launch": ask_credential_on_launch,
        "ask_scm_branch_on_launch": ask_scm_branch_on_launch,
        "ask_limit_on_launch": ask_limit_on_launch,
        "ask_tags_on_launch": ask_tags_on_launch,
        "ask_skip_tags_on_launch": ask_skip_tags_on_launch,
        "ask_job_type_on_launch": ask_job_type_on_launch,
        "ask_verbosity_on_launch": ask_verbosity_on_launch,
        "ask_diff_mode_on_launch": ask_diff_mode_on_launch,
        "webhook_service": webhook_service,
    }
    if organization:
        data["organization"] = organization
    if webhook_credential:
        data["webhook_credential"] = webhook_credential
    
    return await make_request(f"{AAP_URL}/workflow_job_templates/", method="POST", json=data)

@function_tool
async def get_workflow_job_template(workflow_job_template_id: int) -> Any:
    """Get details of a specific workflow job template.
    
    Args:
        workflow_job_template_id: ID of the workflow job template
    """
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/")

@function_tool
async def update_workflow_job_template(
    workflow_job_template_id: int,
    name: str = None,
    description: str = None,
    organization: int = None,
    extra_vars: str = None,
    survey_enabled: bool = None,
    allow_simultaneous: bool = None,
    ask_variables_on_launch: bool = None,
    ask_inventory_on_launch: bool = None,
    ask_credential_on_launch: bool = None,
    ask_scm_branch_on_launch: bool = None,
    ask_limit_on_launch: bool = None,
    ask_tags_on_launch: bool = None,
    ask_skip_tags_on_launch: bool = None,
    ask_job_type_on_launch: bool = None,
    ask_verbosity_on_launch: bool = None,
    ask_diff_mode_on_launch: bool = None,
    webhook_service: str = None,
    webhook_credential: int = None,
) -> Any:
    """Update a workflow job template.
    
    Args:
        workflow_job_template_id: ID of the workflow job template to update
        name: New name for the workflow job template
        description: New description for the workflow job template
        organization: ID of the organization this template belongs to
        extra_vars: Extra variables for the workflow
        survey_enabled: Whether to enable survey for this template
        allow_simultaneous: Whether to allow simultaneous executions
        ask_variables_on_launch: Whether to ask for variables on launch
        ask_inventory_on_launch: Whether to ask for inventory on launch
        ask_credential_on_launch: Whether to ask for credential on launch
        ask_scm_branch_on_launch: Whether to ask for SCM branch on launch
        ask_limit_on_launch: Whether to ask for limit on launch
        ask_tags_on_launch: Whether to ask for tags on launch
        ask_skip_tags_on_launch: Whether to ask for skip tags on launch
        ask_job_type_on_launch: Whether to ask for job type on launch
        ask_verbosity_on_launch: Whether to ask for verbosity on launch
        ask_diff_mode_on_launch: Whether to ask for diff mode on launch
        webhook_service: Webhook service configuration
        webhook_credential: ID of the webhook credential
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if organization is not None:
        data["organization"] = organization
    if extra_vars is not None:
        data["extra_vars"] = extra_vars
    if survey_enabled is not None:
        data["survey_enabled"] = survey_enabled
    if allow_simultaneous is not None:
        data["allow_simultaneous"] = allow_simultaneous
    if ask_variables_on_launch is not None:
        data["ask_variables_on_launch"] = ask_variables_on_launch
    if ask_inventory_on_launch is not None:
        data["ask_inventory_on_launch"] = ask_inventory_on_launch
    if ask_credential_on_launch is not None:
        data["ask_credential_on_launch"] = ask_credential_on_launch
    if ask_scm_branch_on_launch is not None:
        data["ask_scm_branch_on_launch"] = ask_scm_branch_on_launch
    if ask_limit_on_launch is not None:
        data["ask_limit_on_launch"] = ask_limit_on_launch
    if ask_tags_on_launch is not None:
        data["ask_tags_on_launch"] = ask_tags_on_launch
    if ask_skip_tags_on_launch is not None:
        data["ask_skip_tags_on_launch"] = ask_skip_tags_on_launch
    if ask_job_type_on_launch is not None:
        data["ask_job_type_on_launch"] = ask_job_type_on_launch
    if ask_verbosity_on_launch is not None:
        data["ask_verbosity_on_launch"] = ask_verbosity_on_launch
    if ask_diff_mode_on_launch is not None:
        data["ask_diff_mode_on_launch"] = ask_diff_mode_on_launch
    if webhook_service is not None:
        data["webhook_service"] = webhook_service
    if webhook_credential is not None:
        data["webhook_credential"] = webhook_credential
    
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/", method="PUT", json=data)

@function_tool
async def delete_workflow_job_template(workflow_job_template_id: int) -> Any:
    """Delete a workflow job template.
    
    Args:
        workflow_job_template_id: ID of the workflow job template to delete
    """
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/", method="DELETE")

@function_tool
async def patch_setting(category: str, setting_name: str, value: Any) -> Any:
    """Update a specific setting using PATCH method.
    
    Args:
        category: The settings category
        setting_name: The name of the specific setting
        value: The new value for the setting
    """
    return await make_request(
        f"{AAP_URL}/settings/{category}/{setting_name}/",
        method="PATCH",
        data={"value": value}
    )

@function_tool
async def list_workflow_jobs() -> Any:
    """List all workflow jobs in Ansible Automation Platform.
    
    Returns a list of all workflow jobs including their basic information
    such as name, status, workflow job template, and execution details.
    """
    return await make_request(f"{AAP_URL}/workflow_jobs/")

@function_tool
async def create_workflow_job(
    workflow_job_template: int,
    extra_vars: str = "",
    inventory: int = None,
    scm_branch: str = "",
    limit: str = "",
    job_tags: str = "",
    skip_tags: str = "",
    verbosity: int = 0,
    timeout: int = 0,
) -> Any:
    """Create a new workflow job.
    
    Args:
        workflow_job_template: ID of the workflow job template to use
        extra_vars: Extra variables for the workflow job
        inventory: ID of the inventory to use
        scm_branch: SCM branch to use
        limit: Host limit for the job
        job_tags: Tags to run
        skip_tags: Tags to skip
        verbosity: Verbosity level
        timeout: Job timeout in seconds
    """
    data = {
        "workflow_job_template": workflow_job_template,
        "extra_vars": extra_vars,
        "inventory": inventory,
        "scm_branch": scm_branch,
        "limit": limit,
        "job_tags": job_tags,
        "skip_tags": skip_tags,
        "verbosity": verbosity,
        "timeout": timeout,
    }
    return await make_request(f"{AAP_URL}/workflow_jobs/", method="POST", json=data)

@function_tool
async def get_workflow_job(workflow_job_id: int) -> Any:
    """Get details of a specific workflow job.
    
    Args:
        workflow_job_id: ID of the workflow job to retrieve
    """
    return await make_request(f"{AAP_URL}/workflow_jobs/{workflow_job_id}/")

@function_tool
async def update_workflow_job(
    workflow_job_id: int,
    extra_vars: str = None,
    inventory: int = None,
    scm_branch: str = None,
    limit: str = None,
    job_tags: str = None,
    skip_tags: str = None,
    verbosity: int = None,
    timeout: int = None,
) -> Any:
    """Update a workflow job.
    
    Args:
        workflow_job_id: ID of the workflow job to update
        extra_vars: Extra variables for the workflow job
        inventory: ID of the inventory to use
        scm_branch: SCM branch to use
        limit: Host limit for the job
        job_tags: Tags to run
        skip_tags: Tags to skip
        verbosity: Verbosity level
        timeout: Job timeout in seconds
    """
    data = {}
    if extra_vars is not None:
        data["extra_vars"] = extra_vars
    if inventory is not None:
        data["inventory"] = inventory
    if scm_branch is not None:
        data["scm_branch"] = scm_branch
    if limit is not None:
        data["limit"] = limit
    if job_tags is not None:
        data["job_tags"] = job_tags
    if skip_tags is not None:
        data["skip_tags"] = skip_tags
    if verbosity is not None:
        data["verbosity"] = verbosity
    if timeout is not None:
        data["timeout"] = timeout
    return await make_request(f"{AAP_URL}/workflow_jobs/{workflow_job_id}/", method="PUT", json=data)

@function_tool
async def patch_workflow_job(
    workflow_job_id: int,
    extra_vars: str = None,
    inventory: int = None,
    scm_branch: str = None,
    limit: str = None,
    job_tags: str = None,
    skip_tags: str = None,
    verbosity: int = None,
    timeout: int = None,
) -> Any:
    """Partially update a workflow job.
    
    Args:
        workflow_job_id: ID of the workflow job to update
        extra_vars: Extra variables for the workflow job
        inventory: ID of the inventory to use
        scm_branch: SCM branch to use
        limit: Host limit for the job
        job_tags: Tags to run
        skip_tags: Tags to skip
        verbosity: Verbosity level
        timeout: Job timeout in seconds
    """
    data = {}
    if extra_vars is not None:
        data["extra_vars"] = extra_vars
    if inventory is not None:
        data["inventory"] = inventory
    if scm_branch is not None:
        data["scm_branch"] = scm_branch
    if limit is not None:
        data["limit"] = limit
    if job_tags is not None:
        data["job_tags"] = job_tags
    if skip_tags is not None:
        data["skip_tags"] = skip_tags
    if verbosity is not None:
        data["verbosity"] = verbosity
    if timeout is not None:
        data["timeout"] = timeout
    return await make_request(f"{AAP_URL}/workflow_jobs/{workflow_job_id}/", method="PATCH", json=data)

@function_tool
async def delete_workflow_job(workflow_job_id: int) -> Any:
    """Delete a workflow job.
    
    Args:
        workflow_job_id: ID of the workflow job to delete
    """
    return await make_request(f"{AAP_URL}/workflow_jobs/{workflow_job_id}/", method="DELETE")

# Workflow Job Template Nodes API Functions
@function_tool
async def list_workflow_job_template_nodes() -> Any:
    """List all workflow job template nodes in Ansible Automation Platform.
    
    Returns a list of all workflow job template nodes including their basic information
    such as workflow job template, job template, and node configuration.
    """
    return await make_request(f"{AAP_URL}/workflow_job_template_nodes/")

@function_tool
async def create_workflow_job_template_node(
    workflow_job_template: int,
    job_template: int = None,
    workflow_job_template_node: int = None,
    unified_job_template: int = None,
    success_nodes: list = None,
    failure_nodes: list = None,
    always_nodes: list = None,
    identifier: str = "",
    all_parents_must_converge: bool = False,
) -> Any:
    """Create a new workflow job template node.
    
    Args:
        workflow_job_template: ID of the workflow job template
        job_template: ID of the job template to execute
        workflow_job_template_node: ID of the parent workflow job template node
        unified_job_template: ID of the unified job template
        success_nodes: List of node IDs to execute on success
        failure_nodes: List of node IDs to execute on failure
        always_nodes: List of node IDs to always execute
        identifier: Unique identifier for the node
        all_parents_must_converge: Whether all parents must converge
    """
    data = {
        "workflow_job_template": workflow_job_template,
        "identifier": identifier,
        "all_parents_must_converge": all_parents_must_converge,
    }
    if job_template:
        data["job_template"] = job_template
    if workflow_job_template_node:
        data["workflow_job_template_node"] = workflow_job_template_node
    if unified_job_template:
        data["unified_job_template"] = unified_job_template
    if success_nodes:
        data["success_nodes"] = success_nodes
    if failure_nodes:
        data["failure_nodes"] = failure_nodes
    if always_nodes:
        data["always_nodes"] = always_nodes
    
    return await make_request(f"{AAP_URL}/workflow_job_template_nodes/", method="POST", json=data)

@function_tool
async def get_workflow_job_template_node(workflow_job_template_node_id: int) -> Any:
    """Get details of a specific workflow job template node.
    
    Args:
        workflow_job_template_node_id: ID of the workflow job template node
    """
    return await make_request(f"{AAP_URL}/workflow_job_template_nodes/{workflow_job_template_node_id}/")

@function_tool
async def update_workflow_job_template_node(
    workflow_job_template_node_id: int,
    job_template: int = None,
    workflow_job_template_node: int = None,
    unified_job_template: int = None,
    success_nodes: list = None,
    failure_nodes: list = None,
    always_nodes: list = None,
    identifier: str = "",
    all_parents_must_converge: bool = None,
) -> Any:
    """Update a workflow job template node.
    
    Args:
        workflow_job_template_node_id: ID of the workflow job template node to update
        job_template: ID of the job template to execute
        workflow_job_template_node: ID of the parent workflow job template node
        unified_job_template: ID of the unified job template
        success_nodes: List of node IDs to execute on success
        failure_nodes: List of node IDs to execute on failure
        always_nodes: List of node IDs to always execute
        identifier: Unique identifier for the node
        all_parents_must_converge: Whether all parents must converge
    """
    data = {}
    if job_template is not None:
        data["job_template"] = job_template
    if workflow_job_template_node is not None:
        data["workflow_job_template_node"] = workflow_job_template_node
    if unified_job_template is not None:
        data["unified_job_template"] = unified_job_template
    if success_nodes is not None:
        data["success_nodes"] = success_nodes
    if failure_nodes is not None:
        data["failure_nodes"] = failure_nodes
    if always_nodes is not None:
        data["always_nodes"] = always_nodes
    if identifier:
        data["identifier"] = identifier
    if all_parents_must_converge is not None:
        data["all_parents_must_converge"] = all_parents_must_converge
    
    return await make_request(f"{AAP_URL}/workflow_job_template_nodes/{workflow_job_template_node_id}/", method="PUT", json=data)

@function_tool
async def patch_workflow_job_template_node(
    workflow_job_template_node_id: int,
    job_template: int = None,
    workflow_job_template_node: int = None,
    unified_job_template: int = None,
    success_nodes: list = None,
    failure_nodes: list = None,
    always_nodes: list = None,
    identifier: str = None,
    all_parents_must_converge: bool = None,
) -> Any:
    """Update a workflow job template node (partial update).
    
    Args:
        workflow_job_template_node_id: ID of the workflow job template node to update
        job_template: ID of the job template to execute
        workflow_job_template_node: ID of the parent workflow job template node
        unified_job_template: ID of the unified job template
        success_nodes: List of node IDs to execute on success
        failure_nodes: List of node IDs to execute on failure
        always_nodes: List of node IDs to always execute
        identifier: Unique identifier for the node
        all_parents_must_converge: Whether all parents must converge
    """
    data = {}
    if job_template is not None:
        data["job_template"] = job_template
    if workflow_job_template_node is not None:
        data["workflow_job_template_node"] = workflow_job_template_node
    if unified_job_template is not None:
        data["unified_job_template"] = unified_job_template
    if success_nodes is not None:
        data["success_nodes"] = success_nodes
    if failure_nodes is not None:
        data["failure_nodes"] = failure_nodes
    if always_nodes is not None:
        data["always_nodes"] = always_nodes
    if identifier is not None:
        data["identifier"] = identifier
    if all_parents_must_converge is not None:
        data["all_parents_must_converge"] = all_parents_must_converge
    
    return await make_request(f"{AAP_URL}/workflow_job_template_nodes/{workflow_job_template_node_id}/", method="PATCH", json=data)

@function_tool
async def delete_workflow_job_template_node(workflow_job_template_node_id: int) -> Any:
    """Delete a workflow job template node.
    
    Args:
        workflow_job_template_node_id: ID of the workflow job template node to delete
    """
    return await make_request(f"{AAP_URL}/workflow_job_template_nodes/{workflow_job_template_node_id}/", method="DELETE")

# Workflow Job Nodes API Functions
@function_tool
async def list_workflow_job_nodes() -> Any:
    """List all workflow job nodes in Ansible Automation Platform.
    
    Returns a list of all workflow job nodes including their basic information
    such as workflow job, job, and node status.
    """
    return await make_request(f"{AAP_URL}/workflow_job_nodes/")

@function_tool
async def create_workflow_job_node(
    workflow_job: int,
    job: int = None,
    job_template: int = None,
    workflow_job_template_node: int = None,
    extra_data: dict = None,
) -> Any:
    """Create a new workflow job node.
    
    Args:
        workflow_job: ID of the workflow job
        job: ID of the associated job
        job_template: ID of the job template
        workflow_job_template_node: ID of the workflow job template node
        extra_data: Additional data for the node
    """
    data = {
        "workflow_job": workflow_job,
        "extra_data": extra_data or {}
    }
    if job:
        data["job"] = job
    if job_template:
        data["job_template"] = job_template
    if workflow_job_template_node:
        data["workflow_job_template_node"] = workflow_job_template_node
    
    return await make_request(f"{AAP_URL}/workflow_job_nodes/", method="POST", json=data)

@function_tool
async def get_workflow_job_node(workflow_job_node_id: int) -> Any:
    """Get details of a specific workflow job node.
    
    Args:
        workflow_job_node_id: ID of the workflow job node
    """
    return await make_request(f"{AAP_URL}/workflow_job_nodes/{workflow_job_node_id}/")

@function_tool
async def update_workflow_job_node(
    workflow_job_node_id: int,
    workflow_job: int = None,
    job: int = None,
    job_template: int = None,
    workflow_job_template_node: int = None,
    extra_data: dict = None,
) -> Any:
    """Update a workflow job node.
    
    Args:
        workflow_job_node_id: ID of the workflow job node to update
        workflow_job: ID of the workflow job
        job: ID of the associated job
        job_template: ID of the job template
        workflow_job_template_node: ID of the workflow job template node
        extra_data: Additional data for the node
    """
    data = {}
    if workflow_job:
        data["workflow_job"] = workflow_job
    if job:
        data["job"] = job
    if job_template:
        data["job_template"] = job_template
    if workflow_job_template_node:
        data["workflow_job_template_node"] = workflow_job_template_node
    if extra_data:
        data["extra_data"] = extra_data
    
    return await make_request(f"{AAP_URL}/workflow_job_nodes/{workflow_job_node_id}/", method="PUT", json=data)

@function_tool
async def patch_workflow_job_node(
    workflow_job_node_id: int,
    workflow_job: int = None,
    job: int = None,
    job_template: int = None,
    workflow_job_template_node: int = None,
    extra_data: dict = None,
) -> Any:
    """Partially update a workflow job node.
    
    Args:
        workflow_job_node_id: ID of the workflow job node to update
        workflow_job: ID of the workflow job
        job: ID of the associated job
        job_template: ID of the job template
        workflow_job_template_node: ID of the workflow job template node
        extra_data: Additional data for the node
    """
    data = {}
    if workflow_job:
        data["workflow_job"] = workflow_job
    if job:
        data["job"] = job
    if job_template:
        data["job_template"] = job_template
    if workflow_job_template_node:
        data["workflow_job_template_node"] = workflow_job_template_node
    if extra_data:
        data["extra_data"] = extra_data
    
    return await make_request(f"{AAP_URL}/workflow_job_nodes/{workflow_job_node_id}/", method="PATCH", json=data)

@function_tool
async def delete_workflow_job_node(workflow_job_node_id: int) -> Any:
    """Delete a workflow job node.
    
    Args:
        workflow_job_node_id: ID of the workflow job node to delete
    """
    return await make_request(f"{AAP_URL}/workflow_job_nodes/{workflow_job_node_id}/", method="DELETE")

# Hosts API Functions
@function_tool
async def list_hosts() -> Any:
    """List all hosts in Ansible Automation Platform.
    
    Returns a list of all hosts including their basic information
    such as name, description, inventory, and variables.
    """
    return await make_request(f"{AAP_URL}/hosts/")

@function_tool
async def create_host(
    name: str,
    description: str = "",
    inventory: int = None,
    variables: str = "",
    enabled: bool = True,
) -> Any:
    """Create a new host.
    
    Args:
        name: Name of the host
        description: Description of the host
        inventory: ID of the inventory this host belongs to
        variables: Variables for the host (JSON string)
        enabled: Whether the host is enabled
    """
    data = {
        "name": name,
        "description": description,
        "variables": variables,
        "enabled": enabled
    }
    if inventory:
        data["inventory"] = inventory
    return await make_request(f"{AAP_URL}/hosts/", method="POST", json=data)

@function_tool
async def get_host(host_id: int) -> Any:
    """Get details of a specific host.
    
    Args:
        host_id: ID of the host to retrieve
    """
    return await make_request(f"{AAP_URL}/hosts/{host_id}/")

@function_tool
async def update_host(
    host_id: int,
    name: str = None,
    description: str = None,
    inventory: int = None,
    variables: str = None,
    enabled: bool = None,
) -> Any:
    """Update a host.
    
    Args:
        host_id: ID of the host to update
        name: Name of the host
        description: Description of the host
        inventory: ID of the inventory this host belongs to
        variables: Variables for the host (JSON string)
        enabled: Whether the host is enabled
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if inventory is not None:
        data["inventory"] = inventory
    if variables is not None:
        data["variables"] = variables
    if enabled is not None:
        data["enabled"] = enabled
    return await make_request(f"{AAP_URL}/hosts/{host_id}/", method="PUT", json=data)

@function_tool
async def patch_host(
    host_id: int,
    name: str = None,
    description: str = None,
    inventory: int = None,
    variables: str = None,
    enabled: bool = None,
) -> Any:
    """Update a host (partial update).
    
    Args:
        host_id: ID of the host to update
        name: Name of the host
        description: Description of the host
        inventory: ID of the inventory this host belongs to
        variables: Variables for the host (JSON string)
        enabled: Whether the host is enabled
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if inventory is not None:
        data["inventory"] = inventory
    if variables is not None:
        data["variables"] = variables
    if enabled is not None:
        data["enabled"] = enabled
    return await make_request(f"{AAP_URL}/hosts/{host_id}/", method="PATCH", json=data)

@function_tool
async def delete_host(host_id: int) -> Any:
    """Delete a host.
    
    Args:
        host_id: ID of the host to delete
    """
    return await make_request(f"{AAP_URL}/hosts/{host_id}/", method="DELETE")

# Groups API Functions
@function_tool
async def list_groups() -> Any:
    """List all groups in Ansible Automation Platform.
    
    Returns a list of all groups including their basic information
    such as name, description, inventory, and variables.
    """
    return await make_request(f"{AAP_URL}/groups/")

@function_tool
async def create_group(
    name: str,
    description: str = "",
    inventory: int = None,
    variables: str = "",
    enabled: bool = True,
) -> Any:
    """Create a new group.
    
    Args:
        name: Name of the group
        description: Description of the group
        inventory: ID of the inventory this group belongs to
        variables: Variables for the group (JSON string)
        enabled: Whether the group is enabled
    """
    data = {
        "name": name,
        "description": description,
        "variables": variables,
        "enabled": enabled,
    }
    if inventory:
        data["inventory"] = inventory
    return await make_request(f"{AAP_URL}/groups/", method="POST", json=data)

@function_tool
async def get_group(group_id: int) -> Any:
    """Get details of a specific group.
    
    Args:
        group_id: ID of the group to retrieve
    """
    return await make_request(f"{AAP_URL}/groups/{group_id}/")

@function_tool
async def update_group(
    group_id: int,
    name: str = None,
    description: str = None,
    inventory: int = None,
    variables: str = None,
    enabled: bool = None,
) -> Any:
    """Update a group.
    
    Args:
        group_id: ID of the group to update
        name: New name for the group
        description: New description for the group
        inventory: New inventory ID for the group
        variables: New variables for the group (JSON string)
        enabled: Whether the group should be enabled
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if inventory is not None:
        data["inventory"] = inventory
    if variables is not None:
        data["variables"] = variables
    if enabled is not None:
        data["enabled"] = enabled
    return await make_request(f"{AAP_URL}/groups/{group_id}/", method="PUT", json=data)

@function_tool
async def patch_group(
    group_id: int,
    name: str = None,
    description: str = None,
    inventory: int = None,
    variables: str = None,
    enabled: bool = None,
) -> Any:
    """Update a group (partial update).
    
    Args:
        group_id: ID of the group to update
        name: New name for the group
        description: New description for the group
        inventory: New inventory ID for the group
        variables: New variables for the group (JSON string)
        enabled: Whether the group should be enabled
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if inventory is not None:
        data["inventory"] = inventory
    if variables is not None:
        data["variables"] = variables
    if enabled is not None:
        data["enabled"] = enabled
    return await make_request(f"{AAP_URL}/groups/{group_id}/", method="PATCH", json=data)

@function_tool
async def delete_group(group_id: int) -> Any:
    """Delete a group.
    
    Args:
        group_id: ID of the group to delete
    """
    return await make_request(f"{AAP_URL}/groups/{group_id}/", method="DELETE")

# Inventory Sources API Functions
@function_tool
async def list_inventory_sources() -> Any:
    """List all inventory sources in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/inventory_sources/")

@function_tool
async def create_inventory_source(
    name: str,
    source: str,
    inventory: int,
    description: str = "",
    source_vars: str = "",
    credential: int = None,
    source_path: str = "",
    source_project: int = None,
    source_script: int = None,
    source_regions: str = "",
    instance_filters: str = "",
    group_by: str = "",
    overwrite: bool = False,
    overwrite_vars: bool = False,
    update_on_launch: bool = False,
    update_cache_timeout: int = 0,
    verbosity: int = None,
    enabled_var: str = "",
    enabled_value: str = "",
    host_filter: str = "",
) -> Any:
    """Create a new inventory source."""
    data = {
        "name": name,
        "source": source,
        "inventory": inventory,
        "description": description,
        "source_vars": source_vars,
        "source_path": source_path,
        "source_regions": source_regions,
        "instance_filters": instance_filters,
        "group_by": group_by,
        "overwrite": overwrite,
        "overwrite_vars": overwrite_vars,
        "update_on_launch": update_on_launch,
        "update_cache_timeout": update_cache_timeout,
        "enabled_var": enabled_var,
        "enabled_value": enabled_value,
        "host_filter": host_filter,
    }
    if credential:
        data["credential"] = credential
    if source_project:
        data["source_project"] = source_project
    if source_script:
        data["source_script"] = source_script
    if verbosity is not None:
        data["verbosity"] = verbosity
    
    return await make_request(f"{AAP_URL}/inventory_sources/", method="POST", json=data)

@function_tool
async def get_inventory_source(inventory_source_id: int) -> Any:
    """Get details of a specific inventory source."""
    return await make_request(f"{AAP_URL}/inventory_sources/{inventory_source_id}/")

@function_tool
async def update_inventory_source(inventory_source_id: int, **kwargs) -> Any:
    """Update an inventory source."""
    return await make_request(f"{AAP_URL}/inventory_sources/{inventory_source_id}/", method="PUT", data=kwargs)

@function_tool
async def patch_inventory_source(inventory_source_id: int, **kwargs) -> Any:
    """Update an inventory source (partial update)."""
    return await make_request(f"{AAP_URL}/inventory_sources/{inventory_source_id}/", method="PATCH", data=kwargs)

@function_tool
async def delete_inventory_source(inventory_source_id: int) -> Any:
    """Delete an inventory source."""
    return await make_request(f"{AAP_URL}/inventory_sources/{inventory_source_id}/", method="DELETE")

# Inventory Updates API Functions
@function_tool
async def list_inventory_updates() -> Any:
    """List all inventory updates in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/inventory_updates/")

@function_tool
async def create_inventory_update(
    inventory_source: int,
    name: str = "",
    description: str = "",
    extra_vars: str = "",
    limit: str = "",
    verbosity: int = 0,
) -> Any:
    """Create a new inventory update.
    
    Args:
        inventory_source: ID of the inventory source to update
        name: Name of the inventory update
        description: Description of the inventory update
        extra_vars: Extra variables for the update
        limit: Limit hosts to update
        verbosity: Verbosity level (0-4)
    """
    return await make_request(f"{AAP_URL}/inventory_updates/", method="POST", data={
        "inventory_source": inventory_source,
        "name": name,
        "description": description,
        "extra_vars": extra_vars,
        "limit": limit,
        "verbosity": verbosity
    })

@function_tool
async def get_inventory_update(inventory_update_id: int) -> Any:
    """Get details of a specific inventory update.
    
    Args:
        inventory_update_id: ID of the inventory update to retrieve
    """
    return await make_request(f"{AAP_URL}/inventory_updates/{inventory_update_id}/")

@function_tool
async def update_inventory_update(
    inventory_update_id: int,
    name: str = None,
    description: str = None,
    extra_vars: str = None,
    limit: str = None,
    verbosity: int = None,
) -> Any:
    """Update an inventory update.
    
    Args:
        inventory_update_id: ID of the inventory update to update
        name: New name for the inventory update
        description: New description for the inventory update
        extra_vars: New extra variables for the update
        limit: New limit for hosts to update
        verbosity: New verbosity level (0-4)
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if extra_vars is not None:
        data["extra_vars"] = extra_vars
    if limit is not None:
        data["limit"] = limit
    if verbosity is not None:
        data["verbosity"] = verbosity
    
    return await make_request(f"{AAP_URL}/inventory_updates/{inventory_update_id}/", method="PUT", json=data)

@function_tool
async def patch_inventory_update(
    inventory_update_id: int,
    name: str = None,
    description: str = None,
    extra_vars: str = None,
    limit: str = None,
    verbosity: int = None,
) -> Any:
    """Update an inventory update (partial update).
    
    Args:
        inventory_update_id: ID of the inventory update to update
        name: New name for the inventory update
        description: New description for the inventory update
        extra_vars: New extra variables for the update
        limit: New limit for hosts to update
        verbosity: New verbosity level (0-4)
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if extra_vars is not None:
        data["extra_vars"] = extra_vars
    if limit is not None:
        data["limit"] = limit
    if verbosity is not None:
        data["verbosity"] = verbosity
    
    return await make_request(f"{AAP_URL}/inventory_updates/{inventory_update_id}/", method="PATCH", json=data)

@function_tool
async def delete_inventory_update(inventory_update_id: int) -> Any:
    """Delete an inventory update.
    
    Args:
        inventory_update_id: ID of the inventory update to delete
    """
    return await make_request(f"{AAP_URL}/inventory_updates/{inventory_update_id}/", method="DELETE")

# Ad Hoc Commands API Functions
@function_tool
async def list_ad_hoc_commands() -> Any:
    """List all ad hoc commands in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/ad_hoc_commands/")

@function_tool
async def create_ad_hoc_command(
    module_name: str,
    module_args: str = "",
    inventory: int = None,
    credential: int = None,
    job_type: str = "run",
    limit: str = "",
    verbosity: int = 0,
    extra_vars: str = "",
    become_enabled: bool = False,
    diff_mode: bool = False,
) -> Any:
    """Create a new ad hoc command.
    
    Args:
        module_name: Name of the Ansible module to run
        module_args: Arguments for the module
        inventory: ID of the inventory to run against
        credential: ID of the credential to use
        job_type: Type of job (run, check, scan)
        limit: Host pattern to limit execution
        verbosity: Verbosity level (0-4)
        extra_vars: Extra variables for the command
        become_enabled: Whether to enable privilege escalation
        diff_mode: Whether to show differences
    """
    data = {
        "module_name": module_name,
        "module_args": module_args,
        "job_type": job_type,
        "limit": limit,
        "verbosity": verbosity,
        "extra_vars": extra_vars,
        "become_enabled": become_enabled,
        "diff_mode": diff_mode,
    }
    if inventory:
        data["inventory"] = inventory
    if credential:
        data["credential"] = credential
    return await make_request(f"{AAP_URL}/ad_hoc_commands/", method="POST", json=data)

@function_tool
async def get_ad_hoc_command(ad_hoc_command_id: int) -> Any:
    """Get details of a specific ad hoc command.
    
    Args:
        ad_hoc_command_id: ID of the ad hoc command
    """
    return await make_request(f"{AAP_URL}/ad_hoc_commands/{ad_hoc_command_id}/")

@function_tool
async def update_ad_hoc_command(ad_hoc_command_id: int, **kwargs) -> Any:
    """Update an ad hoc command.
    
    Args:
        ad_hoc_command_id: ID of the ad hoc command to update
        **kwargs: Fields to update
    """
    return await make_request(f"{AAP_URL}/ad_hoc_commands/{ad_hoc_command_id}/", method="PUT", data=kwargs)

@function_tool
async def patch_ad_hoc_command(ad_hoc_command_id: int, **kwargs) -> Any:
    """Update an ad hoc command (partial update).
    
    Args:
        ad_hoc_command_id: ID of the ad hoc command to update
        **kwargs: Fields to update
    """
    return await make_request(f"{AAP_URL}/ad_hoc_commands/{ad_hoc_command_id}/", method="PATCH", data=kwargs)

@function_tool
async def delete_ad_hoc_command(ad_hoc_command_id: int) -> Any:
    """Delete an ad hoc command.
    
    Args:
        ad_hoc_command_id: ID of the ad hoc command to delete
    """
    return await make_request(f"{AAP_URL}/ad_hoc_commands/{ad_hoc_command_id}/", method="DELETE")

# System Job Templates API Functions
@function_tool
async def list_system_job_templates() -> Any:
    """List all system job templates in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/system_job_templates/")

@function_tool
async def create_system_job_template(
    name: str,
    job_type: str,
    description: str = "",
    organization: int = None,
    extra_vars: str = "",
    survey_enabled: bool = False,
    allow_simultaneous: bool = False,
    ask_variables_on_launch: bool = False,
    ask_limit_on_launch: bool = False,
    ask_scm_branch_on_launch: bool = False,
    ask_tags_on_launch: bool = False,
    ask_skip_tags_on_launch: bool = False,
    ask_job_type_on_launch: bool = False,
    ask_verbosity_on_launch: bool = False,
    ask_inventory_on_launch: bool = False,
    ask_credential_on_launch: bool = False,
    ask_execution_environment_on_launch: bool = False,
    ask_forks_on_launch: bool = False,
    ask_job_slice_count_on_launch: bool = False,
    ask_timeout_on_launch: bool = False,
    ask_instance_groups_on_launch: bool = False,
    ask_labels_on_launch: bool = False,
    ask_dry_run_on_launch: bool = False,
    ask_diff_mode_on_launch: bool = False,
) -> Any:
    """Create a new system job template.
    
    Args:
        name: Name of the system job template
        job_type: Type of system job (e.g., 'cleanup_jobs', 'cleanup_activity_stream', etc.)
        description: Description of the system job template
        organization: ID of the organization
        extra_vars: Extra variables for the job template
        survey_enabled: Whether to enable surveys for this template
        allow_simultaneous: Whether to allow simultaneous runs
        ask_variables_on_launch: Whether to ask for variables on launch
        ask_limit_on_launch: Whether to ask for limit on launch
        ask_scm_branch_on_launch: Whether to ask for SCM branch on launch
        ask_tags_on_launch: Whether to ask for tags on launch
        ask_skip_tags_on_launch: Whether to ask for skip tags on launch
        ask_job_type_on_launch: Whether to ask for job type on launch
        ask_verbosity_on_launch: Whether to ask for verbosity on launch
        ask_inventory_on_launch: Whether to ask for inventory on launch
        ask_credential_on_launch: Whether to ask for credential on launch
        ask_execution_environment_on_launch: Whether to ask for execution environment on launch
        ask_forks_on_launch: Whether to ask for forks on launch
        ask_job_slice_count_on_launch: Whether to ask for job slice count on launch
        ask_timeout_on_launch: Whether to ask for timeout on launch
        ask_instance_groups_on_launch: Whether to ask for instance groups on launch
        ask_labels_on_launch: Whether to ask for labels on launch
        ask_dry_run_on_launch: Whether to ask for dry run on launch
        ask_diff_mode_on_launch: Whether to ask for diff mode on launch
    """
    data = {
        "name": name,
        "job_type": job_type,
        "description": description,
        "extra_vars": extra_vars,
        "survey_enabled": survey_enabled,
        "allow_simultaneous": allow_simultaneous,
        "ask_variables_on_launch": ask_variables_on_launch,
        "ask_limit_on_launch": ask_limit_on_launch,
        "ask_scm_branch_on_launch": ask_scm_branch_on_launch,
        "ask_tags_on_launch": ask_tags_on_launch,
        "ask_skip_tags_on_launch": ask_skip_tags_on_launch,
        "ask_job_type_on_launch": ask_job_type_on_launch,
        "ask_verbosity_on_launch": ask_verbosity_on_launch,
        "ask_inventory_on_launch": ask_inventory_on_launch,
        "ask_credential_on_launch": ask_credential_on_launch,
        "ask_execution_environment_on_launch": ask_execution_environment_on_launch,
        "ask_forks_on_launch": ask_forks_on_launch,
        "ask_job_slice_count_on_launch": ask_job_slice_count_on_launch,
        "ask_timeout_on_launch": ask_timeout_on_launch,
        "ask_instance_groups_on_launch": ask_instance_groups_on_launch,
        "ask_labels_on_launch": ask_labels_on_launch,
        "ask_dry_run_on_launch": ask_dry_run_on_launch,
        "ask_diff_mode_on_launch": ask_diff_mode_on_launch,
    }
    if organization:
        data["organization"] = organization
    return await make_request(f"{AAP_URL}/system_job_templates/", method="POST", json=data)

@function_tool
async def get_system_job_template(system_job_template_id: int) -> Any:
    """Get details of a specific system job template.
    
    Args:
        system_job_template_id: ID of the system job template
    """
    return await make_request(f"{AAP_URL}/system_job_templates/{system_job_template_id}/")

@function_tool
async def update_system_job_template(system_job_template_id: int, **kwargs) -> Any:
    """Update a system job template.
    
    Args:
        system_job_template_id: ID of the system job template to update
        **kwargs: Fields to update
    """
    return await make_request(f"{AAP_URL}/system_job_templates/{system_job_template_id}/", method="PUT", data=kwargs)

@function_tool
async def patch_system_job_template(system_job_template_id: int, **kwargs) -> Any:
    """Update a system job template (partial update).
    
    Args:
        system_job_template_id: ID of the system job template to update
        **kwargs: Fields to update
    """
    return await make_request(f"{AAP_URL}/system_job_templates/{system_job_template_id}/", method="PATCH", data=kwargs)

@function_tool
async def delete_system_job_template(system_job_template_id: int) -> Any:
    """Delete a system job template.
    
    Args:
        system_job_template_id: ID of the system job template to delete
    """
    return await make_request(f"{AAP_URL}/system_job_templates/{system_job_template_id}/", method="DELETE")

# System Jobs API Functions
@function_tool
async def list_system_jobs() -> Any:
    """List all system jobs in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/system_jobs/")

@function_tool
async def get_system_job(system_job_id: int) -> Any:
    """Retrieve a system job by ID."""
    return await make_request(f"{AAP_URL}/system_jobs/{system_job_id}/")

@function_tool
async def delete_system_job(system_job_id: int) -> Any:
    """Delete a system job by ID."""
    return await make_request(f"{AAP_URL}/system_jobs/{system_job_id}/", method="DELETE")

# Schedules API Functions
@function_tool
async def list_schedules() -> Any:
    """List all schedules in Ansible Automation Platform."""
    return await make_request(f"{AAP_URL}/schedules/")

@function_tool
async def create_schedule(
    name: str,
    unified_job_template: int,
    rrule: str,
    description: str = "",
    enabled: bool = True,
    extra_data: dict = None,
    timezone: str = "UTC",
) -> Any:
    """Create a new schedule for a job template or workflow job template."""
    data = {
        "name": name,
        "unified_job_template": unified_job_template,
        "rrule": rrule,
        "description": description,
        "enabled": enabled,
        "timezone": timezone
    }
    if extra_data:
        data["extra_data"] = extra_data
    return await make_request(f"{AAP_URL}/schedules/", method="POST", json=data)

@function_tool
async def get_schedule(schedule_id: int) -> Any:
    """Retrieve a schedule by ID."""
    return await make_request(f"{AAP_URL}/schedules/{schedule_id}/")

@function_tool
async def update_schedule(
    schedule_id: int,
    name: str = None,
    unified_job_template: int = None,
    rrule: str = None,
    description: str = None,
    enabled: bool = None,
    extra_data: dict = None,
    timezone: str = None,
) -> Any:
    """Update an existing schedule."""
    data = {}
    if name is not None:
        data["name"] = name
    if unified_job_template is not None:
        data["unified_job_template"] = unified_job_template
    if rrule is not None:
        data["rrule"] = rrule
    if description is not None:
        data["description"] = description
    if enabled is not None:
        data["enabled"] = enabled
    if timezone is not None:
        data["timezone"] = timezone
    if extra_data is not None:
        data["extra_data"] = extra_data
    return await make_request(f"{AAP_URL}/schedules/{schedule_id}/", method="PUT", json=data)

@function_tool
async def patch_schedule(
    schedule_id: int,
    name: str = None,
    unified_job_template: int = None,
    rrule: str = None,
    description: str = None,
    enabled: bool = None,
    extra_data: dict = None,
    timezone: str = None,
) -> Any:
    """Partially update a schedule."""
    data = {}
    if name is not None:
        data["name"] = name
    if unified_job_template is not None:
        data["unified_job_template"] = unified_job_template
    if rrule is not None:
        data["rrule"] = rrule
    if description is not None:
        data["description"] = description
    if enabled is not None:
        data["enabled"] = enabled
    if timezone is not None:
        data["timezone"] = timezone
    if extra_data is not None:
        data["extra_data"] = extra_data
    return await make_request(f"{AAP_URL}/schedules/{schedule_id}/", method="PATCH", json=data)

@function_tool
async def delete_schedule(schedule_id: int) -> Any:
    """Delete a schedule by ID."""
    return await make_request(f"{AAP_URL}/schedules/{schedule_id}/", method="DELETE")

@function_tool
async def get_schedule_jobs(schedule_id: int) -> Any:
    """Get all jobs associated with a specific schedule."""
    return await make_request(f"{AAP_URL}/schedules/{schedule_id}/jobs/")

@function_tool
async def get_schedule_next_run(schedule_id: int) -> Any:
    """Get the next scheduled run time for a schedule."""
    return await make_request(f"{AAP_URL}/schedules/{schedule_id}/next_run/")

# Bỏ phần khởi động server này
# if __name__ == "__main__":
#     uvicorn.run(mcp, host="127.0.0.1", port=8889)

@function_tool
async def list_roles() -> Any:
    """List all roles in Ansible AWX."""
    return await make_request(f"{AAP_URL}/roles/")

@function_tool
async def get_role(role_id: int) -> Any:
    """Get the details of a role by ID."""
    return await make_request(f"{AAP_URL}/roles/{role_id}/")

@function_tool
async def list_role_children(role_id: int) -> Any:
    """List the child roles of a role by ID."""
    return await make_request(f"{AAP_URL}/roles/{role_id}/children/")

@function_tool
async def list_role_parents(role_id: int) -> Any:
    """List the parent roles of a role by ID."""
    return await make_request(f"{AAP_URL}/roles/{role_id}/parents/")

@function_tool
async def list_role_teams(role_id: int) -> Any:
    """List the teams associated with a role by ID."""
    return await make_request(f"{AAP_URL}/roles/{role_id}/teams/")

@function_tool
async def list_role_users(role_id: int) -> Any:
    """List the users associated with a role by ID."""
    return await make_request(f"{AAP_URL}/roles/{role_id}/users/")

@function_tool
async def list_notification_templates() -> Any:
    """List all notification templates."""
    return await make_request(f"{AAP_URL}/notification_templates/")

@function_tool
async def create_notification_template(name: str, organization: int, notification_type: str, notification_configuration: dict, description: str = "") -> Any:
    """Create a new notification template."""
    payload = {
        "name": name,
        "organization": organization,
        "notification_type": notification_type,
        "notification_configuration": notification_configuration,
        "description": description
    }
    payload = {k: v for k, v in payload.items() if v or k in ('name', 'organization', 'notification_type', 'notification_configuration')}
    return await make_request(f"{AAP_URL}/notification_templates/", method="POST", json=payload)

@function_tool
async def get_notification_template(notification_template_id: int) -> Any:
    """Get the details of a notification template by ID."""
    return await make_request(f"{AAP_URL}/notification_templates/{notification_template_id}/")

@function_tool
async def update_notification_template(
    notification_template_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    organization: Optional[int] = None,
    notification_type: Optional[str] = None,
    notification_configuration: Optional[dict] = None
) -> Any:
    """Partially update (PATCH) a notification template by ID."""
    payload = {
        "name": name,
        "description": description,
        "organization": organization,
        "notification_type": notification_type,
        "notification_configuration": notification_configuration,
    }
    patch_payload = {k: v for k, v in payload.items() if v is not None}

    if not patch_payload:
        return "Error: No fields provided to update."

    return await make_request(
        f"{AAP_URL}/notification_templates/{notification_template_id}/",
        method="PATCH",
        json=patch_payload
    )

@function_tool
async def delete_notification_template(notification_template_id: int) -> Any:
    """Delete a notification template by ID."""
    return await make_request(
        f"{AAP_URL}/notification_templates/{notification_template_id}/",
        method="DELETE"
    )

@function_tool
async def test_notification_template(notification_template_id: int) -> Any:
    """Send a test notification for a notification template by ID."""
    return await make_request(
        f"{AAP_URL}/notification_templates/{notification_template_id}/test/",
        method="POST"
    )

@function_tool
async def list_notifications() -> Any:
    """List all notifications."""
    return await make_request(f"{AAP_URL}/notifications/")

@function_tool
async def get_notification(notification_id: int) -> Any:
    """Get the details of a notification by ID."""
    return await make_request(f"{AAP_URL}/notifications/{notification_id}/")

@function_tool
async def list_labels() -> Any:
    """List all labels."""
    return await make_request(f"{AAP_URL}/labels/")

@function_tool
async def create_label(name: str, organization: int) -> Any:
    """Create a new label."""
    payload = {
        "name": name,
        "organization": organization,
    }
    return await make_request(f"{AAP_URL}/labels/", method="POST", json=payload)

@function_tool
async def get_label(label_id: int) -> Any:
    """Get the details of a label by ID."""
    return await make_request(f"{AAP_URL}/labels/{label_id}/")

@function_tool
async def delete_label(label_id: int) -> Any:
    """Delete a label by ID."""
    return await make_request(
        f"{AAP_URL}/labels/{label_id}/",
        method="DELETE"
    )

# ======================================================================================================================
# Unified Job Templates
# ======================================================================================================================

@function_tool
async def list_unified_job_templates() -> Any:
    """List all unified job templates."""
    return await make_request(f"{AAP_URL}/unified_job_templates/")

@function_tool
async def get_unified_job_template(unified_job_template_id: int) -> Any:
    """Get the details of a unified job template by ID."""
    return await make_request(f"{AAP_URL}/unified_job_templates/{unified_job_template_id}/")

@function_tool
async def delete_unified_job_template(unified_job_template_id: int) -> Any:
    """Delete a unified job template by ID."""
    return await make_request(
        f"{AAP_URL}/unified_job_templates/{unified_job_template_id}/",
        method="DELETE"
    )

# ======================================================================================================================
# Unified Jobs
# ======================================================================================================================

@function_tool
async def list_unified_jobs() -> Any:
    """List all unified jobs."""
    return await make_request(f"{AAP_URL}/unified_jobs/")

@function_tool
async def get_unified_job(unified_job_id: int) -> Any:
    """Get the details of a unified job by ID."""
    return await make_request(f"{AAP_URL}/unified_jobs/{unified_job_id}/")

@function_tool
async def delete_unified_job(unified_job_id: int) -> Any:
    """Delete a unified job by ID."""
    return await make_request(
        f"{AAP_URL}/unified_jobs/{unified_job_id}/",
        method="DELETE"
    )

@function_tool
async def get_unified_job_stdout(unified_job_id: int) -> Any:
    """Get the stdout for a unified job by ID."""
    return await make_request(f"{AAP_URL}/unified_jobs/{unified_job_id}/stdout/")

@function_tool
async def list_unified_job_events(unified_job_id: int) -> Any:
    """List job events for a unified job by ID."""
    return await make_request(f"{AAP_URL}/unified_jobs/{unified_job_id}/job_events/")

@function_tool
async def list_unified_job_notifications(unified_job_id: int) -> Any:
    """List notifications for a unified job by ID."""
    return await make_request(f"{AAP_URL}/unified_jobs/{unified_job_id}/notifications/")

@function_tool
async def list_unified_job_labels(unified_job_id: int) -> Any:
    """List labels for a unified job by ID."""
    return await make_request(f"{AAP_URL}/unified_jobs/{unified_job_id}/labels/")

@function_tool
async def list_unified_job_activity_stream(unified_job_id: int) -> Any:
    """List the activity stream for a unified job by ID."""
    return await make_request(f"{AAP_URL}/unified_jobs/{unified_job_id}/activity_stream/")

@function_tool
async def relaunch_unified_job(unified_job_id: int) -> Any:
    """Relaunch a unified job by ID."""
    return await make_request(
        f"{AAP_URL}/unified_jobs/{unified_job_id}/relaunch/",
        method="POST"
    )

# ======================================================================================================================
# Workflow Approval Templates
# ======================================================================================================================

@function_tool
async def list_workflow_approval_templates() -> Any:
    """List all workflow approval templates."""
    return await make_request(f"{AAP_URL}/workflow_approval_templates/")

@function_tool
async def create_workflow_approval_template(name: str, description: str = "", timeout: int = 0) -> Any:
    """Create a new workflow approval template."""
    payload = {
        "name": name,
        "description": description,
        "timeout": timeout,
    }
    return await make_request(f"{AAP_URL}/workflow_approval_templates/", method="POST", json=payload)

@function_tool
async def get_workflow_approval_template(workflow_approval_template_id: int) -> Any:
    """Get the details of a workflow approval template by ID."""
    return await make_request(f"{AAP_URL}/workflow_approval_templates/{workflow_approval_template_id}/")

@function_tool
async def update_workflow_approval_template(workflow_approval_template_id: int, name: str, description: str = "", timeout: int = 0) -> Any:
    """Update a workflow approval template."""
    payload = {
        "name": name,
        "description": description,
        "timeout": timeout,
    }
    return await make_request(
        f"{AAP_URL}/workflow_approval_templates/{workflow_approval_template_id}/",
        method="PUT",
        json=payload
    )

@function_tool
async def partial_update_workflow_approval_template(
    workflow_approval_template_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    timeout: Optional[int] = None
) -> Any:
    """Partially update a workflow approval template by ID."""
    payload = {
        "name": name,
        "description": description,
        "timeout": timeout,
    }
    patch_payload = {k: v for k, v in payload.items() if v is not None}

    if not patch_payload:
        return "Error: No fields provided to update."

    return await make_request(
        f"{AAP_URL}/workflow_approval_templates/{workflow_approval_template_id}/",
        method="PATCH",
        json=patch_payload
    )

@function_tool
async def delete_workflow_approval_template(workflow_approval_template_id: int) -> Any:
    """Delete a workflow approval template by ID."""
    return await make_request(
        f"{AAP_URL}/workflow_approval_templates/{workflow_approval_template_id}/",
        method="DELETE"
    )

# ======================================================================================================================
# Workflow Approvals
# ======================================================================================================================

@function_tool
async def list_workflow_approvals() -> Any:
    """List all workflow approvals."""
    return await make_request(f"{AAP_URL}/workflow_approvals/")

@function_tool
async def get_workflow_approval(workflow_approval_id: int) -> Any:
    """Get the details of a workflow approval by ID."""
    return await make_request(f"{AAP_URL}/workflow_approvals/{workflow_approval_id}/")

@function_tool
async def approve_workflow_approval(workflow_approval_id: int) -> Any:
    """Approve a workflow approval."""
    return await make_request(
        f"{AAP_URL}/workflow_approvals/{workflow_approval_id}/approve/",
        method="POST"
    )

@function_tool
async def deny_workflow_approval(workflow_approval_id: int) -> Any:
    """Deny a workflow approval."""
    return await make_request(
        f"{AAP_URL}/workflow_approvals/{workflow_approval_id}/deny/",
        method="POST"
    )

# ======================================================================================================================
# Workflow Job Nodes
# ======================================================================================================================

@function_tool
async def list_workflow_job_nodes() -> Any:
    """List all workflow job nodes."""
    return await make_request(f"{AAP_URL}/workflow_job_nodes/")

@function_tool
async def get_workflow_job_node(workflow_job_node_id: int) -> Any:
    """Get the details of a workflow job node by ID."""
    return await make_request(f"{AAP_URL}/workflow_job_nodes/{workflow_job_node_id}/")

@function_tool
async def delete_workflow_job_node(workflow_job_node_id: int) -> Any:
    """Delete a workflow job node by ID."""
    return await make_request(
        f"{AAP_URL}/workflow_job_nodes/{workflow_job_node_id}/",
        method="DELETE"
    )

@function_tool
async def list_workflow_job_node_always_nodes(workflow_job_node_id: int) -> Any:
    """List the "always" nodes for a given workflow job node."""
    return await make_request(f"{AAP_URL}/workflow_job_nodes/{workflow_job_node_id}/always_nodes/")

@function_tool
async def list_workflow_job_node_failure_nodes(workflow_job_node_id: int) -> Any:
    """List the "failure" nodes for a given workflow job node."""
    return await make_request(f"{AAP_URL}/workflow_job_nodes/{workflow_job_node_id}/failure_nodes/")

@function_tool
async def list_workflow_job_node_success_nodes(workflow_job_node_id: int) -> Any:
    """List the "success" nodes for a given workflow job node."""
    return await make_request(f"{AAP_URL}/workflow_job_nodes/{workflow_job_node_id}/success_nodes/")

@function_tool
async def list_workflow_job_node_credentials(workflow_job_node_id: int) -> Any:
    """List the credentials for a given workflow job node."""
    return await make_request(f"{AAP_URL}/workflow_job_nodes/{workflow_job_node_id}/credentials/")

@function_tool
async def relaunch_workflow_job_node(workflow_job_node_id: int) -> Any:
    """Relaunch a workflow job node."""
    return await make_request(
        f"{AAP_URL}/workflow_job_nodes/{workflow_job_node_id}/relaunch/",
        method="POST"
    )

# ======================================================================================================================
# Workflow Job Template Nodes
# ======================================================================================================================

@function_tool
async def list_workflow_job_template_nodes() -> Any:
    """List all workflow job template nodes."""
    return await make_request(f"{AAP_URL}/workflow_job_template_nodes/")

@function_tool
async def get_workflow_job_template_node(workflow_job_template_node_id: int) -> Any:
    """Get the details of a workflow job template node by ID."""
    return await make_request(f"{AAP_URL}/workflow_job_template_nodes/{workflow_job_template_node_id}/")

@function_tool
async def delete_workflow_job_template_node(workflow_job_template_node_id: int) -> Any:
    """Delete a workflow job template node by ID."""
    return await make_request(
        f"{AAP_URL}/workflow_job_template_nodes/{workflow_job_template_node_id}/",
        method="DELETE"
    )

@function_tool
async def list_workflow_job_template_node_always_nodes(workflow_job_template_node_id: int) -> Any:
    """List the "always" nodes for a given workflow job template node."""
    return await make_request(f"{AAP_URL}/workflow_job_template_nodes/{workflow_job_template_node_id}/always_nodes/")

@function_tool
async def list_workflow_job_template_node_failure_nodes(workflow_job_template_node_id: int) -> Any:
    """List the "failure" nodes for a given workflow job template node."""
    return await make_request(f"{AAP_URL}/workflow_job_template_nodes/{workflow_job_template_node_id}/failure_nodes/")

@function_tool
async def list_workflow_job_template_node_success_nodes(workflow_job_template_node_id: int) -> Any:
    """List the "success" nodes for a given workflow job template node."""
    return await make_request(f"{AAP_URL}/workflow_job_template_nodes/{workflow_job_template_node_id}/success_nodes/")

@function_tool
async def list_workflow_job_template_node_credentials(workflow_job_template_node_id: int) -> Any:
    """List the credentials for a given workflow job template node."""
    return await make_request(f"{AAP_URL}/workflow_job_template_nodes/{workflow_job_template_node_id}/credentials/")

# ======================================================================================================================
# Workflow Job Templates
# ======================================================================================================================

@function_tool
async def create_workflow_job_template(name: str, **kwargs: Any) -> Any:
    """Create a new workflow job template."""
    return await make_request(
        f"{AAP_URL}/workflow_job_templates/",
        method="POST",
        json={"name": name, **kwargs}
    )

@function_tool
async def list_workflow_job_templates() -> Any:
    """List all workflow job templates."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/")

@function_tool
async def get_workflow_job_template(workflow_job_template_id: int) -> Any:
    """Get the details of a workflow job template by ID."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/")

@function_tool
async def update_workflow_job_template(workflow_job_template_id: int, **kwargs: Any) -> Any:
    """Update a workflow job template."""
    return await make_request(
        f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/",
        method="PUT",
        json=kwargs
    )

@function_tool
async def partial_update_workflow_job_template(workflow_job_template_id: int, **kwargs: Any) -> Any:
    """Partially update a workflow job template."""
    return await make_request(
        f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/",
        method="PATCH",
        json=kwargs
    )

@function_tool
async def delete_workflow_job_template(workflow_job_template_id: int) -> Any:
    """Delete a workflow job template."""
    return await make_request(
        f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/",
        method="DELETE"
    )

@function_tool
async def list_workflow_job_template_activity_stream(workflow_job_template_id: int) -> Any:
    """List the activity stream for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/activity_stream/")

@function_tool
async def copy_workflow_job_template(workflow_job_template_id: int, name: str) -> Any:
    """Copy a workflow job template."""
    return await make_request(
        f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/copy/",
        method="POST",
        json={"name": name}
    )

@function_tool
async def list_workflow_job_template_credentials(workflow_job_template_id: int) -> Any:
    """List the credentials for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/credentials/")

@function_tool
async def launch_workflow_job_template(workflow_job_template_id: int, **kwargs: Any) -> Any:
    """Launch a workflow job template."""
    return await make_request(
        f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/launch/",
        method="POST",
        json=kwargs
    )

@function_tool
async def list_workflow_job_template_labels(workflow_job_template_id: int) -> Any:
    """List the labels for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/labels/")

@function_tool
async def list_workflow_job_template_notification_templates(workflow_job_template_id: int) -> Any:
    """List the notification templates for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/notification_templates/")

@function_tool
async def list_workflow_job_template_notification_templates_approvals(workflow_job_template_id: int) -> Any:
    """List the approval notification templates for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/notification_templates_approvals/")

@function_tool
async def list_workflow_job_template_notification_templates_error(workflow_job_template_id: int) -> Any:
    """List the error notification templates for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/notification_templates_error/")

@function_tool
async def list_workflow_job_template_notification_templates_started(workflow_job_template_id: int) -> Any:
    """List the started notification templates for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/notification_templates_started/")

@function_tool
async def list_workflow_job_template_notification_templates_success(workflow_job_template_id: int) -> Any:
    """List the success notification templates for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/notification_templates_success/")

@function_tool
async def list_workflow_job_template_object_roles(workflow_job_template_id: int) -> Any:
    """List the object roles for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/object_roles/")

@function_tool
async def list_workflow_job_template_schedules(workflow_job_template_id: int) -> Any:
    """List the schedules for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/schedules/")

@function_tool
async def get_workflow_job_template_survey_spec(workflow_job_template_id: int) -> Any:
    """Get the survey spec for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/survey_spec/")

@function_tool
async def create_workflow_job_template_survey_spec(workflow_job_template_id: int, spec: dict) -> Any:
    """Create or update the survey spec for a workflow job template."""
    return await make_request(
        f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/survey_spec/",
        method="POST",
        json=spec
    )

@function_tool
async def delete_workflow_job_template_survey_spec(workflow_job_template_id: int) -> Any:
    """Delete the survey spec for a workflow job template."""
    return await make_request(
        f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/survey_spec/",
        method="DELETE"
    )

@function_tool
async def list_workflow_job_template_workflow_jobs(workflow_job_template_id: int) -> Any:
    """List the workflow jobs for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/workflow_jobs/")

@function_tool
async def list_workflow_job_template_workflow_nodes(workflow_job_template_id: int) -> Any:
    """List the workflow nodes for a workflow job template."""
    return await make_request(f"{AAP_URL}/workflow_job_templates/{workflow_job_template_id}/workflow_nodes/")

# ======================================================================================================================
# Workflow Jobs
# ======================================================================================================================

@function_tool
async def list_workflow_jobs() -> Any:
    """List all workflow jobs."""
    return await make_request(f"{AAP_URL}/workflow_jobs/")

@function_tool
async def get_workflow_job(workflow_job_id: int) -> Any:
    """Get the details of a workflow job by ID."""
    return await make_request(f"{AAP_URL}/workflow_jobs/{workflow_job_id}/")

@function_tool
async def delete_workflow_job(workflow_job_id: int) -> Any:
    """Delete a workflow job by ID."""
    return await make_request(
        f"{AAP_URL}/workflow_jobs/{workflow_job_id}/",
        method="DELETE"
    )

@function_tool
async def cancel_workflow_job(workflow_job_id: int) -> Any:
    """Cancel a workflow job by ID."""
    return await make_request(
        f"{AAP_URL}/workflow_jobs/{workflow_job_id}/cancel/",
        method="POST"
    )

@function_tool
async def relaunch_workflow_job(workflow_job_id: int) -> Any:
    """Relaunch a workflow job by ID."""
    return await make_request(
        f"{AAP_URL}/workflow_jobs/{workflow_job_id}/relaunch/",
        method="POST"
    )

@function_tool
async def list_workflow_job_activity_stream(workflow_job_id: int) -> Any:
    """List the activity stream for a workflow job."""
    return await make_request(f"{AAP_URL}/workflow_jobs/{workflow_job_id}/activity_stream/")

@function_tool
async def list_workflow_job_labels(workflow_job_id: int) -> Any:
    """List the labels for a workflow job."""
    return await make_request(f"{AAP_URL}/workflow_jobs/{workflow_job_id}/labels/")

@function_tool
async def list_workflow_job_notification_templates(workflow_job_id: int) -> Any:
    """List the notification templates for a workflow job."""
    return await make_request(f"{AAP_URL}/workflow_jobs/{workflow_job_id}/notification_templates/")

@function_tool
async def list_workflow_job_workflow_nodes(workflow_job_id: int) -> Any:
    """List the workflow nodes for a workflow job."""
    return await make_request(f"{AAP_URL}/workflow_jobs/{workflow_job_id}/workflow_nodes/")