from collections import defaultdict
import time
import driver
from datetime import datetime
import threading
import rdflib
from brickschema.namespaces import RDF, OWL, RDFS, BRICK, A
import lxml.etree
from sys import stdout
import csv
import sys

classes = [
    {'xpath': '//gb:AirLoopEquipment', 'brick': BRICK.HVAC_Equipment},
    {'xpath': '//gb:Zone', 'brick': BRICK.HVAC_Zone},
    {'xpath': '//gb:Space', 'brick': BRICK.Space},
]

# relationships = [
#     {'parent_xpath': '//
# ]

equip_types = {
    "Fan": BRICK.Fan,
    "HeatExchanger": BRICK.Heat_Exchanger,
    "Coil": BRICK.Coil,
    # "Furnace": BRICK.Fan,
    "Evaporative": BRICK.Chiller,
    # "Radiant": BRICK.Fan,
    # "Economizer": BRICK.Fan,
    # "Duct": BRICK.Fan,
    "Humidifier": BRICK.Humidifier,
    "Dehumidifier": BRICK.Dehumidifier,
    # "UnitaryAC": BRICK.Fan,
    # "UnitaryHP": BRICK.Fan,
    # "SplitAC": BRICK.Fan,
    # "SplitHP": BRICK.Fan,
    "TerminalUnit": BRICK.Terminal_Unit,
    # "Register": BRICK.Fan,
    "VAVBox": BRICK.VAV,
    # "EvaporativePreCooler": BRICK.Fan,
    "PreheatCoil": BRICK.Heating_Coil,
}

xmlns = {
    "xs": "http://www.w3.org/2001/XMLSchema",
    "gb": "http://www.gbxml.org/schema"
    }

# filename = 'data/gbxml/examples/gbXMLStandard Test Model 2016.xml'
# root = lxml.etree.parse(filename)

# records = defaultdict(list)
# BLDG = rdflib.Namespace("building#")
#
# for defn in classes:
#     xpath = defn['xpath']
#     bc = defn['brick']
#     res = root.xpath(xpath, namespaces=xmlns)
#     for item in res:
#         ident = item.attrib.get('id')
#
#         records[ident].append((BLDG[ident], A, bc))
#
#         # if equipment, get the type
#         equip_type = item.attrib.get('equipmentType')
#         if equip_type in equip_types:
#             brick_class = equip_types[equip_type]
#             records[ident].append((BLDG[ident], A, brick_class))
#
#         # if a zone, get the airloop identifier
#         airloops = item.xpath("gb:AirLoopId", namespaces=xmlns)
#         for airloop in airloops:
#             airloopid = airloop.attrib.get('airLoopIdRef')
#             vavs = root.xpath(f"//gb:AirLoop[@id=\"{airloopid}\"]//gb:AirLoopEquipment[@equipmentType=\"VAVBox\"]", namespaces=xmlns)
#             print(ident, airloopid)
#             for vav in vavs:
#                 vav_id = vav.attrib.get('id')
#                 records[ident].append((BLDG[ident], BRICK.isFedBy, BLDG[vav_id]))
#
#         # if a space, get the zone identifier
#         zone_id = item.attrib.get('zoneIdRef')
#         if zone_id is not None:
#             zones = root.xpath(f"//gb:Zone[@id=\"{zone_id}\"]", namespaces=xmlns)
#             for zone in zones:
#                 records[ident].append((BLDG[ident], BRICK.isPartOf, BLDG[zone_id]))
#
# for _, triples in records.items():
#     for triple in triples:
#         print(triple)


class GBXMLDriver(driver.Driver):
    def __init__(self, port, servers, bldg_ns, opts):
        self._filename = opts.get('gbxml_file')
        super().__init__(port, servers, bldg_ns)

        t = threading.Thread(target=self._check_source, daemon=True)
        t.start()

    def _check_source(self):
        while True:
            self.load_file(self._filename)
            time.sleep(60)

    def load_file(self, gbxml_file):
        BLDG = rdflib.Namespace(self._ns)
        root = lxml.etree.parse(gbxml_file)
        self.app.logger.info(f"Loading GBXML file {gbxml_file}")
        timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S%Z')
        records = defaultdict(list)
        subtrees = defaultdict(list)
        for defn in classes:
            xpath = defn['xpath']
            bc = defn['brick']
            res = root.xpath(xpath, namespaces=xmlns)
            for item in res:
                ident = item.attrib.get('id')
                subtrees[ident].append(str(lxml.etree.tostring(item)))

                records[ident].append((BLDG[ident], A, bc))
                records[ident].append((BLDG[ident], RDFS.label, rdflib.Literal(ident)))

                # if equipment, get the type
                equip_type = item.attrib.get('equipmentType')
                if equip_type in equip_types:
                    brick_class = equip_types[equip_type]
                    records[ident].append((BLDG[ident], A, brick_class))

                # if a zone, get the airloop identifier
                airloops = item.xpath("gb:AirLoopId", namespaces=xmlns)
                for airloop in airloops:
                    airloopid = airloop.attrib.get('airLoopIdRef')
                    vavs = root.xpath(f"//gb:AirLoop[@id=\"{airloopid}\"]//gb:AirLoopEquipment[@equipmentType=\"VAVBox\"]", namespaces=xmlns)
                    for vav in vavs:
                        vav_id = vav.attrib.get('id')
                        records[ident].append((BLDG[ident], BRICK.isFedBy, BLDG[vav_id]))

                # if a space, get the zone identifier
                zone_id = item.attrib.get('zoneIdRef')
                if zone_id is not None:
                    zones = root.xpath(f"//gb:Zone[@id=\"{zone_id}\"]", namespaces=xmlns)
                    for zone in zones:
                        records[ident].append((BLDG[ident], BRICK.isPartOf, BLDG[zone_id]))

        for ident, triples in records.items():
            rec = {
                'id': ident,
                'source': type(self).__name__,
                'record': {
                    'encoding': 'XML',
                    'content': subtrees.get(ident, []),
                },
                'triples': triples,
                'timestamp': timestamp
            }
            self.add_record(ident, rec)

if __name__ == '__main__':
    import sys
    GBXMLDriver.start_from_configfile(sys.argv[1])
