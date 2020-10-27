import requests

cfg = {
    "time": "2019-05-01T00:00:00Z",
    "driver": "bsync_driver.BuildingSyncDriver",
    "mapping_file": "data/buildingsync/BSync-to-Brick.csv",
    "bsync_file": "data/buildingsync/examples/bsync-carytown.xml"
}

resp = requests.post('http://localhost:5000/get_records', json=cfg)
print(resp.json())
