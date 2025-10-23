from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum

class IntentType(str, Enum):
    RESTAURANT = "restaurant"
    RECIPE = "recipe"
    ORDER = "order"
    UNKNOWN = "unknown"

class Restaurant(BaseModel):
    id: str
    name: str
    location: str
    cuisine_type: str
    meals: List[str]
    rating: float
    price_range: str

class Ingredient(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None

class Recipe(BaseModel):
    id: str
    title: str
    ingredients: List[Ingredient]
    instructions: List[str]
    prep_time: int
    cook_time: int
    difficulty: str
    servings: int
    tags: List[str] = []

class Order(BaseModel):
    id: str
    restaurant_id: str
    meal_id: str
    status: str
    total_price: float

class UserMessage(BaseModel):
    content: str
    timestamp: Optional[str] = None

class AgentResponse(BaseModel):
    message: str
    intent: Optional[IntentType] = None
    tools_used: List[str] = []
    data: Optional[Dict[str, Any]] = None

class SessionState(BaseModel):
    user_id: str
    messages: List[UserMessage] = []
    current_intent: Optional[IntentType] = None
    context: Dict[str, Any] = {}