import json
import time
import hashlib
from datetime import datetime
import driver
import threading
import rdflib
from brickschema.namespaces import RDF
import lxml.etree
from sys import stdout
import csv

class BuildingSyncDriver(driver.Driver):
    def __init__(self, port, servers, bldg_ns, buildingsync_file):
        self._filename = buildingsync_file
        super().__init__(port, servers, bldg_ns)

        self.mappings = {}
        with open('data/buildingsync/BSync-to-Brick.csv') as f:
            lines = csv.reader(f)
            next(lines)
            for line in lines:
                parent_class, xpath, brick_class, _ = line
                self.mappings[xpath] = brick_class

        self.xmlns = {
            "xs": "http://www.w3.org/2001/XMLSchema",
            "auc": "http://buildingsync.net/schemas/bedes-auc/2019"
        }

        t = threading.Thread(target=self._check_source)
        t.start()

    def _check_source(self):
        while True:
            self.load_file(self._filename)
            time.sleep(60)

    def extract_id(self, item):
        ident = item.attrib.get('ID')
        if ident == None:
            ident = item.getparent().attrib.get('ID')
            if ident == None:
                ident = 'unknown'
        return ident

    def load_file(self, bsync_file):
        NS = rdflib.Namespace(self._ns)
        def do_load_file():
            self.app.logger.info(f"Loading BuildingSync file {bsync_file}")
            root = lxml.etree.parse(self._filename)
            # self.haystack_model = json.load(open(haystack_file))
            timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S%Z')
            things = []

            for xpath, brick_class in self.mappings.items():
                if brick_class == 'NA':
                    continue
                res = root.xpath(xpath, namespaces=self.xmlns)
                things.extend(res)
                print(f"Found {len(res)} instances of {brick_class}")

                for item in res:
                    ident = self.extract_id(item)
                    subtree = str(lxml.etree.tostring(item))
                    # graph.add((NS[ident], RDF.type, rdflib.URIRef(brick_class)))

                    rec = {
                        'id': NS[ident],
                        'record': {
                            'encoding': 'XML',
                            'content': subtree,
                        },
                        'triples': [(NS[ident], RDF.type, rdflib.URIRef(brick_class))],
                        'timestamp': timestamp
                    }
                    self._records[NS[ident]] = rec

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
    # srv = BuildingSyncDriver(8081, ["http://localhost:6483"], "http://example.com/haystack#", "data/buildingsync/examples/AT_example_SF_audit_report.xml")
    srv = BuildingSyncDriver(8081, ["http://localhost:6483"], "http://example.com/building#", "data/buildingsync/examples/bsync-carytown.xml")
    srv.serve()
