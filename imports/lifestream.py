import site
import ConfigParser
import os
import sys
import cymysql as MySQLdb
import codecs
import simplejson

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
site.addsitedir(basedir+"/../lib")

#sys.stdout = codecs.getwriter('utf8')(sys.stdout)

config  = ConfigParser.ConfigParser()
try:
    config.readfp(open(basedir+'/../config.ini'))
except IOError:
    config.readfp(open(os.getcwd()+'/../config.ini'))

def getDatabaseConnection():
  
  db = {}  
  for item in config.items("database"):
  	db[item[0]] = item[1]
  
  dbcxn = MySQLdb.connect(user = db['username'], passwd = db['password'], db = db['database'], host = db['hostname'], charset='utf8')
  #dbcxn.set_character_set('utf8')
  return dbcxn
  
def cursor(dbcxn):
  dbc = dbcxn.cursor()
  dbc.execute('SET NAMES utf8;')
  dbc.execute('SET CHARACTER SET utf8;')
  dbc.execute('SET character_set_connection=utf8;')
  
  return dbc


def convertNiceTime(number,format):
	if format == "decimal" or format == "dec":
		return int(number);

	if format == "binary" or format == "bin":
		return Denary2Binary(number);

	if format == "hex" or format == "hexadecimal":
		print "Converting %s to hex" % number
		return hex(int(number))
	

	if format == "oct" or format == "octal":
		print "Converting %s to oct" % number
		return oct(int(number))
	
	if format == "roman" or format == "roman":
		print "Converting %s to roman" % number
		return int_to_roman(int(number))

	return False;

def niceTimeDelta(timedelta, format="decimal"):

	years = int(timedelta / (60*60*24*365));
	remainder = timedelta % (60*60*24*365);
	days = int(remainder / (60*60*24));
	remainder = timedelta % (60*60*24);
	hours = remainder / (60*60)
	remainder = timedelta % (60*60);
	minutes = remainder / 60


	if int(years) == 1:
		years_message = "1 year, "
	elif years > 1:
		years_message = "%s years, " % convertNiceTime(years, format)
	else:
		years_message = ''

	if (days < 7 and years == 0):
		hours = hours + (24*days)
		days = 0;
	
	#if (hours < 48 and years == 0 and days < 3):
	#	minutes = minutes + (60*hours)
	#	hours = 0;

	if int(days) == 1:
		days_message = "1 day, "
	elif days > 1:
		days_message = "%s days, " % days
	else:
		days_message = ''

	if int(hours) == 1:
		hours_message = "1 hour, "
	elif hours > 1:
		hours_message = "%s hours, " % hours
	else:
		hours_message = ''


	if int(minutes) == 1:
		minutes_message = "1 minute"
	elif minutes > 1:
		minutes_message = "%s minutes" % minutes
	else:
		minutes_message = ''
		
	string = years_message+days_message+hours_message+minutes_message

	if string == "":
		return "seconds"
	else:
		return string

class Lifestream:

	dbcxn  = False
	cursor = False
	config = False

	def __init__(self):
		self.dbcxn = getDatabaseConnection()
		self.cursor = cursor(self.dbcxn)
		self.config = config

	# Lifestream.add_entry(type, id, title, source, date, url='', image='', fulldata_json=False)
	def add_entry(self, type, id, title, source, date, url='', image='', fulldata_json=False, update=False):
		
		if fulldata_json:
			fulldata_json = simplejson.dumps(fulldata_json)

		sql = 'select date_created from lifestream where type = %s and systemid = %s order by date_created desc limit 1 ';
		self.cursor.execute(sql, (type, id))
		if self.cursor.fetchone():
			if not update:
				#print "Ignore - %s" % title
				return False
			else:
				#print "Update - %s" % title
				s_sql = u'UPDATE lifestream set `title`=%s, `url`=%s, `date_created`=%s, `source`=%s, `image`=%s, `fulldata_json`=%s where `systemid`=%s and `type`=%s'
				self.cursor.execute(s_sql, (title, url, date, source, image, fulldata_json, id, type))
		else:
			#print "Insert - %s" % title
			s_sql = u'INSERT INTO lifestream (`type`, `systemid`, `title`, `url`, `date_created`, `source`, `image`, `fulldata_json`) values (%s, %s, %s, %s, %s, %s, %s, %s)'
			self.cursor.execute(s_sql, (type, id, title, url, date, source, image, fulldata_json))
