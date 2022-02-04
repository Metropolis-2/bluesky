import numpy as np
import json
import sys
import os
import time
import math

import pandas as pd
from pyproj import CRS
import geopandas as gp
import osmnx as ox
from loguru import logger
from shapely.geometry import LineString
from rtree import index
from multiprocessing import Pool as ThreadPool
import multiprocessing


def normal_round(num, ndigits=0):
    """
    Rounds a float to the specified number of decimal places.
    num: the value to round
    ndigits: the number of digits to round to
    """
    if ndigits == 0:
        return int(num + 0.5)
    else:
        digit_value = 10 ** ndigits
        return int(float("{:.1f}".format(num * digit_value)) + 0.5) / digit_value

class MainApp():


    def startRoutingPlan(self, flight_intentions):

        self.thread_id = multiprocessing.current_process().name
        self.createLoggerHandler()

        self.scenario = ScenarioMaker(self.logger)
        self.routing = RoutingAlgorithm(self, self.logger, angle_cutoff=25)
        #self.logger.debug("Current work directory: {}".format(os.getcwd()))

        self.OUTPUT_SCN = self.settings.ROOT_OUTPUT_SCN + flight_intentions.split(".")[0] + self.settings.OUTPUT_SCN
        self.logger.success("self.OUTPUT_SCN: {}".format(self.OUTPUT_SCN))

        self.loadGraphData()
        self.loadAircraftData()
        self.loadFPlansData(settings.ROOT_FP_PATHS+flight_intentions)

        self.start = time.time()
        # Call method calculate_edges_df_rtree() of routing with edges of lista_g[0] = layer base (EmergencyCruising)
        self.routing.calculate_edges_df_rtree(self.base_edges)
        # start routing process
        self.paths = self.routing.get_paths(self.fp_plans, self.lista_g)

        self.logger.info("Generated PATHS: ")
        for p in self.paths:
            self.logger.info(p)
        self.logger.info("FPLANS AFTER ROUTING STRATEGY")
        for fp in self.fp_plans:
            self.logger.info(fp)

        self.end = time.time()
        self.FINAL_EXECUTION_TIME = self.end - self.start
        self.logger.success(f"Runtime of the program is {self.end - self.start}")

        self.logger.success("FINAL_EXECUTION_TIME: {}".format(self.FINAL_EXECUTION_TIME))
        self.logger.success("ALTITUDE_CHANGES_ASCENDING: {}".format(self.routing.ALTITUDE_CHANGES_ASCENDING))
        self.logger.success("ALTITUDE_CHANGES_DESCENDING: {}".format(self.routing.ALTITUDE_CHANGES_DESCENDING))
        self.logger.success("LAYER_CHANGES_DISTANCE_MARGIN: {}".format(self.routing.LAYER_CHANGES_DISTANCE_MARGIN))
        self.logger.success("LAYER_CHANGES_NO_ROUTE: {}".format(self.routing.LAYER_CHANGES_NO_ROUTE))
        self.logger.success("LAYER_CHANGES_NO_TYPE: {}".format(self.routing.LAYER_CHANGES_NO_TYPE))
        self.logger.success("HAS_CHANGE_ALTITUDE: {}".format(self.routing.HAS_CHANGE_ALTITUDE))


        #Sorting SCN FINAL FILE
        self.sortSCNFinal(self.OUTPUT_SCN)

        # Updating GLIST graphs locally
        # f = open(settings.GPKG_LIST)
        # lines = f.readlines()
        # f.close()
        # for g, name in zip(self.lista_g, lines):
        #     name = name.rstrip("\n")
        #     ox.save_graph_geopackage(g,filepath=f'{settings.GPKG_FOLDER}{name}.gpkg',directed=True)

    def sortSCNFinal(self, input_scn_file):
        # Example:
        # input_scn_file = "scenario/Example_flight_intention_low_200fplans_100cre.scn"
        # output_scn_file = "scenario/Example_flight_intention_low_200fplans_100cre_sorted.scn"
        output_scn_file = input_scn_file.split('.')[0]+"_sorted.scn"
        commands = list()
        # Read the commands from scenario file
        with open(input_scn_file) as fin:
            for line in fin:
                commands.append(line)

        # Add \n in last command
        commands[-1] = commands[-1] + '\n'
        #print(commands)

        # Write commands sorted in new scenario file
        with open(output_scn_file, 'w') as fout:
            for line in sorted(commands, key=lambda line: line.split('>')[0]):
                #print(line)
                fout.write(line)


    def __init__(self, *args, **kwargs):
        self.settings = Settings()
        self.fp_plans = []
        self.lista_g = []
        self.paths = None
        self.joinedPaths = None
        self.start = 0
        self.end = 9999
        self.base_edges = None
        self.OUTPUT_SCN = None
        self.thread_id = None
        self.logger = None

    @logger.catch
    def debugging_filter(self, record):
        min_level = os.getenv("DEBUGGING_LEVEL", self.settings.LOG_LEVEL)
        return record["level"].no >= logger.level(min_level).no

    @logger.catch
    def createLoggerHandler(self):
        # Set handler,format,filter of logger (https://github.com/Delgan/loguru#readme)
        logger.remove(0)  # Remove default handler which has no filter
        fmt = "<white>{extra[threadid]} [{time:YYYY-MM-DD at HH:mm:ss}] | {name}:{function}:{line} -</white> <level>{message}</level>"
        logger.add(sys.stderr, format=fmt,filter=self.debugging_filter, enqueue=True, colorize=True)
        logger.add(os.path.join(self.settings.LOGS_FOLDER, "file_{time}.log"), format=fmt, rotation="50 MB")
        self.logger = logger.bind(threadid=self.thread_id)

    @logger.catch
    def loadGraphData(self):
        with open(settings.GPKG_LIST) as file:
            gpkg_paths = file.readlines()
            gpkg_paths = [settings.GPKG_FOLDER + gpkg_path.rstrip() + ".gpkg" for gpkg_path in gpkg_paths]
        self.logger.info(gpkg_paths)

        i = 0
        for gpkg in gpkg_paths:
            nodes = gp.read_file(gpkg, layer='nodes')
            edges = gp.read_file(gpkg, layer='edges')
            if(i==0):
                self.base_edges = edges

            nodmod = self.routing.node_gdf_format_from_gpkg(nodes)
            edmod = self.routing.edge_gdf_format_from_gpkg(edges)
            graph = ox.graph_from_gdfs(nodmod, edmod)
            self.lista_g.append(graph)

            self.logger.success("Created layer: {}".format(gpkg))
            self.logger.trace("Nans en nodes: {}".format(nodmod.isna().sum()))
            self.logger.trace("Nans en edges: {}".format(edmod.isna().sum()))
            i += 1

    @logger.catch
    def loadAircraftData(self):
        # Load Aircraft File
        self.aircraft = open(settings.AIRCRAFT_PATH)

    @logger.catch
    def loadFPlansData(self, flight_intentions):
        # Load Flight Planes File
        file = open(flight_intentions)
        line = file.readline()
        while line:

            self.logger.debug(line)
            line = line.rstrip("\n") + settings.PENDING_STATUS + "\n"
            line_list = line.rstrip().split(',')
            self.logger.debug(line_list)
            new_line = []
            new_line.append(line_list[0])
            new_line.append(line_list[1])
            new_line.append(line_list[2])
            new_line.append(line_list[3])

            lon_init = line_list[4][2:]
            lat_init = line_list[5][:-2]

            lon_fin = line_list[6][2:]
            lat_fin = line_list[7][:-2]

            tuple_init = eval(lat_init + "," + lon_init)
            self.logger.debug("lat_init {} and lon_init {} and tuple_init {}".format(lat_init, lon_init, tuple_init))
            tuple_fin = eval(lat_fin + "," + lon_fin)
            self.logger.debug("lat_fin {} and lon_fin {} and tuple_fin {}".format(lat_fin, lon_fin, tuple_fin))
            new_line.append(str(tuple_init))
            new_line.append(str(tuple_fin))
            new_line.append(line_list[8])  # priority


            self.logger.debug("len(line_list): {}".format(len(line_list)))
            if(line_list[9] != ''): #loitering mission
                new_line.append(line_list[14])  # status
                new_line.append(line_list[9])  # duration geofence

                lon_point1_bbox = line_list[10]
                lon_point2_bbox = line_list[11]

                lat_point1_bbox = line_list[12]
                lat_point2_bbox = line_list[13]

                tuple_point1_bbox = eval(lat_point1_bbox + "," + lon_point1_bbox)
                new_line.append(str(tuple_point1_bbox))
                self.logger.debug("lat_point1_bbox {} and lon_point1_bbox {} and tuple_point1_bbox {}".format(lat_point1_bbox, lon_point1_bbox, tuple_point1_bbox))
                tuple_point2_bbox = eval(lat_point2_bbox + "," + lon_point2_bbox)
                new_line.append(str(tuple_point2_bbox))
                self.logger.debug("lat_point2_bbox {} and lon_point2_bbox {} and tuple_point2_bbox {}".format(lat_point2_bbox, lon_point2_bbox, tuple_point2_bbox))

            else:
                new_line.append(line_list[14])  # status #TODO: BEFORE WAS 9?


            self.logger.debug(new_line)
            self.fp_plans.append(new_line)
            line = file.readline()
        file.close()

        self.logger.info("FPLANS before sorted")
        for line in self.fp_plans:
            self.logger.info(line)

        self.fp_plans = sorted(self.fp_plans, key=lambda e: (-int(len(e)), e[settings.RECEPTION_TIME_FP_INDEX], -int(e[settings.PRIORITY_INDEX])))

        self.logger.info("FPLANS after sorted")
        for line in self.fp_plans:
            self.logger.info(line)

    @logger.catch
    def buildScenarioUnitary(self, index_layer, dict_nodes_alt, fplan_id, fplan_departuretime, fplan_priority, fplan_arrivaltime, fplan_vehicle, fp, edges_index_dict):
        '''
        CALLfrom get_paths()
        self.mainApp.buildScenarioUnitary(g_cont, dict_nodes_alt, fp[settings.FPLAN_ID_INDEX],
                                          fp[settings.DEPARTURE_INDEX], fp[settings.PRIORITY_INDEX],
                                          str(fplan_arrivaltime), str(fp[settings.VEHICLE_INDEX]), fp)
        '''

        self.logger.debug("index_layer: {}".format(index_layer))
        path_planner = PathPlanner(self.lista_g[index_layer], edges_index_dict, self.logger, angle_cutoff=25)
        osmid_route = dict_nodes_alt
        #{32637472.0: (30,), 33242231.0: (30,), 33242240.0: (30,), 3242084.0: (30,)}

        lista_nodes_id = list(osmid_route.keys()) #[32637472.0, 33242231.0...]
        self.logger.success("lista_nodes_id: {}".format(lista_nodes_id))
        lats, lons, turns, turn_indexs, int_angle_list, angle_cut_off = path_planner.route(lista_nodes_id) #1ºarg: route of nodeids
        self.logger.debug("int_angle_list: {}".format(int_angle_list))

        for fp in self.fp_plans:
            if(fp[settings.FPLAN_ID_INDEX] == fplan_id): #it only goes in once because it is a unit analysis per fp in the calls to this method
                self.logger.debug("fplan_id: {} corresponding with FPLAN_ID {}".format(fplan_id,fp[settings.FPLAN_ID_INDEX]))
                fp_takeOffLat = normal_round(float(eval(fp[settings.INITIAL_LOCATION_INDEX])[0]),6)
                fp_takeOffLon = normal_round(float(eval(fp[settings.INITIAL_LOCATION_INDEX])[1]),6)
                fp_takeOffAlt = float(settings.TAKEOFF_ALT)
                self.logger.debug("fp_takeOffLat: {}".format(fp_takeOffLat))
                self.logger.debug("fp_takeOffLon: {}".format(fp_takeOffLon))
                self.logger.debug("fp_takeOffAlt: {}".format(fp_takeOffAlt))
                fp_landingLat = normal_round(float(eval(fp[settings.FINAL_LOCATION_INDEX])[0]),6)
                fp_landingLon = normal_round(float(eval(fp[settings.FINAL_LOCATION_INDEX])[1]),6)
                fp_landingAlt = float(settings.LANDING_ALT)
                self.logger.debug("fp_landingLat: {}".format(fp_landingLat))
                self.logger.debug("fp_landingLon: {}".format(fp_landingLon))
                self.logger.debug("fp_landingAlt: {}".format(fp_landingAlt))
                break

        #Calculate alts list
        #Convert the dict values: [(30), (30,), (30,), (30,), (30,), (30,)]
        #Into this: [30, 30, 30, 30, 30, 30]
        lista_tuplas_alturas = list(dict_nodes_alt.values())
        self.logger.debug(lista_tuplas_alturas)
        alts = []
        for tupla in lista_tuplas_alturas:
            for t in tupla:
                alts.append(t)
        self.logger.debug("alts list: {}".format(alts))


        if(all(element == alts[0] for element in alts)): #La lista lats tiene la misma altura en todos los elementos (ANALISIS HORIZONTAL)
            self.logger.debug("ALL ALTITUDES IN THE LIST WITH THE INITIAL VALUE: {}".format(alts[0]))
            #Si es el caso rellenamos por el final de la lista de alturas con el ultimo valor
            last_altitude_list = alts[-1]
            self.logger.debug("last_altitude_list: {}".format(last_altitude_list))
            while(len(alts) != len(lats)):
                alts.append(last_altitude_list)

        '''
        BEFORE ADDING THE SENDING AND RECEIVING POINTS OF THE FLIGHT_INTENTION,
         WE CHECK THE GROUND NODE OF THE GRAPH AND IF IT MATCHES THOSE POINTS
        '''
        init_lat_route = lats[0]
        init_lon_route = lons[0]
        self.logger.trace("init position route {},{}".format(init_lat_route, init_lon_route))
        final_lat_route = lats[-1]
        final_lon_route = lons[-1]
        self.logger.trace("final position route {},{}".format(final_lat_route, final_lon_route))

        # TAKEOFF
        lats.insert(0, init_lat_route)
        lons.insert(0, init_lon_route)
        alts.insert(0, fp_takeOffAlt)
        turns.insert(0, False)

        # LANDING
        lats.insert(len(lats), final_lat_route)
        lons.insert(len(lats), final_lon_route)
        alts.insert(len(lats), fp_landingAlt)
        turns.insert(len(lats), False)

        for turn_index,i in zip(turn_indexs,range(0,len(turn_indexs))):
            turn_index = turn_index + 1
            turn_indexs[i] = turn_index

        self.logger.debug("len(lats): {}".format(len(lats)))
        self.logger.debug("len(lons): {}".format(len(lons)))
        self.logger.debug("len(alts): {}".format(len(alts)))
        self.logger.debug("len(turns): {}".format(len(turns)))
        self.logger.debug("len(turn_indexs): {}".format(len(turn_indexs)))
        self.logger.debug("len(int_angle_list): {}".format(len(int_angle_list)))

        new_int_angle_list = []
        for interior_angle in int_angle_list:
            if interior_angle < 180 - angle_cut_off:
                new_int_angle_list.append((interior_angle))
        self.logger.trace("new_int_angle_list: {}".format(new_int_angle_list))
        self.logger.trace("len(new_int_angle_list): {}".format(len(new_int_angle_list)))

        new_turns = []
        for turn in turns:
            if (turn == True):
                new_turns.append(turn)
        self.logger.trace("new_turns: {}".format(new_turns))
        self.logger.trace("len(new_turns): {}".format(len(new_turns)))

        turn_speeds = []
        for int_angle in new_int_angle_list:
            if (int_angle >= 25 and int_angle < 100):
                turn_speed = 2
            elif (int_angle >= 100 and int_angle < 150):
                turn_speed = 5
            elif (int_angle >= 150):
                turn_speed = 10
            else:
                turn_speed = 10
            turn_speeds.append(turn_speed)
        self.logger.trace("turn_speeds: {}".format(turn_speeds))
        self.logger.trace("len(turn_speeds): {}".format(len(turn_speeds)))

        # Initialize scenario
        scenario_dict = dict()
        # Create dictionary
        scenario_dict[fplan_id] = dict() #key is the id of fplan
        # Add start time
        scenario_dict[fplan_id]['start_time'] = self.routing.get_sec(fplan_departuretime)
        # Add lats
        scenario_dict[fplan_id]['lats'] = lats
        # Add lons
        scenario_dict[fplan_id]['lons'] = lons
        # Add alts
        scenario_dict[fplan_id]['alts'] = alts
        # Add turnbool
        scenario_dict[fplan_id]['turnbool'] = turns

        self.logger.debug("scenario_dict: {}".format(scenario_dict))
        self.logger.info("fplan_arrivaltime: {}".format(fplan_arrivaltime))


        # The scenarioini.scn file is saved in the BlueSky scenario folder inside the /plugins folder.
        # The /scenario directory must already exist
        self.scenario.Dict2Scn(self.OUTPUT_SCN, scenario_dict, fplan_priority, fplan_arrivaltime, fplan_vehicle, int_angle_list, turn_indexs, turn_speeds, fp)
        #self.logger.debug(lines)


class RoutingAlgorithm():
    ''' RoutingAlgorithm new entity object for BlueSky. '''

    @logger.catch
    def __init__(self, mainApp, logger, angle_cutoff=25):
        self.logger = logger
        self.mainApp = mainApp
        self.edges_pesoL = []

        self.HAS_CHANGE_ALTITUDE = 0 # counter to see if there is a change in height (the act of going up to another layer)
        self.bool_has_change_altitude = False # boolean to check if height changed
        self.ALTITUDE_CHANGES_ASCENDING = 0 # all height changes when ascending
        self.ALTITUDE_CHANGES_DESCENDING = 0  # all changes in height when descending
        self.LAYER_CHANGES_DISTANCE_MARGIN = 0  # num of layer changes to exceed distance margin
        self.LAYER_CHANGES_NO_ROUTE = 0  # num of layer changes because there is no path
        self.LAYER_CHANGES_NO_TYPE = 0  # num of layer changes because it does not correspond to the layer for that UAV Type

        #Variables for loitering missions
        self.edges_df_rtree= None
        self.edges_df_dict = None

        # TO disconver if a node i turnNode in fp_evaluations
        self.angle_cutoff = angle_cutoff

    @logger.catch
    def calculate_edges_df_rtree(self, edges):
        # In this method, which is executed before routing, we calculate the base edges_df_rtree
        # which is the dataframe of the streets on the base layer (EmergencyCrusing)
        # create rtree index for each edge

        self.logger.info("calculate_edges_df_rtree processing...")
        self.edges_df_rtree = index.Index()
        self.edges_df_dict = {}
        for i, row in edges.iterrows():
            self.edges_df_rtree.insert(i, row['geometry'].bounds)
            self.edges_df_dict[i] = (row['u'], row['v'])
        self.logger.info("edges_df_rtree calculated!")

    @logger.catch
    def createGeofence(self, fp, glist, fplan_arrivaltime):

        geo_point1 = fp[settings.GEOFENCE_BBOX_POINT1]
        geo_point2 = fp[settings.GEOFENCE_BBOX_POINT2]
        geo_duration = fp[settings.GEOFENCE_DURATION]
        loitering_takeoff = fp[settings.DEPARTURE_INDEX]
        self.logger.info("geo_point1: {}".format(geo_point1))
        self.logger.info("geo_point2: {}".format(geo_point2))
        self.logger.info("geo_duration: {}".format(geo_duration))
        self.logger.info("loitering_takeoff: {}".format(loitering_takeoff))

        # create bbox
        poly_bounds = (eval(geo_point1)[1], eval(geo_point1)[0], eval(geo_point2)[1], eval(geo_point2)[0])
        self.logger.info("poly_bounds: {}".format(poly_bounds))

        try:
            # check the intersecting edges to a polygon
            intersecting_rtree = list(self.edges_df_rtree.intersection(poly_bounds))
            intersecting_edges = np.array([self.edges_df_dict[i] for i in intersecting_rtree], dtype='object')
            self.logger.info("intersecting_edges: {}".format(intersecting_edges))
        except Exception as e:
            self.logger.critical(e)

        if(intersecting_edges.size > 0): # if there are streets that intersect the geofence, the generic occupation tuple is extracted with the mission loitering and blocking air space
            self.logger.info("The geofence will be active for {} seconds".format(geo_duration))
            tinit_geo  = int(fplan_arrivaltime) # we take the time in which the UAV arrives at the starting point of loitering (last routing node)
            tfin_geo = int(tinit_geo) + int(geo_duration)
            tuple_geofence = (tinit_geo, tfin_geo)
            tuple_geofence = str(tuple_geofence)
            self.logger.info("tinit_geo {} and tfin_geo {}; form the tuple {}".format(str(tinit_geo), str(tfin_geo), str(tuple_geofence)))

            # Extract and save all nodes and edges afected by geofence
            # Ej intersecting_edges: [(33344821, 392251) (60631958, 60631775) (393373, 33344821)]
            geo_node_list = []
            geo_edge_list = []
            geo_edge_list_inv = []
            for item in intersecting_edges:
                edgeAB = (item[0], item[1], 0) # tuple u,v,k for normal cruising layers
                self.logger.debug("edgeAB: {}".format(edgeAB))
                geo_edge_list.append(edgeAB)
                edgeAB_inv = (item[1], item[0], 0) # tuple v,u,k for inverted crusing layers
                self.logger.debug("edgeAB_inv: {}".format(edgeAB_inv))
                geo_edge_list_inv.append(edgeAB_inv)

                nodeA = item[0]
                self.logger.debug("nodeA: {}".format(nodeA))
                geo_node_list.append(nodeA)

                nodeB = item[1]
                self.logger.debug("nodeB: {}".format(nodeB))
                geo_node_list.append(nodeB)


            # Remove nodes repeated
            geo_node_list = list(dict.fromkeys(geo_node_list))
            self.logger.debug("geo_node_list: {}".format(geo_node_list))
            self.logger.debug("len(geo_node_list): {}".format(len(geo_node_list)))

            self.logger.debug("geo_edge_list: {}".format(geo_edge_list))
            self.logger.debug("len(geo_edge_list): {}".format(len(geo_edge_list)))

            # Iterate list of graphs:
            for g_cont in range(0,len(glist)):
                nodes, edges = ox.graph_to_gdfs(glist[g_cont])
                nodes.sort_index(inplace=True)
                edges.sort_index(inplace=True)


                for osmid in geo_node_list:
                    ocupation_tuples = nodes.iloc[osmid, settings.INDEX_NP_NODES_OCUPATION]
                    if (ocupation_tuples == '[None]' or ocupation_tuples == ""):
                        nodes.iloc[osmid, settings.INDEX_NP_NODES_OCUPATION] = str([tuple_geofence])  # Insert node ocupation field
                    else:
                        aux_list_nodes = ocupation_tuples
                        aux_list_nodes = list(eval(aux_list_nodes))
                        aux_list_nodes.append(tuple_geofence)
                        nodes.iloc[osmid, settings.INDEX_NP_NODES_OCUPATION] = str(aux_list_nodes)  # Update node ocupation field

                if g_cont%2 == 0: # if g_cont is even; they are normal layers
                    aux_geo_edge = geo_edge_list
                else: # if g_count is odd; they are inverted layers
                    aux_geo_edge = geo_edge_list_inv


                for osmid in aux_geo_edge:
                    ocupation_tuples = edges.loc[osmid, 'Ocupation']
                    if (ocupation_tuples == '[None]' or ocupation_tuples == ""):
                        edges.loc[osmid, 'Ocupation'] = str([tuple_geofence])  # Insert edge ocupation field
                    else:
                        aux_list_edges = ocupation_tuples
                        aux_list_edges = list(eval(aux_list_edges))
                        aux_list_edges.append(tuple_geofence)
                        edges.loc[osmid, 'Ocupation'] = str(aux_list_edges)  # Update edge ocupation field

                glist[g_cont] = ox.graph_from_gdfs(nodes, edges)

        return glist

    @logger.catch
    def edge_gdf_format_from_gpkg(self, edges):
        edge_dict = edges.to_dict()
        edge_gdf = gp.GeoDataFrame(edge_dict, crs = CRS.from_user_input(4326))
        edge_gdf.set_index(['u', 'v', 'key'], inplace = True)
        return edge_gdf

    @logger.catch
    def node_gdf_format_from_gpkg(self, nodes):
        node_dict = nodes.to_dict()
        node_gdf = gp.GeoDataFrame(node_dict, crs = CRS.from_user_input(4326))
        node_gdf.set_index(['osmid'], inplace = True)
        return node_gdf

    @logger.catch
    def get_sec(self, time_str):# Convert hh:mm:ss format to tiemstamp seconds
        h, m, s = time_str.split(':')
        return int(h) * settings.MINUTS_CONVERSION + int(m) * settings.SECONDS_CONVERSION + int(s)

    @logger.catch
    def get_min(self, time_int):# Convert tiemstamp seconds to hh:mm:ss
        timestamp = time.strftime('%H:%M:%S', time.gmtime(time_int))
        return timestamp

    @logger.catch
    def shortest_path(self, G, origin, destination, mode):# Calculate the nodes route from an origin (lat, lon) to a destinetion (lat, lon)
        origin_node, d1 = ox.nearest_nodes(G, origin[1], origin[0], return_dist = True)# (lon, lat)
        dest_node, d2 = ox.nearest_nodes(G, destination[1], destination[0], return_dist = True)# (lon, lat)
        self.logger.debug("shortest_path()=> From {} to {}".format(origin_node,dest_node))
        if mode:
            osmid_route = ox.shortest_path(G, origin_node, dest_node, weight = 'pesoL')
        else:
            osmid_route = ox.shortest_path(G, origin_node, dest_node)
        return osmid_route

    @logger.catch
    def nodeIsFree(self, osmid_node, timestamp_tuple, nodes):# Check if node is free or taked in the timestamp instant (tuple)

        slot_time_list = nodes.iloc[osmid_node, settings.INDEX_NP_NODES_OCUPATION]
        self.logger.debug("Node {}; Ocuppation Time {}; Timestamp_tuple {}".format(osmid_node,slot_time_list,timestamp_tuple))

        if(slot_time_list == '[None]' or slot_time_list == ""):# Free Node
            return True

        else:
            for slot_time in eval(slot_time_list):
                self.logger.trace("SLOT_TIME")
                self.logger.trace(slot_time)
                self.logger.trace(eval(slot_time))
                if(eval(slot_time) == timestamp_tuple):# Unavailable Node
                    return False
                elif(eval(slot_time)[0] <= timestamp_tuple[0] < eval(slot_time)[1]):# Unavailable Node
                    return False
                elif(eval(slot_time)[0] < timestamp_tuple[1] <= eval(slot_time)[1]):# Unavailable Node
                    return False
                elif(timestamp_tuple[0] <= eval(slot_time)[0] < timestamp_tuple[1]):# Unavailable Node
                    return False
                elif(timestamp_tuple[0] < eval(slot_time)[1] <= timestamp_tuple[1]):# Unavailable Node
                    return False
            else:
                return True# Free Node

    @logger.catch
    def edgeIsFree(self, osmid_nodeA, osmid_nodeB, timestamp_tuple, edges, edge_index):# Check if the links between two nodes are free in the slot time
        if(osmid_nodeA == osmid_nodeB):# No edge exist between same nodes
            return True
        else:
            slot_time_list = edges.iloc[edge_index, settings.INDEX_NP_EDGES_OCUPATION]
            self.logger.debug("Edge between {} and {}; Ocuppation Slot Time {}; Slot Timestamp {}".format(osmid_nodeA,osmid_nodeB,slot_time_list,timestamp_tuple))

            if(slot_time_list == '[None]' or slot_time_list == ""):# Free Edge
                return True
            else:
                for slot_time in eval(slot_time_list):
                    if(slot_time != None):
                        if(eval(slot_time) == timestamp_tuple):# Unavailable Edge
                            return False
                        elif(eval(slot_time)[0] <= timestamp_tuple[0] < eval(slot_time)[1]):# Unavailable Edge
                            return False
                        elif(eval(slot_time)[0] < timestamp_tuple[1] <= eval(slot_time)[1]):# Unavailable Edge
                            return False
                        elif (timestamp_tuple[0] <= eval(slot_time)[0] < timestamp_tuple[1]):# Unavailable Edge
                            return False
                        elif (timestamp_tuple[0] < eval(slot_time)[1] <= timestamp_tuple[1]):# Unavailable Edge
                            return False
                else:
                    return True# Free Edge

    @logger.catch
    def travel_time(self, nodeA, nodeB, speed, timestamp_nodeA, edges, fp, nodeC, edge_index):
        if(nodeA == nodeB): # will never enter here because it is limited before the action
            # This case of nodeA==nodeB would only occur at the beginning, therefore tinit = time = departure time
            return self.get_sec(str(fp[settings.DEPARTURE_INDEX])) #departure_time
        else:
            length = edges.iloc[edge_index, settings.INDEX_NP_EDGES_LENGTH]
            self.logger.debug("timestamp_nodeA {} ".format(timestamp_nodeA))
            self.logger.debug("nodeA {} ".format(nodeA))
            self.logger.debug("nodeB {} ".format(nodeB))
            self.logger.debug("length {}".format(length))
            self.logger.debug("speed {}".format(speed))
            slot_time = math.ceil(length / speed)# Ceil: Round up
            self.logger.debug("slot_time traveling: {}".format(slot_time))

            # Discover if nodeB is turnNone
            if(nodeB != nodeC): #if nodeB == nodeC means that is the final node
                try:
                    current_edge = (nodeA, nodeB, 0)
                    next_edge = (nodeB, nodeC, 0)
                    self.logger.debug("DISCOVER turnAngle between current edge {} and next edge {}".format(current_edge, next_edge))
                    int_angle_dict = eval(edges.iloc[edge_index, settings.INDEX_NP_EDGES_INTANGLE])
                    self.logger.debug("int_angle_dict: {}".format(int_angle_dict))
                    int_angle = int_angle_dict[next_edge]
                    self.logger.debug("int_angle: {}".format(int_angle))

                    if int_angle < 180 - int(self.angle_cutoff):
                        self.logger.info("nodeB {} is turnNone".format(nodeB))

                        if (int_angle >= 25 and int_angle < 100):
                            turn_duration = settings.S2_TURNNODE_OCCUPATION_TIME_PASS
                        elif (int_angle >= 100 and int_angle < 150):
                            turn_duration = settings.S5_TURNNODE_OCCUPATION_TIME_PASS
                        elif (int_angle >= 150):
                            turn_duration = settings.S10_TURNNODE_OCCUPATION_TIME_PASS
                        else:
                            turn_duration = settings.DEFAULT_TURNNODE_OCCUPATION_TIME_PASS

                        self.logger.debug("int_angle {} < angle_cutoff (180-{}) so is turnNode; add turn_duration {} to slot_time".format(int_angle, self.angle_cutoff, turn_duration))



                        slot_time = slot_time + int(turn_duration)
                        self.logger.debug("new slot_time traveling considering turnNode: {}".format(slot_time))
                    else:
                        self.logger.debug("nodeB {} is NOT turnNone".format(nodeB))

                except Exception as e:
                    self.logger.critical(e)


            if(length == 9999.9):
                self.logger.critical("COLISION WITH GEOFENCE; return None and find other solution")
                return None
            else:
                return slot_time

    @logger.catch
    def elevatorNodes(self, orig_nodeId, fp, isFirstLayer, isLastLayer, ascenso, glist, g_cont):

        # nodes and edges of LAYER_A are those corresponding to the current layer g_cont
        # nodes and edges of LAYER_B are those corresponding to the next layer: if it is ascent g_cont+1 and if it is descent g_cont-1
        # always checking from source that the transitions g_cont+1 and g_cont-1 respectively are possible (to avoid indexOutOfRange glist)


        self.logger.debug("Origin node in the elevator: {}".format(str(orig_nodeId)))
        self.logger.debug("isFirstLayer: {}".format(str(isFirstLayer)))
        self.logger.debug("isLastLayer: {}".format(str(isLastLayer)))
        self.logger.debug("ascending: {}".format(str(ascenso))) #'UP': true or 'DOWN': false

        if (ascenso):
            index_layerB = g_cont + 1
        else:
            index_layerB = g_cont - 1

        self.logger.info("index_layerA (g_cont): {}".format(g_cont))
        self.logger.info("index_layerB: {}".format(index_layerB))

        nodesLayerA, edgesLayerA = ox.graph_to_gdfs(glist[g_cont])
        nodesLayerB, edgesLayerB = ox.graph_to_gdfs(glist[index_layerB])
        nodesLayerA.sort_index(inplace=True)
        nodesLayerB.sort_index(inplace=True)
        edgesLayerA.sort_index(inplace=True)
        edgesLayerB.sort_index(inplace=True)


        try:
            ocupation_tuples_layerA = list(eval(nodesLayerA.iloc[orig_nodeId, settings.INDEX_NP_NODES_OCUPATION]))  # TODO: LOC CALL
            self.logger.info("ocupation_tuples_layerA: {}".format(ocupation_tuples_layerA))
        except:
            ocupation_tuples_layerA = [None]

        try:
            ocupation_tuples_layerB = list(eval(nodesLayerB.iloc[orig_nodeId, settings.INDEX_NP_NODES_OCUPATION]))  # TODO: LOC CALL
            self.logger.info("ocupation_tuples_layerB: {}".format(ocupation_tuples_layerB))
        except:
            ocupation_tuples_layerB = [None]

        if (ascenso):  # if ascending in the elevator
            self.logger.info("ASCENDING...")
            self.ALTITUDE_CHANGES_ASCENDING += 1

            # We calculate the occupancy tuple of the destination node we are going to based on the origin node we start from
            # (destinations are higher than origins)

            if(isFirstLayer): # If I haven't really taken off yet. I start from layer 0, I take the takeoff time as tinit too
                tinit = int(self.get_sec(str(fp[settings.DEPARTURE_INDEX]))) # we take initial takeoff time (departure_time)
                self.logger.debug("tinit {} by the if".format(tinit))

            elif (ocupation_tuples_layerA == [None] or ocupation_tuples_layerA == ""):  # no tuple assigned yet, first time ascending occurs
                tinit = int(self.get_sec(str(fp[settings.DEPARTURE_INDEX]))) # we take initial takeoff time (departure_time)
                self.logger.debug("tinit {} by the elif".format(tinit))

            else:  # con tupla previa
                lastOcupation = eval(ocupation_tuples_layerA[-1])
                tinit = lastOcupation[1]
                self.logger.debug("tinit {} by the else".format(tinit))

            self.logger.debug("tinit is {}".format(tinit))


        else: # if descending in the elevator
            self.logger.info("DESCENDING...")
            self.ALTITUDE_CHANGES_DESCENDING += 1

            # We calculate the occupancy tuple of the destination node we are going to based on the origin node we start from
            # (destinations are lower than origins)

            # ALWAYS with previous tuple because it is assumed that I have already ascended
            lastOcupation = eval(ocupation_tuples_layerA[-1])
            tinit = lastOcupation[1]
            self.logger.debug("tinit is {}".format(tinit))


        # We calculate tuples of time of departure and arrival of the elevator
        tiA = int(tinit)
        if (isFirstLayer):  # If I am in the first layer or in the last
            tfA = tiA + int(settings.NODE_OCCUPATION_TIME_PASS) + int(settings.NODE_OCCUPATION_TIME_PASS) + int(settings.NODE_OCCUPATION_TIME_VERT) + int(settings.ASCENSDING_TAKEOFF) # how much time does the pair of nodes occupy and how long does it take to go up/down
        elif (isLastLayer):  # If I am in the first layer or in the last
            tfA = tiA + int(settings.NODE_OCCUPATION_TIME_PASS) + int(settings.NODE_OCCUPATION_TIME_PASS) + int(settings.NODE_OCCUPATION_TIME_VERT)  # how much time does the pair of nodes occupy and how long does it take to go up/down
        else:  # if it is already from the first layer, we do not take into account one of the node occupation times
            tfA = tiA + int(settings.NODE_OCCUPATION_TIME_PASS) + int(settings.NODE_OCCUPATION_TIME_VERT)  # How much time does the node I go to occupy and how long does it take to go up/down
        tupleA = (tiA, tfA)
        # We block nodeB as nodeA with the same occupancy tuple to block the up/down segment
        tiB = tiA
        tfB = tfA
        tupleB = (tiB, tfB)
        self.logger.info("elevatorNodes() output with tupleA (tiA,tfA) {} and tupleB (tiB,tfB) {}".format(tupleA, tupleB))


        # Whether ascending or descending, I check if nodeB is Free (which has the same id as starting nodeA = orig_nodeId) but on the other layer:
        if (self.nodeIsFree(orig_nodeId, tupleA, nodesLayerA) is False):  # NOT FREE NodeA in LayerA for this tupleA
            self.logger.warning("node id: {} with tuple {} in currentlayer ,is NOT FREE".format(orig_nodeId, tupleA))
            self.logger.warning("PATH NOT POSSIBLE because nodeIsNOTFree in elevator at origin; FPLAN PENDING")
            return None
        elif (self.nodeIsFree(orig_nodeId, tupleB, nodesLayerB) is False):  # NOT FREE NodeB in LayerB for this tupleB
            self.logger.warning("node id: {} with tuple {} in nextlayer ,is NOT FREE".format(orig_nodeId, tupleB))
            self.logger.warning("PATH NOT POSSIBLE because nodeIsNOTFree in elevator on destination; FPLAN PENDING")
            return None

        else: # FREE NodeB in LayerB for this tupleB
            # # We lock nodeA of source layer
            # if (ocupation_tuples_layerA == [None] or ocupation_tuples_layerA == ""):
            #     aux = [str(tupleA)]
            #     self.logger.debug(str(aux))
            #     nodesLayerA.iloc[orig_nodeId, settings.INDEX_NP_NODES_OCUPATION] = str(aux)  # Insert node ocupation field
            # else:
            #     aux = str(tupleA)
            #     ocupation_tuples_layerA.append(aux)
            #     self.logger.debug(str(ocupation_tuples_layerA))
            #     nodesLayerA.iloc[orig_nodeId, settings.INDEX_NP_NODES_OCUPATION] = str(ocupation_tuples_layerA)  # Update node ocupation field
            # self.logger.info("Updated/locked origin node {} for layer altitude change ({})".format(str(orig_nodeId),g_cont))
            # # Update grafoA
            # glist[g_cont] = ox.graph_from_gdfs(nodesLayerA, edgesLayerA)

            # We block destination layer nodeB
            if (ocupation_tuples_layerB == [None] or ocupation_tuples_layerB == ""):
                aux = [str(tupleB)]
                self.logger.debug(str(aux))
                nodesLayerB.iloc[orig_nodeId, settings.INDEX_NP_NODES_OCUPATION] = str(aux)  # Insert node ocupation field
            else:
                aux = str(tupleB)
                ocupation_tuples_layerB.append(aux)
                self.logger.debug(str(ocupation_tuples_layerB))
                nodesLayerB.iloc[orig_nodeId, settings.INDEX_NP_NODES_OCUPATION] = str(ocupation_tuples_layerB)  # Update node ocupation field
            self.logger.info("Updated/locked destination node {} for layer altitude change ({})".format(str(orig_nodeId),index_layerB))
            # Update grafoB
            glist[index_layerB] = ox.graph_from_gdfs(nodesLayerB, edgesLayerB)
            return glist

    @logger.catch
    def delayPendingFplan(self, fplan):
        if (fplan[settings.STATUS_INDEX] == settings.PENDING_STATUS):  # We delay the takeoff time to fplan PENDING
            current_departure_time = self.get_sec(fplan[settings.DEPARTURE_INDEX])
            delay = current_departure_time + settings.DEPARTURE_DELAY
            if(delay <= settings.MAX_DELAYED_TIME):
                self.logger.info("delay {} <= settings.MAX_DELAYED_TIME {}".format(delay,settings.MAX_DELAYED_TIME))
                delayed_flight_time = self.get_min(delay)
                self.logger.info("Fplan {} delayed with {} seconds. Format hh:mm:ss is {}".format(fplan[settings.FPLAN_ID_INDEX], delay,delayed_flight_time))
                fplan[settings.DEPARTURE_INDEX] = delayed_flight_time
                return fplan
        return None


    @logger.catch
    def get_paths(self, fp_plans, glist):
        paths = []
        isFirstLayer = False
        isLastLayer = False


        for i, fp in enumerate(fp_plans):

            self.bool_has_change_altitude = False
            fplan_id = str(fp[settings.FPLAN_ID_INDEX])
            self.logger.success("FPLAN: {}".format(fplan_id))

            # orig on tuple sending_point of flight_intention
            # fin on tuple receiving_point of flight_intention
            orig, fin = tuple(float(s) for s in fp[settings.INITIAL_LOCATION_INDEX].strip('()').split(',')), \
                        tuple(float(s) for s in fp[settings.FINAL_LOCATION_INDEX].strip('()').split(','))

            cont = True

            # CHECK FP TYPE UAV AND ASSIGN GLIST intervals (layernames_routing.txt has 7 layers)
            if (fp[settings.PRIORITY_INDEX] == '4'): # fit only on layer [index 0]. EMERGENCY FLIGHTS
                 iv1 = pd.Interval(left=6, right=7, closed='left') #[6]
            elif (fp[settings.VEHICLE_INDEX] == settings.TIPO1): # fit only on layer [index 1,2,3] for drones of TYPE1
                iv1 = pd.Interval(left=0, right=3, closed='left') #[0,1,2]
            elif (fp[settings.VEHICLE_INDEX] == settings.TIPO2): # fit only in layer [index 4,5,6] for TYPE2 drones
                iv1 = pd.Interval(left=3, right=6, closed='left') #[3,4,5]
            else: # matches any layer from 1st[index 0] to 7th[index 6]
                iv1 = pd.Interval(left=0, right=7, closed='left') #[0,1,2,3,4,5,6]


            self.logger.success("UAV {} with iv1 {} ".format(fp[settings.VEHICLE_INDEX],iv1))
            g_cont = 0

            # backup nodes,edges point to recovery in case of early_stop shortest_path and try again from ground
            # original_glist = glist.copy()

            while(g_cont < len(glist)):

                self.logger.info("Enter in while loop with g_cont: {}".format(g_cont))
                if (cont is False):  # if cont passes to False it means that we have found a path or it has been impossible to assign that fp and we break this for loop to go to the next fplan
                    self.logger.info("Break while to evaluate next fplan!")
                    break

                if (g_cont == 0):
                    isFirstLayer = True
                    self.logger.info("YES isFirstLayer")
                else:
                    isFirstLayer = False
                    self.logger.info("NO isFirstLayer")

                # We calculate the nearest_node with respect to the current position orig (sending_point)
                orig_nodeId, d1 = ox.nearest_nodes(glist[g_cont], orig[1], orig[0], return_dist=True)  # (orig[1]=lon, orig[0]=lat)

                if(g_cont in iv1): # I'm in a layer that corresponds to me
                    self.logger.info("Im in a layer that corresponds to me")
                    g_aux = glist[g_cont]
                    edges_index_dict = {}

                    self.logger.success("SEARCH FOR A NEW SOLUTION")
                    early_stop = 0
                    retorno_delay = None
                    solution1_shortest_path = None
                    flag_exceeded_attempts = False
                    while True:
                        if(early_stop == settings.EARLY_STOP_NUMBER): # If we have reached the maximum number of attempts, we delay the flight and try again
                            self.logger.warning("early_stop limit: {} ".format(early_stop))
                            self.logger.critical("Number of attempts of the shortest paths exceeded, we force change of height")
                            fp[settings.STATUS_INDEX] = settings.PENDING_STATUS
                            flag_exceeded_attempts = True
                            break


                            # glist = original_glist.copy()
                            # self.logger.warning("Recovery backup nodes of edges of glist in the layer {}".format(g_cont))
                            #
                            # retorno_delay = self.delayPendingFplan(fp)
                            # if(retorno_delay is None):  # WAS NOT POSSIBLE TO DELAY FPLAN
                            #     self.logger.critical("MAX_DELAYED_TIME exceed")
                            #     cont = False # IMPORTANT: BREAK WHILE THROUGH FLAG TO CONTINUE WITH OTHER FPLAN
                            #     break # Break this while True
                            # else: # WAS POSSIBLE TO DELAY FPLAN
                            #     break # Break this while True
                            #
                            # early_stop = 0


                        self.logger.info("Num try {} fp_evaluations in get_paths()".format(early_stop))
                        path = self.fp_evaluations(fp, g_aux, g_cont, solution1_shortest_path)
                        self.logger.info("path[0] after fp_evaluations attempt: {}".format(path[0]))
                        solution1_shortest_path = path[3]

                        if(path[0] == -1): # if checkingPreFlight was not valid, delay flight immediately
                            self.logger.warning("try delayed")
                            fp[settings.STATUS_INDEX] = settings.PENDING_STATUS
                            retorno_delay = self.delayPendingFplan(fp)
                            if(retorno_delay is None):  # WAS NOT POSSIBLE TO DELAY FPLAN
                                self.logger.critical("MAX_DELAYED_TIME exceed")
                                cont = False # IMPORTANT: BREAK WHILE THROUGH FLAG TO CONTINUE WITH OTHER FPLAN
                                break # Break this while True
                            else: # WAS POSSIBLE TO DELAY FPLAN
                                break # Break this while True



                        elif (path[0] == 0): # if no route was found because it was busy in that attempt, we update and keep looping
                            self.logger.warning("try pending")
                            fp[settings.STATUS_INDEX] = settings.PENDING_STATUS
                            g_aux = path[1].copy()
                            # continue while

                        elif (path[0] == None):  # it means that the shortest_path does not find a possible path in that layer, we break the loop to handle it below
                            self.logger.warning("try not valid")
                            fp[settings.STATUS_INDEX] = settings.PENDING_STATUS
                            break

                        elif not(path[0] == 0): # if the route has been found, it is because it is not busy in that attempt, we update and break the loop to calculate the ideal route and compare
                            self.logger.success("try approved")
                            g_aux = path[1].copy()
                            edges_index_dict = path[2]
                            break

                        else:
                            self.logger.critical("CASE NOT CONSIDERED")

                        early_stop += 1


                    if(retorno_delay != None): #it means that WAS POSSIBLE TO DELAY FPLAN. So start while again
                        # IMPORTANT: RESET WHILE COUNTER TO START FROM THE BEGUINNING LAYER
                        g_cont = 0
                        continue


                    if(cont != False):
                        nodesLayerA, edgesLayerA = ox.graph_to_gdfs(g_aux)
                        del g_aux
                        nodesLayerA.sort_index(inplace=True)
                        edgesLayerA.sort_index(inplace=True)

                        # alt_actual_layer = edgesLayerA.iloc[0].height  # Horizontal performance layer altitude (at the layer height where it is actually flown)

                        alt_actual_layer = settings.SEPARATION_CRUISING_LAYERS * (g_cont+1)
                        self.logger.success("We are in the layer with altitude: {}".format(alt_actual_layer))
                        self.logger.success("END horizontal scrolling {}".format(fplan_id))
                        self.logger.success("fp_evaluation route (horizontal): {}".format(path[0]))

                        if (path[0] != 0 and path[0] != None and flag_exceeded_attempts != True):
                            # WE HAVE COME TO FIND A ROUTE TO THE LAST HORIZONTAL NODE
                            glist[g_cont] = path[1]  # we update Graph updated in the glist because there is a route

                            # HERE WE CLEAN STREETS GRAPH PESO_L IN [G_CONT]
                            self.logger.warning("pesoL cleaning point")
                            for e in self.edges_pesoL:
                                try:
                                    # index_edge = edges_index_dict[e]
                                    edgesLayerA.loc[e, 'pesoL'] = edgesLayerA.loc[e, 'length']
                                except:
                                    self.logger.warning("exception in pesoL cleaning point")
                                    new_e = (e[1],e[0],0) #invert u and v
                                    edgesLayerA.loc[new_e, 'pesoL'] = edgesLayerA.loc[new_e, 'length']

                                glist[g_cont] = ox.graph_from_gdfs(nodesLayerA, edgesLayerA)
                            self.edges_pesoL.clear()

                            # elevator down
                            self.logger.info("Change altitude to go down to ground (until layer zero -> g_list[0]) from current layer ({})".format(g_cont))
                            orig_nodeId = path[0][-1]
                            self.logger.info("Descent node for altitude change: {}".format(str(orig_nodeId)))

                            retorno = -1
                            g_cont_desc = 0
                            if (g_cont -1 >= 0):  # There are free layers underneath
                                g_cont_desc = 0
                                for i in range(g_cont+1, 0, -1): # descent (goes down to 0; the -1 is not included)
                                    # This for for 3 layers that is, 3 elements in glist with indices [2][1][0], the i goes through 3,2,1

                                    if (i == g_cont+1):
                                        isLastLayer = True
                                    else:
                                        isLastLayer = False

                                    g_cont_desc = i-1 # always 1 less because the index of g_list goes up to [0]

                                    if(g_cont_desc==0): # I break loop when I hit the ground
                                        break # break loop for to descending process

                                    self.logger.debug("g_cont_desc VALUE: {}".format(g_cont_desc))
                                    self.logger.debug("i VALUE: {}".format(i))

                                    self.logger.info("Altitude change (DESCENDING...) because I am in the process of landing")
                                    self.logger.info("Origin node for altitude change: {}".format(str(orig_nodeId)))

                                    retorno = self.elevatorNodes(orig_nodeId, fp, isFirstLayer, isLastLayer, False, glist, g_cont_desc)
                                    if (retorno is None): # ELEVATION NOT VALID. WE HAVE TO BREAK DE FOR LOOP WITH DESCENDING PROCESS
                                        break #break this for
                                    else: # ELEVATION VALID. GLIST UPDATED; AND THE FOR LOOP CONTINUE IN DESCENDING PROCESS
                                        glist = retorno


                            if (retorno == None): # PROBLEM IN DESCENDING PROCESS. NODES BUSY
                                # ELEVATION NOT VALID. DELAY FLIGHT PLAN AND RESET WHILE
                                fp[settings.STATUS_INDEX] = settings.PENDING_STATUS
                                fp = self.delayPendingFplan(fp)

                                if (fp == None):  # WAS NOT POSSIBLE TO DELAY FPLAN
                                    self.logger.critical("MAX_DELAYED_TIME exceed")
                                    cont = False
                                    break  # IMPORTANT: BREAK WHILE TO CONTINUE WITH OTHER FPLAN

                                else:  # WAS POSSIBLE TO DELAY FPLAN
                                    # IMPORTANT: RESET WHILE COUNTER TO START FROM THE BEGUINNING LAYER
                                    g_cont = 0
                                    continue

                            else: # here it enters when g_cont_desc is already 0
                                self.logger.debug("g_cont is: {}".format(g_cont))
                                self.logger.debug("g_cont_desc is: {}".format(g_cont_desc))
                                aux_glist = glist[g_cont_desc]
                                # We have reached the "ground" layer (the lowest)
                                # we are at the lowest layer, we don't have to descend any further, we are at the final and destination node
                                # or we have already made the appropriate descendings by setting the descending node occupation times
                                self.logger.success("THERE ARE NO MORE LAYERS TO LOWER. ROUTE FINISHED\n")
                                fp[settings.STATUS_INDEX] = settings.APPROVED_STATUS

                                # WE HAVE COME TO FIND A ROUTE FROM FLOOR TO FLOOR
                                # glist[g_cont] = aux_glist  # we update Graph updated in the glist because there is a route

                                # Get nodesLayerA lowest layer
                                # TODO: Implement in elevatorNodes
                                nodesLowestLayerA, edgesLowestLayerA = ox.graph_to_gdfs(aux_glist)
                                nodesLowestLayerA.sort_index(inplace=True)
                                edgesLowestLayerA.sort_index(inplace=True)

                                try:
                                    ocupation_orig_nodeId = nodesLowestLayerA.iloc[orig_nodeId, settings.INDEX_NP_NODES_OCUPATION]
                                    self.logger.debug("Query last node {}: {} ".format(orig_nodeId, ocupation_orig_nodeId))
                                    aux_list = eval(ocupation_orig_nodeId)[-1]
                                    fplan_arrivaltime = eval(aux_list)[1]
                                    self.logger.info("fplan_arrivaltime: {}".format(fplan_arrivaltime))
                                except:
                                    self.logger.critical("ERROR: ocupation_orig_nodeId is empty: {}".format(ocupation_orig_nodeId))

                                # We create a dictionary of heights through which the route path[0] has passed
                                # (Elevator floors it goes up + horizontal heights of the last layer + floors it goes down)
                                dict_nodes_alt = {}
                                self.logger.success("alt_actual_layer : {}".format(alt_actual_layer))

                                for node_id in path[0]: # for to pad all tuples to the same height for all node_id
                                    dict_nodes_alt[node_id] = (alt_actual_layer,)
                                self.logger.debug(dict_nodes_alt)

                                paths.append((dict_nodes_alt, fp[settings.FPLAN_ID_INDEX], fp[settings.DEPARTURE_INDEX], fp[settings.VEHICLE_INDEX]))
                                self.mainApp.buildScenarioUnitary(g_cont,dict_nodes_alt,fp[settings.FPLAN_ID_INDEX], fp[settings.DEPARTURE_INDEX], fp[settings.PRIORITY_INDEX], str(fplan_arrivaltime), str(fp[settings.VEHICLE_INDEX]), fp, edges_index_dict)

                                # At this point we check if that mission was loitering to do a higher processing
                                # with the createGeofence() method given:
                                # a bbox (point1, point2) of the geofence
                                # geofence duration
                                # loitering mission takeoff time
                                # an edges_df_rtree with all streets initially precomputed for the base layer
                                # CALCULATES: the polygon of the geofence and returns the edges and nodes affected and sets the occupation of nodes and edges of that reserved air space
                                if(len(fp)> 8): # if it has more than 8 parameters, it is a loitering mission
                                    self.logger.warning("IS A MISSION LOITERING WITH ID: {} and geofence {}{} of duracion {}".format(fp[settings.FPLAN_ID_INDEX], fp[settings.GEOFENCE_BBOX_POINT1], fp[settings.GEOFENCE_BBOX_POINT2], fp[settings.GEOFENCE_DURATION]))
                                    glist = self.createGeofence(fp, glist, fplan_arrivaltime)

                                self.logger.success("POSSIBLE AND ASSIGNED ROUTE\n\n")
                                cont = False  # we stop searching the layer list (glist)
                                break  # IMPORTANT: BREAK WHILE TO CONTINUE WITH OTHER FPLAN



                        else: # I am in a layer where there is no possible route, I change altitude (ASCENDING...)
                            self.logger.info("Altitude change because there is no path possible on that layer")
                            self.bool_has_change_altitude = True
                            self.LAYER_CHANGES_NO_ROUTE += 1
                            self.logger.info("Origin node for hange altitude: {}".format(str(orig_nodeId)))

                            if (g_cont + 1 < len(glist)):  # There are free layers above
                                retorno = self.elevatorNodes(orig_nodeId, fp, isFirstLayer, isLastLayer, True, glist,g_cont)
                                if (retorno is None): # ELEVATION NOT VALID. DELAY FLIGHT PLAN AND RESET WHILE
                                    fp[settings.STATUS_INDEX] = settings.PENDING_STATUS
                                    fp = self.delayPendingFplan(fp)

                                    if (fp == None):
                                        self.logger.critical("MAX_DELAYED_TIME exceed")
                                        cont = False
                                        break # IMPORTANT: BREAK WHILE TO CONTINUE WITH OTHER FPLAN

                                    else: # WAS POSSIBLE TO DELAY FPLAN
                                        # IMPORTANT: RESET WHILE COUNTER TO START FROM THE BEGUINNING LAYER
                                        g_cont = 0
                                        continue

                                else: # ELEVATION VALID. GLIST UPDATED TO NEXT HORIZONTAL PROCEDURE
                                    glist = retorno

                            else:  # we are in the last layer, there is no resolution possible with this strategy of changing layers
                                self.logger.critical("THERE ARE NO MORE LAYERS. ROUTE NOT POSSIBLE")
                                fp[settings.STATUS_INDEX] = settings.PENDING_STATUS
                                cont = False
                                break  # IMPORTANT: BREAK WHILE TO CONTINUE WITH OTHER FPLAN

                else: # I am in a layer that does not correspond to me, I change altitude (ASCENDING...)
                    self.logger.info("Altitude change (ASCENDING...) because the layer for the type of UAV does not correspond")
                    self.bool_has_change_altitude = True
                    self.LAYER_CHANGES_NO_TYPE += 1
                    self.logger.info("Origin node for height change: {}".format(str(orig_nodeId)))

                    if (g_cont + 1 < len(glist)):  # There are free layers above
                        retorno = self.elevatorNodes(orig_nodeId, fp, isFirstLayer, isLastLayer, True, glist, g_cont)
                        if (retorno is None): # ELEVATION NOT VALID. DELAY FLIGHT PLAN AND RESET WHILE
                            fp[settings.STATUS_INDEX] = settings.PENDING_STATUS
                            fp = self.delayPendingFplan(fp)
                            if (fp == None): # WAS NOT POSSIBLE TO DELAY FPLAN
                                self.logger.critical("MAX_DELAYED_TIME exceed")
                                cont = False
                                break # IMPORTANT: BREAK WHILE TO CONTINUE WITH OTHER FPLAN
                            else: # WAS POSSIBLE TO DELAY FPLAN
                                # IMPORTANT: RESET WHILE COUNTER TO START FROM THE BEGUINNING LAYER
                                g_cont = 0
                                continue

                        else: # ELEVATION VALID. GLIST UPDATED TO NEXT HORIZONTAL PROCEDURE
                            glist = retorno

                    else:  # we are in the last layer, there is no resolution possible with this strategy of changing layers
                        self.logger.critical("THERE ARE NO MORE LAYERS. ROUTE NOT POSSIBLE")
                        fp[settings.STATUS_INDEX] = settings.PENDING_STATUS
                        cont = False
                        break # IMPORTANT: BREAK WHILE TO CONTINUE WITH OTHER FPLAN


                g_cont += 1
                self.logger.info("g_cont incremented: {}".format(g_cont))
        return paths

    @logger.catch
    def fp_evaluations(self, fp, G, layer_index, solution1_shortest_path): # horizontal movements. layer_index the index (g_cont) of the current layer (it marks the altitude where we are)
        nodes_route = None
        edges_index_dict = {}  # key (nodeA, nodeB, k) and value index in geodataframe

        if(fp[settings.STATUS_INDEX] == settings.PENDING_STATUS):
            nodes_route = self.shortest_path(G,
                                        tuple(float(s) for s in fp[settings.INITIAL_LOCATION_INDEX].strip('()').split(',')),
                                        tuple(float(s) for s in fp[settings.FINAL_LOCATION_INDEX].strip('()').split(',')), True)

            if(nodes_route != None):

                if(nodes_route == solution1_shortest_path): # compare two list of nodes_route (first and second attempt)
                    self.logger.warning('shortest_path solutions -> nodes_route1 == nodes_route2. Return path (-1,G) to delay fplan')
                    return (-1, G, edges_index_dict, nodes_route)
                else:

                    # nodes_route valid
                    departure_time = int(self.get_sec(str(fp[settings.DEPARTURE_INDEX])))
                    speed = json.load(open(settings.AIRCRAFT_PATH))[str(fp[settings.VEHICLE_INDEX])]['envelop']['cruising_speed']
                    nodes, edges = ox.graph_to_gdfs(G)
                    nodes.sort_index(inplace=True)
                    edges.sort_index(inplace=True)
                    self.logger.success("Generated Path: {}".format(nodes_route))
                    self.logger.success("Number of nodes: {}".format(len(nodes_route)))
                    self.logger.success("layer_index: {}".format(layer_index))



                    if(len(nodes_route) > 0):

                        nodeA = nodes_route[0]

                        #First of all, check if nodeA can operate on the layers according to their take off time
                        if(layer_index == 0): # if we are in first layer
                            node_slot_time = (int(departure_time), int(departure_time + settings.ASCENSDING_TAKEOFF+(settings.NODE_OCCUPATION_TIME_VERT * 2))) # is the estimated ascending ocupation in the elevator from the takeoff to the upper layer (3layers/type, so 2 segments)
                            self.logger.info("CHECKING PREFLIGHT...")

                            if(self.nodeIsFree(nodeA, node_slot_time, nodes)): # if True, preflight approved to this departure_time
                                self.logger.success('Preflight approved to this departure_time. Continue process')
                            else: # if False, preflight denied to this departure_time, so abort and delay flightplan in get_paths
                                self.logger.warning('Preflight denied to this departure_time, so abort and delay flightplan. Return path (-1,G)')
                                return (-1, G, edges_index_dict, nodes_route)


                        nodes_time = {}
                        edges_slotTime = {}

                        contNodesEval = 0
                        lastTimeCheckpoint = departure_time # default

                        # When I arrive at a floor by elevator to start the possible horizontal movement...
                        # if it is the first layer (layer_index=0), I rely on the departure time as the starting point (lastTimeCheckpoint = departure_time is already set above by default)
                        # if not first layer (layer_index>0), rely on current occupancy tuple as starting point
                        try:
                            ocupation_tuples = nodes.iloc[nodeA, settings.INDEX_NP_NODES_OCUPATION]
                        except:
                            ocupation_tuples = '[None]'

                        if(layer_index>0):
                            try:
                                ocupation_tuples = list(eval(ocupation_tuples))
                            except:
                                ocupation_tuples = [None]

                            if(ocupation_tuples != [None] and ocupation_tuples != ""):
                                aux_list_nodes_enplanta = eval(ocupation_tuples[-1])
                                self.logger.debug("aux_list_nodes_enplanta: {}".format(aux_list_nodes_enplanta))
                                lastTimeCheckpoint = aux_list_nodes_enplanta[1]
                                self.logger.debug("lastTimeCheckpoint (based on current occupancy tuple; I am NOT at home layer or going up; layer_index is {}): {}".format(layer_index,lastTimeCheckpoint))
                        else:
                            self.logger.debug("lastTimeCheckpoint (based on takeoff time; If I am in the start layer; Im in {}): {}".format(layer_index,lastTimeCheckpoint))

                        index_aux = 0
                        edge_index = None
                        for node_id in nodes_route:

                            nodeB = node_id
                            nodeC =  nodeB # positioning the nodeC first in nodeB

                            if(index_aux < len(nodes_route)-2): # if is possible positioning the nodeC one futher
                                nodeC = nodes_route[index_aux+2]

                            self.logger.debug("nodeA: {}".format(nodeA))
                            self.logger.debug("nodeB: {}".format(nodeB))
                            self.logger.debug("nodeC: {}".format(nodeC))

                            self.logger.debug("Next step...")

                            if(nodeA == nodeB): #Si es el mismo nodo, continuo a la siguiente iteración del for
                                self.logger.debug("nodeA ({})y nodeB ({}) are equals; continue next iteration loop for".format(nodeA, nodeB))
                                continue

                            # Calculate edge_index and add to edges_index_dict={}
                            edge_index = list(edges.index.values).index((nodeA, nodeB, 0))
                            edges_index_dict[(nodeA, nodeB, 0)] = edge_index
                            self.logger.info("edges_index_dict[{}] = {}".format((nodeA, nodeB, 0), edge_index))


                            timestamp_nodeA = lastTimeCheckpoint
                            time = self.travel_time(nodeA, nodeB, speed, timestamp_nodeA, edges, fp, nodeC, edge_index)
                            if(time == None): #GEOFENCE DETECTED. ABORT SOLUTION AND FIND OTHER
                                self.logger.warning('shortest_path method in fp_evaluations() did not find a possible route caused by GEOFENCE. Return path (None, G)')
                                return (None, G, edges_index_dict, nodes_route)

                            else:
                                self.logger.debug("travel_time from A {} to B {}: {}".format(nodeA, nodeB, time))
                                timestamp_nodeB = timestamp_nodeA + time + settings.NODE_OCCUPATION_TIME_PASS
                                self.logger.debug("timestamp_nodeB (timestamp_nodeA+traveltime+NODE_OCCUPATION_TIME_PASS) {}".format(timestamp_nodeB))

                                if(contNodesEval == 0 and layer_index == 0): # from origin node, we take into account both node occupations
                                    self.logger.debug("Evaluation is from horizontal origin node (so... +NODE_OCCUPATION_TIME_PASS +ASCENSDING_TAKEOFF)")
                                    node_slot_time =  (int(timestamp_nodeA), int(timestamp_nodeB + settings.NODE_OCCUPATION_TIME_PASS) + int(settings.ASCENSDING_TAKEOFF)) # How much time does the node occupy and how long does it take to cross the street?
                                else: # it is not from the origin node, we only take into account the occupation of the destination node
                                    self.logger.debug("Evaluation is NOT from horizontal origin node")
                                    node_slot_time =  (int(timestamp_nodeA), int(timestamp_nodeB)) # How much time does the node occupy and how long does it take to cross the street?
                                self.logger.info("node_slot_time of {}: {}".format(node_id,node_slot_time))

                                if(self.nodeIsFree(nodeA, node_slot_time, nodes) and self.nodeIsFree(node_id, node_slot_time, nodes)):# Free Node origen (nodeA) and destination(nodeB = node_id)
                                    edge_slot_time = node_slot_time # The occupation time of the street will be the same as the occupation time of the nodes that make it up

                                    if(self.edgeIsFree(nodeA, nodeB, edge_slot_time, edges, edge_index)):# Free Edge

                                        if(nodeA != nodeB):
                                            self.logger.debug("nodeA ({}) y nodeB ({}) son distintos ".format(nodeA,nodeB))
                                            contNodesEval +=1
                                            #Assign tuple NodeA
                                            nodes_time[nodeA] = str(node_slot_time) # is a node occupancy time tuple
                                            self.logger.debug("nodes_time[nodeA]: {}".format(nodes_time[nodeA]))
                                            #Assign tuple NodeB
                                            nodes_time[node_id] = str(node_slot_time) # is a node occupancy time tuple
                                            self.logger.debug("nodes_time[nodeB]: {}".format(nodes_time[nodeB]))
                                            lastTimeCheckpoint = int(eval(nodes_time[nodeB])[1])
                                            self.logger.debug("lastTimeCheckpoint: {}".format(lastTimeCheckpoint))
                                            edges_slotTime[(nodeA, nodeB, 0)] = str(edge_slot_time) # is a street occupancy time tuple
                                            self.logger.debug("edges_slotTime[(nodeA, nodeB, 0)]: {}".format(edges_slotTime[(nodeA, nodeB, 0)]))
                                        else:
                                            self.logger.debug("nodeA ({}) and nodeB ({}) are equal; next in nodes_route".format(nodeA,nodeB))


                                    else:# Unavailable Edge
                                        self.logger.warning('Unavailable Edge {} {}'.format(nodeA, nodeB))
                                        #edges.iloc[edge_index, settings.INDEX_NP_EDGES_PESOL] = settings.MAX_PESOL# Update 'pesoL' field
                                        edges.loc[(nodeA, nodeB, 0), 'pesoL'] = settings.MAX_PESOL  # Update 'pesoL' field
                                        G = ox.graph_from_gdfs(nodes, edges)
                                        #Añado calle a lista de edges_pesoL
                                        self.edges_pesoL.append((nodeA, nodeB, 0))

                                        return (0, G, edges_index_dict, nodes_route)

                                else:# Unavailable Node
                                    self.logger.warning('Unavailable Node at origin {} or destination {}'.format(nodeA,nodeB))
                                    #edges.iloc[edge_index, settings.INDEX_NP_EDGES_PESOL] = settings.MAX_PESOL# Update 'pesoL' field
                                    edges.loc[(nodeA, nodeB, 0), 'pesoL'] = settings.MAX_PESOL  # Update 'pesoL' field
                                    G = ox.graph_from_gdfs(nodes, edges)
                                    # Añado calle a lista de edges_pesoL
                                    self.edges_pesoL.append((nodeA, nodeB, 0))
                                    return (0, G, edges_index_dict, nodes_route)

                                nodeA = nodeB
                                timestamp_nodeA = timestamp_nodeB
                                index_aux += 1

                    else:
                        self.logger.warning('No Possible Paths')

                    for k, v in nodes_time.items():

                        ocupation_tuples = nodes.iloc[k, settings.INDEX_NP_NODES_OCUPATION]
                        if(ocupation_tuples == '[None]' or ocupation_tuples == ""):
                            nodes.iloc[k, settings.INDEX_NP_NODES_OCUPATION] = str([v])# Insert node ocupation field
                        else:
                            aux_list_nodes = ocupation_tuples
                            aux_list_nodes = list(eval(aux_list_nodes))
                            aux_list_nodes.append(v)
                            nodes.iloc[k, settings.INDEX_NP_NODES_OCUPATION] = str(aux_list_nodes)# Update node ocupation field

                    for k, v in edges_slotTime.items():

                        edge_index_aux = edges_index_dict[k]

                        ocupation_tuples = edges.iloc[edge_index_aux, settings.INDEX_NP_EDGES_OCUPATION]
                        if(ocupation_tuples == '[None]' or ocupation_tuples == ""):
                            edges.iloc[edge_index_aux, settings.INDEX_NP_EDGES_OCUPATION] = str([v])# Insert edge ocupation field
                        else:
                            aux_list_edges = ocupation_tuples
                            aux_list_edges = list(eval(aux_list_edges))
                            aux_list_edges.append(v)
                            edges.iloc[edge_index_aux, settings.INDEX_NP_EDGES_OCUPATION] = str(aux_list_edges)# Update edge ocupation field

                    G = ox.graph_from_gdfs(nodes, edges)

            else:
                self.logger.warning('shortest_path method in fp_evaluations() did not find a possible route. Return path (None,G)')
                return (None, G, edges_index_dict, nodes_route)

        return (nodes_route, G, edges_index_dict, nodes_route)

class ScenarioMaker():

    def __init__(self, logger):
        self.logger = logger
        self.header_added = False

    @logger.catch
    def Drone2Scn(self, drone_id, start_time, lats, lons, turnbool, alts, priority, sta, uav, int_angle_list, turn_indexs, turn_speeds):
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

        # Let's calculate its required heading.
        qdr = self.qdrdist(lats[0], lons[0], lats[2], lons[2], 'qdr')
        takeoff_altitude = alts[0]
        middle_alt_index = int(len(alts)/2)
        operational_altitude = alts[middle_alt_index]

        #cre_text = f'CRE {drone_id} {uav} {lats[0]} {lons[0]} {qdr} {takeoff_altitude} 0\n'

        # lines.append('\n'+start_time_txt + cre_text)
        # priority_text = f'SETPRIORITY {drone_id} {priority}\n'
        # lines.append(start_time_txt + priority_text)

        setturns_text = f'SETTURNS {drone_id} '
        for i in turn_indexs:
            setturns_text += str(i) + " "
        setturns_text += '\n'
        lines.append(start_time_txt + setturns_text)

        setturnspds_text = f'SETTURNSPDS {drone_id} '
        for i in turn_speeds:
            setturnspds_text += str(int(i)) + " "
        setturnspds_text += '\n'
        lines.append(start_time_txt + setturnspds_text)

        # alt_text = f'ALT {drone_id} {operational_altitude}\n'
        # lines.append(start_time_txt + alt_text)
        #
        # atalt1_text = f'{drone_id} ATALT {operational_altitude} SPD {drone_id} {cruise_speed}\n'
        # lines.append(start_time_txt + atalt1_text)
        # atalt2_text = f'{drone_id} ATALT {operational_altitude} LNAV {drone_id} ON\n'
        # lines.append(start_time_txt + atalt2_text)
        # atalt3_text = f'{drone_id} ATALT {operational_altitude} VNAV {drone_id} ON\n'
        # lines.append(start_time_txt + atalt3_text)


        wpt_txt = f'ADDWAYPOINTS {drone_id} '
        j=0

        for lat, lon, alt, turn, i in zip(lats, lons, alts, turnbool, range(0,len(lats))):

            if(i==0):
                continue

            elif(i<len(lats)-1):

                if turn == True: # turn angle
                    turn_speed = turn_speeds[j]
                    j+=1
                    wpt_txt += f'{lat} {lon} ,{alt},{cruise_speed}, TURNSPEED, {turn_speed},'
                else:
                    if(lat == lats[i-1] and lon == lons[i-1]): # taking off; I check with the previous point
                        wpt_txt += f'{lat} {lon} ,{alt},{0}, FLYBY, 0,'
                    elif(lat == lats[i+1] and lon == lons[i+1]):  # landing; I check with the following point
                        wpt_txt += f'{lat} {lon} ,{alt},{0}, FLYBY, 0,'
                    else:
                        wpt_txt += f'{lat} {lon} ,{alt},{cruise_speed}, FLYBY, 0,'

            elif (i == len(lats)-1): #last WAYPOINT
                    wpt_txt += f'{lat} {lon} ,{alt},{0}, FLYOVER, 0,'
            else:
                self.logger.error("ERROR ADDED WAYPOINT")


        lines.append(start_time_txt + wpt_txt)

        return lines

    @logger.catch
    def TimeToStr(self, time):
        time = round(time)
        m, s = divmod(time, 60)
        h, m = divmod(m, 60)
        return f'{h:02d}:{m:02d}:{s:02d}'

    @logger.catch
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

    @logger.catch
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

    @logger.catch
    def Dict2Scn(self, filepath, dictionary, priority, sta, uav, int_angle_list, turn_indexs, turn_speeds):


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
        turn_indexs
        turn_speeds
        """
        if filepath[-4:] != '.scn':
            filepath = filepath + '.scn'

        with open(filepath, 'a') as f:
            for drone_id in dictionary: #solo itera una vez
                try:
                    start_time = dictionary[drone_id]['start_time']
                    lats = dictionary[drone_id]['lats']
                    lons = dictionary[drone_id]['lons']
                    turnbool = dictionary[drone_id]['turnbool']
                    alts = dictionary[drone_id]['alts']
                except:
                    self.logger.error('Key error. Make sure the dictionary is formatted correctly.')
                    return

                lines = self.Drone2Scn(drone_id, start_time, lats, lons, turnbool, alts, priority, sta, uav, int_angle_list, turn_indexs, turn_speeds)
                # if(not self.header_added):
                #     header_text0 = '00:00:00>CASMACHTHR 0\n'
                #     lines.insert(0, header_text0)
                #     header_text1 = '00:00:00>PAN 48.223775 16.337976\n'
                #     lines.insert(1,header_text1)
                #     header_text2 = '00:00:00>ZOOM 60'
                #     lines.insert(2, header_text2)
                #
                #     self.header_added = True

                f.write(''.join(lines))

                return lines

class PathPlanner():
    ''' PathPlanner new entity object for BlueSky. '''


    @logger.catch
    def __init__(self, G, angle_cutoff=25):
        self.G = G
        # get edge geodataframe
        gdfs = ox.graph_to_gdfs(self.G)
        self.node_gdf = gdfs[0]
        self.edge_gdf = gdfs[1]

        # get edge indices
        self.edge_idx = list(self.edge_gdf.index.values)

        # get angle cutoff to label turns as turnbool
        self.angle_cutoff = angle_cutoff


        # get edge indices
        self.edge_idx = list(self.edge_gdf.index.values)

        # get angle cutoff to label turns as turnbool
        self.angle_cutoff = angle_cutoff

    @logger.catch
    def route(self, osmid_route):

        # get_correct_order of edges inside graph and reverese linestring geometry if necessary
        edge_geom_list = []
        node_geom_list = {}
        for idx in range(len(osmid_route) - 1):

            edge_to_find = (osmid_route[idx], osmid_route[idx + 1], 0)

            # See if edge is in graph otherwise reverese u,v
            if edge_to_find in self.edge_idx:
                edge = edge_to_find
            else:
                edge = (edge_to_find[1], edge_to_find[0], 0)
                logger.critical("Edge not found: {}".format(edge_to_find))

            # check if geometry is in correct direction. if not flip geometry
            # use node of route to check in which  if it lines up with edge linestring
            line_geom = list(self.edge_gdf.loc[edge, 'geometry'].coords)
            logger.debug("\nline_geom of edge {} is: {}".format(edge, line_geom))

            aux_geom = self.node_gdf.loc[osmid_route[idx], 'geometry']
            aux_lat = aux_geom.y
            #aux_lat = self.node_gdf.apply(lambda gdf: gdf['geometry'].y, axis=1)
            lat_node = normal_round(aux_lat,6)
            aux_lon = aux_geom.x
            #aux_lon = self.node_gdf.apply(lambda gdf: gdf['geometry'].x, axis=1)
            lon_node = normal_round(aux_lon,6)
            logger.debug("\nlon_node {} and lat_node {}".format(lon_node, lat_node))

            #Round to 6decimals
            new_line_geom = []
            for geo in line_geom:
                new_lon = normal_round(geo[0],6)
                new_lat = normal_round(geo[1],6)
                new_tuple = (new_lon,new_lat)
                new_line_geom.append(new_tuple)
            line_geom = new_line_geom

            nodeA_edge = osmid_route[idx]
            nodeB_edge = osmid_route[idx + 1]
            node_geom_list[nodeA_edge] = line_geom[0] #added nodeA with position (latA, lonA) extracted of the edge (nodeA, nodeB, 0)
            node_geom_list[nodeB_edge] = line_geom[-1] #added nodeB with position (latB, lonB) extracted of the edge (nodeA, nodeB, 0)
            logger.debug("\nnodeA_edge {} with {} and nodeB_edge {} with {}".format(nodeA_edge,node_geom_list[nodeA_edge], nodeB_edge, node_geom_list[nodeB_edge]))


            logger.debug("CHECKING if {} == {} and {} == {}".format(lon_node, node_geom_list[nodeA_edge][0], lat_node, node_geom_list[nodeA_edge][1]))
            if not (lon_node == node_geom_list[nodeA_edge][0] and lat_node == node_geom_list[nodeA_edge][1]):
                logger.warning("REVERSE becouse line_geom of edge {} was: {}".format(edge, line_geom))
                wrong_geom = line_geom
                wrong_geom.reverse()
                line_geom = list(LineString(wrong_geom).coords)

                # exchange of geom edge positions in nodes
                node_geom_list[nodeA_edge] = line_geom[-1]
                node_geom_list[nodeB_edge] = line_geom[0]

            # append edge and geometry for later use
            edge_geom_list.append((edge, line_geom))

        # # calculate succesive interior angles and see which nodes are turn nodes
        # int_angle_list = []
        # turn_node_list = []
        # for idx in range(len(edge_geom_list) - 1):
        #     current_edge = edge_geom_list[idx][0]
        #     next_edge = edge_geom_list[idx + 1][0]
        #
        #     int_angle_dict = eval(self.edge_gdf.loc[current_edge, 'edge_interior_angle'])
        #     # get interior angle. search in current_edge
        #     try:
        #         interior_angle = int_angle_dict[next_edge]
        #     except KeyError:
        #         next_edge = (next_edge[1], next_edge[0], 0)
        #         interior_angle = int_angle_dict[next_edge]
        #
        #     # get osmids of turn nodes
        #     if interior_angle < 180 - self.angle_cutoff:
        #         node_1 = current_edge[0]
        #         node_2 = current_edge[1]
        #
        #         node_3 = next_edge[0]
        #         node_4 = next_edge[1]
        #
        #         node_to_append = node_2
        #
        #         turn_node_list.append(node_to_append)
        #
        #     int_angle_list.append(interior_angle)

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


        logger.debug("lon_lat_list: {}".format(lon_lat_list))
        logger.debug("len(lon_lat_list): {}".format(len(lon_lat_list)))
        logger.debug("lat_list: {}".format(lat_list))
        logger.debug("len(lat_list): {}".format(len(lat_list)))
        logger.debug("lon_list: {}".format(lon_list))
        logger.debug("len(lon_list): {}".format(len(lon_list)))

        turn_bool, turn_speeds, turn_coords, int_angle_list = self.get_turn_arrays(lat_list, lon_list)

        turn_speeds = turn_speeds.tolist()
        turn_speeds = list(filter(lambda num: num != 0, turn_speeds))

        logger.info("turn_bool: {} and len {}".format(turn_bool, len(turn_bool)))
        logger.info("turn_speeds: {} and len {}".format(turn_speeds, len(turn_speeds)))
        logger.info("turn_coords: {} and len {}".format(turn_coords, len(turn_coords)))
        logger.info("int_angle_list: {} and len {}".format(int_angle_list, len(int_angle_list)))
        logger.info("self.angle_cutoff: {}".format(self.angle_cutoff))

        # find indices of turn_nodes
        turn_indices = []
        index_turn=0
        for tbool in turn_bool:
            if(tbool):
                turn_indices.append(index_turn)
            index_turn+=1

        logger.info("turn_indices: {} and len {}".format(turn_indices, len(turn_indices)))


        # for turn_node in turn_node_list:
        #     # Find lat lon of current turn node
        #     lat_node = node_geom_list[turn_node][1]
        #     lon_node = node_geom_list[turn_node][0]
        #     logger.debug("\nlon_node {} and lat_node {}".format(lon_node, lat_node))
        #
        #     try:
        #         index_turn = lon_lat_list.index(f'{lon_node}-{lat_node}')
        #     except ValueError:
        #         logger.critical("index_turn not found of turn_node {}. lon_node {}, lat_node {}, lon_lat_list, lon_lat_list{}".format(turn_node,lon_node,lat_node,lon_lat_list))
        #         index_turn = 9999
        #
        #     turn_indices.append(index_turn)
        #
        # # create turnbool. true if waypoint is a turn waypoint, else false
        # turnbool = []
        # for idx in range(len(lat_list)):
        #     if idx in turn_indices:
        #         turn_flag = True
        #     else:
        #         turn_flag = False
        #
        #     turnbool.append(turn_flag)
        return lat_list, lon_list, turn_bool.tolist(), turn_indices, turn_speeds, int_angle_list, self.angle_cutoff

    def get_turn_arrays(self,lats, lons, cutoff_angle=25):
        """
        Get turn arrays from latitude and longitude arrays.
        The function returns three arrays with the turn boolean, turn speed and turn coordinates.
        Turn speed depends on the turn angle.
            - Speed set to 0 for no turn.
            - Speed to 10 knots for angles smaller than 45 degrees.
            - Speed to 5 knots for turning angles between 45 and 90 degrees.
            - Speed to 2 knots for turning angles larger tha 90 degrees.
        Parameters
        ----------
        lat : numpy.ndarray
            Array with latitudes of route
        lon : numpy.ndarray
            Array with longitudes of route
        cutoff_angle : int
            Cutoff angle for turning. Default is 25.
        Returns
        -------
        turn_bool : numpy.ndarray
            Array with boolean values for turns.

        turn_speed : numpy.ndarray
            Array with turn speed. If no turn, speed is 0.

        turn_coords : numpy.ndarray
            Array with turn coordinates. If no turn then it has (-9999.9, -9999.9)
        """

        # Define empty arrays that are same size as lat and lon
        turn_speed = np.zeros(len(lats))
        turn_bool = np.array([False] * len(lats), dtype=np.bool8)
        turn_coords = np.array([(-9999.9, -9999.9)] * len(lats), dtype='f,f')
        int_angle_list = []

        # Initialize variables for the loop
        lat_prev = lats[0]
        lon_prev = lons[0]

        # loop thru the points to calculate turn angles
        for i in range(1, len(lats) - 1):
            # reset some values for the loop
            lat_cur = lats[i]
            lon_cur = lons[i]
            lat_next = lats[i + 1]
            lon_next = lons[i + 1]

            # calculate angle between points
            d1 = self.qdrdist(lat_prev, lon_prev, lat_cur, lon_cur)
            d2 = self.qdrdist(lat_cur, lon_cur, lat_next, lon_next)

            # fix angles that are larger than 180 degrees
            angle = abs(d2 - d1)
            angle = 360 - angle if angle > 180 else angle

            int_angle_list.append(angle)

            # give the turn speeds based on the angle
            if angle > cutoff_angle and i != 0:

                # set turn bool to true and get the turn coordinates
                turn_bool[i] = True
                turn_coords[i] = (lat_cur, lon_cur)

                # calculate the turn speed based on the angle.
                if angle < 100:
                    turn_speed[i] = 10
                elif angle < 150:
                    turn_speed[i] = 5
                else:
                    turn_speed[i] = 2
            else:
                turn_coords[i] = (-9999.9, -9999.9)

            # update the previous values at the end of the loop
            lat_prev = lat_cur
            lon_prev = lon_cur

        # make first entry to turn bool true (entering constrained airspace)
        # turn_bool[0] = True

        return turn_bool, turn_speed, turn_coords, int_angle_list


    def qdrdist(self,latd1, lond1, latd2, lond2):
        """ Calculate bearing, using WGS'84
            In:
                latd1,lond1 en latd2, lond2 [deg] :positions 1 & 2
            Out:
                qdr [deg] = heading from 1 to 2

            Function is from bluesky (geo.py)
        """

        # Convert to radians
        lat1 = np.radians(latd1)
        lon1 = np.radians(lond1)
        lat2 = np.radians(latd2)
        lon2 = np.radians(lond2)

        # Bearing from Ref. http://www.movable-type.co.uk/scripts/latlong.html
        coslat1 = np.cos(lat1)
        coslat2 = np.cos(lat2)

        qdr = np.degrees(np.arctan2(np.sin(lon2 - lon1) * coslat2,
                                    coslat1 * np.sin(lat2) -
                                    np.sin(lat1) * coslat2 * np.cos(lon2 - lon1)))

        return qdr

class Settings():
    def __init__(self, *args, **kwargs):
        self.ROOT_FOLDER = './data'
        self.GPKG_FOLDER = "./data/input/GPKGs_finales/airspace-main-v8/"
        self.GPKG_LIST = "./data/input/layernames_routing.txt"
        # self.FP_PATH = "./data/input/Example_flight_intention_low_1fplans.txt"
        self.ROOT_FP_PATHS = "./data/input/Flight_intentions_finales/Flight_intention_100fplans/"
        self.AIRCRAFT_PATH = "./data/input/aircraft.json"
        self.ROOT_OUTPUT_SCN ="scenario/"
        self.OUTPUT_SCN = "_result_01-02-22_H13-05_laptopJPG.scn"
        self.LOGS_FOLDER = "./data/output/logs"
        self.LOG_LEVEL = "SUCCESS"
        self.RECEPTION_TIME_FP_INDEX = 0
        self.FPLAN_ID_INDEX = 1
        self.VEHICLE_INDEX = 2
        self.DEPARTURE_INDEX = 3
        self.INITIAL_LOCATION_INDEX = 4
        self.FINAL_LOCATION_INDEX = 5
        self.PRIORITY_INDEX = 6
        self.STATUS_INDEX = 7
        self.GEOFENCE_DURATION = 8
        self.GEOFENCE_BBOX_POINT1 = 9
        self.GEOFENCE_BBOX_POINT2 = 10
        self.PENDING_STATUS = 'PENDING'
        self.APPROVED_STATUS = 'APPROVED'
        self.MAX_PESOL = 99999.9
        self.EARLY_STOP_NUMBER = 5 # before was 2, and then 4
        self.MARGIN_OPT_DIST = 1.2
        self.NODE_OCCUPATION_TIME_PASS = 0
        self.DEFAULT_TURNNODE_OCCUPATION_TIME_PASS = 3
        self.S10_TURNNODE_OCCUPATION_TIME_PASS = 3
        self.S5_TURNNODE_OCCUPATION_TIME_PASS = 5
        self.S2_TURNNODE_OCCUPATION_TIME_PASS = 8
        self.NODE_OCCUPATION_TIME_VERT = 4
        self.ASCENSDING_TAKEOFF = 5
        self.DEPARTURE_DELAY = 30
        self.MAX_DELAYED_TIME = 300
        self.SEPARATION_CRUISING_LAYERS = 60
        self.LOW_LEVEL_LAYER = 60
        self.TAKEOFF_ALT = 1
        self.LANDING_ALT = 0
        self.MINUTS_CONVERSION = 3600
        self.SECONDS_CONVERSION = 60
        self.TIPO1 = 'MP30'
        self.TIPO2 = 'MP20'
        self.NM = 1852

        # Manage iloc() index GeoDataframe of Nodes and Edges
        self.INDEX_NP_NODES_LAT = 0
        self.INDEX_NP_NODES_LON = 1
        self.INDEX_NP_NODES_OCUPATION = 2
        self.INDEX_NP_NODES_HEIGHT = 3
        self.INDEX_NP_NODES_GEOMETRY = 4

        self.INDEX_NP_EDGES_OCUPATION = 0
        self.INDEX_NP_EDGES_LENGTH = 1
        self.INDEX_NP_EDGES_PESOL = 2
        self.INDEX_NP_EDGES_INTANGLE = 3
        self.INDEX_NP_EDGES_HEIGHT = 4
        self.INDEX_NP_EDGES_GEOMETRY = 5

settings = Settings()
if __name__ == '__main__':
    fp_files = os.listdir(settings.ROOT_FP_PATHS)
    print(fp_files)

    # pool = ThreadPool()
    # results = pool.map(MainApp().startRoutingPlan, fp_files)
    # pool.close()

    MainApp().startRoutingPlan(fp_files[0])