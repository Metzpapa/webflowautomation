# webflow_client.py
"""
Handles interactions with the Webflow Data API.

Provides functions to:
- Create a new CMS item in a specified collection.
- Upload assets to the Webflow site.
"""

import os
import requests
import json
import hashlib # Added for MD5 hash calculation
import sys # Added for error handling exit
from config import WEBFLOW_API_BASE_URL, WEBFLOW_COLLECTION_ID, WEBFLOW_SITE_ID

# --- Configuration ---
# Attempt to load API key from environment variable set by python-dotenv in main.py
WEBFLOW_API_KEY = os.getenv("WEBFLOW_API_KEY")

# --- Webflow API Functions ---

def upload_asset_from_bytes(image_bytes: bytes, filename: str, md5_hash: str) -> tuple[str | None, str | None]:
    """
    Uploads an image directly from bytes to Webflow Assets using the required
    two-step process (metadata registration -> S3 upload).
    Requires the pre-calculated MD5 hash of the image_bytes.

    Args:
        image_bytes (bytes): The raw bytes of the image.
        filename (str): The desired filename for the asset in Webflow.
        md5_hash (str): The pre-calculated MD5 hash of the image_bytes.

    Returns:
        tuple[str | None, str | None]: A tuple containing (asset_id, hosted_url)
                                        or (None, None) on failure.
    """
    if not WEBFLOW_API_KEY:
        print("ERROR: WEBFLOW_API_KEY environment variable not found for asset upload.")
        return None, None
    if not WEBFLOW_SITE_ID or WEBFLOW_SITE_ID == "REPLACE_WITH_YOUR_SITE_ID":
        print("ERROR: WEBFLOW_SITE_ID is not configured in config.py or .env file.")
        return None, None
    if not image_bytes:
        print("ERROR: image_bytes data is empty.")
        return None, None
    if not md5_hash:
        print("ERROR: md5_hash was not provided.")
        return None, None

    # --- Step 0: Calculate MD5 Hash (REMOVED - Now passed as argument) ---
    # try:
    #     md5_hash = hashlib.md5(image_bytes).hexdigest()
    #     print(f"Calculated MD5 Hash: {md5_hash}")
    # except Exception as e:
    #     print(f"ERROR: Failed to calculate MD5 hash: {e}")
    #     return None, None

    # --- Step 1: Asset Metadata Registration (POST to Webflow API) ---
    metadata_api_url = f"{WEBFLOW_API_BASE_URL}/sites/{WEBFLOW_SITE_ID}/assets"
    headers_step1 = {
        "Authorization": f"Bearer {WEBFLOW_API_KEY}",
        "accept": "application/json",
        "Content-Type": "application/json" # Must be JSON
    }
    payload_step1 = {
        "fileName": filename,
        "fileHash": md5_hash
        # Optionally add "parentFolder": "your_folder_id" here
    }

    print(f"Step 1: Posting metadata to {metadata_api_url}...")
    upload_url = None
    upload_details = None
    asset_id = None
    hosted_url = None

    try:
        response_step1 = requests.post(metadata_api_url, headers=headers_step1, json=payload_step1)
        response_step1.raise_for_status() # Check for 4xx/5xx errors

        upload_data = response_step1.json()
        upload_url = upload_data.get('uploadUrl')
        upload_details = upload_data.get('uploadDetails')
        asset_id = upload_data.get('id') # Use 'id' which is the standard Asset ID
        hosted_url = upload_data.get('hostedUrl')

        if not upload_url or not upload_details:
            print("ERROR: 'uploadUrl' or 'uploadDetails' not found in Webflow API response (Step 1).")
            print(f"Response content: {response_step1.text}")
            return None, None # Indicate failure

        print(f"Step 1 Successful. Asset ID: {asset_id}")
        # print(f"Received S3 Upload URL: {upload_url[:50]}...") # Optional debug print

    except requests.exceptions.RequestException as e:
        print(f"ERROR: During Webflow API request (Step 1): {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response Status Code: {e.response.status_code}")
            try:
                print(f"Response Body: {json.dumps(e.response.json(), indent=2)}")
            except json.JSONDecodeError:
                 print(f"Response Body: {e.response.text}")
        return None, None
    except json.JSONDecodeError as e:
        print(f"ERROR: Decoding JSON response from Webflow API (Step 1): {e}")
        print(f"Response content: {response_step1.text}")
        return None, None
    except Exception as e:
         print(f"ERROR: An unexpected error occurred during Step 1: {e}")
         return None, None

    # --- Step 2: File Data Upload (POST to S3 uploadUrl) ---
    # Prepare the payload for S3 POST - fields from uploadDetails go in 'data'
    s3_payload_data = {}
    for key, value in upload_details.items():
        s3_payload_data[key] = value

    # Determine the correct content type for the file part
    file_content_type = upload_details.get('content-type', 'application/octet-stream') # Default if not specified

    # Prepare the file part for S3 POST - the actual image goes in 'files'
    files_payload = {
        'file': (filename, image_bytes, file_content_type)
    }

    print(f"Step 2: Uploading file data to S3 ({upload_url[:60]}...).")
    try:
        s3_response = requests.post(upload_url, data=s3_payload_data, files=files_payload)

        # Check the status code expected by S3 (often 201 or 204)
        expected_s3_status_str = upload_details.get('success_action_status', '201')
        try:
            expected_s3_status = int(expected_s3_status_str)
        except ValueError:
            print(f"Warning: Could not parse expected S3 status '{expected_s3_status_str}'. Checking for general success (2xx).")
            expected_s3_status = None

        if expected_s3_status:
            if s3_response.status_code != expected_s3_status:
                print(f"ERROR: S3 upload failed. Expected status {expected_s3_status}, received {s3_response.status_code}.")
                print(f"S3 Response Body: {s3_response.text}")
                return None, None # Indicate failure
            else:
                print(f"Step 2 Successful: File uploaded to S3 (Status: {s3_response.status_code}).")
        elif not s3_response.ok:
            print(f"ERROR: S3 upload failed with status {s3_response.status_code}.")
            print(f"S3 Response Body: {s3_response.text}")
            return None, None # Indicate failure
        else:
             print(f"Step 2 Successful: File uploaded to S3 (Status: {s3_response.status_code}).")

        # Both steps successful, return the Webflow asset ID and hosted URL
        print(f"Asset upload complete. Webflow Asset ID: {asset_id}")
        if hosted_url:
            print(f"Hosted URL: {hosted_url}")
        return asset_id, hosted_url # Return both values

    except requests.exceptions.RequestException as e:
        print(f"ERROR: During S3 upload request (Step 2): {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response Status Code: {e.response.status_code}")
            print(f"Response Body: {e.response.text}")
        return None, None # Return None for both on error
    except Exception as e:
         print(f"ERROR: An unexpected error occurred during Step 2: {e}")
         return None, None # Return None for both on error


def create_cms_item(payload: dict) -> str | None:
    """
    Creates a new item in the specified Webflow CMS collection.

    Args:
        payload (dict): The complete payload dictionary for the new item,
                        structured according to Webflow API v2 requirements.
                        Expected structure:
                        {
                          "isArchived": bool,
                          "isDraft": bool,
                          "fieldData": {
                            "name": "Post Title", # Required by Webflow
                            "slug": "post-title-slug", # Required by Webflow
                            "your-image-field": {"fileId": "ASSET_ID", "alt": "text"},
                            "your-field-slug-1": "value1",
                            # ... other fields mapped by their Webflow slug
                          }
                        }

    Returns:
        str | None: The ID of the newly created Webflow item if successful,
                    otherwise None.
    """
    if not WEBFLOW_API_KEY:
        print("ERROR: WEBFLOW_API_KEY environment variable not found.")
        return None

    if not WEBFLOW_COLLECTION_ID or WEBFLOW_COLLECTION_ID == "REPLACE_WITH_YOUR_COLLECTION_ID":
        print("ERROR: WEBFLOW_COLLECTION_ID is not configured in config.py.")
        return None

    if not payload or 'fieldData' not in payload:
        print("ERROR: Invalid payload provided for Webflow item creation.")
        return None

    # Construct the API endpoint URL
    api_url = f"{WEBFLOW_API_BASE_URL}/collections/{WEBFLOW_COLLECTION_ID}/items"

    # Set required headers
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_KEY}",
        "accept": "application/json",
        "content-type": "application/json",
        # "Accept-Version": "1.0.0" # Generally not needed if using v2 base URL
    }

    print(f"Attempting to create Webflow item in Collection ID: {WEBFLOW_COLLECTION_ID}...")
    # print(f"Payload being sent:\n{json.dumps(payload, indent=2)}") # Uncomment for debugging

    try:
        response = requests.post(api_url, headers=headers, json=payload)

        # Check the response status code
        if response.status_code in [200, 201, 202]: # 200 OK, 201 Created, or 202 Accepted
            response_data = response.json()
            new_item_id = response_data.get("id") or response_data.get("_id")
            if new_item_id:
                print(f"Webflow item created successfully! Item ID: {new_item_id}")
                return new_item_id
            else:
                print("ERROR: Webflow API returned success status but no item ID found.")
                print(f"Response: {response_data}")
                return None
        else:
            # Handle errors
            print(f"ERROR: Webflow API request failed with status code {response.status_code}")
            try:
                error_details = response.json()
                print("Error Details:")
                print(json.dumps(error_details, indent=2))
            except json.JSONDecodeError:
                print(f"Could not parse error response body: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"ERROR: An error occurred during the Webflow API request: {e}")
        return None
    except Exception as e:
        print(f"ERROR: An unexpected error occurred in create_cms_item: {e}")
        return None