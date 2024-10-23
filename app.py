from flask import Flask, request, send_file, jsonify, redirect
from flask_cors import CORS
import requests
from ics import Calendar, Event
from datetime import datetime
import io
import logging
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Get credentials from environment variables
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = 'https://backend-1-2x3i.onrender.com/oauth/callback'

# Validate required environment variables
if not CLIENT_ID or not CLIENT_SECRET:
    logging.error("Missing required environment variables. Please check .env file")
    raise ValueError("Missing required environment variables")

# Set up logging
logging.basicConfig(level=logging.INFO)

@app.route('/oauth/callback')
def oauth_callback():
    # Get the authorization code from the URL query parameter
    code = request.args.get('code')
    
    if not code:
        return jsonify({'error': 'Authorization code is missing'}), 400

    # Exchange the authorization code for an access token
    token_url = 'https://www.eventbrite.com/oauth/token'
    data = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'redirect_uri': REDIRECT_URI
    }

    # Send POST request to Eventbrite to get the access token
    response = requests.post(token_url, data=data)
    token_data = response.json()

    # Log the token exchange response for debugging
    logging.info(f'Token exchange response: {token_data}')

    # Get the access token from the response
    access_token = token_data.get('access_token')

    if access_token:
        # Redirect to the events page, passing the access token in the query
        return redirect(f'/events?access_token={access_token}')
    else:
        # Log the error if authorization failed
        error_description = token_data.get('error_description', 'Authorization failed')
        logging.error(f'Authorization failed: {error_description}')
        return jsonify({'error': 'Authorization failed', 'details': error_description}), 400

@app.route('/events')
def get_user_events():
    access_token = request.args.get('access_token')  # Access token passed via query parameter

    if not access_token:
        return jsonify({'error': 'Access token missing'}), 400

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    # Make request to Eventbrite API to get the user's events
    response = requests.get('https://www.eventbriteapi.com/v3/users/me/events/', headers=headers)
    
    # Log the event fetching response for debugging
    logging.info(f'Events fetch response: {response.status_code} {response.text}')

    if response.status_code != 200:
        return jsonify({'error': 'Failed to fetch events from Eventbrite', 'details': response.text}), response.status_code

    events_data = response.json()

    # Handle the response (return or process the events)
    if 'events' in events_data:
        return jsonify(events_data['events'])
    else:
        return jsonify({'error': 'No events found or API request failed'}), response.status_code

@app.route('/events/ical')
def download_ical():
    access_token = request.args.get('access_token')

    if not access_token:
        return jsonify({'error': 'Access token missing'}), 400

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get('https://www.eventbriteapi.com/v3/users/me/events/', headers=headers)
    
    # Log the iCal event fetching response for debugging
    logging.info(f'iCal fetch response: {response.status_code} {response.text}')

    if response.status_code != 200:
        return jsonify({'error': 'Failed to fetch events for iCal', 'details': response.text}), response.status_code

    events_data = response.json()

    if 'events' in events_data:
        calendar = Calendar()

        for event in events_data['events']:
            start_time = datetime.strptime(event['start']['utc'], '%Y-%m-%dT%H:%M:%SZ')
            end_time = datetime.strptime(event['end']['utc'], '%Y-%m-%dT%H:%M:%SZ')

            ical_event = Event()
            ical_event.name = event['name']['text']
            ical_event.begin = start_time
            ical_event.end = end_time
            ical_event.location = event['venue']['address']['localized_address_display'] if event.get('venue') else 'No location'
            ical_event.description = event['description']['text'] if event.get('description') else ''

            calendar.events.add(ical_event)

        # Generate iCal file in memory
        ical_file = io.StringIO(str(calendar))
        return send_file(io.BytesIO(ical_file.getvalue().encode()), as_attachment=True, download_name='eventbrite_events.ics', mimetype='text/calendar')

    return jsonify({'error': 'No events found'}), 404

if __name__ == '__main__':
    app.run(debug=True)
