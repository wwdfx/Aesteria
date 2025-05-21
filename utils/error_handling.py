import logging
import traceback
from functools import wraps
from typing import Callable, Any
from sqlalchemy.exc import SQLAlchemyError
from telegram import Update
from telegram.ext import ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='rpg_bot.log'
)
logger = logging.getLogger(__name__)

# Custom exceptions
class GameError(Exception):
    """Base exception for game-related errors."""
    pass

class CharacterError(GameError):
    """Exception for character-related errors."""
    pass

class InventoryError(GameError):
    """Exception for inventory-related errors."""
    pass

class CombatError(GameError):
    """Exception for combat-related errors."""
    pass

class DatabaseError(GameError):
    """Exception for database-related errors."""
    pass

def log_error(error: Exception, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None) -> None:
    """Log error with context information."""
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc()
    }
    
    if update:
        error_info.update({
            'user_id': update.effective_user.id if update.effective_user else None,
            'chat_id': update.effective_chat.id if update.effective_chat else None,
            'message_text': update.message.text if update.message else None
        })
    
    if context:
        error_info['user_data'] = context.user_data
    
    logger.error(f"Error occurred: {error_info}")

def handle_database_error(func: Callable) -> Callable:
    """Decorator to handle database errors."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except SQLAlchemyError as e:
            logger.error(f"Database error in {func.__name__}: {str(e)}")
            update = next((arg for arg in args if isinstance(arg, Update)), None)
            if update and update.message:
                await update.message.reply_text(
                    "A database error occurred. Please try again later."
                )
            raise DatabaseError(f"Database operation failed: {str(e)}")
    return wrapper

def handle_game_error(func: Callable) -> Callable:
    """Decorator to handle game-related errors."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except GameError as e:
            logger.error(f"Game error in {func.__name__}: {str(e)}")
            update = next((arg for arg in args if isinstance(arg, Update)), None)
            if update and update.message:
                await update.message.reply_text(str(e))
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            update = next((arg for arg in args if isinstance(arg, Update)), None)
            if update and update.message:
                await update.message.reply_text(
                    "An unexpected error occurred. Please try again later."
                )
            raise
    return wrapper

def log_command(func: Callable) -> Callable:
    """Decorator to log command execution."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        update = next((arg for arg in args if isinstance(arg, Update)), None)
        if update and update.message:
            logger.info(
                f"Command {func.__name__} executed by user {update.effective_user.id} "
                f"in chat {update.effective_chat.id}"
            )
        return await func(*args, **kwargs)
    return wrapper

def log_state_transition(func: Callable) -> Callable:
    """Decorator to log state transitions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        update = next((arg for arg in args if isinstance(arg, Update)), None)
        if update and update.message:
            logger.info(
                f"State transition in {func.__name__} for user {update.effective_user.id}"
            )
        return await func(*args, **kwargs)
    return wrapper

def log_combat_action(func: Callable) -> Callable:
    """Decorator to log combat actions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        update = next((arg for arg in args if isinstance(arg, Update)), None)
        if update and update.message:
            logger.info(
                f"Combat action {func.__name__} executed by user {update.effective_user.id}"
            )
        return await func(*args, **kwargs)
    return wrapper

def log_inventory_action(func: Callable) -> Callable:
    """Decorator to log inventory actions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        update = next((arg for arg in args if isinstance(arg, Update)), None)
        if update and update.message:
            logger.info(
                f"Inventory action {func.__name__} executed by user {update.effective_user.id}"
            )
        return await func(*args, **kwargs)
    return wrapper 