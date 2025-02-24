#!/bin/bash

set -e  # Exit on error
start_time=$SECONDS  # Start timer

# ==================================================================================================
# Parsing arguments and config

config_file="config.env"
input_video=""
tmp_file_dir="temp_files" # Use unique directory for parallel runs; folder is automatically created
frame_interval=1
delete_all_data=true # Whether to keep all intermediate data or not, includes data before restructuring, interpolating and predicting

log=""

# Parse input arguments
while getopts "c:i:t:f:k" flag; do
    case "${flag}" in
        c) config_file=${OPTARG} ;;
        i) input_video=${OPTARG} ;;
        t) tmp_file_dir=${OPTARG} ;;
        f) frame_interval=${OPTARG} ;;
        k) delete_all_data=false ;;
        *)
            echo "Usage: bash run_pipeline.sh [-c <config-file.env>] -i <input-video> [-t <tmp_file_dir>] [-f <frame_interval>] [-k]"
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
    log+="Video splitting completed.\n"
fi

# Step 2: Remove video clips without enough detections, or too big bounding boxes
if [ "$FILTER_VIDEO_CLIPS" = true ]; then
    echo "Step 2: Filtering video clips..."
    python3 src/remove_unwanted_scenes.py --video_dir "$SPLIT_OUTPUT_DIR" --model "$MODEL_DIR/$YOLO_PLAYER_MODEL"

    echo "Filtering video clips completed."
    log+="Filtering video clips completed.\n"
fi

# Step 3: Restructure data to SoccerNet format
if [ "$FORMAT_VIDEO" = true ]; then
    echo "Step 3: Restructuring data to SoccerNet format..."
    python3 src/format_to_soccernet.py \
        -i "$SPLIT_OUTPUT_DIR" \
        -o "$OUTPUT_DIR" \
        --object_detection_config "object-detection-config.yaml" \
        --temp_file_dir "$tmp_file_dir" \
        --frame_interval "$frame_interval" \
        --delete_processed_videos "$delete_all_data"

    echo "Restructuring data to SoccerNet format completed."
    log+="Restructuring data to SoccerNet format completed.\n"
fi

# Step 4: Game state pipeline
if [ "$GAME_STATE_PIPELINE" = true ]; then
    # Step 4.1: Update configuration files using update_configs.py
    echo "Updating configuration files using update_configs.py..."
    python3 src/update_configs.py \
        --object-detection-config "object-detection-config.yaml" \
        --yolo_player_model "$YOLO_PLAYER_MODEL" \
        --yolo_ball_model "$YOLO_BALL_MODEL" \
        --pnl_sv_kp_model "$PNL_KP_MODEL" \
        --pnl_sv_lines_model "$PNL_LINES_MODEL"
    echo "Configuration update completed."

    # 4.2 Run object detection, tracking, homography transformation etc.
    echo "Step 4: Running game state pipeline..."
    python -m tracklab.main -cn soccernet
    echo "Game state pipeline completed."

    # 4.3 Reformat the predictions to standard SoccerNet format
    echo "Reformatting predictions to SoccerNetGSR input format..."
    data_dir="$(cat "${tmp_file_dir}/data_dir.txt")"  # data_dir was written to file in step 2
    python src/format_predictions_to_annotations.py --data_dir "$data_dir"

    # 4.4 Interpolate missing annotations
    echo "Interpolating annotations"
    python src/interpolate_annotations.py --data_dir "$data_dir"

    echo "Object detection pipeline completed."
    log+="Object detection pipeline completed.\n"
fi

# Step 5: Dribble detection (future implementation)
if [ "$DRIBLE_DETECTION" = true ]; then
    echo "Step 4: Running dribble detection..."
    # TODO: add dribble detection here
    echo "Dribble detection completed."
    log+="Dribble detection completed.\n"
fi

end_time=$SECONDS
elapsed_time=$((end_time - start_time))
elapsed_hours=$((elapsed_time / 3600))
elapsed_minutes=$(((elapsed_time % 3600) / 60))
elapsed_seconds=$((elapsed_time % 60))
echo "Pipeline completed successfully in ${elapsed_hours}h:${elapsed_minutes}m:${elapsed_seconds}s!"
log+="Pipeline completed successfully in ${elapsed_hours}h:${elapsed_minutes}m:${elapsed_seconds}s!\n"

echo "$log" >> "$OUTPUT_DIR/pipeline-log.txt"

# # Step 5: Clean up
# if [ "$delete_all_data" = true ]; then
#     echo "Cleaning up temporary files and data..."
    
#     mkdir -p "$OUTPUT_DIR/game-state-configs"  

#     # Check and remove directories if they exist
#     [ -d "$tmp_file_dir" ] && rm -rf "$tmp_file_dir"
#     [ -d "$OUTPUT_DIR/game-state-output" ] && rm -rf "$OUTPUT_DIR/game-state-output"
#     [ -d "$OUTPUT_DIR/formatted-predictions" ] && rm -rf "$OUTPUT_DIR/formatted-predictions"
#     [ -d "$OUTPUT_DIR/train" ] && rm -rf "$OUTPUT_DIR/train"
# fi
