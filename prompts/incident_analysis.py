from __future__ import annotations

from server import mcp


@mcp.prompt()
def aws_incident_analysis(log_group: str, region: str = "us-east-1") -> str:
    """
    Structured incident analysis using CloudWatch Logs for a specific log group.

    Args:
        log_group: Full CloudWatch log group name to analyse.
        region:    AWS region where the log group resides (default 'us-east-1').
    """
    return f"""You are an on-call SRE investigating an active or recent incident.
Analyse CloudWatch log group **{log_group}** in region **{region}**.

Investigation playbook:
1. `aws_get_cloudwatch_logs` (log_group_name="{log_group}", region="{region}",
   filter_pattern="ERROR", limit=50)
2. `aws_get_cloudwatch_logs` (same group, filter_pattern="WARN", limit=25)
3. `aws_get_cloudwatch_logs` (same group, filter_pattern="Exception", limit=25)
4. `aws_get_cloudwatch_logs` (same group, no filter, limit=50) — capture the
   most recent raw events for timeline reconstruction.

Produce an incident report:
- **Timeline** (ordered sequence of significant events with ISO timestamps)
- **Error summary** (distinct error types, frequency counts)
- **Impact assessment** (what services / users were likely affected)
- **Root cause** (most probable cause based on log evidence)
- **Immediate actions taken** (if any are already visible in logs)
- **Follow-up action items** (what needs to happen to close the incident)
- **Monitoring gaps** (errors that should have triggered alerts but apparently
  did not)"""
