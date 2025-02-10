#!/usr/bin/env python3
"""
Interpolate missing frames in Labels-GameState.json files.
For each video folder under data_dir/formatted-predictions, the script:
  - Loads the JSON file,
  - Fills in missing frames by linear interpolation (if the gap is <= MAX_GAP_FRAMES),
  - Copies all files and directories (e.g. images, subfolders) to the output folder,
  - Writes the interpolated JSON file in place of the original.
  
The output is written to data_dir/interpolated-predictions maintaining the folder structure.
"""

from collections import defaultdict
from pathlib import Path
import argparse
import json
import math
import os
import re
import shutil  # for copying files

# Maximum gap of frames to fill
MAX_GAP_FRAMES = 35  # only fill in missing frames if gap <= MAX_GAP_FRAMES
MAX_GAP_FRAMES_BALL = 100

def linear_interpolate(val1, val2, alpha):
    """Perform simple linear interpolation."""
    return val1 + alpha * (val2 - val1)

def interpolate_bbox_image(b1, b2, alpha):
    """Linearly interpolate each field in two bbox_image dictionaries."""
    return {
        "x": linear_interpolate(b1["x"], b2["x"], alpha),
        "y": linear_interpolate(b1["y"], b2["y"], alpha),
        "x_center": linear_interpolate(b1["x_center"], b2["x_center"], alpha),
        "y_center": linear_interpolate(b1["y_center"], b2["y_center"], alpha),
        "w": linear_interpolate(b1["w"], b2["w"], alpha),
        "h": linear_interpolate(b1["h"], b2["h"], alpha),
    }

def interpolate_bbox_pitch(b1, b2, alpha):
    """Linearly interpolate each field in two bbox_pitch dictionaries."""
    return {
        "x_bottom_left": linear_interpolate(b1["x_bottom_left"], b2["x_bottom_left"], alpha),
        "y_bottom_left": linear_interpolate(b1["y_bottom_left"], b2["y_bottom_left"], alpha),
        "x_bottom_right": linear_interpolate(b1["x_bottom_right"], b2["x_bottom_right"], alpha),
        "y_bottom_right": linear_interpolate(b1["y_bottom_right"], b2["y_bottom_right"], alpha),
        "x_bottom_middle": linear_interpolate(b1["x_bottom_middle"], b2["x_bottom_middle"], alpha),
        "y_bottom_middle": linear_interpolate(b1["y_bottom_middle"], b2["y_bottom_middle"], alpha),
    }

def interpolate_bbox_pitch_raw(b1, b2, alpha):
    """Linearly interpolate each field in two bbox_pitch_raw dictionaries."""
    return {
        "x_bottom_left": linear_interpolate(b1["x_bottom_left"], b2["x_bottom_left"], alpha),
        "y_bottom_left": linear_interpolate(b1["y_bottom_left"], b2["y_bottom_left"], alpha),
        "x_bottom_right": linear_interpolate(b1["x_bottom_right"], b2["x_bottom_right"], alpha),
        "y_bottom_right": linear_interpolate(b1["y_bottom_right"], b2["y_bottom_right"], alpha),
        "x_bottom_middle": linear_interpolate(b1["x_bottom_middle"], b2["x_bottom_middle"], alpha),
        "y_bottom_middle": linear_interpolate(b1["y_bottom_middle"], b2["y_bottom_middle"], alpha),
    }

def interpolate_group(annotations, max_gap=MAX_GAP_FRAMES):
    """
    Given a list of annotations (with the same category_id and track_id)
    sorted by frame number, fill in missing frames by linear interpolation.
    Only fills gaps if the gap size is <= MAX_GAP_FRAMES.
    """
    if len(annotations) < 2:
        return annotations  # No interpolation possible

    interpolated = []
    for i in range(len(annotations) - 1):
        a1 = annotations[i]
        a2 = annotations[i + 1]
        frame1 = int(a1["image_id"])
        frame2 = int(a2["image_id"])

        # Always include the first annotation
        interpolated.append(a1)

        gap_size = frame2 - frame1 - 1
        if 0 < gap_size <= max_gap:
            for step in range(1, gap_size + 1):
                alpha = step / (gap_size + 1.0)
                new_ann = {
                    "id": "interpolated",  # Temporary ID; will be overwritten
                    "image_id": f"{frame1 + step:06d}",
                    "track_id": a1["track_id"],
                    "supercategory": a1["supercategory"],
                    "category_id": a1["category_id"],
                    "bbox_image": None,
                    "bbox_pitch": None,
                    "bbox_pitch_raw": None,
                    "attributes": a1.get("attributes"),
                    "lines": None
                }

                if a1.get("bbox_image") and a2.get("bbox_image"):
                    new_ann["bbox_image"] = interpolate_bbox_image(a1["bbox_image"], a2["bbox_image"], alpha)
                if a1.get("bbox_pitch") and a2.get("bbox_pitch"):
                    new_ann["bbox_pitch"] = interpolate_bbox_pitch(a1["bbox_pitch"], a2["bbox_pitch"], alpha)
                if a1.get("bbox_pitch_raw") and a2.get("bbox_pitch_raw"):
                    new_ann["bbox_pitch_raw"] = interpolate_bbox_pitch_raw(a1["bbox_pitch_raw"], a2["bbox_pitch_raw"], alpha)

                interpolated.append(new_ann)


    interpolated.append(annotations[-1])
    return interpolated

def get_group_key(ann):
    BALL_CATEGORY_ID = 4
    if ann["category_id"] == BALL_CATEGORY_ID:
        # Force a single group for all ball annotations.
        return (ann["category_id"], -1)
    else:
        # For other categories, use the provided track_id (or -1 if None)
        return (ann["category_id"], ann["track_id"] if ann["track_id"] is not None else -1)


def interpolate_labels(labels_data):
    groups = defaultdict(list)
    interpolated_groups = []

    # Group annotations by category_id and track_id (put balls in a single group).
    for ann in labels_data["annotations"]:
        key = get_group_key(ann)
        groups[key].append(ann)

    # Process groups.
    for key, ann_list in groups.items():
        ann_list.sort(key=lambda x: int(x["image_id"]))
        max_gap = MAX_GAP_FRAMES_BALL if key[0] == 4 else MAX_GAP_FRAMES
        
        interpolated_groups.extend(interpolate_group(ann_list, max_gap=max_gap))

    # Sort all annotations and assign new IDs.
    interpolated_groups.sort(key=lambda x: int(x["image_id"]))
    for i, ann in enumerate(interpolated_groups, start=1):
        ann["id"] = f"{i:06d}"

    return {
        "info": labels_data["info"],
        "images": labels_data["images"],
        "annotations": interpolated_groups,
        "categories": labels_data["categories"],
    }

def copy_all_except(src: Path, dst: Path, exclude: list):
    """
    Recursively copy all files and directories from src to dst,
    excluding any items with names in the 'exclude' list.
    """
    for item in src.iterdir():
        if item.name in exclude:
            continue
        dest_item = dst / item.name
        if item.is_dir():
            shutil.copytree(item, dest_item, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest_item)

def process_video_folder(video_dir: Path, output_parent: Path) -> None:
    """
    Process one video folder:
      - Reads the Labels-GameState.json file.
      - Interpolates missing frames.
      - Copies all files and directories (e.g. images) to the output folder.
      - Writes the interpolated JSON file.
    """
    json_file = video_dir / "Labels-GameState.json"
    if not json_file.exists():
        print(f"[WARNING] No Labels-GameState.json in {video_dir}. Skipping.")
        return

    print(f"Processing video folder: {video_dir.name}")
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    interpolated_data = interpolate_labels(data)

    # Create the corresponding output folder
    out_video_dir = output_parent / video_dir.name
    out_video_dir.mkdir(exist_ok=True, parents=True)

    # Copy all files and subdirectories except the original JSON file
    copy_all_except(video_dir, out_video_dir, exclude=["Labels-GameState.json"])

    # Write the interpolated JSON file in the output folder
    out_json_file = out_video_dir / "Labels-GameState.json"
    with open(out_json_file, "w", encoding="utf-8") as outf:
        json.dump(interpolated_data, outf, indent=4)

    print(f"   -> {video_dir} processed to {out_video_dir}")

def main():
    parser = argparse.ArgumentParser(
        description="Interpolate missing frames in predictions and copy all files to a new folder."
    )
    parser.add_argument(
        "--data_dir",
        type=str,
        required=True,
        help="Path to the data directory that contains a 'formatted-predictions' folder."
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        print(f"[ERROR] {data_dir} is not a valid directory.")
        return

    formatted_dir = data_dir / "formatted-predictions"
    if not formatted_dir.is_dir():
        print(f"[ERROR] {formatted_dir} does not exist.")
        return

    output_dir = data_dir / "interpolated-predictions"
    output_dir.mkdir(exist_ok=True, parents=True)

    # Iterate over each video folder in 'formatted-predictions'
    for video_dir in sorted(formatted_dir.iterdir()):
        if video_dir.is_dir():
            process_video_folder(video_dir, output_dir)

    print("[DONE] All video folders processed.")

if __name__ == "__main__":
    main()
