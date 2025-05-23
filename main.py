import os # Added for environment variable access
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi import Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from celery.result import AsyncResult
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from celery_app import process_task

app = FastAPI()

# JWT Authentication Configuration
# For production, generate a strong secret key (e.g., using `openssl rand -hex 32`) and set it as an environment variable.
SECRET_KEY = os.getenv("APP_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], default="bcrypt", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Authentication Helper Functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# TODO: Replace this with actual database logic
def get_user_from_db(username: str):
    print(f"Attempting to get user {username} from DB - NOT IMPLEMENTED")
    # In a real application, this function would query a database.
    # For now, it will prevent crashes but won't actually authenticate.
    # Example structure if user 'user1' existed:
    # if username == "user1":
    #     return {"username": "user1", "hashed_password": pwd_context.hash("password1")}
    return None

def authenticate_user(username: str, password: str):
    user = get_user_from_db(username) # TODO: Implement database interaction
    if not user or not verify_password(password, user["hashed_password"]):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_from_db(username) # TODO: Implement database interaction
    if user is None:
        raise credentials_exception
    return user

# Rate Limiting Configuration
# NOTE: If deploying behind a reverse proxy, ensure `key_func` correctly identifies the client's IP.
# You might need to use a custom function that checks `X-Forwarded-For` or similar headers.
# Example: key_func = lambda: request.headers.get("X-Forwarded-For", get_remote_address())
# Ensure to trust the proxy that sets this header.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Pydantic Model for Task Input
class TaskData(BaseModel):
    data: str

# Authentication Endpoint
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Task Submission Endpoint (Rate-Limited and Authenticated)
@app.post("/tasks/process", dependencies=[Depends(get_current_user)])
@limiter.limit("5/minute")
async def create_process_task(request: Request, task: TaskData):
    # IMPORTANT: If 'task.data' were to be used in database queries, file system operations, or command execution,
    # it would require thorough validation and sanitization to prevent security vulnerabilities like injection attacks.
    result = process_task.delay(task.data)
    return {"task_id": result.id}

# Task Status Endpoint (Authenticated)
@app.get("/tasks/{task_id}", dependencies=[Depends(get_current_user)])
async def get_task_status(task_id: str):
    task_result = AsyncResult(task_id)
    if task_result.ready():
        return {"status": "completed", "result": task_result.get()}
    else:
        return {"status": "pending"}