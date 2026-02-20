from fastapi import FastAPI
import uvicorn


app = FastAPI(title="EkstreHub API", version="1.0.0-alpha.1")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "ekstrehub-api"}


def main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()

