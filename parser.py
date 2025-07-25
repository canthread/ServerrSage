

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
    defaultServices = ["prowlarr"]

    config = df.get_docker_compose("prowlarr") 

    newConfig = df.rewrite_volume_paths(config)

    print("\n" + "="*60)
    print("EXTRACTED DOCKER COMPOSE CONFIGURATION:")
    print("="*60)
    print(newconfig)
    print("="*60)

    df.ensure_docker_directories(newConfig)

    
    api =""

    cloudflare.create_cloudflare_subdomain("95.89.81.41" , "test" , "tekebai.com", api)


def main():
    dotenv.load_dotenv()
    claude_api_key = os.getenv("CLUADE_API_KEY") 
    print(claude_api_key)
    nginx.run_certbot_interactive()



    #defaultServerSetup()

if __name__== "__main__":
    exit(main())

