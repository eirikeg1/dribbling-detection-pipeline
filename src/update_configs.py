from argparse import ArgumentParser
import os
import shutil

GAME_STATE_RECOGNITION_CONFIG = "dependencies/sn-gamestate/sn_gamestate/configs/soccernet.yaml"
PNL_CALIB_CONFIG = "dependencies/sn-gamestate/sn_gamestate/configs/modules/pitch/pnlcalib.yaml"
YOLO_MODEL_CONFIG = "dependencies/tracklab/tracklab/configs/modules/bbox_detector/yolo11.yaml"


def update_yaml_file(file_path, replacements):
    """
    Reads a YAML file, replaces lines based on keys in the replacements dict,
    and writes the updated content back to the file.
    """
    with open(file_path, 'r') as file:
        lines = file.readlines()

    updated_lines = []
    for line in lines:
        stripped_line = line.strip()
        replaced = False
        for key, new_line in replacements.items():
            if stripped_line.startswith(key):
                updated_lines.append(new_line + "\n")
                replaced = True
                break
        if not replaced:
            updated_lines.append(line)

    with open(file_path, 'w') as file:
        file.writelines(updated_lines)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--yolo_player_model", type=str,
                        default="pretrained_models/yolo/yolo11s-player-best.pt",
                        help="Path to YOLO player model weights")
    parser.add_argument("--yolo_ball_model", type=str,
                        default="pretrained_models/yolo/yolo11s-ball-best.pt",
                        help="Path to YOLO ball model weights")
    parser.add_argument("--pnl_sv_kp_model", type=str,
                        default="pretrained_models/calibration/pnl_SV_kp",
                        help="Path to PnLCalib model weights")
    parser.add_argument("--pnl_sv_lines_model", type=str,
                        default="pretrained_models/calibration/pnl_SV_lines",
                        help="Path to PnLCalib model weights")
    parser.add_argument("--object-detection-config", type=str,
                        default="object-detection-config.yaml",
                        help="Path to object detection config file")

    args = parser.parse_args()

    # Update object detection config file
    print(f"Moving object detection config file '{args.object_detection_config}' to dependency location")
    shutil.copy(args.object_detection_config, GAME_STATE_RECOGNITION_CONFIG)

    # Prepare replacements for PnLCalib config file
    pnl_replacements = {
        "checkpoint_kp:": f"checkpoint_kp: ${{model_dir}}/{args.pnl_sv_kp_model}",
        "checkpoint_l:": f"checkpoint_l: ${{model_dir}}/{args.pnl_sv_lines_model}"
    }
    print("Updating PnLCalib config file with provided model weights")
    update_yaml_file(PNL_CALIB_CONFIG, pnl_replacements)

    # Prepare replacements for YOLO model config file
    yolo_replacements = {
        "path_to_checkpoint_player:": f'  path_to_checkpoint_player: "${{model_dir}}/{args.yolo_player_model}"',
        "path_to_checkpoint_ball:": f'  path_to_checkpoint_ball: "${{model_dir}}/{args.yolo_ball_model}"'
    }
    print("Updating YOLO model config file with provided model weights")
    update_yaml_file(YOLO_MODEL_CONFIG, yolo_replacements)
