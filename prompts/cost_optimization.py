from __future__ import annotations

from server import mcp


@mcp.prompt()
def aws_cost_optimization(region: str = "us-east-1") -> str:
    """
    Identify cost optimisation opportunities across AWS resources in a region.
    Focuses on idle compute, oversized instances, and forgotten resources.
    """
    return f"""You are an AWS cost optimisation specialist. Analyse resources in
region **{region}** and identify waste and savings opportunities.

Data gathering:
1. `aws_list_ec2_instances` (region="{region}", state="all") — look for stopped
   instances that may have attached EBS volumes still incurring cost.
2. `aws_list_ec2_instances` (region="{region}", state="running") — note instance
   types; flag anything larger than xlarge for review.
3. `aws_list_lambda_functions` (region="{region}") — note functions with memory
   > 512 MB or timeout > 60s (candidates for right-sizing).
4. `aws_describe_rds_instances` (region="{region}") — flag non-Multi-AZ instances
   in production-looking names, and any with large allocated storage.
5. `aws_list_s3_buckets` — flag buckets with no objects (call
   `aws_get_s3_objects` with max_keys=1; empty bucket = bucket cost only).

Output a cost optimisation report:
- **Quick wins** (actions achievable in < 1 hour, e.g. terminate stopped EC2)
- **Medium-term** (right-sizing, reserved instance candidates)
- **Long-term** (architectural changes, lifecycle policies)
- **Estimated savings** (rough estimates based on resource counts and types)
- **Priority order** (ranked by impact × effort)"""
