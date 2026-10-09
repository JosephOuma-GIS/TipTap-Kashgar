
import argparse, json, os
from pathlib import Path
import ee, geopandas as gpd

PROJECT   = os.environ.get("EE_PROJECT", "your-gee-project")
PREF_SHP  = Path(r"D:\BRA\Data\kashgar_perfecture.shp")
DRIVE_DIR = "TipTap_Kashgar_terrain"
CRS       = "EPSG:32643"          # UTM 43N — projected metres, what Network Analyst needs

ap = argparse.ArgumentParser(); ap.add_argument("--oasis", action="store_true", help="restrict the DEM to the buffered cropland extent")
args = ap.parse_args()

try:
    ee.Initialize(project=PROJECT)
except Exception:
    ee.Authenticate(); ee.Initialize(project=PROJECT)

# --- 1. Prefecture boundary from your shapefile (dissolved, simplified to keep the request small) ------------
pref = gpd.read_file(PREF_SHP).to_crs("EPSG:4326")
geom = pref.geometry.union_all() if hasattr(pref.geometry, "union_all") else pref.geometry.unary_union
geom = geom.simplify(0.002)                                        # ~200 m; the boundary is only used to clip
AOI  = ee.Geometry(json.loads(gpd.GeoSeries([geom], crs="EPSG:4326").to_json())["features"][0]["geometry"])
print("prefecture area, km2:", round(AOI.area(maxError=100).divide(1e6).getInfo()))

# --- 2. Oasis extent, built LOCALLY from the 30 m crop map (cropland >= 15% at ~480 m, buffered 15 km) ------
#        Doing this server-side on 10 m WorldCover exceeds Earth Engine's interactive pixel limit; locally it takes a second.
import numpy as np, rasterio
from rasterio import features as rfeatures
from scipy import ndimage
from shapely.geometry import shape as shp_shape
from shapely.ops import unary_union
CROP_TIF = Path(r"D:\BRA\Data\Kashgar_crops_HLS30\Kashgar_crops_2023_HLS30_WGS84.tif")
with rasterio.open(CROP_TIF) as r:
    arr = r.read(1); tr = r.transform
agg = 16
crop = np.isin(arr, list(range(1, 9))).astype(np.uint8)
h, w = (crop.shape[0] // agg) * agg, (crop.shape[1] // agg) * agg
frac = crop[:h, :w].reshape(h // agg, agg, w // agg, agg).mean(axis=(1, 3))
mask = ndimage.binary_opening(ndimage.binary_closing(frac >= 0.15, iterations=2), iterations=1)
tr_c = rasterio.Affine(tr.a * agg, tr.b, tr.c, tr.d, tr.e * agg, tr.f)
polys = [shp_shape(g) for g, v in rfeatures.shapes(mask.astype(np.uint8), mask=mask, transform=tr_c) if v == 1]
oasis_local = unary_union(polys)
oasis_local = (gpd.GeoSeries([oasis_local], crs="EPSG:4326").to_crs("EPSG:32643").buffer(15000).simplify(500)
               .to_crs("EPSG:4326").iloc[0].intersection(geom))
print("oasis extent area, km2:", round(gpd.GeoSeries([oasis_local], crs="EPSG:4326").to_crs("EPSG:32643").area.iloc[0] / 1e6))
gpd.GeoDataFrame({"name": ["kashgar_oasis_extent"]}, geometry=[oasis_local], crs="EPSG:4326").to_file(
    Path(r"D:\BRA\TipTap\hydraulic\kashgar_oasis_extent.gpkg"), driver="GPKG")
oasis = ee.Geometry(json.loads(gpd.GeoSeries([oasis_local], crs="EPSG:4326").to_json())["features"][0]["geometry"])
REGION = oasis if args.oasis else AOI

# --- 3. Copernicus DEM GLO-30, mosaicked and void-filled -----------------------------------------------------
dem = (ee.ImageCollection("COPERNICUS/DEM/GLO30").select("DEM").filterBounds(REGION).mosaic()
       .focalMean(radius=1, kernelType="square", units="pixels").blend(          # fills isolated voids only
           ee.ImageCollection("COPERNICUS/DEM/GLO30").select("DEM").filterBounds(REGION).mosaic())
       .rename("elev_m").toFloat().clip(REGION))
ee.batch.Export.image.toDrive(image=dem, description="kashgar_dem_glo30", folder=DRIVE_DIR, region=REGION,
                              scale=30, crs=CRS, maxPixels=1e10, fileFormat="GeoTIFF",
                              formatOptions={"cloudOptimized": True}).start()

# --- 4. MERIT Hydro (90 m) — an independent, hydrologically conditioned flow field for cross-checking ---------
merit = ee.Image("MERIT/Hydro/v1_0_1").clip(REGION)
ee.batch.Export.image.toDrive(image=merit.select("upa").rename("upstream_km2").toFloat(), description="kashgar_merit_upa",
                              folder=DRIVE_DIR, region=REGION, scale=90, crs=CRS, maxPixels=1e10).start()
ee.batch.Export.image.toDrive(image=merit.select("dir").rename("flowdir_d8").toInt16(), description="kashgar_merit_dir",
                              folder=DRIVE_DIR, region=REGION, scale=90, crs=CRS, maxPixels=1e10).start()

print(f"4 export tasks started -> Google Drive/{DRIVE_DIR}. Monitor: https://code.earthengine.google.com/tasks")
print("When finished, download to D:\\BRA\\Data\\Terrain\\ . A DEM larger than ~4 GB arrives as tiles "
      "kashgar_dem_glo30-0000000000-0000000000.tif ... : mosaic them in ArcGIS Pro (Mosaic To New Raster) or gdal_merge.")
