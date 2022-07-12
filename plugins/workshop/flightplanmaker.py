import bluesky as bs
from bluesky.core import Entity
from bluesky import stack
import json

from datetime import datetime

def init_plugin():
    # Configuration parameters
    flightplans = FlightPlanMaker()
    config = {
        'plugin_name': 'FLIGHTPLANMAKER',
        'plugin_type': 'sim'
    }
    return config

class FlightPlanMaker(Entity):
    def __init__(self):
        super().__init__()

    def create(self, n=1):
        ''' Create is called when new aircraft are created. '''
        super().create(n)
        self.c2c_fp_loaded[-n:] = False

    def generate_c2c_fp_from_WP(self, acidx, filename):
        message_dict = {}
        message_dict["conflicting_id"] = "gca-paparazzi-1"
        message_dict["timestamp"] =  datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" # current date and time in UTC.strftime("%Y-%m-%dT%H:%M:%S.$f") # current date and time in UTC
        #message_dict["timestamp"] = "2022-02-16T17:02:17.000Z"
        flightplan_dict = {}
        flightplan_dict["version"] = "1.1.0"
        flightplan_dict["FlightPoints"] = []
        # Loop through route and generate fp from and including avoid WP
        for i in range(bs.traf.ap.route[acidx].nwp):
            flightpoint = {}
            flightpoint["Longitude"] = bs.traf.ap.route[acidx].wplon[i]
            flightpoint["Latitude"] = bs.traf.ap.route[acidx].wplat[i]
            flightpoint["AltitudeAMSL"] = bs.traf.ap.route[acidx].wpalt[i]
            flightplan_dict["FlightPoints"].append(flightpoint)
            
        message_dict["flightplan"] = json.dumps(flightplan_dict) + '\n'
        with open(filename, 'w') as f:
            # Save with spacing and tabs
            json.dump(flightplan_dict, f, indent=6)
        return message_dict

    @stack.command()
    def MAKEFLIGHTPLAN(self, acid: 'acid', fp_file: str):
        self.generate_c2c_fp_from_WP(acid, fp_file)