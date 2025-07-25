import os
import subprocess
import sys


def setup_nginx(config_string, name, domain_name):
    """
    Creates an nginx configuration file and enables it by linking to sites-enabled.
    
    Args:
        config_string (str): The nginx configuration content
        name (str): The name part of the filename
        domain_name (str): The domain name part of the filename
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create filename pattern: name.domainname
        filename = f"{name}.{domain_name}"
        
        # Define paths
        sites_available_path = f"/etc/nginx/sites-available/{filename}"
        sites_enabled_path = f"/etc/nginx/sites-enabled/{filename}"
        
        # Write the config file to sites-available
        with open(sites_available_path, 'w') as f:
            f.write(config_string)
        
        print(f"Created config file: {sites_available_path}")
        
        # Create symbolic link to sites-enabled
        if not os.path.exists(sites_enabled_path):
            os.symlink(sites_available_path, sites_enabled_path)
            print(f"Enabled site by linking to: {sites_enabled_path}")
        else:
            print(f"Site already enabled: {sites_enabled_path}")
        
        return True
        
    except PermissionError:
        print("Error: Permission denied. Run with sudo or as root.")
        return False
    except Exception as e:
        print(f"Error creating nginx config: {e}")
        return False


def run_certbot_interactive(domain=None):
    """
    Start certbot interactively and let the user go through the setup process.
    
    Args:
        domain (str, optional): Specific domain to configure. If None, certbot will ask.
    """
    try:
        # Build the basic certbot command
        cmd = ['sudo', 'certbot', '--nginx']
        
        # Add domain if specified
        if domain:
            cmd.extend(['-d', domain])
        
        print(f"Starting certbot: {' '.join(cmd)}")
        print("You'll now go through certbot's interactive setup...\n")
        
        # Run certbot interactively (inherits terminal input/output)
        result = subprocess.run(cmd)
        
        # Check the return code
        if result.returncode == 0:
            print("\n✅ Certbot completed successfully!")
        else:
            print(f"\n❌ Certbot exited with code {result.returncode}")
            
        return result.returncode == 0
        
    except KeyboardInterrupt:
        print("\n⚠️  Certbot interrupted by user")
        return False
        
    except FileNotFoundError:
        print("❌ Error: certbot not found. Please install it first:")
        print("   sudo apt install certbot python3-certbot-nginx")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


