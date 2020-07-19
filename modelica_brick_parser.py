from brickschema.namespaces import BRICK, RDF
import pandas as pd
import numpy as np
import json

class Modelica_Brick_Parser:
    def __init__(self, modelica_buildings_library_path, modelica_json_filename, json_folder):
        self.json_folder = json_folder
        self.modelica_buildings_library_path = modelica_buildings_library_path.replace('/', '.')
        self.main_folder = modelica_buildings_library_path.replace('/', '.')
        self.filename = self.main_folder+'.'+modelica_json_filename.split('.')[0]
        self.model_elements = {}
        self.model_equations = {}
        self.brick_relationships = []

        self.init_mapping()
        self.get_model_elements_equations()
        self.get_model_elements_df()

    def init_mapping(self):
        self.modelica_brick_sensor_type_map = {
            'TemperatureTwoPort': BRICK['Temperature_Sensor'],
            'Temperature': BRICK['Temperature_Sensor'],
            'RelativeTemperature': BRICK['Temperature_Sensor'],
            'TemperatureWetBulbTwoPort': BRICK['Temperature_Sensor'],
            'VolumeFlowRate': BRICK['Flow_Sensor'],
            'RelativeHumidity': BRICK['Humditiy_Sensor'],
            'RelativeHumidityTwoPort': BRICK['Humditiy_Sensor'],
            'Pressure': BRICK['Pressure_Sensor'],
            'RelativePressure': BRICK['Pressure_Sensor']
        }

        self.modelica_brick_heat_exchanger_type_map = {
            'DryCoilCounterFlow': BRICK['Heating_Coil'],
            'DryCoilDiscretized': BRICK['Heating_Coil'],
            'DryCoilEffectivenessNTU': BRICK['Heating_Coil'],
            'WetCoilCounterFlow': BRICK['Cooling_Coil'],
            'WetCoilDiscretized': BRICK['Cooling_Coil'],
            'EvaporatorCondenser': BRICK['Heat_Exchanger'],
            'Heater_T': BRICK['Space_Heater'],
        }

        self.modelica_brick_actuator_type_map = {
            'Dampers.Exponential': BRICK['Damper'],
            'Dampers.MixingBox': BRICK['Damper'],
            'Dampers.MixingBoxMinimumFlow': BRICK['Damper'],
            'Dampers.PressureIndependent': BRICK['Damper'],
            'Valves.ThreeWayEqualPercentageLinear': BRICK['Valve'],
            'Valves.ThreeWayLinear': BRICK['Valve'],
            'Valves.ThreeWayTable': BRICK['Valve'],
            'Valves.TwoWayEqualPercentageLinear': BRICK['Valve'],
            'Valves.TwoWayLinear': BRICK['Valve'],
            'Valves.TwoWayPolynomial': BRICK['Valve'],
            'Valves.TwoWayPressureIndependent': BRICK['Valve'],
            'Valves.TwoWayQuickOpening': BRICK['Valve'],
            'Valves.TwoWayTable': BRICK['Valve']
        }

        self.modelica_brick_mover_type_map = {
            'FlowControlled_dp': BRICK['Pump'],
            'FlowControlled_m_flow': BRICK['Pump'],
            'SpeedCotnrolled_Nrpm': BRICK['Fan'],
            'SpeedControlled_y': BRICK['Fan']
        }

        self.modelica_brick_thermal_zone_type_map = {
            'Detailed.MixedAir': BRICK['HVAC_Zone'],
            'ReducedOrder.EquivalentAirTemperature': BRICK['HVAC_Zone'],
            'ReducedOrder.RC': BRICK['HVAC_Zone'],
            'ReducedOrer.SolarGain': BRICK['HVAC_Zone']
        }

        self.modelica_brick_medium_type_map = {
            'Media.Air': BRICK['Air'],
            'Media.Water': BRICK['Water']
        }

    def __get_model_elements(self, json_op, filename, main_folder, model_elements={}, model_equations={}, extends_files=[]):
        for op in json_op:
            class_definition_list = op.get('class_definition')
            if not class_definition_list is None:
                for class_definition_obj in class_definition_list:
                    class_specifier_obj = class_definition_obj.get('class_specifier')
                    if not class_specifier_obj is None:
                        long_class_specifier_obj = class_specifier_obj.get('long_class_specifier')
                        if not long_class_specifier_obj is None:
                            composition_obj = long_class_specifier_obj.get('composition')
                            if not composition_obj is None:
                                element_list_obj = composition_obj.get('element_list')
                                equation_section_obj_list = composition_obj.get('equation_section')
                                prefixed_element_obj_list = composition_obj.get('prefixed_element')

                                if not element_list_obj is None:
                                    element_obj_list = element_list_obj.get('element')
                                    for element_obj in element_obj_list:
                                        if 'extends_clause' in element_obj:
                                            extends_file_name = element_obj.get('extends_clause', {}).get('name')
                                            if not extends_file_name in extends_files:
                                                extends_files.append(extends_file_name)

                                        if 'component_clause' in element_obj:
                                            component_clause_obj = element_obj.get('component_clause')
                                            if not component_clause_obj is None:
                                                type_specifier_obj = component_clause_obj.get('type_specifier')

                                                if not type_specifier_obj is None:
                                                    name = component_clause_obj.get('component_list', {}).get('component_declaration', {})[0].get('declaration', {}).get('name')
                                                    model_elements[filename+'.'+name] = {'type':type_specifier_obj, 'obj': element_obj}

                                                    if type_specifier_obj.startswith(self.main_folder):
                                                        if not type_specifier_obj in extends_files:
                                                            extends_files.append(type_specifier_obj)

                                if not equation_section_obj_list is None:
                                    for equation_section_obj in equation_section_obj_list:
                                        equation_obj_list = equation_section_obj.get('equation')
                                        if not equation_obj_list is None:
                                            for equation_obj in equation_obj_list:
                                                connect_clause_obj = equation_obj.get('connect_clause')
                                                if not connect_clause_obj is None:
                                                    comp1 = connect_clause_obj.get('component1')
                                                    comp2 = connect_clause_obj.get('component2')
                                                    comp1_element = comp1[0]
                                                    comp2_element = comp2[0]
                                                    equation_dict1 = {'connected_to': comp2_element, 'connect_clause_obj': connect_clause_obj}
                                                    equation_dict2 = {'connected_to': comp1_element, 'connect_clause_obj': connect_clause_obj}

                                                    if len(comp1) == 2:
                                                        comp1_port = comp1[1]
                                                        equation_dict1.update({'comp1_interface': comp1_port})
                                                        equation_dict2.update({'comp2_interface': comp1_port})
                                                    if len(comp2) == 2:
                                                        comp2_port = comp2[1]
                                                        equation_dict1.update({'comp2_interface': comp2_port})
                                                        equation_dict2.update({'comp1_interface': comp2_port})

                                                    if not comp1_element in model_equations:
                                                        model_equations[comp1_element] = [equation_dict1]
                                                    else:
                                                        if not equation_dict1 in model_equations[comp1_element]:
                                                            model_equations[comp1_element].append(equation_dict1)

                                                    if not comp2_element in model_equations:
                                                        model_equations[comp2_element] = [equation_dict2]
                                                    else:
                                                        if not equation_dict2 in model_equations[comp2_element]:
                                                            model_equations[comp2_element].append(equation_dict2)

                                    if not prefixed_element_obj_list is None:
                                        for prefixed_element_obj in prefixed_element_obj_list:
                                            element_obj_list2 = prefixed_element_obj.get('element')
                                            for element_obj2 in element_obj_list2:
                                                class_definition_obj2 = element_obj2.get('class_definition')
                                                component_clause_obj4 = element_obj2.get('component_clause')

                                                if not class_definition_obj2 is None:
                                                    class_specifier_obj2 = class_definition_obj2.get('class_specifier')
                                                    if not class_specifier_obj2 is None:
                                                        long_class_specifier_obj2 = class_specifier_obj2.get('long_class_specifier')
                                                        composition_obj2 = long_class_specifier_obj2.get('composition')
                                                        if not composition_obj2 is None:
                                                            element_list_obj3 = composition_obj2.get('element_list')
                                                            if not element_list_obj3 is None:
                                                                element_obj_list3 = element_list_obj3.get('element')
                                                                for element_obj3 in element_obj_list3:
                                                                    component_clause_obj3 = element_obj3.get('component_clause')
                                                                    if not component_clause_obj3 is None:
                                                                        type_specifier_obj3 = component_clause_obj3.get('type_specifier')

                                                                        if not type_specifier_obj3 is None:
                                                                            name = component_clause_obj3.get('component_list', {}).get('component_declaration', {})[0].get('declaration', {}).get('name')
                                                                            model_elements[filename+'.'+name] = {'type':type_specifier_obj3, 'obj': element_obj3}

                                                if not component_clause_obj4 is None:
                                                    type_specifier_obj4 = component_clause_obj4.get('type_specifier')

                                                    if not type_specifier_obj4 is None:
                                                        name = component_clause_obj4.get('component_list', {}).get('component_declaration', {})[0].get('declaration', {}).get('name')
                                                        model_elements[filename+'.'+name] = {'type':type_specifier_obj4, 'obj': element_obj2}


        return model_elements, model_equations, extends_files

    def __parse_file(self):
        files_to_parse = [self.filename]
        done_files = []
        extends_files = []
        model_elements = {}
        model_equations = {}

        while len(files_to_parse) != 0:
            files_list = files_to_parse
            for filename in files_list:
                with open(self.json_folder+'/'+filename+'.json') as fp:
                    json_op = json.load(fp)
                model_elements, model_equations, extends_files = self.__get_model_elements(json_op, filename, self.main_folder, model_elements, model_equations, extends_files)
                files_to_parse.remove(filename)
                if filename in extends_files:
                    extends_files.remove(filename)
                done_files.append(filename)
                for file in extends_files:
                    if file not in done_files:
                        if file.startswith("Buildings") and not file in files_to_parse:
                            files_to_parse.append(file)

        return model_elements, model_equations

    def get_model_elements_equations(self):
        self.model_elements, self.model_equations = self.__parse_file()

    def __assign_brick_type(self, df, type_list, type_map, group_id):
        elements_df = df.copy(deep=True)
        for modelica_type in type_list:
            subset_df = elements_df.loc[(elements_df.type.str.startswith(modelica_type))]
            if not subset_df.empty:
                elements_df.loc[subset_df.index, 'brick_type'] = subset_df.type.str.split(modelica_type+'.', expand=True)[1].map(type_map)
                elements_df.loc[subset_df.index, 'group'] = group_id

        return elements_df

    def get_model_elements_df(self):
        self.elements_df = pd.DataFrame(self.model_elements).T
        self.elements_df['brick_type'] = np.NaN
        self.elements_df['group'] = -1
        self.elements_df['element_name'] = self.elements_df.index.to_series().str.rsplit('.', expand=True, n=1)[1]
        self.elements_df = self.__assign_brick_type(df=self.elements_df, type_list=['Buildings.Fluid.Sensors', 'Fluid.Sensors'], type_map=self.modelica_brick_sensor_type_map, group_id=0)
        self.elements_df = self.__assign_brick_type(df=self.elements_df, type_list=['Buildings.Fluid.HeatExchangers', 'Fluid.HeatExchangers'], type_map=self.modelica_brick_heat_exchanger_type_map, group_id=2)
        self.elements_df = self.__assign_brick_type(df=self.elements_df, type_list=['Buildings.Fluid.Actuators', 'Fluid.Actuators'], type_map=self.modelica_brick_actuator_type_map, group_id=2)
        self.elements_df = self.__assign_brick_type(df=self.elements_df, type_list=['Buildings.Fluid.Movers', 'Fluid.Movers'], type_map=self.modelica_brick_mover_type_map, group_id=2)
        self.elements_df = self.__assign_brick_type(df=self.elements_df, type_list=['Buildings.ThermalZones', 'ThermalZones'], type_map=self.modelica_brick_thermal_zone_type_map, group_id=3)

    def __get_has_part_type_relationships(self):
        df_list = []
        for element, row in self.elements_df.loc[self.elements_df.type.str.startswith(self.main_folder)].iterrows():
            element_type = row['type']
            element_class = element[:element.rindex('.')]
            element_name = row['element_name']
            for part_element, part_element_row in self.elements_df.loc[self.elements_df.index.str.startswith(element_type)].iterrows():
                new_element = element+'.'+part_element_row['element_name']
                new_element_obj = part_element_row['obj']
                new_element_type = part_element_row['type']
                new_element_brick_type = part_element_row['brick_type']
                new_element_name = new_element.split(element_class+'.')[1]
                new_elem_df = pd.DataFrame({new_element: {'obj': new_element_obj, 'type': new_element_type, 'brick_type': new_element_brick_type, 'group': part_element_row['group'], 'element_name': new_element_name}}).T
                df_list.append(new_elem_df)

                if not part_element_row.isna().any():
                    relationship = {'obj1': element_name, 'relationship': BRICK['hasPart'], 'obj2': element_name+part_element.split(element_type)[1]}
                    if not relationship in self.brick_relationships:
                        self.brick_relationships.append(relationship)
                        self.elements_df.loc[element, 'group'] = 5

        self.elements_df = pd.concat([self.elements_df] + df_list, axis=0, sort=False)
        new_elements_df = pd.concat(df_list)
        for element_idx, row in new_elements_df.iterrows():
            element_name = row['element_name']
            parent_element = element_name.split('.')[0]
            old_name = element_name.split('.')[1]
            equations = self.model_equations.get(old_name, [])
            for equation in equations:
                comp2_df = self.elements_df.loc[self.elements_df.element_name == parent_element+'.'+equation.get('connected_to').split('[')[0]]
                if comp2_df.empty:
                    comp2_df = self.elements_df.loc[self.elements_df.element_name == equation.get('connected_to').split('[')[0]]
                new_equation = {'connected_to': comp2_df.element_name.values[0], 'connect_clause_obj': {'component1': ['vav', 'port_b'], 'component2': ['senMasFlo', 'port_a']}, 'comp1_interface': 'port_b', 'comp2_interface': 'port_a'}

                if not element_name in self.model_equations:
                    self.model_equations[element_name] = [new_equation]
                else:
                    self.model_equations[element_name].append(new_equation)

        for relationship in self.elements_df.dropna().apply(lambda x: {'obj1': x.element_name, 'relationship': RDF['type'], 'obj2': x.brick_type}, axis=1).values:
            if not relationship in self.brick_relationships:
                self.brick_relationships.append(relationship)

    def __search_for_equipment(self, element, prev_elements):
        element = element.split('[')[0]

        if self.elements_df.loc[self.elements_df.element_name == element].empty:
            print("can't find element "+element)
        else:
            element_type = self.elements_df.loc[self.elements_df.element_name == element].type.values[0]

        #print("searching for equipment for "+element+ " type = "+element_type)
        #print("path traversed = ",prev_elements)

        if element not in self.model_equations:
            #print("element does not have any connections; returning None")
            return None

        if element in prev_elements:
            #print("element already traversed; returning None")
            return None

        if element_type.startswith('Buildings.Controls'):
            #print("not traversing a controller; returning None")
            return None

        if element_type.startswith("Buildings.Fluid.Sources"):
            #print("not handling sources right now, returning None")
            return None

        found = False
        equations = self.model_equations[element]

        connected_equipments = []
        for equation in equations:
            connected_to_element = equation['connected_to'].split('[')[0]
            comp1_port = equation.get('comp1_interface')

            connected_element_df = self.elements_df.loc[self.elements_df.element_name == connected_to_element]
            if connected_element_df.empty:
                print('cant find element '+connected_to_element)
            elif not comp1_port is None and (comp1_port.startswith("port_a") or comp1_port.startswith("port_1")):
                pass
            elif connected_to_element in prev_elements:
                pass
            elif connected_element_df.group.values[0] == 2 or connected_element_df.group.values[0] == 5:
                if connected_to_element not in connected_equipments:
                    connected_equipments = connected_equipments + [connected_to_element]
            else:
                if not element in prev_elements:
                    prev_list2 = prev_elements+[element]
                closest_equipment = self.__search_for_equipment(connected_to_element, prev_list2)
                if not closest_equipment is None:
                    connected_equipments = list(set(connected_equipments+ closest_equipment))
                prev_elements = prev_list2
            prev_elements.append(connected_to_element)
        return connected_equipments

    def __get_feeds_relationship(self):
        equipment_df = self.elements_df.loc[self.elements_df.group == 2]
        for element_idx, row in equipment_df.iterrows():
            element_name = row['element_name']
            next_equipment_list = self.__search_for_equipment(element_name, [])

            for next_equipment in next_equipment_list:
                next_equipment_group = self.elements_df.loc[self.elements_df.element_name == next_equipment].group.values[0]
                if next_equipment_group == 2:
                    relationship = {'obj1': element_name, 'relationship': BRICK['feeds'], 'obj2': next_equipment}
                    if not relationship in self.brick_relationships:
                        self.brick_relationships.append(relationship)

    def get_brick_relationships(self):
        self.__get_has_part_type_relationships()
        self.__get_feeds_relationship()
        return self.brick_relationships
