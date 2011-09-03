import site
import ConfigParser
import os
import sys
import MySQLdb
import codecs

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
site.addsitedir(basedir+"/../lib")


sys.stdout = codecs.getwriter('utf8')(sys.stdout)

config  = ConfigParser.ConfigParser()
try:
    config.readfp(open(basedir+'/../dbconfig.ini'))
except IOError:
    config.readfp(open(os.getcwd()+'/../dbconfig.ini'))

def getDatabaseConnection():
  
  db = {}  
  for item in config.items("database"):
  	db[item[0]] = item[1]
  
  dbcxn = MySQLdb.connect(user = db['username'], passwd = db['password'], db = db['database'], host = db['hostname'])
  dbcxn.set_character_set('utf8')
  return dbcxn
  
def cursor(dbcxn):
  dbc = dbcxn.cursor()
  dbc.execute('SET NAMES utf8;')
  dbc.execute('SET CHARACTER SET utf8;')
  dbc.execute('SET character_set_connection=utf8;')
  
  return dbc
  