import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

data = dict()
data["V"] = "12800"
data["I"] = "-1000"


class BmvRequestHandler(BaseHTTPRequestHandler):
    server_version = "bmvd/0.1"

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

        dump = json.dumps(data)
        self.wfile.write(dump.encode("utf-8"))


def main():
    ap = argparse.ArgumentParser(description="Battery monitor http server")
    ap.add_argument("-p", "--port", metavar="PORT", type=int, default=7070,
                    help="server port to listen on")
    args = ap.parse_args()

    print("Starting HTTP server on port {0}".format(args.port))
    server = HTTPServer(("", args.port), BmvRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server shutting down")
        pass


if __name__ == "__main__":
    main()
