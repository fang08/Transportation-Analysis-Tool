import arcpy
import sys
from arcpy.sa import *

# ---- Spatial Analyst Extension check -----
if arcpy.CheckExtension("Spatial") != "Available":
   exit()
else:
   arcpy.CheckOutExtension("Spatial")

# ---- Set input feature classes -----
in_path = arcpy.GetParameterAsText(0)
roads = arcpy.GetParameterAsText(1)
buffer_dist = arcpy.GetParameterAsText(2)
blockgroups = arcpy.GetParameterAsText(3)
boundrary = arcpy.GetParameterAsText(4)
crashes = arcpy.GetParameterAsText(5)
hospitals = arcpy.GetParameterAsText(6)
schools = arcpy.GetParameterAsText(7)
landuse = arcpy.GetParameterAsText(8)
# ---- Set query expressions for raster landuse -----
expression = arcpy.GetParameterAsText(9)
expression2 = arcpy.GetParameterAsText(10)
# ---- Set reclassify weights -----
txtHospWeight = arcpy.GetParameterAsText(11)
numHospWeight = float(txtHospWeight)
txtSchoolWeight = arcpy.GetParameterAsText(12)
numSchoolWeight = float(txtSchoolWeight)
txtResidentialWeight = arcpy.GetParameterAsText(13)
numResidentialWeight = float(txtResidentialWeight)
txtCommericialWeight = arcpy.GetParameterAsText(14)
numCommericialWeight = float(txtCommericialWeight)
numTotalWeight = numHospWeight + numSchoolWeight + numResidentialWeight + numCommericialWeight
if numHospWeight< 0 or numSchoolWeight< 0 or numResidentialWeight< 0 or numCommericialWeight< 0:
    arcpy.AddMessage("The individual weight should be a number between 0 and 1.")
    exit()
if numTotalWeight != 1:
    arcpy.AddMessage("The total weights should be 1. Please enter again.")
    exit()
# ---- Set extent, mask and cell size -----
arcpy.env.extent = arcpy.GetParameterAsText(15)
arcpy.env.mask = arcpy.GetParameterAsText(16)
cellSize = arcpy.GetParameterAsText(17)
if int(cellSize) <= 0:
    arcpy.AddMessage("Please enter a positive integer for cell size.")
    exit()
else:
    arcpy.env.cellSize = cellSize
# ---- Set output path and name -----
out_path = arcpy.GetParameterAsText(18)
final_results = arcpy.GetParameterAsText(19)
# ---- Set overwrite output -----
chkOverwrite = arcpy.GetParameterAsText(20)
if chkOverwrite.lower() == "true":
    arcpy.env.overwriteOutput = True
else:
    arcpy.env.overwriteOutput = False

# ---- Set environment -----
arcpy.env.workspace =in_path


# ## ---- Block 1: Calculating crash rates and categories ----- ##

# ---- Set all the intermediate variables in vector part -----
lyr_blockgroups = "blockgroups_lyr"
se_blockgroups = "Select_blockgroups"
intersect_infc = [se_blockgroups, roads]
roads_intersect = "Roads_Intersect"
roads_calculate = "Roads_Calculate"
statistics_fd = [["LENGTH", "SUM"]]
out_buffer = "Buffer_roads"
out_clip = "Clip_crashes"
out_spatialjoin = "Crashes_Join"
add_fdnm = "Crash_Rates"
queryexpression = "[Join_Count] / [SUM_LENGTH]"
add_fdnm2 = "Crash_Category"
udFields = [add_fdnm, add_fdnm2]
category_results = "Category_results"
fieldList = [add_fdnm, add_fdnm2]
high_crashrates = "High_crashrates"
queryexpression2 = "\"Crash_Category\" = 'High'"

# ---- Set all the variables in raster part -----
select_residential = "Select_residential"
select_commercial = "Select_Commercial"
reclassall = "Reclass_All"
out_polygon = "Polygon_result"

# ---- Set all the variables in third part -----
intersect_infc2 = [high_crashrates, out_polygon]
overlap = "Overlap"
add_fdnm3 = "Proportion"
queryexpression3 = "[Shape_Area_12] / [Shape_Area]"
queryexpression4 = "\"Proportion\" >= 0.5"

try:
    # ---- Select Layer By Location and save it -----
    arcpy.MakeFeatureLayer_management(blockgroups, lyr_blockgroups)
    arcpy.SelectLayerByLocation_management(lyr_blockgroups, "HAVE_THEIR_CENTER_IN", boundrary, "", "NEW_SELECTION")
    matchcount = int(arcpy.GetCount_management(lyr_blockgroups)[0])
    if matchcount == 0:
        exit()
    else:
        arcpy.CopyFeatures_management(lyr_blockgroups, se_blockgroups)

    # ---- Intersect roads and selected blockgroups -----
    arcpy.Intersect_analysis(intersect_infc, roads_intersect, "ALL", "", "INPUT")

    # ---- Add Geometry Attributes to convert roads to miles -----
    arcpy.AddGeometryAttributes_management(roads_intersect, "LENGTH", "MILES_US")

    # ---- Summary Statistics calculate sum of roads in each selected blockgroup -----
    arcpy.Statistics_analysis(roads_intersect, roads_calculate, statistics_fd, "GEOID10")

    # ---- Buffer major roads -----
    arcpy.Buffer_analysis(roads, out_buffer, buffer_dist, "FULL", "ROUND", "ALL", "", "PLANAR")

    # ---- Clip the crashes points -----
    arcpy.Clip_analysis(crashes, out_buffer, out_clip)

    # ---- Spatial Join blockgroups and clip crashes -----
    arcpy.SpatialJoin_analysis(se_blockgroups, out_clip, out_spatialjoin, "JOIN_ONE_TO_ONE", "KEEP_ALL", "#", "INTERSECT")

    # ---- Join Field put each blockgroup's road length and crashes together -----
    arcpy.JoinField_management(roads_calculate, "GEOID10", out_spatialjoin, "GEOID10", "Join_Count")

    # ---- Add Field to calculate crash rates -----
    arcpy.AddField_management(roads_calculate, add_fdnm, "FLOAT", "", "", "", "", "NULLABLE")

    # ---- Calculate Field calculate crash rates -----
    arcpy.CalculateField_management(roads_calculate, add_fdnm, queryexpression, "VB")

    # ---- Add Field to calculate crash category -----
    arcpy.AddField_management(roads_calculate, add_fdnm2, "TEXT", "", "", "", "", "NULLABLE")

    # ---- calculate max, min, mean use SearchCursor ----
    num_sum = 0
    num_counter = 0
    minimum = 0
    maximum = 0
    with arcpy.da.SearchCursor(roads_calculate,[add_fdnm]) as cursor:
        for row in cursor:
            num_sum = num_sum + row[0]
            num_counter = num_counter + 1
            if row[0]> maximum:
                maximum = row[0]
            if row[0]< minimum:
                minimum = row[0]

    num_mean = num_sum / num_counter
    value_low = (minimum + num_mean)/2
    value_high = (maximum + num_mean)/2

    # ---- calculate crash category use UpdateCursor ----
    with arcpy.da.UpdateCursor(roads_calculate, udFields) as cursor:
        for row in cursor:
            if row[0] <= value_low:
                row[1] = "Low"
            elif (row[0] > value_low and row[0] <= value_high):
                row[1] = "Medium"
            elif row[0] > value_high:
                row[1] = "High"
            cursor.updateRow(row)
    arcpy.Copy_management(roads_calculate, category_results)
    # ---- this is the end of customized tool -----

    # ---- Join Field put crash rates and categories into blockgroups table -----
    arcpy.JoinField_management(se_blockgroups, "GEOID10", category_results, "GEOID10", fieldList)

    # ---- Feature Class to Feature Class -----
    arcpy.FeatureClassToFeatureClass_conversion(se_blockgroups, in_path, high_crashrates, queryexpression2)

    # ## ---- this is the end of calculating crash rates and categories ----- ##


    # ## ---- Block 2: Calculating suitability ----- ##

    # ---- Feature Class to Feature Class -----
    arcpy.FeatureClassToFeatureClass_conversion(landuse, in_path, select_residential, expression)
    arcpy.FeatureClassToFeatureClass_conversion(landuse, in_path, select_commercial, expression2)

    # ---- Euclidean Distance -----
    schools_raster = EucDistance(schools)
    hospital_raster = EucDistance(hospitals)
    residential_raster = EucDistance(select_residential)
    commercial_raster = EucDistance(select_commercial)

    # ---- Reclassify -----
    reclass_school = Slice(schools_raster,9,"NATURAL_BREAKS",1)
    reclass_residential = Slice(residential_raster,9,"NATURAL_BREAKS",1)
    reclass_commercial = Slice(commercial_raster,9,"NATURAL_BREAKS",1)
    reclass_hospital = Slice(hospital_raster,9,"NATURAL_BREAKS",1)
    remapString = "1 9;2 8;3 7;4 6;5 5;6 4;7 3;8 2;9 1"
    reclass_hospital = Reclassify(reclass_hospital, "VALUE", remapString)

    # ---- Raster Calculator create final suitability-----
    rasSuitability = reclass_school * numSchoolWeight + reclass_hospital * numHospWeight + reclass_residential * numResidentialWeight + reclass_commercial * numCommericialWeight
    int_rasSuitability = Int(rasSuitability)
    int_rasSuitability.save(reclassall)

    # ---- Extract by Attributes -----
    extract_Int = ExtractByAttributes("Reclass_All", "VALUE = 1")

    # ---- Raster to Polygon -----
    arcpy.RasterToPolygon_conversion(extract_Int, out_polygon, "SIMPLIFY", "VALUE")

   # ## ---- this is the end of calculating suitability ----- ##


    # ## ---- Block 3: Calculating final results ----- ##

    # ---- Intersect crash rates and suitability polygon -----
    arcpy.Intersect_analysis(intersect_infc2, overlap, "ALL", "", "INPUT")

    # ---- Join Field -----
    arcpy.JoinField_management(high_crashrates, "GEOID10", overlap, "GEOID10", ["Crash_Rates", "SHAPE_Area"])

    # ---- Add Field -----
    arcpy.AddField_management(high_crashrates, add_fdnm3, "FLOAT", "", "", "", "", "NULLABLE")

    # ---- Calculate Field -----
    arcpy.CalculateField_management(high_crashrates, add_fdnm3, queryexpression3, "VB")

    # ---- Feature Class to Feature Class -----
    arcpy.FeatureClassToFeatureClass_conversion(high_crashrates, out_path, final_results, queryexpression4)

    # ## ---- this is the end of calculating final results ----- ##

except Exception:
    e = sys.exc_info()[1]
    arcpy.AddMessage(e.args[0])