#!/bin/bash


# ==================================================================================================
# Parsing arguments

set -e # Exit on error

config_file=""
input_video=""

# Parse input arguments
while getopts "c:i:" flag; do
    case "${flag}" in
        c) config_file=${OPTARG} ;;
        i) input_video=${OPTARG} ;;
        *)
            echo "Usage: bash run_pipeline.sh -c <config-file.env> -i <input-video>"
            exit 1
            ;;
    esac
done

# Check if config file is provided
if [ -z "$config_file" ]; then
    echo "Error: Config file is required."
    echo "Usage: bash run_pipeline.sh -c <config-file.env> -i <input-video>"
    exit 1
fi

# Load the config file
if [ -f "$config_file" ]; then
    source "$config_file"
else
    echo "Error: Config file not found: $config_file"
    exit 1
fi

# Check if input video file is provided
if [ -z "$input_video" ]; then
    echo "Error: Input video file is required."
    echo "Usage: bash run_pipeline.sh -c <config-file.env> -i <input-video>"
    exit 1
fi



# ==================================================================================================
# Run the pipeline

# Step 1: Split the video
echo "Step 1: Splitting the video..."
bash src/split_video_script.sh -i "$input_video" -o "$OUTPUT_DIR"
echo "Video splitting completed."

# Step 2: Restructure data to SoccerNet format
echo "Step 2: Restructuring data to SoccerNet format..."
python3 src/format_to_soccernet.py -i "$OUTPUT_DIR" -o "$OUTPUT_DIR"
echo "Data restructuring completed."

echo "Pipeline completed successfully!"
