#!/usr/bin/env python3
import os
import json
import sys

# Input path from command line
input_path = sys.argv[1]

def get_index_file(file_path):
    if os.path.isdir(file_path):
        # Directory contains a package.json file
        if os.path.exists(os.path.join(file_path, "package.json")):
            with open(os.path.join(file_path, "package.json"), "r") as f:
                package_json = json.load(f)

                # Get the main field
                main = package_json.get("main", None)
                if main:
                    main = os.path.normpath(main)
                    # Check if it has a file extension
                    if not main.endswith(".js") and not main.endswith(".mjs") and not main.endswith(".cjs"):
                        main += ".js"
                    # Check if main is a directory with only one file
                    if os.path.isdir(os.path.join(file_path, main)):
                        main_files = os.listdir(os.path.join(file_path, main))
                        if len(main_files) == 1:
                            main = os.path.join(main, main_files[0])
                    print(f"Using main file: {main}", file=sys.stderr)
                    return os.path.join(file_path, main)

        # No package.json file, check for default entry file
        print(f"No 'main' field found. Looking for default entry point...", file=sys.stderr)

        # List of possible locations where the main file might be
        possible_files = [
            'index.js',  # Default main file
            'lib/index.js',  # Common folder for libraries
            'src/index.js',  # Common folder for source files
            'dist/index.js'  # Common folder for distribution files
        ]

        for file in possible_files:
            file_path_check = os.path.join(file_path, file)
            if os.path.exists(file_path_check):
                print(f"Found default entry point: {file}", file=sys.stderr)
                return file_path_check

        # If no default entry point is found, exit
        sys.exit(f"No default entry point found in directory: {file_path}")
    
    # If it's already a file, just return it
    return file_path

# Get the index file and print it for the bash script to capture
actual_file = get_index_file(input_path)
print(actual_file)