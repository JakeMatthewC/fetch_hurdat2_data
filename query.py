from sqlalchemy import create_engine, text
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
        SELECT st.id, st.storm_id, st.timestamp, st.lat, st.lon, st.wind_speed, st.pressure, st.heading, st.speed, s.storm_name
        FROM storms.storm_tracks st
        JOIN storms.storms s on st.storm_id = s.storm_id
        WHERE :buoy_timestamp BETWEEN (st.timestamp - INTERVAL '15 minutes')
                                  AND (st.timestamp + INTERVAL '15 minutes')    
    """), conn, params={"buoy_timestamp": buoy_timestamp})   
    return df                   

def update_storm_match(time_step_id, storm_id, storm_timestamp, dist):
    x=1

def update_buoy_time_steps(storm_row):
    x=1          