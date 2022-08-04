import numpy as np
import requests
import json
import codecs
import datetime
from datetime import timedelta
from time import sleep

try:
    from rich import print
    from rich.console import Console

except ImportError:
    class Console:
        def rule(self, style=None, title=None, **kwargs):
            print(title)

console = Console()

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
            
            # prep payload, make request and get token and save
            payload = f'username={username}&password={password}&grant_type=password'
            response = requests.request("POST", url, headers=headers, data=payload)
            token = response.json()['access_token']
            self.token_ids[key] = token
    
    def get_uas_dict(self):
        ''' Get a dictionary of all uas registered to ussers'''

        # get the url and headers
        url = f"{self.base_url}/api/uases"

        # loop through token_ids to get their uas
        for key in self.token_ids:

            # get saved token, make request, get uas dict and save
            token = self.token_ids[key]
            headers = {
                        'Accept': 'application/json',
                        'Authorization': f'Bearer {token}'
                        }
            response = requests.request("GET", url, headers=headers)
            user_uas_dict = {uas['nickname']: uas['uniqueIdentifier'] for uas in response.json()}
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
                
            # get the saved token, make request, get pilots dict and save
            token = self.token_ids[key]
            headers = {
                        'Accept': 'application/json',
                        'Authorization': f'Bearer {token}'
                        }
            response = requests.request("GET", url, headers=headers, data=payload)
            self.pilots_dict[key] = response.json()

        print('[blue]Active pilots:')
        print(self.pilots_dict)

    @timed_function(dt=120)
    # TODO: delete this when smart
    def update_authentication_timed(self):
        self.update_authentication()

    @stack.command()
    def postuasop(self, acidx : 'acid', operator, alt):
        '''
        Post a UAS to an operator.

        Requires three request POSTS:
        1. POST draft operation
        2. POST publish operation
        3. POST check for any action items
        4. If action items permissions, POST permission
        
        '''

        # get the acid
        acid = bs.traf.id[acidx]
        
        # print some stuff
        console.rule(style='green', title=f'[bold blue]Posting UAS operation for aircraft with acid:[bold green] {acid}')
        print(f'[blue]Posting draft operation for acid: [green]{acid}[/] with uuid: [green]{self.uuid[acidx]}')

        # The first step is to get the operator token and assign an operator to each aircraft
        self.operator[acidx] = operator
        operator_token = self.token_ids[self.operator[acidx]]

        # For a draft route we need the coordinates of the route, start time and end time (+10 mins)
        route = bs.traf.ap.route[acidx]
        coordinates = [[lon, lat] for lat, lon in zip(route.wplat, route.wplon)]
        start = datetime.datetime.now()
        end = start + timedelta(minutes=10)

        # get the contact information for the uas from self.pilots_dict
        pilot_contact = self.pilots_dict[operator][0]['contact']
        pilot_uuid = self.pilots_dict[operator][0]['user']

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
            "contact": pilot_contact,
            "pilot": pilot_uuid,
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

        if response.status_code == 200:
            op_uuid = response.json()['uniqueIdentifier']
            self.opuid[acidx] = op_uuid
            print(f'[blue]Successfully posted draft operation for acid [green]{acid}[/] with operation id: [green]{op_uuid}')
        else:
            console.rule(style='red')
            print(f'[red]Failed to post draft operation for acid [green]{acid}')
            print(f'[red]Status Code: [cyan]{response.status_code}')
            print(response.json())
            console.rule(style='red')
            return
        # sleep for 5 seconds before Publishing the draft operation
        sleep(5)

        # The second step is to publish the draft operation
        print(f'[blue]Publishing UAS operation for acid: [green]{acid}[/] with operation id: [green]{op_uuid}')

        # Prepare the message for publishing
        url = f"{self.base_url}/api/uasoperations/{op_uuid}/publish"
        payload = ""
        headers = {
        'Content-Type': 'application/vnd.geo+json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {operator_token}'
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        
        if response.status_code == 200:
            print(f'[blue]Successfully published operation for acid: [green]{acid}[/] with operation id: [green]{op_uuid}')
        else:
            console.rule(style='red')
            print(f'[red]Failed to publish operation for acid: {acid} with operation id: [green]{op_uuid}')
            print(f'[red]Status Code: [cyan]{response.status_code}')
            print(response.json())
            console.rule(style='red')

        # sleep two seconds before requesting action items
        sleep(2)

        # The third step is to request action items
        print(f'[blue]Requesting action items for acid: [green]{acid}[/] witb operation id: [green]{op_uuid}')

        # Prepare the message for asking for action items
        url = f"{self.base_url}/api/uasoperations/{op_uuid}/actionItems"
        payload={}
        response = requests.request("GET", url, headers=headers, data=payload)

        # Check if you need to ask for permission
        if response.json()[0]['status'] == 'INITIATED' and response.json()[0]['type'] == 'PERMISSION':
            
            print(f'[blue]Requesting permission for acid: [green]{acid}[/] with operation id: [green]{op_uuid}')

            # get the action unique id
            action_uid = response.json()[0]['uniqueIdentifier']

            # Prepare the permission request
            url = f"https://portal.eu.unifly.tech/api/uasoperations/{op_uuid}/permissions/{action_uid}/request"
            now = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
            payload_key_meta = {
            'uniqueIdentifier': '{{'+action_uid+'}}',
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

            if response.status_code == 201:
                print(f'[blue]Successfully requested permission for acid: [green]{acid}[/] with operation id: [green]{op_uuid}') 
                print(f'[bold blue]Aircraft with acid: [green]{acid}[/] is waiting for take off command.')
                console.rule(style='green')

            else:
                console.rule(style='red')
                print(f'[red]Failed to request permission for acid: [green]{acid}[/] with operation id: [green]{op_uuid}')
                print(f'[red]Status Code: [cyan]{response.status_code}')
                print(response.json())
                console.rule(style='red')


    @stack.command()
    def posttakeoff(self, acidx : 'acid'):
        '''
        Post takeoff for a UAS.
        '''

        # TODO: take off real drones around this time from fligtmanaget
        # stack.stack('takeoffac', acidx)
        
        # get coordinates of route
        route = bs.traf.ap.route[acidx]
        coordinates = [[lon, lat] for lat, lon in zip(route.wplat, route.wplon)]
        
        # Get all tokens and ids
        operator_token = self.token_ids[self.operator[acidx]]
        opuid = self.opuid[acidx]
        uuid = self.uuid[acidx]

        url = f"{self.base_url}/api/uasoperations/{opuid}/uases/{uuid}/takeoff"

        # prepare the message
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

        if response.status_code == 200:
            print(f'[blue]Successfully posted takeoff for aircraft with acid: [green]{bs.traf.id[acidx]}[/]')
        else:
            console.rule(style='red')
            print(f'[red]Failed to post takeoff for acid [green]{bs.traf.id[acidx]}')
            print(f'[red]Status Code: [cyan]{response.status_code}')
            print(response.json())
            console.rule(style='red')
            return

        self.airborne[acidx] = True

        print(f"[green]{bs.traf.id[acidx]} [blue]is airborne")

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

        print(response.json())

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

            if response.status_code == 200:
                print(f'[blue]Posting telemetry for aircraft with acid: [green]{acid}[/]')
            else:
                console.rule(style='red')
                print(f'[red]Failed to post telemetry for aircraft with acid: [green]{acid}')
                print(f'[red]Status Code: [cyan]{response.status_code}')
                print(response.json())
                console.rule(style='red')


    @stack.command()
    def postlanding(self, acidx : 'acid'):
        '''
        Post landing for a UAS.
        '''
        # TODO: take off real drones around this time from fligtmanager
        # stack.stack('takeoffac', acidx)
        
        # get coordinates of landing
        route = bs.traf.ap.route[acidx]
        coordinates = [[lon, lat] for lat, lon in zip(route.wplat, route.wplon)]
        
        # get tokens and ids
        operator_token = self.token_ids[self.operator[acidx]]
        opuid = self.opuid[acidx]
        uuid = self.uuid[acidx]

        # prepare message
        url = f"https://portal.eu.unifly.tech/api/uasoperations/{opuid}/uases/{uuid}/landing"
        payload = json.dumps({
        "endTime": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+02:00"),
        "pilotLocation": {
            "longitude": coordinates[-1][0],
            "latitude": coordinates[-1][1]
        }
        })
        headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {operator_token}',
        'content-type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload)

        if response.status_code == 200:
            print(f'[blue]Successfully posted landing for aircraft with acid: [green]{bs.traf.id[acidx]}[/]')
        else:
            console.rule(style='red')
            print(f'[red]Failed to post landing for aircraft with acid: [green]{bs.traf.id[acidx]}')
            print(f'[red]Status Code: [cyan]{response.status_code}')
            print(response.json())
            console.rule(style='red')
            return

        self.airborne[acidx] = False
        

