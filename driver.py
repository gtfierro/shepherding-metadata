from flask import Flask, request, json
from datetime import datetime
import toml
import logging
import requests
import threading
import hashlib
import time


class Driver:
    def __init__(self, port, servers, bldg_ns):
        self._port = port
        self._servers = servers
        self._server_updated = {srv: False for srv in self._servers}
        self._ns = bldg_ns
        self._records = {}
        self._source_hash = None

        self.app = Flask(__name__, static_url_path='')
        self.app.logger.setLevel(logging.INFO)
        self.app.logger.info(f"Setting up Flask routes")
        self.app.add_url_rule('/', view_func=self.http_resources)
        self.app.add_url_rule('/ids', view_func=self.http_ids)
        self.app.add_url_rule('/id/<ident>', view_func=self.http_record)

        self.app.logger.info("INITIALIZED")
        # start thread
        t = threading.Thread(target=self._monitor_push, daemon=True)
        t.start()

    def _compute_changed(self):
        m = hashlib.sha256()
        for ident in sorted(self.ids):
            defn = self.get_id(ident)
            b = bytes(json.dumps(defn.get('record')), 'utf-8')
            m.update(b)
        mhash = m.digest()
        changed = mhash != self._source_hash
        if mhash != self._source_hash:
            for srv in self._servers:
                self._server_updated[srv] = False
        self._source_hash = mhash

    @property
    def ids(self):
        return self._records.keys()

    def get_id(self, ident):
        return self._records.get(ident)

    def add_record(self, ident, record):
        self._records[ident] = record

    def _monitor_push(self):
        while True:
            # self.app.logger.info("Start update")
            for srv, updated in self._server_updated.items():
                # if updated:
                #     continue
                self.app.logger.info(f"Push to {srv}")
                self._push(srv)
            time.sleep(10)

    def _push(self, server):
        """
        Pushes records to the server
        """
        defns = [self.get_id(ident) for ident in list(self.ids)]
        #for ident in list(self.ids):
        #    defn = self.get_id(ident)
        if len(defns) == 0:
            return
        self.app.logger.info(f"Updating {server} with {len(defns)} records")
        url = f"{server}/add_record"
        try:
            resp = requests.post(url, json=defns)
        except Exception as e:
            self.app.logger.error(str(e))
            return
        if not resp.ok:
            self.app.logger.error(f"{resp.reason} {resp.content}")
            return
        self._server_updated[server] = True

    def http_resources(self):
        return json.jsonify(['ids'])

    def http_ids(self):
        return json.jsonify(list(self._records.keys()))

    def http_record(self, ident):
        return json.jsonify(self._records.get(ident))

    def serve(self):
        self.app.run(host='localhost', port=str(self._port))

    @classmethod
    def start_from_config(cls, filename):
        cfg = toml.load(open(filename))
        srv_cfg = cfg.get('server')
        if srv_cfg is None:
            raise Exception("Need 'server' section")
        srv = cls(srv_cfg['port'], srv_cfg['servers'], srv_cfg['ns'], cfg.get('driver'))
        srv.serve()
