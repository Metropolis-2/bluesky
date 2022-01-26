""" BlueSky plugin template. The text you put here will be visible
    in BlueSky as the description of your plugin. """
from random import randint
import numpy as np
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, settings, navdb, sim, scr, tools

def calc_dist(acid: 'acid'):
    ownship = traf

    #get the current ownship lat lon and flightplan
    ac_lat = ownship.lat[acid]
    ac_lon = ownship.lon[acid]
    ac_route = ownship.ap.route[acid]

    # if the ac does not have a flightplan, argmax will trigger an error
    try:
        #get the index of the last waypoint
        last_wptidx = np.argmax(ac_route.wpname)
        sec_last_wptidx = last_wptidx# - 1
        last_wpt_lat = ac_route.wplat[last_wptidx]
        last_wpt_lon = ac_route.wplon[last_wptidx]
        sec_last_wpt_lat = ac_route.wplat[sec_last_wptidx]
        sec_last_wpt_lon = ac_route.wplon[sec_last_wptidx]

    except:
        #if there is no flightplan set the values to -2 to ensure the next if statement will not because of None vals
        sec_last_wptidx = -2
        last_wpt_lat = -2
        last_wpt_lon = -1
        sec_last_wpt_lat = -1
        sec_last_wpt_lon = -2

    #if the index of the last waypoint in the flightplan matches with the current active waypoint

    if sec_last_wptidx == ac_route.iactwp and last_wpt_lat==sec_last_wpt_lat and last_wpt_lon == sec_last_wpt_lon:

        # select the lat and lon of the next (and last) waypoint element
        wpt_lat = ac_route.wplat[ac_route.iactwp]
        wpt_lon = ac_route.wplon[ac_route.iactwp]

        #calculate the distance to the next (and last) waypoint
        qdr_to_next, distance_to_wpt = tools.geo.kwikqdrdist(ac_lat, ac_lon, wpt_lat, wpt_lon)
        distance_to_wpt = distance_to_wpt * tools.geo.nm  # Now in meters

        return distance_to_wpt


def checker(acid: 'acid', dist):
    if dist is not None and dist > traf.wptdist[acid]:
        val = True
        stack.stack(f'REROUTEOVERSHOOT {traf.id[acid]}')
        traf.wptdist[acid] = 99999
    #if distance is calculated and thus the last waypoint is active, set the val still to false and also update the dist in the wptdist array
    elif dist is not None:
        val = False
        traf.wptdist[acid] = dist
    elif dist is None:
        val = False
    return val

#TODO dont trigger overshoot if its less than 100m overshot.