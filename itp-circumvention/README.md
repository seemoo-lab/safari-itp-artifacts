# In-the-Wild Circumvention
This folder produces the data used in Section 6.3 of our paper.

## Setup
1. Built the docker image:
```
docker build -t itp-circumvention .
```
2. Run the docker image:
```
docker run -v $(pwd):/app/results -v zenodo-data:/data:ro itp-circumvention
```

## Outputs
In addition to the logging to the console, the container produces a number of output files:
- `successful_circumventions.json`: Evidence of sites successfully circumventing ITP's script-written purge
- `top_cookies_lifetime_table.md`: Top 10 most frequent persistent cookies (Table 4)
- `itp_purge_cookie_downgrade_evidence.json`: Top 10 domains receiving persistent tracking identifiers (Table 5)
