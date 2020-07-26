import glob
import os
import sys
sys.path.append(".")
import pandas as pd
from driver import Driver
import requests
import threading
import time

add = lambda x,y: x+y
get = lambda uri: requests.get(uri).json()

if len(sys.argv) < 2:
    print("Usage: python evaluation/haystack_stats.py <file_dir>")

file_dir = sys.argv[1]

for filename in glob.glob(f"{file_dir}/*.json"):

    bldg = os.path.basename(filename).split(".")[0]
    cfg = {
        "server": {
            "port": 8080,
            "servers": ["http://localhost:6483"],
            "ns": f"http://example.com/{bldg}#",
            "driver": "haystack_json_driver.HaystackJSONDriver"
        },
        "driver": {
            "file": filename
        }
    }

    t = threading.Thread(daemon=True, target=Driver.start_from_config, args=(cfg,))
    t.start()
    records = []

    size_last_changed = time.time()
    size_output = 0

    start_time = time.time()
    while True:
        if (time.time() - size_last_changed) > 20 and size_output > 0:
            print(f"Size has been {size_output} for last 20 seconds")
            break
        try:
            time.sleep(1)
            resp = requests.get(f"http://localhost:8080/ids")
            elapsed = 1000 * (time.time() - start_time)
            num_triples = 0
            for ident in resp.json():
                num_triples += len(get(f"http://localhost:8080/id/{ident}")['triples'])
            if num_triples == 0:
                continue
            records.append(("haystack", bldg, elapsed, len(resp.json()), num_triples))
            if num_triples != size_output:
                size_output = num_triples
                size_last_changed = time.time()
            print(records[-1])
        except Exception as e:
            print(e)
            break

    # TODO: dataframe
    df = pd.DataFrame.from_records(records, columns=['sourcetype', 'site', 'elapsed', '# ids', '# triples'])
    df.to_csv('evaluation/haystack_stats.csv', mode='a', header=False, index=False)
    print("Cleaning up")
    resp = requests.post(f"http://localhost:8080/shutdown")
    t.join()
