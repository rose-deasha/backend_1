# Eventbrite to iCal Converter - Backend

Flask backend service for the Eventbrite to iCal Converter application. Handles OAuth authentication and iCal file generation.

## 📋 Table of Contents
- [Features](#-features)
- [Technology Stack](#-technology-stack)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [API Documentation](#-api-documentation)
- [Configuration](#-configuration)
- [Deployment](#-deployment)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features
- OAuth2 authentication with Eventbrite
- Fetch user's Eventbrite orders
- Generate iCal files from event data
- CORS support for frontend integration

## 💻 Technology Stack
- Python 3.7+
- Flask
- Flask-CORS
- ics (iCal generation)
- Requests (HTTP client)

## 📦 Prerequisites
- Python 3.7 or higher
- pip (Python package manager)
- Eventbrite API credentials
- Virtual environment (recommended)

## 💻 Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/eventbrite-to-ical-backend.git
cd eventbrite-to-ical-backend
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file:
```env
CLIENT_ID=your_eventbrite_client_id
CLIENT_SECRET=your_eventbrite_client_secret
FRONTEND_URL=your_frontend_url
```

5. Run the application:
```bash
python app.py
```

## 📚 API Documentation

### OAuth Callback
```
GET /oauth/callback
```
Handles the OAuth callback from Eventbrite.

### Download iCal
```
GET /events/ical
Query Parameters:
- access_token: Eventbrite OAuth access token
```
Generates and returns an iCal file of the user's Eventbrite tickets.

## ⚙️ Configuration

### Environment Variables
- `CLIENT_ID`: Eventbrite application client ID
- `CLIENT_SECRET`: Eventbrite application client secret
- `FRONTEND_URL`: URL of the frontend application
- `REDIRECT_URI`: OAuth callback URL

### Required Python Packages
- Flask
- Flask-CORS
- requests
- python-dotenv
- ics

## 🚀 Deployment

### Deploying to Render

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Configure environment variables:
   - `CLIENT_ID`
   - `CLIENT_SECRET`
   - `FRONTEND_URL`
4. Set the build command:
```bash
pip install -r requirements.txt
```
5. Set the start command:
```bash
gunicorn app:app
```

## 🤝 Contributing
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
