
##

#!/usr/bin/python
# Python
import dateutil.parser
import pytz
import sys
from datetime import datetime
import socket
import logging
import pickle
from datetime import timedelta
import time
import hashlib

# Libraries
import requests

# Local
import lifestream
from lifestream import destiny_exceptions
import CodeFetcher9000

Lifestream = lifestream.Lifestream()

logger = logging.getLogger('Destiny2')

lifestream.arguments.add_argument(
    '--reauth',
    required=False,
    help="Get new token",
    default=False,
    action='store_true')

lifestream.arguments.add_argument(
    '--import-all',
    required=False,
    help="Import all data",
    default=False,
    action='store_true')


args = lifestream.arguments.parse_args()


socket.setdefaulttimeout(60)  # Force a timeout if twitter doesn't respond


OAUTH_FILENAME = "%s/bungie.oauth" % (
    lifestream.config.get("global", "secrets_dir"))
APP_KEY = lifestream.config.get("bungie", "key")
APP_CLIENT_ID = lifestream.config.get("bungie", "client_id")
APP_CLIENT_SECRET = lifestream.config.get("bungie", "client_secret")

# authenticate(OAUTH_FILENAME, appid, secret, force_reauth=False):


def authenticate(
        OAUTH_FILENAME,
        api_key,
        client_id,
        client_secret,
        force_reauth=False):

    request_token_url = 'https://www.bungie.net/en/oauth/authorize?client_id=%s&response_type=code&state=6i0mkLx79Hp91nzWVceHrzHG4' % (
        client_id)

    if not force_reauth:
        try:
            f = open(OAUTH_FILENAME, "rb")
            oauth_token = pickle.load(f)
            f.close()
        except:
            logger.error("Couldn't open %s, reloading..." % OAUTH_FILENAME)
            oauth_token = False
    else:
        logger.info("Forcing reauth")
        oauth_token = False

    try:
        CodeFetcher9000.are_we_working()
        CodeFetcher9000.get_url()
        UseCodeFetcher = True
    except CodeFetcher9000.WeSayNotToday:
        try:
            '{}/keyback/destiny'.format(
                lifestream.config.get(
                    "dayze",
                    "base")),
            UseCodeFetcher = False
        except ConfigParser.Error:
            logger.error("Dayze base not configured")
            print "To catch an OAuth request, you need either CodeFetcher9000 or Dayze configured in config.ini"
            sys.exit(32)

    if oauth_token:

        expiration_date = oauth_token['expire_dt']
        if datetime.now() > expiration_date:
            logger.error("Refreshing access token with refresh token")
            oauth_token = refresh_token(
                OAUTH_FILENAME,
                oauth_token,
                client_id,
                client_secret)
            expiration_date = oauth_token['expire_dt']

        refresh_expiration_date = oauth_token['refresh_expire_dt']
        delta = refresh_expiration_date - datetime.now()

        if delta.days <= 7:
            print "Refresh token will expire in {}!".format(lifestream.niceTimeDelta(delta))

        return oauth_token

    # Step 2: Redirect to the provider. Since this is a CLI script we do not
    # redirect. In a web application you would redirect the user to the URL
    # below.

    print "Go to the following link in your browser:"
    print request_token_url
    print

    if UseCodeFetcher:
        oauth_redirect = CodeFetcher9000.get_code("code")
        access_key = oauth_redirect['code'][0]
    else:
        print "If you configure CodeFetcher9000, this is a lot easier."
        print " - "
        access_key = raw_input('What is the PIN? ')

    access_token_url = "https://www.bungie.net/platform/app/oauth/token/"

    payload = {
        'grant_type': 'authorization_code',
        'code': access_key,
        'client_id': client_id,
        'client_secret': client_secret
    }
    access_token = requests.post(access_token_url, data=payload)
    print access_token.text
    oauth_token = access_token.json()

    delta = timedelta(seconds=int(oauth_token['expires_in']))
    oauth_token['expire_dt'] = datetime.now() + delta

    refresh_delta = timedelta(seconds=int(oauth_token['refresh_expires_in']))
    oauth_token['refresh_expire_dt'] = datetime.now() + refresh_delta

    f = open(OAUTH_FILENAME, "w")
    pickle.dump(oauth_token, f)
    f.close()

    return oauth_token


def refresh_token(OAUTH_FILENAME, oauth_token, client_id, client_secret):
    logger.info("Refreshing token...")

    access_token_url = "https://www.bungie.net/platform/app/oauth/token/"

    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': oauth_token['refresh_token'],
        'client_id': client_id,
        'client_secret': client_secret
    }
    extend_token = requests.post(access_token_url, data=payload)
    oauth_token = extend_token.json()

    delta = timedelta(seconds=int(oauth_token['expires_in']))
    oauth_token['expire_dt'] = datetime.now() + delta
    logger.info(
        "New token expires in {}".format(
            lifestream.niceTimeDelta(delta)))

    refresh_delta = timedelta(seconds=int(oauth_token['refresh_expires_in']))
    oauth_token['refresh_expire_dt'] = datetime.now() + refresh_delta

    f = open(OAUTH_FILENAME, "w")
    pickle.dump(oauth_token, f)
    f.close()

    return oauth_token


credentials = authenticate(
    OAUTH_FILENAME,
    APP_KEY,
    APP_CLIENT_ID,
    APP_CLIENT_SECRET,
    args.reauth)


if datetime.now() > credentials['expire_dt']:
    logger.error("Token has expired!")


delta = credentials['expire_dt'] - datetime.now()

logger.info("Token will expire in {}!".format(lifestream.niceTimeDelta(delta)))

delta = credentials['refresh_expire_dt'] - datetime.now()
if delta.days <= 7:
    logger.warning(
        "Refresh Token will expire in {}!".format(
            lifestream.niceTimeDelta(delta)))
else:
    logger.info(
        "Refresh Token will expire in {}!".format(
            lifestream.niceTimeDelta(delta)))

NEXT_REQUEST = datetime.now()


def destinyCall(path, payload={}):

    logger.info("Making a call to {}".format(path))
    global NEXT_REQUEST

    delta = datetime.now() - NEXT_REQUEST

    if delta.seconds > 0:
        logger.warning("throttled, waiting {}".format(delta.seconds))
        time.sleep(delta.seconds)

    ROOT = 'https://www.bungie.net/Platform'
    url = "{}/{}".format(ROOT, path)

    headers = {
        'X-API-Key': APP_KEY,
        "Authorization": '{} {}'.format(
            credentials['token_type'],
            credentials["access_token"])}

    result = requests.get(url, headers=headers, params=payload).json()

    if result['ErrorCode'] != 1:
        logger.error(result['Message'])
        try:
            raise getattr(destiny_exceptions, result['ErrorStatus'])
        except AttributeError:
            raise destiny_exceptions.DestinyException(result['ErrorStatus'])

    request_delta = timedelta(seconds=result['ThrottleSeconds'])
    NEXT_REQUEST = datetime.now()

    return result['Response']


def destinyEntity(entityType, hashIdentifier):
    path = '/Destiny2/Manifest/{entityType}/{hashIdentifier}/'.format(
        entityType=entityType,
        hashIdentifier=hashIdentifier)
    return destinyCall(path)

memberships = destinyCall('User/GetMembershipsForCurrentUser/')

IMAGE_BASE = 'https://www.bungie.net'

MEMBERSHIP_TYPES = {
    0: 'None',
    1: 'TigerXbox',
    2: 'TigerPsn',
    4: 'TigerBlizzard',
    10: 'TigerDemon',
    254: 'BungieNext',
    -1: 'All',
}


def dt_parse(t):
    ret = datetime.strptime(t[0:15], '%Y%m%dT%H%M%S')

    if t[15] == '+':
        ret -= timedelta(hours=int(t[16:18]), minutes=int(t[18:]))
    elif t[15] == '-':
        ret += timedelta(hours=int(t[16:18]), minutes=int(t[18:]))
    elif t[15] == 'Z':
        pass
    else:
        raise Exception("Bad time format %s, %s" % (t, t[15]))
    return ret.replace(tzinfo=pytz.UTC)

for member_data in memberships['destinyMemberships']:
        # [{u'displayName': u'Aquarionic',
        #     u'iconPath': u'/img/theme/destiny/icons/icon_psn.png',
        #     u'membershipId': u'4611686018428725676',
        #     u'membershipType': 2},
        # member_data['membershipType'] = MEMBERSHIP_TYPES[member_data['membershipType']]
    try:
        logger.info(
            "Looking at membership for {}".format(
                MEMBERSHIP_TYPES[
                    member_data['membershipType']]))
        membership = destinyCall(
            'Destiny2/{membershipType}/Profile/{membershipId}/'.format(**member_data), {'components': 'Characters'})
    except destiny_exceptions.DestinyAccountNotFound:
        logger.info(
            "Membership for {} doesn't have D2".format(
                MEMBERSHIP_TYPES[
                    member_data['membershipType']]))
        continue

    character_list = membership['characters']['data'].keys()
    for character_id in character_list:
        character_data = membership['characters']['data'][character_id]
        logger.info("Hello character {}".format(character_id))

        # Useful bits of character data:
        #   u'emblemPath': u'/common/destiny2_content/icons/5dc023c8be5d682eae90be7f5d420f69.jpg',
        #   u'emblemBackgroundPath': u'/common/destiny2_content/icons/e452c62485491a02fbc0e36f06d301d2.jpg',
        #   u'levelProgression'/'level'

        path_params = {
            'membershipType': member_data['membershipType'],
            'membershipId': member_data['membershipId'],
            'characterId': character_id
        }

        path = '/Destiny2/{membershipType}/Account/{membershipId}/Character/{characterId}/Stats/Activities/'.format(
            **path_params)
        query_params = {
            'count': 100,
            'mode': 'None',
            'page': 0
        }

        activities = destinyCall(path, query_params)

        for instance in activities['activities']:
            logger.info("Hello instance {}".format(
                instance['activityDetails']['directorActivityHash']))
            if instance['values']['completed']['basic']['value'] == 0:
                logger.info("...I do not care about your failure")
                continue

            activity = destinyEntity(
                'DestinyActivityDefinition',
                instance['activityDetails']['referenceId'])

            id = hashlib.md5()
            id.update("destiny2")
            id.update(character_id)
            id.update(str(instance['activityDetails']['directorActivityHash']))

            display = activity['displayProperties']

            if 'name' not in display:
		logger.error("Event doesn't have name? Skipping")
		continue

            logger.info("Completed instance {name} at {period}".format(
                name=display['name'], period=instance['period']))

            text = u"%s --- %s" % (display['name'], display['description'])

            localdate = dateutil.parser.parse(instance['period'])
            utcdate = localdate.astimezone(pytz.utc)

            if display['hasIcon']:
                image = IMAGE_BASE + display['icon']
            else:
                image = IMAGE_BASE + character_data['emblemPath']

            item = {
                'instance_info': instance,
                'activity_info': activity
            }

            # print text, image, utcdate, item['accountWide']

            Lifestream.add_entry(
                "gaming",
                id.hexdigest(),
                text,
                "destiny2",
                utcdate,
                url=False,
                image=image,
                fulldata_json=item)
