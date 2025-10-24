from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
from datetime import datetime

class IntentType(str, Enum):
    RESTAURANT = "restaurant"
    RESTAURANT_DETAILS = "restaurant_details"
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
    id: str
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

class DisplayName(BaseModel):
    """
    Model for the 'displayName' object.
    """
    text: str
    languageCode: str

class GoogleMapsLinks(BaseModel):
    """
    Model for the 'googleMapsLinks' object.
    """
    directionsUri: str
    placeUri: str
    writeAReviewUri: str
    reviewsUri: str
    photosUri: str

class OpeningTimePoint(BaseModel):
    """
    Model for the 'open' and 'close' time points
    within an opening period.
    """
    day: int
    hour: int
    minute: int

class OpeningPeriod(BaseModel):
    """
    Model for a single 'period' object.
    """
    open: OpeningTimePoint
    close: OpeningTimePoint

class BaseOpeningHours(BaseModel):
    """
    A base model for common fields in 'regularOpeningHours'
    and 'regularSecondaryOpeningHours'.
    """
    openNow: bool
    periods: List[OpeningPeriod]
    weekdayDescriptions: List[str]
    nextCloseTime: datetime # Pydantic will auto-parse the ISO 8601 string

class RegularOpeningHours(BaseOpeningHours):
    """
    Model for 'regularOpeningHours'. Inherits all fields from BaseOpeningHours.
    """
    pass

class SecondaryOpeningHours(BaseOpeningHours):
    """
    Model for items in 'regularSecondaryOpeningHours'.
    Inherits from BaseOpeningHours and adds 'secondaryHoursType'.
    """
    secondaryHoursType: str

# --- Main Model ---

class PlaceDetails(BaseModel):
    """
    The main Pydantic model for the entire place details response.
    """
    name: str
    formattedAddress: str
    regularOpeningHours: RegularOpeningHours
    displayName: DisplayName
    regularSecondaryOpeningHours: List[SecondaryOpeningHours]
    googleMapsLinks: GoogleMapsLinks