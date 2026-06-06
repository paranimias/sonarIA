import os

# Set AWS env vars at module level so boto3 clients created during pytest
# collection (module-level imports in handler files) don't raise NoRegionError.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
