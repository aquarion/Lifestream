#!/usr/bin/python
# -*- coding: utf-8 -*-

# Local
import lifestream
import CodeFetcher9000
import logging
import sys, os

import requests
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient
from pprint import pprint
import pickle
from datetime import datetime
from ipdb import set_trace
import pytz
import hashlib

SCOPE=["wow.profile",]

steamtime = pytz.timezone('Europe/Paris')

Lifestream = lifestream.Lifestream()

OAUTH_FILENAME = "%s/blizzard_user.oauth" % (
    lifestream.config.get("global", "secrets_dir"))
CLIENT_AUTH_FILENAME = "%s/blizzard_app.oauth" % (
    lifestream.config.get("global", "secrets_dir"))
CHARACTER_CACHE = "%s/blizzard.cache" % (
    lifestream.config.get("global", "secrets_dir"))

APP_KEY = lifestream.config.get("blizzard", "key")
APP_SECRET = lifestream.config.get("blizzard", "secret")
APP_REGION = lifestream.config.get("blizzard", "region")

BASE_OAUTH_URL='https://{}.battle.net'.format(APP_REGION)

BASE_API_URL='https://{}.api.blizzard.com'.format(APP_REGION)

logger = logging.getLogger('WoW')


lifestream.arguments.add_argument(
    '--reauth',
    required=False,
    help="Get new token",
    default=False,
    action='store_true')

lifestream.arguments.add_argument(
    '--catchup',
    required=False,
    help="Force sync of all achivements",
    default=False,
    action='store_true')


args = lifestream.arguments.parse_args()


def fetch_new_code():

    try:
        CodeFetcher9000.are_we_working()
        redirect_uri = CodeFetcher9000.get_url()
        UseCodeFetcher = True
    except CodeFetcher9000.WeSayNotToday:
        try:
            redirect_uri = '{}/keyback/wow.py'.format(
                lifestream.config.get(
                    "dayze",
                    "base")),
            UseCodeFetcher = False
        except ConfigParser.Error:
            logger.error("Dayze base not configured")
            print "To catch an OAuth request, you need either CodeFetcher9000 or Dayze configured in config.ini"
            sys.exit(32)

    oauth = OAuth2Session(APP_KEY, redirect_uri=redirect_uri, scope=SCOPE)

    authorization_url, state = oauth.authorization_url('{}/oauth/authorize'.format(BASE_OAUTH_URL))

    print "Go to the following link in your browser:"
    print authorization_url
    print

    if UseCodeFetcher:
        params = CodeFetcher9000.get_code("code")
        oauth_verifier = params['code'][0]
    else:
        print "If you configure CodeFetcher9000, this is a lot easier."
        print " - "
        oauth_verifier = raw_input('What is the PIN? ')



    # headers = {'Content-Type':'application/json'}
    auth = HTTPBasicAuth(APP_KEY, APP_SECRET)
    data = { 'redirect_uri' : redirect_uri,
            'scope' : SCOPE,
            'grant_type' : 'authorization_code',
            'code' : oauth_verifier }

    r = requests.post('{}/oauth/token'.format(BASE_OAUTH_URL), data=data, auth=auth)

    token = r.json()

    token['created_at'] = datetime.now()


    f = open(OAUTH_FILENAME, "w")
    pickle.dump(token, f)
    f.close()

    return token

if not args.reauth:
    try:
        f = open(OAUTH_FILENAME, "rb")
        oauth_token = pickle.load(f)
        f.close()
    except:
        logger.error("Couldn't open %s, reloading..." % OAUTH_FILENAME)
        oauth_token = False
else:
    oauth_token = False

if not oauth_token:
    oauth_token = fetch_new_code();

# ==============================================================

# Application token


try:
    f = open(CLIENT_AUTH_FILENAME, "rb")
    client_token = pickle.load(f)
    f.close()
except:
    logger.error("Couldn't open %s, reloading..." % CLIENT_AUTH_FILENAME)
    client_token = False

if client_token:
    expiration_date = datetime.fromtimestamp(client_token[u'expires_at'])
    if datetime.now() > expiration_date:
        logger.warn("App token has expired! Getting new one")
        client_token = False
    
if not client_token:
    client = BackendApplicationClient(client_id=APP_KEY)
    oauth = OAuth2Session(client=client)
    client_token = oauth.fetch_token(token_url=BASE_OAUTH_URL+'/oauth/token', client_id=APP_KEY, client_secret=APP_SECRET)
    f = open(CLIENT_AUTH_FILENAME, "w")
    pickle.dump(client_token, f)
    f.close()

# ==============================================================


class BlizzardAPI:
    
    token = False
    key = False

    def __init__(self, user_token, app_token):
        self.user_token = user_token
        self.app_token = app_token
        self.user_key = user_token['access_token']
        self.app_key = app_token['access_token']

    def check_token(self):
        URL='{}/oauth/check_token'.format(BASE_OAUTH_URL)
        data={'token':self.user_key}
        r = requests.post(URL,data=data)
        return r.json()

    def get_profile(self):
        try:
            cachefile=os.stat(CHARACTER_CACHE)
            oauthfile=os.stat(OAUTH_FILENAME)
            if oauthfile.st_mtime > cachefile.st_mtime:
                logger.info("Forcing a refresh of the profiles")
                raise BlizzardForceRefreshProfile('Token updated')
            else:
                logger.info("Oauth: {} Cache: {}, not refreshing".format(datetime.fromtimestamp(oauthfile.st_mtime), datetime.fromtimestamp(cachefile.st_mtime)))

            try:
                f = open(CHARACTER_CACHE, "rb")
                profile = pickle.load(f)
                f.close()
            except OSError as e:
                raise BlizzardForceRefreshProfile('Cache file not found')


            if 'error' in profile:
                raise BlizzardForceRefreshProfile('Error in cache file')

            return profile
        except (BlizzardForceRefreshProfile, OSError) as e:
            logger.info("Refreshing profile because {}".format(e))
            URL=u'{}/wow/user/characters'.format(BASE_API_URL)
            headers={'Authorization': 'Bearer {}'.format(self.user_key)}
            r = requests.get(URL,headers=headers)

            if not r.ok:
                logger.error('Error getting characters: ' + r.text)
                sys.exit(5)

            profile = r.json()

            if 'error' in profile:
                raise BlizzardCharacterNotFound(r.text)

            f = open(CHARACTER_CACHE, "w")
            pickle.dump(r.json(), f)
            f.close()
        
        return profile


    def get_character(self, name, realm, fields=[]):
        URL=u'{url}/wow/character/{realm}/{character}'.format(url=BASE_API_URL, realm=realm, character=name)
        data={'fields': ' '.join(fields)}
        headers={'Authorization': 'Bearer {}'.format(self.app_key)}
        #headers={}
        r = requests.get(URL,headers=headers,params=data)
        if r.ok:
            return r.json()
        else:
            raise BlizzardCharacterNotFound('{} on {}'.format(name, realm))

    def get_achievement(self, id):
        URL=u'{url}/wow/achievement/{id}'.format(url=BASE_API_URL, id=id)
        data={'region': APP_REGION }
        headers={'Authorization': 'Bearer {}'.format(self.app_key)}
        r = requests.get(URL,headers=headers,params=data)
        if r.ok:
            return r.json()
        else:
            logger.warn('Achivement not found: ' + r.text)
            raise BlizzardAchivementNotFound('on {}'.format(id))


def log_achievement(item, timestamp, character):
    image = "http://%s.media.blizzard.com/wow/icons/56/%s.jpg" % (
        APP_REGION, item['icon'])
    url = "http://%s.battle.net/wow/en/character/%s/%s/simple" % (
        APP_REGION, character['realm'], character['name'])
    # if item['accountWide']:
    #     text = "%s &mdash; %s" % (item['title'], item['description'])
    # else:
    #     text = "%s earnt %s &mdash; %s" % (character['name'], item['title'], item['description'])

    text = u"%s --- %s" % (item['title'], item['description'])

    date = datetime.fromtimestamp(timestamp / 1000)

    localdate = steamtime.localize(date)
    utcdate = localdate.astimezone(pytz.utc)

    id = hashlib.md5()
    id.update("%d-wow" % item['id'])

    logger.info(u'{}, {}, {}'.format(character['realm'], character['name'],text))

    # print text, image, utcdate, item['accountWide']

    Lifestream.add_entry(
        "gaming",
        id.hexdigest(),
        text,
        "blizzard_wow",
        utcdate,
        url=url,
        image=image,
        fulldata_json=item)

class BlizzardCharacterNotFound(Exception):
    pass

class BlizzardAchivementNotFound(Exception):
    pass

class BlizzardForceRefreshProfile(Exception):
    pass

api = BlizzardAPI(oauth_token, client_token)

########### check age of oauth
creation_date = oauth_token['created_at']
delta = datetime.now() - creation_date

if delta.days >= 28:
    logger.error("User access token is {} days old, please run with --reauth to refresh".format(delta.days))
else:
    logger.info("User access token is {} days old".format(delta.days))

profile = api.get_profile()


########### Check age of app

########## 
for character in profile['characters']:
    logger.info("%s L%d %s" % (character['name'], character['level'], character['class']))
    # pprint(character)
    #Achievement( apikey='Your key', region='us',achievement="" )

    modified = datetime.fromtimestamp(character['lastModified'] / 1000)
    since_login = (datetime.now() - modified).days

    if args.catchup:

        try:
            character_data = api.get_character(character['name'],character['realm'],['achievements', "feed"])
        except BlizzardCharacterNotFound:
            logger.warning("404 getting %s L%d %s" % (character['name'], character['level'], character['class']))
            continue
        
        completed = character_data['achievements']['achievementsCompleted']
        completed_ts = character_data['achievements'][
            'achievementsCompletedTimestamp']
        for index in range(0, len(completed)):
            # print index, completed[index], completed_ts[index]
            try:
                achievement = api.get_achievement(completed[index])
                log_achievement(achievement, completed_ts[index], character)
            except BlizzardAchivementNotFound as e:
                logger.warning("Achievement {} not found".format(achievement))
    else:

        if since_login > 7:
            logger.debug('> 7 days since login, skipping')
            continue

        character_data = api.get_character(character['name'],character['realm'],['achievements', "feed"])

        for item in character_data['feed']:
            if item['type'] in ('ACHIEVEMENT'):
                # pprint(item)
                log_achievement(
                    item['achievement'],
                    item['timestamp'],
                    character)

            elif item['type'] in (u'LOOT', u'BOSSKILL',  u'CRITERIA'):
                pass
            else:
                pprint(item)

