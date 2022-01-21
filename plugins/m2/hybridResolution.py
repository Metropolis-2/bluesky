""" The hybridResolution plugin performs tactical airborne conflict resolution in the
    Hybrid concept of the Metropolis 2 project.
    Created by: Emmanuel
    Date: 29 July 2021
"""
import numpy as np
import copy

# Import the global bluesky objects. Uncomment the ones you need
from bluesky import traf, stack #, core #, settings, navdb, sim, scr, tools
from bluesky.traffic.asas import ConflictResolution
from bluesky.tools.aero import nm, ft, kts, fpm
from bluesky.tools import geo
from plugins.m2.conflictprobe import conflictProbe
import plugins.m2.resostrategies as rs


def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity. Seems to work even if you don't do this.
    reso = hybridResolution()

    # Configuration parameters
    config = {
        # The name of your plugin. Keep it the same as the class
        'plugin_name':     'hybridResolution',

        # The type of this plugin.  For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config

class hybridResolution(ConflictResolution):
    def __init__(self):
        super().__init__()

    def resolve(self, conf, ownship, intruder):
        ''' This resolve function will override the default resolution of ConflictResolution
            It should return the gs, vs, alt and trk that the conflicting aircraft should
            fly to return the conflict. The hypri'''
        # note 'conf' is the CD object --> traf.cd
        # this resolve function should have the following four outputs: newtrk, newgs, newvs, newalt

        # Make a copy of the traffic gs, alt, trk and vs. These are the outputs of this function.
        newtrk = copy.deepcopy(traf.ap.trk)
        newgs = np.where(traf.resoTasActive, traf.resospd, traf.ap.tas)
        newvs = np.where(traf.resoVsActive, traf.resovs, traf.ap.vs)
        newalt = np.where(traf.resoAltActive, traf.resoalt, traf.ap.alt)

        # Sort the conflicts based on lowest tLOS last, so that the most urgent conflict gets solved first
        sorted_indx = np.argsort(conf.tLOS)[::-1]

        # Determine all aircraft in MACC
        MACC = []
        for si in sorted_indx:
            (ac1, ac2) = conf.confpairs[si]
            idxown = ownship.id.index(ac1)
            # Check if idxown is already in MACC
            if idxown in np.squeeze(MACC) or traf.flightphase[idxown] != 0:
                continue
            # Determine the confpairs that contain idxown
            conflictsWithOwnship = self.pairs(conf, ownship, idxown)
            # Check if idxown is in a MACC and add all intruders to MACC, put highest priority first
            if len(conflictsWithOwnship) > 1:
                temp = [idxown]
                highest_prio = idxown
                for i in conflictsWithOwnship:
                    idxother = ownship.id.index(conf.confpairs[i][1])
                    temp.append(idxother)
                    if self.priorityChecker(highest_prio, idxother):
                        highest_prio = idxother
                temp.remove(highest_prio)
                temp = [highest_prio] + temp
                MACC.append(temp)

        # Loop through each conflict that is not a MACC, determine the resolution method, and set
        # the resolution for the asas module
        for si in sorted_indx:
            (ac1, ac2) = conf.confpairs[si]
            idxown = ownship.id.index(ac1)
            idxint = intruder.id.index(ac2)

            # Check if ownship is in MACC
            if idxown in np.squeeze(MACC):
                continue

            ownshipResolves = self.priorityChecker(idxown, idxint)

            # if ownship is resolving determine which reso method to use and use it!
            if ownshipResolves:
                # determine the ownship and intruder flight phase
                fpown = traf.flightphase[idxown]
                fpint = traf.flightphase[idxint]

                # determine if the ownship is in a resolution layer (True if ownship is in a resolution layer)
                rlayerown = traf.aclayername[idxown].lower().count("reso") > 0

                # Add the intruder into resoidint if not already in there
                if traf.id[idxint] not in traf.resoidint[idxown]:
                    # append the intruder callsigns that ownship is currently resolving in traf.resoidint
                    traf.resoidint[idxown].append(traf.id[idxint])

                ################## DETERMINE OWNSHIP RESO STRATEGY ##################
                # ownship and intruder are cruising
                if fpown == 0 and fpint == 0:
                    if rlayerown:
                        newgs[idxown] = rs.reso2(idxown, idxint)  # use the speed resolution strategy
                        stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso2: speed strategy")
                    else:
                        if not conflictProbe(ownship, intruder, idxown, idxint, dtlook=traf.dtlookup[idxown],
                                             targetVs=traf.perf.vsmax[idxown]):
                            newalt[idxown], newvs[idxown] = rs.reso1(idxown)  # use the "climb into resolution layer" strategy
                            stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso1: climb into resolution layer strategy")
                        else:
                            newgs[idxown] = rs.reso2(idxown, idxint)  # use the speed resolution strategy
                            stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso2: speed strategy")


                # ownship is cruising and intruder is climbing
                elif fpown == 0 and fpint == 1:
                    if rlayerown:
                        newgs[idxown] = rs.reso2(idxown, idxint)  # use the speed resolution strategy
                        stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso2: speed strategy")
                    else:
                        if not conflictProbe(ownship, intruder, idxown, idxint, dtlook=traf.dtlookup[idxown],
                                             targetVs=traf.perf.vsmax[idxown]):
                            newalt[idxown], newvs[idxown], newgs[idxown] = rs.reso5(idxown, idxint)  # use the climb into resolution layer + speed resolution strategy
                            stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso5: climb into resolution layer + speed resolution strategy")
                        else:
                            newgs[idxown] = rs.reso2(idxown, idxint)  # use the speed resolution strategy
                            stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso2: speed strategy")


                # ownship is cruising and intruder is descending
                elif fpown == 0 and fpint == 2:
                    if rlayerown:
                        newgs[idxown] = rs.reso2(idxown, idxint)  # use the speed resolution strategy
                        stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso2: speed strategy")
                    else:
                        if not conflictProbe(ownship, intruder, idxown, idxint, dtlook=traf.dtlookup[idxown],
                                             targetVs=traf.perf.vsmax[idxown]):
                            newalt[idxown], newvs[idxown], newgs[idxown] = rs.reso5(idxown, idxint)  # use the climb into resolution layer + speed resolution strategy
                            stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso5: climb into resolution layer + speed resolution strategy")
                        else:
                            newgs[idxown] = rs.reso2(idxown, idxint)  # use the speed resolution strategy
                            stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso2: speed strategy")

                # ownship is climbing and intruder is cruising
                elif fpown == 1 and fpint == 0:
                    if rlayerown:
                        newgs[idxown], newvs[idxown], newalt[idxown] = rs.reso3(idxown, fpown)  # Hover in the resolution layer strategy
                        stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso3: hover in the resolution layer strategy")
                    else:
                        if not conflictProbe(ownship, intruder, idxown, idxint, dtlook=traf.dtlookup[idxown],
                                             targetVs=traf.perf.vsmax[idxown]):
                            newgs[idxown], newvs[idxown], newalt[idxown] = rs.reso6(idxown, fpown)  # use the climb into resolution layer + hover resolution strategy
                            stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso6: climb into resolution layer + hover resolution strategy")
                        else:
                            newalt[idxown], traf.cr.altactive[idxown] = rs.reso4(idxown)  # temporarily level off strategy
                            # TODO
                            # stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso4: temporarily level off strategy")

                # ownship is climbing and intruder is climbing
                elif fpown == 1 and fpint == 1:
                    newvs[idxown] = rs.reso8(idxown, idxint, fpown)  # velocity matching in the vertical direction
                    stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso8: velocity matching in the vertical direction")

                # ownship is climbing and intruder is descending
                elif fpown == 1 and fpint == 2:
                    newalt[idxown], traf.cr.altactive[idxown] = rs.reso4(idxown)  # temporarily level off strategy
                    # TODO
                    # stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso4: temporarily level off strategy")

                # ownship is descending and intruder is cruising
                elif fpown == 2 and fpint == 0:
                    if rlayerown:
                        newgs[idxown], newvs[idxown], newalt[idxown] = rs.reso3(idxown, fpown)  # Hover in the resolution layer strategy
                        stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso3: hover in the resolution layer strategy")
                    else:
                        if not conflictProbe(ownship, intruder, idxown, idxint, dtlook=traf.dtlookdown[idxown],
                                             targetVs=traf.perf.vsmin[idxown]):
                            newgs[idxown], newvs[idxown], newalt[idxown] = rs.reso7(idxown, fpown)  # use the descend into resolution layer + hover resolution strategy
                            stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso7: descend into resolution layer + hover resolution strategy")
                        else:
                            newalt[idxown], traf.cr.altactive[idxown] = rs.reso4(idxown)  # temporarily level off strategy
                            # TODO
                            # stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso4: temporarily level off strategy")

                # ownship is descending and intruder is climbing
                elif fpown == 2 and fpint == 1:
                    newalt[idxown], traf.cr.altactive[idxown] =rs.reso4(idxown)  # temporarily level off strategy
                    # TODO
                    # stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso4: temporarily level off strategy")

                # ownship is descending and intruder is descending
                elif fpown == 2 and fpint == 2:
                    newvs[idxown] = rs.reso8(idxown, idxint, fpown)  # velocity matching in the vertical direction
                    stack.stack(f"ECHO {traf.id[idxown]} is resolving conflict with {traf.id[idxint]} using reso8: velocity matching in the vertical direction")
                else:
                    print("ERROR: THE FLIGHT PHASE HAS BEEN COMPUTED WORNGLY. CHECK THE flightphase PLUGIN ")

        for confidxs in MACC:
            for i in range(1, len(confidxs)):
                # Add the intruder into resoidint if not already in there
                if traf.id[confidxs[0]] not in traf.resoidint[confidxs[i]]:
                    # append the intruder callsigns that ownship is currently resolving in traf.resoidint
                    traf.resoidint[confidxs[i]].append(traf.id[confidxs[0]])

                newgs[confidxs[i]], newvs[confidxs[i]], newalt[confidxs[i]] = rs.reso9(confidxs[i], confidxs[0])
            stack.stack(f"ECHO {' & '.join(list(map(traf.id.__getitem__, confidxs[1:])))} are resolving conflict with {traf.id[confidxs[0]]} using reso9: multi aircraft conflict")

            ################### END CR Strategy Switch ###################

        return newtrk, newgs, newvs, newalt

    def resumenav(self, conf, ownship, intruder):
        '''
            NOTE: This function overrides the resumenav defined in ConflictResolution
            Decide for each aircraft in the conflict list whether the ASAS
            should be followed or not, based on if the aircraft pairs passed
            their CPA.
        '''

        # Add new conflicts to resopairs and confpairs_all and new losses to lospairs_all
        self.resopairs.update(conf.confpairs)

        # Conflict pairs to be deleted
        delpairs = set()
        changeactive = dict()

        # Look at all conflicts, also the ones that are solved but CPA is yet to come
        for conflict in self.resopairs:
            idx1, idx2 = traf.id2idx(conflict)
            # If the ownship aircraft is deleted remove its conflict from the list
            if idx1 < 0:
                delpairs.add(conflict)
                continue

            if idx2 >= 0:
                rpz = max(conf.rpz[idx1], conf.rpz[idx2])
                hpz = max(conf.hpz[idx1], conf.hpz[idx2])
                # Distance vector using flat earth approximation
                re = 6371000.
                dist = re * np.array([np.radians(intruder.lon[idx2] - ownship.lon[idx1]) *
                                      np.cos(0.5 * np.radians(intruder.lat[idx2] +
                                                              ownship.lat[idx1])),
                                      np.radians(intruder.lat[idx2] - ownship.lat[idx1])])

                # Relative velocity vector
                vrel = np.array([intruder.gseast[idx2] - ownship.gseast[idx1],
                                 intruder.gsnorth[idx2] - ownship.gsnorth[idx1]])

                # Check if conflict is past CPA
                past_cpa = np.dot(dist, vrel) > 0.0

                # hor_los:
                # Aircraft should continue to resolve until there is no horizontal
                # LOS. This is particularly relevant when vertical resolutions are used.
                hdist = np.linalg.norm(dist)
                hor_los = hdist < rpz

                # LOS
                # if LOS, then its too late. Don't resolve, just continue! This is better for metrics.
                dalt = traf.alt[idx2] - traf.alt[idx1]
                ver_los = (np.abs(dalt) < hpz)
                swlos = hor_los * ver_los

                # New: determine priority of the idx1 (ownship) in conflict
                idx1Resolves = self.priorityChecker(idx1, idx2)




                # boolean to maintain sufficient distance for speed resolution
                if traf.resostrategy[idx1] == "RESO2" or traf.resostrategy[idx1] == "RESO5" or traf.resostrategy[idx1] == "RESO9":
                    distnotok = (hdist < rpz * 2.0)
                elif traf.resostrategy[idx1] == "RESO8":
                    distnotok = dalt < traf.layerHeight

                # make sure AC continues flying in reso layer until sufficient horizontal separation, regardless of the vertical separation
                elif traf.resostrategy[idx1] == "RESO1":
                    distnotok = (hdist < rpz * 2.0)
                    ver_los = distnotok
                else:
                    distnotok = False

                # For reso5, it is necessary to wait until the aircraft are separated horizontally before recovering, regardless of the vertical separation.
                if traf.resostrategy[idx1] == "RESO5" and traf.flightphase[idx2] == 1 and traf.alt[idx1] < traf.alt[
                    idx2]:
                    distnotok = ver_los
                    past_cpa = not ver_los
                elif traf.resostrategy[idx1] == "RESO5" and traf.flightphase[idx2] == 2 and dalt <= -2 * traf.layerHeight:
                    distnotok = ver_los
                    past_cpa = not ver_los

                # only for reso6 and reso7:
                if (traf.resostrategy[idx1] == "RESO6" or traf.resostrategy[idx1] == "RESO7") and idx1Resolves:
                    iwpid = traf.ap.route[idx1].findact(idx1)
                    # detremine if continuing the vertical climb/descend is ok
                    if traf.ap.route[idx1].wpalt[iwpid] - traf.alt[idx1] > 0:  # then climbing
                        reso67probe = conflictProbe(ownship, intruder, idx1, dtlook=traf.dtlookup[idx1],
                                                    targetVs=traf.perf.vsmax[idx1])
                    else:  # descending
                        reso67probe = conflictProbe(ownship, intruder, idx1, dtlook=traf.dtlookdown[idx1],
                                                    targetVs=traf.perf.vsmin[idx1])
                    if not reso67probe:
                        past_cpa = True

                # If both aircraft are hovering, then its neessary to force them to continue to solve the conflict
                if traf.gs[idx1] == 0 and traf.gs[idx2] == 0 and traf.vs[idx1] == 0 and traf.vs[idx2] == 0:
                    past_cpa = True

            # Start recovery for ownship if intruder is deleted, or if past CPA
            # and not in horizontal LOS or a bouncing conflict. New: check idx1Resolves
            if idx2 >= 0 and (not past_cpa or (distnotok and ver_los)):  # and not swlos:
                # Enable ASAS for this aircraft
                changeactive[idx1] = True
            else:
                # Switch ASAS off for ownship if there are no other conflicts
                # that this aircraft is involved in.
                changeactive[idx1] = changeactive.get(idx1, False)
                # If conflict is solved, remove it from the resopairs list
                delpairs.add(conflict)
                # NEW: Once the conflict with idx2 is resolved, remove idx2 from resoidint
                if traf.id[idx2] in traf.resoidint[idx1]:
                    traf.resoidint[idx1].remove(traf.id[idx2])

        # Remove pairs from the list that are past CPA or have deleted aircraft
        self.resopairs -= delpairs

        # Update active and intent of each aircraft that are doing a resolution
        for idx, active in changeactive.items():
            # Loop a second time: this is to avoid that ASAS resolution is
            # turned off for an aircraft that is involved simultaneously in
            # multiple conflicts, where the first, but not all conflicts are
            # resolved.
            self.active[idx] = active

        # Trajectory after the original conflict is finished and update intent
        for idx in np.where(self.active == False)[0]:
            # Because active is false, switch off all the asas channels


            # Waypoint recovery after conflict: Find the next active waypoint
            # and send the aircraft to that waypoint, but only if conflict probe is False.
            iwpid = traf.ap.route[idx].findact(idx)

            if iwpid > -1 and traf.resostrategy[idx] != "None":  # To avoid problems if there are no waypoints
                # Get the max and min vertical speed of ownship (needed for conflict probe)
                vsMinOwn = traf.perf.vsmin[idx]
                vsMaxOwn = traf.perf.vsmax[idx]
                # determine the look-ahead for the conflict probe
                dtlookup = np.abs(traf.layerHeight / vsMaxOwn)
                dtlookdown = np.abs(traf.layerHeight / vsMinOwn)

                if traf.resostrategy[idx] == "RESO1":
                    # If it is safe to descend back to the cruising altitude, then do so!
                    if not conflictProbe(ownship, intruder, idx, dtlook=traf.dtlookdown[idx],
                                         targetVs=traf.perf.vsmin[idx]):
                        traf.resostrategy[idx] = "None"
                        traf.cr.hdgactive[idx] = False
                        traf.cr.tasactive[idx] = False
                        traf.cr.altactive[idx] = False
                        traf.cr.vsactive[idx] = False
                    else:
                        # keep flying the resolution altitude
                        traf.ap.alt[idx] = traf.resoalt[idx]
                        traf.selalt[idx] = traf.resoalt[idx]
                        # TODO: Add speed command of previous wpt (for turns)

                elif traf.resostrategy[idx] == "RESO2":
                    # if it is safe to resmue the original speed, go for it!
                    if not conflictProbe(ownship, intruder, idx, targetGs=traf.recoveryspd[idx]):
                        traf.resostrategy[idx] = "None"
                        traf.cr.hdgactive[idx] = False
                        traf.cr.tasactive[idx] = False
                        traf.cr.altactive[idx] = False
                        traf.cr.vsactive[idx] = False

                elif traf.resostrategy[idx] == "RESO3" or traf.resostrategy[idx] == "RESO6" or traf.resostrategy[
                    idx] == "RESO7":
                    # conflict probe direction depends on whether the aircraft
                    # was climbing or descending before the conflict
                    if traf.ap.route[idx].wpalt[iwpid] - traf.alt[idx] > 0:  # then climbing
                        reso3probe = conflictProbe(ownship, intruder, idx, dtlook=traf.dtlookup[idx],
                                                   targetVs=traf.perf.vsmax[idx])
                    else:  # descending
                        reso3probe = conflictProbe(ownship, intruder, idx, dtlook=traf.dtlookdown[idx],
                                                   targetVs=traf.perf.vsmin[idx])
                    # if it is safe to resume climb/descend, then resume climb/descend!
                    if not reso3probe:
                        traf.resostrategy[idx] = "None"
                        traf.cr.hdgactive[idx] = False
                        traf.cr.tasactive[idx] = False
                        traf.cr.altactive[idx] = False
                        traf.cr.vsactive[idx] = False
                        stack.stack(f"ALT {traf.id[idx]} {traf.ap.route[idx].wpalt[iwpid] / ft}")
                        stack.stack(
                            f"ATALT {traf.id[idx]} {traf.ap.route[idx].wpalt[iwpid] / ft} LNAV {traf.id[idx]} ON")
                        stack.stack(
                            f"ATALT {traf.id[idx]} {traf.ap.route[idx].wpalt[iwpid] / ft} VNAV {traf.id[idx]} ON")
                    else:
                        # keep hovering
                        traf.ap.vs[idx] = traf.resovs[idx]
                        traf.ap.tas[idx] = traf.resospd[idx]
                        traf.ap.alt[idx] = traf.resoalt[idx]
                        traf.selalt[idx] = traf.resoalt[idx]

                elif traf.resostrategy[idx] == "RESO5":
                    # If it is safe to descend back to the cruising altitude, then do so!
                    reso5probe = conflictProbe(ownship, intruder, idx, dtlook=traf.dtlookdown[idx],
                                               targetVs=traf.perf.vsmin[idx]) #and conflictProbe(ownship, intruder, idx, targetGs=traf.recoveryspd[idx])
                    if not reso5probe:
                        traf.resostrategy[idx] = "None"
                        traf.cr.hdgactive[idx] = False
                        traf.cr.tasactive[idx] = False
                        traf.cr.altactive[idx] = False
                        traf.cr.vsactive[idx] = False
                    else:
                        # keep flying the resolution altitude
                        traf.ap.alt[idx] = traf.resoalt[idx]
                        traf.selalt[idx] = traf.resoalt[idx]

                elif traf.resostrategy[idx] == "RESO8":
                    if traf.ap.route[idx].wpalt[iwpid] - traf.alt[idx] > 0:  # then climbing
                        reso8probe = conflictProbe(ownship, intruder, idx, dtlook=dtlookup, targetVs=vsMaxOwn)
                    else:  # descending
                        reso8probe = conflictProbe(ownship, intruder, idx, dtlook=dtlookdown, targetVs=vsMinOwn)
                    if not reso8probe:
                        traf.resostrategy[idx] = "None"
                        traf.cr.hdgactive[idx] = False
                        traf.cr.tasactive[idx] = False
                        traf.cr.altactive[idx] = False
                        traf.cr.vsactive[idx] = False
                    else:
                        traf.ap.vs[idx] = traf.resovs[idx]

                elif traf.resostrategy[idx] == "RESO9":
                    if not conflictProbe(ownship, intruder, idx, targetGs=traf.recoveryspd[idx]):
                        traf.resostrategy[idx] = "None"
                        traf.cr.hdgactive[idx] = False
                        traf.cr.tasactive[idx] = False
                        traf.cr.altactive[idx] = False
                        traf.cr.vsactive[idx] = False
                else:
                    traf.resostrategy[idx] = "None"
                    traf.cr.hdgactive[idx] = False
                    traf.cr.tasactive[idx] = False
                    traf.cr.altactive[idx] = False
                    traf.cr.vsactive[idx] = False

            # no waypoints
            else:
                traf.resostrategy[idx] = "None"
                traf.cr.hdgactive[idx] = False
                traf.cr.tasactive[idx] = False
                traf.cr.altactive[idx] = False
                traf.cr.vsactive[idx] = False

    # The four functions below control the four asas channels. These
    @property
    def hdgactive(self):
        ''' Return a boolean array sized according to the number of aircraft
            with True for all elements where heading is currently controlled by
            the conflict resolution algorithm.
        '''
        return traf.resoHdgActive

    @property
    def tasactive(self):
        ''' Return a boolean array sized according to the number of aircraft
            with True for all elements where heading is currently controlled by
            the conflict resolution algorithm.
        '''
        return traf.resoTasActive

    @property
    def altactive(self):
        ''' Return a boolean array sized according to the number of aircraft
            with True for all elements where heading is currently controlled by
            the conflict resolution algorithm.
        '''
        return traf.resoAltActive

    @property
    def vsactive(self):
        ''' Return a boolean array sized according to the number of aircraft
            with True for all elements where heading is currently controlled by
            the conflict resolution algorithm.
        '''
        return traf.resoVsActive


    def pairs(self, conf, ownship, idx):
        '''Returns the indices of confpairs that involve aircraft idx '''

        idx_pairs = np.array([], dtype=int)
        for idx_pair, pair in enumerate(conf.confpairs):
            if traf.flightphase[traf.id2idx(pair[1])] != 0:
                continue
            if ownship.id[idx] == pair[0]:
                idx_pairs = np.append(idx_pairs, idx_pair)

        return idx_pairs

    def priorityChecker(self, idxown, idxint):
        'Determines if the ownship has lower priority and therefore has to resolve the conflict'

        # get the priority of the ownship and intruder from traf
        prioOwn = traf.priority[idxown]
        prioInt = traf.priority[idxint]

        # Compare the priority of ownship and intruder
        if prioOwn < prioInt:  # if ownship has lower priority, then it resolves
            return True

        elif prioOwn == prioInt:  # if both drones have the same priority, the callsign breaks the deadlock

            # get number in the callsign of the ownship and intruder
            numberOwn = int(traf.id[idxown][1:]) # This is a simpler and faster solution if callsigns are of the format 'D12345'
            numberInt = int(traf.id[idxint][1:])

            # The aircraft if the the higher callsign has lower priority, and therefore has to resolve
            if numberOwn > numberInt:
                return True
            else:
                return False

        else:  # if the ownship has higher priority, then it does not resolve
            return False
