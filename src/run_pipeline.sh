#!/bin/bash

# ==================================================================================================
# Parsing arguments and config

set -e # Exit on error

config_file="config.env"
input_video=""

# Parse input arguments
while getopts "c:i:f:" flag; do
    case "${flag}" in
        c) config_file=${OPTARG} ;;
        i) input_video=${OPTARG} ;;
        *)
            echo "Usage: bash run_pipeline.sh [-c <config-file.env>] -i <input-video>"
            exit 1
            ;;
    esac
done

# Check if input video file is provided
if [ -z "$input_video" ]; then
    echo "Error: Input video file is required."
    echo "Usage: bash run_pipeline.sh [-c <config-file.env>] -i <input-video>"
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
    echo "Step 1: Splitting the video..."
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
    python3 src/format_to_soccernet.py -i "$SPLIT_OUTPUT_DIR" -o "$OUTPUT_DIR" --object_detection_config "object-detection-config.yaml"
fi

# Step 3: Game state pipeline (future implementation)
if [ "$GAME_STATE_PIPELINE" = true ]; then
    # Copy the object detection config file to correct dependency location
    echo "Copying object-detection-config.yaml to the correct folder"
    mkdir -p "$SOCCERNET_CONFIG_DIR"
    cp object-detection-config.yaml "$SOCCERNET_CONFIG_DIR/soccernet.yaml"
    echo ""

    # Run object detection, tracking, homography transformation etc.
    echo "Step 3: Running game state pipeline..."
    python -m tracklab.main -cn soccernet
    echo "Game state pipeline completed."
fi

# Step 4: Dribble detection (future implementation)
if [ "$DRIBLE_DETECTION" = true ]; then
    echo "Step 4: Running dribble detection..."
    # TODO: add dribble detection here
    echo "Dribble detection completed."
fi

echo "Pipeline completed successfully!"
