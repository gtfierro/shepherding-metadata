import glob
from functools import reduce
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
    print("Usage: python evaluation/gbxml_stats.py <file_dir>")

file_dir = sys.argv[1]

for filename in glob.glob(f"{file_dir}/*.xml"):

    bldg = os.path.basename(filename).split(".")[0]
    bldg = bldg.replace(' ', '_')
    cfg = {
        "server": {
            "port": 8082,
            "servers": ["http://localhost:6483"],
            "ns": f"http://example.com/{bldg}#",
            "driver": "gbxml_driver.GBXMLDriver"
        },
        "driver": {
            "gbxml_file": filename,
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
            resp = requests.get(f"http://localhost:8082/ids")
            elapsed = 1000 * (time.time() - start_time)
            num_triples = 0
            for ident in resp.json():
                num_triples += len(get(f"http://localhost:8082/id/{ident}")['triples'])
            if num_triples == 0:
                continue
            records.append(("gbxml", bldg, elapsed, len(resp.json()), num_triples))
            if num_triples != size_output:
                size_output = num_triples
                size_last_changed = time.time()
            print(records[-1])
        except Exception as e:
            print(e)
            break

    # TODO: dataframe
    df = pd.DataFrame.from_records(records, columns=['sourcetype', 'site', 'elapsed', '# ids', '# triples'])
    df.to_csv('evaluation/gbxml_stats.csv', mode='a', header=False, index=False)
    print("Cleaning up")
    resp = requests.post(f"http://localhost:8082/shutdown")
    t.join()


