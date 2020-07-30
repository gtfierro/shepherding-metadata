from rdflib import URIRef
from prompt_toolkit.shortcuts import radiolist_dialog

class UserDisambiguation:
    def __init__(self, graph):
        self.g = graph

    def S(self, uri):
        if isinstance(uri, str):
            uri = URIRef(uri)
        return uri.n3(self.g.g.namespace_manager)

    def ask(self, classes, entity):
        values = [(c, c) for c in classes]
        dialog = radiolist_dialog(values=values, text=f"Choose correct type for {entity}")
        res = dialog.run()
        return res

    def do_recluster(self, cluster):
        values = [("recluster", "Recluster"), ("keep", "Keep Cluster, Refine Types")]
        dialog = radiolist_dialog(values=values, text=f"Choose how to handle cluster {cluster}")
        res = dialog.run()
        return res == "recluster"

    def recluster(self, bad_cluster):
        clusters = []
        if len(bad_cluster) == 2:
            return [[bad_cluster[0]], [bad_cluster[1]]]
        while len(bad_cluster) > 0:
            print("-"*10)
            for i, c in enumerate(bad_cluster):
                print(f"{i}) {c}")
            print(f"Currently have {len(clusters)}")
            inp_cluster = input("List items in cluster: ")
            ids = [int(i.strip()) for i in inp_cluster]
            values = [bad_cluster[i] for i in ids if i < len(bad_cluster)]
            if len(values) == 0:
                continue
            clusters.append(values)
            for val in values:
                bad_cluster.remove(val)
        return clusters

