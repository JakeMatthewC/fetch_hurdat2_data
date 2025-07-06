import pandas as pd
from psycopg2.extras import execute_values

# modules
import query as q
import utils as u


def storm_buoy_match(storm_df, buoy_df, max_distance_km=400):
    # if updating storms tables or adding a buoy
    # for each stormtrack timestep -> filter to buoy timesteps within 15 min of the timestep
    # check haversine distance and windspeed at buoy at the timesteps
    # mark is_storm and update matches table if needed

    # storm_df: a df containing all storm timesteps
    # buoy_df if updating storms table: a df containing all buoy timesteps within 15 min of a storm timestep
    # buoy_df if adding a buoy: a df containing all timesteps for the buoy witin 15 min of a storm timestep
    # updating storms condition, storm_df is all new storm data
    if storm_df is not None:
        # check each storm timestep for nearby buoys that meet conditions
        for _, storm_row in storm_df.iterrows():
            storm_timestamp = storm_row['timestamp']
            storm_lat = storm_row['lat']
            storm_lon = storm_row['lon']
            storm_id = storm_row['storm_id']
            
            # query all buoys with this timestamp
            buoys_with_ts = q.find_buoys_with_timestamp(storm_timestamp)

            # check for conditions to set is_storm=True
            for _, buoy_row in buoys_with_ts.iterrows():
                time_step_id = buoy_row['id']
                dist = u.haversine_km(storm_lat, storm_lon, buoy_row['lat'], buoy_row['lon'])

                if dist <= max_distance_km:
                    # update database tables
                    q.update_storm_match(time_step_id, storm_id, storm_timestamp, dist)
                    q.update_buoy_time_steps(storm_row)


    # adding new buoy condition
    elif buoy_df is not None:
        for _, row in buoy_df.iterrows():
            buoy_timestamp = row['timestamp']

            # query all storm timesteps with this timestamp
            storms_with_ts = q.find_stormtracks_with_timestamp(buoy_timestamp)

            # check for conditions to set is_storm=True

            # update buoy timestep with storm parameters

            # update storm_matches