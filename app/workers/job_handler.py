import uuid
import logging
import httpx
import asyncio
import os
from fastapi import BackgroundTasks
from app.services.billingservice import run_scraper
from app.models.billingmodels import Credentials
from app.utils.redis_helper import set_job_status, get_job_status
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Set up logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Retrieve the webhook URL from the environment
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise EnvironmentError("WEBHOOK_URL environment variable is not set.")

async def run_scraper_job(credentials: Credentials, background_tasks: BackgroundTasks):
    """Handler for initiating the scraper job."""
    job_id = str(uuid.uuid4())  # Unique job ID

    try:
        await set_job_status(job_id, "pending")  # Set initial job status to pending
        logger.info(f"Job {job_id} started with status 'pending'.")
    except Exception as e:
        logger.critical(f"Failed to set initial status for job {job_id}: {e}")
        raise RuntimeError(f"Job {job_id} initialization failed.")

    # Add the scraper task to the background queue
    background_tasks.add_task(_run_scraper_task, credentials, job_id, WEBHOOK_URL)
    
    return job_id

async def _run_scraper_task(credentials: Credentials, job_id: str, webhook_url: str):
    """Task that runs the scraper and updates the job status."""
    try:
        await set_job_status(job_id, "processing")  # Update job status to 'processing'
        logger.info(f"Job {job_id} is now processing.")
        
        # Run the scraper and check for valid response
        download_dir = await run_scraper(credentials.username, credentials.password)
        if not download_dir:
            raise ValueError("No download directory returned; scraper likely failed.")

        # Job completed successfully
        await set_job_status(job_id, "completed")
        logger.info(f"Job {job_id} completed successfully. Files saved to {download_dir}.")
        
        # Notify via webhook on success
        await send_webhook_notification(webhook_url, job_id, "completed", download_dir)

    except ValueError as e:
        await handle_job_failure(job_id, f"Scraper error: {e}", webhook_url)
        
    except ConnectionError as e:
        await handle_job_failure(job_id, f"Connection error during scraper run: {e}", webhook_url)
        
    except Exception as e:
        await handle_job_failure(job_id, f"Unexpected error: {e}", webhook_url)

async def handle_job_failure(job_id: str, error_message: str, webhook_url: str):
    """
    Gracefully handle job failure by setting the job status to 'failed', logging the error, and sending a webhook notification.
    """
    try:
        await set_job_status(job_id, "failed")
        logger.error(f"Job {job_id} failed. Error: {error_message}")
        
        # Notify via webhook on failure
        await send_webhook_notification(webhook_url, job_id, "failed", error_message)

    except Exception as e:
        logger.critical(f"Failed to update status to 'failed' for job {job_id}. Original error: {error_message}. Status update error: {e}")

async def send_webhook_notification(webhook_url: str, job_id: str, status: str, message: str, max_retries: int = 3):
    """
    Sends a webhook notification to inform the user of the job's completion or failure, with retry logic.
    
    Args:
        webhook_url (str): The URL to send the webhook notification.
        job_id (str): The ID of the job.
        status (str): The job's final status, e.g., 'completed' or 'failed'.
        message (str): Additional information (download directory or error message).
        max_retries (int): The maximum number of retry attempts for the webhook notification.
    """
    payload = {
        "job_id": job_id,
        "status": status,
        "message": message,
    }
    
    # Retry logic
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(webhook_url, json=payload)
                
                if response.status_code == 200:
                    logger.info(f"Webhook notification for job {job_id} sent successfully.")
                    return  # Exit on success
                else:
                    logger.error(f"Failed to send webhook for job {job_id}. Response status: {response.status_code}. Attempt {attempt} of {max_retries}")
        
        except httpx.RequestError as e:
            logger.error(f"Request error on webhook for job {job_id}: {e}. Attempt {attempt} of {max_retries}")
        except Exception as e:
            logger.critical(f"Unexpected error sending webhook for job {job_id}: {e}. Attempt {attempt} of {max_retries}")

        # Wait before retrying
        await asyncio.sleep(2 ** attempt)

    # Log final failure after all retries
    logger.critical(f"Webhook notification failed for job {job_id} after {max_retries} attempts.")
