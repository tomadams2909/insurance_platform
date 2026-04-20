import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import models.tenant
import models.user
import models.quote
import models.vehicle
import models.policy
import models.policy_transaction
import models.document
import models.dealer
import models.dealer_commission  # noqa: F401
from routers import auth, dealers, quotes, policies, internal, reports

app = FastAPI(title="Insurance Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

app.include_router(auth.router)
app.include_router(quotes.router)
app.include_router(policies.router)
app.include_router(dealers.router)
app.include_router(internal.router)
app.include_router(reports.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
