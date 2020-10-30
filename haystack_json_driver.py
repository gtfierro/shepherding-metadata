import driver
from datetime import datetime
import time
import threading
from rdflib import RDFS, Literal
from brickschema.inference import HaystackInferenceSession
import json

class HaystackJSONDriver(driver.Driver):
    def __init__(self, port, servers, bldg_ns, opts):
        self._haystack_file = opts['file']
        super().__init__(port, servers, bldg_ns)

        t = threading.Thread(target=self._check_source, daemon=True)
        t.start()


    def _check_source(self):
        while True:
            self.load_file(self._haystack_file)
            time.sleep(600)

    def load_file(self, haystack_file):

        def do_load_file():
            self.app.logger.info(f"Loading Haystack JSON dump {haystack_file}")
            self.haystack_model = json.load(open(haystack_file))
            timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S%Z')

            sess = HaystackInferenceSession(self._ns)
            model = sess.infer_model(self.haystack_model)
            # already has labels attached
            triples = list(sess._generated_triples)
            rec = {
                'id': 'all',
                'source': type(self).__name__,
                'record': {
                    'encoding': 'JSON',
                    'content': '',
                },
                'triples': triples,
                'timestamp': timestamp
            }
            self.add_record(rec['id'], rec)

            # for row in self.haystack_model['rows']:
            #     sess = HaystackInferenceSession(self._ns)
            #     model = {'rows': [row]}
            #     model = sess.infer_model(model)

            #     # already has labels attached
            #     triples = list(sess._generated_triples)
            #     rec = {
            #         'id': row['id'],
            #         'source': type(self).__name__,
            #         'record': {
            #             'encoding': 'JSON',
            #             'content': row,
            #         },
            #         'triples': triples,
            #         'timestamp': timestamp
            #     }
            #     self.add_record(rec['id'], rec)
            self.app.logger.info(f"Loaded {len(self._records)} records")
            self._compute_changed()
        do_load_file()
        # # start thread
        # t = threading.Thread(target=do_load_file, daemon=True)
        # t.start()

if __name__ == '__main__':
    import sys
    HaystackJSONDriver.start_from_configfile(sys.argv[1])
