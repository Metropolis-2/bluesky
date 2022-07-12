import bluesky as bs
from bluesky.core import Entity, timed_function
from bluesky import stack
from bluesky.tools.aero import ft
from bluesky.tools.geo import qdrdist

import numpy as np

import json

from datetime import datetime

def init_plugin():
    # Configuration parameters
    flightplans = FlightManager()
    config = {
        'plugin_name': 'FLIGHTMANAGER',
        'plugin_type': 'sim'
    }
    return config

class FlightManager(Entity):
    def __init__(self):
        super().__init__()
        
        with self.settrafarrays():
            self.virtual_ac = np.array([])
            
    def convert_to_virtual(self, acid):
        pass
            