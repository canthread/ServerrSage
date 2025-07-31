import anthropic
import re
from typing import Optional

def generate_nginx_config(image_name: str, domain_name: str, api_key: Optional[str] = None) -> str:
    """
    Generate nginx reverse proxy config for a given image/service name using Claude API.
    
    Args:
        image_name (str): Name of the Docker image/service
        domain_name (str): Domain name for the nginx config
        api_key (str, optional): Anthropic API key. If None, will try to get from environment
    
    Returns:
        str: The nginx configuration code from Claude's response
    """
    # Initialize the Anthropic client
    if api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        # Will automatically use ANTHROPIC_API_KEY environment variable
        client = anthropic.Anthropic()
    
    # Construct the prompt with domain name
    prompt = f'nginx "{image_name}" http reverse proxy for domain"{image_name}"."{domain_name}" only http no ssl no certificates. just the http. certificates will be manages by other service. '
    
    try:
        # Make the API call
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        # Extract the response content
        response_text = message.content[0].text
        
        # Extract code blocks from the response
        # Look for nginx config code blocks
        code_pattern = r'```(?:nginx|conf|apache)?\n(.*?)```'
        code_matches = re.findall(code_pattern, response_text, re.DOTALL)
        
        if code_matches:
            # Return the first code block found
            return code_matches[0].strip()
        else:
            # If no code blocks, try to extract the main nginx config
            # Look for server blocks
            server_pattern = r'(server\s*{.*?})'
            server_matches = re.findall(server_pattern, response_text, re.DOTALL)
            
            if server_matches:
                return server_matches[0].strip()
            else:
                # Fallback: return the full response
                return response_text.strip()
                
    except Exception as e:
        raise Exception(f"Error calling Claude API: {str(e)}")

