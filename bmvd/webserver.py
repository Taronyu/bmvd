import argparse
import json
import logging
import signal
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from bmvd.bmv600s import AlarmReason, MonitorData


class MonitorDataJsonEncoder(json.JSONEncoder):
    "JSON Encoder for the monitor data class"

    def default(self, obj):
        if isinstance(obj, MonitorData):
            return obj.__dict__
        else:
            return super.default(obj)


class _BmvRequestHandler(BaseHTTPRequestHandler):
    "BMV request handler implementation."

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

        dump = _BmvRequestHandler._get_data_json()
        self.wfile.write(dump.encode("utf-8"))

    @classmethod
    def _get_data_json(cls) -> str:
        "Gets the current monitor data as a JSON string."

        if not cls.data_provider:
            return "{}"

        data = cls.data_provider.copy_current_data()
        if data:
            return json.dumps(data.__dict__, cls=MonitorDataJsonEncoder)
        else:
            return "{}"


class WebServerThread(threading.Thread):
    "Web server thread implementation."

    def __init__(self, port: int, data_provider):
        super().__init__()

        logging.debug("Creating web server thread.")

        self.name = "WebserverThread"
        self.daemon = False

        _BmvRequestHandler.data_provider = data_provider
        self._server = HTTPServer(("", port), _BmvRequestHandler, True)
        self._server.timeout = 2.0

    def stop(self):
        "Stops the web server thread."

        logging.info("Stopping the webserver")
        self._server.shutdown()

    def run(self):
        logging.info("Starting the webserver")
        with self._server:
            self._server.serve_forever()

        logging.debug("Web server thread has ended.")


class _DummyDataProvider:
    "Dummy data provider implementation used for testing only."

    def __init__(self):
        self._data = MonitorData()
        self._data.voltage = 12800
        self._data.current = -2000
        self._data.alarm = True
        ar = int(AlarmReason.LOW_VOLTAGE | AlarmReason.HIGH_VOLTAGE)
        self._data.alarm_reason = MonitorData.as_alarm_str(str(ar))
        self._data.model_name = "dummy_bmv"
        self._data.firmware_version = "010"

    def copy_current_data(self) -> MonitorData:
        return self._data


def main():
    "Entry point for the test application."

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
