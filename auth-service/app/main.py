"""FastAPI endpoints (API layer - thin, delegates to services)"""
import sys
sys.path.insert(0, '/shared')

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging_client
import init_dynamodb

from pydantic import BaseModel
import jwt

from app.models.requests import LoginRequest, RegisterRequest, LinkAuthMethodRequest
from app.models.responses import LoginResponse, UserResponse, RefreshResponse
from app.utils.jwt import verify_refresh_token, create_access_token
from app.services.authentication_service import AuthenticationService
from app.providers.password_provider import PasswordAuthProvider
from app.repositories.user_repository import DynamoDBUserRepository
from app.repositories.auth_method_repository import DynamoDBAuthMethodRepository

# Initialize logger
logger = logging_client.setup_logger('auth-service')

app = FastAPI(title="Trollama Auth Service", version="2.0.0")


@app.on_event("startup")
async def startup_event():
    """Initialize DynamoDB tables on startup."""
    logger.info("Initializing DynamoDB tables...")
    try:
        tables_created = await init_dynamodb.initialize_all_tables()
        if tables_created:
            logger.info(f"Created tables: {', '.join(tables_created)}")
        else:
            logger.info("All tables already exist")
    except Exception as e:
        logger.error(f"Failed to initialize DynamoDB tables: {e}")
        raise

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency Injection (DIP - inject dependencies)
user_repo = DynamoDBUserRepository()
auth_method_repo = DynamoDBAuthMethodRepository()

# Register auth providers (OCP - easy to add new providers)
auth_providers = {
    'password': PasswordAuthProvider(auth_method_repo)
}

auth_service = AuthenticationService(auth_providers, user_repo, auth_method_repo)


@app.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login with any auth provider"""
    logger.info(f"Login attempt: {request.identifier} via {request.provider}")

    try:
        result = await auth_service.login(
            provider=request.provider,
            identifier=request.identifier,
            credentials=request.credentials
        )

        if not result:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        return LoginResponse(
            access_token=result['access_token'],
            refresh_token=result['refresh_token'],
            token_type=result['token_type'],
            user=UserResponse.from_domain(result['user'])
        )
    except HTTPException:
        # Re-raise HTTPException to preserve status code
        raise
    except ValueError as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/register", response_model=LoginResponse)
async def register(request: RegisterRequest):
    """Register new user"""
    logger.info(f"Registration: {request.identifier} via {request.provider}")

    try:
        result = await auth_service.register(
            provider=request.provider,
            identifier=request.identifier,
            credentials=request.credentials,
            display_name=request.display_name,
            email=request.email
        )

        return LoginResponse(
            access_token=result['access_token'],
            refresh_token=result['refresh_token'],
            token_type=result['token_type'],
            user=UserResponse.from_domain(result['user'])
        )
    except HTTPException:
        # Re-raise HTTPException to preserve status code
        raise
    except ValueError as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected registration error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


class RefreshRequest(BaseModel):
    refresh_token: str


@app.post("/refresh", response_model=RefreshResponse)
async def refresh_token(request: RefreshRequest):
    """Refresh access token using refresh token."""
    logger.debug("Token refresh attempt")

    try:
        # Verify refresh token
        payload = verify_refresh_token(request.refresh_token)

        # Create new access token with same user data
        new_access_token = create_access_token({
            "user_id": payload["user_id"],
            "display_name": payload["display_name"],
            "role": payload["role"]
        })

        logger.info(f"Token refreshed for user {payload['user_id']}")

        return RefreshResponse(
            access_token=new_access_token,
            token_type="bearer"
        )

    except jwt.ExpiredSignatureError:
        logger.warning("Refresh token expired")
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid refresh token: {e}")
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except Exception as e:
        logger.error(f"Unexpected refresh error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/link-auth-method")
async def link_auth_method(request: LinkAuthMethodRequest):
    """Link new auth method to existing user (account linking)"""
    logger.info(f"Linking {request.provider} to user {request.user_id}")

    try:
        auth_method = await auth_service.link_auth_method(
            user_id=request.user_id,
            provider=request.provider,
            identifier=request.identifier,
            credentials=request.credentials
        )

        return {
            "status": "success",
            "auth_method_id": auth_method.auth_method_id,
            "provider": auth_method.provider
        }
    except HTTPException:
        # Re-raise HTTPException to preserve status code
        raise
    except ValueError as e:
        logger.error(f"Link auth method error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected link auth method error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "auth-service",
        "version": "2.0.0"
    }
