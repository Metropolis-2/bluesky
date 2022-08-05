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

end = ''
class Unifly(Entity):
    
    def __init__(self):
        super().__init__()

        with self.settrafarrays():
            self.uuid      = np.array([], dtype=object)
            self.opuid     = np.array([], dtype=object)
            self.airborne  = np.array([], dtype=bool)
            self.ga_flight = np.array([], dtype=bool)
            self.operator  = np.array([], dtype=str)
            self.op_start_time =  np.array([], dtype=object)
        
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

        # some telemetry data
        self.telemetry_enable = True
        self.telemetry_time_enable = 0

    def create(self, n=1):
        super().create(n)

        # look through uas_dict for the uuid
        acid = bs.traf.id[-1]

        self.uuid[-n:] = self.uas_dict.get(acid, 'None')

        self.opuid[-n:] = ''

        self.airborne[-n:] = False

        if acid == 'HELI1':
            self.ga_flight[-n:] = True
        else:
            self.ga_flight[-n:] = False

        self.operator[-n:] = ''

        self.op_start_time[-n:] = ''

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
    def update_authentication_timed(self):
        print('[bold magenta]Updating authentication...')
        self.update_authentication()
        print('[bold magenta]Successfully updated authentication!')

    @stack.command()
    def forceauth(self):
        ''' Force authentication update in case of error'''
        print('[bold magenta]Forcing authentication...')
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
        global end

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
        self.op_start_time[acidx] = start.strftime("%Y-%m-%dT%H:%M:%S+02:00")

        if not end:
            end = (start + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S+02:00")

        # get the contact information for the uas from self.pilots_dict
        pilot_contact = self.pilots_dict[operator][0]['contact']
        pilot_uuid = self.pilots_dict[operator][0]['user']

        # set priorority
        priority = self.priority_levels[1] if acid == 'B1' else self.priority_levels[0]

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
            "startTime": self.op_start_time[acidx],
            "endTime": end,
            "name": "BlueSky operation",
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
            "priorityGroup": priority,
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
        data = {
            'method': 'POST',
            'url'     : url,
            'headers' : headers,
            'data'    : payload,
            'acid'    : acid,
            'operator_token': operator_token,
            'base_url': self.base_url,
            'uuid': self.uuid[acidx],
        }

        bs.net.send_stream(b'POSTUASOP', data)

        # stop telemetry for some seconds
        self.disable_telemetry()

    @stack.command()
    def setopuid(self, acidx: 'acid', opuid: str):
        """Get the operation id for a given acid"""

        self.opuid[acidx] = opuid
        print(f'[blue]Operation id for acid: [green]{bs.traf.id[acidx]}[/] is: [green]{self.opuid[acidx]}[/]')

    @stack.command()
    def posttakeoff(self, acidx : 'acid'):
        '''
        Post takeoff for a UAS.
        '''

        acid = bs.traf.id[acidx]

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

        data = {
            'method': 'POST',
            'url'     : url,
            'headers' : headers,
            'data'    : payload,
            'acid'    : acid,
        }

        bs.net.send_stream(b'POSTTAKEOFF', data)
        
        print(f'[blue]Attemptint to post takeoff for aircraft with acid: [green]{acid}[/]')

        self.airborne[acidx] = True

        print(f"[green]{bs.traf.id[acidx]} [blue]is airborne")

    @stack.command()
    def postnewflightplan(self, acidx : 'acid'):

        acid = bs.traf.id[acidx]

        console.rule(style='green', title=f'[bold blue]Posting modified UAS operation for aircraft with acid:[bold green] {acid}')
        print(f'[blue]Posting modified operation for acid: [green]{acid}[/] with uuid: [green]{self.uuid[acidx]}')

        # get coordinates of route
        route = bs.traf.ap.route[acidx]
        coordinates = [[lon, lat] for lat, lon in zip(route.wplat, route.wplon)]

        # Get all tokens and ids
        operator_token = self.token_ids[self.operator[acidx]]
        opuid = self.opuid[acidx]
        uuid = self.uuid[acidx]


        url = f"{self.base_url}/api/uasoperations/{opuid}"


        payload = json.dumps({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
        },
        "properties": {
            "geoZone": {
            "startTime": self.op_start_time[acidx],
            "endTime": end,
            "name": "BlueSky operation - modified",
            "lowerLimit": {
                "altitude": 0,
                "unit": "M",
                "reference": "GND",
                "isMostAccurate": False
            },
            "upperLimit": {
                "altitude": 80,
                "unit": "M",
                "reference": "GND",
                "isMostAccurate": False
            }
            },
            "uniqueIdentifier": opuid,
            "buffer": 2,
            "uases": [
            uuid
            ]
        }
        })
        headers = {
        'Content-Type': 'application/vnd.geo+json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {operator_token}'
        }

        data = {
            'method': 'PUT',
            'url'     : url,
            'headers' : headers,
            'data'    : payload,
            'acid'    : acid,
            'uuid'    : uuid,
            'opuid'   : opuid,
        }

        bs.net.send_stream(b'POSTNEWFLIGHTPLAN', data)
        
        print(f'[blue]Attempting to post modified operation for acid [green]{acid}[/] with operation id: [green]{opuid}')

        # disable telemetry for about 3 simulation seconds to not overload client
        self.disable_telemetry()

        console.rule(style='green')

    def blueskysendsalert(self, acidx : 'acid'):
        pass

    @timed_function(dt=1)
    def postgaflight(self):
        ''' 
        Post a GA flight to unifly client
        '''

        # Don't send GA flight if telemtry is disabled
        if not self.telemetry_enable:
                return

        data = {}
        for acidx, acid in enumerate(bs.traf.id):
            
            if not self.ga_flight[acidx]:
                continue

            url = f"{self.base_url}/api/tracking"

            payload = json.dumps({
            "apiKey": "TUD_Kp37f9R",
            "identification": "78AF18",
            "callSign": "DOC99",
            "timestamp":  datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+02:00"),
            "vehicleType": "AIRPLANE",
            "location": {
                "longitude": bs.traf.lon[acidx],
                "latitude": bs.traf.lat[acidx]
            },
            "altitude": {
                "altitude": bs.traf.alt[acidx],
                "unit": "ft",
                "reference": "MSL"
            },
            "heading": {
                "trueHeading": bs.traf.hdg[acidx],
            },
            "aircraftData": {
                "groundSpeed": bs.traf.gs[acidx],
            }
            })
            headers = {
            'Content-Type': 'application/json'
            }

            data_acid = {
                'method': 'POST',
                'url'     : url,
                'headers' : headers,
                'data'    : payload,
            }

            data[acid] = data_acid

        if data:
            bs.net.send_stream(b'POSTGAFLIGHT', data)

    @timed_function(dt=1)
    def posttelemetry(self):
        '''
        Post telemetry data to unifly client.
        '''

        # first check if telemetry is enabled and enable it once simulation time is larger
        # than time to enable
        if not self.telemetry_enable:
            if bs.sim.simt > self.telemetry_time_enable:
                self.telemetry = True
            else:
                return

        data = {}        
        for acidx, acid in enumerate(bs.traf.id):
            
            # if route is empty or flight is not airborne, skip
            if bs.traf.ap.route[acidx].wplat == [] or not self.airborne[acidx]:
                continue
            
            # if aircraft is not a UAS, skip
            if self.ga_flight[acidx]:
                continue

            # get tokens
            opuid = self.opuid[acidx]
            uuid = self.uuid[acidx]
            operator_token = self.token_ids[self.operator[acidx]]

            # prepare messages
            url = f"{self.base_url}/api/uasoperations/{opuid}/uases/{uuid}/track"

            payload = json.dumps({
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+02:00"),
            "location": {
                "longitude": bs.traf.lon[acidx],
                "latitude": bs.traf.lat[acidx]
            },
            "altitudeMSL": bs.traf.alt[acidx],
            "altitudeAGL": bs.traf.alt[acidx] + 2,
            "heading": bs.traf.hdg[acidx],
            "speed": bs.traf.gs[acidx],
            })
            headers = {
            'Authorization': f'Bearer {operator_token}',
            'content-type': 'application/json'
            }

            data_acid = {
                'method': 'POST',
                'url'     : url,
                'headers' : headers,
                'data'    : payload,
            }

            # add to dictionary
            data[acid] = data_acid

            print(f'[bright_black]Attempting to post telemetry for aircraft with acid: [green]{acid}[/]')
        
        if data:
            bs.net.send_stream(b'POSTTELEMETRY', data)

    @stack.command()
    def postlanding(self, acidx : 'acid'):
        '''
        Post landing for a UAS.
        '''

        # get acid
        acid = bs.traf.id[acidx]

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

        data = {
            'method': 'POST',
            'url'     : url,
            'headers' : headers,
            'data'    : payload,
            'acid'    : acid,
        }

        bs.net.send_stream(b'POSTLANDING', data)
        
        print(f'[blue]Attempting to post landing for aircraft with acid: [green]{acid}[/]')

        self.airborne[acidx] = False

    @stack.command()
    def forcelanding(self, acidx : 'acid', operator):
        '''
        Post a forced landing for a UAS after bluesky crashes without landing UAS.
        Requires the aircraft to be initialized in BlueSky traffic.
        '''
        
        # The first step is to get the operator token and assign an operator to each aircraft
        self.operator[acidx] = operator
        operator_token = self.token_ids[self.operator[acidx]]
   
        # get tokens and ids
        operator_token = self.token_ids[self.operator[acidx]]
        opuid = '741e90a8-9c14-447d-8880-25494a4baa18'
        uuid = self.uuid[acidx]

        # prepare message
        url = f"https://portal.eu.unifly.tech/api/uasoperations/{opuid}/uases/{uuid}/landing"

        payload = json.dumps({
        "endTime": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+02:00"),
        "pilotLocation": {
            "longitude":4.416856266047878,
            "latitude": 52.171876266151514
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

    def disable_telemetry(self, disable_time=3):
        '''
        Disable telemetry while other data is being sent for some seconds (default is 3 seconds).
        '''
        self.telemetry_enable = False
        self.telemetry_time_enable = bs.sim.simt + disable_time