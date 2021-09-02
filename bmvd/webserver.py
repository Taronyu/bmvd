import argparse
from flask import Flask, json

api = Flask(__name__)

data = dict()
data["V"] = "12800"
data["I"] = "-1000"


@api.route("/bmv600s", methods=["GET"])
def get_bmv600s_status():
    return json.dumps(data)


def main():
    ap = argparse.ArgumentParser(description="Battery monitor http server")
    ap.add_argument("-p", "--port", metavar="PORT", type=int, default=7070,
                    help="server port to listen on")
    args = ap.parse_args()
    api.run(host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
