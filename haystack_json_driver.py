import driver
from datetime import datetime
import time
import threading
from brickschema.inference import HaystackInferenceSession
import json

class HaystackJSONDriver(driver.Driver):
    def __init__(self, port, servers, bldg_ns, haystack_file):
        self._haystack_file = haystack_file
        super().__init__(port, servers, bldg_ns)

        t = threading.Thread(target=self._check_source)
        t.start()


    def _check_source(self):
        while True:
            self.load_file(self._haystack_file)
            time.sleep(60)

    def load_file(self, haystack_file):

        def do_load_file():
            self.app.logger.info(f"Loading Haystack JSON dump {haystack_file}")
            self.haystack_model = json.load(open(haystack_file))
            timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S%Z')
            for row in self.haystack_model['rows']:
                sess = HaystackInferenceSession(self._ns)
                model = {'rows': [row]}
                model = sess.infer_model(model)

                rec = {
                    'id': row['id'],
                    'source': type(self).__name__,
                    'record': {
                        'encoding': 'JSON',
                        'content': row,
                    },
                    'triples': list(sess._generated_triples),
                    'timestamp': timestamp
                }
                self.add_record(rec['id'], rec)
            self.app.logger.info(f"Loaded {len(self._records)} records")
            self._compute_changed()
        # start thread
        t = threading.Thread(target=do_load_file)
        t.start()

if __name__ == '__main__':
    srv = HaystackJSONDriver(8080, ["http://localhost:6483"], "http://example.com/building#", "data/haystack/carytown.json")
    srv.serve()
