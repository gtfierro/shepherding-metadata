import driver
import threading
import time
from rdflib import URIRef, Namespace, Literal, RDFS
from collections import defaultdict
from datetime import datetime
from modelica_brick_parser import Modelica_Brick_Parser

class ModelicaJSONDriver(driver.Driver):
    def __init__(self, port, servers, bldg_ns, opts):
        self._lib_path = opts.get('lib_path')
        self._modelica_json_file = opts.get('modelica_json_file')
        self._path = opts.get('path')
        super().__init__(port, servers, bldg_ns)

        t = threading.Thread(target=self._check_source, daemon=True)
        t.start()

    def _check_source(self):
        while True:
            self.load_file()
            time.sleep(600)

    def load_file(self):
        BLDG = Namespace(self._ns)

        def do_load_file():
            self.app.logger.info(f"Loading modelica models from {self._path}")
            timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S%Z')
            parser = Modelica_Brick_Parser(modelica_buildings_library_path=self._lib_path,
                                           modelica_json_filename=self._modelica_json_file,
                                           json_folder=self._path)

            brick_relationships = parser.get_brick_relationships()

            records = defaultdict(list)
            sources = {}
            for rel in brick_relationships:

                triple = [
                   rel['obj1'] if isinstance(rel['obj1'], URIRef) else BLDG[rel['obj1']],
                   rel['relationship'] if isinstance(rel['relationship'], URIRef) else BLDG[rel['relationship']],
                   rel['obj2'] if isinstance(rel['obj2'], URIRef) else BLDG[rel['obj2']],
                ]
                triple = [str(t) for t in triple]

                records[rel['obj1']].append(triple)

                # add "label":
                label_triple = (
                    triple[0], RDFS.label, Literal(rel['obj1'])
                )
                records[rel['obj1']].append(label_triple)


            for ent, triples in records.items():
                rec = {
                    'id': ent,
                    'source': type(self).__name__,
                    'record': {
                        'encoding': 'JSON',
                        # TODO: get some JSON for the entity?
                        'content': '{"content": "N/A"}',
                    },
                    'triples': triples,
                    'timestamp': timestamp
                }
                self.add_record(ent, rec)
            self.app.logger.info(f"Loaded {len(self._records)} records")
        # start thread
        t = threading.Thread(target=do_load_file, daemon=True)
        t.start()

if __name__ == '__main__':
    import sys
    ModelicaJSONDriver.start_from_configfile(sys.argv[1])
