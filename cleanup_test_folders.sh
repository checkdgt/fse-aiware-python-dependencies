#!/bin/bash

# Script to clean up folders in local-test-gists
# Keeps only snippet.py and Dockerfile-llm-2.7, then renames Dockerfile-llm-2.7 to Dockerfile-llm

LOCAL_TEST_DIR="/Users/abartlett/Documents/code/pllm/pllm-passed"

echo "Starting cleanup process in: $LOCAL_TEST_DIR"

# Counter for tracking
processed_count=0
error_count=0

# Process each directory in local-test-gists
for folder in "$LOCAL_TEST_DIR"/*; do
    if [ -d "$folder" ]; then
        folder_name=$(basename "$folder")
        echo "Processing: $folder_name"
        
        # Change to the folder
        cd "$folder"
        
        # Check if required files exist
        if [ ! -f "snippet.py" ]; then
            echo "  WARNING: snippet.py not found in $folder_name"
            ((error_count++))
        fi
        
        if [ ! -f "Dockerfile-llm-2.7" ]; then
            echo "  WARNING: Dockerfile-llm-2.7 not found in $folder_name"
            ((error_count++))
        fi
        
        # Remove all files except snippet.py and Dockerfile-llm-2.7
        for file in *; do
            if [ "$file" != "snippet.py" ] && [ "$file" != "Dockerfile-llm-2.7" ]; then
                if [ -f "$file" ]; then
                    echo "  Removing file: $file"
                    rm "$file"
                elif [ -d "$file" ]; then
                    echo "  Removing directory: $file"
                    rm -rf "$file"
                fi
            fi
        done
        
        # Rename Dockerfile-llm-2.7 to Dockerfile-llm
        if [ -f "Dockerfile-llm-2.7" ]; then
            echo "  Renaming Dockerfile-llm-2.7 to Dockerfile-llm"
            mv "Dockerfile-llm-2.7" "Dockerfile-llm"
        fi
        
        echo "  Completed: $folder_name"
        ((processed_count++))
        
        # Go back to parent directory
        cd "$LOCAL_TEST_DIR"
    fi
done

echo ""
echo "Cleanup process completed!"
echo "Folders processed: $processed_count"
echo "Folders with errors: $error_count"

# Show final state
echo ""
echo "Final contents check (first 5 folders):"
count=0
for folder in "$LOCAL_TEST_DIR"/*; do
    if [ -d "$folder" ] && [ $count -lt 5 ]; then
        folder_name=$(basename "$folder")
        echo "Contents of $folder_name:"
        ls -la "$folder"
        echo ""
        ((count++))
    fi
done
