from flask import Flask, request, json
from jsonschema import validate
import reasonable
import logging
import rdflib
import time

app = Flask(__name__, static_url_path='')
app.logger.setLevel(logging.INFO)

_add_record_schema = json.load(open('./schemas/record.schema.json'))

graph = rdflib.Graph()
graph.parse("ttl/Brick.ttl", format="ttl")
r = reasonable.PyReasoner()
r.from_graph(graph)

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
        num_added += len(triples)
    print(f"Updating graph with {num_added} triple")
    t0 = time.time()
    triples = r.reason()
    update_graph(triples)
    t1 = time.time()
    print(f"Graph now contains {len(graph)} triples (updated in {t1-t0:.2f} sec)")
    return "ok"


if __name__ == '__main__':
    app.run(host='localhost', port='6483')
