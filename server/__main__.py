import os

import uvicorn

from server.app import create_app

uvicorn.run(create_app(os.environ.get("CVT_DATA", "data")),
            host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 8000)))
