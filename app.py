from flask import Flask, request, jsonify
from flask_cors import CORS
import pickle
import razorpay
import hashlib
import hmac
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import numpy as np
import jwt
from functools import wraps
import bcrypt

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# ===========================
# Configuration
# ===========================
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
MONGODB_URI = os.getenv('MONGODB_URI')

JWT_SECRET = os.getenv('SECRET_KEY', 'your-secret-key-here')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# Initialize Razorpay client
try:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    print("✓ Razorpay client initialized")
except Exception as e:
    print(f"✗ Razorpay initialization failed: {e}")
    razorpay_client = None

# Initialize MongoDB with proper error handling
mongo_client = None
db = None
collections = {}
mongodb_connected = False

def init_mongodb():
    global mongo_client, db, collections, mongodb_connected
    
    if not MONGODB_URI:
        print("⚠️  WARNING: MONGODB_URI not configured")
        mongodb_connected = False
        return False
    
    try:
        mongo_client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=5000,
            retryWrites=True
        )
        
        mongo_client.server_info()
        
        db = mongo_client['carvalueai']
        collections = {
            'users': db['users'],
            'cars': db['cars'],
            'bookings': db['bookings'],
            'payments': db['payments']
        }
        
        print("✓ MongoDB connected successfully")
        
        # Create indexes
        collections['users'].create_index('email', unique=True)
        collections['users'].create_index('user_id', unique=True)
        collections['cars'].create_index('car_id', unique=True)
        collections['bookings'].create_index('booking_id', unique=True)
        collections['payments'].create_index('order_id', unique=True)
        
        mongodb_connected = True
        return True
        
    except ServerSelectionTimeoutError:
        print("✗ MongoDB connection timeout - server not reachable")
        mongodb_connected = False
        return False
    except ConnectionFailure as e:
        print(f"✗ MongoDB connection failed: {e}")
        mongodb_connected = False
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        mongodb_connected = False
        return False

# Initialize MongoDB
init_mongodb()

# Load ML model
try:
    with open('model_artifacts.pkl', 'rb') as f:
        artifacts = pickle.load(f)
    model = artifacts['model']
    scaler = artifacts['scaler']
    label_encoders = artifacts['label_encoders']
    feature_cols = artifacts['feature_cols']
    print("✓ ML model loaded successfully")
except Exception as e:
    print(f"✗ Model loading failed: {e}")
    model = None

# ===========================
# Authentication Helper Functions
# ===========================

def hash_password(password):
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, hashed):
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_jwt_token(user_id, email):
    """Create JWT token"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

def verify_jwt_token(token):
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def token_required(f):
    """Decorator to verify JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'status': 'error', 'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'status': 'error', 'error': 'Token is missing'}), 401
        
        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({'status': 'error', 'error': 'Invalid or expired token'}), 401
        
        request.user_id = payload['user_id']
        request.user_email = payload['email']
        return f(*args, **kwargs)
    
    return decorated

# ===========================
# Helper Functions
# ===========================

def safe_encode_label(encoder, value):
    """Safely encode a label, handling unseen values"""
    try:
        return encoder.transform([value])[0]
    except ValueError:
        print(f"Warning: '{value}' not in training data, using default")
        return 0

def prepare_features(data):
    """Prepare features for model prediction"""
    current_year = 2024
    
    car_age = current_year - data['year']
    km_per_year = data['km_driven'] / (car_age + 1)
    
    if 'mileage' not in data or not data['mileage']:
        mileage_map = {'Petrol': 18, 'Diesel': 22, 'CNG': 25, 'Electric': 30}
        data['mileage'] = mileage_map.get(data['fuel'], 18)
    
    if 'engine' not in data or not data['engine']:
        data['engine'] = 1200
    
    if 'max_power' not in data or not data['max_power']:
        data['max_power'] = data['engine'] * 0.07
    
    if 'seats' not in data or not data['seats']:
        data['seats'] = 5
    
    power_efficiency = data['max_power'] / data['engine']
    
    name_encoded = safe_encode_label(label_encoders['name'], data['name'])
    fuel_encoded = safe_encode_label(label_encoders['fuel'], data['fuel'])
    seller_type_encoded = safe_encode_label(label_encoders['seller_type'], data['seller_type'])
    transmission_encoded = safe_encode_label(label_encoders['transmission'], data['transmission'])
    owner_encoded = safe_encode_label(label_encoders['owner'], data['owner'])
    
    features = np.array([[
        data['year'],
        data['km_driven'],
        data['mileage'],
        data['engine'],
        data['max_power'],
        data['seats'],
        car_age,
        km_per_year,
        power_efficiency,
        name_encoded,
        fuel_encoded,
        seller_type_encoded,
        transmission_encoded,
        owner_encoded
    ]])
    
    return features

def send_booking_email(customer_email, booking_details):
    """Send booking confirmation email"""
    try:
        smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_user = os.getenv('SMTP_USER')
        smtp_password = os.getenv('SMTP_PASSWORD')
        
        if not all([smtp_user, smtp_password]):
            print("Email credentials not configured")
            return False
        
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = customer_email
        msg['Subject'] = 'Inspection Booking Confirmation - CarValueAI'
        
        body = f"""
        Dear {booking_details['customer_name']},
        
        Your car inspection has been booked successfully!
        
        Booking Details:
        - Booking ID: {booking_details['booking_id']}
        - Date: {booking_details['inspection_date']}
        - Time: {booking_details['inspection_time']}
        - Address: {booking_details['address']}
        
        Our certified inspector will visit your location at the scheduled time.
        
        Thank you for choosing CarValueAI!
        
        Best regards,
        CarValueAI Team
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

# ===========================
# Authentication Endpoints
# ===========================

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """User signup endpoint"""
    try:
        data = request.json
        
        if not data.get('name') or not data.get('email') or not data.get('password'):
            return jsonify({'status': 'error', 'error': 'Missing required fields'}), 400
        
        name = data['name'].strip()
        email = data['email'].strip().lower()
        password = data['password']
        
        if '@' not in email or '.' not in email.split('@')[1]:
            return jsonify({'status': 'error', 'error': 'Invalid email format'}), 400
        
        if len(password) < 6:
            return jsonify({'status': 'error', 'error': 'Password must be at least 6 characters'}), 400
        
        if mongodb_connected:
            existing_user = collections['users'].find_one({'email': email})
            if existing_user:
                return jsonify({'status': 'error', 'error': 'Email already registered'}), 400
            
            user_id = f"USER_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            hashed_password = hash_password(password)
            
            user_doc = {
                'user_id': user_id,
                'name': name,
                'email': email,
                'password': hashed_password,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            collections['users'].insert_one(user_doc)
            
            token = create_jwt_token(user_id, email)
            
            return jsonify({
                'status': 'success',
                'user_id': user_id,
                'token': token,
                'message': 'Account created successfully'
            }), 201
        else:
            return jsonify({'status': 'error', 'error': 'Database not connected'}), 500
    
    except Exception as e:
        print(f"Signup error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 400

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.json
        
        if not data.get('email') or not data.get('password'):
            return jsonify({'status': 'error', 'error': 'Missing email or password'}), 400
        
        email = data['email'].strip().lower()
        password = data['password']
        
        if mongodb_connected:
            user = collections['users'].find_one({'email': email})
            
            if not user:
                return jsonify({'status': 'error', 'error': 'Invalid email or password'}), 401
            
            if not verify_password(password, user['password']):
                return jsonify({'status': 'error', 'error': 'Invalid email or password'}), 401
            
            token = create_jwt_token(user['user_id'], email)
            
            collections['users'].update_one(
                {'user_id': user['user_id']},
                {'$set': {'last_login': datetime.now()}}
            )
            
            return jsonify({
                'status': 'success',
                'user_id': user['user_id'],
                'token': token,
                'name': user['name'],
                'email': user['email'],
                'message': 'Login successful'
            }), 200
        else:
            return jsonify({'status': 'error', 'error': 'Database not connected'}), 500
    
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 400

@app.route('/api/auth/logout', methods=['POST'])
@token_required
def logout():
    """User logout endpoint"""
    return jsonify({
        'status': 'success',
        'message': 'Logged out successfully'
    }), 200

@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_user():
    """Get current user profile"""
    try:
        if mongodb_connected:
            user = collections['users'].find_one({'user_id': request.user_id})
            
            if user:
                return jsonify({
                    'status': 'success',
                    'user_id': user['user_id'],
                    'name': user['name'],
                    'email': user['email'],
                    'created_at': user['created_at'].isoformat()
                }), 200
            else:
                return jsonify({'status': 'error', 'error': 'User not found'}), 404
        else:
            return jsonify({'status': 'error', 'error': 'Database not connected'}), 500
    
    except Exception as e:
        print(f"Get user error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 400

@app.route('/api/auth/verify-token', methods=['POST'])
def verify_token():
    """Verify if token is valid"""
    try:
        data = request.json
        token = data.get('token')
        
        if not token:
            return jsonify({'status': 'error', 'error': 'Token is missing'}), 400
        
        payload = verify_jwt_token(token)
        
        if payload:
            return jsonify({
                'status': 'success',
                'valid': True,
                'user_id': payload['user_id'],
                'email': payload['email']
            }), 200
        else:
            return jsonify({
                'status': 'success',
                'valid': False
            }), 200
    
    except Exception as e:
        print(f"Token verification error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 400

# ===========================
# Protected Car Prediction Endpoint
# ===========================

@app.route('/api/predict', methods=['POST'])
@token_required
def predict():
    """Predict car price (requires authentication)"""
    try:
        data = request.json
        
        required_fields = ['name', 'year', 'km_driven', 'fuel', 'seller_type', 
                         'transmission', 'owner']
        
        for field in required_fields:
            if field not in data:
                return jsonify({'status': 'error', 'error': f'Missing field: {field}'}), 400
        
        if model is not None:
            features = prepare_features(data)
            features_scaled = scaler.transform(features)
            predicted_price = int(model.predict(features_scaled)[0])
            predicted_price = max(50000, min(predicted_price, 5000000))
        else:
            predicted_price = 450000
        
        car_id = f"CAR_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        if mongodb_connected:
            car_doc = {
                'car_id': car_id,
                'user_id': request.user_id,
                'car_details': data,
                'predicted_price': predicted_price,
                'created_at': datetime.now()
            }
            collections['cars'].insert_one(car_doc)
        
        return jsonify({
            'status': 'success',
            'predicted_price': predicted_price,
            'car_id': car_id
        })
    
    except Exception as e:
        print(f"Prediction error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 400

# ===========================
# Payment and Booking Endpoints
# ===========================

@app.route('/api/create-order', methods=['POST'])
@token_required
def create_order():
    """Create Razorpay order"""
    try:
        if razorpay_client is None:
            return jsonify({'status': 'error', 'error': 'Payment service not configured'}), 500
        
        data = request.json
        amount = data.get('amount', 50000)
        
        order_data = {
            'amount': amount,
            'currency': 'INR',
            'payment_capture': 1
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        if mongodb_connected:
            order_doc = {
                'order_id': order['id'],
                'amount': amount,
                'user_id': request.user_id,
                'car_id': data.get('car_id'),
                'customer_name': data.get('customer_name'),
                'customer_email': data.get('customer_email'),
                'customer_phone': data.get('customer_phone'),
                'status': 'created',
                'created_at': datetime.now()
            }
            collections['payments'].insert_one(order_doc)
        
        return jsonify({
            'status': 'success',
            'order_id': order['id'],
            'amount': order['amount'],
            'currency': order['currency'],
            'key_id': RAZORPAY_KEY_ID
        })
    
    except Exception as e:
        print(f"Order creation error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 400

@app.route('/api/verify-payment', methods=['POST'])
@token_required
def verify_payment():
    """Verify Razorpay payment signature"""
    try:
        data = request.json
        
        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            f"{data['order_id']}|{data['payment_id']}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        if generated_signature == data['signature']:
            if mongodb_connected:
                collections['payments'].update_one(
                    {'order_id': data['order_id']},
                    {'$set': {
                        'payment_id': data['payment_id'],
                        'signature': data['signature'],
                        'status': 'verified',
                        'verified_at': datetime.now()
                    }}
                )
            
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'error': 'Invalid signature'}), 400
    
    except Exception as e:
        print(f"Payment verification error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 400

@app.route('/api/book-inspection', methods=['POST'])
@token_required
def book_inspection():
    """Book inspection after successful payment"""
    try:
        data = request.json
        booking_id = f"BOOK_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        booking_doc = {
            'booking_id': booking_id,
            'user_id': request.user_id,
            'car_id': data.get('car_id'),
            'order_id': data.get('order_id'),
            'customer_name': data.get('customer_name'),
            'customer_email': data.get('customer_email'),
            'customer_phone': data.get('customer_phone'),
            'address': data.get('address'),
            'inspection_date': data.get('inspection_date'),
            'inspection_time': data.get('inspection_time'),
            'status': 'confirmed',
            'created_at': datetime.now()
        }
        
        if mongodb_connected:
            collections['bookings'].insert_one(booking_doc)
        
        send_booking_email(data.get('customer_email'), booking_doc)
        
        return jsonify({
            'status': 'success',
            'booking_id': booking_id
        })
    
    except Exception as e:
        print(f"Booking error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 400

# ===========================
# Health Check
# ===========================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'model_loaded': model is not None,
        'database_connected': mongodb_connected,
        'razorpay_configured': razorpay_client is not None,
        'timestamp': datetime.now().isoformat()
    })

# ===========================
# Main
# ===========================
    if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
