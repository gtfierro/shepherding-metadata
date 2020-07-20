import re
from collections import defaultdict
import pandas as pd
from scipy import stats
import numpy as np
from rdflib import Namespace, Literal
from brickschema.namespaces import BRICK, A, RDF, RDFS
from brickschema.inference import BrickInferenceSession
from brickschema.graph import Graph

import distance
import recordlinkage
from recordlinkage.base import BaseCompareFeature

def graph_from_triples(triples):
    g = Graph(load_brick=True)
    g.add(*triples)
    sess = BrickInferenceSession()
    return sess.expand(g)

def tokenize_string(s):
    s = s.lower()
    s = re.split(r'-| |_|#|/', s)
    return s


class VectorLevenshteinCompare(BaseCompareFeature):
    def _compute_vectorized(self, s1, s2):
        # calculate pair-wise levenshtein
        sim = np.array([-distance.levenshtein(list(s1[i]), list(s2[i])) \
                    for i in range(len(s1))])
        # normalize to [0, 1]
        sim = (sim - np.min(sim))/np.ptp(sim)
        return sim


class MaxLevenshteinMatch(BaseCompareFeature):
    def _compute_vectorized(self, s1, s2):
        # calculate pair-wise levenshtein
        s1 = list(s1)
        s2 = list(s2)
        sim = np.array([distance.levenshtein(s1[i], s2[i]) for i in range(len(s1))])
        min_sim = np.min(sim)
        sim = np.array([1 if x == min_sim else 0 for x in sim])
        return sim


def cluster_on_labels(graphs):
    # populates the following list; contains lists of URIs that are linked to be
    # the same entity
    clusters = []

    datasets = []
    for source, graph in graphs.items():
        df = pd.DataFrame(columns=['label', 'uris'])
        print(f"{'-'*5} {source} {'-'*5}")
        res = graph.query("SELECT ?ent ?lab WHERE { \
                            ?ent rdf:type/rdfs:subClassOf brick:Class .\
                            ?ent brick:sourcelabel ?lab }")
        # TODO: remove common prefix from labels?
        labels = [tokenize_string(str(row[1])) for row in res \
                    if isinstance(row[1], Literal)]
        uris = [row[0] for row in res if isinstance(row[1], Literal)]
        df['label'] = labels
        df['uris'] = uris
        datasets.append(df)


    indexer = recordlinkage.Index()
    indexer.full()
    candidate_links = indexer.index(*datasets)
    comp = recordlinkage.Compare()
    comp.add(VectorLevenshteinCompare('label', 'label', label='y_label'))
    features = comp.compute(candidate_links, *datasets)
    # use metric of '>=.9' because there's just one feature for now and it scales
    # [0, 1]
    matches = features[features.sum(axis=1) >= .9]
    for idx_list in matches.index:
        pairs = zip(datasets, idx_list)
        entities = [ds['uris'].iloc[idx] for ds, idx in pairs]
        clusters.append(entities)

    return clusters

def cluster_on_type_alignment(graphs):
    clusters = []
    counts = defaultdict(lambda: defaultdict(set))
    uris = {}
    for source, graph in graphs.items():
        res = graph.query("SELECT ?ent ?type ?lab WHERE { \
                ?ent rdf:type ?type .\
                ?type rdfs:subClassOf+ brick:Class .\
                ?ent brick:sourcelabel ?lab }")
        for row in res:
            entity, brickclass, label = row
            counts[brickclass][source].add(str(label))
            uris[str(label)] = entity
    for bc, c in counts.items():
        mode_count = stats.mode([len(x) for x in c.values()]).mode[0]
        candidates = [(src, list(ents)) for src, ents in c.items() if len(ents) == mode_count]
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
            if entities in clusters:
                continue
            clusters.append(entities)

    return clusters

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
    ],
}

graphs = {source: graph_from_triples(triples) \
          for source, triples in records.items()}

clusters = []
clusters.extend(cluster_on_labels(graphs))
clusters.extend(cluster_on_type_alignment(graphs))

for cluster in clusters:
    print([str(x) for x in cluster])
