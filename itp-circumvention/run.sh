#!/bin/sh
set -e

python3 analyze.py
python3 compare.py
python3 stats.py
