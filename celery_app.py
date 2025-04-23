from celery import Celery

# Initialize Celery with Redis as the broker and result backend
app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

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