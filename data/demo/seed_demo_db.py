"""手动生成/重置演示数据库: python data/demo/seed_demo_db.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.adapters.mock_mes import DEMO_DB, seed_demo_db

path = seed_demo_db(DEMO_DB, force=True)
print(f"演示库已生成: {path}")
