

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

    parser.add_argument('-p', '--port',
                        help='Port number to use for the service', required=False)
    parser.add_argument('-d', '--domain',
                        help='Domain name to use for the service', required=False)
    parser.add_argument('-sd', '--subdomain',
                        help='Subdomain name to use for the service', required=False)
    parser.add_argument('-c', '--cloudflare',
                        help='Cloudflare API key for managing DNS records', required=False)
    parser.add_argument('-s', '--search',
                        help='Search for a specific service or image', required=False,
                        nargs='?', const='all', default=None)

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

    args = parseArguments()

    if args.search:

        print("Hello im searching")
        df.get_linuxserver_services()

if __name__== "__main__":
    exit(main())

