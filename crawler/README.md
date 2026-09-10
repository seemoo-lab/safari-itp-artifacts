# Playwright Crawler
This folder produces the crawling data used in Sections 6.1 and 6.3.

By default this crawls the top 100 pages instead of the top 10K used in the paper, to keep the run time manageable. Change the `--k` parameter in `run.sh` to 10000 to reproduce the full run.

## Setup
Instructions to set up the environment.
1. Copy the example environment file and fill in the values:
```
cp example.env .env
```
2. Edit `.env` and source it:
```
source .env
```
3. Start the database and crawler:
```
docker compose up -d
```

## Outputs
Extract the crawled data as JSONL:
```bash
docker compose --profile export run --rm export
```

This produces two files:
- `crawl_webkit_1.jsonl`: First crawl results
- `crawl_webkit_2.jsonl`: Second crawl results