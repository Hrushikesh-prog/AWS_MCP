#!/usr/bin/env bash
# =============================================================================
# AWS MCP Server — EC2 Deployment Script
# Deploys the MCP server on Amazon Linux 2023 with SSE transport
# Run from the project root:  bash infra/deploy.sh
# =============================================================================
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="aws-mcp-server-deploy-${ACCOUNT_ID}"
ROLE_NAME="aws-mcp-server-role"
PROFILE_NAME="aws-mcp-server-profile"
SG_NAME="aws-mcp-server-sg"
INSTANCE_NAME="aws-mcp-server"
INSTANCE_TYPE="t3.small"
PORT=8080

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[deploy]${NC} $*"; }

# ── Step 1: Package & upload source ──────────────────────────────────────────
info "Packaging source code..."
TMPZIP=$(mktemp /tmp/aws-mcp-XXXXXX.zip)
zip -qr "$TMPZIP" . \
  -x ".venv/*" -x "**/__pycache__/*" -x "__pycache__/*" \
  -x "*.pyc" -x ".git/*" -x ".env" -x ".env.*" \
  -x "claude_desktop_config.json" -x ".mcp.json" -x ".claude/*" \
  -x "aws_ledger.md" -x "infra/*"

info "Creating S3 bucket if needed..."
if aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
  warn "Bucket $BUCKET already exists — reusing."
else
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
    $([ "$REGION" != "us-east-1" ] && echo "--create-bucket-configuration LocationConstraint=$REGION" || echo "") \
    --output json > /dev/null
fi

info "Uploading source to s3://$BUCKET/source.zip ..."
aws s3 cp "$TMPZIP" "s3://${BUCKET}/source.zip" --region "$REGION"
rm -f "$TMPZIP"

# ── Step 2: IAM role + instance profile ──────────────────────────────────────
info "Creating IAM role: $ROLE_NAME ..."
if aws iam get-role --role-name "$ROLE_NAME" 2>/dev/null; then
  warn "Role $ROLE_NAME already exists — reusing."
else
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{
      "Version":"2012-10-17",
      "Statement":[{
        "Effect":"Allow",
        "Principal":{"Service":"ec2.amazonaws.com"},
        "Action":"sts:AssumeRole"
      }]
    }' \
    --description "AWS MCP Server EC2 role" \
    --output json > /dev/null
fi

info "Attaching service-scoped IAM policies..."
POLICIES=(
  "arn:aws:iam::aws:policy/AmazonS3FullAccess"
  "arn:aws:iam::aws:policy/AmazonEC2FullAccess"
  "arn:aws:iam::aws:policy/AWSLambda_FullAccess"
  "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
  "arn:aws:iam::aws:policy/CloudWatchFullAccess"
  "arn:aws:iam::aws:policy/IAMReadOnlyAccess"
  "arn:aws:iam::aws:policy/AmazonSNSFullAccess"
  "arn:aws:iam::aws:policy/AmazonSQSFullAccess"
  "arn:aws:iam::aws:policy/AmazonECS_FullAccess"
  "arn:aws:iam::aws:policy/AWSCloudFormationFullAccess"
  "arn:aws:iam::aws:policy/SecretsManagerReadWrite"
  "arn:aws:iam::aws:policy/AmazonSSMFullAccess"
  "arn:aws:iam::aws:policy/AWSBillingReadOnlyAccess"
  "arn:aws:iam::aws:policy/AmazonRDSFullAccess"
  "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
)
for arn in "${POLICIES[@]}"; do
  aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "$arn" 2>/dev/null || true
  echo "  + ${arn##*/}"
done

info "Creating instance profile: $PROFILE_NAME ..."
if aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" 2>/dev/null; then
  warn "Instance profile already exists — reusing."
else
  aws iam create-instance-profile \
    --instance-profile-name "$PROFILE_NAME" \
    --output json > /dev/null
  aws iam add-role-to-instance-profile \
    --instance-profile-name "$PROFILE_NAME" \
    --role-name "$ROLE_NAME"
fi

info "Waiting 15s for IAM to propagate..."
sleep 15

# ── Step 3: Security group ────────────────────────────────────────────────────
info "Creating security group: $SG_NAME ..."
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" --output text --region "$REGION")

SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query "SecurityGroups[0].GroupId" --output text --region "$REGION" 2>/dev/null || echo "")

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  SG_ID=$(aws ec2 create-security-group \
    --group-name "$SG_NAME" \
    --description "AWS MCP Server — SSE transport port $PORT" \
    --vpc-id "$VPC_ID" \
    --region "$REGION" \
    --query "GroupId" --output text)
  info "Created security group: $SG_ID"

  # Allow MCP SSE port from anywhere (restrict in production)
  aws ec2 authorize-security-group-ingress \
    --group-id "$SG_ID" \
    --protocol tcp --port "$PORT" --cidr "0.0.0.0/0" \
    --region "$REGION"

  # Allow SSM (no SSH key needed) — no inbound rule required; SSM uses outbound only
else
  warn "Security group $SG_NAME ($SG_ID) already exists — reusing."
fi

# ── Step 4: User-data bootstrap script ───────────────────────────────────────
USER_DATA=$(cat <<USERDATA_EOF
#!/bin/bash
set -e
exec > >(tee /var/log/aws-mcp-setup.log) 2>&1

echo "=== AWS MCP Server Bootstrap ==="

# System packages
dnf install -y python3.11 python3.11-pip unzip

# uv (provides uvx for child MCP servers)
curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh
uvx --version

# Download source from S3
aws s3 cp s3://${BUCKET}/source.zip /tmp/aws-mcp-source.zip --region ${REGION}
mkdir -p /opt/aws-mcp
unzip -o /tmp/aws-mcp-source.zip -d /opt/aws-mcp/app
rm /tmp/aws-mcp-source.zip

# Install Python dependencies
cd /opt/aws-mcp/app
python3.11 -m pip install --upgrade pip --quiet
python3.11 -m pip install -r requirements.txt --quiet

# Systemd service
cat > /etc/systemd/system/aws-mcp.service << 'SVCEOF'
[Unit]
Description=AWS MCP Server (SSE)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/aws-mcp/app
Environment=MCP_TRANSPORT=sse
Environment=PORT=${PORT}
Environment=AWS_DEFAULT_REGION=${REGION}
ExecStart=/usr/bin/python3.11 main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable aws-mcp
systemctl start aws-mcp

PUBLIC_IP=\$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "=== Bootstrap complete ==="
echo "SSE endpoint: http://\${PUBLIC_IP}:${PORT}/sse"
USERDATA_EOF
)

# ── Step 5: Launch EC2 instance ───────────────────────────────────────────────
info "Looking up latest Amazon Linux 2023 AMI..."
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" "Name=state,Values=available" \
  --query "sort_by(Images, &CreationDate)[-1].ImageId" \
  --output text --region "$REGION")
info "AMI: $AMI_ID"

SUBNET_ID=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=default-for-az,Values=true" \
  --query "Subnets[0].SubnetId" --output text --region "$REGION")

info "Launching EC2 instance ($INSTANCE_TYPE)..."
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --iam-instance-profile Name="$PROFILE_NAME" \
  --security-group-ids "$SG_ID" \
  --subnet-id "$SUBNET_ID" \
  --associate-public-ip-address \
  --user-data "$USER_DATA" \
  --metadata-options "HttpTokens=required,HttpEndpoint=enabled" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME},{Key=Project,Value=aws-mcp-server}]" \
  --region "$REGION" \
  --query "Instances[0].InstanceId" --output text)

info "Launched instance: $INSTANCE_ID"

# ── Step 6: Wait for running state ───────────────────────────────────────────
info "Waiting for instance to reach 'running' state..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"

PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text --region "$REGION")

echo ""
echo "============================================================"
echo -e "${GREEN}  Deployment complete!${NC}"
echo "  Instance ID : $INSTANCE_ID"
echo "  Public IP   : $PUBLIC_IP"
echo "  SSE endpoint: http://$PUBLIC_IP:$PORT/sse"
echo ""
echo "  Bootstrap logs (ready in ~3 min):"
echo "    aws ssm start-session --target $INSTANCE_ID --region $REGION"
echo "    sudo journalctl -u aws-mcp -f"
echo ""
echo "  Claude Desktop config entry:"
echo '    "aws-mcp": {'
echo '      "type": "sse",'
echo "      \"url\": \"http://$PUBLIC_IP:$PORT/sse\""
echo '    }'
echo "============================================================"
