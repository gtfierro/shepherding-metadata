"""
"""
import sys
sys.path.append('.')
import resolver
from brickschema.namespaces import BRICK
import rdflib
from server import Triplestore
ts = Triplestore("triples.db")

with ts.cursor() as cur:
    res = cur.execute("SELECT DISTINCT src FROM latest_triples")
    sites = [row[0] for row in res]
    print(sites)

graphs = {}

full_graph, canonical = resolver.resolve(ts.to_records())
full_graph.serialize('eval.ttl', format='ttl')

# canonicalize
def canonicalize_ent(t):
    for cluster, ent in canonical:
        if t[0] in cluster:
            return (ent, t[1], t[2])
    return t

# get one "authoritative" ID per cluster
# clusters = []
# res = full_graph.query("SELECT ?e1 ?e2 WHERE { \
#     ?e1 owl:sameAs ?e2 . ?e1 brick:sourcelabel ?l1 . \
#     ?e2 brick:sourcelabel ?l2 }")
# for row in res:
#     e1, e2 = str(row[0]), str(row[1])
#     added = False
#     for c in clusters:
#         if e1 in c:
#             c.add(e2)
#             added = True
#             break
#         elif e2 in c:
#             c.add(e1)
#             added = True
#             break
#     if not added:
#         clusters.append(set([e1, e2]))
# print(clusters)
# entities = [list(c)[0] for c in clusters]


# get all of the triples with an entity as a subject
res = full_graph.query("SELECT ?s ?p ?o WHERE { \
    ?s ?p ?o . \
    ?s brick:sourcelabel ?l }")
# filter out non-unified entities
# res = [t for t in res if str(t[0]) in entities]
# filter out blank nodes
res = [t for t in res if not isinstance(t[2], rdflib.BNode)]
# filter out tags
res = [t for t in res if t[1] != BRICK.hasTag]
res = [t for t in res if 'building#' in str(t)]
# TODO: do not "double count" triples when the entities are the same


for site in sites:
    with ts.cursor() as cur:
        triples = cur.execute("SELECT s, p, o FROM latest_triples where src = ?", (site, ))#  and (s LIKE '%building#%' or o LIKE '%building#%')", (site, ))
        triples = list(map(canonicalize_ent, triples))
        graphs[site] = triples

# unions
for site, subgraph in graphs.items():
    print(f"UNION,{site},{len(subgraph) / len(res)}")

# intersections
common_triples = set()
for site, subgraph in graphs.items():
    print('-'*20)
    fix = lambda x: tuple(map(str, x))
    if len(common_triples) == 0:
        [common_triples.add(fix(t)) for t in subgraph]
    else:
        trips = set([fix(t) for t in subgraph])
        common_triples = common_triples.intersection(trips)
print(f"INTERSECTION,{len(common_triples)},{len(common_triples)/len(res)}")

# # set diferences
# for site, subgraph in graphs.items():
#     fix = lambda x: tuple(map(str, x))
#     trips = set([fix(t) for t in subgraph])
#     print(f"SET DIFF,{site},{
