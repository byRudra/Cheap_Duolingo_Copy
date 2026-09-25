import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.errors import AppError
from app.routers import course, lessons, me, social


logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    if settings.AUTO_SEED:
        from app.seed import is_seeded, seed

        with SessionLocal() as db:
            if not is_seeded(db):
                logger.info("Empty database: seeding demo data")
                seed(db)
    yield


app = FastAPI(title=f"{settings.APP_NAME} API", version="1.1.0", lifespan=lifespan)


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"detail": {"code": code, "message": message}}
    )


@app.middleware("http")
async def unhandled_error_middleware(request: Request, call_next):
    """Turn unexpected exceptions into the standard error body.

    Registered before CORSMiddleware so CORS stays outermost and even 500s
    carry Access-Control-Allow-Origin (Starlette's own 500 handler sits
    outside CORS, so the browser would otherwise see an opaque network error).
    """
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error(500, "INTERNAL_ERROR", "Something went wrong. Please try again.")


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return _error(exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", []) if part != "body")
    message = first.get("msg", "Invalid request.")
    return _error(422, "VALIDATION_ERROR", f"{location}: {message}" if location else message)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "NOT_FOUND" if exc.status_code == 404 else f"HTTP_{exc.status_code}"
    return _error(exc.status_code, code, str(exc.detail))


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(course.router)
app.include_router(lessons.router)
app.include_router(me.router)
app.include_router(social.router)
