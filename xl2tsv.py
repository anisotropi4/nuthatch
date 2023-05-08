#!/usr/bin/env python3

import argparse
import os
import sys
import pandas as pd

parser = argparse.ArgumentParser(
    description="Dump xls(x) files tab(s) to .tsv files, to the (default output) path"
)

parser.add_argument(
    "inputfiles", type=str, nargs="*", help="name of xls-file to process"
)

parser.add_argument(
    "--path", dest="path", type=str, default="output", help="output directory file"
)

parser.add_argument(
    "--tab", type=str, dest="tab", default=None, help="name of tab to process"
)

parser.add_argument(
    "--tabnames",
    dest="tabnames",
    action="store_true",
    default=False,
    help="dump name of tabs",
)

parser.add_argument(
    "--noempty",
    dest="noempty",
    action="store_true",
    default=False,
    help="remove blank lines",
)

parser.add_argument(
    "--filename",
    dest="filename",
    action="store_true",
    default=False,
    help="add filename to output file",
)

args = parser.parse_args()

path = args.path
noempty = args.noempty

if not os.path.exists(path):
    os.makedirs(path)

if args.tabnames:
    for filename in args.inputfiles:
        if len(args.inputfiles) > 1:
            print(filename)
        df = pd.read_excel(filename, None)
        print("\t".join(df.keys()))
    sys.exit(0)

if args.filename:
    filebase = args.filename + ":"
    if "." in args.filename:
        filebase = args.filename.rsplit(".", 1)[0] + ":"

for filename in args.inputfiles:
    filebase = ""
    if args.tab:
        tab = args.tab
        try:
            output = pd.read_excel(filename, tab)
            if noempty:
                output = output.dropna(how="all")
            output.to_csv(f"{path}/{filebase}{tab}.tsv", index=False, sep="\t")
        except KeyError:
            pass
    else:
        df = pd.read_excel(filename, None)
        if args.filename:
            filebase = filename + ":"
            if "." in filename:
                filebase = filename.rsplit(".", 1)[0] + ":"
        for tab in df.keys():
            output = df[tab]
            if noempty:
                output = output.dropna(how="all")
            output.to_csv(f"{path}/{filebase}{tab}.tsv", index=False, sep="\t")
