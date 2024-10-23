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
    
    logging.info(f'Received callback with code: {code is not None}')
    
    if not code:
        logging.error('No authorization code received')
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

    # Log the token request data (excluding secret)
    logging.info(f'Requesting token with client_id: {CLIENT_ID} and redirect_uri: {REDIRECT_URI}')

    try:
        # Send POST request to Eventbrite to get the access token
        response = requests.post(token_url, data=data)
        token_data = response.json()
        
        # Log the token exchange response (excluding sensitive data)
        logging.info(f'Token exchange response status: {response.status_code}')
        logging.info(f'Token exchange response contains access_token: {"access_token" in token_data}')

        # Get the access token from the response
        access_token = token_data.get('access_token')

        if access_token:
            # Redirect to frontend with the access token
            frontend_url = "YOUR_FRONTEND_URL"  # Replace with your frontend URL
            return redirect(f'{frontend_url}?access_token={access_token}')
        else:
            # Log the error if authorization failed
            error_description = token_data.get('error_description', 'Authorization failed')
            logging.error(f'Authorization failed: {error_description}')
            return jsonify({
                'error': 'Authorization failed',
                'details': error_description
            }), 400
    except Exception as e:
        logging.error(f'Exception during token exchange: {str(e)}')
        return jsonify({'error': 'Server error during authorization'}), 500

@app.route('/events')
def get_user_events():
    access_token = request.args.get('access_token')  # Access token passed via query parameter

    if not access_token:
        return jsonify({'error': 'Access token missing'}), 400

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

     # First, get the user's ID
    user_response = requests.get(
        'https://www.eventbriteapi.com/v3/users/me/',
        headers=headers
    )
    
    # Log the user response for debugging
    logging.info(f'User fetch response: {user_response.status_code} {user_response.text}')

    if user_response.status_code != 200:
        return jsonify({
            'error': 'Failed to fetch user info from Eventbrite',
            'details': user_response.text
        }), user_response.status_code

    user_data = user_response.json()
    user_id = user_data['id']

    # Then get the user's events using their ID
    events_response = requests.get(
        f'https://www.eventbriteapi.com/v3/organizations/{user_id}/events/',
        headers=headers
    )
    
    # Log the event fetching response for debugging
    logging.info(f'Events fetch response: {events_response.status_code} {events_response.text}')

    if events_response.status_code != 200:
        return jsonify({
            'error': 'Failed to fetch events from Eventbrite',
            'details': events_response.text
        }), events_response.status_code

    events_data = events_response.json()

    return jsonify(events_data.get('events', []))

@app.route('/events/ical')
def download_ical():
    access_token = request.args.get('access_token')

    if not access_token:
        return jsonify({'error': 'Access token missing'}), 400

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

   # First, get the user's ID
    user_response = requests.get(
        'https://www.eventbriteapi.com/v3/users/me/',
        headers=headers
    )

    if user_response.status_code != 200:
        return jsonify({
            'error': 'Failed to fetch user info',
            'details': user_response.text
        }), user_response.status_code

    user_data = user_response.json()
    user_id = user_data['id']

    # Then get the user's events
    events_response = requests.get(
        f'https://www.eventbriteapi.com/v3/organizations/{user_id}/events/',
        headers=headers
    )

    if events_response.status_code != 200:
        return jsonify({
            'error': 'Failed to fetch events',
            'details': events_response.text
        }), events_response.status_code

    events_data = events_response.json()

    if 'events' in events_data:
        calendar = Calendar()

        for event in events_data['events']:
            try:
                start_time = datetime.strptime(event['start']['utc'], '%Y-%m-%dT%H:%M:%SZ')
                end_time = datetime.strptime(event['end']['utc'], '%Y-%m-%dT%H:%M:%SZ')

                ical_event = Event()
                ical_event.name = event['name']['text']
                ical_event.begin = start_time
                ical_event.end = end_time
                
                # Only add venue if it exists
                if 'venue' in event and event['venue']:
                    ical_event.location = event['venue'].get('address', {}).get('localized_address_display', 'No location')
                
                # Only add description if it exists
                if 'description' in event and event['description']:
                    ical_event.description = event['description'].get('text', '')

                calendar.events.add(ical_event)
            except Exception as e:
                logging.error(f"Error processing event {event.get('id', 'unknown')}: {str(e)}")
                continue

        # Generate iCal file in memory
        ical_file = io.StringIO(str(calendar))
        return send_file(
            io.BytesIO(ical_file.getvalue().encode()),
            as_attachment=True,
            download_name='eventbrite_events.ics',
            mimetype='text/calendar'
        )

    return jsonify({'error': 'No events found'}), 404

if __name__ == '__main__':
    app.run(debug=True)
