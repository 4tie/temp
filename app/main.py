from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.routers import backtest, compare, evolution, hyperopt, presets, settings, strategies, ai_chat
from app.services.ai_chat.loop_service import load_loop_state


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/css/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_loop_state()
    yield


app = FastAPI(
    title="4tie",
    version="1.0.0",
    root_path="",
    lifespan=lifespan,
)

app.add_middleware(NoCacheMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static", html=False), name="static")

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
    return Response(
        content="self.addEventListener('install', () => self.skipWaiting());\n"
        "self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));\n",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )
