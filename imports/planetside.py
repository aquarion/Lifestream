#!/usr/bin/python

import lifestream
import requests, hashlib

IMG = "http://art.istic.net/iconography/games/planetside2.png"

characters = ['jascain']


dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

s_sql = u'INSERT IGNORE INTO lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`, `image`) values (%s, %s, %s, NOW(), %s, %s, %s);'

for character in characters:
	charac  = requests.get("http://census.soe.com/get/ps2-beta/character/?name.first_lower=%s" % character)
	xp      = charac.json['character_list'][0]['experience'][0]
	faction = charac.json['character_list'][0]['type']['faction']
	ranki   = requests.get("http://census.soe.com/get/ps2-beta/rank/%s" % xp['rank'])
	rank    = ranki.json['rank_list'][0][faction]['en']
	name    = charac.json['character_list'][0]['name']['first']
	text    = "In Planetside 2, %s achieved the rank %s" % (name, rank)
	url     = "https://players.planetside2.com/#!/%s" % charac.json['character_list'][0]['id']
	
	id = hashlib.md5()
	id.update(text)
	cursor.execute(s_sql, ("gaming", id.hexdigest(), text, url, "Planetside 2", IMG))
