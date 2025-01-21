#!/usr/bin/env python3

import argparse
import os
import json
import subprocess
import datetime
import glob
import default_values

def get_video_fps(video_path):
    """
    Returns the frames per second (float) of the first video stream,
    by parsing ffprobe's 'r_frame_rate' output.
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    raw_rate = proc.stdout.strip()  # e.g., "25/1" or "30/1" or "30000/1001"

    if '/' in raw_rate:
        top, bottom = raw_rate.split('/')
        return float(top) / float(bottom)
    else:
        return float(raw_rate)


def extract_frames(video_path, output_folder):
    """
    Extract all frames from the video file (video_path),
    scaling them to 1920x1080, and save as sequential .jpg images.
    """
    os.makedirs(output_folder, exist_ok=True)
    
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vf', 'scale=1920:1080',
        '-qscale:v', '2',
        '-start_number', '1',
        '-vsync', '0',
        os.path.join(output_folder, '%06d.jpg')
    ]
    
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def get_frame_count(folder_path):
    """
    Count how many .jpg files are in the folder.
    """
    return len(glob.glob(os.path.join(folder_path, '*.jpg')))


def create_labels_json(video_name, frame_rate, total_frames, output_file):
    """
    Create a minimal Labels-GameState.json file that includes:
      - frame_rate
      - seq_length (total number of frames)
      - clip_stop as an optional 'duration' in ms if desired
    """
    # Simple duration in ms = (total_frames / frame_rate) * 1000
    duration_ms = int((total_frames / frame_rate) * 1000) if frame_rate > 0 else 0

    info_block = {
        "version": "1.3",
        "name": video_name,
        "im_dir": "img1",
        "frame_rate": frame_rate,
        "seq_length": total_frames,
        "im_ext": ".jpg",
        "clip_start": "0",
        "clip_stop": str(duration_ms)
    }

    # Build a minimal list of images, each with the forced 1920x1080 resolution
    images_list = []
    for i in range(1, total_frames + 1):
        file_name = f"{i:06d}.jpg"
        image_id_str = f"{i:09d}"
        images_list.append({
            "is_labeled": False,
            "image_id": image_id_str,
            "file_name": file_name,
            "height": 1080,
            "width": 1920
        })

    # Minimal placeholders for annotations or categories if needed
    annotations_list = []
    categories_list = []
    # categories_list = default_values.categories

    data = {
        "info": info_block,
        "images": images_list,
        "annotations": annotations_list,
        "categories": categories_list
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


def main():
    parser = argparse.ArgumentParser(description="Format videos into a structured directory with frames + JSON.")
    parser.add_argument('-i', '--input_dir', type=str, default='./inputs', help='Input directory containing videos')
    parser.add_argument('-o', '--output_dir', type=str, default='./outputs', help='Output directory for structured data')
    args = parser.parse_args()
    
    input_dir = args.input_dir
    output_dir = args.output_dir

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Loop through all mp4/webm files in input_dir
    for file_name in os.listdir(input_dir):
        if file_name.lower().endswith(('.mp4', '.webm')):
            base_name = os.path.splitext(file_name)[0]
            # Replace spaces with dashes
            base_name_sanitized = base_name.replace(' ', '-').lower()

            # Append current date/time for uniqueness
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            new_folder_name = f"{base_name_sanitized}-{timestamp}"
            new_folder_path = os.path.join(output_dir, new_folder_name)
            train_dir = os.path.join(new_folder_path, 'train')
            video_dir = os.path.join(train_dir, 'video1')
            img_dir = os.path.join(video_dir, 'img1')
            
            os.makedirs(new_folder_path, exist_ok=True)
            os.makedirs(train_dir, exist_ok=True)
            os.makedirs(img_dir, exist_ok=True)

            video_path = os.path.join(input_dir, file_name)
            print(f"Processing video: {video_path}...")

            # 1) Get the actual FPS from the video
            fps = get_video_fps(video_path)
            print(f"  - Detected FPS: {fps}")

            # 2) Extract frames, scaling to 1920x1080
            extract_frames(video_path, img_dir)
            print(f"\nFrames extracted to: {img_dir}")
            
            # 3) Count how many frames we extracted
            total_frames = get_frame_count(img_dir)
            print(f"  - Total frames extracted: {total_frames}")

            # 4) Create Labels-GameState.json with the relevant info
            print(f"\nCreating Labels-GameState.json...")
            json_path = os.path.join(video_dir, "Labels-GameState.json")
            create_labels_json(
                video_name=base_name_sanitized,
                frame_rate=fps,
                total_frames=total_frames,
                output_file=json_path
            )
            print(f"  - {json_path} created.")

    print("Processing completed.\n")


if __name__ == "__main__":
    main()
