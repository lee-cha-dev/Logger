import os
import yaml

class EnhancedLoggerConfig:
    """Enhanced configuration system with environment variable support"""

    @staticmethod
    def get_config(config_path=None):
        """Load configuration from file and/or environment variables"""
        # Default configuration
        config = {
            'level': 'INFO',
            'max_bytes': 10 * 1024 * 1024,  # 10MB
            'backup_count': 5,
            'also_print': True,
            'format': "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            'date_format': "%Y-%m-%d %H:%M:%S",
            'encoding': "utf-8",
            'buffer_size': 0,  # 0 means no buffering
            'flush_interval': 5.0,
        }

        # Load from YAML if provided
        if config_path:
            try:
                with open(config_path, 'r') as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config:
                        config.update(yaml_config)
            except (FileNotFoundError, yaml.YAMLError) as e:
                print(f"Warning: Could not load config file: {e}")

        # Override with environment variables
        env_prefix = "LOGGER_"
        for key in config:
            env_key = f"{env_prefix}{key.upper()}"
            if env_key in os.environ:
                # Type conversion based on default type
                default_value = config[key]
                if isinstance(default_value, bool):
                    config[key] = os.environ[env_key].lower() in ('true', '1', 'yes')
                elif isinstance(default_value, int):
                    config[key] = int(os.environ[env_key])
                elif isinstance(default_value, float):
                    config[key] = float(os.environ[env_key])
                else:
                    config[key] = os.environ[env_key]

        return config