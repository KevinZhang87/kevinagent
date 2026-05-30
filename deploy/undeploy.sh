#!/bin/bash
set -e

# ============================================
# KevinAgent - Undeploy Script
# ============================================

NAMESPACE="kevin-agent"
RELEASE_NAME="kevin-agent"

echo "============================================"
echo "  KevinAgent - Undeploy"
echo "============================================"
echo ""

echo "This will remove all KevinAgent resources from namespace '${NAMESPACE}'."
read -p "Are you sure? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 1
fi

# Try Helm uninstall first
if command -v helm &> /dev/null; then
  helm uninstall ${RELEASE_NAME} -n ${NAMESPACE} 2>/dev/null || true
fi

# Delete K8s resources
echo "Deleting K8s resources..."
kubectl delete -f k8s/ingress.yaml --ignore-not-found
kubectl delete -f k8s/frontend-service.yaml --ignore-not-found
kubectl delete -f k8s/frontend-deployment.yaml --ignore-not-found
kubectl delete -f k8s/backend-service.yaml --ignore-not-found
kubectl delete -f k8s/backend-deployment.yaml --ignore-not-found
kubectl delete -f k8s/pvc.yaml --ignore-not-found
kubectl delete -f k8s/secret.yaml --ignore-not-found
kubectl delete -f k8s/configmap.yaml --ignore-not-found
kubectl delete -f k8s/namespace.yaml --ignore-not-found

echo ""
echo "Undeploy complete!"
