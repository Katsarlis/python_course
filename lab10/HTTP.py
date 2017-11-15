import asyncore
import asynchat
import socket
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
                content_length = self.request_headers['content-length']
                if content_length>0:
                    self.set_terminator(content_length)
                else:
                    self.handle_request()
            else:
                self.handle_request()
        else:
            self.parse_body()
            self.handle_request()

    def parse_headers(self):
        # TODO refactor
        self.log(">>>Parsing headers")
        raw = str(self.incoming[0])

        for string in raw.split("\\r\\n"):
            if string.find("b'") != -1:
                self.method = string.split(" ")[0].replace("b'", "")
                self.request_headers['method'] = self.method
                self.uri = string.split(" ")[1]
                self.request_headers["uri"] = self.uri
                self.protocol = string.split(" ")[2]
                self.request_headers['protocol'] = self.protocol
            else:
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
            self.handle_close()
        else:
            handler = getattr(self, method_name)
            handler()

    def send_header(self, keyword, value):
        # TODO добавляет новый заголовок (в словарь) для отправки клиенту - формирование заголовков для ответа клиенту
        if keyword.lower() == 'connection':
            if value.lower() == 'close':
                self.close_connection = 1
            elif value.lower() == 'keep-alive':
                self.close_connection = 0
        self.response_headers[keyword] = value




    def send_response(self, data):
        if self.method == 'POST':
            pass
        else:
            if len(data) > 0:
                self.push(data)

    def date_time_string(self):
        weekdayname = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
        monthname = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
        year, month, day, hh, mm, ss, wd, y, z = time.gmtime(time.time())
        return f"{weekdayname[wd]}, {day} {monthname[month]} {year} {hh}:{mm}:{ss} GMT"

    def send_head(self):
        # TODO
        pass

    def do_GET(self):
        # TODO
        self.log(">>Do_get")
        pass

    def do_HEAD(self):
        # TODO
        self.log(">>Do_head")
        pass

    def do_POST(self):
        # TODO
        self.log(">>Do_post")
        self.request_headers['content-length']
        pass

    def translate_path(self, path):
        # TODO
        path = url_normalize(path)
        return path

    def add_terminator(self):
        self.push()

    def respond(self, code, data=''):
        self.log(f"Responding withe code ${code}")
        try:
            message, _ = self.responses[code]
        except KeyError:
            message = '???'
            # TODO


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
