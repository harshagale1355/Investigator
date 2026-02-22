import random
from datetime import datetime, timedelta

TOTAL_LINES = 1_000_000
ERROR_COUNT = 2

log_levels = ["INFO", "DEBUG", "WARN"]
components = ["AuthService", "DBService", "Cache", "API", "Scheduler", "Worker"]
messages = {
    "INFO": [
        "Request processed successfully",
        "Heartbeat check passed",
        "Cache hit",
        "Background job completed"
    ],
    "DEBUG": [
        "Query execution time recorded",
        "Payload validation passed",
        "Retry mechanism initialized"
    ],
    "WARN": [
        "High memory usage detected",
        "API response time slow",
        "Cache miss occurred"
    ]
}

error_messages = [
    "NullPointerException at UserService.java:42",
    "Database connection timeout",
]

start_time = datetime.now()

# Pick random lines for ERROR
error_lines = set(random.sample(range(TOTAL_LINES), ERROR_COUNT))

with open("system.log", "w") as f:
    for i in range(TOTAL_LINES):
        timestamp = (start_time + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
        component = random.choice(components)

        if i in error_lines:
            f.write(f"{timestamp} ERROR {component} - {random.choice(error_messages)}\n")
        else:
            level = random.choice(log_levels)
            msg = random.choice(messages[level])
            f.write(f"{timestamp} {level} {component} - {msg}\n")
