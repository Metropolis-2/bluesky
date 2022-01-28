from random import randint
import numpy as np
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, sim, settings  # , navdb, sim, scr, tools
from bluesky.tools.aero import ft
import plugins.m2.descendcheck as descendcheck
import plugins.m2.ingeoFence as ingeoFence
import plugins.m2.overshootcheck as overshootcheck



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

        # update traf
        traf.overshot = self.overshot
        traf.wptdist = self.wptdist
        traf.ingeofence = self.ingeofence
        traf.acingeofence = self.acingeofence
        traf.startDescend = self.startDescend

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

        # update traf
        traf.overshot = self.overshot
        traf.wptdist = self.wptdist
        traf.ingeofence = self.ingeofence
        traf.acingeofence = self.acingeofence
        traf.startDescend = self.startDescend


    def delete(self, idx):
        super().delete(idx)

        # update traf
        traf.overshot = self.overshot
        traf.wptdist = self.wptdist
        traf.ingeofence = self.ingeofence
        traf.acingeofence = self.acingeofence
        traf.startDescend = self.startDescend

    def reset(self):
        ''' Reset area state when simulation is reset. '''
        super().reset()
        with self.settrafarrays():
            self.startDescend = np.array([], dtype=bool)  # array of booleans to check if descend can start
            self.overshot = np.array([], dtype=bool)
            self.wptdist = np.array([])
            self.ingeofence = np.array([], dtype=bool)
            self.acingeofence = np.array([], dtype=bool)

        # update traf
        traf.overshot = self.overshot
        traf.wptdist = self.wptdist
        traf.ingeofence = self.ingeofence
        traf.acingeofence = self.acingeofence
        traf.startDescend = self.startDescend

        self.reference_ac = []


    @core.timed_function(name='descendcheck', dt=5)
    def update(self):
        for i in traf.id:
            idx = traf.id2idx(i)
            if traf.priority[idx] != 5:
                # ingeofence checker:
                routeval, acval = ingeoFence.checker(acid=idx)

                self.ingeofence[idx] = routeval
                self.acingeofence[idx] = acval

                traf.ingeofence = self.ingeofence
                traf.acingeofence = self.acingeofence

                # overshoot checker:
                if not self.startDescend[idx]:
                    dist = overshootcheck.calc_dist(idx)
                    val = overshootcheck.checker(idx, dist)
                    self.overshot[idx] = val
                    traf.overshot = self.overshot

                # Delete the last waypoint at 0ft and 0kts
                if traf.id[idx] not in self.reference_ac and traf.ap.route[idx].iactwp > -1:
                    lastwpname = traf.ap.route[idx].wpname[-1]
                    stack.stack(f"DELWPT {traf.id[idx]} {lastwpname}")
                    self.reference_ac.append(traf.id[idx])

                # TODO: Add speedupdate here
                # if not self.startDescend[idx]:

                # descend checker
                if not self.startDescend[idx] and not traf.loiter.loiterbool[idx] and traf.resostrategy[idx] == 'None':
                    self.startDescend[idx] = descendcheck.checker(idx)

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