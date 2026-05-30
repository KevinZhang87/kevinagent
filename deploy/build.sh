#!/bin/bash
set -e

# ============================================
# KevinAgent - Docker Build Script
# ============================================

REGISTRY=${REGISTRY:-""}
TAG=${TAG:-"latest"}
PUSH=${PUSH:-"false"}

echo "============================================"
echo "  KevinAgent - Docker Build"
echo "============================================"
echo ""

# Build backend
echo "[1/2] Building backend image..."
docker build -t ${REGISTRY}kevin-agent/backend:${TAG} -f backend/Dockerfile backend/
echo "  -> ${REGISTRY}kevin-agent/backend:${TAG}"

# Build frontend
echo "[2/2] Building frontend image..."
docker build \
  --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 \
  --build-arg NEXT_PUBLIC_WS_URL=ws://localhost:8000 \
  -t ${REGISTRY}kevin-agent/frontend:${TAG} -f frontend/Dockerfile frontend/
echo "  -> ${REGISTRY}kevin-agent/frontend:${TAG}"

echo ""

if [ "$PUSH" = "true" ]; then
  echo "Pushing images..."
  docker push ${REGISTRY}kevin-agent/backend:${TAG}
  docker push ${REGISTRY}kevin-agent/frontend:${TAG}
fi

echo "Build complete!"
echo ""
echo "Images:"
echo "  - ${REGISTRY}kevin-agent/backend:${TAG}"
echo "  - ${REGISTRY}kevin-agent/frontend:${TAG}"
