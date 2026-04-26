import json
from typing import Dict

import requests


class LLMClient:
    def __init__(self, api_key: str, api_base: str, model_name: str):
        self.api_key = api_key
        self.api_base = api_base
        self.model_name = model_name

    def generate(self, system_prompt: str, user_content: str, timeout: int = 180) -> str:
        if not self.api_key:
            raise RuntimeError("服务端未配置 LLM_API_KEY")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload: Dict[str, object] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 5000,
            "temperature": 0.1,
            "stream": False,
        }
        response = requests.post(
            self.api_base,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def stream(self, system_prompt: str, user_content: str, timeout: int = 180):
        if not self.api_key:
            raise RuntimeError("服务端未配置 LLM_API_KEY")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 5000,
            "temperature": 0.1,
            "stream": True,
        }
        response = requests.post(
            self.api_base,
            headers=headers,
            json=payload,
            timeout=timeout,
            stream=True,
        )
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8", errors="ignore")
            if not decoded.startswith("data: "):
                continue
            payload_str = decoded[6:]
            if payload_str.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(payload_str)
            except json.JSONDecodeError:
                continue
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            token = delta.get("content", "")
            if token:
                yield token
