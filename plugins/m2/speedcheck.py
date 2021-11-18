import numpy as np
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, settings, navdb, sim, scr, tools,simulation
from datetime import datetime, timedelta



def calc_eta(acid: 'acid'):
    ownship=traf

    # get the current ownship lat lon and flightplan
    ac_gs = ownship.gs[acid]
    ac_lat = ownship.lat[acid]
    ac_lon = ownship.lon[acid]
    ac_route = ownship.ap.route[acid]
    iactwp = ac_route.iactwp

    total_length = 0
    total_time = 0

    #calculate current flight leg
    cur_lat = ac_route.wplat[iactwp]
    cur_lon = ac_route.wplon[iactwp]

    qdr_to_next, distance_to_wpt = tools.geo.kwikqdrdist(ac_lat, ac_lon, cur_lat, cur_lon)
    distance_to_wpt = distance_to_wpt * tools.geo.nm  # Now in meters
    total_length += distance_to_wpt
    total_time += distance_to_wpt / ac_gs

    # TODO add logic that determines if there is a climb leg, no horizontal speed but vertical speed.
    # calculate rest of route
    for idx in range(iactwp,ac_route.nwp+1):
        cur_lat = ac_route.wplat[idx]
        cur_lon = ac_route.wplon[idx]

        spd = ac_route.wpspd[idx]

        max_wpidx = np.argmax(ac_route.wpname)

        #stop the loop if it is at the final waypoint
        if idx == max_wpidx:
            break

        next_lat = ac_route.wplat[idx+1]
        next_lon = ac_route.wplon[idx+1]

        #calc vertical distance and time
        if cur_lat == next_lat and cur_lon == next_lon:
            break

        qdr_to_next, distance_to_wpt = tools.geo.kwikqdrdist(cur_lat, cur_lon, next_lat, next_lon)
        distance_to_wpt = distance_to_wpt * tools.geo.nm  # Now in meters

        total_length += distance_to_wpt
        total_time += distance_to_wpt/spd

    #calculate the average speed for the rest of the flightplan
    avg_spd = total_length/total_time

    #determine the eta
    eta = simulation.utc.datetime.timedelta(seconds=total_time)

    return eta,avg_spd,total_time,total_length

def check_eta(eta,sta):
    diff = sta - eta
    diff = diff.total_seconds()

    # if the delay is larger than 20 seconds return True
    if diff < -20:
        val = True
    else:
        val = False

    return val