#!/bin/bash

# ==== Configuration ====
CONTAINER_NAME="neo4j_import_test"
IMAGE_NAME="neo4j:latest"  # Specifying latest to ensure compatibility
HTTP_PORT=7474
BOLT_PORT=7687

# These should be full paths (replace with your actual paths)
GRAPH_PATH="$(pwd)/$1"
DATA_PATH="$(pwd)/neo4j_data"  # Persistent data directory
LOGS_PATH="$(pwd)/logs"

NEO4J_USER="neo4j"
NEO4J_PASSWORD="neo4jroot"

# ==== Ensure directories exist ====
mkdir -p "$DATA_PATH"
mkdir -p "$LOGS_PATH"

# ==== Cleanup any previous container ====
docker stop $CONTAINER_NAME 2>/dev/null
docker rm $CONTAINER_NAME 2>/dev/null

# ==== First, create a container just for importing data ====
echo "Running neo4j-admin import..."
docker run --rm \
  -v "$GRAPH_PATH":/import \
  -v "$DATA_PATH":/data \
  $IMAGE_NAME \
  neo4j-admin database import full \
    --overwrite-destination \
    --nodes=/import/nodes.csv \
    --relationships=/import/rels.csv \
    --delimiter='¿' \
    --skip-bad-relationships=true \
    --skip-duplicate-nodes=true \
    --high-parallel-io=on

# ==== Now start Neo4j with the imported database ====
echo "Starting Neo4j container with imported database..."
docker run -d \
  --name $CONTAINER_NAME \
  -p ${HTTP_PORT}:7474 \
  -p ${BOLT_PORT}:7687 \
  -v "$GRAPH_PATH":/import \
  -v "$DATA_PATH"/databases:/data/databases \
  -v "$DATA_PATH"/transactions:/data/transactions \
  -e NEO4J_AUTH="${NEO4J_USER}/${NEO4J_PASSWORD}" \
  -e NEO4J_dbms_allow__upgrade=true \
  -e NEO4J_dbms_directories_import=/import \
  -e NEO4J_dbms_memory_heap_initial__size=512m \
  -e NEO4J_dbms_memory_heap_max__size=1G \
  $IMAGE_NAME

# ==== Wait and check if container is running ====
echo "Waiting for Neo4j to start..."
sleep 5

if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    echo "Container is running. Waiting for Neo4j to initialize..."
    # Wait longer for Neo4j to initialize
    ATTEMPTS=0
    MAX_ATTEMPTS=30
    
    while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
        ATTEMPTS=$((ATTEMPTS+1))
        
        if docker logs $CONTAINER_NAME 2>&1 | grep -q "Started"; then
            echo "Neo4j has successfully started!"
            break
        fi
        
        if [ $ATTEMPTS -eq $MAX_ATTEMPTS ]; then
            echo "Neo4j didn't start properly. Check logs:"
            docker logs $CONTAINER_NAME
            exit 1
        fi
        
        echo "Waiting... (Attempt $ATTEMPTS of $MAX_ATTEMPTS)"
        sleep 5
    done
    
    # ==== Display connection information ====
    echo "Neo4j is now running!"
    echo "Web interface: http://localhost:${HTTP_PORT}"
    echo "Bolt connection: bolt://localhost:${BOLT_PORT}"
    echo "Username: ${NEO4J_USER}"
    echo "Password: ${NEO4J_PASSWORD}"
    
    # ==== Connect to cypher-shell ====
    echo "Connecting to cypher-shell..."
    docker exec -it $CONTAINER_NAME cypher-shell -u ${NEO4J_USER} -p ${NEO4J_PASSWORD} --address=bolt://localhost:7687
else
    echo "Container failed to start. Check logs:"
    docker logs $CONTAINER_NAME
fi

docker rm -f neo4j_import_test