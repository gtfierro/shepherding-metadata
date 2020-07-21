from flask import Flask, request, json
from jsonschema import validate
from collections import defaultdict
from brickschema.namespaces import RDF
import reasonable
import logging
import rdflib
import re
import time
from contextlib import contextmanager
import sqlite3

class Triplestore:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)

        self.conn.execute("""CREATE TABLE IF NOT EXISTS triples (
            s TEXT NOT NULL,
            p TEXT NOT NULL,
            o TEXT NOT NULL,
            sourcename TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );""")

        self.conn.execute("""CREATE VIEW IF NOT EXISTS latest_versions AS
            SELECT sourcename, max(timestamp) as timestamp FROM
            triples GROUP BY sourcename""")

        self.conn.execute("""CREATE VIEW IF NOT EXISTS latest_triples AS
            SELECT s, p, o, lv.sourcename as src FROM triples
            INNER JOIN latest_versions AS lv
            ON lv.sourcename = triples.sourcename
               AND lv.timestamp = triples.timestamp""")

    @contextmanager
    def cursor(self):
        cur = self.conn.cursor()
        try:
            yield cur
            self.conn.commit()
        finally:
            cur.close()

    def add_triples(self, src, ts, triples):
        # list of 3-tuples
        with self.cursor() as cur:
            values = ((s, p, o, src, ts) for (s, p, o) in triples)
            cur.executemany("INSERT INTO triples(s, p, o, sourcename, timestamp) VALUES (?, ?, ?, ?, ?)", values)

    def dump(self):
        with self.cursor() as cur:
            cur.execute("SELECT s, p, o FROM latest_triples")
            for row in cur:
                print(">", row)

triplestore = Triplestore("triples.db")

app = Flask(__name__, static_url_path='')
app.logger.setLevel(logging.INFO)

_add_record_schema = json.load(open('./schemas/record.schema.json'))

graph = rdflib.Graph()
graph.parse("ttl/Brick.ttl", format="ttl")
r = reasonable.PyReasoner()
r.from_graph(graph)

def preprocess(column):
    column = re.sub('  +', ' ', column)
    column = re.sub('\n', ' ', column)
    column = re.sub('-', ' ', column)
    column = column.strip().strip('"').strip("'").lower().strip()
    if not column :
        column = None
    return column

def fix_term(term):
    if ' ' in term:
        return rdflib.Literal(term)
    if 'http' in term:
        return rdflib.URIRef(term)
    return rdflib.BNode(term)

def update_graph(triples):
    for t in triples:
        t = tuple(map(fix_term, t))
        graph.add(t)



@app.route('/add_record', methods=['POST'])
def add_triples():
    try:
        msg = request.get_json(force=True)
        validate(msg, schema=_add_record_schema)
    except Exception as e:
        print(e)
        return json.jsonify({'error': str(e)}), 500
    num_added = 0
    for rec in msg:
        if len(rec['triples']) == 0:
            continue
        triples = list(map(tuple, rec['triples']))
        r.load_triples(triples)
        triplestore.add_triples(rec['source'], rec['timestamp'], triples)
        num_added += len(triples)
    print(f"Updating graph with {num_added} triple")
    t0 = time.time()
    triples = r.reason()
    update_graph(triples)
    t1 = time.time()
    print(f"Graph now contains {len(graph)} triples (updated in {t1-t0:.2f} sec)")
    graph.serialize('output.ttl', format='ttl')

    return "ok"


if __name__ == '__main__':
    app.run(host='localhost', port='6483')
