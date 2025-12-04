from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
from datetime import datetime


class IntentType(str, Enum):
    RESTAURANT = "restaurant"
    RESTAURANT_DETAILS = "restaurant_details"
    RECIPE_SEARCH = "recipe_search"
    RECIPE_DETAILS = "recipe_details"
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
    calories: Optional[float] = None


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
    languageCode: Optional[str] = None


class GoogleMapsLinks(BaseModel):
    """
    Model for the 'googleMapsLinks' object.
    """

    directionsUri: Optional[str] = None
    placeUri: Optional[str] = None
    writeAReviewUri: Optional[str] = None
    reviewsUri: Optional[str] = None
    photosUri: Optional[str] = None


class OpeningTimePoint(BaseModel):
    """
    Model for the 'open' and 'close' time points
    within an opening period.
    """

    day: Optional[int] = None
    hour: Optional[int] = None
    minute: Optional[int] = None


class OpeningPeriod(BaseModel):
    """
    Model for a single 'period' object.
    """

    open: Optional[OpeningTimePoint] = None
    close: Optional[OpeningTimePoint] = None


class BaseOpeningHours(BaseModel):
    """
    A base model for common fields in 'regularOpeningHours'
    and 'regularSecondaryOpeningHours'.
    """

    openNow: Optional[bool] = None
    periods: List[OpeningPeriod] = []
    weekdayDescriptions: List[str] = []
    nextCloseTime: Optional[datetime] = None
    nextOpenTime: Optional[datetime] = None


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

    secondaryHoursType: Optional[str] = None


# --- Main Model ---


class PlaceDetails(BaseModel):
    """
    The main Pydantic model for the entire place details response.
    Flexible schema - all fields optional except name to handle varying API responses.
    """

    name: str
    formattedAddress: Optional[str] = None
    regularOpeningHours: Optional[RegularOpeningHours] = None
    displayName: Optional[DisplayName] = None
    regularSecondaryOpeningHours: Optional[List[SecondaryOpeningHours]] = None
    googleMapsLinks: Optional[GoogleMapsLinks] = None
    priceLevel: Optional[str] = None
    rating: Optional[float] = None
    userRatingCount: Optional[int] = None
    websiteUri: Optional[str] = None
    nationalPhoneNumber: Optional[str] = None
    internationalPhoneNumber: Optional[str] = None
    editorialSummary: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"  # Allow additional fields from API without failing

class UserPreferences(BaseModel):
    dietary_restrictions: List[str] = []
    cuisine_preferences: List[str] = []
    price_range: Optional[str] = None
    location: Optional[str] = None
    default_servings: Optional[int] = None
    preferred_difficulty: Optional[str] = None


class SessionSummary(BaseModel):
    session_id: str
    user_id: str
    timestamp: str
    summary: str
    key_entities: Dict[str, Any] = {}
    intents: List[str] = []
    tools_used: List[str] = []


class UserProfile(BaseModel):
    user_id: str
    preferences: UserPreferences = UserPreferences()
    created_at: str
    updated_at: str
