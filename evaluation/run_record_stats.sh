#!/bin/bash

rm evaluation/record_stats.csv
for cfg in `ls cfgs/*.toml`; do
    python evaluation/record_stats.py $cfg 60
    sleep 10
done
