#!/usr/bin/env python3
"""
fix_images_inplace.py - normalise the "images" section of SoccerNet-GS JSONs.

• Scans DATA_ROOT recursively for *.json.
• Builds a fresh, sequential images list from the distinct image_id values
  found in "annotations": "000001", "000002", ...
• Rewrites every annotation's image_id to the new value.
• Saves the result over the original file (atomic temp-file swap).

Usage:
    python fix_images_inplace.py /path/to/json/root

If your frame-file names need a different zero-pad width, change PAD below.
"""

from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from typing import Dict
from tempfile import NamedTemporaryFile

PAD = 6            # zero‑pad width for "000001"
DEF_H = 1080       # fallback height  (only used if none present)
DEF_W = 1920       # fallback width

def rebuild_images(data) -> None:
    # Map old → new id in discover order
    id_map: Dict[str, str] = {}
    for ann in data["annotations"]:
        oid = ann["image_id"]
        if oid not in id_map:
            id_map[oid] = str(len(id_map) + 1).zfill(PAD)
        ann["image_id"] = id_map[oid]

    h = data["images"][0].get("height", DEF_H) if data.get("images") else DEF_H
    w = data["images"][0].get("width",  DEF_W) if data.get("images") else DEF_W

    im_dir = data["info"]["im_dir"]
    data["images"] = [{
        "is_labeled": True,
        "image_id": nid,
        "file_name": f"{nid}.jpg",
        "height": h,
        "width": w,
        "has_labeled_person": True,
        "has_labeled_pitch": True,
        "has_labeled_camera": True,
    } for nid in id_map.values()]

def rewrite(path: Path) -> None:
    with path.open() as fh:
        data = json.load(fh)

    rebuild_images(data)

    # atomic write‑back
    with NamedTemporaryFile("w", dir=path.parent, delete=False) as tmp:
        json.dump(data, tmp, separators=(",", ":"))
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)          # overwrite original

def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: fix_images_inplace.py <DATA_ROOT>")
    root = Path(sys.argv[1])
    if not root.is_dir():
        sys.exit("DATA_ROOT must be a directory")

    for jp in root.rglob("*.json"):
        rewrite(jp)
        rel = jp.relative_to(root)
        print(f"✔ fixed {rel}")

if __name__ == "__main__":
    main()
