# Earth Engine exports

| script | output | read by |
|---|---|---|
| Sentinel zonal / PMLI export (Earth Engine Code Editor script; add as `gee_export_sentinel_zonal_pmli.js`) | `tiptap_zonal_YYYY_NNN.csv` (Sentinel-2 L2A and Sentinel-1 IW GRD parcel mean and SD on the 12-day grid, 4,000 parcels per file), `tiptap_pmli_YYYY.csv`, `tiptap_cell_lookup.csv` | notebook 1.2 |
| `gee_export_era5_cell_12day.py` | `era5_cell_12day_YYYY.csv` (concatenate into `era5_cell_12day.csv`) | notebook 1.9 |
| `gee_export_dem_kashgar.py` | Copernicus GLO-30 DEM and MERIT Hydro for the hydraulic network | `arcgis/arcpy_hydraulic_position.py` |

Set `EE_PROJECT` to your Earth Engine project before running.
