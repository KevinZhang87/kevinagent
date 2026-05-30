#!/bin/bash
set -e

# ============================================
# KevinAgent - K8s Deployment Script
# ============================================

NAMESPACE="kevin-agent"
K8S_DIR="$(dirname "$0")/k8s"

echo "============================================"
echo "  KevinAgent - K8s Deployment"
echo "============================================"
echo ""

# Check kubectl
if ! command -v kubectl &> /dev/null; then
  echo "Error: kubectl is not installed"
  exit 1
fi

# Apply manifests
echo "[1/4] Creating namespace..."
kubectl apply -f ${K8S_DIR}/namespace.yaml

echo "[2/4] Applying ConfigMap and Secret..."
kubectl apply -f ${K8S_DIR}/configmap.yaml
echo ""
echo "  IMPORTANT: Edit ${K8S_DIR}/secret.yaml to set your API keys before continuing!"
echo "  Then run: kubectl apply -f ${K8S_DIR}/secret.yaml"
echo ""
read -p "  Have you configured the secrets? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted. Please configure secrets first."
  exit 1
fi
kubectl apply -f ${K8S_DIR}/secret.yaml

echo "[3/4] Creating PVC..."
kubectl apply -f ${K8S_DIR}/pvc.yaml

echo "[4/4] Deploying applications..."
kubectl apply -f ${K8S_DIR}/backend-deployment.yaml
kubectl apply -f ${K8S_DIR}/backend-service.yaml
kubectl apply -f ${K8S_DIR}/frontend-deployment.yaml
kubectl apply -f ${K8S_DIR}/frontend-service.yaml
kubectl apply -f ${K8S_DIR}/ingress.yaml

echo ""
echo "Deployment complete!"
echo ""
echo "Check status:"
echo "  kubectl -n ${NAMESPACE} get pods"
echo "  kubectl -n ${NAMESPACE} get svc"
echo "  kubectl -n ${NAMESPACE} get ingress"
echo ""
echo "Access the app:"
echo "  kubectl -n ${NAMESPACE} port-forward svc/kevin-frontend 3000:3000"
echo "  Then open http://localhost:3000"
