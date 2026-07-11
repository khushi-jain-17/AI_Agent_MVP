import os
from typing import Type, TypeVar, Optional, Any
from pydantic import BaseModel
from openai import OpenAI
from src.config import settings
from src.utils.logger import logger

T = TypeVar("T", bound=BaseModel)

class BaseAgent:
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        
        # Verify API Key is present for official run
        if not settings.openai_api_key:
            raise ValueError(
                f"[{self.name}] Configuration Error: Missing 'OPENAI_API_KEY'. "
                "Please configure a valid API key in your .env file or environment variables to run in live mode."
            )
            
        try:
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )
            logger.info(f"[{self.name}] OpenAI-compatible client initialized successfully.")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to initialize OpenAI client: {e}")
            raise e

    def _call_llm(
        self, 
        prompt: str, 
        response_model: Type[T]
    ) -> T:
        """Calls the OpenAI client with structured outputs."""
        logger.info(f"[{self.name}] Dispatching structured LLM call...")
        try:
            completion = self.client.beta.chat.completions.parse(
                model=settings.default_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format=response_model
            )
            parsed_response = completion.choices[0].message.parsed
            if parsed_response is None:
                raise ValueError("LLM response could not be parsed to schema.")
            return parsed_response
        except Exception as e:
            logger.error(f"[{self.name}] Error during LLM structural output call: {e}")
            raise e

    def _call_llm_text(self, prompt: str) -> str:
        """Calls the OpenAI client returning raw text response."""
        logger.info(f"[{self.name}] Dispatching text LLM call...")
        try:
            completion = self.client.chat.completions.create(
                model=settings.default_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            return completion.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"[{self.name}] Error during LLM text call: {e}")
            raise e
