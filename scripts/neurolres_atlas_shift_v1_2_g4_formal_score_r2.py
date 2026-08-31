#!/usr/bin/env python3
"""Resume frozen NEUROLRES-ATLAS-SHIFT v1.2 formal G4 scoring after E2.

The self-test and preflight modes do not open patient images or model outputs.
The run mode is the single authorized effect-unblinding step.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import pickle
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np


PROTOCOL_ID = "NEUROLRES-ATLAS-SHIFT-v1.2"
EXPECTED_N = 762
STRATA = ("R2_TEST", "SOOP", "R3_NEW")
EXPECTED_DENOMINATORS = {"R2_TEST": 288, "SOOP": 157, "R3_NEW": 317}
EXPECTED_CENTERS = {"R2_TEST": 24, "SOOP": 1, "R3_NEW": 26}
EXPECTED_PRIMARY_CENTER_UNION = 46
EXPECTED_PRIMARY_CENTER_INTERSECTION = 4
PRIMARY_THRESHOLD = 0.05
BOOTSTRAP_REPETITIONS = 10_000
BOOTSTRAP_SEED = 260827
VOXEL_SIZE_ABS_TOL = 1e-6
GT_STORAGE_ABS_TOL = 1e-6
TOKEN_PATTERN = re.compile(r"^v12f\d{4}$")
METRICS = (
    "dice",
    "lesion_f1",
    "pr_auc",
    "abs_volume_difference_ml",
    "abs_lesion_count_difference",
)
EXPECTED_SHA256 = {
    "protocol": "66af57ab785bca729d6549184b661118d7961a8c3d9692caf1b11469fa377749",
    "dataset_contract": "fe83bd8443db12e4bbaf7dec0311ae8731ebae0a8cb9e692cc8d298959cbdb14",
    "freeze_manifest": "010803fc76767eeedb157dbc7ae8df016ee0dcd2bb482c20aaf3917cd406019e",
    "formal_execution_lock": "c8973d822a5b7bec01166f08f40dfa470463834b2c2969e6cf8ade73f7222b69",
    "restricted_token_mapping": "3d50730735050aacb65e88634b4ca83ae2ecf43f23790f750d60e847d01d1b1d",
    "g3_lock": "ec73f849b4251f3d09ac24aeb49d542f5e1ba2b914c130db3b29bfa67dba407c",
    "g3_summary": "639dfd9281f710eb65fc77b5101d26708e245f1a5bc201d4211d04490b4dd019",
    "g3_restricted_details": "6662a4e9abf6f75575328faff9b66c719cc6c4391c66630e82046fdfda5a8421",
    "official_scorer": "73668f48b70a56fe1ce785701595627ac3a6086412fb0f85b211ff7dc09ffcfd",
    "prior_identity_summary": "38702146136cd50c7767b5ad5beda4baad1f690120593e80d660d78d8fa290df",
    "scoring_environment": "3d37fdf3c51d1e55626f050cd476ecfca02f0ecdf4b16150646f88497364eb7c",
    "pilot36_manifest": "74841b0a3041df76fc8b8cae75dcdd0d2ee38d9aafe0aebeeba86f6121199828",
    "release_index": "2fe4bc3cd7e8eb91630c3900887488072c8f345f91780db57678be294903c85c",
}
EXPECTED_G3_TRIPLET_MANIFEST_SHA256 = (
    "b35b5ea9fea7ba08a2db8260e855f72ab032f2dd9df8d43aaffd5b988433c6dd"
)
RESUME1_COMPLETED_CASE_FILES = 240
RESUME1_CASE_FILE_MANIFEST_SHA256 = (
    "97afa5eaf0d3afb4e28f75b731216bf946a92366414864261993a60fdfe6ea5b"
)
RESUME2_PRIOR_SHA256 = {
    "formal_g4_scorer_r1": "1104a18b5495c15d249029c60e926e2cf67ead6d768726cd5ecbf57c58a678f1",
    "resume1_lock": "13e54a4b26c39f6b667065921f06408dc0268868405a513bc07b939c2f9efe90",
    "resume1_preflight": "dc2a2cf7a81480fce35458188c6541ec856edbd0fb26c6606f3734cce883768a",
    "resume1_launch_receipt": "dd12544776cc8fe7f58f3ca7317dbbf24a22a9361b397c4465a21bdecc08b0a5",
    "resume1_failure_summary": "b060eb655a2e4b188a2bae80e16bbabd9d9a7501e0c9b6c998d98068fbf7a043",
    "resume1_worker_log": "c04cc1d2683742246f100dab8aa3bad0b091bb1cb9a22a27bb92e35002426c02",
    "resume1_header_audit": "416f210e386e98aec9bb81c9d485e9e6eaf9071b188c86e419903a43dd3af732",
    "erratum_e2": "0b5126605f350e258eea46d1d1bb5a57c4f3dbd5c1b678e62a214263ccb591ad",
}
EXPECTED_OFFICIAL_REPOSITORY_COMMIT = "e589d022953f797bdc6acc1ce9701f793dab295a"
EXPECTED_PANOPTICA_REPOSITORY_COMMIT = "3cc264a470b5c02853aace0f30d6a9af21335abd"
EXPECTED_PACKAGES = {
    "numpy": "2.2.6",
    "scikit-learn": "1.6.1",
    "scipy": "1.18.1",
    "panoptica": "2.1.7",
    "connected-components-3d": "3.29.0",
    "nibabel": "5.3.3",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any], exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    with path.open(mode, encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def project_paths(root: Path) -> dict[str, Path]:
    return {
        "protocol": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.2_protocol_20260827.md",
        "dataset_contract": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.2_dataset_contract_20260827.json",
        "freeze_manifest": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.2_freeze_manifest_20260827.json",
        "formal_execution_lock": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.2_formal_execution_lock_20260827.json",
        "restricted_token_mapping": root / "data/authorized/atlas_r3/formal_v1.2/inference/restricted_token_mapping.csv",
        "g3_lock": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.2_G3_completeness_lock_20260830.json",
        "g3_summary": root / "results/NEUROLRES_ATLAS_SHIFT_v1.2_formal_G3_completeness_20260830.json",
        "g3_restricted_details": root / "data/authorized/atlas_r3/formal_v1.2/inference/qc/v1_2_formal_G3_completeness_details_20260830.json",
        "official_scorer": root / "models/vendor/isles26/utils/eval_utils.py",
        "official_repository": root / "models/vendor/isles26",
        "panoptica_repository": root / "models/vendor/panoptica",
        "prior_identity_summary": root / "results/NEUROLRES_ATLAS_SHIFT_v1.1_P5_identity_summary_20260826.json",
        "scoring_environment": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.1_scoring_environment_E4_20260826.json",
        "pilot36_manifest": root / "data/authorized/atlas_r3/pilot_v1.1/NEUROLRES_ATLAS_SHIFT_v1.1_pilot36_manifest.csv",
        "release_index": root / "data/authorized/atlas_r3/formal_v1.1/preflight/NEUROLRES_ATLAS_SHIFT_v1.1_rebuilt_release_index.csv",
        "formal_g4_scorer_r1": root / "scripts/neurolres_atlas_shift_v1_2_g4_formal_score_r1.py",
        "resume1_lock": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.2_G4_resume1_lock_20260831.json",
        "resume1_preflight": root / "results/NEUROLRES_ATLAS_SHIFT_v1.2_G4_resume1_preflight_20260831.json",
        "resume1_launch_receipt": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.2_G4_resume1_launch_receipt_20260831.json",
        "resume1_failure_summary": root / "results/NEUROLRES_ATLAS_SHIFT_v1.2_G4_summary_r1_20260831.json",
        "resume1_worker_log": root / "data/authorized/atlas_r3/formal_v1.2/metrics/formal_worker_log_r1.jsonl",
        "resume1_header_audit": root / "results/NEUROLRES_ATLAS_SHIFT_v1.2_G4_resume1_header_audit_20260831.json",
        "erratum_e2": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.2_G4_implementation_erratum_E2_20260831.md",
        "g4_self_test": root / "results/NEUROLRES_ATLAS_SHIFT_v1.2_G4_self_test_r2_20260831.json",
        "g4_lock": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.2_G4_resume2_lock_20260831.json",
        "g4_preflight": root / "results/NEUROLRES_ATLAS_SHIFT_v1.2_G4_resume2_preflight_20260831.json",
        "g4_launch_receipt": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.2_G4_resume2_launch_receipt_20260831.json",
        "case_dir": root / "data/authorized/atlas_r3/formal_v1.2/metrics/case_json",
        "restricted_case_metrics": root / "data/authorized/atlas_r3/formal_v1.2/metrics/NEUROLRES_ATLAS_SHIFT_v1.2_formal_case_metrics.csv",
        "restricted_worker_log": root / "data/authorized/atlas_r3/formal_v1.2/metrics/formal_worker_log_r2.jsonl",
        "restricted_primary_details": root / "data/authorized/atlas_r3/formal_v1.2/metrics/restricted_primary_bootstrap_details.json",
        "g4_summary": root / "results/NEUROLRES_ATLAS_SHIFT_v1.2_G4_summary_r2_20260831.json",
    }


def validate_frozen_hashes(paths: dict[str, Path]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for label, expected in EXPECTED_SHA256.items():
        path = paths[label]
        if not path.is_file():
            raise SystemExit(f"FAIL_MISSING_{label.upper()}")
        observed[label] = file_sha256(path)
        if observed[label] != expected:
            raise SystemExit(f"FAIL_{label.upper()}_DRIFT")
    return observed


def git_commit(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def git_clean(path: Path) -> bool:
    lines = subprocess.check_output(
        ["git", "-C", str(path), "status", "--porcelain"], text=True
    ).splitlines()
    source_changes = []
    for line in lines:
        relative = line[3:].strip() if len(line) >= 4 else line.strip()
        if "__pycache__/" in relative or relative.endswith((".pyc", ".pyo")):
            continue
        source_changes.append(line)
    return not source_changes


def environment_state(paths: dict[str, Path]) -> dict[str, Any]:
    packages = {
        name: importlib.metadata.version(name) for name in EXPECTED_PACKAGES
    }
    official_commit = git_commit(paths["official_repository"])
    panoptica_commit = git_commit(paths["panoptica_repository"])
    state = {
        "python": ".".join(str(value) for value in sys.version_info[:3]),
        "packages": packages,
        "official_repository_commit": official_commit,
        "official_repository_clean": git_clean(paths["official_repository"]),
        "panoptica_repository_commit": panoptica_commit,
        "panoptica_repository_clean": git_clean(paths["panoptica_repository"]),
    }
    if state["python"] != "3.12.5":
        raise SystemExit("FAIL_SCORING_PYTHON_DRIFT")
    if packages != EXPECTED_PACKAGES:
        raise SystemExit("FAIL_SCORING_PACKAGE_DRIFT")
    if official_commit != EXPECTED_OFFICIAL_REPOSITORY_COMMIT:
        raise SystemExit("FAIL_OFFICIAL_REPOSITORY_DRIFT")
    if panoptica_commit != EXPECTED_PANOPTICA_REPOSITORY_COMMIT:
        raise SystemExit("FAIL_PANOPTICA_REPOSITORY_DRIFT")
    if not state["official_repository_clean"] or not state["panoptica_repository_clean"]:
        raise SystemExit("FAIL_VENDOR_WORKTREE_DIRTY")
    return state


def load_official_scorer(path: Path):
    if file_sha256(path) != EXPECTED_SHA256["official_scorer"]:
        raise SystemExit("FAIL_OFFICIAL_SCORER_DRIFT")
    spec = importlib.util.spec_from_file_location("frozen_isles26_eval_utils_g4", path)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL_OFFICIAL_SCORER_IMPORT_SPEC")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_mapping(path: Path) -> list[dict[str, str]]:
    if file_sha256(path) != EXPECTED_SHA256["restricted_token_mapping"]:
        raise SystemExit("FAIL_RESTRICTED_MAPPING_DRIFT")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_N:
        raise SystemExit(f"FAIL_DENOMINATOR_{len(rows)}")
    tokens = [row["token"] for row in rows]
    if len(set(tokens)) != EXPECTED_N or not all(TOKEN_PATTERN.fullmatch(x) for x in tokens):
        raise SystemExit("FAIL_TOKEN_SET")
    counts = Counter(row["stratum"] for row in rows)
    if dict(counts) != EXPECTED_DENOMINATORS:
        raise SystemExit(f"FAIL_STRATUM_DENOMINATORS_{dict(counts)}")
    centers = {
        stratum: {row["center"] for row in rows if row["stratum"] == stratum}
        for stratum in STRATA
    }
    if {key: len(value) for key, value in centers.items()} != EXPECTED_CENTERS:
        raise SystemExit("FAIL_CENTER_DENOMINATORS")
    if len(centers["R2_TEST"] | centers["R3_NEW"]) != EXPECTED_PRIMARY_CENTER_UNION:
        raise SystemExit("FAIL_PRIMARY_CENTER_UNION")
    if len(centers["R2_TEST"] & centers["R3_NEW"]) != EXPECTED_PRIMARY_CENTER_INTERSECTION:
        raise SystemExit("FAIL_PRIMARY_CENTER_INTERSECTION")
    return rows


def read_case_ids(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {row["case_id"] for row in csv.DictReader(handle)}


def validate_g3(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    summary = json.loads(paths["g3_summary"].read_text(encoding="utf-8"))
    details = json.loads(paths["g3_restricted_details"].read_text(encoding="utf-8"))
    if summary.get("status") != "G3_PASS":
        raise SystemExit("FAIL_G3_NOT_PASS")
    if summary.get("total_successful_triplets") != EXPECTED_N:
        raise SystemExit("FAIL_G3_DENOMINATOR")
    if summary.get("triplet_content_manifest_sha256") != EXPECTED_G3_TRIPLET_MANIFEST_SHA256:
        raise SystemExit("FAIL_G3_MANIFEST_DRIFT")
    if details.get("triplet_content_manifest_sha256") != EXPECTED_G3_TRIPLET_MANIFEST_SHA256:
        raise SystemExit("FAIL_G3_RESTRICTED_MANIFEST_DRIFT")
    records = details.get("case_records", [])
    if len(records) != EXPECTED_N or not all(record.get("g3_case_pass") for record in records):
        raise SystemExit("FAIL_G3_CASE_RECORDS")
    by_token = {str(record["token"]): record for record in records}
    if len(by_token) != EXPECTED_N:
        raise SystemExit("FAIL_G3_CASE_TOKEN_SET")
    return by_token


def validate_g4_lock(paths: dict[str, Path]) -> dict[str, Any]:
    lock = json.loads(paths["g4_lock"].read_text(encoding="utf-8"))
    if lock.get("protocol_id") != PROTOCOL_ID:
        raise SystemExit("FAIL_G4_LOCK_PROTOCOL")
    if lock.get("artifact_role") != "FORMAL_762_G4_RESUME2_LOCK":
        raise SystemExit("FAIL_G4_LOCK_ROLE")
    if lock.get("status") != "G4_RESUME2_AUTHORIZED_LOCKED_NOT_RUN":
        raise SystemExit("FAIL_G4_LOCK_STATUS")
    if lock.get("authorization", {}).get("user_explicit_authorization") is not True:
        raise SystemExit("FAIL_G4_NOT_AUTHORIZED")
    locked = lock.get("locked_sha256", {})
    for label, expected in EXPECTED_SHA256.items():
        if locked.get(label) != expected:
            raise SystemExit(f"FAIL_G4_LOCK_{label.upper()}_HASH")
    if locked.get("formal_g4_scorer") != file_sha256(Path(__file__).resolve()):
        raise SystemExit("FAIL_G4_SCORER_DRIFT")
    if locked.get("g4_self_test") != file_sha256(paths["g4_self_test"]):
        raise SystemExit("FAIL_G4_SELF_TEST_DRIFT")
    for label, expected in RESUME2_PRIOR_SHA256.items():
        path = paths[label]
        if not path.is_file() or file_sha256(path) != expected:
            raise SystemExit(f"FAIL_G4_PRIOR_{label.upper()}_DRIFT")
        if locked.get(label) != expected:
            raise SystemExit(f"FAIL_G4_LOCK_{label.upper()}_DRIFT")
    analysis = lock.get("analysis_contract", {})
    required = {
        "fixed_n": EXPECTED_N,
        "primary_endpoint": "center-macro lesion-wise F1",
        "primary_comparison": "R2_TEST - R3_NEW",
        "effect_threshold": PRIMARY_THRESHOLD,
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "percentile_ci": [0.025, 0.975],
        "two_sided_p_definition": "2*min((1+sum(delta_boot<=0))/(B+1),(1+sum(delta_boot>=0))/(B+1)); capped at 1",
    }
    for key, expected in required.items():
        if analysis.get(key) != expected:
            raise SystemExit(f"FAIL_G4_LOCK_ANALYSIS_{key.upper()}")
    geometry = lock.get("E2_geometry_contract", {})
    required_geometry = {
        "scoring_space": "unchanged array index",
        "shape_equality_required": True,
        "voxel_size_absolute_tolerance": VOXEL_SIZE_ABS_TOL,
        "affine_and_orientation_recorded_not_exclusionary": True,
        "ground_truth_resampling": False,
        "prediction_resampling": False,
        "header_anomalies_to_disclose": 5,
    }
    for key, expected in required_geometry.items():
        if geometry.get(key) != expected:
            raise SystemExit(f"FAIL_G4_LOCK_GEOMETRY_{key.upper()}")
    return lock


def reconstruct_foreground_probability(row: dict[str, str]) -> np.ndarray:
    with np.load(row["prediction_npz"]) as archive:
        if "softmax" not in archive.files:
            raise ValueError("NPZ_MISSING_SOFTMAX")
        softmax = np.asarray(archive["softmax"])
    if softmax.ndim != 4 or softmax.shape[0] != 2:
        raise ValueError("INVALID_SOFTMAX_SHAPE")
    if not np.isfinite(softmax).all():
        raise ValueError("NONFINITE_SOFTMAX")
    with Path(row["prediction_properties"]).open("rb") as handle:
        properties = pickle.load(handle)
    original_shape = tuple(int(value) for value in properties["original_size_of_raw_data"])
    probability = np.zeros(original_shape, dtype=np.float16)
    foreground_crop = softmax[1]
    bbox = properties.get("crop_bbox")
    if bbox is None:
        if foreground_crop.shape != original_shape:
            raise ValueError("SOFTMAX_ORIGINAL_SHAPE_MISMATCH")
        probability = foreground_crop
    else:
        slices = tuple(slice(int(bounds[0]), int(bounds[1])) for bounds in bbox)
        expected_shape = tuple(index.stop - index.start for index in slices)
        if foreground_crop.shape != expected_shape:
            raise ValueError("SOFTMAX_CROP_SHAPE_MISMATCH")
        probability[slices] = foreground_crop
    return probability


def validate_prediction_hashes(row: dict[str, str], g3_record: dict[str, Any]) -> dict[str, str]:
    observed = {
        "nii_gz": file_sha256(Path(row["prediction_nii"])),
        "npz": file_sha256(Path(row["prediction_npz"])),
        "pkl": file_sha256(Path(row["prediction_properties"])),
    }
    expected = g3_record.get("file_sha256", {})
    if observed != expected:
        raise ValueError("PREDICTION_HASH_DRIFT_AFTER_G3")
    return observed


def normalize_ground_truth(gt_xyz: np.ndarray) -> np.ndarray:
    if not np.isfinite(gt_xyz).all():
        raise ValueError("NONFINITE_GROUND_TRUTH")
    unique_values = np.unique(gt_xyz).astype(float)
    valid_storage = np.isclose(
        unique_values, 0.0, rtol=0.0, atol=GT_STORAGE_ABS_TOL
    ) | np.isclose(unique_values, 1.0, rtol=0.0, atol=GT_STORAGE_ABS_TOL)
    if not bool(np.all(valid_storage)):
        raise ValueError("GROUND_TRUTH_NOT_BINARY_WITHIN_E1_STORAGE_TOLERANCE")
    return gt_xyz > 0.5


def validate_array_index_geometry(
    gt_img: nib.spatialimages.SpatialImage,
    pred_img: nib.spatialimages.SpatialImage,
) -> dict[str, Any]:
    """Enforce E2 scoring geometry without resampling or header-based exclusion."""
    gt_shape = tuple(int(value) for value in gt_img.shape)
    pred_shape = tuple(int(value) for value in pred_img.shape)
    if gt_shape != pred_shape:
        raise ValueError("GT_PRED_SHAPE_MISMATCH")
    gt_voxel_size = tuple(float(value) for value in gt_img.header.get_zooms()[:3])
    pred_voxel_size = tuple(float(value) for value in pred_img.header.get_zooms()[:3])
    voxel_size_equal = bool(
        np.allclose(
            gt_voxel_size,
            pred_voxel_size,
            rtol=0.0,
            atol=VOXEL_SIZE_ABS_TOL,
        )
    )
    if not voxel_size_equal:
        raise ValueError("GT_PRED_VOXEL_SIZE_MISMATCH")
    orientation_equal = bool(
        nib.aff2axcodes(gt_img.affine) == nib.aff2axcodes(pred_img.affine)
    )
    affine_delta = float(np.max(np.abs(gt_img.affine - pred_img.affine)))
    return {
        "shape_equal": True,
        "voxel_size_equal": True,
        "gt_voxel_size_mm": gt_voxel_size,
        "prediction_voxel_size_mm": pred_voxel_size,
        "selected_orientation_equal": orientation_equal,
        "affine_max_abs_delta_mm": affine_delta,
        "scoring_rule": "ARRAY_INDEX_NO_RESAMPLING_E2",
    }


def score_one_case(
    row: dict[str, str],
    g3_record: dict[str, Any],
    scorer_path: Path,
    output_path: Path,
) -> None:
    scorer = load_official_scorer(scorer_path)
    prediction_hashes = validate_prediction_hashes(row, g3_record)
    mask_path = Path(row["mask_path"])
    mask_sha256 = file_sha256(mask_path)
    gt_img = nib.load(str(mask_path))
    pred_img = nib.load(row["prediction_nii"])
    geometry_qc = validate_array_index_geometry(gt_img, pred_img)
    gt_xyz = np.asanyarray(gt_img.dataobj)
    pred_xyz = np.asanyarray(pred_img.dataobj)
    if not np.isfinite(pred_xyz).all():
        raise ValueError("NONFINITE_PREDICTION")
    if not set(np.unique(pred_xyz).tolist()).issubset({0, 1, 0.0, 1.0}):
        raise ValueError("PREDICTION_NOT_BINARY")
    gt_binary_xyz = normalize_ground_truth(gt_xyz)
    gt_zyx = np.transpose(gt_binary_xyz, (2, 1, 0))
    pred_zyx = np.transpose(pred_xyz, (2, 1, 0)) > 0.5
    probability_zyx = reconstruct_foreground_probability(row)
    if probability_zyx.shape != gt_zyx.shape:
        raise ValueError("GT_PROBABILITY_SHAPE_MISMATCH")

    lesion_f1, count_difference, dice = scorer.compute_dice_f1_instance_difference(
        gt_zyx, pred_zyx
    )
    pr_auc = scorer.compute_pr_auc(gt_zyx, probability_zyx)
    voxel_volume_ml = np.asarray(np.prod(gt_img.header.get_zooms()[:3]) / 1000.0)
    volume_difference = scorer.compute_absolute_volume_difference(
        gt_zyx, pred_zyx, voxel_volume_ml
    )
    result: dict[str, Any] = {
        "token": row["token"],
        "case_id": row["case_id"],
        "stratum": row["stratum"],
        "center": row["center"],
        "status": "PASS",
        "dice": float(dice),
        "lesion_f1": float(lesion_f1),
        "pr_auc": float(pr_auc),
        "abs_volume_difference_ml": float(volume_difference),
        "abs_lesion_count_difference": int(count_difference),
        "empty_prediction": bool(not np.any(pred_zyx)),
        "gt_empty": bool(not np.any(gt_zyx)),
        "gt_voxels": int(np.sum(gt_zyx)),
        "prediction_voxels": int(np.sum(pred_zyx)),
        "voxel_volume_ml": float(voxel_volume_ml),
        "affine_max_abs_delta_mm": geometry_qc["affine_max_abs_delta_mm"],
        "selected_orientation_equal": geometry_qc["selected_orientation_equal"],
        "voxel_size_equal": geometry_qc["voxel_size_equal"],
        "gt_voxel_size_mm": geometry_qc["gt_voxel_size_mm"],
        "prediction_voxel_size_mm": geometry_qc["prediction_voxel_size_mm"],
        "geometry_scoring_rule": geometry_qc["scoring_rule"],
        "mask_sha256": mask_sha256,
        "prediction_sha256": prediction_hashes,
    }
    if not all(np.isfinite(float(result[metric])) for metric in METRICS):
        raise ValueError("NONFINITE_OFFICIAL_METRIC")
    if not all(0.0 <= float(result[metric]) <= 1.0 for metric in ("dice", "lesion_f1", "pr_auc")):
        raise ValueError("BOUNDED_METRIC_OUT_OF_RANGE")
    write_json(output_path, result, exclusive=True)


def distribution(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(array)),
        "sd": float(np.std(array, ddof=1)) if len(array) > 1 else 0.0,
        "median": float(np.median(array)),
        "q1": float(np.quantile(array, 0.25, method="linear")),
        "q3": float(np.quantile(array, 0.75, method="linear")),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }


def center_means(rows: list[dict[str, Any]], metric: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row["center"])].append(float(row[metric]))
    return {center: float(np.mean(values)) for center, values in grouped.items()}


def primary_center_macro(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_stratum = {
        stratum: [row for row in rows if row["stratum"] == stratum]
        for stratum in ("R2_TEST", "R3_NEW")
    }
    means = {
        stratum: center_means(stratum_rows, "lesion_f1")
        for stratum, stratum_rows in by_stratum.items()
    }
    values = {
        stratum: float(np.mean(list(center_values.values())))
        for stratum, center_values in means.items()
    }
    return {
        "center_means": means,
        "macro_values": values,
        "observed_delta": float(values["R2_TEST"] - values["R3_NEW"]),
    }


def joint_center_bootstrap(
    r2_center_means: dict[str, float],
    r3_center_means: dict[str, float],
    repetitions: int = BOOTSTRAP_REPETITIONS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    union = np.asarray(sorted(set(r2_center_means) | set(r3_center_means)), dtype=object)
    rng = np.random.default_rng(seed)
    deltas: list[float] = []
    attempted = 0
    while len(deltas) < repetitions:
        drawn = rng.choice(union, size=len(union), replace=True)
        attempted += 1
        r2_values = [r2_center_means[str(center)] for center in drawn if str(center) in r2_center_means]
        r3_values = [r3_center_means[str(center)] for center in drawn if str(center) in r3_center_means]
        if not r2_values or not r3_values:
            continue
        deltas.append(float(np.mean(r2_values) - np.mean(r3_values)))
    array = np.asarray(deltas, dtype=float)
    lower, upper = np.quantile(array, [0.025, 0.975], method="linear")
    lower_tail = (1 + int(np.sum(array <= 0.0))) / (repetitions + 1)
    upper_tail = (1 + int(np.sum(array >= 0.0))) / (repetitions + 1)
    p_value = min(1.0, 2.0 * min(lower_tail, upper_tail))
    return {
        "deltas": deltas,
        "ci_lower": float(lower),
        "ci_upper": float(upper),
        "p_value_two_sided": float(p_value),
        "valid_repetitions": len(deltas),
        "attempted_draws": attempted,
        "seed": seed,
        "center_union_n": len(union),
        "tail_definition": "plus-one empirical tails around zero, doubled and capped at 1",
    }


def case_bootstrap_means(
    rows: list[dict[str, Any]],
    repetitions: int = BOOTSTRAP_REPETITIONS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, dict[str, float]]:
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(rows), size=(repetitions, len(rows)))
    output: dict[str, dict[str, float]] = {}
    metric_arrays = {
        metric: np.asarray([float(row[metric]) for row in rows], dtype=float)
        for metric in METRICS
    }
    metric_arrays["empty_prediction_rate"] = np.asarray(
        [float(bool(row["empty_prediction"])) for row in rows], dtype=float
    )
    for metric, values in metric_arrays.items():
        bootstrap_means = np.mean(values[indices], axis=1)
        lower, upper = np.quantile(
            bootstrap_means, [0.025, 0.975], method="linear"
        )
        output[metric] = {
            "observed_mean": float(np.mean(values)),
            "ci_lower": float(lower),
            "ci_upper": float(upper),
        }
    return output


def public_stratum_summary(rows: list[dict[str, Any]], fixed_n: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "fixed_n": fixed_n,
        "n_scored": len(rows),
        "inference_failure_rate": 0.0,
        "scoring_failure_rate": float((fixed_n - len(rows)) / fixed_n),
        "empty_prediction_rate": float(np.mean([bool(row["empty_prediction"]) for row in rows])),
        "empty_ground_truth_rate": float(np.mean([bool(row["gt_empty"]) for row in rows])),
    }
    for metric in METRICS:
        summary[metric] = distribution([float(row[metric]) for row in rows])
    return summary


def write_restricted_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = sorted({key for row in rows for key in row})
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in row.items()
                }
            )


def case_file_manifest(case_dir: Path) -> tuple[int, str]:
    paths = sorted(case_dir.glob("v12f*.json")) if case_dir.exists() else []
    digest = hashlib.sha256()
    for path in paths:
        digest.update(
            f"{path.name}\t{path.stat().st_size}\t{file_sha256(path)}\n".encode()
        )
    return len(paths), digest.hexdigest()


def run_self_test(root: Path, paths: dict[str, Path]) -> int:
    if paths["g4_self_test"].exists():
        raise SystemExit("FAIL_SELF_TEST_OUTPUT_EXISTS")
    observed_hashes = validate_frozen_hashes(paths)
    environment = environment_state(paths)
    scorer = load_official_scorer(paths["official_scorer"])
    ground_truth = np.zeros((16, 16, 16), dtype=np.uint8)
    ground_truth[2:5, 2:5, 2:5] = 1
    ground_truth[10:14, 9:13, 8:12] = 1
    prediction = ground_truth.copy()
    soft_prediction = ground_truth.astype(np.float32)
    lesion_f1, lesion_count_difference, dice = scorer.compute_dice_f1_instance_difference(
        ground_truth, prediction
    )
    pr_auc = scorer.compute_pr_auc(ground_truth, soft_prediction)
    volume_difference = scorer.compute_absolute_volume_difference(
        ground_truth, prediction, np.asarray(0.001, dtype=float)
    )
    identity_values = {
        "dice": float(dice),
        "lesion_f1": float(lesion_f1),
        "pr_auc": float(pr_auc),
        "abs_lesion_count_difference": int(lesion_count_difference),
        "abs_volume_difference_ml": float(volume_difference),
    }
    identity_pass = bool(
        np.isclose(identity_values["dice"], 1.0)
        and np.isclose(identity_values["lesion_f1"], 1.0)
        and np.isclose(identity_values["pr_auc"], 1.0)
        and identity_values["abs_lesion_count_difference"] == 0
        and np.isclose(identity_values["abs_volume_difference_ml"], 0.0)
    )
    scaled_upper = np.asarray([0.0, 1.0000000591389835], dtype=float)
    scaled_lower = np.asarray([0.0, 0.9999999776482582], dtype=float)
    empty_truth = np.zeros((2, 2), dtype=float)
    storage_tolerance_pass = bool(
        normalize_ground_truth(scaled_upper).tolist() == [False, True]
        and normalize_ground_truth(scaled_lower).tolist() == [False, True]
        and not np.any(normalize_ground_truth(empty_truth))
    )
    invalid_intermediate_rejected = False
    try:
        normalize_ground_truth(np.asarray([0.0, 0.25, 1.0], dtype=float))
    except ValueError:
        invalid_intermediate_rejected = True
    encoding_test_pass = storage_tolerance_pass and invalid_intermediate_rejected
    synthetic_geometry_data = np.zeros((4, 5, 6), dtype=np.uint8)
    geometry_gt = nib.Nifti1Image(synthetic_geometry_data, np.eye(4))
    mirrored_affine = np.diag([-1.0, 1.0, 1.0, 1.0])
    geometry_pred_header_anomaly = nib.Nifti1Image(
        synthetic_geometry_data.copy(), mirrored_affine
    )
    geometry_qc = validate_array_index_geometry(
        geometry_gt, geometry_pred_header_anomaly
    )
    header_anomaly_accepted = bool(
        geometry_qc["shape_equal"]
        and geometry_qc["voxel_size_equal"]
        and not geometry_qc["selected_orientation_equal"]
        and geometry_qc["affine_max_abs_delta_mm"] > 0.001
    )
    shape_mismatch_rejected = False
    try:
        validate_array_index_geometry(
            geometry_gt,
            nib.Nifti1Image(np.zeros((4, 5, 7), dtype=np.uint8), np.eye(4)),
        )
    except ValueError as error:
        shape_mismatch_rejected = str(error) == "GT_PRED_SHAPE_MISMATCH"
    voxel_size_mismatch_rejected = False
    try:
        validate_array_index_geometry(
            geometry_gt,
            nib.Nifti1Image(
                synthetic_geometry_data.copy(), np.diag([2.0, 1.0, 1.0, 1.0])
            ),
        )
    except ValueError as error:
        voxel_size_mismatch_rejected = str(error) == "GT_PRED_VOXEL_SIZE_MISMATCH"
    geometry_test_pass = bool(
        header_anomaly_accepted
        and shape_mismatch_rejected
        and voxel_size_mismatch_rejected
    )
    r2 = {"A": 0.7, "B": 0.5}
    r3 = {"A": 0.4, "C": 0.2}
    bootstrap_a = joint_center_bootstrap(r2, r3)
    bootstrap_b = joint_center_bootstrap(r2, r3)
    bootstrap_pass = bool(
        bootstrap_a["deltas"] == bootstrap_b["deltas"]
        and bootstrap_a["valid_repetitions"] == BOOTSTRAP_REPETITIONS
        and np.isfinite(bootstrap_a["ci_lower"])
        and np.isfinite(bootstrap_a["ci_upper"])
        and 0.0 <= bootstrap_a["p_value_two_sided"] <= 1.0
    )
    synthetic_rows = [
        {
            "dice": value,
            "lesion_f1": value,
            "pr_auc": value,
            "abs_volume_difference_ml": value,
            "abs_lesion_count_difference": value,
            "empty_prediction": False,
        }
        for value in (0.1, 0.2, 0.3, 0.4)
    ]
    case_bootstrap_a = case_bootstrap_means(synthetic_rows)
    case_bootstrap_b = case_bootstrap_means(synthetic_rows)
    case_bootstrap_pass = case_bootstrap_a == case_bootstrap_b
    passed = bool(
        identity_pass
        and encoding_test_pass
        and geometry_test_pass
        and bootstrap_pass
        and case_bootstrap_pass
    )
    payload = {
        "protocol_id": PROTOCOL_ID,
        "artifact_role": "FORMAL_G4_R2_SYNTHETIC_SELF_TEST",
        "created_at_utc": utc_now(),
        "status": "G4_SELF_TEST_PASS" if passed else "G4_SELF_TEST_FAIL_STOP",
        "formal_g4_scorer_sha256": file_sha256(Path(__file__).resolve()),
        "observed_frozen_sha256": observed_hashes,
        "environment": environment,
        "identity_test": {"pass": identity_pass, "values": identity_values},
        "E1_ground_truth_storage_test": {
            "pass": encoding_test_pass,
            "absolute_tolerance": GT_STORAGE_ABS_TOL,
            "scaled_upper_accepted": storage_tolerance_pass,
            "scaled_lower_accepted": storage_tolerance_pass,
            "empty_truth_accepted": storage_tolerance_pass,
            "invalid_intermediate_rejected": invalid_intermediate_rejected,
            "binary_rule": "unchanged raw_value > 0.5"
        },
        "E2_array_index_geometry_test": {
            "pass": geometry_test_pass,
            "voxel_size_absolute_tolerance": VOXEL_SIZE_ABS_TOL,
            "same_shape_and_voxel_size_header_anomaly_accepted": header_anomaly_accepted,
            "shape_mismatch_rejected": shape_mismatch_rejected,
            "voxel_size_mismatch_rejected": voxel_size_mismatch_rejected,
            "affine_and_orientation_used_for_exclusion": False,
            "ground_truth_resampled": False,
            "prediction_resampled": False,
            "synthetic_header_anomaly_qc": geometry_qc,
        },
        "joint_center_bootstrap_test": {
            "pass": bootstrap_pass,
            "synthetic_observed_delta": 0.3,
            "ci_lower": bootstrap_a["ci_lower"],
            "ci_upper": bootstrap_a["ci_upper"],
            "p_value_two_sided": bootstrap_a["p_value_two_sided"],
            "valid_repetitions": bootstrap_a["valid_repetitions"],
            "attempted_draws": bootstrap_a["attempted_draws"],
        },
        "case_bootstrap_test": {"pass": case_bootstrap_pass},
        "patient_data_read": False,
        "model_output_read": False,
        "ground_truth_read": False,
        "effect_metrics_read": False,
    }
    write_json(paths["g4_self_test"], payload, exclusive=True)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if passed else 1


def run_preflight(root: Path, paths: dict[str, Path]) -> int:
    if paths["g4_preflight"].exists():
        raise SystemExit("FAIL_PREFLIGHT_OUTPUT_EXISTS")
    observed_hashes = validate_frozen_hashes(paths)
    environment = environment_state(paths)
    lock = validate_g4_lock(paths)
    self_test = json.loads(paths["g4_self_test"].read_text(encoding="utf-8"))
    if self_test.get("status") != "G4_SELF_TEST_PASS":
        raise SystemExit("FAIL_G4_SELF_TEST_NOT_PASS")
    rows = read_mapping(paths["restricted_token_mapping"])
    g3_by_token = validate_g3(paths)
    if set(g3_by_token) != {row["token"] for row in rows}:
        raise SystemExit("FAIL_G3_MAPPING_TOKEN_MISMATCH")
    pilot_case_ids = read_case_ids(paths["pilot36_manifest"])
    formal_case_ids = {row["case_id"] for row in rows}
    pilot_overlap = len(pilot_case_ids & formal_case_ids)
    if pilot_overlap != 0:
        raise SystemExit("FAIL_PILOT36_OVERLAP")
    mask_present_nonempty = sum(
        Path(row["mask_path"]).is_file() and Path(row["mask_path"]).stat().st_size > 0
        for row in rows
    )
    if mask_present_nonempty != EXPECTED_N:
        raise SystemExit("FAIL_MASK_PATH_INTEGRITY")
    output_paths = (
        paths["restricted_case_metrics"],
        paths["restricted_worker_log"],
        paths["restricted_primary_details"],
        paths["g4_summary"],
        paths["g4_launch_receipt"],
    )
    if any(path.exists() for path in output_paths):
        raise SystemExit("FAIL_G4_OUTPUT_ALREADY_EXISTS")
    existing_case_n, existing_case_manifest = case_file_manifest(paths["case_dir"])
    if existing_case_n != RESUME1_COMPLETED_CASE_FILES:
        raise SystemExit("FAIL_G4_R2_EXISTING_CASE_COUNT")
    if existing_case_manifest != RESUME1_CASE_FILE_MANIFEST_SHA256:
        raise SystemExit("FAIL_G4_R2_EXISTING_CASE_MANIFEST")
    payload = {
        "protocol_id": PROTOCOL_ID,
        "artifact_role": "FORMAL_762_G4_PREFLIGHT",
        "created_at_utc": utc_now(),
        "status": "G4_R2_RESUME_PREFLIGHT_PASS_READY",
        "formal_g4_scorer_sha256": file_sha256(Path(__file__).resolve()),
        "g4_lock_sha256": file_sha256(paths["g4_lock"]),
        "g4_self_test_sha256": file_sha256(paths["g4_self_test"]),
        "observed_frozen_sha256": observed_hashes,
        "environment": environment,
        "fixed_n": EXPECTED_N,
        "fixed_denominators": EXPECTED_DENOMINATORS,
        "fixed_centers": EXPECTED_CENTERS,
        "primary_center_union_n": EXPECTED_PRIMARY_CENTER_UNION,
        "primary_center_intersection_n": EXPECTED_PRIMARY_CENTER_INTERSECTION,
        "g3_triplet_manifest_sha256": EXPECTED_G3_TRIPLET_MANIFEST_SHA256,
        "g3_tokens_exactly_match_mapping": True,
        "pilot36_overlap": pilot_overlap,
        "mask_paths_present_nonempty": mask_present_nonempty,
        "new_output_targets_empty": True,
        "resume1_existing_case_files": existing_case_n,
        "resume1_existing_case_manifest_sha256": existing_case_manifest,
        "resume1_case_files_opened_by_preflight": False,
        "remaining_cases_to_score": EXPECTED_N - existing_case_n,
        "E2_geometry_contract": lock["E2_geometry_contract"],
        "header_anomalies_to_disclose": 5,
        "authorization_recorded": lock["authorization"],
        "patient_file_contents_read": False,
        "model_output_contents_read": False,
        "ground_truth_read": False,
        "effect_metrics_read_by_preflight": False,
        "outcome_partially_unblinded_before_resume2": True,
        "next_action": "RESUME_FORMAL_G4_WITHOUT_OVERWRITE",
    }
    write_json(paths["g4_preflight"], payload, exclusive=True)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def run_worker(root: Path, paths: dict[str, Path], worker_index: int) -> int:
    validate_frozen_hashes(paths)
    validate_g4_lock(paths)
    rows = read_mapping(paths["restricted_token_mapping"])
    if not 0 <= worker_index < EXPECTED_N:
        raise SystemExit("FAIL_WORKER_INDEX")
    g3_by_token = validate_g3(paths)
    row = rows[worker_index]
    output = paths["case_dir"] / f"{row['token']}.json"
    if output.exists():
        raise SystemExit("FAIL_WORKER_OUTPUT_EXISTS")
    score_one_case(row, g3_by_token[row["token"]], paths["official_scorer"], output)
    return 0


def write_technical_failure_summary(
    paths: dict[str, Path],
    completed_n: int,
    failed_index: int,
    returncode: int,
) -> None:
    payload = {
        "protocol_id": PROTOCOL_ID,
        "artifact_role": "FORMAL_762_G4_SUMMARY",
        "created_at_utc": utc_now(),
        "status": "G4_TECHNICAL_FAIL_STOP_EFFECTS_PARTIALLY_UNBLINDED",
        "fixed_n": EXPECTED_N,
        "completed_case_files": completed_n,
        "failed_worker_index_zero_based": failed_index,
        "failed_worker_returncode": returncode,
        "aggregate_effect_statistics_computed": False,
        "primary_G4_decision_computed": False,
        "effect_metrics_read": completed_n > 0,
        "outcome_unblinded": completed_n > 0,
        "failure_action": "STOP_PRESERVE_PARTIAL_RESTRICTED_OUTPUTS_NO_THRESHOLD_OR_SAMPLE_CHANGES",
    }
    write_json(paths["g4_summary"], payload, exclusive=True)


def run_formal(root: Path, paths: dict[str, Path], resume: bool) -> int:
    validate_frozen_hashes(paths)
    lock = validate_g4_lock(paths)
    environment_state(paths)
    preflight = json.loads(paths["g4_preflight"].read_text(encoding="utf-8"))
    if preflight.get("status") != "G4_R2_RESUME_PREFLIGHT_PASS_READY":
        raise SystemExit("FAIL_G4_PREFLIGHT_NOT_PASS")
    if preflight.get("formal_g4_scorer_sha256") != file_sha256(Path(__file__).resolve()):
        raise SystemExit("FAIL_G4_PREFLIGHT_SCORER_DRIFT")
    if preflight.get("g4_lock_sha256") != file_sha256(paths["g4_lock"]):
        raise SystemExit("FAIL_G4_PREFLIGHT_LOCK_DRIFT")
    rows = read_mapping(paths["restricted_token_mapping"])
    validate_g3(paths)
    paths["case_dir"].mkdir(parents=True, exist_ok=True)
    existing = sorted(paths["case_dir"].glob("v12f*.json"))
    if not resume:
        raise SystemExit("FAIL_G4_R2_REQUIRES_EXPLICIT_RESUME_MODE")
    existing_n, existing_manifest = case_file_manifest(paths["case_dir"])
    if existing_n != RESUME1_COMPLETED_CASE_FILES:
        raise SystemExit("FAIL_G4_R2_EXISTING_CASE_COUNT")
    if existing_manifest != RESUME1_CASE_FILE_MANIFEST_SHA256:
        raise SystemExit("FAIL_G4_R2_EXISTING_CASE_MANIFEST")
    if paths["g4_summary"].exists() or paths["restricted_case_metrics"].exists():
        raise SystemExit("FAIL_FINAL_G4_OUTPUT_EXISTS")
    if paths["restricted_worker_log"].exists() or paths["g4_launch_receipt"].exists():
        raise SystemExit("FAIL_G4_R2_RUN_ARTIFACT_EXISTS")
    launch = {
        "protocol_id": PROTOCOL_ID,
        "artifact_role": "FORMAL_762_G4_RESUME2_LAUNCH_RECEIPT",
        "created_at_utc": utc_now(),
        "status": "G4_RESUME2_AUTHORIZED_STARTED_BEFORE_ADDITIONAL_EFFECT_READ",
        "fixed_n": EXPECTED_N,
        "formal_g4_scorer_sha256": file_sha256(Path(__file__).resolve()),
        "g4_resume_lock_sha256": file_sha256(paths["g4_lock"]),
        "g4_resume_preflight_sha256": file_sha256(paths["g4_preflight"]),
        "g3_triplet_manifest_sha256": EXPECTED_G3_TRIPLET_MANIFEST_SHA256,
        "existing_case_metric_files": existing_n,
        "existing_case_metric_manifest_sha256": existing_manifest,
        "existing_case_metric_contents_read_by_resume_preflight": False,
        "effect_metrics_already_read_before_resume2": True,
        "aggregate_effect_statistics_already_computed": False,
        "E2_geometry_contract": lock["E2_geometry_contract"],
        "resume_policy": "SKIP_EXACT_240_EXISTING_CASE_JSON_WITHOUT_OVERWRITE; SCORE_REMAINING_522",
    }
    write_json(paths["g4_launch_receipt"], launch, exclusive=True)
    paths["restricted_worker_log"].parent.mkdir(parents=True, exist_ok=True)
    paths["restricted_worker_log"].touch(exist_ok=False)

    completed_before = {path.stem for path in existing}
    for index, row in enumerate(rows):
        if row["token"] in completed_before:
            continue
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "worker",
            "--project-root",
            str(root),
            "--worker-index",
            str(index),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        log_record = {
            "worker_index_zero_based": index,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
        with paths["restricted_worker_log"].open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(log_record, ensure_ascii=False) + "\n")
        total_complete = len(list(paths["case_dir"].glob("v12f*.json")))
        print(f"scored_cases={total_complete}/{EXPECTED_N} returncode={completed.returncode}", flush=True)
        if completed.returncode != 0:
            write_technical_failure_summary(
                paths, total_complete, index, completed.returncode
            )
            return 1

    case_paths = sorted(paths["case_dir"].glob("v12f*.json"))
    if len(case_paths) != EXPECTED_N:
        write_technical_failure_summary(paths, len(case_paths), -1, 98)
        return 1
    case_results = [json.loads(path.read_text(encoding="utf-8")) for path in case_paths]
    expected_tokens = {row["token"] for row in rows}
    observed_tokens = {str(row["token"]) for row in case_results}
    if observed_tokens != expected_tokens or not all(row.get("status") == "PASS" for row in case_results):
        write_technical_failure_summary(paths, len(case_results), -1, 99)
        return 1
    write_restricted_csv(paths["restricted_case_metrics"], case_results)

    by_stratum = {
        stratum: [row for row in case_results if row["stratum"] == stratum]
        for stratum in STRATA
    }
    primary = primary_center_macro(case_results)
    bootstrap = joint_center_bootstrap(
        primary["center_means"]["R2_TEST"],
        primary["center_means"]["R3_NEW"],
    )
    soop_bootstrap = case_bootstrap_means(by_stratum["SOOP"])
    criterion_delta = primary["observed_delta"] >= PRIMARY_THRESHOLD
    criterion_ci = bootstrap["ci_lower"] > 0.0
    criterion_p = bootstrap["p_value_two_sided"] < 0.05
    g4_pass = bool(criterion_delta and criterion_ci and criterion_p)

    restricted_primary = {
        "protocol_id": PROTOCOL_ID,
        "artifact_role": "FORMAL_G4_RESTRICTED_PRIMARY_DETAILS",
        "created_at_utc": utc_now(),
        "center_means": primary["center_means"],
        "bootstrap_deltas": bootstrap["deltas"],
        "bootstrap_attempted_draws": bootstrap["attempted_draws"],
        "soop_case_bootstrap": soop_bootstrap,
        "case_metric_csv_sha256": file_sha256(paths["restricted_case_metrics"]),
    }
    write_json(paths["restricted_primary_details"], restricted_primary, exclusive=True)

    public_primary = {
        "endpoint": "center-macro lesion-wise F1",
        "comparison": "R2_TEST - R3_NEW",
        "R2_TEST": {
            "n_centers": len(primary["center_means"]["R2_TEST"]),
            "center_macro_lesion_f1": primary["macro_values"]["R2_TEST"],
        },
        "R3_NEW": {
            "n_centers": len(primary["center_means"]["R3_NEW"]),
            "center_macro_lesion_f1": primary["macro_values"]["R3_NEW"],
        },
        "observed_R2_TEST_minus_R3_NEW": primary["observed_delta"],
        "percentile_95_ci": [bootstrap["ci_lower"], bootstrap["ci_upper"]],
        "bootstrap_p_two_sided": bootstrap["p_value_two_sided"],
        "bootstrap_repetitions": bootstrap["valid_repetitions"],
        "bootstrap_seed": BOOTSTRAP_SEED,
        "center_union_n": bootstrap["center_union_n"],
        "G4_criteria": {
            "delta_at_least_0_05": criterion_delta,
            "ci_lower_greater_than_0": criterion_ci,
            "p_less_than_0_05": criterion_p,
        },
    }
    summary = {
        "protocol_id": PROTOCOL_ID,
        "artifact_role": "FORMAL_762_G4_SUMMARY",
        "created_at_utc": utc_now(),
        "status": "G4_PASS" if g4_pass else "G4_FAIL_G5_NEGATIVE_POSITIONING_REQUIRED",
        "fixed_n": EXPECTED_N,
        "n_scored": len(case_results),
        "n_failed": 0,
        "fixed_denominators": EXPECTED_DENOMINATORS,
        "strata": {
            stratum: public_stratum_summary(by_stratum[stratum], EXPECTED_DENOMINATORS[stratum])
            for stratum in STRATA
        },
        "primary": public_primary,
        "SOOP_conditional_case_bootstrap_95_ci": soop_bootstrap,
        "G4_pass": g4_pass,
        "claim_boundary": (
            "PRESPECIFIED_MEANINGFUL_MULTICENTER_TEMPORAL_SOURCE_SHIFT_DECLINE_SUPPORTED"
            if g4_pass
            else "NO_PRESPECIFIED_MEANINGFUL_DECLINE_CLAIM; NEGATIVE_EXTERNAL_VALIDATION_ROBUSTNESS_POSITIONING_ONLY"
        ),
        "next_action": (
            "G5_MANUSCRIPT_POSITIONING_WITH_PRESPECIFIED_DECLINE_CLAIM"
            if g4_pass
            else "G5_NEGATIVE_EXTERNAL_VALIDATION_ROBUSTNESS_POSITIONING"
        ),
        "formal_g4_scorer_sha256": file_sha256(Path(__file__).resolve()),
        "g4_lock_sha256": file_sha256(paths["g4_lock"]),
        "g4_preflight_sha256": file_sha256(paths["g4_preflight"]),
        "g4_launch_receipt_sha256": file_sha256(paths["g4_launch_receipt"]),
        "g3_triplet_manifest_sha256": EXPECTED_G3_TRIPLET_MANIFEST_SHA256,
        "official_scorer_sha256": EXPECTED_SHA256["official_scorer"],
        "restricted_case_metrics": str(paths["restricted_case_metrics"].resolve()),
        "restricted_case_metrics_sha256": file_sha256(paths["restricted_case_metrics"]),
        "restricted_worker_log": str(paths["restricted_worker_log"].resolve()),
        "restricted_worker_log_sha256": file_sha256(paths["restricted_worker_log"]),
        "restricted_primary_details": str(paths["restricted_primary_details"].resolve()),
        "restricted_primary_details_sha256": file_sha256(paths["restricted_primary_details"]),
        "pilot36_included": False,
        "sample_replacement": False,
        "geometry_scoring_rule": "ARRAY_INDEX_NO_RESAMPLING_E2",
        "shape_equality_required": True,
        "voxel_size_absolute_tolerance": VOXEL_SIZE_ABS_TOL,
        "affine_and_orientation_used_for_exclusion": False,
        "header_anomalies_disclosed": 5,
        "gt_resampling": False,
        "prediction_resampling": False,
        "threshold_changed": False,
        "post_hoc_subgroups_added": False,
        "effect_metrics_read": True,
        "outcome_unblinded": True,
    }
    write_json(paths["g4_summary"], summary, exclusive=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("self-test", "preflight", "run"):
        subparser = subparsers.add_parser(mode)
        subparser.add_argument("--project-root", type=Path, required=True)
        if mode == "run":
            subparser.add_argument("--resume", action="store_true")
    worker = subparsers.add_parser("worker")
    worker.add_argument("--project-root", type=Path, required=True)
    worker.add_argument("--worker-index", type=int, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    root = args.project_root.resolve()
    paths = project_paths(root)
    if args.mode == "self-test":
        return run_self_test(root, paths)
    if args.mode == "preflight":
        return run_preflight(root, paths)
    if args.mode == "worker":
        return run_worker(root, paths, args.worker_index)
    return run_formal(root, paths, args.resume)


if __name__ == "__main__":
    raise SystemExit(main())
