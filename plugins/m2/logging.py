import pandas as pd
import numpy as np

# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, traf, stack, sim #, core #, settings, navdb,  scr, tools
from bluesky.tools import datalog
conheader = \
    '#######################################################\n' + \
    'CONF LOG\n' + \
    'Conflict Statistics\n' + \
    '#######################################################\n\n' + \
    'Parameters [Units]:\n' + \
    'Simulation time [s], ' + \
    'AC1 [-], ' + \
    'flightphase AC1 [-], ' + \
    'AC2 [-], ' + \
    'flightphase AC2 [-]\n'


losheader = \
    '#######################################################\n' + \
    'LOS LOG\n' + \
    'LOS Statistics\n' + \
    '#######################################################\n\n' + \
    'Parameters [Units]:\n' + \
    'Simulation time [s], ' + \
    'AC1 [-], ' + \
    'flightphase AC1 [-], ' + \
    'AC2 [-], ' + \
    'flightphase AC2 [-]\n'


def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    Logging = logging()

    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'logging',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config


class logging(core.Entity):
    ''' Example new entity object for BlueSky. '''
    def __init__(self):
        super().__init__()
        self.prevconfpairs = set()
        self.prevlospairs = set()
        self.hybridlog = datalog.crelog('CONFLICTLOG', None, conheader)
        self.loslog = datalog.crelog('LOSLOG', None, losheader)
        self.start = False

    def reset(self):
        ''' Reset area state when simulation is reset. '''
        super().reset()
        self.prevconfpairs = set()
        self.prevlospairs = set()
        self.hybridlog = datalog.crelog('CONFLICTLOG', None, conheader)
        self.loslog = datalog.crelog('LOSLOG', None, losheader)
        self.start = False

    @core.timed_function(name='logging', dt=sim.simdt)
    def update(self):
        if self.start == False:
            self.hybridlog.start()
            self.loslog.start()
            self.start = True


        list_pf = ['cruising/hovering', 'climbing', 'descending']

        # Store statistics for all new conflict pairs
        # Conflict pairs detected in the current timestep that were not yet
        # present in the previous timestep
        confpairs_new = list(set(traf.cd.confpairs) - self.prevconfpairs)
        if confpairs_new:
            newconf_unique = {frozenset(pair) for pair in confpairs_new}
            ac1, ac2 = zip(*newconf_unique)
            idx1 = traf.id2idx(ac1)
            idx2 = traf.id2idx(ac2)
            for i in range(len(ac1)):
                self.hybridlog.log(ac1[i], list_pf[traf.flightphase[idx1][0]], ac2[i], list_pf[traf.flightphase[idx2][0]])
        self.prevconfpairs = set(traf.cd.confpairs)

        lospairs_new = list(set(traf.cd.lospairs) - self.prevlospairs)
        if lospairs_new:
            newlos_unique = {frozenset(pair) for pair in lospairs_new}
            ac1, ac2 = zip(*newlos_unique)
            idx1 = traf.id2idx(ac1)
            idx2 = traf.id2idx(ac2)
            for i in range(len(ac1)):
                self.loslog.log(ac1[i], list_pf[traf.flightphase[idx1][0]], ac2[i], list_pf[traf.flightphase[idx2][0]])
        self.prevlospairs = set(traf.cd.lospairs)

