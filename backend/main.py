from fastapi import FastAPI

import models.tenant
import models.user
import models.quote
import models.vehicle
import models.policy
from routers import auth, quotes

app = FastAPI(title="Insurance Platform")

app.include_router(auth.router)
app.include_router(quotes.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
