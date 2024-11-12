from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from app.models.billingmodels import Credentials
from app.workers.job_handler import run_scraper_job
from app.services.storageservice import StorageService
from app.utils.redis_helper import set_job_status, get_job_status
import logging
from app.middleware.rate_limiter import limiter  # Import the limiter

# Initialize router and set up logging
router = APIRouter()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@router.post("/billing/retrieve", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")  # Limit to 5 requests per minute
async def retrieve_billing_data(credentials: Credentials, background_tasks: BackgroundTasks):
    """
    Starts the billing data retrieval job, uploads downloaded data to AWS S3, and returns the job status.

    Args:
        credentials: The billing credentials needed to authenticate and start the scraper.

    Returns:
        A JSON response containing the job ID, initial status ("downloading"), and uploaded files.
    """
    try:
        logger.info("Starting billing data retrieval job.")
        
        # Start the download process
        job_id = await run_scraper_job(credentials, background_tasks)
        if not job_id:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Data download failed")

        # Set job status to 'downloading' initially in Redis
        await set_job_status(job_id, "downloading")
        logger.info(f"Job {job_id} started with status 'downloading'.")

        # Initialize the StorageService to handle AWS S3 upload
        storage_service = StorageService()

        # Update job status to 'uploading' before the upload process begins
        await set_job_status(job_id, "uploading")
        logger.info(f"Job {job_id} status updated to 'uploading'.")

        # Upload all files in the download directory to AWS S3
        uploaded_files = await storage_service.upload_files(job_id)
        if not uploaded_files:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AWS upload failed")

        # Mark job status as 'completed' after successful upload
        await set_job_status(job_id, "completed")
        logger.info(f"Job {job_id} completed with {len(uploaded_files)} files uploaded to S3.")

        return {"job_id": job_id, "status": "completed", "uploaded_files": uploaded_files}
    
    except Exception as e:
        logger.error(f"Error during retrieval and upload: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to complete the job")

@router.get("/billing/status/{job_id}")
@limiter.limit("10/minute")  
async def check_job_status(job_id: str):
    """
    Checks the status of a specific job using its job ID, providing both download and upload status updates.

    Args:
        job_id: The unique identifier of the job to check.

    Returns:
        A JSON response containing the job ID and its current status (e.g., downloading, uploading, completed).
    
    Raises:
        HTTPException: If the job ID does not exist.
    """
    try:
        # Retrieve the current status from Redis asynchronously
        current_status = await get_job_status(job_id)
        if current_status is None:
            logger.warning(f"Job ID {job_id} not found.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job ID not found.")
        
        logger.info(f"Job ID {job_id} status: {current_status}")
        return {"job_id": job_id, "status": current_status}
    except Exception as e:
        logger.error(f"Error checking job status for {job_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve job status")

@router.get("/health/status", status_code=status.HTTP_200_OK)
@limiter.limit("50/minute") 
async def detailed_health_check():
    """
    Provides the health status of the application and job count.

    Returns:
        A JSON response with the health status, version, and job count (stubbed for now).
    """
    try:
        # Placeholder for future Redis job count retrieval
        job_count = "Job count will be implemented using Redis soon"
        
        logger.info("Health check passed.")
        return {
            "status": "OK",
            "version": "1.0.0",
            "job_count": job_count,
        }
    except Exception as e:
        logger.error(f"Error during health check: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Health check failed")
