import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables")

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("No DATABASE_URL found in environment variables")

# Game Configuration
MAX_LEVEL = 100
BASE_HEALTH = 100
BASE_MANA = 50
BASE_STRENGTH = 10
BASE_DEFENSE = 5

# Experience Configuration
BASE_XP_REQUIREMENT = 100
XP_SCALING_FACTOR = 1.5

# Combat Configuration
TURN_TIMEOUT = 60  # seconds
COMBAT_REWARD_MULTIPLIER = 1.0

# Item Rarity Multipliers
RARITY_MULTIPLIERS = {
    'common': 1.0,
    'uncommon': 1.5,
    'rare': 2.0,
    'mythical': 3.0,
    'legendary': 4.0,
    'immortal': 5.0
} 