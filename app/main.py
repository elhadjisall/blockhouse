from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from . import models, database
from datetime import datetime

app = FastAPI(title="Trading API")

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/orders/", response_model=models.Order)
def create_order(order: models.OrderCreate, db: Session = Depends(get_db)):
    db_order = database.OrderModel(
        symbol=order.symbol,
        price=order.price,
        quantity=order.quantity,
        order_type=order.order_type,
        timestamp=datetime.utcnow()
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

@app.get("/orders/", response_model=List[models.Order])
def get_orders(db: Session = Depends(get_db)):
    orders = db.query(database.OrderModel).all()
    return orders


from fastapi import WebSocket
from .routes.websocket import manager
import json


@app.websocket("/ws/orders")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Order update: {data}")
    except:
        manager.disconnect(websocket)