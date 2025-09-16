# AI Journalist Bot v4.16 - Web Server Backend
import threading
import time
import json
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select
import requests
from bs4 import BeautifulSoup
import os

# --- Flask App Setup ---
app = Flask(__name__)
CORS(app)

# --- Logging ---
def log_message(message):
    """Prints a message with a timestamp. This will show up in Render logs."""
    timestamp = time.strftime('%H:%M:%S')
    print(f"{timestamp} - {message}", flush=True)

# --- AI Helper Functions ---
def fetch_url_content(url, log_func):
    """Scrapes the text content from a given URL."""
    if not url or not url.startswith('http'):
        return None
    log_func(f"🕸️ Fetching content from {url}...")
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text = ' '.join(p.get_text() for p in soup.find_all('p'))
        log_func(f"✅ Successfully scraped {len(text)} characters.")
        return text
    except Exception as e:
        log_func(f"🔥 URL scraping failed: {e}")
        return None

def call_gemini(prompt, api_key, step_name, log_func):
    """Calls the Gemini API and returns the JSON response."""
    log_func(f"🧠 Contacting Google Gemini for {step_name}...")
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(api_url, json=payload, timeout=120)
        response.raise_for_status()
        text_response = response.json()['candidates'][0]['content']['parts'][0]['text']
        start_index = text_response.find('{')
        end_index = text_response.rfind('}')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            clean_json_text = text_response[start_index:end_index+1]
            log_func(f"✅ Gemini response received for {step_name}.")
            return json.loads(clean_json_text)
        else:
            log_func(f"🔥 Gemini API Error during {step_name}: Could not find valid JSON.")
            return None
    except Exception as e:
        log_func(f"🔥 Gemini API Error during {step_name}: {e}")
        return None

def call_openai(prompt, api_key, step_name, log_func):
    """Calls the OpenAI API and returns the JSON response."""
    log_func(f"🧠 Contacting OpenAI (ChatGPT) for {step_name}...")
    api_url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        json_response_text = response.json()['choices'][0]['message']['content']
        log_func(f"✅ OpenAI response received for {step_name}.")
        return json.loads(json_response_text)
    except Exception as e:
        log_func(f"🔥 OpenAI API Error during {step_name}: {e}")
        return None

# --- CHANGE START: Updated prompts to use Checkbox IDs for Countries as well ---
def get_metadata_prompt(article_title, article_body):
    """Creates the detailed prompt for generating CMS metadata."""
    
    publication_ids = """
    "Blog": "edit-field-publication-und-0-2971-2971",
    "Africa Blog": "edit-field-publication-und-0-2971-2971-children-3523-3523",
    "Asia Blog": "edit-field-publication-und-0-2971-2971-children-3524-3524",
    "Global Today": "edit-field-publication-und-0-2972-2972",
    "Africa Today": "edit-field-publication-und-0-2972-2972-children-1008-1008",
    "Asia Today": "edit-field-publication-und-0-2972-2972-children-3159-3159",
    "EU Today": "edit-field-publication-und-0-2972-2972-children-2975-2975",
    "Eurasia Today": "edit-field-publication-und-0-2972-2972-children-3280-3280",
    "LatAm Today": "edit-field-publication-und-0-2972-2972-children-3174-3174",
    "Middle East Today": "edit-field-publication-und-0-2972-2972-children-3310-3310",
    "NewsBase": "edit-field-publication-und-0-2973-2973"
    """

    industry_ids = """
    "Oil & Gas Drilling": "edit-field-industry-und-0-443-443-children-457-457-children-482-482-children-552-552",
    "Oil & Gas Equipment & Services": "edit-field-industry-und-0-443-443-children-457-457-children-482-482-children-553-553",
    "Integrated Oil & Gas": "edit-field-industry-und-0-443-443-children-457-457-children-483-483-children-554-554",
    "Oil & Gas Exploration & Production": "edit-field-industry-und-0-443-443-children-457-457-children-483-483-children-555-555",
    "Oil & Gas Refining & Marketing": "edit-field-industry-und-0-443-443-children-457-457-children-483-483-children-556-556",
    "Oil & Gas Storage & Transportation": "edit-field-industry-und-0-443-443-children-457-457-children-483-483-children-557-557",
    "Coal & Consumable Fuels": "edit-field-industry-und-0-443-443-children-457-457-children-483-483-children-558-558",
    "Electric Utilities": "edit-field-industry-und-0-456-456-children-481-481-children-547-547-children-712-712",
    "Gas Utilities": "edit-field-industry-und-0-456-456-children-481-481-children-548-548-children-713-713",
    "Renewables": "edit-field-industry-und-0-456-456-children-481-481-children-2766-2766",
    "Steel": "edit-field-industry-und-0-444-444-children-458-458-children-487-487-children-571-571",
    "Gold": "edit-field-industry-und-0-444-444-children-458-458-children-487-487-children-569-569",
    "Aerospace & Defense": "edit-field-industry-und-0-445-445-children-459-459-children-489-489-children-574-574",
    "Automotive": "edit-field-industry-und-0-2767-2767-children-447-447-children-463-463-children-504-504",
    "Airlines": "edit-field-industry-und-0-445-445-children-462-462-children-499-499-children-594-594",
    "Banking": "edit-field-industry-und-0-451-451-children-473-473",
    "Capital Markets": "edit-field-industry-und-0-531-531",
    "Insurance": "edit-field-industry-und-0-451-451-children-475-475",
    "Real Estate": "edit-field-industry-und-0-451-451-children-476-476",
    "e-commerce & IT": "edit-field-industry-und-0-2768-2768",
    "Telecommunication Services": "edit-field-industry-und-0-2768-2768-children-455-455",
    "Cryptocurrency & Fintech": "edit-field-industry-und-0-2768-2768-children-3113-3113",
    "Health care & Pharmaceuticals": "edit-field-industry-und-0-450-450"
    """
    
    country_ids = """
    "Africa": "edit-field-country-und-0-720-720",
    "Eastern Africa": "edit-field-country-und-0-720-720-children-721-721",
    "Kenya": "edit-field-country-und-0-720-720-children-721-721-children-727-727",
    "Nigeria": "edit-field-country-und-0-720-720-children-766-766-children-779-779",
    "South Africa": "edit-field-country-und-0-720-720-children-760-760-children-764-764",
    "Americas": "edit-field-country-und-0-784-784",
    "Latin America and the Caribbean": "edit-field-country-und-0-784-784-children-785-785",
    "Brazil": "edit-field-country-und-0-784-784-children-785-785-children-824-824-children-827-827",
    "Mexico": "edit-field-country-und-0-784-784-children-785-785-children-815-815-children-821-821",
    "Northern America": "edit-field-country-und-0-784-784-children-839-839",
    "United States of America": "edit-field-country-und-0-784-784-children-839-839-children-844-844",
    "Canada": "edit-field-country-und-0-784-784-children-839-839-children-841-841",
    "Asia": "edit-field-country-und-0-845-845",
    "Central Asia": "edit-field-country-und-0-845-845-children-846-846",
    "Kazakhstan": "edit-field-country-und-0-845-845-children-846-846-children-847-847",
    "Uzbekistan": "edit-field-country-und-0-845-845-children-846-846-children-851-851",
    "Eastern Asia": "edit-field-country-und-0-845-845-children-852-852",
    "China": "edit-field-country-und-0-845-845-children-852-852-children-853-853",
    "Japan": "edit-field-country-und-0-845-845-children-852-852-children-856-856",
    "Southern Asia": "edit-field-country-und-0-845-845-children-861-861",
    "India": "edit-field-country-und-0-845-845-children-861-861-children-865-865",
    "Iran (Islamic Republic of)": "edit-field-country-und-0-845-845-children-861-861-children-866-866",
    "Pakistan": "edit-field-country-und-0-845-845-children-861-861-children-869-869",
    "Western Asia": "edit-field-country-und-0-845-845-children-883-883",
    "Saudi Arabia": "edit-field-country-und-0-845-845-children-883-883-children-897-897",
    "Turkey": "edit-field-country-und-0-845-845-children-883-883-children-899-899",
    "United Arab Emirates": "edit-field-country-und-0-845-845-children-883-883-children-900-900",
    "Europe": "edit-field-country-und-0-902-902",
    "Eastern Europe": "edit-field-country-und-0-902-902-children-903-903",
    "Poland": "edit-field-country-und-0-902-902-children-903-903-children-909-909",
    "Romania": "edit-field-country-und-0-902-902-children-903-903-children-910-910",
    "Russian Federation": "edit-field-country-und-0-902-902-children-903-903-children-911-911",
    "Ukraine": "edit-field-country-und-0-902-902-children-903-903-children-913-913",
    "Western Europe": "edit-field-country-und-0-902-902-children-950-950",
    "Germany": "edit-field-country-und-0-902-902-children-950-950-children-954-954"
    """

    return f"""
    You are an expert sub-editor. Your response must be ONLY a valid JSON object.
    Based on the article, fill in the metadata using these keys: "weekly_title_value", "website_callout_value", "social_media_callout_value", "seo_title_value", "seo_description_value", "seo_keywords_value", "daily_subject_value", "key_point_value", "publication_id_selections", "industry_id_selections", "country_id_selections".

    RULES FOR CHECKBOX SELECTIONS (ID-BASED):
    - The JSON response for "publication_id_selections", "industry_id_selections", and "country_id_selections" must be an ARRAY of STRINGS, where each string is the ID of a checkbox to be selected.
    - Choose at least one publication ID.
    - For industries, choose ONLY the IDs of the most specific sub-sections.
    - For countries, choose the IDs for the specific country and its parent regions.
    
    AVAILABLE PUBLICATION IDs:
    {{ {publication_ids} }}

    AVAILABLE INDUSTRY IDs (Choose only specific sub-sections):
    {{ {industry_ids} }}

    AVAILABLE COUNTRY IDs:
    {{ {country_ids} }}

    RULES FOR DROPDOWN SELECTIONS:
    - daily_subject_value: Choose ONE from ["Macroeconomic News", "Banking And Finance", "Companies and Industries", "Political"]
    - key_point_value: Choose ONE from ["Yes", "No"].

    ARTICLE FOR ANALYSIS:
    Article Title: "{article_title}"
    Article Body: "{article_body}"
    """
# --- CHANGE END ---

def remove_non_bmp_chars(text):
    """Removes characters that ChromeDriver can't handle (e.g., emojis)."""
    if not isinstance(text, str):
        return text
    return "".join(c for c in text if ord(c) <= 0xFFFF)

def tick_checkboxes_by_id(driver, id_list, log_func):
    """Finds and ticks checkboxes directly by their ID."""
    if not id_list:
        return
    log_func(f"   - Selecting checkboxes by ID...")
    for checkbox_id in id_list:
        try:
            checkbox = driver.find_element(By.ID, checkbox_id)
            if not checkbox.is_selected():
                driver.execute_script("arguments[0].click();", checkbox)
                log_func(f"       - Ticked '{checkbox_id}'")
        except Exception:
            log_func(f"     - ⚠️ Could not find or tick checkbox with ID '{checkbox_id}'")

def select_dropdown_option(driver, element_id, value, log_func, field_name):
    """Selects an option from a dropdown by its visible text."""
    try:
        if value and value.lower().strip() != "- none -":
            select_element = driver.find_element(By.ID, element_id)
            select_obj = Select(select_element)
            select_obj.select_by_visible_text(value)
            log_func(f"   - Selected {field_name}: '{value}'")
    except Exception as e:
        log_func(f"   - ⚠️ Could not select {field_name} ('{value}'): {e}")

def run_bot_logic_worker(config_data):
    """The main function that performs the browser automation."""
    log_func = log_message
    
    log_func("🤖 Bot thread started. Phase 1: Generating all article content...")
    ai_model = config_data.get('ai_model', 'gemini')
    if ai_model == 'openai':
        api_key = config_data.get('openai_api_key')
        ai_call_function = call_openai
        log_func("🤖 Using OpenAI (ChatGPT) model for generation.")
    else:
        api_key = config_data.get('gemini_api_key')
        ai_call_function = call_gemini
        log_func("🤖 Using Google Gemini model for generation.")

    articles_to_post = []
    for i in range(1, 4):
        source_url = config_data.get(f'source_url_{i}')
        prompt = config_data.get(f'prompt_{i}')
        if not source_url or not prompt:
            continue
        log_func(f"--- Preparing Article {i} from URL: {source_url} ---")
        scraped_text = fetch_url_content(source_url, log_func)
        if not scraped_text:
            log_func(f"🔥 Skipping Article {i}: Could not fetch content.")
            continue
        log_func("--- AI Step 1: Generating Article ---")
        article_prompt = f'You are an expert journalist. Respond with a JSON object with two keys: "title" and "body". Based on the web content below, {prompt}.\n\nWeb Content:\n---\n{scraped_text[:8000]}\n---'
        article_data = ai_call_function(article_prompt, api_key, "article generation", log_func)
        if not article_data:
            log_func(f"🔥 Skipping Article {i}: Failed to generate article content.")
            continue
        log_func("--- AI Step 2: Generating Metadata ---")
        article_title = article_data.get("title", "")
        article_body = article_data.get("body", "")
        metadata_prompt = get_metadata_prompt(article_title, article_body)
        metadata = ai_call_function(metadata_prompt, api_key, "metadata generation", log_func)
        if not metadata:
            log_func(f"🔥 Skipping Article {i}: Failed to generate metadata.")
            continue
        final_article_data = {"title_value": article_title, "body_value": article_body, **metadata}
        articles_to_post.append(final_article_data)
        log_func(f"✅ Content for Article {i} is ready.")

    if not articles_to_post:
        log_func("No articles were generated. Stopping.")
        log_func("🤖 Bot thread finished.")
        return

    log_func(f"✅ Phase 1 Complete. {len(articles_to_post)} article(s) ready.")
    log_func("🚀 Phase 2: Starting browser automation...")
    driver = None
    try:
        chrome_options = webdriver.ChromeOptions()
        IS_RENDER = os.environ.get('RENDER', False)
        if IS_RENDER:
            log_func("🚀 Running in production mode (Render).")
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            driver = webdriver.Chrome(options=chrome_options)
        else:
            log_func("🖥️ Running in local mode for debugging.")
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(15)

        log_func("Navigating to login URL...")
        driver.get(config_data.get('login_url'))
        log_func("Entering credentials...")
        driver.find_element(By.ID, "edit-name").send_keys(config_data.get('username'))
        driver.find_element(By.ID, "edit-pass").send_keys(config_data.get('password'))
        log_func("Clicking login button...")
        driver.find_element(By.ID, "edit-submit").click()
        time.sleep(4)
        log_func("✅ Login successful.")
        
        for idx, article_content in enumerate(articles_to_post):
            log_func(f"--- Posting Article {idx + 1}/{len(articles_to_post)} ---")
            log_func("Navigating to the 'Add Article' page...")
            driver.get(config_data.get('add_article_url'))
            time.sleep(3)
            log_func("📝 Filling article form...")
            
            driver.find_element(By.ID, "edit-title").send_keys(remove_non_bmp_chars(article_content.get('title_value', '')))
            driver.find_element(By.ID, "edit-field-weekly-title-und-0-value").send_keys(remove_non_bmp_chars(article_content.get('weekly_title_value', '')))
            driver.find_element(By.ID, "edit-field-website-callout-und-0-value").send_keys(remove_non_bmp_chars(article_content.get('website_callout_value', '')))
            driver.find_element(By.ID, "edit-field-social-media-callout-und-0-value").send_keys(remove_non_bmp_chars(article_content.get('social_media_callout_value', '')))
            driver.find_element(By.ID, "edit-metatags-und-title-value").send_keys(remove_non_bmp_chars(article_content.get('seo_title_value', '')))
            driver.find_element(By.ID, "edit-metatags-und-description-value").send_keys(remove_non_bmp_chars(article_content.get('seo_description_value', '')))
            driver.find_element(By.ID, "edit-metatags-und-keywords-value").send_keys(remove_non_bmp_chars(article_content.get('seo_keywords_value', '')))
            
            body_content = remove_non_bmp_chars(article_content.get('body_value', ''))
            escaped_body = json.dumps(body_content)
            driver.execute_script(f"CKEDITOR.instances['edit-body-und-0-value'].setData({escaped_body});")

            log_func("   - Expanding all collapsible sections...")
            try:
                expand_buttons = driver.find_elements(By.XPATH, "//div[contains(@class, 'term-reference-tree-collapsed')]//div[contains(@class, 'term-reference-tree-button')]")
                for button in expand_buttons:
                    driver.execute_script("arguments[0].click();", button)
                    time.sleep(0.1)
                log_func("   - All sections expanded.")
            except Exception as e:
                log_func(f"   - ⚠️ Could not expand sections: {e}")
            
            # --- CHANGE START: Use new ID-based function for all checkboxes ---
            tick_checkboxes_by_id(driver, article_content.get('country_id_selections'), log_func)
            tick_checkboxes_by_id(driver, article_content.get('publication_id_selections'), log_func)
            tick_checkboxes_by_id(driver, article_content.get('industry_id_selections'), log_func)
            # --- CHANGE END ---

            select_dropdown_option(driver, 'edit-field-subject-und', article_content.get('daily_subject_value'), log_func, "Daily Subject")
            select_dropdown_option(driver, 'edit-field-key-und', article_content.get('key_point_value'), log_func, "Key Point")
            select_dropdown_option(driver, 'edit-field-africa-daily-section-und', article_content.get('africa_daily_section_value'), log_func, "Africa Daily Section")
            select_dropdown_option(driver, 'edit-field-cee-middle-east-africa-tod-und', article_content.get('cee_news_watch_section_value'), log_func, "CEE News Watch Section")
            select_dropdown_option(driver, 'edit-field-middle-east-n-africa-today-und', article_content.get('n_africa_today_section_value'), log_func, "N.Africa Today Section")
            select_dropdown_option(driver, 'edit-field-middle-east-today-section-und', article_content.get('middle_east_today_section_value'), log_func, "Middle East Today Section")
            select_dropdown_option(driver, 'edit-field-asia-today-sections-und', article_content.get('asia_today_section_value'), log_func, "Asia Today Section")
            select_dropdown_option(driver, 'edit-field-latam-today-und', article_content.get('latam_today_section_value'), log_func, "LatAm Today Section")

            save_button_id = config_data.get("save_button_id")
            if save_button_id:
                log_func("🚀 Clicking the final 'Save' button...")
                driver.find_element(By.ID, save_button_id).click()
                time.sleep(5)
                log_func(f"✅ Article {idx + 1} submitted successfully!")
            else:
                log_func("⚠️ Save button ID not configured. Form filled but not saved.")

            if idx < len(articles_to_post) - 1:
                log_func(f"--- Pausing for 10 seconds before next article ---")
                time.sleep(10)

        log_func("✅✅✅ Batch processing complete! ✅✅✅")

    except Exception as e:
        log_func(f"🔥🔥🔥 A critical error occurred in the main worker: {e}")
    finally:
        if driver:
            driver.quit()
        log_func("🤖 Bot thread finished.")

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run-bot', methods=['POST'])
def run_bot():
    config_data = request.json
    ai_model = config_data.get('ai_model')
    if ai_model == 'openai' and not config_data.get('openai_api_key'):
        return jsonify({'status': 'error', 'message': 'Missing OpenAI API Key.'}), 400
    if ai_model == 'gemini' and not config_data.get('gemini_api_key'):
        return jsonify({'status': 'error', 'message': 'Missing Gemini API Key.'}), 400
    
    thread = threading.Thread(target=run_bot_logic_worker, args=(config_data,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'success', 'message': 'Bot process started. Check the Logs tab in your Render dashboard for progress.'})

# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
