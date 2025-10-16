from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import jwt
from functools import wraps

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# ===========================
# CORS Configuration (CRITICAL!)
# ===========================
CORS(app, 
     resources={r"/*": {
         "origins": [
             "https://carfrontend10.onrender.com",
             "http://localhost:3000",
             "http://localhost:5500",
             "http://127.0.0.1:5500"
         ],
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
         "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
         "expose_headers": ["Content-Length", "X-Requested-With"],
         "supports_credentials": True,
         "max_age": 86400
     }})

# ===========================
# Configuration
# ===========================
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
app.config['MONGODB_URI'] = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/carvalueai')
app.config['RAZORPAY_KEY_ID'] = os.getenv('RAZORPAY_KEY_ID')
app.config['RAZORPAY_KEY_SECRET'] = os.getenv('RAZORPAY_KEY_SECRET')

# ===========================
# Database Connection
# ===========================
try:
    client = MongoClient(app.config['MONGODB_URI'])
    db = client.get_database()
    print("✅ Connected to MongoDB")
except Exception as e:
    print(f"❌ MongoDB connection error: {e}")
    db = None

# ===========================
# CRITICAL: Handle OPTIONS requests FIRST
# ===========================
@app.before_request
def handle_options():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Max-Age'] = '86400'
        return response, 200

# ===========================
# Request Logging Middleware
# ===========================
@app.before_request
def log_request():
    if request.method != 'OPTIONS':  # Don't log OPTIONS spam
        print(f"{datetime.now().isoformat()} - {request.method} {request.path}")
        print(f"Origin: {request.headers.get('Origin')}")

# ===========================
# Authentication Decorator (Simplified - OPTIONS already handled)
# ===========================
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]  # Bearer TOKEN
            except IndexError:
                return jsonify({
                    'status': 'error',
                    'error': 'Invalid token format'
                }), 401
        
        if not token:
            return jsonify({
                'status': 'error',
                'error': 'Access denied. No token provided.'
            }), 401
        
        try:
            # Verify token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.current_user = data
        except jwt.ExpiredSignatureError:
            return jsonify({
                'status': 'error',
                'error': 'Token expired. Please login again.'
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'status': 'error',
                'error': 'Invalid token'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated

# ===========================
# Health Check Routes
# ===========================
@app.route('/', methods=['GET', 'OPTIONS'])
def home():
    return jsonify({
        'status': 'ok',
        'message': 'CarValueAI API is running',
        'timestamp': datetime.now().isoformat(),
        'cors': 'enabled'
    }), 200

@app.route('/health', methods=['GET', 'OPTIONS'])
def health():
    db_status = 'connected' if db is not None else 'disconnected'
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'timestamp': datetime.now().isoformat()
    }), 200

# ===========================
# Auth Routes
# ===========================
@app.route('/auth/register', methods=['POST', 'OPTIONS'])
def register():
    try:
        data = request.get_json()
        # Your registration logic here
        return jsonify({
            'status': 'success',
            'message': 'User registered successfully'
        }), 201
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

@app.route('/auth/login', methods=['POST', 'OPTIONS'])
def login():
    try:
        data = request.get_json()
        # Your login logic here
        # Generate JWT token
        token = jwt.encode({
            'user_id': 'user_id_here',
            'exp': datetime.utcnow() + timedelta(days=30)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'status': 'success',
            'token': token,
            'user': {
                'id': 'user_id_here',
                'name': 'User Name',
                'email': data.get('email')
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

@app.route('/auth/me', methods=['GET', 'OPTIONS'])
@token_required
def get_current_user():
    try:
        user_id = request.current_user.get('user_id')
        # Fetch user from database
        return jsonify({
            'status': 'success',
            'user': {
                'id': user_id,
                'name': 'User Name',
                'email': 'user@email.com'
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

# ===========================
# Prediction Routes
# ===========================
@app.route('/predict', methods=['POST', 'OPTIONS'])
@token_required
def predict():
    try:
        data = request.get_json()
        # Your ML prediction logic here
        predicted_price = 500000  # Example price
        
        return jsonify({
            'status': 'success',
            'predicted_price': predicted_price,
            'car_id': 'generated_car_id'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

# ===========================
# Payment Routes
# ===========================
@app.route('/create-order', methods=['POST', 'OPTIONS'])
@token_required
def create_order():
    try:
        import razorpay
        
        data = request.get_json()
        amount = data.get('amount', 50000)
        
        client = razorpay.Client(auth=(
            app.config['RAZORPAY_KEY_ID'], 
            app.config['RAZORPAY_KEY_SECRET']
        ))
        
        order_data = {
            'amount': amount,
            'currency': 'INR',
            'payment_capture': 1
        }
        
        order = client.order.create(data=order_data)
        
        return jsonify({
            'status': 'success',
            'order_id': order['id'],
            'amount': order['amount'],
            'currency': order['currency'],
            'key_id': app.config['RAZORPAY_KEY_ID']
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

@app.route('/verify-payment', methods=['POST', 'OPTIONS'])
@token_required
def verify_payment():
    try:
        import razorpay
        
        data = request.get_json()
        
        client = razorpay.Client(auth=(
            app.config['RAZORPAY_KEY_ID'], 
            app.config['RAZORPAY_KEY_SECRET']
        ))
        
        # Verify payment signature
        params_dict = {
            'razorpay_order_id': data.get('order_id'),
            'razorpay_payment_id': data.get('payment_id'),
            'razorpay_signature': data.get('signature')
        }
        
        client.utility.verify_payment_signature(params_dict)
        
        return jsonify({
            'status': 'success',
            'message': 'Payment verified successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

@app.route('/book-inspection', methods=['POST', 'OPTIONS'])
@token_required
def book_inspection():
    try:
        data = request.get_json()
        # Your booking logic here
        
        booking_id = f"BOOK{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return jsonify({
            'status': 'success',
            'booking_id': booking_id,
            'message': 'Inspection booked successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

# ===========================
# Error Handlers
# ===========================
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'error': 'Route not found',
        'path': request.path
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'status': 'error',
        'error': 'Internal server error'
    }), 500

# ===========================
# Run Server
# ===========================
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print('=' * 50)
    print(f'🚀 Server running on port {port}')
    print(f'🔒 CORS enabled for frontend')
    print(f'📅 Started at: {datetime.now().isoformat()}')
    print('=' * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
