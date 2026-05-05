# From https://github.com/sixohsix/twitter/blob/master/twitter/oauth.py


def write_token_file(filename, oauth_token, oauth_token_secret):
    """
    Write a token file to hold the oauth token and oauth token secret.
    """
    with open(
        filename, "w"
    ) as oauth_file:  # codeql[py/clear-text-storage-sensitive-data] - intentional: token file stores credentials for OAuth persistence
        oauth_file.write(oauth_token + "\n")
        oauth_file.write(oauth_token_secret + "\n")


def read_token_file(filename):
    """
    Read a token file and return the oauth token and oauth token secret.
    """
    f = open(filename)
    return f.readline().strip(), f.readline().strip()
