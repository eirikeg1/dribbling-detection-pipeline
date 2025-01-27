import argparse
import os
import json
import subprocess
import datetime
import glob
import shutil
import time
import default_values

def get_video_fps(video_path):
    """
    Returns the frames per second (float) of the first video stream by parsing
    ffprobe's 'r_frame_rate' output (e.g., '25/1', '30/1', or '30000/1001').
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
    raw_rate = proc.stdout.strip()

    if '/' in raw_rate:
        numerator, denominator = raw_rate.split('/')
        return float(numerator) / float(denominator)
    else:
        return float(raw_rate)

def extract_frames(video_path, output_folder):
    """
    Extracts all frames from the video file (video_path) at 1920x1080 resolution
    and saves them as sequential .jpg images in output_folder.
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
    Counts how many .jpg files are in the specified folder_path.
    """
    return len(glob.glob(os.path.join(folder_path, '*.jpg')))

def create_labels_json(video_name, frame_rate, total_frames, output_file):
    """
    Creates a minimal Labels-GameState.json file containing:
        - frame_rate
        - seq_length (total number of frames)
        - clip_stop = total duration in milliseconds
      Adds a list of images with forced resolution (1920x1080).
    """
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

    # Record start time
    start_time = time.time()
    start_dt = datetime.datetime.now()

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Create a unique run folder under the output directory
    timestamp = start_dt.strftime("%Y-%m-%d-%H_%M_%S")
    run_folder = os.path.join(output_dir, f"run_{timestamp}")
    train_dir = os.path.join(run_folder, "train")
    os.makedirs(train_dir, exist_ok=True)

    # Create a processed folder for this run
    processed_run_folder = os.path.join("processed", f"run_{timestamp}")
    os.makedirs(processed_run_folder, exist_ok=True)

    # For collecting summary info about the run
    video_details = []

    video_counter = 1

    # Loop through all mp4/webm files in input_dir
    for file_name in os.listdir(input_dir):
        if file_name.lower().endswith(('.mp4', '.webm')):
            # Create subfolder "video{video_counter}" and img1 for frames
            video_subfolder_name = f"video{video_counter}"
            video_dir = os.path.join(train_dir, video_subfolder_name)
            img_dir = os.path.join(video_dir, "img1")

            os.makedirs(video_dir, exist_ok=True)
            os.makedirs(img_dir, exist_ok=True)

            video_path = os.path.join(input_dir, file_name)
            base_name = os.path.splitext(file_name)[0]
            base_name_sanitized = base_name.replace(' ', '-').lower()

            print(f"Processing video: {video_path}...")

            # 1) Get the actual FPS from the video
            fps = get_video_fps(video_path)
            print(f"  - Detected FPS: {fps}")

            # 2) Extract frames (scaled to 1920x1080) into img1
            extract_frames(video_path, img_dir)
            print(f"  - Frames extracted to: {img_dir}")
            
            # 3) Count the frames
            total_frames = get_frame_count(img_dir)
            print(f"  - Total frames extracted: {total_frames}")

            # 4) Create Labels-GameState.json
            json_path = os.path.join(video_dir, "Labels-GameState.json")
            create_labels_json(
                video_name=base_name_sanitized,
                frame_rate=fps,
                total_frames=total_frames,
                output_file=json_path
            )
            print(f"  - {json_path} created.")

            # 5) Move the original video to the processed folder for this run
            shutil.move(video_path, processed_run_folder)
            print(f"  - Moved video to: {processed_run_folder}\n")

            # Collect details for this video
            video_details.append({
                "original_file_name": file_name,
                "video_name": base_name_sanitized,
                "fps": fps,
                "frames_extracted": total_frames
            })

            video_counter += 1

    # Record end time and compute duration
    end_time = time.time()
    end_dt = datetime.datetime.now()
    duration = end_time - start_time

    # Create the run info data
    data_info = {
        "start_time": start_dt.isoformat(),
        "end_time": end_dt.isoformat(),
        "duration_seconds": round(duration, 2),
        "videos_processed": len(video_details),
        "details": video_details
    }

    # Write the data info file in the run folder
    data_info_path = os.path.join(run_folder, "data_info.json")
    with open(data_info_path, 'w', encoding='utf-8') as f:
        json.dump(data_info, f, indent=4)

    print("All videos have been processed and moved.")
    print(f"Run information written to {data_info_path}\n")

if __name__ == "__main__":
    main()
