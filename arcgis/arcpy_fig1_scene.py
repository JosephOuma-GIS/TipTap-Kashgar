"""
arcpy_fig1_scene.py — Fig. 1 study-area figure: 3-D perspective of the Kashgar oasis (Local Scene) + plan view + locators.

Run in the ArcGIS Pro Python window (project open):
    exec(open(r"D:\BRA\TipTap\hydraulic\arcpy_fig1_scene.py").read())
    fig1_build_scene()      # creates the Local Scene 'Fig1_3D' with the parcels (RCI), water network, intakes and DEM
    fig1_build_layout()     # creates layout 'Fig1_studyarea' (3-D frame + plan frame + two locators) and exports at 600 dpi
Two settings cannot be set from arcpy and are done once by hand after fig1_build_scene() — see the printed checklist
(ground elevation source and lighting). Everything else is scripted so the figure can be regenerated.
"""
import arcpy, os, glob
arcpy.env.overwriteOutput = True
ROOT = r"D:\BRA"; WORK = os.path.join(ROOT, "TipTap", "hydraulic"); GDB = os.path.join(WORK, "hydraulic.gdb")
OUTF = os.path.join(ROOT, "TipTap", "outputs_final", "figures")
PARCELS = os.path.join(ROOT, r"TipTap\outputs_final\gis\parcels_recovery.gpkg", "main.parcels")
DEM = (glob.glob(os.path.join(WORK, "TipTap_Kashgar_terrain", "*dem*.tif")) + glob.glob(os.path.join(WORK, "TipTap_Kashgar_terrain", "*.tif")) + [None])[0]
PREF = os.path.join(ROOT, r"Data\kashgar_perfecture.shp")
aprx = arcpy.mp.ArcGISProject("CURRENT")

def _fc(name_candidates):
    arcpy.env.workspace = GDB
    fcs = arcpy.ListFeatureClasses() or []
    for ds in (arcpy.ListDatasets() or []):
        fcs += [f"{ds}/{f}" for f in (arcpy.ListFeatureClasses(feature_dataset=ds) or [])]
    for c in name_candidates:
        for f in fcs:
            if f.split("/")[-1].lower() == c.lower(): return os.path.join(GDB, f)
    return None

def fig1_build_scene(vertical_exaggeration=20):
    for m in aprx.listMaps("Fig1_3D"): aprx.deleteItem(m)
    scene = aprx.createMap("Fig1_3D", "SCENE")
    scene.spatialReference = arcpy.SpatialReference(32643)
    # --- layers (bottom to top): DEM, prefecture outline, parcels (RCI), water network, intakes
    if DEM: dem_lyr = scene.addDataFromPath(DEM); print("DEM added:", DEM)
    else: dem_lyr = None; print("DEM not found in", os.path.join(WORK, "TipTap_Kashgar_terrain"))
    pref = scene.addDataFromPath(PREF); pref.name = "Prefecture"
    par = scene.addDataFromPath(PARCELS); par.name = "Parcels (RCI)"
    edges = _fc(["water_edges", "water_edges_dir", "edges_dir"]); intakes = _fc(["intakes", "intakes_all", "intake_pts"])
    e_lyr = scene.addDataFromPath(edges) if edges else None
    i_lyr = scene.addDataFromPath(intakes) if intakes else None
    # --- symbology
    sym = pref.symbology; sym.renderer.symbol.applySymbolFromGallery("Extent Transparent Wide Gray") if hasattr(sym.renderer.symbol, "applySymbolFromGallery") else None
    try:
        sym = pref.symbology; sym.renderer.symbol.color = {"RGB": [0, 0, 0, 0]}; sym.renderer.symbol.outlineColor = {"RGB": [60, 60, 60, 100]}; sym.renderer.symbol.outlineWidth = 1.2; pref.symbology = sym
    except Exception as ex: print("prefecture symbology by hand:", ex)
    try:
        sym = par.symbology; sym.updateRenderer("GraduatedColorsRenderer"); sym.renderer.classificationField = "rci"; sym.renderer.breakCount = 6
        ramps = aprx.listColorRamps("Yellow-Green-Blue (Continuous)") or aprx.listColorRamps("Viridis") or aprx.listColorRamps()
        sym.renderer.colorRamp = ramps[0]
        for b in sym.renderer.classBreaks: b.symbol.outlineColor = {"RGB": [0, 0, 0, 0]}
        par.symbology = sym
    except Exception as ex: print("parcel symbology by hand (graduated colours on 'rci'):", ex)
    if e_lyr:
        try:
            sym = e_lyr.symbology; sym.updateRenderer("UniqueValueRenderer"); sym.renderer.fields = ["fclass"]
            cols = {"river": [21, 101, 192, 100], "canal": [2, 136, 209, 100], "drain": [120, 144, 156, 100], "stream": [77, 182, 172, 100]}
            for g in sym.renderer.groups:
                for it in g.items:
                    it.symbol.color = {"RGB": cols.get(it.values[0][0], [90, 90, 90, 100])}; it.symbol.size = 1.6 if it.values[0][0] == "river" else 0.8
            e_lyr.symbology = sym; e_lyr.name = "Water network (OSM, directed)"
        except Exception as ex: print("edge symbology by hand:", ex)
    if i_lyr:
        try:
            sym = i_lyr.symbology; sym.renderer.symbol.color = {"RGB": [198, 40, 40, 100]}; sym.renderer.symbol.size = 4; i_lyr.symbology = sym; i_lyr.name = "Intakes"
        except Exception as ex: print("intake symbology by hand:", ex)
    # --- vertical exaggeration through the CIM (ground surface)
    try:
        cim = scene.getDefinition("V3")
        for s in cim.elevationSurfaces: s.verticalExaggeration = vertical_exaggeration
        scene.setDefinition(cim); print(f"vertical exaggeration set to {vertical_exaggeration}x")
    except Exception as ex: print("set vertical exaggeration by hand (Scene Properties > Elevation Surface > Ground):", ex)
    # --- camera: oblique from the south-east, looking north-west up the piedmont
    try:
        ext = arcpy.Describe(PARCELS).extent
        cam = scene.defaultCamera; cam.setExtent(ext); cam.heading = 325; cam.pitch = -32; cam.roll = 0; scene.defaultCamera = cam
    except Exception as ex: print("camera by hand:", ex)
    print("\nScene 'Fig1_3D' created. Do these two things by hand, once:")
    print("  1. Contents pane > expand 'Elevation Surfaces' > right-click 'Ground' > Add Elevation Source > pick the DEM layer",
          "\n     (or drag the DEM layer onto 'Ground'), then uncheck the DEM as a drawn layer.")
    print("  2. Scene tab > Illumination: sun altitude ~35°, azimuth ~315°, shadows ON; Display: 'Draw parcels on ground' (default).")
    return scene

def fig1_build_layout(dpi=600):
    scene = aprx.listMaps("Fig1_3D")[0]
    plan = (aprx.listMaps("Map") or aprx.listMaps("*"))[0]
    for l in aprx.listLayouts("Fig1_studyarea"): aprx.deleteItem(l)
    lyt = aprx.createLayout(18, 20, "CENTIMETER", "Fig1_studyarea")
    def frame(x, y, w, h, m, name):
        pts = arcpy.Array([arcpy.Point(x, y), arcpy.Point(x, y + h), arcpy.Point(x + w, y + h), arcpy.Point(x + w, y), arcpy.Point(x, y)])
        return lyt.createMapFrame(arcpy.Polygon(pts), m, name)
    try:
        mf3d = frame(0.5, 7.5, 17, 12, scene, "3D")            # a: perspective, top
        mfpl = frame(0.5, 0.5, 10.5, 6.6, plan, "plan")           # b: plan view, bottom left
        loc1 = frame(11.5, 3.9, 6, 3.2, aprx.listMaps("China_Locator")[0], "china")  if aprx.listMaps("China_Locator") else None
        loc2 = frame(11.5, 0.5, 6, 3.2, aprx.listMaps("Xinjiang locator")[0], "xinjiang") if aprx.listMaps("Xinjiang locator") else None
        for f, tag in ((mf3d, "a"), (mfpl, "b"), (loc1, "c"), (loc2, "d")):
            if f is None: continue
            t = lyt.createTextElement(f, arcpy.Point(f.elementPositionX + 0.25, f.elementPositionY + f.elementHeight - 0.25), "POINT", tag, 11, "Arial", "Bold") if hasattr(lyt, "createTextElement") else None
        mf3d.camera = scene.defaultCamera
        out = os.path.join(OUTF, "fig1_study_area_3D")
        lyt.exportToPNG(out + ".png", resolution=dpi); lyt.exportToPDF(out + ".pdf", resolution=dpi)
        print("exported:", out + ".png / .pdf at", dpi, "dpi")
    except Exception as ex:
        print("Layout API not available in this Pro version:", ex)
        print("Do it by hand: Insert > New Layout (A4 portrait) > Insert > Map Frame: 'Fig1_3D' (top, 17 x 12 cm), 'Map' (bottom-left, 10.5 x 6.6 cm),",
              "'China_Locator' and 'Xinjiang locator' (bottom-right, 6 x 3.2 cm each); add panel letters a–d; Share > Export Layout > PNG, 600 dpi, to", OUTF)
