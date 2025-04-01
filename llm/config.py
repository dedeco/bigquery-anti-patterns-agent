"""Configuration for LLM-based query analysis"""
import os

class LLMConfig:
    def __init__(self,
                 model_name="claude-3-sonnet",
                 api_key=None,
                 fallback_to_rule_based=True):
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.fallback_to_rule_based = fallback_to_rule_based 