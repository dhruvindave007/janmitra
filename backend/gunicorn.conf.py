# =============================================================================
# GUNICORN CONFIGURATION
# JanMitra Backend - Production WSGI Server
# =============================================================================

import multiprocessing
import os

# =============================================================================
# SERVER SOCKET
# =============================================================================

# Bind to all interfaces on port 8000
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# =============================================================================
# WORKER PROCESSES
# =============================================================================

# Number of worker processes
# Recommended: (2 x num_cores) + 1
# For demo: Use 2-4 workers
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# Worker class - sync is most stable for Django
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "sync")

# Worker connections (only for async workers like gevent)
worker_connections = 1000

# Maximum requests per worker before restart (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 100

# Worker timeout (seconds) - important for large file uploads
timeout = 300  # 5 minutes for video uploads

# Graceful timeout for worker shutdown
graceful_timeout = 30

# Keep-alive connections
keepalive = 5

# =============================================================================
# SECURITY
# =============================================================================

# Limit request line size (prevent HTTP request smuggling)
limit_request_line = 4094

# Limit request fields
limit_request_fields = 100

# Limit request field size
limit_request_field_size = 8190

# =============================================================================
# SERVER MECHANICS
# =============================================================================

# Daemonize - False for Docker (container manages process)
daemon = False

# PID file location
pidfile = None

# User/Group - handled by Docker USER directive
user = None
group = None

# Working directory
chdir = "/app"

# Temporary file directory
tmp_upload_dir = None

# =============================================================================
# LOGGING
# =============================================================================

# Access log - stdout for Docker
accesslog = "-"

# Error log - stderr for Docker
errorlog = "-"

# Log level
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Access log format
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Capture output from Django's print statements
capture_output = True

# Enable stdout/stderr for Django logging
enable_stdio_inheritance = True

# =============================================================================
# PROCESS NAMING
# =============================================================================

# Process name prefix
proc_name = "janmitra"

# =============================================================================
# SERVER HOOKS
# =============================================================================

def on_starting(server):
    """Called just before the master process is initialized."""
    pass

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    pass

def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    pass

def worker_abort(worker):
    """Called when a worker receives SIGABRT (timeout)."""
    pass

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    pass

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    pass

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    pass

def nworkers_changed(server, new_value, old_value):
    """Called when the number of workers has been changed."""
    pass

def on_exit(server):
    """Called just before exiting gunicorn."""
    pass
