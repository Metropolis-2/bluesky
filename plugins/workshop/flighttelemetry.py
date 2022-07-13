from curses.ascii import alt
from socket import MsgFlag
from termios import VMIN
import bluesky as bs
from bluesky.core import Entity, timed_function
from bluesky import stack

import paho.mqtt.client as mqtt
import threading
import json
import numpy as np
from datetime import datetime

from bluesky.tools.misc import lat2txt, lon2txt

def init_plugin():
    # Instantiate C2CTelemetry entity
    telemetry = FlightTelemetry()
    # Configuration parameters
    config = {
        'plugin_name': 'FLIGHTTELEMETRY',
        'plugin_type': 'sim'
    }
    return config

class FlightTelemetry(Entity):
    def __init__(self):
        super().__init__()

        self.lock = threading.Lock()

        self.mqtt_msg_buf = []

        self.mqtt_msgs = []

        # Start mqtt client to read out control commands
        self.mqtt_client = TelemetryClient(self)
        self.mqtt_client.run()

        # Initialize list of real aircraft ids    
        self.real_acids = []
    
        with self.settrafarrays():
            self.last_telemetry_update = []
            
        bs.traf.last_telemetry_update = self.last_telemetry_update
        
    def create(self, n=1):
        super().create(n)
        self.last_telemetry_update[-1] = datetime.now()

    def recv_mqtt(self, payload):
        self.lock.acquire()
        try:
            self.mqtt_msg_buf.append(payload)

        finally:
            self.lock.release()        
    
    def copy_buffers(self):
        self.lock.acquire()
        try:
            for msg in self.mqtt_msg_buf:
                self.mqtt_msgs.append(msg)

            # Empty buffers
            self.mqtt_msg_buf = []
        finally:
            self.lock.release()

    def update_c2c_telemetry(self):
        return

    def connect_pprz_telemetry(self, acid: str):
        '''Connect paparazzi telemetry to an existing vehicle or create one'''
        # Check if vehicle with vehicle id already exists
        if acid not in bs.traf.id:
            bs.traf.cre(acid, 'M600', 0., 0., 0., 0., 0.)

        # Append to list of real aircraft
        self.real_acids.append(acid)
        bs.traf.virtual_ac[bs.traf.id2idx(acid)] = False

    @timed_function(dt=0.05)
    def update(self):
        self.copy_buffers()
        # Check if there are messages and update
        for msg in self.mqtt_msgs:
            if msg['topic'] == 'telemetry':
                lat = msg['Location']['Latitude']
                lon = msg['Location']['Longitude']
                alt = msg['Location']['AltitudeAMSL']
                vn = msg['Speed']['Vn']
                ve = msg['Speed']['Ve']
                vd = msg['Speed']['Vd']
                hdg = np.rad2deg(np.arctan2(ve, vn))
                h_spd = np.sqrt(ve**2 + vn**2)
                if h_spd < 0.1:
                    h_spd = 0.
                acidx = bs.traf.id2idx(msg['acid'])
                bs.traf.move(acidx, lat, lon, alt, hdg, h_spd, -vd)
                bs.traf.last_telemetry_update[acidx] = datetime.now()
                
        self.mqtt_msgs = []
        return

class TelemetryClient(mqtt.Client):
    def __init__(self, pprz_telem_object):
        super().__init__()
        self.pprz_telem_obj = pprz_telem_object

    def on_message(self, mqttc, obj, msg):

        payload = json.loads(msg.payload)
        
        # telemetry message comes in here
        if "telemetry/periodic/" in msg.topic:
            # message topic is "telemetry/periodic/{acid}"
            # extract the acid from the topic
            payload['acid'] = 'R' + msg.topic.split('/')[-1]
            payload['topic'] = 'telemetry'

            # TODO: check here that disconnected drones don't send data
            if payload['acid'] not in self.pprz_telem_obj.real_acids:
                self.pprz_telem_obj.connect_pprz_telemetry(payload['acid'])

            self.pprz_telem_obj.recv_mqtt(payload)
        
    def run(self):
        self.connect("192.168.1.2", 1883, 60)
        self.subscribe("telemetry/periodic/#", 0)
        rc = self.loop_start()
        return rc

    def stop(self):
        self.loop_stop()