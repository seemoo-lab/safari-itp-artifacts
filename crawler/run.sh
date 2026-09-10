#!/bin/sh
set -e

python3 -m dataset.create --list "4342X" --k 100

python3 main.py