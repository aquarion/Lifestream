#!/usr/bin/python

import lifestream
import requests, hashlib, ConfigParser
from datetime import datetime

IMG = "http://art.istic.net/iconography/games/planetside2.png"

characters  = lifestream.config.get("planetside", "characters")
characters = characters.split(",");

try:
	api_key = "/s:%s" % lifestream.config.get("planetside", "service_key")
except ConfigParser.NoOptionError:
	api_key = '';

api_base = "http://census.soe.com%s/get/ps2-beta" % api_key

Lifestream = lifestream.Lifestream()


for character in characters:
	charac  = requests.get("%s/character/?name.first_lower=%s" % (api_base, character) )
	
	profile = charac.json['character_list'][0]
	xp      = profile['experience'][0]
	faction = profile['type']['faction']
	name    = profile['name']['first']
	
	## 
	ranki   = requests.get("%s/rank/%s" % (api_base, xp['rank']) )
	rank    = ranki.json['rank_list'][0][faction]['en']
	text    = "In Planetside 2, %s achieved the rank %s" % (name, rank)
	url     = "https://players.planetside2.com/#!/%s" % charac.json['character_list'][0]['id']
	
	id = hashlib.md5()
	id.update(text)

	Lifestream.add_entry("gaming", id.hexdigest(), text, "Planetside 2", datetime.now(), url=url, image=IMG, fulldata_json=profile, ignore=True)
	
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
		Lifestream.add_entry("gaming", id.hexdigest(), text, "Planetside 2", datetime.now(), url=url, image=IMG, fulldata_json=stats, ignore=True)
