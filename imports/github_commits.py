#!/usr/bin/python
# Python
import logging

import dateutil.parser
import pytz
import requests
import simplejson as json

# Local
import lifestream

# Libraries



Lifestream = lifestream.Lifestream()

USERNAME = lifestream.config.get("github", "username")
TOKEN = lifestream.config.get("github", "auth_token")
MAX_PAGES = 2
URL_PREFIX = "https://github.com"

ls_type = "code"
ls_source = "github"

logger = logging.getLogger("Github")
args = lifestream.arguments.parse_args()


def github_call(path, token, page=1, perpage=100):
    logger.debug("Calling %s" % path)
    gh_url = "https://api.github.com/%s?page=%d&perpage=%d" % (path, page, perpage)
    headers = {"Authorization": "token %s" % token}
    r = requests.get(gh_url, headers=headers)
    if not r.status_code == 200:
        print(r.status_code)
        print(r.url)
        print(r.text)
        raise Exception
    else:
        return json.loads(r.text)


repos = github_call("user/repos", TOKEN)

for repo in repos:
    logger.debug("Hello %s" % repo["name"])
    # if repo['private']:
    # continue;

    commits = github_call("repos/%s/commits" % repo["full_name"], TOKEN)
    for commit in commits:

        if commit["author"] is None:
            author = repo["owner"]["login"]
        else:
            author = commit["author"]["login"]

        if not USERNAME.lower() == author.lower():
            logger.debug("%s - Skipped" % commit["commit"]["message"])
            # print
            continue

        message = "%s: %s" % (repo["name"], commit["commit"]["message"])
        url = commit["url"]
        localdate = dateutil.parser.parse(commit["commit"]["author"]["date"])
        utcdate = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
        id = commit["sha"]

        # print message
        logger.info(message)
        # cursor.execute(s_sql, (ls_type, id, message, utcdate, url, ls_source))
        # print s_sql % (ls_type, id, message, utcdate, url, ls_source)
        Lifestream.add_entry(
            ls_type, id, message, ls_source, utcdate, url=url, fulldata_json=commit
        )
