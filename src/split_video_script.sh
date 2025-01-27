#!/bin/bash

# Default output folder is the current directory
output_folder="."

# Parse input arguments
while getopts "i:o:" flag; do
    case "${flag}" in
        i) input_file=${OPTARG} ;;
        o) output_folder=${OPTARG} ;;
        *) 
            echo "Usage: $0 -i <input_file> [-o <output_folder>]"
            exit 1
            ;;
    esac
done

# Check if input file is provided
if [ -z "$input_file" ]; then
    echo "Error: Input file is required."
    echo "Usage: $0 -i <input_file> [-o <output_folder>]"
    exit 1
fi

# Create the output folder if doesn't exist
mkdir -p "$output_folder"

# Run the scenedetect command
scenedetect -i "$input_file" detect-hist split-video -hq -o "$output_folder"


echo "Scene detection and splitting complete."
echo "Output stored in: $output_folder"
