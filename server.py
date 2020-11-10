from flask import Flask, request, json, jsonify
from flask_cors import CORS, cross_origin
from jsonschema import validate
from collections import defaultdict
from brickschema.namespaces import RDF, RDFS, BRICK
import reasonable
import resolver
import logging
import rdflib
import re
import time
from contextlib import contextmanager
import sqlite3

def preprocess(column):
    column = re.sub('  +', ' ', column)
    column = re.sub('\n', ' ', column)
    column = re.sub('-', ' ', column)
    column = column.strip().strip('"').strip("'").lower().strip()
    if not column :
        column = None
    return column

def fix_term(term):
    if ' ' in term or term == 'unknown':
        return rdflib.Literal(term)
    if 'http' in term:
        return rdflib.URIRef(term)
    return rdflib.Literal(term)

def fix_triple(t):
    return (fix_term(t[0]), fix_term(t[1]), fix_term(t[2]))

def update_graph(triples):
    for t in triples:
        t = tuple(map(fix_term, t))
        graph.add(t)

def rewrite_labels(triples):
    for t in triples:
        if t[1] == RDFS.label:
            yield (t[0], BRICK.sourcelabel, t[2])
        yield t


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
            SELECT s, p, o, lv.sourcename as src, lv.timestamp as timestamp FROM triples
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

    def to_records(self):
        records = defaultdict(list)
        with self.cursor() as cur:
            cur.execute("SELECT src, s, p, o FROM latest_triples")
            for row in cur:
                records[row[0]].append((fix_term(row[1]), fix_term(row[2]), fix_term(row[3])))
        return records

    def latest_version(self, srcname):
        with self.cursor() as cur:
            cur.execute("SELECT distinct timestamp FROM latest_triples WHERE src = ?", (srcname,))
            return cur.fetchone()

    def dump(self):
        with self.cursor() as cur:
            cur.execute("SELECT s, p, o FROM latest_triples")
            for row in cur:
                print(">", row)

triplestore = Triplestore("triples.db")

app = Flask(__name__, static_url_path='')
app.logger.setLevel(logging.DEBUG)
cors = CORS(app, send_wildcard=True)

_add_record_schema = json.load(open('./schemas/record.schema.json'))

graph = rdflib.Graph()
graph.parse("ttl/Brick.ttl", format="ttl")
r = reasonable.PyReasoner()
r.from_graph(graph)
resolved = None

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
        # triples = map(tuple, rec['triples'])
        triples = map(fix_triple, rec['triples'])
        triples = rewrite_labels(triples)
        triples = list(triples)
        # for t in triples:
        #     print(t)

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
    # clear cache
    resolved = None

    return jsonify({'latest': triplestore.latest_version(rec['source'])})

@app.route('/graph', methods=['GET'])
@cross_origin()
def get_graph():
    global resolved
    if resolved is None:
        make_resolve_graph()
    context = {"@vocab": "https://brickschema.org/schema/1.1/Brick#", "@language": "en"}
    return resolved.serialize(format='json-ld', context=context)

@app.route('/resolve', methods=['GET'])
def resolve():
    global resolved
    make_resolve_graph()
    return jsonify({'size': len(resolved)})

def make_resolve_graph():
    global resolved
    t0 = time.time()
    records = triplestore.to_records()
    graph, _ = resolver.resolve(records)
    t1 = time.time()
    print(f"Resolve took {t1-t0:.2f} seconds, had {len(graph)} triples")

    res = list(graph.query("SELECT ?s ?p ?o WHERE { \
                        ?s rdf:type ?type .\
                        { ?type rdfs:subClassOf+ brick:Equipment } \
                        UNION \
                        { ?type rdfs:subClassOf+ brick:System } \
                        UNION \
                        { ?type rdfs:subClassOf+ brick:Point } \
                        UNION \
                        { ?type rdfs:subClassOf+ brick:Location } \
                        ?s ?p ?o . \
                        FILTER (!isBlank(?o))}"))
    resolved = rdflib.Graph()
    # add everything to the graph
    for row in res:
        resolved.add(row)
    # loop through and remove
    entities = set((r[0] for r in res))
    for ent in entities:
        eclasses = list(resolved.objects(predicate=rdflib.RDF.type, subject=ent))
        print("\n\nlook at", ent)
        if len(eclasses) == 1:
            print("only", eclasses)
            continue
        for eclass in eclasses:
            # if eclass is not the most specific class, remove this triple
            print(f"SELECT ?subc WHERE {{ ?subc rdfs:subClassOf+ <{eclass}> }}")
            subclasses = [r[0] for r in graph.query(f"SELECT ?subc WHERE {{ ?subc rdfs:subClassOf+ <{eclass}> }}")]
            if len(subclasses) < 10:
                print(f"----{eclass}:\nsubclasses {subclasses}\nbase {eclasses}")
            else:
                print(f"----{eclass}:\nsubclasses {len(subclasses)}\nbase {eclasses}")

            if len(subclasses) == 0:
                print(f"class {eclass} is specific (is leaf class)")
                continue
            overlap = len(set(subclasses).intersection(set(eclasses)))
            if  overlap > 2 or (overlap <= 2 and eclass not in subclasses):
                print(f"class {eclass} is not specific enough (overlap) {overlap}")
                resolved.remove((ent, rdflib.RDF.type, eclass))
            else:
                print(f"class {eclass} is specific")
    resolved.serialize('resolved.ttl', format='ttl')

if __name__ == '__main__':
    app.run(host='localhost', port='6483')
