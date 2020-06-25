
from __future__ import print_function


#From https://github.com/sixohsix/twitter/blob/master/twitter/oauth.py

def write_token_file(filename, oauth_token, oauth_token_secret):
    """
    Write a token file to hold the oauth token and oauth token secret.
    """
    oauth_file = open(filename, 'w')
    print(oauth_token, file=oauth_file)
    print(oauth_token_secret, file=oauth_file)
    oauth_file.close()

def read_token_file(filename):
    """
    Read a token file and return the oauth token and oauth token secret.
    """
    f = open(filename)
    return f.readline().strip(), f.readline().strip()