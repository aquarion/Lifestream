#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import configparser
import logging
import math
import os
import re
import site
import sqlite3
import sys
from glob import iglob
from pprint import pprint
from stat import S_ISDIR, S_ISREG

import paramiko
import requests
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
site.addsitedir(basedir + "/../imports")

config = configparser.ConfigParser()
config.read("ffxiv_config.ini")

APIKEY = config.get("xivapi", "apikey")
LOCAL_ICONS_BASE = config.get("local", "icon_local_base")
REMOTE_ICONS = config.get("remote", "icon_remote_location")

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
parser.add_argument("--verbose", action="store_true", help="Enable verbose mode")
args = parser.parse_args()

# Set up logging


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    white = "\x1b[1;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: white + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.WARN)
logging.getLogger("paramiko").setLevel(logging.WARN)  # for example

ch = logging.StreamHandler()
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

# Set debug level based on command line argument
if args.debug:
    logger.setLevel(logging.DEBUG)
    logger.debug("Debug mode enabled")
    ch.setLevel(logging.DEBUG)
if args.verbose:
    logger.setLevel(logging.INFO)
    logger.info("Verbose mode enabled")
    ch.setLevel(logging.INFO)


class XIVImageUpgraded(Exception):
    pass


class SaintCoinach:

    db_connection = False

    def __init__(self, dbpath):
        self.db_connection = sqlite3.connect(dbpath)
        self.db_connection.row_factory = sqlite3.Row  # add this row

    def count_achievements(self):
        cursor = self.db_connection.cursor()
        result = cursor.execute("SELECT COUNT(*) FROM achievements")
        return result.fetchone()[0]

    def list_achievements(self):
        cursor = self.db_connection.cursor()
        result = cursor.execute("SELECT * FROM achievements")
        return result

    def get_achievement(self, achievement_id):
        cursor = self.db_connection.cursor()
        result = cursor.execute(
            "SELECT * FROM achievements WHERE ID = ?", (achievement_id,)
        )
        record = result.fetchone()
        return record

    def icon_path(self, icon_id):
        icon_id = int(icon_id)
        filename = "{:06d}".format(icon_id)
        foldername = "{:06d}".format(math.floor(icon_id / 1000) * 1000)
        return "{}/{}.png".format(foldername, filename)

    def icon_image(self, icon_id):
        local_icons = self.find_icons_path(LOCAL_ICONS_BASE)

        icon_id = int(icon_id)
        filename = "{:06d}".format(icon_id)
        foldername = "{:06d}".format(math.floor(icon_id / 1000) * 1000)
        low_quality = "{}/{}.png".format(foldername, filename)
        high_quality = "{}/{}_hr1.png".format(foldername, filename)
        if os.path.isfile(f"{local_icons}/{high_quality}"):
            return high_quality
        else:
            return low_quality

    def find_icons_path(self, icon_local_base):
        if not os.path.isdir(icon_local_base):
            raise IOError(f"Unable to find icon location {icon_local_base}")

        dirs = []
        for icon_location in iglob(f"{icon_local_base}/*"):
            if os.path.isdir(icon_location):
                dirname = os.path.basename(icon_location)
                # 0000.00.00.0000.0000
                if re.match(r"^\d{4}\.\d{2}\.\d{2}\.\d{4}\.\d{4}$", dirname):
                    dirs.append(icon_location)
        if not dirs:
            raise IOError(
                f"Unable to find icon directory {icon_local_base}/XXXX.XX.XX.0000.0000"
            )
        dir = sorted(dirs).pop() + "/ui/icon"
        logger.info(f"Using icon directory {dir}")
        return dir


class SSHClient:

    ssh = False
    sftp = False

    def __init__(self, server, username):
        self.ssh = paramiko.SSHClient()
        self.ssh.load_host_keys(
            os.path.expanduser(os.path.join("~", ".ssh", "known_hosts"))
        )
        self.ssh.connect(server, username=username, compress=True)
        
    def ls(self, remotepath):
        all_files = {}
        if not self.sftp:
            self.sftp = self.ssh.open_sftp()
        try:
            files = self.sftp.listdir_attr(remotepath)
            for file in files:
                if S_ISDIR(file.st_mode):
                    all_files = all_files | self.ls(f"{remotepath}/{file.filename}")
                elif S_ISREG(file.st_mode):
                    all_files[f"{remotepath}/{file.filename}"] = file
            return all_files
        except IOError as e:
            logger.error(f"Error listing directory {remotepath}: {e}")
            return []

    def put(self, localpath, remotepath, achviement_name="Achievement"):

        if not self.sftp:
            self.sftp = self.ssh.open_sftp()
        try:
            remote_stat = self.sftp.stat(remotepath)
            local_stat = os.stat(localpath)
            if remote_stat.st_size == local_stat.st_size:
                logger.debug("File {} already exists".format(remotepath))
                return False
            else:
                logger.debug("File {} exists but is different size".format(remotepath))
                raise XIVImageUpgraded

        except (IOError, XIVImageUpgraded):
            exploded_path = remotepath.split(os.path.sep)
            imploded_path = os.path.sep.join(exploded_path[:-1])
            logger.debug("Checking for directory {}".format(imploded_path))
            try:
                self.sftp.stat(imploded_path)
            except IOError:
                self.sftp.mkdir(imploded_path)
                logger.debug("Created directory {}".format(imploded_path))
            logger.info("Uploading file {} to {}".format(localpath, remotepath))
            self.sftp.put(localpath, remotepath)
            return True

        return False

    def __del__(self):
        self.sftp.close()
        self.ssh.close()


class XIVClient:

    def __init__(self, api_key):
        self.api_key = api_key

    def __call(self, url, limit=1000, page=1):
        url_base = "https://xivapi.com"
        params = {"private_key": self.api_key}
        if limit:
            params["limit"] = limit
        if page > 1:
            params["page"] = page

        response = requests.get(url_base + url, params=params)
        return response.json()

    def get_achievement(self, id):
        url = f"/achievement/{id}"
        return self.__call(url)

    def list_achievements(self):
        logger.info("Getting achievements")
        url = "/achievement"
        achievements = []
        this_page = self.__call(url)
        achievements += this_page["Results"]
        while this_page["Pagination"]["PageNext"]:
            logger.debug(
                f"Getting page {this_page['Pagination']['PageNext']}/{this_page['Pagination']['PageTotal']} of achievements"
            )
            this_page = self.__call(url, page=this_page["Pagination"]["PageNext"])
            achievements += this_page["Results"]
            logger.debug("Next page is {}".format(this_page["Pagination"]["PageNext"]))

        return achievements


#  Main

print("Updating achievement icons")

logger.info(
    "Connecting to local database {}".format(config.get("local", "saintcoinach_db"))
)

client = SaintCoinach(config.get("local", "saintcoinach_db"))

logger.info(
    "Connecting to remote server {}".format(config.get("remote", "remote_server"))
)
ssh_client = SSHClient(
    config.get("remote", "remote_server"), config.get("remote", "remote_user")
)

logger.info("Getting achievements")
rowcount = client.count_achievements()
achievements = client.list_achievements()

files = ssh_client.ls(REMOTE_ICONS)
logger.info(f"Found {len(files)} files in {REMOTE_ICONS}")   
       
# with logging_redirect_tqdm(loggers=[logger]):
local_icons = client.find_icons_path(LOCAL_ICONS_BASE)
upload_count = 0
for achievement in tqdm(
    achievements, desc="Achievements", unit=" achievement", total=rowcount
):

    #  {'ID': 3210,
    #   'Icon': '/i/000000/000116.png',
    #   'Name': 'On the Proteion I',
    #   'Url': '/Achievement/3210'},
    # logger.info("{}: ".format(achievement['Name']))
    warning = False
    message = False
    if not achievement["Name"]:
        message = f"No name for {achievement['ID']}"
        continue
    if not achievement["Icon"]:
        warning = True
        message = f"No icon set for {achievement['Name']}"
        continue
    icon_path = client.icon_path(achievement["Icon"])
    icon_image = client.icon_image(achievement["Icon"])
    if not os.path.isfile(f"{local_icons}/{icon_image}"):
        warning = True
        message = f"Unable find icon for {achievement['Name']}: {local_icons}/{icon_image}"
    else:
        try:
            remote_filepath = f"{REMOTE_ICONS}/{icon_path}"
            if remote_filepath in files:
                remote_file = files[remote_filepath]
                if remote_file.st_size == os.stat(f"{local_icons}/{icon_image}").st_size:
                    logger.debug(f"File {remote_filepath} already exists")
                    continue
                else:
                    logger.debug(
                        f"File {remote_filepath} exists but is different size"
                    )
        
            logger.debug(f"File {remote_filepath} does not exist on remote server")
            logger.debug(
                f"Uploading {local_icons}/{icon_image} to {REMOTE_ICONS}/{icon_path}"
            )
            result = ssh_client.put(
                f"{local_icons}/{icon_image}",
                f"{REMOTE_ICONS}/{icon_path}",
                achievement["Name"],
            )
            if result:
                upload_count += 1
                if icon_path == icon_image:
                    message = (
                        f"Uploaded icon for {achievement['Name']}: {icon_path}"
                    )
                else:
                    message = (
                        f"Uploaded HQ icon for {achievement['Name']}: {icon_path}"
                    )
        except IOError:
            warning = True
            message = f"Unable to upload icon for {achievement['Name']}: {REMOTE_ICONS}/{icon_path}"
    if warning:
        logger.warning(f"{achievement['name']} : {message}")
    elif message:
        logger.info(f"{achievement['name']} : {message}")

print(f"Uploaded {upload_count} icons")
