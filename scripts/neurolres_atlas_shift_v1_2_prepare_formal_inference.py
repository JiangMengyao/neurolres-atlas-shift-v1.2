#!/usr/bin/env python3
"""Prepare the fixed Pilot-36-excluded nnU-Net inputs for frozen v1.2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_INDEX_SHA256 = "2fe4bc3cd7e8eb91630c3900887488072c8f345f91780db57678be294903c85c"
EXPECTED_PILOT_SHA256 = "74841b0a3041df76fc8b8cae75dcdd0d2ee38d9aafe0aebeeba86f6121199828"
EXPECTED_G0_G2_SHA256 = "397c8a25b77f3efaaf6f25ee2fb8e277c99f7992e89f109d72d8a73a2ec39687"
EXPECTED_FREEZE_SHA256 = "010803fc76767eeedb157dbc7ae8df016ee0dcd2bb482c20aaf3917cd406019e"
EXPECTED_STRATA = {"R2_TEST": 288, "SOOP": 157, "R3_NEW": 317}
STRATUM_ORDER = {"R2_TEST": 0, "SOOP": 1, "R3_NEW": 2}
EXPECTED_N = 762


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_empty_or_absent(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise SystemExit(f"FAIL_NONEMPTY_TARGET: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--pilot-manifest", type=Path, required=True)
    parser.add_argument("--g0-g2-summary", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--formal-root", type=Path, required=True)
    parser.add_argument("--weights-root", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)

    expected = {
        args.index: EXPECTED_INDEX_SHA256,
        args.pilot_manifest: EXPECTED_PILOT_SHA256,
        args.g0_g2_summary: EXPECTED_G0_G2_SHA256,
        args.freeze_manifest: EXPECTED_FREEZE_SHA256,
    }
    for path, digest in expected.items():
        if sha256(path) != digest:
            raise SystemExit(f"FAIL_FROZEN_INPUT_DRIFT: {path}")

    gate = json.loads(args.g0_g2_summary.read_text(encoding="utf-8"))
    if gate.get("gates") != {"G0": True, "G1": True, "G2": True}:
        raise SystemExit("FAIL_G0_G2_NOT_PASS")
    freeze = json.loads(args.freeze_manifest.read_text(encoding="utf-8"))
    if freeze.get("status") != "V1_2_FROZEN_BEFORE_ANY_V1_2_PREDICTION":
        raise SystemExit("FAIL_FREEZE_STATUS")

    with args.index.open(newline="", encoding="utf-8-sig") as handle:
        all_rows = list(csv.DictReader(handle))
    with args.pilot_manifest.open(newline="", encoding="utf-8-sig") as handle:
        pilot_rows = list(csv.DictReader(handle))
    pilot_ids = {row["case_id"] for row in pilot_rows}
    if len(pilot_rows) != 36 or len(pilot_ids) != 36:
        raise SystemExit("FAIL_PILOT_EXCLUSION_DENOMINATOR")

    rows = [
        row
        for row in all_rows
        if row["stratum"] in EXPECTED_STRATA and row["case_id"] not in pilot_ids
    ]
    rows.sort(key=lambda row: (STRATUM_ORDER[row["stratum"]], row["case_id"]))
    counts = Counter(row["stratum"] for row in rows)
    if len(rows) != EXPECTED_N or dict(counts) != EXPECTED_STRATA:
        raise SystemExit(
            f"FAIL_FORMAL_DENOMINATOR: n={len(rows)} strata={dict(counts)}"
        )
    if any(row["case_id"] in pilot_ids for row in rows):
        raise SystemExit("FAIL_PILOT_OVERLAP")
    if len({row["case_id"] for row in rows}) != EXPECTED_N:
        raise SystemExit("FAIL_DUPLICATE_CASE_ID")

    formal_root = args.formal_root.resolve()
    inference_root = formal_root / "inference"
    input_dir = inference_root / "nnunet_input"
    output_dir = inference_root / "nnunet_output_folds0_4_no_tta"
    runtime_dir = inference_root / "runtime"
    results_folder = runtime_dir / "RESULTS_FOLDER"
    model_link = results_folder / "nnUNet" / "3d_fullres"
    raw_base = runtime_dir / "nnUNet_raw_data_base"
    preprocessed = runtime_dir / "nnUNet_preprocessed"
    mapping_path = inference_root / "restricted_token_mapping.csv"
    exclusion_path = inference_root / "restricted_pilot_exclusion_receipt.json"
    state_path = inference_root / "formal_inference_preparation_state.json"

    for path in (input_dir, output_dir):
        require_empty_or_absent(path)
    for path in (mapping_path, exclusion_path, state_path, model_link):
        if path.exists() or path.is_symlink():
            raise SystemExit(f"FAIL_PREEXISTING_ARTIFACT: {path}")

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_base.mkdir(parents=True, exist_ok=True)
    preprocessed.mkdir(parents=True, exist_ok=True)
    model_link.parent.mkdir(parents=True, exist_ok=True)

    weights_3d = args.weights_root.resolve() / "3d_fullres"
    if not weights_3d.is_dir():
        raise SystemExit(f"FAIL_WEIGHTS_LAYOUT: {weights_3d}")
    model_link.symlink_to(weights_3d, target_is_directory=True)

    mapping_rows: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        token = f"v12f{index:04d}"
        source = Path(row["t1_path"]).resolve()
        mask = Path(row["mask_path"]).resolve()
        metadata = Path(row["metadata_path"]).resolve()
        for label, path in (("T1", source), ("MASK", mask), ("METADATA", metadata)):
            if not path.is_file():
                raise SystemExit(f"FAIL_{label}_MISSING: {path}")
        input_path = input_dir / f"{token}_0000.nii.gz"
        input_path.symlink_to(source)
        mapping_rows.append(
            {
                "token": token,
                "case_id": row["case_id"],
                "stratum": row["stratum"],
                "center": row["center"],
                "t1_path": str(source),
                "mask_path": str(mask),
                "metadata_path": str(metadata),
                "nnunet_input": str(input_path.absolute()),
                "prediction_nii": str(output_dir / f"{token}.nii.gz"),
                "prediction_npz": str(output_dir / f"{token}.npz"),
                "prediction_properties": str(output_dir / f"{token}.pkl"),
            }
        )

    with mapping_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(mapping_rows[0]))
        writer.writeheader()
        writer.writerows(mapping_rows)

    exclusion = {
        "protocol_id": "NEUROLRES-ATLAS-SHIFT-v1.2",
        "pilot_manifest_sha256": EXPECTED_PILOT_SHA256,
        "pilot_n": 36,
        "formal_n": len(mapping_rows),
        "formal_counts": dict(counts),
        "pilot_formal_case_id_overlap_n": 0,
        "effect_selection_rule": "frozen effect strata minus every Pilot-36 case ID",
    }
    exclusion_path.write_text(
        json.dumps(exclusion, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    state = {
        "protocol_id": "NEUROLRES-ATLAS-SHIFT-v1.2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "V1_2_FORMAL_INPUTS_READY_NOT_STARTED",
        "freeze_manifest_sha256": EXPECTED_FREEZE_SHA256,
        "source_index_sha256": EXPECTED_INDEX_SHA256,
        "pilot_exclusion_sha256": EXPECTED_PILOT_SHA256,
        "g0_g2_summary_sha256": EXPECTED_G0_G2_SHA256,
        "n_inputs": len(mapping_rows),
        "strata": dict(counts),
        "pilot_overlap_n": 0,
        "sort_order": ["R2_TEST", "SOOP", "R3_NEW", "then case_id ascending"],
        "input_naming": "v12fNNNN_0000.nii.gz",
        "input_mode": "SYMLINK_TO_AUTHORIZED_T1_NO_IMAGE_REWRITE",
        "restricted_mapping": str(mapping_path),
        "restricted_mapping_sha256": sha256(mapping_path),
        "restricted_exclusion_receipt": str(exclusion_path),
        "restricted_exclusion_receipt_sha256": sha256(exclusion_path),
        "nnunet_input": str(input_dir),
        "nnunet_output": str(output_dir),
        "environment": {
            "RESULTS_FOLDER": str(results_folder),
            "nnUNet_raw_data_base": str(raw_base),
            "nnUNet_preprocessed": str(preprocessed),
        },
        "model_link": str(model_link),
        "model_link_target": str(weights_3d),
        "formal_contract": {
            "folds": [0, 1, 2, 3, 4],
            "probability_aggregation": "equal arithmetic mean across five folds",
            "disable_tta": True,
            "disable_mixed_precision": True,
            "save_npz": True,
            "postprocessing": "none",
        },
        "formal_inference_started": False,
        "effect_metrics_read": False,
    }
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
