#!/usr/bin/python

import lifestream

import github
import pytz
import dateutil.parser

from urllib2 import URLError, HTTPError

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

API_KEY    = lifestream.config.get("github", "key")
USERNAME   = lifestream.config.get("github", "username")
MAX_PAGES  = 2
URL_PREFIX = "https://github.com"

gh = github.GitHub(USERNAME, API_KEY)

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`) values (%s, %s, %s, %s, %s, %s);'

ls_type = "code"

author = False

for r in gh.repos.forUser(USERNAME):
    ls_source = "github"
    
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
              
            
            c.message = "%s: %s" % (r.name, c.message)
            
            if len(c.message) > 250:
		          c.message = c.message[0:250]
		        
            localdate = dateutil.parser.parse(c.authored_date)
            utcdate = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
            cursor.execute(s_sql, (ls_type, c.id, c.message, utcdate, URL_PREFIX+c.url, ls_source))

