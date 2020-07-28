import secrets
import json
import time
import hashlib
from datetime import datetime
import driver
import threading
import rdflib
from brickschema.namespaces import RDF, OWL, RDFS, BRICK
import lxml.etree
from sys import stdout
import csv

# TODO: pump systems
relationships = [
    {'parent_xpath': '//auc:Buildings/auc:Building', 'child_xpath': 'auc:Sections/auc:Section/auc:ThermalZones/auc:ThermalZone', 'relship': BRICK.hasPart},
    {'parent_xpath': '//auc:Buildings/auc:Building', 'child_xpath': 'auc:Sections/auc:Section/auc:ThermalZones/auc:ThermalZone', 'relship': BRICK.isLocationOf},
    {'parent_xpath': '//auc:Sites/auc:Site', 'child_xpath': 'auc:Buildings/auc:Building', 'relship': BRICK.hasPart},
    {'parent_xpath': '//auc:Sites/auc:Site', 'child_xpath': 'auc:Buildings/auc:Building', 'relship': BRICK.isLocationOf},
    {'parent_xpath': '//auc:FanSystem[auc:LinkedSystemIDs/auc:LinkedSystemID]', 'child_xpath': 'auc:LinkedSystemIDs/auc:LinkedSystemID', 'relship': BRICK.isPartOf},
]

class BuildingSyncDriver(driver.Driver):
    def __init__(self, port, servers, bldg_ns, opts):
        self._filename = opts.get('bsync_file')
        super().__init__(port, servers, bldg_ns)

        self.mappings = {}
        with open(opts.get('mapping_file')) as f:
            lines = csv.reader(f)
            next(lines)
            for line in lines:
                parent_class, xpath, brick_class, _ = line
                self.mappings[xpath] = brick_class

        self.xmlns = {
            "xs": "http://www.w3.org/2001/XMLSchema",
            "auc": "http://buildingsync.net/schemas/bedes-auc/2019"
        }

        t = threading.Thread(target=self._check_source, daemon=True)
        t.start()

    def _check_source(self):
        while True:
            self.load_file(self._filename)
            time.sleep(60)

    def extract_id(self, item):
        ident = item.attrib.get('ID')
        if ident is not None:
            return ident
        ident = item.attrib.get('IDref')
        if ident is not None:
            return ident
        ident = item.getparent().attrib.get('ID')
        if ident is not None:
            return ident
        tagname = item.tag
        tagname = tagname[tagname.find('}')+1:]
        return f"{tagname}-{secrets.token_hex(8)}"

    def load_file(self, bsync_file):
        NS = rdflib.Namespace(self._ns)
        def do_load_file():
            self.app.logger.info(f"Loading BuildingSync file {bsync_file}")
            root = lxml.etree.parse(self._filename)
            # self.haystack_model = json.load(open(haystack_file))
            timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S%Z')
            records = {}

            for xpath, brick_class in self.mappings.items():
                if brick_class == 'NA':
                    continue
                res = root.xpath(xpath, namespaces=self.xmlns)
                if len(res) == 0:
                    continue
                print(f"Found {len(res)} instances of {brick_class}")

                for item in res:
                    ident = self.extract_id(item)
                    subtree = str(lxml.etree.tostring(item))
                    # graph.add((NS[ident], RDF.type, rdflib.URIRef(brick_class)))
                    records[ident] = {
                        'id': ident,
                        'source': type(self).__name__,
                        'record': {
                            'encoding': 'XML',
                            'content': subtree,
                        },
                        'triples': [(NS[ident], RDF.type, rdflib.URIRef(brick_class)),
                                    (NS[ident], RDFS.label, rdflib.Literal(ident))],
                        'timestamp': timestamp
                    }


            for d in relationships:
                srcpath = d['parent_xpath']
                dstpath = d['child_xpath']
                for src_elem in root.xpath(srcpath, namespaces=self.xmlns):
                    for dst_elem in src_elem.xpath(dstpath, namespaces=self.xmlns):
                        src = self.extract_id(src_elem)
                        dst = self.extract_id(dst_elem)
                        print(src, dst, d['relship'])
                        if src not in records:
                            continue
                        records[src]["triples"].append((NS[src], d['relship'], NS[dst]))

            for ident, rec in records.items():
                self.add_record(ident, rec)
            # # TODO: add more relationships
            # for thing in things[:-1]:
            #     for thing2 in things[1:]:
            #         if thing2 in thing.getchildren():
            #             print(thing2, "in", thing)
            #         if thing in thing2.getchildren():
            #             print(thing, "in", thing2)


            #     rec = {
            #         'id': row['id'],
            #         'record': {
            #             'encoding': 'JSON',
            #             'content': row,
            #         },
            #         'triples': list(sess._generated_triples),
            #         'timestamp': timestamp
            #     }
            #     self._records[rec['id']] = rec
            self.app.logger.info(f"Loaded {len(self._records)} records")
            self._compute_changed()
        # start thread
        t = threading.Thread(target=do_load_file)
        t.start()


if __name__ == '__main__':
    import sys
    BuildingSyncDriver.start_from_configfile(sys.argv[1])
