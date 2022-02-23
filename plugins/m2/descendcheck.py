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

        if iwpid > sec_last_wptidx:
            pass

        if iwpid > sec_last_wptidx and not conflictProbe(traf, traf, idx, dtlook=traf.dtlookdown[idx], targetVs=traf.perf.vsmin[idx]):

            stack.stack(f'ECHO For {traf.id[idx]} descendcheck is turned ON')
            # call the stacks
            landing = not traf.swlnav[idx] and traf.actwp.swlastwp[idx]

            if landing:
                traf.selspd[idx] = 0.0
                traf.selalt[idx] = 0.0
                # stack.stack(f"{traf.id[idx]} SPD 0")
                # stack.stack(f"{traf.id[idx]} ALT 0 ")

                stack.stack(f"ATALT {traf.id[idx]} 5 DEL {traf.id[idx]}")

                # update startDescend
                startDescend = True

            else:
                startDescend = False
        else:
            startDescend = False
    else:
        startDescend = False

    return startDescend
