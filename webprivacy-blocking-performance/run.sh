#!/bin/sh
set -e

# Baseline volumes
python3 -m baseline.stats

# Update frequency and observed changes
python3 -m cumulative.stats
python3 -m cumulative.plot

# Blocking performance, including false positives and false negatives
python3 -m fn_fp_analysis.analyze
python3 -m fn_fp_analysis.stats
