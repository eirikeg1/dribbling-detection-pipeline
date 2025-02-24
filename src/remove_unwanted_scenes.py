"""
Iterates over all video files in a folder, extracts the middle frame,
runs a YOLO model for player detection, and deletes videos that do not meet the criteria:
- At least 4 players detected (above a confidence threshold).
- No player's bounding box occupies 1/4 or more of the frame height (i.e. to filter zoomed-in shots).

"""

import argparse
import os
import sys
import cv2
import subprocess
from ultralytics import YOLO

# Configuration constants
CONF_THRESHOLD = 0.6        # Minimum confidence for a detection
MIN_PLAYERS = 4             # Minimum number of players required
MAX_BBOX_HEIGHT_RATIO = 1/4 # Maximum allowed fraction of the frame height for any player's bbox

CHUNK_LENGTH = 45  # max length of each video chunk (in seconds)
OVERLAP = 2        # overlap between consecutive chunks (in seconds)

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
    """Run the YOLO model on the frame and return list of detections."""
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
        print(f"[INFO] Not enough players detected ({len(detections)} of minimum {MIN_PLAYERS}).")
        return False
    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        if (y2 - y1) >= frame_height * MAX_BBOX_HEIGHT_RATIO:
            print(f"[INFO] Bounding box too large: {y2 - y1} >= {frame_height * MAX_BBOX_HEIGHT_RATIO} (frame height is {frame_height}). Video will be deleted.")
            return False
    return True

def get_video_duration(video_path):
    """
    Use ffprobe to retrieve the duration (in seconds) of the video.
    """
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'csv=p=0', video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
    except Exception as e:
        print(f"[WARN] Could not determine duration for {video_path}: {e}")
        return 0.0

def split_video_into_segments(video_path, chunk_length=30, overlap=1):
    """
    Split a video into segments of `chunk_length` seconds with `overlap` seconds.
    - The first chunk goes from 0 to chunk_length seconds,
    - The next chunk goes from (chunk_length - overlap) to (2*chunk_length - overlap), etc.
    - Continues until the end of the video.
    - Saves segments into the same directory as the original video.
    """
    total_duration = get_video_duration(video_path)
    if total_duration <= 0:
        print(f"[WARN] Invalid duration ({total_duration}s). Skipping split for {video_path}")
        return

    # If video is shorter than or equal to the chunk_length, no additional splits
    if total_duration <= chunk_length:
        print(f"[INFO] Video shorter than or equal to {chunk_length}s. Skipping split for {video_path}.")
        return

    video_dir = os.path.dirname(video_path)
    video_base = os.path.splitext(os.path.basename(video_path))[0]

    start = 0.0
    chunk_index = 1
    while start < total_duration:
        # Calculate chunk duration (might be shorter for the final chunk)
        end = start + chunk_length
        if end > total_duration:
            end = total_duration
        current_chunk_length = end - start

        # Output filename
        out_filename = f"{video_base}_chunk{chunk_index:03d}.mp4"
        out_path = os.path.join(video_dir, out_filename)

        # ffmpeg command:
        #   -ss <start>   : seek to 'start' second
        #   -t <duration> : record 'current_chunk_length' seconds
        #   -c copy       : copy codec (fast, no re-encoding)
        cmd = [
            'ffmpeg', '-hide_banner', '-loglevel', 'error',
            '-ss', f"{start}",
            '-i', video_path,
            '-t', f"{current_chunk_length}",
            '-c', 'copy',
            out_path
        ]

        print(f"[INFO] Generating chunk {chunk_index} from {start:.2f}s to {end:.2f}s -> {out_path}")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] ffmpeg failed: {e}")
            break

        chunk_index += 1
        # Move start for the next chunk, subtracting overlap
        start += (chunk_length - overlap)
        # If we are within 0.5s of total_duration, break (avoid tiny leftover chunk)
        if (total_duration - start) < 0.5:
            break

def process_video(model, video_path):
    """
    Process a single video file: extract its middle frame,
    run detection, and delete the video if the criteria are not met.
    If kept, split the video into 30s chunks with 1s overlap in the same directory.
    """
    frame, frame_height = get_middle_frame(video_path)
    if frame is None:
        print(f"[WARN] Unable to read frame from: {video_path}")
        return False

    detections = run_detection(model, frame)
    if not check_criteria(detections, frame_height):
        os.remove(video_path)
        print(f"[INFO] Deleted: {video_path}")
        return False

    # If the video passes criteria, we keep it and split it
    print(f"[INFO] Kept: {video_path}")
    split_video_into_segments(
        video_path,
        chunk_length=CHUNK_LENGTH,
        overlap=OVERLAP
    )
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

        video_path = os.path.join(folder_path, filename)
        num_processed += 1
        
        was_kept = process_video(model, video_path)
        if not was_kept:
            num_deleted += 1

    print(f"[INFO] Processed {num_processed} videos, deleted {num_deleted}.")

    if num_processed == 0:
        print(f"[WARN] No video files found in: {folder_path}, "
              f"make sure they are in a supported format (.webm, .mp4, .avi, .mov, .mkv).")

if __name__ == '__main__':
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Delete videos based on player detection, then optionally split kept videos.'
    )
    parser.add_argument('--video_dir', type=str, help='Path to the folder containing video files.')
    parser.add_argument('--model', type=str, default='yolo11s.pt', help='Path to YOLO model weights.')
    args = parser.parse_args()
    
    video_dir = args.video_dir
    model = args.model
    
    main(video_dir, model)
