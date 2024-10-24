from flask import Flask, request, send_file, jsonify, redirect
from flask_cors import CORS
import requests
from ics import Calendar, Event
from datetime import datetime
import io
import logging
import os
from dotenv import load_dotenv
import traceback

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = 'https://backend-1-2x3i.onrender.com/oauth/callback'
FRONTEND_URL = 'https://rose-deasha.github.io/eventbrite-to-ical/'

# Validate required environment variables
if not CLIENT_ID or not CLIENT_SECRET:
    logger.error("Missing required environment variables. Please check .env file")
    raise ValueError("Missing required environment variables")


def fetch_all_orders(access_token):
    """Fetch all orders from the Eventbrite API, handling pagination."""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    orders = []
    page = 1

    while True:
        response = requests.get(
            f'https://www.eventbriteapi.com/v3/users/me/orders/',
            headers=headers,
            params={'page': page}
        )

        if response.status_code != 200:
            raise Exception(f"Failed to fetch orders: {response.text}")

        data = response.json()

        # Add the orders from this page to the list of orders
        orders.extend(data['orders'])

        # Check if there are more pages
        pagination = data.get('pagination', {})
        if not pagination.get('has_more_items'):
            break

        # Move to the next page
        page += 1

    return orders


@app.route('/events/ical')
def download_ical():
    """Generate and download iCal file for user's events"""
    try:
        access_token = request.args.get('access_token')
        if not access_token:
            return jsonify({'error': 'Access token missing'}), 400

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # Fetch all orders, handling pagination
        orders = fetch_all_orders(access_token)

        if not orders:
            return jsonify({'error': 'No orders found'}), 404

        # Create calendar
        calendar = Calendar()
        calendar.creator = 'Eventbrite to iCal Converter'

        for order in orders:
            try:
                # Fetch event details for each order
                event_id = order['event_id']
                event_response = requests.get(
                    f'https://www.eventbriteapi.com/v3/events/{event_id}/',
                    headers=headers
                )

                event_data = event_response.json()

                ical_event = Event()
                ical_event.name = event_data['name']['text']
                
                # Parse the start time correctly
                start_time = datetime.strptime(event_data['start']['utc'], '%Y-%m-%dT%H:%M:%SZ')
                ical_event.begin = start_time

                # Parse the end time, or set a default if missing
                end_time = event_data.get('end', {}).get('utc')
                if end_time:
                    ical_event.end = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%SZ')
                else:
                    ical_event.end = start_time  # Use start time if no end time is available

                # Add event URL
                ical_event.url = event_data.get('url', '')

                # Add venue if available
                if event_data.get('venue'):
                    venue_address = event_data['venue'].get('address', {})
                    address_parts = [
                        venue_address.get('address_1'),
                        venue_address.get('address_2'),
                        venue_address.get('city'),
                        venue_address.get('region'),
                        venue_address.get('postal_code'),
                        venue_address.get('country')
                    ]
                    ical_event.location = ', '.join(filter(None, address_parts))

                # Add description
                description_parts = [event_data.get('description', {}).get('text', '')]
                description_parts.append(f"Event URL: {event_data.get('url', '')}")
                ical_event.description = '\n\n'.join(description_parts)

                calendar.events.add(ical_event)
                logger.info(f"Added event to calendar: {ical_event.name}")

            except Exception as e:
                logger.error(f"Error processing order {order.get('id', 'unknown')}: {str(e)}")
                continue

        # Generate iCal file
        ical_file = io.StringIO(str(calendar))

        # Log success
        logger.info("Successfully generated iCal file")

        return send_file(
            io.BytesIO(ical_file.getvalue().encode()),
            as_attachment=True,
            download_name='eventbrite_orders.ics',
            mimetype='text/calendar'
        )

    except Exception as e:
        logger.error(f"Error generating iCal: {traceback.format_exc()}")
        return jsonify({
            'error': 'Failed to generate iCal file',
            'details': str(e)
        }), 500


if __name__ == '__main__':
    logger.info("Starting application")
    logger.info(f"CLIENT_ID configured: {bool(CLIENT_ID)}")
    logger.info(f"CLIENT_SECRET configured: {bool(CLIENT_SECRET)}")
    logger.info(f"REDIRECT_URI: {REDIRECT_URI}")
    logger.info(f"FRONTEND_URL: {FRONTEND_URL}")
    
    app.run(debug=True)
