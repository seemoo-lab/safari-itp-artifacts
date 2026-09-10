import argparse
import logging
from baseline.webprivacy import fetch_counts
from baseline.disconnect import fetch_domains_from_items as fetch_disconnect_domains
from baseline.duckduckgo import fetch_domains_from_items as fetch_duckduckgo_domains
from baseline.easyprivacy import fetch_domains_from_lists as fetch_easyprivacy_domains

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("BaselineStats")


def parse_args():
    parser = argparse.ArgumentParser(description="Run baseline stats analysis.")
    parser.add_argument(
        "--webprivacy-path",
        default="./baseline/webprivacy",
        help="Path to the WebPrivacy dataset directory (default: %(default)s)"
    )
    parser.add_argument(
        "--easyprivacy-path",
        default="./baseline/easyprivacy",
        help="Path to the EasyPrivacy dataset directory (default: %(default)s)"
    )
    parser.add_argument(
        "--disconnect-path",
        default="./baseline/disconnect/services.json",
        help="Path to the Disconnect services.json file (default: %(default)s)"
    )
    parser.add_argument(
        "--duckduckgo-path",
        default="./baseline/duckduckgo/extension-tds.json",
        help="Path to the DuckDuckGo extension-tds.json file (default: %(default)s)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger.info("Starting baseline analysis...")

    webprivacy_domains = fetch_counts(args.webprivacy_path)
    logger.info(f"Number of rules in WebPrivacy dataset: {webprivacy_domains['ALL_RULES']}")
    logger.info(f"Number of unique fingerprinting scripts domains: {webprivacy_domains['FINGERPRINTING_SCRIPTS_DOMAINS']}")
    logger.info(f"Number of unique ATFP domains: {webprivacy_domains['ATFP_DOMAINS']}")
    logger.info(f"Number of unique tracking subnets: {webprivacy_domains['TRACKING_SUBNETS']}")
    logger.info(f"Number of unique query parameters: {webprivacy_domains['QUERY_PARAM']}")

    easyprivacy_domains = fetch_easyprivacy_domains(args.easyprivacy_path)
    logger.info(f"Number of unique domains in EasyPrivacy dataset: {len(easyprivacy_domains)}")

    disconnect_domains = fetch_disconnect_domains(args.disconnect_path)
    logger.info(f"Number of unique domains in Disconnect dataset: {len(disconnect_domains)}")

    duckduckgo_domains = fetch_duckduckgo_domains(args.duckduckgo_path)
    logger.info(f"Number of unique domains in DuckDuckGo dataset: {len(duckduckgo_domains)}")

    logger.info("Baseline analysis completed.")

if __name__ == "__main__":
    main()