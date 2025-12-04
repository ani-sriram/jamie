import json
import os
from typing import Optional
from datetime import datetime
from google.cloud import storage
from config import Config
from agent.schemas import UserProfile, UserPreferences, SessionSummary


class MemoryStorage:
    def __init__(self):
        self.client = storage.Client()
        self.bucket_name = Config.BASE_BUCKET

    def _get_profile_path(self, user_id: str) -> str:
        return f"users/{user_id}/profile.json"

    def _get_session_summary_path(self, user_id: str, session_id: str) -> str:
        return f"users/{user_id}/session_summaries/{session_id}.json"

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        try:
            bucket = self.client.bucket(self.bucket_name)
            file_path = self._get_profile_path(user_id)
            blob = bucket.blob(file_path)

            if not blob.exists():
                return None

            content = blob.download_as_text()
            data = json.loads(content)
            return UserProfile(**data)
        except Exception as e:
            print(f"Error retrieving user profile from GCS: {e}")
            return None

    def save_user_profile(self, profile: UserProfile) -> bool:
        try:
            bucket = self.client.bucket(self.bucket_name)
            file_path = self._get_profile_path(profile.user_id)
            blob = bucket.blob(file_path)

            profile.updated_at = datetime.utcnow().isoformat() + "Z"
            content = json.dumps(profile.model_dump(), indent=2)
            blob.upload_from_string(content)

            return True
        except Exception as e:
            print(f"Error saving user profile to GCS: {e}")
            return False

    def create_or_update_profile(self, user_id: str, preferences: Optional[UserPreferences] = None) -> UserProfile:
        existing = self.get_user_profile(user_id)
        
        if existing:
            if preferences:
                existing.preferences = preferences
            return existing
        
        now = datetime.utcnow().isoformat() + "Z"
        profile = UserProfile(
            user_id=user_id,
            preferences=preferences or UserPreferences(),
            created_at=now,
            updated_at=now
        )
        self.save_user_profile(profile)
        return profile

    def update_preferences(self, user_id: str, preferences: UserPreferences) -> bool:
        profile = self.get_user_profile(user_id)
        if not profile:
            profile = self.create_or_update_profile(user_id, preferences)
        else:
            profile.preferences = preferences
            self.save_user_profile(profile)
        return True

    def save_session_summary(self, summary: SessionSummary) -> bool:
        try:
            bucket = self.client.bucket(self.bucket_name)
            file_path = self._get_session_summary_path(summary.user_id, summary.session_id)
            blob = bucket.blob(file_path)

            content = json.dumps(summary.model_dump(), indent=2)
            blob.upload_from_string(content)

            return True
        except Exception as e:
            print(f"Error saving session summary to GCS: {e}")
            return False

    def get_session_summaries(self, user_id: str, limit: int = 10) -> list[SessionSummary]:
        try:
            bucket = self.client.bucket(self.bucket_name)
            prefix = f"users/{user_id}/session_summaries/"

            blobs = list(bucket.list_blobs(prefix=prefix))
            summaries = []

            for blob in blobs[:limit]:
                if blob.name.endswith('.json'):
                    content = blob.download_as_text()
                    data = json.loads(content)
                    summaries.append(SessionSummary(**data))

            summaries.sort(key=lambda x: x.timestamp, reverse=True)
            return summaries
        except Exception as e:
            print(f"Error retrieving session summaries from GCS: {e}")
            return []

    def delete_user_profile(self, user_id: str) -> bool:
        try:
            bucket = self.client.bucket(self.bucket_name)
            file_path = self._get_profile_path(user_id)
            blob = bucket.blob(file_path)

            if blob.exists():
                blob.delete()
                return True
            return False
        except Exception as e:
            print(f"Error deleting user profile from GCS: {e}")
            return False
