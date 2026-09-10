# Artifact Appendix

Paper title: **The Risks of Local Learning: Analyzing and Exposing Vulnerabilities in Apple Safari's Privacy Defenses**

Requested Badge(s):
  - [x] **Available**
  - [x] **Functional**
  - [x] **Reproduced**

## Description
Artifact for the paper **The Risks of Local Learning: Analyzing and Exposing Vulnerabilities in Apple Safari's Privacy Defenses** by Heiko Kiesel, Nils Rollshausen, Matthias Hollick, and Jiska Classen, to appear in the Proceedings on Privacy Enhancing Technologies 2027(1).

This artifact contains the crawling infrastructure, ITP database donation platform, ITP circumvention in-the-wild analysis scripts, ITP proof-of-concept exploits, WebPrivacy list evaluation scripts, WebPrivacy list crawler, and WebKit patches for enhanced logging.

Finally, we provide an export of our raw crawling and measurement data together with scripts to reproduce results and figures in our paper.

### Security/Privacy Issues and Ethical Concerns

To the best of our knowledge, the measurement components of this artifact pose no security or privacy risk to the evaluator's machine.

Experiment 1 requires a GitHub access token with minimal permissions to pull commit histories from public repositories. This token is exclusively used to authenticate against GitHub.

Our proof-of-concept exploits tamper with Safari ITP's observations database entries. While all communication is local and does not pose a privacy risk, the attacks jam the database and causes ITP to forget its learned trackers. Thus, we strongly recommend backing up ITP's observations database before running the exploits, or running them in a virtual machine to avoid unintended loss of ITP's learned trackers.

**Note:** Our PoC exploits currently remain under embargo due to the ongoing disclosure process. They will be evaluated privately by PETS artifact chairs.

## Basic Requirements

### Hardware Requirements

Can run on a laptop (No special hardware requirements). We recommend running the artifacts on a device with at least 16GB of RAM and 8 CPU cores to ensure smooth execution of the parallel crawling and analysis scripts. The experiment described in the following sections were performed on an off-the-shelf MacBook Pro (arm64).

### Software Requirements

Testing our PoC Attacks requires a MacOS machine with Safari, Python 3, and homebrew installed (we tested on macOS 26.6.2). For all other experiments, we only require a working docker setup.

Needed OS Packages:
- Python >= 3.11
- Python venv
- Docker >= 4.89.0 with Docker Compose

### Estimated Time and Storage Consumption

Overall human time: <40 minutes

Overall compute time: 1 hour

Overall disk space: ~10 GB

## Environment

In the following, we describe the environment setup for using this artifact.

### Accessibility
- Source Code: [GitHub](https://github.com/seemoo-lab/safari-itp-artifacts)
- Datasets: [Zenodo](https://doi.org/10.5281/zenodo.22163942)

*Note: The datasets are automatically downloaded as part of the setup described here.*

### Set Up the Environment

Ensure you have docker and docker-compose installed and ready to use.
Then check out the repository:
```bash
git clone https://github.com/seemoo-lab/safari-itp-artifacts.git
cd safari-itp-artifacts
```
And download the datasets:
```bash
docker volume create zenodo-data
docker build -t zenodo-fetcher ./dataset
docker run --rm -v zenodo-data:/data zenodo-fetcher
```

Finally, build the docker containers used for the experiments:
```bash
cd itp-circumvention
docker build -t itp-circumvention .
cd ../webprivacy-blocking-performance
docker build -t webprivacy-eval .
```

Each subdirectory also contains a README.md file with detailed instructions on how to set up the environment for the respective components of the artifact. 

**Optionally,** if replicating the currently embargoed PoC attacks on MacOS:

```bash
# create a local trusted CA for our test sites
brew install mkcert
mkcert -install
```

### Testing the Environment

In a successful setup, the `docker run` command for the `zenodo-fetcher` should download our datasets for a few minutes (~5-20, depending on connection speed) and produce something similar to the following output:

```
57250K .......... .......... .......... .......... .......... 99% 16.2M 0s
57300K .......... .......... .......... .......... .......   100% 9.27M=9.9s

2026-09-10 11:57:45 (5.63 MB/s) - 'webprivacy-lists.tar.gz' saved [58723426/58723426]

Extracting tar archive...
Cleaning up...
Verifying files...
Success: All files downloaded successfully.
```

Furthermore, all `docker build` commands should indicate successful builds.

## Artifact Evaluation

### Main Results and Claims

Our paper makes three main claims that are supported by the artifacts released here.

#### Main Result 1: WebPrivacy List Blocking Performance

In Section 6.1, we analyze the volume, update frequency, and blocking performance of the static blocklists shipped by Safari.
Analyzing the number of changes over time (Figure 4), we find that Apple's WebPrivacy lists receive hardly any updates, compared to regularly maintained established blocklists. Using requests collected from a Tranco Top 10K crawl, we find that WebPrivacy lists also have high false-negative rates, with 42% of websites embedding trackers that are not detected by WebPrivacy but *are* detected by all of our reference lists.

#### Main Result 2: In-the-Wild Circumvention

In Section 6.3, we show that a number of websites are employing cookie-exfiltration techniques to bypass the limitations on third-party cookies imposed by Safari. On these sites, cookies set in a first-party context via HTTP are forwarded to third-party analytics providers, whose cookies would normally be deleted after a given time by Safari. We find this behaviour on 4% of the top 10K websites.

#### Main Result 3: Proof-of-Concept Exploits

In Section 7, we identify several vulnerabilities in Safari's ITP that can be used to degrade the tracking prevention system and leak sensitive browsing data.
Specifically, we show that an attacker-controlled website can determine whether the user has interacted with arbitrary domains, and whether a certain domain is classified by ITP as a prevalent tracker (Section 7.5). The PoCs we provide implement oracles for both these attacks that can be used to query user-chosen domains.

### Experiments

#### Experiment 1: WebPrivacy Blocking Performance
- Time: 10 human minutes + 15 compute minutes.
- Storage: <10GB

This experiment reproduces **Main Result 1** by performing three distinct analyses:

1. It determines baseline list volumes, reproducing the numbers we give in the *Baseline volumes* paragraph of Section 6.1
2. It computes the number of changes in WebPrivacy lists and popular reference lists over time, using our WebPrivacy snapshots from Zenodo and GitHub commit histories for the reference lists. This reproduces Figure 4 and the numbers in the *Update frequency* paragraph.
3. It performs a false-positive and false-negative analysis of the WebPrivacy lists using data from our web crawl, reproducing the numbers in the *Blocking performance*, *False negatives*, and *False positives* paragraphs. 

To get historical commit data from GitHub, we require a GitHub access token. You can generate one at [github.com/settings/tokens](https://github.com/settings/tokens). Read-only access to public repos without any further permissions is sufficient.

```bash
cd webprivacy-blocking-performance
# docker build -t webprivacy-eval . (if not built already during environment setup)
docker run -e GITHUB_TOKEN="<github token>" -v $(pwd):/app/results -v zenodo-data:/data:ro webprivacy-eval
```

After the run completes, you should see a newly created `cumulative_change_comparison.pdf` in the `webprivacy-blocking-performance` folder showing blocklist updates over time (Figure 4).

You should also see the following (abridged) output:

```
INFO - Number of rules in WebPrivacy dataset: 6193
INFO - Number of unique fingerprinting scripts domains: 218
INFO - Number of unique ATFP domains: 456
INFO - Number of unique tracking subnets: 4
INFO - Number of unique query parameters: 26
INFO - Number of unique domains in EasyPrivacy dataset: 2965
INFO - Number of unique domains in Disconnect dataset: 1915
INFO - Number of unique domains in DuckDuckGo dataset: 4383
...
INFO - Disconnect: 180 domains added, 64 domains removed (total changes: 244)
INFO - DuckDuckGo: 1543 domains added, 3434 domains removed (total changes: 4977)
INFO - EasyPrivacy: 2311 domains added, 782 domains removed (total changes: 3093)
INFO - WebPrivacy: 4 entries added, 1 entries removed (total changes: 5)
...
INFO - Disconnect blocked 198998/904568 requests
INFO - DuckDuckGo blocked 130351/904568 requests
INFO - EasyPrivacy blocked 109931/904568 requests
INFO - Found 42621/904568 requests blocked by FINGERPRINTING_SCRIPTS
INFO - Found 96649/904568 requests blocked by SAFARI_PRIVATE_BROWSING
INFO -   90635/96649 (94.00%) blocked via TRACKING_DOMAINS
INFO -   3674/96649 (3.80%) blocked via TRACKING_SUBNETS
INFO -   2340/96649 (2.42%) blocked via URL_FILTER
...
INFO - Deduplicated 239639 requests blocked by at least one blocker into 168065 unique requests
INFO - Analyzing false negatives for SAFARI_PRIVATE_BROWSING against: ['EasyPrivacy', 'Disconnect', 'DuckDuckGo']
INFO - Found 93795/159641 requests not blocked by SAFARI_PRIVATE_BROWSING but blocked by >=1 reference list
INFO - Resulting FNR: 93795/159641 (59%)
INFO - Found 33809/91848 requests not blocked by SAFARI_PRIVATE_BROWSING but blocked by >=2 reference lists
INFO - Resulting FNR: 33809/91848 (37%)
INFO - Found 14368/46163 requests not blocked by SAFARI_PRIVATE_BROWSING but blocked by all three reference lists
INFO - Resulting FNR: 14368/46163 (31%)
...
INFO - Analyzing false positives for SAFARI_PRIVATE_BROWSING against: ['EasyPrivacy', 'Disconnect', 'DuckDuckGo']
INFO - Only blocked by SAFARI_PRIVATE_BROWSING: 793/168065
INFO - Sites with >=1 unblocked tracker: 367/7218
```


#### Experiment 2: ITP Circumvention

- Time: 10 human-minutes + 5 compute-minutes
- Storage: <10GB

This example experiment supports **Main Result 2**, reproducing the numbers given in Section 6.3, as well as the contents of Tables 4 and 5. It uses requests and cookie values recorded during our two crawls to identify exfiltration of first-party identifiers to third-party services that bypasses Safari's privacy protections.

```bash
cd itp-circumvention
# docker build -t itp-circumvention . (if not built already during environment setup)
docker run -v $(pwd):/app/results -v zenodo-data:/data:ro itp-circumvention
```

After the run completes, you should see `top_cookies_lifetime_table.md` and `top_exfiltrated_domains_table.md` files in the `itp-circumvention` directory matching the contents of Tables 4 and 5.

You should also see the following output:

```
...
INFO - Analysis complete. Found 645 URLs with potential exfiltration evidence. Results written to 'itp_purge_cookie_downgrade_evidence.json'.
INFO - Loaded 645 crawl items from itp_purge_cookie_downgrade_evidence.json.
INFO - Analyzing 645 crawl items across 8 worker processes.
INFO - Analysis complete. Found 288 circumvention cases to blocklist-endpoints.
...
INFO - Total websites exfiltrating cookies: 288
INFO - Total cookies exfiltrated: 373
INFO - Cookies set via CNAME mismatch: 86
INFO - Cookies set via IP cloaking: 87
INFO - Cookies with BOTH CNAME mismatch and IP cloaking: 81
INFO - Total websites evading ITP script-written purge: 214
INFO - Total cookies evading ITP script-written purge: 281
INFO - Results written to results/successful_circumventions.json
INFO - Average cookie lifetime (in days): 353
INFO - Top 10 cookie names account for 65 out of 281 cookies (23.13%)
INFO - Cookies covered by top 10 cookies: 65 (23.13%)
INFO - Top 10 most frequent persistent cookies table written to results/top_cookies_lifetime_table.md
INFO - Exfiltrations covered by top 10 exfiltration domains: 1543 (53.91%)
INFO - Exfiltrations to Google-owned domains: 828 (28.93%)
INFO - Top 10 domains receiving persistent tracking identifiers table written to results/top_exfiltrated_domains_table.md
```

#### Experiment 3: Proof-of-Concept Exploits

- Time: 15 human-minutes + 0 compute-minutes
- Storage: <10GB

This example experiment supports **Main Result 3**, demonstrating the attacks described in Sections 7.4 and 7.5. As subcomponents in these attacks, this also validates the attacks in Section 7.2.

**Note:** Our PoCs remain under embargo as of submission. This experiment requires non-public data that will be provided to PETS artifacts chairs privately. See limitations section.

This experiment requires a MacOS machine with Safari (versions 26.0-26.6.2) installed.

If targeting Safari on a machine that sees everyday use, consider backing up Safari's observation database to avoid destructive changes:

```bash
cp ~/Library/Containers/com.apple.Safari/Data/Library/WebKit/WebsiteData/ResourceLoadStatistics/observations.db backup.db
```

To start from a clean-slate state without any private data, you may also choose `History > Clear History > Last Hour` in Safari. This completely erases the ITP observations database.

Launch the local webserver hosting our test sites:

```bash
cd poc
sudo python3 server.py
```

Then open [itp-poc.local](https://itp-poc.local) in Safari. The page offers several PoC attacks, but all relevant techniques are included in the *interaction leak* chain. For ease of evaluation, we execute only this attack.

On the *interaction leak* page, enter a domain to test for user interaction, for example `apple.com`. Make sure you know if you have interaced with `apple.com` since last clearing Safari history. If in doubt, open `apple.com` now and interact with it (by clicking anywhere on the site).

Once launched, the attack should run for about a minute. After completion, fully close and restart Safari. Return to the interaction leak page, which should now show a "reveal truth" button. The verdict shown should match whether you have / have not interacted with `apple.com`.

Additionally, you can inspect the contents of your observations database (`~/Library/Containers/com.apple.Safari/Data/Library/WebKit/WebsiteData/ResourceLoadStatistics/observations.db`) using our visualization tool at [itp-visualizer.byheiko.de](https://itp-visualizer.byheiko.de) (or any tool capable of reading SQLite3 databases). Note that the online tool processes data entirely on-device.

You should see many entries for `itp-spam-*.invalid` domains, most of them classified as prevalent trackers, as well as an entry for `sentinel.local` that is classified as a tracker iff you have interacted with the target site.

**Note:** Always clear the ITP database by clearing history in Safari before re-running the experiment (last hour is sufficient). Since we re-use attack domains, ITP classifications of that domain from the first run can influence the second. 

To restore your ITP database to the pre-attack state, fully close Safari and replace the database with the backup made previously:

```
rm ~/Library/Containers/com.apple.Safari/Data/Library/WebKit/WebsiteData/ResourceLoadStatistics/observations*
cp backup.db ~/Library/Containers/com.apple.Safari/Data/Library/WebKit/WebsiteData/ResourceLoadStatistics/observations.db
```

## Limitations

To protect the privacy of our study participants, we do not release the full data donations of ITP observation databases we collected. This means that Figure 5, Tables 1, 3, and 6, and the statistics given in Section 6.2 cannot be reproduced directly.

However, we include the full source code for our data donation platform as well as python scripts for data analysis in the `data-donation` directory, allowing replication of our results with a new set of participants in the future.

Additionally, we omit the execution of the Tranco Top 10K crawler runs. A full run takes several hours to complete, and the results depend heavily on the live state of the websites, which changes continuously. To ensure reproducibility of the experiments relying on the crawler, we provide the full raw crawled data in our released datasets.

At the time of evaluation, we are also not yet publicly releasing our attack PoCs. After coordinating with PETS artifact chairs, we decided to have the PoCs privately evaluated outside of the regular artifact evaluation. We will add the PoCs to our public repository on publication of the paper, following the disclosure timeline coordinated with Apple.

## Notes on Reusability

We expect that our tooling may be re-purposed for analysis of other privacy protections in browsers, especially to include Safari's widely deployed protection measures in baseline-measurements for newly proposed privacy enhancing technologies.
