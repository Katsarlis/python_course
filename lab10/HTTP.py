import asyncore
import asynchat
import multiprocessing
import logging
import mimetypes
import os
import urllib
import argparse
import time


def url_normalize(path):
    if path.startswith("."):
        path = "/" + path
    while "../" in path:
        p1 = path.find("/..")
        p2 = path.rfind("/", 0, p1)
        if p2 != -1:
            path = path[:p2] + path[p1 + 3:]
        else:
            path = path.replace("/..", "", 1)
    path = path.replace("/./", "/")
    path = path.replace("/.", "")
    return path


def to_byte(string):
    return bytes(str(string), 'utf-8')


class FileProducer(object):
    def __init__(self, file, chunk_size=4096):
        self.file = file
        self.chunk_size = chunk_size

    def more(self):
        if self.file:
            data = self.file.read(self.chunk_size)
            if data:
                return data
            self.file.close()
            self.file = None
        return ""


class AsyncHTTPServer(asyncore.dispatcher):
    def __init__(self, host="127.0.0.1", port=9000):
        super().__init__()
        self.create_socket()
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(5)

    def handle_accepted(self, sock, addr):
        self.log(f"Incoming connection from {addr}")
        AsyncHTTPRequestHandler(sock)

    def serve_forever(self):
        asyncore.loop()


class AsyncHTTPRequestHandler(asynchat.async_chat):
    def __init__(self, sock):
        super().__init__(sock)
        self.socket = sock
        self.set_terminator(b"\r\n\r\n")
        self.isParsed = False
        self.protocol_version = "1.1"
        self.request_headers = {}
        self.response_headers = {
            'Host': "127.0.0.1",
            'Server': "Async HTTP server",
            'Date': self.date_time_string()
        }
        self.body = ""

    def collect_incoming_data(self, data):
        self.log(f"Incoming data: {data}")
        self._collect_incoming_data(data)

    def found_terminator(self):
        self.parse_request()

    def parse_request(self):
        self.log(">>Parsing request")
        if not self.isParsed:
            if not self.parse_headers():
                self.respond(400)
                return
            if self.method == "POST":
                content_length = self.request_headers['Content-Length']
                self.log(f">>>>>PARSING, METHOD IS POST, length is {content_length}")
                if content_length != "0":
                    self.set_terminator(content_length)
                else:
                    self.handle_request()
            else:
                self.handle_request()
        else:
            self.body = self._get_data()
            self.handle_request()

    def parse_headers(self):
        # TODO refactor
        self.log(">>>Parsing headers")
        raw = str(self.incoming[0])

        raw = raw[2:-1]
        state, headers = raw.split("\\r\\n", 1)
        self.log(f"STATE IS {state}, HEADERS IS {headers}")

        self.method = state.split(" ")[0].replace("b'", "")
        self.request_headers['method'] = self.method
        self.uri = state.split(" ")[1]
        if "?" in self.uri:
            self.uri, self.query_string = self.uri.split("?")
        self.request_headers["uri"] = self.uri
        self.protocol = state.split(" ")[2]
        self.request_headers['protocol'] = self.protocol

        for string in headers.split("\\r\\n"):
            h = string.split(": ")
            self.request_headers[h[0]] = h[1]

        self.isParsed = True
        self.log(self.request_headers)
        return True

    def handle_request(self):
        self.log(f"Handling {self.method} request")
        method_name = 'do_' + self.method
        if not hasattr(self, method_name):
            self.respond(405)
        else:
            handler = getattr(self, method_name)
            handler()

    def respond(self, code, data=''):
        self.log(f"Responding with code {code}")
        try:
            message, _ = self.responses[code]
        except KeyError:
            message = '???'

        if len(data) > 0:
            self.response_headers["Content-Length"] = len(data)

        self.begin_response(code, message)
        self.send_response(data)
        self.add_terminator(2)
        self.close_when_done()

    def begin_response(self, code, message):
        self.log(f">>Begin response")
        self.log(f"{self.protocol} {code} {message}")
        self.push(to_byte(f"{self.protocol} {code} {message}\r\n"))
        self.log(f"Response headers: {self.response_headers}")
        for key, value in self.response_headers.items():
            self.send_header(key, value)
        self.add_terminator()

    def send_header(self, keyword, value):
        self.log(f">>PUSHING HEADER {keyword} {value}")
        self.push(to_byte("{}: {}\r\n".format(keyword, value)))

    def send_response(self, data):
        self.log(f">>Sending response")
        if self.method == 'POST':
            pass
        else:
            if len(data) > 0 and self.method != "HEAD":
                if self.isText:
                    self.push(to_byte(data))
                else:
                    self.push(data)

    def do_GET(self):
        self.log(">>Do_get")
        self.send_head()

    def do_HEAD(self):
        self.log(">>Do_head")
        self.send_head()

    def do_POST(self):
        self.log(">>Do_post")
        if self.uri.endswith('.html'):
            self.respond(400)
        else:
            self.response_headers['Content-Length'] = len(self.body)
            self.respond(200)

    def send_head(self):
        self.log(f">>Sending head")
        path = self.translate_path(self.uri)

        self.log(f"Current directory is {os.getcwd()}, path is {path}")

        if os.path.isdir(path) or path == "":
            path = os.path.join(path, "index.html")
            if not os.path.exists(path):
                self.respond(403)

        data = ""

        _, ext = os.path.splitext(path)

        try:
            ctype = mimetypes.types_map[ext.lower()]
            self.log(f">>>>> File type is {ctype}")
            self.isText = ctype in self.text_types
        except KeyError:
            self.respond(403)

        try:
            if self.isText:
                self.log(">>This is a text type")
                read_mode = "r"
            else:
                self.log(">>This is NOT a text type")
                read_mode = "rb"
            f = open(path, read_mode)
            data = f.read()
            self.log(f"Read {len(data)} bytes")
            f.close()
            # При тесте картинок добавить бинарное чтение
        except IOError:
            self.respond(404)
            return None

        self.response_headers["Content-Type"] = ctype
        self.respond(200, data)

    def translate_path(self, path):
        self.log("************Translating path")
        path = url_normalize(urllib.parse.unquote(path))
        self.log(f"Path after unquoting {path}")
        if path.startswith("/"):
            path = path[1:]
        return path

    def add_terminator(self, count=1):
        self.push(to_byte(count * "\r\n"))

    def date_time_string(self):
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())

    responses = {
        200: ('OK', 'Request fulfilled, document follows'),
        400: ('Bad Request',
              'Bad request syntax or unsupported method'),
        403: ('Forbidden',
              'Request forbidden -- authorization will not help'),
        404: ('Not Found', 'Nothing matches the given URI'),
        405: ('Method Not Allowed',
              'Specified method is invalid for this resource.'),
    }

    text_types = ["text/html"]


def parse_args():
    parser = argparse.ArgumentParser("Simple asynchronous web-server")
    parser.add_argument("--host", dest="host", default="127.0.0.1")
    parser.add_argument("--port", dest="port", type=int, default=9000)
    parser.add_argument("--log", dest="loglevel", default="debug")
    parser.add_argument("--logfile", dest="logfile", default=None)
    parser.add_argument("-w", dest="nworkers", type=int, default=1)
    parser.add_argument("-r", dest="document_root", default=".")
    return parser.parse_args()


def run():
    server = AsyncHTTPServer()
    server.serve_forever()


if __name__ == "__main__":
    args = parse_args()

    logging.basicConfig(
        filename=args.logfile,
        level=getattr(logging, args.loglevel.upper()),
        format="%(name)s: %(process)d %(message)s")

    DOCUMENT_ROOT = args.document_root
    for _ in range(args.nworkers):
        p = multiprocessing.Process(target=run)
        p.start()
