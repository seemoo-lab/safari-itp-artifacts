#!/bin/bash

DATE=$(date +%d%m%Y_%H%M)
cd /app && /usr/local/bin/python webprivacy.py --output_dir /app/output/output_${DATE}