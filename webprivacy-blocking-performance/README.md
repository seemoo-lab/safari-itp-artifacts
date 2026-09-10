# WebPrivacy List Blocking Performance
This folder produces the data used in Section 6.1 of our paper.

## Structure
- `baseline/`: Scripts to analyze the baseline rule volume and domain coverage.
- `cumulative/`: Scripts to analyze update frequency and observed changes.
- `fn-fp-analysis/`: Scripts to analyze blocking performance, false negatives, and false positives.

## Setup
1. Built the docker image:
```
docker build -t webprivacy-eval .
```
2. Generate a [GitHub personal access token](https://github.com/settings/tokens/new) without any scopes required.
3. Run the docker image with the GitHub token:
```
docker run -e GITHUB_TOKEN="<your_token>" -v $(pwd):/app/results -v zenodo-data:/data:ro webprivacy-eval
```

## Outputs
In addition to the logging to the console, the container produces a number of output files:
- `blocker_extended_analysis_results.json`: Fine-grained per-list blocking results
- `blocker_request_level_results.jsonl`: Per-request blocking results for each list