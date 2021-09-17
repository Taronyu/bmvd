import argparse
import signal

from bmvd.bmv600s import SerialReaderThread
from bmvd.webserver import WebServerThread

_serial_reader: SerialReaderThread = None
_webserver: WebServerThread = None


def start_serial(device: str, port: int) -> None:
    global _serial_reader
    global _webserver

    # Start the serial reader thread
    _serial_reader = SerialReaderThread(device)
    _serial_reader.start()

    # Start the webserver thread
    _webserver = WebServerThread(port, _serial_reader)
    _webserver.start()


def stop_serial() -> None:
    # Stop the webserver thread
    if _webserver:
        _webserver.stop()

    # Stop the serial reader thread
    if _serial_reader:
        _serial_reader.stop()


def _signal_handler(signum, frame):
    stop_serial()


def main():
    ap = argparse.ArgumentParser(
        prog="bmvd", description="Battery Monitor daemon")
    ap.add_argument("--port", type=int, metavar="PORT", dest="web_port",
                    help="set the port to listen on for the http server",
                    default=7070)
    ap.add_argument("--datafile", type=str, metavar="FILE",
                    help="use a datafile instead of reading live data from the battery monitor")
    args = ap.parse_args()

    # Register signal handler
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    if not args.datafile:
        start_serial("", args.web_port)
    else:
        pass


if __name__ == "__main__":
    main()
