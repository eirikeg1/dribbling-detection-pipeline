#!/usr/bin/env python3
"""
delete_invalid_videos.py

This script iterates over all video files in a folder, extracts the middle frame,
runs a YOLO model for player detection, and deletes videos that do not meet the criteria:
- At least 4 players detected (above a confidence threshold).
- No player's bounding box occupies 1/3 or more of the frame height (i.e. to filter zoomed-in shots).
"""

import argparse
import os
import sys
import cv2
from ultralytics import YOLO

# Configuration constants
CONF_THRESHOLD = 0.6        # Minimum confidence for a detection
MIN_PLAYERS = 4             # Minimum number of players required
MAX_BBOX_HEIGHT_RATIO = 1/3 # Maximum allowed fraction of the frame height for any player's bbox

def get_middle_frame(video_path):
    """Extract the middle frame of the given video."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None, None
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    mid_frame_index = total_frames // 2
    cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame_index)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None, None
    return frame, frame.shape[0]  # Return frame and its height

def run_detection(model, frame):
    """
    Run the YOLO model on the frame and return list of detections.
    """
    results = model(frame)
    detections = []
    for result in results:
        boxes = result.boxes
        for i in range(len(boxes)):
            conf = float(boxes.conf[i])
            if conf < CONF_THRESHOLD:
                continue
            x1, y1, x2, y2 = boxes.xyxy[i].tolist()
            detections.append({'bbox': (x1, y1, x2, y2), 'conf': conf})
    return detections

def check_criteria(detections, frame_height):
    """
    Return True if the frame meets the criteria:
    - At least MIN_PLAYERS detected.
    - No bounding box height exceeds MAX_BBOX_HEIGHT_RATIO of the frame height.
    """
    if len(detections) < MIN_PLAYERS:
        print(f"[INFO] Not enough players detected ( {len(detections)} of minimum {MIN_PLAYERS}).")
        return False
    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        if (y2 - y1) >= frame_height * MAX_BBOX_HEIGHT_RATIO:
            print(f"[INFO] Bounding box too large: {y2 - y1} >= {frame_height * MAX_BBOX_HEIGHT_RATIO} (frame height is {frame_height}). Video will be deleted")
            return False
    return True

def process_video(model, video_path):
    """
    Process a single video file: extract its middle frame,
    run detection, and delete the video if the criteria are not met.
    """
    frame, frame_height = get_middle_frame(video_path)
    if frame is None:
        print(f"[WARN] Unable to read frame from: {video_path}")
        return False
    detections = run_detection(model, frame)
    if not check_criteria(detections, frame_height):
        os.remove(video_path)
        return False
    print(f"[INFO] Kept: {video_path}")
    return True

def main(folder_path, model):
    """Iterate over video files in the folder and process each one."""
    if not os.path.isdir(folder_path):
        print(f"[ERROR] {folder_path} is not a valid directory.")
        return
    model = YOLO(model)
    
    num_processed = 0
    num_deleted = 0
    for filename in os.listdir(folder_path):
        if not filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            continue
        num_processed += 1
        video_path = os.path.join(folder_path, filename)
        
        result = process_video(model, video_path)
        if result:
            num_deleted += 1
            
    print(f"[INFO] Processed {num_processed} videos, deleted {num_deleted}.")

    if num_processed == 0:
        print(f"[WARN] No video files found in: {folder_path}, make sure they are in a supported format (.webm, .mp4, .avi, .mov, .mkv).")
if __name__ == '__main__':
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Delete videos based on player detection.')
    parser.add_argument('--video_dir', type=str, help='Path to the folder containing video files.')
    parser.add_argument('--model', type=str, default='yolo11s.pt', help='Path to YOLO model weights.')
    args = parser.parse_args()
    
    video_dir = args.video_dir
    model = args.model
    
    main(video_dir, model)
