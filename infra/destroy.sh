#!/usr/bin/env bash
# =============================================================================
# AWS MCP Server — Teardown Script
# Removes all resources created by deploy.sh
# Run from project root:  bash infra/destroy.sh
# =============================================================================
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="aws-mcp-server-deploy-${ACCOUNT_ID}"
ROLE_NAME="aws-mcp-server-role"
PROFILE_NAME="aws-mcp-server-profile"
SG_NAME="aws-mcp-server-sg"
INSTANCE_NAME="aws-mcp-server"

RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${RED}[destroy]${NC} $*"; }

# Terminate EC2 instance
info "Terminating EC2 instance(s) tagged Name=$INSTANCE_NAME ..."
INSTANCE_IDS=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running,stopped,pending" \
  --query "Reservations[].Instances[].InstanceId" \
  --output text --region "$REGION")

if [ -n "$INSTANCE_IDS" ] && [ "$INSTANCE_IDS" != "None" ]; then
  aws ec2 terminate-instances --instance-ids $INSTANCE_IDS --region "$REGION" --output json > /dev/null
  info "Waiting for termination..."
  aws ec2 wait instance-terminated --instance-ids $INSTANCE_IDS --region "$REGION"
  info "Instances terminated."
else
  info "No running instances found."
fi

# Delete security group (wait a moment for ENIs to detach)
info "Deleting security group: $SG_NAME ..."
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" --output text --region "$REGION")
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query "SecurityGroups[0].GroupId" --output text --region "$REGION" 2>/dev/null || echo "")
if [ -n "$SG_ID" ] && [ "$SG_ID" != "None" ]; then
  sleep 5
  aws ec2 delete-security-group --group-id "$SG_ID" --region "$REGION" 2>/dev/null && info "Deleted $SG_ID" || info "Could not delete $SG_ID (may still have dependencies)"
else
  info "Security group not found."
fi

# Remove IAM role from instance profile and delete profile
info "Cleaning up IAM instance profile: $PROFILE_NAME ..."
aws iam remove-role-from-instance-profile \
  --instance-profile-name "$PROFILE_NAME" \
  --role-name "$ROLE_NAME" 2>/dev/null || true
aws iam delete-instance-profile \
  --instance-profile-name "$PROFILE_NAME" 2>/dev/null && info "Deleted instance profile." || info "Instance profile not found."

# Detach all policies from role then delete role
info "Cleaning up IAM role: $ROLE_NAME ..."
ATTACHED=$(aws iam list-attached-role-policies --role-name "$ROLE_NAME" \
  --query "AttachedPolicies[].PolicyArn" --output text 2>/dev/null || echo "")
for arn in $ATTACHED; do
  aws iam detach-role-policy --role-name "$ROLE_NAME" --policy-arn "$arn" 2>/dev/null || true
done
aws iam delete-role --role-name "$ROLE_NAME" 2>/dev/null && info "Deleted IAM role." || info "IAM role not found."

# Empty and delete S3 bucket
info "Deleting S3 bucket: $BUCKET ..."
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  aws s3 rm "s3://$BUCKET" --recursive 2>/dev/null || true
  aws s3api delete-bucket --bucket "$BUCKET" --region "$REGION" && info "Deleted S3 bucket."
else
  info "S3 bucket not found."
fi

echo ""
echo "============================================================"
echo "  All AWS MCP Server resources have been removed."
echo "============================================================"
