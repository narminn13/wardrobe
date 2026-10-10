# Wardrobe AI

Wardrobe AI is a personal wardrobe management and AI-powered outfit planning web application.

Users can upload photos of their clothes, automatically analyse each garment with AI, organise their wardrobe, and generate weekly outfit suggestions based on their available clothes and the weather.

The project combines wardrobe management, image analysis, weather data, and AI-powered outfit generation into one application.

---

## Features

### 👗 Digital Wardrobe

Users can build a personal digital wardrobe by uploading photos of their clothes.

Each garment can be analysed and stored with information such as:

- Category
- Primary colour
- Secondary colours
- Material
- Pattern
- Fit
- Style
- Season
- Formality
- Warmth
- Weather suitability
- Description

Users can also:

- View all wardrobe items
- Open individual garment details
- Mark garments as unavailable
- Archive garments
- Add new garments at any time

Multiple images can be uploaded at once, with a maximum of 5 images per upload.

Supported formats:

- JPG
- JPEG
- PNG
- WEBP

Maximum file size:

- 8 MB per image

---

## 🤖 AI Garment Analysis

Uploaded garment images are analysed using the OpenAI API.

The system extracts structured information from each garment and stores the analysis in the database.

This allows the application to understand what the user owns and use those garments when creating outfit combinations.

The system does not generate imaginary wardrobe items. Outfit recommendations are created from the user's actual available garments.

---

## 🌦️ Weather-Aware Outfit Planning

Wardrobe AI integrates with the Open-Meteo API to retrieve weather forecasts.

The planner considers information such as:

- Minimum temperature
- Maximum temperature
- Rain
- Precipitation probability
- Wind speed
- Weather conditions

Weather data is associated with the user's selected city and planning dates.

The application also caches weather data to reduce unnecessary API requests.

---

## 📅 Weekly Outfit Planner

Users can generate outfits for:

- The current week
- The next week

### Current Week

For the current week, outfits are generated only from the current day through Sunday.

### Next Week

For the next week, outfits are generated from Monday through Sunday.

Users cannot create plans for past weeks or weeks more than one week in the future.

Each generated outfit contains:

- Date
- Outfit title
- Explanation
- Weather information
- Selected garments
- Garment roles

Examples of roles include:

- Top
- Bottom
- Dress
- Shoes
- Outerwear
- Item

The AI attempts to create practical combinations based on both the wardrobe and weather conditions.

---

## 🔐 Authentication

The application includes user authentication.

Users can:

- Create an account
- Sign in
- Sign out
- Maintain their own private wardrobe
- Create their own weekly plans

Each user's wardrobe, weather data, and outfit plans are associated with their account.

---

## ☁️ Cloud Media Storage

Garment images are stored using Cloudinary.

This allows uploaded images to remain available after deployment instead of depending on the local server filesystem.

The application uses:

- Cloudinary
- django-cloudinary-storage

Production media files are therefore separated from the application's deployment environment.

---

## 🗄️ Database

The production application uses PostgreSQL hosted on Neon.

The database stores:

- Users
- Garments
- Weekly plans
- Outfits
- Outfit items
- Weather forecasts

The application uses Django ORM for database operations.

---

## 🏗️ Project Structure

```text
wardrobe_ai/
│
├── accounts/
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   └── ...
│
├── wardrobe/
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── services.py
│   ├── urls.py
│   └── ...
│
├── planner/
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── services.py
│   ├── urls.py
│   └── ...
│
├── weather/
│   ├── models.py
│   ├── services.py
│   └── ...
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── ...
│
├── templates/
│   ├── accounts/
│   ├── planner/
│   ├── wardrobe/
│   └── ...
│
├── static/
│
├── manage.py
├── requirements.txt
└── README.md



🧩 Main Django Models
User
Custom Django user model used for authentication and user-specific application data.
Garment
Represents an individual clothing item uploaded by a user.
Stores both the uploaded image and AI-generated garment attributes.
WeeklyPlan
Represents a user's weekly outfit planning session.
A plan is associated with:
- User
- Week
- City
- Notes
- Generation status
Outfit
Represents one outfit for a specific date within a weekly plan.
OutfitItem
Connects an outfit with the garments used in that outfit.
This allows one outfit to contain multiple wardrobe items.
WeatherForecast
Stores weather information used during outfit generation.
🔄 Outfit Generation Flow
The main outfit generation process is:
User
  │
  ▼
Select Week + City
  │
  ▼
Retrieve Weather Forecast
  │
  ▼
Retrieve Available Garments
  │
  ▼
Build Garment + Weather Context
  │
  ▼
Send Structured Context to OpenAI
  │
  ▼
Receive Outfit JSON
  │
  ▼
Validate Garment IDs and Dates
  │
  ▼
Create Outfit Records
  │
  ▼
Create OutfitItem Records
  │
  ▼
Display Weekly Outfits
The application validates the AI response before saving outfit data.
Only garments belonging to the current user and marked as available can be selected.
🧠 AI Safety and Validation
The AI-generated response is validated before being stored.
The application checks that:
- The response contains valid JSON
- Outfit dates belong to the requested forecast period
- Garment IDs exist in the user's available wardrobe
- Duplicate outfits are not created for the same date
- Every forecast day receives an outfit
- Invalid garment IDs are ignored
- The weekly plan is marked as generated only after successful creation
🎨 UI / UX
The application uses a minimal, modern wardrobe-focused design.
The interface includes:
- Responsive layouts
- Clean typography
- Neutral colour palette
- Garment image cards
- Outfit cards
- Weather information
- Responsive navigation
- Mobile-friendly layouts
- Hover interactions
- Subtle animations
- Reduced-motion support
The design aims to feel more like a modern fashion product than a traditional CRUD application.
🚀 Deployment
The application is deployed using Render.
Production architecture:
Browser
   │
   ▼
Render
   │
   ├── Django
   │
   ├── Gunicorn
   │
   └── WhiteNoise
        │
        ├──────────────► Neon PostgreSQL
        │
        ├──────────────► Cloudinary
        │
        ├──────────────► OpenAI API
        │
        └──────────────► Open-Meteo API
The production application uses environment variables for sensitive configuration.
Secrets such as API keys, database credentials, and Cloudinary credentials are not stored in the repository.
⚙️ Technologies
Backend
- Python
- Django
- Django ORM
- Gunicorn
Database
- PostgreSQL
- Neon
AI
- OpenAI API
Weather
- Open-Meteo API
Media Storage
- Cloudinary
- django-cloudinary-storage
Frontend
- HTML
- CSS
- JavaScript
- Bootstrap
Deployment
- Render
- WhiteNoise
🔑 Environment Variables
The application requires environment variables for production configuration.
Example:
SECRET_KEY=your-secret-key

DEBUG=False

OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=your-openai-model

PGHOST=your-postgres-host
PGDATABASE=your-postgres-database
PGUSER=your-postgres-user
PGPASSWORD=your-postgres-password
PGPORT=5432
PGSSLMODE=require
PGCHANNELBINDING=require

CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
Actual credentials should never be committed to GitHub.
💻 Local Development
Clone the repository:
git clone https://github.com/narminn13/wardrobe.git
cd wardrobe
Create and activate a virtual environment:
python -m venv venv

Windows:
venv\Scripts\activate

Install dependencies:
pip install -r requirements.txt

Create the required environment variables.
Run migrations:
python manage.py migrate

Create a superuser if needed:
python manage.py createsuperuser

Run the development server:
python manage.py runserver

Then open:
http://127.0.0.1:8000/

🧪 Testing
The project includes automated Django tests covering important application functionality.
Tests include areas such as:
- Authentication
- Wardrobe functionality
- Garment uploads
- Weather services
- Weekly planning
- Outfit generation
- Model behaviour
Run the test suite with:
python manage.py test

🔮 Future Improvements
The current application focuses on wardrobe management and weekly outfit planning, but the architecture can be extended further.
Clothing Collections
Future versions could allow users to organise garments into separate collections such as:
- Tops
- Bottoms
- Dresses
- Shoes
- Outerwear
- Accessories
- Workwear
- Casual wear
- Seasonal collections
Users could create and manage custom collections in addition to the automatic garment categories.
Saved Outfit Collections
Users could save generated outfits into named collections.
Examples:
- Favourite Outfits
- University Looks
- Work Outfits
- Weekend Looks
- Travel Outfits
- Summer Outfits
Monthly Outfit Planning
The planner could be expanded from weekly planning to monthly outfit planning.
Users could generate and save outfit plans for an entire month.
Outfit History
Previously generated outfits could be stored and viewed later instead of being limited to the current and next week.
Saved Weekly Plans
Users could save completed weeks under custom names and revisit them later.
Outfit Regeneration
Users could regenerate a single day's outfit instead of regenerating the entire week.
User Preferences
Future versions could allow users to define additional preferences such as:
- Favourite colours
- Preferred styles
- Dress code
- Clothing rotation preferences
- Items they want to wear more often
- Items they want to avoid
Improved AI Styling
Future AI features could include:
- More advanced outfit compatibility analysis
- Personal style learning
- Colour combination analysis
- Occasion-based outfit generation
- Travel packing suggestions
- Seasonal wardrobe recommendations
Calendar Integration
Generated outfits could eventually be integrated with a calendar so users can see their planned outfits alongside their daily schedule.
🌱 Project Vision
Wardrobe AI is designed to evolve from a simple digital wardrobe into a personal styling assistant.
The long-term goal is to help users:
1. Digitise their wardrobe
2. Understand what they own
3. Organise clothing into collections
4. Plan outfits around weather and occasions
5. Save favourite outfits
6. Build weekly and monthly outfit plans
7. Reduce the effort of deciding what to wear
👩‍💻 Author
Narmin Hasanova
Information Technology student at Baku Engineering University.
