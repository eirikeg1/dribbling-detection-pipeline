#!/usr/bin/env python3
"""
Restore all missing frames and re-index the ones that were kept when frames
were sub-sampled during `format_to_soccernet.py`.

Usage
-----
python restore_frames_and_reindex.py \
      --data_dir   /path/to/run_YYYY-MM-DD_HH-MM-SS \
      --full_train /path/to/run_YYYY-MM-DD_HH-MM-SS/train \
      --frame_interval 10
"""

import argparse
import json
import shutil
from pathlib import Path

# small helpers

def padding(img_dir: Path) -> int:
    """Guess zero-padding from the first jpg in a folder (default 6)."""
    for f in sorted(img_dir.glob("*.jpg")):
        return len(f.stem)
    return 6


def find_frames(img_dir: Path) -> list[int]:
    """Return sorted list of existing frame numbers in a folder."""
    return sorted(int(f.stem) for f in img_dir.glob("*.jpg"))


def relabel_json(json_path: Path, id_map: dict[int, int], total_frames: int) -> None:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    ext = data["info"].get("im_ext", ".jpg")
    
    # images
    new_images = {i: None for i in range(1, total_frames + 1)}
    for img in data["images"]:
        old_id = int(img["image_id"])
        new_id = id_map[old_id]
    
        img["image_id"] = f"{new_id:06d}"
        img["file_name"] = f"{new_id:06d}{ext}"
        new_images[new_id] = img

    # fill gaps (is_labeled False)
    dummy = {
        "height": 1080,
        "width": 1920,
        "is_labeled": False,
    }
    data["images"] = [
        {"image_id": f"{i:06d}", "file_name": f"{i:06d}.jpg", **dummy}
        if new_images[i] is None else new_images[i]
        for i in range(1, total_frames + 1)
    ]

    # annotations
    for ann in data["annotations"]:
        ann["image_id"] = f"{id_map[int(ann['image_id'])]:06d}"

    # info
    data["info"]["seq_length"] = total_frames

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def process_video(
    fp_video: Path,
    fp_full: Path,
    frame_interval: int,
):
    img_sparse = fp_video / "img1"
    img_full = fp_full / fp_video.name / "img1"

    print(f" * img_full: {img_full}")
    if img_full.is_dir():
        print(f" Processing {fp_video.name}")
    else:
        print(f"[WARN] Skipping {fp_video.name}: all_frames dir not found.")
        return

    pad = padding(img_full)

    # 1. rename the sparse frames so their index == original frame index
    sparse_frames = find_frames(img_sparse)
    id_map = {}
    # first rename to temp names to avoid clashes
    for fn in img_sparse.glob("*.jpg"):
        fn.rename(fn.with_name(f"tmp_{fn.name}"))

    for i_sparse in sparse_frames:
        original = (i_sparse - 1) * frame_interval + 1
        src = img_sparse / f"tmp_{i_sparse:0{pad}d}.jpg"
        dst = img_sparse / f"{original:0{pad}d}.jpg"
        src.rename(dst)
        id_map[i_sparse] = original

    # 2. copy every missing frame from the full set
    total_frames = max(find_frames(img_full))
    have = set(find_frames(img_sparse))
    need = [i for i in range(1, total_frames + 1) if i not in have]

    print(f"\nNeed:")
    for i in need:
        f = img_full / f"{i:0{pad}d}.jpg"
        d = img_sparse / f"{i:0{pad}d}.jpg"
        shutil.copy2(
            img_full / f"{i:0{pad}d}.jpg",
            img_sparse / f"{i:0{pad}d}.jpg",
        )

    # 3. update JSON
    relabel_json(fp_video / "Labels-GameState.json", id_map, total_frames)

    print(f"[OK] {fp_video.name}: +{len(need)} frames, "
          f"{len(sparse_frames)} renamed, total {total_frames}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True, help="run_* folder")
    parser.add_argument(
        "--all_frames",
        required=True,
        help="train folder that still contains ALL frames",
    )
    parser.add_argument("--frame_interval", type=int, required=True)
    args = parser.parse_args()
    
    print("\nRestoring frames skipped for prediction step")

    fp_pred = Path(args.data_dir) / "formatted-predictions"
    fp_full = Path(args.all_frames) # Replaces all spaces with dashes

    if not fp_pred.is_dir():
        raise SystemExit("formatted-predictions not found")

    for v in sorted(fp_pred.iterdir()):
        if v.is_dir():
            process_video(v, fp_full, args.frame_interval)


if __name__ == "__main__":
    main()
