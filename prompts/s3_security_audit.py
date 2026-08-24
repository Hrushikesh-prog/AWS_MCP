from __future__ import annotations

from server import mcp


@mcp.prompt()
def aws_s3_security_audit() -> str:
    """
    Audit all S3 buckets for common security misconfigurations.
    Checks bucket inventory and flags exposure risks.
    """
    return """You are an AWS security engineer. Audit all S3 buckets in this account
for common security misconfigurations.

Steps:
1. Call `aws_list_s3_buckets` to get the full bucket inventory.
2. For each bucket, call `aws_get_s3_objects` with max_keys=1 to check
   accessibility (a successful response without explicit credentials can
   indicate a public bucket misconfiguration).

Produce a security report with:
- **Bucket inventory table** (name, creation date)
- **Access findings** (which buckets returned objects without issue)
- **Risk classification** (High / Medium / Low) per bucket based on:
  - Naming patterns that suggest sensitive data (backup, prod, pii, finance)
  - Unexpectedly large object counts
  - Very old creation dates (legacy buckets often lack modern policies)
- **Recommended actions** (enable S3 Block Public Access, enforce encryption,
  enable versioning and access logging)

Note: This is a passive read-only audit. It cannot check bucket policies or ACLs
directly. Flag any buckets that warrant a deeper manual review."""
