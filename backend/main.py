from fastapi import FastAPI

app = FastAPI(title="Insurance Platform")

# from routers import auth, quotes, policies, reports
# app.include_router(auth.router)
# app.include_router(quotes.router)
# app.include_router(policies.router)
# app.include_router(reports.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}