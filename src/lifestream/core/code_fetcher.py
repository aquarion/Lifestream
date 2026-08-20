"""CodeFetcher9000 - OAuth callback server for capturing authorization codes."""

import configparser
import http.server
import logging
import ssl
import urllib.parse

from lifestream.core.config import config, get_project_root

logger = logging.getLogger("CodeFetcher")

code = False
key_wanted = False


class WeSayNotToday(Exception):
    """Raised when CodeFetcher9000 isn't configured/available; callers should fall back."""

    pass


class MyHandler(http.server.BaseHTTPRequestHandler):
    """Handles the OAuth provider's redirect back to us."""

    def success(self, params) -> None:
        path = get_project_root() / "templates" / "success.html"
        with open(path, "rb") as f:
            data = f.read()

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(data)

    def failure(self, params) -> None:
        path = get_project_root() / "templates" / "failure.html"
        with open(path) as f:
            file_data = f.read()

        file_data = file_data.replace("[[params]]", str(params))
        file_data = file_data.replace("[[key_wanted]]", str(key_wanted))

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(file_data.encode("utf8"))

    def do_GET(self) -> None:
        global code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if key_wanted in params:
            self.success(params)
            code = params
        elif self.path == "/test/success":
            self.success(params)
        else:
            self.failure(params)


def get_url() -> str:
    """URL the OAuth provider should redirect the user's browser back to."""
    domain = config.get("CodeFetcher9000", "domain")
    port = int(config.get("CodeFetcher9000", "port"))
    return f"https://{domain}:{port}/keyback/"


def are_we_working() -> bool:
    """Check that CodeFetcher9000's TLS cert/key are configured and readable."""
    try:
        certfile = config.get("CodeFetcher9000", "certfile")
        keyfile = config.get("CodeFetcher9000", "keyfile")
    except configparser.Error as e:
        logger.error("CodeFetcher9000 not configured: %s", e)
        raise WeSayNotToday() from e

    for path in (certfile, keyfile):
        try:
            with open(path, "rb"):
                pass
        except OSError as e:
            logger.error("Could not read CodeFetcher9000 file %s: %s", path, e)
            raise WeSayNotToday() from e

    return True


def get_code(key_wanted_arg: str):
    """Run a short-lived HTTPS server and block until the OAuth redirect arrives."""
    global code, key_wanted
    key_wanted = key_wanted_arg
    code = False

    certfile = config.get("CodeFetcher9000", "certfile")
    keyfile = config.get("CodeFetcher9000", "keyfile")
    port = int(config.get("CodeFetcher9000", "port"))

    httpd = http.server.HTTPServer(("0.0.0.0", port), MyHandler)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    sa = httpd.socket.getsockname()
    logger.info("Waiting on %s:%s", sa[0], sa[1])

    while not code:
        httpd.handle_request()

    return code
