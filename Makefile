.PHONY: dev build deploy-helm deploy-k8s undeploy clean

# ============================================
# Development
# ============================================

dev:
	@echo "Starting development servers..."
	@cd backend && python run.py &
	@cd frontend && npm run dev

dev-backend:
	@cd backend && python run.py

dev-frontend:
	@cd frontend && npm run dev

# ============================================
# Docker Build
# ============================================

build:
	@bash deploy/build.sh

build-backend:
	@docker build -t kevin-agent/backend:latest -f backend/Dockerfile backend/

build-frontend:
	@docker build -t kevin-agent/frontend:latest -f frontend/Dockerfile frontend/

# ============================================
# K8s Deployment (Raw Manifests)
# ============================================

deploy-k8s:
	@bash deploy/deploy-k8s.sh

# ============================================
# Helm Deployment
# ============================================

deploy-helm:
	@bash deploy/deploy-helm.sh

# ============================================
# Undeploy
# ============================================

undeploy:
	@bash deploy/undeploy.sh

# ============================================
# Clean
# ============================================

clean:
	@echo "Cleaning build artifacts..."
	@rm -rf backend/__pycache__ backend/app/__pycache__ backend/app/**/__pycache__
	@rm -rf frontend/.next frontend/node_modules
	@rm -f backend/kevin.db
	@echo "Clean complete."
