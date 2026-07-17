from fastapi import FastAPI

app = FastAPI(title="LDEO_IX Cruise/Cast Intake")


@app.get("/health")
def health():
    return {"status": "ok"}
