# Libraries
import requests
from datetime import datetime, timezone, timedelta
import pandas as pd
from skyfield.api import load, wgs84, EarthSatellite, Topos
import matplotlib.pyplot as plt
import json
from matplotlib.animation import FuncAnimation
import matplotlib.dates as mdates
import matplotlib.patches as patches
import math

# CONSTS
SATELLITE_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"
TLE_FILE_NAME = "satellite_tles.txt"

# My location to compate to satellite
lat, lon, elev_m = 32.85548069219173, -117.20414146258183, 111

# Option 1: numeric (positive lat = North, negative lon = West)
observer = Topos(latitude_degrees=lat, longitude_degrees=lon, elevation_m=elev_m)


# API call to get tle data for satellites
satellite_tles = requests.get(SATELLITE_URL)

# Declaring global file_data
file_data = None

# Putting satellite tle data in file
if satellite_tles.status_code == 200:
    file_data = satellite_tles.text
    with open(TLE_FILE_NAME, "w") as f:
        f.write(file_data)
else:
    print(f"Error: {satellite_tles.status_code}")


# Creating global variables for lines and data and time
lines = []
data = []
times = []

# function to extract all data from the first tle line
def parse_tle1(tle):
    line_number = tle[0]                  # col 1
    satellite_number = tle[2:7]           # cols 3–7
    classification = tle[7]               # col 8
    international_designator = tle[9:17]  # cols 10–17
    epoch_year = tle[18:20]               # cols 19–20
    epoch_day = tle[20:32]                # cols 21–32
    first_derivative = tle[33:43]         # cols 34–43
    second_derivative = tle[44:52]        # cols 45–52
    bstar_drag = tle[53:61]               # cols 54–61
    ephemeris_type = tle[62]              # col 63
    element_set_number = tle[64:68]       # cols 65–68
    checksum = tle[68]                    # col 69

    return line_number, satellite_number, classification, international_designator, epoch_year, epoch_day, first_derivative, second_derivative, bstar_drag, ephemeris_type, element_set_number, checksum

#function to extract all data from the second tle line
def parse_tle2(tle):
    line_number = tle[0]             # col 1
    satellite_number = tle[2:7]      # cols 3–7
    inclination = tle[8:16]          # cols 9–16
    raan = tle[17:25]                # cols 18–25
    eccentricity = tle[26:33]        # cols 27–33 (decimal assumed)
    arg_perigee = tle[34:42]         # cols 35–42
    mean_anomaly = tle[43:51]        # cols 44–51
    mean_motion = tle[52:63]         # cols 53–63
    rev_number = tle[63:68]          # cols 64–68
    checksum = tle[68]               # col 69

    return line_number, satellite_number, inclination, raan, eccentricity, arg_perigee, mean_anomaly, mean_motion, rev_number, checksum


# Clean data to be used
with open(TLE_FILE_NAME) as f:
    for line in f.readlines():
        lines.append(line.strip())

ts = load.timescale()

start_dt = datetime.now(timezone.utc)
dt_list = [start_dt + timedelta(minutes=m) for m in range(1440)]
times = ts.from_datetimes(dt_list)

# loop through all tle data and extract all information to be stored in data frame
# (keeping your original indexing; adding a guard so it doesn't crash if the file doesn't match)
for i in range(0, len(lines), 6):
    try:
        name = lines[i]
        tle_1 = lines[i + 2]
        tle_2 = lines[i + 4]

        # parse calls left as-is (even though you don't use most fields yet)
        parse_tle1(tle_1)
        parse_tle2(tle_2)

        data.append({
            "name": name,
            "tle_1": tle_1,
            "tle_2": tle_2,
        })
    except IndexError:
        break

observation_data = []
alts = []
satellite = EarthSatellite(data[0]["tle_1"], data[0]["tle_2"], data[0]["name"], ts)

previous_visible = False
max_alt = 0
pass_start_time = 0

passes = []
difference = satellite - observer

for t in times:
    topocentric = difference.at(t)
    alt, az, distance = topocentric.altaz()
    alts.append(alt.degrees)
    if alt.degrees > 10 and previous_visible:
        max_alt = max(max_alt, alt.degrees)
    if alt.degrees > 10 and previous_visible == False:
        max_alt = alt.degrees
        previous_visible = True
        pass_start_time = t.utc_datetime()
        pass_data = {
            "starttime": pass_start_time
        }
    if alt.degrees <= 10 and previous_visible == True:
        previous_visible = False
        duration_min = (t.utc_datetime() - pass_start_time).total_seconds() / 60
        pass_data["end_time"] = t.utc_datetime()
        pass_data["duration_min"] = duration_min
        pass_data["max_altitude_deg"] = float(max_alt)
        max_alt = 0
        passes.append(pass_data)
        pass_data = {}

print("tracking:", data[0]["name"])
print("alt range (deg):", min(alts), "->", max(alts))

passes_df = pd.DataFrame(passes)
print(passes_df)

time_list = [t.utc_datetime() for t in times]

# --- LIVE SKY DOME (ALL SATS, COLOR CHANGES WHEN VISIBLE) ---

ani = None  # keep animation alive

def create_figure():
    global ani

    fig, ax = plt.subplots()

    north = 1
    east = 1
    south = -1
    west = -1

    center = (0, 0)
    outer_horizon_radius = 1
    inner_altitude_ring1_radius = 0.667
    inner_altitude_ring2_radius = 0.333

    outer_horizon = patches.Circle(center, outer_horizon_radius, facecolor="none", edgecolor='white')
    inner_altitude_ring1 = patches.Circle(center, inner_altitude_ring1_radius, facecolor="none", edgecolor='white')
    inner_altitude_ring2 = patches.Circle(center, inner_altitude_ring2_radius, facecolor="none", edgecolor='white')

    ax.add_patch(outer_horizon)
    ax.add_patch(inner_altitude_ring1)
    ax.add_patch(inner_altitude_ring2)

    ax.set_xlim(west -.2, east +.2)
    ax.set_ylim(south -.2, north +.2)
    ax.plot([x for x in range(west, east + 1)], [y*0 for y in range(south, north + 1)], color="green")
    ax.plot([x*0 for x in range(west, east + 1)], [y for y in range(south, north + 1)], color="green")
    ax.text(0, north + 0.05, "N", color="white")
    ax.text(east + 0.05, 0, "E", color="white")
    ax.text(0, south - 0.1, "S", color="white")
    ax.text(west -0.1, 0, "W", color="white")

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_facecolor("black")
    ax.set_aspect('equal')
    ax.set_title('Matplotlib Circle Patch', color="white")

    # Build all satellite objects once
    satellites = [EarthSatellite(d["tle_1"], d["tle_2"], d["name"], ts) for d in data]

    # One scatter artist for all satellites
    dots = ax.scatter([0]*len(satellites), [0]*len(satellites), s=18)

    # Status HUD (so you can tell it's updating even if nothing is visible)
    status = ax.text(0, 0, "", color="white", ha="center", va="center")

    def update(frame):
        t_now = ts.now()
        offsets = []
        colors = []
        visible = 0

        for sat in satellites:
            topocentric = (sat - observer).at(t_now)
            alt, az, distance = topocentric.altaz()

            # Always plot position on dome
            r = (90 - alt.degrees) / 90
            theta = math.radians(az.degrees)
            x = r * math.sin(theta)
            y = r * math.cos(theta)

            offsets.append([x, y])

            # Color changes when visible
            if alt.degrees >= 0:
                colors.append("yellow")   # visible
                visible += 1
            else:
                colors.append("gray")     # below horizon

        dots.set_offsets(offsets)
        dots.set_color(colors)
        status.set_text(f"UTC {t_now.utc_datetime().strftime('%H:%M:%S')} | visible: {visible}")

        return dots, status

    ani = FuncAnimation(fig, update, interval=200, blit=False)
    plt.show()

create_figure()