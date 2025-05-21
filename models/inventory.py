from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum, Table
from sqlalchemy.orm import relationship
import enum
from .base import Base
from config.config import RARITY_MULTIPLIERS

class ItemType(enum.Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    CONSUMABLE = "consumable"

class ItemRarity(enum.Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    MYTHICAL = "mythical"
    LEGENDARY = "legendary"
    IMMORTAL = "immortal"

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    item_type = Column(Enum(ItemType), nullable=False)
    rarity = Column(Enum(ItemRarity), default=ItemRarity.COMMON)
    
    # Item stats
    damage = Column(Float, default=0)
    defense = Column(Float, default=0)
    health_bonus = Column(Float, default=0)
    mana_bonus = Column(Float, default=0)
    strength_bonus = Column(Float, default=0)
    
    # Relationships
    inventory_items = relationship("InventoryItem", back_populates="item")
    equipment = relationship("Equipment", back_populates="item")

    def apply_rarity_multiplier(self):
        """Apply rarity multiplier to item stats."""
        multiplier = RARITY_MULTIPLIERS[self.rarity.value]
        self.damage *= multiplier
        self.defense *= multiplier
        self.health_bonus *= multiplier
        self.mana_bonus *= multiplier
        self.strength_bonus *= multiplier

class Inventory(Base):
    __tablename__ = "inventories"

    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id"))
    capacity = Column(Integer, default=20)
    
    # Relationships
    character = relationship("Character", back_populates="inventory")
    items = relationship("InventoryItem", back_populates="inventory")

class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True)
    inventory_id = Column(Integer, ForeignKey("inventories.id"))
    item_id = Column(Integer, ForeignKey("items.id"))
    quantity = Column(Integer, default=1)
    
    # Relationships
    inventory = relationship("Inventory", back_populates="items")
    item = relationship("Item", back_populates="inventory_items")

class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id"))
    item_id = Column(Integer, ForeignKey("items.id"))
    slot = Column(String, nullable=False)  # e.g., "weapon", "armor", "accessory"
    
    # Relationships
    character = relationship("Character", back_populates="equipment")
    item = relationship("Item", back_populates="equipment") 