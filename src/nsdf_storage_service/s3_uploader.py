import logging
from os import path
from pathlib import Path
import boto3

logger = logging.getLogger(__name__)


DEFAULT_DATA_DIR = "/app/data"
DEFAULT_DATA_FILE = "data.json"
DEFAULT_BUCKET = "scientistcloud"
DEFAULT_PREFIX = "test-uploader"


class S3Uploader:
    def __init__(self) -> None:
        # S3 config
        self._client: boto3.client | None = None
        self._bucket: str = ""
        self._prefix: str = ""
        # Local data config
        self._data_dir: Path = Path("/app/data/")

    def init_s3(self, config: dict) -> None:
        """Configure boto3 client, bucket, and local output dir from config."""
        if not config.get("aws_access_key_id") or not config.get("aws_secret_access_key"):
            logger.warning("S3 credentials not configured; skipping S3 uploads")
            self._client = None
            return

        self._client = boto3.client(
            "s3",
            aws_access_key_id=config["aws_access_key_id"],
            aws_secret_access_key=config["aws_secret_access_key"],
            endpoint_url=config.get("endpoint_url"),
        )
        self._bucket = config.get("bucket", DEFAULT_BUCKET)
        self._prefix = config.get("prefix", DEFAULT_PREFIX)
        self._data_dir = Path(config.get("data_dir", DEFAULT_DATA_DIR))
        self._data_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "S3 uploader initialized, using data directory= %s",
            self._data_dir,
        )

    def object_key(self, file: str) -> str:
        """Return full object key"""
        return path.join(self._prefix, file)

    def upload_file(self, file: str) -> None:
        """Upload a local file to the configured S3 bucket"""
        if self._client is None:
            logger.debug("S3 client not configured; skipping upload of %s", file)
            return

        local_path = self._data_dir / file
        if not local_path.exists():
            logger.warning("File not found for S3 upload: %s", local_path)
            return

        object_key = self.object_key(file)
        try:
            self._client.upload_file(str(local_path), self._bucket, object_key)
            logger.info("Uploaded %s to s3://%s/%s", local_path, self._bucket, object_key)
        except Exception:
            logger.exception("Failed to upload %s to S3", object_key)


_uploader = S3Uploader()


def init_s3(config: dict) -> None:
    """Initialize uploader config"""
    _uploader.init_s3(config)


def uploader_data_dir() -> Path:
    """Return the directory configured to upload file"""
    return _uploader._data_dir


def upload_file(object_key: str) -> None:
    """Upload file to s3"""
    _uploader.upload_file(object_key)
