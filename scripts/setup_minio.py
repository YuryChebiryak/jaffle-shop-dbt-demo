"""Create the lakehouse bucket in MinIO and verify connectivity."""
import boto3
from botocore.client import Config

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

bucket = "lakehouse"
existing = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
if bucket not in existing:
    s3.create_bucket(Bucket=bucket)
    print(f"Created bucket: {bucket}")
else:
    print(f"Bucket already exists: {bucket}")

print("MinIO setup complete.")
