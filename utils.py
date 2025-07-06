from math import radians, sin, cos, sqrt, atan2, degrees
from datetime import timedelta
import pandas as pd
import psycopg2

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))   

def calculate_heading(lat1, lon1, lat2, lon2):
    dlon = radians(lon2 - lon1)
    lat1 = radians(lat1)
    lat2 = radians(lat2)
    x = sin(dlon) * cos(lat2)
    y = cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dlon)
    bearing = atan2(x, y)
    return (degrees(bearing) + 360) % 360 

def calculate_speed_kts(distance_km, delta_hours):
    return (distance_km / delta_hours) * 0.539957  # 1 km/hr = 0.539957 knots

def interpolate_storm_timesteps(df_track_values):
    interval_minutes = 30
    # get storm ids and so you can loop through each storm separately
    storm_ids = df_track_values['storm_id'].unique()

    conn = psycopg2.connect(
    dbname="postgres",
    user="Jacob",
    password="",
    host="localhost",
    port="5432"
    )

    exist_storms = []
    # search for storms that have already been uploaded and skip those
    for storm_id in storm_ids:
        check_storm = check_exist_storm(conn, storm_id)
        if check_storm:
            exist_storms.append(storm_id)
        else:  
            continue

    # remove the existing storms from the dataframe
    df_track_values = df_track_values[~df_track_values['storm_id'].isin(exist_storms)]

    interpolated_rows = []
    # loop through each separate storm
    for sid in storm_ids:
        storm = df_track_values.loc[df_track_values['storm_id'] == sid].sort_values("timestamp")
        # loop through the track and interpolate to 30 minutes
        for i in range(len(storm) - 1):
            row_start = storm.iloc[i]
            row_end = storm.iloc[i + 1]
            interval_count = int((row_end['timestamp'] - row_start['timestamp']).total_seconds() / (interval_minutes * 60))

            # Pre-calculate segment-level speed and heading
            distance_km = haversine_km(row_start['lat'], row_start['lon'], row_end['lat'], row_end['lon'])
            heading = calculate_heading(row_start['lat'], row_start['lon'], row_end['lat'], row_end['lon'])
            speed_kts = (distance_km / ((row_end['timestamp'] - row_start['timestamp']).total_seconds() / 3600)) * 0.539957

            # just use row_start storm type for now
            storm_type = row_start['storm_type']

            for step in range(interval_count):
                factor = step / interval_count
                interpolated_time = row_start['timestamp'] + timedelta(minutes=interval_minutes * step)
                lat = row_start['lat'] + factor * (row_end['lat'] - row_start['lat'])
                lon = row_start['lon'] + factor * (row_end['lon'] - row_start['lon'])
                wind_speed = row_start['wind_speed'] + factor * (row_end['wind_speed'] - row_start['wind_speed'])
                # handle case where a pressure value is missing
                if row_start['pressure'] is not None and row_end['pressure'] is not None:
                    pressure = row_start['pressure'] + factor * (row_end['pressure'] - row_start['pressure'])
                else:
                    pressure = None

                interpolated_rows.append({
                    "storm_id": sid,
                    "timestamp": interpolated_time,
                    "lat": lat,
                    "lon": lon,
                    "wind_speed": wind_speed,
                    "pressure": pressure,
                    "storm_type": storm_type,
                    "heading": heading,
                    "speed": speed_kts                   
                })

        # Add final point for the stormtrack
        interpolated_rows.append(storm.iloc[-1].to_dict())          
    # return as a dataframe
    return pd.DataFrame(interpolated_rows)

def parse_radius(val):
    return None if val == "-999" or int(val) == -999 else int(val)

def check_exist_storm(conn, storm_id):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id FROM storms.storms
            WHERE storm_id = %s
        """, (storm_id,))
        return cur.fetchone()