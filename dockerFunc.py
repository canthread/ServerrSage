#!/usr/bin/env python3
import yaml
import re
import sys
import json
import os
import sys
from pathlib import Path
import requests
from typing import Optional, Dict, List





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



    import subprocess
import os
from pathlib import Path

def run_docker_compose(image_name):
    """
    Run docker compose up -d for a specific image in ~/Docker/imagename/ directory.
    
    Args:
        image_name (str): The name of the image/directory to run
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Construct the path to the docker compose directory
        home_dir = Path.home()
        compose_dir = home_dir / "Docker" / image_name
        
        # Check if the directory exists
        if not compose_dir.exists():
            print(f"Error: Directory {compose_dir} does not exist")
            return False
        
        # Check if docker-compose.yml or compose.yml exists
        compose_files = ['docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml']
        compose_file_found = False
        
        for compose_file in compose_files:
            if (compose_dir / compose_file).exists():
                compose_file_found = True
                print(f"Found compose file: {compose_file}")
                break
        
        if not compose_file_found:
            print(f"Error: No docker compose file found in {compose_dir}")
            print(f"Looked for: {', '.join(compose_files)}")
            return False
        
        # Change to the directory and run docker compose
        print(f"Running docker compose up -d in {compose_dir}")
        
        result = subprocess.run(
            ['sudo', 'docker', 'compose', 'up', '-d'],
            cwd=compose_dir,
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"Docker compose up successful for {image_name}")
        if result.stdout:
            print("Output:", result.stdout)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to run docker compose for {image_name}: {e}")
        print(f"Error output: {e.stderr}")
        if e.stdout:
            print(f"Standard output: {e.stdout}")
        return False
    except Exception as e:
        print(f"Unexpected error running docker compose for {image_name}: {e}")
        return False

def run_docker_compose_with_options(image_name, extra_args=None):
    """
    Run docker compose with additional options.
    
    Args:
        image_name (str): The name of the image/directory to run
        extra_args (list): Additional arguments to pass to docker compose
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        home_dir = Path.home()
        compose_dir = home_dir / "Docker" / image_name
        
        if not compose_dir.exists():
            print(f"Error: Directory {compose_dir} does not exist")
            return False
        
        # Build the command
        cmd = ['sudo', 'docker', 'compose', 'up', '-d']
        if extra_args:
            cmd.extend(extra_args)
        
        print(f"Running command: {' '.join(cmd)} in {compose_dir}")
        
        result = subprocess.run(
            cmd,
            cwd=compose_dir,
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"Docker compose up successful for {image_name}")
        if result.stdout:
            print("Output:", result.stdout)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to run docker compose for {image_name}: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def stop_docker_compose(image_name):
    """
    Stop docker compose services for a specific image.
    
    Args:
        image_name (str): The name of the image/directory to stop
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        home_dir = Path.home()
        compose_dir = home_dir / "Docker" / image_name
        
        if not compose_dir.exists():
            print(f"Error: Directory {compose_dir} does not exist")
            return False
        
        print(f"Stopping docker compose services in {compose_dir}")
        
        result = subprocess.run(
            ['sudo', 'docker', 'compose', 'down'],
            cwd=compose_dir,
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"Docker compose down successful for {image_name}")
        if result.stdout:
            print("Output:", result.stdout)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to stop docker compose for {image_name}: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def list_available_images():
    """
    List all available image directories in ~/Docker/
    
    Returns:
        list: List of directory names in ~/Docker/
    """
    try:
        home_dir = Path.home()
        docker_dir = home_dir / "Docker"
        
        if not docker_dir.exists():
            print(f"Docker directory {docker_dir} does not exist")
            return []
        
        # Get all subdirectories
        subdirs = [d.name for d in docker_dir.iterdir() if d.is_dir()]
        
        if subdirs:
            print("Available images:")
            for subdir in subdirs:
                print(f"  - {subdir}")
        else:
            print("No image directories found in ~/Docker/")
        
        return subdirs
        
    except Exception as e:
        print(f"Error listing directories: {e}")
        return []


def get_linuxserver_services(include_deprecated: bool = False, include_config: bool = False, paginate: bool = True) -> None:
    """
    Retrieves and prints all services from LinuxServer.io API.
    
    Args:
        include_deprecated (bool): Include deprecated images in the results
        include_config (bool): Include configuration details for each image
        paginate (bool): Use less/more for pagination (like manpages)
    """
    # LinuxServer.io API endpoint
    base_url = "https://api.linuxserver.io/api/v1/images"
    
    # API parameters
    params = {
        'include_config': str(include_config).lower(),
        'include_deprecated': str(include_deprecated).lower()
    }
    
    try:
        # Collect all output in a list if pagination is enabled
        output_lines = []
        
        def print_or_collect(text=""):
            if paginate:
                output_lines.append(text)
            else:
                print(text)
        
        print_or_collect("🔍 Fetching LinuxServer.io services...")
        print_or_collect("=" * 60)
        
        # Make API request
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        # Parse JSON response
        data = response.json()
        
        # Extract LinuxServer services
        linuxserver_images = data.get('data', {}).get('repositories', {}).get('linuxserver', [])
        
        if not linuxserver_images:
            print_or_collect("❌ No services found or unexpected API response format")
            return
        
        print_or_collect(f"📦 Found {len(linuxserver_images)} LinuxServer.io services:")
        print_or_collect()
        
        # Sort services by name for better readability
        sorted_services = sorted(linuxserver_images, key=lambda x: x.get('name', ''))
        
        # Print each service
        for i, service in enumerate(sorted_services, 1):
            name = service.get('name', 'Unknown')
            description = service.get('description', 'No description available')
            category = service.get('category', 'Uncategorized')
            version = service.get('version', 'Unknown')
            stable = service.get('stable', False)
            deprecated = service.get('deprecated', False)
            stars = service.get('stars', 0)
            monthly_pulls = service.get('monthly_pulls', 0)
            
            # Status indicators
            status_indicators = []
            if stable:
                status_indicators.append("✅ Stable")
            else:
                status_indicators.append("⚠️  Unstable")
            
            if deprecated:
                status_indicators.append("🚫 Deprecated")
            
            status = " | ".join(status_indicators)
            
            print_or_collect(f"{i:3d}. 📋 {name}")
            print_or_collect(f"     📝 {description}")
            print_or_collect(f"     🏷️  Category: {category}")
            print_or_collect(f"     🔖 Version: {version}")
            print_or_collect(f"     ⭐ Stars: {stars:,} | 📥 Monthly pulls: {monthly_pulls:,}")
            print_or_collect(f"     🔍 Status: {status}")
            
            # Print GitHub and project URLs if available
            github_url = service.get('github_url', '')
            project_url = service.get('project_url', '')
            
            if github_url:
                print_or_collect(f"     🔗 GitHub: {github_url}")
            if project_url and project_url != github_url:
                print_or_collect(f"     🌐 Project: {project_url}")
            
            print_or_collect()
        
        # If pagination is enabled, pipe output through less
        if paginate and output_lines:
            try:
                # Try 'less' first (better), fallback to 'more'
                pager = subprocess.Popen(['less', '-R'], stdin=subprocess.PIPE, text=True)
                pager.communicate('\n'.join(output_lines))
            except FileNotFoundError:
                try:
                    pager = subprocess.Popen(['more'], stdin=subprocess.PIPE, text=True)
                    pager.communicate('\n'.join(output_lines))
                except FileNotFoundError:
                    # Fallback: just print normally if no pager available
                    for line in output_lines:
                        print(line)
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON response: {e}")
    except KeyError as e:
        print(f"❌ Unexpected API response format: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def search_linuxserver_service(search_term: str) -> None:
    """
    Search for a specific service in LinuxServer.io catalog.
    
    Args:
        search_term (str): Service name to search for
    """
    base_url = "https://api.linuxserver.io/api/v1/images"
    params = {'include_config': 'false', 'include_deprecated': 'true'}
    
    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        linuxserver_images = data.get('data', {}).get('repositories', {}).get('linuxserver', [])
        
        # Search for matching services
        matches = [
            service for service in linuxserver_images 
            if search_term.lower() in service.get('name', '').lower() or 
               search_term.lower() in service.get('description', '').lower()
        ]
        
        if matches:
            print(f"🔍 Found {len(matches)} service(s) matching '{search_term}':\n")
            for service in matches:
                name = service.get('name', 'Unknown')
                description = service.get('description', 'No description available')
                print(f"📋 {name}")
                print(f"   {description}\n")
        else:
            print(f"❌ No services found matching '{search_term}'")
            
    except Exception as e:
        print(f"❌ Error searching services: {e}")

