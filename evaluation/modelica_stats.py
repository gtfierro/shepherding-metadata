import os
import sys
import pandas as pd
import requests
import threading
import time
sys.path.append(".")
from driver import Driver


def add(x, y):
    return x+y


def get(uri):
    return requests.get(uri).json()


if len(sys.argv) < 2:
    print("Usage: python evaluation/modelica_stats.py lib_path modelica_json path")

# file_dir = sys.argv[1]
lib_path, modelica_json, path = sys.argv[1:]

# for filename in glob.glob(f"{file_dir}/*.xml"):

bldg = os.path.basename(modelica_json)
cfg = {
    "server": {
        "port": 8083,
        "servers": ["http://localhost:6483"],
        "ns": f"http://example.com/{bldg}#",
        "driver": "modelica_driver.ModelicaJSONDriver"
    },
    "driver": {
        "lib_path": lib_path,
        "modelica_json_file": modelica_json,
        "path": path,
    }
}

t = threading.Thread(daemon=True, target=Driver.start_from_config, args=(cfg,))
t.start()
records = []

size_last_changed = time.time()
size_output = 0

start_time = time.time()
while True:
    if (time.time() - size_last_changed) > 5:
        print(f"Size has been {size_output} for last 5 seconds")
        break
    try:
        time.sleep(1)
        resp = requests.get(f"http://localhost:8083/ids")
        elapsed = 1000 * (time.time() - start_time)
        num_triples = 0
        for ident in resp.json():
            num_triples += len(get(f"http://localhost:8083/id/{ident}")['triples'])
        if num_triples == 0:
            size_last_changed = time.time()
            continue
        records.append(("modelica", bldg, elapsed, len(resp.json()), num_triples))
        if num_triples != size_output:
            size_output = num_triples
            size_last_changed = time.time()
        print(records[-1])
    except Exception as e:
        print(e)
        break

# TODO: dataframe
df = pd.DataFrame.from_records(records, columns=['sourcetype', 'site', 'elapsed', '# ids', '# triples'])
df.to_csv('evaluation/modelica_stats.csv', mode='a', header=False, index=False)
print("Cleaning up")
resp = requests.post(f"http://localhost:8083/shutdown")
t.join()


