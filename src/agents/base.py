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
        self.client: Optional[OpenAI] = None
        
        # Initialize OpenAI client if not in mock mode and API key exists
        if not settings.mock_mode and settings.openai_api_key:
            try:
                self.client = OpenAI(api_key=settings.openai_api_key)
                logger.info(f"[{self.name}] OpenAI client initialized successfully.")
            except Exception as e:
                logger.warning(f"[{self.name}] Failed to initialize OpenAI client: {e}. Falling back to Simulation Mode.")
        else:
            logger.info(f"[{self.name}] Running in Simulation Mode.")

    def _call_llm(
        self, 
        prompt: str, 
        response_model: Type[T]
    ) -> T:
        """Calls the OpenAI client with structured outputs, or raises ValueError if not available."""
        if not self.client:
            raise ValueError("LLM client not initialized. Must run in Mock/Simulation Mode.")
            
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
        if not self.client:
            raise ValueError("LLM client not initialized. Must run in Mock/Simulation Mode.")
            
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
