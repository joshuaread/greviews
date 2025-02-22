import os
import base64
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve the API key
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')

# Optional: Check if the key is missing
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("Missing GOOGLE_MAPS_API_KEY environment variable")

import requests
from flask import Flask, render_template, request, jsonify
import gspread
from google.oauth2.service_account import Credentials

# Initialize Flask app
app = Flask(__name__)

# Load Google Maps API key from environment variables (already handled above, no need to redefine)
# GOOGLE_MAPS_API_KEY = os.environ['GOOGLE_MAPS_API_KEY']  # Remove or comment this out to avoid redundancy

# Set up Google Sheets client using base64-decoded environment variable
# Decode service account JSON from environment variable
service_account_json = base64.b64decode(os.environ['SERVICE_ACCOUNT_JSON']).decode('utf-8')
creds = Credentials.from_service_account_info(json.loads(service_account_json), scopes=['https://www.googleapis.com/auth/spreadsheets'])
client = gspread.authorize(creds)
sheet = client.open('DPC Reviews').sheet1  # Access the "DPC Reviews" sheet

# Function to geocode a zip code into latitude and longitude
def geocode_zip(zip_code):
    url = f'https://maps.googleapis.com/maps/api/geocode/json?address={zip_code}&key={GOOGLE_MAPS_API_KEY}'
    response = requests.get(url).json()
    if response['status'] == 'OK':
        location = response['results'][0]['geometry']['location']
        return location['lat'], location['lng']
    return None

# Function to search for businesses near a location
def search_places(lat, lng, search_term, radius=32186):  # 20 miles = ~32,186 meters
    url = f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius={radius}&keyword={search_term}&key={GOOGLE_MAPS_API_KEY}'
    response = requests.get(url).json()
    if response['status'] == 'OK':
        return response['results']
    return []

# Function to get detailed information, including reviews, for a place
def get_place_details(place_id):
    url = f'https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,formatted_address,rating,reviews&key={GOOGLE_MAPS_API_KEY}'
    response = requests.get(url).json()
    if response['status'] == 'OK':
        return response['result']
    return None

# Home route: Display the input form or process the search
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        zip_code = request.form['zip_code']
        search_term = request.form['search_term']
        
        # Geocode the zip code
        location = geocode_zip(zip_code)
        if not location:
            return "Invalid zip code. Please try again.", 400
        
        lat, lng = location
        # Search for businesses
        places = search_places(lat, lng, search_term)
        if not places:
            return "No businesses found for the given search term and zip code.", 404
        
        # Collect results
        results = []
        for place in places:
            details = get_place_details(place['place_id'])
            if details and 'reviews' in details:
                for review in details['reviews']:
                    results.append({
                        'company_name': details['name'],
                        'location': details['formatted_address'],
                        'stars': review['rating'],
                        'review_text': review['text']
                    })
        
        if not results:
            return "No reviews found for the businesses in this area.", 404
        
        return render_template('results.html', results=results)
    
    return render_template('index.html')

# Export route: Push results to Google Sheet
@app.route('/export', methods=['POST'])
def export():
    results = request.json['results']
    for result in results:
        sheet.append_row([
            result['company_name'],
            result['location'],
            result['stars'],
            result['review_text']
        ])
    return jsonify({"message": "Exported successfully"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))