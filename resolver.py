import re
from collections import defaultdict
import pandas as pd
from scipy import stats
import numpy as np
from rdflib import Namespace, Literal, URIRef
from brickschema.namespaces import BRICK, A, OWL
from brickschema.inference import BrickInferenceSession
from brickschema.graph import Graph
import resolve_ui as ui

import distance
import recordlinkage
from recordlinkage.base import BaseCompareFeature



def graph_from_triples(triples):
    g = Graph(load_brick=True)
    # g.load_file("ttl/owl.ttl")
    g.add(*triples)
    sess = BrickInferenceSession()
    return sess.expand(g)


def tokenize_string(s):
    s = s.lower()
    s = re.split(r'-| |_|#|/|:', s)
    return s


def compatible_classes(graph, c1, c2):
    """
    Returns true if the two classes are compatible (equal, or one is a subclass
    of another), false otherwise
    """
    q1 = f"ASK {{ <{c1}> owl:equivalentClass?/rdfs:subClassOf*/owl:equivalentClass? <{c2}> }}"
    q2 = f"ASK {{ <{c2}> owl:equivalentClass?/rdfs:subClassOf*/owl:equivalentClass? <{c1}> }}"
    return graph.query(q1)[0] or graph.query(q2)[0]


def trim_prefix_tokenized(names):
    if len(names) <= 1:
        return names
    max_length = max(map(len, names))
    pfx_size = 1
    # increase pfx_size until it doesn't match, then reduce by 1 and trim
    while pfx_size <= max_length:
        pfx = names[0][:pfx_size]
        if not all(map(lambda x: x[:pfx_size] == pfx, names[1:])):
            pfx_size -= 1
            return list([x[pfx_size:] for x in names])
        pfx_size += 1


# def trim_common_prefix(names):
#     if len(names) <= 1:
#         return names
#     max_length = max(map(len, names))
#     min_length = min(map(len, names))
#     pfx_size = max_length
#     while True:
#         pfx = names[0][:pfx_size]
#         # if prefix is common, we return
#         if not all(map(lambda x: x[:pfx_size] == pfx, names[1:])):
#             pfx_size = int(pfx_size / 2) + 1
#
#         return list([x[:pfx_size] for x in names])


# ignore_brick_classes = [BRICK.Sensor, BRICK


class VectorJaccardCompare(BaseCompareFeature):
    def _compute_vectorized(self, s1, s2):
        s1 = list(s1)
        s2 = list(s2)
        sim = np.array([1-distance.jaccard(s1[i], s2[i])
                       for i in range(len(s1))])
        return sim


class MaxLevenshteinMatch(BaseCompareFeature):
    def _compute_vectorized(self, s1, s2):
        # calculate pair-wise levenshtein
        s1 = list(s1)
        s2 = list(s2)
        sim = np.array([distance.jaccard(s1[i], s2[i])
                       for i in range(len(s1))])
        min_dist = np.min(sim)
        sim = np.array([1 if x == min_dist and x > .8 else 0 for x in sim])
        return sim


def cluster_on_labels(graphs):
    # populates the following list; contains lists of URIs that are linked to
    # be the same entity
    clusters = []
    # list of clustered entities
    clustered = set()

    datasets = []
    for source, graph in graphs.items():
        df = pd.DataFrame(columns=['label', 'uris'])
        print(f"{'-'*5} {source} {'-'*5}")
        res = graph.query("SELECT ?ent ?lab WHERE { \
                            ?ent rdf:type ?type .\
                            { ?type rdfs:subClassOf* brick:Equipment } \
                            UNION \
                            { ?type rdfs:subClassOf* brick:Point } \
                            UNION \
                            { ?type rdfs:subClassOf* brick:Location } \
                            ?ent brick:sourcelabel ?lab }")
        # TODO: remove common prefix from labels?
        labels = [tokenize_string(str(row[1])) for row in res
                  if isinstance(row[1], Literal)]
        # labels = [l for l in labels if l != ["unknown"]]
        labels = trim_prefix_tokenized(labels)
        uris = [row[0] for row in res if isinstance(row[1], Literal)]
        df['label'] = labels
        df['uris'] = uris
        datasets.append(df)

    print("lengths", [len(df) for df in datasets])

    if len(datasets) <= 1:
        return clusters, clustered

    indexer = recordlinkage.Index()
    indexer.full()
    candidate_links = indexer.index(*datasets)
    comp = recordlinkage.Compare()
    comp.add(VectorJaccardCompare('label', 'label', label='y_label'))
    features = comp.compute(candidate_links, *datasets)
    # use metric of '>=.9' because there's just one feature for now and it
    # scales [0, 1]

    matches = features[features.sum(axis=1) >= .9]
    for idx_list in matches.index:
        pairs = zip(datasets, idx_list)
        entities = [ds['uris'].iloc[idx] for ds, idx in pairs]
        for ent in entities:
            clustered.add(str(ent))
        clusters.append(entities)

    return clusters, clustered


def cluster_on_type_alignment(graphs, clustered):
    clusters = []
    counts = defaultdict(lambda: defaultdict(set))
    uris = {}
    for source, graph in graphs.items():
        res = graph.query("SELECT ?ent ?type ?lab WHERE { \
                ?ent rdf:type ?type .\
                { ?type rdfs:subClassOf: brick:Equipment } \
                UNION \
                { ?type rdfs:subClassOf+ brick:Point } \
                UNION \
                { ?type rdfs:subClassOf+ brick:Location } \
                ?ent brick:sourcelabel ?lab }")
        for row in res:
            entity, brickclass, label = row
            if entity in clustered:
                continue
            counts[brickclass][source].add(str(label))
            uris[str(label)] = entity
    for bc, c in counts.items():
        mode_count = stats.mode([len(x) for x in c.values()]).mode[0]
        candidates = [(src, list(ents)) for src, ents in c.items()
                      if len(ents) == mode_count]
        if len(candidates) <= 1:
            continue
        print(f"class {bc} has {len(c)} sources with {mode_count} candidates each")

        # short-circuit in the common case
        if mode_count == 1:
            cluster = [uris[ents[0]] for _, ents in candidates]
            if cluster not in clusters:
                clusters.append(cluster)
            continue

        datasets = [pd.DataFrame({'label': ents, 'uris': [uris[x] for x in ents]}) for (_, ents) in candidates]
        indexer = recordlinkage.Index()
        indexer.full()
        candidate_links = indexer.index(*datasets)
        comp = recordlinkage.Compare()
        comp.add(MaxLevenshteinMatch('label', 'label', label='y_label'))
        features = comp.compute(candidate_links, *datasets)
        matches = features[features.sum(axis=1) == 1]
        for idx_list in matches.index:
            pairs = zip(datasets, idx_list)
            entities = [ds['uris'].iloc[idx] for ds, idx in pairs]
            for ent in entities:
                clustered.add(str(ent))
            if entities in clusters:
                continue
            clusters.append(entities)

    return clusters, clustered


def merge_triples(triples, clusters):
    # choose arbitrary entity as the canonical name
    canonical = [([str(u) for u in c], list(c)[0]) for c in clusters]

    def fix_triple(t):
        for cluster, ent in canonical:
            if t[0] in cluster:
                return (ent, t[1], t[2])
        return t

    def cluster_for_entity(ent):
        candidates = [c for c in clusters if ent in c]
        # ent should be in at most one
        if len(candidates) > 0:
            return candidates[0]
        return None

    # replace = lambda x: [ent for (cluster, ent) in canonical if x in cluster][0]
    triples = list(map(fix_triple, triples))

    graph = graph_from_triples(triples)
    print(len(graph))
    for cluster in clusters:
        pairs = zip(cluster[:-1], cluster[1:])
        triples = [(a, OWL.sameAs, b) for (a, b) in pairs]
        graph.add(*triples)

    sess = BrickInferenceSession()
    graph = sess.expand(graph)


    # check the inferred classes
    # TODO: forward reasonable errors up to Python
    res = graph.query("SELECT ?ent ?type WHERE { \
                        ?ent rdf:type ?type .\
                        { ?type rdfs:subClassOf+ brick:Equipment } \
                        UNION \
                        { ?type rdfs:subClassOf+ brick:Point } \
                        UNION \
                        { ?type rdfs:subClassOf+ brick:Location } \
                        ?ent brick:sourcelabel ?lab }")


    dis = ui.UserDisambiguation(graph)

    entity_types = defaultdict(set)
    for row in res:
        # print(">", row)
        ent, brickclass = row[0], row[1]
        entity_types[ent].add(brickclass)

    # TODO: handle this
    """
    How to identify "bad" clusters:
    1) if the types are incompatible

    How to fix bad clusters:
    - easy way: ask user to manually partition the bad clusters and recall the
      merge_triples method (this method) with the new clusters
    """

    # TODO: remove quantity kinds from this??
    redo_clusters = []
    for ent, classlist in entity_types.items():
        classlist = list(classlist)
        for (c1, c2) in zip(classlist[:-1], classlist[1:]):
            if c1 == c2:
                continue
            if not compatible_classes(graph, c1, c2):
                # print(clusters[0], ent, type(ent))
                badcluster = cluster_for_entity(ent)
                if badcluster is not None:
                    print("bad cluster", badcluster)
                    new_clusters = dis.recluster(badcluster)
                    print(new_clusters)
                    redo_clusters.extend(new_clusters)
                else:
                    print("INCOMPATIBLE BUT NO CLUSTER?", ent, c1, c2)
                    # choose class and remove old triple
                    chosen = dis.ask([c1, c2], ent)
                    for c in [c1, c2]:
                        graph.g.remove((ent, A, c))
                    graph.g.add((ent, A, chosen))
                # for c in clusters:
                #     print(ent, c, ent in c)
                break
                # chosen = dis.ask([c1, c2], ent)
                # for c in [c1, c2]:
                #     graph.g.remove((ent, A, c))
                # graph.g.add((ent, A, chosen))
                # print(chosen, ent)
                # print("PROBLEM", S(c1), S(c2), S(ent))
    # TODO: if any exception is thrown, need to recluster
    if len(redo_clusters) > 0:
        new_graph, new_canonical = merge_triples(triples, redo_clusters)
        print(new_canonical)
        print(canonical)
        return new_graph + graph.g, new_canonical + canonical
    else:
        return graph.g, canonical

def resolve(records):
    """
    Records with format {srcname: [list of triples], ...}
    """
    graphs = {source: graph_from_triples(triples) \
              for source, triples in records.items()}

    clusters = []

    new_clusters, clustered = cluster_on_labels(graphs)
    clusters.extend(new_clusters)
    for c in new_clusters:
        print(f"Label cluster: {c}")

    new_clusters, clustered = cluster_on_type_alignment(graphs, clustered)
    clusters.extend(new_clusters)
    for c in new_clusters:
        print(f"Type cluster: {c}")

    # for cluster in clusters:
    #     print([str(x) for x in cluster])

    all_triples = [t for triples in records.values() for t in triples]
    # graph, canonical
    return merge_triples(all_triples, clusters)

if __name__ == '__main__':
    BLDG = Namespace("http://building#")

    records = {
        'haystack': [
            (BLDG['hay-rtu1'], A, BRICK['Rooftop_Unit']),
            (BLDG['hay-rtu1'], BRICK.sourcelabel, Literal("my-cool-building RTU 1")),
            (BLDG['hay-rtu2'], A, BRICK['Rooftop_Unit']),
            (BLDG['hay-rtu2'], BRICK.sourcelabel, Literal("my-cool-building RTU 2")),
            (BLDG['hay-rtu2-fan'], A, BRICK['Supply_Fan']),
            (BLDG['hay-rtu2-fan'], BRICK.sourcelabel, Literal("my-cool-building RTU 2 Fan")),
            (BLDG['hay-site'], A, BRICK['Site']),
            (BLDG['hay-site'], BRICK.sourcelabel, Literal("my-cool-building")),
        ],
        'buildingsync': [
            (BLDG['bsync-ahu1'], A, BRICK['Air_Handler_Unit']),
            (BLDG['bsync-ahu1'], BRICK.sourcelabel, Literal("AHU-1")),
            (BLDG['bsync-ahu2'], A, BRICK['Air_Handler_Unit']),
            (BLDG['bsync-ahu2'], BRICK.sourcelabel, Literal("AHU-2")),
            (BLDG['bsync-site'], A, BRICK['Site']),
            (BLDG['bsync-site'], BRICK.sourcelabel, Literal("my-cool-building")),
            # (BLDG['BADENT'], A, BRICK['Room']),
            # (BLDG['BADENT'], BRICK.sourcelabel, Literal("my-cool-building RTU 2 Fan")),
        ],
    }

    graph = resolve(records)
    print(len(graph))
