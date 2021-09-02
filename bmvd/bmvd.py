import argparse


def main():
    ap = argparse.ArgumentParser(
        prog="bmvd", description="Battery Monitor daemon")
    ap.add_argument("--endpoint", type=str, metavar="ADDRESS",
                    help="set the listen adress:port for the http server")
    ap.add_argument("--datafile", type=str, metavar="FILE",
                    help="use a datafile instead of reading live data from the battery monitor")
    args = ap.parse_args()

    if not args.datafile:
        pass
    else:
        pass


if __name__ == "__main__":
    main()
