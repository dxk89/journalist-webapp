# AI Journalist Bot v4.7 - Web Server Backend

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



def get_metadata_prompt(article_title, article_body):

    """Creates the detailed prompt for generating CMS metadata."""

    publications = "Blog, Africa Blog, Asia Blog, Balkan Blog, Baltic Blog, Bucharest Blog, Caucasus Blog, Central Asia Blog, Istanbul Blog, Kyiv Blog, LatAm Blog, Minsk Blog, Moscow Blog, Tehran Blog, Video Blog, Visegrad Blog, Global Today, Africa Today, Eastern Africa, Burundi Today, Comoros Today, Djibouti Today, Eritrea Today, Ethiopia Today, Kenya Today, Madagascar Today, Malawi Today, Mauritius Today, Mayotte Today, Mozambique Today, Réunion Today, Rwanda Today, Seychelles Today, Somalia Today, Tanzania Today, Uganda Today, Zambia Today, Zimbabwe Today, Middle Africa, Angola Today, Cameroon Today, Central African Republic Today, Chad Today, Democratic Republic of the Congo Today, Equatorial Guinea Today, Gabon Today, Republic of the Congo Today, São Tomé and Príncipe Today, Northern Africa, Algeria Today, Egypt Today, Libya Today, Middle East & N.Africa Today, Morocco Today, North Africa Today, South Sudan Today, Sudan Today, Tunisia Today, Western Sahara Today, Southern Africa, Botswana Today, Eswatini Today, Lesotho Today, Namibia Today, South Africa Today, Swaziland, Western Africa, Benin Today, Burkina Faso, Cape Verde Today, Gambia Today, Ghana Today, Guinea Today, Guinea-Bissau Today, Ivory Coast Today, Liberia Today, Mali Today, Mauritania Today, Niger Today, Nigeria Today, Saint Helena, Ascension and Tristan da Cunha Today, Senegal Today, Sierra Leone Today, Togo Today, Asia Today, Bahrain, Bangladesh, Bhutan, Brunei, Cambodia, China, East Timor, Hong Kong, India, Indonesia, Japan, Laos, Macao, Malaysia, Maldives, Mynmar, Nepal Today, North Korea, Pakistan, Papua new Guinea, Philippines, Singapore, South Korea, Sri Lanka, Taiwan, Thailand, Vietnam, EU Today, Baltic States Today, Bulgaria Today, Croatia Today, Czech Republic Today, Hungary Today, Poland Today, Romania Today, Slovakia Today, Slovenia Today, Eurasia Today, Afghanistan Today, Albania Today, Armenia Today, Azerbaijan Today, Belarus Today, Bosnia and Herzegovina Today, Georgia Today, Kazakhstan Today, Kosovo Today, Kyrgyzstan Today, Moldova Today, Mongolia Today, Montenegro Today, North Macedonia Today, Russia Today, Serbia Today, Tajikistan Today, Turkey Sectors and Companies Today, Turkey Today, Turkmenistan Today, Ukraine Today, Uzbekistan Today, LatAm Today, Argentina, Belize, Bolivia, Brazil, Caribbean Islands, Chile, Colombia, Costa Rica, Cuba, Ecuador, El Salvador, French Guiana, Guatemala, Guyana, Haiti, Honduras, Mexico, Nicaragua, Panama, Paraguay, Peru, Suriname, Uruguay, Venezuela, Middle East Today, Asia Banking, Asia Credit, Asia Energy, Asia Infrastructure, Asia M&A and investment review, Asia Metals and mining, Asia Telecoms & IT, Bahrain, Iran, Iraq, Israel, Jordan, Kuwait, Lebanon, Oman, Palestine, Qatar, Saudi Arabia, Syrian Arab Republic, United Arab Emirates, Yemen, Rest of the world, USA & Canada, NewsBase, AfrElec, AfrOil, AsiaElec, AsianOil, DMEA, ENERGO, EurOil, FSUOGM, GLNG, LatAmOil, MEOG, NorthAmOil, REM, Other, Africa Credit, Africa Energy, Africa Infrastructure, African Banking Review, African M&A and Investments Review, African Mining Review, African Telecom & IT Review, Asia Banking, Asia Credit, Asia Energy, Asia Infrastructure, Asia M&A and investment review, Asia Metals and mining, Asia Telecoms & IT, bne:Banker, bne:Credit, bne:Infrastructure, Bricks & Mortar, CEE Energy News Watch, CEE Telecoms/Media/IT News Watch, Conference Call, Latam Banking, Latam Credit, Latam Energy, Latam Infrastructure, Latam M&A and investment review, Latam Metals and mining"

    countries = "Africa, Eastern Africa, Burundi, Comoros, Djibouti, Eritrea, Ethiopia, Kenya, Madagascar, Malawi, Mauritius, Mayotte, Mozambique, Réunion, Rwanda, Seychelles, Somalia, Tanzania, Uganda, Zambia, Zimbabwe, Middle Africa, Angola, Cameroon, Central African Republic, Chad, Congo, Congo, Democratic Republic of the, Equatorial Guinea, Gabon, Sao Tome and Principe, Northern Africa, Algeria, Egypt, Libya, Morocco, South Sudan, Sudan, Tunisia, Western Sahara, Southern Africa, Botswana, Lesotho, Namibia, South Africa, Swaziland, Western Africa, Benin, Burkina Faso, Cape Verde, Cote d'Ivoire, Gambia, Ghana, Guinea, Guinea-Bissau, Liberia, Mali, Mauritania, Niger, Nigeria, Saint Helena, Ascension and Tristan da Cunha, Senegal, Sierra Leone, Togo, Americas, Latin America and the Caribbean, Caribbean, Anguilla, Antigua and Barbuda, Aruba, Bahamas, Barbados, Bonaire, Saint Eustatius and Saba, British Virgin Islands, Cayman Islands, Cuba, Curaçao, Dominica, Dominican Republic, Grenada, Guadeloupe, Haiti, Jamaica, Martinique, Montserrat, Puerto Rico, Saint Kitts and Nevis, Saint Lucia, Saint Martin, Saint Vincent and the Grenadines, Saint-Barthélemy, Sint Maarten, Trinidad and Tobago, Turks and Caicos Islands, United States Virgin Islands, Central America, Belize, Costa Rica, El Salvador, Guatemala, Honduras, Mexico, Nicaragua, Panama, South America, Argentina, Bolivia, Brazil, Chile, Colombia, Ecuador, Falkland Islands (Malvinas), French Guiana, Guyana, Paraguay, Peru, Suriname, Uruguay, Venezuela, Northern America, Bermuda, Canada, Greenland, Saint Pierre and Miquelon, United States of America, Asia, Central Asia, Armenia, Kazakhstan, Kyrgyzstan, Tajikistan, Turkmenistan, Uzbekistan, Eastern Asia, China, Hong Kong, Macao, Japan, Korea, Democratic People's Republic of, Korea, Republic of, Mongolia, Taiwan, South-Eastern Asia, Brunei Darussalam, Cambodia, Indonesia, Lao People's Democratic Republic, Laos, Malaysia, Myanmar, Papua New Guinea, Philippines, Singapore, Thailand, Timor-Leste, Viet Nam, Southern Asia, Afghanistan, Bangladesh, Bhutan, India, Iran (Islamic Republic of), Maldives, Nepal, Pakistan, Sri Lanka, Western Asia, Armenia, Azerbaijan, Bahrain, Georgia, Iraq, Israel, Jordan, Kuwait, Lebanon, Oman, Palestinian Territory, Occupied, Qatar, Saudi Arabia, Syrian Arab Republic, Turkey, United Arab Emirates, Yemen, Europe, Eastern Europe, Belarus, Bulgaria, Cyprus, Czech Republic, Hungary, Moldova, Republic of, Poland, Romania, Russian Federation, Slovak Republic, Ukraine, Northern Europe, Aland Islands, Channel Islands, Denmark, Estonia, Faeroe Islands, Finland, Guernsey, Iceland, Ireland, Jersey, Latvia, Lithuania, Man, Isle of, Norway, Svalbard and Jan M
