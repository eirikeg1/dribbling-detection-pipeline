#!/usr/bin/env bash
set -euo pipefail

# Arrays of keywords and years
KEYWORDS=("Barcelona" "Real Madrid" "Atletico Madrid" "Manchester United" "Liverpool" "Chelsea" "Arsenal" "Manchester City" "Tottenham" "Newcastle" "Juventus" "Napoli" "Inter" "AC Milan" "Roma" "Bayern Munchen" "Dortmund" "PSG" "Brazil" "Argentina" "Germany" "England" "France" "Spain" "Italy" "Portugal")
YEARS=("2019-20" "2020-21" "2021-22" "2022-23" "2023-24" "2024-25")

# Loop over each year, then each keyword
for year in "${YEARS[@]}"; do
  for keyword in "${KEYWORDS[@]}"; do

    # Compose the search query
    search_term="soccer ${keyword} ${year} full match"

    # Format the search term to snake case for the file name
    safe_search_term="$(echo "${search_term}" | tr ' ' '-')"
    
    echo "Searching and downloading videos for: ${search_term}"
    
    # Download the first 5 videos that match the filter: duration > 70 minutes (4200 seconds)
    yt-dlp \
      "ytsearch5:${search_term}" \
      --match-filter "duration > 4200" \
      --ignore-errors \
      --recode-video mp4 \
      -o "${safe_search_term}-%(playlist_index)s-%(title)s.%(ext)s"

    echo "------------------------------------------------"
  done
done

echo "All downloads completed."
