import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import ScalarFormatter

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.WARNING)
logger = logging.getLogger("Plot")
logger.setLevel(logging.INFO)

START_WINDOW = pd.Timestamp("2025-10-20")
END_WINDOW = pd.Timestamp("2026-08-13")

OUTPUT_PATH = Path("results/cumulative_change_comparison.pdf")

PLOT_RC_PARAMS = {
    "font.family": "serif",
    "font.serif": ["Liberation Serif"],
    "font.size": 14,
    "axes.labelsize": 14,
    "xtick.labelsize": 30,
    "ytick.labelsize": 30,
    "legend.fontsize": 30,
    "pdf.fonttype": 42,
}
AXIS_FONT_SIZE = 30


def _count_domain_changes(commit: dict) -> int:
    return len(commit.get("domains_added", [])) + len(commit.get("domains_removed", []))

def _count_easyprivacy_changes(commit: dict) -> int:
    return sum(
        len(change.get("additions", [])) + len(change.get("removals", []))
        for change in commit.get("file_changes", [])
    )

def _count_webprivacy_changes(change: dict) -> int:
    if change["list_name"] == "RESOURCE_MONITOR_URLS":
        return 1
    return len(change["added"]) + len(change["removed"])


@dataclass
class ListSource:
    name: str
    filename: str
    color: str
    linewidth: float
    count_fn: Callable[[dict], int]

SOURCES: list[ListSource] = [
    ListSource("EasyPrivacy", "results/easyprivacy_changes.json", "#0072B2", 2, _count_easyprivacy_changes),
    ListSource("Disconnect", "results/disconnect_domain_changes.json", "#E69F00", 2, _count_domain_changes),
    ListSource("DuckDuckGo", "results/duckduckgo_domain_changes.json", "#009E73", 2, _count_domain_changes),
    ListSource("WebPrivacy (Apple)", "results/webprivacy_changes.json", "#D55E00", 3, _count_webprivacy_changes),
]

def load_cumulative_changes(source: ListSource) -> pd.DataFrame:
    path = Path(source.filename)
    if not path.exists():
        logger.warning("%s: file not found (%s), skipping", source.name, path)
        return pd.DataFrame(columns=["date", "changes", "cumulative_changes"])

    with path.open("r") as f:
        raw = json.load(f)

    records = [
        {"date": pd.to_datetime(entry["date"]).tz_localize(None), "changes": source.count_fn(entry)}
        for entry in raw
    ]
    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    df["cumulative_changes"] = df["changes"].cumsum()
    logger.info("%s: %d total changes", source.name, df["changes"].sum())
    return df

def clip_to_window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Restrict a cumulative-changes DataFrame to [start, end], carrying forward
    the cumulative total from before `start` and holding it flat through `end`
    so the step plot renders correctly at both edges."""
    if df.empty:
        return pd.DataFrame(
            [{"date": start, "changes": 0, "cumulative_changes": 0},
             {"date": end, "changes": 0, "cumulative_changes": 0}]
        )

    carried_in_value = df.loc[df["date"] < start, "cumulative_changes"].iloc[-1] if (df["date"] < start).any() else 0

    window = df[(df["date"] >= start) & (df["date"] <= end)].copy()

    lead_in = pd.DataFrame([{"date": start, "changes": 0, "cumulative_changes": carried_in_value}])
    window = pd.concat([lead_in, window], ignore_index=True)

    if window["date"].iloc[-1] < end:
        trailing_value = window["cumulative_changes"].iloc[-1]
        trail_out = pd.DataFrame([{"date": end, "changes": 0, "cumulative_changes": trailing_value}])
        window = pd.concat([window, trail_out], ignore_index=True)

    return window

def plot_sources(sources: list[ListSource], output_path: Path) -> None:
    plt.rcParams.update(PLOT_RC_PARAMS)
    plt.figure(figsize=(12, 6))

    for source in sources:
        df = load_cumulative_changes(source)
        df = clip_to_window(df, START_WINDOW, END_WINDOW)
        plt.step(
            df["date"], df["cumulative_changes"],
            label=source.name, color=source.color, linewidth=source.linewidth, where="post",
        )

    ax = plt.gca()
    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(formatter)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))

    plt.ylabel("Cumulative Changes", fontsize=AXIS_FONT_SIZE)
    plt.xlabel("Date", fontsize=AXIS_FONT_SIZE)
    plt.grid(True, which="both", linestyle=":", alpha=0.6)
    plt.legend(loc="upper left")
    plt.xlim(START_WINDOW, END_WINDOW)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    logger.info("Plot saved to %s", output_path.name)

if __name__ == "__main__":
    plot_sources(SOURCES, OUTPUT_PATH)