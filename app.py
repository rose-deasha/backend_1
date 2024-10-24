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

@app.route('/oauth/callback')
def oauth_callback():
    """Handle the OAuth callback from Eventbrite"""
    try:
        # Get the authorization code from the URL query parameter
        code = request.args.get('code')
        state = request.args.get('state')
        
        logger.info(f"Received callback with code: {code[:5]}... and state: {state}")
        
        if not code:
            logger.error("No authorization code received")
            return redirect(f"{FRONTEND_URL}?error=missing_code")

        # Exchange the authorization code for an access token
        token_url = 'https://www.eventbrite.com/oauth/token'
        data = {
            'grant_type': 'authorization_code',
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'redirect_uri': REDIRECT_URI
        }

        logger.info(f"Exchanging code for token with client_id: {CLIENT_ID}")
        logger.info(f"Redirect URI: {REDIRECT_URI}")

        # Send POST request to Eventbrite to get the access token
        response = requests.post(token_url, data=data)
        logger.info(f"Token exchange response status: {response.status_code}")

        if response.status_code != 200:
            error_info = response.json() if response.text else {"error": "Unknown error"}
            logger.error(f"Token exchange failed: {error_info}")
            return redirect(f"{FRONTEND_URL}?error=token_exchange_failed")

        # Get the access token from the response
        token_data = response.json()
        access_token = token_data.get('access_token')

        if not access_token:
            logger.error("No access token in response")
            return redirect(f"{FRONTEND_URL}?error=no_access_token")

        # Redirect back to frontend with the access token
        logger.info("Successfully obtained access token, redirecting to frontend")
        return redirect(f"{FRONTEND_URL}?access_token={access_token}")

    except Exception as e:
        logger.error(f"Error in OAuth callback: {traceback.format_exc()}")
        return redirect(f"{FRONTEND_URL}?error=server_error&message={str(e)}")

@app.route('/events/ical')
def download_ical():
    """Generate and download iCal file for user's attended events"""
    try:
        access_token = request.args.get('access_token')
        if not access_token:
            return jsonify({'error': 'Access token missing'}), 400

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }

        # Get user's orders with expanded event details
        logger.info("Fetching user's orders...")
        response = requests.get(
            'https://www.eventbriteapi.com/v3/users/me/orders/',
            headers=headers,
            params={
                'expand': ['event', 'event.venue', 'attendees']
            }
        )

        # Log the raw response for debugging
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response content: {response.text[:1000]}")  # Log first 1000 chars

        if response.status_code != 200:
            return jsonify({
                'error': 'Failed to fetch orders',
                'details': response.text
            }), response.status_code

        data = response.json()
        
        # Create calendar
        calendar = Calendar()
        calendar.creator = 'Eventbrite to iCal Converter'

        if not data.get('orders'):
            logger.warning("No orders found in response")
            return jsonify({'error': 'No orders found'}), 404

        # Debug log the number of orders
        logger.info(f"Found {len(data['orders'])} orders")

        # Process each order
        for order in data['orders']:
            try:
                # Log the entire order for debugging
                logger.info(f"Processing order: {order.get('id')}")
                logger.info(f"Order data: {order}")

                # Get the event data
                event = order.get('event')
                if not event:
                    logger.warning(f"No event data for order {order.get('id')}")
                    continue

                # Log the event data
                logger.info(f"Event data: {event}")

                # Create the calendar event
                ical_event = Event()
                ical_event.name = event['name']['text']

                # Parse start date
                start_str = event['start']['utc']
                logger.info(f"Start date string: {start_str}")
                ical_event.begin = datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%SZ')

                # Parse end date
                end_str = event['end']['utc']
                logger.info(f"End date string: {end_str}")
                ical_event.end = datetime.strptime(end_str, '%Y-%m-%dT%H:%M:%SZ')

                # Add the URL
                ical_event.url = event.get('url', '')

                # Add venue information
                if event.get('venue'):
                    venue = event['venue']
                    venue_address = venue.get('address', {})
                    address_parts = []
                    
                    # Add venue name if available
                    if venue.get('name'):
                        address_parts.append(venue['name'])
                    
                    # Add address components
                    for field in ['address_1', 'address_2', 'city', 'region', 'postal_code', 'country']:
                        if venue_address.get(field):
                            address_parts.append(venue_address[field])
                    
                    if address_parts:
                        ical_event.location = ', '.join(filter(None, address_parts))

                # Add description with event and ticket details
                description_parts = []
                
                # Add event description
                if event.get('description', {}).get('text'):
                    description_parts.append(event['description']['text'])

                # Add order information
                description_parts.append(f"\nOrder #: {order.get('reference', 'N/A')}")

                # Add ticket information
                if order.get('attendees'):
                    description_parts.append("\nTickets:")
                    for attendee in order['attendees']:
                        if attendee.get('ticket_class_name'):
                            description_parts.append(f"- {attendee['ticket_class_name']}")

                # Add event URL
                description_parts.append(f"\nEvent URL: {event.get('url', '')}")

                ical_event.description = '\n'.join(description_parts)

                # Add the event to the calendar
                calendar.events.add(ical_event)
                logger.info(f"Successfully added event: {ical_event.name} ({ical_event.begin} to {ical_event.end})")

            except Exception as e:
                logger.error(f"Error processing order: {str(e)}")
                logger.error(traceback.format_exc())
                continue

        # Check if we added any events
        if not calendar.events:
            logger.warning("No events were successfully processed")
            return jsonify({'error': 'No events found'}), 404

        # Generate the iCal file
        ical_file = io.StringIO(str(calendar))
        
        response = send_file(
            io.BytesIO(ical_file.getvalue().encode()),
            as_attachment=True,
            download_name='eventbrite_events.ics',
            mimetype='text/calendar'
        )

        # Add CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        
        return response

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
