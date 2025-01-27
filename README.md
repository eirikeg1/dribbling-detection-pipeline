# Dribling Detection Pipeline

## Steps

1. Split the video (split_video_script.sh)
2. Restructure data to soccernet format
3. Run modified game state recognition pipeline (for player bounding boxes, 2d coordinates and teams)
4. Run dribling detection algorithm on data

## Run:
Fill out config file
```bash
./src/run_pipeline.sh -c <config-file.env> -i <input-video>
```

