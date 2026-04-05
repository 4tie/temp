from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response

from app.routers import backtest, strategies, presets, compare, hyperopt, ai_chat, evolution, settings

app = FastAPI(
    title="4tie",
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

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

app.include_router(backtest.router)
app.include_router(strategies.router)
app.include_router(presets.router)
app.include_router(compare.router)
app.include_router(hyperopt.router)
app.include_router(ai_chat.router)
app.include_router(evolution.router)
app.include_router(settings.router)


@app.get("/healthz")
async def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse(request=request, name="layouts/base.html")


@app.get("/sw.js")
async def service_worker() -> Response:
    # No-op service worker to satisfy browsers that still request /sw.js.
    return Response(
        content="self.addEventListener('install', () => self.skipWaiting());\n"
                "self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));\n",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )
