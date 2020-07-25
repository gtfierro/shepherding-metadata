import glob
import os
import sys
sys.path.append(".")
import pandas as pd
from driver import Driver
import requests
import threading
import time

if len(sys.argv) < 3:
    print("Usage: python evaluation/haystack_stats.py <file_dir> <timeout>")

file_dir = sys.argv[1]
timeout = int(sys.argv[2])

for filename in glob.glob(f"{file_dir}/*.json"):

    bldg = os.path.basename(filename).split(".")[0]
    cfg = {
        "server": {
            "port": 8080,
            "servers": ["http://localhost:6483"],
            "ns": f"http://example.com/building#",
            "driver": "haystack_json_driver.HaystackJSONDriver"
        },
        "driver": {
            "file": filename
        }
    }

    t = threading.Thread(daemon=True, target=Driver.start_from_config, args=(cfg,))
    t.start()
    records = []

    start_time = time.time()
    while True:
        if int(time.time() - start_time) > timeout:
            break
        try:
            time.sleep(1)
            resp = requests.get(f"http://localhost:8080/ids")
            elapsed = 1000 * (time.time() - start_time)
            records.append(("haystack", bldg, elapsed, len(resp.json()), len(resp.content)))
            print(records[-1])
        except Exception as e:
            print(e)
            break

    # TODO: dataframe
    df = pd.DataFrame.from_records(records, columns=['sourcetype', 'site', 'elapsed', '# ids', 'bytes'])
    df.to_csv('evaluation/haystack_stats.csv', mode='a', header=False, index=False)
    print("Cleaning up")
    resp = requests.post(f"http://localhost:8080/shutdown")
    t.join()
