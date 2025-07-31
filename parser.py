

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
    parser.add_argument('-ii', '--install_image', 
                        help='Install a docker image from the linuxserver.io repository requires --image or -i to function',
                        required=False, action='store_true')

    parser.add_argument('-i','--image', 
                       help='Image name (e.g., jellyfin, plex) or full URL', required=False)

    parser.add_argument('-p', '--port',
                        help='Port number to use for the service', required=False)
    parser.add_argument('-d', '--domain_name',
                        help='Domain name to use for the service', required=False)
    parser.add_argument('-sd', '--subdomain',
                        help='Subdomain name to use for the service', required=False)
    parser.add_argument('-ca', '--cloudflare_api',
                        help='Cloudflare API key for managing DNS records', required=False)
    parser.add_argument('-s', '--search',
                        help='Search for a specific service or image', required=False,
                        nargs='?', const='all', default=None)
    parser.add_argument('-cd', '--cloudflare_dns', 
                        help='Setup Cloudflare DNS for a service, requires --image and --domain and --ipaddress to work',
                        required=False,
                        action='store_true')

    parser.add_argument('-t', '--test',
                        help='Test the setup by running a specific command',
                        required=False,
                        action='store_true')

    parser.add_argument('-ip', '--ipaddress', 
                        help='IP address to use for the service, required for Cloudflare DNS setup',
                        required=False)


    return parser.parse_args()


# Default server setup will setup only prowlarr, jellyfin, sonarr, radarr 
def defaultServerSetup():

    print("Hello world")
    
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


def setup_docker_service(image_name, domain_name, claude_api_key):
    # create the docker compose 
    docker_compose_yml = df.get_docker_compose(image_name) 
    docker_compose_yml = df.rewrite_volume_paths(docker_compose_yml)

    print("Docker Compose Configuration: \n", docker_compose_yml)

    # write the compose file to appropriate location
    df.ensure_docker_directories(docker_compose_yml)
    df.create_docker_compose_file(docker_compose_yml, image_name)

    df.run_docker_compose(image_name)   

    
def setup_cloudflare(ip_address, image_name, domain_name, cloudflare_api_key, claude_api_key):

    # create the cloudflare subdomain for the service
    cloudflare.create_cloudflare_subdomain(ip_address, image_name, domain_name, cloudflare_api_key)

    #generate nginx cofig 
    nginx_config = claude.generate_nginx_config(image_name, domain_name, claude_api_key)

    print("Nginx Configuration: \n", nginx_config)

    #place in /etc/nginx/sites-available/
    # ln -s to /etc/nginx/sites-enabled/
    nginx.setup_nginx(nginx_config, image_name, domain_name)

    nginx.reload_and_restart_nginx()

    nginx.run_certbot_interactive()


def main():
    args = parseArguments()
    dotenv.load_dotenv()
    claude_api_key = os.getenv("CLUADE_API_KEY") 
    cloudflare_api_key = os.getenv("CLOUDFLARE_API_KEY")

    print("Claude API Key: ", claude_api_key)

    if args.test:
        ipaddress = "95.89.81.41"
        image_name = "prowlarr"
        domain_name = "canthread.com"
        setup_cloudflare(ipaddress, image_name, domain_name, cloudflare_api_key, claude_api_key)

    
    if args.install_image:

        if args.image and args.domain_name:
            image_name = args.image
            domain_name = args.domain_name
            setup_docker_service(image_name, domain_name, claude_api_key)

        else:
            print("Image name is required for installation")
            exit(1)

    if args.search:
        df.get_linuxserver_services()

    if args.subdomain:
        subdomain = args.subdomain
        if args.domain:
            domain = args.domain
            cloudflare.create_cloudflare_subdomain(ipaddress, image_name, domain_name)
        else:
            print("Domain name is required for subdomain setup")
            exit(1)

    if args.cloudflare_dns:
        if args.image and args.domain_name and args.ipaddress:
            image_name = args.image
            domain_name = args.domain_name
            ipaddress = args.ipaddress
            setup_cloudflare(ipaddress, image_name, domain_name, cloudflare_api_key, claude_api_key)
        else:
            print("Image name, domain name, and IP address are required for Cloudflare DNS setup")
            exit(1)
        # cloudflare.create_cloudflare_subdomain("95.89.81.41" , "prowlarr" , domain, cloudflare_api_key)
        #

if __name__== "__main__":
    exit(main())

