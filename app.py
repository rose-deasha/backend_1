from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import requests
from ics import Calendar, Event
from datetime import datetime
import io
import logging

app = Flask(__name__)
CORS(app)

# Set up logging to capture errors
logging.basicConfig(level=logging.DEBUG)

@app.route('/create-ical', methods=['POST'])
def create_ical():
    try:
        data = request.get_json()
        if 'apiKey' not in data:
            return jsonify({'error': 'API key missing'}), 400
        
        api_key = data.get('apiKey')
        headers = {
            'Authorization': f'Bearer {api_key}'
        }

        # Send request to Eventbrite API
        response = requests.get('https://www.eventbriteapi.com/v3/users/me/events/', headers=headers)
        
        if response.status_code != 200:
            return jsonify({'error': 'Failed to fetch events from Eventbrite'}), response.status_code

        events_data = response.json()

        # Create a new calendar
        calendar = Calendar()

        for event in events_data.get('events', []):
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

    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

if __name__ == '__main__':
    app.run(debug=True)
