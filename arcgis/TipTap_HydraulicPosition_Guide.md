# Directed hydraulic position for every Kashgar parcel
### From Earth Engine terrain export to an ArcGIS Pro network solve to the notebook — step by step

Companion to `TipTap_02_recovery_inequality_pipeline.ipynb`. Files in `D:\BRA\TipTap\hydraulic\`:
`gee_export_dem_kashgar.py` (step A), `arcpy_hydraulic_position.py` (steps 1–9), this guide, and — once you have run it — `hydraulic_position.csv`, the one file the notebook needs.

**What this replaces and why.** The notebook's §4.4 measures water access as undirected network distance from any river node along OSM lines, snapping parcels within 3 km. Two weaknesses: 60% of parcels are farther than 3 km from any mapped channel (OSM is sparse in the Bingtuan divisions), and an undirected graph cannot tell a parcel at the head of a lateral from one at its tail when both are equally far from the river. The workflow below (i) gives every canal edge a flow direction from the Copernicus 30 m DEM, (ii) identifies intakes where the distribution network leaves a river, (iii) solves the *downstream* shortest path from each intake to each parcel with Network Analyst's Closest Facility, and (iv) turns the result into a head-to-tail rank within each canal command — the variable the head–tail inequity literature uses. Parcels the mapped network cannot reach get a physically meaningful DEM fallback (elevation below the nearest intake) instead of a flag alone.

Expected time: GEE export 20–60 min (background); ArcGIS steps 1–5 about 30 min; network build 5 min; Closest Facility solve 30–90 min for ~50 000 reachable parcels; notebook rerun from §4 about 15 min.

---

## A. Data acquisition in Earth Engine (terrain inputs, clipped to Kashgar Prefecture)

**A1.** Install the client once in the `geo` environment: `pip install earthengine-api`.

**A2.** Run the export script from a terminal with `geo` active:

```
python D:\BRA\TipTap\hydraulic\gee_export_dem_kashgar.py --oasis
```

`--oasis` clips the DEM to the ESA WorldCover cropland mask buffered by 15 km, which covers every parcel and every canal but leaves out the Pamir and Kunlun slopes (the full prefecture is ~162 000 km², about 180 million 30 m pixels, and Fill/Flow Direction on that takes hours for nothing). Drop the flag only if you want the whole prefecture. The script reads your own boundary (`Data\kashgar_perfecture.shp`), so the clip is identical to the notebook's.

Four tasks start in Earth Engine: `kashgar_dem_glo30` (Copernicus DEM GLO-30, void-filled, EPSG:32643, 30 m), `kashgar_merit_upa` and `kashgar_merit_dir` (MERIT Hydro upstream area and D8 direction at 90 m, used only as an independent cross-check of canal directions), and `kashgar_oasis_extent` (the clip polygon, for your map).

**A3.** When the tasks finish (Code Editor → Tasks, or `earthengine task list`), download the Drive folder `TipTap_Kashgar_terrain` into `D:\BRA\TipTap\hydraulic\` (so the DEM is at `hydraulic\TipTap_Kashgar_terrain\kashgar_dem_glo30.tif`). If the DEM arrived as several tiles (`kashgar_dem_glo30-0000000000-0000000000.tif`, …), mosaic them once: ArcGIS Pro → *Mosaic To New Raster* (32-bit float, 1 band, output `kashgar_dem_glo30.tif`), or `gdal_merge.py -o kashgar_dem_glo30.tif kashgar_dem_glo30-*.tif`.

**A4.** Also make sure the notebook has been run at least through §13 once on the full panel, because the parcel layer the ArcGIS script uses is `TipTap\outputs_final\gis\parcels_recovery.gpkg` (it carries `parcel_id`, `county`, and the current covariates).

Why Copernicus GLO-30 and not SRTM: GLO-30 is a 2011–2015 TanDEM-X product with ~2 m vertical accuracy on flat terrain versus SRTM's 2000 acquisition and ~6 m; on an oasis whose canals drop only a few metres per kilometre, that difference decides whether edge directions are recoverable at all. The 150 m focal mean applied in step 2 is there for the same reason.

---

## B. ArcGIS Pro: build the directed water network and solve

Open ArcGIS Pro, create a project in `D:\BRA\TipTap\hydraulic\` (the script creates `hydraulic.gdb` there), and open the Python window (View → Python). Load the script with `exec(open(r"D:\BRA\TipTap\hydraulic\arcpy_hydraulic_position.py").read())` and call the steps one at a time — the first time through, do not run the `__main__` block. Each step prints a count you can sanity-check against the numbers below.

### Step 1 — waterways as a planar graph (`step1_waterways()`)
Exports `river`, `canal`, `drain` and `stream` lines from `osm_all_features.gpkg`, projects them to UTM 43N, and runs *Feature To Line* so that every crossing and touching line becomes a shared endpoint (without this the network would pass over junctions), then *Integrate* at 3 m to close small digitising gaps. Expect roughly 40 000–60 000 edges. GUI equivalent: Export Features → Project → Feature To Line → Integrate.

### Step 2 — DEM hydrology (`step2_dem()`)
*Fill* → *Focal Statistics* (5 × 5 mean, i.e. 150 m) → *Flow Direction* (D8) → *Flow Accumulation*. The smoothed DEM is what edge endpoints are compared against; the raw filled DEM drives flow direction and accumulation. Takes 5–15 minutes on the oasis extent.

### Step 3 — flow direction of every edge (`step3_edge_direction()`)
*Feature Vertices To Points* (START and END) → *Extract Multi Values To Points* (smoothed elevation and flow accumulation) → written back to the edges. Rule: `FlowDir = "FT"` (from start to end vertex) if the start is more than 0.5 m higher, `"TF"` if lower, otherwise the segment is *flat* and direction is taken from the D8 accumulation gradient; if that is also indeterminate the edge is `"B"` (both directions allowed) and flagged. Read the printed count of flat edges: on the Kashgar alluvial fans expect 10–25%. If it is above 40%, raise the focal window to 7 × 7 or the tolerance to 1.0 m — do not lower the tolerance, that only manufactures noise directions.

### Step 4 — intakes (`step4_intakes()`)
An intake is the START vertex of a canal/drain/stream edge that lies within 60 m of a river and whose edge flows away from the river (`FlowDir` FT or B). Expect a few hundred. Open `intakes` on top of Sentinel-2 imagery (Living Atlas → Sentinel-2 Level-2A) and check a handful against the visible headworks on the Kashgar and Yarkand rivers; delete obvious false intakes (a drain discharging *into* the river will occasionally pass the rule) and add missing major headworks by hand — a dozen manual edits here are worth more than any parameter.

### Step 5 — parcels as incidents plus the DEM fallback (`step5_parcels()`)
Parcel inside-points from `parcels_recovery.gpkg`, sampled on the smoothed DEM; *Near* to rivers and to intakes. Produces `hyd_dz_m` = parcel elevation minus elevation of its nearest intake: negative means the parcel lies below its intake, as gravity irrigation requires. This is the covariate used for parcels the mapped network never reaches, and it is meaningful everywhere because it needs no canal lines at all.

### Step 6 — network dataset with the flow-direction restriction (one-time, GUI)
arcpy can build and solve a network but cannot add a field-based restriction without a template, so create it once by hand:

1. Catalog → `hydraulic.gdb\network` → right-click → *New → Network Dataset*. Name `water_nd`, source feature class `water_edges`, elevation model *No elevation*.
2. Open the network dataset properties. **Travel Attributes → Costs:** keep `Length` (metres). **Travel Attributes → Restrictions:** add `Downstream`, usage *Prohibited*, and set its evaluator on `water_edges` to *Field Script* with
   - From–To direction: `[FlowDir] = "TF"`  (prohibited when the edge flows the other way)
   - To–From direction: `[FlowDir] = "FT"`
   Edges coded `B` are therefore traversable both ways.
3. **Travel Modes:** add a mode named `Downstream`, impedance `Length`, restrictions `Downstream` ticked, U-turns *Allowed*. Make it the default.
4. **Source settings → Connectivity:** *End Point* policy for `water_edges` (that is why Feature To Line was run).
5. Build the network (right-click → Build), or run `step6_build_network()`.

Optional but recommended once it works: *Create Template From Network Dataset* and save the XML in `hydraulic\` — after that the whole chain, including a rebuilt network, is scriptable.

### Step 7 — Closest Facility, downstream from intakes (`step7_solve()`)
Facilities = intakes (`Name` = `intake_id`), incidents = parcel points (`Name` = `parcel_id`, search tolerance 3 000 m, snapped to the nearest edge), travel direction *from facilities*, one facility per incident, travel mode `Downstream`. The solver returns, for every reachable parcel, the shortest *downstream* path length from an intake — parcels that are close to a river as the crow flies but fed by a long lateral get a long distance, which is the whole point. Parcels beyond 3 000 m of any edge are skipped and appear later as `hyd_mapped = 0`. The solve is the slow step; if it exceeds two hours, run it county by county by selecting incidents.

### Step 8 — the covariate table (`step8_export()`)
Writes `hydraulic_position.csv` with:

| column | meaning |
|---|---|
| `parcel_id` | join key |
| `intake_id` | the intake that serves the parcel (its canal command) |
| `hyd_net_dir_m` | directed network distance from that intake (m); empty if unreachable |
| `hyd_rank_cmd` | percentile rank of that distance among parcels on the same intake: 0 = head, 1 = tail (needs ≥ 5 parcels on the intake) |
| `hyd_rank_county` | the same rank within the county, for commands too small to rank |
| `hyd_dz_m` | parcel elevation minus nearest-intake elevation (m); available for every parcel |
| `dist_intake_m` | straight-line distance to the nearest intake (m) |
| `hyd_mapped` | 1 if the directed network reached the parcel |

The printed "reached" share is the number to report in the paper next to the old 40%. Anything above ~55% is a clear improvement; if it is *lower* than the notebook's undirected figure, some canals have been given the wrong direction (usually flat segments near intakes) — inspect `FlowDir` along the main canals and, if needed, set `FLAT_TOL` to 1.0 and rerun steps 3–8.

### Step 9 — independent check of directions (optional, `step9_qa_merit()`)
Samples MERIT Hydro's D8 direction at every edge midpoint. On river edges the DEM-derived direction should agree with MERIT in well over 80% of cases; on canals agreement will be lower because canals are engineered, but a canal command where agreement is under 50% deserves a look. This is a one-line sentence in the methods that pre-empts the "how do you know the canal flows that way" question.

---

## C. Plug the result into the notebook

Insert a new code cell immediately after the §4 cell (before "5 · Phenology-normalised anomalies") with the content below, then make the three small edits listed under it. Everything downstream — Cox model, H1/H2 GLMs, the exit model, the sensitivity table, the GeoPackage — then uses the directed measure.

```python
# 4.7 · Directed hydraulic position from ArcGIS Pro (replaces the undirected OSM proxy of §4.4)
HYD_CSV = DATA_ROOT / "TipTap" / "hydraulic" / "hydraulic_position.csv"
if HYD_CSV.exists():
    hyd = pd.read_csv(HYD_CSV)
    PARCELS = PARCELS.drop(columns=[c for c in ["intake_id", "hyd_net_dir_m", "hyd_rank_cmd", "hyd_rank_county", "hyd_dz_m", "dist_intake_m", "hyd_mapped"] if c in PARCELS], errors="ignore")
    PARCELS = PARCELS.merge(hyd, on="parcel_id", how="left")
    PARCELS["hyd_mapped"] = PARCELS.hyd_mapped.fillna(0).astype(int)
    # head-to-tail rank: within canal command where the command is large enough, else within county
    PARCELS["hyd_rank"] = PARCELS.hyd_rank_cmd.fillna(PARCELS.hyd_rank_county)
    # parcels the network cannot reach keep the DEM fallback and a flag; their rank is set to the county median
    PARCELS["hyd_unmapped"] = (PARCELS.hyd_mapped == 0).astype(int)
    PARCELS["hyd_rank"] = PARCELS.hyd_rank.fillna(PARCELS.groupby("county").hyd_rank.transform("median")).fillna(0.5)
    PARCELS["hyd_dz_m"] = PARCELS.hyd_dz_m.fillna(PARCELS.groupby("county").hyd_dz_m.transform("median"))
    PARCELS["hyd_remote_km"] = np.where(PARCELS.hyd_mapped == 1, PARCELS.hyd_net_dir_m / 1000, PARCELS.hyd_remote_km)   # used by the Lorenz curve
    PARCELS["hyd_tercile"] = PARCELS.groupby("county")["hyd_rank"].transform(lambda s: pd.qcut(s.rank(method="first"), 3, labels=["head", "middle", "tail"]))
    MANIFEST["hydraulic_source"] = "ArcGIS Pro directed network (Copernicus GLO-30 flow direction, Closest Facility from intakes)"
    MANIFEST["hydraulic_unmapped_share"] = float(PARCELS.hyd_unmapped.mean())
    print(f"directed hydraulic position loaded: {PARCELS.hyd_mapped.mean():.1%} of parcels reached by the network; "
          f"hyd_rank median {PARCELS.hyd_rank.median():.2f}; hyd_dz_m median {PARCELS.hyd_dz_m.median():.1f} m")
else:
    PARCELS["hyd_rank"] = np.nan; PARCELS["hyd_dz_m"] = np.nan
    print("hydraulic_position.csv not found — §4.4 undirected proxy remains in use")
```

Then three edits so the models use the rank (and the DEM fallback) instead of the undirected distance:

1. **§8 (Cox)**, in the `NUM = [...]` list, replace `"log_hyd_remote"` with `"hyd_rank", "hyd_dz_m"`.
2. **§9 (H1/H2)**, in `GLM_COLS`, `F_BASE` and `F_INT`, replace every `log_hyd_remote` with `hyd_rank + hyd_dz_m` (in `F_INT` the interaction becomes `hyd_rank:high_demand`), and in the `inter = ...` line replace `"log_hyd_remote:high_demand"` with `"hyd_rank:high_demand"`.
3. **§10 (exit)**, in `F3`, replace `log_hyd_remote` with `hyd_rank + hyd_dz_m`.

`hyd_unmapped` stays in every model as before, so the reader can see whether unreachable parcels behave differently. In §8's grouped-SHAP dictionary, add `"hyd_rank", "hyd_dz_m"` to the water-access group.

Rerun from §4 (the Parquet ingest in §3 is cached, so this is quick). In the results, `hyd_rank` is read as: a coefficient below one in the Cox table or a negative marginal effect in H1 means tail-end parcels recover less often; the `hyd_rank:high_demand` interaction is the head–tail inequity test of H2, and the placebo in §12 (shuffled position) now shuffles `log_dist_desert` — add `hyd_rank` to that shuffle to keep the placebo symmetric.

---

## D. What to write in the methods (two sentences you will need)

"Hydraulic position was derived on a directed water network: OpenStreetMap channels were planarised, each edge was assigned a flow direction from the elevation drop on the 150 m-smoothed Copernicus GLO-30 DEM (flat segments resolved by D8 accumulation gradient, X% flagged), intakes were defined as channel heads within 60 m of a river, and the downstream shortest path from the nearest intake to each parcel was solved with ArcGIS Pro Network Analyst (Closest Facility, one-way restriction). Position is expressed as the percentile rank of that distance within the canal command (0 = head, 1 = tail); the Y% of parcels beyond 3 km of any mapped channel enter the models with a flag and with their elevation below the nearest intake as the fallback measure."

Fill X and Y from the printed counts of steps 3 and 8.

---

# Part 2 — Spatial extension: MGWR, emerging hot spots, command-level targeting

Files: `arcpy_spatial_extension.py` (ArcGIS Pro), `notebook_cells_spatial.md` (three notebook cells §14–§16, also built into `TipTap_02_recovery_inequality_pipeline_v3.ipynb`). Order of operations:

1. **Notebook first.** Run the notebook (with the hydraulic cells) through §14. §14 rewrites `outputs_recovery\gis\parcels_recovery.gpkg` with `mulch_share`, `log_area` and `log_ntl` added, and writes `outputs_recovery\gis\parcel_season_nonrec.csv` (one row per cultivated parcel-season: lon, lat, date, unrecovered stress-days, episodes). §15 (command-level targeting) runs immediately, needing nothing from ArcGIS. §16 prints "not found" until step 3 is done.
2. **ArcGIS Pro.** In the Python window: `exec(open(r"D:\BRA\TipTap\hydraulic\arcpy_spatial_extension.py").read())`, then `d = stepA_hexagons()`, `stepB_mgwr(d)`, `stepC_ehsa()`. Outputs land in `TipTap\hydraulic\spatial\`.
3. **Notebook again.** Rerun §16 only (Run Cell). Figures 7 and 8 and Table 10 appear.

## Step A — hexagons (`stepA_hexagons`)
*Generate Tessellation* (2 km² hexagons, UTM 43N) over the parcel extent; parcel inside-points; *Summarize Within* sums `variable × area_ha` and `area_ha` per hexagon, so every hexagon value is the **area-weighted mean** of its parcels. Hexagons with fewer than 5 parcels are dropped (`MIN_PARCELS_PER_HEX`). Expect 4 000–6 000 hexagons on the full panel. The dependent variable for MGWR is `log_deficit = log1p(deficit_days)` — unrecovered stress-days per cultivated season 2019–22, which is right-skewed. The geometry is exported to `spatial\hex_grid.gpkg`.

## Step B — Multiscale GWR (`stepB_mgwr`)
*Multiscale Geographically Weighted Regression* (Spatial Statistics → Modeling Spatial Relationships), continuous model, drivers `hyd_rank, hyd_dz_m, dist_desert_km, log_area, mulch_share, si_preseason, log_ntl, dist_settlement_km`, neighbourhood = number of neighbours chosen by golden search between 30 and 1000, bisquare kernel, scaled data. Two outputs are exported: `hex_mgwr.csv` (local coefficients `C*_<driver>`, local R², predictions, residuals per hexagon) and `mgwr_bandwidths.csv` (one bandwidth per driver). **How to read it:** a driver with a small bandwidth (say 60 neighbours) varies locally — its effect differs between oases; a driver with a bandwidth near the maximum is effectively global, and the notebook's single coefficient for it is the right summary. The local-coefficient maps (Fig. 7) show where each lever matters; a hexagon with a strongly positive `mulch_share` coefficient, for instance, is a place where drip conversion is *not* associated with lower deficit — worth a sentence in the discussion.

If the arcpy call fails on a parameter name (tool signatures shift between Pro versions), run the tool from the Geoprocessing pane with the same settings, name the output `hex_mgwr` and the table `mgwr_bandwidths` in `hydraulic.gdb`, then call `stepB_mgwr()` again — it will skip nothing but the export will work because the outputs exist. Simpler still: comment out the `arcpy.stats.MGWR(...)` call before re-running.

Two MGWR failure modes to expect: "severe multicollinearity" (drop `log_ntl` or `dist_settlement_km`, which correlate in Bingtuan areas) and "not enough features" for the chosen minimum neighbours (raise `MIN_PARCELS_PER_HEX` or lower `minimum_number_of_neighbors` to 20).

## Step C — Emerging Hot Spot Analysis (`stepC_ehsa`)
*XY Table To Point* on `parcel_season_nonrec.csv` → *Create Space Time Cube By Aggregating Points* (hexagon bins 1.52 km high ≈ 2 km², annual time steps, SUM of unrecovered stress-days with empty bins as zero) → *Emerging Hot Spot Analysis* on `NONREC_DAYS_SUM_ZEROS` with a 6 km fixed-distance neighbourhood and a one-step time window → categories joined to the modelling hexagons and exported as `hex_ehsa.csv`. Seven annual slices is the minimum the Mann–Kendall trend inside EHSA can work with; interpret *intensifying/persistent* and *diminishing* with that in mind, and treat *new* or *sporadic* categories with caution. **How to read it:** Table 10 in the notebook cross-tabulates the category against the 2023–25 exit and orchard-conversion rates — the expectation from H3 is that exit concentrates in persistent and intensifying hot spots. If EHSA complains that the cube has too few time steps, change `time_step_interval` to "6 Months" (14 slices; empty winter slices are zeros).

## §15 — targeting by canal command (notebook only)
Parcels served by the same intake (tier 1 or 2) form a canal command; commands with at least 10 parcels are ranked by the same five rules as §11 and evaluated on 2023–25 unrecovered stress-days. Table 9 and Fig. 6 report capture at 10/20/30% of commands and of command area. This replaces the Location-Allocation step originally proposed: the command is the unit a rehabilitation programme funds, and no network dataset is needed.

## Methods sentences
"Spatial heterogeneity of the structural effects was examined with multiscale geographically weighted regression on 2 km hexagons (area-weighted parcel means; golden-search bandwidths, bisquare kernel), and the space–time pattern of unrecovered stress with emerging hot-spot analysis on a hexagon–year space–time cube (Getis–Ord Gi* with a 6 km neighbourhood, Mann–Kendall trend across seven seasons). Targeting rules were evaluated at the scale of the canal command, defined by the intake serving each parcel on the directed water network."
