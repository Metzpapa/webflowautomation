import boto3
import uuid
import os

s3 = boto3.client(
    "s3", 
    region_name=os.getenv("S3_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)
BUCKET = os.environ["S3_BUCKET"]

def upload_png(png_bytes: bytes) -> str:
    key = f"blog/{uuid.uuid4()}.png"
    s3.put_object(
        Bucket=BUCKET, 
        Key=key, 
        Body=png_bytes,
        ContentType="image/png", 
        ACL="public-read"
    )
    return f"https://{BUCKET}.s3.amazonaws.com/{key}"