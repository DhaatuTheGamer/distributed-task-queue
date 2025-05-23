from celery import Celery
import time # For time.sleep()

# Initialize Celery with Redis as the broker and result backend
app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

app.conf.task_serializer = 'json'
app.conf.accept_content = ['json']  # Ensure the worker only accepts json
app.conf.result_serializer = 'json'

# Configure task queues for prioritization
app.conf.task_queues = {
    'default': {
        'exchange': 'default',
        'routing_key': 'default',
    },
    'high_priority': {
        'exchange': 'high_priority',
        'routing_key': 'high_priority',
    },
}

# Enable late acknowledgment for fault tolerance and set result expiration
app.conf.task_acks_late = True
app.conf.result_expires = 3600  # Results expire after 1 hour

# Define a sample task with retry logic
@app.task(bind=True, max_retries=3, default_retry_delay=60, queue='default')
def process_task(self, data):
    try:
        # Simulate a long-running task (e.g., image processing or data analysis)
        import time
        time.sleep(5)  # Simulate computation
        return f"Processed: {data}"
    except Exception as exc:
        # Retry on failure, up to 3 times with a 60-second delay
        raise self.retry(exc=exc)

@app.task(queue='default')
def add_numbers(numbers):
    if not isinstance(numbers, list):
        # It's good practice for Celery tasks to raise exceptions that Celery can handle
        # or return a serializable error state. Raising TypeError is fine.
        raise TypeError("Input must be a list of numbers.")
    
    for num in numbers:
        if not isinstance(num, (int, float)):
            raise TypeError(f"List contains non-numeric element: {num}")
            
    return sum(numbers)

@app.task(queue='default')
def simulate_image_processing(image_id):
    if not isinstance(image_id, str) or not image_id.strip():
        # Raising ValueError is appropriate here.
        raise ValueError("image_id must be a non-empty string.")
    time.sleep(1)  # Simulate image processing time
    return f"Image {image_id} processed successfully."

# SECURITY BEST PRACTICES for Broker/Backend (Redis):
# 1. Secure Redis with a strong password: Modify the broker/backend URLs to include the password,
#    e.g., 'redis://:yourpassword@localhost:6379/0'.
# 2. Use network ACLs or firewall rules to restrict access to the Redis instance to only trusted hosts.
# 3. Run Redis in protected mode (default in recent versions) if it's not password protected and accessible from the internet.
# 4. Consider using SSL/TLS for encrypting data in transit if Redis is accessed over untrusted networks.