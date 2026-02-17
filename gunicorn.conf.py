# Gunicorn configuration file for large file uploads
import multiprocessing

# Binding
bind = "0.0.0.0:10000"

# Workers - Usar 1 porque los datos se guardan en memoria del proceso (SESSIONS dict).
# Con >1 worker, los datos subidos en un worker no son visibles en otro.
workers = 1
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
