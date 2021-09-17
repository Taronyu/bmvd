import argparse
import json
import threading
import signal
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

        dump = json.dumps(BmvRequestHandler._get_blocks())
        self.wfile.write(dump.encode("utf-8"))

    @classmethod
    def _get_blocks(cls) -> dict():
        if not cls.data_provider:
            return {}

        blocks = cls.data_provider.take_blocks()
        if len(blocks) >= 2:
            return {**blocks[0], **blocks[1]}
        else:
            return {}


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


class _DummyDataProvider:
    def __init__(self):
        data1 = dict()
        data1["voltage"] = 12000
        data1["current"] = -2800

        data2 = dict()
        data2["deepest_discharge"] = 10000
        data2["last_discharge"] = 2000

        self._data = [data1, data2]

    def take_blocks(self) -> list:
        return self._data


def main():
    ap = argparse.ArgumentParser(description="Battery monitor http server")
    ap.add_argument("-p", "--port", metavar="PORT", type=int, default=7070,
                    help="server port to listen on")
    args = ap.parse_args()

    provider = _DummyDataProvider()
    server = WebServerThread(args.port, provider)

    def sighandler(signum, frame): return server.stop()
    signal.signal(signal.SIGINT, sighandler)
    signal.signal(signal.SIGTERM, sighandler)

    server.start()


if __name__ == "__main__":
    main()
