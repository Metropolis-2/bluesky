""" BlueSky plugin template. The text you put here will be visible
    in BlueSky as the description of your plugin. """
from random import randint
import numpy as np
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf  #, settings, navdb, sim, scr, tools

### Initialization function of your plugin. Do not change the name of this
### function, as it is the way BlueSky recognises this file as a plugin.
def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    example = init_hybrid()

    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'init_hybrid',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config

class init_hybrid(core.Entity):
    ''' Example new entity object for BlueSky. '''
    def __init__(self):
        super().__init__()
        # All classes deriving from Entity can register lists and numpy arrays
        # that hold per-aircraft data. This way, their size is automatically
        # updated when aircraft are created or deleted in the simulation.
        self.start = False

    @core.timed_function(name='init_hybrid', dt=0.5)
    def update(self):
        if self.start == False:
            stack.stack("ASAS HYBRIDCD")
            stack.stack("RESO HYBRIDRESOLUTION")
            stack.stack("SYMBOL")
            stack.stack("casmachthr 0")
            stack.stack("PCALL STREETS")
            stack.stack("IMPL WINDSIM M2WIND")
            #stack.stack("SETM2WIND 3 180")
            stack.stack("LOADGEOJSON open_geofence id height")
            stack.stack("LOADGEOJSON bldg_geofence fid h")
            # stack.stack("STARTM2LOG")
            self.start = True

    def reset(self):
        ''' Reset area state when simulation is reset. '''
        self.start = False
