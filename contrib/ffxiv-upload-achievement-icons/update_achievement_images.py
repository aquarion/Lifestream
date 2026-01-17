#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script to update FFXIV achievement icons from local Saint Coinach data to remote server."""

import argparse
import configparser
import logging
import os
import site
import sys
from stat import S_ISDIR, S_ISREG

from fabric import Connection
from paramiko import ssh_exception as SSH_Exception
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

#### Add imports from lib/python ####

# Add the lib/python directory to the sys.path
basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
site.addsitedir(os.path.join(basedir, "lib", "python"))

from XIVAPI import XIVClient
from SaintCoinach import SaintCoinach

#### Setup ####

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
site.addsitedir(os.path.join(basedir, "..", "imports"))


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
logging.getLogger("paramiko").setLevel(
    logging.WARNING
)  # fabric uses paramiko underneath

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


class SSHClient:
    """SSH client for uploading files to remote server."""

    connection = None
    sftp = False

    def __init__(self, server, username):
        try:
            self.connection = Connection(
                host=server, user=username, connect_kwargs={"compress": True}
            )
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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # cleanup code here
        if self.sftp:
            self.sftp.close()
        if self.connection:
            self.connection.close()


def validate_config(config):
    required_keys = ['remote.remote_server', 'remote.remote_user', ...]
    for key in required_keys:
        if not config.get(*key.split('.')):
            raise ValueError(f"Missing required config: {key}")


def main():
    """Main function to update achievement icons."""

    print("Updating achievement icons")

    # Load and extract all configuration values
    config = configparser.ConfigParser()
    config.read("ffxiv_config.ini")
    
    data_dir = config.get("local", "data_directory")
    icon_directory = config.get("local", "icon_directory")
    remote_server = config.get("remote", "remote_server")
    remote_user = config.get("remote", "remote_user")
    remote_icons = config.get("remote", "remote_icon_directory")

    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)

    # Update the local Saint Coinach achievement database
    database_path = data_dir + "/saintcoinach_achievements.db"
    logger.info("Connecting to local database %s", database_path)
    client = SaintCoinach(database_path, config)
    schema_file_path = os.path.join(basedir, "etc", "achievements_schema.sql")
    client.update_achievement_database(schema_file_path=schema_file_path)

    logger.info("Connecting to remote server %s", remote_server)
    ssh_client = SSHClient(remote_server, remote_user)

    logger.info("Getting achievements")
    rowcount = client.count_achievements()
    achievements = client.list_achievements()

    files = ssh_client.ls(remote_icons)
    logger.info("Found %d files in %s", len(files), remote_icons)

    local_icons = client.find_icons_path(icon_directory)
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
                    remote_filepath = f"{remote_icons}/{icon_path}"
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
                        remote_icons,
                        icon_path,
                    )
                    result = ssh_client.put(
                        f"{local_icons}/{icon_image}", f"{remote_icons}/{icon_path}"
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
                        f"{remote_icons}/{icon_path}"
                    )
            if warning:
                logger.warning("%s : %s", achievement["Name"], message)
            elif message:
                logger.info("%s : %s", achievement["Name"], message)

    print(f"Uploaded {upload_count} icons")


if __name__ == "__main__":
    main()
