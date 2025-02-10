#!/bin/bash

set -e  # Exit on error
start_time=$SECONDS  # Start timer

# ==================================================================================================
# Parsing arguments and config

config_file="config.env"
input_video=""
tmp_file_dir="temp_files" # Use unique directory for parallel runs; folder is automatically created
frame_interval=1

# Parse input arguments
while getopts "c:i:t:f:" flag; do
    case "${flag}" in
        c) config_file=${OPTARG} ;;
        i) input_video=${OPTARG} ;;
        t) tmp_file_dir=${OPTARG} ;;
        f) frame_interval=${OPTARG} ;;
        *)
            echo "Usage: bash run_pipeline.sh [-c <config-file.env>] -i <input-video> [-t <tmp_file_dir>] [-f <frame_interval>]"
            exit 1
            ;;
    esac
done

# Check if input video file is provided
if [ -z "$input_video" ]; then
    echo "Error: Input video file is required."
    echo "Usage: bash run_pipeline.sh [-c <config-file.env>] -i <input-video> [-t <tmp_file_dir>] [-f <frame_interval>]"
    exit 1
fi

# Load the config file
if [ -f "$config_file" ]; then
    echo "Loading configuration from $config_file..."
    source "$config_file"
else
    echo "Error: Config file not found: $config_file"
    exit 1
fi

# ==================================================================================================
# Run the pipeline

# Step 1: Split the video
if [ "$SPLIT_VIDEO" = true ]; then
    echo "Step 1: Splitting the video '$input_video' into shorter video clips..."
    bash src/split_video_script.sh -i "$input_video" -o "$SPLIT_OUTPUT_DIR"
    if [ $? -ne 0 ]; then
        echo "Error: Video splitting failed."
        exit 1
    fi
    echo "Video splitting completed."
fi

# Step 2: Restructure data to SoccerNet format
if [ "$FORMAT_VIDEO" = true ]; then
    echo "Step 2: Restructuring data to SoccerNet format..."
    python3 src/format_to_soccernet.py \
        -i "$SPLIT_OUTPUT_DIR" \
        -o "$OUTPUT_DIR" \
        --object_detection_config "object-detection-config.yaml" \
        --temp_file_dir "$tmp_file_dir" \
        --frame_interval "$frame_interval"
    echo "Restructuring data to SoccerNet format completed."
fi

# Step 3: Game state pipeline
if [ "$GAME_STATE_PIPELINE" = true ]; then
    # 3.1 Copy the object detection config file to correct dependency location
    echo "Copying object-detection-config.yaml to the correct folder"
    mkdir -p "$SOCCERNET_CONFIG_DIR"
    cp object-detection-config.yaml "$SOCCERNET_CONFIG_DIR/soccernet.yaml"
    echo ""

    # 3.2 Run object detection, tracking, homography transformation etc.
    echo "Step 3: Running game state pipeline..."
    python -m tracklab.main -cn soccernet
    echo "Game state pipeline completed."

    # 3.3 Reformat the predictions to standard SoccerNet format
    echo "Reformatting predictions to SoccerNetGSR input format..."
    data_dir="$(cat "${tmp_file_dir}/data_dir.txt")"  # data_dir was written to file in step 2
    python src/format_predictions_to_annotations.py --data_dir "$data_dir"

    # 3.4 Interpolate missing annotations
    echo "Interpolating annotations"
    python src/interpolate_annotations.py --data_dir "$data_dir"

    echo "Object detection pipeline completed."
fi

# Step 4: Dribble detection (future implementation)
if [ "$DRIBLE_DETECTION" = true ]; then
    echo "Step 4: Running dribble detection..."
    # TODO: add dribble detection here
    echo "Dribble detection completed."
fi

end_time=$SECONDS
elapsed_time=$((end_time - start_time))
elapsed_hours=$((elapsed_time / 3600))
elapsed_minutes=$(((elapsed_time % 3600) / 60))
elapsed_seconds=$((elapsed_time % 60))
echo "Pipeline completed successfully in ${elapsed_hours}h:${elapsed_minutes}m:${elapsed_seconds}s!"
