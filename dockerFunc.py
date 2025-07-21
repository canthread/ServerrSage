#!/usr/bin/env python3
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

#!/usr/bin/env python3
"""
Function to rewrite Docker Compose volume paths to use standardized ~/Docker/ structure
"""

import yaml
import re
import os


def rewrite_volume_paths(compose_content, image_name=None):
    """
    Rewrite volume paths in Docker Compose config to use ~/Docker/<service_name>/<target_dir> format

    Args:
        compose_content (str): The Docker Compose YAML content as a string
        image_name (str, optional): The image name to use. If not provided, will try to extract from services

    Returns:
        str: Modified Docker Compose YAML content with rewritten volume paths

    Examples:
        - /path/to/jellyfin/library:/config -> ~/Docker/jellyfin/config:/config
        - /path/to/tvseries:/data/tvshows -> ~/Docker/jellyfin/tvshows:/data/tvshows
    """

    try:
        # Parse the YAML content
        compose_data = yaml.safe_load(compose_content)

        if not compose_data or 'services' not in compose_data:
            print("No services found in compose configuration", file=sys.stderr)
            return compose_content

        services = compose_data['services']

        # Process each service
        for service_name, service_config in services.items():
            # Use provided image_name or fall back to service_name
            target_image_name = image_name or service_name

            # Check if this service has volumes
            if 'volumes' not in service_config:
                continue

            volumes = service_config['volumes']
            new_volumes = []

            for volume in volumes:
                if isinstance(volume, str):
                    # Handle string format: "host_path:container_path" or "host_path:container_path:options"
                    new_volume = rewrite_volume_string(volume, target_image_name)
                    new_volumes.append(new_volume)
                elif isinstance(volume, dict):
                    # Handle dict format (long syntax)
                    new_volume = rewrite_volume_dict(volume, target_image_name)
                    new_volumes.append(new_volume)
                else:
                    # Keep as-is if format is not recognized
                    new_volumes.append(volume)

            # Update the volumes in the service config
            compose_data['services'][service_name]['volumes'] = new_volumes

        # Convert back to YAML string
        modified_yaml = yaml.dump(compose_data, default_flow_style=False, sort_keys=False, width=1000)

        return modified_yaml

    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}", file=sys.stderr)
        return compose_content
    except Exception as e:
        print(f"Error processing compose content: {e}", file=sys.stderr)
        return compose_content


def rewrite_volume_string(volume_string, image_name):
    """
    Rewrite a volume string from host_path:container_path to ~/Docker/<image>/<target>:container_path

    Args:
        volume_string (str): Volume mapping like "/path/to/data:/container/path"
        image_name (str): Name of the image/service

    Returns:
        str: Rewritten volume string
    """

    # Split by colon, handling potential mount options
    parts = volume_string.split(':')

    if len(parts) < 2:
        # Not a standard volume mapping, return as-is
        return volume_string

    host_path = parts[0].strip()
    container_path = parts[1].strip()
    mount_options = ':'.join(parts[2:]) if len(parts) > 2 else ''

    # Skip if it's a named volume or special volume (no slash at start)
    if not host_path.startswith('/') and not host_path.startswith('~'):
        return volume_string

    # Extract the target directory name from the container path
    target_dir = extract_target_directory(container_path)

    # Build the new host path
    new_host_path = f"~/Docker/{image_name}/{target_dir}"

    # Reconstruct the volume string
    if mount_options:
        return f"{new_host_path}:{container_path}:{mount_options}"
    else:
        return f"{new_host_path}:{container_path}"


def rewrite_volume_dict(volume_dict, image_name):
    """
    Rewrite a volume dictionary (long syntax) to use the new path structure

    Args:
        volume_dict (dict): Volume configuration in dict format
        image_name (str): Name of the image/service

    Returns:
        dict: Modified volume dictionary
    """

    if 'source' not in volume_dict or 'target' not in volume_dict:
        # Not a bind mount or missing required fields
        return volume_dict

    source_path = volume_dict['source']
    target_path = volume_dict['target']

    # Skip if it's not a file system path
    if not source_path.startswith('/') and not source_path.startswith('~'):
        return volume_dict

    # Extract target directory name
    target_dir = extract_target_directory(target_path)

    # Create new volume dict with updated source
    new_volume_dict = volume_dict.copy()
    new_volume_dict['source'] = f"~/Docker/{image_name}/{target_dir}"

    return new_volume_dict


def extract_target_directory(container_path):
    """
    Extract the target directory name from a container path

    Args:
        container_path (str): Container path like "/config" or "/data/tvshows"

    Returns:
        str: Target directory name

    Examples:
        "/config" -> "config"
        "/data/tvshows" -> "tvshows"
        "/app/data/media" -> "media"
    """

    # Remove leading/trailing slashes and split by slash
    path_parts = container_path.strip('/').split('/')

    if not path_parts or path_parts == ['']:
        return 'data'  # fallback name

    # Return the last part (deepest directory)
    return path_parts[-1]


def extract_image_name_from_compose(compose_content):
    """
    Extract the image name from the compose content if not provided

    Args:
        compose_content (str): Docker Compose YAML content

    Returns:
        str: Extracted image name or None
    """

    try:
        compose_data = yaml.safe_load(compose_content)

        if not compose_data or 'services' not in compose_data:
            return None

        # Look for LinuxServer images
        for service_name, service_config in compose_data['services'].items():
            if 'image' in service_config:
                image = service_config['image']

                # Extract from LinuxServer image names
                if 'linuxserver/' in image or 'lscr.io/linuxserver/' in image:
                    # Extract image name from patterns like:
                    # - linuxserver/jellyfin
                    # - lscr.io/linuxserver/jellyfin:latest
                    match = re.search(r'linuxserver/([^:]+)', image)
                    if match:
                        return match.group(1)

            # Fall back to service name if no image found
            return service_name

        return None

    except Exception as e:
        print(f"Error extracting image name: {e}", file=sys.stderr)
        return None


# Example usage function
def process_compose_with_rewritten_paths(image_name):
    """
    Complete workflow: get compose config and rewrite volume paths

    Args:
        image_name (str): Name of the image to process

    Returns:
        str: Modified compose configuration with rewritten paths
    """

    # Get the original compose config (using the existing function)
    original_compose = get_docker_compose(image_name)

    if not original_compose:
        print(f"Could not get compose configuration for {image_name}", file=sys.stderr)
        return None

    # Rewrite the volume paths
    modified_compose = rewrite_volume_paths(original_compose, image_name)

    return modified_compose


# Test function
def test_rewrite_function():
    """
    Test the volume path rewriting function
    """

    test_compose = """
---
services:
    jellyfin:
        image: lscr.io/linuxserver/jellyfin:latest
    container_name: jellyfin
    environment:
        - PUID=1000
      - PGID=1000
      - TZ=Etc/UTC
    volumes:
        - /path/to/jellyfin/library:/config
      - /path/to/tvseries:/data/tvshows
      - /path/to/movies:/data/movies
    ports:
        - 8096:8096
    restart: unless-stopped
"""

    print("Original compose:")
    print(test_compose)
    print("\n" + "="*50 + "\n")

    modified = rewrite_volume_paths(test_compose, "jellyfin")
    print("Modified compose:")
    print(modified)

