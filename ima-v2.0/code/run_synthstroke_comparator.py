#!/usr/bin/env python3
"""Run the outcome-blinded SynthStroke-synth feasibility or formal inference."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
import pickle
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import nibabel as nib
import numpy as np
import torch
import monai as mn
from monai.data import MetaTensor


ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "models/vendor/SynthStroke"
sys.path.insert(0, str(VENDOR))

from synthstroke_model import InferenceConfig, SynthStrokeModel  # noqa: E402


MAPPING = ROOT / "data/authorized/atlas_r3/formal_v1.2/inference/restricted_token_mapping.csv"
LOCK = ROOT / "protocols/IMA_UPGRADE_v2.0_exploratory_SynthStroke_lock_E2_20260929.json"
STORAGE_LOCK = ROOT / "protocols/IMA_UPGRADE_v2.0_SynthStroke_formal_storage_lock_E3_20260929.json"
PARALLEL_LOCK = ROOT / "protocols/IMA_UPGRADE_v2.0_SynthStroke_parallel_execution_E5_20260929.json"
WEIGHT_ROOT = ROOT / "models/weights/SynthStroke-synth-2025"
WEIGHTS = WEIGHT_ROOT / "model.safetensors"
CONFIG = WEIGHT_ROOT / "config.json"
OUTPUT_ROOT = ROOT / "data/authorized/atlas_r3/formal_v1.2/comparators/synthstroke"
RESULT_ROOT = ROOT / "results/ima_upgrade_20260929"
PILOT_TOKENS = ("v12f0001", "v12f0289", "v12f0446")
EXPECTED_MAPPING_SHA256 = "3d50730735050aacb65e88634b4ca83ae2ecf43f23790f750d60e847d01d1b1d"
EXPECTED_VENDOR_COMMIT = "f627b57b8f9291bfa870cb54cb21ddbeb4941d39"
EXPECTED_HF_REVISION = "ced72e683ed68d3d110b675714e1a07bac584948"
PATCH_SIZE = 192


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_mapping() -> list[dict[str, str]]:
    if sha256(MAPPING) != EXPECTED_MAPPING_SHA256:
        raise SystemExit("formal mapping drift")
    with MAPPING.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 762:
        raise SystemExit("formal denominator drift")
    return rows


def git_commit() -> str:
    import subprocess

    return subprocess.check_output(["git", "-C", str(VENDOR), "rev-parse", "HEAD"], text=True).strip()


def weight_receipt() -> dict[str, object]:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if lock.get("protocol_extension_id") != "IMA-UPGRADE-v2.0-E2-SynthStroke-exploratory":
        raise SystemExit("SynthStroke extension lock drift")
    if not STORAGE_LOCK.is_file():
        raise SystemExit("missing SynthStroke storage lock")
    parallel_lock = json.loads(PARALLEL_LOCK.read_text(encoding="utf-8"))
    if parallel_lock.get("runner_sha256") != sha256(Path(__file__).resolve()):
        raise SystemExit("SynthStroke runner drift")
    if git_commit() != EXPECTED_VENDOR_COMMIT:
        raise SystemExit("SynthStroke vendor commit drift")
    for path in (WEIGHTS, CONFIG):
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"missing SynthStroke artifact: {path}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config.get("model_type") != "synth" or config.get("out_channels") != 6:
        raise SystemExit(f"unexpected SynthStroke configuration: {config}")
    return {
        "model_id": "liamchalcroft/synthstroke-synth",
        "hugging_face_revision": EXPECTED_HF_REVISION,
        "vendor_commit": EXPECTED_VENDOR_COMMIT,
        "model_sha256": sha256(WEIGHTS),
        "config_sha256": sha256(CONFIG),
        "config": config,
    }


def build_preprocessing() -> mn.transforms.Compose:
    return mn.transforms.Compose(
        [
            mn.transforms.LoadImaged(keys=["img"], image_only=False),
            mn.transforms.EnsureChannelFirstd(keys=["img"]),
            mn.transforms.Orientationd(keys=["img"], axcodes="RAS"),
            mn.transforms.Spacingd(keys=["img"], pixdim=(1.0, 1.0, 1.0), mode="bilinear"),
            mn.transforms.HistogramNormalized(keys=["img"]),
            mn.transforms.NormalizeIntensityd(keys=["img"], nonzero=False, channel_wise=True),
        ]
    )


def inverse_probabilities(
    probabilities: torch.Tensor,
    processed: MetaTensor,
    preprocessing: mn.transforms.Compose,
) -> np.ndarray:
    tensor = MetaTensor(
        probabilities.detach().cpu(),
        affine=processed.affine.detach().cpu().clone(),
        meta=copy.deepcopy(processed.meta),
        applied_operations=copy.deepcopy(processed.applied_operations),
    )
    inverse = preprocessing.inverse({"img": tensor})["img"]
    array = inverse.detach().cpu().numpy().astype(np.float32)
    if array.ndim != 4 or array.shape[0] != 6 or not np.isfinite(array).all():
        raise ValueError(f"invalid inverse probability array: {array.shape}")
    array = np.clip(array, 0.0, 1.0)
    denominator = np.sum(array, axis=0, keepdims=True)
    array = array / np.maximum(denominator, 1e-7)
    return array


def save_case(
    row: dict[str, str],
    model: SynthStrokeModel,
    preprocessing: mn.transforms.Compose,
    output_dir: Path,
) -> dict[str, object]:
    token = row["token"]
    target_nii = output_dir / f"{token}.nii.gz"
    target_npz = output_dir / f"{token}.npz"
    target_pkl = output_dir / f"{token}.pkl"
    if all(path.is_file() and path.stat().st_size > 0 for path in (target_nii, target_npz, target_pkl)):
        return {"token": token, "status": "SKIPPED_COMPLETE"}

    started = time.monotonic()
    source_image = nib.load(row["t1_path"])
    batch = preprocessing({"img": row["t1_path"]})
    processed = batch["img"]
    if not isinstance(processed, MetaTensor) or processed.ndim != 4:
        raise ValueError("preprocessing did not produce a tracked 4D MetaTensor")
    input_tensor = processed.unsqueeze(0).to(model.device)
    inference = InferenceConfig(
        apply_softmax=True,
        use_tta=False,
        use_sliding_window=True,
        patch_size=PATCH_SIZE,
        use_mc_dropout=False,
    )
    result = model.predict_comprehensive(input_tensor, config=inference)
    probabilities = result.probabilities
    if probabilities is None or probabilities.shape[0] != 1:
        raise ValueError("SynthStroke did not return probabilities")
    native_probabilities = inverse_probabilities(probabilities[0], processed, preprocessing)
    if tuple(native_probabilities.shape[1:]) != tuple(source_image.shape):
        raise ValueError(
            f"inverse shape mismatch {native_probabilities.shape[1:]} != {source_image.shape}"
        )
    lesion_probability_xyz = native_probabilities[5]
    prediction_xyz = (np.argmax(native_probabilities, axis=0) == 5).astype(np.uint8)
    header = source_image.header.copy()
    header.set_data_dtype(np.uint8)
    nib.save(nib.Nifti1Image(prediction_xyz, source_image.affine, header), str(target_nii))

    lesion_probability_zyx = np.transpose(lesion_probability_xyz, (2, 1, 0))
    np.savez_compressed(target_npz, foreground=lesion_probability_zyx.astype(np.float16))
    properties = {
        "original_size_of_raw_data": list(lesion_probability_zyx.shape),
        "crop_bbox": None,
        "source_model": "liamchalcroft/synthstroke-synth",
        "probability_storage": "single foreground channel float16; no spatial crop",
        "preprocessing": "RAS orientation; 1-mm spacing; histogram normalization; whole-volume intensity normalization; inverse to native space",
        "binary_prediction_rule": "argmax across six native-space interpolated class probabilities equals stroke class 5",
    }
    with target_pkl.open("wb") as handle:
        pickle.dump(properties, handle, protocol=pickle.HIGHEST_PROTOCOL)
    del input_tensor, probabilities, native_probabilities, result
    elapsed = time.monotonic() - started
    return {
        "token": token,
        "status": "PASS",
        "source_shape_xyz": list(source_image.shape),
        "processed_shape_cxyz": list(processed.shape),
        "elapsed_seconds": elapsed,
        "files": {
            "nii_gz": {"size": target_nii.stat().st_size, "sha256": sha256(target_nii)},
            "npz": {"size": target_npz.stat().st_size, "sha256": sha256(target_npz)},
            "pkl": {"size": target_pkl.stat().st_size, "sha256": sha256(target_pkl)},
        },
    }


def output_state(output_dir: Path, expected: int) -> dict[str, object]:
    counts = {
        "nii": len(list(output_dir.glob("v12f*.nii.gz"))),
        "npz": len(list(output_dir.glob("v12f*.npz"))),
        "pkl": len(list(output_dir.glob("v12f*.pkl"))),
    }
    return {**counts, "expected": expected, "complete": counts == {"nii": expected, "npz": expected, "pkl": expected}}


def selected_state(output_dir: Path, rows: list[dict[str, str]]) -> dict[str, object]:
    missing = []
    for row in rows:
        token = row["token"]
        paths = [output_dir / f"{token}{suffix}" for suffix in (".nii.gz", ".npz", ".pkl")]
        if not all(path.is_file() and path.stat().st_size > 0 for path in paths):
            missing.append(token)
    return {"expected": len(rows), "missing_n": len(missing), "complete": not missing}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pilot", "full"), required=True)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        raise SystemExit("invalid shard specification")
    if args.threads < 1 or args.threads > 8:
        raise SystemExit("threads must be between 1 and 8")
    if args.mode == "pilot" and args.shard_count != 1:
        raise SystemExit("pilot mode does not support sharding")
    os.environ.setdefault("PYTHONHASHSEED", "0")
    torch.set_num_threads(args.threads)
    rows = read_mapping()
    if args.mode == "pilot":
        selected = [row for row in rows if row["token"] in PILOT_TOKENS]
    else:
        selected = [row for index, row in enumerate(rows) if index % args.shard_count == args.shard_index]
    expected = len(selected)
    output_dir = OUTPUT_ROOT / f"{args.mode}_output_no_tta"
    output_dir.mkdir(parents=True, exist_ok=True)
    record = weight_receipt()
    started = utc_now()
    model = SynthStrokeModel.from_checkpoint(str(WEIGHTS)).to("cpu")
    model.eval()
    preprocessing = build_preprocessing()
    case_records = []
    for index, row in enumerate(selected, start=1):
        result = save_case(row, model, preprocessing, output_dir)
        case_records.append(result)
        print(json.dumps({"index": index, "expected": expected, **result}, ensure_ascii=False), flush=True)
    state = selected_state(output_dir, selected)
    global_state = output_state(output_dir, 762 if args.mode == "full" else expected)
    receipt = {
        "protocol_extension": "IMA-UPGRADE-v2.0-E2-SynthStroke-exploratory",
        "status": "PASS" if state["complete"] else "FAIL_STOP",
        "mode": args.mode,
        "started_utc": started,
        "finished_utc": utc_now(),
        "input_n": expected,
        "state": state,
        "global_state": global_state,
        "shard": {"index": args.shard_index, "count": args.shard_count},
        "weight_provenance": record,
        "settings": {
            "device": "cpu",
            "torch_threads": args.threads,
            "patch_size": PATCH_SIZE,
            "spacing_mm": [1.0, 1.0, 1.0],
            "tta": False,
            "mc_dropout": False,
            "postprocessing": "none",
            "native_binary_rule": "argmax across six class probabilities equals stroke class 5",
        },
        "ground_truth_access": False,
        "effect_scoring": False,
        "case_records": case_records,
    }
    receipt_name = f"{args.mode}_receipt.json" if args.shard_count == 1 else f"{args.mode}_shard{args.shard_index}of{args.shard_count}_receipt.json"
    receipt_path = OUTPUT_ROOT / receipt_name
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.mode == "pilot":
        RESULT_ROOT.mkdir(parents=True, exist_ok=True)
        (RESULT_ROOT / "synthstroke_feasibility_receipt.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({"receipt": str(receipt_path), "status": receipt["status"]}, indent=2))
    return 0 if state["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
