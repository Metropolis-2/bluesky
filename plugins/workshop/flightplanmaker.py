import json
import numpy as np
import random
import paho.mqtt.client as mqtt
from datetime import datetime
from time import sleep

import bluesky as bs
from bluesky.core import Entity
from bluesky import stack

from plugins.workshop import flightmanager as fm
from plugins.workshop import flighttelemetry as fte

flightplans = None
def init_plugin():
    # Configuration parameters
    global flightplans
    flightplans = FlightPlanMaker()

    config = {
        'plugin_name': 'FLIGHTPLANMAKER',
        'plugin_type': 'sim'
    }
    return config

class FlightPlanMaker(Entity):
    def __init__(self):
        super().__init__()
        
        # Start mqtt client to send flight plans
        self.mqtt_client = MQTTFPClient()
        self.mqtt_client.run()

        with self.settrafarrays():
            self.drone_32bid = np.array([], dtype=np.int32)

    def create(self, n=1):
        super().create(n)
        # get a random 32bit integer ID
        random_int = random.getrandbits(32)

        # make sure it is not already in use, if not keep generating
        while random_int in self.drone_32bid:
            random_int = random.getrandbits(32)

        self.drone_32bid[-n:] = random_int

    def generate_c2c_fp_from_WP(self, acidx, filename=None):
        ''' Generate a C2C flight plan from waypoints. '''
        # TODO: ensure that drone is connected in telemetry before pushning flight plan
        # TODO: change 32bid of plan if old
        
        # Get paparazzi id of this drone
        pprz_id = fm.flightmanager.pprz_ids[acidx]

        flightplan_dict = {}
        flightplan_dict["version"] = "1.0.3"
        flightplan_dict["FlightPlan32bId"] = str(self.drone_32bid[acidx])
        flightplan_dict["FlightPoints"] = []
        # Loop through route and generate fp from and including avoid WP
        for i in range(bs.traf.ap.route[acidx].nwp):
            flightpoint = {}
            flightpoint["Speed"] = bs.traf.ap.route[acidx].wpspd[i]
            flightpoint["Longitude"] = bs.traf.ap.route[acidx].wplon[i]
            flightpoint["Latitude"] = bs.traf.ap.route[acidx].wplat[i]
            flightpoint["AltitudeAMSL"] = bs.traf.ap.route[acidx].wpalt[i]
            flightplan_dict["FlightPoints"].append(flightpoint)

        # send json object to mqtt
        self.mqtt_client.publish(f'control/flightplanupload/{pprz_id}', json.dumps(flightplan_dict))
        sleep(1)

        # Only save to file if filename is given
        if filename is not None:
            filename += '.json' if filename[-5:] != '.json' else ''    
            with open(f'data/flightplans/{filename}', 'w') as f:
                json.dump(flightplan_dict, f, indent=6)

        return


class MQTTFPClient(mqtt.Client):
    def __init__(self):
        super().__init__()
    
    def run(self):
        self.connect("192.168.1.2", 1883, 60)
        rc = self.loop_start()
        return rc

    def stop(self):
        self.loop_stop()


