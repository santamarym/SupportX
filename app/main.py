from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import auth, tickets, chat, kb

# Creates all tables on startup if they don't exist yet (fine for a demo;
# in production you'd use Alembic migrations instead).
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SupportX API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(chat.router)
app.include_router(kb.router)

@app.get("/")
def root():
    return {"message": "SupportX API is running"}
