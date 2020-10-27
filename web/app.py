from flask import Flask, request, json, jsonify, send_from_directory
import time
import requests
from threading import Thread
from datetime import datetime
import logging
import sys
sys.path.append('.')
from driver import Driver
logging.basicConfig(level=logging.INFO)

app = Flask(__name__, static_url_path='/static')
app.logger.setLevel(logging.INFO)

# store (timestamp, drivername) => driver thread
next_port = 8081
ports = {}
drivers = {}

def pt(timestamp):
    """parses RFC3339 timestamps"""
    return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')

def start_driver(driver_cfg):
    global next_port
    key = (driver_cfg['time'], driver_cfg['driver'])
    port = None
    if key not in drivers:
        cfg = {
            "server": config['server'],
        }
        cfg['server']['port'] = next_port
        ports[key] = next_port
        next_port += 1
        cfg['server']['driver'] = driver_cfg.pop('driver')
        cfg['driver'] = driver_cfg
        logging.info(f"Starting driver {key}")
        t = Thread(target=Driver.start_from_config, args=(cfg,), daemon=True)
        t.start()
        drivers[key] = t
    else:
        logging.info(f"Driver {key} already started")
    # return address of driver
    return f"http://localhost:{ports[key]}"


config = {
    "server": {
        "ns": "http://example.com/building#",
        "servers": ['http://localhost:6483']
    },
    "timeline": [
        {
            "time": "2020-01-01T00:00:00Z",
            "label": "First Haystack",
            "driver": "haystack_json_driver.HaystackJSONDriver",
            "file": "data/haystack/carytown.json"
        },
        {
            "time": "2019-01-01T00:00:00Z",
            "label": "First Building Sync",
            "driver": "bsync_driver.BuildingSyncDriver",
            "mapping_file": "data/buildingsync/BSync-to-Brick.csv",
            "bsync_file": "data/buildingsync/examples/bsync-carytown.xml"
        },
        {
            "time": "2019-05-01T00:00:00Z",
            "label": "Updated BSync",
            "driver": "bsync_driver.BuildingSyncDriver",
            "mapping_file": "data/buildingsync/BSync-to-Brick.csv",
            "bsync_file": "data/buildingsync/examples/bsync-carytown.xml"
        }
    ]
}

@app.route('/', methods=['GET'])
def index():
    return send_from_directory('static', 'index.html')

@app.route('/timeline', methods=['GET'])
def get_timeline():
    """
    Returns unique timestamps in RFC3339 format in ascending order
    """
    times = [x for x in config['timeline']]
    return jsonify(sorted(times, key=lambda x: pt(x['time'])))

@app.route('/sources', methods=['GET'])
def get_sources():
    # TODO: return at least the most recent source version for each driver
    before = request.args.get('before', None)
    after = request.args.get('after', None)
    limit = int(request.args.get('limit', len(config['timeline'])))
    inverse = False
    ret = []
    for version in config['timeline']:
        if before and after:
            if pt(version['time']) <= pt(before) and pt(version['time']) >= pt(after):
                ret.append(version)
                continue
        elif before and pt(version['time']) <= pt(before):
            inverse = True
            ret.append(version)
            continue
        elif after and pt(version['time']) >= pt(after):
            ret.append(version)
            continue
        elif not before and not after:
            ret.append(version)
    if inverse:
        return jsonify(sorted(ret, key=lambda x: pt(x['time']))[-limit:])
    return jsonify(sorted(ret, key=lambda x: pt(x['time']))[:limit])

@app.route('/get_records', methods=['POST'])
def get_records():
    _cfg = request.get_json(force=True)
    addr = start_driver(_cfg)
    time.sleep(1)
    resp = []
    ids = requests.get(addr + "/ids").json()
    for rid in ids:
        resp.append(requests.get(addr + "/id/" + rid).json())
    return jsonify(resp)


if __name__ == '__main__':
    app.run(host='localhost', port='5000', threaded=True)
