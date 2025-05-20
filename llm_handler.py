# llm_handler.py
"""
Handles interactions with the Google Generative AI (Gemini) API.

Provides functions to:
- Configure the Gemini client library.
- Generate the main blog post content (HTML).
- Generate metadata (title, excerpts, reading time, image description) as JSON.
- Generate a LinkedIn post draft.
"""

import os
import json
import time # Added for potential retries/delays
import google.generativeai as genai
# Import 'types' for accessing Content and GenerationConfig
# Import Part directly
from google.generativeai import types
# Removed direct import of Part

# Added for retry logic exception handling
from google.api_core import exceptions as core_exceptions

# --- Prompt Templates ---
# Moved prompt construction outside functions for easier modification

LINKEDIN_PROMPT_TEMPLATE = """
Analyze the following blog post content snippet intended for real estate appraisers:
--- START BLOG CONTENT SNIPPET ---
{blog_content_snippet}
--- END BLOG CONTENT SNIPPET ---

Based *only* on this blog post content, make a version that is 100 words shorter and change the words slightly.
1.  Introduce the post by mentioning a new blog article is available (e.g., "(Appraiser Name) just published a new article on our website...") a clear call to action directing readers to the full article using this exact URL:** {new_blog_post_url} Both the introduction as well as the call to action should be relevant to the content of this specific blog post. If there is no name in the orginal blog post. you can ommit it. 
4.  The original blog post mentioned these related topics/articles with the following URLs:
    {formatted_interlinks}
    If relevant to your summary and space permits, you *may* briefly mention any of these related topics and include its *full raw URL*. Do not use Markdown link formatting like [text](url).
5.  **Output Format:** Generate only the plain text for the new more concise version of the blog post. Ensure ALL URLs included in your response are the full, raw URLs (e.g., https://www.example.com/article). Do not use Markdown link formatting.
"""

METADATA_PROMPT_TEMPLATE = """Analyze the following HTML blog post content:

{html_content_snippet}
Use code with caution.
Python
(Content truncated if necessary)
Based only on the provided HTML content, generate a JSON object containing the following metadata fields:
title: A compelling and relevant title for the blog post (string).
excerpt_page: A concise summary suitable for a blog listing page (approx. 1-2 sentences, string). This will also be used to check against future post generation to avoid duplicates. Inlcude as many facts as you can about the blog so later you know what to not repeat. **Max 160 characters.**
excerpt_featured: A slightly shorter, punchier excerpt suitable for a featured post section (string, can be similar to excerpt_page but potentially shorter). **Max 120 Characters.**
reading_time: An estimated reading time in minutes (integer number).
image_description: A brief description (1-2 sentences) of an ideal featured image for this post, suitable for prompting an image generation model (string). Make it specific  to this post. 
Your response must be only the valid JSON object, enclosed in json tags. Do not include any other text, explanation, or preamble.
Example JSON format:
{{
  "title": "Example Blog Post Title",
  "excerpt_page": "This is a concise summary of the blog post content, suitable for listing pages.",
  "excerpt_featured": "Short, punchy excerpt for featured sections.",
  "reading_time": 5,
  "image_description": "A modern abstract illustration showing data streams flowing between different devices, symbolizing appraisal modernization. There should be absolutely no text or letters visible."
}}
Use code with caution.
Json
"""

# --- Configuration ---
# Attempt to load API key from environment variable set by python-dotenv in main.py
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Global variable to store uploaded file references
_uploaded_files = []

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 30

# List of PDF files to use as context
_CONTEXT_PDF_FILES = [
    "uad-lpp-readiness-overview-for-lenders.pdf",
    "uad_overview_fact_sheet.pdf",
    "Fannie Mae SG Update Nov 2024 (2).pdf",
    "uadexecutivesummary_fre_20181217.pdf",
    "Uniform Appraisal Dataset Overview.pdf",
    "GSE Experts Answer Your UAD Redesign Questions - Freddie Mac Single-Family.pdf",
    "uad-redesign-timeline.pdf",
    "Uniform Appraisal Dataset - Freddie Mac Single-Family.pdf",
    "Everything You Need to Know About the UAD 3.6 Rollout and Changes _ ValueLink Appraisal Management Software.pdf",
    "uad-lender-readiness-kit.pdf",
    "uad-redesign-snapshot.pdf",
    "Microsoft Word - Legacy Forms to Redesigned URAR Property Type Characteristics_2024-06-04.docx.pdf",
    "Fannie Mae FAQs Nov 2024 (1).pdf",
    "New-URAR-Appendix-D-1-Appendix-E-1-Report-Style-Guide-Supplement.pdf",
    # Add any other required PDFs here
]

# --- Client Configuration & File Upload ---

def configure_genai():
    """
    Configures the Google Generative AI library with the API key.

    Returns:
        bool: True if configuration was successful, False otherwise.
    """
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY environment variable not found.")
        return False
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("Gemini library configured successfully.")
        return True # Indicate success
    except Exception as e:
        print(f"ERROR: Failed to configure Gemini library: {e}")
        return False

def upload_context_files() -> bool:
    """
    Uploads the specified PDF files to use as context for generation.
    Stores the file objects in the global _uploaded_files list.

    Returns:
        bool: True if all files were uploaded successfully, False otherwise.
    """
    global _uploaded_files
    _uploaded_files = [] # Clear previous uploads if any
    print(f"Starting upload of {len(_CONTEXT_PDF_FILES)} context files...")

    all_successful = True
    for filename in _CONTEXT_PDF_FILES:
        print(f"  Uploading {filename}...")
        try:
            # Check if file exists locally first
            if not os.path.exists(filename):
                 print(f"  ERROR: File not found locally: {filename}")
                 all_successful = False
                 continue # Skip to the next file

            # Upload the file
            # Note: genai.upload_file automatically uses the configured API key
            uploaded_file = genai.upload_file(path=filename)

            # Basic check if upload seemed successful (has a name/uri)
            if uploaded_file and uploaded_file.name and uploaded_file.uri:
                 _uploaded_files.append(uploaded_file)
                 print(f"  Successfully uploaded {filename} as {uploaded_file.name}")
                 # Optional: Add a small delay to avoid hitting rate limits
                 # time.sleep(1)
            else:
                print(f"  ERROR: Failed to upload {filename}. Response: {uploaded_file}")
                all_successful = False

        except FileNotFoundError:
             print(f"  ERROR: File not found at path: {filename}")
             all_successful = False
        except Exception as e:
            print(f"  ERROR: An unexpected error occurred uploading {filename}: {e}")
            all_successful = False
            # Consider whether to stop all uploads on the first error

    if all_successful:
        print("All context files uploaded successfully.")
    else:
        print("ERROR: One or more context files failed to upload. Generation may lack context.")
        # Clean up potentially partially uploaded files if needed (optional)
        # for f in _uploaded_files:
        #     try: genai.delete_file(f.name)
        #     except Exception: pass

    return all_successful

# --- Content Generation Functions ---

def generate_html_body(model_name: str, base_prompt: str, previous_summaries: list[dict[str, str]]) -> str | None:
    """
    Generates the main blog post body as Markdown using the Gemini API,
    using the globally uploaded files as context.

    Args:
        model_name (str): The name of the Gemini model to use (e.g., 'gemini-1.5-pro').
        base_prompt (str): The core instructions and context for the blog post.
        previous_summaries (list[dict[str, str]]): A list of dictionaries, each containing
                                                    'summary' and 'url' of previous posts.

    Returns:
        str | None: The generated blog post body as a Markdown string, or None if an error occurs.
    """
    global _uploaded_files

    # Format the previous summaries for the prompt
    if previous_summaries:
        formatted_summaries = "\nPrevious Posts (Avoid repeating these specific topics; link if relevant):\n"
        for item in previous_summaries:
            formatted_summaries += f"  - Summary: {item['summary']} (URL: {item['url']})\n"
    else:
        formatted_summaries = "\nNo previous posts to reference."

    if not _uploaded_files:
        print("WARN: No context files were successfully uploaded. Generating without file context.")
        # Fallback to text-only prompt if files aren't available
        # summaries_text = "\n - ".join(previous_summaries) if previous_summaries else "None"
        full_prompt = f"""{base_prompt}

{formatted_summaries}

Generate the full blog post content based on the instructions and context provided above.

**Output Format:**
The output should be **only the blog post body formatted directly as GitHub Flavored Markdown**. Do not include preamble, title, or any text other than the Markdown content itself. Use standard Markdown syntax (e.g., # H1, ## H2, *, -, lists, **bold**, *italic*).
"""
        generation_contents = [full_prompt] # Simple list for text-only
    else:
        # Construct the prompt including file references and formatted summaries
        # summaries_text = "\n - ".join(previous_summaries) if previous_summaries else "None"
        final_text_prompt = f"""{base_prompt}

{formatted_summaries}

Generate the full blog post content based on the instructions and context provided above AND in the attached files.

**Output Format:**
The output should be **only the blog post body formatted directly as GitHub Flavored Markdown**. Do not include preamble, title, or any text other than the Markdown content itself. Use standard Markdown syntax (e.g., # H1, ## H2, *, -, lists, **bold**, *italic*).
"""
        # Build the parts list as dictionaries
        parts_data = []
        for file in _uploaded_files:
            parts_data.append({
                'file_data': {
                    'mime_type': file.mime_type,
                    'file_uri': file.uri
                }
            })
        # Append the final text prompt as a dictionary
        parts_data.append({'text': final_text_prompt})

        # The entire list of parts dictionaries forms the user content
        generation_contents = parts_data # Pass the list of dicts directly

    model = None # Initialize model variable
    response = None # Initialize response variable
    retries = 0
    while retries < MAX_RETRIES:
        try:
            # Create the model instance directly only if not already created
            if model is None:
                model = genai.GenerativeModel(model_name)

            # Configure generation parameters
            generation_config = types.GenerationConfig(
                temperature=0.7, # Adjust temperature as needed
            )

            print(f"Generating body using model: {model_name} with {{_uploaded_files and len(_uploaded_files)}} file(s) as context... (Attempt {retries + 1}/{MAX_RETRIES})")

            # --- ADDED PRINT STATEMENT ---
            print("\n--- Context for generate_html_body ---")
            if isinstance(generation_contents, list):
                # Print text part separately for readability if files are included
                for part in generation_contents:
                    if isinstance(part, dict) and 'text' in part:
                        print("--- Text Prompt Part ---")
                        print(part['text'])
                        print("--- (File Parts Omitted for Brevity) ---")
                        break # Assuming only one text part
                else: # If only file parts (unlikely but possible) or other structure
                    import pprint
                    pprint.pprint(generation_contents) # Pretty print the list structure
            else: # If it's just a string (no files uploaded)
                print(generation_contents)
            print("--- End Context for generate_html_body ---\n")
            # --- END ADDED PRINT STATEMENT ---

            # Call generate_content with the structured contents
            response = model.generate_content(
                contents=generation_contents, # Use the potentially multi-part contents
                generation_config=generation_config
            )

            # If successful, break the loop
            break

        except (core_exceptions.ResourceExhausted, core_exceptions.Aborted) as e:
            retries += 1
            print(f"WARN: Rate limit hit (429) or conflict during body generation. Retrying in {RETRY_DELAY_SECONDS}s... ({retries}/{MAX_RETRIES})")
            if retries >= MAX_RETRIES:
                print(f"ERROR: Max retries reached for body generation. Last error: {e}")
                # Try to print feedback if available
                if response and hasattr(response, 'prompt_feedback'):
                    print(f"Prompt Feedback: {response.prompt_feedback}")
                return None
            time.sleep(RETRY_DELAY_SECONDS)
        except Exception as e:
            print(f"ERROR: Failed to generate HTML body on attempt {retries + 1}: {e}")
            # Try to print feedback if available
            if response and hasattr(response, 'prompt_feedback'):
                 print(f"Prompt Feedback: {response.prompt_feedback}")
            return None # Don't retry on other errors

    # --- Process successful response (moved outside loop) ---
    if response is None:
        print("ERROR: No response received after retries or due to non-retryable error.")
        return None

    try:
        # Accessing the generated text (check response structure)
        if not response.candidates:
            print("ERROR: No candidates returned from LLM. Check prompt feedback.")
            try:
                print(f"Prompt Feedback: {response.prompt_feedback}")
            except AttributeError:
                print("Prompt feedback attribute not found.")
            return None

        if not response.candidates[0].content.parts:
            print("ERROR: No parts found in the first candidate's content.")
            try:
                print(f"Prompt Feedback: {response.prompt_feedback}")
                print(f"Finish Reason: {response.candidates[0].finish_reason}")
            except AttributeError:
                 print("Feedback/finish reason attributes not found.")
            return None

        markdown_output = response.candidates[0].content.parts[0].text
        # Simple clean-up: Remove potential markdown code block fences if present
        if markdown_output.strip().startswith("```markdown"):
            markdown_output = markdown_output.strip()[11:]
        elif markdown_output.strip().startswith("```"):
            markdown_output = markdown_output.strip()[3:]

        if markdown_output.strip().endswith("```"):
            markdown_output = markdown_output.strip()[:-3]

        markdown_output = markdown_output.strip()

        print("Markdown body generation successful.")
        return markdown_output

    except Exception as e:
        print(f"ERROR: Failed to generate HTML body processing response: {e}")
        return None

def generate_metadata_json(model_name: str, html_content: str) -> dict | None:
    """
    Generates metadata (title, excerpts, reading time, image description)
    as a JSON object based on the provided HTML content.

    Args:
        model_name (str): The name of the Gemini model to use.
        html_content (str): The HTML content of the blog post generated previously.

    Returns:
        dict | None: A dictionary containing the metadata, or None if an error occurs.
    """
    if not html_content:
        print("ERROR: Cannot generate metadata from empty HTML content.")
        return None

    # Use the template, truncating content if needed
    prompt = METADATA_PROMPT_TEMPLATE.format(html_content_snippet=html_content[:4000])

    model = None
    response = None
    retries = 0
    while retries < MAX_RETRIES:
        try:
            # Create the model instance directly
            if model is None:
                model = genai.GenerativeModel(model_name)

            # Configure generation specifically for JSON output
            generation_config = types.GenerationConfig(
                temperature=0.8, # Lower temperature for factual extraction
                response_mime_type="application/json" # Instruct model to output valid JSON
            )

            print(f"Generating metadata JSON using model: {model_name}... (Attempt {retries + 1}/{MAX_RETRIES})")

            # --- ADDED PRINT STATEMENT ---
            print("\n--- Context for generate_metadata_json ---")
            print(prompt)
            print("--- End Context for generate_metadata_json ---\n")
            # --- END ADDED PRINT STATEMENT ---

            # Call generate_content directly on the model instance
            response = model.generate_content(
                contents=[prompt], # Content should be a list
                generation_config=generation_config
            )
            # If successful, break the loop
            break

        except (core_exceptions.ResourceExhausted, core_exceptions.Aborted) as e:
            retries += 1
            print(f"WARN: Rate limit hit (429) or conflict during metadata generation. Retrying in {RETRY_DELAY_SECONDS}s... ({retries}/{MAX_RETRIES})")
            if retries >= MAX_RETRIES:
                print(f"ERROR: Max retries reached for metadata generation. Last error: {e}")
                if response and hasattr(response, 'prompt_feedback'):
                     print(f"Prompt Feedback: {response.prompt_feedback}")
                return None
            time.sleep(RETRY_DELAY_SECONDS)
        except Exception as e:
            print(f"ERROR: Failed to generate metadata JSON on attempt {retries + 1}: {e}")
            if response and hasattr(response, 'prompt_feedback'):
                 print(f"Prompt Feedback: {response.prompt_feedback}")
            return None # Don't retry on other errors

    # --- Process successful response --- 
    if response is None:
        print("ERROR: No response received for metadata after retries or due to non-retryable error.")
        return None

    try:
        # Extract and parse the JSON response
        if not response.candidates or not response.candidates[0].content.parts:
            print("ERROR: No valid response content received for metadata generation.")
            try:
                print(f"Prompt Feedback: {response.prompt_feedback}")
                if response.candidates:
                    print(f"Finish Reason: {response.candidates[0].finish_reason}")
            except AttributeError:
                print("Feedback/finish reason attributes not found.")
            return None

        # Use response.text shortcut which often handles simple text/JSON extraction
        json_string = response.text
        print("Raw JSON response received.")
        # print(f"Raw JSON string:\n{json_string}") # Uncomment for debugging

        metadata_dict = json.loads(json_string)
        print("Metadata JSON parsing successful.")

        # Basic validation
        expected_keys = ["title", "excerpt_page", "excerpt_featured", "reading_time", "image_description"]
        if not all(key in metadata_dict for key in expected_keys):
            print(f"WARNING: Metadata JSON is missing one or more expected keys: {expected_keys}")

        return metadata_dict

    except json.JSONDecodeError as json_err:
        print(f"ERROR: Failed to parse metadata JSON response: {json_err}")
        if 'json_string' in locals():
            print(f"Raw response text was:\n{json_string}")
        else:
            print("Could not retrieve raw response text.")
        return None
    except Exception as e:
        print(f"ERROR: Failed to generate metadata JSON processing response: {e}")
        return None

# --- UPDATED FUNCTION for LinkedIn Post ---

def generate_linkedin_post(
    model_name: str,
    blog_content_snippet: str,
    new_blog_post_url: str,
    interlinks: list[str]
) -> str | None:
    """
    Generates a draft LinkedIn post based on the blog content snippet,
    including the new post's URL and potentially related interlinks.

    Args:
        model_name (str): The name of the Gemini model to use.
        blog_content_snippet (str): A snippet of the Markdown content of the blog post.
        new_blog_post_url (str): The full URL of the newly generated blog post.
        interlinks (list[str]): A list of raw URLs extracted from the main blog post.

    Returns:
        str | None: The generated LinkedIn post text draft (with raw URLs), or None if an error occurs.
    """
    if not blog_content_snippet:
        print("ERROR: Cannot generate LinkedIn post from empty blog content snippet.")
        return None
    if not new_blog_post_url:
        print("ERROR: Cannot generate LinkedIn post without the new blog post URL.")
        return None

    # Format the interlinks for the prompt
    if interlinks:
        formatted_interlinks = "\n".join([f"- {link}" for link in interlinks])
    else:
        formatted_interlinks = "None provided."

    # Use the updated template
    prompt = LINKEDIN_PROMPT_TEMPLATE.format(
        blog_content_snippet=blog_content_snippet, # Use the full body passed from main.py
        new_blog_post_url=new_blog_post_url,
        formatted_interlinks=formatted_interlinks
    )

    model = None
    response = None
    retries = 0
    while retries < MAX_RETRIES:
        try:
            if model is None:
                model = genai.GenerativeModel(model_name)

            # Configure generation for text output
            generation_config = types.GenerationConfig(temperature=0.6) # Slightly lower temp for concise summary

            print(f"Generating LinkedIn post draft using model: {model_name}... (Attempt {retries + 1}/{MAX_RETRIES})")

            # --- ADDED PRINT STATEMENT ---
            print("\n--- Context for generate_linkedin_post ---")
            print(prompt)
            print("--- End Context for generate_linkedin_post ---\n")
            # --- END ADDED PRINT STATEMENT ---

            response = model.generate_content(
                contents=[prompt],
                generation_config=generation_config
            )
            break # Success

        except (core_exceptions.ResourceExhausted, core_exceptions.Aborted) as e:
            retries += 1
            print(f"WARN: Rate limit hit (429) or conflict during LinkedIn post generation. Retrying in {RETRY_DELAY_SECONDS}s... ({retries}/{MAX_RETRIES})")
            if retries >= MAX_RETRIES:
                print(f"ERROR: Max retries reached for LinkedIn post generation. Last error: {e}")
                return None
            time.sleep(RETRY_DELAY_SECONDS)
        except Exception as e:
            print(f"ERROR: Failed to generate LinkedIn post on attempt {retries + 1}: {e}")
            return None # Don't retry other errors

    # Process successful response
    if response is None:
        print("ERROR: No response received for LinkedIn post after retries or due to non-retryable error.")
        return None

    try:
        if not response.candidates or not response.candidates[0].content.parts:
            print("ERROR: No valid response content received for LinkedIn post generation.")
            # Try to print feedback if available
            if hasattr(response, 'prompt_feedback'): print(f"Prompt Feedback: {response.prompt_feedback}")
            if response.candidates and hasattr(response.candidates[0], 'finish_reason'): print(f"Finish Reason: {response.candidates[0].finish_reason}")
            return None

        linkedin_draft = response.candidates[0].content.parts[0].text.strip()
        print("LinkedIn post draft generated successfully.")
        return linkedin_draft

    except Exception as e:
        print(f"ERROR: Failed processing LinkedIn post response: {e}")
        return None