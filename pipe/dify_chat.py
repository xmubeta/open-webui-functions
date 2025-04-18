"""
title: Dify chat bot
author: Kohei Yamashita
author_url: https://github.com/KoheiYamashita
funding_url: https://github.com/KoheiYamashita
repo_url:https://github.com/KoheiYamashita/open-webui-functions
version: 0.1
"""

import json
import re
from pydantic import BaseModel, Field
import requests


class Pipe:
    class Valves(BaseModel):
        CHAT_BOT_ID: str = Field(
            default="1",
            description="dify chat bot id",
        )
        CHAT_BOT_NAME: str = Field(
            default="Dify Chat Bot",
            description="dify chat bot name",
        )
        BASE_URL: str = Field(
            default="https://api.dify.ai/v1",
            description="dify api url",
        )
        API_KEY: str = Field(
            default="",
            description="dify api key",
        )
        VERIFY_SSL: bool = Field(
            default=True,
            description="Verify SSL certificates.",
        )

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self):
        return [
            {"id": self.valves.CHAT_BOT_ID, "name": self.valves.CHAT_BOT_NAME},
        ]

    def pipe(self, body: dict, __user__: dict):
        api_key = self.valves.API_KEY

        # Get the latest message
        messages = body.get("messages", [])
        if not messages:
            return "Error: No messages provided"

        user_message = messages[-1].get("content", "")

        # Extract conversation ID from previous assistant messages
        conversation_id = None
        if len(messages) > 1:
            # Check previous messages in reverse order, excluding the latest message
            for message in reversed(messages[:-1]):
                if message.get("role") == "assistant":
                    content = message.get("content", "")
                    # Search for [CONVID:xxx] pattern
                    convid_match = re.search(r"\[CONVID:([^\]]+)\]", content)
                    if convid_match:
                        conversation_id = convid_match.group(1)
                        break

        # Set request headers
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Build request data
        data = {
            "inputs": {},
            "query": user_message,
            "response_mode": "streaming",
            "user": __user__.get("id", "anonymous"),
        }

        if conversation_id:
            data["conversation_id"] = conversation_id

        # Send request
        response = requests.post(
            f"{self.valves.BASE_URL}/chat-messages",
            headers=headers,
            json=data,
            stream=True,
            verify=self.valves.VERIFY_SSL,
        )

        if response.status_code == 200:
            # Variable for tracking conversation_id
            extracted_conversation_id = None
            for line in response.iter_lines():
                if line:
                    try:
                        # Remove 'data: ' prefix and parse JSON
                        line_text = line.decode("utf-8")
                        if line_text.startswith("data: "):
                            json_data = json.loads(line_text.replace("data: ", ""))

                            # Extract conversation_id
                            if (
                                "conversation_id" in json_data
                                and not extracted_conversation_id
                            ):
                                extracted_conversation_id = json_data.get(
                                    "conversation_id"
                                )

                            # Process based on event type
                            event_type = json_data.get("event")

                            if event_type == "message":
                                # Process text chunks from LLM and return immediately
                                answer = json_data.get("answer", "")
                                if answer:
                                    yield answer

                            elif event_type == "workflow_finished":
                                # Return conversation_id for future reference when finished
                                yield f"\n\n[CONVID:{extracted_conversation_id}]"

                    except json.JSONDecodeError as e:
                        print(f"Failed to parse JSON: {line} - Error: {e}")
        else:
            error_message = (
                f"Workflow request failed with status code: {response.status_code}"
            )
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_message += f" - {error_data['error']}"
            except:
                pass
            yield error_message
