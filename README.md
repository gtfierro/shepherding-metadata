# Shepherding Metadata

This repository implements the platform described in our [BuildSys 2020 submission](http://people.eecs.berkeley.edu/~gtfierro/papers/shepherding2020fierro.pdf). The current code is of "research-quality" with more than a few sharp edges, so be wary!

## Getting Started

1. Install the Python requirements in `requirements.txt`
2. Drivers are run as standalone processes, and are configured with a `yml` file. Use the `run_driver.py` file to start a driver; this takes a single argument which is a path to a config file:

    ```
    $ python run_driver.py cfgs/bsync_carytown.toml
    2020-11-12:14:12:58,430 INFO    [driver.py:23] Setting up Flask routes
    2020-11-12:14:12:58,431 INFO    [driver.py:29] INITIALIZED
    2020-11-12:14:12:58,431 INFO    [driver.py:63] Push to http://localhost:6483
    2020-11-12:14:12:58,432 INFO    [driver.py:98] Starting driver webserver on port http://localhost:8081
     * Serving Flask app "driver" (lazy loading)
    2020-11-12:14:12:58,432 INFO    [bsync_driver.py:66] Loading BuildingSync file data/buildingsync/examples/bsync-carytown.xml
    2020-11-12:14:12:58,434 INFO    [_internal.py:113]  * Running on http://localhost:8081/ (Press CTRL+C to quit)
    2020-11-12:14:12:58,437 INFO    [bsync_driver.py:130] Loaded 4 records
    ```
    
    You can now visit [`http://localhost:8081/ids`](http://localhost:8081/ids) to see the entities inferred by the driver; visit `http://localhost:8081/id/<identifier>` to see the record for a particular entity, including any inferred Brick metadata. (Example: [`http://localhost:8081/id/Site-1`](http://localhost:8081/id/Site-1)
3. To run the integration server, run `python server.py`; this will create a SQLite store `triples.db` which stores the inferred Brick model. Read the source code for available API endpoints.
