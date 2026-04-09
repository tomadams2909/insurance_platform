from fastapi import FastAPI

import models.tenant
import models.user
import models.quote
import models.vehicle
from routers import auth

app = FastAPI(title="Insurance Platform")

app.include_router(auth.router)

# app.include_router(quotes.router)
# app.include_router(policies.router)
# app.include_router(reports.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
