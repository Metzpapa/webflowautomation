# config.py

import os

# --- Webflow Configuration ---

# Webflow Site ID (Required for Asset Upload)
# TODO: Replace with your actual Webflow Site ID (find in Site Settings -> General -> API Access)
WEBFLOW_SITE_ID = os.getenv("WEBFLOW_SITE_ID", "REPLACE_WITH_YOUR_SITE_ID")

# TODO: Replace with your actual Webflow Blog Post Collection ID
WEBFLOW_COLLECTION_ID = "67dc8e9bea199c35f6f2e025"

# TODO: Replace with the Item ID of the default Category you want to assign posts to
DEFAULT_CATEGORY_ID = "67e4991ad69e1c8f370cb203"

# TODO: Replace with the Item ID of the default Author you want to assign posts to
DEFAULT_AUTHOR_ID = "6811134e2949fa13950f26e0"

# Webflow API Base URL (v2)
WEBFLOW_API_BASE_URL = "https://api.webflow.com/v2"

# Base URL for published blog posts (Include trailing slash if needed)
# Example: "https://www.yourdomain.com/blog/"
WEBFLOW_PUBLISHED_URL_BASE = os.getenv("WEBFLOW_PUBLISHED_URL_BASE", "https://www.valuemate.ai/blog/")

# URL for the chatbot resource
CHATBOT_URL = os.getenv("CHATBOT_URL", "https://www.valuemate.ai/#More")

# --- LLM Configuration ---

# Default Gemini model to use for generation
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"

# --- File Paths ---

# Path to the file storing summaries of previously generated posts
# Assumes it's in the same directory as this config file or the main script's CWD
SUMMARIES_FILE_PATH = "summaries.txt"

# --- Placeholders ---

# TODO: Update with a real URL if you have a preferred placeholder image
# This URL will be used for both 'Post - Featured Image' and 'Post - Thumbnail Image'
# Ensure it's a publicly accessible URL.
PLACEHOLDER_IMAGE_URL = "https://via.placeholder.com/1080x720.png?text=Placeholder+Image"

# --- Script Settings ---

# Set to True to enable the user confirmation step before posting to Webflow
REQUIRE_USER_CONFIRMATION = True

# Default status for new posts created via API ('draft' or 'published')
# Note: Webflow API v2 uses _draft: true/false in payload or live=false/true query param
# We will use _draft: true in the payload for clarity.
DEFAULT_POST_STATUS_IS_DRAFT = True

# Default value for the 'Post - Featured?' switch field
DEFAULT_FEATURED_STATUS = True

# --- Image Generation Settings ---
# Model to use for image generation
# Requires paid tier and appropriate API access.
OPENAI_IMAGE_MODEL = "gpt-image-1"
OPENAI_IMAGE_SIZE  = "1024x1024"

print("Configuration loaded.")
# You can add more sophisticated loading/validation here if needed later