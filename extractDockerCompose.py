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

def main():
    """
    Main function to extract Docker Compose from any LinuxServer.io image docs
    """
    parser = argparse.ArgumentParser(
        description='Extract Docker Compose configuration from LinuxServer.io documentation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s jellyfin
  %(prog)s plex
  %(prog)s sonarr
  %(prog)s radarr
  %(prog)s https://docs.linuxserver.io/images/docker-nginx/
        """
    )
    parser.add_argument('image', 
                       help='Image name (e.g., jellyfin, plex) or full URL')
    parser.add_argument('-o', '--output', 
                       help='Output filename (default: <service>-docker-compose.yml)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Build the URL
    url = build_url(args.image)
    
    if args.verbose:
        print(f"Target URL: {url}")
    
    print(f"Fetching page content for {args.image}...")
    html_content = fetch_page_with_curl(url)
    
    if not html_content:
        print("Failed to fetch page content.")
        return 1
    
    if args.verbose:
        print(f"Page content length: {len(html_content)} characters")
    
    # Extract service name for better parsing
    service_name = extract_service_name(url, html_content)
    if args.verbose and service_name:
        print(f"Detected service name: {service_name}")
    
    print("Extracting Docker Compose configuration...")
    compose_config = extract_docker_compose(html_content, service_name)
    
    if compose_config:
        cleaned_config = clean_docker_compose(compose_config)
        
        print("\n" + "="*60)
        print("EXTRACTED DOCKER COMPOSE CONFIGURATION:")
        print("="*60)
        print(cleaned_config)
        print("="*60)
        
        # Determine output filename
        if args.output:
            output_file = args.output
        else:
            if service_name:
                output_file = f'{service_name}-docker-compose.yml'
            else:
                # Extract from input argument
                clean_name = args.image.replace('docker-', '').replace('/', '').replace(':', '').split('?')[0]
                if clean_name.endswith('-'):
                    clean_name = clean_name[:-1]
                output_file = f'{clean_name}-docker-compose.yml'
        
        # Save to file
        try:
            with open(output_file, 'w') as f:
                f.write(cleaned_config)
            print(f"\nConfiguration saved to: {output_file}")
        except IOError as e:
            print(f"Warning: Could not save to file: {e}")
        
        return 0
    else:
        print("Could not extract Docker Compose configuration from the page.")
        print("The page structure might have changed or the content is not available.")
        
        if args.verbose:
            print("\nSearching for any YAML-like content...")
            # Try to find any indented content that might be compose-related
            lines = html_content.split('\n')
            in_yaml = False
            yaml_lines = []
            for line in lines:
                if 'services:' in line.lower():
                    in_yaml = True
                    yaml_lines = [line]
                elif in_yaml:
                    if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                        if len(yaml_lines) > 3:  # Only print if we found substantial content
                            print("Found potential YAML content:")
                            print('\n'.join(yaml_lines[:20]))  # First 20 lines
                        break
                    yaml_lines.append(line)
        
        return 1

if __name__ == "__main__":
    exit(main())
