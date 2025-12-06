from typing import Optional, List
from datetime import datetime
from agent.schemas import UserProfile, UserPreferences, SessionSummary, ConversationMessage, IntentType
from agent_service.memory_storage import MemoryStorage
from agent.clients import GeminiClient
import os


class MemoryManager:
    def __init__(self):
        self.storage = MemoryStorage()
        self.llm_client = GeminiClient()

    @staticmethod
    def _is_memory_disabled() -> bool:
        val = os.getenv("JAMIE_DISABLE_MEMORY", "").strip().lower()
        return val in ("1", "true", "yes", "on")

    def get_user_profile(self, user_id: str) -> UserProfile:
        profile = self.storage.get_user_profile(user_id)
        if not profile:
            profile = self.storage.create_or_update_profile(user_id)
        return profile

    def update_preferences(self, user_id: str, preferences: UserPreferences) -> bool:
        return self.storage.update_preferences(user_id, preferences)

    def extract_preferences_from_conversation(
        self, user_id: str, messages: List[ConversationMessage]
    ) -> Optional[UserPreferences]:
        if self._is_memory_disabled():
            return None
        if not messages:
            return None

        conversation_text = "\n".join([
            f"{'User' if msg.role.value == 'user' else 'Assistant'}: {msg.content}"
            for msg in messages[-10:]
        ])

        system_prompt = """Analyze the conversation and extract user preferences. 
        Look for mentions of:
        - Dietary restrictions (vegetarian, vegan, gluten-free, allergies, etc.)
        - Cuisine preferences (Italian, Asian, Mediterranean, etc.)
        - Price range preferences ($, $$, $$$, $$$$)
        - Location/address
        - Preferred serving sizes
        - Preferred difficulty levels (easy, medium, hard)
        
        Return a JSON object with these fields (null or empty array if not mentioned):
        {
            "dietary_restrictions": ["vegetarian", "gluten-free", ...],
            "cuisine_preferences": ["Italian", "Asian", ...],
            "price_range": "$" or "$$" or "$$$" or "$$$$" or null,
            "location": "city, state" or null,
            "default_servings": number or null,
            "preferred_difficulty": "easy" or "medium" or "hard" or null
        }
        
        Only extract preferences that are explicitly mentioned or clearly implied. 
        Do not infer preferences that aren't stated."""

        try:
            response = self.llm_client.generate_response(conversation_text, system_prompt)
            import json
            import re
            
            response_text = response.strip()
            
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)
            
            data = json.loads(response_text)
            
            preferences = UserPreferences(**data)
            
            if not any([
                preferences.dietary_restrictions,
                preferences.cuisine_preferences,
                preferences.price_range,
                preferences.location,
                preferences.default_servings,
                preferences.preferred_difficulty
            ]):
                return None
            
            current_profile = self.get_user_profile(user_id)
            merged_preferences = self._merge_preferences(current_profile.preferences, preferences)
            
            if merged_preferences != current_profile.preferences:
                self.update_preferences(user_id, merged_preferences)
                return merged_preferences
            
            return None
        except Exception as e:
            print(f"Error extracting preferences: {e}")
            return None

    def _merge_preferences(self, existing: UserPreferences, new: UserPreferences) -> UserPreferences:
        dietary_restrictions = list(set(existing.dietary_restrictions + new.dietary_restrictions))
        cuisine_preferences = list(set(existing.cuisine_preferences + new.cuisine_preferences))
        
        return UserPreferences(
            dietary_restrictions=dietary_restrictions,
            cuisine_preferences=cuisine_preferences,
            price_range=new.price_range or existing.price_range,
            location=new.location or existing.location,
            default_servings=new.default_servings or existing.default_servings,
            preferred_difficulty=new.preferred_difficulty or existing.preferred_difficulty
        )

    def create_session_summary(
        self,
        user_id: str,
        session_id: str,
        messages: List[ConversationMessage],
        intents: List[IntentType],
        tools_used: List[str]
    ) -> SessionSummary:
        if self._is_memory_disabled():
            # Minimal placeholder summary; do not call LLM or persist
            return SessionSummary(
                session_id=session_id,
                user_id=user_id,
                timestamp=datetime.utcnow().isoformat() + "Z",
                summary=f"Session with {len(messages)} messages",
                key_entities={"recipes": [], "restaurants": []},
                intents=[intent.value for intent in intents],
                tools_used=tools_used
            )
        conversation_text = "\n".join([
            f"{'User' if msg.role.value == 'user' else 'Assistant'}: {msg.content}"
            for msg in messages
        ])

        system_prompt = """Create a concise summary of this conversation session. 
        Include:
        1. Main topics discussed
        2. Key decisions or selections made
        3. Important recipes or restaurants mentioned
        
        Keep the summary to 2-3 sentences. Focus on what would be useful to remember for future conversations."""

        try:
            summary_text = self.llm_client.generate_response(conversation_text, system_prompt)
        except Exception as e:
            print(f"Error generating session summary: {e}")
            summary_text = f"Session with {len(messages)} messages"

        key_entities = {
            "recipes": [],
            "restaurants": []
        }

        for msg in messages:
            if "recipe" in msg.content.lower():
                key_entities["recipes"].append(msg.content[:100])
            if "restaurant" in msg.content.lower():
                key_entities["restaurants"].append(msg.content[:100])

        summary = SessionSummary(
            session_id=session_id,
            user_id=user_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            summary=summary_text.strip(),
            key_entities=key_entities,
            intents=[intent.value for intent in intents],
            tools_used=tools_used
        )

        self.storage.save_session_summary(summary)
        return summary

    def get_recent_session_summaries(self, user_id: str, limit: int = 5) -> List[SessionSummary]:
        if self._is_memory_disabled():
            return []
        return self.storage.get_session_summaries(user_id, limit)

    def get_user_preferences_context(self, user_id: str) -> str:
        if self._is_memory_disabled():
            return ""
        profile = self.get_user_profile(user_id)
        prefs = profile.preferences
        
        context_parts = []
        
        if prefs.dietary_restrictions:
            context_parts.append(f"Dietary restrictions: {', '.join(prefs.dietary_restrictions)}")
        
        if prefs.cuisine_preferences:
            context_parts.append(f"Preferred cuisines: {', '.join(prefs.cuisine_preferences)}")
        
        if prefs.price_range:
            context_parts.append(f"Price range preference: {prefs.price_range}")
        
        if prefs.location:
            context_parts.append(f"Location: {prefs.location}")
        
        if prefs.default_servings:
            context_parts.append(f"Default servings: {prefs.default_servings}")
        
        if prefs.preferred_difficulty:
            context_parts.append(f"Preferred difficulty: {prefs.preferred_difficulty}")
        
        if context_parts:
            return "User preferences:\n" + "\n".join(context_parts)
        
        return ""
