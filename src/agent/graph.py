from typing import Dict, Any, List
import json
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from agent.clients import GeminiClient
from agent.schemas import SessionState, IntentType, ConversationMessage, MessageRole
from datetime import datetime
from agent.tools.restaurants import RestaurantTool
from agent.tools.recipes import RecipeTool


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
        workflow.add_node("restaurant_details", self._get_restaurant_details)
        workflow.add_node("recipe_search", self._search_recipes)
        workflow.add_node("recipe_details", self._get_recipe_details)
        workflow.add_node("generate_response", self._generate_response)

        workflow.set_entry_point("intent_classifier")

        workflow.add_conditional_edges(
            "intent_classifier",
            self._route_intent,
            {
                "restaurant_search": "restaurant_search",
                "restaurant_details": "restaurant_details",
                "recipe_search": "recipe_search",
                "recipe_details": "recipe_details",
                "unknown": "generate_response",
            },
        )

        workflow.add_edge("restaurant_search", "generate_response")
        workflow.add_edge("restaurant_details", "generate_response")
        workflow.add_edge("recipe_search", "generate_response")
        workflow.add_edge("recipe_details", "generate_response")
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
        Classify the user's intent as one of: restaurant_search, restaurant_details, recipe, or unknown.
        - Use 'restaurant_search' for new searches (e.g., "find italian food").
        - Use 'restaurant_details' for follow-up questions about specific restaurants that have already been mentioned (e.g., "what are the hours for the second one?", "tell me more about that place"). Do not route to this if there is no prior restaurant search in the conversation.
        - Use 'recipe_search' for recipe-related queries.
        - Use 'recipe_details' for follow-up questions about specific recipes that have already been mentioned (e.g., "what are the ingredients for that recipe?", "tell me more about that recipe"). Do not route to this if there is no prior recipe search in the conversation.
        Consider the full conversation context. Return only the intent type."""

        conversation_context = self._build_conversation_context(state.messages)
        intent_response = self.llm_client.generate_response(
            f"Conversation context: {conversation_context}", system_prompt
        )

        intent_map = {
            "restaurant_search": IntentType.RESTAURANT,
            "restaurant_details": IntentType.RESTAURANT_DETAILS,
            "recipe_search": IntentType.RECIPE_SEARCH,
            "recipe_details": IntentType.RECIPE_DETAILS,
        }

        intent = intent_map.get(intent_response.strip().lower(), IntentType.UNKNOWN)
        state.current_intent = intent
        print(f"Classified intent: {state.current_intent}")
        return state

    def _route_intent(self, state: SessionState) -> str:
        if state.current_intent == IntentType.RESTAURANT:
            return "restaurant_search"
        elif state.current_intent == IntentType.RESTAURANT_DETAILS:
            return "restaurant_details"
        elif state.current_intent == IntentType.RECIPE_SEARCH:
            print("Routing to recipe search")
            return "recipe_search"
        elif state.current_intent == IntentType.RECIPE_DETAILS:
            print("Routing to recipe details")
            return "recipe_details"
        else:
            print("Routing to unknown")
            return "unknown"

    def _get_restaurant_details(self, state: SessionState) -> SessionState:
        # Use full conversation history for context
        conversation_context = self._build_conversation_context(state.messages)

        # First try to get restaurant details by name matching
        system_prompt = """
        The user has requested details about a specific restaurant. 
        Previously the user searched for restaurants and you have a list of results.
        Figure out which restaurant they are referring to from the conversation context.
        
        Available restaurants from the last search:
        {restaurant_list}
        
        Try to identify the restaurant by name. If you can identify the restaurant name, 
        provide just the restaurant name. If you can't identify by name, provide the index 
        number (starting from 0) from the list above.
        
        Respond with either:
        - The restaurant name (e.g., "Pizza Palace")
        - The index number (e.g., "2")
        """

        # Build restaurant list for the prompt
        restaurant_list = []
        for i, restaurant in enumerate(self.restaurant_tool.last_search_results):
            restaurant_list.append(f"{i}. {restaurant.name} - {restaurant.location}")

        restaurant_list_str = "\n".join(restaurant_list)

        selection = self.llm_client.generate_response(
            f"Conversation context: {conversation_context}\n\nRestaurant list:\n{restaurant_list_str}",
            system_prompt.format(restaurant_list=restaurant_list_str),
        ).strip()

        print(f"Restaurant selection: {selection}")

        # Track tool usage
        state.context["tools_used"] = state.context.get("tools_used", [])
        state.context["tools_used"].append("RestaurantTool.get_restaurant_details")

        # Try to get details by name first, then by index
        details = None
        try:
            # Check if selection is a number (index)
            if selection.isdigit():
                index = int(selection)
                details = self.restaurant_tool.get_restaurant_details_by_index(index)
                print(
                    f"Fetching details for restaurant at index {index}: {self.restaurant_tool.last_search_results[index].name}"
                )
            else:
                # Try to get by name
                details = self.restaurant_tool.get_restaurant_details_by_name(selection)
                print(f"Fetching details for restaurant by name: {selection}")
        except (ValueError, IndexError) as e:
            print(f"Error parsing restaurant selection: {e}")
            details = None

        if details:
            state.context["restaurant_details"] = details.model_dump()
        else:
            state.context["restaurant_details_error"] = (
                f"Could not retrieve restaurant details for: {selection}"
            )

        return state

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
        Most likely the user will only provide a recipe title or ingredients. Don't use any fields if they are not provided.
        Consider the full conversation context to understand references like "that recipe you mentioned", "the ingredients from before", etc.
        Return a JSON object with these fields (null if not mentioned):
        {
            "recipe_title": "recipe title" or null,
            "ingredients": [{"name": "ingredient", "quantity": number or null, "unit": "unit" or null, "calories": number or null}, ...] or null,
            "excluded_ingredients": ["ingredient1", ...] or null,
            "max_total_time": number or null,
            "difficulty": "easy/medium/hard" or null,
            "tags": ["tag1", "tag2", ...] or null,
            "servings": number or null
        }"""

        search_criteria = self.llm_client.generate_response(
            f"Conversation context: {conversation_context}", system_prompt
        )

        try:
            print("using search criteria:", search_criteria)
            criteria = json.loads(search_criteria)
            # We call find_recipes here, so record that actual tool usage
            state.context["tools_used"].append("RecipeTool.find_recipes")
            # Extract just the ingredient names from the ingredient objects
            ingredient_names = [ing["name"] for ing in criteria.get("ingredients", [])]
            recipes = self.recipe_tool.find_recipes(
                ingredients=ingredient_names,
                difficulty=criteria.get("difficulty"),
                max_prep_time=criteria.get("max_total_time"),
            )
        except json.JSONDecodeError:
            # Fallback to simple ingredient search
            ingredient_names = [ing.strip() for ing in search_criteria.split(",")]
            # Record the fallback tool call as well
            state.context["tools_used"].append("RecipeTool.find_recipes")
            recipes = self.recipe_tool.find_recipes(ingredient_names)

        state.context["recipes"] = [recipe.model_dump() for recipe in recipes]

        # Add search criteria to context for response generation
        state.context["search_criteria"] = (
            criteria if "criteria" in locals() else {"ingredients": ingredient_names}
        )
        return state

    def _get_recipe_details(self, state: SessionState) -> SessionState:
        # Use full conversation history for context
        conversation_context = self._build_conversation_context(state.messages)

        system_prompt = """The user has requested details about a specific recipe. Figure out which recipe they are referring to from the conversation context. Then provide its ID. Provide the recipe Id"""

        recipe_id = self.llm_client.generate_response(
            f"Conversation context: {conversation_context}", system_prompt
        ).strip()
        print(f"Fetching details for recipe ID: {recipe_id}")
        # Track tool usage
        state.context["tools_used"] = state.context.get("tools_used", [])
        state.context["tools_used"].append("RecipeTool.get_recipe_details")
        details = self.recipe_tool.get_recipe_by_id(recipe_id)
        if details:
            state.context["recipe_details"] = details.model_dump()
        else:
            state.context["recipe_details_error"] = "Could not retrieve recipe details."

        return state

    def _generate_response(self, state: SessionState) -> SessionState:
        # Use full conversation history for context
        conversation_context = self._build_conversation_context(state.messages)

        # Different prompts based on intent
        if state.current_intent == IntentType.UNKNOWN:
            system_prompt = """You are Jamie, a helpful food recommendation assistant.
            Respond to general greetings warmly and explain what you can help with:
            1. Finding and recommending recipes
            2. Finding restaurants if given a location and details about what they want
            
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
                system_prompt,
            )

            # Include tool usage in response
            tools_used = state.context.get("tools_used", [])

            if state.current_intent == IntentType.UNKNOWN:
                if (
                    not conversation_context.strip()
                    or conversation_context == "No previous conversation."
                ):
                    response = (
                        "Hello! I'm Jamie, your food assistant. I can help you with:\n"
                        "1. Finding and recommending recipes\n"
                        "2. Finding restaurants and their menus\n"
                        "What would you like help with?"
                    )
                else:
                    response = f"{response}\n\nYou can ask me about recipes or restaurants. How can I help?"

        except Exception as e:
            response = (
                "I'm having trouble understanding that. Could you try rephrasing your request? "
                "I can help with recipes or restaurants."
            )
            tools_used = []
        response_with_tools = (
            f"{response}\n\n"
            f"[Debug Info]\n"
            f"Tools used in this interaction:\n"
            f"- " + "\n- ".join(tools_used)
        )

        state.context["response"] = response_with_tools
        return state

    def process_message(
        self,
        user_id: str,
        message: str,
        session_id: str = None,
        conversation_history: List[ConversationMessage] = None,
    ) -> str:
        try:
            conversation_message = ConversationMessage(
                session_id=session_id or "",
                user_id=user_id,
                role=MessageRole.USER,
                content=message,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )

            # Combine conversation history with current message
            all_messages = (conversation_history or []) + [conversation_message]

            print(
                f"[DEBUG] Creating session state for user {user_id} with {len(all_messages)} messages"
            )
            state = SessionState(
                user_id=user_id, session_id=session_id or "", messages=all_messages
            )

            print(f"[DEBUG] Invoking graph")
            result = self.graph.invoke(state)

            print(f"[DEBUG] Graph result context: {result.get('context', {})}")
            response = result["context"].get(
                "response", "I'm sorry, I couldn't process your request."
            )
            print(f"[DEBUG] Final response: {response}")
            return response

        except Exception as e:
            import traceback

            error_trace = traceback.format_exc()
            print(f"[ERROR] Error in process_message:\n{error_trace}")
            print(
                f"[ERROR] State at failure: {vars(state) if 'state' in locals() else 'No state'}"
            )
            raise
