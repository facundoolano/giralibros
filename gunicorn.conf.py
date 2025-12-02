"""
Gunicorn configuration file for giralibros.

This file is used by the gunicorn server when running in production.
It should be referenced in the systemd service file with --config flag.
"""

import multiprocessing

# Bind to unix socket (systemd creates /run/gunicorn/ directory)
bind = "unix:/run/gunicorn/gunicorn.sock"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1

# Worker class
worker_class = "sync"

# Timeout for requests (seconds)
timeout = 60

# Graceful timeout for workers during reload (seconds)
graceful_timeout = 30

# Max requests per worker before restart (helps with memory leaks)
max_requests = 1000
max_requests_jitter = 100

# Logging
accesslog = "-"  # Log to stdout (systemd will capture)
errorlog = "-"  # Log to stderr (systemd will capture)
loglevel = "info"

# Process naming
proc_name = "giralibros"

# Preload application for better performance
preload_app = True

umask = 0o007
