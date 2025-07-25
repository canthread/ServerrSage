

import subprocess
import re
from bs4 import BeautifulSoup
import sys
import argparse
import urllib.parse
import dockerFunc as df
import cloudflare
import dotenv
import os
import nginx
import claude

# parse arguments and return the proceessed arguments
def parseArguments():

    parser = argparse.ArgumentParser(
            description='A simple parser for command line arguments',
            formatter_class=argparse.RawDescriptionHelpFormatter,)

    parser.add_argument('-i','--image', 
                       help='Image name (e.g., jellyfin, plex) or full URL', required=False)

    return parser.parse_args()


# Default server setup will setup only prowlarr, jellyfin, sonarr, radarr 
def defaultServerSetup():
    print("Hello world")
    dotenv.load_dotenv()
    claude_api_key = os.getenv("CLUADE_API_KEY") 
    cloudflare_api_key = os.getenv("CLOUDFLARE_API_KEY")

    # get docker compose configuratoin for prowlarr
    config = df.get_docker_compose("prowlarr")

    # rewrite the volume paths for configuration
    newconfig = df.rewrite_volume_paths(config)

    # place the docker compose configuration in the appropriate directory and ensure the directories exist
    df.ensure_docker_directories(newconfig)

    # generate the nginx configuratio for prowlarr
    # place the nginx configuration in the appropriate directory
    nginxConfig =claude.generate_nginx_config("prowlarr", "canthread.com", claude_api_key)
    nginx.setup_nginx(nginxConfig, "prowlarr", "canthread.com")

    # run certbot to generate the SSL certificate for prowlarr
    nginx.run_certbot_interactive()
    
    # reload and restart nginx to apply the new configuration
    nginx.reload_and_restart_nginx()

    # setup the cloudflare subdomain for prowlarr
    cloudflare.create_cloudflare_subdomain("95.89.81.41" , "prowlarr" , "canthread.com", cloudflare_api_key)



def main():
    config = df.get_docker_compose("prowlarr")

    # rewrite the volume paths for configuration
    newconfig = df.rewrite_volume_paths(config)

    # place the docker compose configuration in the appropriate directory and ensure the directories exist
    df.ensure_docker_directories(newconfig)

    df.create_docker_compose_file(newconfig, "prowlarr")

    #defaultServerSetup()

if __name__== "__main__":
    exit(main())

