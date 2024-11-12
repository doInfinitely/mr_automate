Based on the files you provided and the existing project details, here’s a draft for the README that accurately reflects the structure, functionality, and setup instructions:

---

# Billing Data Scraper API

This FastAPI application facilitates the automated retrieval and upload of billing data from UPS using web scraping techniques. It handles background tasks, stores job status in Redis, and sends notifications via configurable webhooks when tasks are completed. This project is equipped with AWS S3 integration for file storage and robust error management.

## Features

- **Billing Data Retrieval**: Automates the login and retrieval of billing data from UPS using provided credentials.
- **Asynchronous Job Management**: Background tasks are handled asynchronously, with real-time job status updates via Redis.
- **Webhook Notifications**: Users receive notifications on job completion or failure via configurable webhooks.
- **AWS S3 Integration**: Successfully retrieved files are uploaded to an AWS S3 bucket.
- **Comprehensive Error Handling**: Detailed error handling for Redis, scraping, and webhook operations.
- **Health Monitoring**: API health endpoint provides operational status and version information.

## Project Structure

- **`app/models/billingmodels.py`**: Defines data models for handling billing credentials and job data.
- **`app/workers/job_handler.py`**: Manages background job execution and orchestrates the scraping process.
- **`app/services/storageservice.py`**: Provides an interface for uploading files to AWS S3.
- **`app/utils/redis_helper.py`**: Contains helper functions for managing Redis connections and job status operations.
- **`app/routes.py`**: Defines API endpoints for starting the billing retrieval process, checking job status, and monitoring API health.
- **`app/billing/service.py`**: Implements the main scraping logic using Playwright to interact with the UPS billing portal.

## Requirements

- Python 3.9+
- Redis server
- AWS S3 bucket and credentials
- Playwright for Python (installed and set up via `playwright install` command)

## Environment Variables

Configure these environment variables in a `.env` file to enable Redis and AWS integration, as well as other necessary settings for the scraper.

- `REDIS_URL`: Redis connection string (e.g., `redis://localhost:6379`)
- `AWS_ACCESS_KEY_ID`: AWS access key for S3.
- `AWS_SECRET_ACCESS_KEY`: AWS secret key for S3.
- `AWS_BUCKET_NAME`: Name of the AWS S3 bucket to upload files to.
- `WEBHOOK_URL`: URL for the webhook to notify job completion.
- `MAX_PAGES`: Maximum number of pages to process in the billing portal.
- `API_KEY`: API key for ZenRows, if used for proxying.

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd billing-data-scraper-api
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Playwright installation (for browser automation):**
   ```bash
   playwright install
   ```

4. **Set up environment variables** in a `.env` file.

## Usage

1. **Start Redis server** (if not already running):
   ```bash
   redis-server
   ```

2. **Run the FastAPI application:**
   ```bash
   uvicorn app.main:app --reload
   ```

3. **API Endpoints**:
   - `POST /billing/retrieve`: Initiates the billing data retrieval process with user credentials.
   - `GET /billing/status/{job_id}`: Checks the status of a job by `job_id`.
   - `GET /health/status`: Provides the health status of the application.

## API Endpoints

### Retrieve Billing Data
- **Endpoint**: `POST /billing/retrieve`
- **Description**: Starts a background job to retrieve billing data and upload files to S3.
- **Request Body**:
  ```json
  {
      "username": "user@example.com",
      "password": "yourpassword"
  }
  ```
- **Response**:
  ```json
  {
      "job_id": "unique-job-id",
      "status": "downloading",
      "uploaded_files": ["file1.csv", "file2.csv"]
  }
  ```

### Check Job Status
- **Endpoint**: `GET /billing/status/{job_id}`
- **Description**: Checks the current status of a job using its `job_id`.
- **Response**:
  ```json
  {
      "job_id": "unique-job-id",
      "status": "completed"
  }
  ```

### Health Check
- **Endpoint**: `GET /health/status`
- **Description**: Verifies the health and readiness of the API.
- **Response**:
  ```json
  {
      "status": "OK",
      "version": "1.0.0",
      "job_count": "Job count will be implemented using Redis soon"
  }
  ```

## Logging

Logs are maintained in `script_log.log` for monitoring scraping processes and error occurrences.

## feel free to suggest any adjustments