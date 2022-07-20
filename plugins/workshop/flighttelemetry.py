import paho.mqtt.client as mqtt
import threading
import json
import numpy as np
from datetime import datetime

import bluesky as bs
from bluesky.core import Entity, timed_function
from bluesky import stack
from bluesky.tools.misc import lat2txt, lon2txt

from plugins.workshop import flightmanager as fm

telemetry = None

def init_plugin():
    # Instantiate C2CTelemetry entity
    global telemetry
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
        self.mqtt_client = MQTTTelemetryClient()
        self.mqtt_client.run()
    
        with self.settrafarrays():
            self.last_telemetry_update = []
                    
    def create(self, n=1):
        super().create(n)
        # self.last_telemetry_update[-n:] = datetime.now()

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

    @stack.command
    def connect_pprz_telemetry(self, acid: str, pprz_id: str):
        '''Connect paparazzi telemetry to an existing vehicle'''
        # Make aircraft real and connect to pprz_id
        acidx = bs.traf.id2idx(acid)
        fm.flightmanager.pprz_ids[acidx] = pprz_id
        fm.flightmanager.virtual_ac[acidx] = False
        

    @timed_function(dt=0.05)
    def update(self):
        self.copy_buffers()
        # Check if there are messages and update
        for msg in self.mqtt_msgs:
            if msg['topic'] == 'telemetry':
                # TODO: also extract the 32bit id
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
                # self.last_telemetry_update[acidx] = datetime.now()
                
        self.mqtt_msgs = []
        return

class MQTTTelemetryClient(mqtt.Client):
    def __init__(self):
        super().__init__()

    def on_message(self, mqttc, obj, msg):

        payload = json.loads(msg.payload)
        
        # telemetry message comes in here
        if "telemetry/periodic/" in msg.topic:
            # message topic is "telemetry/periodic/{acid}"

            # extract the pprz_id from the topic and search for it's acidx
            pprz_id = msg.topic.split('/')[-1]
            # search for index in fm.flightmanager.pprz_ids numpy array
            acidx = np.where(fm.flightmanager.pprz_ids == pprz_id)[0] if pprz_id in fm.flightmanager.pprz_ids else None

            # If the aircraft is not connected, ignore the message
            if acidx is not None:
                payload['acid'] = bs.traf.id[acidx[0]]
                payload['topic'] = 'telemetry'

                telemetry.recv_mqtt(payload)
        
    def run(self):
        self.connect("192.168.1.2", 1883, 60)
        self.subscribe("telemetry/periodic/#", 0)
        rc = self.loop_start()
        return rc

    def stop(self):
        self.loop_stop()