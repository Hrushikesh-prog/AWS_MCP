from __future__ import annotations

from server import mcp


@mcp.prompt()
def aws_infrastructure_overview(region: str = "us-east-1") -> str:
    """
    Generate a comprehensive AWS infrastructure overview for a given region.
    Discovers and summarises EC2, RDS, Lambda, S3, SNS, SQS, and CloudWatch.
    """
    return f"""You are an AWS cloud architect. Perform a comprehensive, read-only
infrastructure overview for region **{region}** using the available MCP tools.

Follow these steps in order:
1. Call `aws_get_caller_identity` to confirm which account you are auditing.
2. Call `aws_list_ec2_instances` (region="{region}", state="all").
3. Call `aws_list_lambda_functions` (region="{region}").
4. Call `aws_describe_rds_instances` (region="{region}").
5. Call `aws_list_s3_buckets` (buckets are global, not regional).
6. Call `aws_list_sns_topics` (region="{region}").
7. Call `aws_list_sqs_queues` (region="{region}").

After gathering all data, produce a structured report with these sections:
- **Account summary** (account ID, active region)
- **Compute** (EC2 instances by state, Lambda function runtimes)
- **Data stores** (RDS engines and sizes, S3 bucket count)
- **Messaging** (SNS topic count, SQS queue count)
- **Observations** (anything unusual: stopped instances, large buckets, etc.)
- **Recommended next steps** (areas to investigate further)

Be concise; use tables where appropriate."""
