# Dribling Detection Pipeline

## Pipeline Steps

1. Split the video into shorter video clips on scene change (different camera angles, zoom, etc.)
2. Restructure data to soccernet format
3. Run modified game state recognition pipeline (for player bounding boxes, 2d coordinates and teams)
4. Restructure data from game state recognition output format to dribling detection output
5. Run dribling detection algorithm on data

## Installation

### 1. Clone repository
This includes this repository, as well as the two dependancy repositories:
```bash
    git clone git@github.com:eirikeg1/dribbling-detection-pipeline.git
    cd dribbling-detection-pipeline
```

### 2. Install dependencies
All steps are optional, you do not need to download the steps which are deactivated in `config.env`.

#### 1. Create conda environment
```bash
    conda create -n dribling-detection pip python=3.10 pytorch==1.13.1 torchvision==0.14.1 pytorch-cuda=11.7 -c pytorch -c nvidia -y
    conda activate dribling-detection
```

#### 2. Video splitting
```bash
    pip install scenedetect
    conda install -c conda-forge ffmpeg
    conda install -c conda-forge x264
```

#### 3. Object position annotation pipeline
```bash
    # Download repositories
    mkdir dependencies
    cd dependencies
    git clone https://github.com/eirikeg1/sn-gamestate-fork.git sn-gamestate
    git clone https://github.com/eirikeg1/tracklab-fork.git tracklab

    # Install dependencies
    cd sn-gamestate
    pip install -e .
    pip install -e ../tracklab
    mim install mmcv==2.0.1
``` 

#### 4. Dribbling detection pipeline

## Run:

Some configurations can be changed in `config.env`. You can use custom config files, which can be
changed with the `-c` flag. This includes different directory paths and what parts of the pipeline
to run.

All steps requires outputs from the previous step to be done by default. By changing the directories
(or moving files) in the `config.env` this can be fixed. (object detection config in `dependency` 
folder should also be changed if data-formatting is not run)

```bash
./src/run_pipeline.sh -i <input-video> [optional-args]
```

### Arguments
- `-i <input-video>`: (required) Path to the input video file
- `-c <config-file>`: (optional, `config.env` is default) Path to the configuration file
- `-t <temp-file-dir>`: (optional, `temp_files` is default) Path to a directory for temporary files 
    during runtime. Make sure this folder is unique across runs if running in parallel. The folder 
    is created if it does not already exist

For example:
```bash
./src/run_pipeline.sh -i my-video.mp4 -c custom-config.env
```
