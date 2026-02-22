import sys
import os
from dotenv import load_dotenv

load_dotenv() 

# Add project root to path so all modules (llm_service, db, middleware) resolve correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_cors import CORS
from routes.auth import auth_bp
from routes.scholarships import scholarships_bp
from routes.eligibility import eligibility_bp
from routes.admin import admin_bp
from config import Config

print("KEY:", os.getenv("MEGALLM_API_KEY"))  # 👈 PASTE HERE

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Register blueprints
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(scholarships_bp, url_prefix="/api/scholarships")
app.register_blueprint(eligibility_bp, url_prefix="/api/eligibility")
app.register_blueprint(admin_bp, url_prefix="/api/admin")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)