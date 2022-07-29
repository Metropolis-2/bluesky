import numpy as np
import requests
import json
import codecs
import datetime
from datetime import timedelta
from time import sleep
from rich import print

import bluesky as bs
from bluesky.core import Entity, timed_function
from bluesky import stack, settings


settings.set_variable_defaults(
    unifly_base_url="https://portal.eu.unifly.tech",
    active_operators = ['TA', 'TB'],
    operators_dict = {
        'TA': {
                'username'      : 't.lundby+mptesta@unifly.aero',
                'password'      : 'MP2Demo',
                'description'   : 'Test Operator A',
        },
        'TB': {
                'username'      : 't.lundby+mptestb@unifly.aero',
                'password'      : 'MP2Demo',
                'description'   : 'Test Operator B',
        },
        'DA': {
                'username'      : 't.lundby+mpdemoa@unifly.aero',
                'password'      : 'MP2Demo',
                'description'   : 'Demonstration Operator A',
        },
        'DB': {
                'username'      : 't.lundby+mpdemob@unifly.aero',
                'password'      : 'MP2Demo',
                'description'   : 'Demonstration Operator B',
        },
    }
)


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
            self.uuid      = np.array([], dtype=object)
            self.opuid     = np.array([], dtype=object)
            self.airborne  = np.array([], dtype=bool)
            self.ga_flight = np.array([], dtype=bool)
            self.operator  = np.array([], dtype=str)
        
        # get defaults from settings
        self.base_url = settings.unifly_base_url
        self.active_operators  = settings.active_operators
        self.operators_dict = {k: v for k, v in settings.operators_dict.items() if k in self.active_operators}
        
        # go through values and modify 'username' so that '+' and '@' are replaced with %2B and %40
        for key, value in self.operators_dict.items():
            self.operators_dict[key]['username'] = value['username'].replace('+', '%2B')
            self.operators_dict[key]['username'] = value['username'].replace('@', '%40')
        
        print('[blue]Active Operators:')
        print(self.active_operators)
        # Initial authentication
        # TODO: update token id's in a smart way
        self.token_ids = {}
        self.update_authentication()

        # Pull UAS list from Unifly
        self.uas_dict = {}
        self.get_uas_dict()

        # get the pilots from Unifly
        self.pilots_dict = {}
        self.get_pilots_dict()

        # save priorities
        self.priority_levels = ['PRIORITY_GROUP_DEFAULT', 'PRIORITY_GROUP_PRIORITY']

    def create(self, n=1):
        super().create(n)

        # look through uas_dict for the uuid
        acid = bs.traf.id[-1]

        self.uuid[-n:] = self.uas_dict.get(acid, 'None')

        self.opuid[-n:] = ''

        self.airborne[-n:] = False

        self.ga_flight[-n:] = False

        self.operator[-n:] = ''

    # TODO: make it smart and just call when failing
    # TODO: differentiate between operators (A and B)
    def update_authentication(self):
        '''
        Update the authentication tokens for the operators

        Below is a payload example
        payload = 'username=t.lundby%2Bmptesta%40unifly.aero&password=MP2Demo&grant_type=password'
        
        '''

        # get the url and headers
        url = f"{self.base_url}/auth/realms/OperatorPortal/protocol/openid-connect/token"
        headers = {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'application/json',
                        'Authorization': 'Basic YWlyZW5hV2ViUG9ydGFsOg=='
                        }

        # loop through keys of self.users_dict to get authentication tocken
        for key in self.operators_dict:

            # get the username and password
            username = self.operators_dict[key]['username']
            password = self.operators_dict[key]['password']
            
            payload = rf'username={username}&password={password}&grant_type=password'
            # make the request
            response = requests.request("POST", url, headers=headers, data=payload)

            # get the token
            token = response.json()['access_token']

            # save the token
            self.token_ids[key] = token
    
    def get_uas_dict(self):
        ''' Get a dictionary of all uas registered to ussers'''

        # get the url and headers
        url = f"{self.base_url}/api/uases"

        # loop through token_ids to get their uas
        for key in self.token_ids:

            # get the token
            token = self.token_ids[key]

            # headers
            headers = {
                        'Accept': 'application/json',
                        'Authorization': f'Bearer {token}'
                        }

            # make the request
            response = requests.request("GET", url, headers=headers)

            # get the uas
            user_uas_dict = {uas['nickname']: uas['uniqueIdentifier'] for uas in response.json()}

            # get all keys and values and extend self.uas_dict
            self.uas_dict.update(user_uas_dict)

        print('[blue]Active UASes:')
        print(self.uas_dict)

    def get_pilots_dict(self):
        '''
        Get a dictionary of all pilots from all operators. 
        The key is the operator and the value is a list of pilots.
        '''

        # get the url and empty payload
        url = f"{self.base_url}/api/uasoperations/users"

        payload = {}

        # loop through token_ids to get thee pilots
        for key in self.token_ids:
                
            # get the token
            token = self.token_ids[key]

            # headers
            headers = {
                        'Accept': 'application/json',
                        'Authorization': f'Bearer {token}'
                        }

            # make the request
            response = requests.request("GET", url, headers=headers, data=payload)

            # get the pilots of this user
            self.pilots_dict[key] = response.json()

        print('[blue]Active pilots:')
        print(self.pilots_dict)

    @timed_function(dt=120)
    # TODO: delete this when smart
    def update_authentication_timed(self):
        self.update_authentication()

    @stack.command()
    def postuasop(self, acidx : 'acid', operator, alt):

        print(f'[blue]Posting Draft UAS operation for acid: [green]{bs.traf.id[acidx]}[/] with uuid: [blue]{self.uuid[acidx]}')

        # The first step is to get the operator token and assign an operator to each aircraft
        self.operator[acidx] = operator
        operator_token = self.token_ids[self.operator[acidx]]

        # For a draft route we need the coordinates of the route, start time and end time (+10 mins)
        route = bs.traf.ap.route[acidx]
        coordinates = [[lon, lat] for lat, lon in zip(route.wplat, route.wplon)]
        start = datetime.datetime.now()
        end = start + timedelta(minutes=10)
        
        # prepare message for operation
        url = f"{self.base_url}/api/uasoperations/draft"

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

        response = requests.request("POST", url, headers=headers, data=payload)
        op_uuid = response.json()['uniqueIdentifier']
        self.opuid[acidx] = op_uuid

        if response.status_code == 200:
            print(f'[blue]Successfullt posted this operation with operation id: [green]{op_uuid}')

        # sleep for 5 seconds before Publishing the draft operation
        sleep(5)

        print(f'[blue]Publishing UAS operation with opid: [green]{op_uuid}[/] for acid: [green]{bs.traf.id[acidx]}')

        url = f"{self.base_url}/api/uasoperations/{op_uuid}/publish"

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
