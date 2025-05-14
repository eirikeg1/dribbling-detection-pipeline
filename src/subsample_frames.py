#!/usr/bin/env python3
"""
subsample_frames.py - make a sparse copy of the dataset, keeping only every
`frame_interval`-th entry **as they appear in Labels-GameState.json**.

The output is compatible with restore_frames_and_reindex.py.
"""

from __future__ import annotations
import argparse
import json
import shutil
import copy
from pathlib import Path
from typing import Dict, List


# ───────────────────────── helpers ──────────────────────────
def padding(img_dir: Path) -> int:
    """Guess zero-padding from the first jpg name (default 6)."""
    for f in sorted(img_dir.glob("*.jpg")):
        return len(f.stem)
    return 6


def write_subsampled_json(
    src_json: Path,
    dst_json: Path,
    keep_map: Dict[int, int],
    kept_count: int,
) -> None:
    """Clone JSON, keep only frames in keep_map and re-index them."""
    with src_json.open(encoding="utf-8") as f:
        data = json.load(f)

    ext = data["info"].get("im_ext", ".jpg")

    # Images
    new_images = []
    for img in data["images"]:
        old_id = int(img["image_id"])
        if old_id not in keep_map:
            continue
        img_cp              = copy.deepcopy(img)
        new_idx             = keep_map[old_id]
        img_cp["image_id"]  = f"{new_idx:06d}"
        img_cp["file_name"] = f"{new_idx:06d}{ext}"
        new_images.append(img_cp)
    data["images"] = new_images

    # Annotations
    new_anns = []
    for ann in data["annotations"]:
        old_id = int(ann["image_id"])
        if old_id not in keep_map:
            continue
        ann_cp             = copy.deepcopy(ann)
        ann_cp["image_id"] = f"{keep_map[old_id]:06d}"
        new_anns.append(ann_cp)
    data["annotations"] = new_anns

    # Info
    data["info"]["seq_length"] = kept_count

    with dst_json.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def process_video(
    src_video: Path,
    dst_video: Path,
    frame_interval: int,
) -> None:
    """
    1.  Read Labels-GameState.json to know the canonical ordering.
    2.  Select every k-th image record.
    3.  Copy the corresponding jpg (by its original image_id/filename).
    4.  Write a new JSON with remapped contiguous ids.
    """
    img_src = src_video / "img1"
    img_dst = dst_video / "img1"
    img_dst.mkdir(parents=True, exist_ok=True)

    src_json = src_video / "Labels-GameState.json"
    dst_json = dst_video / "Labels-GameState.json"
    if not src_json.exists():
        print(f"[WARN] {src_video.name}: Labels-GameState.json missing, skipped.")
        return

    # read image order from JSON
    with src_json.open(encoding="utf-8") as f:
        data = json.load(f)
    images_sorted = sorted(data["images"], key=lambda im: int(im["image_id"]))

    if not images_sorted:
        print(f"[WARN] {src_video.name}: no image entries, skipped.")
        return

    # keep 0-th, k-th, 2k-th, … entry from that list
    chosen_imgs = images_sorted[::frame_interval]
    
    keep_original_ids = [int(im["image_id"]) for im in chosen_imgs]
    
    first_original = int(images_sorted[0]["image_id"])
    keep_map = {
        orig: (orig - first_original) // frame_interval + 1
        for orig in keep_original_ids
    }

    pad = padding(img_src)

    # copy/rename jpgs
    for im in chosen_imgs:                       # every kept <image> record
        orig_id       = int(im["image_id"])
        src_filename  = im["file_name"]          # e.g. "000001.jpg", "000020.png"
        ext           = Path(src_filename).suffix
        src_path      = img_src / src_filename
        dst_path      = img_dst / f"{keep_map[orig_id]:06d}{ext}"

        if src_path.exists():
            shutil.copy2(src_path, dst_path)
        else:
            print(f"[WARN] {src_video.name}: frame {src_filename} missing, skipped.")


    # write new JSON
    write_subsampled_json(src_json, dst_json, keep_map, len(keep_original_ids))

    print(f"[OK] {src_video.name}: kept {len(keep_original_ids)}/{len(images_sorted)} frames")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--src_dir", required=True, help="folder with ALL frames")
    p.add_argument("--dst_dir", required=True, help="output folder (sparse copy)")
    p.add_argument("--frame_interval", type=int, required=True, help="k - keep every k-th frame")
    args = p.parse_args()

    src_root = Path(args.src_dir)
    dst_root = Path(args.dst_dir)
    dst_root.mkdir(parents=True, exist_ok=True)

    for vid in sorted(src_root.iterdir()):
        if vid.is_dir():
            process_video(vid, dst_root / vid.name, args.frame_interval)


if __name__ == "__main__":
    main()
