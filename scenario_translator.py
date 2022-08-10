""" Plugin to translate and scale aircraft between two different areas. """
import numpy as np
from os import path
import geopandas as gpd
from shapely.affinity import rotate, scale, translate
from pyproj import Transformer
from typing import Union
import warnings
from shapely.errors import ShapelyDeprecationWarning
warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)

# ------- USER INPUTS -------
# scenario to read
scenario = 'scenario/valkenburg/HYB_2_air.scn'

# x_ydistance transalte
xy_offset_m = (-450, -660)

# ------- END USER INPUTS -------

# transformers
transformer_m = Transformer.from_crs(4326, 3857, always_xy=True)
transformer_deg = Transformer.from_crs(3857, 4326)

def translate_data(lat: str,lon: str):
    '''
    Translate the lat and lon data with a prededined offset
    '''
    # Step 1
    # transform to UTM
    x, y = transformer_m.transform(float(lon), float(lat))

    # step 2 translate
    x_pos = x + xy_offset_m[0]
    y_pos = y + xy_offset_m[1]

    # step3 convert back to lat lon
    lat_t, lon_t = transformer_deg.transform(x_pos, y_pos)
    
    return str(lat_t), str(lon_t)

def cmd_translator(cmd_split: Union[list, None] = None):
    ''' CRE, ADDWAYPOINTS, ATDIST translator

    The CRE command is as follows: xs
        hh:mm:ss>CRE [acid] [type] [lat] [lon] [hdg] [spd] [alt]
    
    The ADDWAYPOINTS works as follows
        hh:mm:ss>ADDWAYPOINTS [acid] [lat1] [lon1] [alt1] [spd1] [wptype1] [turnspd1] [lat2] [lon2] [alt2] [spd2] [wptype2] [turnspd2] [lat3] ...
    
    The ATDIST Command works as follows
        hh:mm:ss>ATDIST [acid] [lat] [lon] [dist] [cmd]
    '''

    if cmd_split[0] not in ['CRE', 'ADDWAYPOINTS', 'ATDIST']:
        return cmd_split

    if cmd_split[0] == 'CRE':
        # if CRE CMD lat,lon are 3 and 4 positions
        lat_t, lon_t =  translate_data(*cmd_split[3:5])
        cmd_split[3:5] = [lat_t, lon_t]
        new_cmd = ' '.join(cmd_split)

    elif cmd_split[0] == 'ATDIST':
        # if ATDIST CMD lat,lon are 2 and 3 positions
        lat_t, lon_t =  translate_data(*cmd_split[2:4])
        cmd_split[2:4] = [lat_t, lon_t]

        # call itself  to translate the command
        cmd_split[5:] = cmd_translator(cmd_split[5:])

        new_cmd = ' '.join(cmd_split)
        
    elif cmd_split[0] == 'ADDWAYPOINTS':
        # ADDWAYPOINTS is more complicated
        # lat is at postion 1 and then it repeats every 6 positions
        # lon is at position 2 and then it repeats every 6 positions
        # get lats and lons from ADDWAYPOINTS
        lats = cmd_split[2::6]
        lons = cmd_split[3::6]
        
        lat_lons = [translate_data(*lat_lon) for lat_lon in zip(lats, lons)]
        lats_t = [lat_lon[0] for lat_lon in lat_lons]
        lons_t = [lat_lon[1] for lat_lon in lat_lons]

        cmd_split[2::6] = lats_t
        cmd_split[3::6] = lons_t
        
        new_cmd = ' '.join(cmd_split)

    return new_cmd


# now open the scenario data
with open(scenario, 'r') as f:
    data = f.readlines()

# now loop over the lines and translate the aircraft
# only modify lines that start with:
# CRE, ADDWAYPOINTS, ATDIST

line_new = []
for idx, line in enumerate(data):
    time = line[0:9]
    cmd = line[9:]
    cmd_split = cmd.split(' ')

    if cmd_split[0] not in ['CRE', 'ADDWAYPOINTS', 'ATDIST']:
        line_new.append(line)
    else:
        # translate the new command
        new_cmd = cmd_translator(cmd_split)
        # now join the new command
        line_new.append(time + new_cmd)

# now write the new scenario
scenario_new = scenario.replace('.scn', '_translated.scn')
with open(scenario_new, 'w') as f:
    f.writelines(line_new)

