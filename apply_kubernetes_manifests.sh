#!/bin/bash

# May need to run `chmod +x apply_kubernetes_manifests.sh` to make this script executable

SERVICES=("car" "car_listing" "gateway" "inspection" "maintenance" "meeting" "transaction" "user")
K8S_DIR="k8s"
ENV_FILE=".env"

kubectl create secret generic all-credentials --from-env-file=${ENV_FILE}

kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/cloud/deploy.yaml

echo "📦 Applying Kubernetes manifests..."

kubectl apply -f ./${K8S_DIR}/databases/pvc-postgres.yaml
kubectl apply -f ./${K8S_DIR}/databases/deployment.yaml
kubectl apply -f ./${K8S_DIR}/databases/service.yaml

# Apply monitoring infrastructure
echo "🔍 Setting up monitoring infrastructure..."
kubectl create configmap prometheus-cm --from-file ${K8S_DIR}/monitoring/prometheus-cm.yaml
kubectl apply -f ./${K8S_DIR}/monitoring/prometheus.yaml
kubectl apply -f ./k8s/monitoring/grafana.yaml

for SERVICE in "${SERVICES[@]}"; do
  SERVICE_DIR="./${K8S_DIR}/${SERVICE}"
  if [ -d "$SERVICE_DIR" ]; then
    for FILE in $SERVICE_DIR/*.yaml; do
      echo "Applying ${FILE}..."
      kubectl apply -f "$FILE"
    done
  fi
done

echo "🌐 Setting up Ingress for gateway..."
kubectl apply -f ./ingress.yaml

echo ""
echo "🚀 Deployment complete!"
echo "🔎 Use 'kubectl get pods' to check status."
echo ""