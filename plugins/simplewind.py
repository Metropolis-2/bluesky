'''Plugin to implement a simple wind effect for the Metropolis 2 project.
It only affects aircraft in the direction of travel.'''

import bluesky as bs
from bluesky.core import Entity, timed_function
from bluesky import stack

def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    wind = SimpleWind()

    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'SimpleWind',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config

class SimpleWind(Entity):
    def __init__(self, magnitude=0, direction=0):
        self.magnitude = magnitude
        self.direction = direction
    @timed_function(name = 'simplewind', dt = bs.settings.simdt, hook=bs.traf.update_groundspeed)
    def applywind(self):
        '''Applies the wind.'''
        print('I work.')
        
    