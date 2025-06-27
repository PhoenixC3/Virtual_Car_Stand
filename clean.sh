#!/bin/bash

# May need to run `chmod +x clean.sh` to make this script executable

echo "CLEANING UP..."

kubectl delete services --all
kubectl delete deployments --all
kubectl delete configmaps --all
kubectl delete pvc --all
kubectl delete jobs --all
kubectl delete pods --all
kubectl delete --all hpa
kubectl delete secrets --all

echo ""
echo "ALL CLEANED!"