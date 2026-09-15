from typing import List, Optional, Dict
from itertools import count
from unittest import skip 

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from motor.motor_asyncio import AsyncIOMotorClient
from bson import objectid
from contextlib import asynccontextmanager

#MongoDB connection string
MONGODB_URI = "mongodb://localhost:27017"
DB_NAME = "pepes_db"
COLL_NAME = "items"

client = AsyncIOMotorClient(None)
db = None
coll = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, db, coll
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    coll = db[COLL_NAME]
    yield
    client.close()

app = FastAPI(title="FastAPIasd", version="1.0.0", lifespan=lifespan)

class itemModel(BaseModel):
    name: str = Field(min_length=1,description="Nombre del producto", example="Item Name")
    precio: float = Field(gt=0, description="Precio del producto", example=10000)
    tags: list[str] = Field(defaultFactory=list, description="Lista de etiquetas del producto", example=["tag1", "tag2"])
    activo: bool = True

class itemModel(BaseModel):
    name: str = Field(min_length=1,description="Nombre del producto", example="Item Name")
    precio: float = Field(gt=0, description="Precio del producto", example=10000)
    tags: list[str] = Field(defaultFactory=list, description="Lista de etiquetas del producto", example=["tag1", "tag2"])
    activo: bool = True


class ItemOut(ItemModel):
    id: str

def doc_to_itemout(doc) -> ItemOut:
    return ItemOut(
        id=str(doc["_id"]),
        name=doc["name"],
        precio=doc["precio"],
        tags=doc.get("tags", []),
        activo=doc.get("activo", True)
    )

#EndPoints

@app.get("/health", tags=["sistema"])
def health_check():
    return {"status": "ok"} 

@app.get("/items", response_model=List[ItemOut])
async def listar_items(
    t: Optional[str] = Query(None, description="Filtro de búsqueda por nombre que tenga t")
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    query = {}
    if t:
        query["nombre"] = {"$regex": t, "$options": "i"}
    cursor = coll.find(query).skip(skip).limit(limit)
    items: List[ItemOut] = []
    async for doc in cursor:
        items.append(doc_to_itemout(doc))
    return items

@app.post("/items", response_model=ItemOut, status_code=201, tags=["items"])