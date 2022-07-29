import bluesky as bs
import numpy as np
from bluesky.core import Entity, timed_function
from bluesky import stack
import requests
import json
import codecs
import datetime
from datetime import timedelta
from time import sleep
from rich import print

### Initialization function of plugin.
def init_plugin():
    uniplugin = Unifly()

    config = {
        'plugin_name':     'UNIFLY',
        'plugin_type':     'sim',
        }

    return config

class Unifly(Entity):
    
    def __init__(self):
        super().__init__()

        with self.settrafarrays():
            self.uuid = []
            self.opuid = []
            self.airborne = np.array([], dtype=bool)
            self.ga_flight = np.array([], dtype=bool)
            self.operator = np.array([], dtype=str)
        
        # Initial authentication
        # TODO: implememnt a way to differentiate between operators (A and B)
        # TODO: update token id's in a smart way
        self.update_authentication()

        # Pull UAS list from Unifly
        self.get_uas_dict()

        # get the pilots from Unifly
        self.get_pilot_dicts()

        # save priorities
        self.priority_levels = ['PRIORITY_GROUP_DEFAULT', 'PRIORITY_GROUP_PRIORITY']

    def create(self, n=1):
        super().create(n)

        # look through uas_dict for the uuid
        acid = bs.traf.id[-1]

        self.uuid[-1] = self.uas_dict.get(acid, 'None')

        self.opuid[-1] = ''

        self.airborne[-n:] = False

        self.ga_flight[-n:] = False

        self.operator[-n:] = ''


    @stack.command()
    def postuasop(self, acidx : 'acid', operator, alt):

        print(f'Posting UAS operation for {bs.traf.id[acidx]}')
        print(f'With uuid: {self.uuid[acidx]}')

        self.operator[acidx] = operator
        operator_token = self.token_ids[self.operator[acidx]]

        # get route 
        route = bs.traf.ap.route[acidx]

        # make list of coordinates with wplat wplon
        coordinates = [[lon, lat] for lat, lon in zip(route.wplat, route.wplon)]

        # get datetime.now() anc convert to iso format
        start = datetime.datetime.now()

        # add 10 minutes to now
        end = start + timedelta(minutes=10)

        url = "https://portal.eu.unifly.tech/api/uasoperations/draft"

        payload = json.dumps({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
        },
        "properties": {
            "geoZone": {
            "startTime": start.strftime("%Y-%m-%dT%H:%M:%S+02:00"),
            "endTime": end.strftime("%Y-%m-%dT%H:%M:%S+02:00"),
            "name": "GCS Test operation",
            "lowerLimit": {
                "altitude": 0,
                "unit": "M",
                "reference": "GND",
                "isMostAccurate": False
            },
            "upperLimit": {
                "altitude": alt,
                "unit": "M",
                "reference": "GND",
                "isMostAccurate": False
            }
            },
            "buffer": 2,
            "takeOffPosition": {
            "longitude": coordinates[0][0],
            "latitude": coordinates[0][1]
            },
            "landPosition": {
            "longitude": coordinates[-1][0],
            "latitude": coordinates[-1][1]
            },
            "additionalInformation": "Description for the UAS operation",
            "crew": {
            "contact": {
                "lastName": "Metropolis 2",
                "firstName": "Test Operator A",
                "email": "t.lundby+mptesta@unifly.aero",
                "name": "Metropolis 2 Test Operator A"
            },
            "pilot": "0d03e61b-411f-43b1-8862-8f241b6f49f1"
            },
            "rulesetCode": "DEMO",
            "priorityGroup": "PRIORITY_GROUP_DEFAULT",
            "uases": [
            self.uuid[acidx]
            ],
            "metaData": {
            "lineOfSightType": "VLOS"
            }
        }
        })

        headers = {
        'Content-Type': 'application/vnd.geo+json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {operator_token}'
        }

        # save payload as json
        with open('A1.json', 'w') as f:
            f.write(payload)


        response = requests.request("POST", url, headers=headers, data=payload)

        sleep(5)
        
        op_uuid = response.json()['uniqueIdentifier']
        self.opuid[acidx] = op_uuid

        print(f'UAS operation opid: {op_uuid} for {bs.traf.id[acidx]}')

        url = f"https://portal.eu.unifly.tech/api/uasoperations/{op_uuid}/publish"

        payload = ""
        headers = {
        'Content-Type': 'application/vnd.geo+json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {operator_token}'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        
        sleep(2)

        url = f"https://portal.eu.unifly.tech/api/uasoperations/{op_uuid}/actionItems"

        payload={}

        response = requests.request("GET", url, headers=headers, data=payload)

        print('-----permission requests-------')
        # TODO: response may fail in case list do a type check
        if response.json()[0]['status'] == 'INITIATED' and response.json()[0]['type'] == 'PERMISSION':
            action_uuid = response.json()[0]['uniqueIdentifier']


            # now submit permission request
            url = f"https://portal.eu.unifly.tech/api/uasoperations/{op_uuid}/permissions/{action_uuid}/request"

            now = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
            print(now)

            payload_key_meta = {
            'uniqueIdentifier': '{{'+action_uuid+'}}',
            'additionalData': {},
            'permissionRemark': {
                'message': {
                'message': 'test',
                'timestamp': now
                }
            }
            }
            files = []
            boundary = 'wL36Yn8afVp8Ag7AmP8qZ0SA4n1v9T'
            dataList = []
            dataList.append(codecs.encode(f'--{boundary}'))
            dataList.append(codecs.encode('Content-Disposition: form-data; name=meta;'))
            dataList.append(codecs.encode('Content-Type: {}'.format('application/json')))
            dataList.append(codecs.encode(''))
            dataList.append(codecs.encode(json.dumps(payload_key_meta)))
            dataList.append(codecs.encode(f'--{boundary}--'))
            dataList.append(codecs.encode(''))
            payload = b'\r\n'.join(dataList)

            headers = {
            'Authorization': f'Bearer {operator_token}',
            'Content-type': f'multipart/form-data; boundary={boundary}'
            }
            response = requests.request("POST", url, headers=headers, data=payload, files=files)        
    
    @stack.command()
    def posttakeoff(self, acidx : 'acid'):

        # TODO: take off real drones around this time from fligtmanaget
        # stack.stack('takeoffac', acidx)
        operator_token = self.token_ids[self.operator[acidx]]
        
        # get route 
        route = bs.traf.ap.route[acidx]

        # make list of coordinates with wplat wplon
        coordinates = [[lon, lat] for lat, lon in zip(route.wplat, route.wplon)]
        
        opuid = self.opuid[acidx]
        uuid = self.uuid[acidx]

        url = f"https://portal.eu.unifly.tech/api/uasoperations/{opuid}/uases/{uuid}/takeoff"

        payload = json.dumps({
        "startTime": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+02:00"),
        "pilotLocation": {
            "longitude": coordinates[0][0],
            "latitude": coordinates[0][1]
        }
        })
        headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {operator_token}',
        'content-type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        print(response.text)

        self.airborne[acidx] = True

        print(f"{bs.traf.id[acidx]} is airborne")

    def postnewflightplan(self, acidx : 'acid'):
        pass

    def blueskysendsalert(self, acidx : 'acid'):
        pass

    @stack.command()
    def postgaflight(self, acidx : 'acid'):
        # TODO: test
        # get route 
        route = bs.traf.ap.route[acidx]
        self.ga_flight[acidx] = True

        # TODO: finish this

        # make list of coordinates with wplat wplon
        coordinates = [[lon, lat] for lat, lon in zip(route.wplat, route.wplon)]

        url = "https://portal.eu.unifly.tech/api/tracking"

        payload = json.dumps({
        "apiKey": "TUD_Kp37f9R",
        "identification": "78AF18",
        "callSign": "DOC99",
        "timestamp":  datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+02:00"),
        "vehicleType": "AIRPLANE",
        "location": {
            "longitude": coordinates[0][0],
            "latitude": coordinates[0][1]
        },
        "altitude": {
            "altitude": 0,
            "unit": "ft",
            "reference": "MSL"
        },
        "heading": {
            "trueHeading": 90
        },
        "aircraftData": {
            "groundSpeed": 0
        }
        })
        headers = {
        'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        print(response.text)

        # triger timed function to send emergency message every second with updated position, hdg, gs, altitude

    @timed_function(dt=1)
    def posttelemetry(self):

        # TODO: updated position, hdg, gs, altitude
        # TODO : make sure route is available at beginning of scenario

        # if GA emergency vehicle use postemergency api, for that one scenario
        
        for acidx, acid in enumerate(bs.traf.id):

            opuid = self.opuid[acidx]
            uuid = self.uuid[acidx]
            
            url = f"https://portal.eu.unifly.tech/api/uasoperations/{opuid}/uases/{uuid}/track"

            # if route is empty continue
            if bs.traf.ap.route[acidx].wplat == [] or not self.airborne[acidx]:
                continue

            operator_token = self.token_ids[self.operator[acidx]]

            route = bs.traf.ap.route[acidx]

            # make list of coordinates with wplat wplon
            coordinates = [[lon, lat] for lat, lon in zip(route.wplat, route.wplon)]

            payload = json.dumps({
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+02:00"),
            "location": {
                "longitude": coordinates[0][0],
                "latitude": coordinates[0][1]
            },
            "altitudeMSL": 35,
            "altitudeAGL": 20,
            "heading": 90,
            "speed": 5
            })
            headers = {
            'Authorization': f'Bearer {operator_token}',
            'content-type': 'application/json'
            }

            response = requests.request("POST", url, headers=headers, data=payload)

            print('Telemetry for ' + acid )
            print(response.status_code)

    @stack.command()
    def postlanding(self, acidx : 'acid'):

        # TODO: take off real drones around this time from fligtmanaget
        # stack.stack('takeoffac', acidx)
        operator_token = self.token_ids[self.operator[acidx]]
        # get route 
        route = bs.traf.ap.route[acidx]

        # make list of coordinates with wplat wplon
        coordinates = [[lon, lat] for lat, lon in zip(route.wplat, route.wplon)]
        
        opuid = self.opuid[acidx]
        uuid = self.uuid[acidx]

        url = f"https://portal.eu.unifly.tech/api/uasoperations/{opuid}/uases/{uuid}/landing"

        payload = json.dumps({
        "endTime": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+02:00"),
        "pilotLocation": {
            "longitude": coordinates[0][0],
            "latitude": coordinates[0][1]
        }
        })
        headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {operator_token}',
        'content-type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        print(response.text)

        self.airborne[acidx] = False
        
        print(f"{bs.traf.id[acidx]} has landed")


    # TODO: make it smart and just call when failing
    # TODO: differentiate between operators (A and B)
    def update_authentication(self):
        url = "https://portal.eu.unifly.tech/auth/realms/OperatorPortal/protocol/openid-connect/token"
        payload_a = 'username=t.lundby%2Bmptesta%40unifly.aero&password=MP2Demo&grant_type=password'
        headers = {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'application/json',
                        'Authorization': 'Basic YWlyZW5hV2ViUG9ydGFsOg=='
                        }
        response_a = requests.request("POST", url, headers=headers, data=payload_a)

        payload_b = 'username=t.lundby%2Bmptestb%40unifly.aero&password=MP2Demo&grant_type=password'
        response_b = requests.request("POST", url, headers=headers, data=payload_b)

        self.acces_token_a, self.acces_token_b = response_a.json()['access_token'], response_b.json()['access_token']

        self.token_ids = {'A': self.acces_token_a, 'B': self.acces_token_b}
    
    @timed_function(dt=120)
    # TODO: delete this when smart
    def update_authentication_timed(self):
        self.update_authentication()

    def get_uas_dict(self):
        url = "https://portal.eu.unifly.tech/api/uases"

        payload={}
        headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {self.acces_token_a}'
        }

        response_a = requests.request("GET", url, headers=headers, data=payload)
        # response comes as a list of json objects. We need to extract the nickname and the uniqueIdentifier.
        # make a dictionary with the nickname as key and the uniqueIdentifier as value
        uas_dict_a = {uas['nickname']: uas['uniqueIdentifier'] for uas in response_a.json()}


        headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {self.acces_token_b}'
        }

        response_b = requests.request("GET", url, headers=headers, data=payload)
        uas_dict_b = {uas['nickname']: uas['uniqueIdentifier'] for uas in response_b.json()}

        # join two dictionaries
        self.uas_dict = {**uas_dict_a, **uas_dict_b}

        print(f'Active UAS dict: {self.uas_dict}')

    def get_pilot_dicts(self):
        url = "https://portal.eu.unifly.tech/api/uasoperations/users"

        payload={}
        headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {self.acces_token_a}'
        }

        response_a = requests.request("GET", url, headers=headers, data=payload)
        # response comes as a list of json objects. We need to extract the nickname and the uniqueIdentifier.
        # make a dictionary with the nickname as key and the uniqueIdentifier as value
        pilot_dict_a = response_a.json()


        headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {self.acces_token_b}'
        }

        response_b = requests.request("GET", url, headers=headers, data=payload)
        # response comes as a list of json objects. We need to extract the nickname and the uniqueIdentifier.
        # make a dictionary with the nickname as key and the uniqueIdentifier as value
        pilot_dict_b = response_b.json()

        # join two dictionaries
        # TODO: build these correctly
        self.pilot_dict = {}


# TODO: make class operator A and B
# class Operator:
#     def __init__(self, id) -> None:

#         self.id = id

#         self.access_token = ''


#     def update_authentication(self):
#         url = "https://portal.eu.unifly.tech/auth/realms/OperatorPortal/protocol/openid-connect/token"
#         payload_a = 'username=t.lundby%2Bmptesta%40unifly.aero&password=MP2Demo&grant_type=password'
#         headers = {
#                         'Content-Type': 'application/x-www-form-urlencoded',
#                         'Accept': 'application/json',
#                         'Authorization': 'Basic YWlyZW5hV2ViUG9ydGFsOg=='
#                         }
#         response_a = requests.request("POST", url, headers=headers, data=payload_a)

#         payload_b = 'username=t.lundby%2Bmptestb%40unifly.aero&password=MP2Demo&grant_type=password'
#         response_b = requests.request("POST", url, headers=headers, data=payload_b)

#         self.acces_token_a, self.acces_token_b = response_a['access_token'], response_b['access_token']
