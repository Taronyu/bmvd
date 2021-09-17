import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class BmvRequestHandler(BaseHTTPRequestHandler):
    server_version = "bmvd/0.1"
    data_provider = None

    def do_GET(self):
        if self.path == "/":
            # Redirect to battery monitor status page
            self.send_response(301)
            self.send_header("Location", "/bmv600s")
            self.end_headers()
        elif self.path == "/bmv600s":
            self._send_data()
        else:
            self.send_error(404, message="Path not found")

    def _send_data(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        dump = None
        if BmvRequestHandler.data_provider:
            blocks = BmvRequestHandler.take_blocks()
            if blocks:
                dump = json.dumps(blocks)

        if not dump:
            dump = "[]"

        self.wfile.write(dump.encode("utf-8"))


class WebServerThread(threading.Thread):
    def __init__(self, port: int, data_provider):
        super().__init__()
        self.name = "WebserverThread"
        self.daemon = False

        BmvRequestHandler.data_provider = data_provider
        self._server = HTTPServer(("", port), BmvRequestHandler, True)
        self._server.timeout = 2.0

    def stop(self):
        print("Stopping the webserver")
        self._server.shutdown()

    def run(self):
        print("Starting the webserver")
        with self._server:
            self._server.serve_forever()


def main():
    ap = argparse.ArgumentParser(description="Battery monitor http server")
    ap.add_argument("-p", "--port", metavar="PORT", type=int, default=7070,
                    help="server port to listen on")
    args = ap.parse_args()

    server = WebServerThread(args.port, None)
    try:
        server.start()
    except KeyboardInterrupt:
        print("Server is shutting down")
        server.stop()


if __name__ == "__main__":
    main()
