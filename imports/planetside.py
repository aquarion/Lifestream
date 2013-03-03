#!/usr/bin/python

import lifestream
import requests, hashlib

IMG = "http://art.istic.net/iconography/games/planetside2.png"

characters = ['jascain', 'aquarion']


dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

s_sql = u'INSERT IGNORE INTO lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`, `image`) values (%s, %s, %s, NOW(), %s, %s, %s);'

for character in characters:
	charac  = requests.get("http://census.soe.com/get/ps2-beta/character/?name.first_lower=%s" % character)
	
	profile = charac.json['character_list'][0]
	xp      = profile['experience'][0]
	faction = profile['type']['faction']
	name    = profile['name']['first']
	
	## 
	ranki   = requests.get("http://census.soe.com/get/ps2-beta/rank/%s" % xp['rank'])
	rank    = ranki.json['rank_list'][0][faction]['en']
	text    = "In Planetside 2, %s achieved the rank %s" % (name, rank)
	url     = "https://players.planetside2.com/#!/%s" % charac.json['character_list'][0]['id']
	
	id = hashlib.md5()
	id.update(text)
	cursor.execute(s_sql, ("gaming", id.hexdigest(), text, url, "Planetside 2", IMG))
	
	if 'stats_daily' in profile.keys():
		stats = profile['stats_daily']
		text = "Played Planetside as %s %s for %s, with a K:D of %2.2f%% (%d:%d)"
		time = lifestream.niceTimeDelta(int(stats['play_time']['value']))
		kd   = float(stats['kill_death_ratio']['value'])
		k    = int(stats['kills']['value'])
		d    = int(stats['deaths']['value'])
		text = text % (rank, name, time, kd, k, d)
		
		id = hashlib.md5()
		id.update(text)
		cursor.execute(s_sql, ("gaming", id.hexdigest(), text, url, "Planetside 2", IMG))
