from __future__ import annotations

from server import mcp


@mcp.prompt()
def aws_ec2_troubleshoot(instance_id: str, issue: str) -> str:
    """
    Structured troubleshooting guide for a specific EC2 instance issue.

    Args:
        instance_id: The EC2 instance ID to investigate (e.g. i-0abc123def456).
        issue:       A short description of the problem being observed.
    """
    return f"""You are an AWS operations engineer. Troubleshoot the following issue
on EC2 instance **{instance_id}**:

> {issue}

Investigation steps:
1. Call `aws_list_ec2_instances` (state="all") and find `{instance_id}`.
   Note: instance type, current state, public/private IPs, and Name tag.
2. Call `aws_get_cloudwatch_logs` targeting the log group for this instance
   (common patterns: `/aws/ec2/`, `/var/log/messages`, the app's log group).
   Use filter_pattern="ERROR" first, then broaden if no results.
3. If the instance is in a stopped or terminated state, note the last
   launch time and any relevant CloudWatch log entries near that time.

Diagnosis report format:
- **Instance summary** (ID, type, state, IPs)
- **Recent log evidence** (relevant log lines with timestamps)
- **Root cause hypothesis** (most likely explanation given the evidence)
- **Immediate remediation steps** (ordered by priority)
- **Preventive measures** (to avoid recurrence)"""
