import os

import dotenv
from django.core.asgi import get_asgi_application

dotenv.load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "movbitsapi.settings.base")

application = get_asgi_application()
