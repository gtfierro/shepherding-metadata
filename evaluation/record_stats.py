import toml
import sys
import pandas as pd
import requests
import subprocess
import time

if len(sys.argv) < 3:
    print("Usage: python evaluation/record_stats.py <cfg> <timeout>")

cfg_file = sys.argv[1]
port = toml.load(open(cfg_file))['server']['port']
timeout = int(sys.argv[2])

# measurements
# append (driver, time elapsed in ms, # of IDs, size in bytes)
records = []

# start driver process
start_time = time.time()
process = subprocess.Popen(f"python run_driver.py {cfg_file}", shell=True)
while True:
    if int(time.time() - start_time) > timeout:
        break
    try:
        time.sleep(1)
        resp = requests.get(f"http://localhost:{port}/ids")
        elapsed = 1000 * (time.time() - start_time)
        records.append((cfg_file, elapsed, len(resp.json()), len(resp.content)))
        print(records[-1])
    except Exception as e:
        print(e)
        break

# TODO: dataframe
df = pd.DataFrame.from_records(records, columns=['driver', 'elapsed', '# ids', 'bytes'])
df.to_csv('evaluation/record_stats.csv', mode='a', header=False, index=False)

resp = requests.post(f"http://localhost:{port}/shutdown")
print("Cleaning up")
process.terminate()
print("waiting")
process.wait()
