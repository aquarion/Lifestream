import requests
import configparser
import logging
from pprint import pprint

import os
import paramiko
import sys


config = configparser.ConfigParser()
config.read('config.ini')

APIKEY = config.get("xivapi", "apikey")
LOCAL_ICONS = config.get("xivapi", "icon_local_location")
REMOTE_ICONS = config.get("xivapi", "icon_remote_location")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
logging.getLogger("paramiko").setLevel(logging.WARN) # for example

class SSHClient:
    
    ssh = False
    sftp = False
    
    def __init__(self, server, username):
      self.ssh = paramiko.SSHClient() 
      self.ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
      self.ssh.connect(server, username=username)

    def put(self, localpath, remotepath):
           
      if not self.sftp:
        self.sftp = self.ssh.open_sftp()
      try:
        stat = self.sftp.stat(remotepath)
        # logger.info("File {} already exists".format(remotepath))
        return False
      except IOError:
        exploded_path = remotepath.split(os.path.sep)
        imploded_path = os.path.sep.join(exploded_path[:-1])
        logger.info("Checking for directory {}".format(imploded_path))
        try:
          self.sftp.stat(imploded_path)
        except IOError:
          self.sftp.mkdir(imploded_path)
          logger.info("Created directory {}".format(imploded_path))
        logger.info("Uploading file {} to {}".format(localpath, remotepath))
        self.sftp.put(localpath, remotepath)

      return True
      

    def __del__(self):
      self.sftp.close()
      self.ssh.close()

class XIVClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def __call(self, url, limit=1000, page=1):
        url_base = "https://xivapi.com"
        params={"private_key": self.api_key}
        if (limit):
            params["limit"] = limit
        if page > 1:
            params["page"] = page

        response = requests.get(url_base + url, params=params)
        return response.json()
  
    def get_achievement(self, id):
        url = f"/achievement/{id}"
        return self.__call(url)
    
    def list_achivements(self):
        logger.info("Getting achivements")
        url = "/achievement"
        achivements = []
        this_page = self.__call(url)
        achivements += this_page['Results']
        while this_page['Pagination']['PageNext']:
            logger.info(f"Getting page {this_page['Pagination']['PageNext']}/{this_page['Pagination']['PageTotal']} of achivements")
            this_page = self.__call(url, page=this_page['Pagination']['PageNext'])
            achivements += this_page['Results']
            logger.info("Next page is {}".format(this_page['Pagination']['PageNext']))

        return achivements 

client = XIVClient(api_key=APIKEY)

ssh_client = SSHClient(config.get("xivapi", "remote_server"), config.get("xivapi", "remote_user"))

achivements = client.list_achivements()

for achivement in achivements:
    #  {'ID': 3210,
    #   'Icon': '/i/000000/000116.png',
    #   'Name': 'On the Proteion I',
    #   'Url': '/Achievement/3210'},
    # logger.info("{}: ".format(achivement['Name']))
    if not achivement['Name']:
       logger.debug(f"No name for {achivement['ID']}")
       continue
    if not achivement['Icon']:
        logger.debug(f"No icon set for {achivement['Name']}")
        continue
    if not os.path.isfile(f"{LOCAL_ICONS}{achivement['Icon']}"):
        logger.info(f"Unable find icon for {achivement['Name']}: {achivement['Icon']}")
    else: 
      try:
        result = ssh_client.put(f"{LOCAL_ICONS}{achivement['Icon']}", f"{REMOTE_ICONS}{achivement['Icon']}")
        if result:
          logger.info(f"Uploaded icon for {achivement['Name']}: {achivement['Icon']}")
      except IOError:
        logger.error(f"Unable to upload icon for {achivement['Name']}: {REMOTE_ICONS}{achivement['Icon']}")
