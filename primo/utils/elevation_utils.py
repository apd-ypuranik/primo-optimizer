#################################################################################
# PRIMO - The P&A Project Optimizer was produced under the Methane Emissions
# Reduction Program (MERP) and National Energy Technology Laboratory's (NETL)
# National Emissions Reduction Initiative (NEMRI).
#
# NOTICE. This Software was developed under funding from the U.S. Government
# and the U.S. Government consequently retains certain rights. As such, the
# U.S. Government has been granted for itself and others acting on its behalf
# a paid-up, nonexclusive, irrevocable, worldwide license in the Software to
# reproduce, distribute copies to the public, prepare derivative works, and
# perform publicly and display publicly, and to permit others to do so.
#################################################################################

# Standard libs
import logging
import os
from typing import Tuple

# Installed libs
import numpy as np
import pandas as pd
import rasterio
import requests
from dotenv import load_dotenv
from pyproj import Proj, transform

# User-defined libs
from primo.utils import Start_coordinates
from primo.utils.geo_utils import get_distance
from primo.utils.raise_exception import raise_exception

LOGGER = logging.getLogger(__name__)


def get_bing_maps_api_key() -> str:
    """
    Retrieve the Bing Maps API key from the environment file stored under .env.

    Returns
    -------
    str
        The Bing Maps API key

    Raises
    ------
    KeyError if BING_API_KEY is not found in .env file
    """
    load_dotenv()
    return os.environ["BING_API_KEY"]


def get_route(
    api_key: str, start_coord: Tuple[float, float], end_coord: Tuple[float, float]
) -> dict:
    """
    Get the route between two coordinates using the Bing Maps API.

    Parameters
    ----------
    api_key : str
        The Bing Maps API key
    start_coord : Tuple[float, float]
        The coordinates of the starting point
    end_coord : Tuple[float, float]
        The coordinates of the ending point

    Returns
    -------
    Optional[Dict]
        Detailed route information if available; otherwise None
    """
    base_url = "http://dev.virtualearth.net/REST/V1/Routes/Driving"

    params = {
        "wayPoint.1": f"{start_coord[0]},{start_coord[1]}",
        "wayPoint.2": f"{end_coord[0]},{end_coord[1]}",
        "key": api_key,
        "routeAttributes": "routePath",
    }

    response = requests.get(base_url, params=params, timeout=60)
    data = response.json()

    if response.status_code == 200 and data.get("resourceSets"):
        route = data["resourceSets"][0]["resources"][0]
        return route
    LOGGER.warning("get_route method returned a non-OK response code")
    LOGGER.warning(f"Error: {response.status_code}, {data.get('errorDetails')}")
    return {}


def get_nearest_road_point(lat: float, long: float) -> Tuple[float, float]:
    """
    Get the nearest road point to a given latitude and longitude using the Bing Maps API.

    Parameters
    ----------
    lat : float
        Latitude of the point
    long : float
        Longitude of the point

    Returns
    -------
    Tuple[float, float]
        The latitude and longitude of the nearest road point
    """

    bing_maps_api_key = get_bing_maps_api_key()

    # Example coordinates (latitude, longitude)

    start_coordinates = Start_coordinates
    end_coordinates = (lat, long)  # well

    # Get detailed route information
    route = get_route(bing_maps_api_key, start_coordinates, end_coordinates)

    if route is None:
        raise ValueError(
            "Route information is not available for all given input. "
            "Please see error message above for the specific point with issue."
        )

    # Extract route details
    route_path = route["routePath"]["line"]["coordinates"]

    # Extract the last waypoint coordinates
    last_waypoint = route_path[-1]

    return tuple(last_waypoint)


def accessibility(lat: float, long: float) -> float:
    """
    Calculate the accessibility quotient for a given latitude and longitude.

    Parameters
    ----------
    lat : float
        Latitude of the location
    long : float
        Longitude of the location

    Returns
    -------
    float
        The accessibility quotient
    """

    closest_road_point = get_nearest_road_point(lat, long)
    accessibility_quotient = get_distance(
        (closest_road_point[0], closest_road_point[1]),
        (lat, long),
        "haversine",
        "MILES",
    )

    return accessibility_quotient


def get_elevation(lat: float, long: float, tif_file_path: str) -> float:
    """
    Get the elevation at a given latitude and longitude using a specified GeoTIFF file.

    Parameters
    ----------
    lat : float
        Latitude of the location
    long : float
        Longitude of the location
    tif_file_path : str
        The path to the GeoTIFF file containing elevation data

    Returns
    -------
    Optional[float]
        The elevation at the specified location if available; otherwise None
    """
    try:
        # Define the source and destination coordinate systems
        src_crs = Proj(init="epsg:4326")  # WGS84
        dst_crs = Proj(init="epsg:5070")  # EPSG:5070

        # Transform latitude and longitude to the projected CRS
        long_transform, lat_transform = transform(src_crs, dst_crs, long, lat)

        with rasterio.open(tif_file_path) as src:
            # Transform latitude and longitude to pixel coordinates
            row, col = map(int, src.index(long_transform, lat_transform))

            # Read elevation data at the specified location
            elevation = src.read(1, window=((row, row + 1), (col, col + 1)))
            # Check if the value is NoData
            if elevation[0][0] != src.nodatavals[0]:
                raise_exception(
                    "No elevation available for these coordinates - "
                    f"Latitude:{lat}, Longitude:{long}",
                    ValueError,
                )

            return elevation[0][0]  # Return the elevation value

    except IndexError:
        msg = (
            "Empty array after reading elevation data from source file. "
            "Latitude and longitude values are not within bounds of the region of "
            "the raster file given."
        )
        LOGGER.warning(msg)
        raise_exception(
            f"No elevation available for these coordinates - Latitude:{lat}, Longitude:{long}",
            ValueError,
        )


def get_elevation_delta(df: pd.DataFrame, tif_file_path: str) -> pd.DataFrame:
    """
    Calculate the elevation delta for each location in the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing latitude and longitude coordinates
    tif_file_path : str
        The path to the GeoTIFF file containing elevation data

    Returns
    -------
    pd.DataFrame
        The DataFrame with an added column 'elevation_delta' indicating the elevation delta
        for each location
    """
    deltas = []
    for _, row in df.iterrows():
        closest_road_point_lat, closest_road_point_long = get_nearest_road_point(
            row["Latitude"], row["Longitude"]
        )
        elevation = get_elevation(row["Latitude"], row["Longitude"], tif_file_path)
        closest_road_elevation = get_elevation(
            closest_road_point_lat, closest_road_point_long, tif_file_path
        )
        if elevation is None or closest_road_elevation is None:
            delta = np.nan
        else:
            delta = elevation - closest_road_elevation
        deltas.append(delta)

    df["Elevation Delta [m]"] = deltas
    return df
