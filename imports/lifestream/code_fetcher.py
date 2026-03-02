"""CodeFetcher9000 - OAuth callback server for capturing authorization codes."""

import configparser
import http.server
import logging
import os
import ssl
import urllib.parse

from . import config, project_root

logger = logging.getLogger("CodeFetcher")

os.chdir(project_root)

ServerClass = http.server.HTTPServer
port = int(config.get("CodeFetcher9000", "port"))
server_address = ("0.0.0.0", port)
code = False
key_wanted = False


class WeSayNotToday(Exception):
    pass


class MyHandler(http.server.BaseHTTPRequestHandler):

    def __init__(self, req, client_addr, server):
        http.server.BaseHTTPRequestHandler.__init__(self, req, client_addr, server)

    def success(self, params):

        f = open(os.path.join(project_root, "templates/success.html"), "rb")

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        while True:
            file_data = f.read(32768)  # use an appropriate chunk size
            if file_data is None or len(file_data) == 0:
                break
            self.wfile.write(file_data)
        f.close()

    def failure(self, params):

        f = open(os.path.join(project_root, "templates/failure.html"), "rt")

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        while True:
            file_data = f.read(32768)  # use an appropriate chunk size
            if file_data is None or len(file_data) == 0:
                break
            file_data = file_data.replace("[[params]]", str(params))
            file_data = file_data.replace("[[key_wanted]]", str(key_wanted))
            self.wfile.write(file_data.encode("utf8"))
        f.close()

    def do_GET(self):
        global code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if key_wanted in params:
            self.success(params)
            code = params
            return
        elif self.path == "/test/success":
            self.success(params)

        elif self.path == "/test/failure":
            self.failure(params)
        else:
            self.failure(params)


def get_port():
    return server_address[1]


def get_url():
    domain = config.get("CodeFetcher9000", "domain")
    return "https://{}:{}/keyback/".format(domain, server_address[1])


def are_we_working():
    try:
        certfile = config.get("CodeFetcher9000", "certfile")
    except configparser.Error:
        logger.error("Certfile not defined in config")
        raise WeSayNotToday()
    
    try:
        f = open(certfile, "rb")
        f.close()
    except IOError:
        logger.error("Could not read certificate file: {}".format(certfile))
        raise WeSayNotToday()

    try:
        keyfile = config.get("CodeFetcher9000", "keyfile")
    except configparser.Error:
        logger.error("Keyfile not defined in config")
        raise WeSayNotToday()
    
    try:
        f = open(keyfile, "rb")
        f.close()
    except IOError:
        logger.error("Could not read key file: {}".format(keyfile))
        raise WeSayNotToday()

    return True


def get_code(key_wanted_arg):
    http.server.HTTPServer
    handler_class = MyHandler

    global key_wanted
    key_wanted = key_wanted_arg

    try:
        certfile = config.get("CodeFetcher9000", "certfile")
        keyfile = config.get("CodeFetcher9000", "keyfile")
    except IOError:
        logger.error("Could not read file")
        raise WeSayNotToday()
    except configparser.Error:
        logger.error("Could not find config")
        raise WeSayNotToday()

    httpd = ServerClass(server_address, handler_class)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    sa = httpd.socket.getsockname()
    print("Waiting on {}:{}".format(sa[0], sa[1]))

    while not code:
        httpd.handle_request()

    return code
