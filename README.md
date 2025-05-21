# Telegram RPG Bot

A Telegram bot that implements a basic RPG system with combat, inventory, and character progression.

## Features

- Character creation and progression
- Turn-based combat system
- Inventory management
- Item system with different rarities
- Monster encounters
- Experience and leveling system

## Prerequisites

- Python 3.8 or higher
- PostgreSQL database
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd telegram-rpg-bot
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with the following content:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://username:password@localhost:5432/database_name
```

5. Create the PostgreSQL database:
```sql
CREATE DATABASE database_name;
```

## Running the Bot

1. Start the bot:
```bash
python main.py
```

2. Open Telegram and start a chat with your bot
3. Use the `/start` command to begin

## Available Commands

- `/start` - Start the bot and create a character
- `/stats` - View your character's stats
- `/combat` - Start a battle
- `/inventory` - View your inventory

## Game Mechanics

### Character Classes

- **Warrior**: High health and strength
- **Mage**: High mana and magical damage
- **Rogue**: High speed and critical hit chance

### Combat System

- Turn-based combat
- Basic actions: Attack, Skill, Item, Flee
- Experience and gold rewards
- Item drops from monsters

### Item System

- Different item types: Weapons, Armor, Consumables
- Rarity levels: Common, Uncommon, Rare, Mythical, Legendary, Immortal
- Equipment slots: Weapon, Armor, Accessory

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 