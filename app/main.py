from fastapi import FastAPI
from app.api.routes import router  # Importing API router
from app.middleware.rate_limiter import init_app

# Initialize the FastAPI application
app = FastAPI()

init_app(app)
# Include the router from api/routes.py
app.include_router(router)

# Basic health check endpoint 
@app.get("/health")
async def health_check():
    return {"status": "OK"}
