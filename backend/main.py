import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import models.tenant
import models.user
import models.quote
import models.vehicle
import models.policy
import models.policy_transaction
import models.document
import models.dealer
import models.dealer_commission
from routers import auth, quotes, policies

app = FastAPI(title="Insurance Platform")

_static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

app.include_router(auth.router)
app.include_router(quotes.router)
app.include_router(policies.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
