#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script to update FFXIV achievement icons from local Saint Coinach data to remote server."""

import argparse
import configparser
import csv
import io
import logging
import math
import os
import re
import site
import sqlite3
import sys
from glob import iglob
from stat import S_ISDIR, S_ISREG

import requests
from fabric import Connection
from paramiko import ssh_exception as SSH_Exception
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
site.addsitedir(os.path.join(basedir, "..", "imports"))

config = configparser.ConfigParser()
config.read("ffxiv_config.ini")

LOCAL_ICONS_BASE = config.get("local", "icon_local_base")
REMOTE_ICONS = config.get("remote", "icon_remote_location")

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
parser.add_argument("--verbose", action="store_true", help="Enable verbose mode")
args = parser.parse_args()

# Set up logging


class CustomFormatter(logging.Formatter):
    """Custom formatter for colored logging output."""
    grey = "\x1b[38;20m"
    white = "\x1b[1;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format_tmpl = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )

    FORMATS = {
        logging.DEBUG: grey + format_tmpl + reset,
        logging.INFO: white + format_tmpl + reset,
        logging.WARNING: yellow + format_tmpl + reset,
        logging.ERROR: red + format_tmpl + reset,
        logging.CRITICAL: bold_red + format_tmpl + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.WARNING)
logging.getLogger("fabric").setLevel(logging.WARNING)  # for example
logging.getLogger("paramiko").setLevel(logging.WARNING)  # fabric uses paramiko underneath

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
    """Exception raised when an image has been upgraded."""


class SaintCoinach:
    """Interface for working with SaintCoinach achievement database."""

    db_connection = False

    def __init__(self, dbpath):
        self.db_connection = sqlite3.connect(dbpath)
        self.db_connection.row_factory = sqlite3.Row  # add this row

    def count_achievements(self):
        """Count the number of achievements in the database."""
        cursor = self.db_connection.cursor()
        result = cursor.execute("SELECT COUNT(*) FROM achievements")
        return result.fetchone()[0]

    def list_achievements(self):
        """List all achievements in the database."""
        cursor = self.db_connection.cursor()
        result = cursor.execute("SELECT * FROM achievements")
        return result

    def get_achievement(self, achievement_id):
        """Get a specific achievement by ID."""
        cursor = self.db_connection.cursor()
        result = cursor.execute(
            "SELECT * FROM achievements WHERE ID = ?", (achievement_id,)
        )
        record = result.fetchone()
        return record

    def icon_path(self, icon_id):
        """Get the icon path for a given icon ID."""
        icon_id = int(icon_id)
        filename = f"{icon_id:06d}"
        foldername = f"{math.floor(icon_id / 1000) * 1000:06d}"
        return f"{foldername}/{filename}.png"

    def icon_image(self, icon_id):
        """Get the icon image filename for a given icon ID, preferring high quality."""
        local_icons = self.find_icons_path(LOCAL_ICONS_BASE)

        icon_id = int(icon_id)
        filename = f"{icon_id:06d}"
        foldername = f"{math.floor(icon_id / 1000) * 1000:06d}"
        low_quality = f"{foldername}/{filename}.png"
        high_quality = f"{foldername}/{filename}_hr1.png"
        if os.path.isfile(f"{local_icons}/{high_quality}"):
            return high_quality
        return low_quality

    def find_icons_path(self, icon_local_base):
        """Find the path to the icon directory in the local Saint Coinach data."""
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
        icon_directory_path = sorted(dirs).pop() + "/ui/icon"
        # logger.info("Using icon directory %s", icon_directory_path)
        return icon_directory_path


class SSHClient:
    """SSH client for uploading files to remote server."""

    connection = None
    sftp = False

    def __init__(self, server, username):
        try:
            self.connection = Connection(host=server, user=username, connect_kwargs={'compress': True})
        except SSH_Exception.AuthenticationException as e:
            logger.error("Failed to connect to %s as %s: %s", server, username, e)
            self.connection = None

    def ls(self, remotepath):
        """List files in remote directory recursively."""
        all_files = {}
        if not self.sftp:
            self.sftp = self.connection.sftp()
        try:
            files = self.sftp.listdir_attr(remotepath)
            for file in files:
                if S_ISDIR(file.st_mode):
                    all_files = all_files | self.ls(f"{remotepath}/{file.filename}")
                elif S_ISREG(file.st_mode):
                    all_files[f"{remotepath}/{file.filename}"] = file
            return all_files
        except IOError as e:
            logger.error("Error listing directory %s: %s", remotepath, e)
            return {}

    def put(self, localpath, remotepath):
        """Upload a file to the remote server if it doesn't exist or differs."""

        if not self.sftp:
            self.sftp = self.connection.sftp()
        try:
            remote_stat = self.sftp.stat(remotepath)
            local_stat = os.stat(localpath)
            if remote_stat.st_size == local_stat.st_size:
                logger.debug("File %s already exists", remotepath)
                return False
            else:
                logger.debug("File %s exists but is different size", remotepath)
                raise XIVImageUpgraded

        except (IOError, XIVImageUpgraded):
            exploded_path = remotepath.split(os.path.sep)
            imploded_path = os.path.sep.join(exploded_path[:-1])
            logger.debug("Checking for directory %s", imploded_path)
            try:
                self.sftp.stat(imploded_path)
            except IOError:
                self.sftp.mkdir(imploded_path)
                logger.debug("Created directory %s", imploded_path)
            logger.info("Uploading file %s to %s", localpath, remotepath)
            self.sftp.put(localpath, remotepath)
            return True

        return False

    def __del__(self):
        if self.sftp:
            self.sftp.close()
        if self.connection:
            self.connection.close()


class XIVClient:
    """Client for interacting with XIVAPI."""

    def __init__(self, api_key):
        self.api_key = api_key

    def _call(self, url, limit=1000, page=1):
        """Make a call to the XIVAPI."""
        url_base = "https://xivapi.com"
        params = {"private_key": self.api_key}
        if limit:
            params["limit"] = limit
        if page > 1:
            params["page"] = page

        response = requests.get(url_base + url, params=params, timeout=10)
        return response.json()

    def get_achievement(self, identifier):
        """Get a specific achievement by identifier."""
        url = f"/achievement/{identifier}"
        return self._call(url)

    def list_achievements(self):
        """List all achievements from the API."""
        logger.info("Getting achievements")
        url = "/achievement"
        achievements = []
        this_page = self._call(url)
        achievements += this_page["Results"]
        while this_page["Pagination"]["PageNext"]:
            logger.debug(
                "Getting page %s/%s of achievements",
                this_page["Pagination"]["PageNext"],
                this_page["Pagination"]["PageTotal"],
            )
            this_page = self._call(url, page=this_page["Pagination"]["PageNext"])
            achievements += this_page["Results"]
            logger.debug("Next page is %s", this_page["Pagination"]["PageNext"])

        return achievements


def update_achievement_database(db_file):
    """Update the achievement database from the remote CSV file."""
    url = "https://github.com/xivapi/ffxiv-datamining/raw/master/csv/Achievement.csv"
    logger.info("Updating achievement database from %s", url)
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        logger.error(
            "Unable to download achievement database from %s: %s",
            url,
            response.status_code,
        )
        sys.exit(1)
    if os.path.exists(db_file):
        os.remove(db_file)

    conn = sqlite3.connect(db_file)
    schema_file_path = os.path.join(basedir, "etc", "achievements_schema.sql")
    with open(schema_file_path, "r", encoding="utf-8") as schema_file:
        schema_sql = schema_file.read()

    conn.executescript(schema_sql)
    cur = conn.cursor()

    csvfile = io.StringIO(response.text)
    reader = csv.reader(csvfile)

    for row in range(0, 3):
        skipped_row = next(reader)
        logger.debug("Skipping row %d: %s", row, skipped_row)

    logger.info("Inserting achievements into database %s", db_file)

    for row in reader:
        cur.execute(
            f'INSERT INTO achievements VALUES ({",".join(["?"]*len(row))})', row
        )
    conn.commit()
    conn.close()


#  Main


def main():
    """Main function to update achievement icons."""

    print("Updating achievement icons")
    
    data_dir = config.get("local", "data_directory")
    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)
    
    database_path = data_dir + "/saintcoinach_achievements.db"

    update_achievement_database(database_path)

    logger.info(
        "Connecting to local database %s", database_path
    )

    client = SaintCoinach(database_path)

    logger.info("Connecting to remote server %s", config.get("remote", "remote_server"))
    ssh_client = SSHClient(
        config.get("remote", "remote_server"), config.get("remote", "remote_user")
    )

    logger.info("Getting achievements")
    rowcount = client.count_achievements()
    achievements = client.list_achievements()

    files = ssh_client.ls(REMOTE_ICONS)
    logger.info("Found %d files in %s", len(files), REMOTE_ICONS)

    local_icons = client.find_icons_path(LOCAL_ICONS_BASE)
    upload_count = 0

    with logging_redirect_tqdm(loggers=[logger]):
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
                message = (
                    f"Unable to find icon for {achievement['Name']}: "
                    f"{local_icons}/{icon_image}"
                )
            else:
                try:
                    remote_filepath = f"{REMOTE_ICONS}/{icon_path}"
                    if remote_filepath in files:
                        remote_file = files[remote_filepath]
                        if (
                            remote_file.st_size
                            == os.stat(f"{local_icons}/{icon_image}").st_size
                        ):
                            logger.debug("File %s already exists", remote_filepath)
                            continue
                        logger.debug(
                            "File %s exists but is different size", remote_filepath
                        )

                    logger.debug(
                        "File %s does not exist on remote server", remote_filepath
                    )
                    logger.debug(
                        "Uploading %s/%s to %s/%s",
                        local_icons,
                        icon_image,
                        REMOTE_ICONS,
                        icon_path,
                    )
                    result = ssh_client.put(
                        f"{local_icons}/{icon_image}", f"{REMOTE_ICONS}/{icon_path}"
                    )
                    if result:
                        upload_count += 1
                        if icon_path == icon_image:
                            message = (
                                f"Uploaded icon for {achievement['Name']}: {icon_path}"
                            )
                        else:
                            message = f"Uploaded HQ icon for {achievement['Name']}: {icon_path}"
                except IOError:
                    warning = True
                    message = (
                        f"Unable to upload icon for {achievement['Name']}: "
                        f"{REMOTE_ICONS}/{icon_path}"
                    )
            if warning:
                logger.warning("%s : %s", achievement["Name"], message)
            elif message:
                logger.info("%s : %s", achievement["Name"], message)

    print(f"Uploaded {upload_count} icons")


if __name__ == "__main__":
    main()
