import argparse


def main():
    ap = argparse.ArgumentParser(
        prog="bmvd", description="Battery Monitor daemon")
    ap.add_argument("--endpoint", type=str, metavar="ADDRESS",
                    help="set the listen adress:port for the http server")
    args = ap.parse_args()


if __name__ == "__main__":
    main()
