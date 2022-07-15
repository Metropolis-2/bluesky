import bluesky as bs
from bluesky.core import Entity
from bluesky import stack
import json
import numpy as np
import random
import paho.mqtt.client as mqtt
from time import sleep


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

        with self.settrafarrays():
            self.drone_32bid = np.array([], dtype=bool)

    def create(self, n=1):
        ''' Create is called when new aircraft are created. '''
        super().create(n)

        self.drone_32bid[:-n] = 4

    def generate_c2c_fp_from_WP(self, acidx, filename):
        if '.json' not in filename:
            filename += '.json'
        flightplan_dict = {}
        flightplan_dict["version"] = "1.1.0"
        flightplan_dict["FlightPlan32bId"] = "4"
        flightplan_dict["FlightPoints"] = []
        # Loop through route and generate fp from and including avoid WP
        for i in range(bs.traf.ap.route[acidx].nwp):
            flightpoint = {}
            flightpoint["Longitude"] = bs.traf.ap.route[acidx].wplon[i]
            flightpoint["Latitude"] = bs.traf.ap.route[acidx].wplat[i]
            flightpoint["AltitudeAMSL"] = bs.traf.ap.route[acidx].wpalt[i]
            flightplan_dict["FlightPoints"].append(flightpoint)
            
        with open('data/flightplans/' + filename, 'w') as f:
            # Save with spacing and tabs
            json.dump(flightplan_dict, f, indent=6)

        # send object
        TestSend(flightplan_dict)
        return True

    @stack.command()
    def MAKEFLIGHTPLAN(self, acid: 'acid', fp_file: str):
        self.generate_c2c_fp_from_WP(acid, fp_file)


class MQTTClient(mqtt.Client):
    def __init__(self):
        mqtt.Client.__init__(self)
    
    def run(self):
        self.connect("192.168.1.2", 1883, 60)
        rc = self.loop_start()
        return rc

    def stop(self):
        self.loop_stop()

class TestSend(object):
    def __init__(self, flight_plan_dict):
        self.mqtt_client = MQTTClient()
        self.mqtt_client.run()

        self.fp_dict = flight_plan_dict

        self.send_fp()
    
    def send_fp(self):

        self.mqtt_client.publish('control/flightplanupload/13', json.dumps(self.fp_dict))
        sleep(1)


