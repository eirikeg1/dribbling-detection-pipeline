#!/usr/bin/env python3
import argparse
import default_values
import json
import os
import shutil
from pathlib import Path

def build_info_block(
    version="1.3",
    game_id="demo_game",
    name="converted_dataset",
    frame_rate=25,
    seq_length=9999,
    clip_start="0",
    clip_stop="30000"
):
    return {
        "version": version,
        "game_id": game_id,
        "num_tracklets": "0",
        "action_position": "NA",
        "action_class": "NA",
        "visibility": "visible",
        "game_time_start": "0:00",
        "game_time_stop": "0:00",
        "clip_start": clip_start,
        "clip_stop": clip_stop,
        "name": name,
        "im_dir": "img1",
        "frame_rate": frame_rate,
        "seq_length": seq_length,
        "im_ext": ".jpg"
    }

def build_image_entry(image_id, file_name, height=1080, width=1920, is_labeled=True):
    return {
        "is_labeled": is_labeled,
        "image_id": str(image_id),
        "file_name": file_name,
        "height": height,
        "width": width,
        "has_labeled_person": True,
        "has_labeled_pitch": True,
        "has_labeled_camera": True
    }

def build_bbox_image(b):
    return {
        "x": b.get("x", 0.0),
        "y": b.get("y", 0.0),
        "x_center": b.get("x_center", 0.0),
        "y_center": b.get("y_center", 0.0),
        "w": b.get("w", 0.0),
        "h": b.get("h", 0.0),
    }

def build_bbox_pitch(b):
    return {
        "x_bottom_left": b.get("x_bottom_left", 0.0),
        "y_bottom_left": b.get("y_bottom_left", 0.0),
        "x_bottom_right": b.get("x_bottom_right", 0.0),
        "y_bottom_right": b.get("y_bottom_right", 0.0),
        "x_bottom_middle": b.get("x_bottom_middle", 0.0),
        "y_bottom_middle": b.get("y_bottom_middle", 0.0)
    }

def build_bbox_pitch_raw(b):
    return {
        "x_bottom_left": b.get("x_bottom_left", 0.0),
        "y_bottom_left": b.get("y_bottom_left", 0.0),
        "x_bottom_right": b.get("x_bottom_right", 0.0),
        "y_bottom_right": b.get("y_bottom_right", 0.0),
        "x_bottom_middle": b.get("x_bottom_middle", 0.0),
        "y_bottom_middle": b.get("y_bottom_middle", 0.0)
    }

def build_annotation(pred_obj, ann_id):
    ann = {
        "id": str(ann_id),
        "image_id": str(pred_obj.get("image_id", "")),
        "track_id": pred_obj.get("track_id"),
        "supercategory": pred_obj.get("supercategory", "object"),
        "category_id": int(pred_obj.get("category_id", 0)),
        "bbox_image": None,
        "bbox_pitch": None,
        "bbox_pitch_raw": None,
        "attributes": None,
        "lines": None
    }

    # image-space bounding box
    if "bbox_image" in pred_obj:
        ann["bbox_image"] = build_bbox_image(pred_obj["bbox_image"])
    elif isinstance(pred_obj.get("bbox"), list):
        # if "bbox" is [x, y, w, h], for example
        x, y, w, h = pred_obj["bbox"]
        ann["bbox_image"] = {
            "x": x,
            "y": y,
            "x_center": x + w/2,
            "y_center": y + h/2,
            "w": w,
            "h": h
        }

    # pitch bounding box
    if "bbox_pitch" in pred_obj:
        ann["bbox_pitch"] = build_bbox_pitch(pred_obj["bbox_pitch"])
    if "bbox_pitch_raw" in pred_obj:
        ann["bbox_pitch_raw"] = build_bbox_pitch_raw(pred_obj["bbox_pitch_raw"])

    # attributes
    if "attributes" in pred_obj:
        att = pred_obj["attributes"]
        ann["attributes"] = {
            "role": att.get("role"),
            "jersey": None if att.get("jersey") in [None, "null"] else str(att.get("jersey")),
            "team": att.get("team")
        }

    # lines
    if "lines" in pred_obj:
        ann["lines"] = {}
        try:
            for line_name, points in pred_obj["lines"].items():
                ann["lines"][line_name] = [
                    {"x": float(pt.get("x", 0.0)), "y": float(pt.get("y", 0.0))}
                    for pt in points
                ]
        except Exception as e:
            print(f"Error in lines: {e}")

    return ann

def convert_predictions_to_labels(predictions, padding_length=6):
    """
    Convert a list of predictions (all for one video) into
    the dict structure for a single Labels-GameState.json
    (minus the 'info' block).
    
    padding_length: number of digits to pad for the file name 
                    (e.g. 6 => 000001.jpg)
    """
    images_map = {}
    annotations_list = []
    ann_id = 1

    for p in predictions:
        img_id_str = str(p.get("image_id", ""))

        # Zero-pad the image_id so that it matches the filenames
        padded_img_id_str = img_id_str.zfill(padding_length)
        file_name = f"{padded_img_id_str}.jpg"

        # Create image entry if not yet in the map
        if padded_img_id_str not in images_map:
            images_map[padded_img_id_str] = build_image_entry(
                image_id=padded_img_id_str,
                file_name=file_name,
                height=1080,  # Adjust if known
                width=1920
            )
        # Add annotation
        annotation = build_annotation(p, ann_id)
        # Force the annotation's "image_id" to match the new padded version
        annotation["image_id"] = padded_img_id_str
        annotations_list.append(annotation)
        ann_id += 1

    return list(images_map.values()), annotations_list

def find_padding_length(img_folder: Path) -> int:
    """
    Inspects the .jpg filenames in img_folder to guess a padding length.
    For example, if files are named '000001.jpg', '000002.jpg', 
    it returns 6.
    Default to 6 if no images or no numeric parse is possible.
    """
    jpg_files = sorted(img_folder.glob("*.jpg"))
    if not jpg_files:
        return 6

    max_len = 0
    for f in jpg_files:
        stem = f.stem  # e.g. "000001"
        # Count length
        max_len = max(max_len, len(stem))
    return max_len if max_len > 0 else 6

def main():
    parser = argparse.ArgumentParser(
        description="Convert SoccerNet-GS style predictions into final Labels-GameState.json files."
    )
    parser.add_argument("--data_dir", type=str, required=True,
                        help="Path to the 'run_YYYY-MM-DD_HH-MM-SS' folder containing predictions + original data.")
    parser.add_argument("--output_name", type=str, default="formatted-predictions",
                        help="Name of the new folder to create in 'data_dir' for the final results.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output.")
    args = parser.parse_args()

    # Locate the 'tracklab' folder:
    tracklab_dir = list(
        Path(args.data_dir).glob("game-state-output/eval/pred/SoccerNetGS-train/tracklab")
    )
    if not tracklab_dir:
        print(f"[ERROR] Could not find 'tracklab' folder under {args.data_dir}/game-state-output/eval/pred/.")
        return
    
    # If more than one matching path is found, pick first:
    tracklab_path = tracklab_dir[0]

    # Create output root folder (e.g., "data_dir/formatted-predictions")
    output_root = Path(args.data_dir) / args.output_name
    output_root.mkdir(parents=True, exist_ok=True)

    # Gather all *.json prediction files in the tracklab folder
    json_files = sorted(tracklab_path.glob("*.json"))

    for i, jfile in enumerate(json_files):
        # Use the JSON file stem as the video name, e.g. "comp-vid-scene-017"
        video_name = jfile.stem

        if args.verbose:
            print(f"[INFO] Processing {jfile.name} -> folder: {video_name}")

        with open(jfile, "r", encoding="utf-8") as f:
            pred_data = json.load(f)

        # If the file has a top-level "predictions" key, use that; else assume array
        if isinstance(pred_data, dict) and "predictions" in pred_data:
            predictions = pred_data["predictions"]
        elif isinstance(pred_data, list):
            predictions = pred_data
        else:
            print(f"[WARNING] {jfile.name} missing 'predictions' array. Skipping.")
            continue

        # Attempt to find original frames in data_dir/train/<video_name>/img1
        original_img1_dir = Path(args.data_dir) / "train" / video_name / "img1"

        # Build output path: data_dir/formatted-predictions/<video_name>/img1
        # original_img1_dir = Path(args.data_dir) / "train" / f"video_{i}" / "img1"
        out_video_dir = output_root / video_name
        out_img1_dir = out_video_dir / "img1"
        out_img1_dir.mkdir(parents=True, exist_ok=True)

        # Copy frames if they exist
        if original_img1_dir.is_dir():
            # Figure out how many digits are used in the original frame filenames
            padding_length = find_padding_length(original_img1_dir)
            if args.verbose:
                print(f"   -> Determined padding length = {padding_length} based on original frames.")

            # Copy frames over (names remain the same)
            for frame_jpg in sorted(original_img1_dir.glob("*.jpg")):
                dest = out_img1_dir / frame_jpg.name
                if not dest.exists():
                    shutil.copy2(frame_jpg, dest)
        else:
            print(f"[WARNING] Original frames folder not found: {original_img1_dir}")
            # fallback
            padding_length = 6

        # Now convert predictions, ensuring we pad the image_id to match
        images_list, annotations_list = convert_predictions_to_labels(predictions, padding_length=padding_length)

        # Count frames in out_img1_dir
        seq_len = len(list(out_img1_dir.glob("*.jpg")))

        # Build 'info' block
        info_block = build_info_block(
            game_id=video_name,
            name=f"{video_name}_converted",
            frame_rate=25,
            seq_length=seq_len,
            clip_start="0",
            clip_stop=str(seq_len * 40)  # example: 25 fps => ~40 ms/frame
        )

        # Prepare final data
        out_data = {
            "info": info_block,
            "images": images_list,
            "annotations": annotations_list,
            "categories": default_values.categories
        }

        # Write the JSON
        labels_json_path = out_video_dir / "Labels-GameState.json"
        with open(labels_json_path, "w", encoding="utf-8") as f:
            json.dump(out_data, f, indent=4)

        if args.verbose:
            print(f"   -> Wrote {labels_json_path}")

    print("\nAll prediction JSONs have been converted and placed in", output_root)


if __name__ == "__main__":
    main()
