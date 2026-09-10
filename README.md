# The Risks of Local Learning: Understanding and Attacking Safari’s Privacy Features
Artifact for our **The Risks of Local Learning: Understanding and Attacking Safari’s Privacy Features** paper to be published in Proceedings on Privacy Enhancing Technologies 2027 (Issue 1).

## Prerequisites
- Docker and Docker Compose installed (consider adding yourself to the docker group [see more](https://docs.docker.com/engine/install/linux-postinstall/#add-your-user-to-the-docker-group))

## Global Setup (Dataset)
Create and download a shared volume for the dataset:
```bash
docker volume create zenodo-data
docker build -t zenodo-fetcher ./dataset
docker run --rm -v zenodo-data:/data zenodo-fetcher
```


## Components
This section describes the different components we designed for this paper, structured as different subdirectories in this repository. For detailed information, refer to the `README.md` in each subdirectory.

### Crawling Infrastructure
The [crawler](crawler) directory contains the crawling infrastructure used for our Tranco Top 10K crawls.

### Data Donation Platform
The [data-donation](data-donation) directory contains the data donation platform used for our user study. It consists of the study web application and the analytic scripts used to analyze the collected data.

### ITP Circumvention Analysis
The [itp-circumvention](itp-circumvention) directory contains the scripts used to analyze ITP circumvention in the wild.

### Proof-of-Concept Code
The [poc](poc) directory contains the proof-of-concept code used to demonstrate the attacks described in our paper.

### WebPrivacy List Evaluation
The [webprivacy-blocking-performance](webprivacy-blocking-performance) directory contains the scripts used to evaluate the performance of the WebPrivacy blocking lists in comparison to the reference lists.

### WebPrivacy List Crawler
The [webprivacy-crawler](webprivacy-crawler) directory contains the WebPrivacy list crawler used to periodically fetch all WebPrivacy lists.

### WebKit Patches
The [webkit-patches](webkit-patches) directory contains the WebKit patches for enhanced logging.
