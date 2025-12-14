"""
Configuration management utilities.

This module handles loading and accessing system configuration from YAML files.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Configuration manager for the system."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration YAML file. If None, uses default.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f) or {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key path.
        
        Supports nested keys using dot notation (e.g., "embedding.model_name").
        
        Args:
            key: Configuration key path
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_embedding_config(self) -> Dict[str, Any]:
        """Get embedding configuration."""
        return self._config.get("embedding", {})
    
    def get_vector_store_config(self) -> Dict[str, Any]:
        """Get vector store configuration."""
        return self._config.get("vector_store", {})
    
    def get_similarity_config(self) -> Dict[str, Any]:
        """Get similarity configuration."""
        return self._config.get("similarity", {})
    
    def get_retrieval_config(self) -> Dict[str, Any]:
        """Get retrieval configuration."""
        return self._config.get("retrieval", {})
    
    def get_paths_config(self) -> Dict[str, Any]:
        """Get paths configuration."""
        return self._config.get("paths", {})


# Global configuration instance
_config_instance: Optional[Config] = None


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Config instance
    """
    global _config_instance
    _config_instance = Config(config_path)
    return _config_instance


def get_config() -> Config:
    """
    Get the global configuration instance.
    
    Returns:
        Config instance
        
    Raises:
        RuntimeError: If configuration not loaded
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


