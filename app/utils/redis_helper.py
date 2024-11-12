import aioredis
import json
import time
import logging
from typing import Optional
from app.utils.config import REDIS_HOST, REDIS_PORT, REDIS_DB  # Import from config.py

# Retry settings
MAX_RETRIES = 5
INITIAL_BACKOFF = 1  # seconds

# Redis client (using aioredis for async operations)
redis_pool: Optional[aioredis.Redis] = None

async def get_redis_client() -> aioredis.Redis:
    """Returns a Redis client (with retry mechanism for connection failures)."""
    global redis_pool
    
    if redis_pool is None:
        retries = 0
        while retries < MAX_RETRIES:
            try:
                redis_pool = await aioredis.create_redis_pool(
                    (REDIS_HOST, REDIS_PORT), db=REDIS_DB
                )
                logging.info("Connected to Redis.")
                return redis_pool
            except (aioredis.RedisError, ConnectionError) as e:
                retries += 1
                wait_time = INITIAL_BACKOFF * (2 ** retries)  # Exponential backoff
                logging.warning(f"Redis connection failed (attempt {retries}/{MAX_RETRIES}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                
        logging.error(f"Could not connect to Redis after {MAX_RETRIES} attempts.")
        raise ConnectionError("Unable to connect to Redis.")

    return redis_pool

async def set_job_status(job_id: str, status: str):
    """Sets the job status in Redis asynchronously with retry logic."""
    try:
        redis = await get_redis_client()
        await redis.set(job_id, status)
        logging.info(f"Job status for {job_id} set to {status}.")
    except Exception as e:
        logging.error(f"Error setting job status for {job_id}: {e}")

async def get_job_status(job_id: str) -> Optional[str]:
    """Gets the job status from Redis asynchronously with retry logic."""
    try:
        redis = await get_redis_client()
        status = await redis.get(job_id)
        if status:
            return status.decode("utf-8")
        return None
    except Exception as e:
        logging.error(f"Error getting job status for {job_id}: {e}")
        return None

async def delete_job_status(job_id: str):
    """Deletes the job status from Redis asynchronously with retry logic."""
    try:
        redis = await get_redis_client()
        await redis.delete(job_id)
        logging.info(f"Job status for {job_id} deleted.")
    except Exception as e:
        logging.error(f"Error deleting job status for {job_id}: {e}")

async def close_redis_pool():
    """Closes the Redis connection pool gracefully."""
    global redis_pool
    if redis_pool:
        redis_pool.close()
        await redis_pool.wait_closed()
        logging.info("Redis connection pool closed.")
