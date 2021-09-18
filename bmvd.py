import argparse
import logging
import signal

from bmvd.bmv600s import SerialReaderThread
from bmvd.webserver import WebServerThread
from bmvd import __version__

class BatteryMonitorDaemon:
    def __init__(self, serial_device: str, web_port: int):
        self._serial_reader = SerialReaderThread(serial_device)
        self._webserver = WebServerThread(web_port, self._serial_reader)

    def start(self):
        self._serial_reader.start()
        self._webserver.start()

    def stop(self):
        self._webserver.stop()
        self._serial_reader.stop()


def main():
    ap = argparse.ArgumentParser(
        prog="bmvd", description="Battery Monitor daemon")
    ap.add_argument("--version", "-v", action="version",
                    version=__version__)
    ap.add_argument("serial_device", type=str, metavar="DEVICE",
                    help="serial port device to use")
    ap.add_argument("--port", type=int, metavar="PORT", dest="web_port",
                    help="set the port to listen on for the http server",
                    default=7070)
    ap.add_argument("--logfile", type=str, metavar="FILE", dest="logfile",
                    help="set the path to a logfile. If not set, log output will be sent to stdout")
    args = ap.parse_args()

    if args.logfile:
        logging.basicConfig(filename=args.logfile, level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.DEBUG)

    daemon = BatteryMonitorDaemon(args.serial_device, args.web_port)

    # Register signal handlers
    def sighandler(signum, frame): return daemon.stop()
    signal.signal(signal.SIGTERM, sighandler)
    signal.signal(signal.SIGINT, sighandler)

    daemon.start()


if __name__ == "__main__":
    main()
