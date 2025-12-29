#!/bin/bash

# Directory to search in
search_dir="./hard-gists-readpy"

# File name to search for
target_file="Dockerfile"

# Loop through all subdirectories
for subdir in "$search_dir"/*/; do
    if [ ! -f "$subdir$target_file" ]; then
        # echo "File found: $subdir$target_file"
        echo "File not found in: $subdir"
    fi
done
