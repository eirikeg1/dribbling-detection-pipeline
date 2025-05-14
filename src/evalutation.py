from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

ROOT = Path(__file__).resolve().parent
PRED_ROOT = Path("/home/eirik/Projects/data/soccernet-gs-predictions/formatted-predictions")
GOLD_ROOT = Path("/home/eirik/Projects/data/SoccerNetGS/train-mod")

# merge these into "player" for BOTH GT and predictions
CLASS_ALIAS = {
    "referee": "player",
    "other": "player",
    "goalkeeper": "player",
}

Space = str  # "image" | "pitch"
Box = Tuple[float, float, float, float]


# ───────────────────────────── bbox helpers ─────────────────────────────

def _xywh_from_image(b: dict) -> Box:
    # always trust explicit (x, y, w, h)
    return b["x"], b["y"], b["w"], b["h"]


def _xywh_from_pitch(b: dict) -> Box:
    xs = [b[k] for k in ("x_bottom_left", "x_bottom_middle", "x_bottom_right")]
    ys = [b[k] for k in ("y_bottom_left", "y_bottom_middle", "y_bottom_right")]
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def _collect_bbox(ann: dict, which: Space) -> Box | None:
    if which == "image":
        bb = ann.get("bbox_image")
        return _xywh_from_image(bb) if bb else None
    bb = ann.get("bbox_pitch")
    return _xywh_from_pitch(bb) if bb else None


# ─────────────────────── COCO‑compatible construction ──────────────────────

def _make_coco_datasets(pred_path: Path, gold_path: Path, which: Space):
    """Return (coco_gt, results, class_names).
    Images are joined by *file_name* so ID mismatches are harmless.
    Alias mapping collapses categories *before* the categories list is built
    so only canonical classes appear.
    """
    gt_raw = json.loads(gold_path.read_text())
    dt_raw = json.loads(pred_path.read_text())

    def _canon(nm: str) -> str:  # canonical class name
        return CLASS_ALIAS.get(nm, nm)

    names = sorted({_canon(c["name"]) for c in gt_raw["categories"]} |
                   {_canon(c["name"]) for c in dt_raw["categories"]})
    cat2id = {nm: i + 1 for i, nm in enumerate(names)}
    categories = [{"id": cid, "name": nm, "supercategory": "object"} for nm, cid in cat2id.items()]

    # map image‑id → file_name for both jsons
    fname_by_id_gt = {img.get("image_id", img.get("id")): img["file_name"] for img in gt_raw["images"]}
    fname_by_id_dt = {img.get("image_id", img.get("id")): img["file_name"] for img in dt_raw["images"]}

    all_fnames = sorted(set(fname_by_id_gt.values()) | set(fname_by_id_dt.values()))
    fname2int = {fn: i + 1 for i, fn in enumerate(all_fnames)}

    # choose one record per file_name, prefer one that has height/width
    img_meta: Dict[str, dict] = {}
    for src_img in gt_raw["images"] + dt_raw["images"]:
        fn = src_img["file_name"]
        if fn not in img_meta or (src_img.get("height") and src_img.get("width")):
            img_meta[fn] = {
                "id": fname2int[fn],
                "file_name": fn,
                "height": src_img.get("height", 0),
                "width": src_img.get("width", 0),
            }
    images = list(img_meta.values())

    # annotations
    gt_anns, dt_results = [], []
    ann_id = 1
    for ann in gt_raw["annotations"]:
        bbox = _collect_bbox(ann, which)
        if bbox is None:
            continue
        fn = fname_by_id_gt[ann["image_id"]]
        gt_anns.append({
            "id": ann_id,
            "image_id": fname2int[fn],
            "category_id": cat2id[_canon(next(c["name"] for c in gt_raw["categories"] if c["id"] == ann["category_id"]))],
            "bbox": list(map(float, bbox)),
            "area": float(bbox[2] * bbox[3]),
            "iscrowd": 0,
        })
        ann_id += 1

    for ann in dt_raw["annotations"]:
        bbox = _collect_bbox(ann, which)
        if bbox is None:
            continue
        fn = fname_by_id_dt[ann["image_id"]]
        dt_results.append({
            "image_id": fname2int[fn],
            "category_id": cat2id[_canon(next(c["name"] for c in dt_raw["categories"] if c["id"] == ann["category_id"]))],
            "bbox": list(map(float, bbox)),
            "score": float(ann.get("score", 1.0)),
        })

    coco_gt = COCO()
    coco_gt.dataset = {"images": images, "annotations": gt_anns, "categories": categories}
    coco_gt.createIndex()
    
    # sanity counters (printed only once per call)
    missing_img = sum(ann["image_id"] not in fname_by_id_dt for ann in dt_raw["annotations"])
    bbox_only   = sum("bbox" in ann and not ann.get("bbox_image") and not ann.get("bbox_pitch")
                    for ann in dt_raw["annotations"])
    if missing_img or bbox_only:
        print(f"[WARN] {pred_path.parent.name}: "
            f"{missing_img} dt anns lack image entry, "
            f"{bbox_only} use plain 'bbox'")


    return coco_gt, dt_results, names


# ───────────────────────── evaluation for one space ─────────────────────────

def _eval_space(pred_path: Path, gold_path: Path, which: Space) -> Dict[str, Tuple[float, float]]:
    coco_gt, results, names = _make_coco_datasets(pred_path, gold_path, which)
    if not results:
        return {n: (0.0, 0.0) for n in names}

    coco_dt = coco_gt.loadRes(results)
    eva = COCOeval(coco_gt, coco_dt, iouType="bbox")
    eva.evaluate()
    eva.accumulate()

    precisions = eva.eval["precision"]  # T x R x K x A x M
    ap_per_class: Dict[str, Tuple[float, float]] = {}
    for k, cid in enumerate(coco_gt.getCatIds()):
        p = precisions[:, :, k, 0, 2]
        valid = p > -1
        mAP = float(np.mean(p[valid])) if np.any(valid) else 0.0
        # AP@0.50 is slice [0, ...]
        p50 = p[0]
        ap50 = float(np.mean(p50[p50 > -1])) if np.any(p50 > -1) else 0.0
        ap_per_class[coco_gt.loadCats(cid)[0]["name"]] = (mAP, ap50)
    return ap_per_class


# ─────────────────────────── per‑clip evaluation ───────────────────────────

def evaluate_clip_coco(clip_dir: Path) -> Dict[str, Dict[Space, Tuple[float, float]]]:
    pred_json = clip_dir / "Labels-GameState.json"
    gold_json = GOLD_ROOT / clip_dir.relative_to(PRED_ROOT) / "Labels-GameState.json"
    if not gold_json.exists():
        return {}

    img_scores = _eval_space(pred_json, gold_json, "image")
    pitch_scores = _eval_space(pred_json, gold_json, "pitch")

    classes = img_scores.keys() | pitch_scores.keys()
    return {cls: {"image": img_scores.get(cls, (0.0, 0.0)),
                  "pitch": pitch_scores.get(cls, (0.0, 0.0))}
            for cls in classes}


# ────────────────────────────── CLI / main ────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="COCO mAP@0.50‑0.95 and AP@0.50 evaluation for SoccerNet‑GS",
    )
    parser.add_argument("--debug", action="store_true", help="Print GT/DT counts per clip")
    args = parser.parse_args()

    totals: Dict[str, List[float]] = {}
    n_clips = 0

    for pred_json in PRED_ROOT.rglob("Labels-GameState.json"):
        clip_dir = pred_json.parent
        clip_scores = evaluate_clip_coco(clip_dir)

        if args.debug:
            pred_cnt = sum(bool(j.get("bbox_image")) or bool(j.get("bbox_pitch")) for j in json.loads(pred_json.read_text())["annotations"])
            gold_cnt = sum(bool(j.get("bbox_image")) or bool(j.get("bbox_pitch")) for j in json.loads((GOLD_ROOT / clip_dir.relative_to(PRED_ROOT) / "Labels-GameState.json").read_text())["annotations"])
            print(f"{clip_dir.name}: GT boxes={gold_cnt}, DT boxes={pred_cnt}")

        for cls, sc in clip_scores.items():
            totals.setdefault(cls, [0.0, 0.0, 0.0, 0.0])
            totals[cls][0] += sc["image"][0]
            totals[cls][1] += sc["image"][1]
            totals[cls][2] += sc["pitch"][0]
            totals[cls][3] += sc["pitch"][1]
        n_clips += 1

    if n_clips == 0:
        print("No prediction clips found.")
        return

    print(f"Evaluated {n_clips} clips")
    header = f"{'Class':12} |  mAP(img)  AP50(img) |  mAP(pitch)  AP50(pitch)"
    print(header)
    print("-" * len(header))
    for cls, (m_i, p50_i, m_p, p50_p) in sorted(totals.items()):
        print(f"{cls:12} |   {m_i / n_clips:.4f}     {p50_i / n_clips:.4f} |   {m_p / n_clips:.4f}      {p50_p / n_clips:.4f}")


if __name__ == "__main__":
    main()