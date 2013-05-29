import lifestream

def newstat(date, stat, number):
	dbcxn  = lifestream.getDatabaseConnection()
	cursor = lifestream.cursor(dbcxn)
	
	s_sql = u'replace into lifestream_stats (`date`, `statistic`, `number`) values (%s, %s, %s);'
	cursor.execute(s_sql, (date, stat, number))
	
	#print cursor._last_executed
	
	dbcxn.commit();
	return True;
	
