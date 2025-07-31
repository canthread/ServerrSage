import os
import subprocess
import sys

def run_with_sudo(command):
    """Run a command with sudo, handling the case where sudo might prompt for password"""
    try:
        # First try without password prompt
        result = subprocess.run(["sudo", "-n"] + command, 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result
        
        # If that fails, try with password prompt
        print("Sudo privileges required. You may be prompted for your password.")
        result = subprocess.run(["sudo"] + command, 
                              capture_output=True, text=True)
        return result
        
    except subprocess.TimeoutExpired:
        print("Sudo command timed out")
        return None
    except Exception as e:
        print(f"Error running sudo command: {e}")
        return None

def setup_nginx(config_string, name, domain_name):
    """Your modified function using run_with_sudo"""
    try:
        filename = f"{name}.{domain_name}"
        sites_available_path = f"/etc/nginx/sites-available/{filename}"
        sites_enabled_path = f"/etc/nginx/sites-enabled/{filename}"
        
        # Write to temp file
        temp_config_path = f"/tmp/{filename}.nginx.conf"
        with open(temp_config_path, 'w') as f:
            f.write(config_string)
        
        # Copy with sudo
        result = run_with_sudo(["cp", temp_config_path, sites_available_path])
        if not result or result.returncode != 0:
            print(f"Failed to copy config file: {result.stderr if result else 'Unknown error'}")
            return False
        
        print(f"Created config file: {sites_available_path}")
        
        # Create symlink if it doesn't exist
        if not os.path.exists(sites_enabled_path):
            result = run_with_sudo(["ln", "-s", sites_available_path, sites_enabled_path])
            if not result or result.returncode != 0:
                print(f"Failed to create symlink: {result.stderr if result else 'Unknown error'}")
                return False
            print(f"Enabled site by linking to: {sites_enabled_path}")
        else:
            print(f"Site already enabled: {sites_enabled_path}")
        
        # Clean up
        os.remove(temp_config_path)
        return True
        
    except Exception as e:
        print(f"Error creating nginx config: {e}")
        return False

# def setup_nginx(config_string, name, domain_name):
#     """
#     Creates an nginx configuration file and enables it by linking to sites-enabled.
#
#     Args:
#         config_string (str): The nginx configuration content
#         name (str): The name part of the filename
#         domain_name (str): The domain name part of the filename
#
#     Returns:
#         bool: True if successful, False otherwise
#     """
#     try:
#         # Create filename pattern: name.domainname
#         filename = f"{name}.{domain_name}"
#
#         # Define paths
#         sites_available_path = f"/etc/nginx/sites-available/{filename}"
#         sites_enabled_path = f"/etc/nginx/sites-enabled/{filename}"
#
#         # Write the config file to sites-available
#         with open(sites_available_path, 'w') as f:
#             f.write(config_string)
#
#         print(f"Created config file: {sites_available_path}")
#
#         # Create symbolic link to sites-enabled
#         if not os.path.exists(sites_enabled_path):
#             os.symlink(sites_available_path, sites_enabled_path)
#             print(f"Enabled site by linking to: {sites_enabled_path}")
#         else:
#             print(f"Site already enabled: {sites_enabled_path}")
#
#         return True
#
#     except PermissionError:
#         print("Error: Permission denied. Run with sudo or as root.")
#         return False
#     except Exception as e:
#         print(f"Error creating nginx config: {e}")
#         return False
#

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


def reload_nginx():
    """
    Reload nginx configuration using systemctl.
    Returns True if successful, False otherwise.
    """
    try:
        result = subprocess.run(
            ['sudo', 'systemctl', 'reload', 'nginx'],
            capture_output=True,
            text=True,
            check=True
        )
        print("Nginx reloaded successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to reload nginx: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error reloading nginx: {e}")
        return False


def restart_nginx():
    """
    Restart nginx service using systemctl.
    Returns True if successful, False otherwise.
    """
    try:
        result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'nginx'],
            capture_output=True,
            text=True,
            check=True
        )
        print("Nginx restarted successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to restart nginx: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error restarting nginx: {e}")
        return False

def reload_and_restart_nginx():
    """
    First reload nginx, then restart it.
    Returns True if both operations succeed, False otherwise.
    """
    print("Reloading nginx configuration...")
    reload_success = reload_nginx()
    
    print("Restarting nginx service...")
    restart_success = restart_nginx()
    
    if reload_success and restart_success:
        print("Both reload and restart completed successfully")
        return True
    else:
        print("One or both operations failed")
        return False

def check_nginx_status():
    """
    Check the status of nginx service.
    Returns True if nginx is active, False otherwise.
    """
    try:
        result = subprocess.run(
            ['sudo', 'systemctl', 'is-active', 'nginx'],
            capture_output=True,
            text=True,
            check=True
        )
        if result.stdout.strip() == 'active':
            print("Nginx is active and running")
            return True
        else:
            print(f"Nginx status: {result.stdout.strip()}")
            return False
    except subprocess.CalledProcessError:
        print("Nginx is not active")
        return False
    except Exception as e:
        print(f"Error checking nginx status: {e}")
        return False
