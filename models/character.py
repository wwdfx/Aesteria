from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum
from .base import Base
from config.config import BASE_HEALTH, BASE_MANA, BASE_STRENGTH, BASE_DEFENSE

class CharacterClass(enum.Enum):
    WARRIOR = "warrior"
    MAGE = "mage"
    ROGUE = "rogue"

class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    name = Column(String, nullable=False)
    character_class = Column(Enum(CharacterClass), nullable=False)
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)
    
    # Base stats
    health = Column(Float, default=BASE_HEALTH)
    max_health = Column(Float, default=BASE_HEALTH)
    mana = Column(Float, default=BASE_MANA)
    max_mana = Column(Float, default=BASE_MANA)
    strength = Column(Float, default=BASE_STRENGTH)
    defense = Column(Float, default=BASE_DEFENSE)
    
    # Relationships
    inventory = relationship("Inventory", back_populates="character", uselist=False)
    equipment = relationship("Equipment", back_populates="character", uselist=False)

    def calculate_level_up_requirements(self):
        """Calculate XP needed for next level."""
        return int(100 * (1.5 ** (self.level - 1)))

    def add_experience(self, amount):
        """Add experience and handle level ups."""
        self.experience += amount
        while self.experience >= self.calculate_level_up_requirements():
            self.level_up()

    def level_up(self):
        """Handle level up logic."""
        if self.level >= 100:  # Max level
            return False
        
        self.level += 1
        self.max_health += 10
        self.health = self.max_health
        self.max_mana += 5
        self.mana = self.max_mana
        self.strength += 2
        self.defense += 1
        return True

    def get_stats(self):
        """Get formatted character stats."""
        return {
            "name": self.name,
            "class": self.character_class.value,
            "level": self.level,
            "health": f"{self.health}/{self.max_health}",
            "mana": f"{self.mana}/{self.max_mana}",
            "strength": self.strength,
            "defense": self.defense,
            "experience": f"{self.experience}/{self.calculate_level_up_requirements()}"
        } 