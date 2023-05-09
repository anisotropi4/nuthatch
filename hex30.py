#!/usr/bin/env python3

import os
import datetime as dt

os.environ["USE_PYGEOS"] = "0"
import pandas as pd
import numpy as np
from shapely.geometry import Polygon, MultiPolygon
import h3
from tobler.util import h3fy
from tobler.area_weighted import area_interpolate

import geopandas as gp
from pyogrio import read_dataframe, write_dataframe, list_layers, read_info

pd.set_option("display.max_columns", None)
CRS = "EPSG:32630"

OUTFILE = "hex30-MSOA.gpkg"

BRITAIN = gp.read_file("britain.gpkg", layer="simple", engine="pyogrio")
GF = BRITAIN.explode(index_parts=False).reset_index(drop=True)
GF["area"] = GF.area
GF = GF.sort_values("area", ascending=False).iloc[0]
BRITAIN["geometry"] = GF["geometry"]

OUT00 = gp.GeoDataFrame(geometry=BRITAIN.envelope, crs=CRS)
write_dataframe(OUT00, OUTFILE, layer="outer-00")

OUT30 = gp.GeoDataFrame(geometry=OUT00.rotate(30), crs=CRS)
write_dataframe(OUT30, OUTFILE, layer="outer-30")


def get_hside(resolution):
    # derived from avg_area_table.ipynb at https://github.com/uber/h3-py-notebooks
    hareas = [
        4.357449416078392e12,
        6.097884417941342e11,
        8.680178039899734e10,
        1.239343465508818e10,
        1.770347654491310e09,
        2.529038581819453e08,
        3.612906216441251e07,
        5.161293359717200e06,
        7.373275975944190e05,
        1.053325134272069e05,
        1.504750190766437e04,
        2.149643129451882e03,
        3.070918756316065e02,
        4.387026794728303e01,
        6.267181135324324e00,
        8.953115907605805e-01,
    ]
    area = hareas[resolution]
    return int(np.sqrt(2 * area / 3 / np.sqrt(3)))


START = dt.datetime.now()


def get_hexagon(hex_id):
    return Polygon(h3.h3_to_geo_boundary(hex_id, geo_json=True))


def get_hexagons(hex_df):
    WGS84 = "EPSG:4326"
    r = gp.GeoDataFrame(geometry=hex_df.apply(get_hexagon), crs=WGS84)
    r.name = "geometry"
    r.index = hex_df.values
    return r.to_crs(CRS)


if "MSOA" not in globals():
    MSOA = read_dataframe("geography.gpkg", layer="MSOA")

if "POINT" not in globals():
    POINT = None

for n in range(1, 10):
    print(n, dt.datetime.now() - START, "hex MSOA 00")
    layer = f"hexagon{n}-00"
    layers = [i for i, _ in list_layers(OUTFILE)]
    if layer in layers:
        continue
    s = get_hside(n)
    hex_ids = h3fy(OUT00.buffer(s), n, return_geoms=False)
    print(s, dt.datetime.now() - START)
    hx = []
    for i, j in enumerate(np.array_split(hex_ids, n)):
        gf = get_hexagons(j)
        gf = gf.clip(OUT00)
        gf = gf.clip(BRITAIN).explode(index_parts=False)
        gf = gf.drop_duplicates(subset="geometry").reset_index(drop=True)
        gf = area_interpolate(
            MSOA, gf, allocate_total=False, extensive_variables=["population"]
        )
        gf["area"] = gf.area
        gf["density"] = gf["population"] / gf["area"]
        hx.append(gf)
    gf = pd.concat(hx)
    gf = gf.drop_duplicates(subset="geometry").reset_index(drop=True)
    write_dataframe(gf, OUTFILE, layer=f"hexagon{n}-00")

for n in range(1, 10):
    s = get_hside(n)
    print(n, dt.datetime.now() - START, "hex MSOA 30")
    layer = f"hexagon{n}-30"
    layers = [i for i, _ in list_layers(OUTFILE)]
    if layer in layers:
        continue
    sq30 = OUT30.envelope.buffer(n * s, cap_style="square", join_style="mitre")
    try:
        sq30 = sq30.rotate(30, origin=POINT)
    except TypeError:
        sq30 = sq30.rotate(30, origin="centroid")
    hex_ids = h3fy(sq30, n, return_geoms=False)

    print(s, dt.datetime.now() - START)
    hx = []
    for i, j in enumerate(np.array_split(hex_ids, n)):
        gf = get_hexagons(j)
        if not POINT:
            p = gp.GeoDataFrame(geometry=gf.centroid, crs=CRS).sindex.nearest(
                OUT00.centroid
            )
            idx = p.reshape(-1)[1]
            POINT = gf.centroid[idx]
            write_dataframe(
                gp.GeoDataFrame(geometry=[POINT], crs=CRS), OUTFILE, layer="point"
            )
        gs = gp.GeoSeries(MultiPolygon(gf["geometry"].values))
        gs = gs.rotate(-30, origin=POINT).explode(ignore_index=True)
        gf["geometry"] = gs.values
        gf = gf.clip(OUT00)
        gf = gf.clip(BRITAIN).explode(index_parts=False)
        gf = gf.drop_duplicates(subset="geometry").reset_index(drop=True)
        gf = area_interpolate(
            MSOA, gf, allocate_total=False, extensive_variables=["population"]
        )
        gf["area"] = gf.area
        gf["density"] = gf["population"] / gf["area"]
        hx.append(gf)
    gf = pd.concat(hx)
    print(s, dt.datetime.now() - START)
    gf = gf.drop_duplicates(subset="geometry").reset_index(drop=True)
    write_dataframe(gf, OUTFILE, layer=f"hexagon{n}-30")

print(s, dt.datetime.now() - START)

del MSOA


if "OA" not in globals():
    OA = read_dataframe("geography.gpkg", layer="OA")

OA = OA[["population", "geometry"]]
INFILE = "hex30-MSOA.gpkg"
OUTFILE = "hex30-OA.gpkg"

write_dataframe(OUT00, OUTFILE, layer="outer-00")
write_dataframe(OUT30, OUTFILE, layer="outer-30")

for k in ["00", "30"]:
    for n in range(1, 10):
        print(n, dt.datetime.now() - START, f"hex OA {k}")
        s = get_hside(n)
        layer = f"hexagon{n}-{k}"
        layers = [i for i, _ in list_layers(OUTFILE)]
        if layer in layers:
            continue
        print(s, dt.datetime.now() - START)
        m = 1048576
        finfo = read_info(INFILE, layer=layer)
        hx = []
        for i, j in enumerate(range(0, finfo["features"], m)):
            print(n, i, j)
            gf = gp.read_file(
                INFILE, layer=f"hexagon{n}-{k}", rows=slice(j, j + m), engine="pyogrio"
            )
            print(i, dt.datetime.now() - START, f"hex OA {k}")
            gf = area_interpolate(
                OA, gf, allocate_total=False, extensive_variables=["population"]
            )
            hx.append(gf)
        gf = pd.concat(hx)
        gf["area"] = gf.area
        gf["density"] = gf["population"] / gf["area"]
        write_dataframe(gf, OUTFILE, layer=f"hexagon{n}-{k}")

print(n, dt.datetime.now() - START)

write_dataframe(gp.GeoDataFrame(geometry=[POINT], crs=CRS), OUTFILE, layer="point")
print(s, dt.datetime.now() - START)
