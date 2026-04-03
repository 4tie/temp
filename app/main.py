import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import backtest, strategies, presets, compare, hyperopt

app = FastAPI(
    title="FreqTrade Backtest API",
    version="1.0.0",
    root_path="",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backtest.router)
app.include_router(strategies.router)
app.include_router(presets.router)
app.include_router(compare.router)
app.include_router(hyperopt.router)


@app.get("/healthz")
async def health():
    return {"status": "ok"}
