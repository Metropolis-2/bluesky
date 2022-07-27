import bluesky as bs
import numpy as np
from bluesky.core import Entity, timed_function
from bluesky import stack
import requests
import json
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
        
        # Initial authentication
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

    @stack.command()
    def postuasop(self, acidx : 'acid', alt):
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
        'Authorization': f'Bearer {self.acces_token_a}'
        }
        # save payload as json
        with open('A1.json', 'w') as f:
            f.write(payload)


        response = requests.request("POST", url, headers=headers, data=payload)

        sleep(5)

        op_uuid = response.json()['uniqueIdentifier']
        self.opuid[acidx] = op_uuid

        url = f"https://portal.eu.unifly.tech/api/uasoperations/{op_uuid}/publish"

        payload = ""
        headers = {
        'Content-Type': 'application/vnd.geo+json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {self.acces_token_a}'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        
        sleep(2)

        url = f"https://portal.eu.unifly.tech/api/uasoperations/{op_uuid}/actionItems"

        payload={}

        response = requests.request("GET", url, headers=headers, data=payload)

        # TODO: response may fail in case list do a type check
        if response.json()[0]['status'] == 'INITIATED' and response.json()[0]['type'] == 'PERMISSION':
            action_uuid = response.json()[0]['uniqueIdentifier']


            # now submit permission request
            url = f"https://portal.eu.unifly.tech/api/uasoperations/{op_uuid}/permissions/{action_uuid}/request"

            # payload= json.dumps(
            #     'meta': 
            #         {"uniqueIdentifier": "{{" + action_uuid + "}}",
            #         "additionalData":{},
            #         "permissionRemark":{
            #                 "message":{
            #                         "message":"THIS IS A GCS TEST",
            #                         "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+02:00")
            #                 }
            #         }
            #         },
            #     'attachmentUpdate': {"updates":[]}
            #     )
            
            # files=[]

            # headers = {
            # 'Authorization': f'Bearer {self.acces_token_a}',
            # 'Content-Type': 'multipart/form-data'
            # }

            # save payload as json with tabs and spaces
            # with open('payload.json', 'w') as f:
            #     f.write(json.dumps(payload))

            # print(payload)

            # response = requests.request("POST", url, headers=headers, data=payload, files=files)

            # print(response.json())
    
    @stack.command()
    def posttakeoff(self, acidx : 'acid'):

        # TODO: take off real drones around this time from fligtmanaget
        # stack.stack('takeoffac', acidx)

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
        'Authorization': f'Bearer {self.acces_token_a}'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        print(response.text)

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

        response = requests.request("GET", url, headers=headers, data=payload)
        # response comes as a list of json objects. We need to extract the nickname and the uniqueIdentifier.
        # make a dictionary with the nickname as key and the uniqueIdentifier as value
        self.uas_dict = {uas['nickname']: uas['uniqueIdentifier'] for uas in response.json()}

    def get_pilot_dicts(self):
        url = "https://portal.eu.unifly.tech/api/uasoperations/users"

        payload={}
        headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {self.acces_token_a}'
        }

        response = requests.request("GET", url, headers=headers, data=payload)
        # response comes as a list of json objects. We need to extract the nickname and the uniqueIdentifier.
        # make a dictionary with the nickname as key and the uniqueIdentifier as value
        self.pilot_dicts = response.json()


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
