from flask import Flask, json

api = Flask(__name__)

data = dict()
data["V"] = "12800"
data["I"] = "-1000"


@api.route("/bmv600s", methods=["GET"])
def get_bmv600s_status():
    return json.dumps(data)


def run(host="0.0.0.0", port=7070):
    api.run(host=host, port=port)


if __name__ == "__main__":
    run()
