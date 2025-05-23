# Distributed Task Queue Project

This is a beginner-friendly Python project that uses **Celery**, **Redis**, and **FastAPI** to create a system for processing tasks in the background. For example, you can send a task (like processing some data) to the system, and it will handle it while you do other things. It’s like sending a job to a worker who reports back when done!

The project includes:

- A **FastAPI** web server to submit tasks and check their status.
- **Celery** to manage and process tasks in the background.
- **Redis** to store tasks and results.
- **Authentication** so only authorized users can submit tasks.
- **Rate limiting** to prevent too many requests.
- **Flower** to monitor tasks in a web dashboard.

This guide is for beginners. Follow the steps carefully to set up and run the project on **Windows**.

---

## Prerequisites

Before you start, make sure you have:

1. **Python 3.12** installed. Download it from python.org and install it, checking “Add Python to PATH” during setup.
2. **Docker Desktop** installed. Get it from docker.com and ensure it’s running.
3. **Git** installed. Download it from git-scm.com and install with default settings.
4. **VS Code** (optional but recommended). Download it from code.visualstudio.com.
5. A **GitHub account**. Sign up at github.com if you don’t have one.

---

## Setup Instructions

Follow these steps to set up the project on your Windows computer.

### Step 1: Clone the Project

1. Open VS Code and go to **Terminal** > **New Terminal**.
2. Navigate to your project folder (e.g., `E:\List`). Type:

   ```
   cd E:\List
   ```

   and press Enter.
3. Clone this repository. Replace `your-username` with your GitHub username:

   ```
   git clone https://github.com/your-username/distributed-task-queue.git
   ```
4. Move into the project folder:

   ```
   cd distributed-task-queue
   ```

### Step 2: Set Up Redis with Docker

1. Open a Command Prompt (search “cmd” in Windows).
2. Start Redis in Docker:

   ```
   docker run -d -p 6379:6379 --name redis-server redis
   ```
3. Check it’s running:

   ```
   docker ps
   ```

   You should see `redis-server` listed.

### Step 3: Create a Virtual Environment

1. In the VS Code terminal (in the project folder), create a virtual environment:

   ```
   python -m venv venv
   ```
2. Activate it:

   ```
   .\venv\Scripts\activate
   ```

   You’ll see `(venv)` in the terminal prompt.

### Step 4: Install Dependencies

1. Install the project’s packages:

   ```
   pip install -r requirements.txt
   ```
2. Verify installation:

   ```
   pip list
   ```

   Check that packages like `celery`, `fastapi`, and `redis` are listed.

### Step 5: Verify Project Files

The project includes two main files:

- `celery_app.py`: Defines the Celery setup and a sample task.
- `main.py`: Runs the FastAPI server with authentication and task endpoints.

Open them in VS Code to explore the code. Don’t edit them unless you want to customize the project.

---

## Running the Project

You’ll run three components: Redis (already running in Docker), Celery workers, and the FastAPI server.

### Step 1: Start Celery Workers

1. Open a new terminal in VS Code (**Terminal** > **New Terminal**).
2. Activate the virtual environment:

   ```
   .\venv\Scripts\activate
   ```
3. Run the worker for the `default` queue:

   ```
   celery -A celery_app worker -Q default --loglevel=info --pool=solo
   ```
4. Open another terminal, activate the virtual environment, and run the worker for the `high_priority` queue:

   ```
   celery -A celery_app worker -Q high_priority --loglevel=info --pool=solo
   ```

   Keep both terminals open.

### Step 2: Start the FastAPI Server

1. Open another terminal in VS Code.
2. Activate the virtual environment:

   ```
   .\venv\Scripts\activate
   ```
3. Run the server:

   ```
   uvicorn main:app --reload
   ```

   You’ll see output like:

   ```
   INFO: Uvicorn running on http://127.0.0.1:8000
   ```

   Keep this terminal open.

---

## Testing the Project

Use PowerShell to test the system by sending tasks and checking their status. The project uses authentication, so you’ll need a token first.

### Test 1: Get an Access Token

1. Open a PowerShell terminal in VS Code.
2. Run:

   ```
   (Invoke-WebRequest -Uri "http://localhost:8000/token" -Method POST -Headers @{ "Content-Type" = "application/x-www-form-urlencoded" } -Body "username=user1&password=password1").Content | ConvertFrom-Json
   ```
3. You’ll see:

   ```json
   {
       "access_token": "some-long-jwt-token",
       "token_type": "bearer"
   }
   ```
4. Copy the `access_token`.

### Test 2: Submit a Task

1. Run this command, replacing `your-jwt-token` with the token:

   ```
   (Invoke-WebRequest -Uri "http://localhost:8000/tasks/process" -Method POST -Headers @{ "Authorization" = "Bearer your-jwt-token"; "Content-Type" = "application/json" } -Body '{"data": "example data"}').Content | ConvertFrom-Json
   ```
2. You’ll see:

   ```json
   {
       "task_id": "some-uuid"
   }
   ```
3. Copy the `task_id`.

### Test 3: Check Task Status

1. Wait 5 seconds (the task takes 5 seconds to process).
2. Run, replacing `some-uuid` and `your-jwt-token`:

   ```
   (Invoke-WebRequest -Uri "http://localhost:8000/tasks/some-uuid" -Method GET -Headers @{ "Authorization" = "Bearer your-jwt-token" }).Content | ConvertFrom-Json
   ```
3. You’ll see:
   - If still processing:

     ```json
     {
         "status": "pending"
     }
     ```
   - If done:

     ```json
     {
         "status": "completed",
         "result": "Processed: example data"
     }
     ```

---

## Monitoring Tasks with Flower

Flower is a web dashboard to see your tasks in action.

1. Open a new terminal in VS Code.
2. Activate the virtual environment:

   ```
   .\venv\Scripts\activate
   ```
3. Run Flower:

   ```
   celery -A celery_app flower
   ```
4. Open your browser and go to `http://localhost:5555`.
5. You’ll see a dashboard showing your workers and tasks.

---

## Stopping the Project

When you’re done, stop all services:

1. **Celery Workers**: Press `Ctrl + C` in each worker terminal.
2. **FastAPI Server**: Press `Ctrl + C` in the Uvicorn terminal.
3. **Flower**: Press `Ctrl + C` in the Flower terminal.
4. **Redis**: In a Command Prompt, run:

   ```
   docker stop redis-server
   ```

To restart later, follow the “Running the Project” steps.

---

## Troubleshooting

- **Redis not running**: Check with `docker ps`. Restart with `docker start redis-server`.
- **FastAPI errors**: Ensure all dependencies are installed (`pip install -r requirements.txt`).
- **Task not processing**: Verify both Celery workers are running.
- **PowerShell errors**: Double-check token and task ID in commands.
- **Need help?**: Ask on GitHub Issues or check Stack Overflow.

---

## What’s Next?

You’ve built a cool system! Here are ideas to make it better:

- Add more tasks in `celery_app.py` (e.g., process numbers or images).
- Connect a database to store task results.
- Create a web page to submit tasks instead of PowerShell.

---

## Acknowledgments

Built with the help from Grok 3 (created by xAI). Thanks for trying my project!

## Security Recommendations

This section outlines important security considerations for this application:

1.  **Dependency Vulnerability Scanning:**
    *   Regularly scan `requirements.txt` and all dependencies for known vulnerabilities using tools like `pip-audit`, Snyk, or Trivy. Keep dependencies updated to patched versions.

2.  **CSRF Protection:**
    *   While JWTs are used (which can offer some CSRF protection if tokens are not stored in client-side JavaScript accessible cookies), consider implementing explicit CSRF protection mechanisms, especially if session cookies are used or if there are concerns about token handling.

3.  **Production Error Handling:**
    *   Ensure that detailed error messages or stack traces, which might reveal sensitive system information, are not exposed to clients in a production environment. Implement robust error handling that logs details server-side but shows generic error messages to users.

4.  **Idempotent Celery Tasks:**
    *   The Celery configuration in `celery_app.py` uses `task_acks_late = True`. This enhances fault tolerance but means a task could potentially be executed more than once if a worker fails after starting a task but before acknowledging its completion. Ensure that all Celery tasks (like `process_task`) are designed to be idempotent, meaning they can be safely executed multiple times with the same input without causing unintended side effects.

5.  **Secret Management:**
    *   The `SECRET_KEY` for JWT signing in `main.py` has been modified to be loaded from the `APP_SECRET_KEY` environment variable. Ensure this environment variable is set to a strong, unique, randomly generated key in your production environment. Do not commit the actual secret key to version control.

6.  **Database Security:**
    *   The application has been updated to remove the hardcoded `fake_users_db`. When integrating a real database for user authentication and other data storage:
        *   Use strong, unique credentials for database access.
        *   Limit database user privileges to the minimum required.
        *   Consider network ACLs or firewalls to restrict database access.
        *   Use Object-Relational Mappers (ORMs) or parameterized queries to prevent SQL injection vulnerabilities.

7.  **Celery Broker/Backend Security:**
    *   As noted in `celery_app.py`, secure your Celery broker and backend (e.g., Redis) with passwords, network restrictions, and potentially SSL/TLS if accessed over untrusted networks.

8.  **Rate Limiting with Proxies:**
    *   As noted in `main.py`, if deploying behind a reverse proxy, ensure the rate limiting mechanism correctly identifies client IPs by checking headers like `X-Forwarded-For`.
