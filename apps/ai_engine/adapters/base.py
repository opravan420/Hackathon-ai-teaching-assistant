class BaseLLMAdapter:
    """Abstract interface for LLM provider adapters."""
    
    def generate(self, prompt: str, system_prompt: str = None, options: dict = None) -> str:
        """
        Generate text based on the provided prompts and options.
        
        Args:
            prompt: The main user prompt.
            system_prompt: Optional instructions configuring model behavior.
            options: Optional adapter-specific configuration parameters.
            
        Returns:
            The generated response string.
        """
        raise NotImplementedError("Subclasses must implement the generate method.")
