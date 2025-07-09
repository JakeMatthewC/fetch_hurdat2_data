import requests
from datetime import datetime
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values, Json
from sqlalchemy import create_engine

# modules
import helpers.utils as u
import helpers.storm_buoy_match as sbm

engine = create_engine("postgresql+psycopg2://Jacob:@localhost:5432/postgres")

# path to the hurdat2 file
hurdat2_path = r'https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2024-040425.txt'

response = requests.get(hurdat2_path)
hurdat2_text = response.text

# split the lines of the text file
lines = hurdat2_text.splitlines()

storm_rows = []
track_rows = []

# if statement to record from header and timestamp rows
for i, line in enumerate(lines):
    if line.startswith(('AL', 'EP')):
        parts = [p.strip() for p in line.split(',')]
        hurdat_storm_id = parts[0]
        storm_name = parts[1]
        track_count = int(parts[2])
        basin = hurdat_storm_id[:2]
        storm_number = int(hurdat_storm_id[2:4])
        season_year = int(hurdat_storm_id[4:])

        storm_rows.append({
            'hurdat_storm_id': hurdat_storm_id,
            'storm_name': storm_name,
            'basin': basin,
            'season_year': season_year,
            'storm_number': storm_number,
            'track_count': track_count,
            'track_start_index': len(track_rows)})
    else:
        fields = [f.strip() for f in line.split(',')]
        date_str, time_str = fields[0], fields[1]
        timestamp = datetime.strptime(date_str + time_str, '%Y%m%d%H%M')
        lat_str, lon_str = fields[4], fields[5]
        lat = float(lat_str[:-1]) * (1 if lat_str[-1] == 'N' else -1)
        lon = float(lon_str[:-1]) * (-1 if lon_str[-1] == 'W' else 1)
        wind_speed = int(fields[6])
        pressure = int(fields[7]) if fields[7].isdigit() and int(fields[7]) != -999 else None
        storm_type = fields[3]

        radii_34kt = {
            'ne': u.parse_radius(fields[8]),
            'se': u.parse_radius(fields[9]),
            'sw': u.parse_radius(fields[10]),
            'nw': u.parse_radius(fields[11]),
        }
        rad_max_wind = u.parse_radius(fields[20])

        track_rows.append({
            'hurdat_storm_id': hurdat_storm_id,
            'timestamp': timestamp,
            'lat': lat,
            'lon': lon,
            'wind_speed': wind_speed,
            'pressure': pressure,
            'storm_type': storm_type,
            'radii_34kt': radii_34kt,
            'rad_max_wind': rad_max_wind
        })

# get the start time and end time for each storm
for storm in storm_rows:
    start_idx = storm['track_start_index']
    end_idx = start_idx + storm['track_count']
    times = [track_rows[i]['timestamp'] for i in range(start_idx, end_idx)]
    storm['start_time'] = min(times)
    storm['end_time'] = max(times)

# calculate heading and speed for timesteps where available
prev_points = {}

for t in track_rows:
    sid = t['hurdat_storm_id']
    if sid in prev_points:
        prev = prev_points[sid]
        delta_hours = (t['timestamp'] - prev['timestamp']).total_seconds() / 3600.0
        if delta_hours > 0:
            dist_km = u.haversine_km(prev['lat'], prev['lon'], t['lat'], t['lon'])
            heading = u.calculate_heading(prev['lat'], prev['lon'], t['lat'], t['lon'])
            speed_kts = u.calculate_speed_kts(dist_km, delta_hours)
            t['heading'] = heading
            t['speed'] = speed_kts
        else:
            t['heading'] = None
            t['speed'] = None
    else:
        t['heading'] = None
        t['speed'] = None
    prev_points[sid] = t  # update last point

conn = psycopg2.connect(
    dbname="postgres",
    user="Jacob",
    password="",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

# organize storm parameters for storms db
storm_values = [
    (
        s['hurdat_storm_id'],
        s['storm_name'],
        s['basin'],
        s['season_year'],
        s['storm_number'],
        s['start_time'],
        s['end_time'],
    )
    for s in storm_rows
]
# store storm parameters
execute_values(cur, """
    INSERT INTO storms.storms
    (hurdat_storm_id, storm_name, basin, season_year, storm_number, start_time, end_time)
    VALUES %s
    ON CONFLICT (hurdat_storm_id) DO NOTHING;
""", storm_values)

conn.commit()

cur.execute("SELECT id, hurdat_storm_id FROM storms.storms")
id_map = {row[1]: row[0] for row in cur.fetchall()}

# organize storm track data for tracks db
track_values = [
    (
        t['hurdat_storm_id'],
        t['timestamp'],
        t['lat'],
        t['lon'],
        t['wind_speed'],
        t['pressure'],
        t['storm_type'],
        #Json(t['radii_34kt']),
        t['rad_max_wind'],
        t['heading'],
        t['speed']
    )
    for t in track_rows if t['hurdat_storm_id'] in id_map
]

# convert track_values to dataframe
df_track_values = pd.DataFrame(track_values,columns=['hurdat_storm_id','timestamp', 'lat', 'lon', 'wind_speed', 'pressure', 'storm_type',
                                                     'rad_max_wind', 'heading', 'speed'])
# remove the unused columns for now
df_track_values.drop(columns=['rad_max_wind'], inplace=True)

# roughly interpolate to 30 minute timesteps
df_interp_track_values = u.interpolate_storm_timesteps(df_track_values)

# store interpolated track data
df_interp_track_values.to_sql("storm_tracks", engine, schema="storms", index=False, if_exists="append")

'''# store track data
execute_values(cur, """
    INSERT INTO storms.storm_tracks
    (hurdat_storm_id, timestamp, lat, lon, wind_speed, pressure, storm_type, heading, speed)
    VALUES %s;
""", track_values)'''

conn.commit()

# flag buoy timesteps is_storm=True where needed, update storm_matches table
sbm.storm_buoy_match(cur, df_interp_track_values, None)

conn.commit()
cur.close()
conn.close()