import os
import shutil
import toml
from dotenv import load_dotenv
from app.paths import get_app_dir, get_user_data_dir

def load_config():
    # 1. Load .env from project root (or _MEIPASS)
    load_dotenv(get_app_dir() / ".env")
    
    # 2. Setup user config
    user_data_dir = get_user_data_dir()
    user_data_dir.mkdir(parents=True, exist_ok=True)
    
    config_path = user_data_dir / "config.toml"
    example_config_path = get_app_dir() / "config.example.toml"
    
    if not config_path.exists():
        if example_config_path.exists():
            shutil.copy2(example_config_path, config_path)
    
    # 3. Load config.toml
    config = {}
    if config_path.exists():
        try:
            config = toml.load(config_path)
        except Exception as e:
            print(f"Error loading config: {e}")
            
    return config
