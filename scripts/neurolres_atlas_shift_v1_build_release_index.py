#!/usr/bin/env python3
"""Build the frozen ATLAS R3 release index without reading image volumes.

This adapter uses only release paths, filenames, and CSV metadata. It does not
open NIfTI files, inspect masks, run a model, or calculate effect metrics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


EXPECTED = {"R2_TRAIN": 655, "R2_TEST": 300, "SOOP": 169, "R3_NEW": 329}
DATASET_TO_STRATUM = {
    "Training": "R2_TRAIN",
    "Training_ATLAS2": "R2_TRAIN",
    "Testing": "R2_TEST",
    "Testing_ATLAS2": "R2_TEST",
    "ATLAS3": "R3_NEW",
}
OUTPUT_COLUMNS = (
    "case_id",
    "stratum",
    "center",
    "t1_path",
    "mask_path",
    "metadata_path",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def one_match(parent: Path, pattern: str, case_id: str) -> Path:
    matches = sorted(parent.glob(pattern))
    if len(matches) != 1:
        raise SystemExit(
            f"FAIL_FILE_PAIRING: case={case_id} pattern={pattern} n={len(matches)}"
        )
    if not matches[0].is_file() or matches[0].stat().st_size <= 0:
        raise SystemExit(f"FAIL_EMPTY_OR_MISSING_FILE: case={case_id} path={matches[0]}")
    return matches[0].resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qc", type=Path, required=True)
    args = parser.parse_args()

    os.umask(0o077)
    root = args.root.resolve()
    metadata_files = sorted(root.rglob("*_metadata.csv"))
    if len(metadata_files) != 1453:
        raise SystemExit(
            f"FAIL_METADATA_FILE_DENOMINATOR: observed={len(metadata_files)} expected=1453"
        )

    rows: list[dict[str, str]] = []
    metadata_status: Counter[str] = Counter()
    release_values: Counter[str] = Counter()
    centers_by_stratum: dict[str, Counter[str]] = defaultdict(Counter)

    for metadata_path in metadata_files:
        relative = metadata_path.relative_to(root)
        source_dir = relative.parts[0]
        case_id = metadata_path.parents[2].name
        if not case_id.startswith("sub-"):
            raise SystemExit(f"FAIL_CASE_ID_PATH: {metadata_path}")

        with metadata_path.open(newline="", encoding="utf-8-sig") as handle:
            metadata_rows = list(csv.DictReader(handle))
        if len(metadata_rows) > 1:
            raise SystemExit(f"FAIL_MULTIPLE_METADATA_ROWS: case={case_id}")

        if source_dir == "SOOP":
            stratum = "SOOP"
            center = "SOOP"
            if metadata_rows:
                row = {key: (value or "").strip() for key, value in metadata_rows[0].items()}
                if row.get("ATLAS2_DATASET") != "ATLAS3" or row.get("SITE") != "SOOP":
                    raise SystemExit(f"FAIL_SOOP_METADATA_ASSIGNMENT: case={case_id}")
                metadata_status["SOOP_COMPLETE_ROW"] += 1
                release_values[row["ATLAS2_DATASET"]] += 1
            else:
                metadata_status["SOOP_HEADER_ONLY_ROW_INFERRED_FROM_RELEASE_DIRECTORY"] += 1
        else:
            if len(metadata_rows) != 1:
                raise SystemExit(f"FAIL_NON_SOOP_METADATA_ROW: case={case_id}")
            row = {key: (value or "").strip() for key, value in metadata_rows[0].items()}
            release_value = row.get("ATLAS2_DATASET", "")
            if release_value not in DATASET_TO_STRATUM:
                raise SystemExit(
                    f"FAIL_UNKNOWN_RELEASE_ASSIGNMENT: case={case_id} value={release_value!r}"
                )
            stratum = DATASET_TO_STRATUM[release_value]
            center = row.get("SITE", "")
            if not center or center != source_dir:
                raise SystemExit(
                    f"FAIL_CENTER_DIRECTORY_MISMATCH: case={case_id} center={center!r} source={source_dir!r}"
                )
            metadata_status["NON_SOOP_COMPLETE_ROW"] += 1
            release_values[release_value] += 1

        t1_path = one_match(
            metadata_path.parent,
            "*_space-orig_desc-brain_T1w.nii.gz",
            case_id,
        )
        mask_path = one_match(
            metadata_path.parent,
            "*_space-orig_label-lesion_desc-T1lesion_mask.nii.gz",
            case_id,
        )
        centers_by_stratum[stratum][center] += 1
        rows.append(
            {
                "case_id": case_id,
                "stratum": stratum,
                "center": center,
                "t1_path": str(t1_path),
                "mask_path": str(mask_path),
                "metadata_path": str(metadata_path.resolve()),
            }
        )

    case_ids = [row["case_id"] for row in rows]
    if len(set(case_ids)) != len(case_ids):
        raise SystemExit("FAIL_CASE_ID_UNIQUENESS")
    observed = Counter(row["stratum"] for row in rows)
    if dict(observed) != EXPECTED:
        raise SystemExit(
            f"FAIL_STRATUM_DENOMINATORS: observed={dict(observed)} expected={EXPECTED}"
        )

    rows.sort(key=lambda row: (row["stratum"], row["case_id"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    qc = {
        "protocol_id": "NEUROLRES-ATLAS-SHIFT-v1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "RELEASE_INDEX_BUILT_BEFORE_VOLUME_OR_EFFECT_READ",
        "release_root": str(root),
        "release_index": str(args.output.resolve()),
        "release_index_sha256": sha256(args.output),
        "n_cases": len(rows),
        "n_t1_files": len(rows),
        "n_mask_files": len(rows),
        "n_metadata_files": len(metadata_files),
        "strata": dict(sorted(observed.items())),
        "release_assignment_values": dict(sorted(release_values.items())),
        "metadata_status": dict(sorted(metadata_status.items())),
        "centers_by_stratum": {
            stratum: {
                "n_centers": len(counter),
                "counts": dict(sorted(counter.items())),
            }
            for stratum, counter in sorted(centers_by_stratum.items())
        },
        "nifti_header_read": False,
        "mask_volume_read": False,
        "model_output_read": False,
        "effect_metrics_read": False,
    }
    args.qc.parent.mkdir(parents=True, exist_ok=True)
    args.qc.write_text(json.dumps(qc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(qc, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
