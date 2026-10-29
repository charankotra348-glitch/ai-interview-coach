#!/usr/bin/env bash
# Build both images, push them to ECR, and roll the service onto them.
#
#   cd infra/aws && ./deploy.sh            # first run: creates everything (about 15 minutes)
#   ./deploy.sh                            # later runs: new images, same infrastructure
#
# Needs: AWS CLI v2 signed in (aws sts get-caller-identity works), Terraform >= 1.6, Docker.
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(git rev-parse --show-toplevel)"
TAG="$(git rev-parse --short HEAD)"
NAME="${NAME:-interview-coach}"   # must match var.name
REGION="$(terraform output -raw region 2>/dev/null || echo "${AWS_REGION:-us-east-1}")"

terraform init -input=false >/dev/null

# 1. The image repositories must exist before there is anything to push.
terraform apply -input=false -auto-approve -target='aws_ecr_repository.app' -var "name=$NAME"

REGISTRY="$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${REGION}.amazonaws.com"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"

# 2. ARM64 images (the task runs on Graviton), tagged with the commit.
for part in backend frontend; do
  docker buildx build --platform linux/arm64 -t "$REGISTRY/$NAME-$part:$TAG" --push "$ROOT/$part"
done

# 3. Everything else, pointing the task at the new tag. ECS replaces the running task and
#    rolls back by itself if the new one never becomes healthy.
terraform apply -input=false -auto-approve -var "image_tag=$TAG" -var "name=$NAME"

echo
echo "App: $(terraform output -raw url)"
echo "Logs: aws logs tail $(terraform output -raw log_group) --follow --region $REGION"
