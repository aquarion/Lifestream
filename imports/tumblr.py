#!/usr/bin/python

import lifestream

from pprint import pprint

import sys, urlparse, cPickle as pickle
import simplejson
from datetime import datetime
from time import mktime

from pytumblr import TumblrRestClient
import oauth2 as oauth

Lifestream = lifestream.Lifestream()

OAUTH_TUMBLR  = lifestream.config.get("tumblr", "secrets_file")


def tumblrAuth(config, OAUTH_TUMBLR):
	consumer_key    = config.get("tumblr", "consumer_key")
	consumer_secret = config.get("tumblr", "secret_key")

	request_token_url = 'http://www.tumblr.com/oauth/request_token'
	access_token_url = 'http://www.tumblr.com/oauth/access_token'
	authorize_url = 'http://www.tumblr.com/oauth/authorize'

	try:
		f = open(OAUTH_TUMBLR, "rb")
		oauth_token = pickle.load(f)
		f.close();
	except:
		print "Couldn't open %s, reloading..." % OAUTH_TUMBLR
		oauth_token = False

	if(not oauth_token):
		consumer = oauth.Consumer(consumer_key, consumer_secret)
		client   = oauth.Client(consumer)
		resp, content = client.request(request_token_url, "GET")
		if resp['status'] != '200':
		    raise Exception("Invalid response %s." % resp['status'])

		request_token = dict(urlparse.parse_qsl(content))
		print "Go to the following link in your browser:"
		print "%s?oauth_token=%s" % (authorize_url, request_token['oauth_token'])
		print

		accepted = 'n'
		while accepted.lower() == 'n':
		    accepted = raw_input('Have you authorized me? (y/n) ')
		oauth_verifier = raw_input('What is the PIN? ')

		token = oauth.Token(request_token['oauth_token'], request_token['oauth_token_secret'])
		token.set_verifier(oauth_verifier)
		client = oauth.Client(consumer, token)


		resp, content = client.request(access_token_url, "POST")
		oauth_token = dict(urlparse.parse_qsl(content))
		print resp

		print oauth_token
		print "Access key:", oauth_token['oauth_token']
		print "Access Secret:", oauth_token['oauth_token_secret']

		f = open(OAUTH_TUMBLR, "w")
		pickle.dump(oauth_token, f)
		f.close();
		
	return TumblrRestClient(consumer_key, consumer_secret, oauth_token['oauth_token'], oauth_token['oauth_token_secret'])

tumblr = tumblrAuth(lifestream.config, OAUTH_TUMBLR)

blogs = lifestream.config.get("tumblr","blogs").split(",")

for blog in blogs:
	details = tumblr.posts(blog)
	startat = 0.0;
	max_posts = details['blog']['posts']


	#while startat < max_posts:
	# 	details = tumblr.posts(blog, offset=startat, limit=20)
	# 	startat += 20;

	if True:
		posts = details['posts'];

		#print "%s %d/%d %.2f%%" % (blog, startat,max_posts, (startat/max_posts)*100.0);

		for post in posts:
			id   = post['id'];
			type = post['type']
			url  = post['post_url']
			image = False

			if post.has_key("title") and post['title']:
				title = post['title']
			elif post.has_key("caption"):
				title = post['caption']
			elif post.has_key("text"):
				title = post['text']
			elif post.has_key("body"):
				title = post['body']
			else:
			#	print post
				title = "Tumblr %s" % type

			if type == "quote":
				title = post['text']

			if type == "photo":
				image = post['photos'][0]['original_size']['url']

			Lifestream.add_entry(type, id, title, "tumblr", post['date'], url=url, image=image, fulldata_json=post)
