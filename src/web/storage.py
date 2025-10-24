import json
import os
from typing import List, Optional
from datetime import datetime
from google.cloud import storage
from config import Config
from agent.schemas import ConversationMessage, MessageRole


class GCPSessionStorage:
    def __init__(self):
        self.client = storage.Client()
        self.bucket_name = Config.BASE_BUCKET

    def _get_session_file_path(self, user_id: str, session_id: str) -> str:
        """Get the GCS path for a session file"""
        return f"sessions/{user_id}/{session_id}.jsonl"

    def save_message(self, message: ConversationMessage) -> bool:
        """Save a single message to the session file"""
        try:
            bucket = self.client.bucket(self.bucket_name)
            file_path = self._get_session_file_path(message.user_id, message.session_id)
            blob = bucket.blob(file_path)

            # Create simplified message format
            message_data = {
                "timestamp": message.timestamp,
                "role": message.role.value,
                "content": message.content,
            }
            message_line = f"{json.dumps(message_data)}\n"

            # Check if file exists
            if blob.exists():
                # Append to existing file
                existing_content = blob.download_as_text()
                blob.upload_from_string(existing_content + message_line)
            else:
                # Create new file
                blob.upload_from_string(message_line)

            return True
        except Exception as e:
            print(f"Error saving message to GCS: {e}")
            return False

    def get_session_messages(
        self, user_id: str, session_id: str
    ) -> List[ConversationMessage]:
        """Retrieve all messages for a session"""
        try:
            bucket = self.client.bucket(self.bucket_name)
            file_path = self._get_session_file_path(user_id, session_id)
            blob = bucket.blob(file_path)

            if not blob.exists():
                return []

            content = blob.download_as_text()
            messages = []

            for line in content.strip().split("\n"):
                if line.strip():
                    message_data = json.loads(line)
                    # Convert simplified format back to ConversationMessage
                    messages.append(
                        ConversationMessage(
                            session_id=session_id,
                            user_id=user_id,
                            role=MessageRole(message_data["role"]),
                            content=message_data["content"],
                            timestamp=message_data["timestamp"],
                        )
                    )

            return messages
        except Exception as e:
            print(f"Error retrieving session messages from GCS: {e}")
            return []

    def list_user_sessions(self, user_id: str) -> List[str]:
        """List all session IDs for the user"""
        try:
            bucket = self.client.bucket(self.bucket_name)
            prefix = f"sessions/{user_id}/"

            blobs = bucket.list_blobs(prefix=prefix)
            session_ids = []

            for blob in blobs:
                if blob.name.endswith(".jsonl"):
                    # Extract session ID from filename
                    filename = os.path.basename(blob.name)
                    session_id = filename.replace(".jsonl", "")
                    session_ids.append(session_id)

            return session_ids
        except Exception as e:
            print(f"Error listing user sessions from GCS: {e}")
            return []

    def delete_session(self, user_id: str, session_id: str) -> bool:
        """Delete a session file"""
        try:
            bucket = self.client.bucket(self.bucket_name)
            file_path = self._get_session_file_path(user_id, session_id)
            blob = bucket.blob(file_path)

            if blob.exists():
                blob.delete()
                return True
            return False
        except Exception as e:
            print(f"Error deleting session from GCS: {e}")
            return False

    def delete_all_user_sessions(self, user_id: str) -> bool:
        """Delete all session files for the user"""
        try:
            bucket = self.client.bucket(self.bucket_name)
            prefix = f"sessions/{user_id}/"

            blobs = bucket.list_blobs(prefix=prefix)
            deleted_count = 0

            for blob in blobs:
                if blob.name.endswith(".jsonl"):
                    blob.delete()
                    deleted_count += 1

            return deleted_count > 0
        except Exception as e:
            print(f"Error deleting all user sessions from GCS: {e}")
            return False
