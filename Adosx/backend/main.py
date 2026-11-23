import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

from backend.database import init_db
from backend.api.routes import router as api_router

# Initialize database on startup
init_db()

app = FastAPI(
    title="AdosX Data Reconciliation Engine",
    description="Full-stack multi-tenant data reconciliation application",
    version="1.0.0"
)

# Enable CORS for local Vite dev server if running separately
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(api_router)

# Path to static frontend
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
STATIC_INDEX = os.path.join(FRONTEND_DIR, "index.html")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    if os.path.exists(STATIC_INDEX):
        with open(STATIC_INDEX, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>AdosX Reconciliation Engine Backend is running. Frontend index.html not found.</h1>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
