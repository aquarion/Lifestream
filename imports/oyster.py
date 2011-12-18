#!/usr/bin/python

import lifestream
import sys
import mechanize
from BeautifulSoup import BeautifulSoup
import pytz

import hashlib

from datetime import datetime

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)


if (len(sys.argv) < 3):
	print "Usage: %s class oystercard_number" % sys.argv[0]
	sys.exit(5)

TYPE          = sys.argv[1]
OYSTER_NUMBER = sys.argv[2]
USERNAME      = lifestream.config.get("oyster", "username")
PASSWORD      = lifestream.config.get("oyster", "password")

londontime    = pytz.timezone("Europe/London")

`2`
br = mechanize.Browser()
br.set_handle_robots(False)

################ Login

response = br.open("https://oyster.tfl.gov.uk/oyster/entry.do")

br.select_form(name="sign-in")
br['j_password']=PASSWORD
br['j_username']=USERNAME
br.submit()

############### Card Choice

br.select_form(nr=0)
br['cardId']=[OYSTER_NUMBER,]
br.submit()

############### Dashboard

link=br.find_link(text="Journey history")
br.follow_link(link)

link=br.find_link(text="Switch to the previous version")
br.follow_link(link)

############### Journey History

html = br.response().read()
soup = BeautifulSoup(html)

page = 1

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`) values (%s, %s, %s, %s, %s, %s);'

while page < 9:
    
  history = soup.findAll(attrs={"class":"journeyhistory"})[0]
  rows = history.findAll("tr")[1:]
  
  #<tr>
  #<th>Date</th>
  #<th>Time</th>
  #<th>Location</th>
  #<th>Action</th>
  #<th>Fare</th>
  #<th>Price cap</th>
  #<th>Balance</th>
  #</tr>
  
  date = False
  
  events = []
  
  for row in rows:
    cells = row.findAll("td")
    
    if len(cells) < 4:
        continue;
    
    if cells[0] and not cells[0].string.strip() == "&nbsp;":
      date = cells[0].string.strip()

      
    time = cells[1].string.strip()
    location = cells[2].string.strip()
    action = cells[3].string.strip()
    #fare = cells[4].string.strip()
    #price_cap = cells[5].string.strip()
    #balance = cells[6].string.strip()
    
    py_date  = datetime.strptime(date+" "+time, "%d/%m/%y %H:%M")
    loc_date = londontime.localize(py_date)
    utcdate  = loc_date.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
    
    
    events.append({"date":utcdate, 'location':location, 'action':action})
    
    if action == "Entry":
      action = "Entered"
    else:
      action = "Exited"
      
    id = hashlib.md5()
    id.update(utcdate)
    id.update(location)
        
    message = "%s %s" % (action, location)

    cursor.execute(s_sql, ("oyster", id.hexdigest(), message, utcdate, "#", "oyster"))
    
  page += 1
  #link=br.find_link(text="%s" % page)
  #br.follow_link(link)
  #html = br.response().read()
  #soup = BeautifulSoup(html)
  

  
  
  
  
  
  
  
  
  
  
  
  
  
  
