#!/usr/bin/env python3
"""Score the locked two-model comparison and predictive-uncertainty extension."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import pickle
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "protocols/IMA_UPGRADE_v2.0_multimodel_uncertainty_lock_20260929.json"
CLARIFICATION = ROOT / "protocols/IMA_UPGRADE_v2.0_implementation_clarification_E1_20260929.md"
SYNTHSTROKE_STORAGE_LOCK = ROOT / "protocols/IMA_UPGRADE_v2.0_SynthStroke_formal_storage_lock_E3_20260929.json"
FEASIBILITY_AMENDMENT = ROOT / "protocols/IMA_UPGRADE_v2.0_comparator_feasibility_amendment_E4_20260929.json"
MAPPING = ROOT / "data/authorized/atlas_r3/formal_v1.2/inference/restricted_token_mapping.csv"
DEFAULT_METRICS = ROOT / "data/authorized/atlas_r3/formal_v1.2/metrics/NEUROLRES_ATLAS_SHIFT_v1.2_formal_case_metrics.csv"
SCORER = ROOT / "models/vendor/isles26/utils/eval_utils.py"
RESULT_ROOT = ROOT / "results/ima_upgrade_20260929"
RESTRICTED_ROOT = ROOT / "data/authorized/atlas_r3/formal_v1.2/upgrade_v2"
PACKAGE_ROOT = ROOT / "投稿版_IMA_升级版_20260929"
SUPPLEMENT_ROOT = PACKAGE_ROOT / "04_补充材料"
FIGURE_ROOT = PACKAGE_ROOT / "02_图"
CASE_ROOT = RESTRICTED_ROOT / "case_json"

EXPECTED_PROTOCOL_SHA256 = "4a6a1421310231ac21ae251a8aff7c1e22ef8bbedbb01a7d3e43c1dfafaf3b21"
EXPECTED_MAPPING_SHA256 = "3d50730735050aacb65e88634b4ca83ae2ecf43f23790f750d60e847d01d1b1d"
EXPECTED_DEFAULT_METRICS_SHA256 = "717a853f203b24adab92935cb046c8778cee994db17ca355ede21caab4c44f90"
EXPECTED_N = 762
REPETITIONS = 10_000
SEED = 260929
STRATA = ("R2_TEST", "SOOP", "R3_NEW")
MODEL_ORDER = ("default", "synthstroke")
MODEL_LABEL = {
    "default": "Default nnU-Net",
    "dtk10": "DiceTopK10 nnU-Net",
    "resunet": "Residual nnU-Net",
    "synthstroke": "SynthStroke (2025)",
}
_SCORER_MODULE = None
PREDICTION_DIRS = {
    "default": ROOT / "data/authorized/atlas_r3/formal_v1.2/inference/nnunet_output_folds0_4_no_tta",
    "dtk10": ROOT / "data/authorized/atlas_r3/formal_v1.2/comparators/dtk10/full_output_folds0_4_no_tta",
    "resunet": ROOT / "data/authorized/atlas_r3/formal_v1.2/comparators/resunet/full_output_folds0_4_no_tta",
    "synthstroke": ROOT / "data/authorized/atlas_r3/formal_v1.2/comparators/synthstroke/full_output_no_tta",
}
METRICS = (
    "dice",
    "lesion_f1",
    "pr_auc",
    "abs_volume_difference_ml",
    "abs_lesion_count_difference",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_scorer():
    global _SCORER_MODULE
    if _SCORER_MODULE is not None:
        return _SCORER_MODULE
    spec = importlib.util.spec_from_file_location("ima_upgrade_eval_utils", SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to import official scorer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _SCORER_MODULE = module
    return _SCORER_MODULE


def reconstruct_probability(npz_path: Path, pkl_path: Path) -> np.ndarray:
    with np.load(npz_path) as archive:
        if "foreground" in archive.files:
            foreground = np.asarray(archive["foreground"], dtype=np.float32)
            softmax = None
        elif "softmax" in archive.files:
            softmax = np.asarray(archive["softmax"])
            if softmax.ndim != 4 or softmax.shape[0] != 2:
                raise ValueError("invalid softmax")
            foreground = np.asarray(softmax[1], dtype=np.float32)
        else:
            raise ValueError("NPZ lacks foreground or softmax probability")
    if foreground.ndim != 3 or not np.isfinite(foreground).all():
        raise ValueError("invalid foreground probability")
    with pkl_path.open("rb") as handle:
        properties = pickle.load(handle)
    original_shape = tuple(int(value) for value in properties["original_size_of_raw_data"])
    bbox = properties.get("crop_bbox")
    if bbox is None:
        if foreground.shape != original_shape:
            raise ValueError("softmax/original shape mismatch")
        return foreground
    output = np.zeros(original_shape, dtype=np.float32)
    slices = tuple(slice(int(bounds[0]), int(bounds[1])) for bounds in bbox)
    if foreground.shape != tuple(index.stop - index.start for index in slices):
        raise ValueError("softmax/crop shape mismatch")
    output[slices] = foreground
    return output


def probability_qc(probability: np.ndarray) -> None:
    if not np.isfinite(probability).all():
        raise ValueError("nonfinite probability")
    if float(np.min(probability)) < -1e-4 or float(np.max(probability)) > 1.0001:
        raise ValueError("probability outside [0,1]")


def reliability_components(probability: np.ndarray, truth: np.ndarray) -> tuple[list[int], list[float], list[int]]:
    indices = np.minimum((probability * 10).astype(np.int16), 9)
    counts = np.bincount(indices, minlength=10)
    sum_probability = np.bincount(indices, weights=probability, minlength=10)
    sum_truth = np.bincount(indices, weights=truth.astype(np.float32), minlength=10)
    return counts.astype(int).tolist(), sum_probability.astype(float).tolist(), sum_truth.astype(int).tolist()


def score_case(task: tuple[str, dict[str, str], dict[str, str] | None]) -> dict[str, Any]:
    model, row, baseline = task
    token = row["token"]
    prediction_dir = PREDICTION_DIRS[model]
    nii_path = prediction_dir / f"{token}.nii.gz"
    npz_path = prediction_dir / f"{token}.npz"
    pkl_path = prediction_dir / f"{token}.pkl"
    for path in (nii_path, npz_path, pkl_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"missing model output: {path}")

    gt_img = nib.load(row["mask_path"])
    t1_img = nib.load(row["t1_path"])
    pred_img = nib.load(str(nii_path))
    if gt_img.shape != pred_img.shape or gt_img.shape != t1_img.shape:
        raise ValueError("array shape mismatch")
    gt_xyz = np.asanyarray(gt_img.dataobj)
    pred_xyz = np.asanyarray(pred_img.dataobj)
    t1_xyz = np.asanyarray(t1_img.dataobj)
    if not np.isfinite(gt_xyz).all() or not np.isfinite(pred_xyz).all():
        raise ValueError("nonfinite segmentation array")
    gt_zyx = np.transpose(gt_xyz > 0.5, (2, 1, 0))
    pred_zyx = np.transpose(pred_xyz > 0.5, (2, 1, 0))
    brain_zyx = np.transpose(np.isfinite(t1_xyz) & (t1_xyz != 0), (2, 1, 0))
    probability = reconstruct_probability(npz_path, pkl_path)
    probability_qc(probability)
    if probability.shape != gt_zyx.shape or not np.any(brain_zyx):
        raise ValueError("probability/brain shape mismatch or empty brain mask")

    if model == "default":
        if baseline is None:
            raise ValueError("missing frozen default metrics")
        metrics = {key: float(baseline[key]) for key in METRICS}
    else:
        scorer = load_scorer()
        lesion_f1, count_difference, dice = scorer.compute_dice_f1_instance_difference(gt_zyx, pred_zyx)
        pr_auc = scorer.compute_pr_auc(gt_zyx, probability)
        voxel_volume_ml = np.asarray(np.prod(gt_img.header.get_zooms()[:3]) / 1000.0)
        volume_difference = scorer.compute_absolute_volume_difference(gt_zyx, pred_zyx, voxel_volume_ml)
        metrics = {
            "dice": float(dice),
            "lesion_f1": float(lesion_f1),
            "pr_auc": float(pr_auc),
            "abs_volume_difference_ml": float(volume_difference),
            "abs_lesion_count_difference": float(count_difference),
        }

    p = probability[brain_zyx].astype(np.float64)
    y = gt_zyx[brain_zyx]
    squared_error = np.square(p - y.astype(np.float64))
    lesion_error = squared_error[y]
    background_error = squared_error[~y]
    if lesion_error.size:
        balanced_brier = 0.5 * float(np.mean(lesion_error)) + 0.5 * float(np.mean(background_error))
        balanced_rule = "equal lesion/background weight"
    else:
        balanced_brier = float(np.mean(background_error))
        balanced_rule = "background-only because ground truth was empty"
    candidate = p >= 0.01
    if np.any(candidate):
        clipped = np.clip(p[candidate], 1e-7, 1 - 1e-7)
        uncertainty = float(np.mean(-(clipped * np.log(clipped) + (1 - clipped) * np.log(1 - clipped))))
    else:
        uncertainty = 0.0
    counts, sum_probability, sum_truth = reliability_components(p, y)

    return {
        "model": model,
        "model_label": MODEL_LABEL[model],
        "token": token,
        "case_id": row["case_id"],
        "stratum": row["stratum"],
        "center": row["center"],
        **metrics,
        "empty_prediction": bool(not np.any(pred_zyx)),
        "gt_empty": bool(not np.any(gt_zyx)),
        "mean_foreground_probability": float(np.mean(p)),
        "brain_brier": float(np.mean(squared_error)),
        "balanced_brier": balanced_brier,
        "balanced_brier_rule": balanced_rule,
        "case_uncertainty": uncertainty,
        "uncertainty_voxel_n": int(np.sum(candidate)),
        "brain_voxel_n": int(p.size),
        "reliability_count": counts,
        "reliability_sum_probability": sum_probability,
        "reliability_sum_truth": sum_truth,
        "prediction_sha256": {
            "nii_gz": sha256(nii_path),
            "npz": sha256(npz_path),
            "pkl": sha256(pkl_path),
        },
    }


def validate_inputs(models: tuple[str, ...]) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    if sha256(PROTOCOL) != EXPECTED_PROTOCOL_SHA256:
        raise SystemExit("upgrade protocol drift")
    if not CLARIFICATION.is_file():
        raise SystemExit("missing implementation clarification")
    if not SYNTHSTROKE_STORAGE_LOCK.is_file():
        raise SystemExit("missing SynthStroke storage lock")
    amendment = json.loads(FEASIBILITY_AMENDMENT.read_text(encoding="utf-8"))
    if amendment.get("active_models") != list(MODEL_ORDER):
        raise SystemExit("active-model amendment drift")
    if amendment.get("scorer_sha256") != sha256(Path(__file__).resolve()):
        raise SystemExit("multimodel scorer drift")
    if sha256(MAPPING) != EXPECTED_MAPPING_SHA256:
        raise SystemExit("formal mapping drift")
    if sha256(DEFAULT_METRICS) != EXPECTED_DEFAULT_METRICS_SHA256:
        raise SystemExit("default metrics drift")
    mapping = read_csv(MAPPING)
    baseline_rows = read_csv(DEFAULT_METRICS)
    if len(mapping) != EXPECTED_N or len(baseline_rows) != EXPECTED_N:
        raise SystemExit("fixed denominator mismatch")
    baseline = {row["token"]: row for row in baseline_rows}
    if set(baseline) != {row["token"] for row in mapping}:
        raise SystemExit("default metric/mapping token mismatch")
    for model in models:
        directory = PREDICTION_DIRS[model]
        counts = {
            suffix: len(list(directory.glob(f"v12f*.{suffix}")))
            for suffix in ("nii.gz", "npz", "pkl")
        }
        if counts != {"nii.gz": EXPECTED_N, "npz": EXPECTED_N, "pkl": EXPECTED_N}:
            raise SystemExit(f"incomplete {model} output: {counts}")
    return mapping, baseline


def distribution(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(array)),
        "sd": float(np.std(array, ddof=1)),
        "median": float(np.median(array)),
        "q1": float(np.quantile(array, 0.25)),
        "q3": float(np.quantile(array, 0.75)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }


def center_values(rows: list[dict[str, Any]], metric: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row["center"])].append(float(row[metric]))
    return {center: float(np.mean(values)) for center, values in grouped.items()}


def center_bootstrap_ci(values: dict[str, float], seed: int) -> tuple[float, float]:
    keys = np.asarray(sorted(values), dtype=object)
    observed = np.asarray([values[str(key)] for key in keys], dtype=float)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(keys), size=(REPETITIONS, len(keys)))
    means = np.mean(observed[indices], axis=1)
    return tuple(float(x) for x in np.quantile(means, [0.025, 0.975]))


def paired_center_bootstrap(a: list[dict[str, Any]], b: list[dict[str, Any]], metric: str, seed: int) -> dict[str, float | int]:
    by_token_a = {str(row["token"]): row for row in a}
    by_token_b = {str(row["token"]): row for row in b}
    if set(by_token_a) != set(by_token_b):
        raise ValueError("paired token mismatch")
    grouped: dict[str, list[float]] = defaultdict(list)
    for token in sorted(by_token_a):
        center = str(by_token_a[token]["center"])
        if center != str(by_token_b[token]["center"]):
            raise ValueError("paired center mismatch")
        grouped[center].append(float(by_token_a[token][metric]) - float(by_token_b[token][metric]))
    diffs = np.asarray([np.mean(grouped[key]) for key in sorted(grouped)], dtype=float)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(diffs), size=(REPETITIONS, len(diffs)))
    draws = np.mean(diffs[indices], axis=1)
    lower, upper = np.quantile(draws, [0.025, 0.975])
    lower_tail = (1 + int(np.sum(draws <= 0))) / (REPETITIONS + 1)
    upper_tail = (1 + int(np.sum(draws >= 0))) / (REPETITIONS + 1)
    return {
        "estimate": float(np.mean(diffs)),
        "ci_lower": float(lower),
        "ci_upper": float(upper),
        "p_raw": float(min(1.0, 2 * min(lower_tail, upper_tail))),
        "center_n": int(len(diffs)),
    }


def source_gap_bootstrap(rows: list[dict[str, Any]], metric: str, seed: int) -> dict[str, float | int]:
    r2 = center_values([row for row in rows if row["stratum"] == "R2_TEST"], metric)
    r3 = center_values([row for row in rows if row["stratum"] == "R3_NEW"], metric)
    union = np.asarray(sorted(set(r2) | set(r3)), dtype=object)
    rng = np.random.default_rng(seed)
    draws: list[float] = []
    while len(draws) < REPETITIONS:
        sampled = rng.choice(union, size=len(union), replace=True)
        left = [r2[str(key)] for key in sampled if str(key) in r2]
        right = [r3[str(key)] for key in sampled if str(key) in r3]
        if left and right:
            draws.append(float(np.mean(left) - np.mean(right)))
    estimate = float(np.mean(list(r2.values())) - np.mean(list(r3.values())))
    lower, upper = np.quantile(np.asarray(draws), [0.025, 0.975])
    return {"estimate": estimate, "ci_lower": float(lower), "ci_upper": float(upper), "center_union_n": len(union)}


def holm_adjust(records: list[dict[str, Any]]) -> None:
    order = sorted(range(len(records)), key=lambda index: float(records[index]["p_raw"]))
    running = 0.0
    total = len(records)
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (total - rank) * float(records[index]["p_raw"])))
        records[index]["p_holm"] = running


def spearman_summary(rows: list[dict[str, Any]], seed: int) -> dict[str, float | int]:
    uncertainty = np.asarray([float(row["case_uncertainty"]) for row in rows])
    error = np.asarray([1.0 - float(row["dice"]) for row in rows])
    rho = float(spearmanr(uncertainty, error).statistic)
    rng = np.random.default_rng(seed)
    draws = np.empty(REPETITIONS, dtype=float)
    for index in range(REPETITIONS):
        sampled = rng.integers(0, len(rows), size=len(rows))
        draws[index] = spearmanr(uncertainty[sampled], error[sampled]).statistic
    finite = draws[np.isfinite(draws)]
    lower, upper = np.quantile(finite, [0.025, 0.975])
    return {"n": len(rows), "rho": rho, "ci_lower": float(lower), "ci_upper": float(upper), "valid_bootstrap_n": len(finite)}


def aggregate() -> dict[str, Any]:
    case_rows: list[dict[str, Any]] = []
    for model in MODEL_ORDER:
        paths = sorted((CASE_ROOT / model).glob("v12f*.json"))
        if len(paths) != EXPECTED_N:
            raise SystemExit(f"incomplete case JSON for {model}: {len(paths)}")
        case_rows.extend(json.loads(path.read_text(encoding="utf-8")) for path in paths)

    summary_rows: list[dict[str, Any]] = []
    center_source_rows: list[dict[str, Any]] = []
    for model_index, model in enumerate(MODEL_ORDER):
        model_rows = [row for row in case_rows if row["model"] == model]
        for stratum_index, stratum in enumerate(STRATA):
            rows = [row for row in model_rows if row["stratum"] == stratum]
            centers = center_values(rows, "lesion_f1")
            lower, upper = center_bootstrap_ci(centers, SEED + 100 * model_index + stratum_index)
            entry: dict[str, Any] = {
                "model": model,
                "model_label": MODEL_LABEL[model],
                "stratum": stratum,
                "n": len(rows),
                "center_n": len(centers),
                "center_macro_lesion_f1": float(np.mean(list(centers.values()))),
                "center_macro_ci_lower": lower,
                "center_macro_ci_upper": upper,
                "empty_prediction_rate": float(np.mean([row["empty_prediction"] for row in rows])),
                "brain_brier_mean": float(np.mean([row["brain_brier"] for row in rows])),
                "balanced_brier_mean": float(np.mean([row["balanced_brier"] for row in rows])),
            }
            for metric in METRICS:
                stats = distribution([float(row[metric]) for row in rows])
                for key, value in stats.items():
                    entry[f"{metric}_{key}"] = value
            summary_rows.append(entry)
            for center, value in sorted(centers.items()):
                center_source_rows.append({"model": MODEL_LABEL[model], "stratum": stratum, "center": center, "lesion_f1": value})

    comparisons: list[dict[str, Any]] = []
    for comparator_index, comparator in enumerate(("synthstroke",)):
        for stratum_index, stratum in enumerate(("R3_NEW", "R2_TEST")):
            a = [row for row in case_rows if row["model"] == comparator and row["stratum"] == stratum]
            b = [row for row in case_rows if row["model"] == "default" and row["stratum"] == stratum]
            result = paired_center_bootstrap(a, b, "lesion_f1", SEED + 1000 * comparator_index + stratum_index)
            analysis_role = "exploratory contemporary comparator"
            result["p_raw"] = ""
            comparisons.append({"comparator": comparator, "comparator_label": MODEL_LABEL[comparator], "reference": "default", "stratum": stratum, "analysis_role": analysis_role, **result})
    for row in comparisons:
        row["p_holm"] = ""

    gaps = []
    for model_index, model in enumerate(MODEL_ORDER):
        rows = [row for row in case_rows if row["model"] == model]
        gaps.append({"model": model, "model_label": MODEL_LABEL[model], **source_gap_bootstrap(rows, "lesion_f1", SEED + model_index)})

    reliability_rows: list[dict[str, Any]] = []
    risk_rows: list[dict[str, Any]] = []
    correlation_rows: list[dict[str, Any]] = []
    scatter_rows: list[dict[str, Any]] = []
    coverages = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5)
    for model_index, model in enumerate(MODEL_ORDER):
        for group_index, stratum in enumerate((*STRATA, "ALL")):
            rows = [row for row in case_rows if row["model"] == model and (stratum == "ALL" or row["stratum"] == stratum)]
            correlation_rows.append({"model": model, "model_label": MODEL_LABEL[model], "stratum": stratum, **spearman_summary(rows, SEED + 100 * model_index + group_index)})
            ordered = sorted(rows, key=lambda row: (float(row["case_uncertainty"]), str(row["token"])))
            for coverage in coverages:
                retained_n = max(1, int(math.ceil(coverage * len(ordered))))
                retained = ordered[:retained_n]
                risk_rows.append({
                    "model": model,
                    "model_label": MODEL_LABEL[model],
                    "stratum": stratum,
                    "coverage": coverage,
                    "retained_n": retained_n,
                    "mean_dice": float(np.mean([row["dice"] for row in retained])),
                    "mean_error": float(np.mean([1.0 - row["dice"] for row in retained])),
                })
        for stratum in STRATA:
            rows = [row for row in case_rows if row["model"] == model and row["stratum"] == stratum]
            for bin_index in range(10):
                count = int(sum(row["reliability_count"][bin_index] for row in rows))
                sum_probability = float(sum(row["reliability_sum_probability"][bin_index] for row in rows))
                sum_truth = int(sum(row["reliability_sum_truth"][bin_index] for row in rows))
                reliability_rows.append({
                    "model": model,
                    "model_label": MODEL_LABEL[model],
                    "stratum": stratum,
                    "bin": bin_index + 1,
                    "bin_lower": bin_index / 10,
                    "bin_upper": (bin_index + 1) / 10,
                    "voxel_n": count,
                    "mean_predicted_probability": sum_probability / count if count else "",
                    "observed_frequency": sum_truth / count if count else "",
                })
        public_index = 0
        for row in sorted([item for item in case_rows if item["model"] == model], key=lambda item: (item["stratum"], item["token"])):
            public_index += 1
            scatter_rows.append({
                "model": MODEL_LABEL[model],
                "stratum": row["stratum"],
                "display_index": public_index,
                "case_uncertainty": row["case_uncertainty"],
                "one_minus_dice": 1.0 - row["dice"],
            })

    restricted_csv = RESTRICTED_ROOT / "IMA_UPGRADE_v2_multimodel_case_metrics_uncertainty.csv"
    flattened = []
    for row in case_rows:
        flattened.append({key: json.dumps(value) if isinstance(value, (list, dict)) else value for key, value in row.items()})
    write_csv(restricted_csv, flattened)
    write_csv(RESULT_ROOT / "multimodel_stratum_summary.csv", summary_rows)
    write_csv(RESULT_ROOT / "multimodel_pairwise_comparisons.csv", comparisons)
    write_csv(RESULT_ROOT / "multimodel_source_gaps.csv", gaps)
    write_csv(RESULT_ROOT / "multimodel_reliability.csv", reliability_rows)
    write_csv(RESULT_ROOT / "multimodel_risk_coverage.csv", risk_rows)
    write_csv(RESULT_ROOT / "multimodel_uncertainty_correlations.csv", correlation_rows)
    write_csv(FIGURE_ROOT / "Figure_5_source_data.csv", center_source_rows)
    write_csv(FIGURE_ROOT / "Figure_5_summary_source_data.csv", [
        {
            "model": row["model_label"], "stratum": row["stratum"],
            "n": row["n"], "center_n": row["center_n"],
            "center_macro_lesion_f1": row["center_macro_lesion_f1"],
            "ci_lower": row["center_macro_ci_lower"], "ci_upper": row["center_macro_ci_upper"],
        }
        for row in summary_rows
    ])
    write_csv(FIGURE_ROOT / "Figure_5_pairwise_source_data.csv", comparisons)
    write_csv(FIGURE_ROOT / "Figure_5_gap_source_data.csv", gaps)
    write_csv(FIGURE_ROOT / "Figure_6_reliability_source_data.csv", reliability_rows)
    write_csv(FIGURE_ROOT / "Figure_6_risk_coverage_source_data.csv", risk_rows)
    write_csv(FIGURE_ROOT / "Figure_6_uncertainty_error_source_data.csv", scatter_rows)
    write_csv(SUPPLEMENT_ROOT / "Table_S6_multimodel_pairwise_comparisons.csv", comparisons)
    supplement_uncertainty_rows = [
        {
            "analysis": "uncertainty-error association",
            "model": row["model"], "model_label": row["model_label"], "stratum": row["stratum"],
            "n": row["n"], "rho": row["rho"], "ci_lower": row["ci_lower"],
            "ci_upper": row["ci_upper"], "coverage": "", "retained_n": "",
            "mean_dice": "", "mean_error": "",
        }
        for row in correlation_rows
    ] + [
        {
            "analysis": "risk coverage",
            "model": row["model"], "model_label": row["model_label"], "stratum": row["stratum"],
            "n": "", "rho": "", "ci_lower": "", "ci_upper": "",
            "coverage": row["coverage"], "retained_n": row["retained_n"],
            "mean_dice": row["mean_dice"], "mean_error": row["mean_error"],
        }
        for row in risk_rows
    ]
    write_csv(SUPPLEMENT_ROOT / "Table_S7_uncertainty_calibration_and_risk_coverage.csv", supplement_uncertainty_rows)
    payload = {
        "status": "PASS",
        "created_at_utc": utc_now(),
        "protocol_sha256": sha256(PROTOCOL),
        "clarification_sha256": sha256(CLARIFICATION),
        "fixed_n_per_model": EXPECTED_N,
        "model_order": list(MODEL_ORDER),
        "stratum_summary": summary_rows,
        "pairwise_comparisons": comparisons,
        "source_gaps": gaps,
        "uncertainty_correlations": correlation_rows,
        "output_sha256": {
            "restricted_case_metrics": sha256(restricted_csv),
            "summary": sha256(RESULT_ROOT / "multimodel_stratum_summary.csv"),
            "comparisons": sha256(RESULT_ROOT / "multimodel_pairwise_comparisons.csv"),
        },
    }
    write_json(RESULT_ROOT / "multimodel_uncertainty_results.json", payload)
    return payload


def run(workers: int, selected_models: tuple[str, ...]) -> int:
    mapping, baseline = validate_inputs(selected_models)
    CASE_ROOT.mkdir(parents=True, exist_ok=True)
    pending: list[tuple[str, dict[str, str], dict[str, str] | None]] = []
    for model in selected_models:
        (CASE_ROOT / model).mkdir(parents=True, exist_ok=True)
        for row in mapping:
            output = CASE_ROOT / model / f"{row['token']}.json"
            if output.is_file() and output.stat().st_size > 0:
                continue
            pending.append((model, row, baseline[row["token"]] if model == "default" else None))
    print(json.dumps({"pending": len(pending), "workers": workers, "started_at_utc": utc_now()}), flush=True)
    completed = 0
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(score_case, task): task for task in pending}
        for future in as_completed(futures):
            model, row, _ = futures[future]
            result = future.result()
            write_json(CASE_ROOT / model / f"{row['token']}.json", result)
            completed += 1
            if completed % 25 == 0 or completed == len(pending):
                print(json.dumps({"newly_completed": completed, "remaining": len(pending) - completed, "model": model, "token": row["token"]}), flush=True)
    complete_models = {
        model: len(list((CASE_ROOT / model).glob("v12f*.json"))) == EXPECTED_N
        for model in MODEL_ORDER
    }
    if all(complete_models.values()):
        payload = aggregate()
        print(json.dumps({"status": payload["status"], "results": str(RESULT_ROOT / "multimodel_uncertainty_results.json")}, indent=2))
    else:
        print(json.dumps({"status": "PARTIAL_SCORING_PASS", "complete_case_json": complete_models}, indent=2))
    return 0


def self_test() -> int:
    probability = np.asarray([0.0, 0.2, 0.5, 1.0], dtype=float)
    truth = np.asarray([False, False, True, True])
    counts, sum_probability, sum_truth = reliability_components(probability, truth)
    test_rows_a = [
        {"token": f"a{i}", "center": center, "lesion_f1": value}
        for i, (center, value) in enumerate((("A", 0.8), ("A", 0.6), ("B", 0.4)))
    ]
    test_rows_b = [
        {"token": f"a{i}", "center": center, "lesion_f1": value}
        for i, (center, value) in enumerate((("A", 0.7), ("A", 0.5), ("B", 0.2)))
    ]
    boot_a = paired_center_bootstrap(test_rows_a, test_rows_b, "lesion_f1", SEED)
    boot_b = paired_center_bootstrap(test_rows_a, test_rows_b, "lesion_f1", SEED)
    passed = bool(
        sum(counts) == 4
        and np.isclose(sum(sum_probability), 1.7)
        and sum(sum_truth) == 2
        and boot_a == boot_b
        and np.isclose(float(boot_a["estimate"]), 0.15)
    )
    payload = {"status": "PASS" if passed else "FAIL", "reliability_count": counts, "paired_bootstrap": boot_a}
    write_json(RESULT_ROOT / "multimodel_scoring_self_test.json", payload)
    print(json.dumps(payload, indent=2))
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("self-test", "run", "aggregate"), required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--models", nargs="+", choices=MODEL_ORDER, default=list(MODEL_ORDER))
    args = parser.parse_args()
    if args.mode == "self-test":
        return self_test()
    if args.mode == "aggregate":
        aggregate()
        return 0
    if args.workers < 1 or args.workers > 2:
        raise SystemExit("workers must be 1 or 2 on this host")
    return run(args.workers, tuple(dict.fromkeys(args.models)))


if __name__ == "__main__":
    raise SystemExit(main())
