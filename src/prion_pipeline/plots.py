"""Optional figures for Phase 1 (headless / non-interactive).

Saves PNGs rather than showing windows, so the CLI works over SSH and in CI.
Each function mirrors a plotting cell from ``01_phase1_burden_morphometry`` and
returns the path it wrote.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: never tries to open a window
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .analysis import MorphotypeResult  # noqa: E402
from .config import Config  # noqa: E402


def _save(fig, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def burden_by_region(img_df: pd.DataFrame, cfg: Config, out_path: Path) -> Path:
    """Jittered strip plot of PrP burden by region, dodged by group."""
    df = img_df.copy()
    df["group"] = df["species"] + "_" + df["condition"]
    regs = [r for r in cfg.regions if r in df["region"].unique()]
    grps = sorted(df["group"].unique())
    offsets = np.linspace(-0.28, 0.28, len(grps)) if len(grps) > 1 else np.array([0.0])
    rng = np.random.default_rng(cfg.random_state)

    fig, ax = plt.subplots(figsize=(10, 5))
    for gi, grp in enumerate(grps):
        for ri, reg in enumerate(regs):
            y = df[(df["group"] == grp) & (df["region"] == reg)]["pct_area_burden"].dropna().values
            x = ri + offsets[gi] + rng.uniform(-0.05, 0.05, size=len(y))
            ax.scatter(x, y, s=14, alpha=0.45, color=f"C{gi}", label=grp if ri == 0 else None)
        means = [
            df[(df["group"] == grp) & (df["region"] == r)]["pct_area_burden"].mean()
            for r in regs
        ]
        ax.scatter(np.arange(len(regs)) + offsets[gi], means, marker="_", s=420,
                   color=f"C{gi}", linewidths=2.5)
    ax.set_xticks(range(len(regs)))
    ax.set_xticklabels(regs)
    ax.set_xlabel("region")
    ax.set_ylabel("PrP-positive area (%)")
    ax.set_title("CWD PrP burden by region / group (jittered; long bars = group mean)")
    ax.legend(title="group")
    return _save(fig, out_path)


def morphotype_pca(result: MorphotypeResult, out_path: Path) -> Path:
    """PCA scatter of morphotype clusters + area-by-morphotype boxplot."""
    md, Z = result.clustered, result.pca_coords
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    for nm in result.names.values():
        m = md["morphotype"].values == nm
        ax[0].scatter(Z[m, 0], Z[m, 1], s=6, alpha=0.4, label=nm)
    ax[0].set_xlabel("PC1")
    ax[0].set_ylabel("PC2")
    ax[0].legend()
    ax[0].set_title("morphotype clusters (PCA)")
    md.boxplot(column="area_um2", by="morphotype", ax=ax[1])
    ax[1].set_yscale("log")
    ax[1].set_title("area by morphotype")
    fig.suptitle("")
    return _save(fig, out_path)


def threshold_sweep(pivot: pd.DataFrame, cfg: Config, out_path: Path) -> Path:
    """Mean burden vs DAB threshold for control/treatment groups (log y)."""
    fig, ax = plt.subplots(figsize=(8, 5))
    for grp in pivot.columns:
        ax.plot(pivot.index, pivot[grp], marker="o", label=grp)
    if cfg.dab_threshold is not None:
        ax.axvline(cfg.dab_threshold, color="k", ls="--",
                   label=f"current = {cfg.dab_threshold}")
    ax.set_xlabel("DAB threshold (optical density)")
    ax.set_ylabel("mean burden % (sampled images)")
    ax.set_yscale("log")
    ax.legend()
    ax.set_title("WT control -> background floor; treatment stays above")
    return _save(fig, out_path)


def ripley(spread: dict, out_path: Path) -> Path:
    """Ripley's L(r)-r with the CSR envelope for one image."""
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.fill_between(spread["radii"], spread["lo"], spread["hi"],
                    color="gray", alpha=0.3, label="CSR 95% envelope")
    ax.plot(spread["radii"], spread["L"], "b-", label="observed")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("r (um)")
    ax.set_ylabel("L(r) - r")
    ax.legend()
    ax.set_title(f"Ripley L — {spread['image']} (n={spread['n']}); above envelope = clustering")
    return _save(fig, out_path)
