from random import randint
import numpy as np
import copy
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, sim, settings  # , navdb, sim, scr, tools
from bluesky.tools.aero import ft
import plugins.m2.descendcheck as descendcheck
import plugins.m2.ingeoFence as ingeoFence
import plugins.m2.overshootcheck as overshootcheck
import plugins.m2.etacheck as etacheck
import plugins.geofence as geofence_TUD

### Initialization function of your plugin. Do not change the name of this
### function, as it is the way BlueSky recognises this file as a plugin.
def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    checkstate = checkState()

    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name': 'checkstate',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type': 'sim',
    }

    # init_plugin() should always return a configuration dict.
    return config
#creation of the sta object that will store multiple time related values.
class sta:
    def __init__(
            self,
            time:int,
            sta_dt,
            reroutes: int,
            atd,
            ata,
            atd_dt,
            ata_dt
    ):
        self.time = time  # integer
        self.sta_dt = sta_dt
        self.reroutes = reroutes
        self.atd = atd
        self.atd_datetime = atd_dt
        self.ata = ata
        self.ata_datetime = ata_dt

class checkState(core.Entity):
    ''' Example new entity object for BlueSky. '''

    def __init__(self):
        super().__init__()
        with self.settrafarrays():
            self.startDescend = np.array([], dtype=bool)  # array of booleans to check if descend can start
            self.overshot = np.array([], dtype=bool)
            self.wptdist = np.array([])
            self.ingeofence = np.array([], dtype=bool)
            self.acingeofence = np.array([], dtype=bool)
            self.geoPoly = None
            self.geoDictOld = dict()

            #etacheck
            self.orignwp = np.array([], dtype=int)
            self.sta = np.array([],dtype=object)
            self.eta = np.array([])
            self.delayed = np.array([],dtype=float)
            self.turns = np.array([],dtype=object)
            self.turnspeed = np.array([],dtype=object)


        # update traf
        traf.overshot = self.overshot
        traf.wptdist = self.wptdist
        traf.ingeofence = self.ingeofence
        traf.acingeofence = self.acingeofence
        traf.geoPoly = self.geoPoly
        traf.geoDictOld = self.geoDictOld

        #etacheck
        traf.orignwp = self.orignwp
        traf.sta = self.sta
        traf.eta = self.eta
        traf.delayed = self.delayed
        traf.turns = self.turns
        traf.turnspeed = self.turnspeed

        self.reference_ac = []
    def create(self, n=1):
        ''' This function gets called automatically when new aircraft are created. '''
        # Don't forget to call the base class create when you reimplement this function!
        super().create(n)
        self.startDescend[-n:] = False
        self.overshot[-n:] = False
        self.wptdist[-n:] = 99999
        self.ingeofence[-n:] = False
        self.acingeofence[-n:] = False

        #etacheck
        self.orignwp[-n:] = 0
        self.sta[-n:] = sta(time=0, sta_dt=0, reroutes=0, ata=0, ata_dt=0, atd=0, atd_dt=0)
        self.eta[-n:] = 0
        self.delayed[-n:] = False
        self.turns[-n:] = 0
        self.turnspeed[-n:] = 0

        # update traf
        traf.overshot = self.overshot
        traf.wptdist = self.wptdist
        traf.ingeofence = self.ingeofence
        traf.acingeofence = self.acingeofence
        traf.startDescend = self.startDescend

        #etacheck
        traf.orignwp = self.orignwp
        traf.sta = self.sta
        traf.eta = self.eta
        traf.delayed = self.delayed
        traf.turns = self.turns
        traf.turnspeed = self.turnspeed


    def delete(self, idx):
        super().delete(idx)

        # update traf
        traf.overshot = self.overshot
        traf.wptdist = self.wptdist
        traf.ingeofence = self.ingeofence
        traf.acingeofence = self.acingeofence
        traf.startDescend = self.startDescend

        #etacheck
        traf.orignwp = self.orignwp
        traf.sta = self.sta
        traf.eta = self.eta
        traf.delayed = self.delayed
        traf.turns = self.turns
        traf.turnspeed = self.turnspeed

    def reset(self):
        ''' Reset area state when simulation is reset. '''
        super().reset()
        with self.settrafarrays():
            self.startDescend = np.array([], dtype=bool)  # array of booleans to check if descend can start
            self.overshot = np.array([], dtype=bool)
            self.wptdist = np.array([])
            self.ingeofence = np.array([], dtype=bool)
            self.acingeofence = np.array([], dtype=bool)
            self.geoPoly = None
            self.geoDictOld = dict()

        # update traf
        traf.overshot = self.overshot
        traf.wptdist = self.wptdist
        traf.ingeofence = self.ingeofence
        traf.acingeofence = self.acingeofence
        traf.startDescend = self.startDescend
        traf.geoPoly = self.geoPoly
        traf.geoDictOld = self.geoDictOld

        self.reference_ac = []


    @core.timed_function(name='descendcheck', dt=5)
    def update(self):
        for i in traf.id:
            idx = traf.id2idx(i)

            # ingeofence checker:
            # only run this code if there actually is a geofence somewhere and we are on the way
            if geofence_TUD.Geofence.geo_save_dict != dict() and traf.ap.route[idx].iactwp > 1:

                # update old dict to ensure we only recreate the multipolygon if something changed
                if self.geoDictOld != geofence_TUD.Geofence.geo_save_dict:
                    self.geoDictOld = copy.deepcopy(geofence_TUD.Geofence.geo_save_dict)
                    self.geoPoly = ingeoFence.create_multipoly(geofences=geofence_TUD.Geofence.geo_save_dict)

                routeval, acval = ingeoFence.checker(acid=idx, multiGeofence=self.geoPoly)
                self.ingeofence[idx] = routeval
                self.acingeofence[idx] = acval

                traf.ingeofence = self.ingeofence
                traf.acingeofence = self.acingeofence
                traf.geoPoly = self.geoPoly
                traf.geoDictOld = self.geoDictOld

            # overshoot checker (only if there is a route and we are almost at destination):
            if traf.ap.route[idx].iactwp != -1 and traf.ap.route[idx].iactwp == np.argmax(traf.ap.route[idx].wpname):
                dist = overshootcheck.calc_dist(idx)
                val = overshootcheck.checker(idx, dist)
                self.overshot[idx] = val
                traf.overshot = self.overshot

            #etacheck:
            acid = traf.id2idx(i)
            ac_route = traf.ap.route[acid]

            #TODO check if'jes

            # Check if there is a route.
            if ac_route.iactwp != -1 and ac_route.nwp != 0:

                #First time calculation of the atd
                if self.sta[acid].atd == 0:
                    self.sta[acid].atd = sim.utc.timestamp()
                    self.sta[acid].atd_datetime = etacheck.secToDT(sim.utc.timestamp())

                #First time the last waypoint gets active, the ATA is logged
                if ac_route.iactwp == ac_route.nwp - 1 and self.sta[acid].ata == 0:
                    self.sta[acid].ata = sim.utc.timestamp()
                    self.sta[acid].ata_datetime = etacheck.secToDT(sim.utc.timestamp())

                # First time calculation of STA
                if self.sta[acid].time == 0:
                    self.sta[acid].time = etacheck.calc_eta(acid)
                    self.sta[acid].sta_dt = etacheck.secToDT(self.sta[acid].sta_dt)

                # Keep updating the ETA, until activation of last waypoint.
                if ac_route.iactwp < ac_route.nwp - 1:
                    self.eta[acid] = etacheck.calc_eta(acid)
                    sta = self.sta[acid].time
                    eta = self.eta[acid]
                    diff = sta - eta
                    self.delayed[acid] = diff

                #update Traffic variables
                traf.orignwp = self.orignwp
                traf.sta = self.sta
                traf.eta = self.eta
                traf.delayed = self.delayed


            # Delete the last waypoint at 0ft and 0kts
            if traf.id[idx] not in self.reference_ac and traf.ap.route[idx].iactwp > -1:
                lastwpname = traf.ap.route[idx].wpname[-1]
                stack.stack(f"DELWPT {traf.id[idx]} {lastwpname}")
                self.reference_ac.append(traf.id[idx])

            # TODO: Add speedupdate here
            # if not self.startDescend[idx]:

            # descend checker
            # if for some reason the startDescend boolean is true, but the aircraft was not deleted,
            # then delete the aircraft when it is below 1 ft

            if not self.startDescend[idx] and not traf.loiter.loiterbool[idx] and traf.resostrategy[idx] == 'None':
                self.startDescend[idx] = descendcheck.checker(idx)
            elif traf.alt[idx] < 1.0 * ft:
                stack.stack(f"{traf.id[idx]} DEL")

            traf.startDescend = self.startDescend

    @stack.command
    def echoacgeofence(self, acid: 'acid'):
        ''' Print the if an acid is in conflict with a geofence '''
        geofence = self.getacgeofence(acid)
        return True, f'{traf.id[acid]} geofence conflict {geofence}.'

    def getacgeofence(self, acid: 'acid'):
        ''' return the bool value in ingeofence of a specific acid '''
        val = self.ingeofence[acid]
        return val

    @stack.command
    def echoacovershot(self, acid: 'acid'):
        ''' Print the if an acid is has overshot or not '''
        overshot = self.getacovershot(acid)
        if overshot:
            return True, f'{traf.id[acid]} has overshot.'
        elif not overshot:
            return True, f'{traf.id[acid]} has not overshot.'

    def getacovershot(self, acid: 'acid'):
        ''' return the bool value in ingeofence of a specific acid '''
        val = self.overshot[acid]
        return val

    @stack.command()
    def setturns(self, acid:'acid', *turnid: int):
        ''' set turnid's and turns for acid
            Arguments:
            - acid: aircraft id
            - turnid: one or more waypoint ids that are a turn
        '''
        self.turns[acid] = np.array(turnid)
        traf.turns = self.turns
        return True

    @stack.command()
    def setturnspds(self, acid:'acid', *turnspds: int):
        ''' set turnid's and turns for acid
            Arguments:
            - acid: aircraft id
            - turnspds: turnspeeds corresponding to turns in the order the waypoint ids of setturns were supplied.
        '''
        self.turnspeed[acid] = np.array(turnspds)
        traf.turnspeed = self.turnspeed
        return True
