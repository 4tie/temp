import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("BACKTEST_API_PORT", "5000"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_dirs=["app", "templates", "static"],
    )
