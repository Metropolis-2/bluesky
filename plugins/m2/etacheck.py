""" BlueSky plugin template. The text you put here will be visible
    in BlueSky as the description of your plugin. """
from random import randint
import numpy as np
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, sim, tools #, settings, navdb, scr, tools
from datetime import datetime

turn_delay=\
    {'MP30':
        {
            15:3,
            10:4,
            5:6,
            2:9
        },
    'MP20':
        {
            15:1,
            10:1,
            5:3,
            2:7
        }
    }

def calc_eta(acid: 'acid'):

    ownship = traf
    total_distance = 0
    total_time = 0

    # get the flightplan and details
    ac_route = ownship.ap.route[acid]
    iactwp = ac_route.iactwp

    next_lat = ac_route.wplat[iactwp]
    next_lon = ac_route.wplon[iactwp]
    next_alt = ac_route.wpalt[iactwp]

    # use standard aircraft cruising speed for the speed.
    ownship_type = traf.type[acid]
    if ownship_type == 'MP20':
        ac_gs=20*tools.aero.kts
    elif ownship_type == 'MP30':
        ac_gs = 30*tools.aero.kts
    else:
        ac_gs = 20*tools.aero.kts


    # get the current ownship aircraft state
    ac_lat = ownship.lat[acid]
    ac_lon = ownship.lon[acid]
    ac_vs = ownship.perf.vsmax[acid]
    ac_alt = ownship.alt[acid]


    distance, time = calc_leg(ac_lat,ac_lon,next_lat,next_lon,ac_alt,next_alt,ac_gs,ac_vs)

    total_distance += distance
    total_time += time
    # calculate rest of route
    for idx in range(iactwp, ac_route.nwp - 2):

        cur_lat = ac_route.wplat[idx]
        cur_lon = ac_route.wplon[idx]
        cur_gs = ac_route.wpspd[idx]

        cur_vs = ownship.perf.vsmax[acid]
        cur_alt = ac_route.wpalt[idx]

        next_lat = ac_route.wplat[idx + 1]
        next_lon = ac_route.wplon[idx + 1]
        next_alt = ac_route.wpalt[idx + 1]

        distance, time = calc_leg(cur_lat, cur_lon, next_lat, next_lon, cur_alt, next_alt, cur_gs, cur_vs)

        total_distance += distance
        total_time += time

    # determine the eta

    eta = sim.utc.timestamp()+total_time

    eta = eta + turnDelay(acid)

    return eta

def horizontal_leg(start_lat, start_lon, end_lat, end_lon, spd):
    qdr_to_next, distance = tools.geo.kwikqdrdist(start_lat, start_lon, end_lat, end_lon)
    distance = distance * tools.geo.nm #[m]

    time = distance / spd #[sec]
    return distance, time

def vertical_leg(start_alt, end_alt, vs):

    distance = abs(start_alt - end_alt) #[m]
    time = distance/abs(vs) #[sec]
    return distance, time

def calc_leg(start_lat, start_lon, end_lat, end_lon, start_alt, end_alt, spd, vs):
    if start_lat == end_lat and start_lon == end_lon:
        distance, time = vertical_leg(start_alt, end_alt, vs)
    else:
        distance,time = horizontal_leg(start_lat,start_lon, end_lat, end_lon, spd)

    return distance, time

def turnDelay(acid:'acid'):
    turnspd = traf.turnspeed[acid]
    turns = traf.turns[acid]
    ac_route = traf.ap.route[acid]
    turnspd = turnspd[np.where(turns > ac_route.iactwp)]
    ownship_type = traf.type[acid]
    delay = 0
    for i in turnspd:
        delay += turn_delay[ownship_type][i]
    return delay


def secToDT(seconds):
    return datetime.fromtimestamp(int(seconds)).strftime("%Y-%m-%d, %H:%M:%S")