#!/usr/bin/env python3
import yaml
import re
import sys
import json
import os
import sys
from pathlib import Path





"""
Script to extract Docker Compose configuration from LinuxServer.io image documentation
Uses curl to fetch the page and BeautifulSoup to parse and extract the compose example

Usage:
    python3 extractDockerCompose.py <image_name>
    python3 extractDockerCompose.py <full_url>

Examples:
    python3 extractDockerCompose.py jellyfin
    python3 extractDockerCompose.py plex
    python3 extractDockerCompose.py https://docs.linuxserver.io/images/docker-sonarr/
"""

import subprocess
import re
from bs4 import BeautifulSoup
import sys
import argparse
import urllib.parse

def fetch_page_with_curl(url):
    """
    Fetch the webpage content using curl
    """
    try:
        result = subprocess.run([
            'curl', 
            '-s',  # Silent mode
            '-L',  # Follow redirects
            '-A', 'Mozilla/5.0 (Linux; x86_64) AppleWebKit/537.36',  # User agent
            url
        ], capture_output=True, text=True, check=True)
        
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error fetching page with curl: {e}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("Error: curl command not found. Please install curl.", file=sys.stderr)
        return None

def build_url(input_arg):
    """
    Build the full URL from user input
    Accepts either a full URL or just the image name
    """
    # If it's already a full URL, return it
    if input_arg.startswith('http://') or input_arg.startswith('https://'):
        return input_arg
    
    # If it starts with docker-, remove it as LinuxServer URLs don't include it
    image_name = input_arg
    if image_name.startswith('docker-'):
        image_name = image_name[7:]  # Remove 'docker-' prefix
    
    # Build the LinuxServer.io docs URL
    base_url = "https://docs.linuxserver.io/images/docker-"
    return f"{base_url}{image_name}/"

def extract_service_name(url, html_content):
    """
    Extract the service name from the URL or HTML content
    This is used to identify the main service in the docker-compose
    """
    # Try to extract from URL first
    if 'docker-' in url:
        # Extract from URL like: /images/docker-jellyfin/ -> jellyfin
        match = re.search(r'/docker-([^/]+)/?', url)
        if match:
            return match.group(1)
    
    # Fallback: look for the main service in the compose content
    soup = BeautifulSoup(html_content, 'html.parser')
    code_blocks = soup.find_all(['code', 'pre'])
    
    for block in code_blocks:
        text = block.get_text()
        if 'services:' in text:
            # Look for the first service name after "services:"
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if 'services:' in line and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if ':' in next_line and not next_line.startswith('-'):
                        service_name = next_line.split(':')[0].strip()
                        if service_name and not service_name.startswith('#'):
                            return service_name
    
    return None
def extract_docker_compose(html_content, service_name=None):
    """
    Extract the Docker Compose configuration from the HTML content
    Now works for any LinuxServer.io service
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Method 1: Look for code blocks that contain "services:" and any service name
    code_blocks = soup.find_all(['code', 'pre'])
    
    for block in code_blocks:
        text = block.get_text()
        if 'services:' in text and ('image: lscr.io/linuxserver/' in text or 'linuxserver/' in text):
            return text.strip()
    
    # Method 2: Use regex to find the docker-compose block
    # Look for the pattern starting with "---" and containing services
    if service_name:
        compose_pattern = rf'---\s*\n(.*?services:.*?{re.escape(service_name)}:.*?)(?=\n\s*docker cli|\n\s*Parameters|\Z)'
    else:
        compose_pattern = r'---\s*\n(.*?services:.*?)(?=\n\s*docker cli|\n\s*Parameters|\Z)'
    
    match = re.search(compose_pattern, html_content, re.DOTALL | re.IGNORECASE)
    
    if match:
        return match.group(0).strip()
    
    # Method 3: Look for YAML-like content with LinuxServer image
    yaml_pattern = r'(services:\s*\n.*?image:\s*lscr\.io/linuxserver/.*?)(?=\n[a-zA-Z]|\n\s*docker cli|\Z)'
    match = re.search(yaml_pattern, html_content, re.DOTALL)
    
    if match:
        return f"---\n{match.group(1)}"
    
    # Method 4: Broader search for any services block
    services_pattern = r'(services:\s*\n(?:\s+\w+:\s*\n(?:\s+.*\n)*)*)'
    match = re.search(services_pattern, html_content, re.MULTILINE)
    
    if match:
        return f"---\n{match.group(1)}"
    
    return None

def clean_docker_compose(compose_text):
    """
    Clean up the extracted Docker Compose text
    """
    if not compose_text:
        return None
    
    # Remove any HTML entities or extra whitespace
    compose_text = re.sub(r'&lt;', '<', compose_text)
    compose_text = re.sub(r'&gt;', '>', compose_text)
    compose_text = re.sub(r'&amp;', '&', compose_text)
    
    # Ensure proper YAML formatting
    lines = compose_text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Remove any HTML tags that might remain
        line = re.sub(r'<[^>]+>', '', line)
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def get_docker_compose(image_name):
    """
    Main function to get the Docker Compose configuration for a given image
    """
    url = build_url(image_name)
    html_content = fetch_page_with_curl(url)
    
    if not html_content:
        print(f"Failed to fetch content for {image_name}", file=sys.stderr)
        return None
    
    service_name = extract_service_name(url, html_content)
    
    compose_text = extract_docker_compose(html_content, service_name)
    
    if not compose_text:
        print(f"No Docker Compose configuration found for {image_name}", file=sys.stderr)
        return None
    
    cleaned_compose = clean_docker_compose(compose_text)
    
    return cleaned_compose


def rewrite_volume_paths(compose_content, image_name=None):
    """
    Rewrite volume paths in Docker Compose config to use ~/Docker/<service_name>/<target_dir> format
    """
    if not compose_content:
        return compose_content
    
    # Try text-based processing (simpler and more reliable for scraped content)
    return process_with_text_replacement(compose_content, image_name)


def process_with_text_replacement(compose_content, image_name):
    """
    Text-based processing for volume path replacement
    """
    lines = compose_content.split('\n')
    modified_lines = []
    
    # Extract image name from content if not provided
    if not image_name:
        image_name = extract_image_name_from_text(compose_content)
    
    for line in lines:
        # Check if this line contains a volume mapping pattern like: "    - /path:/container/path"
        volume_match = re.match(r'^(\s+- )(/[^:]+):(/[^:\s]+)(.*)$', line)
        if volume_match:
            indent, host_path, container_path, rest = volume_match.groups()
            
            # Extract target directory from container path
            target_dir = extract_target_directory(container_path)
            
            # Build new host path
            new_host_path = f"~/Docker/{image_name}/{target_dir}"
            
            # Reconstruct the line
            new_line = f"{indent}{new_host_path}:{container_path}{rest}"
            modified_lines.append(new_line)
        else:
            # Keep the line as-is
            modified_lines.append(line)
    
    return '\n'.join(modified_lines)


def extract_image_name_from_text(compose_content):
    """
    Extract image name from text content
    """
    # Look for LinuxServer images in text
    match = re.search(r'image:\s*[\'"]?(?:lscr\.io/)?linuxserver/([^:\s\'"]+)', compose_content)
    if match:
        return match.group(1)
    
    # Look for service names near "services:" line
    lines = compose_content.split('\n')
    for i, line in enumerate(lines):
        if 'services:' in line and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if ':' in next_line and not next_line.startswith('-'):
                service_name = next_line.split(':')[0].strip()
                if service_name and not service_name.startswith('#'):
                    return service_name
    
    return 'app'  # fallback


def extract_target_directory(container_path):
    """
    Extract the target directory name from a container path
    """
    # Remove leading/trailing slashes and split by slash
    path_parts = container_path.strip('/').split('/')
    
    if not path_parts or path_parts == ['']:
        return 'data'  # fallback name
    
    # Return the last part (deepest directory)
    return path_parts[-1]


def get_docker_compose_rewritten(image_name):
    """
    Main function: get compose config and rewrite volume paths
    THIS IS THE FUNCTION YOU SHOULD CALL!
    """
    # Get the original compose config
    original_compose = get_docker_compose(image_name)
    
    if not original_compose:
        print(f"Could not get compose configuration for {image_name}", file=sys.stderr)
        return None
    
    # Rewrite the volume paths
    modified_compose = rewrite_volume_paths(original_compose, image_name)
    
    return modified_compose  



def docker_compose_to_json(compose_yaml_string):
    """
    Convert Docker Compose YAML string to JSON format
    
    Args:
        compose_yaml_string (str): The YAML string returned from get_docker_compose()
    
    Returns:
        str: JSON formatted string of the Docker Compose configuration
        None: If parsing fails
    """
    if not compose_yaml_string:
        return None
    
    try:
        # Parse the YAML string into a Python dictionary
        compose_dict = yaml.safe_load(compose_yaml_string)
        
        # Convert the dictionary to JSON string with pretty formatting
        json_string = json.dumps(compose_dict, indent=2, ensure_ascii=False)
        
        return json_string
        
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}", file=sys.stderr)
        return None
    except json.JSONEncodeError as e:
        print(f"Error converting to JSON: {e}", file=sys.stderr)
        return None


def ensure_docker_directories(compose_yaml_string):
    """
    Parse Docker Compose YAML string and ensure all host volume directories exist.
    Creates directories if they don't exist.
    
    Args:
        compose_yaml_string (str): The YAML string returned from get_docker_compose()
    
    Returns:
        list: List of directories that were created
        None: If parsing fails
    """
    if not compose_yaml_string:
        print("No compose configuration provided", file=sys.stderr)
        return None
    
    try:
        # Parse the YAML string
        compose_dict = yaml.safe_load(compose_yaml_string)
        
        if not compose_dict or 'services' not in compose_dict:
            print("No services found in compose configuration", file=sys.stderr)
            return []
        
        created_directories = []
        
        # Iterate through all services
        for service_name, service_config in compose_dict['services'].items():
            if 'volumes' not in service_config:
                continue
            
            # Process each volume mapping
            for volume in service_config['volumes']:
                host_path = extract_host_path(volume)
                
                if host_path:
                    # Expand user path (~ to home directory)
                    expanded_path = os.path.expanduser(host_path)
                    
                    # Convert to Path object for easier handling
                    path_obj = Path(expanded_path)
                    
                    # Check if directory exists
                    if not path_obj.exists():
                        try:
                            # Create directory and any necessary parent directories
                            path_obj.mkdir(parents=True, exist_ok=True)
                            created_directories.append(str(path_obj.absolute()))
                            print(f"Created directory: {path_obj.absolute()}")
                            
                        except PermissionError:
                            print(f"Permission denied creating directory: {path_obj.absolute()}", file=sys.stderr)
                        except OSError as e:
                            print(f"Error creating directory {path_obj.absolute()}: {e}", file=sys.stderr)
                    
                    elif not path_obj.is_dir():
                        print(f"Warning: {path_obj.absolute()} exists but is not a directory", file=sys.stderr)
        
        return created_directories
        
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return None


def extract_host_path(volume_string):
    """
    Extract the host path from a Docker volume string.
    Handles various volume formats:
    - "/host/path:/container/path"
    - "/host/path:/container/path:ro"
    - "volume_name:/container/path"
    - "~/Docker/app/config:/app/config"
    
    Args:
        volume_string (str): Volume mapping string from Docker Compose
    
    Returns:
        str: Host path if it's a bind mount, None if it's a named volume or invalid
    """
    if not isinstance(volume_string, str):
        return None
    
    # Split by colon
    parts = volume_string.split(':')
    
    if len(parts) < 2:
        return None
    
    host_part = parts[0].strip()
    
    # Check if it's a bind mount (starts with / or ~ or ./ or ../)
    # Named volumes typically don't start with these characters
    if (host_part.startswith('/') or 
        host_part.startswith('~/') or 
        host_part.startswith('./') or 
        host_part.startswith('../')):
        return host_part
    
    # If it doesn't start with path-like characters, it's probably a named volume
    return None


def create_docker_compose_file(compose_content, image_name, filename="docker-compose.yml"):
    """
    Create a docker compose YAML file in ~/Docker/imagename/ directory.
    
    Args:
        compose_content (str): The docker compose content as a string
        image_name (str): The name of the image/directory to create
        filename (str): Name of the compose file (default: docker-compose.yml)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Construct the target directory path
        home_dir = Path.home()
        target_dir = home_dir / "Docker" / image_name
        
        # Create the directory if it doesn't exist
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created/verified directory: {target_dir}")
        
        # Full path for the compose file
        compose_file_path = target_dir / filename
        
        # Write the compose content to the file
        with open(compose_file_path, 'w', encoding='utf-8') as f:
            f.write(compose_content)
        
        print(f"Successfully created {filename} in {target_dir}")
        print(f"File location: {compose_file_path}")
        
        return True
        
    except Exception as e:
        print(f"Error creating docker compose file: {e}")
        return False
