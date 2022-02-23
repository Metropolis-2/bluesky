""" BlueSky plugin template. The text you put here will be visible
    in BlueSky as the description of your plugin. """
from random import randint
import numpy as np
import re
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, tools  #, settings, navdb, sim, scr, tools
from bluesky.tools.aero import kts

def setSpeed(idxown, diff):

    # Determine the layer index of the current layer of ownship
    idxCurrentLayer = np.where(traf.layernames == traf.aclayername[idxown])[0]
    nameCurrentLayer = traf.aclayername[idxown]
    ac_route = traf.ap.route[idxown]
    iactwp = ac_route.iactwp
    lowerSpdLimit = traf.layerLowerSpd[idxCurrentLayer][0] / kts
    upperSpdLimit = traf.layerUpperSpd[idxCurrentLayer][0] / kts

    if re.match('cruising.+',nameCurrentLayer) is not None and traf.flightphase[idxown] == 0 and iactwp > 0:
        # get the currect layers speed limits

        if not traf.speedupdate[idxown] and iactwp!=np.argmax(ac_route.wpname) and iactwp!=np.argmax(ac_route.wpname)-1:
            if diff < -25 and iactwp not in traf.turns[idxown] and iactwp+1 not in traf.turns[idxown]:
                traf.speedupdate[idxown] = True
                stack.stack(f"SPD {traf.id[idxown]} {upperSpdLimit}")
                stack.stack(f"SPD {traf.id[idxown]} {upperSpdLimit}")
                stack.stack(f"ECHO {traf.id[idxown]} is speeding up")
            elif diff > 25 and iactwp not in traf.turns[idxown] and iactwp+1 not in traf.turns[idxown]:
                traf.speedupdate[idxown] = True
                stack.stack(f"SPD {traf.id[idxown]} {lowerSpdLimit}")
                stack.stack(f"SPD {traf.id[idxown]} {lowerSpdLimit}")
                stack.stack(f"ECHO {traf.id[idxown]} is slowing down")
        elif traf.speedupdate[idxown]:
            if abs(diff) < 15:
                stack.stack(f"{traf.id[idxown]} LNAV ON")
                stack.stack(f"{traf.id[idxown]} VNAV ON")
                stack.stack(f"ECHO {traf.id[idxown]} is going back to wpt speed")
                traf.speedupdate[idxown] = False
            elif iactwp+1 in traf.turns[idxown] or iactwp in traf.turns[idxown]:
                stack.stack(f"{traf.id[idxown]} LNAV ON")
                stack.stack(f"{traf.id[idxown]} VNAV ON")
                stack.stack(f"ECHO {traf.id[idxown]} is going back to wpt speed")
                traf.speedupdate[idxown] = False
        elif traf.swvnav[idxown] and not traf.swvnavspd[idxown] and int(traf.gs[idxown]/kts)==19:
            stack.stack(f"{traf.id[idxown]} LNAV ON")
            stack.stack(f"{traf.id[idxown]} VNAV ON")
            stack.stack(f"ECHO {traf.id[idxown]} 19kts bug")
            traf.speedupdate[idxown] = False

        if traf.speedupdate[idxown] and iactwp == np.argmax(ac_route.wpname) or iactwp == np.argmax(ac_route.wpname)-1:
            stack.stack(f"{traf.id[idxown]} LNAV ON")
            stack.stack(f"{traf.id[idxown]} VNAV ON")
            stack.stack(f"ECHO {traf.id[idxown]} close to destination, back to wpt speed")
            traf.speedupdate[idxown] = False


    iactwp = traf.ap.route[idxown].iactwp
    wplat = traf.ap.route[idxown].wplat[iactwp]
    wplon = traf.ap.route[idxown].wplon[iactwp]
    aclat = traf.lat[idxown]
    aclon = traf.lon[idxown]
    bearing, _ = tools.geo.qdrdist(aclat,aclon,wplat,wplon)

    if re.match('reso_0', nameCurrentLayer) is not None and traf.gs[idxown]==0 and traf.vs[idxown]==0:
        stack.stack(f"{traf.id[idxown]} LNAV ON")
        stack.stack(f"SPD {traf.id[idxown]} 5")
    elif re.match('reso_0', nameCurrentLayer) is not None and traf.gs[idxown] == upperSpdLimit and traf.vs[idxown] == 0 and bearing > 90:
        stack.stack(f"{traf.id[idxown]} LNAV ON")
        stack.stack(f"SPD {traf.id[idxown]} 5")