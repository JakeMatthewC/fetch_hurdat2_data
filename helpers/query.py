from sqlalchemy import create_engine, text
from psycopg2.extras import execute_values, Json
import pandas as pd


CONN_STR = "postgresql+psycopg2://Jacob:@localhost:5432/postgres"
engine = create_engine(CONN_STR)
conn = engine.connect() 

def find_buoys_with_timestamp(storm_timestamp):   
    df = pd.read_sql(text("""
        SELECT ts.id, ts.timestamp, b.station_id, b.lat, b.lon  
        FROM dirspec.time_steps ts
        JOIN dirspec.buoys b on ts.buoy_id = b.id
        WHERE ts.timestamp BETWEEN (:storm_timestamp - INTERVAL '15 minutes')
                               AND (:storm_timestamp + INTERVAL '15 minutes')    
    """), conn, params={"storm_timestamp": storm_timestamp})
    return df

def find_stormtracks_with_timestamp(buoy_timestamp):
    df = pd.read_sql(text("""
        SELECT st.id, st.storm_id, st.timestamp, st.lat, st.lon, st.wind_speed, st.pressure, st.heading, st.speed, st.storm_type, s.storm_name
        FROM storms.storm_tracks st
        JOIN storms.storms s on st.storm_id = s.storm_id
        WHERE :buoy_timestamp BETWEEN (st.timestamp - INTERVAL '15 minutes')
                                  AND (st.timestamp + INTERVAL '15 minutes')    
    """), conn, params={"buoy_timestamp": buoy_timestamp})   
    return df

def get_station_lat_lon(buoy_id):   
    df = pd.read_sql(text("""
        SELECT b.lat, b.lon
        FROM dirspec.buoys b
        WHERE b.id = :buoy_id      
    """), conn, params={"buoy": buoy_id})  
    return df    

def get_storm_name(hurdat_storm_id):
    df = pd.read_sql(text("""
        SELECT s.storm_name
        FROM storms.storms s
        WHERE s.hurdat_storm_id = :hurdat_storm_id                      
        """), conn, params={"hurdat_storm_id": hurdat_storm_id})
    return df['storm_name']       

def update_storm_match(cur, time_step_id, hurdat_storm_id, dist, storm_timestamp):
    execute_values(cur, """
        INSERT INTO storms.storm_matches
        (time_step_id, hurdat_storm_id, storm_distance_km, storm_track_time)
        VALUES %s
        ON CONFLICT (time_step_id, hurdat_storm_id) DO NOTHING;
    """, [(time_step_id, hurdat_storm_id, dist, storm_timestamp)
    ])

def update_time_steps_table(cur, row_to_update, storm_name, time_step_id):
    cur.execute("""
        UPDATE dirspec.time_steps ts
        SET storm_name = %s,
            storm_type = %s,
            storm_heading_deg = %s,
            storm_speed_kts = %s,
            storm_distance_km = %s,
            storm_section_9 = %s,
            hurdat_storm_id = %s,
            is_storm = %s
        WHERE ts.id = %s;
    """, (
        storm_name,
        row_to_update['storm_type'], 
        row_to_update['storm_heading_deg'], 
        row_to_update['storm_speed_kts'],
        row_to_update['storm_distance_km'], 
        row_to_update['storm_Section_9'], 
        row_to_update['hurdat_storm_id'], 
        row_to_update['is_storm'],
        time_step_id
    ))
    