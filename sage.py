 
import subprocess
import re
from bs4 import BeautifulSoup
import sys
import argparse
import urllib.parse
import docker_func



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
    url =docker_func.build_url(args.image)
    
    if args.verbose:
        print(f"Target URL: {url}")
    
    print(f"Fetching page content for {args.image}...")
    html_content = docker_func.fetch_page_with_curl(url)
    
    if not html_content:
    # html_content = fetch_page_with_curl(url)
        print("Failed to fetch page content.")
        return 1
    
    if args.verbose:
        print(f"Page content length: {len(html_content)} characters")
    
    # Extract service name for better parsing
    service_name = docker_func.extract_service_name(url, html_content)
    if args.verbose and service_name:
        print(f"Detected service name: {service_name}")
    
    print("Extracting Docker Compose configuration...")
    compose_config = docker_func.extract_docker_compose(html_content, service_name)
    
    if compose_config:
        cleaned_config =docker_func.clean_docker_compose(compose_config)
        
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
