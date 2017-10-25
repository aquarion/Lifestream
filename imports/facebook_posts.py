
##

#!/usr/bin/python
# Python
import sys
from datetime import datetime
import socket
import logging
import pickle
from datetime import timedelta
import ConfigParser  # For the exceptions

# Libraries
import facebook
import requests

# Local
import lifestream
import CodeFetcher9000

Lifestream = lifestream.Lifestream()

logger = logging.getLogger('Facebook')

lifestream.arguments.add_argument(
    '--reauth',
    required=False,
    help="Get new token",
    default=False,
    action='store_true')


args = lifestream.arguments.parse_args()


socket.setdefaulttimeout(60)  # Force a timeout if twitter doesn't respond


OAUTH_FILENAME = "%s/facebook.oauth" % (
    lifestream.config.get("global", "secrets_dir"))
APP_KEY = lifestream.config.get("facebook", "appid")
APP_SECRET = lifestream.config.get("facebook", "secret")


def authenticate(OAUTH_FILENAME, appid, secret, force_reauth=False):

    try:
        CodeFetcher9000.are_we_working()
        redirect_uri = CodeFetcher9000.get_url()
        UseCodeFetcher = True
    except CodeFetcher9000.WeSayNotToday:
        try:
            redirect_uri = '{}/facebook/catch.php'.format(
                lifestream.config.get(
                    "dayze",
                    "base")),
            UseCodeFetcher = False
        except ConfigParser.Error:
            logger.error("Dayze base not configured")
            print "To catch an OAuth request, you need either CodeFetcher9000 or Dayze configured in config.ini"
            sys.exit(32)

    request_token_url = 'https://www.facebook.com/dialog/oauth?client_id=%s&redirect_uri=%s&response_type=token&scope=user_posts,user_status' % (
        appid, redirect_uri)

    if not force_reauth:
        try:
            f = open(OAUTH_FILENAME, "rb")
            oauth_token = pickle.load(f)
            f.close()
        except:
            logger.error("Couldn't open %s, reloading..." % OAUTH_FILENAME)
            oauth_token = False
    else:
        oauth_token = False

    if(not oauth_token):
        print "Go to the following link in your browser:"
        print request_token_url
        print

        if UseCodeFetcher:
            oauth_redirect = CodeFetcher9000.get_code("access_token")
            access_key = oauth_redirect['access_token'][0]
        else:
            print "If you configure CodeFetcher9000, this is a lot easier."
            print " - "
            access_key = raw_input('What is the PIN? ')

        extend_token_url = "https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s" % (
            appid, secret, access_key)
        extend_token = requests.get(extend_token_url)

        oauth_token = extend_token.json()

        print oauth_token

        delta = timedelta(seconds=int(oauth_token['expires_in']))
        oauth_token['expire_dt'] = datetime.now() + delta

        f = open(OAUTH_FILENAME, "w")
        pickle.dump(oauth_token, f)
        f.close()

    return oauth_token


def some_action(post, graph, profile):

    visible_filters = lifestream.config.get("facebook", "visible_filters")

    filters = {}
    for key, value in lifestream.config.items("facebook:filters"):
        filters[key] = value

    if 'application' in post and 'namespace' in post[
            'application'] and post['application']['namespace'] == "twitter":
        return

    if post['privacy']['value'] == "SELF":
        return

    # pprint(post)

    show = True

    url = "https://www.facebook.com/%s/posts/%s" % (
        profile['id'], post['id'].split("_")[1])

    if post['privacy']['value'] == "CUSTOM":
        if not post['privacy']['allow']:
            logger.info(
                "Ignoring post %s due to an ad-hoc privacy filter" %
                url)
        elif post['privacy']['allow'] in filters:
            filter_name = filters[post['privacy']['allow']]
            # print "... That's the %s filter" % filter_name
            if filter_name in visible_filters:
                # print "... Keep that"
                show = True
            else:
                # print "... hide that"
                show = False
        else:
            logger.error(
                "[ERROR] on %s - List ID %s not known" %
                (url, post['privacy']['allow']))
            show = False

    if not show:
        return

    if 'picture' in post:
        image = post['picture']
    else:
        image = False

    if not 'message' in post:
        post['message'] = ''

    # Lifestream.add_entry(
    #     post['type'],
    #     post['id'],
    #     post['message'],
    #     "facebook",
    #     post['created_time'],
    #     url=url,
    #     fulldata_json=o_item)
    Lifestream.add_entry(
        post['type'],
        post['id'],
        post['message'],
        "facebook",
        post['created_time'],
        url=url,
        image=image,
        fulldata_json=post)

credentials = authenticate(OAUTH_FILENAME, APP_KEY, APP_SECRET, args.reauth)


if datetime.now() > credentials['expire_dt']:
    logger.error("Token has expired! {} days!".format(delta.days))
    print "Token has expired!"

delta = credentials['expire_dt'] - datetime.now()

if delta.days <= 7:
    logger.warning("Token will expire in {} days!".format(delta.days))
    print "Token will expire in {} days!".format(delta.days)
else:
    logger.info("Token will expire in {} days!".format(delta.days))

graph = facebook.GraphAPI(credentials['access_token'], version="2.7")
profile = graph.get_object('me')
posts = graph.get_object(
    "me/posts",
    fields="application,message,type,privacy,status_type,source,properties,link,picture,created_time")

# Wrap this block in a while loop so we can keep paginating requests until
# finished.
page = 0
while True:
    page += 1
    # print "Page ", pagea
    [some_action(post=post, graph=graph, profile=profile)
     for post in posts['data']]
    if page >= 5:
        break
    try:
        # Perform some action on each post in the collection we receive from
        # Facebook.
        # Attempt to make a request to the next page of data, if it exists.
        posts = requests.get(posts['paging']['next']).json()
        #raise KeyError;
    except KeyError:
        # When there are no more pages (['paging']['next']), break from the
        # loop and end the script.
        print "No next"
        break
