# Wardrobe AI

Wardrobe AI is a Django-based personal wardrobe management and outfit planning application.

Users can upload their clothing items, analyze them with AI, and create weekly outfit plans based on their wardrobe, preferred style, and weather conditions.

## Features

- User registration and authentication
- Clothing image upload
- AI-powered garment analysis
- Automatic clothing categorization
- Color, material, pattern, season and formality detection
- Personal wardrobe management
- Garment availability and archive management
- Weekly outfit planning
- Weather-based outfit recommendations
- AI-generated outfit combinations
- 7-day weather forecast integration

## Technologies

- Python
- Django
- SQLite
- OpenAI API
- Open-Meteo Weather API
- Pillow
- HTML
- CSS
- JavaScript

## Project Structure

text
wardrobe_ai/
│
├── accounts/
├── wardrobe/
├── planner/
├── weather/
├── templates/
├── static/
├── media/
├── manage.py
└── requirements.txt
How It Works
1. The user creates an account.
2. Clothing items are uploaded to the wardrobe.
3. The application analyzes clothing images using the OpenAI API.
4. Garment information is stored in the database.
5. The user creates a weekly plan and selects a city and preferred formality.
6. Weather data is retrieved for the selected city.
7. The application generates suitable outfits using the user's available garments and weather conditions.
8. The generated weekly outfits are displayed in the planner.
Setup
Clone the repository
git clone https://github.com/narminhasanova/wardrobe-ai.git
cd wardrobe-ai
Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate
Install dependencies
pip install -r requirements.txt
Create a .env file
Add your API credentials:
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=your_model
Run migrations
python manage.py migrate
Start the development server
python manage.py runserver
Open:
http://127.0.0.1:8000/
Environment Variables
The following environment variables are required:
- OPENAI_API_KEY
- OPENAI_MODEL
API keys and secret credentials should never be committed to the repository.
Future Improvements
- Outfit history and favourites
- More advanced wardrobe filters
- Outfit rating system
- Calendar integration
- Improved weather-based recommendations
- User style preferences
- Production deployment
Author
Narmin Hasanova
