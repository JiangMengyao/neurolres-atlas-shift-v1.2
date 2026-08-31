#!/usr/bin/env python3
"""Run the frozen v1.2 formal-output G3 completeness gate without scoring effects."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import pickletools
import re
import struct
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROTOCOL_ID = "NEUROLRES-ATLAS-SHIFT-v1.2"
EXPECTED_N = 762
EXPECTED_DENOMINATORS = {"R2_TEST": 288, "SOOP": 157, "R3_NEW": 317}
G3_MIN_RATE = 0.95
TOKEN_PATTERN = re.compile(r"^v12f\d{4}$")
EXPECTED_SHA256 = {
    "freeze_manifest": "010803fc76767eeedb157dbc7ae8df016ee0dcd2bb482c20aaf3917cd406019e",
    "formal_execution_lock": "c8973d822a5b7bec01166f08f40dfa470463834b2c2969e6cf8ade73f7222b69",
    "formal_preparation_state": "00976907d0e32fb1e5e16347e5a24ee0b1497861ef94973b25e4d4d442183783",
    "restricted_token_mapping": "3d50730735050aacb65e88634b4ca83ae2ecf43f23790f750d60e847d01d1b1d",
    "formal_runner": "a81ef92bc9eb744962f3770de2154b7785f367331c6fcca452d5a7b559accb70",
}
OUTPUT_FIELDS = {
    "nii_gz": ("prediction_nii", ".nii.gz"),
    "npz": ("prediction_npz", ".npz"),
    "pkl": ("prediction_properties", ".pkl"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_nii_gz(path: Path) -> tuple[str, int]:
    content_sha256 = sha256(path)
    decompressed_bytes = 0
    header = b""
    with gzip.open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            if len(header) < 352:
                header += chunk[: 352 - len(header)]
            decompressed_bytes += len(chunk)
    if len(header) < 348:
        raise ValueError("NIFTI_HEADER_TRUNCATED")
    little = struct.unpack("<I", header[:4])[0]
    big = struct.unpack(">I", header[:4])[0]
    if 348 not in (little, big):
        raise ValueError("NIFTI_SIZEOF_HDR_INVALID")
    if header[344:348] not in (b"n+1\x00", b"ni1\x00"):
        raise ValueError("NIFTI_MAGIC_INVALID")
    return content_sha256, decompressed_bytes


def validate_npz(path: Path) -> tuple[str, list[str]]:
    content_sha256 = sha256(path)
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if "softmax.npy" not in members:
            raise ValueError("NPZ_MISSING_SOFTMAX_NPY")
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError("NPZ_CRC_FAILURE")
    return content_sha256, members


def validate_pkl(path: Path) -> str:
    payload = path.read_bytes()
    last_opcode = None
    for opcode, _argument, _position in pickletools.genops(payload):
        last_opcode = opcode.name
    if last_opcode != "STOP":
        raise ValueError("PICKLE_STOP_MISSING")
    return hashlib.sha256(payload).hexdigest()


def latest_run_log_checks(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    starts = [match.start() for match in re.finditer(r"^run_started_or_resumed_utc=", text, re.M)]
    latest = text[starts[-1] :] if starts else ""
    completed = re.findall(r"^run_completed_utc=(.+)$", latest, re.M)
    fatal_patterns = {
        "traceback": r"Traceback \(most recent call last\):",
        "segmentation_fault": r"Segmentation fault",
        "bus_error": r"Bus error",
        "no_space": r"No space left on device",
        "out_of_memory": r"(?:out of memory|MemoryError)",
    }
    fatal_counts = {
        label: len(re.findall(pattern, latest, flags=re.I | re.M))
        for label, pattern in fatal_patterns.items()
    }
    checks = {
        "run_segment_present": bool(starts),
        "latest_run_completed_once": len(completed) == 1,
        "latest_run_completed_utc": completed[0] if len(completed) == 1 else None,
        "fixed_n_762_logged": "fixed_n=762 pilot_overlap=0" in latest,
        "locked_parameters_logged": (
            "device=CPU folds=0,1,2,3,4 tta=false mixed_precision=false save_npz=true"
            in latest
        ),
        "prediction_export_finished": (
            "inference done. Now waiting for the segmentation export to finish..." in latest
        ),
        "expected_no_postprocessing_warning_present": (
            "Cannot run postprocessing because the postprocessing file is missing" in latest
        ),
        "fatal_counts_latest_run": fatal_counts,
        "fatal_count_latest_run": sum(fatal_counts.values()),
    }
    checks["pass"] = bool(
        checks["run_segment_present"]
        and checks["latest_run_completed_once"]
        and checks["fixed_n_762_logged"]
        and checks["locked_parameters_logged"]
        and checks["prediction_export_finished"]
        and checks["fatal_count_latest_run"] == 0
    )
    return checks


def related_processes() -> list[str]:
    completed = subprocess.run(
        ["ps", "-axo", "pid=,command="],
        check=True,
        capture_output=True,
        text=True,
    )
    patterns = (
        "neurolres_atlas_shift_v1_2_run_formal_762_five_fold_no_tta.sh",
        "neurolres_atlas_shift_v1_1_predict_fork_launcher.py",
        "nnunet.inference.predict",
    )
    current_pid = os.getpid()
    matches: list[str] = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, command = stripped.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if pid == current_pid:
            continue
        if any(pattern in command for pattern in patterns):
            matches.append(f"pid={pid}")
    return matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--gate-lock", type=Path, required=True)
    parser.add_argument("--restricted-details", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)

    root = args.project_root.resolve()
    checker = Path(__file__).resolve()
    frozen_paths = {
        "freeze_manifest": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.2_freeze_manifest_20260827.json",
        "formal_execution_lock": root / "protocols/NEUROLRES_ATLAS_SHIFT_v1.2_formal_execution_lock_20260827.json",
        "formal_preparation_state": root / "data/authorized/atlas_r3/formal_v1.2/inference/formal_inference_preparation_state.json",
        "restricted_token_mapping": root / "data/authorized/atlas_r3/formal_v1.2/inference/restricted_token_mapping.csv",
        "formal_runner": root / "scripts/neurolres_atlas_shift_v1_2_run_formal_762_five_fold_no_tta.sh",
    }
    output_dir = root / "data/authorized/atlas_r3/formal_v1.2/inference/nnunet_output_folds0_4_no_tta"
    log_path = root / "data/authorized/atlas_r3/formal_v1.2/inference/logs/v1_2_formal_762_folds0_4_no_tta.log"

    gate_lock = json.loads(args.gate_lock.read_text(encoding="utf-8"))
    lock_checks = {
        "protocol_id": gate_lock.get("protocol_id") == PROTOCOL_ID,
        "artifact_role": gate_lock.get("artifact_role") == "FORMAL_762_G3_COMPLETENESS_LOCK",
        "checker_sha256": gate_lock.get("locked_sha256", {}).get("checker") == sha256(checker),
        "effect_scoring_forbidden": gate_lock.get("prohibited_access", {}).get("effect_scoring") is True,
        "ground_truth_forbidden": gate_lock.get("prohibited_access", {}).get("ground_truth") is True,
    }
    observed_hashes = {label: sha256(path) for label, path in frozen_paths.items()}
    frozen_hash_checks = {
        label: observed_hashes[label] == expected
        for label, expected in EXPECTED_SHA256.items()
    }
    lock_hash_checks = {
        label: gate_lock.get("locked_sha256", {}).get(label) == expected
        for label, expected in EXPECTED_SHA256.items()
    }

    mapping_path = frozen_paths["restricted_token_mapping"]
    with mapping_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = set(reader.fieldnames or [])
    required_fields = {"token", "stratum", *[field for field, _ext in OUTPUT_FIELDS.values()]}
    denominators = Counter(row.get("stratum", "") for row in rows)
    tokens = [row.get("token", "") for row in rows]
    mapping_checks = {
        "required_fields_present": required_fields.issubset(fieldnames),
        "n_exact": len(rows) == EXPECTED_N,
        "tokens_unique": len(set(tokens)) == EXPECTED_N,
        "tokens_valid": all(TOKEN_PATTERN.fullmatch(token) for token in tokens),
        "denominators_exact": dict(denominators) == EXPECTED_DENOMINATORS,
    }

    expected_paths: dict[str, set[Path]] = {label: set() for label in OUTPUT_FIELDS}
    mapping_path_mismatches = 0
    for row in rows:
        token = row["token"]
        for label, (mapping_field, extension) in OUTPUT_FIELDS.items():
            expected = (output_dir / f"{token}{extension}").resolve()
            expected_paths[label].add(expected)
            if Path(row[mapping_field]).resolve() != expected:
                mapping_path_mismatches += 1

    observed_paths = {
        "nii_gz": {path.resolve() for path in output_dir.glob("v12f*.nii.gz")},
        "npz": {path.resolve() for path in output_dir.glob("v12f*.npz")},
        "pkl": {path.resolve() for path in output_dir.glob("v12f*.pkl")},
    }
    set_checks: dict[str, object] = {
        "mapping_path_mismatches": mapping_path_mismatches,
        "temporary_file_count": sum(
            1
            for path in output_dir.iterdir()
            if path.is_file()
            and (
                path.name.endswith((".tmp", ".part", ".partial"))
                or path.name.startswith(".") and path.name.endswith(".tmp")
            )
        ),
    }
    for label in OUTPUT_FIELDS:
        set_checks[f"{label}_observed"] = len(observed_paths[label])
        set_checks[f"{label}_missing"] = len(expected_paths[label] - observed_paths[label])
        set_checks[f"{label}_unexpected"] = len(observed_paths[label] - expected_paths[label])

    case_records: list[dict[str, object]] = []
    success_by_stratum: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    triplet_manifest_digest = hashlib.sha256()
    for index, row in enumerate(rows, start=1):
        token = row["token"]
        stratum = row["stratum"]
        record: dict[str, object] = {"token": token, "stratum": stratum}
        failures: list[str] = []
        file_hashes: dict[str, str] = {}
        file_sizes: dict[str, int] = {}

        for label, (_mapping_field, extension) in OUTPUT_FIELDS.items():
            path = output_dir / f"{token}{extension}"
            present_nonempty = path.is_file() and path.stat().st_size > 0
            record[f"{label}_present_nonempty"] = present_nonempty
            if not present_nonempty:
                failures.append(f"{label.upper()}_MISSING_OR_EMPTY")
                continue
            file_sizes[label] = path.stat().st_size
            try:
                if label == "nii_gz":
                    digest, decompressed_bytes = validate_nii_gz(path)
                    record["nii_gz_decompressed_bytes"] = decompressed_bytes
                elif label == "npz":
                    digest, members = validate_npz(path)
                    record["npz_members"] = members
                else:
                    digest = validate_pkl(path)
                file_hashes[label] = digest
                record[f"{label}_container_valid"] = True
            except Exception as error:  # Continue to report all case-level failures.
                record[f"{label}_container_valid"] = False
                record[f"{label}_exception_type"] = type(error).__name__
                failures.append(f"{label.upper()}_CONTAINER_INVALID")

        case_pass = not failures
        record["file_sizes"] = file_sizes
        record["file_sha256"] = file_hashes
        record["failure_codes"] = failures
        record["g3_case_pass"] = case_pass
        case_records.append(record)
        if case_pass:
            success_by_stratum[stratum] += 1
        for failure in failures:
            failure_counts[failure] += 1
        for label in sorted(file_hashes):
            triplet_manifest_digest.update(
                f"{token}\t{stratum}\t{label}\t{file_sizes[label]}\t{file_hashes[label]}\n".encode()
            )
        if index % 50 == 0 or index == EXPECTED_N:
            print(f"validated_cases={index}/{EXPECTED_N}", flush=True)

    rates = {
        stratum: success_by_stratum[stratum] / denominator
        for stratum, denominator in EXPECTED_DENOMINATORS.items()
    }
    log_checks = latest_run_log_checks(log_path)
    active_processes = related_processes()
    structural_pass = bool(
        all(lock_checks.values())
        and all(frozen_hash_checks.values())
        and all(lock_hash_checks.values())
        and all(mapping_checks.values())
        and mapping_path_mismatches == 0
        and set_checks["temporary_file_count"] == 0
        and all(set_checks[f"{label}_missing"] == 0 for label in OUTPUT_FIELDS)
        and all(set_checks[f"{label}_unexpected"] == 0 for label in OUTPUT_FIELDS)
        and log_checks["pass"]
        and not active_processes
    )
    g3_pass = bool(
        structural_pass
        and all(rates[stratum] >= G3_MIN_RATE for stratum in EXPECTED_DENOMINATORS)
    )

    details = {
        "protocol_id": PROTOCOL_ID,
        "artifact_role": "FORMAL_762_G3_RESTRICTED_DETAILS",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate_lock_sha256": sha256(args.gate_lock),
        "checker_sha256": sha256(checker),
        "lock_checks": lock_checks,
        "observed_frozen_sha256": observed_hashes,
        "frozen_hash_checks": frozen_hash_checks,
        "lock_hash_checks": lock_hash_checks,
        "mapping_checks": mapping_checks,
        "denominators": dict(sorted(denominators.items())),
        "set_checks": set_checks,
        "log_checks": log_checks,
        "related_process_count": len(active_processes),
        "related_processes": active_processes,
        "success_by_stratum": dict(sorted(success_by_stratum.items())),
        "success_rates": rates,
        "failure_counts": dict(sorted(failure_counts.items())),
        "triplet_content_manifest_sha256": triplet_manifest_digest.hexdigest(),
        "case_records": case_records,
        "ground_truth_accessed": False,
        "effect_metrics_read": False,
        "probability_values_interpreted": False,
    }
    args.restricted_details.parent.mkdir(parents=True, exist_ok=True)
    args.restricted_details.write_text(
        json.dumps(details, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = {
        "protocol_id": PROTOCOL_ID,
        "artifact_role": "FORMAL_762_G3_COMPLETENESS_SUMMARY",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "G3_PASS" if g3_pass else "G3_FAIL_STOP",
        "fixed_n": EXPECTED_N,
        "threshold": G3_MIN_RATE,
        "denominators": EXPECTED_DENOMINATORS,
        "successful_triplets_by_stratum": dict(sorted(success_by_stratum.items())),
        "success_rates": rates,
        "total_successful_triplets": sum(success_by_stratum.values()),
        "total_failed_triplets": EXPECTED_N - sum(success_by_stratum.values()),
        "failure_counts": dict(sorted(failure_counts.items())),
        "exact_output_set_pass": bool(
            mapping_path_mismatches == 0
            and set_checks["temporary_file_count"] == 0
            and all(set_checks[f"{label}_missing"] == 0 for label in OUTPUT_FIELDS)
            and all(set_checks[f"{label}_unexpected"] == 0 for label in OUTPUT_FIELDS)
        ),
        "container_integrity_pass": not failure_counts,
        "frozen_hashes_pass": all(frozen_hash_checks.values()) and all(lock_hash_checks.values()),
        "latest_run_log_pass": log_checks["pass"],
        "latest_run_completed_utc": log_checks["latest_run_completed_utc"],
        "expected_no_postprocessing_warning_present": log_checks[
            "expected_no_postprocessing_warning_present"
        ],
        "related_process_count": len(active_processes),
        "triplet_content_manifest_sha256": triplet_manifest_digest.hexdigest(),
        "gate_lock_sha256": sha256(args.gate_lock),
        "checker_sha256": sha256(checker),
        "restricted_details": str(args.restricted_details.resolve()),
        "restricted_details_sha256": sha256(args.restricted_details),
        "ground_truth_accessed": False,
        "effect_metrics_read": False,
        "probability_values_interpreted": False,
        "failure_action": (
            "NONE_G3_PASS_G4_REMAINS_SEPARATELY_AUTHORIZED"
            if g3_pass
            else "STOP_PRESERVE_OUTPUTS_DO_NOT_SCORE_G4"
        ),
        "next_permitted_action": (
            "G4_EFFECT_SCORING_ONLY_AFTER_SEPARATE_AUTHORIZATION"
            if g3_pass
            else "NO_G4"
        ),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if g3_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
