""" The hybridcd plugin overrides the default statebased CD. It is a combination
of statebased CD with an intent filter at the end. The aim is to reduce the number of
flase positives using intent. """
import numpy as np
import copy
from shapely.ops import nearest_points

# Import the global bluesky objects. Uncomment the ones you need
from bluesky import traf  # , core, stack, settings, navdb, sim, scr, tools
from bluesky.traffic.asas import ConflictDetection
from bluesky.tools.geo import kwikdist
from bluesky.tools import geo
from bluesky.tools.aero import nm  # , ft
import casas


def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    cd = hybridconfdetect()

    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name': 'hybridconfdetect',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type': 'sim',
    }

    # init_plugin() should always return a configuration dict.
    return config


class hybridconfdetect(ConflictDetection):
    ''' Example new entity object for BlueSky. '''

    def __init__(self):
        super().__init__()

    def detect(self, ownship, intruder, rpz, hpz, dtlookahead):

        confpairs, lospairs, inconf, tcpamax, qdr, dist, dcpa2, tcpa, tinconf = casas.detect(ownship, intruder, rpz, hpz, dtlookahead)

        return confpairs, lospairs, inconf, tcpamax, \
               qdr, dist, dcpa2, \
               tcpa, tinconf

    def intentFilter(self, conf, confpairs, inconf, ownship, intruder, swverconf, swconfl):
        '''Function to check and remove conflicts from the confpairs and inconf lists
           if such a conflict is automatically solved by the intended routes of the aircraft '''

        # dict to store the the idxs of the aircraft to change their active status
        changeactive = dict()

        # make a deep copy of confpairs in order to loop through and delete from conf.confpairs
        conflicts = copy.deepcopy(confpairs)

        # loop through each conflict and remove conflict if intent resolves conflict
        for conflict in conflicts:

            # idx of ownship and intruder
            idxown, idxint = traf.id2idx(conflict)

            # minimum horizontal separation
            rpz = max(conf.rpz[idxown], conf.rpz[idxint])  # *1.05
            hpz = max(conf.hpz[idxown], conf.hpz[idxint])

            # get the intents of ownship and intruder. This is calculated in the intent plugin.
            own_intent, own_target_alt = ownship.intent[idxown]
            intruder_intent, intruder_target_alt = intruder.intent[idxint]

            # Find the nearest point in the two line strings
            pown, pint = nearest_points(own_intent, intruder_intent)

            # Find the distance between the points
            point_distance = kwikdist(pown.y, pown.x, pint.y, pint.x) * nm  # [m]

            # Also do vertical intent
            # Difference between own altitude and intruder target
            fpown = traf.flightphase[idxown]
            fpint = traf.flightphase[idxint]

            diff = own_target_alt - intruder_target_alt

            if (fpown == 0 and fpint == 1) or (fpown == 2 and fpint == 0):
                if own_target_alt > intruder_target_alt:
                    verticalCondition = hpz >= abs(diff)
                elif traf.alt[idxown] < traf.alt[idxint]:
                    verticalCondition = hpz >= abs(diff)
                else:
                    verticalCondition = swverconf[idxown]

            elif (fpown == 0 and fpint == 2) or (fpown == 1 and fpint == 0):
                if own_target_alt < intruder_target_alt:
                    verticalCondition = hpz >= abs(diff)
                elif traf.alt[idxown] > traf.alt[idxint]:
                    verticalCondition = hpz >= abs(diff)
                else:
                    verticalCondition = swverconf[idxown]

            elif (fpown == 0 and fpint == 0):
                verticalCondition = hpz >= abs(diff)

            else:
                verticalCondition = swverconf[idxown]

                # if fpown != fpint:
            #     diff = own_target_alt - intruder_target_alt
            #     verticalCondition = hpz >= abs(diff)
            # else:
            #     verticalCondition = swverconf[idxown]

            # Basically, there are two conditions to be met in order to skip
            # a conflict due to intent:
            # 1. The minimum distance between the horizontal intent lines is greater than r;
            # 2. The difference between the current altitude and the target altitude of the
            # intruder is greater than the vertical separation margin;
            if (point_distance < rpz) and verticalCondition:
                # if this is a real conflict, set it to active to True
                changeactive[idxown] = True
                changeactive[idxint] = True
            else:
                # if the intent resolves the conflict, then remove this conflict
                # from the conflict lists and set active to False
                confpairs.remove(conflict)
                # if set(conflict) in conf.confpairs_unique:
                #     conf.confpairs_unique.remove(set(conflict))
                # if set(conflict) in conf.confpairs_all:
                #     conf.confpairs_all.remove(set(conflict))
                swconfl[idxown, idxint] = False
                changeactive[idxown] = changeactive.get(idxown, False)
                changeactive[idxint] = changeactive.get(idxint, False)

        for idx, active in changeactive.items():
            # Loop a second time: this is to avoid that ASAS resolution is
            # turned off for an aircraft that is involved simultaneously in
            # multiple conflicts, where the first, but not all conflicts are
            # resolved.
            # traf.cr.active[idx] = active
            inconf[idx] = active

        return confpairs, inconf, swconfl
