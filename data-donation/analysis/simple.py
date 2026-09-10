import logging
import json
import os
import numpy as np
import pandas as pd
import seaborn as sns
from collections import Counter
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, PercentFormatter, ScalarFormatter, NullLocator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SimpleAnalysis")

INPUT_DIR = "donations"
CURRUPTED_DONATIONS = []

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman"],
    "font.size": 12,
    "axes.labelsize": 12,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.fontsize": 12,
    "legend.title_fontsize": 14
})


def read_json_file(file_path: str):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.error(f"Error reading JSON file {file_path}: {e}")
        return None

def list_all_json_files(input_dir: str):
    json_files = []
    for filename in os.listdir(input_dir):
        if filename.endswith(".json"):
            json_files.append(os.path.join(input_dir, filename))
    return json_files

def plot_count_distribution(counts, key, title):

    plt.hist(counts, bins=20, edgecolor='black')
    plt.title(title)
    plt.xlabel(key)
    plt.ylabel("Frequency")

    plt.gca().yaxis.set_major_locator(plt.MaxNLocator(integer=True))

    plt.grid(axis='y', alpha=0.75)

    plt.savefig(f"{key}_distribution.png")

    plt.show()

def plot_combined_distribution(data_before, data_after, x_label, filename, legend_loc="upper right"):
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Create equal-width bins of 100, from 0 to 1000
    bins = np.arange(0, 1100, 100)
    
    # Plot the grouped histogram
    ax.hist(
        [data_before, data_after], 
        bins=bins, 
        color=['#2b7bba', '#ff7f0e'], 
        label=['Before Filtering', 'After Filtering'],
        edgecolor='black',
        linewidth=0.7
    )
    
    # Lock X-axis limits to your known bounds
    ax.set_xlim(0, 1000)
    
    # Set the tick positions to the geometric center of each 100-unit bin (50, 150, 250...)
    tick_positions = np.arange(50, 1050, 100)
    ax.set_xticks(tick_positions)
    
    # Create string labels that explicitly state the range (e.g., "0-100", "100-200")
    tick_labels = [f"{i}-{i+99}" for i in range(0, 1000, 100)]
    tick_labels[-1] = "900-1000"
    ax.set_xticklabels(tick_labels, rotation=0, ha='center')
    
    # Force Y-axis to only show integer ticks
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    
    ax.set_xlabel(x_label)
    ax.set_ylabel("Frequency")
    ax.legend(loc=legend_loc, frameon=False)
    
    # Keep the grid subtle
    ax.grid(axis='y', alpha=0.5, linestyle='--')
    
    fig.tight_layout()
    fig.savefig(filename, format='pdf', dpi=300)
    plt.close(fig)

def plot_prevalent_domains(prevalent_domains, total_donations):
    # Calculate the frequency (percentage) for each domain
    frequencies = [count / total_donations for count in prevalent_domains.values()]

    # Set up the plot style
    fig, ax = plt.subplots(figsize=(12, 6))

    # Replicate seaborn's 'whitegrid' style
    ax.grid(True, axis='y', linestyle='--', alpha=0.7)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_facecolor('#fff')

    # Capture the outputs of hist to get the exact counts and the bar objects (patches)
    counts, bins, patches = ax.hist(frequencies, bins=20, range=(0, 1), color="#2b7bba", edgecolor="white", log=True)

    ax.yaxis.set_minor_locator(NullLocator())

    # Add text labels above each bar, skipping empty bins
    for count, patch in zip(counts, patches):
        if count > 0:
            # Place text at the center of the bar's x-axis, and right at the top of the bar's y-axis
            ax.text(patch.get_x() + patch.get_width() / 2, patch.get_height(), 
                    str(int(count)), ha='center', va='bottom', fontsize=18)

    # Format the x-axis to show percentages
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0))

    # Format the y-axis to show plain numbers
    y_formatter = ScalarFormatter()
    y_formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(y_formatter)

    # Add labels
    ax.set_xlabel("Presence in Donations")
    ax.set_ylabel("Prevalent Domains (Log Scale)")

    ax.set_ylim(bottom=0.5, top=max(counts) * 2.0)

    plt.tight_layout()
    fig.savefig("prevalent_domains_histogram.pdf", format='pdf', dpi=300)
    #plt.show()


def analyze_questions(donations):
    stats = {
        "adblocker": Counter(),
        "safari_usage": Counter(),
        "platform": Counter(),
        "search_engine": Counter()
    }
    
    for donation in donations:
        q = donation.get("questions", {})
        stats["adblocker"][q.get("usesAdBlocker", "unknown")] += 1
        stats["safari_usage"][q.get("safariUsageFrequency", "unknown")] += 1
        stats["platform"][q.get("platform", "unknown")] += 1
        stats["search_engine"][q.get("searchEngine", "unknown")] += 1

    questions_analysis = {k: dict(v) for k, v in stats.items()}

    logger.info("Ad Blocker Usage:")
    for key, value in questions_analysis["adblocker"].items():
        logger.info(f"  {key}: {value} ({value/len(donations):.2%} of donations)")

    logger.info("Safari Usage Frequency:")
    for key, value in questions_analysis["safari_usage"].items():
        logger.info(f"  {key}: {value} ({value/len(donations):.2%} of donations)")

    logger.info("Platform:")
    for key, value in questions_analysis["platform"].items():
        logger.info(f"  {key}: {value} ({value/len(donations):.2%} of donations)")

    logger.info("Search Engine:")
    for key, value in questions_analysis["search_engine"].items():
        logger.info(f"  {key}: {value} ({value/len(donations):.2%} of donations)")

    return questions_analysis

def analyze_metadata(donations):

    # avg and mean count of domains and topFrameUniqueRedirects
    domains_count_per_donation = [len(d.get("domains", [])) for d in donations]
    top_frame_redirects_count_per_donation = [len(d.get("topFrameUniqueRedirects", [])) for d in donations]

    domains_avg = np.average(domains_count_per_donation) if domains_count_per_donation else 0
    top_frame_redirects_avg = np.average(top_frame_redirects_count_per_donation) if top_frame_redirects_count_per_donation else 0
    domains_median = np.median(domains_count_per_donation) if domains_count_per_donation else 0
    top_frame_redirects_median = np.median(top_frame_redirects_count_per_donation) if top_frame_redirects_count_per_donation else 0

    domains_min = min(domains_count_per_donation) if domains_count_per_donation else 0
    domains_max = max(domains_count_per_donation) if domains_count_per_donation else 0
    top_frame_redirects_min = min(top_frame_redirects_count_per_donation) if top_frame_redirects_count_per_donation else 0
    top_frame_redirects_max = max(top_frame_redirects_count_per_donation) if top_frame_redirects_count_per_donation else 0

    # metadata object: operationDays
    operation_days_per_donation = [d.get("metadata", {}).get("operationDays", 0) for d in donations]
    operation_days_avg = sum(operation_days_per_donation) / len(operation_days_per_donation) if operation_days_per_donation else 0
    operation_days_median = np.median(operation_days_per_donation) if operation_days_per_donation else 0
    operation_days_min = min(operation_days_per_donation) if operation_days_per_donation else 0
    operation_days_max = max(operation_days_per_donation) if operation_days_per_donation else 0

    return {
        "domains_avg": domains_avg,
        "domains_median": domains_median,
        "domains_min": domains_min,
        "domains_max": domains_max,
        "domains_counts": domains_count_per_donation,

        "top_frame_redirects_avg": top_frame_redirects_avg,
        "top_frame_redirects_median": top_frame_redirects_median,
        "top_frame_redirects_min": top_frame_redirects_min,
        "top_frame_redirects_max": top_frame_redirects_max,
        "top_frame_redirects_counts": top_frame_redirects_count_per_donation,

        "operation_days_avg": operation_days_avg,
        "operation_days_median": operation_days_median,
        "operation_days_min": operation_days_min,
        "operation_days_max": operation_days_max,
        "operation_days_counts": operation_days_per_donation
    }

def analyze_filtering(donations):

    data = []
    for donation in donations:

        domain_count_before = donation.get("metadata", {}).get("observedDomainCountBeforeFiltering", 0)
        domain_count_after = len(donation.get("domains", []))

        prevalent_count_before = donation.get("metadata", {}).get("prevalentDomainCountBeforeFiltering", 0)
        prevalent_count_after = sum(1 for d in donation.get("domains", []).items() if d[1].get("isPrevalent", True))

        very_prevalent_count_before = donation.get("metadata", {}).get("veryPrevalentDomainCountBeforeFiltering", 0)
        very_prevalent_count_after = sum(1 for d in donation.get("domains", []).items() if d[1].get("isVeryPrevalent", True))

        user_interaction_count_before = donation.get("metadata", {}).get("userInteractionDomainCountBeforeFiltering", 0)
        user_interaction_count_after = sum(1 for d in donation.get("domains", []).items() if d[1].get("hadUserInteraction", True))

        domain_count_convergence_before = domain_count_before >= 800
        domain_count_low_before = domain_count_before < 100

        domain_count_convergence_after = domain_count_after >= 800

        data.append({
            "domain_count_before": domain_count_before,
            "domain_count_after": domain_count_after,

            "prevalent_count_before": prevalent_count_before,
            "prevalent_count_after": prevalent_count_after,

            "very_prevalent_count_before": very_prevalent_count_before,
            "very_prevalent_count_after": very_prevalent_count_after,

            "user_interaction_count_before": user_interaction_count_before,
            "user_interaction_count_after": user_interaction_count_after,

            "domain_count_convergence_before": domain_count_convergence_before,
            "domain_count_low_before": domain_count_low_before,

            "domain_count_convergence_after": domain_count_convergence_after,
        })

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman"],
        "font.size": 24,
        "axes.labelsize": 24,
        "xtick.labelsize": 24,
        "ytick.labelsize": 24,
        "legend.fontsize": 24,
        "legend.title_fontsize": 24
    })

    metrics = [
        ("domain_count", "Observations"),
        ("prevalent_count", "Prevalent Domains"),
        ("user_interaction_count", "User Interactions")
    ]

    df = pd.DataFrame(data)

    plot_data = []
    for metric_name, metric_label in metrics:
        
        before_col = f"{metric_name}_before"
        before_df = df[[before_col]].copy()
        before_df.columns = ["Count"]
        before_df["Attribute"] = metric_label
        before_df["Condition"] = "Pre-Filtering"
        
        after_col = f"{metric_name}_after"
        after_df = df[[after_col]].copy()
        after_df.columns = ["Count"]
        after_df["Attribute"] = metric_label
        after_df["Condition"] = "Post-Filtering"
        
        plot_data.extend([before_df, after_df])

    # Combine everything into a single DataFrame
    plot_df = pd.concat(plot_data, ignore_index=True)

    # Generate the grouped boxplot
    plt.figure(figsize=(10, 6))
    sns.boxplot(
        data=plot_df, 
        x="Attribute", 
        y="Count", 
        hue="Condition",
        palette="Set2"
    )

    plt.legend(title=None)

    plt.xlabel("Category")
    plt.ylabel("Count")
    plt.tight_layout()

    plt.savefig("filtering_barplot_comparison.pdf", format='pdf', dpi=300)
    plt.close()

    # median before and after for each metric
    for metric_name, metric_label in metrics:
        before_median = df[f"{metric_name}_before"].median()
        after_median = df[f"{metric_name}_after"].median()
        logger.info(f"{metric_label} - Median Before: {int(before_median)}, Median After: {int(after_median)} ({(after_median - before_median) / before_median * 100:.2f}% change)")

    # data domain_count_convergence_before
    logger.info(f"Domain Count Convergence Before: {df['domain_count_convergence_before'].sum()} donations ({df['domain_count_convergence_before'].mean() * 100:.2f}%)")

    return data

def analyze_prevalent_domains(donations):
    total_donations = len(donations)
    prevalent_domains = Counter()
    very_prevalent_domains = Counter()
    
    for donation in donations:
        for domain, info in donation.get("domains", {}).items():
            if info.get("isPrevalent", False):
                prevalent_domains[domain] += 1
            if info.get("isVeryPrevalent", False):
                very_prevalent_domains[domain] += 1
    
    # count number of keys in prevalent_domains
    count_prevalent_domains = len(prevalent_domains)
    logger.info(f"Total prevalent domains across donations: {count_prevalent_domains}")

    # Sort first by count descending (-item[1]), then by domain alphabetically (item[0])
    sorted_prevalent = sorted(prevalent_domains.items(), key=lambda item: (-item[1], item[0]))

    logger.info("Most common prevalent domains across donations:")
    for domain, count in sorted_prevalent[:15]:
        pct = count / total_donations if total_donations > 0 else 0
        logger.info(f"  {domain}: {count} ({pct:.2%} of donations)")

    plot_prevalent_domains(prevalent_domains, total_donations)

    # log domains that are classified in exactly 1 donation as prevalent
    single_donation_prevalent_domains = [domain for domain, count in prevalent_domains.items() if count == 1]
    logger.info(f"Prevalent domains that are prevalent in exactly 1 donation: {len(single_donation_prevalent_domains)} ({len(single_donation_prevalent_domains)/count_prevalent_domains:.2%} of prevalent domains)")

    # set of all classified domains -> write to classified_domains.txt
    classified_domains = set(prevalent_domains.keys()) | set(very_prevalent_domains.keys())
    with open("classified_domains.txt", "w") as f:
        for domain in sorted(classified_domains):
            f.write(f"{domain}\n")

def analyze_bounce_hubs(donations):
    hub_counter = Counter()

    for donation in donations:
        redirects = donation.get("topFrameUniqueRedirects", {})
        
        # Track hubs per donation to avoid overcounting a single aggressive session
        donation_hubs = set() 
        
        for from_domain, redirect_list in redirects.items():
            for redirect in redirect_list:
                since_same_site_strict_enforcement = redirect.get("sinceSameSiteStrictEnforcement", False)

                if since_same_site_strict_enforcement:
                    donation_hubs.add(from_domain)
        
        # Add the unique hubs from this donation to our global counter
        for hub in donation_hubs:
            hub_counter[hub] += 1

    total_donations = len(donations)
    
    # Original logging
    logger.info("Top Bounce Hubs across all donations:")
    for hub, count in hub_counter.most_common(15):
        pct_val = count / total_donations if total_donations > 0 else 0
        logger.info(f"  {hub}: {count} donations ({pct_val:.2%} of donations)")

    with open("bounce_hubs.txt", "w") as f:
        for hub, count in hub_counter.most_common():
            f.write(f"{hub},{count}\n")
        
    return hub_counter.most_common()

def analyze_bouncing_domains(donations):

    for donation in donations:
        redirects = donation.get("topFrameUniqueRedirects", {})
        logger.info(f"Donation with {len(redirects)} top frame unique origin domains:")

        donation_bounces = list()
        
        for from_domain, redirect_list in redirects.items():
                
            for redirect in redirect_list:
                to_domain = redirect.get("toDomain", "unknown")
                since_same_site_strict_enforcement = redirect.get("sinceSameSiteStrictEnforcement", False)
                has_link_decorations = redirect.get("hasLinkDecorations", False)

                logger.info(f"  {from_domain} -> {to_domain}, sinceSameSiteStrictEnforcement: {since_same_site_strict_enforcement}, hasLinkDecorations: {has_link_decorations}")

                if since_same_site_strict_enforcement:
                    # this is an item to identify bouncing domains
                    donation_bounces.append([from_domain, to_domain])
        
        logger.info(f"  Total bouncing domains in this donation: {len(donation_bounces)}")


def main():
    
    donations = [(file, read_json_file(file)) for file in list_all_json_files(INPUT_DIR)]
    logger.info(f"Loaded {len(donations)} donation records.")

    # Find donations with less than 100 domains
    low_domain_donations = [d for d in donations if d[1].get("metadata", {}).get("observedDomainCountBeforeFiltering", 0) < 100]
    logger.info(f"Donations with less than 100 domains before filtering: {len(low_domain_donations)}")
    for file, donation in low_domain_donations:
        domain_count_before = donation.get("metadata", {}).get("observedDomainCountBeforeFiltering", 0)
        logger.info(f"  {file}: {domain_count_before} domains before filtering")

    # filter out corrupted donations
    donations = [d for d in donations if not d[0] in CURRUPTED_DONATIONS]

    # just get donation from donations with >= 100 domains before filtering
    donations = [d[1] for d in donations if d[1].get("metadata", {}).get("observedDomainCountBeforeFiltering", 0) >= 100] # TODO: change 100 to 0 for Demographics section, leave at 100 for rest of analysis
    logger.info(f"Filtered donations to those with >= 100 domains before filtering: {len(donations)}")

    # Questions analysis
    analyze_questions(donations)
    
    # Filtering analysis
    analyze_filtering(donations)

    # Prevalent domains analysis
    analyze_prevalent_domains(donations)
    
    # analyze_bouncing_domains(donations)
    analyze_bounce_hubs(donations)



if __name__ == "__main__":
    main()