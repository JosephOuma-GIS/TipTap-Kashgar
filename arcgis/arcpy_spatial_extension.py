"""
arcpy_spatial_extension.py — Multiscale GWR and Emerging Hot Spot Analysis on the Tip–Tap parcel results (ArcGIS Pro 3.x)

Inputs (written by the notebook, §13–§14):
    D:\BRA\TipTap\outputs_final\gis\parcels_recovery.gpkg      parcel polygons with rci, deficit_days, hyd_rank, hyd_dz_m, ...
    D:\BRA\TipTap\outputs_final\gis\parcel_season_nonrec.csv    parcel-season unrecovered stress-days with lon/lat and date
Outputs (read back by the notebook, §16), in D:\BRA\TipTap\hydraulic\spatial\:
    hex_grid.gpkg          2 km hexagons (GRID_ID) — geometry for the maps
    hex_mgwr.csv           hexagon-level MGWR results: local coefficients (C*_ fields), local R2, predicted, residuals
    mgwr_bandwidths.csv    bandwidth (number of neighbours) per explanatory variable
    hex_ehsa.csv           Emerging Hot Spot category per hexagon (PATTERN field)

Run from the ArcGIS Pro Python window:  exec(open(r"D:\BRA\TipTap\hydraulic\arcpy_spatial_extension.py").read())
then call the steps one at a time the first time: stepA_hexagons(); stepB_mgwr(); stepC_ehsa()
Read each step's messages.
"""
import arcpy, os, csv
arcpy.env.overwriteOutput = True
ROOT   = r"D:\BRA"
WORK   = os.path.join(ROOT, "TipTap", "hydraulic")
SPAT   = os.path.join(WORK, "spatial"); os.makedirs(SPAT, exist_ok=True)
GDB    = os.path.join(WORK, "hydraulic.gdb")
if not arcpy.Exists(GDB): arcpy.management.CreateFileGDB(WORK, "hydraulic.gdb")
arcpy.env.workspace = GDB
PARCELS_GPKG = os.path.join(ROOT, r"TipTap\outputs_final\gis\parcels_recovery.gpkg", "main.parcels")
SEASON_CSV   = os.path.join(ROOT, r"TipTap\outputs_final\gis\parcel_season_nonrec.csv")
CRS      = arcpy.SpatialReference(32643)        # UTM 43N
HEX_SIZE = "2 SquareKilometers"                 # hexagon area; ~4 000–6 000 hexagons over the oasis
MIN_PARCELS_PER_HEX = 5
# dependent variable and drivers for MGWR (all must exist as fields in parcels_recovery.gpkg)
DEP = "deficit_days"                            # unrecovered stress-days per cultivated season, 2019–22 (log1p-transformed below)
DRIVERS = ["hyd_rank", "hyd_dz_m", "dist_desert_km", "log_area", "mulch_share", "si_preseason", "log_ntl", "dist_settlement_km"]

def to_oid32(fc):
    ws, name = os.path.split(fc); tmp = name + "_oid64"
    arcpy.management.Rename(fc, tmp); desc = arcpy.Describe(os.path.join(ws, tmp))
    arcpy.management.CreateFeatureclass(ws, name, desc.shapeType.upper(), template=os.path.join(ws, tmp), spatial_reference=desc.spatialReference, oid_type="32_BIT")
    arcpy.management.Append(os.path.join(ws, tmp), fc, "NO_TEST"); arcpy.management.Delete(os.path.join(ws, tmp))

# ------------------------------------------------------------------------------------------------------------
# STEP A — 2 km hexagons with area-weighted parcel means
# ------------------------------------------------------------------------------------------------------------
def stepA_hexagons():
    arcpy.management.Project(PARCELS_GPKG, os.path.join(GDB, "parcels_x"), CRS); to_oid32(os.path.join(GDB, "parcels_x"))
    px = os.path.join(GDB, "parcels_x")
    fields = [f.name for f in arcpy.ListFields(px)]
    drivers = [d for d in DRIVERS if d in fields]
    missing = [d for d in DRIVERS if d not in fields]
    if missing: print("WARNING — drivers missing from the parcel layer and skipped:", missing)
    # area-weighted sums: w_<var> = var * area_ha, summed per hexagon and divided by summed area
    vars_ = [DEP] + drivers
    for v in vars_:
        arcpy.management.AddField(px, f"w_{v}"[:31], "DOUBLE")
        arcpy.management.CalculateField(px, f"w_{v}"[:31], f"(!{v}! if !{v}! is not None else 0) * !area_ha!", "PYTHON3")
    arcpy.management.AddField(px, "one", "SHORT"); arcpy.management.CalculateField(px, "one", "1", "PYTHON3")
    arcpy.management.GenerateTessellation(os.path.join(GDB, "hex"), arcpy.Describe(px).extent, "HEXAGON", HEX_SIZE, CRS)
    arcpy.management.FeatureToPoint(px, os.path.join(GDB, "parcels_x_pts"), "INSIDE")
    sum_fields = [[f"w_{v}"[:31], "SUM"] for v in vars_] + [["area_ha", "SUM"], ["one", "SUM"]]
    # positional: in_polygons, in_sum_features, out_feature_class, keep_all_polygons, sum_fields, sum_shape
    arcpy.analysis.SummarizeWithin(os.path.join(GDB, "hex"), os.path.join(GDB, "parcels_x_pts"), os.path.join(GDB, "hex_sum"),
                                   "ONLY_INTERSECTING", sum_fields, "NO_SHAPE_SUM")
    hs = os.path.join(GDB, "hex_sum")
    fl = {f.name.lower(): f.name for f in arcpy.ListFields(hs)}
    def sumname(v):
        for cand in (f"sum_w_{v}"[:31], f"sum_w_{v}", f"sum_{f'w_{v}'[:31]}"):
            if cand.lower() in fl: return fl[cand.lower()]
        raise KeyError(f"summed field for {v} not found; fields are {list(fl.values())}")
    for v in vars_: arcpy.management.AddField(hs, v[:31], "DOUBLE")
    arcpy.management.AddField(hs, "n_parcels", "LONG")
    cols = [sumname(v) for v in vars_] + [fl["sum_area_ha"], fl["sum_one"]] + [v[:31] for v in vars_] + ["n_parcels"]
    k = len(vars_)
    with arcpy.da.UpdateCursor(hs, cols) as cur:
        for row in cur:
            area, n = row[k], row[k + 1]
            for i in range(k): row[k + 2 + i] = (row[i] / area) if (area and row[i] is not None) else None
            row[-1] = int(n or 0); cur.updateRow(row)
    arcpy.management.MakeFeatureLayer(hs, "hex_lyr", f"n_parcels >= {MIN_PARCELS_PER_HEX}")
    arcpy.management.CopyFeatures("hex_lyr", os.path.join(GDB, "hex_model"))
    hm = os.path.join(GDB, "hex_model")
    arcpy.management.AddField(hm, "log_deficit", "DOUBLE"); arcpy.management.CalculateField(hm, "log_deficit", f"math.log1p(!{DEP}!) if !{DEP}! is not None else None", "PYTHON3")
    # geometry export for the notebook (GeoPackage)
    gp = os.path.join(SPAT, "hex_grid.gpkg")
    if not arcpy.Exists(gp): arcpy.management.CreateSQLiteDatabase(gp, "GEOPACKAGE_1.3")
    arcpy.conversion.ExportFeatures(hm, os.path.join(gp, "hex_grid"))
    print(f"step A done: {arcpy.management.GetCount(hm)} hexagons with >= {MIN_PARCELS_PER_HEX} parcels; drivers used: {drivers}")
    return drivers

# ------------------------------------------------------------------------------------------------------------
# STEP B — Multiscale Geographically Weighted Regression
# ------------------------------------------------------------------------------------------------------------
def stepB_mgwr(drivers=None):
    hm = os.path.join(GDB, "hex_model")
    fields = [f.name for f in arcpy.ListFields(hm)]
    drivers = drivers or [d for d in DRIVERS if d in fields]
    out = os.path.join(GDB, "hex_mgwr"); tbl = os.path.join(GDB, "mgwr_bandwidths")
    arcpy.stats.MGWR(in_features=hm, dependent_variable="log_deficit", model_type="CONTINUOUS", explanatory_variables=drivers,
                     output_features=out, neighborhood_type="NUMBER_OF_NEIGHBORS", neighborhood_selection_method="GOLDEN_SEARCH",
                     minimum_number_of_neighbors=30, maximum_number_of_neighbors=1000, local_weighting_scheme="BISQUARE",
                     output_table=tbl, scale="SCALE_DATA")
    print(arcpy.GetMessages())
    if "GRID_ID" not in [f.name for f in arcpy.ListFields(out)]:           # carry the hexagon id through SOURCE_ID
        arcpy.management.JoinField(out, "SOURCE_ID", hm, arcpy.Describe(hm).OIDFieldName, ["GRID_ID"])
    # exports
    for fc, name in [(out, "hex_mgwr.csv"), (tbl, "mgwr_bandwidths.csv")]:
        flds = [f.name for f in arcpy.ListFields(fc) if f.type not in ("Geometry", "Blob", "Raster") and f.name.lower() != "shape"]
        with open(os.path.join(SPAT, name), "w", newline="") as f:
            w = csv.writer(f); w.writerow(flds)
            for r in arcpy.da.SearchCursor(fc, flds): w.writerow(r)
    print("step B done:", os.path.join(SPAT, "hex_mgwr.csv"))

# ------------------------------------------------------------------------------------------------------------
# STEP C — Space-time cube and Emerging Hot Spot Analysis of unrecovered stress-days
# ------------------------------------------------------------------------------------------------------------
def stepC_ehsa(neighborhood_km=6):
    pts = os.path.join(GDB, "season_pts")
    arcpy.management.XYTableToPoint(SEASON_CSV, pts, "lon", "lat", coordinate_system=arcpy.SpatialReference(4326))
    arcpy.management.Project(pts, os.path.join(GDB, "season_pts_x"), CRS); to_oid32(os.path.join(GDB, "season_pts_x"))
    px = os.path.join(GDB, "season_pts_x")
    arcpy.management.AddField(px, "t_date", "DATE"); arcpy.management.CalculateField(px, "t_date", "!date!", "PYTHON3")
    cube = os.path.join(SPAT, "nonrec_cube.nc")
    # hexagon bins of ~2 km2 (a 2 km2 hexagon is 1.52 km high), annual time steps aligned to the first season
    arcpy.stpm.CreateSpaceTimeCube(in_features=px, output_cube=cube, time_field="t_date", time_step_interval="1 Years",
                                   time_step_alignment="START_TIME", distance_interval="1.52 Kilometers",
                                   summary_fields=[["nonrec_days", "SUM", "ZEROS"], ["episodes", "SUM", "ZEROS"]],
                                   aggregation_shape_type="HEXAGON_GRID")
    print(arcpy.GetMessages())
    out = os.path.join(GDB, "hex_ehsa")
    arcpy.stpm.EmergingHotSpotAnalysis(in_cube=cube, analysis_variable="NONREC_DAYS_SUM_ZEROS", output_features=out,
                                       neighborhood_distance=f"{neighborhood_km} Kilometers", neighborhood_time_step=1, polygon_mask=None,
                                       conceptualization_of_spatial_relationships="FIXED_DISTANCE", number_of_neighbors=None, define_global_window="ENTIRE_CUBE")
    print(arcpy.GetMessages())
    # the EHSA hexagons are the cube's own grid, not hex_model: attach the EHSA category to hex_model by centroid-in-polygon
    arcpy.management.FeatureToPoint(os.path.join(GDB, "hex_model"), os.path.join(GDB, "hex_model_pts"), "INSIDE")
    arcpy.analysis.SpatialJoin(os.path.join(GDB, "hex_model_pts"), out, os.path.join(GDB, "hex_model_ehsa"), "JOIN_ONE_TO_ONE", "KEEP_ALL", match_option="WITHIN")
    flds = ["GRID_ID", "PATTERN"] if "GRID_ID" in [f.name for f in arcpy.ListFields(os.path.join(GDB, "hex_model_ehsa"))] else ["ORIG_FID", "PATTERN"]
    with open(os.path.join(SPAT, "hex_ehsa.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(flds)
        for r in arcpy.da.SearchCursor(os.path.join(GDB, "hex_model_ehsa"), flds): w.writerow(r)
    print("step C done:", os.path.join(SPAT, "hex_ehsa.csv"))

# Note: exec() in the ArcGIS Pro Python window sets __name__ to "__main__"; call the steps explicitly instead:
#   d = stepA_hexagons(); stepB_mgwr(d); stepC_ehsa()
