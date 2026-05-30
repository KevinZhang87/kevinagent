import uvicorn
from app.config import app_config

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=app_config.server.host,
        port=app_config.server.port,
        reload=app_config.server.debug,
    )
