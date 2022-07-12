from curses.ascii import alt
from termios import VMIN
import bluesky as bs
from bluesky.core import Entity, timed_function
from bluesky import stack

import paho.mqtt.client as mqtt
import threading
import json
import numpy as np

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

        self.acid_updated = None

        self.mqtt_msg_buf = []

        self.mqtt_msgs = []

        # Start mqtt client to read out control commands
        self.mqtt_client = MQTTPPRZTelemetryClient(self)
        self.mqtt_client.run()

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
    def connect_pprz_telemetry(self, acid: str):
        '''Connect paparazzi telemetry to an existing vehicle or create one'''
        # Check if vehicle with vehicle id already exists
        if acid not in bs.traf.id:
            bs.traf.cre(acid, 'M600', 0., 0., 0., 0., 0.)
        self.acid_updated = acid

    @timed_function(dt=0.05)
    def update(self):
        self.copy_buffers()
        # Check if there are messages and update
        for msg in self.mqtt_msgs:
            if msg['topic'] == 'c2c_telemetry':
                lat = msg['Location']['Longitude']
                lon = msg['Location']['Latitude']
                alt = msg['Location']['AltitudeAMSL']
                vn = msg['Speed']['Vn']
                ve = msg['Speed']['Ve']
                vd = msg['Speed']['Vd']
                hdg = np.rad2deg(np.arctan2(ve, vn))
                h_spd = np.sqrt(ve**2 + vn**2)
                if h_spd < 0.1:
                    h_spd = 0.
                bs.traf.move(bs.traf.id2idx(self.acid_updated), lat, lon, alt, hdg, h_spd, vd)
        self.mqtt_msgs = []
        return

class MQTTPPRZTelemetryClient(mqtt.Client):
    def __init__(self, pprz_telem_object):
        super().__init__()
        self.pprz_telem_obj = pprz_telem_object

    def on_message(self, mqttc, obj, msg):
        #print(msg.topic+" "+str(msg.qos)+" "+str(msg.payload))
        if self.pprz_telem_obj.acid_updated == None:
            return
        payload = json.loads(msg.payload)
        if msg.topic == "pprz2bs/c2c_telemetry":
            payload['topic'] = 'c2c_telemetry'
            self.pprz_telem_obj.recv_mqtt(payload)
        
    def run(self):
        self.connect("localhost", 1883, 60)
        self.subscribe("pprz2bs/c2c_telemetry", 0)
        rc = self.loop_start()
        return rc

    def stop(self):
        self.loop_stop()