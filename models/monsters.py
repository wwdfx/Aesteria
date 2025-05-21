from sqlalchemy import Column, Integer, String, Float, Enum
import enum
from .base import Base

class MonsterType(enum.Enum):
    NORMAL = "normal"
    ELITE = "elite"
    BOSS = "boss"

class Monster(Base):
    __tablename__ = "monsters"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    monster_type = Column(Enum(MonsterType), default=MonsterType.NORMAL)
    level = Column(Integer, default=1)
    
    # Combat stats
    health = Column(Float, nullable=False)
    max_health = Column(Float, nullable=False)
    damage = Column(Float, nullable=False)
    defense = Column(Float, nullable=False)
    
    # Rewards
    experience_reward = Column(Integer, nullable=False)
    gold_reward = Column(Integer, nullable=False)
    
    # Drop table (stored as JSON string)
    drop_table = Column(String)  # JSON string of item_id: drop_chance pairs

    def get_stats(self):
        """Get formatted monster stats."""
        return {
            "name": self.name,
            "type": self.monster_type.value,
            "level": self.level,
            "health": f"{self.health}/{self.max_health}",
            "damage": self.damage,
            "defense": self.defense
        }

# Predefined monsters
DEFAULT_MONSTERS = [
    {
        "name": "Goblin",
        "description": "A small, green creature that likes to steal things.",
        "monster_type": MonsterType.NORMAL,
        "level": 1,
        "health": 50,
        "max_health": 50,
        "damage": 5,
        "defense": 2,
        "experience_reward": 10,
        "gold_reward": 5,
        "drop_table": "{}"
    },
    {
        "name": "Orc Warrior",
        "description": "A muscular orc trained in combat.",
        "monster_type": MonsterType.ELITE,
        "level": 5,
        "health": 150,
        "max_health": 150,
        "damage": 15,
        "defense": 8,
        "experience_reward": 50,
        "gold_reward": 25,
        "drop_table": "{}"
    },
    {
        "name": "Dragon",
        "description": "A fearsome dragon that guards its treasure.",
        "monster_type": MonsterType.BOSS,
        "level": 20,
        "health": 1000,
        "max_health": 1000,
        "damage": 50,
        "defense": 30,
        "experience_reward": 500,
        "gold_reward": 1000,
        "drop_table": "{}"
    }
] 