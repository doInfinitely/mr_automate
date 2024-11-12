from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from fastapi import Request, FastAPI
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

def init_app(app: FastAPI):
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_error(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
        )
