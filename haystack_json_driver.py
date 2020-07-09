from brickschema.inference import HaystackInferenceSession
from flask import Flask, request, json
from datetime import datetime
import threading

# TODO: hash the file contents and store on disk so we can avoid recompute
# TODO: periodically check for changed file?

class HaystackJSONDriver:
    def __init__(self, port, bldg_ns, haystack_file):
        self._port = port
        self._ns = bldg_ns
        self._records = {}

        self.app = Flask(__name__, static_url_path='')

        self.load_file(haystack_file)

        self.app.logger.info(f"Setting up Flask routes")
        self.app.add_url_rule('/', view_func=self.http_resources)
        self.app.add_url_rule('/ids', view_func=self.http_ids)
        self.app.add_url_rule('/id/<ident>', view_func=self.http_record)

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
                    'record': {
                        'json': row,
                    },
                    'triples': list(sess._generated_triples),
                    'timestamp': timestamp
                }
                self._records[rec['id']] = rec
            self.app.logger.info(f"Loaded {len(self._records)} records")
        # start thread
        t = threading.Thread(target=do_load_file)
        t.start()

    def http_resources(self):
        return json.jsonify(['ids'])

    def http_ids(self):
        return json.jsonify(list(self._records.keys()))

    def http_record(self, ident):
        return json.jsonify(self._records.get(ident))

    def serve(self):
        self.app.run(host='localhost', port=str(self._port), debug=True)


if __name__ == '__main__':
    srv = HaystackJSONDriver(8080, "http://example.com/haystack#", "data/haystack/carytown.json")
    srv.serve()
