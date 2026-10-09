"""ERA5-Land block forcing for Tip–Tap: daily aggregates -> 12-day means (1 March–20 November) per 9 km ERA5 cell.

Each cell is represented by the mean centroid of its parcels (cell key and geometry from tiptap_cell_lookup.csv, written by the
parcel zonal export). One CSV per year is exported to Google Drive; concatenate them into era5_cell_12day.csv.
"""
import argparse, json, os
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import shape
import ee

ap = argparse.ArgumentParser()
ap.add_argument("--lookup", required=True)
ap.add_argument("--years", default="2019-2025")
ap.add_argument("--folder", default="TipTap_Kashgar")
a = ap.parse_args()
y0, y1 = map(int, a.years.split("-"))

try:
    ee.Initialize(project=os.environ.get("EE_PROJECT"))
except Exception:
    ee.Authenticate(); ee.Initialize(project=os.environ.get("EE_PROJECT"))

lk = pd.read_csv(a.lookup)
lk = gpd.GeoDataFrame(lk, geometry=[shape(json.loads(s)) for s in lk[".geo"]], crs="EPSG:4326")
pts = lk.assign(lon=lk.geometry.x, lat=lk.geometry.y).groupby("cell")[["lon", "lat"]].mean().reset_index()
fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([r.lon, r.lat]), {"cell": r.cell}) for r in pts.itertuples()])
era = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")

def derived(img):
    t   = img.select("temperature_2m").subtract(273.15)
    tmx = img.select("temperature_2m_max").subtract(273.15)
    td  = img.select("dewpoint_temperature_2m").subtract(273.15)
    es  = t.expression("0.6108*exp(17.27*T/(T+237.3))", {"T": t})
    ea  = td.expression("0.6108*exp(17.27*T/(T+237.3))", {"T": td})
    vpd = es.subtract(ea).rename("vpd")
    u2  = img.select("u_component_of_wind_10m").hypot(img.select("v_component_of_wind_10m")).multiply(4.87 / np.log(67.8 * 10 - 5.42))
    rn  = img.select("surface_net_solar_radiation_sum").add(img.select("surface_net_thermal_radiation_sum")).divide(1e6)
    delta = es.expression("4098*es/((T+237.3)**2)", {"es": es, "T": t})
    gamma = ee.Image.constant(0.0665)
    et0 = (delta.multiply(0.408).multiply(rn).add(gamma.multiply(900).divide(t.add(273)).multiply(u2).multiply(vpd))
           .divide(delta.add(gamma.multiply(u2.multiply(0.34).add(1))))).rename("et0")
    p = img.select("total_precipitation_sum").multiply(1000).rename("precip_mm")
    return ee.Image.cat([tmx.rename("tmax"), vpd, et0, p]).copyProperties(img, ["system:time_start"])

for y in range(y0, y1 + 1):
    rows = []
    for s in pd.date_range(f"{y}-03-01", f"{y}-11-20", freq="12D"):
        e = s + pd.Timedelta(days=12)
        img = era.filterDate(str(s.date()), str(e.date())).map(derived).mean()
        rows.append(img.reduceRegions(fc, ee.Reducer.first(), scale=9000).map(lambda f, d=str(s.date()): f.set("grid_start", d)))
    task = ee.batch.Export.table.toDrive(collection=ee.FeatureCollection(rows).flatten(), description=f"era5_cell_12day_{y}", folder=a.folder,
                                         fileFormat="CSV", selectors=["cell", "grid_start", "tmax", "vpd", "et0", "precip_mm"])
    task.start(); print("started", task.id, y)
