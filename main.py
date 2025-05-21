import logging
import json
import random
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from config.config import BOT_TOKEN
from models.base import Base, engine, get_db
from models.character import Character, CharacterClass
from models.inventory import Item, Inventory, InventoryItem, Equipment, ItemType, ItemRarity
from models.monsters import Monster, DEFAULT_MONSTERS, MonsterType
from utils.error_handling import (
    handle_database_error,
    handle_game_error,
    log_command,
    log_state_transition,
    log_combat_action,
    log_inventory_action,
    log_error,
    CharacterError,
    InventoryError,
    CombatError,
    DatabaseError
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='rpg_bot.log'
)
logger = logging.getLogger(__name__)

# Cache for character data
character_cache: Dict[int, Dict[str, Any]] = {}
CACHE_TIMEOUT = 300  # 5 minutes

@contextmanager
def get_db_session():
    """Context manager for database sessions."""
    session = next(get_db())
    try:
        yield session
    finally:
        session.close()

def get_character_by_user_id(user_id: int) -> Optional[Character]:
    """Get character by user ID with caching."""
    current_time = datetime.now()
    
    # Check cache
    if user_id in character_cache:
        cache_data = character_cache[user_id]
        if current_time - cache_data['timestamp'] < timedelta(seconds=CACHE_TIMEOUT):
            return cache_data['character']
    
    # Fetch from database
    with get_db_session() as db:
        character = db.query(Character).filter(Character.user_id == user_id).first()
        if character:
            character_cache[user_id] = {
                'character': character,
                'timestamp': current_time
            }
        return character

def clear_character_cache(user_id: int):
    """Clear character cache for a user."""
    if user_id in character_cache:
        del character_cache[user_id]

# Conversation states
(
    CHOOSING_CLASS,
    ENTERING_NAME,
    IN_COMBAT,
    CHOOSING_SKILL,
    CHOOSING_ITEM,
    INVENTORY_MANAGEMENT,
    EQUIPPING_ITEM,
    USING_ITEM,
) = range(8)

# Combat states
COMBAT_ACTIONS = {
    'attack': 'Attack',
    'skill': 'Skill',
    'item': 'Item',
    'flee': 'Flee'
}

@log_command
@handle_game_error
@handle_database_error
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask for character class."""
    user_id = update.effective_user.id
    logger.info(f"Start command received from user {user_id}")
    
    # Check if user already has a character
    character = get_character_by_user_id(user_id)
    if character:
        logger.info(f"User {user_id} already has character {character.name}")
        await update.message.reply_text(
            f"You already have a character named {character.name}!\n"
            f"Use /stats to view your stats\n"
            f"Use /combat to start a battle\n"
            f"Use /inventory to view your inventory"
        )
        return ConversationHandler.END

    keyboard = [
        [
            InlineKeyboardButton("Warrior", callback_data="warrior"),
            InlineKeyboardButton("Mage", callback_data="mage"),
            InlineKeyboardButton("Rogue", callback_data="rogue"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Welcome to the RPG Bot! Choose your character class:",
        reply_markup=reply_markup
    )
    return CHOOSING_CLASS

@log_state_transition
@handle_game_error
async def class_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle character class selection."""
    query = update.callback_query
    await query.answer()
    
    context.user_data['character_class'] = query.data
    logger.info(f"User {update.effective_user.id} selected class {query.data}")
    
    await query.edit_message_text(
        f"You selected {query.data.capitalize()}! Now, please enter your character name:"
    )
    return ENTERING_NAME

@log_state_transition
@handle_game_error
async def name_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle character name entry."""
    name = update.message.text
    if len(name) < 3 or len(name) > 20:
        logger.warning(f"Invalid name length from user {update.effective_user.id}: {len(name)}")
        await update.message.reply_text(
            "Name must be between 3 and 20 characters. Please try again:"
        )
        return ENTERING_NAME
    
    context.user_data['character_name'] = name
    logger.info(f"User {update.effective_user.id} entered name: {name}")
    await create_character(update, context)
    return ConversationHandler.END

@log_command
@handle_database_error
async def create_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new character in the database."""
    with get_db_session() as db:
        try:
            # Create character
            character = Character(
                user_id=update.effective_user.id,
                name=context.user_data['character_name'],
                character_class=CharacterClass(context.user_data['character_class'])
            )
            db.add(character)
            db.flush()

            # Create inventory
            inventory = Inventory(character_id=character.id)
            db.add(inventory)

            # Add starting items based on class
            starting_items = get_starting_items(character.character_class)
            for item_data in starting_items:
                item = Item(**item_data)
                db.add(item)
                db.flush()
                
                inventory_item = InventoryItem(
                    inventory_id=inventory.id,
                    item_id=item.id,
                    quantity=1
                )
                db.add(inventory_item)

            db.commit()
            clear_character_cache(update.effective_user.id)
            logger.info(f"Created character {character.name} for user {update.effective_user.id}")
            
            await update.message.reply_text(
                f"Character created successfully!\n"
                f"Name: {character.name}\n"
                f"Class: {character.character_class.value.capitalize()}\n\n"
                f"Use /stats to view your character stats\n"
                f"Use /combat to start a battle\n"
                f"Use /inventory to view your inventory"
            )
        except SQLAlchemyError as e:
            db.rollback()
            log_error(e, update, context)
            raise DatabaseError("Failed to create character")
        except Exception as e:
            db.rollback()
            log_error(e, update, context)
            raise CharacterError("Failed to create character")

def get_starting_items(character_class: CharacterClass) -> list:
    """Get starting items based on character class."""
    if character_class == CharacterClass.WARRIOR:
        return [
            {
                "name": "Basic Sword",
                "description": "A simple iron sword",
                "item_type": ItemType.WEAPON,
                "damage": 5,
                "defense": 0
            },
            {
                "name": "Leather Armor",
                "description": "Basic leather protection",
                "item_type": ItemType.ARMOR,
                "damage": 0,
                "defense": 3
            }
        ]
    elif character_class == CharacterClass.MAGE:
        return [
            {
                "name": "Wooden Staff",
                "description": "A simple magical staff",
                "item_type": ItemType.WEAPON,
                "damage": 3,
                "mana_bonus": 5
            },
            {
                "name": "Apprentice Robes",
                "description": "Basic magical robes",
                "item_type": ItemType.ARMOR,
                "defense": 2,
                "mana_bonus": 3
            }
        ]
    else:  # Rogue
        return [
            {
                "name": "Dagger",
                "description": "A sharp dagger",
                "item_type": ItemType.WEAPON,
                "damage": 4
            },
            {
                "name": "Leather Vest",
                "description": "Light and flexible armor",
                "item_type": ItemType.ARMOR,
                "defense": 2
            }
        ]

@log_command
@handle_database_error
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display character stats."""
    character = get_character_by_user_id(update.effective_user.id)
    
    if not character:
        logger.warning(f"Stats command from user {update.effective_user.id} with no character")
        await update.message.reply_text(
            "You don't have a character yet! Use /start to create one."
        )
        return

    stats = character.get_stats()
    logger.info(f"Displaying stats for character {character.name}")
    
    stats_text = (
        f"Character Stats:\n"
        f"Name: {stats['name']}\n"
        f"Class: {stats['class'].capitalize()}\n"
        f"Level: {stats['level']}\n"
        f"Health: {stats['health']}\n"
        f"Mana: {stats['mana']}\n"
        f"Strength: {stats['strength']}\n"
        f"Defense: {stats['defense']}\n"
        f"Experience: {stats['experience']}"
    )
    
    await update.message.reply_text(stats_text)

@log_command
@handle_database_error
async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display inventory and show management options."""
    character = get_character_by_user_id(update.effective_user.id)
    
    if not character:
        logger.warning(f"Inventory command from user {update.effective_user.id} with no character")
        await update.message.reply_text(
            "You don't have a character yet! Use /start to create one."
        )
        return ConversationHandler.END

    if not character.inventory or not character.inventory.items:
        logger.info(f"Empty inventory for character {character.name}")
        await update.message.reply_text("Your inventory is empty!")
        return ConversationHandler.END

    # Create keyboard with inventory management options
    keyboard = [
        [
            InlineKeyboardButton("Equip Item", callback_data="equip"),
            InlineKeyboardButton("Use Item", callback_data="use"),
        ],
        [
            InlineKeyboardButton("Drop Item", callback_data="drop"),
            InlineKeyboardButton("View Equipment", callback_data="equipment"),
        ],
        [InlineKeyboardButton("Close", callback_data="close_inventory")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Display inventory contents
    inventory_text = "Your Inventory:\n\n"
    for idx, item in enumerate(character.inventory.items, 1):
        inventory_text += (
            f"{idx}. {item.item.name} (x{item.quantity})\n"
            f"   Type: {item.item.item_type.value}\n"
            f"   Rarity: {item.item.rarity.value}\n"
            f"   Description: {item.item.description}\n\n"
        )

    logger.info(f"Displaying inventory for character {character.name}")
    await update.message.reply_text(inventory_text, reply_markup=reply_markup)
    return INVENTORY_MANAGEMENT

@log_inventory_action
@handle_database_error
async def handle_inventory_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle inventory management actions."""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    with get_db_session() as db:
        character = db.query(Character).get(update.effective_user.id)
    
    logger.info(f"Inventory action {action} from user {update.effective_user.id}")

    if action == "close_inventory":
        await query.edit_message_text("Inventory closed.")
        return ConversationHandler.END

    elif action == "equip":
        # Create keyboard with equippable items
        keyboard = []
        for idx, item in enumerate(character.inventory.items, 1):
            if item.item.item_type in [ItemType.WEAPON, ItemType.ARMOR]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{item.item.name} ({item.item.item_type.value})",
                        callback_data=f"equip_{item.id}"
                    )
                ])
        
        if not keyboard:
            await query.edit_message_text("You have no equippable items!")
            return ConversationHandler.END

        keyboard.append([InlineKeyboardButton("Back", callback_data="back_to_inventory")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Select an item to equip:",
            reply_markup=reply_markup
        )
        return EQUIPPING_ITEM

    elif action == "use":
        # Create keyboard with usable items
        keyboard = []
        for idx, item in enumerate(character.inventory.items, 1):
            if item.item.item_type == ItemType.CONSUMABLE:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{item.item.name} (x{item.quantity})",
                        callback_data=f"use_{item.id}"
                    )
                ])
        
        if not keyboard:
            await query.edit_message_text("You have no usable items!")
            return ConversationHandler.END

        keyboard.append([InlineKeyboardButton("Back", callback_data="back_to_inventory")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Select an item to use:",
            reply_markup=reply_markup
        )
        return USING_ITEM

    elif action == "drop":
        # Create keyboard with all items
        keyboard = []
        for idx, item in enumerate(character.inventory.items, 1):
            keyboard.append([
                InlineKeyboardButton(
                    f"{item.item.name} (x{item.quantity})",
                    callback_data=f"drop_{item.id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("Back", callback_data="back_to_inventory")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Select an item to drop:",
            reply_markup=reply_markup
        )
        return INVENTORY_MANAGEMENT

    elif action == "equipment":
        await show_equipment(update, context)
        return INVENTORY_MANAGEMENT

    elif action == "back_to_inventory":
        await inventory(update, context)
        return INVENTORY_MANAGEMENT

@log_inventory_action
@handle_database_error
async def handle_equip_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle equipping an item."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_inventory":
        await inventory(update, context)
        return INVENTORY_MANAGEMENT

    item_id = int(query.data.split("_")[1])
    with get_db_session() as db:
        character = db.query(Character).get(update.effective_user.id)
    
    try:
        # Find the inventory item
        inventory_item = next(
            (item for item in character.inventory.items if item.id == item_id),
            None
        )
        
        if not inventory_item:
            logger.warning(f"Item {item_id} not found for user {update.effective_user.id}")
            await query.edit_message_text("Item not found!")
            return ConversationHandler.END

        # Check if item is already equipped
        existing_equipment = db.query(Equipment).filter(
            Equipment.character_id == character.id,
            Equipment.item_id == inventory_item.item_id
        ).first()

        if existing_equipment:
            logger.info(f"Item {item_id} already equipped for user {update.effective_user.id}")
            await query.edit_message_text("This item is already equipped!")
            return ConversationHandler.END

        # Create new equipment entry
        equipment = Equipment(
            character_id=character.id,
            item_id=inventory_item.item_id,
            slot=inventory_item.item.item_type.value
        )
        db.add(equipment)
        db.commit()

        logger.info(f"User {update.effective_user.id} equipped item {inventory_item.item.name}")
        await query.edit_message_text(
            f"Equipped {inventory_item.item.name}!"
        )
        await inventory(update, context)
        return INVENTORY_MANAGEMENT

    except Exception as e:
        db.rollback()
        log_error(e, update, context)
        raise InventoryError("Failed to equip item")

@log_inventory_action
@handle_database_error
async def handle_use_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle using a consumable item."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_inventory":
        await inventory(update, context)
        return INVENTORY_MANAGEMENT

    item_id = int(query.data.split("_")[1])
    with get_db_session() as db:
        character = db.query(Character).get(update.effective_user.id)
    
    try:
        # Find the inventory item
        inventory_item = next(
            (item for item in character.inventory.items if item.id == item_id),
            None
        )
        
        if not inventory_item:
            logger.warning(f"Item {item_id} not found for user {update.effective_user.id}")
            await query.edit_message_text("Item not found!")
            return ConversationHandler.END

        if inventory_item.item.item_type != ItemType.CONSUMABLE:
            logger.warning(f"Non-consumable item {item_id} used by user {update.effective_user.id}")
            await query.edit_message_text("This item cannot be used!")
            return ConversationHandler.END

        # Apply item effects
        character.health = min(
            character.max_health,
            character.health + inventory_item.item.health_bonus
        )
        character.mana = min(
            character.max_mana,
            character.mana + inventory_item.item.mana_bonus
        )

        # Remove one item from inventory
        inventory_item.quantity -= 1
        if inventory_item.quantity <= 0:
            db.delete(inventory_item)

        db.commit()
        logger.info(f"User {update.effective_user.id} used item {inventory_item.item.name}")

        await query.edit_message_text(
            f"Used {inventory_item.item.name}!\n"
            f"Health: {character.health}/{character.max_health}\n"
            f"Mana: {character.mana}/{character.max_mana}"
        )
        await inventory(update, context)
        return INVENTORY_MANAGEMENT

    except Exception as e:
        db.rollback()
        log_error(e, update, context)
        raise InventoryError("Failed to use item")

@log_command
@handle_database_error
async def show_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display currently equipped items."""
    query = update.callback_query
    db = next(get_db())
    character = get_character_by_user_id(db, update.effective_user.id)
    
    logger.info(f"Showing equipment for character {character.name}")
    
    equipment_text = "Currently Equipped:\n\n"
    
    if not character.equipment:
        equipment_text += "No items equipped."
    else:
        for equip in character.equipment:
            equipment_text += (
                f"{equip.slot.capitalize()}: {equip.item.name}\n"
                f"Type: {equip.item.item_type.value}\n"
                f"Rarity: {equip.item.rarity.value}\n"
                f"Description: {equip.item.description}\n\n"
            )

    keyboard = [[InlineKeyboardButton("Back", callback_data="back_to_inventory")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        equipment_text,
        reply_markup=reply_markup
    )

async def combat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start combat."""
    db = next(get_db())
    character = get_character_by_user_id(db, update.effective_user.id)
    
    if not character:
        await update.message.reply_text(
            "You don't have a character yet! Use /start to create one."
        )
        return ConversationHandler.END

    # Select a random monster based on character level
    monster = select_monster_for_level(character.level)
    context.user_data['current_monster'] = monster.get_stats()
    
    keyboard = [
        [
            InlineKeyboardButton("Attack", callback_data="attack"),
            InlineKeyboardButton("Skill", callback_data="skill"),
        ],
        [
            InlineKeyboardButton("Item", callback_data="item"),
            InlineKeyboardButton("Flee", callback_data="flee"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    combat_text = (
        f"Combat started!\n\n"
        f"Your stats:\n"
        f"Health: {character.health}/{character.max_health}\n"
        f"Mana: {character.mana}/{character.max_mana}\n\n"
        f"Monster: {monster.name}\n"
        f"Health: {monster.health}/{monster.max_health}\n\n"
        f"Choose your action:"
    )
    
    await update.message.reply_text(combat_text, reply_markup=reply_markup)
    return IN_COMBAT

def select_monster_for_level(character_level: int) -> Monster:
    """Select an appropriate monster based on character level."""
    db = next(get_db())
    
    # Get monsters within 2 levels of the character
    monsters = db.query(Monster).filter(
        Monster.level.between(character_level - 2, character_level + 2)
    ).all()
    
    if not monsters:
        # If no monsters found, create a default one
        monster_data = DEFAULT_MONSTERS[0].copy()
        monster_data['level'] = character_level
        monster = Monster(**monster_data)
        db.add(monster)
        db.commit()
        return monster
    
    return monsters[0]  # Return the first matching monster

async def handle_combat_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle combat actions."""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    if action not in COMBAT_ACTIONS:
        return IN_COMBAT
    
    db = next(get_db())
    character = get_character_by_user_id(db, update.effective_user.id)
    monster = context.user_data.get('current_monster')
    
    if not character or not monster:
        await query.edit_message_text("Combat has ended unexpectedly.")
        return ConversationHandler.END
    
    # Handle different combat actions
    if action == 'attack':
        return await handle_attack(update, context, character, monster)
    elif action == 'skill':
        return await handle_skill_selection(update, context, character)
    elif action == 'item':
        return await handle_item_selection(update, context, character)
    elif action == 'flee':
        return await handle_flee(update, context, character, monster)
    
    return IN_COMBAT

async def handle_attack(update: Update, context: ContextTypes.DEFAULT_TYPE, character: Character, monster: dict) -> int:
    """Handle attack action."""
    query = update.callback_query
    
    # Calculate damage
    base_damage = character.strength
    damage_variance = random.uniform(0.8, 1.2)
    final_damage = int(base_damage * damage_variance)
    
    # Apply damage to monster
    monster['health'] = max(0, monster['health'] - final_damage)
    
    # Check if monster is defeated
    if monster['health'] <= 0:
        await handle_combat_victory(update, context, character, monster)
        return ConversationHandler.END
    
    # Monster's turn
    monster_damage = calculate_monster_damage(monster)
    character.health = max(0, character.health - monster_damage)
    
    # Check if character is defeated
    if character.health <= 0:
        await handle_combat_defeat(update, context, character)
        return ConversationHandler.END
    
    # Update combat state
    context.user_data['current_monster'] = monster
    db = next(get_db())
    db.commit()
    
    # Show combat results
    combat_text = format_combat_text(character, monster, final_damage, monster_damage)
    keyboard = get_combat_keyboard()
    
    await query.edit_message_text(combat_text, reply_markup=keyboard)
    return IN_COMBAT

async def handle_skill_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, character: Character) -> int:
    """Handle skill selection."""
    query = update.callback_query
    
    # Get available skills based on character class
    skills = get_character_skills(character.character_class)
    
    keyboard = []
    for skill in skills:
        keyboard.append([InlineKeyboardButton(skill['name'], callback_data=f"skill_{skill['id']}")])
    keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Select a skill to use:\nMana: {character.mana}/{character.max_mana}",
        reply_markup=reply_markup
    )
    return CHOOSING_SKILL

async def handle_item_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, character: Character) -> int:
    """Handle item selection."""
    query = update.callback_query
    
    # Get consumable items from inventory
    consumables = get_consumable_items(character)
    
    if not consumables:
        await query.edit_message_text(
            "You have no consumable items!",
            reply_markup=get_combat_keyboard()
        )
        return IN_COMBAT
    
    keyboard = []
    for item in consumables:
        keyboard.append([InlineKeyboardButton(
            f"{item.name} (x{item.quantity})",
            callback_data=f"item_{item.id}"
        )])
    keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Select an item to use:",
        reply_markup=reply_markup
    )
    return CHOOSING_ITEM

async def handle_flee(update: Update, context: ContextTypes.DEFAULT_TYPE, character: Character, monster: dict) -> int:
    """Handle flee action."""
    query = update.callback_query
    
    # 50% chance to successfully flee
    if random.random() < 0.5:
        await query.edit_message_text("You successfully fled from combat!")
        return ConversationHandler.END
    
    # Failed to flee, monster gets a free hit
    monster_damage = calculate_monster_damage(monster)
    character.health = max(0, character.health - monster_damage)
    
    if character.health <= 0:
        await handle_combat_defeat(update, context, character)
        return ConversationHandler.END
    
    db = next(get_db())
    db.commit()
    
    combat_text = (
        f"Failed to flee! The monster attacks you for {monster_damage} damage!\n\n"
        f"Your health: {character.health}/{character.max_health}\n"
        f"Monster health: {monster['health']}/{monster['max_health']}"
    )
    
    await query.edit_message_text(combat_text, reply_markup=get_combat_keyboard())
    return IN_COMBAT

async def handle_combat_victory(update: Update, context: ContextTypes.DEFAULT_TYPE, character: Character, monster: dict):
    """Handle combat victory."""
    query = update.callback_query
    
    # Add experience and handle level up
    character.add_experience(monster['experience_reward'])
    
    # Add gold (implement gold system later)
    
    # Handle item drops
    drops = handle_item_drops(monster)
    
    db = next(get_db())
    db.commit()
    
    victory_text = (
        f"Victory! You defeated the {monster['name']}!\n"
        f"Experience gained: {monster['experience_reward']}\n"
    )
    
    if drops:
        victory_text += "\nItems dropped:\n"
        for item in drops:
            victory_text += f"- {item.name}\n"
    
    await query.edit_message_text(victory_text)

async def handle_combat_defeat(update: Update, context: ContextTypes.DEFAULT_TYPE, character: Character):
    """Handle combat defeat."""
    query = update.callback_query
    
    # Reset character health
    character.health = character.max_health
    character.mana = character.max_mana
    
    db = next(get_db())
    db.commit()
    
    await query.edit_message_text(
        "You have been defeated! Your health and mana have been restored."
    )

def calculate_monster_damage(monster: dict) -> int:
    """Calculate monster damage with variance."""
    base_damage = monster['damage']
    damage_variance = random.uniform(0.8, 1.2)
    return int(base_damage * damage_variance)

def format_combat_text(character: Character, monster: dict, player_damage: int, monster_damage: int) -> str:
    """Format combat text."""
    return (
        f"Combat Status:\n\n"
        f"Your stats:\n"
        f"Health: {character.health}/{character.max_health}\n"
        f"Mana: {character.mana}/{character.max_mana}\n\n"
        f"Monster: {monster['name']}\n"
        f"Health: {monster['health']}/{monster['max_health']}\n\n"
        f"You dealt {player_damage} damage!\n"
        f"The monster dealt {monster_damage} damage!"
    )

def get_combat_keyboard() -> InlineKeyboardMarkup:
    """Get combat action keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("Attack", callback_data="attack"),
            InlineKeyboardButton("Skill", callback_data="skill"),
        ],
        [
            InlineKeyboardButton("Item", callback_data="item"),
            InlineKeyboardButton("Flee", callback_data="flee"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_character_skills(character_class: CharacterClass) -> list:
    """Get available skills for character class."""
    if character_class == CharacterClass.WARRIOR:
        return [
            {
                'id': 'slash',
                'name': 'Slash',
                'damage_multiplier': 1.5,
                'mana_cost': 10
            },
            {
                'id': 'whirlwind',
                'name': 'Whirlwind',
                'damage_multiplier': 2.0,
                'mana_cost': 20
            }
        ]
    elif character_class == CharacterClass.MAGE:
        return [
            {
                'id': 'fireball',
                'name': 'Fireball',
                'damage_multiplier': 2.0,
                'mana_cost': 15
            },
            {
                'id': 'lightning',
                'name': 'Lightning',
                'damage_multiplier': 2.5,
                'mana_cost': 25
            }
        ]
    else:  # Rogue
        return [
            {
                'id': 'backstab',
                'name': 'Backstab',
                'damage_multiplier': 2.0,
                'mana_cost': 15
            },
            {
                'id': 'poison_strike',
                'name': 'Poison Strike',
                'damage_multiplier': 1.5,
                'mana_cost': 10
            }
        ]

def get_consumable_items(character: Character) -> list:
    """Get consumable items from inventory."""
    consumables = []
    if character.inventory:
        for item in character.inventory.items:
            if item.item.item_type == ItemType.CONSUMABLE:
                consumables.append(item)
    return consumables

def handle_item_drops(monster: dict) -> list:
    """Handle item drops from monster."""
    # TODO: Implement proper item drop system
    return []

def main() -> None:
    """Start the bot."""
    try:
        # Create database tables
        Base.metadata.create_all(engine)
        logger.info("Database tables created successfully")
        
        # Create the Application
        application = Application.builder().token(BOT_TOKEN).build()

        # Add conversation handler for character creation
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                CHOOSING_CLASS: [CallbackQueryHandler(class_selection)],
                ENTERING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_entry)],
            },
            fallbacks=[],
        )

        # Add inventory management conversation handler
        inventory_handler = ConversationHandler(
            entry_points=[CommandHandler("inventory", inventory)],
            states={
                INVENTORY_MANAGEMENT: [
                    CallbackQueryHandler(handle_inventory_action)
                ],
                EQUIPPING_ITEM: [
                    CallbackQueryHandler(handle_equip_item)
                ],
                USING_ITEM: [
                    CallbackQueryHandler(handle_use_item)
                ],
            },
            fallbacks=[],
        )

        # Add combat conversation handler
        combat_handler = ConversationHandler(
            entry_points=[CommandHandler("combat", combat)],
            states={
                IN_COMBAT: [CallbackQueryHandler(handle_combat_action)],
                CHOOSING_SKILL: [CallbackQueryHandler(handle_skill_selection)],
                CHOOSING_ITEM: [CallbackQueryHandler(handle_item_selection)],
            },
            fallbacks=[],
        )

        # Add handlers
        application.add_handler(conv_handler)
        application.add_handler(inventory_handler)
        application.add_handler(combat_handler)
        application.add_handler(CommandHandler("stats", stats))
        application.add_handler(CommandHandler("inventory", inventory))

        # Start the Bot
        logger.info("Starting bot...")
        application.run_polling()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise

if __name__ == '__main__':
    main() 