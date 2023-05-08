#!/usr/bin/env python3

import io
import os
from functools import partial
import requests
from shapely.ops import transform
from shapely.validation import make_valid
from scipy.spatial import cKDTree

import pandas as pd

os.environ["USE_PYGEOS"] = "0"
import geopandas as gp


pd.set_option("display.max_columns", None)

# EPSG:4326 WG 84
# EPSG:32630
CRS = "EPSG:32630"

OUTFILE = "queensferry.gpkg"

URBANTYPES = {
    "Large Town",
    "Large Town in Conurbation",
    "Core City (outside London)",
    "Village or small community in Conurbation",
    "Other City",
    "Small Town in Conurbation",
    "Small Town",
    "Medium Town",
    "Medium Town in Conurbation",
    "Core City (London)",
    "Village or Small Community in Conurbation",
}


def _set_precision(precision=6):
    def _precision(x, y, z=None):
        return tuple([round(i, precision) for i in [x, y, z] if i])

    return partial(transform, _precision)


def nearest_stations(c, stations):
    stree = cKDTree(stations["geometry"].apply(lambda v: (v.x, v.y)).to_list())
    return stree.query(c.centroid.apply(lambda v: (v.x, v.y)).to_list(), k=1)


print("Load Output Area Data")
TOWNDATA = pd.read_csv("oa-classification-csv.csv")

TOWNDATA["name"] = TOWNDATA["bua_name"]
IDX1 = TOWNDATA["bua_name"] == "None"
TOWNDATA.loc[IDX1, "name"] = TOWNDATA.loc[IDX1, "la_name"]
TOWNDATA["Town"] = TOWNDATA["name"]
for k in [" BUA in Conurbation", " BUASD", " BUA"]:
    TOWNDATA["Town"] = TOWNDATA["Town"].str.replace(k, "")

print("Loaded Output Area Data")

print("Load geography")
AREAS = gp.read_file("geography.gpkg", driver="GPKG", layer="OA", engine="pyogrio")
AREAS = AREAS.dropna()


# Fix broken geometry
def fix_geometry(df):
    idx1 = df.is_valid
    gs1 = df.loc[~idx1, "geometry"].apply(make_valid)
    idx2 = gs1.geom_type == "GeometryCollection"
    gs2 = gs1[idx2].explode(index_parts=False)
    gs2 = gs2[gs2.geom_type.str.contains("Polygon")]
    gs1[gs2.index] = gs2
    return gs1


GS1 = fix_geometry(AREAS)
AREAS.loc[GS1.index, "geometry"] = GS1

OA21TO11 = pd.read_csv(
    "data/OA2011_OA2021_LocalAuthorityDistrict2022_EW.csv", low_memory=False
)
OA21TO11 = OA21TO11[["OA11CD", "OA21CD"]].set_index("OA21CD")
AREAS = AREAS.join(OA21TO11, on="OA")
AREAS["OA11CD"].fillna(AREAS["LSOA"], inplace=True)

FIELDS = [
    "la_code",
    "la_name",
    "region_name",
    "bua_code",
    "bua_name",
    "constituency_code",
    "constituency_name",
    "citytownclassification",
    "Town",
]

AREAS = AREAS.set_index("OA11CD")
IDX1 = AREAS["Country"] == "Scotland"

AREAS.loc[~IDX1, FIELDS] = TOWNDATA.set_index("outputarea_code").loc[
    AREAS[~IDX1].index, FIELDS
]
AREAS.loc[IDX1, FIELDS] = TOWNDATA.set_index("lsoa_code").loc[AREAS[IDX1].index, FIELDS]
AREAS = AREAS.reset_index()
IDX2 = AREAS["citytownclassification"].isin(URBANTYPES)
AREAS["urban"] = 0
AREAS.loc[IDX2, "urban"] = 2
del TOWNDATA

KEYS = ["region_name", "Town", "bua_code", "urban"]
BOUNDARY = AREAS[KEYS + ["geometry", "population"]].dissolve(by=KEYS, aggfunc=sum)
BOUNDARY = BOUNDARY.reset_index()
BOUNDARY["area"] = BOUNDARY.area / 1.0e6
BOUNDARY["density"] = BOUNDARY["population"] / BOUNDARY["area"]
IDX3 = (BOUNDARY["density"] > 1000) & (BOUNDARY["urban"] == 0)
BOUNDARY.loc[IDX3, "urban"] = 1

IDX4 = (AREAS["density"] > 1000) & (AREAS["urban"] == 0)
AREAS.loc[IDX4, "urban"] = 1

FIELDS = ["population", "Town", "urban", "geometry"]
TOWNS = AREAS[FIELDS].dissolve(by=["urban", "Town"], aggfunc="sum").reset_index()
TOWNS.to_crs(CRS).to_file(OUTFILE, driver="GPKG", layer="towns", engine="pyogrio")
TOWNS["geometry"] = TOWNS.centroid
TOWNS.to_crs(CRS).to_file(OUTFILE, driver="GPKG", layer="townsgrid", engine="pyogrio")



def get_databuffer(uri, encoding="UTF-8"):
    """Download data from URI and returns as an StringIO buffer"""
    r = requests.get(uri, timeout=10)
    return io.StringIO(str(r.content, encoding))


def get_naptan():
    # NaPTAN data service
    URI = "https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv"
    buffer = get_databuffer(URI)
    df = pd.read_csv(buffer, low_memory=False).dropna(axis=1, how="all")
    data = df[["Easting", "Northing"]].values
    points = gp.points_from_xy(*data.T, crs="EPSG:27700")
    r = gp.GeoDataFrame(data=df, geometry=points)
    return r


def get_crs():
    URI = "https://www.nationalrail.co.uk/station_codes%20(07-12-2020).csv"
    buffer = get_databuffer(URI)
    data = pd.read_csv(buffer, low_memory=False)
    data.columns = ["Station Name", "CRS"] * 4
    r = pd.concat(
        [data.iloc[:, 0:2], data.iloc[:, 2:4], data.iloc[:, 4:6], data.iloc[:, 6:]]
    )
    r = r.dropna().reset_index(drop=True)
    r = r.set_index("Station Name")
    return r


try:
    NaPTAN
except NameError:
    NaPTAN = get_naptan()

FIELDS = [
    "ATCOCode",
    "CommonName",
    "LocalityName",
    "ParentLocalityName",
    "StopType",
    "Status",
    "geometry",
]
STATIONS = NaPTAN[NaPTAN["StopType"].isin(["RLY", "MET"])]
STATIONS = STATIONS[FIELDS].dropna(axis=1, how="all").fillna("-")
STATIONS["TIPLOC"] = STATIONS["ATCOCode"].str[4:]
STATIONS["Name"] = STATIONS["CommonName"].str.replace(" Rail Station", "")


if "CRScode" not in globals():
    CRScode = get_crs()

STATIONS = STATIONS.join(CRScode, on="Name")
KEYS = ["Status", "StopType", "TIPLOC", "CRS", "Name", "geometry"]
ACTIVE = STATIONS.loc[
    (STATIONS["Status"] == "active") & (STATIONS["StopType"] == "RLY"), KEYS
].reset_index(drop=True)
ACTIVE = ACTIVE.fillna("-").to_crs(CRS)

del NaPTAN
del STATIONS

KEYS = ["region_name", "Town", "bua_code"]

D, IDX5 = nearest_stations(AREAS.centroid, ACTIVE)
DF1 = ACTIVE.drop(columns="geometry").loc[IDX5].reset_index(drop=True)
DF1["distance"] = D
AREAS = AREAS.join(DF1)

D, IDX6 = nearest_stations(BOUNDARY.centroid, ACTIVE)
DF2 = ACTIVE.drop(columns="geometry").loc[IDX6].reset_index(drop=True)
DF2["distance"] = D
BOUNDARY = BOUNDARY.join(DF2)

IDX7 = BOUNDARY["Town"].str.contains(r"\(")
BOUNDARY["ShortTown"] = BOUNDARY["Town"]
BOUNDARY.loc[IDX7, "ShortTown"] = BOUNDARY.loc[IDX7, "Town"].str.split(
    r" \(", expand=True
)[0]


def get_class(df):
    r = pd.Series(0, index=df.index, name="class")
    idx = df["distance"] > 5.0e3
    r[idx] = 1
    r[df["distance"] > 10.0e3] = 2
    r[df["distance"] > 32.0e3] = 3
    r[(df["density"] > 150) & idx] = 4
    r[(df["density"] > 1500) & idx] = 5
    r[(df["density"] > 2500) & idx] = 6
    r[(df["density"] > 4500) & idx] = 7
    return r


AREAS["class"] = get_class(AREAS)
BOUNDARY["class"] = get_class(BOUNDARY)
print("Output urban and semi-urban boundaries")

del IDX1
del IDX2
del IDX3
del IDX4
del IDX5
del IDX6
del IDX7
del DF1
del DF2

ACTIVE.to_crs(CRS).to_file(OUTFILE, driver="GPKG", layer="stations", engine="pyogrio")
AREAS.to_crs(CRS).to_file(OUTFILE, driver="GPKG", layer="density", engine="pyogrio")
BOUNDARY.to_crs(CRS).to_file(
    OUTFILE, driver="GPKG", layer="classification", engine="pyogrio"
)


_precision = _set_precision(0)
GBCRS = "EPSG:27700"

GF = ACTIVE.to_crs(GBCRS)
GF["geometry"] = GF["geometry"].apply(_precision)
GF.to_crs(GBCRS).to_file("station.geojson", driver="GeoJSON", engine="pyogrio")
del ACTIVE

GF = BOUNDARY.to_crs(GBCRS)
del BOUNDARY

GF["geometry"] = GF["geometry"].apply(_precision)
GF.to_crs(GBCRS).to_file(
    "urbanarea.geojson", driver="GeoJSON", engine="pyogrio", engine="pyogrio"
)


GF = AREAS.to_crs(GBCRS)
del AREAS
GF["geometry"] = GF["geometry"].apply(_precision)
GF.to_crs(GBCRS).to_file(
    "outputarea.geojson", driver="GeoJSON", engine="pyogrio", engine="pyogrio"
)
