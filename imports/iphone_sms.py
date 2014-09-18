
import pickle
import sqlite3

from dropbox import client, rest, session

# SOme constants
APPLE_TO_UNIX_CONVERSION = 978307200

# Some Settings

OAUTH_TOKEN_FILE = ".dropbox_session"
DROPBOX_PATH = '/Documents/iPhone Backup/6fe928c857d388710370d7191f398899eac87aac/3d0d7e5fb2ce288813306e4d4636395e047a3d28'
MESSAGES_DATABASE_CACHE = "/home/aquarion/scratch/sms.sqlite"

# SOME DROPBOX Settings
ACCESS_TYPE = "dropbox"
APP_KEY = "mntt25zkcqfeq3r"
APP_SECRET = "jpmlsyh2w8ql7qh"

# Get token data

token_data = open(OAUTH_TOKEN_FILE, "rb")
token = pickle.load(token_data)
token_data.close()

# Setup Dropbox Access

sess = session.DropboxSession(APP_KEY, APP_SECRET, ACCESS_TYPE)
sess.set_token(token['key'], token['secret'])
## client = client.DropboxClient(sess)

# Grab the database
## f, metadata = client.get_file_and_metadata(DROPBOX_PATH)

# Write it out
## out = open(MESSAGES_DATABASE_CACHE, "wb")
# out.write(f.read())
# out.close()

# Connect to it

cxn = sqlite3.connect(MESSAGES_DATABASE_CACHE)

print "HellO"
print cxn

# Get the data

sql = "select message.guid, message.text, message.date, handle.id, message.is_from_me from message, handle where handle.rowid = message.handle_id;"

# 0 - GUID
# 1 - Text
# 2 - Date
# 3 - From
# 4 - Is From Me

res = cxn.execute(sql)
messages = res.fetchall()

exclude = ("86444",  # Twitter
           "google",
           '+447781484000',  # Pingdom
           '3alerts',  # 3
           '+447786204400',  # Paypal
           'irc',
           'halifax'
           )

for message in messages:
    if message[3]in exclude:
        continue
    print message[3], message[1]
