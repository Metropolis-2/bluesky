import bluesky as bs
from bluesky.tools.geo import kwikpos, kwikqdrdist
import numpy as np
from bluesky.core import Entity, timed_function
from shapely.geometry import LineString
from bluesky.tools.aero import nm


def init_plugin():

    # Instantiate our example entity
    intent = Intent()
    
    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'INTENT',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim'
    }

    return config

class Intent(Entity):
    def __init__(self):
        super().__init__()
        with self.settrafarrays():
            self.intent = []
        bs.traf.intent = self.intent
            
    @timed_function(name = 'intent_update', dt = 1)           
    def update(self):
        # Called from within traffic
        self.calc_intent(bs.traf)
        bs.traf.intent = self.intent
        return
    
    def create(self, n=1):
        super().create(n)
        for ridx, acid in enumerate(bs.traf.id[-n:]):
            self.intent[ridx-n] = None

        bs.traf.intent = self.intent

    def calc_intent(self, ownship):
        # The point of intent is to minimise false positive conflicts.
        # For now, create some shapely linestrings that give the future coordinates of
        # The aircraft. In Bluesky, drones fly in straight lines pretty much, so this
        # approach should be pretty solid. 
        # TODO: Should a fallback be impelented? If intent is not followed (how to decide this?!)
        # do we fall back to no intent?
        ntraf = ownship.ntraf
        
        for idx in range(ntraf):
            #------------ Vertical----------------
            # If there is a vertical maneuver going on, target altitude is intent.
            # Otherwise, intent is simply current altitude.
            if abs(ownship.selalt[idx] - ownship.alt[idx]) > 1:
                # There is a maneuver going on
                intentAlt = ownship.selalt[idx]
            else:
                # No maneuver going on
                intentAlt = ownship.alt[idx]


            # First, get route
            ac_route = ownship.ap.route[idx]
            # Current waypoint index
            wpt_i = ac_route.iactwp
            # Current aircraft data
            ac_lat = ownship.lat[idx]
            ac_lon = ownship.lon[idx]
            ac_tas = ownship.gs[idx]
            # Initialize stuff
            prev_lat = ac_lat
            prev_lon = ac_lon
            distance = 0 # Keep this in [m]
            # First point in intent line is the position of the aircraft itself
            linecoords = [(ac_lon, ac_lat)]
            # Target distance
            distance_max = ac_tas * bs.settings.asas_dtlookahead
            
            while True:
                # Stop if there are no waypoints, just create a line with current position and projected
                # Also stop if we ran out of waypoints.
                if wpt_i == len(ac_route.wpname):
                    # Just make a line between current position and the one within dtlookahead
                    # end_lat, end_lon = kwikpos(prev_lat, prev_lon, ownship.trk[idx], distance_max / nm)
                    # intentLine = LineString([(prev_lon, prev_lat), (end_lon, end_lat)])
                    # self.intent[idx] = (intentLine, intentAlt)
                    
                    # For M2: Just keep this line, destination is last waypoint
                    intentLine = LineString(linecoords)
                    # Append intentLine to overall intent
                    self.intent[idx] = (intentLine, intentAlt)
                    # Stop the while loop, go to next aircraft
                    break

                # Get waypoint data
                wpt_lat = ac_route.wplat[wpt_i]
                wpt_lon = ac_route.wplon[wpt_i]
                
                qdr_to_next, distance_to_next  = kwikqdrdist(prev_lat, prev_lon, wpt_lat, wpt_lon)
                distance_to_next = distance_to_next * nm # Now in meters
                
                if (distance + distance_to_next) < distance_max:
                    # Next waypoint is closer than distance_max
                    distance = distance + distance_to_next
                    # Simply take the waypoint as the next point in the line
                    linecoords.append((wpt_lon, wpt_lat))
                    prev_lat = wpt_lat
                    prev_lon = wpt_lon
                    # Go to next waypoint
                    wpt_i += 1
                    
                else:
                    # We have reached the max distance, but the next waypoint is further away
                    # Create a point a certain distance from the previous point and take that
                    # as the next intent waypoint. 
                    # Distance to new temp waypoint
                    travel_dist = (distance_max - distance) / nm # Convert to NM
                    # Calculate new waypoint
                    end_lat, end_lon = kwikpos(prev_lat, prev_lon, qdr_to_next, travel_dist)
                    # Do the same thing as before
                    linecoords.append((end_lon, end_lat))
                    intentLine = LineString(linecoords)
                    # Append intentLine to overall intent
                    self.intent[idx] = (intentLine, intentAlt)
                    # Stop the while loop, go to next aircraft
                    break
        return