from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(title="Local API Gateway")

# Permite que index.php consuma este endpoint sin problemas de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKEND_URL = "http://localhost:9000"

@app.get("/api/products")
async def products():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/products")
    return response.json()
