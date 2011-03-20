#!/usr/bin/python

import codecs, sys, os
import ConfigParser, MySQLdb, socket
import re
from datetime import datetime

from github import github

import calendar, rfc822
import pytz
import dateutil.parser

from urllib2 import URLError, HTTPError


sys.stdout = codecs.getwriter('utf8')(sys.stdout)

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
config = ConfigParser.ConfigParser()
config.readfp(open(basedir+'/../dbconfig.ini'))

db = {}
for item in config.items("database"):
	db[item[0]] = item[1]
	
API_KEY  = config.get("github", "key")
USERNAME = config.get("github", "username")
MAX_PAGES = 2
URL_PREFIX = "https://github.com"


dbcxn = MySQLdb.connect(user = db['username'], passwd = db['password'], db = db['database'], host = db['hostname'])
cursor = dbcxn.cursor()

#MAX_PAGES = 1

gh = github.GitHub(USERNAME, API_KEY)

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`) values (%s, %s, %s, %s, %s, %s);'

ls_type = "code"

author = False

for r in gh.repos.forUser(USERNAME):
    ls_source = r.name
    
    p = 1
    keep_going = True
    
    while keep_going:
      try:
      	commits = gh.commits.forBranch(USERNAME, r.name, page=p)
      except HTTPError:
      	commits = ()
      if len(commits) == 0 or p == MAX_PAGES:
        keep_going = False
      else:
        p += 1        
        for c in commits:
          if not hasattr(c.author, 'login'):
            c.author = author
            
          if c.author.login.lower() == USERNAME.lower():
            author = c.author
            #print "%s %s" % (c.id[:7], c.message[:60].split("\n")[0])
            #print c.id
            if not hasattr(c, 'message'):
              c.message = "Empty message"
          
            localdate = dateutil.parser.parse(c.authored_date)
            utcdate = localdate.astimezone(pytz.utc).isoformat()

            cursor.execute(s_sql, (ls_type, c.id, c.message, utcdate, URL_PREFIX+c.url, ls_source))

