#!/usr/bin/env bash
set -euo pipefail

# Arrays of keywords and years
KEYWORDS=("La liga" "Serie A" "Premier League" "Bundesliga" "Ligue 1")
YEARS=(2017 2018 2019 2020 2021 2022 2023 2024)

# Loop over each year, then each keyword
for year in "${YEARS[@]}"; do
  for keyword in "${KEYWORDS[@]}"; do

    # Compose the search query
    search_term="${year} ${keyword} dribbling compilation"

    # Create a "safe" version of the search term for the output filename
    safe_search_term="$(echo "${search_term}" | tr ' ' '-')"
    
    echo "Searching and downloading video for: ${search_term}"
    
    # Download the first video that matches the filter: duration > 20 minutes (1200 seconds)
    yt-dlp \
      "ytsearch1:${search_term}" \
      --match-filter "duration > 1200" \
      --ignore-errors \
      --recode-video mp4 \
      -o "${safe_search_term} - %(title)s.%(ext)s"

    echo "------------------------------------------------"
  done
done

echo "All downloads completed."
