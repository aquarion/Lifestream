import sys
import BaseHTTPServer
import urlparse
import logging
import ssl
import lifestream
import ConfigParser

logger = logging.getLogger('CodeFetcher')

ServerClass  = BaseHTTPServer.HTTPServer
port = int(lifestream.config.get("CodeFetcher9000", "port"))
server_address = ('0.0.0.0', port)
code = False
key_wanted = False

class WeSayNotToday(Exception):
    pass

class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def __init__(self,req,client_addr,server):
        BaseHTTPServer.BaseHTTPRequestHandler.__init__(self,req,client_addr,server)

    # def do_POST(s):
    #     global code
    #     s.send_response(200)
    #     s.end_headers()
    #     print s.headers
    #     varLen = int(s.headers['Content-Length'])
    #     postVars = s.rfile.read(varLen)
    #     print postVars

    def do_GET(s):
        global code
        # varLen = int(s.headers['Content-Length'])
        # postVars = s.rfile.read(varLen)
        # params = parse_qs(s.path[2:])
        parsed = urlparse.urlparse(s.path)
        params = urlparse.parse_qs(parsed.query)

        if key_wanted in params:
            s.send_response(200)
            s.send_header("Content-type", "text/html")
            s.end_headers()
            s.wfile.write("<html><head><title>Code Collector</title></head>")
            s.wfile.write("<body><h1>New Token collected, you can close this tab</h1>")
            s.wfile.write("</body></html>")
            code = params
        else:
            s.send_response(200)
            s.send_header("Content-type", "text/html")
            s.end_headers()
            s.wfile.write("<html><head><title>Code Collector</title></head>")
            s.wfile.write("<body><h1>Access Code Not Found</h1>")
            s.wfile.write("<p>I got the parameters: %s</p>" % params)
            s.wfile.write("<p>I am looking for: %s</p>" % key_wanted)

            js_fragment = """<script type="text/javascript">
                if (window.location.hash) {
                    paramstring = window.location.hash.substring(1);
                    window.location = '/keyback/?'+paramstring;
                } else {
                    console.log("No Fragment");
                }
                
            </script>"""
            s.wfile.write(js_fragment)
            s.wfile.write("</body></html>")


def get_port():
    return server_address[1]

def get_url():
    domain = lifestream.config.get("CodeFetcher9000", "domain")
    return "https://{}:{}/keyback/".format(domain, server_address[1])
    return "https://{}".format(domain)


def are_we_working():
    try:
        certfile=lifestream.config.get("CodeFetcher9000", "certfile")
        f = open(certfile, 'rb')
        f.close()
    except IOError:
        logger.error("Could not read certificate file: {}".format(certfile))
        raise WeSayNotToday()
    except ConfigParser.Error:
        logger.error("Certfile not defined in config")
        raise WeSayNotToday()

    try:
        keyfile=lifestream.config.get("CodeFetcher9000", "keyfile")
        f = open(keyfile, 'rb')
        f.close()
    except IOError:
        logger.error("Could not read key file: {}".format(keyfile))
        raise WeSayNotToday()
    except ConfigParser.Error:
        logger.error("Keyfile not defined in config")
        raise WeSayNotToday()

    return True

def get_code(key_wanted_arg):
    server_class=BaseHTTPServer.HTTPServer
    handler_class=MyHandler

    global key_wanted
    key_wanted = key_wanted_arg

    try:
        certfile=lifestream.config.get("CodeFetcher9000", "certfile")
        keyfile=lifestream.config.get("CodeFetcher9000", "keyfile")
    except IOError:
        logger.error("Could not read file")
        raise WeSayNotToday()
    except ConfigParser.Error:
        logger.error("Could not find config")
        raise WeSayNotToday()

    httpd = ServerClass(server_address, handler_class)
    httpd.socket = ssl.wrap_socket(
        httpd.socket, 
        certfile = certfile, 
        keyfile = keyfile, 
        server_side=True)

    sa = httpd.socket.getsockname()
    print "Waiting on {}:{}".format(sa[0], sa[1])

    while not code:
        httpd.handle_request()

    return code