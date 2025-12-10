from typing import Dict, Any, List, Optional
import json
import re
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from agent.clients import GeminiClient
from agent.schemas import SessionState, IntentType, ConversationMessage, MessageRole
from datetime import datetime
from agent.tools.restaurants import RestaurantTool
from agent.tools.recipes import RecipeTool


class JamieAgent:
    def __init__(self, memory_manager=None):
        self.llm_client = GeminiClient()
        self.restaurant_tool = RestaurantTool()
        self.recipe_tool = RecipeTool()
        self.memory_manager = memory_manager
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

    def _build_conversation_context(
        self, messages: List[ConversationMessage], user_id: str = None
    ) -> str:
        """Build a conversation context string from all messages"""
        context_parts = []

        if self.memory_manager and user_id:
            preferences_context = self.memory_manager.get_user_preferences_context(
                user_id
            )
            if preferences_context:
                context_parts.append(preferences_context)

        if not messages:
            if context_parts:
                return "\n".join(context_parts)
            return "No previous conversation."

        for msg in messages:
            role = "User" if msg.role == MessageRole.USER else "Assistant"
            context_parts.append(f"{role}: {msg.content}")

        return "\n".join(context_parts)

    def _classify_intent(self, state: SessionState) -> SessionState:
        system_prompt = """You are Jamie, a food recommendation assistant.
        Classify the user's intent as one of: restaurant_search, restaurant_details, recipe_search, recipe_details, or unknown.
        - Use 'restaurant_search' for new searches (e.g., "find italian food").
        - Use 'restaurant_details' for follow-up questions about specific restaurants that have already been mentioned (e.g., "what are the hours for the second one?", "tell me more about that place"). Do not route to this if there is no prior restaurant search in the conversation.
        - Use 'recipe_search' for recipe-related queries.
        - Use 'recipe_details' for follow-up questions about specific recipes that have already been mentioned (e.g., "what are the ingredients for that recipe?", "tell me more about that recipe"). Do not route to this if there is no prior recipe search in the conversation.
        Consider the full conversation context. Return only the intent type."""

        conversation_context = self._build_conversation_context(
            state.messages, state.user_id
        )
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
        conversation_context = self._build_conversation_context(
            state.messages, state.user_id
        )

        # Build restaurant list for the prompt (1-indexed for natural language)
        restaurant_list = []
        for i, restaurant in enumerate(
            self.restaurant_tool.last_search_results, start=1
        ):
            restaurant_list.append(f"{i}. {restaurant.name} - {restaurant.location}")
        restaurant_list_str = "\n".join(restaurant_list)

        # Use structured JSON output for reliable parsing
        system_prompt = f"""You are analyzing a conversation to identify which restaurant the user wants details about.

Available restaurants from the last search:
{restaurant_list_str}

Analyze the conversation and determine which restaurant the user is referring to.
The user might reference a restaurant by:
- Position ("the first one", "number 2", "the third option")
- Name ("tell me about Pizza Palace")
- Description ("the one on Main Street")

You MUST respond with ONLY a valid JSON object in this exact format:
{{{{
  "position": <number 1-{len(self.restaurant_tool.last_search_results)} or null>,
  "name": "<exact restaurant name from the list or null>",
  "confidence": "high" | "medium" | "low"
}}}}

IMPORTANT: Always try to provide BOTH position AND name when possible.
- If the user mentions a restaurant by name, look up its position in the list above and include both.
- If the user uses a position reference, include both the position and the corresponding name from the list.

Examples:
- User says "the first one" and first is "Pizza Palace" -> {{"position": 1, "name": "Pizza Palace", "confidence": "high"}}
- User says "tell me about Olive Garden" and it's #3 -> {{"position": 3, "name": "Olive Garden", "confidence": "high"}}
- User says "the Italian place" and you think it's #2 "Luigi's" -> {{"position": 2, "name": "Luigi's", "confidence": "medium"}}

Do not include any other text, just the JSON object."""

        selection_json = self.llm_client.generate_response(
            f"Conversation context:\n{conversation_context}",
            system_prompt,
        ).strip()

        print(f"Restaurant selection JSON: {selection_json}")

        # Track tool usage
        state.context["tools_used"] = state.context.get("tools_used", [])
        state.context["tools_used"].append("RestaurantTool.get_restaurant_details")

        details = None
        selection_info = ""

        try:
            # Clean up the JSON response (remove markdown code blocks if present)
            clean_json = selection_json
            if "```" in clean_json:
                clean_json = clean_json.split("```")[1]
                if clean_json.startswith("json"):
                    clean_json = clean_json[4:]
                clean_json = clean_json.strip()

            selection = json.loads(clean_json)
            position = selection.get("position")
            name = selection.get("name")
            confidence = selection.get("confidence", "low")

            print(
                f"Parsed selection - position: {position}, name: {name}, confidence: {confidence}"
            )

            # Try position first (most reliable for ordinal references)
            if position is not None and isinstance(position, int):
                details = self.restaurant_tool.get_restaurant_by_position(position)
                if details:
                    selection_info = f"restaurant #{position}"
                    print(f"Found restaurant by position {position}")

            # Fall back to name matching if position didn't work
            if details is None and name:
                details = self.restaurant_tool.get_restaurant_details_by_name(name)
                if details:
                    selection_info = name
                    print(f"Found restaurant by name: {name}")

        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {e}")
            # Fallback: try to extract a number or name from the raw response
            selection_info = selection_json

            # Check for ordinal patterns
            import re

            ordinal_match = re.search(
                r"(\d+)|first|second|third|fourth|fifth", selection_json.lower()
            )
            if ordinal_match:
                ordinal_map = {
                    "first": 1,
                    "second": 2,
                    "third": 3,
                    "fourth": 4,
                    "fifth": 5,
                }
                match_text = ordinal_match.group(0)
                position = ordinal_map.get(match_text) or int(match_text)
                details = self.restaurant_tool.get_restaurant_by_position(position)
            else:
                # Try name matching as last resort
                details = self.restaurant_tool.get_restaurant_details_by_name(
                    selection_json
                )

        if details:
            state.context["restaurant_details"] = details.model_dump()
        else:
            state.context["restaurant_details_error"] = (
                f"Could not retrieve restaurant details for: {selection_info}"
            )

        return state

    def _search_restaurants(self, state: SessionState) -> SessionState:
        conversation_context = self._build_conversation_context(
            state.messages, state.user_id
        )
        # Track tool usage
        state.context["tools_used"] = state.context.get("tools_used", [])
        state.context["tools_used"].append("RestaurantTool.search_restaurants")
        restaurants = self.restaurant_tool.search_restaurants(conversation_context)
        print(f"Found {len(restaurants)} restaurants")
        state.context["restaurants"] = [rest.model_dump() for rest in restaurants]
        return state

    def _search_recipes(self, state: SessionState) -> SessionState:
        conversation_context = self._build_conversation_context(
            state.messages, state.user_id
        )

        if self.memory_manager:
            profile = self.memory_manager.get_user_profile(state.user_id)
            prefs = profile.preferences
            if prefs.dietary_restrictions:
                conversation_context += f"\nNote: User has dietary restrictions: {', '.join(prefs.dietary_restrictions)}"
            if prefs.preferred_difficulty:
                conversation_context += f"\nNote: User prefers {prefs.preferred_difficulty} difficulty recipes"

        # Track tool usage
        state.context["tools_used"] = state.context.get("tools_used", [])

        # Extract search criteria
        system_prompt = """Analyze the user's recipe request and extract:
        1. Recipe title or dish name (if they mention a specific dish)
        2. Ingredients to include (just names, no quantities needed)
        3. Ingredients to exclude
        4. Maximum total time (in minutes)
        5. Difficulty level (easy/medium/hard)
        6. Dietary preferences or cuisine types (as tags)
        7. Minimum servings needed
        8. Whether user wants recipes with ALL listed ingredients (true) or ANY of them (false)
           - "I have X and Y, what can I make?" → true (they want to use up what they have)
           - "find something with X or Y" → false (flexible, either works)
           - Default to true when user lists multiple ingredients they have on hand
        Most likely the user will only provide a recipe title or ingredients. Don't use any fields if they are not provided.
        Consider the full conversation context to understand references like "that recipe you mentioned", "the ingredients from before", etc.
        Return a JSON object with these fields (null if not mentioned):
        {
            "recipe_title": "recipe title or dish name" or null,
            "ingredients": ["ingredient1", "ingredient2", ...] or null,
            "excluded_ingredients": ["ingredient1", ...] or null,
            "max_total_time": number or null,
            "difficulty": "easy" or "medium" or "hard" or null,
            "tags": ["tag1", "tag2", ...] or null,
            "servings": number or null,
            "require_all_ingredients": true or false (default true if multiple ingredients listed)
        }"""

        criteria = self.llm_client.generate_response(
            f"Conversation context: {conversation_context}", system_prompt
        )

        search_criteria = criteria
        if "```" in search_criteria:
            search_criteria = search_criteria.split("```")[1]
            if search_criteria.startswith("json"):
                search_criteria = search_criteria[4:]
            search_criteria = search_criteria.strip()

        try:
            print("using search criteria:", search_criteria)
            criteria = json.loads(search_criteria)
            state.context["tools_used"].append("RecipeTool.search_recipes")

            # Extract ingredient names (handle both string and dict formats)
            ingredients = criteria.get("ingredients") or []
            if ingredients and isinstance(ingredients[0], dict):
                ingredients = [ing.get("name", str(ing)) for ing in ingredients]

            # First attempt: search with all provided filters
            recipes = self.recipe_tool.search_recipes(
                recipe_title=criteria.get("recipe_title"),
                ingredients=ingredients if ingredients else None,
                excluded_ingredients=criteria.get("excluded_ingredients"),
                max_total_time=criteria.get("max_total_time"),
                difficulty=criteria.get("difficulty"),
                servings=criteria.get("servings"),
                tags=criteria.get("tags"),
                require_all_ingredients=criteria.get("require_all_ingredients", True),
            )

            # Fallback 1: If no results and we had filters, try with just title or ingredients
            if not recipes and (
                criteria.get("difficulty") or criteria.get("max_total_time")
            ):
                print("No results with filters, trying without difficulty/time filters")
                recipes = self.recipe_tool.search_recipes(
                    recipe_title=criteria.get("recipe_title"),
                    ingredients=ingredients if ingredients else None,
                    excluded_ingredients=criteria.get("excluded_ingredients"),
                )

            # Fallback 2: If still no results and we have a title, try title-only search
            if not recipes and criteria.get("recipe_title"):
                print("No results, trying title-only search")
                recipes = self.recipe_tool.search_by_title(criteria.get("recipe_title"))

            # Fallback 3: If still no results but we have ingredients, try ingredients-only
            if not recipes and ingredients:
                print("No results, trying ingredients-only search")
                recipes = self.recipe_tool.search_recipes(ingredients=ingredients)

        except json.JSONDecodeError:
            # Fallback to simple ingredient search
            ingredient_names = [ing.strip() for ing in search_criteria.split(",")]
            state.context["tools_used"].append("RecipeTool.search_recipes")
            recipes = self.recipe_tool.search_recipes(ingredients=ingredient_names)
            criteria = {"ingredients": ingredient_names}

        # Cache results for follow-up questions
        self.recipe_tool.last_search_results = recipes

        state.context["recipes"] = [recipe.model_dump() for recipe in recipes]

        # Add search criteria to context for response generation
        state.context["search_criteria"] = criteria
        return state

    def _get_recipe_details(self, state: SessionState) -> SessionState:
        conversation_context = self._build_conversation_context(
            state.messages, state.user_id
        )

        # Build recipe list for the prompt (1-indexed for natural language)
        recipe_list = []
        for i, recipe in enumerate(self.recipe_tool.last_search_results, start=1):
            recipe_list.append(f"{i}. {recipe.title} (ID: {recipe.id})")
        recipe_list_str = (
            "\n".join(recipe_list)
            if recipe_list
            else "No recipes from previous search."
        )

        # Use structured JSON output for reliable parsing (like restaurant_details)
        system_prompt = f"""You are analyzing a conversation to identify which recipe the user wants details about.

Available recipes from the last search:
{recipe_list_str}

Analyze the conversation and determine which recipe the user is referring to.
The user might reference a recipe by:
- Position ("the first one", "number 2", "the third recipe")
- Name ("tell me about the carbonara", "the chicken stir-fry")
- Description ("the easy one", "the pasta dish")

You MUST respond with ONLY a valid JSON object in this exact format:
{{
  "position": <number 1-{len(self.recipe_tool.last_search_results)} or null>,
  "name": "<recipe name from the list or null>",
  "confidence": "high" | "medium" | "low"
}}

IMPORTANT: Always try to provide BOTH position AND name when possible.
Do not include any other text, just the JSON object."""

        selection_json = self.llm_client.generate_response(
            f"Conversation context:\n{conversation_context}",
            system_prompt,
        ).strip()

        print(f"Recipe selection JSON: {selection_json}")

        # Track tool usage
        state.context["tools_used"] = state.context.get("tools_used", [])
        state.context["tools_used"].append("RecipeTool.get_recipe_details")

        details = None
        selection_info = ""

        try:
            # Clean up the JSON response (remove markdown code blocks if present)
            clean_json = selection_json
            if "```" in clean_json:
                clean_json = clean_json.split("```")[1]
                if clean_json.startswith("json"):
                    clean_json = clean_json[4:]
                clean_json = clean_json.strip()

            selection = json.loads(clean_json)
            position = selection.get("position")
            name = selection.get("name")

            print(f"Parsed selection - position: {position}, name: {name}")

            # Try position first (most reliable for ordinal references)
            if position is not None and isinstance(position, int):
                details = self.recipe_tool.get_recipe_by_position(position)
                if details:
                    selection_info = f"recipe #{position}"
                    print(f"Found recipe by position {position}")

            # Fall back to name matching if position didn't work
            if details is None and name:
                details = self.recipe_tool.get_recipe_by_name(name)
                if details:
                    selection_info = name
                    print(f"Found recipe by name: {name}")

        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {e}")
            # Fallback: try to extract a number or name from the raw response
            selection_info = selection_json

            ordinal_match = re.search(
                r"(\d+)|first|second|third|fourth|fifth", selection_json.lower()
            )
            if ordinal_match:
                ordinal_map = {
                    "first": 1,
                    "second": 2,
                    "third": 3,
                    "fourth": 4,
                    "fifth": 5,
                }
                match_text = ordinal_match.group(0)
                position = ordinal_map.get(match_text) or int(match_text)
                details = self.recipe_tool.get_recipe_by_position(position)
            else:
                # Try name matching as last resort
                details = self.recipe_tool.get_recipe_by_name(selection_json)

        if details:
            state.context["recipe_details"] = details.model_dump()
        else:
            state.context["recipe_details_error"] = (
                f"Could not retrieve recipe details for: {selection_info}"
            )

        return state

    def _generate_response(self, state: SessionState) -> SessionState:
        conversation_context = self._build_conversation_context(
            state.messages, state.user_id
        )

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
            1. ALWAYS display ALL restaurants from the search results as a numbered list (1, 2, 3, etc.)
            2. Format each restaurant with its number, name, location, and price level
            3. Use context from previous messages to understand references like "the first one" or "that place"
            4. When showing restaurant details, include hours, address, and any available information
            5. The numbered list is important so users can reference restaurants by number later
            
            Example restaurant list format:
            1. **Restaurant Name** - Address (Price Level)
            2. **Another Restaurant** - Address (Price Level)
            ...and so on for ALL restaurants in the results"""

        context_info = ""
        print("Generating response with context:\n\n", state.context)

        # Only inject data relevant to the active intent
        if state.current_intent in [
            IntentType.RESTAURANT,
            IntentType.RESTAURANT_DETAILS,
        ]:
            if "restaurants" in state.context:
                context_info += f"Restaurants: {state.context['restaurants']}\n"
            if "restaurant_details" in state.context:
                context_info += f"Selected Restaurant Details: {state.context['restaurant_details']}\n"

        elif state.current_intent in [
            IntentType.RECIPE_SEARCH,
            IntentType.RECIPE_DETAILS,
        ]:
            if "recipes" in state.context:
                context_info += f"Recipes: {state.context['recipes']}\n"
            if "recipe_details" in state.context:
                context_info += (
                    f"Selected Recipe Details: {state.context['recipe_details']}\n"
                )
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
