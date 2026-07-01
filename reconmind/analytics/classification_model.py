"""
reconmind/analytics/classification_model.py
===========================================
Milestone 13 — Multiclass attack-type classifier.

Trains Dummy / Logistic Regression / Random Forest / XGBoost pipelines
to predict one of four injection types from run-level behavioural features.

Design decisions
────────────────
• Reuses the exact same 20 features produced by features.py (M12).
  This lets us directly compare which features matter for *detection*
  (binary) versus *classification* (4-class) — a research finding in
  its own right.
• Trains on ALL attack runs regardless of outcome (ignored / partial /
  full_success).  The model's job is to identify attack *type* from
  behavioural signals, not to predict success.
• Includes a Dummy baseline so we can quantify the lift from real
  features over a trivial majority-class predictor.
• Permutation importance is computed per-class for tree models, giving
  "what behavioural signal most distinguishes memory_poisoning from
  direct_injection" — genuinely useful for defensive routing.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")                       # headless — no display needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    make_scorer,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from xgboost import XGBClassifier


# ──────────────────────────────────────────────────────────────────────
# Data contract
# ──────────────────────────────────────────────────────────────────────
# Columns that must NEVER appear in X — they leak the answer.
_LEAKAGE_COLUMNS = frozenset([
    "injection_present_this_event",
    "injection_outcome",
    "expected_signal",
    "detecting_defense",
])

# Dev-era naming variants → canonical 4-class labels.
_TYPE_CANONICAL = {
    "direct_prompt_injection":   "direct_injection",
    "indirect_prompt_injection": "indirect_injection",
    "direct_injection":          "direct_injection",
    "indirect_injection":        "indirect_injection",
    "memory_poisoning":          "memory_poisoning",
    "tool_misuse":               "tool_misuse",
}

# Minimum examples per class before we refuse to train.
_MIN_CLASS_COUNT = 5


# ──────────────────────────────────────────────────────────────────────
# Return type
# ──────────────────────────────────────────────────────────────────────
@dataclass
class ClassificationReport:
    """Holds every artefact produced by evaluate_classification()."""
    metrics:              Dict[str, Dict[str, Any]]
    confusion_matrices:   Dict[str, np.ndarray]
    feature_importances:  pd.DataFrame
    class_names:          List[str]
    label_encoder:        LabelEncoder = field(repr=False, default=None)


# ──────────────────────────────────────────────────────────────────────
# 1. Data preparation
# ──────────────────────────────────────────────────────────────────────
def prepare_classification_data(
    features_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray, List[str], LabelEncoder]:
    """
    Filter to attack runs, canonicalise labels, encode, stratified split.

    Returns
    -------
    X_train, X_test, y_train, y_test, class_names, label_encoder
    """
    # ── leakage gate ──
    leaked = _LEAKAGE_COLUMNS & set(features_df.columns)
    if leaked:
        raise ValueError(f"Leakage columns present in feature set: {leaked}")

    if "injection_type" not in features_df.columns:
        raise ValueError("injection_type column not found in features DataFrame")

    df = features_df.copy()

    # Canonicalise labels
    df["injection_type"] = df["injection_type"].map(_TYPE_CANONICAL)

    # Keep attack runs only (clean runs map to NaN → dropped)
    df = df.dropna(subset=["injection_type"]).copy()

    # Assert minimum per-class count
    class_counts = df["injection_type"].value_counts()
    too_few = class_counts[class_counts < _MIN_CLASS_COUNT]
    if not too_few.empty:
        raise ValueError(
            f"Classes with fewer than {_MIN_CLASS_COUNT} examples — "
            f"need more campaign runs:\n{too_few}"
        )

    # ── separate X / y ──
    y_raw = df["injection_type"]
    drop_cols = ["run_id", "injection_type", "attack_success_binary"]
    X = df.drop(columns=[c for c in drop_cols if c in df.columns])

    le = LabelEncoder()
    y = le.fit_transform(y_raw)
    class_names = list(le.classes_)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42,
    )

    return X_train, X_test, y_train, y_test, class_names, le


# ──────────────────────────────────────────────────────────────────────
# 2. Model training
# ──────────────────────────────────────────────────────────────────────
def train_classification_models(
    X_train: pd.DataFrame, y_train: np.ndarray,
) -> Dict[str, Pipeline]:
    """Train four pipelines and return them keyed by human-readable name."""

    models: Dict[str, Pipeline] = {}

    # 0. Dummy — majority-class baseline
    models["Dummy Baseline"] = Pipeline([
        ("classifier", DummyClassifier(strategy="most_frequent", random_state=42)),
    ])

    # 1. Logistic Regression (scaled)
    models["Logistic Regression"] = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=42,
        )),
    ])

    # 2. Random Forest
    models["Random Forest"] = Pipeline([
        ("classifier", RandomForestClassifier(
            n_estimators=100,
            class_weight="balanced",
            random_state=42,
        )),
    ])

    # 3. XGBoost (GPU-accelerated on RTX 4060)
    models["XGBoost"] = Pipeline([
        ("classifier", XGBClassifier(
            n_estimators=100,
            random_state=42,
            eval_metric="mlogloss",
            objective="multi:softprob",
            device="cuda",
        )),
    ])

    for name, pipe in models.items():
        pipe.fit(X_train, y_train)

    return models


# ──────────────────────────────────────────────────────────────────────
# 3. Evaluation
# ──────────────────────────────────────────────────────────────────────
def _class_f1_scorer(class_idx: int):
    """Build a scorer that measures binary F1 for one class vs rest."""
    def _score(y_true, y_pred):
        return f1_score(
            (y_true == class_idx).astype(int),
            (y_pred == class_idx).astype(int),
            zero_division=0,
        )
    return make_scorer(_score)


def evaluate_classification(
    models: Dict[str, Pipeline],
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    class_names: List[str],
    label_encoder: LabelEncoder | None = None,
) -> ClassificationReport:
    """
    Compute per-model macro metrics, per-class breakdowns, confusion
    matrices, and permutation importance for tree-based models.
    """
    metrics: Dict[str, Dict[str, Any]] = {}
    cms: Dict[str, np.ndarray] = {}
    importances_df = pd.DataFrame(index=X_test.columns)

    for name, pipeline in models.items():
        preds = pipeline.predict(X_test)

        # ── aggregate metrics ──
        macro_f1  = f1_score(y_test, preds, average="macro", zero_division=0)
        macro_p   = precision_score(y_test, preds, average="macro", zero_division=0)
        macro_r   = recall_score(y_test, preds, average="macro", zero_division=0)
        acc       = accuracy_score(y_test, preds)

        report_dict = classification_report(
            y_test, preds,
            target_names=class_names,
            output_dict=True,
            zero_division=0,
        )

        metrics[name] = {
            "accuracy":        acc,
            "macro_precision": macro_p,
            "macro_recall":    macro_r,
            "macro_f1":        macro_f1,
            "per_class": {c: report_dict[c] for c in class_names},
        }

        # ── confusion matrix ──
        cms[name] = confusion_matrix(y_test, preds)

        # ── permutation importance (tree models only, skip Dummy) ──
        if name in ("Random Forest", "XGBoost"):
            for idx, cname in enumerate(class_names):
                result = permutation_importance(
                    pipeline, X_test, y_test,
                    scoring=_class_f1_scorer(idx),
                    n_repeats=10,
                    random_state=42,
                )
                importances_df[f"{name} | {cname}"] = result.importances_mean

    return ClassificationReport(
        metrics=metrics,
        confusion_matrices=cms,
        feature_importances=importances_df,
        class_names=class_names,
        label_encoder=label_encoder,
    )


# ──────────────────────────────────────────────────────────────────────
# 4. Reporting — console + figures
# ──────────────────────────────────────────────────────────────────────
def render_classification_report(report: ClassificationReport, output_dir: Path) -> None:
    """Print structured results and save publication-quality figures."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── console output ──
    print("\n" + "=" * 64)
    print("  MULTICLASS ATTACK-TYPE CLASSIFICATION — EVALUATION REPORT")
    print("=" * 64)

    dummy_f1 = report.metrics.get("Dummy Baseline", {}).get("macro_f1", 0.0)

    for name, m in report.metrics.items():
        delta = m["macro_f1"] - dummy_f1
        delta_str = f"  (Δ = +{delta:.4f} vs dummy)" if name != "Dummy Baseline" else ""
        print(f"\n┌─ {name}{delta_str}")
        print(f"│  Accuracy:        {m['accuracy']:.4f}")
        print(f"│  Macro Precision: {m['macro_precision']:.4f}")
        print(f"│  Macro Recall:    {m['macro_recall']:.4f}")
        print(f"│  Macro F1:        {m['macro_f1']:.4f}")
        print("│  Per-class:")
        for cname, cm in m["per_class"].items():
            print(f"│    {cname:25s}  P={cm['precision']:.3f}  R={cm['recall']:.3f}  F1={cm['f1-score']:.3f}")
        print("└" + "─" * 63)

    # ── Figure 1: confusion matrices (skip Dummy — it's all one column) ──
    real_models = {k: v for k, v in report.confusion_matrices.items() if k != "Dummy Baseline"}
    n = len(real_models)
    fig, axes = plt.subplots(1, n, figsize=(5.5 * n, 5))
    if n == 1:
        axes = [axes]

    for ax, (model_name, cm) in zip(axes, real_models.items()):
        sns.heatmap(
            cm, annot=True, fmt="d", cmap="Oranges",
            xticklabels=report.class_names,
            yticklabels=report.class_names,
            ax=ax, cbar=False,
            linewidths=0.5, linecolor="white",
        )
        mf1 = report.metrics[model_name]["macro_f1"]
        ax.set_title(f"{model_name}\n(Macro F1 = {mf1:.3f})", fontsize=11)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        ax.set_xticklabels(report.class_names, rotation=35, ha="right", fontsize=8)
        ax.set_yticklabels(report.class_names, rotation=0, fontsize=8)

    fig.suptitle("Confusion Matrices — Attack Type Classification", fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(output_dir / "confusion_matrices.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # ── Figure 2: global feature importance (averaged across tree models) ──
    imp = report.feature_importances
    if not imp.empty:
        global_mean = imp.mean(axis=1).sort_values()
        top = global_mean.tail(12)

        fig, ax = plt.subplots(figsize=(8, 6))
        top.plot(kind="barh", color="#e67e22", ax=ax)
        ax.set_title("Global Permutation Feature Importance\n(averaged across RF + XGBoost, all classes)")
        ax.set_xlabel("Mean F1-score decrease when feature is shuffled")
        fig.tight_layout()
        fig.savefig(output_dir / "global_feature_importance.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

    # ── Figure 3 & 4: per-class importance for each tree model ──
    for model_tag in ("Random Forest", "XGBoost"):
        cols = [c for c in imp.columns if c.startswith(model_tag)]
        if len(cols) != len(report.class_names):
            continue

        fig, axes = plt.subplots(2, 2, figsize=(13, 10))
        for ax, col in zip(axes.flat, cols):
            class_label = col.split(" | ", 1)[1]   # "Random Forest | direct_injection" → "direct_injection"
            top_feats = imp[col].sort_values().tail(8)
            colours = ["#c0392b" if v > 0 else "#95a5a6" for v in top_feats]
            top_feats.plot(kind="barh", color=colours, ax=ax)
            ax.set_title(class_label.replace("_", " ").title(), fontsize=10)
            ax.set_xlabel("ΔF1 on shuffle")
            ax.axvline(0, color="black", linewidth=0.5)

        fig.suptitle(
            f"{model_tag} — Per-Class Permutation Importance",
            fontsize=13, y=1.01,
        )
        fig.tight_layout()
        tag = model_tag.lower().replace(" ", "_")
        fig.savefig(
            output_dir / f"{tag}_per_class_importance.png",
            dpi=300, bbox_inches="tight",
        )
        plt.close(fig)

    print(f"\nFigures saved to {output_dir}/")
