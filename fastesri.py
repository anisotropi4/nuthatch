#!/usr/bin/env python

import json
import sys
import argparse
from esridump.dumper import EsriDumper
import pandas as pd


def _parse_args(args):
    parser = argparse.ArgumentParser(
        description="Faster convertion of a single Esri feature service URL to GeoJSON"
    )
    parser.add_argument("uri", help="Esri layer URI")
    parser.add_argument(
        "outfile",
        type=argparse.FileType("w"),
        default="-",
        nargs="?",
        help="Output file name",
    )
    parser.add_argument(
        "--jsonlines",
        action="store_true",
        default=False,
        help="Output newline-delimited GeoJSON Features instead of a FeatureCollection",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        default=False,
        help="Output newline-delimited GeoJSON Features instead of a FeatureCollection",
    )
    parser.add_argument(
        "--no-geometry",
        dest="request_geometry",
        action="store_false",
        default=True,
        help="Don't request geometry for the feature so the server returns attributes only",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds, default 30",
    )
    parser.add_argument(
        "-p", "--pause", type=int, default=1, help="HTTP pause in seconds, default 1"
    )
    return parser.parse_args(args)


def main():
    args = _parse_args(sys.argv[1:])
    dumper = EsriDumper(
        args.uri,
        request_geometry=args.request_geometry,
        timeout=args.timeout,
        pause_seconds=args.pause,
    )

    if args.csv:
        df = pd.DataFrame([i["properties"] for i in dumper])
        args.outfile.write(df.to_csv(index=False))
        return

    if args.jsonlines:
        for feature in dumper:
            args.outfile.write(json.dumps(feature))
            args.outfile.write("\n")
        return

    args.outfile.write('{"type":"FeatureCollection","features":[\n')
    feature_iter = iter(dumper)
    try:
        feature = next(feature_iter)
        while True:
            args.outfile.write(json.dumps(feature))
            feature = next(feature_iter)
            args.outfile.write(",\n")
    except StopIteration:
        args.outfile.write("\n")
        args.outfile.write("]}")


if __name__ == "__main__":
    main()
