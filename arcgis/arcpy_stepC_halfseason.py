"""
arcpy_stepC_halfseason.py — Step C (Emerging Hot Spot Analysis) with 14 half-season time slices.

Why: 'Create Space Time Cube' requires >= 10 time slices; seven annual seasons give 7. Each season is split at
composite 12 (~23 July) into an early and a late half by episode onset (notebook §14 writes
parcel_halfseason_nonrec.csv), dated 1 March / 1 September so a 6-month time step separates them: 14 slices.
The analysis variable rel_nonrec is the parcel's unrecovered stress-days divided by the oasis-wide mean of the
same half-season, so hot spots are hexagons consistently above the oasis level and trends are relative trends.

Use in the ArcGIS Pro Python window, after exec() of arcpy_spatial_extension.py (needs GDB, SPAT, CRS, to_oid32):
    exec(open(r"D:\BRA\TipTap\hydraulic\arcpy_stepC_halfseason.py").read())
    stepC_ehsa()            # points -> cube (14 slices)
    stepC_ehsa_part2()      # EHSA -> hex_model join -> spatial\hex_ehsa.csv (read by notebook §16)
"""
import arcpy, os, csv
HALF_CSV = os.path.join(ROOT, r"TipTap\outputs_final\gis\parcel_halfseason_nonrec.csv")
CUBE     = os.path.join(SPAT, "nonrec_cube.nc")

def stepC_ehsa():
    pts = os.path.join(GDB, "half_pts"); px = os.path.join(GDB, "half_pts_x")
    arcpy.management.XYTableToPoint(HALF_CSV, pts, "lon", "lat", coordinate_system=arcpy.SpatialReference(4326))
    arcpy.management.Project(pts, px, CRS); to_oid32(px)
    arcpy.management.AddField(px, "t_date", "DATE"); arcpy.management.CalculateField(px, "t_date", "!date!", "PYTHON3")
    print("half-season points:", int(arcpy.management.GetCount(px)[0]))
    try:
        arcpy.stpm.CreateSpaceTimeCube(in_features=px, output_cube=CUBE, time_field="t_date",
                                       time_step_interval="6 Months", time_step_alignment="START_TIME",
                                       distance_interval="1.52 Kilometers",
                                       summary_fields=[["rel_nonrec", "MEAN", "ZEROS"], ["nonrec_days", "MEAN", "ZEROS"], ["episodes", "SUM", "ZEROS"]],
                                       aggregation_shape_type="HEXAGON_GRID")
        print(arcpy.GetMessages()); print("cube written:", CUBE, "-> now call stepC_ehsa_part2()")
    except Exception as e:
        print("Create Space Time Cube did not run from arcpy:", e)
        print("Run 'Create Space Time Cube By Aggregating Points' from the Geoprocessing pane: input half_pts_x, output", CUBE,
              "| time field t_date | time step 6 Months | alignment start time | distance interval 1.52 km |",
              "summary fields rel_nonrec MEAN (fill ZEROS), nonrec_days MEAN (ZEROS), episodes SUM (ZEROS) | shape Hexagon grid — then call stepC_ehsa_part2().")

def stepC_ehsa_part2(neighborhood_km=6, variable="REL_NONREC_MEAN_ZEROS"):
    out = os.path.join(GDB, "hex_ehsa")
    arcpy.stpm.EmergingHotSpotAnalysis(in_cube=CUBE, analysis_variable=variable, output_features=out,
                                       neighborhood_distance=f"{neighborhood_km} Kilometers", neighborhood_time_step=1,
                                       conceptualization_of_spatial_relationships="FIXED_DISTANCE", define_global_window="ENTIRE_CUBE")
    print(arcpy.GetMessages())
    hm = os.path.join(GDB, "hex_model"); hp = os.path.join(GDB, "hex_model_pts"); hj = os.path.join(GDB, "hex_model_ehsa")
    arcpy.management.FeatureToPoint(hm, hp, "INSIDE")
    arcpy.analysis.SpatialJoin(hp, out, hj, "JOIN_ONE_TO_ONE", "KEEP_ALL", match_option="WITHIN")
    names = [f.name for f in arcpy.ListFields(hj)]
    idf = next(n for n in ["GRID_ID", "SOURCE_ID", "ORIG_FID"] if n in names)
    flds = [idf, "PATTERN"] + [n for n in names if "TREND" in n.upper() or n.upper().startswith("PCT_HOT") or n.upper().startswith("PCT_COLD")]
    with open(os.path.join(SPAT, "hex_ehsa.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(flds)
        for r in arcpy.da.SearchCursor(hj, flds): w.writerow(r)
    cnt = {}
    for (p,) in arcpy.da.SearchCursor(hj, ["PATTERN"]): cnt[p] = cnt.get(p, 0) + 1
    print("step C done:", os.path.join(SPAT, "hex_ehsa.csv")); print("pattern counts:", cnt)
