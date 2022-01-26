""" This plugin checks if it is possible for a drone to start its descend
to its destination """

import numpy as np
from bluesky import core, stack, traf, settings #, navdb, sim, scr, tools
from bluesky.tools.aero import ft, kts
from plugins.m2.conflictprobe import conflictProbe

def checker(idx):
    # find out the current active waypoint
    iwpid = traf.ap.route[idx].iactwp

    # Proceed if the aircraft has waypoints
    if iwpid > -1:

        # Determine the lat lon of the last and the second last waypoints. the second last waypoint is the ToD
        sec_last_wptidx = traf.ap.route[idx].nwp-2
        sec_last_wpt_lat = traf.ap.route[idx].wplat[sec_last_wptidx]
        sec_last_wpt_lon = traf.ap.route[idx].wplon[sec_last_wptidx]

        # If all the conditions are satisfied, then use stack commands to descend this aircraft
        if iwpid > sec_last_wptidx and not conflictProbe(traf, traf, idx, dtlook=traf.dtlookdown[idx],
                                         targetVs=traf.perf.vsmin[idx]):

            stack.stack(f'ECHO For {traf.id[idx]} descendcheck is turned ON')
            # call the stacks
            stack.stack(f"SPD {traf.id[idx]} {traf.ap.route[idx].wpspd[iwpid] / kts}")
            stack.stack(f"ATDIST {traf.id[idx]} {sec_last_wpt_lat} {sec_last_wpt_lon} 0.1115982 {traf.id[idx]} VNAV OFF")
            stack.stack(f"ATDIST {traf.id[idx]} {sec_last_wpt_lat} {sec_last_wpt_lon} 0.1115982 SPD {traf.id[idx]} 0")
            stack.stack(f"ATSPD {traf.id[idx]} 0 ALT {traf.id[idx]} 0")
            stack.stack(f"ATALT {traf.id[idx]} 5 DEL {traf.id[idx]}")

            # update startDescend
            startDescend = True

        elif iwpid == sec_last_wptidx+1:
            stack.stack(f"SPD {traf.id[idx]} 0")
            stack.stack(f"ATSPD {traf.id[idx]} 0 ALT {traf.id[idx]} 0")
            stack.stack(f"ATALT {traf.id[idx]} 5 DEL {traf.id[idx]}")

            # update startDescend
            startDescend = True

        else:
            startDescend = False

    else:
        startDescend = False

    return startDescend
