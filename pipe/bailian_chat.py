"""
title: Alibaba Cloud Bailian Chat Bot
author: Beta Zhou
author_url: https://github.com/BetaZhou
funding_url: https://github.com/BetaZhou
repo_url: https://github.com/BetaZhou/open-webui-functions
version: 0.1
reference_author: Kohei Yamashita
reference_url: https://github.com/KoheiYamashita/open-webui-functions
"""

import json
import re
from pydantic import BaseModel, Field
import requests


class Pipe:
    class Valves(BaseModel):
        CHAT_BOT_ID: str = Field(
            default="1",
            description="Bailian chat bot id",
        )
        CHAT_BOT_NAME: str = Field(
            default="Bailian Chat Bot",
            description="Bailian chat bot name",
        )
        BASE_URL: str = Field(
            default="https://dashscope.aliyuncs.com",
            description="Bailian API base URL",
        )
        APP_ID: str = Field(
            default="",
            description="Bailian application ID",
        )
        API_KEY: str = Field(
            default="",
            description="Bailian API key",
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

    async def pipe(self, body: dict, __user__: dict):
        api_key = self.valves.API_KEY
        app_id = self.valves.APP_ID

        if not api_key or not app_id:
            yield "Error: API_KEY and APP_ID are required"
            return

        # Get the latest message
        messages = body.get("messages", [])
        if not messages:
            yield "Error: No messages provided"
            return

        user_message = messages[-1].get("content", "")

        # Extract session ID from previous assistant messages
        session_id = None
        if len(messages) > 1:
            # Check previous messages in reverse order, excluding the latest message
            for message in reversed(messages[:-1]):
                if message.get("role") == "assistant":
                    content = message.get("content", "")
                    # Search for [SESSIONID:xxx] pattern
                    session_match = re.search(r"\[SESSIONID:([^\]]+)\]", content)
                    if session_match:
                        session_id = session_match.group(1)
                        break

        # Set request headers for Bailian API
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Build request data for Bailian API
        data = {
            "input": {
                "prompt": user_message
            },
            "parameters": {},
            "debug": {}
        }

        if session_id:
            data["input"]["session_id"] = session_id

        # Send request to Bailian API
        response = requests.post(
            f"{self.valves.BASE_URL}/api/v1/apps/{app_id}/completion",
            headers=headers,
            json=data,
            stream=True,
            verify=self.valves.VERIFY_SSL,
        )

        if response.status_code == 200:
            # Variable for tracking session_id
            extracted_session_id = None
            
            for line in response.iter_lines():
                if line:
                    print(line.decode("utf-8"))
                    try:
                        # Parse JSON directly from the line
                        line_text = line.decode("utf-8")
                        json_data = json.loads(line_text)

                        # Extract session_id from output
                        if "output" in json_data and "session_id" in json_data["output"]:
                            if not extracted_session_id:
                                extracted_session_id = json_data["output"]["session_id"]

                        # Process the response
                        if "output" in json_data:
                            output = json_data["output"]
                            
                            # Get the text content
                            yield output.get("text", "")
                

                            # Check if this is the final response
                            #finish_reason = output.get("finish_reason")
                            #if finish_reason == "stop" and extracted_session_id:
                            #    yield f"\n\n[SESSIONID:{extracted_session_id}]"

                    except json.JSONDecodeError as e:
                        print(f"Failed to parse JSON: {line} - Error: {e}")
        else:
            error_message = (
                f"Bailian API request failed with status code: {response.status_code}"
            )
            try:
                error_data = response.json()
                if "message" in error_data:
                    error_message += f" - {error_data['message']}"
                elif "error" in error_data:
                    error_message += f" - {error_data['error']}"
            except:
                pass
            yield error_message
