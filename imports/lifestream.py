import site
site.addsitedir("../lib")

import ConfigParser
import os
import MySQLdb
import sys
import codecs

sys.stdout = codecs.getwriter('utf8')(sys.stdout)

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
config  = ConfigParser.ConfigParser()
config.readfp(open(basedir+'/../dbconfig.ini'))

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
  