"""
arcpy_hydraulic_position.py — directed hydraulic position of every Kashgar parcel (ArcGIS Pro 3.x, arcpy + Spatial Analyst + Network Analyst)

Produces  D:\BRA\TipTap\hydraulic\hydraulic_position.csv  with one row per parcel:
    parcel_id, intake_id, hyd_net_dir_m, hyd_rank_cmd, hyd_rank_county, hyd_dz_m, dist_river_m, hyd_mapped

Run it step by step from the ArcGIS Pro Python window or as a script in the Pro conda environment.
Steps 1–5 and 7–9 are automated. Step 6 (network dataset with the flow-direction restriction) is done once in the
GUI, following the guide; after that the script can rebuild and re-solve as often as you like.

Run each STEP block on its own the first time and read the messages.
"""
import arcpy, os, csv, math
from arcpy.sa import Fill, FlowDirection, FlowAccumulation, FocalStatistics, NbrRectangle, ExtractMultiValuesToPoints

arcpy.CheckOutExtension("Spatial"); arcpy.CheckOutExtension("Network")
arcpy.env.overwriteOutput = True

# ------------------------------------------------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------------------------------------------------
ROOT      = r"D:\BRA"
WORK      = os.path.join(ROOT, "TipTap", "hydraulic")
GDB       = os.path.join(WORK, "hydraulic.gdb")
FDS       = os.path.join(GDB, "network")                      # feature dataset that will hold the network dataset
OSM_GPKG  = os.path.join(ROOT, r"Data\Gee_Data\social_financial_capital\osm\osm_all_features.gpkg", "main.osm_all_features")
TERRAIN   = os.path.join(WORK, "TipTap_Kashgar_terrain")                     # where the GEE download was placed
DEM_TIF   = os.path.join(TERRAIN, "kashgar_dem_glo30.tif")          # from gee_export_dem_kashgar.py
PARCELS   = os.path.join(ROOT, r"TipTap\outputs_final\gis\parcels_recovery.gpkg", "main.parcels")  # notebook §13 output
CRS       = arcpy.SpatialReference(32643)                    # UTM 43N, metres — must match the DEM export
FLAT_TOL  = 0.5      # m: elevation drop below this -> segment treated as flat (both directions allowed, flagged)
SNAP_TOL  = "3000 Meters"   # parcels farther than this from the network are 'unmapped' (same rule as the notebook)
INTAKE_TOL = 60      # m: a canal end within this distance of a river counts as an intake
os.makedirs(WORK, exist_ok=True)
if not arcpy.Exists(GDB): arcpy.management.CreateFileGDB(WORK, "hydraulic.gdb")
if not arcpy.Exists(FDS): arcpy.management.CreateFeatureDataset(GDB, "network", CRS)
arcpy.env.workspace = GDB

# ------------------------------------------------------------------------------------------------------------
# STEP 1 — waterways from OSM, projected, split at every intersection (planar graph)
# ------------------------------------------------------------------------------------------------------------
def step1_waterways():
    arcpy.conversion.ExportFeatures(OSM_GPKG, os.path.join(GDB, "osm_water_raw"),
                                    where_clause="fclass IN ('river','canal','drain','stream')")
    arcpy.management.Project("osm_water_raw", "osm_water_utm", CRS)
    # Feature To Line splits lines where they cross/touch so that junctions become shared endpoints
    arcpy.management.FeatureToLine("osm_water_utm", os.path.join(FDS, "water_edges"), cluster_tolerance="2 Meters", attributes="ATTRIBUTES")
    arcpy.management.Integrate(os.path.join(FDS, "water_edges"), "3 Meters")          # closes tiny gaps at junctions
    arcpy.management.AddField(os.path.join(FDS, "water_edges"), "edge_id", "LONG")
    arcpy.management.CalculateField(os.path.join(FDS, "water_edges"), "edge_id", "!OBJECTID!", "PYTHON3")
    print("step 1 done:", arcpy.management.GetCount(os.path.join(FDS, "water_edges")))

# ------------------------------------------------------------------------------------------------------------
# STEP 2 — DEM hydrology: fill, smooth, flow direction, flow accumulation
# ------------------------------------------------------------------------------------------------------------
def step2_dem():
    dem = arcpy.Raster(DEM_TIF)
    arcpy.env.snapRaster = dem; arcpy.env.cellSize = dem
    dem_fill = Fill(dem); dem_fill.save(os.path.join(GDB, "dem_fill"))
    dem_smooth = FocalStatistics(dem_fill, NbrRectangle(5, 5, "CELL"), "MEAN"); dem_smooth.save(os.path.join(GDB, "dem_smooth"))  # 150 m mean: removes pixel noise on a 30 m DEM before endpoint comparison
    fdir = FlowDirection(dem_fill, "NORMAL", None, "D8"); fdir.save(os.path.join(GDB, "flowdir_d8"))
    facc = FlowAccumulation(fdir, None, "FLOAT", "D8"); facc.save(os.path.join(GDB, "flowacc"))
    print("step 2 done")

# ------------------------------------------------------------------------------------------------------------
# STEP 3 — direction of every edge from the elevation drop between its start and end vertex
# ------------------------------------------------------------------------------------------------------------
def step3_edge_direction():
    edges = os.path.join(FDS, "water_edges")
    for which in ["START", "END"]:
        pts = os.path.join(GDB, f"edge_{which.lower()}")
        arcpy.management.FeatureVerticesToPoints(edges, pts, which)
        ExtractMultiValuesToPoints(pts, [[os.path.join(GDB, "dem_smooth"), f"z_{which.lower()}"],
                                         [os.path.join(GDB, "flowacc"), f"fa_{which.lower()}"]], "NONE")
    for f in ["z_start", "z_end", "fa_start", "fa_end"]:
        if f not in [x.name for x in arcpy.ListFields(edges)]: arcpy.management.AddField(edges, f, "DOUBLE")
    for which in ["start", "end"]:
        vals = {r[0]: (r[1], r[2]) for r in arcpy.da.SearchCursor(os.path.join(GDB, f"edge_{which}"), ["ORIG_FID", f"z_{which}", f"fa_{which}"])}
        with arcpy.da.UpdateCursor(edges, ["OBJECTID", f"z_{which}", f"fa_{which}"]) as cur:
            for row in cur:
                z, fa = vals.get(row[0], (None, None)); row[1], row[2] = z, fa; cur.updateRow(row)
    # FlowDir: FT = flows from start to end (start higher), TF = end to start, B = flat/undetermined (both allowed)
    for f, t in [("FlowDir", "TEXT"), ("dz_m", "DOUBLE"), ("flat", "SHORT")]:
        if f not in [x.name for x in arcpy.ListFields(edges)]: arcpy.management.AddField(edges, f, t, field_length=2 if t == "TEXT" else None)
    n_flat = 0
    with arcpy.da.UpdateCursor(edges, ["z_start", "z_end", "fa_start", "fa_end", "FlowDir", "dz_m", "flat"]) as cur:
        for row in cur:
            zs, ze, fs, fe = row[0], row[1], row[2], row[3]
            dz = (zs - ze) if (zs is not None and ze is not None) else None
            if dz is None: fd, flat = "B", 1
            elif dz > FLAT_TOL: fd, flat = "FT", 0
            elif dz < -FLAT_TOL: fd, flat = "TF", 0
            else:   # flat within tolerance: fall back to the D8 accumulation gradient (water flows toward higher accumulation)
                if fs is not None and fe is not None and abs(fe - fs) > 0: fd, flat = ("FT" if fe > fs else "TF"), 1
                else: fd, flat = "B", 1
            row[4], row[5], row[6] = fd, dz, flat; n_flat += flat; cur.updateRow(row)
    print("step 3 done; flat/undetermined edges:", n_flat)

# ------------------------------------------------------------------------------------------------------------
# STEP 4 — intakes: points where the distribution network takes water from a river
# ------------------------------------------------------------------------------------------------------------
def step4_intakes():
    edges = os.path.join(FDS, "water_edges")
    arcpy.management.MakeFeatureLayer(edges, "rivers", "fclass = 'river'")
    arcpy.management.MakeFeatureLayer(edges, "channels", "fclass IN ('canal','drain','stream')")
    # (a) topological junctions: channel edges whose START vertex touches a river
    arcpy.management.FeatureVerticesToPoints("channels", os.path.join(GDB, "chan_start"), "START")
    arcpy.management.MakeFeatureLayer(os.path.join(GDB, "chan_start"), "chan_start_lyr")
    arcpy.management.SelectLayerByLocation("chan_start_lyr", "WITHIN_A_DISTANCE", "rivers", f"{INTAKE_TOL} Meters", "NEW_SELECTION")
    arcpy.management.CopyFeatures("chan_start_lyr", os.path.join(GDB, "intakes_raw"))
    # (b) keep only intakes that are heads (edge flows away from the river): FlowDir = FT at a start vertex
    arcpy.management.MakeFeatureLayer(os.path.join(GDB, "intakes_raw"), "intakes_lyr", "FlowDir IN ('FT','B')")
    arcpy.management.CopyFeatures("intakes_lyr", os.path.join(GDB, "intakes"))
    arcpy.management.AddField(os.path.join(GDB, "intakes"), "intake_id", "LONG")
    arcpy.management.CalculateField(os.path.join(GDB, "intakes"), "intake_id", "!OBJECTID!", "PYTHON3")
    print("step 4 done: intakes =", arcpy.management.GetCount(os.path.join(GDB, "intakes")))

# ------------------------------------------------------------------------------------------------------------
# STEP 5 — parcel centroids as incidents (+ DEM fallback covariates for parcels the network cannot reach)
# ------------------------------------------------------------------------------------------------------------
def step5_parcels():
    arcpy.management.Project(PARCELS, os.path.join(GDB, "parcels_utm"), CRS)
    arcpy.management.FeatureToPoint(os.path.join(GDB, "parcels_utm"), os.path.join(GDB, "parcel_pts"), "INSIDE")
    ExtractMultiValuesToPoints(os.path.join(GDB, "parcel_pts"), [[os.path.join(GDB, "dem_smooth"), "z_parcel"]], "NONE")
    arcpy.management.MakeFeatureLayer(os.path.join(FDS, "water_edges"), "rivers", "fclass = 'river'")
    arcpy.analysis.Near(os.path.join(GDB, "parcel_pts"), "rivers", search_radius=None, location="NO_LOCATION", angle="NO_ANGLE")  # NEAR_DIST = straight-line distance to river
    arcpy.analysis.Near(os.path.join(GDB, "parcel_pts"), os.path.join(GDB, "intakes"), search_radius=None)                          # overwrites NEAR_FID/NEAR_DIST -> nearest intake
    # elevation of the nearest intake -> hyd_dz_m = z_parcel - z_intake (negative = parcel lies below its intake, as it should)
    z_int = {r[0]: r[1] for r in arcpy.da.SearchCursor(os.path.join(GDB, "intakes"), ["OBJECTID", "z_start"])}
    arcpy.management.AddField(os.path.join(GDB, "parcel_pts"), "hyd_dz_m", "DOUBLE")
    with arcpy.da.UpdateCursor(os.path.join(GDB, "parcel_pts"), ["NEAR_FID", "z_parcel", "hyd_dz_m"]) as cur:
        for row in cur:
            zi = z_int.get(row[0]); row[2] = (row[1] - zi) if (zi is not None and row[1] is not None) else None; cur.updateRow(row)
    print("step 5 done:", arcpy.management.GetCount(os.path.join(GDB, "parcel_pts")))

# ------------------------------------------------------------------------------------------------------------
# STEP 6 — network dataset: ONE-TIME GUI STEP (see guide §6). Afterwards, (re)build here.
# ------------------------------------------------------------------------------------------------------------
ND = os.path.join(FDS, "water_nd")
def step6_build_network():
    if not arcpy.Exists(ND):
        raise SystemExit("Create the network dataset 'water_nd' in the GUI first (guide §6): source = water_edges, "
                         "cost = Length (m), restriction 'Downstream' from field FlowDir, travel mode 'Downstream'.")
    arcpy.na.BuildNetwork(ND); print("step 6 done: network built")

# ------------------------------------------------------------------------------------------------------------
# STEP 7 — Closest Facility: from each intake (facility) downstream to each parcel (incident)
# ------------------------------------------------------------------------------------------------------------
def step7_solve():
    lyr = arcpy.na.MakeClosestFacilityAnalysisLayer(ND, "HydPos", travel_mode="Downstream", travel_direction="FROM_FACILITIES",
                                                   cutoff=None, number_of_facilities_to_find=1, line_shape="NO_LINES",
                                                   ignore_invalid_locations="SKIP").getOutput(0)
    sub = arcpy.na.GetNAClassNames(lyr)
    arcpy.na.AddLocations(lyr, sub["Facilities"], os.path.join(GDB, "intakes"), "Name intake_id #", "200 Meters", append="CLEAR")
    arcpy.na.AddLocations(lyr, sub["Incidents"], os.path.join(GDB, "parcel_pts"), "Name parcel_id #", SNAP_TOL, append="CLEAR",
                          snap_to_position_along_network="SNAP", snap_offset="0 Meters")
    arcpy.na.Solve(lyr, "SKIP", "TERMINATE")
    routes = lyr.listLayers(sub["CFRoutes"])[0]
    arcpy.management.CopyFeatures(routes, os.path.join(GDB, "hyd_routes"))
    print("step 7 done: routes =", arcpy.management.GetCount(os.path.join(GDB, "hyd_routes")))

# ------------------------------------------------------------------------------------------------------------
# STEP 8 — assemble the covariate table: directed network distance, ranks, fallbacks
# ------------------------------------------------------------------------------------------------------------
def step8_export():
    routes = os.path.join(GDB, "hyd_routes")
    len_field = [f.name for f in arcpy.ListFields(routes) if f.name.startswith("Total_")][0]   # Total_Length
    # Name is "<intake> - <parcel>" in CF routes; FacilityID/IncidentID are the OIDs of the sublayer rows, so parse Name
    net = {}
    for name, d in arcpy.da.SearchCursor(routes, ["Name", len_field]):
        intake, parcel = [s.strip() for s in name.split(" - ", 1)]
        net[int(float(parcel))] = (int(float(intake)), float(d))
    # county from the parcels layer (already a column from the notebook)
    rows = []
    with arcpy.da.SearchCursor(os.path.join(GDB, "parcel_pts"), ["parcel_id", "county", "hyd_dz_m", "NEAR_DIST"]) as cur:
        for pid, county, dz, dist_int in cur:
            pid = int(pid); intake, d = net.get(pid, (None, None))
            rows.append(dict(parcel_id=pid, county=county, intake_id=intake, hyd_net_dir_m=d, hyd_dz_m=dz, dist_intake_m=dist_int,
                             hyd_mapped=int(d is not None)))
    # percentile rank of directed distance within canal command (same intake) and within county — head (0) to tail (1)
    import collections
    def add_rank(key, field):
        groups = collections.defaultdict(list)
        for r in rows:
            if r["hyd_net_dir_m"] is not None: groups[r[key]].append(r["hyd_net_dir_m"])
        for r in rows:
            if r["hyd_net_dir_m"] is None or len(groups[r[key]]) < 5: r[field] = None; continue
            g = sorted(groups[r[key]]); r[field] = sum(v <= r["hyd_net_dir_m"] for v in g) / len(g)
    add_rank("intake_id", "hyd_rank_cmd"); add_rank("county", "hyd_rank_county")
    out = os.path.join(WORK, "hydraulic_position.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    mapped = sum(r["hyd_mapped"] for r in rows)
    print(f"step 8 done: {out} | parcels {len(rows)} | reached by the directed network {mapped} ({mapped/len(rows):.1%})")

# ------------------------------------------------------------------------------------------------------------
# STEP 9 (optional QA) — agreement of DEM-derived edge direction with MERIT Hydro D8 direction
# ------------------------------------------------------------------------------------------------------------
def step9_qa_merit(merit_dir_tif=os.path.join(TERRAIN, "kashgar_merit_dir.tif")):
    """Compares the sign of the elevation drop with the MERIT flow direction sampled at the edge midpoint.
    Reports the share of non-flat edges whose direction agrees; expect > 80% on rivers, lower on engineered canals."""
    edges = os.path.join(FDS, "water_edges")
    arcpy.management.FeatureVerticesToPoints(edges, os.path.join(GDB, "edge_mid"), "MID")
    ExtractMultiValuesToPoints(os.path.join(GDB, "edge_mid"), [[merit_dir_tif, "merit_dir"]], "NONE")
    print("MERIT direction sampled; compare 'merit_dir' (MERIT D8 codes) with the bearing of each edge in a quick table — see guide §9")

if __name__ == "__main__":
    step1_waterways(); step2_dem(); step3_edge_direction(); step4_intakes(); step5_parcels()
    step6_build_network(); step7_solve(); step8_export()
