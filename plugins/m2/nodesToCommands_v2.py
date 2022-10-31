import math
import numpy as np
import geopandas as gp
import osmnx as ox
from pyproj import CRS
from shapely.geometry import LineString


def edge_gdf_format_from_gpkg(edges):
    edge_dict = edges.to_dict()
    edge_gdf = gp.GeoDataFrame(edge_dict, crs=CRS.from_user_input(4326))
    edge_gdf.set_index(['u', 'v', 'key'], inplace=True)
    return edge_gdf

def node_gdf_format_from_gpkg(nodes):
    node_dict = nodes.to_dict()
    node_gdf = gp.GeoDataFrame(node_dict, crs=CRS.from_user_input(4326))
    node_gdf.set_index(['osmid'], inplace=True)
    return node_gdf


class PathPlanner():
    ''' PathPlanner new entity object for BlueSky. '''

    def __init__(self, G, angle_cutoff=30):
        self.G = G
        # get edge geodataframe
        gdfs = ox.graph_to_gdfs(self.G)
        self.node_gdf = gdfs[0]
        self.edge_gdf = gdfs[1]

        # get edge indices
        self.edge_idx = list(self.edge_gdf.index.values)

        # get angle cutoff to label turns as turnbool
        self.angle_cutoff = angle_cutoff

    def route(self, osmid_route):

        # get_correct_order of edges inside graph and reverese linestring geometry if necessary
        edge_geom_list = []
        for idx in range(len(osmid_route) - 1):

            edge_to_find = (osmid_route[idx], osmid_route[idx + 1], 0)

            # See if edge is in graph otherwise reverese u,v
            if edge_to_find in self.edge_idx:
                edge = edge_to_find
            else:
                edge = (edge_to_find[1], edge_to_find[0], 0)

            # check if geometry is in correct direction. if not flip geometry
            # use node of route to check in which  if it lines up with edge linestring
            line_geom = list(self.edge_gdf.loc[edge, 'geometry'].coords)

            lat_node = self.node_gdf.loc[osmid_route[idx], 'y']
            lon_node = self.node_gdf.loc[osmid_route[idx], 'x']

            if not (lon_node == line_geom[0][0] and lat_node == line_geom[0][1]):
                wrong_geom = line_geom
                wrong_geom.reverse()
                line_geom = list(LineString(wrong_geom).coords)

            # append edge and geometry for later use
            edge_geom_list.append((edge, line_geom))

        # calculate succesive interior angles and see which nodes are turn nodes
        int_angle_list = []
        turn_node_list = []
        for idx in range(len(edge_geom_list) - 1):
            current_edge = edge_geom_list[idx][0]
            next_edge = edge_geom_list[idx + 1][0]

            int_angle_dict = eval(self.edge_gdf.loc[current_edge, 'edge_interior_angle'])
            # get interior angle. search in current_edge
            try:
                interior_angle = int_angle_dict[next_edge]
            except KeyError:
                next_edge = (next_edge[1], next_edge[0], 0)
                interior_angle = int_angle_dict[next_edge]

            # get osmids of turn nodes
            if interior_angle < 180 - self.angle_cutoff:
                node_1 = current_edge[0]
                node_2 = current_edge[1]

                node_3 = next_edge[0]
                node_4 = next_edge[1]

                #NOT NECCESARY
                # if node_1 == node_3 or node_1 == node_4:
                #     node_to_append = node_1
                # else:
                node_to_append = node_2

                turn_node_list.append(node_to_append)

            int_angle_list.append(interior_angle)

            # create list of lat lon for path finding
        lat_list = []
        lon_list = []
        lon_lat_list = []  # this is used for searching for turn nodes
        last_lat = 0
        last_lon = 0
        for edge_geo in edge_geom_list:
            edge = edge_geo[0]
            geom = edge_geo[1]

            # add all geometry info. adds the first node and second to last

            for idx in range(len(geom)):
                lon = geom[idx][0]
                lat = geom[idx][1]

                if(lon != last_lon and lat != last_lat):
                    lon_list.append(lon)
                    lat_list.append(lat)
                    lon_lat_list.append(f'{lon}-{lat}')

                last_lat = lat
                last_lon = lon

        # find indices of turn_nodes
        turn_indices = []
        for turn_node in turn_node_list:
            # Find lat lon of current turn node
            lat_node = self.node_gdf.loc[turn_node, 'y']
            lon_node = self.node_gdf.loc[turn_node, 'x']

            try:
                index_turn = lon_lat_list.index(f'{lon_node}-{lat_node}')
            except ValueError:
                print("index_turn not found")
                index_turn = 9999

            turn_indices.append(index_turn)

        # create turnbool. true if waypoint is a turn waypoint, else false
        turnbool = []
        for idx in range(len(lat_list)):
            if idx in turn_indices:
                turn_flag = True
            else:
                turn_flag = False

            turnbool.append(turn_flag)

        return lat_list, lon_list, turnbool, int_angle_list


class ScenarioMaker():
    ''' ScenarioMaker new entity object for BlueSky. '''

    header_added = False

    def Drone2Scn(self, drone_id, start_time, lats, lons, turnbool, alts, priority, sta, uav, int_angle_list):
        # Define the lines list to be returned
        lines = []

        # Change these values to control how an aircraft turns and cruises
        turn_speed = 10 # [kts]
        if(uav == 'MP20'):
            cruise_speed = 20 # [kts]
        elif(uav == 'MP30'):
            cruise_speed = 30  # [kts]
        else:
            cruise_speed = 20  # [kts]

        start_time_txt = self.TimeToStr(start_time) + '>'

        # Everyone starts at 0ft above ground
        # Let's calculate its required heading.
        qdr = self.qdrdist(lats[0], lons[0], lats[1], lons[1], 'qdr')
        takeoff_altitude = alts[0]
        middle_alt_index = int(len(alts)/2)
        operational_altitude = alts[middle_alt_index]
        cre_text = f'CRE {drone_id} {uav} {lats[0]} {lons[0]} {qdr} {takeoff_altitude} 0\n'
        lines.append('\n'+start_time_txt + cre_text)
        priority_text = f'SETPRIORITY {drone_id} {priority}\n'
        lines.append(start_time_txt + priority_text)
        sta_text = f'SETSTA {drone_id} {sta}\n'
        lines.append(start_time_txt + sta_text)
        alt_text = f'ALT {drone_id} {operational_altitude}\n'
        lines.append(start_time_txt + alt_text)

        atalt1_text = f'{drone_id} ATALT {operational_altitude} SPD {drone_id} {cruise_speed}\n'
        lines.append(start_time_txt + atalt1_text)
        atalt2_text = f'{drone_id} ATALT {operational_altitude} LNAV {drone_id} ON\n'
        lines.append(start_time_txt + atalt2_text)
        atalt3_text = f'{drone_id} ATALT {operational_altitude} VNAV {drone_id} ON\n'
        lines.append(start_time_txt + atalt3_text)


        wpt_txt = f'ADDWAYPOINTS {drone_id} '
        j=0

        if(len(lats)>0 and len(lons)>0):
            init_lat = lats[0]
            init_lon = lons[0]
            final_lat = lats[-1]
            final_lon = lons[-1]

            last_lat = lats[0]
            last_lon = lons[0]

        for lat, lon, alt, turn, i in zip(lats, lons, alts, turnbool, range(0,len(lats))):

            if(i==0):
                wpt_txt += f'{lat} {lon} ,{alt},{0}, FLYBY, 0,'

            elif(i<len(lats)-1):

                if turn == 1 or turn == True: #turn angle
                    if (int_angle_list[j] >= 25 and int_angle_list[j] < 100):
                        turn_speed = 10 
                    elif (int_angle_list[j] >= 100 and int_angle_list[j] < 150):
                        turn_speed = 5
                    elif (int_angle_list[j] >= 150):
                        turn_speed = 2 
                    j+=1

                    wpt_txt += f'{lat} {lon} ,{alt},{cruise_speed}, TURNSPEED, {turn_speed},'
                else:
                    if(lat == lats[i-1] and lon == lons[i-1]): #take-off phase
                        wpt_txt += f'{lat} {lon} ,{alt},{0}, FLYBY, 0,'

                    elif(lat == lats[i+1] and lon == lons[i+1]):  # landing phase
                        wpt_txt += f'{lat} {lon} ,{alt},{0}, FLYBY, 0,'

                    else:
                        wpt_txt += f'{lat} {lon} ,{alt},{cruise_speed}, FLYBY, 0,'

            elif (i == len(lats)-1): #last WAYPOINT
                    wpt_txt += f'{lat} {lon} ,{alt},{0}, FLYOVER, 0,'
            else:
                print("ERROR WAAYPOINT")


            last_lat = lat
            last_lon = lon

        lines.append(start_time_txt + wpt_txt)

        return lines

    def TimeToStr(self, time):
        time = round(time)
        m, s = divmod(time, 60)
        h, m = divmod(m, 60)
        return f'{h:02d}:{m:02d}:{s:02d}'

    def qdrdist(self, latd1, lond1, latd2, lond2, mode):
        """ Calculate bearing and distance, using WGS'84
            In:
                latd1,lond1 en latd2, lond2 [deg] :positions 1 & 2
            Out:
                qdr [deg] = heading from 1 to 2
                d [m]    = distance from 1 to 2 in m """

        # Haversine with average radius for direction

        # Check for hemisphere crossing,
        # when simple average would not work

        # res1 for same hemisphere
        res1 = self.rwgs84(0.5 * (latd1 + latd2))

        # res2 :different hemisphere
        a    = 6378137.0       # [m] Major semi-axis WGS-84
        r1   = self.rwgs84(latd1)
        r2   = self.rwgs84(latd2)
        res2 = 0.5 * (abs(latd1) * (r1 + a) + abs(latd2) * (r2 + a)) / \
            (np.maximum(0.000001,abs(latd1) + abs(latd2)))

        # Condition
        sw   = (latd1 * latd2 >= 0.)

        r    = sw * res1 + (1 - sw) * res2

        # Convert to radians
        lat1 = np.radians(latd1)
        lon1 = np.radians(lond1)
        lat2 = np.radians(latd2)
        lon2 = np.radians(lond2)


        #root = sin1 * sin1 + coslat1 * coslat2 * sin2 * sin2
        #d    =  2.0 * r * np.arctan2(np.sqrt(root) , np.sqrt(1.0 - root))
        # d =2.*r*np.arcsin(np.sqrt(sin1*sin1 + coslat1*coslat2*sin2*sin2))

        # Corrected to avoid "nan" at westward direction
        d = r*np.arccos(np.cos(lat1)*np.cos(lat2)*np.cos(lon2-lon1) + np.sin(lat1)*np.sin(lat2))

        # Bearing from Ref. http://www.movable-type.co.uk/scripts/latlong.html

        sin1 = np.sin(0.5 * (lat2 - lat1))
        sin2 = np.sin(0.5 * (lon2 - lon1))

        coslat1 = np.cos(lat1)
        coslat2 = np.cos(lat2)


        qdr = np.degrees(np.arctan2(np.sin(lon2 - lon1) * coslat2,
            coslat1 * np.sin(lat2) - np.sin(lat1) * coslat2 * np.cos(lon2 - lon1)))

        if mode == 'qdr':
            return qdr
        elif mode == 'dist':
            return d
        else:
            return qdr, d

    def rwgs84(self, latd):
        """ Calculate the earths radius with WGS'84 geoid definition
            In:  lat [deg] (latitude)
            Out: R   [m]   (earth radius) """
        lat    = np.radians(latd)
        a      = 6378137.0       # [m] Major semi-axis WGS-84
        b      = 6356752.314245  # [m] Minor semi-axis WGS-84
        coslat = np.cos(lat)
        sinlat = np.sin(lat)

        an     = a * a * coslat
        bn     = b * b * sinlat
        ad     = a * coslat
        bd     = b * sinlat

        # Calculate radius in meters
        r = np.sqrt((an * an + bn * bn) / (ad * ad + bd * bd))

        return r

    def Dict2Scn(self, dictionary, priority, sta, uav, int_angle_list):

        """Creates a scenario file from dictionary given that dictionary
        has the correct format.

        Parameters
        ----------
        filepath : str
            The file path and name of the scn file.

        dictionary : dict
            This dictionary needs the format needed to use the Drone2Scn function.
            Drone_id is used as a main key, and then a sub dictionary is defined
            with the other variables.

            Example:
                dictionary = dict()
                dictionary['drone_id'] = dict()
                dictionary['drone_id']['start_time'] = start_time
                dictionary['drone_id']['lats'] = lats
                dictionary['drone_id']['lons'] = lons
                dictionary['drone_id']['truebool'] = turnbool
                dictionary['drone_id']['alts'] = alts

            Set alts as None if no altitude constraints are needed.

        priority
        sta
        uav
        int_angle_list

        """
        for drone_id in dictionary: #solo itera una vez
            try:
                start_time = dictionary[drone_id]['start_time']
                lats = dictionary[drone_id]['lats']
                lons = dictionary[drone_id]['lons']
                turnbool = dictionary[drone_id]['turnbool']
                alts = dictionary[drone_id]['alts']
            except:
                print('Key error. Make sure the dictionary is formatted correctly.')
                return

            lines = self.Drone2Scn(drone_id, start_time, lats, lons, turnbool, alts, priority, sta, uav, int_angle_list)
            if(not self.header_added):
                header_text0 = '00:00:00>CASMACHTHR 0\n'
                lines.insert(0, header_text0)
                header_text1 = '00:00:00>PAN 48.223775 16.337976\n'
                lines.insert(1,header_text1)
                header_text2 = '00:00:00>ZOOM 60'
                lines.insert(2, header_text2)

                self.header_added = True

            return lines
