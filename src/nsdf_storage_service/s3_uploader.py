import logging
from datetime import datetime, timezone
from os import path
from pathlib import Path
import boto3

from . import refresh_notifier

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
        self._data_dir = Path(config.get("data_dir") or DEFAULT_DATA_DIR)
        self._data_dir.mkdir(parents=True, exist_ok=True)

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

        logger.info(
            "S3 uploader initialized, using data directory= %s",
            self._data_dir,
        )

    def object_key(self, file: str) -> str:
        """Return full object key"""
        return path.join(self._prefix, file)

    def timestamped_file_name(self, file: str, dataset_x_size: int | None = None) -> str:
        """Return the timestamped object name for a stable JSON file."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        file_path = Path(file)
        size_suffix = "" if dataset_x_size is None else f"_{dataset_x_size}"
        return f"{file_path.stem}_{timestamp}{size_suffix}{file_path.suffix}"

    def upload_file(self, file: str, dataset_x_size: int | None = None) -> bool:
        """Upload a local file to the configured S3 bucket"""
        if self._client is None:
            logger.debug("S3 client not configured; skipping upload of %s", file)
            return False

        local_path = self._data_dir / file
        if not local_path.exists():
            logger.warning("File not found for S3 upload: %s", local_path)
            return False

        object_key = self.object_key(file)
        timestamped_file = self.timestamped_file_name(file, dataset_x_size)
        timestamped_object_key = self.object_key(timestamped_file)
        try:
            self._client.upload_file(str(local_path), self._bucket, object_key)
            logger.info("Uploaded %s to s3://%s/%s", local_path, self._bucket, object_key)
            self._client.upload_file(str(local_path), self._bucket, timestamped_object_key)
            logger.info(
                "Uploaded %s to s3://%s/%s",
                local_path,
                self._bucket,
                timestamped_object_key,
            )
            refresh_notifier.notify_refresh()
            return True
        except Exception:
            logger.exception("Failed to upload %s to S3", object_key)
            return False


_uploader = S3Uploader()


def init_s3(config: dict) -> None:
    """Initialize uploader config"""
    _uploader.init_s3(config)


def uploader_data_dir() -> Path:
    """Return the directory configured to upload file"""
    return _uploader._data_dir


def upload_file(object_key: str, dataset_x_size: int | None = None) -> bool:
    """Upload file to s3"""
    return _uploader.upload_file(object_key, dataset_x_size)
