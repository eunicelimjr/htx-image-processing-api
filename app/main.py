from fastapi import FastAPI

app = FastAPI(title="HTX Image Processing API")

@app.get("/health")
def health():
    return {"status": "ok"}