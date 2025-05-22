#!/bin/bash

rm -r output/
mkdir output

# Get current and parent dir
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PARENT_DIR=$(dirname "${SCRIPT_DIR}")

# Display help
Help()
{
    echo "Usage: ./graphjs_hybrid.sh -i <path> [options]"
    echo "Description: Run Graph.js MDG generation locally and queries in a Neo4j Docker container."
    echo ""
    echo "Required:"
    echo "-i <path>    Input path (filename to run specific file or directory to run package level)."
    echo ""
    echo "Options:"
    echo "-o <path>    Path to store analysis results."
    echo "-e           Create exploit template (implies --with-types)."
    echo "-t           Generate taint summary with type information."
    echo "-s           Silent mode: Does not save graph .svg."
    echo "-q <type>    Query type: 'bottom_up_greedy' or 'intra' (default: bottom_up_greedy)."
    echo "-d           Don't clean output dir if it exists (dirty)."
    echo "--optimized  Try optimized import without stopping neo4j."
    echo "-h           Print this help."
    echo
}

# Default values
SILENT_MODE=false
WITH_TYPES=false
EXPLOIT=False
DIRTY=false
OPTIMIZED=False
QUERY_TYPE="bottom_up_greedy"
PY_FLAGS=""

while getopts "i:o:estq:d-:h" flag; do
    case "${flag}" in
        i) INPUT_PATH=$OPTARG
            INPUT_PATH="$( realpath "$INPUT_PATH" )"
            if [ ! -f "$INPUT_PATH" ] && [ ! -d "$INPUT_PATH" ]; then
                echo "File $OPTARG does not exist."
                exit 1
            fi;;
        o) OUTPUT_PATH=$OPTARG
            OUTPUT_PATH="$( realpath "$OUTPUT_PATH" )"
            if [ ! -d "$OUTPUT_PATH" ]; then
                echo "Output path $OPTARG does not exist. Creating new directory."
                mkdir -p $OUTPUT_PATH
            fi;;
        e) EXPLOIT=true
            PY_FLAGS+=" -e";;
        s) SILENT_MODE=true
            PY_FLAGS+=" -s";;
        t) WITH_TYPES=true
            PY_FLAGS+=" --with-types";;
        q) QUERY_TYPE=$OPTARG
            PY_FLAGS+=" -q $OPTARG";;
        d) DIRTY=true
            PY_FLAGS+=" --dirty";;
        -) case "${OPTARG}" in
                optimized) OPTIMIZED=true
                    PY_FLAGS+=" --optimized-import";;
                *) echo "Invalid option: --${OPTARG}"
                    Help
                    exit 1;;
            esac;;
        :?h) Help
            exit;;
    esac
done

# Check if the required input path is provided
if [ ! -f "$INPUT_PATH" ] && [ ! -d "$INPUT_PATH" ]; then
  echo "Option -i is required."
  Help
  exit 1
fi

# If output_path is not provided, use default
if [ -z "$OUTPUT_PATH" ]; then
    # Generate output file
    # If path is a directory, go up one level only
    if [ -d "$INPUT_PATH" ]; then
        file_parent_dir=$(dirname "$INPUT_PATH")
    else
        file_parent_dir=$(dirname "$(dirname "$INPUT_PATH")")        
    fi
    OUTPUT_PATH="$file_parent_dir/tool_outputs/graphjs"
    mkdir -p ${OUTPUT_PATH}
fi

INPUT_DIR=$(dirname "$INPUT_PATH")
FNAME=$(basename "$INPUT_PATH")
GRAPH_OUTPUT="${OUTPUT_PATH}/graph"
RUN_OUTPUT="${OUTPUT_PATH}/run"

# Create necessary directories
mkdir -p "$GRAPH_OUTPUT"
mkdir -p "$RUN_OUTPUT"

# Check if the input is a directory and find the main index file
if [ -d "$INPUT_PATH" ]; then
    echo "Input is a directory. Finding the main index file..."
    # Create a helper Python script to find the index file
    ACTUAL_FILE=$(python3 find_index_file.py "$INPUT_PATH")
    if [ $? -ne 0 ]; then
        echo "Error finding index file in directory."
        exit 1
    fi
    echo "Using file: $ACTUAL_FILE"
    INPUT_PATH="$ACTUAL_FILE"
fi

echo "[STEP 1] Running MDG generation locally..."
# Run MDG generation locally using node directly
# First, load the constants from your constants.py file to get the MDG path
MDG_PATH=$(python3 -c "import constants; print(constants.MDG_PATH)")
# Run the MDG generator
ABS_INPUT_PATH=$(realpath "$INPUT_PATH")
node $MDG_PATH -f "$ABS_INPUT_PATH" -o "$GRAPH_OUTPUT" --csv --silent

# Stop after MDG generation but before query execution
echo "[STEP 2] Local MDG generation complete. Preparing Neo4j Docker for query execution..."

# Build neo4j docker image if it does not exist
# Build docker image if it does not exist
if [ -z "$(docker images -q graphjs)" ]; then
    docker build . -t graphjs
fi

# Run the Neo4j Docker container for query execution
echo "[STEP 3] Running queries in Neo4j Docker container..."
docker run -it \
    -v "${INPUT_DIR}":/input \
    -v "${OUTPUT_PATH}":/output_path \
    graphjs \
    /bin/bash -c "sudo chown graphjs:graphjs -R /output_path; \
                  python3 -c \"
import sys
import os
sys.path.insert(0, os.getcwd())
import detection.neo4j_import.neo4j_management as neo4j_management
import detection.run as detection
import detection.utils as utils

# Define paths
file_path = '$(basename "$INPUT_PATH")'
if os.path.dirname('$INPUT_PATH') != '$INPUT_DIR':
    # If the input was a nested file in a directory
    rel_path = os.path.relpath('$INPUT_PATH', '$INPUT_DIR')
    file_path = '/input/' + rel_path
else:
    file_path = '/input/' + file_path
    
graph_path = '/output_path/graph'
run_path = '/output_path/run'
summary_path = '/output_path/taint_summary.json'
time_path = '/output_path/run/time_stats.txt'

# Print status
print('[STEP 3] Queries: Importing the graph...')

# Import CSV and run queries
neo4j_management.import_csv_local(graph_path, run_path)
print('[STEP 3] Queries: Imported')

# Perform graph traversals
print('[STEP 4] Queries: Traversing Graph...')
detection.traverse_graph(
    graph_path,
    file_path,
    summary_path,
    time_path,
    '$QUERY_TYPE',
    $EXPLOIT,
    optimized=$OPTIMIZED
)
print('[STEP 4] Queries: Completed.')
\" && \
chmod 777 -R /output_path;"

echo "Analysis complete. Results are available in $OUTPUT_PATH"