from typing import Dict, Any, List
import json
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from .clients import GeminiClient
from .schemas import SessionState, IntentType, ConversationMessage, MessageRole
from datetime import datetime
from .tools.restaurants import RestaurantTool
from .tools.recipes import RecipeTool

class JamieAgent:
    def __init__(self):
        self.llm_client = GeminiClient()
        self.restaurant_tool = RestaurantTool()
        self.recipe_tool = RecipeTool()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(SessionState)
        
        workflow.add_node("intent_classifier", self._classify_intent)
        workflow.add_node("restaurant_search", self._search_restaurants)
        workflow.add_node("recipe_search", self._search_recipes)
        workflow.add_node("generate_response", self._generate_response)
        
        workflow.set_entry_point("intent_classifier")
        
        workflow.add_conditional_edges(
            "intent_classifier",
            self._route_intent,
            {
                "restaurant": "restaurant_search",
                "recipe": "recipe_search", 
                "unknown": "generate_response"
            }
        )

        workflow.add_edge("restaurant_search", "generate_response")
        workflow.add_edge("recipe_search", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()
    
    def _build_conversation_context(self, messages: List[ConversationMessage]) -> str:
        """Build a conversation context string from all messages"""
        if not messages:
            return "No previous conversation."
        
        context_parts = []
        for msg in messages:
            role = "User" if msg.role == MessageRole.USER else "Assistant"
            context_parts.append(f"{role}: {msg.content}")
        
        return "\n".join(context_parts)
    
    def _classify_intent(self, state: SessionState) -> SessionState:
        system_prompt = """You are Jamie, a food recommendation assistant. 
        Classify the user's intent as one of: restaurant, recipe, or unknown.
        Consider the full conversation context to understand references like "that first one", "the restaurant you mentioned", etc.
        Return only the intent type."""
        
        # Use full conversation history for context
        conversation_context = self._build_conversation_context(state.messages)
        intent_response = self.llm_client.generate_response(
            f"Conversation context: {conversation_context}",
            system_prompt
        )
        
        intent_map = {
            "restaurant": IntentType.RESTAURANT,
            "recipe": IntentType.RECIPE,
        }
        
        intent = intent_map.get(intent_response.strip().lower(), IntentType.UNKNOWN)
        state.current_intent = intent
        print(f"Classified intent: {state.current_intent}")
        return state
    
    def _route_intent(self, state: SessionState) -> str:
        if state.current_intent == IntentType.RESTAURANT:
            print("Routing to restaurant search")
            return "restaurant"
        elif state.current_intent == IntentType.RECIPE:
            print("Routing to recipe search")
            return "recipe"
        else:
            print("Routing to unknown")
            return "unknown"
    
    def _search_restaurants(self, state: SessionState) -> SessionState:
        # Use full conversation history for context
        conversation_context = self._build_conversation_context(state.messages)
        
        # Track tool usage
        state.context["tools_used"] = state.context.get("tools_used", [])
        state.context["tools_used"].append("RestaurantTool.search_restaurants")
        restaurants = self.restaurant_tool.search_restaurants(conversation_context)
        print(f"Found {len(restaurants)} restaurants")
        state.context["restaurants"] = [rest.model_dump() for rest in restaurants]
        return state
    
    def _search_recipes(self, state: SessionState) -> SessionState:
        # Use full conversation history for context
        conversation_context = self._build_conversation_context(state.messages)
        
        # Track tool usage
        state.context["tools_used"] = state.context.get("tools_used", [])
        
        # Extract search criteria
        system_prompt = """Analyze the user's recipe request and extract:
        1. Ingredients to include (with quantities if specified)
        2. Ingredients to exclude
        3. Maximum total time (in minutes)
        4. Difficulty level (easy/medium/hard)
        5. Dietary preferences or cuisine types (as tags)
        6. Minimum servings needed
        
        Consider the full conversation context to understand references like "that recipe you mentioned", "the ingredients from before", etc.
        
        Return a JSON object with these fields (null if not mentioned):
        {
            "ingredients": [{"name": "ingredient", "quantity": number or null, "unit": "unit" or null}, ...],
            "excluded_ingredients": ["ingredient1", ...],
            "max_total_time": number or null,
            "difficulty": "easy/medium/hard" or null,
            "tags": ["tag1", "tag2", ...],
            "servings": number or null
        }"""
        
        search_criteria = self.llm_client.generate_response(
            f"Conversation context: {conversation_context}",
            system_prompt
        )
        
        try:
            criteria = json.loads(search_criteria)
            # We call find_recipes here, so record that actual tool usage
            state.context["tools_used"].append("RecipeTool.find_recipes")
            # Extract just the ingredient names from the ingredient objects
            ingredient_names = [ing["name"] for ing in criteria.get("ingredients", [])]
            recipes = self.recipe_tool.find_recipes(
                ingredients=ingredient_names,
                difficulty=criteria.get("difficulty"),
                max_prep_time=criteria.get("max_total_time")
            )
        except json.JSONDecodeError:
            # Fallback to simple ingredient search
            ingredient_names = [ing.strip() for ing in search_criteria.split(",")]
            # Record the fallback tool call as well
            state.context["tools_used"].append("RecipeTool.find_recipes")
            recipes = self.recipe_tool.find_recipes(ingredient_names)
        
        state.context["recipes"] = [recipe.model_dump() for recipe in recipes]
        
        # Add search criteria to context for response generation
        state.context["search_criteria"] = criteria if "criteria" in locals() else {"ingredients": ingredient_names}
        return state
    
    def _place_order(self, state: SessionState) -> SessionState:
        # Use full conversation history for context
        conversation_context = self._build_conversation_context(state.messages)
        
        system_prompt = """Extract restaurant name and meal name from the user's message.
        Consider the full conversation context to understand references like "that restaurant", "the first one", etc.
        Return format: restaurant_name|meal_name"""
        
        order_info = self.llm_client.generate_response(
            f"Conversation context: {conversation_context}",
            system_prompt
        )
        
        try:
            restaurant_name, meal_name = order_info.split("|")
            # Track tool usage
            state.context["tools_used"] = state.context.get("tools_used", [])
            state.context["tools_used"].append("RestaurantTool.get_restaurant_by_id")
            restaurant = self.restaurant_tool.get_restaurant_by_id(restaurant_name.strip())
            
            if restaurant:
                state.context["tools_used"].append("OrderTool.place_order")
                order = self.order_tool.place_order(restaurant.id, meal_name.strip())
                state.context["order"] = order.model_dump()
            else:
                state.context["order_error"] = "Restaurant not found"
        except Exception as e:
            state.context["order_error"] = str(e)
        
        return state
    
    def _generate_response(self, state: SessionState) -> SessionState:
        # Use full conversation history for context
        conversation_context = self._build_conversation_context(state.messages)
        
        # Different prompts based on intent
        if state.current_intent == IntentType.UNKNOWN:
            system_prompt = """You are Jamie, a helpful food recommendation assistant.
            Respond to general greetings warmly and explain what you can help with:
            1. Finding and recommending recipes
            2. Finding restaurants and their menus
            3. Placing food orders
            
            If the user's message is unclear, ask for clarification about which of these services they need."""
        else:
            system_prompt = """You are Jamie, a helpful food recommendation assistant.
            Be conversational and helpful. Use the full conversation context to understand references like "that first one", "the restaurant you mentioned", etc.
            
            When discussing recipes:
            1. Format ingredient lists clearly with quantities and units
            2. Mention relevant tags (cuisine type, dietary info, etc.)
            3. Include total time and difficulty level
            4. If the search had specific criteria, acknowledge them in your response
            5. Suggest similar recipes based on tags when relevant
            
            When discussing restaurants:
            1. Reference specific restaurants mentioned in the conversation
            2. Use context from previous messages to understand references like "the first one" or "that place"
            3. Provide helpful details about location, price, and cuisine type"""
        
        context_info = ""
        print("Generating response with context:\n\n", state.context)
        if "restaurants" in state.context:
            context_info += f"Restaurants: {state.context['restaurants']}\n"
        if "recipes" in state.context:
            context_info += f"Recipes: {state.context['recipes']}\n"
            if "search_criteria" in state.context:
                context_info += f"Search Criteria: {state.context['search_criteria']}\n"
        
        try:
            response = self.llm_client.generate_response(
                f"Conversation context: {conversation_context}\nContext: {context_info}",
                system_prompt
            )
            
            # Include tool usage in response
            tools_used = state.context.get("tools_used", [])
            
            if state.current_intent == IntentType.UNKNOWN:
                if not conversation_context.strip() or conversation_context == "No previous conversation.":
                    response = "Hello! I'm Jamie, your food assistant. I can help you with:\n" \
                             "1. Finding and recommending recipes\n" \
                             "2. Finding restaurants and their menus\n" \
                             "3. Placing food orders\n\n" \
                             "What would you like help with?"
                else:
                    response = f"{response}\n\nYou can ask me about recipes, restaurants, or placing orders. How can I help?"
                    
        except Exception as e:
            response = "I'm having trouble understanding that. Could you try rephrasing your request? " \
                      "I can help with recipes, restaurants, or placing orders."
            tools_used = []
        response_with_tools = (
            f"{response}\n\n"
            f"[Debug Info]\n"
            f"Tools used in this interaction:\n"
            f"- " + "\n- ".join(tools_used)
        )
        
        state.context["response"] = response_with_tools
        return state
    
    def process_message(self, user_id: str, message: str, session_id: str = None, conversation_history: List[ConversationMessage] = None) -> str:
        try:
            conversation_message = ConversationMessage(
                session_id=session_id or "",
                user_id=user_id,
                role=MessageRole.USER,
                content=message,
                timestamp=datetime.utcnow().isoformat() + "Z"
            )
            
            # Combine conversation history with current message
            all_messages = (conversation_history or []) + [conversation_message]
            
            print(f"[DEBUG] Creating session state for user {user_id} with {len(all_messages)} messages")
            state = SessionState(
                user_id=user_id, 
                session_id=session_id or "",
                messages=all_messages
            )
            
            print(f"[DEBUG] Invoking graph")
            result = self.graph.invoke(state)
            
            print(f"[DEBUG] Graph result context: {result.get('context', {})}")
            response = result["context"].get("response", "I'm sorry, I couldn't process your request.")
            print(f"[DEBUG] Final response: {response}")
            return response
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"[ERROR] Error in process_message:\n{error_trace}")
            print(f"[ERROR] State at failure: {vars(state) if 'state' in locals() else 'No state'}")
            raise
