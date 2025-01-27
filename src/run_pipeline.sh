#!/bin/bash

# ==================================================================================================
# Parsing arguments and config

set -e # Exit on error

config_file="config.env"
input_video=""

# Parse input arguments
while getopts "c:i:" flag; do
    case "${flag}" in
        c) config_file=${OPTARG} ;;  # Config file
        i) input_video=${OPTARG} ;;  # Input video file
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
    echo "Video splitting completed."
fi

# Step 2: Restructure data to SoccerNet format
if [ "$FORMAT_VIDEO" = true ]; then
    echo "Step 2: Restructuring data to SoccerNet format..."
    python3 src/format_to_soccernet.py -i "$SPLIT_OUTPUT_DIR" -o "$OUTPUT_DIR"
fi

# Step 3: Game state pipeline (future implementation)
if [ "$GAME_STATE_PIPELINE" = true ]; then
    echo "Step 3: Running game state pipeline..."
    # TODO: add game state pipeline here
    echo "Game state pipeline completed."
fi

# Step 4: Dribble detection (future implementation)
if [ "$DRIBLE_DETECTION" = true ]; then
    echo "Step 4: Running dribble detection..."
    # TODO: add dribble detection here
    echo "Dribble detection completed."
fi

echo "Pipeline completed successfully!"
