from flask import Flask, request, send_file
import requests
from ics import Calendar, Event
from urllib.parse import quote as url_quote
from datetime import datetime
import io

app = Flask(__name__)

@app.route('/create-ical', methods=['POST'])
def create_ical():
    data = request.get_json()
    api_key = data.get('apiKey')
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    response = requests.get('https://www.eventbriteapi.com/v3/users/me/events/', headers=headers)

    events_data = response.json()

    # Create a new calendar
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

if __name__ == '__main__':
    app.run(debug=True)
