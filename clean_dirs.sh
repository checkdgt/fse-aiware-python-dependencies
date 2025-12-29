#! /bin/bash

exec < 'my_gists.csv'

file_to_keep="snippet.py"

while IFS= read -r location
do
    # rm -r $location/modules
    subdir=$(echo "$location" | awk -F'/' '{print $(NF-1) "/" $NF}')
    echo $subdir
    find "$subdir" -mindepth 1 ! -name "$file_to_keep" -exec rm -rf {} +
done
