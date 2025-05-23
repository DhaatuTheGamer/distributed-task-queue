import os # Added for environment variable access
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from celery.result import AsyncResult
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from celery_app import process_task, add_numbers, simulate_image_processing
import aiosqlite # For async SQLite operations

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database Configuration
DATABASE_URL = "tasks_and_users.db"

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

async def get_user_from_db(username: str): # Make it async
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row # To get dict-like rows
        cursor = await db.execute("SELECT username, hashed_password, disabled FROM users WHERE username = ?", (username,))
        user_row = await cursor.fetchone()
        await cursor.close() # Good practice to close cursor
        if user_row:
            return user_row # Returns a Row object which behaves like a dict
        return None

async def authenticate_user(username: str, password: str): # Removed fake_db, made async
    user = await get_user_from_db(username)
    if not user:
        return False
    if not verify_password(password, user["hashed_password"]): # Access hashed_password via key
        return False
    # Optionally, you could check user["disabled"] here if needed, e.g.:
    # if user["disabled"]:
    #     return False
    return user # Return the user object (Row)

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
    user = await get_user_from_db(username) # Await the async call
    if user is None:
        raise credentials_exception
    # If you need to check if the user is disabled *after* token validation:
    # if user["disabled"]: # Accessing Row object like a dict
    #     raise HTTPException(status_code=400, detail="Inactive user")
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

class NumbersTaskData(BaseModel):
    numbers: list[float] # Allows integers and floats

class ImageTaskData(BaseModel):
    image_id: str

# Database Models (Pydantic models for DB interaction, can also be used for response models)
class TaskResultModel(BaseModel):
    task_id: str
    name: str # To store the name of the task, e.g., "process_task", "add_numbers"
    status: str
    result: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

class UserModel(BaseModel):
    username: str
    hashed_password: str
    disabled: bool = False

# Database initialization function
async def create_db_and_tables():
    async with aiosqlite.connect(DATABASE_URL) as db:
        # Create tasks table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)
        # Create users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                hashed_password TEXT NOT NULL,
                disabled INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def create_test_user_if_not_exists():
    async with aiosqlite.connect(DATABASE_URL) as db:
        cursor = await db.execute("SELECT username FROM users WHERE username = ?", ("user1",))
        user_exists = await cursor.fetchone()
        await cursor.close()

        if not user_exists:
            hashed_password = pwd_context.hash("password1")
            await db.execute(
                "INSERT INTO users (username, hashed_password, disabled) VALUES (?, ?, ?)",
                ("user1", hashed_password, 0)
            )
            await db.commit()
            print("Test user 'user1' created with default password 'password1'.")
        else:
            print("Test user 'user1' already exists.")

@app.on_event("startup")
async def startup_event():
    await create_db_and_tables()
    await create_test_user_if_not_exists() # Add this call

# Root endpoint to serve index.html
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        with open("static/index.html", "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>File not found</h1><p>index.html missing from static folder.</p>", status_code=404)

# Authentication Endpoint
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password) # Await the async call
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
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "INSERT INTO tasks (task_id, name, status, created_at) VALUES (?, ?, ?, ?)",
            (result.id, "process_task", "SUBMITTED", datetime.utcnow().isoformat())
        )
        await db.commit()
    return {"task_id": result.id}

@app.post("/tasks/process-numbers", dependencies=[Depends(get_current_user)])
@limiter.limit("5/minute") # Apply similar rate limiting
async def create_add_numbers_task(request: Request, task_data: NumbersTaskData):
    result = add_numbers.delay(task_data.numbers)
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "INSERT INTO tasks (task_id, name, status, created_at) VALUES (?, ?, ?, ?)",
            (result.id, "add_numbers", "SUBMITTED", datetime.utcnow().isoformat())
        )
        await db.commit()
    return {"task_id": result.id}

@app.post("/tasks/process-image", dependencies=[Depends(get_current_user)])
@limiter.limit("5/minute") # Apply similar rate limiting
async def create_simulate_image_processing_task(request: Request, task_data: ImageTaskData):
    result = simulate_image_processing.delay(task_data.image_id)
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "INSERT INTO tasks (task_id, name, status, created_at) VALUES (?, ?, ?, ?)",
            (result.id, "simulate_image_processing", "SUBMITTED", datetime.utcnow().isoformat())
        )
        await db.commit()
    return {"task_id": result.id}

# Task Status Endpoint (Authenticated)
@app.get("/tasks/{task_id}", dependencies=[Depends(get_current_user)])
async def get_task_status(task_id: str):
    task_result = AsyncResult(task_id)
    if task_result.ready():
        async with aiosqlite.connect(DATABASE_URL) as db:
            await db.execute(
                "UPDATE tasks SET status = ?, result = ?, completed_at = ? WHERE task_id = ?",
                (task_result.status, str(task_result.result), datetime.utcnow().isoformat(), task_id)
            )
            await db.commit()
        
        async with aiosqlite.connect(DATABASE_URL) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT task_id, name, status, result, created_at, completed_at FROM tasks WHERE task_id = ?", (task_id,)) as cursor:
                db_row = await cursor.fetchone()
            if db_row:
                return dict(db_row)
            else:
                # Fallback if DB row not found after update (should not happen ideally)
                return {"status": "completed", "result": str(task_result.result), "task_id": task_id, "name": "N/A", "source": "celery_direct"}
    else:
        async with aiosqlite.connect(DATABASE_URL) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT task_id, name, status, created_at FROM tasks WHERE task_id = ?", (task_id,)) as cursor:
                db_row = await cursor.fetchone()
            if db_row:
                return dict(db_row)
            else:
                # Fallback if DB row not found for pending task
                return {"status": "pending", "task_id": task_id, "name": "N/A", "source": "celery_direct_pending"}