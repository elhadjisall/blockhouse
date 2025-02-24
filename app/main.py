from fastapi import FastAPI, Depends, HTTPException, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from . import models, database
from .routes.websocket import manager
from datetime import datetime
import json

app = FastAPI(
    title="Trading API",
    description="A simple REST API for handling trade orders",
    version="1.0.0"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Database dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - returns basic API information
    """
    return {
        "message": "Trading API is running",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }


@app.post("/orders/",
          response_model=models.Order,
          tags=["Orders"],
          status_code=status.HTTP_201_CREATED)
async def create_order(order: models.OrderCreate, db: Session = Depends(get_db)):
    """
    Create a new order with the following information:
    - symbol: Stock symbol (e.g., AAPL)
    - price: Order price
    - quantity: Number of shares
    - order_type: Either 'BUY' or 'SELL'
    """
    try:
        db_order = database.OrderModel(
            symbol=order.symbol.upper(),
            price=order.price,
            quantity=order.quantity,
            order_type=order.order_type,
            timestamp=datetime.utcnow()
        )
        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        # Broadcast order creation to WebSocket clients
        await manager.broadcast(
            json.dumps({
                "event": "new_order",
                "data": {
                    "id": db_order.id,
                    "symbol": db_order.symbol,
                    "price": db_order.price,
                    "quantity": db_order.quantity,
                    "order_type": db_order.order_type,
                    "timestamp": db_order.timestamp.isoformat()
                }
            })
        )

        return db_order
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.get("/orders/",
         response_model=List[models.Order],
         tags=["Orders"])
async def get_orders(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    """
    Retrieve a list of orders with pagination support.
    - skip: Number of records to skip
    - limit: Maximum number of records to return
    """
    orders = db.query(database.OrderModel) \
        .offset(skip) \
        .limit(limit) \
        .all()
    return orders


@app.get("/orders/{order_id}",
         response_model=models.Order,
         tags=["Orders"])
async def get_order(order_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific order by its ID
    """
    order = db.query(database.OrderModel) \
        .filter(database.OrderModel.id == order_id) \
        .first()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with id {order_id} not found"
        )
    return order


@app.delete("/orders/{order_id}",
            status_code=status.HTTP_204_NO_CONTENT,
            tags=["Orders"])
async def delete_order(order_id: int, db: Session = Depends(get_db)):
    """
    Delete a specific order by its ID
    """
    order = db.query(database.OrderModel) \
        .filter(database.OrderModel.id == order_id) \
        .first()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with id {order_id} not found"
        )

    db.delete(order)
    db.commit()

    # Broadcast order deletion to WebSocket clients
    await manager.broadcast(
        json.dumps({
            "event": "delete_order",
            "data": {"id": order_id}
        })
    )

    return None


@app.websocket("/ws/orders")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time order updates
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo the received data back to all connected clients
            await manager.broadcast(data)
    except Exception as e:
        manager.disconnect(websocket)


@app.get("/health",
         tags=["Health"])
async def health_check():
    """
    Health check endpoint for monitoring
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)