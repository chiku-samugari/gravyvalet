import dataclasses

import boto3
from botocore import exceptions as BotoExceptions
from django.core.exceptions import ValidationError

from addon_toolkit.credentials import (
    AccessKeySecretKeyCredentials,
    Credentials,
)
from addon_toolkit.interfaces import storage


@dataclasses.dataclass
class StorageAddonClientConnectorImp[T](storage.StorageAddonClientRequestorImp):
    """base class for storage addon with fully configurable client
    """

    config: dataclasses.InitVar[storage.StorageConfig]

    # def __post_init__(self, config, credentials):
    # InitVar argument order is not fixed.
    #  https://github.com/python/cpython/issues/91507
    def __post_init__(self, *args):
        credentials, config = None, None
        if isinstance(args[0], storage.StorageConfig):
            credentials, config = args[1], args[0]
        else:
            credentials, config = args[0], args[1]

        self.config = config
        self.client = self.create_client(credentials, config)

    @staticmethod
    def create_client(credentials, config) -> T:
        raise NotImplementedError


class S3CompatStorageImp(StorageAddonClientConnectorImp):
    """Storage addon for S3 Compatible Storages
    """

    @classmethod
    def confirm_credentials(cls, credentials):
        if(len(credentials.access_key) == 0):
            raise ValidationError("Access Key cannot be an empty string.")
        if(len(credentials.secret_key) == 0):
            raise ValidationError("Secret Key cannot be an empty string.")

    def validate_connection(self):
        try:
            self.client.list_buckets()
        except BotoExceptions.ClientError:
            raise ValidationError("Fail to validate the connection")

    @staticmethod
    def validate_connection_resource_approach(credentials: AccessKeySecretKeyCredentials):
        return boto3.resource(
            "s3",
            aws_access_key_id=credentials.access_key,
            aws_secret_access_key=credentials.secret_key,
            # region= ??? it is only for oraclecloud, work on it later
            #endpoint_url=
        )

    @staticmethod
    def create_client(
            credentials: AccessKeySecretKeyCredentials,
            config: storage.StorageConfig
    ):
        kwargs = {
            "aws_access_key_id": credentials.access_key,
            "aws_secret_access_key": credentials.secret_key,
            "endpoint_url": config.external_api_url,
        }
        # TODO: how to do it?
        # if region:
        #     kwargs["region_name"] = region
        return boto3.client("s3", **kwargs)

    async def get_external_account_id(self, auth_result_extras: dict[str, str]) -> str:
        return ""

    async def list_root_items(self, page_cursor: str = "") -> storage.ItemSampleResult:
        results = list(self.list_buckets())
        return storage.ItemSampleResult(
            items=results,
            total_count=len(results),
        )

    async def list_child_items(
        self,
        item_id: str,
        page_cursor: str = "",
        item_type: storage.ItemType | None = None,
    ) -> storage.ItemSampleResult:
        if ":/" not in item_id:
            return storage.ItemSampleResult(items=[], total_count=0)

        bucket, key = item_id.split(":/", 1)

        if not key or key.endswith("/"):
            try:
                response = self.client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=key,
                    Delimiter="/"
                )

                if('Contents' in response):
                    await self.get_item_info(f"{bucket}:/{response['Contents'][1]['Key']}")

                results = []

                if response.get("CommonPrefixes") and (
                    item_type is None or item_type == storage.ItemType.FOLDER
                ):
                    for folder in response["CommonPrefixes"]:
                        folder_prefix = folder["Prefix"]
                        # Extract folder name (remove trailing slash and get last part)
                        folder_name_parts = folder_prefix.rstrip("/").split("/")
                        folder_name = folder_name_parts[-1] + "/"

                        results.append(
                            storage.ItemResult(
                                item_id=f'{bucket}:/{folder_prefix}',
                                item_name=folder_name,
                                item_type=storage.ItemType.FOLDER,
                            )
                        )

                if response.get("Contents") and (
                    item_type is None or item_type == storage.ItemType.FILE
                ):
                    for file_obj in response["Contents"]:
                        file_key = file_obj["Key"]
                        if file_key.endswith("/"):
                            continue

                        file_name_parts = file_key.split("/")
                        file_name = file_name_parts[-1]

                        results.append(
                            storage.ItemResult(
                                item_id=f'{bucket}:/{file_key}',
                                item_name=file_name,
                                item_type=storage.ItemType.FILE,
                            )
                        )

                return storage.ItemSampleResult(
                    items=results,
                    total_count=len(results),
                )

            except Exception as e:
                return storage.ItemSampleResult(items=[], total_count=0)

        # If key doesn't end with "/", this might be a file request
        # Return empty result for now (could implement single file info here)
        return storage.ItemSampleResult(items=[], total_count=0)

    def list_buckets(self):
        for bucket in self.client.list_buckets()["Buckets"]:
            yield storage.ItemResult(
                item_id=bucket["Name"] + ":/",
                item_name=bucket["Name"] + "/",
                item_type=storage.ItemType.FOLDER,
            )

    async def build_wb_config(self) -> dict:
        return {
            "host": self.config.external_api_url,
            "bucket": self.config.connected_root_id.split(":/")[0],
            "id": self.config.connected_root_id,
            "encrypt_uploads": True,
        }

    async def get_item_info(self, item_id: str) -> storage.ItemResult:
        """Get information about a specific item (file or folder) in S3-compatible storage"""

        if not item_id or ":/" not in item_id:
            return None

        bucket, key = item_id.split(":/", 1)

        if key:
            try:
                response = self.client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=key,
                    Delimiter="/"
                )

                if response.get("Contents"):
                    exact_match = None
                    for content in response["Contents"]:
                        if content["Key"] == key and not content["Key"].endswith("/"):
                            exact_match = content
                            break

                    if exact_match:
                        # This is a file
                        file_name = key.split("/")[-1]  # Extract filename
                        return storage.ItemResult(
                            item_id=f"{bucket}:/{exact_match['Key']}",
                            item_name=file_name,
                            item_type=storage.ItemType.FILE,
                        )

                    if not response.get("CommonPrefixes"):
                        # Multiple files with this prefix = folder
                        folder_name_parts = key.rstrip("/").split("/")
                        folder_name = folder_name_parts[-1] + "/"
                        return storage.ItemResult(
                            item_id=item_id,
                            item_name=folder_name,
                            item_type=storage.ItemType.FOLDER,
                        )

                if response.get("CommonPrefixes") or key.endswith("/"):
                    folder_name_parts = key.rstrip("/").split("/")
                    folder_name = folder_name_parts[-1] + "/"
                    return storage.ItemResult(
                        item_id=item_id,
                        item_name=folder_name,
                        item_type=storage.ItemType.FOLDER,
                    )

                return None

            except BotoExceptions.ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ['NoSuchKey', 'NoSuchBucket']:
                    return None
                raise
            except Exception as e:
                return None

        else:
            # This is a bucket reference (key is empty)
            bucket_name = bucket.strip(":/")
            try:
                self.client.head_bucket(Bucket=bucket_name)
                return storage.ItemResult(
                    item_id=item_id,
                    item_name=bucket_name + "/",
                    item_type=storage.ItemType.FOLDER,
                )
            except BotoExceptions.ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                return None
            except Exception as e:
                return None
