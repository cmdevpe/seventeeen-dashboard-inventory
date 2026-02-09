# Gunicorn configuration file for large file uploads
import multiprocessing

# Binding
bind = "0.0.0.0:10000"

# Workers - Usar 2 para plan gratuito (512MB RAM)
workers = 2
worker_class = "sync"

# Timeouts - Aumentados para procesar archivos grandes
timeout = 300  # 5 minutos para procesar archivos grandes
graceful_timeout = 120
keepalive = 5

# Request limits
limit_request_line = 0  # Sin límite
limit_request_field_size = 0  # Sin límite

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Para archivos grandes
worker_tmp_dir = "/dev/shm"  # Usar memoria compartida si está disponible
