import math
from typing import Dict, List, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from config import PALETTE, TEXTS


def _style_axes(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(PALETTE["border"])
    ax.tick_params(colors=PALETTE["text"], labelsize=8)
    ax.xaxis.label.set_color(PALETTE["text"])
    ax.yaxis.label.set_color(PALETTE["text"])


def _figure(width: float = 4.2, height: float = 3.0):
    fig, ax = plt.subplots(figsize=(width, height))
    fig.patch.set_facecolor("white")
    _style_axes(ax)
    return fig, ax


def confusion_heatmap(
    counts: Dict[str, int],
    title: str,
    actual_labels: Sequence[str],
    predicted_labels: Sequence[str],
):
    matrix = np.array([[counts["TP"], counts["FN"]], [counts["FP"], counts["TN"]]], dtype=float)
    cmap = LinearSegmentedColormap.from_list("calm", ["#ffffff", PALETTE["accent"]])
    fig, ax = plt.subplots(figsize=(3.4, 3.0))
    fig.patch.set_facecolor("white")
    ax.imshow(matrix, cmap=cmap, vmin=0, vmax=max(matrix.max(), 1.0))
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(predicted_labels, fontsize=8, color=PALETTE["text"])
    ax.set_yticklabels(actual_labels, fontsize=8, color=PALETTE["text"])
    ax.set_xlabel(TEXTS["label_predicted"], fontsize=8, color=PALETTE["text"])
    ax.set_ylabel(TEXTS["label_actual"], fontsize=8, color=PALETTE["text"])
    ax.set_title(title, fontsize=9, color=PALETTE["text"])
    names = [["TP", "FN"], ["FP", "TN"]]
    for i in range(2):
        for j in range(2):
            value = matrix[i, j]
            shade = "white" if value > matrix.max() * 0.6 else PALETTE["text"]
            ax.text(j, i, "%s\n%d" % (names[i][j], value), ha="center", va="center", fontsize=9, color=shade)
    for side in ax.spines.values():
        side.set_color(PALETTE["border"])
    ax.tick_params(length=0)
    fig.tight_layout()
    return fig


def ring_chart(passed: int, total: int, title: str):
    fig, ax = plt.subplots(figsize=(3.0, 3.0))
    fig.patch.set_facecolor("white")
    failed = max(total - passed, 0)
    values = [passed, failed] if total else [1, 0]
    ax.pie(
        values,
        colors=[PALETTE["pass"], PALETTE["fail"]],
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.28, "edgecolor": "white"},
    )
    ax.text(0, 0, "%d/%d" % (passed, total), ha="center", va="center", fontsize=14, color=PALETTE["text"])
    ax.set_title(title, fontsize=9, color=PALETTE["text"])
    fig.tight_layout()
    return fig


def convergence_plot(curves: Dict[str, List[float]]):
    fig, ax = _figure(5.0, 3.0)
    for index, (name, values) in enumerate(curves.items()):
        if not values:
            continue
        color = PALETTE["series"][index % len(PALETTE["series"])]
        ax.plot(range(len(values)), values, color=color, linewidth=1.4, label=name)
    ax.set_xlabel(TEXTS["axis_step"], fontsize=8)
    ax.set_ylabel(TEXTS["axis_penalty"], fontsize=8)
    if len(curves) > 1:
        ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def radar_chart(values: Dict[str, float], title: str):
    labels = list(values)
    data = [min(max(float(v), 0.0), 1.0) for v in values.values()]
    n = len(labels)
    angles = [2 * math.pi * i / n for i in range(n)]
    data_closed = data + data[:1]
    angles_closed = angles + angles[:1]
    fig = plt.figure(figsize=(3.8, 3.4))
    fig.patch.set_facecolor("white")
    ax = fig.add_subplot(111, polar=True)
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=7, color=PALETTE["text"])
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["", "0.5", "", "1.0"], fontsize=7, color=PALETTE["neutral"])
    ax.grid(color=PALETTE["border"])
    ax.spines["polar"].set_color(PALETTE["border"])
    ax.plot(angles_closed, data_closed, color=PALETTE["primary"], linewidth=1.4)
    ax.fill(angles_closed, data_closed, color=PALETTE["accent"], alpha=0.25)
    ax.set_title(title, fontsize=9, color=PALETTE["text"], pad=14)
    fig.tight_layout()
    return fig


def grouped_bars(data: Dict[str, Dict[str, float]], title: str, log_scale: bool = True):
    groups = list(data)
    series = list(next(iter(data.values()))) if data else []
    width = 0.8 / max(len(series), 1)
    fig, ax = _figure(5.4, 3.2)
    positions = np.arange(len(groups))
    for index, name in enumerate(series):
        heights = [data[g][name] for g in groups]
        ax.bar(
            positions + index * width,
            heights,
            width,
            label=name,
            color=PALETTE["series"][index % len(PALETTE["series"])],
        )
    ax.set_xticks(positions + width * (len(series) - 1) / 2)
    ax.set_xticklabels(groups, fontsize=8)
    ax.set_ylabel(TEXTS["axis_ms"], fontsize=8)
    if log_scale:
        ax.set_yscale("log")
    ax.set_title(title, fontsize=9, color=PALETTE["text"])
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def rate_with_interval(rows: List[dict], title: str):
    fig, ax = _figure(5.4, 3.2)
    positions = np.arange(len(rows))
    rates = [r["rate"] for r in rows]
    lower = [max(r["rate"] - r["low"], 0.0) for r in rows]
    upper = [max(r["high"] - r["rate"], 0.0) for r in rows]
    ax.bar(positions, rates, color=PALETTE["accent"], width=0.5)
    ax.errorbar(positions, rates, yerr=[lower, upper], fmt="none", ecolor=PALETTE["primary"], capsize=3, linewidth=1)
    ax.set_xticks(positions)
    ax.set_xticklabels([r["name"] for r in rows], fontsize=7, rotation=15, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel(TEXTS["axis_rate"], fontsize=8)
    ax.set_title(title, fontsize=9, color=PALETTE["text"])
    fig.tight_layout()
    return fig


def show(fig) -> None:
    import streamlit as st

    st.pyplot(fig, clear_figure=True)
    plt.close(fig)