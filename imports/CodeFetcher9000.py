import http.server
import urllib.parse
import logging
import ssl
import lifestream
import configparser
import os

logger = logging.getLogger('CodeFetcher')

os.chdir(os.path.dirname(__file__) + '/..')

ServerClass = http.server.HTTPServer
port = int(lifestream.config.get("CodeFetcher9000", "port"))
server_address = ('0.0.0.0', port)
code = False
key_wanted = False


class WeSayNotToday(Exception):
    pass


class MyHandler(http.server.BaseHTTPRequestHandler):

    def __init__(self, req, client_addr, server):
        http.server.BaseHTTPRequestHandler.__init__(
            self,
            req,
            client_addr,
            server)

    # def do_POST(s):
    #     global code
    #     s.send_response(200)
    #     s.end_headers()
    #     print s.headers
    #     varLen = int(s.headers['Content-Length'])
    #     postVars = s.rfile.read(varLen)
    #     print postVars

    def success(s, params):

        f = open('templates/success.html', 'rb')

        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()
        while True:
            file_data = f.read(32768)  # use an appropriate chunk size
            if file_data is None or len(file_data) == 0:
                break
            s.wfile.write(file_data)
        f.close()

    def failure(s, params):

        f = open('templates/failure.html', 'rt')

        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()
        while True:
            file_data = f.read(32768)  # use an appropriate chunk size
            if file_data is None or len(file_data) == 0:
                break
            file_data = file_data.replace('[[params]]', str(params))
            file_data = file_data.replace('[[key_wanted]]', str(key_wanted))
            s.wfile.write(file_data.encode("utf8"))
        f.close()

    def do_GET(s):
        global code
        # varLen = int(s.headers['Content-Length'])
        # postVars = s.rfile.read(varLen)
        # params = parse_qs(s.path[2:])
        parsed = urllib.parse.urlparse(s.path)
        params = urllib.parse.parse_qs(parsed.query)

        if key_wanted in params:
            s.success(params)
            code = params
            return
        elif s.path == '/test/success':
            s.success(params)

        elif s.path == '/test/failure':
            s.failure(params)
        else:
            s.failure(params)


def get_port():
    return server_address[1]


def get_url():
    domain = lifestream.config.get("CodeFetcher9000", "domain")
    return "https://{}:{}/keyback/".format(domain, server_address[1])
    return "https://{}".format(domain)


def are_we_working():
    try:
        certfile = lifestream.config.get("CodeFetcher9000", "certfile")
        f = open(certfile, 'rb')
        f.close()
    except IOError:
        logger.error("Could not read certificate file: {}".format(certfile))
        raise WeSayNotToday()
    except configparser.Error:
        logger.error("Certfile not defined in config")
        raise WeSayNotToday()

    try:
        keyfile = lifestream.config.get("CodeFetcher9000", "keyfile")
        f = open(keyfile, 'rb')
        f.close()
    except IOError:
        logger.error("Could not read key file: {}".format(keyfile))
        raise WeSayNotToday()
    except configparser.Error:
        logger.error("Keyfile not defined in config")
        raise WeSayNotToday()

    return True


def get_code(key_wanted_arg):
    http.server.HTTPServer
    handler_class = MyHandler

    global key_wanted
    key_wanted = key_wanted_arg

    try:
        certfile = lifestream.config.get("CodeFetcher9000", "certfile")
        keyfile = lifestream.config.get("CodeFetcher9000", "keyfile")
    except IOError:
        logger.error("Could not read file")
        raise WeSayNotToday()
    except configparser.Error:
        logger.error("Could not find config")
        raise WeSayNotToday()

    httpd = ServerClass(server_address, handler_class)
    httpd.socket = ssl.wrap_socket(
        httpd.socket,
        certfile=certfile,
        keyfile=keyfile,
        server_side=True)

    sa = httpd.socket.getsockname()
    print("Waiting on {}:{}".format(sa[0], sa[1]))

    while not code:
        httpd.handle_request()

    return code
