import os
from dotenv import load_dotenv

load_dotenv()

# YouTube
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Google Sheets
GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

# Search parameters
SEARCH_KEYWORD = os.getenv("SEARCH_KEYWORD", "")
MAX_CHANNELS = int(os.getenv("MAX_CHANNELS", 50))
MIN_SUBSCRIBER_COUNT = int(os.getenv("MIN_SUBSCRIBER_COUNT", 1000))

# Crawling standard
TARGET_CATEGORY_ID = "24"          # 24 = Entertainment (YouTube category ID)
TARGET_CATEGORY_NAME = "Entertainment"
MAX_VIDEOS_PER_CHANNEL = 10        # Fetch only the 10 most recent videos per channel

# YouTube API quota
QUOTA_DAILY_LIMIT = 9500   # halt before hitting hard 10,000 limit
BATCH_SIZE = 50             # max items per API request

# Spreadsheet sheet names
SHEET_CHANNELS = "Channels"
SHEET_VIDEOS = "Videos"
SHEET_LEADS = "Leads"
SHEET_RUN_LOG = "Run_Log"

# Email regex
EMAIL_REGEX = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
