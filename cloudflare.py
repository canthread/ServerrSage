import json
import sys
import urllib.request
import urllib.parse
import urllib.error

def create_cloudflare_subdomain(ip_address, image_name, domain_name, api_token=None, email=None, api_key=None):
    """
    Create a subdomain in Cloudflare with pattern imagename.domainname.com
    
    Args:
        ip_address (str): The IP address to point the subdomain to
        image_name (str): The image name (will become the subdomain)
        domain_name (str): The domain name (e.g., "example.com")
        api_token (str, optional): Cloudflare API token (recommended method)
        email (str, optional): Cloudflare account email (legacy auth)
        api_key (str, optional): Cloudflare global API key (legacy auth)
    
    Returns:
        dict: Response from Cloudflare API if successful, None if failed
    """
    
    # Validate inputs
    if not all([ip_address, image_name, domain_name]):
        print("Error: ip_address, image_name, and domain_name are required", file=sys.stderr)
        return None
    
    # Authentication setup
    headers = {
        'Content-Type': 'application/json',
    }
    
    if api_token:
        headers['Authorization'] = f'Bearer {api_token}'
    elif email and api_key:
        headers['X-Auth-Email'] = email
        headers['X-Auth-Key'] = api_key
    else:
        print("Error: Must provide either api_token or both email and api_key", file=sys.stderr)
        return None
    
    # Clean up inputs
    image_name = image_name.lower().strip()
    domain_name = domain_name.lower().strip()
    
    # Remove any 'docker-' prefix from image name if present
    if image_name.startswith('docker-'):
        image_name = image_name[7:]
    
    # Create the full subdomain name
    subdomain = f"{image_name}.{domain_name}"
    
    try:
        # Step 1: Get the zone ID for the domain
        zone_id = get_zone_id(domain_name, headers)
        if not zone_id:
            print(f"Error: Could not find zone ID for domain {domain_name}", file=sys.stderr)
            return None
        
        # Step 2: Check if DNS record already exists
        existing_record = check_existing_dns_record(zone_id, subdomain, headers)
        if existing_record:
            print(f"DNS record for {subdomain} already exists. Updating...")
            return update_dns_record(zone_id, existing_record['id'], ip_address, headers)
        
        # Step 3: Create the DNS record
        return create_dns_record(zone_id, subdomain, ip_address, headers)
        
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return None


def make_request(url, headers, method='GET', data=None):
    """
    Make HTTP request using urllib
    """
    try:
        req = urllib.request.Request(url, headers=headers, method=method)
        
        if data:
            req.data = json.dumps(data).encode('utf-8')
        
        with urllib.request.urlopen(req) as response:
            response_data = response.read().decode('utf-8')
            return json.loads(response_data)
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"HTTP Error {e.code}: {error_body}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}", file=sys.stderr)
        return None


def get_zone_id(domain_name, headers):
    """
    Get the Cloudflare zone ID for a domain
    """
    url = f"https://api.cloudflare.com/client/v4/zones?name={domain_name}"
    
    response = make_request(url, headers)
    
    if not response:
        print("Failed to connect to Cloudflare API", file=sys.stderr)
        return None
    
    if not response.get('success'):
        errors = response.get('errors', [])
        messages = response.get('messages', [])
        print(f"Cloudflare API error: {errors}", file=sys.stderr)
        if messages:
            print(f"Messages: {messages}", file=sys.stderr)
        return None
    
    zones = response.get('result', [])
    if not zones:
        print(f"Domain '{domain_name}' not found in your Cloudflare account.", file=sys.stderr)
        print("Troubleshooting steps:", file=sys.stderr)
        print("1. Verify the domain is added to your Cloudflare account", file=sys.stderr)
        print("2. Check your API token has Zone:Read permissions", file=sys.stderr)
        print("3. Ensure the domain name is spelled correctly", file=sys.stderr)
        
        # List available zones for debugging
        list_all_zones(headers)
        return None
    
    return zones[0]['id']


def list_all_zones(headers):
    """
    List all zones in the account for debugging
    """
    url = "https://api.cloudflare.com/client/v4/zones"
    
    response = make_request(url, headers)
    
    if response and response.get('success'):
        zones = response.get('result', [])
        if zones:
            print("\nAvailable domains in your Cloudflare account:", file=sys.stderr)
            for zone in zones:
                print(f"  - {zone.get('name', 'Unknown')}", file=sys.stderr)
        else:
            print("\nNo domains found in your Cloudflare account", file=sys.stderr)
    else:
        print("\nCould not retrieve zones list", file=sys.stderr)


def check_existing_dns_record(zone_id, subdomain, headers):
    """
    Check if a DNS record already exists for the subdomain
    """
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?name={subdomain}&type=A"
    
    response = make_request(url, headers)
    
    if not response or not response.get('success'):
        return None
    
    records = response.get('result', [])
    return records[0] if records else None


def create_dns_record(zone_id, subdomain, ip_address, headers):
    """
    Create a new DNS record
    """
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    
    data = {
        'type': 'A',
        'name': subdomain,
        'content': ip_address,
        'proxied': True,  # Enable Cloudflare proxy
        'ttl': 1  # Auto TTL when proxied
    }
    
    response = make_request(url, headers, method='POST', data=data)
    
    if not response or not response.get('success'):
        errors = response.get('errors', 'Unknown error') if response else 'No response'
        print(f"Failed to create DNS record: {errors}", file=sys.stderr)
        return None
    
    print(f"Successfully created DNS record for {subdomain} -> {ip_address} (proxied)")
    return response


def update_dns_record(zone_id, record_id, ip_address, headers):
    """
    Update an existing DNS record
    """
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
    
    data = {
        'type': 'A',
        'content': ip_address,
        'proxied': True,  # Enable Cloudflare proxy
        'ttl': 1  # Auto TTL when proxied
    }
    
    response = make_request(url, headers, method='PUT', data=data)
    
    if not response or not response.get('success'):
        errors = response.get('errors', 'Unknown error') if response else 'No response'
        print(f"Failed to update DNS record: {errors}", file=sys.stderr)
        return None
    
    print(f"Successfully updated DNS record to {ip_address} (proxied)")
    return response


# Example usage:
def example_usage():
    """
    Example of how to use the function
    """
    # Using API token (recommended)
    api_token = "your_cloudflare_api_token_here"
    
    result = create_cloudflare_subdomain(
        ip_address="192.168.1.100",
        image_name="jellyfin",
        domain_name="example.com",
        api_token=api_token
    )
    
    if result:
        print("Subdomain created successfully!")
        print(json.dumps(result, indent=2))
    else:
        print("Failed to create subdomain")

