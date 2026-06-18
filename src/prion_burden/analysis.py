"""Phase 1 downstream analysis: morphotypes, spatial spread, group stats.

Faithful ports of the morphotype-typing, Ripley's-L and group-comparison cells
of ``01_phase1_burden_morphometry``, plus the DAB-threshold calibration sweep.
All functions are pure (no plotting); :mod:`prion_burden.plots` renders them.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config
from .discovery import parse_metadata
from .segment import dab_channel, load_and_standardize, tissue_mask

# Shape features used for morphotype clustering.
MORPHO_FEATURES = [
    "area_um2", "circularity", "solidity", "aspect_ratio", "eccentricity", "extent",
]
MORPHO_NAMES = ["compact", "intermediate", "diffuse"]


# --- morphotypes -----------------------------------------------------------
@dataclass
class MorphotypeResult:
    objects: pd.DataFrame          # objs_df with a 'morphotype' column merged in
    pca_coords: np.ndarray         # 2-D PCA embedding of the clustered objects
    clustered: pd.DataFrame        # rows that were clustered (subset, with labels)
    names: dict[int, str]          # cluster id -> morphotype name


def assign_morphotypes(objs_df: pd.DataFrame, cfg: Config) -> MorphotypeResult | None:
    """Cluster objects by shape into compact/intermediate/diffuse.

    Returns ``None`` if there are no objects with complete shape features.
    Clusters are named by ascending median ``area_um2`` so the labels are stable.
    """
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    if not len(objs_df):
        return None
    md = objs_df.dropna(subset=MORPHO_FEATURES).copy()
    # Need at least n_morphotypes *distinct* shapes to form that many clusters;
    # otherwise KMeans/PCA emit alarming-but-harmless warnings on degenerate input.
    if md[MORPHO_FEATURES].drop_duplicates().shape[0] < cfg.n_morphotypes:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # PCA divide / KMeans convergence chatter
        X = StandardScaler().fit_transform(md[MORPHO_FEATURES].values)
        Z = PCA(n_components=2).fit_transform(X)
        md["cluster"] = KMeans(
            n_clusters=cfg.n_morphotypes, n_init=10, random_state=cfg.random_state
        ).fit_predict(X)
    order = md.groupby("cluster")["area_um2"].median().sort_values().index
    names = {
        lab: nm for lab, nm in zip(order, MORPHO_NAMES[: cfg.n_morphotypes])
    }
    md["morphotype"] = md["cluster"].map(names)
    merged = objs_df.drop(columns=["morphotype"], errors="ignore").merge(
        md[["image", "label", "morphotype"]], on=["image", "label"], how="left"
    )
    return MorphotypeResult(merged, Z, md, names)


def morphotype_composition(objs_df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Counts of each morphotype per (species, condition, region)."""
    if "morphotype" not in objs_df.columns:
        return pd.DataFrame()
    return (
        objs_df.dropna(subset=["morphotype"])
        .pivot_table(
            index=["species", "condition", "region"],
            columns="morphotype",
            values="label",
            aggfunc="count",
            fill_value=0,
        )
    )


# --- spatial spread (Ripley's L) ------------------------------------------
def ripley_L(
    xy: np.ndarray,
    width: float,
    height: float,
    radii: np.ndarray,
    n_sim: int = 99,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Ripley's ``L(r) - r`` for point pattern ``xy`` vs a CSR envelope.

    Returns ``(L_observed, env_low, env_high)`` or ``None`` if too few points.
    Self-contained, no edge correction - use R ``spatstat`` (``Kinhom``/``pcf``)
    for publication-grade inhomogeneous spatial statistics.
    """
    from scipy.spatial import cKDTree

    rng = np.random.default_rng(seed)
    n = len(xy)
    area = width * height
    if n < 5 or area <= 0:
        return None
    lam = n / area

    def L_of(pts: np.ndarray) -> np.ndarray:
        tree = cKDTree(pts)
        K = np.array(
            [2 * len(tree.query_pairs(r, output_type="ndarray")) / (lam * n) for r in radii]
        )
        return np.sqrt(K / np.pi) - radii

    L_obs = L_of(xy)
    sims = np.array(
        [
            L_of(np.column_stack([rng.uniform(0, width, n), rng.uniform(0, height, n)]))
            for _ in range(n_sim)
        ]
    )
    lo, hi = np.percentile(sims, [2.5, 97.5], axis=0)
    return L_obs, lo, hi


def spread_for_image(
    path: Path,
    cfg: Config,
    scale: dict[str, float],
    n_sim: int = 99,
) -> dict | None:
    """Compute Ripley's L for the deposits in a single image."""
    from skimage import measure

    from .segment import segment_dab

    img, upp = load_and_standardize(path, cfg, scale)
    labels, *_ = segment_dab(img, upp, cfg)
    if labels.max() == 0:
        return None
    u = upp if not np.isnan(upp) else 1.0
    props = measure.regionprops_table(labels, properties=["centroid"])
    xy = np.column_stack([props["centroid-1"], props["centroid-0"]]) * u
    height, width = labels.shape[0] * u, labels.shape[1] * u
    radii = np.linspace(5, min(height, width) / 4, 25)
    res = ripley_L(xy, width, height, radii, n_sim=n_sim, seed=cfg.random_state)
    if res is None:
        return None
    L, lo, hi = res
    return dict(image=path.name, radii=radii, L=L, lo=lo, hi=hi, n=len(xy))


# --- group comparison ------------------------------------------------------
def group_comparison(img_df: pd.DataFrame, cfg: Config) -> dict:
    """Compare PrP burden across groups.

    With ≥3 known animals, fits a mixed-effects model (animal = random effect) -
    the publication-valid analysis. Otherwise falls back to an image-level
    Kruskal-Wallis test per region, which is EXPLORATORY and pseudoreplicated.
    Returns a dict describing which path was taken and the result/text.
    """
    import warnings

    from scipy import stats

    known = img_df[img_df["animal"] != "UNKNOWN"]
    mixedlm_error = None
    if known["animal"].nunique() >= 3:
        import statsmodels.formula.api as smf

        agg = (
            known.groupby(["animal", "species", "condition", "region"], as_index=False)
            .agg(burden=("pct_area_burden", "mean"))
        )
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # convergence chatter
                model = smf.mixedlm(
                    "burden ~ C(condition) * C(species) + C(region)",
                    agg,
                    groups=agg["animal"],
                )
                fit = model.fit()
            return dict(method="mixedlm", n_animals=int(known["animal"].nunique()),
                        summary=str(fit.summary()))
        except Exception as exc:  # e.g. rank-deficient/confounded design
            # The fixed-effects design can be collinear (species confounded with
            # condition); don't crash - fall back to the exploratory test below.
            mixedlm_error = f"{type(exc).__name__}: {exc}"

    img_df = img_df.copy()
    img_df["group"] = img_df["species"] + "_" + img_df["condition"]
    regs = [r for r in cfg.regions if r in img_df["region"].unique()]
    per_region = {}
    for reg in regs:
        g = img_df[img_df["region"] == reg]
        order = sorted(g["group"].unique())
        data = [g[g["group"] == grp]["pct_area_burden"].dropna().values for grp in order]
        big = [d for d in data if len(d) > 1]
        if len(big) >= 2:
            H, p = stats.kruskal(*big)
            per_region[reg] = dict(H=float(H), p=float(p), groups=order)
    note = ("Image-level comparison - exploratory only (the animal, not the "
            "image, is the true experimental unit; treating images as "
            "independent is pseudoreplication).")
    return dict(method="kruskal", note=note, mixedlm_error=mixedlm_error,
                per_region=per_region)


# --- DAB-threshold calibration sweep --------------------------------------
def threshold_sweep(
    image_paths: list[Path],
    cfg: Config,
    scale: dict[str, float],
    animal_lookup: dict[str, str],
    thresholds: np.ndarray | None = None,
    k: int = 5,
) -> pd.DataFrame:
    """Sweep the DAB cutoff on sampled WT-control vs treatment images.

    Returns a ``threshold × group`` table of mean burden %. Pick the lowest
    threshold where WT control drops to its background floor while treatment
    stays well above it.
    """
    if thresholds is None:
        thresholds = np.round(np.arange(0.02, 0.161, 0.01), 3)

    def sample(pred):
        g = [p for p in image_paths if pred(parse_metadata(p, cfg, animal_lookup))]
        return g[:: max(1, len(g) // k)][:k] if g else []

    groups = {
        "wt_control": sample(lambda m: m["condition"] == "control"),
        "deer_tx": sample(lambda m: m["species"] == "deer" and m["condition"] == "treatment"),
        "elk_tx": sample(lambda m: m["species"] == "elk" and m["condition"] == "treatment"),
    }
    rows = []
    for label, paths in groups.items():
        for p in paths:
            img, upp = load_and_standardize(p, cfg, scale)
            dab = dab_channel(img)
            tis = tissue_mask(img)
            denom = max(tis.sum(), 1)
            for thr in thresholds:
                rows.append(
                    dict(group=label, image=p.name, thr=float(thr),
                         burden=100 * (((dab > thr) & tis).sum() / denom))
                )
    cal = pd.DataFrame(rows)
    if cal.empty:
        return cal
    return cal.groupby(["thr", "group"])["burden"].mean().unstack("group")
