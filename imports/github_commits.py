#!/usr/bin/python

import lifestream

import pytz
import dateutil.parser
import sys

import urllib2

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

USERNAME   = lifestream.config.get("github", "username")
PASSWORD   = lifestream.config.get("github", "password")
MAX_PAGES  = 2
URL_PREFIX = "https://github.com"


s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`) values (%s, %s, %s, %s, %s, %s);'

ls_type = "code"
ls_source = "github"


import requests
import simplejson as json


def github_call(path, username, password, page = 1, perpage = 100):
	gh_url = 'https://api.github.com/%s?page=%d&perpage=%d' % (path, page, perpage)
	r = requests.get(gh_url, auth=(username, password))
	if not r.status_code == 200:
		print r.status_code
		print r.url
		print r.text
		raise Exception
	else:
		return json.loads(r.text)

repos = github_call("user/repos", USERNAME, PASSWORD)

for repo in repos:
	if repo['private']:
		continue;
		
	commits = github_call("repos/%s/commits" % repo['full_name'], USERNAME, PASSWORD)
	for commit in commits:
		
		if commit['author'] == None:
			author = repo['owner']['login']
		else:
			author = commit['author']['login']
		

		if not USERNAME.lower() == author.lower():
			#print "%s - Skipped" % commit['commit']['message']
			continue
		
		message   = "%s: %s" % (repo['name'], commit['commit']['message'])
		url       = commit['url']
		localdate = dateutil.parser.parse(commit['commit']['author']['date'])
		utcdate   = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
		id        = commit['sha']
		
		#print message
		cursor.execute(s_sql, (ls_type, id, message, utcdate, url, ls_source))
		#print s_sql % (ls_type, id, message, utcdate, url, ls_source)
