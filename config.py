import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else []

# Tournament settings
ALLOWED_TEAM_SIZES = [3, 4]
TOURNAMENT_SIZES = [8, 16, 32, 64]
