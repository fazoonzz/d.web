from typing import List, Optional, Dict
from itertools import count
from unittest import skip 
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId, objectid
from contextlib import asynccontextmanager

#MongoDB connection string
MONGODB_URI = "mongodb://localhost:27017"
DB_NAME = "dulce_tentacion_db"
COLL_NAME = "items"

client = None 
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

app = FastAPI(title="FastAPI_Dulce_Tentacion", version="1.0.0", lifespan=lifespan)
    
# Añadir middleware CORS para permitir solicitudes desde cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ItemModel(BaseModel):
    name: str = Field(min_length=1,description="Nombre del producto", example="Torta de Chocolate")
    precio: float = Field(gt=0, description="Precio del producto", example=18.990)
    tags: list[str] = Field(defaultFactory=list, description="Categorías del producto", example=["Tortas", "Postres"])
    activo: bool = True

class ItemIn(BaseModel):
    name: str = Field(min_length=1,description="Nombre del producto", example="Torta de Chocolate")
    precio: float = Field(gt=0, description="Precio del producto", example=18.990)
    tags: list[str] = Field(defaultFactory=list, description="Categorías del producto", example=["Tortas", "Postres"])
    activo: bool = True


class ItemOut(ItemModel):
    id: str

def doc_to_itemout(doc) -> ItemOut:
    return ItemOut(
        id=str(doc["_id"]),
        name=doc["name"],
        precio=doc.get("precio", 0),
        tags=doc.get("tags", []),
        activo=doc.get("activo", True)
    )

#EndPoints

@app.get("/health", tags=["sistema"])
def health_check():
    return {"status": "ok", "Backend": "Operativo   " } 

@app.get("/products")
def get_products():
    return {
        "products": [
            {"id": "P01", "name": "Torta Suprema de Chocolate", "price": 18990},
            {"id": "P02", "name": "Deliciosa Torta de Piña", "price": 16500},
            {"id": "P03", "name": "Pie de Limón Artesanal", "price": 12000},
            {"id": "P04", "name": "Torta Selva Negra", "price": 22990}
        ]
    }


@app.get("/items", response_model=List[ItemOut])
async def listar_items(t: Optional[str] = Query(None), skip: int = 0, limit: int = 50):
    query = {}
    if t:
        query["name"] = {"$regex": t, "$options": "i"}
    cursor = coll.find(query).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        items.append(doc_to_itemout(doc))
    return items

@app.post("/items", response_model=ItemOut, status_code=201, tags=["items"])
async def crear_item(item: ItemIn):
    result = await coll.insert_one(item.model_Dump())
    doc = await coll.find_one({"_id": result.inserted_id})
    return doc_to_itemout(doc)

@app.get("/items/{item_id}", response_model=ItemOut, status_code=201, tags=["items"])
async def obtener_item(item_id: str):
    if not ObjectId.is_valid(item_id):
        raise HTTPException(status_code=400, detail="ID inválido")
    doc = await coll.find_one({"_id": ObjectId(item_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    return doc_to_itemout(doc)

@app.put("/items/{item_id}", response_model=ItemOut, tags=["items"])
async def actualizar_item(item_id: str, item: ItemIn):
    if not ObjectId.is_valid(item_id):
        raise HTTPException(status_code=400, detail="ID inválido")
    result = await coll.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": item.model_dump()}
    )   
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    doc = await coll.find_one({"_id": ObjectId(item_id)})
    return doc_to_itemout(doc)

@app.delete("/items/{item_id}", status_code=204, tags=["items"])
async def eliminar_item(item_id: str):
    if not ObjectId.is_valid(item_id):
        raise HTTPException(status_code=400, detail="ID inválido")
    result = await coll.delete_one({"_id": ObjectId(item_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    return None