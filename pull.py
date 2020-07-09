import requests

ids = requests.get('http://localhost:8080/ids').json()
for ident in ids:
    print(f"Fetching {ident}")
    rec = requests.get(f'http://localhost:8080/id/{ident}').json()
    print(rec['triples'])
