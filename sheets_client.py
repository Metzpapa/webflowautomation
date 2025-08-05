# webflowautomation/sheets_client.py

import os
import gspread
import google.auth

# This is the final, corrected version for using Application Default Credentials
# with service account impersonation handled automatically by the environment.

# Define the necessary scopes for Google Sheets API access.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# 1. Use the standard google.auth library to find the Application Default Credentials.
# It will automatically find the file from `gcloud auth application-default login`.
# It will also automatically use the GOOGLE_CLOUD_IMPERSONATE_SERVICE_ACCOUNT
# environment variable to handle impersonation.
creds, _ = google.auth.default(scopes=SCOPES)

# 2. Authorize the gspread client using the credentials we just found.
gc = gspread.authorize(creds)

# 3. Open the spreadsheet using the authorized client and the document ID from your .env file.
ws = gc.open_by_key(
    os.environ["GOOGLE_SHEETS_DOC_ID"]
).worksheet("posts")

# The exact headers that must be in the first row of your "posts" worksheet.
HEADERS = [
    "name", "slug", "excerpt_page", "excerpt_featured",
    "reading_time", "body_html", "image_url",
    "draft", "created_at"
]

def upsert(row: dict[str, str | int | bool]) -> str:
    """
    Adds or updates a row in the Google Sheet based on the slug.
    """
    slug = row["slug"]
    existing = {r["slug"]: idx + 2 for idx, r in enumerate(ws.get_all_records())}
    row_values = [row.get(h, "") for h in HEADERS]

    if slug in existing:
        row_index = existing[slug]
        ws.update(f"A{row_index}:I{row_index}", [row_values])
        print(f"Updated existing row for slug: {slug}")
    else:
        ws.append_row(row_values)
        print(f"Appended new row for slug: {slug}")

    return slug