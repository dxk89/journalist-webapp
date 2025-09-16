# AI Journalist Bot v4.8 - Web Server Backend
import threading
import time
import json
import queue
from flask import Flask, render_template, request, jsonify, Response
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
log_queue = queue.Queue()

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
            log_func(f"🔥 Gemini API Error during {step_name}: Could not find a valid JSON object in the response.")
            log_func(f"   - Raw response: {text_response}")
            return None
    except Exception as e:
        log_func(f"🔥 Gemini API Error during {step_name}: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            log_func(f"   - Full API response text: {response.text}")
        return None

def call_openai(prompt, api_key, step_name, log_func):
    """Calls the OpenAI API and returns the JSON response."""
    log_func(f"🧠 Contacting OpenAI (ChatGPT) for {step_name}...")
    api_url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
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
        if 'response' in locals() and hasattr(response, 'text'):
            log_func(f"   - Full API response text: {response.text}")
        return None

# --- CHANGE START: Wrapped long strings in triple quotes ---
def get_metadata_prompt(article_title, article_body):
    """Creates the detailed prompt for generating CMS metadata."""
    publications = """Blog, Africa Blog, Asia Blog, Balkan Blog, Baltic Blog, Bucharest Blog, Caucasus Blog, Central Asia Blog, Istanbul Blog, Kyiv Blog, LatAm Blog, Minsk Blog, Moscow Blog, Tehran Blog, Video Blog, Visegrad Blog, Global Today, Africa Today, Eastern Africa, Burundi Today, Comoros Today, Djibouti Today, Eritrea Today, Ethiopia Today, Kenya Today, Madagascar Today, Malawi Today, Mauritius Today, Mayotte Today, Mozambique Today, Réunion Today, Rwanda Today, Seychelles Today, Somalia Today, Tanzania Today, Uganda Today, Zambia Today, Zimbabwe Today, Middle Africa, Angola Today, Cameroon Today, Central African Republic Today, Chad Today, Democratic Republic of the Congo Today, Equatorial Guinea Today, Gabon Today, Republic of the Congo Today, São Tomé and Príncipe Today, Northern Africa, Algeria Today, Egypt Today, Libya Today, Middle East & N.Africa Today, Morocco Today, North Africa Today, South Sudan Today, Sudan Today, Tunisia Today, Western Sahara Today, Southern Africa, Botswana Today, Eswatini Today, Lesotho Today, Namibia Today, South Africa Today, Swaziland, Western Africa, Benin Today, Burkina Faso, Cape Verde Today, Gambia Today, Ghana Today, Guinea Today, Guinea-Bissau Today, Ivory Coast Today, Liberia Today, Mali Today, Mauritania Today, Niger Today, Nigeria Today, Saint Helena, Ascension and Tristan da Cunha Today, Senegal Today, Sierra Leone Today, Togo Today, Asia Today, Bahrain, Bangladesh, Bhutan, Brunei, Cambodia, China, East Timor, Hong Kong, India, Indonesia, Japan, Laos, Macao, Malaysia, Maldives, Mynmar, Nepal Today, North Korea, Pakistan, Papua new Guinea, Philippines, Singapore, South Korea, Sri Lanka, Taiwan, Thailand, Vietnam, EU Today, Baltic States Today, Bulgaria Today, Croatia Today, Czech Republic Today, Hungary Today, Poland Today, Romania Today, Slovakia Today, Slovenia Today, Eurasia Today, Afghanistan Today, Albania Today, Armenia Today, Azerbaijan Today, Belarus Today, Bosnia and Herzegovina Today, Georgia Today, Kazakhstan Today, Kosovo Today, Kyrgyzstan Today, Moldova Today, Mongolia Today, Montenegro Today, North Macedonia Today, Russia Today, Serbia Today, Tajikistan Today, Turkey Sectors and Companies Today, Turkey Today, Turkmenistan Today, Ukraine Today, Uzbekistan Today, LatAm Today, Argentina, Belize, Bolivia, Brazil, Caribbean Islands, Chile, Colombia, Costa Rica, Cuba, Ecuador, El Salvador, French Guiana, Guatemala, Guyana, Haiti, Honduras, Mexico, Nicaragua, Panama, Paraguay, Peru, Suriname, Uruguay, Venezuela, Middle East Today, Asia Banking, Asia Credit, Asia Energy, Asia Infrastructure, Asia M&A and investment review, Asia Metals and mining, Asia Telecoms & IT, Bahrain, Iran, Iraq, Israel, Jordan, Kuwait, Lebanon, Oman, Palestine, Qatar, Saudi Arabia, Syrian Arab Republic, United Arab Emirates, Yemen, Rest of the world, USA & Canada, NewsBase, AfrElec, AfrOil, AsiaElec, AsianOil, DMEA, ENERGO, EurOil, FSUOGM, GLNG, LatAmOil, MEOG, NorthAmOil, REM, Other, Africa Credit, Africa Energy, Africa Infrastructure, African Banking Review, African M&A and Investments Review, African Mining Review, African Telecom & IT Review, Asia Banking, Asia Credit, Asia Energy, Asia Infrastructure, Asia M&A and investment review, Asia Metals and mining, Asia Telecoms & IT, bne:Banker, bne:Credit, bne:Infrastructure, Bricks & Mortar, CEE Energy News Watch, CEE Telecoms/Media/IT News Watch, Conference Call, Latam Banking, Latam Credit, Latam Energy, Latam Infrastructure, Latam M&A and investment review, Latam Metals and mining"""
    countries = """Africa, Eastern Africa, Burundi, Comoros, Djibouti, Eritrea, Ethiopia, Kenya, Madagascar, Malawi, Mauritius, Mayotte, Mozambique, Réunion, Rwanda, Seychelles, Somalia, Tanzania, Uganda, Zambia, Zimbabwe, Middle Africa, Angola, Cameroon, Central African Republic, Chad, Congo, Congo, Democratic Republic of the, Equatorial Guinea, Gabon, Sao Tome and Principe, Northern Africa, Algeria, Egypt, Libya, Morocco, South Sudan, Sudan, Tunisia, Western Sahara, Southern Africa, Botswana, Lesotho, Namibia, South Africa, Swaziland, Western Africa, Benin, Burkina Faso, Cape Verde, Cote d'Ivoire, Gambia, Ghana, Guinea, Guinea-Bissau, Liberia, Mali, Mauritania, Niger, Nigeria, Saint Helena, Ascension and Tristan da Cunha, Senegal, Sierra Leone, Togo, Americas, Latin America and the Caribbean, Caribbean, Anguilla, Antigua and Barbuda, Aruba, Bahamas, Barbados, Bonaire, Saint Eustatius and Saba, British Virgin Islands, Cayman Islands, Cuba, Curaçao, Dominica, Dominican Republic, Grenada, Guadeloupe, Haiti, Jamaica, Martinique, Montserrat, Puerto Rico, Saint Kitts and Nevis, Saint Lucia, Saint Martin, Saint Vincent and the Grenadines, Saint-Barthélemy, Sint Maarten, Trinidad and Tobago, Turks and Caicos Islands, United States Virgin Islands, Central America, Belize, Costa Rica, El Salvador, Guatemala, Honduras, Mexico, Nicaragua, Panama, South America, Argentina, Bolivia, Brazil, Chile, Colombia, Ecuador, Falkland Islands (Malvinas), French Guiana, Guyana, Paraguay, Peru, Suriname, Uruguay, Venezuela, Northern America, Bermuda, Canada, Greenland, Saint Pierre and Miquelon, United States of America, Asia, Central Asia, Armenia, Kazakhstan, Kyrgyzstan, Tajikistan, Turkmenistan, Uzbekistan, Eastern Asia, China, Hong Kong, Macao, Japan, Korea, Democratic People's Republic of, Korea, Republic of, Mongolia, Taiwan, South-Eastern Asia, Brunei Darussalam, Cambodia, Indonesia, Lao People's Democratic Republic, Laos, Malaysia, Myanmar, Papua New Guinea, Philippines, Singapore, Thailand, Timor-Leste, Viet Nam, Southern Asia, Afghanistan, Bangladesh, Bhutan, India, Iran (Islamic Republic of), Maldives, Nepal, Pakistan, Sri Lanka, Western Asia, Armenia, Azerbaijan, Bahrain, Georgia, Iraq, Israel, Jordan, Kuwait, Lebanon, Oman, Palestinian Territory, Occupied, Qatar, Saudi Arabia, Syrian Arab Republic, Turkey, United Arab Emirates, Yemen, Europe, Eastern Europe, Belarus, Bulgaria, Cyprus, Czech Republic, Hungary, Moldova, Republic of, Poland, Romania, Russian Federation, Slovak Republic, Ukraine, Northern Europe, Aland Islands, Channel Islands, Denmark, Estonia, Faeroe Islands, Finland, Guernsey, Iceland, Ireland, Jersey, Latvia, Lithuania, Man, Isle of, Norway, Svalbard and Jan Mayen Islands, Sweden, United Kingdom, Southern Europe, Albania, Andorra, Bosnia and Herzegovina, Croatia, Gibraltar, Greece, Holy See (Vatican City State), Italy, Kosovo, Malta, Montenegro, North Macedonia, Portugal, San Marino, Serbia, Slovenia, Spain, Western Europe, Austria, Belgium, France, Germany, Liechtenstein, Luxembourg, Monaco, Netherlands, Switzerland, Oceania, Australia and New Zealand, Australia, Christmas Island, Cocos (keeling) Islands, New Zealand, Norfolk Island, Melanesia, Fiji, New Caledonia, Papua New Guinea, Solomon Islands, Vanuatu, Micronesia, Guam, Kiribati, Marshall Islands, Micronesia, Federated States of, Nauru, Northern Mariana Islands, Palau, Polynesia, American Samoa, Cook Islands, French Polynesia, Niue, Pitcairn, Samoa, Tokelau, Tonga, Tuvalu, Wallis and Futuna Islands, Unclassified, Antarctica, Bouvet Island, British Indian Ocean Territory, French Southern Territories, Heard Island and McDonald Islands, South Georgia and the South Sandwich Islands, United States Minor Outlying Islands"""
    industries = """Energy, oil, gas & combustibles, Power, Renewables, Nuclear Utiltiies, Materials, Metals & Chemicals, Steel, Gold, Industrials, Aerospace & Defense, Automotive, Machinery, Transportation, Airlines, Consumer, Food & Staples Retailing, Banking, Finance, Capital Markets, Insurance, Real Estate, Tech, e-commerce & IT, Telecommunication Services, Cryptocurrency & Fintech, Health care & Pharmaceuticals"""

    return f"""
    You are an expert sub-editor for an emerging markets news publication. Your response will be parsed by a program, so you must respond with ONLY a valid JSON object with the exact keys specified.

    Based on the article below, fill in CMS metadata using the following keys: "weekly_title_value", "website_callout_value", "social_media_callout_value", "seo_title_value", "seo_description_value", "seo_keywords_value", "daily_subject_value", "key_point_value", "country_selections_value", "industry_selections_value", "publication_selections_value", "africa_daily_section_value", "cee_news_watch_section_value", "n_africa_today_section_value", "middle_east_today_section_value", "asia_today_section_value", "latam_today_section_value".

    RULES:
    - Be accurate and ensure your choices directly reflect the article's content.
    - For comma-separated checkbox selections, choose ONLY the country/countries the article is primarily about and any other countries explicitly mentioned.
    
    DROPDOWN OPTIONS:
    - daily_subject_value: Choose ONE from ["Macroeconomic News", "Banking And Finance", "Companies and Industries", "Political"]
    - key_point_value: Choose ONE from ["Yes", "No"]. Select "Yes" only if it is a major, market-moving story.
    - For the daily/regional sections below, select the relevant country if the article fits that publication. Otherwise, select "- None -".
    - africa_daily_section_value: Choose ONE from ["- None -", "Regional News", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi", "Cameroon", "Cape Verde", "Central African Republic", "Chad", "Comoros", "Congo", "Cote d'Ivoire", "Democratic Republic of Congo", "Djibouti", "Egypt", "Equatorial Guinea", "Eritrea", "Ethiopia", "Gabon", "Gambia", "Ghana", "Guinea", "Guinea-Bissau", "Kenya", "Lesotho", "Liberia", "Madagascar", "Malawi", "Mali", "Mauritania", "Mauritius", "Mayotte", "Morocco", "Mozambique", "Namibia", "Niger", "Nigeria", "Réunion", "Rwanda", "Saint Helena, Ascension and Tristan da Cunha", "Sao Tome and Principe", "Senegal", "Seychelles", "Sierra Leone", "Somalia", "South Africa", "South Sudan", "Sudan", "Swaziland", "Tanzania", "Togo", "Uganda", "Zambia", "Zimbabwe"]
    - cee_news_watch_section_value: Choose ONE from ["- None -", "Albania", "Armenia", "Azerbaijan", "Baltic States", "Belarus", "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Czech Republic", "Georgia", "Hungary", "Kazakhstan", "Kosovo", "Kyrgyzstan", "Moldova", "Montenegro", "North Macedonia", "Poland", "Romania", "Russia", "Serbia", "Slovakia", "Slovenia", "Tajikistan", "Turkey", "Turkmenistan", "Ukraine", "Uzbekistan"]
    - n_africa_today_section_value: Choose ONE from ["- None -", "Regional", "Algeria", "Bahrain", "Egypt", "Jordan", "Libya", "Morocco", "Syria", "Tunisia"]
    - middle_east_today_section_value: Choose ONE from ["- None -", "Bahrain", "Iran", "Iraq", "Israel", "Kuwait", "Lebanon", "Oman", "Palestine", "Qatar", "Saudia Arabia", "UAE", "Yemen"]
    - asia_today_section_value: Choose ONE from ["- None -", "Bangladesh", "Bhutan", "Brunei", "Cambodia", "China", "Hong Kong", "India", "Indonesia", "Japan", "Laos", "Malaysia", "Myanmar", "Nepal", "Pakistan", "Philippines", "Singapore", "South Korea", "Sri Lanka", "Taiwan", "Thailand", "Vietnam"]
    - latam_today_section_value: Choose ONE from ["- None -", "Argentina", "Belize", "Bolivia", "Brazil", "Chile", "Columbia", "Costa Rica", "Ecuador", "El Salvador", "French Guiana", "Guatemala", "Guyana", "Honduras", "Mexico", "Nicaragua", "Panama", "Paraguay", "Peru", "Suriname", "Uruguay", "Venezuela"]

    CHECKBOX OPTIONS (provide a comma-separated string):
    - country_selections_value: From this list: '{countries}'. **IMPORTANT**: If you select a country (e.g., 'Germany'), you MUST ALSO include all of its parent regions (e.g., 'Western Europe', 'Europe') in the list.
    - industry_selections_value: From this list: '{industries}'. **IMPORTANT**: If you select a sub-category (e.g., 'Steel'), you MUST ALSO include its parent category (e.g., 'Materials, Metals & Chemicals') in the list.
    - publication_selections_value: From this list: '{publications}'.

    ARTICLE FOR ANALYSIS:
    Article Title: "{article_title}"
    Article Body: "{article_body}"
    """
# --- CHANGE END ---

def run_bot_logic_worker(config_data, log_func):
    """The main function that performs the browser automation."""
    
    # --- Phase 1: Data Generation ---
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
        article_prompt = f'You are an expert journalist. Your response will be parsed by a program, so you must respond with ONLY a valid JSON object with two keys: "title" and "body". Based on the web content below, {prompt}.\n\nWeb Content:\n---\n{scraped_text[:8000]}\n---'
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

    # --- Phase 2: Browser Automation ---
    log_func(f"✅ Phase 1 Complete. {len(articles_to_post)} article(s) ready.")
    log_func("🚀 Phase 2: Starting browser automation...")
    driver = None
    try:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        driver = webdriver.Chrome(options=chrome_options)
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

            tick_checkboxes(driver, 'edit-field-country-und', article_content.get('country_selections_value'), log_func)
            tick_checkboxes(driver, 'edit-field-industry-und', article_content.get('industry_selections_value'), log_func)
            tick_checkboxes(driver, 'edit-field-publication-und', article_content.get('publication_selections_value'), log_func)

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
def log_message_to_queue(message):
    timestamp = time.strftime('%H:%M:%S')
    log_queue.put(f"{timestamp} - {message}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream-log')
def stream_log():
    def generate():
        while True:
            try:
                message = log_queue.get(timeout=10)
                yield f"data: {message}\n\n"
            except queue.Empty:
                yield ": keep-alive\n\n"
    return Response(generate(), mimetype='text/event-stream')

@app.route('/run-bot', methods=['POST'])
def run_bot():
    config_data = request.json
    ai_model = config_data.get('ai_model')
    if ai_model == 'openai' and not config_data.get('openai_api_key'):
        return jsonify({'status': 'error', 'message': 'Missing OpenAI API Key.'}), 400
    if ai_model == 'gemini' and not config_data.get('gemini_api_key'):
        return jsonify({'status': 'error', 'message': 'Missing Gemini API Key.'}), 400
    
    thread = threading.Thread(target=run_bot_logic_worker, args=(config_data, log_message_to_queue))
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'success', 'message': 'Bot process started.'})

# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print("AI Journalist Bot Server starting...")
    print(f"Open your web browser and go to http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
