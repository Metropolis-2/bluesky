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
            
        bs.traf.virtual_ac = self.virtual_ac
        
    def create(self, n=1):
        super().create(n)
        self.virtual_ac[-1] = False
            
    def convert_to_virtual(self, acidx):
        bs.traf.virtual_ac[acidx] = True
        stack.stack(f'{bs.traf.id[acidx]} LNAV ON')
        return
    
    @timed_function(dt=1.0)
    def check_connections(self):
        now = datetime.now()
        for i in range(bs.traf.ntraf):
            time_diff = now - bs.traf.last_telemetry_update[i]
            # If more than 5 seconds then we convert to virtual aircraft
            if time_diff.total_seconds() > 5:
                self.convert_to_virtual(i)
            