# Dribling Detection Pipeline

## Steps

1. Split the video (split_video_script.sh)
2. Restructure data to soccernet format
3. Run modified game state recognition pipeline (for player bounding boxes, 2d coordinates and teams)
4. Run dribling detection algorithm on data

## Run:

Some configurations can be changed in `config.env`. You can use custom config files, which can be
changed with the `-c` flag.

```bash
./src/run_pipeline.sh -i <input-video> [optional-args]
```

### Arguments
- `-i <input-video>`: Path to the input video file (required)
- `-c <config-file>`: Path to the configuration file (optional, `config.env` from root is default)

For example:
```bash
./src/run_pipeline.sh -i my-video.mp4 -c custom-config.env
```

