import numpy as np

import bluesky as bs
from bluesky import stack
from bluesky.core import Entity
from bluesky.core.simtime import timed_function

def init_plugin():
    ''' Plugin initialisation function. '''

    # initliaze rogue traffic
    roguetraffic = RogueTraffic()
    
    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'rogueaircraft',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config

class RogueTraffic(Entity):

    def __init__(self):
        super().__init__()

        with self.settrafarrays():
            self.rogue_bool = np.array([], dtype=np.bool8)

        bs.traf.roguetraffic = self

    def create(self, n=1):
        super().create(n)

        # default value of rogue bool is always False
        self.rogue_bool[-n:] = False

        return
    
    @staticmethod
    @stack.command
    def crerogue(acid:'txt', actype:'txt', aclat:'lat', aclon:'lon', achdg:'hdg', acalt:'alt', acspd:'spd'):
        '''Create a rogue aircraft.'''
        # First, create aircraft
        bs.traf.cre(acid, actype, aclat, aclon, achdg, acalt, acspd)

        # get the index of the rogue aircraft
        acidx = bs.traf.id2idx(acid)

        # Now set rogue bool to true
        bs.traf.roguetraffic.rogue_bool[acidx] = True
