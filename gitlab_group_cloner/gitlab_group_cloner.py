import os
import subprocess
import requests
from urllib.parse import urljoin

def get_all_group_projects(base_url, group_id, private_token, page=1, projects=None):
    """Recursively get all projects in a GitLab group and its subgroups"""
    if projects is None:
        projects = []
    
    # API endpoint for group projects
    api_url = urljoin(base_url, f"/api/v4/groups/{group_id}/projects?per_page=100&page={page}")
    
    headers = {"Private-Token": private_token} if private_token else {}
    
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        current_projects = response.json()
        
        if not current_projects:
            return projects
            
        projects.extend(current_projects)
        
        # Check if there are more pages
        if 'next' in response.links:
            return get_all_group_projects(base_url, group_id, private_token, page+1, projects)
        else:
            return projects
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching projects: {e}")
        return projects

def get_all_subgroups(base_url, group_id, private_token, page=1, subgroups=None):
    """Get all subgroups of a GitLab group"""
    if subgroups is None:
        subgroups = []
    
    api_url = urljoin(base_url, f"/api/v4/groups/{group_id}/subgroups?per_page=100&page={page}")
    
    headers = {"Private-Token": private_token} if private_token else {}
    
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        current_subgroups = response.json()
        
        if not current_subgroups:
            return subgroups
            
        subgroups.extend(current_subgroups)
        
        # Recursively get subgroups of subgroups
        for subgroup in current_subgroups:
            get_all_subgroups(base_url, subgroup['id'], private_token, 1, subgroups)
            
        # Check if there are more pages
        if 'next' in response.links:
            return get_all_subgroups(base_url, group_id, private_token, page+1, subgroups)
        else:
            return subgroups
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching subgroups: {e}")
        return subgroups

def clone_all_repos(base_url, group_id, output_dir=".", private_token=None):
    """Clone all repositories in a GitLab group and its subgroups"""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all subgroups first
    print("Discovering subgroups...")
    subgroups = get_all_subgroups(base_url, group_id, private_token)
    group_ids = [group_id] + [sg['id'] for sg in subgroups]
    
    # Get all projects from all groups
    all_projects = []
    for gid in group_ids:
        print(f"Discovering projects in group {gid}...")
        projects = get_all_group_projects(base_url, gid, private_token)
        all_projects.extend(projects)
    
    print(f"Found {len(all_projects)} repositories to clone")
    
    # Clone each repository
    for project in all_projects:
        repo_url = project['ssh_url_to_repo'] if private_token else project['http_url_to_repo']
        repo_path = project['path_with_namespace']
        full_path = os.path.join(output_dir, repo_path)
        
        # Create directory structure
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        print(f"Cloning {repo_path}...")
        try:
            subprocess.run(["git", "clone", repo_url, full_path], check=True)
            print(f"Successfully cloned {repo_path}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone {repo_path}: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clone all repositories in a GitLab group and its subgroups")
    parser.add_argument("base_url", help="GitLab base URL (e.g., https://gitlab.com)")
    parser.add_argument("group_id", help="GitLab group ID (numeric)")
    parser.add_argument("--output-dir", default=".", help="Output directory for cloned repositories")
    parser.add_argument("--private-token", help="GitLab private token for authentication (required for private repos)")
    
    args = parser.parse_args()
    
    clone_all_repos(args.base_url, args.group_id, args.output_dir, args.private_token)