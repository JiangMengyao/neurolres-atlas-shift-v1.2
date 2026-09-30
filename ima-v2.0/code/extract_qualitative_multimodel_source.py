#!/usr/bin/env python3
"""Extract structured, restricted slice data for the R-only qualitative figure."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import nibabel as nib
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "投稿版_IMA_升级版_20260929"
SELECTION = PACKAGE / "04_补充材料/Figure_4_source_data.csv"
RECEIPT = PACKAGE / "04_补充材料/Figure_4_build_receipt.json"
MAPPING = ROOT / "data/authorized/atlas_r3/formal_v1.2/inference/restricted_token_mapping.csv"
CASE_METRICS = ROOT / "data/authorized/atlas_r3/formal_v1.2/upgrade_v2/IMA_UPGRADE_v2_multimodel_case_metrics_uncertainty.csv"
RESTRICTED_PIXELS = ROOT / "data/authorized/atlas_r3/formal_v1.2/upgrade_v2/Figure_4_multimodel_restricted_pixels.csv"
PUBLIC_METRICS = PACKAGE / "02_图/Figure_4_multimodel_source_data.csv"
PUBLIC_METADATA = PACKAGE / "02_图/Figure_4_multimodel_panel_metadata.csv"

PREDICTION_DIRS = {
    "Default nnU-Net": ROOT / "data/authorized/atlas_r3/formal_v1.2/inference/nnunet_output_folds0_4_no_tta",
    "SynthStroke (2025)": ROOT / "data/authorized/atlas_r3/formal_v1.2/comparators/synthstroke/full_output_no_tta",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def canonical_array(path: Path) -> tuple[nib.Nifti1Image, np.ndarray]:
    image = nib.as_closest_canonical(nib.load(str(path)))
    return image, np.asanyarray(image.dataobj)


def normalize_t1(array: np.ndarray) -> np.ndarray:
    finite = array[np.isfinite(array) & (array != 0)]
    if finite.size == 0:
        raise ValueError("empty T1")
    low, high = np.percentile(finite, [1.0, 99.5])
    return np.clip((array - low) / (high - low), 0, 1)


def main() -> int:
    selected = read_csv(SELECTION)
    mapping = {row["token"]: row for row in read_csv(MAPPING)}
    metrics = read_csv(CASE_METRICS)
    metrics_by_key = {(row["token"], row["model_label"]): row for row in metrics}
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    render_by_token = {row["token"]: row for row in receipt["render_records"]}
    if len(selected) != 6:
        raise SystemExit("qualitative selection denominator drift")

    pixel_rows: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    metadata_rows: list[dict[str, object]] = []
    for selection in selected:
        token = selection["token"]
        map_row = mapping[token]
        render = render_by_token[token]
        t1_img, t1 = canonical_array(Path(map_row["t1_path"]))
        _, gt = canonical_array(Path(map_row["mask_path"]))
        predictions = {}
        for label, directory in PREDICTION_DIRS.items():
            _, prediction = canonical_array(directory / f"{token}.nii.gz")
            predictions[label] = prediction > 0.5
        if any(array.shape != t1.shape for array in [gt, *predictions.values()]):
            raise ValueError(f"canonical shape mismatch for {token}")
        z = int(render["slice_index_ras_axial"])
        x0, x1, y0, y1 = (int(value) for value in render["zoom_box_pre_rotation"])
        intensity = np.rot90(normalize_t1(t1)[:, :, z][x0:x1, y0:y1])
        truth = np.rot90((gt[:, :, z] > 0.5)[x0:x1, y0:y1])
        pred_slices = {
            label: np.rot90(array[:, :, z][x0:x1, y0:y1])
            for label, array in predictions.items()
        }
        case_label = selection["case_label"].lower()
        for y in range(intensity.shape[0]):
            for x in range(intensity.shape[1]):
                pixel_rows.append(
                    {
                        "case_label": case_label,
                        "token": token,
                        "x": x,
                        "y": y,
                        "intensity": float(intensity[y, x]),
                        "ground_truth": int(truth[y, x]),
                        "default": int(pred_slices["Default nnU-Net"][y, x]),
                        "synthstroke": int(pred_slices["SynthStroke (2025)"][y, x]),
                    }
                )
        metadata_rows.append(
            {
                "case_label": case_label,
                "token": token,
                "stratum": selection["stratum"],
                "lesion_band": selection["band"],
                "gt_volume_ml": selection["gt_volume_ml"],
                "slice_index_ras_axial": z,
                "crop_width_pixels": intensity.shape[1],
                "crop_height_pixels": intensity.shape[0],
                "horizontal_pixel_size_mm": float(t1_img.header.get_zooms()[0]),
                "selection_sha256": selection["selection_sha256"],
            }
        )
        for label in PREDICTION_DIRS:
            row = metrics_by_key[(token, label)]
            metric_rows.append(
                {
                    "case_label": case_label,
                    "stratum": selection["stratum"],
                    "lesion_band": selection["band"],
                    "gt_volume_ml": selection["gt_volume_ml"],
                    "model": label,
                    "dice": row["dice"],
                    "lesion_f1": row["lesion_f1"],
                }
            )

    write_csv(RESTRICTED_PIXELS, pixel_rows)
    write_csv(PUBLIC_METRICS, metric_rows)
    write_csv(PUBLIC_METADATA, metadata_rows)
    result = {
        "status": "PASS",
        "selected_n": len(selected),
        "restricted_pixel_rows": len(pixel_rows),
        "public_metric_rows": len(metric_rows),
        "restricted_pixels": str(RESTRICTED_PIXELS),
        "public_metrics": str(PUBLIC_METRICS),
        "public_metadata": str(PUBLIC_METADATA),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
