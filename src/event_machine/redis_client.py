import ssl

import redis
from django.conf import settings

redis_url = settings.EVENT_MACHINE_REDIS_URL

# Parse URL if needed (urlparse or use redis.from_url)
redis_client = redis.from_url(
    redis_url,
    connection_class=redis.SSLConnection,  # Use SSLConnection for secure connections
    ssl_cert_reqs=ssl.CERT_NONE,  # Disable certificate verification for self-signed certificates
)
