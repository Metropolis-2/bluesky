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

    last_wptidx = np.argmax(ac_route.wpname)
    last_wpt_lat = ac_route.wplat[last_wptidx]
    last_wpt_lon = ac_route.wplon[last_wptidx]

    qdr_to_next, distance_to_wpt = tools.geo.kwikqdrdist(ac_lat, ac_lon, last_wpt_lat, last_wpt_lon)
    distance_to_wpt = distance_to_wpt * tools.geo.nm  # Now in meters

    return distance_to_wpt


def checker(acid: 'acid', dist):
    if dist is not None and dist-50 > traf.wptdist[acid]:
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
