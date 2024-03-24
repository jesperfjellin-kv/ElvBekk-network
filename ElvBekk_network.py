#!C:\Users\jespe\anaconda3\envs\gis-env\python.exe

import geopandas as gpd
import rasterio
from shapely.geometry import Point, LineString, box
from rasterio.transform import from_origin

# List of DEM raster paths
dem_raster_paths = [
    r'C:\Python\GDAL\Reproj-TIF\32_1.tif',
    r'C:\Python\GDAL\Reproj-TIF\32_2.tif',
    r'C:\Python\GDAL\Reproj-TIF\32_3.tif',
    r'C:\Python\GDAL\Reproj-TIF\32_4.tif'
]

# Load the Elvbekk GML file
elvbekk_gml_path = r'C:\Python\Elvbekk_network\FKB-vann.gml'
elvbekk_gdf = gpd.read_file(elvbekk_gml_path)
if 'geometri' in elvbekk_gdf.columns:
    elvbekk_gdf.set_geometry('geometry = senterlinje', inplace=True)

# Function to get elevation from the relevant DEM at a point
def get_elevation(dem_list, point):
    for dem_path in dem_list:
        with rasterio.open(dem_path) as src:
            # Convert geographical coordinates to dataset's pixel coordinates
            x, y = point.x, point.y
            row, col = src.index(x, y)
            
            # Read the dataset's value at the calculated pixel coordinates
            # Ensure the point is within the raster bounds
            if (0 <= col < src.width) and (0 <= row < src.height):
                value = src.read(1)[row, col]  # Assuming elevation data is in band 1
                return value
    return None  # Point is not within any DEM bounds

# Create a list to store endpoints and their elevation
endpoints = []

# Iterate through each Elvbekk feature to get the start and end points
for idx, elvbekk in elvbekk_gdf.iterrows():
    start_point = Point(elvbekk.geometry.coords[0])
    end_point = Point(elvbekk.geometry.coords[-1])
    for point in [start_point, end_point]:
        elevation = get_elevation(dem_raster_paths, point)
        endpoints.append({'geometry': point, 'elevation': elevation})

# Convert list of endpoints to GeoDataFrame
endpoints_gdf = gpd.GeoDataFrame(endpoints, crs=elvbekk_gdf.crs)

# Sort endpoints by elevation in descending order (highest first)
endpoints_gdf.sort_values(by='elevation', ascending=False, inplace=True)

# Parameters for connection logic
distance_threshold = 50  # Maximum distance to search for a connecting endpoint
elevation_threshold = 1  # Minimum difference in elevation to consider a connection

# Function to connect endpoints
def connect_endpoints(endpoints_df, dist_thresh, elev_thresh):
    connected = []
    for idx, endpoint in endpoints_df.iterrows():
        potential_matches = endpoints_df[
            (endpoints_df['elevation'] < endpoint['elevation'] - elev_thresh) &  # Lower elevation
            (endpoint['geometry'].distance(endpoints_df['geometry']) < dist_thresh)  # Within distance threshold
        ]
        
        if not potential_matches.empty:
            # Sort by elevation difference and distance, then take the closest
            best_match = potential_matches.assign(
                elev_diff=lambda df: endpoint['elevation'] - df['elevation'],
                dist=lambda df: endpoint['geometry'].distance(df['geometry'])
            ).sort_values(by=['elev_diff', 'dist']).iloc[0]

            # Create new LineString geometry that connects the two endpoints
            new_connection = LineString([endpoint['geometry'], best_match['geometry']])
            connected.append({'geometry': new_connection})

    # Return new GeoDataFrame with connections
    return gpd.GeoDataFrame(connected, crs=endpoints_df.crs)

# Use the function to connect endpoints
connections_gdf = connect_endpoints(endpoints_gdf, distance_threshold, elevation_threshold)

# Append new connections to the original Elvbekk GeoDataFrame
elvbekk_gdf = elvbekk_gdf.append(connections_gdf, ignore_index=True)

# Save the updated Elvbekk features with connections as a new GML file
output_gml_path = r'C:\Python\Elvbekk_network\Updated_FKB-vann.gml'
elvbekk_gdf.to_file(output_gml_path, driver="GML")
