# main.py
"""
Main orchestration script for the Blog Automation Workflow.

Loads configuration, interacts with the LLM to generate content and metadata,
prepares the data for Webflow, handles user confirmation, posts to Webflow API,
and updates the summary log upon success.
"""

import os
import json
import re
import markdown
import time # For delays
import hashlib # For MD5 hash
import argparse # For command-line arguments
from openai import OpenAI # Updated OpenAI import
import base64 # Added for OpenAI image generation
import requests # Added for fetching image from URL
from dotenv import load_dotenv
from io import BytesIO # Added for image handling
import openai # Added for error handling in image generation

# Import Pillow for image compression
try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow library not found. Please install it: pip install Pillow")
    exit(1)

# --- ADDED CLIPBOARD IMPORT ---
try:
    import pyperclip
    clipboard_available = True
except ImportError:
    print("WARN: pyperclip library not found. Install it (`pip install pyperclip`) to enable automatic clipboard copying.")
    clipboard_available = False
# --- END ADDED CLIPBOARD IMPORT ---

# Load environment variables from .env file *before* importing other modules
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Now import project modules
import config
import llm_handler

# --- Helper Functions ---

def load_summaries(filepath: str) -> list[dict[str, str]]:
    """Loads previously generated summaries and their URLs from the specified file.
       Expects format: summary text::url
    """
    summaries_data = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                parts = line.split('::', 1)
                if len(parts) == 2:
                    summary, url = parts
                    summaries_data.append({'summary': summary.strip(), 'url': url.strip()})
                else:
                    print(f"WARN: Malformed line {line_num+1} in {filepath}: '{line}'. Skipping.")
        print(f"Loaded {len(summaries_data)} previous summaries/URLs from {filepath}")
    except FileNotFoundError:
        print(f"Summary file not found at {filepath}. Starting fresh.")
    except Exception as e:
        print(f"Error loading summaries from {filepath}: {e}")
    return summaries_data

def save_summary(filepath: str, summary: str, url: str):
    """Appends a new summary and its URL to the specified file."""
    if not summary or not url:
        print(f"WARN: Attempted to save empty summary or URL to {filepath}. Skipping.")
        return
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(f"{summary}::{url}\n") # Save in summary::url format
        print(f"Successfully appended new summary and URL to {filepath}")
    except Exception as e:
        print(f"Error saving summary/URL to {filepath}: {e}")

def prepare_webflow_payload(slug: str, body_content: str, metadata: dict, image_file_id: str | None, hosted_image_url: str | None) -> dict:
    """Prepares the JSON payload for the Webflow Create Item API call.
       Converts the input markdown body_content to HTML for Webflow.
       Uses the provided image_file_id and hosted_image_url for image fields.
       Accepts pre-calculated slug.
    """
    raw_title = metadata.get("title", "untitled-post")
    try:
        html_body_content_raw = markdown.markdown(body_content)
        html_body_content = html_body_content_raw.replace("\n", "")
    except Exception as e:
        print(f"WARN: Failed to convert/clean Markdown to HTML: {e}. Sending raw Markdown instead.")
        html_body_content = body_content # Fallback

    field_data = {
        "name": raw_title,
        "slug": slug,
        "post-body": html_body_content,
        "post-excerpt-post-page": metadata.get("excerpt_page", ""),
        "post-excerpt-post-featured": metadata.get("excerpt_featured", ""),
        "post-reading-time-minutes": metadata.get("reading_time", 0),
        "post-category": config.DEFAULT_CATEGORY_ID,
        "post-author": config.DEFAULT_AUTHOR_ID,
        "post-featured": config.DEFAULT_FEATURED_STATUS,
        "post-main-image": {
            "fileId": image_file_id,
            "alt": raw_title,
            "url": hosted_image_url
        } if image_file_id and hosted_image_url else None,
        "post-main-image-thumbnail": {
             "fileId": image_file_id,
             "alt": f"{raw_title} Thumbnail",
             "url": hosted_image_url
        } if image_file_id and hosted_image_url else None,
    }
    filtered_field_data = {k: v for k, v in field_data.items() if v is not None}
    payload = {
        "isArchived": False,
        "isDraft": config.DEFAULT_POST_STATUS_IS_DRAFT,
        "fieldData": filtered_field_data
    }
    return payload

# --- Main Execution Logic --- (Refactored for Loop) ---

def main(num_posts: int, generate_linkedin: bool, auto_mode: bool, provider: str = "webflow"):
    """Runs the main blog post generation and publishing workflow for num_posts."""
    # Import and configure CMS provider
    if provider == "webflow":
        from cms_providers.webflow_provider import create_cms_item as webflow_publish
        publish_fn = webflow_publish
        upload_asset_fn = None
        try:
            from cms_providers.webflow_provider import upload_asset_from_bytes
            upload_asset_fn = upload_asset_from_bytes
        except ImportError:
            print("WARN: webflow upload_asset_from_bytes not available")
    else:  # framer-sheets
        from cms_providers.framer_sheets_provider import FramerSheetsProvider
        framer_provider = FramerSheetsProvider()
        publish_fn = framer_provider.publish
        upload_asset_fn = None  # Framer provider handles images internally
    print("--- Starting Blog Automation Workflow ---")

    # --- One-Time Setup ---
    print("\nStep 0: Initializing Clients & Uploading Context...")
    if not llm_handler.configure_genai():
        print("ERROR: Failed to configure Gemini library. Exiting.")
        return
    if not llm_handler.upload_context_files():
        print("WARN: Failed to upload one or more context files. Proceeding without file context.")
    # Load previous summaries ONCE before the loop
    previous_summaries = load_summaries(config.SUMMARIES_FILE_PATH)
    print("Initialization complete.")
    # --- End One-Time Setup ---

    # --- Main Generation Loop ---
    posts_created_count = 0
    for i in range(num_posts):
        print(f"\n===== Starting Post {i+1}/{num_posts} ====")

        # Define Base Prompt (Remains the same for each loop)
        BASE_BLOG_PROMPT = """
    You are Daniel Yoder, an experienced residential real estate appraiser writing an educational, high-trust blog post for fellow appraisers.
    Your goal is to help them understand the ongoing developments and changes related to UAD 3.6 and UPD.
    You are writing for a company called Valuemate. It is a real estate app that allows an appraiser — or anyone collecting property data — to walk into a house, scan it, and automatically generate a 3D model of the entire property. But it doesn't stop there — the app (Valuemate) also auto-generates key parts of the property report. Here is a brief description on what sections it automates and what it does not (you can find these sections in the example report)
    Automated Sections
    1.  Contact Information Section
    •   Appraisers enter all information when they create their account.
    2.  Site Exhibits (Street Scene)
    •   Automated via photos taken when entering the site.
    3.  Sketch
    •   Automated using LiDAR floor plans.
    4.  Exhibits
    •   Automated as pictures will be taken throughout the scan.
    5.  Interior and Area Breakdown
    •   Automated via calculation of square footage.
    6.  Quality Interior Features
    •   Automated via AI Vision and user input.
    7.  Unit Interior Exhibits
    •   Automated via pictures.
    8.  Interior (General)
    •   Automated as the appraiser just states the room they are in.
    9.  Vehicle Storage Exhibits
    •   Automated via photos taken throughout the scan.
    10. Market Analysis
    •   Automated along with graphs and exhibits.
    11. Sales Comparison Approach
    •   Automated until the end (likely involving calculation and comparison algorithms).
    ⸻
    Mixed (Partially Automated, Partially Manual) Sections
    1.  Summary Aspect
    •   Automated for verbal inputs; manual for data like borrower's name and current owner.
    2.  Damages Section
    •   Automated if mentioned aloud by appraiser; manual otherwise.
    3.  Subject Property (Till Apparent Defects)
    •   Automated if described aloud; manual otherwise.
    4.  Energy Efficient Features
    •   Partially automated; additional input may be required from the appraiser.
    5.  Quality and Condition
    •   Automated if mentioned aloud; manual for other details.
    6.  Mechanical System Details, Apparent Defects, Dwelling Exterior Commentary
    •   Automated if mentioned aloud; manual otherwise.
    7.  Sales Contract and Prior Sales
    •   Could be automated depending on available data at the time.
    ⸻
    Not Automated (Manual Input Required)
    •   Borrower's Name & Current Owner (as it won't come up during a scan)
    •   Any missing details not covered by verbal input or available data sources.
    This lowers the barrier to entry for creating high-quality reports and speed up turnaround time.
    A big part of this expected shift is related to the introduction of UAD 3.6 and the Uniform Property Dataset (UPD). These are initiatives by Fannie Mae and Freddie Mac intended to modernize and standardize the appraisal and property data collection process. UAD 3.6 **proposes updates** to the structure of traditional appraisal reports (like the URAR) with a more dynamic and flexible format. UPD, on the other hand, is a **proposed** new dataset designed for standardized property data collection, especially in desktop and hybrid appraisals. Together, UAD 3.6 and UPD **are envisioned** to form the backbone of a more automated, consistent, and scalable valuation process.

    As part of our content and marketing strategy, we're planning to create blog posts that help
    appraisers understand these developments in their appraisals. They should be specific and niche. Right now we are trying to create Educational, high-trust posts.
    Our target audience is the Individual Real Estate Appraiser specializing in residential properties. This includes any appraiser who is actively practicing in the field and is responsible for property inspection, data collection, and reporting. They work with appraisal standards and forms, and are therefore **likely to be impacted** by industry updates like the Uniform Property Dataset (UPD).

    Mention Valuemate sparingly, only if highly relevant as a tool that **could assist with navigating** the discussed topics.

    **Previous Post Context & Interlinking:**
    Below this prompt, a list of previously generated posts may be provided, including their summary and URL. While you MUST ensure the main topic of *this* new post is distinct from those summaries, you **can and should reference** a previous post (using its Markdown link format like `[link text](URL)`) if it provides relevant background or context for a specific point you are making in the *current* post. Only link if it genuinely adds value for the reader. You should add links wherever you believe it is really actually valuable. 

    **Important Tone and Certainty Guidance:**
    Focus on providing specific, niche, and practical insights based on the provided context documents (UAD/UPD PDFs).
    When discussing specific details about UAD 3.6 and UPD:
    If a detail is clearly stated as a finalized decision, a current standard, or a definite past event in the provided documents, present it confidently and factually.
    Maintain a professional, informative, and helpful tone throughout. Carefully balance confidence in confirmed facts. Its important your posts should be distinct from all the previous summaries, and your introduction should be specific to the post you are doing right now, not a generic introduction
    Try to refrain from making tables. Try to refrain from making philisophical posts about the future of appraising, focus on key facts that will change with UAD 3.6 and UPD. Do not tell appraiser what they should do, instead give them the necessary information to make their own decisions. You should introduce yourself at the beginning of a post but make the introduction specfic to the content of the post. This way you dont say the same exact thing each time. 

        """ # Base prompt definition ends here

        # 1. Generate Markdown Blog Post Body (Uses uploaded context)
        print(f"\nStep 1.{i+1}: Generating Blog Post Markdown Body...")
        markdown_body = llm_handler.generate_html_body(
            config.DEFAULT_GEMINI_MODEL,
            BASE_BLOG_PROMPT,
            previous_summaries # Pass current list of summaries
        )
        if not markdown_body:
            print(f"ERROR: Markdown body generation failed for post {i+1}. Skipping.")
            continue # Skip to next iteration

        # --- Extract Interlinks from Markdown Body ---
        extracted_interlinks = []
        try:
            # Find all URLs within markdown links: [text](URL)
            extracted_interlinks = re.findall(r'\[[^\]]*?\]\((https?://[^\)]+)\)', markdown_body)
            if extracted_interlinks:
                print(f"  Extracted {len(extracted_interlinks)} interlinks from blog body.")
            else:
                print("  No interlinks found in blog body.")
        except Exception as e:
            print(f"WARN: Failed to extract interlinks from markdown body: {e}")
        # --- End Interlink Extraction ---

        # 2. Generate Metadata JSON
        print(f"\nStep 2.{i+1}: Generating Metadata JSON...")
        metadata = llm_handler.generate_metadata_json(
            config.DEFAULT_GEMINI_MODEL, # Can likely use flash model here
            markdown_body
        )
        if not metadata:
            print(f"ERROR: Metadata generation failed for post {i+1}. Skipping.")
            continue

        # --- Calculate Slug and Final URL Early ---
        raw_title = metadata.get("title", "untitled-post")
        slug = re.sub(r'[^a-z0-9-]', '', raw_title.lower().replace(" ", "-")).strip('-')
        slug = slug or "untitled-post"
        blog_post_url = config.WEBFLOW_PUBLISHED_URL_BASE + slug # Calculate final URL
        print(f"  Calculated slug: {slug}")
        print(f"  Calculated final URL: {blog_post_url}")
        # --- End Slug/URL Calculation ---

        # 3. Image Handling (Conditional)
        print(f"\nStep 3.{i+1}: Image Handling...")
        image_file_id = None
        hosted_image_url = None
        compressed_image_bytes = None

        # --- MODIFIED SECTION: Image generation only runs for the 'webflow' provider ---
        if provider == "webflow":
            print("  Provider is 'webflow', proceeding with image generation and upload.")
            image_description = metadata.get("image_description")

            if image_description:
                print(f"  Using description: '{image_description}'")
                if not client:
                    print("  ERROR: OpenAI client not initialized. Skipping image for this post.")
                    original_image_bytes = None # Skip image part
                else:
                    max_retries_img = 3
                    retry_delay_img = 30  # seconds
                    original_image_bytes = None # Initialize
                    for attempt in range(max_retries_img):
                        try:
                            print(f"  Generating image with GPT Image model… (Attempt {attempt+1}/{max_retries_img})")
                            response = client.images.generate(
                                model="gpt-image-1",
                                prompt=image_description,
                                n=1,
                                size=config.OPENAI_IMAGE_SIZE
                            )

                            if response.data and hasattr(response.data[0], 'b64_json') and response.data[0].b64_json:
                                base64_image_data = response.data[0].b64_json
                                print(f"  Base64 image data received. Decoding...")
                                try:
                                    original_image_bytes = base64.b64decode(base64_image_data)
                                    print(f"  Image decoded successfully.")
                                    if hasattr(response.data[0], 'revised_prompt'):
                                        print(f"  Revised prompt: {response.data[0].revised_prompt}")
                                except base64.binascii.Error as b64_err:
                                    print(f"  ERROR: Failed to decode base64 image data: {b64_err}. Skipping image for this post.")
                                    original_image_bytes = None
                                    break
                                except Exception as e:
                                    print(f"  ERROR: An unexpected error occurred during base64 decoding: {e}. Skipping image for this post.")
                                    original_image_bytes = None
                                    break
                            else:
                                print(f"  ERROR: OpenAI API did not return valid b64_json image data for the prompt: '{image_description}'.")
                                if response.data and len(response.data) > 0:
                                    print(f"  Response data[0] content: {response.data[0]}")
                                elif hasattr(response, 'error') and response.error:
                                    print(f"  API Error Code: {getattr(response.error, 'code', 'N/A')}")
                                    print(f"  API Error Message: {getattr(response.error, 'message', 'N/A')}")
                                else:
                                    print(f"  Full API response: {response}")
                                original_image_bytes = None
                                break
                            if original_image_bytes:
                                break
                        except openai.APIError as e:
                            print(f"  ERROR: OpenAI API error on attempt {attempt+1}: {e}")
                            if hasattr(e, 'http_status'):
                                print(f"    HTTP Status: {e.http_status}")
                            if hasattr(e, 'code'):
                                print(f"    Error Code: {e.code}")
                            if isinstance(e, openai.RateLimitError) and attempt < max_retries_img - 1:
                                print(f"    Rate limit hit. Retrying in {retry_delay_img}s...")
                                time.sleep(retry_delay_img)
                                continue
                            else:
                                original_image_bytes = None
                                break
                        except Exception as e:
                            print(f"  ERROR: Unexpected error during image generation on attempt {attempt+1}: {e}")
                            original_image_bytes = None
                            break

                    if original_image_bytes:
                        print(f"  Image generated successfully (Original size: {len(original_image_bytes) / 1024:.1f} KB). Compressing...")

                        try:
                            img = Image.open(BytesIO(original_image_bytes))
                            if img.mode in ('RGBA', 'P'):
                               img = img.convert('RGB')
                            
                            buffer = BytesIO()
                            img.save(buffer, format='PNG', optimize=True)
                            compressed_image_bytes = buffer.getvalue()
                            print(f"  Image compressed successfully (New size: {len(compressed_image_bytes) / 1024:.1f} KB).")
                        except Exception as e:
                            print(f"  WARN: Failed to compress image: {e}. Uploading original image bytes.")
                            compressed_image_bytes = original_image_bytes

                        if compressed_image_bytes:
                            try:
                                md5_hash = hashlib.md5(compressed_image_bytes).hexdigest()
                                print(f"  Calculated MD5 Hash for upload: {md5_hash}")
                            except Exception as e:
                                print(f"  ERROR: Failed to calculate MD5 hash for compressed bytes: {e}. Skipping image upload.")
                                md5_hash = None

                            if md5_hash:
                                max_slug_len = 90
                                image_slug = slug
                                if len(slug) > max_slug_len:
                                    image_slug = slug[:max_slug_len]
                                    print(f"  WARN: Original slug \'{slug}\' was too long for image filename, truncated to: {image_slug}")

                                filename = f"{image_slug}-main.png"
                                print(f"  Using filename for upload: {filename}")

                                if upload_asset_fn:
                                    image_file_id, hosted_image_url = upload_asset_fn(
                                        compressed_image_bytes, filename, md5_hash
                                    )
                                    if not image_file_id or not hosted_image_url:
                                        print("  WARN: Failed to upload compressed image to Webflow Assets or get required data.")
                                        image_file_id = None
                                        hosted_image_url = None
                                else:
                                    print("  WARN: Asset upload function not available for Webflow provider.")
                                    image_file_id = None
                                    hosted_image_url = None
                    else:
                        print("  ERROR: OpenAI image generation failed after retries or returned no image data.")
            else:
                 print(f"  Skipping image generation for post {i+1}: No image_description found in metadata.")
        else:
            print("  Provider is 'framer-sheets', skipping image generation and upload.")
        # --- END MODIFIED SECTION ---

        # 4. Prepare Payload
        print(f"\nStep 4.{i+1}: Preparing Payload...")
        if provider == "webflow":
            # Pass the pre-calculated slug
            payload = prepare_webflow_payload(slug, markdown_body, metadata, image_file_id, hosted_image_url)
        else:
            # For framer-sheets, we'll pass the data directly to the publish function
            payload = None

        # 5. User Confirmation (or Skip in Auto Mode)
        print(f"\nStep 5.{i+1}: User Confirmation...")
        proceed_to_create = False # Flag to control proceeding
        # Always print details for logging
        print("-" * 30)
        print(f"Title: {metadata.get('title', 'N/A')}")
        print(f"Excerpt (Page): {metadata.get('excerpt_page', 'N/A')}")
        print(f"Image Asset File ID: {image_file_id if image_file_id else 'N/A'}")
        print(f"Hosted Image URL: {hosted_image_url if hosted_image_url else 'N/A'}")
        print(f"Status: {'Draft' if config.DEFAULT_POST_STATUS_IS_DRAFT else 'Published'}")
        print(f"Collection ID: {config.WEBFLOW_COLLECTION_ID}")
        print("-" * 30)

        if not auto_mode:
            # Manual mode: Ask for confirmation
            confirm = input(f"Proceed to create item {i+1} in {provider}? (y/n): ").lower()
            if confirm == 'y':
                proceed_to_create = True
            else:
                print(f"Operation cancelled by user for this post. Skipping {provider} creation.")
        else:
            # Auto mode: Skip confirmation input
            print("Auto mode enabled: Skipping user confirmation input and proceeding automatically...")
            proceed_to_create = True

        # Only proceed if confirmed (manually or automatically)
        new_item_id = None # Initialize new_item_id outside the block
        if proceed_to_create:
            # 6. Create CMS Item
            print(f"\nStep 6.{i+1}: Creating CMS Item via {provider} provider...")
            if provider == "webflow":
                new_item_id = publish_fn(payload) # Assign result here
            else:  # framer-sheets
                new_item_id = publish_fn(
                    slug=slug,
                    html_body=markdown_body,
                    metadata=metadata,
                    image_bytes=compressed_image_bytes  # will be None for this provider
                )

            # 7. Update Summaries and Finish Loop Iteration (Conditional on Success)
            print(f"\nStep 7.{i+1}: Finalizing...")
            if new_item_id:
                print(f"Workflow successful for post {i+1}! New item created with ID/Slug: {new_item_id}")
                posts_created_count += 1
                # --- Save Summary and URL ---
                new_summary = metadata.get("excerpt_page")
                if new_summary:
                    # Note: This URL is Webflow-specific. For Framer, the URL structure might differ.
                    # This is acceptable for now as the summary file's main purpose is preventing topic duplication.
                    blog_post_url = config.WEBFLOW_PUBLISHED_URL_BASE + slug
                    save_summary(config.SUMMARIES_FILE_PATH, new_summary, blog_post_url)
                    previous_summaries.append({'summary': new_summary, 'url': blog_post_url})
                else:
                    print("Warning: Could not save summary as 'excerpt_page' was missing from metadata.")
                # --- End Save Summary ---

                # --- Generate LinkedIn Post (if flag is set) ---
                if generate_linkedin:
                    print(f"\nStep 7a.{i+1}: Generating LinkedIn Post Draft...")
                    linkedin_draft = llm_handler.generate_linkedin_post(
                        model_name=config.DEFAULT_GEMINI_MODEL,
                        blog_content_snippet=markdown_body,
                        new_blog_post_url=blog_post_url,
                        interlinks=extracted_interlinks
                    )
                    if linkedin_draft:
                        chatbot_url = config.CHATBOT_URL
                        final_post = linkedin_draft.replace("[CHATBOT_URL]", chatbot_url)

                        print("\n" + "-"*15 + " LinkedIn Post Draft " + "-"*15)
                        print(final_post)
                        print("-"*51 + "\n")

                        if clipboard_available:
                            try:
                                pyperclip.copy(final_post)
                                print(">>> LinkedIn draft copied to clipboard! <<<")
                            except Exception as clip_err:
                                print(f"WARN: Failed to copy LinkedIn draft to clipboard: {clip_err}")
                    else:
                        print("  WARN: Failed to generate LinkedIn post draft.")
                # --- End LinkedIn Post Generation ---

            else: # new_item_id is None (creation failed)
                print(f"Workflow failed for post {i+1}. Could not create item in {provider}.")

        # Add delay between posts (except after the last one)
        if i < num_posts - 1:
             print(f"\n--- Pausing for 5 minutes before starting post {i+2}/{num_posts}... ---")
             time.sleep(300) # 5 minutes

    # --- End Main Generation Loop ---

    print(f"\n--- Blog Automation Workflow Finished --- ({posts_created_count}/{num_posts} posts successfully created) ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate and publish blog posts.")
    parser.add_argument(
        "-n", "--num-posts",
        type=int,
        default=1,
        help="Number of blog posts to generate and publish (default: 1)."
    )
    parser.add_argument(
        "-l", "--linkedin",
        action="store_true", # Makes it a flag, default False
        help="Generate a LinkedIn post draft for each successful blog post."
    )
    parser.add_argument(
        "-a", "--auto",
        action="store_true", # Makes it a flag, default False
        help="Enable auto mode: Skips user confirmation and adds a 5-minute delay between posts."
    )
    parser.add_argument(
        "--provider",
        default="webflow",
        choices=["webflow", "framer-sheets"],
        help="CMS provider to use: webflow or framer-sheets (default: framer-sheets)." # <-- Updated the help text
    )
    args = parser.parse_args()

    if args.num_posts < 1:
        print("Error: Number of posts must be at least 1.")
    else:
        main(args.num_posts, args.linkedin, args.auto, args.provider)