import pyproj
from datetime import datetime, timedelta
from sgp4.api import Satrec, jday
from sgp4.propagation import true
import time
import ray

# Load TLE data from the file
with open("30sats.txt", "r") as file:
    tle_lines = file.read().splitlines()

# input coordinates for latitude and longitude regions
region = []
for i in range(4):
    lat = float(input(f"Enter Latitude for Point {i + 1}: "))
    lon = float(input(f"Enter Longitude for Point {i + 1}: "))
    region.append((lat, lon))

# Initialize Ray with memory settings (1 GB)
ray.init(_memory=1073741824, object_store_memory=1073741824)


# Define a function to calculate latitude, longitude, and altitude
def ecef2lla(pos_x, pos_y, pos_z):
    ecef = pyproj.CRS(proj="geocent", ellps="WGS84", datum="WGS84")
    lla = pyproj.CRS(proj="latlong", ellps="WGS84", datum="WGS84")
    transformer = pyproj.Transformer.from_crs(ecef, lla, always_xy=true)
    lon, lat, alt = transformer.transform(pos_x, pos_y, pos_z)
    return lon, lat, alt


# Define a function to check if a position is within a region
def is_within_region(lon, lat, region):
    lons = sorted([point[0] for point in region])
    lats = sorted([point[1] for point in region])
    return lons[0] <= lon <= lons[3] and lats[0] <= lat <= lats[3]


# Function to generate state vectors for a satellite
@ray.remote
def generate_state_vectors(tle):
    # Split the TLE data into two lines
    tle_line1, tle_line2 = tle[0], tle[1]

    # Create a satellite object
    satellite = Satrec.twoline2rv(tle_line1, tle_line2)

    # Initialize a list to store filtered results
    filtered_results = []

    # Iterate for five days with a one-second interval
    for j in range(5 * 24 * 3600):
        # Calculate the timestamp
        timestamp = datetime(2023, 11, 1, 0, 0, 0) + timedelta(seconds=j)
        jd, fr = jday(timestamp.year, timestamp.month, timestamp.day, timestamp.hour, timestamp.minute,
                      timestamp.second)

        # Compute the satellite's position and velocity
        error, position, velocity = satellite.sgp4(jd, fr)
        lon, lat, alt = ecef2lla(position[0], position[1], position[2])

        # Check if the position is within the specified region
        if is_within_region(lon, lat, region):
            filtered_results.append((timestamp, (lon, lat, alt)))

    return filtered_results


# Function to save data to a file
def save_to_file(text, spec):
    with open(text, mode='w', encoding='utf-8') as file:
        for item in spec:
            file.write(f"\n{item}")


# Main program
if __name__ == "__main":
    # Start timing the execution
    start_time = time.time()

    # Use Ray to process the TLE data in parallel
    results = ray.get([generate_state_vectors.remote(tle_lines[i:i + 2]) for i in range(0, len(tle_lines), 2)])

    # Combine and flatten the results
    filtered_results = [item for sublist in results for item in sublist]

    # Calculate the duration of execution
    duration = time.time() - start_time
    print(f"Execution time: {duration} seconds")

    # Shutdown Ray
    ray.shutdown()

    # Save the filtered results to a file
    save_to_file('filteredresults.txt', filtered_results)
