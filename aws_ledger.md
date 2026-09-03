# AWS Instance Ledger
**Account:** `346553908034` | **User:** `arn:aws:iam::346553908034:user/mcp_server_aws_iam` | **Region:** `us-east-1`

---

## Instance Registry

| # | Name | Instance ID | Type | State | Public IP | Private IP | AZ | Key Pair | Launched |
|---|------|-------------|------|-------|-----------|------------|----|----------|----------|
| 1 | TestServer_for_autoscaling | `i-0a8773530133dfa22` | t3.micro | 🔴 stopped | — | 172.31.24.73 | us-east-1c | autoscale_instanceKey | 2026-06-29 |
| 2 | server_to_confirm MCP | `i-05d01fb20baae52d8` | t3.micro | 🔴 stopped | — | 172.31.4.61 | us-east-1a | autoscale_instanceKey | 2026-08-24 |
| 3 | test instance | `i-048700dd60dcd81b8` | t3.micro | 🔴 stopped | — | 172.31.26.53 | us-east-1c | _(none)_ | 2026-08-30 |

---

## Change Log

| Timestamp (UTC) | Instance ID | Name | Event | Details |
|-----------------|-------------|------|-------|---------|
| 2026-08-30 18:18:38 | `i-048700dd60dcd81b8` | test instance | **LAUNCHED** | t3.micro, ami-0c02fb55956c7d316, no key pair |
| 2026-08-30 18:xx:xx | `i-048700dd60dcd81b8` | test instance | **STARTED** | State: running, Public IP: 54.82.126.26 |
| 2026-08-31 xx:xx:xx | `i-048700dd60dcd81b8` | test instance | **STOPPED** | State: stopped, Public IP released |

---

## Instance Details

### 1. TestServer_for_autoscaling
- **Instance ID:** `i-0a8773530133dfa22`
- **Type:** t3.micro
- **State:** stopped
- **AMI:** ami-08f44e8eca9095668
- **Private IP:** 172.31.24.73
- **VPC:** vpc-0e4c8e1d624f4e89a
- **Subnet:** subnet-010696f992bf0a999
- **Security Group:** sg-03006af7079f7f282 (default)
- **Key Pair:** autoscale_instanceKey
- **Launched:** 2026-06-29 09:10:19 UTC

---

### 2. server_to_confirm MCP
- **Instance ID:** `i-05d01fb20baae52d8`
- **Type:** t3.micro
- **State:** stopped
- **AMI:** ami-0332d564d76dbd8d6
- **Private IP:** 172.31.4.61
- **VPC:** vpc-0e4c8e1d624f4e89a
- **Subnet:** subnet-0ce11ac320f9de5ac
- **Security Group:** sg-04d760aac68080dc9 (launch-wizard-1)
- **Key Pair:** autoscale_instanceKey
- **Launched:** 2026-08-24 07:44:50 UTC

---

### 3. test instance
- **Instance ID:** `i-048700dd60dcd81b8`
- **Type:** t3.micro
- **State:** stopped
- **AMI:** ami-0c02fb55956c7d316
- **Private IP:** 172.31.26.53
- **VPC:** vpc-0e4c8e1d624f4e89a
- **Subnet:** subnet-010696f992bf0a999
- **Security Group:** sg-03006af7079f7f282 (default)
- **Key Pair:** _(none — use EC2 Instance Connect)_
- **Launched:** 2026-08-30 18:18:38 UTC
- **Notes:** SSH port 22 open to 0.0.0.0/0

---

## Cost Summary (Monthly Estimate)

| Instance | State | Compute Cost | EBS Cost | Total |
|----------|-------|--------------|----------|-------|
| TestServer_for_autoscaling | stopped | $0.00 | ~$0.80 | ~$0.80 |
| server_to_confirm MCP | stopped | $0.00 | ~$0.80 | ~$0.80 |
| test instance | stopped | $0.00 | ~$0.80 | ~$0.80 |
| **Total** | | **$0.00** | **~$2.40** | **~$2.40/mo** |

> Stopped instances are not charged for compute. EBS volumes (~8 GB gp2 @ $0.10/GB-mo) are still billed.
> If all 3 instances were running as t3.micro: ~$24.87/mo

---

_Last updated: 2026-08-31 | Refresh by asking Claude to update the ledger_
