from app.core.body_limit import BodyLimitMiddleware
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

application = FastAPI()
application.add_middleware(BodyLimitMiddleware, max_bytes=16)


@application.post("/upload")
async def upload(request: Request):
    return {"length": len(await request.body())}


client = TestClient(application)


def test_oversized_content_length_rejected_before_reading_body():
    response = client.post("/upload", content=b"x" * 17)
    assert response.status_code == 413


def test_chunked_body_cannot_bypass_size_limit():
    response = client.post("/upload", content=iter([b"x" * 10, b"y" * 10]))
    assert response.status_code == 413


def test_within_limit_can_be_read():
    response = client.post("/upload", content=b"valid")
    assert response.status_code == 200
    assert response.json() == {"length": 5}
