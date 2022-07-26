import bluesky as bs
import numpy as np
from bluesky.core import Entity, timed_function
from bluesky import stack

### Initialization function of plugin.
def init_plugin():
    config = {
        'plugin_name':     'UNIFLY',
        'plugin_type':     'sim',
        }

    return config

class Unifly(Entity):
    
    def __init__(self):
        super().__init__()
    
    @timed_function(dt = 1)
    def update(self):
        pass

