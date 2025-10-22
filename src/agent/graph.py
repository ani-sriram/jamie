from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from .llm_client import GeminiClient
from .schemas import SessionState, IntentType, AgentResponse, UserMessage
from .tools.restaurants import RestaurantTool
from .tools.recipes import RecipeTool
from .tools.order import OrderTool

class JamieAgent:
    def __init__(self):
        self.llm_client = GeminiClient()
        self.restaurant_tool = RestaurantTool()
        self.recipe_tool = RecipeTool()
        self.order_tool = OrderTool()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(SessionState)
        
        workflow.add_node("intent_classifier", self._classify_intent)
        workflow.add_node("restaurant_search", self._search_restaurants)
        workflow.add_node("recipe_search", self._search_recipes)
        workflow.add_node("place_order", self._place_order)
        workflow.add_node("generate_response", self._generate_response)
        
        workflow.set_entry_point("intent_classifier")
        
        workflow.add_conditional_edges(
            "intent_classifier",
            self._route_intent,
            {
                "restaurant": "restaurant_search",
                "recipe": "recipe_search", 
                "order": "place_order",
                "unknown": "generate_response"
            }
        )
        
        workflow.add_edge("restaurant_search", "generate_response")
        workflow.add_edge("recipe_search", "generate_response")
        workflow.add_edge("place_order", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()
    
    def _classify_intent(self, state: SessionState) -> SessionState:
        system_prompt = """You are Jamie, a food recommendation assistant. 
        Classify the user's intent as one of: restaurant, recipe, order, or unknown.
        Return only the intent type."""
        
        last_message = state.messages[-1].content if state.messages else ""
        intent_response = self.llm_client.generate_response(
            f"User message: {last_message}",
            system_prompt
        )
        
        intent_map = {
            "restaurant": IntentType.RESTAURANT,
            "recipe": IntentType.RECIPE,
            "order": IntentType.ORDER
        }
        
        intent = intent_map.get(intent_response.strip().lower(), IntentType.UNKNOWN)
        state.current_intent = intent
        return state
    
    def _route_intent(self, state: SessionState) -> str:
        if state.current_intent == IntentType.RESTAURANT:
            return "restaurant"
        elif state.current_intent == IntentType.RECIPE:
            return "recipe"
        elif state.current_intent == IntentType.ORDER:
            return "order"
        else:
            return "unknown"
    
    def _search_restaurants(self, state: SessionState) -> SessionState:
        last_message = state.messages[-1].content if state.messages else ""
        
        restaurants = self.restaurant_tool.search_restaurants(last_message)
        state.context["restaurants"] = [rest.model_dump() for rest in restaurants]
        return state
    
    def _search_recipes(self, state: SessionState) -> SessionState:
        last_message = state.messages[-1].content if state.messages else ""
        
        system_prompt = """Extract ingredients mentioned in the user's message. 
        Return only a comma-separated list of ingredients."""
        
        ingredients_response = self.llm_client.generate_response(
            f"User message: {last_message}",
            system_prompt
        )
        
        ingredients = [ing.strip() for ing in ingredients_response.split(",")]
        recipes = self.recipe_tool.find_recipes(ingredients)
        state.context["recipes"] = [recipe.model_dump() for recipe in recipes]
        return state
    
    def _place_order(self, state: SessionState) -> SessionState:
        last_message = state.messages[-1].content if state.messages else ""
        
        system_prompt = """Extract restaurant name and meal name from the user's message.
        Return format: restaurant_name|meal_name"""
        
        order_info = self.llm_client.generate_response(
            f"User message: {last_message}",
            system_prompt
        )
        
        try:
            restaurant_name, meal_name = order_info.split("|")
            restaurant = self.restaurant_tool.get_restaurant_by_id(restaurant_name.strip())
            
            if restaurant:
                order = self.order_tool.place_order(restaurant.id, meal_name.strip())
                state.context["order"] = order.model_dump()
            else:
                state.context["order_error"] = "Restaurant not found"
        except Exception as e:
            state.context["order_error"] = str(e)
        
        return state
    
    def _generate_response(self, state: SessionState) -> SessionState:
        last_message = state.messages[-1].content if state.messages else ""
        
        system_prompt = """You are Jamie, a helpful food recommendation assistant. 
        Be conversational and helpful. Use the context data to provide relevant recommendations."""
        
        context_info = ""
        if "restaurants" in state.context:
            context_info += f"Restaurants: {state.context['restaurants']}\n"
        if "recipes" in state.context:
            context_info += f"Recipes: {state.context['recipes']}\n"
        if "order" in state.context:
            context_info += f"Order: {state.context['order']}\n"
        if "order_error" in state.context:
            context_info += f"Order Error: {state.context['order_error']}\n"
        
        response = self.llm_client.generate_response(
            f"User: {last_message}\nContext: {context_info}",
            system_prompt
        )
        
        state.context["response"] = response
        return state
    
    def process_message(self, user_id: str, message: str) -> str:
        state = SessionState(user_id=user_id, messages=[UserMessage(content=message)])
        result = self.graph.invoke(state)
        return result["context"].get("response", "I'm sorry, I couldn't process your request.")
