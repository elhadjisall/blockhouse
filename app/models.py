from pydantic import BaseModel, validator
from datetime import datetime
from typing import Optional

class OrderBase(BaseModel):
    symbol: str
    price: float
    quantity: int
    order_type: str

    @validator('price')
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Price must be positive')
        return v

    @validator('quantity')
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be positive')
        return v

    @validator('order_type')
    def order_type_must_be_valid(cls, v):
        if v.upper() not in ['BUY', 'SELL']:
            raise ValueError('Order type must be either BUY or SELL')
        return v.upper()