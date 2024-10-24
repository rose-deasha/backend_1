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

        # Create calendar
        calendar = Calendar()
        calendar.creator = 'Eventbrite to iCal Converter'

        # Initialize variables for pagination
        continuation_token = None
        all_orders = []

        # Fetch all orders using pagination
        while True:
            params = {
                'expand': 'event,event.venue,event.ticket_classes'
            }
            
            if continuation_token:
                params['continuation'] = continuation_token

            # Get user's orders (events they're attending)
            logger.info(f"Fetching orders page with params: {params}")
            orders_response = requests.get(
                'https://www.eventbriteapi.com/v3/users/me/orders/',
                headers=headers,
                params=params
            )

            logger.info(f"Orders API Response Status: {orders_response.status_code}")
            
            if orders_response.status_code != 200:
                return jsonify({
                    'error': 'Failed to fetch orders',
                    'details': orders_response.text
                }), orders_response.status_code

            orders_data = orders_response.json()
            
            if orders_data.get('orders'):
                all_orders.extend(orders_data['orders'])

            # Check for pagination
            pagination = orders_data.get('pagination', {})
            continuation_token = pagination.get('continuation')
            
            if not continuation_token:
                break

        if not all_orders:
            logger.info("No orders found")
            return jsonify({'error': 'No tickets found'}), 404

        logger.info(f"Total orders found: {len(all_orders)}")

        # Process all orders
        for order in all_orders:
            try:
                event = order.get('event')
                if not event:
                    logger.warning(f"No event data in order {order.get('id')}")
                    continue

                logger.info(f"Processing event: {event.get('name', {}).get('text', 'Unknown Event')}")
                logger.info(f"Event dates - Start: {event.get('start')}, End: {event.get('end')}")

                ical_event = Event()
                ical_event.name = event['name']['text']
                
                # Handle datetime conversion
                try:
                    ical_event.begin = datetime.strptime(event['start']['utc'], '%Y-%m-%dT%H:%M:%SZ')
                    ical_event.end = datetime.strptime(event['end']['utc'], '%Y-%m-%dT%H:%M:%SZ')
                except Exception as e:
                    logger.error(f"Error parsing dates for event {event.get('id')}: {e}")
                    continue

                ical_event.url = event.get('url', '')

                # Add venue if available
                if event.get('venue'):
                    venue_address = event['venue'].get('address', {})
                    address_parts = []
                    for field in ['address_1', 'address_2', 'city', 'region', 'postal_code', 'country']:
                        if venue_address.get(field):
                            address_parts.append(venue_address[field])
                    
                    if address_parts:
                        ical_event.location = ', '.join(address_parts)

                # Add description
                description_parts = []
                if event.get('description', {}).get('text'):
                    description_parts.append(event['description']['text'])

                # Add order information
                description_parts.append("\nOrder Information:")
                description_parts.append(f"Order #: {order.get('reference', 'N/A')}")
                
                # Add ticket information
                attendees = order.get('attendees', [])
                if attendees:
                    description_parts.append("\nTicket Information:")
                    for attendee in attendees:
                        ticket_info = []
                        if attendee.get('ticket_class_name'):
                            ticket_info.append(f"Type: {attendee['ticket_class_name']}")
                        if ticket_info:
                            description_parts.append(" - " + ", ".join(ticket_info))

                description_parts.append(f"\nEvent URL: {event.get('url', '')}")
                ical_event.description = '\n'.join(description_parts)

                calendar.events.add(ical_event)
                logger.info(f"Successfully added event to calendar: {ical_event.name}")

            except Exception as e:
                logger.error(f"Error processing order {order.get('id', 'unknown')}: {str(e)}")
                continue

        if not calendar.events:
            logger.warning("No events were successfully processed")
            return jsonify({'error': 'No valid events found'}), 404

        logger.info(f"Total events added to calendar: {len(calendar.events)}")

        # Generate iCal file
        ical_file = io.StringIO(str(calendar))
        logger.info("Successfully generated iCal file")

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
