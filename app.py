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
CORS(app, origins=['https://rose-deasha.github.io/eventbrite-to-ical/'])

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

@app.route('/')
def index():
    """Health check endpoint"""
    try:
        return jsonify({
            "status": "ok",
            "client_id_configured": bool(CLIENT_ID),
            "client_secret_configured": bool(CLIENT_SECRET)
        })
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/oauth/callback')
def oauth_callback():
    """Handle OAuth callback from Eventbrite"""
    try:
        logger.info("Received callback request")
        logger.info(f"Query parameters: {request.args}")
        
        # Get authorization code
        code = request.args.get('code')
        if not code:
            logger.error("No authorization code received")
            return redirect(f"{FRONTEND_URL}?error=missing_code")

        logger.info(f"Received authorization code: {code[:5]}...")

        # Exchange code for token
        token_url = 'https://www.eventbrite.com/oauth/token'
        data = {
            'grant_type': 'authorization_code',
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'redirect_uri': REDIRECT_URI
        }

        logger.info(f"Requesting token from {token_url}")
        response = requests.post(token_url, data=data)
        logger.info(f"Token response status: {response.status_code}")

        if response.status_code != 200:
            error_message = response.text
            logger.error(f"Token exchange failed: {error_message}")
            return redirect(f"{FRONTEND_URL}?error=token_exchange_failed")

        token_data = response.json()
        access_token = token_data.get('access_token')

        if not access_token:
            logger.error("No access token in response")
            return redirect(f"{FRONTEND_URL}?error=no_access_token")

        logger.info("Successfully obtained access token")
        return redirect(f"{FRONTEND_URL}?access_token={access_token}")

    except Exception as e:
        logger.error(f"Unexpected error in callback: {traceback.format_exc()}")
        return redirect(f"{FRONTEND_URL}?error=server_error")

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

        # Get user's orders (events they're attending)
        logger.info("Fetching user's orders...")
        orders_response = requests.get(
            'https://www.eventbriteapi.com/v3/users/me/orders/',
            headers=headers,
            params={
                'expand': 'event,event.venue,event.ticket_classes'
            }
        )

        logger.info(f"Orders API Response Status: {orders_response.status_code}")
        logger.info(f"Orders API Response Headers: {dict(orders_response.headers)}")

        if orders_response.status_code != 200:
            return jsonify({
                'error': 'Failed to fetch orders',
                'details': orders_response.text
            }), orders_response.status_code

        orders_data = orders_response.json()
        
        if not orders_data.get('orders'):
            logger.info("No orders found in response")
            return jsonify({'error': 'No tickets found'}), 404

        # Create calendar
        calendar = Calendar()
        calendar.creator = 'Eventbrite to iCal Converter'

        # Process each order
        for order in orders_data['orders']:
            try:
                event = order['event']
                
                ical_event = Event()
                ical_event.name = event['name']['text']
                ical_event.begin = datetime.strptime(event['start']['utc'], '%Y-%m-%dT%H:%M:%SZ')
                ical_event.end = datetime.strptime(event['end']['utc'], '%Y-%m-%dT%H:%M:%SZ')
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
                        if attendee.get('barcodes'):
                            for barcode in attendee['barcodes']:
                                if barcode.get('barcode'):
                                    ticket_info.append(f"Barcode: {barcode['barcode']}")
                        if ticket_info:
                            description_parts.append(" - " + ", ".join(ticket_info))

                description_parts.append(f"\nEvent URL: {event.get('url', '')}")
                ical_event.description = '\n'.join(description_parts)

                calendar.events.add(ical_event)
                logger.info(f"Added event to calendar: {ical_event.name}")

            except Exception as e:
                logger.error(f"Error processing order {order.get('id', 'unknown')}: {str(e)}")
                continue

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

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404 error: {error}")
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {error}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    logger.info("Starting application")
    logger.info(f"CLIENT_ID configured: {bool(CLIENT_ID)}")
    logger.info(f"CLIENT_SECRET configured: {bool(CLIENT_SECRET)}")
    logger.info(f"REDIRECT_URI: {REDIRECT_URI}")
    logger.info(f"FRONTEND_URL: {FRONTEND_URL}")
    
    app.run(debug=True)
