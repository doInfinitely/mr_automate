import os
import asyncio
import aioboto3
import aiofiles
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError, BotoCoreError
import logging
from datetime import datetime
from typing import List

# Initialize logging with additional detail
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AWS S3 configuration
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
MAX_RETRIES = 3
RETRY_DELAY = 2  # Seconds

class StorageService:
    def __init__(self):
        """
        Initialize the S3 client with retries and error handling, ensuring credentials are available.
        """
        if not all([AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_BUCKET_NAME, AWS_REGION]):
            logger.critical("Missing AWS credentials or configuration.")
            raise EnvironmentError("AWS configuration is missing.")

        self.s3_session = aioboto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )
        logger.debug("Initialized aioboto3 session for S3 access.")

    async def upload_file(self, file_path: str, s3_key: str) -> bool:
        """
        Upload a single file to S3 with retry and error handling.
        """
        async with self.s3_session.client('s3') as s3_client:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    logger.info(f"Uploading {file_path} to s3://{AWS_BUCKET_NAME}/{s3_key}, attempt {attempt}.")
                    await s3_client.upload_file(file_path, AWS_BUCKET_NAME, s3_key)
                    logger.info(f"Upload successful for {file_path} as {s3_key}.")
                    return True
                except (ClientError, EndpointConnectionError) as e:
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    logger.error(f"Upload attempt {attempt} failed for {file_path} with error: {error_code} - {e}")
                    if error_code in ('RequestTimeout', 'Throttling'):
                        logger.warning("Transient error detected, retrying after delay.")
                        await asyncio.sleep(RETRY_DELAY * attempt)
                    else:
                        break
                except Exception as e:
                    logger.exception(f"Unexpected error during upload of {file_path}: {e}")
                    break
            logger.error(f"Upload failed for {file_path} after {MAX_RETRIES} attempts.")
            return False

    async def multipart_upload(self, file_path: str, s3_key: str) -> bool:
        """
        Perform a multipart upload for large files with detailed error handling and retries.
        """
        async with self.s3_session.client('s3') as s3_client:
            try:
                file_size = os.path.getsize(file_path)
                part_size = 5 * 1024 * 1024  # 5MB per part
                if file_size <= part_size:
                    return await self.upload_file(file_path, s3_key)

                logger.info(f"Initiating multipart upload for {file_path} to {AWS_BUCKET_NAME}/{s3_key}")
                create_response = await s3_client.create_multipart_upload(Bucket=AWS_BUCKET_NAME, Key=s3_key)
                upload_id = create_response['UploadId']
                parts = []

                async with aiofiles.open(file_path, 'rb') as file:
                    part_number = 1
                    while True:
                        part_data = await file.read(part_size)
                        if not part_data:
                            break

                        # Upload each part with retries
                        for attempt in range(1, MAX_RETRIES + 1):
                            try:
                                logger.debug(f"Uploading part {part_number} of {s3_key}, attempt {attempt}")
                                part_response = await s3_client.upload_part(
                                    Bucket=AWS_BUCKET_NAME,
                                    Key=s3_key,
                                    PartNumber=part_number,
                                    UploadId=upload_id,
                                    Body=part_data
                                )
                                parts.append({'PartNumber': part_number, 'ETag': part_response['ETag']})
                                logger.info(f"Part {part_number} uploaded successfully.")
                                break
                            except (ClientError, EndpointConnectionError) as e:
                                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                                logger.error(f"Error on part {part_number} upload: {error_code} - {e}")
                                if attempt < MAX_RETRIES:
                                    await asyncio.sleep(RETRY_DELAY * attempt)
                                else:
                                    logger.critical(f"Part {part_number} failed after {MAX_RETRIES} attempts.")
                                    await self.abort_multipart_upload(s3_client, upload_id, s3_key)
                                    return False
                        part_number += 1

                # Complete the multipart upload
                logger.info(f"Completing multipart upload for {file_path}")
                await s3_client.complete_multipart_upload(
                    Bucket=AWS_BUCKET_NAME,
                    Key=s3_key,
                    UploadId=upload_id,
                    MultipartUpload={'Parts': parts}
                )
                logger.info(f"Multipart upload completed for {file_path} to {s3_key}")
                return True
            except ClientError as e:
                logger.error(f"Client error during multipart upload of {file_path}: {e}")
                await self.abort_multipart_upload(s3_client, upload_id, s3_key)
            except EndpointConnectionError as e:
                logger.error(f"Network error during multipart upload of {file_path}: {e}")
                await self.abort_multipart_upload(s3_client, upload_id, s3_key)
            except Exception as e:
                logger.exception(f"Unexpected error during multipart upload of {file_path}: {e}")
                await self.abort_multipart_upload(s3_client, upload_id, s3_key)
            return False

    async def abort_multipart_upload(self, s3_client, upload_id: str, s3_key: str):
        """
        Abort a multipart upload if an error occurs.
        """
        try:
            logger.warning(f"Aborting multipart upload for {s3_key} with UploadId {upload_id}.")
            await s3_client.abort_multipart_upload(Bucket=AWS_BUCKET_NAME, Key=s3_key, UploadId=upload_id)
            logger.info(f"Aborted multipart upload for {s3_key}")
        except Exception as e:
            logger.error(f"Failed to abort multipart upload for {s3_key}: {e}")

    async def upload_files(self, directory: str) -> List[str]:
        """
        Upload all files in a directory to S3, logging each successful upload.
        """
        if not os.path.isdir(directory):
            logger.critical(f"Directory does not exist: {directory}")
            return []

        success_files = []
        total_files = len(os.listdir(directory))
        if total_files == 0:
            logger.warning(f"No files found in directory: {directory}")
            return []

        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            s3_key = f"{datetime.now().strftime('%Y/%m/%d')}/{filename}"
            
            if os.path.isfile(file_path):
                logger.info(f"Starting upload for {file_path}.")
                if await self.multipart_upload(file_path, s3_key):
                    success_files.append(file_path)
                else:
                    logger.error(f"Upload failed for {file_path}.")
        return success_files

if __name__ == "__main__":
    storage = StorageService()
    uploaded_files = asyncio.run(storage.upload_files('/path/to/files'))
    if uploaded_files:
        logger.info(f"Successfully uploaded the following files: {', '.join(uploaded_files)}")
    else:
        logger.error("No files were uploaded successfully.")
