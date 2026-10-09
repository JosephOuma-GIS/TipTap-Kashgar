# Tip–Tap: persistent crop stress and agricultural land-use change, Kashgar oasis (2019–2025)

Code for Ouma et al., *Persistent crop stress and agricultural land-use change* (manuscript). The analysis follows 127,245 irrigated parcels through seven growing seasons on 12-day Sentinel-1/2 composites, detects confirmed crop-stress episodes (Tip) and their recovery (Tap) against a crop × county × composite baseline, models recovery with harvest censoring, and tests whether the 2019–2022 recovery record precedes exit from cultivation and annual-to-orchard conversion in 2023–2025.

## Repository

| Folder | Content | Environment |
|---|---|---|
| `notebooks/TipTap_complete_analysis.ipynb` | Full analysis, run top to bottom. Part 1 core analysis; Part 2 parcel sample and fixed boundaries; Part 3 cultivation rule and crop maps; Part 4 revision checks | Python (`environment.yml`) |
| `gee/` | Google Earth Engine exports: ERA5-Land 12-day block forcing, Copernicus DEM for the hydraulic network | Python + `earthengine-api` |
| `arcgis/` | ArcGIS Pro 3.x scripts: directed hydraulic position, MGWR, emerging hot spots, study-area scene | ArcGIS Pro Python (arcpy, Spatial and Network Analyst) |
| `figures/fig2_decision_logic.py` | Fig. 2, decision logic of the Tip–Tap detection | Python (matplotlib) |
| `zenodo/prepare_zenodo.py` | Builds the Zenodo input-data package | Python |

## Data

Input data are archived at Zenodo (doi:10.5281/zenodo.23263208) under the file names and folder layout the notebook reads. Unzip and set `TIPTAP_DATA_ROOT` to the unzipped folder.

| Input | Source | Path under `TIPTAP_DATA_ROOT` (default `D:\BRA`) |
|---|---|---|
| Sentinel-1/2 parcel panel, parcel geometry | Earth Engine export; Wu et al. (2025) boundaries | `TipTap/outputs_recovery/interim/panel_full_YYYY.parquet`, `parcel_meta_full_YYYY.parquet` |
| Plastic-mulch index, ERA5 cell lookup | Earth Engine export | `TipTap_Kashgar/tiptap_pmli_YYYY.csv`, `tiptap_cell_lookup.csv` |
| ERA5-Land 12-day forcing | `gee/gee_export_era5_cell_12day.py` | `TipTap/outputs_recovery/interim/era5_cell_12day.csv` |
| Crop maps 2019–2024 | Liang et al. (2026) | `Data/Kashgar_crops_HLS30/` |
| Plastic-mulched farmland 2020 | China-PMF-10 | `Data/Public/China-PMF-10_2020.tif` |
| VIIRS night-time light | Earth Engine export | `Data/Gee_Data/financial_capital/viirs_ntl/` |
| Directed hydraulic position, MGWR and hot-spot results | `arcgis/` | `TipTap/hydraulic/` |
| OpenStreetMap extract, geoBoundaries ADM3, prefecture outline | public (not redistributed) | `Data/...` (paths in notebook 1.1) |

## Run order

1. `gee/`: ERA5-Land forcing and the DEM (the Sentinel panel is supplied in the Zenodo package).
2. Notebook Part 1, sections 1.1–1.17. Section 1.17 writes the parcel and half-season tables for ArcGIS.
3. `arcgis/arcpy_hydraulic_position.py` (guide: `arcgis/TipTap_HydraulicPosition_Guide.md`), then `arcgis/arcpy_spatial_extension.py` and `arcgis/arcpy_stepC_halfseason.py`. These write `TipTap/hydraulic/`; the published results are included, so this step is needed only if the parcel layer changes.
4. Run the notebook top to bottom.
5. `python figures/fig2_decision_logic.py <output path>` for Fig. 2.

Settings: `TIPTAP_DATA_ROOT`; `TIPTAP_DEV=1` for a quick code check on the first export chunk of each year (outputs tagged `dev`, not for reporting). All random steps use seed 20260913. A full run takes several hours and about 16 GB of RAM.

## Outputs and the manuscript

All outputs are written under `TipTap/outputs_recovery/`.

| Manuscript | File | Notebook section |
|---|---|---|
| Fig. 1 | ArcGIS layout (`arcgis/arcpy_fig1_scene.py`) | — |
| Fig. 2 | `figures/fig2_decision_logic.py` | — |
| Fig. 3 | `figures/fig9_network_commands` | 1.20 |
| Fig. 4 | `figures/fig1_system` | 1.16 |
| Fig. 5, Table 3 | `figures/fig2_km_recovery`, `tables/table1_recovery_by_stratum.csv` | 1.10 |
| Fig. 6 | `figures/fig3_inequality` | 1.12 |
| Fig. 7 | `figures/fig4_exit` | 1.13 |
| Fig. 8 | `figures/fig5_targeting` | 1.14 |
| Fig. 9 | `figures/fig6_targeting_by_command` | 1.18 |
| Fig. 10, Fig. 11 | `figures/fig7_mgwr_local_effects`, `figures/fig8_emerging_hotspots` | 1.19 |
| Fig. 12 | `revision/R_checks/FigS_calibration_2023_2024.pdf` | 4.3 |
| Fig. 13 | `figures/fig10_deficit_exit_map` | 1.20 |
| Table 4 | `revision/R_checks/Table4_landuse_change.csv` | 4.8 |
| Supplementary tables | `revision/R10_R11/`, `revision/R12_R13/`, `revision/R_checks/` | Parts 2–4 |

Figures are written as 600 dpi PNG and vector PDF.

## Licence and citation

Code: MIT (see `LICENSE`). Data: see the Zenodo record. Please cite the article and the Zenodo DOI of the code release.
