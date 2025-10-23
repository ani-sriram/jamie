from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class IntentType(str, Enum):
    RESTAURANT = "restaurant"
    RECIPE = "recipe"
    UNKNOWN = "unknown"

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

class ConversationMessage(BaseModel):
    session_id: str
    user_id: str
    role: MessageRole
    content: str
    timestamp: str

class Restaurant(BaseModel):
    name: str
    location: Optional[str]
    priceLevel: Optional[str]
    description: Optional[str] = None

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

class AgentResponse(BaseModel):
    message: str
    intent: Optional[IntentType] = None
    tools_used: List[str] = []
    data: Optional[Dict[str, Any]] = None

class SessionState(BaseModel):
    user_id: str
    session_id: str
    messages: List[ConversationMessage] = []
    current_intent: Optional[IntentType] = None
    context: Dict[str, Any] = {}