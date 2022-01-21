import numpy as np

from bluesky import traf  # , stack #, core #, settings, navdb, sim, scr, tools
from bluesky.tools.aero import nm, ft, kts, fpm


def reso1(idxown):
    '''The climb into resolution layer strategy.
    This strategy is only used when both the ownship and intruder are
    cruising and in a cruising layer '''

    # update the resostrategy used by ownship
    traf.resostrategy[idxown] = "RESO1"

    # Set the resolution active in altitude and vertical speed.
    traf.resoAltActive[idxown] = True
    traf.resoVsActive[idxown] = True

    # Determine the index of the current cruising layer within traf.layernames
    idxCurrentLayer = np.where(traf.layernames == traf.aclayername[idxown])[0]

    # Determine the altitude of the resolution layer from traf.layerLowerAlt
    # Note: resolution layer is always above the current resolution layer
    resoalt = traf.layerLowerAlt[idxCurrentLayer + 1][0]

    # Use the maximum performance to climb to the correct altitude
    resovs = traf.perf.vsmax[idxown]

    # add resoalt to the traf variable. needed updating intent and trajectory recovery
    traf.resoalt[idxown] = resoalt
    traf.resovs[idxown] = resovs
    traf.recoveryvs[idxown] = traf.ap.vs[idxown]
    return resoalt, resovs


def reso2(idxown, idxint, limitspeed=True):
    'The speed resolution strategy'

    # update the resostrategy used by ownship
    traf.resostrategy[idxown] = "RESO2"

    # activate the spd asas channel
    traf.resoTasActive[idxown] = True

    # Determine the layer index of the current layer of ownship
    idxCurrentLayer = np.where(traf.layernames == traf.aclayername[idxown])[0]

    # get the currect layers speed limits
    lowerSpdLimit = traf.layerLowerSpd[idxCurrentLayer][0]
    upperSpdLimit = traf.layerUpperSpd[idxCurrentLayer][0]

    # the current velocity ground speed vector of ownship and intruder
    # needed for velocity matching
    ownvector = np.array([traf.gseast[idxown], traf.gsnorth[idxown]])
    intvector = np.array([traf.gseast[idxint], traf.gsnorth[idxint]])

    # save the current ownship spd for recovery after conflict
    traf.recoveryspd[idxown] = traf.ap.tas[idxown]

    if np.linalg.norm(
            ownvector) > 0:  # avoid division by zero --> happens only if ownship is hovering in resolution layer
        resospd = np.dot(intvector, ownvector) / np.linalg.norm(ownvector)
    else:
        resospd = lowerSpdLimit + 0.5

    # Make sure that the resolution speed is within the speed limits of the current layer
    if limitspeed:
        if lowerSpdLimit <= resospd <= upperSpdLimit:
            traf.resospd[idxown] = resospd
        elif abs(lowerSpdLimit - resospd) < abs(upperSpdLimit - resospd):
            resospd = lowerSpdLimit
            traf.resospd[idxown] = resospd
        else:
            resospd = upperSpdLimit
            traf.resospd[idxown] = resospd
    else:
        traf.resospd[idxown] = resospd

    return resospd


def reso3(idxown, fpown):
    'The hover in the resolution layer strategy'

    # update the traf.resoname for ownship
    traf.resostrategy[idxown] = "RESO3"

    # activate the spd and vs asas channel
    traf.resoTasActive[idxown] = True
    traf.resoVsActive[idxown] = True
    traf.resoAltActive[idxown] = True  # needed to make sure that it hovers exactly at the lower alt of resolution layer

    # determine the hover altitude --> the lower alt of the current (resolution) layer
    idxCurrentLayer = np.where(traf.layernames == traf.aclayername[idxown])[0]
    resoalt = traf.layerLowerAlt[idxCurrentLayer][0]

    # Make the ownship hover
    resospd = 0.0

    # Determine the initial vertical speed during this resolution. Final vertical speed when resoalt is achived is 0.0 m/s
    resovs = 0.0 if abs(traf.alt[idxown] - resoalt) < abs(traf.layerHeight - traf.cd.hpz[idxown]) else traf.perf.vsmin[
        idxown]

    # Set the traffic variables
    traf.resospd[idxown] = resospd
    traf.resovs[idxown] = resovs
    traf.resoalt[idxown] = resoalt
    traf.recoveryspd[idxown] = 0.0

    # performance of the ownship
    vsMinOwn = traf.perf.vsmin[idxown]
    vsMaxOwn = traf.perf.vsmax[idxown]

    # Make sure the resovsown can be achieved
    if fpown == 1:
        traf.recoveryvs[idxown] = vsMaxOwn
    else:
        traf.recoveryvs[idxown] = vsMinOwn

    return resospd, resovs, resoalt


def reso4(idxown):
    'The temporarily level-off strategy'

    # TODO: determine the correct altitude for the drone to level off
    newalt = traf.alt[idxown]
    altactive = False  # TODO: CHANGE THIS

    # update the traf.resoname for ownship
    # TODO--> CHANGE THIS
    traf.resostrategy[idxown] = "None"

    # TODO: set traf.startDescend[idxown] to False!!!

    return newalt, altactive


def reso5(idxown, idxint):
    'The Climb into resolution layer + speed strategy'

    # call reso1 to get the correct resolution altitude and vs
    resoalt, resovs = reso1(idxown)

    # call reso2 to compute the correct resolution spd
    resospd = reso2(idxown, idxint, False)

    # update the traf.resoname for ownship
    traf.resostrategy[idxown] = "RESO5"

    return resoalt, resovs, resospd


def reso6(idxown, fpown):
    'The Climb into resolution layer + hover strategy'

    # update the traf.resoname for ownship
    traf.resostrategy[idxown] = "RESO6"

    # activate the spd and vs asas channel
    traf.resoTasActive[idxown] = True
    traf.resoVsActive[idxown] = True
    traf.resoAltActive[idxown] = True  # needed to make sure that it hovers exactly at the lower alt of resolution layer

    # determine the hover altitude --> the lower alt of the current (resolution) layer
    idxCurrentLayer = np.where(traf.layernames == traf.aclayername[idxown])[0]
    resoalt = traf.layerLowerAlt[idxCurrentLayer + 1][0]

    # Make the ownship hover
    resospd = 0.0

    # Determine the initial vertical speed during this resolution. Final vertical speed when resoalt is achived is 0.0 m/s
    resovs = 0.0 if abs(traf.alt[idxown] - resoalt) < abs(traf.layerHeight - traf.cd.hpz[idxown]) else traf.perf.vsmin[
        idxown]

    # Set the traffic variables
    traf.resospd[idxown] = resospd
    traf.resovs[idxown] = resovs
    traf.resoalt[idxown] = resoalt
    traf.recoveryspd[idxown] = 0.0

    # performance of the ownship
    vsMinOwn = traf.perf.vsmin[idxown]
    vsMaxOwn = traf.perf.vsmax[idxown]

    # Make sure the resovsown can be achieved
    if fpown == 1:
        traf.recoveryvs[idxown] = vsMaxOwn
    else:
        traf.recoveryvs[idxown] = vsMinOwn

    return resospd, resovs, resoalt


def reso7(idxown, fpown):
    'The descend into resolution layer + hover strategy'

    # update the traf.resoname for ownship
    traf.resostrategy[idxown] = "RESO7"

    # activate the spd and vs asas channel
    traf.resoTasActive[idxown] = True
    traf.resoVsActive[idxown] = True
    traf.resoAltActive[idxown] = True  # needed to make sure that it hovers exactly at the lower alt of resolution layer

    # determine the hover altitude --> the lower alt of the current (resolution) layer
    idxCurrentLayer = np.where(traf.layernames == traf.aclayername[idxown])[0]
    resoalt = traf.layerLowerAlt[idxCurrentLayer - 1][0]

    # Make the ownship hover
    resospd = 0.0

    # Determine the initial vertical speed during this resolution. Final vertical speed when resoalt is achived is 0.0 m/s
    resovs = 0.0 if abs(traf.alt[idxown] - resoalt) < abs(traf.layerHeight - traf.cd.hpz[idxown]) else \
        traf.perf.vsmin[idxown]

    # Set the traffic variables
    traf.resospd[idxown] = resospd
    traf.resovs[idxown] = resovs
    traf.resoalt[idxown] = resoalt
    traf.recoveryspd[idxown] = 0.0

    # performance of the ownship
    vsMinOwn = traf.perf.vsmin[idxown]
    vsMaxOwn = traf.perf.vsmax[idxown]

    # Make sure the resovsown can be achieved
    if fpown == 1:
        traf.recoveryvs[idxown] = vsMaxOwn
    else:
        traf.recoveryvs[idxown] = vsMinOwn

    return resospd, resovs, resoalt


def reso8(idxown, idxint, fpown):
    '''Velocity matching in the vertical direction'''

    # update the resostrategy used by ownship
    traf.resostrategy[idxown] = "RESO8"

    # Set the resolution active in altitude and vertical speed.
    traf.resoVsActive[idxown] = True

    # performance of the ownship
    vsMinOwn = traf.perf.vsmin[idxown]
    vsMaxOwn = traf.perf.vsmax[idxown]

    # match the vertical speed of the intruder
    resovsown = traf.vs[idxint]

    # save it to traf
    traf.resovs[idxown] = resovsown

    # Make sure the resovsown can be achieved
    if fpown == 1:
        traf.recoveryvs[idxown] = vsMaxOwn
    else:
        traf.recoveryvs[idxown] = vsMinOwn

    return resovsown


def reso9(idxown, idxint):
    # update the resostrategy used by ownship
    traf.resostrategy[idxown] = "RESO9"

    if traf.flightphase[idxown] == 0:
        # activate the spd asas channel
        traf.resoTasActive[idxown] = True

        # Determine the layer index of the current layer of ownship
        idxCurrentLayer = np.where(traf.layernames == traf.aclayername[idxown])[0]

        # get the currect layers speed limits
        lowerSpdLimit = traf.layerLowerSpd[idxCurrentLayer][0]
        upperSpdLimit = traf.layerUpperSpd[idxCurrentLayer][0]

        # the current velocity ground speed vector of ownship and intruder
        # needed for velocity matching
        ownvector = np.array([traf.gseast[idxown], traf.gsnorth[idxown]])
        intvector = np.array([traf.gseast[idxint], traf.gsnorth[idxint]])

        # save the current ownship spd for recovery after conflict
        traf.recoveryspd[idxown] = traf.ap.tas[idxown]

        if np.linalg.norm(
                ownvector) > 0:  # avoid division by zero --> happens only if ownship is hovering in resolution layer
            resospd = np.dot(intvector, ownvector) / np.linalg.norm(ownvector)
        else:
            resospd = lowerSpdLimit + 0.5

        if lowerSpdLimit <= resospd <= upperSpdLimit:
            traf.resospd[idxown] = resospd
        elif abs(lowerSpdLimit - resospd) < abs(upperSpdLimit - resospd):
            resospd = lowerSpdLimit
            traf.resospd[idxown] = resospd
        else:
            resospd = upperSpdLimit
            traf.resospd[idxown] = resospd

        traf.resospd[idxown] = resospd
        # Cruising aircraft should remain level
        resovs = 0
        resoalt = traf.alt[idxown]

        return resospd, resovs, resoalt

    else:
        # activate the spd and vs asas channel
        traf.resoTasActive[idxown] = True
        traf.resoVsActive[idxown] = True
        traf.resoAltActive[
            idxown] = True  # needed to make sure that it hovers exactly at the lower alt of resolution layer

        # determine the hover altitude
        idxCurrentLayer = np.where(traf.layernames == traf.aclayername[idxown])[0]

        if traf.aclayername[idxown].rfind('reso'):
            resoalt = traf.layerLowerAlt[idxCurrentLayer][0]

            # Determine the initial vertical speed during this resolution. Final vertical speed when resoalt is achived is 0.0 m/s
            resovs = 0.0 if abs(traf.alt[idxown] - resoalt) < abs(traf.layerHeight - traf.cd.hpz[idxown]) else \
            traf.perf.vsmin[idxown]

        else:
            resoalt = traf.layerLowerAlt[idxCurrentLayer + 1][0]

            # Determine the initial vertical speed during this resolution. Final vertical speed when resoalt is achived is 0.0 m/s
            resovs = 0.0 if abs(traf.alt[idxown] - resoalt) < abs(traf.layerHeight - traf.cd.hpz[idxown]) else \
            traf.perf.vsmin[idxown]

        # Climbing/descending drone should not move horizontally
        resospd = 0.0

        # Set the traffic variables
        traf.resospd[idxown] = resospd
        traf.resovs[idxown] = resovs
        traf.resoalt[idxown] = resoalt
        traf.recoveryspd[idxown] = 0.0

        return resospd, resovs, resoalt



