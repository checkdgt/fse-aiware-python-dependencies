# Simple base script to create a list of folders into a file for running our gists
#! /bin/bash

folder_name=$1

for item in "$folder_name"/*; do
    echo $item >> my_gists.csv
done
