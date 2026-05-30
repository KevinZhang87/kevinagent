#!/bin/bash
set -e

# ============================================
# KevinAgent - Helm Deployment Script
# ============================================

RELEASE_NAME=${RELEASE_NAME:-"kevin-agent"}
NAMESPACE=${NAMESPACE:-"kevin-agent"}
CHART_DIR="$(dirname "$0")/helm/kevin-agent"

echo "============================================"
echo "  KevinAgent - Helm Deployment"
echo "============================================"
echo ""

# Check helm
if ! command -v helm &> /dev/null; then
  echo "Error: helm is not installed"
  exit 1
fi

# Create namespace
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

# Install or upgrade
echo "Installing/upgrading Helm release..."
helm upgrade --install ${RELEASE_NAME} ${CHART_DIR} \
  --namespace ${NAMESPACE} \
  --set secrets.openaiApiKey="${OPENAI_API_KEY}" \
  --set secrets.anthropicApiKey="${ANTHROPIC_API_KEY}" \
  --set secrets.deepseekApiKey="${DEEPSEEK_API_KEY}" \
  --set secrets.moonshotApiKey="${MOONSHOT_API_KEY}" \
  --set secrets.glmApiKey="${GLM_API_KEY}" \
  --wait \
  --timeout 5m

echo ""
echo "Deployment complete!"
echo ""
echo "Check status:"
echo "  helm -n ${NAMESPACE} status ${RELEASE_NAME}"
echo "  kubectl -n ${NAMESPACE} get pods"
echo ""
echo "Access the app:"
echo "  kubectl -n ${NAMESPACE} port-forward svc/${RELEASE_NAME}-frontend 3000:3000"
echo "  Then open http://localhost:3000"
