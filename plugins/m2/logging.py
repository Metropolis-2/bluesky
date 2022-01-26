import pandas as pd
import numpy as np

# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, traf, settings, sim #, core #, settings, navdb,  scr, tools, stack, sim,
from bluesky.tools import datalog

deleted_aircraft = []

conheader = \
    '#######################################################\n' + \
    'CONF LOG\n' + \
    'Conflict Statistics\n' + \
    '#######################################################\n\n' + \
    'Parameters [Units]:\n' + \
    'Simulation time [s], ' + \
    'AC1 [-], ' + \
    'flightphase AC1 [-], ' + \
    'resolution strategy AC1 [-], ' + \
    'AC2 [-], ' + \
    'flightphase AC2 [-]' + \
    'resolution strategy AC2 [-]\n'


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

ftheader = 'Parameters [Units]:\n' + \
            'Simulation time [s], ' + \
            'Call sign, ' + \
            'Flight time [s]\n'


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
        self.ftlog = datalog.crelog('FTLOG', None, ftheader)
        self.start = False

        with self.settrafarrays():
            self.spawntime = np.array([])

    def create(self, n=1):
        super().create(n)
        self.spawntime[-n:] = sim.simt

    def delete(self, idx):
        if traf.id[idx[0]] not in deleted_aircraft:
            flighttime = sim.simt - self.spawntime[idx[0]]
            self.ftlog.log(traf.id[idx[0]], flighttime)
            deleted_aircraft.append(traf.id[idx[0]])
        super().delete(idx)


    def reset(self):
        ''' Reset area state when simulation is reset. '''
        super().reset()
        self.prevconfpairs = set()
        self.prevlospairs = set()
        self.hybridlog = datalog.crelog('CONFLICTLOG', None, conheader)
        self.loslog = datalog.crelog('LOSLOG', None, losheader)
        self.ftlog = datalog.crelog('FTLOG', None, ftheader)
        self.start = False

    @core.timed_function(name='logging', dt=settings.asas_dt, hook='postupdate')
    def update(self):
        if self.start == False:
            self.hybridlog.start()
            self.loslog.start()
            self.ftlog.start()
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
                self.hybridlog.log(ac1[i], list_pf[traf.flightphase[idx1[i]]], traf.resostrategy[idx1[i]], ac2[i], list_pf[traf.flightphase[idx2[i]]], traf.resostrategy[idx2[i]])
        self.prevconfpairs = set(traf.cd.confpairs)

        lospairs_new = list(set(traf.cd.lospairs) - self.prevlospairs)
        if lospairs_new:
            newlos_unique = {frozenset(pair) for pair in lospairs_new}
            ac1, ac2 = zip(*newlos_unique)
            idx1 = traf.id2idx(ac1)
            idx2 = traf.id2idx(ac2)
            for i in range(len(ac1)):
                self.loslog.log(ac1[i], list_pf[traf.flightphase[idx1[i]]], traf.resostrategy[idx1[i]], ac2[i], list_pf[traf.flightphase[idx2[i]]], traf.resostrategy[idx2[i]])
        self.prevlospairs = set(traf.cd.lospairs)

