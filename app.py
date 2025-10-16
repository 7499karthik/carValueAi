from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import pickle
import razorpay
import hashlib
import hmac
from datetime import datetime
import os
from dotenv import load_dotenv
import numpy as np

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI', 'your_mongodb_atlas_uri')
client = MongoClient(MONGODB_URI)
db = client['carvalueai']
cars_collection = db['cars']
bookings_collection = db['bookings']
payments_collection = db['payments']

# Razorpay Configuration
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'your_key_id')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', 'your_key_secret')
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Load ML model artifacts
try:
    with open('model_artifacts.pkl', 'rb') as f:
        artifacts = pickle.load(f)
        model = artifacts['model']
        scaler = artifacts['scaler']
        label_encoders = artifacts['label_encoders']
        feature_cols = artifacts['feature_cols']
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error loading model: {e}")
    model = None

def encode_categorical_features(data):
    """Encode categorical features using saved label encoders"""
    encoded_data = data.copy()
    
    categorical_mapping = {
        'name': 'name_encoded',
        'fuel': 'fuel_encoded',
        'seller_type': 'seller_type_encoded',
        'transmission': 'transmission_encoded',
        'owner': 'owner_encoded'
    }
    
    for original_col, encoded_col in categorical_mapping.items():
        if original_col in data:
            try:
                le = label_encoders[original_col]
                # Handle unseen labels
                if data[original_col] not in le.classes_:
                    # Use the most common class
                    encoded_data[encoded_col] = 0
                else:
                    encoded_data[encoded_col] = le.transform([data[original_col]])[0]
            except Exception as e:
                print(f"Error encoding {original_col}: {e}")
                encoded_data[encoded_col] = 0
    
    return encoded_data

def prepare_features(data):
    """Prepare features for prediction"""
    current_year = 2024
    
    # Calculate derived features
    car_age = current_year - data['year']
    km_per_year = data['km_driven'] / (car_age + 1)
    power_efficiency = data['max_power'] / data['engine']
    
    # Encode categorical features
    encoded_data = encode_categorical_features(data)
    
    # Create feature array
    features = {
        'year': data['year'],
        'km_driven': data['km_driven'],
        'mileage': data['mileage'],
        'engine': data['engine'],
        'max_power': data['max_power'],
        'seats': data['seats'],
        'car_age': car_age,
        'km_per_year': km_per_year,
        'power_efficiency': power_efficiency,
        'name_encoded': encoded_data['name_encoded'],
        'fuel_encoded': encoded_data['fuel_encoded'],
        'seller_type_encoded': encoded_data['seller_type_encoded'],
        'transmission_encoded': encoded_data['transmission_encoded'],
        'owner_encoded': encoded_data['owner_encoded']
    }
    
    # Create feature array in correct order
    feature_array = np.array([[features[col] for col in feature_cols]])
    
    return feature_array

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'success',
        'message': 'CarValueAI API is running',
        'version': '1.0.0'
    })

@app.route('/api/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        
        if not model:
            return jsonify({
                'status': 'error',
                'error': 'Model not loaded'
            }), 500
        
        # Prepare features
        feature_array = prepare_features(data)
        
        # Scale features
        feature_array_scaled = scaler.transform(feature_array)
        
        # Make prediction
        predicted_price = model.predict(feature_array_scaled)[0]
        predicted_price = int(round(predicted_price))
        
        # Generate car ID
        car_id = f"CAR_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # Save to MongoDB
        car_document = {
            'car_id': car_id,
            'details': data,
            'predicted_price': predicted_price,
            'created_at': datetime.now(),
            'status': 'predicted'
        }
        cars_collection.insert_one(car_document)
        
        return jsonify({
            'status': 'success',
            'predicted_price': predicted_price,
            'car_id': car_id
        })
        
    except Exception as e:
        print(f"Prediction error: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

@app.route('/api/create-order', methods=['POST'])
def create_order():
    try:
        data = request.json
        amount = data.get('amount', 50000)  # Amount in paise (₹500)
        car_id = data.get('car_id')
        
        # Create Razorpay order
        order_data = {
            'amount': amount,
            'currency': 'INR',
            'payment_capture': 1,
            'notes': {
                'car_id': car_id,
                'customer_name': data.get('customer_name'),
                'customer_email': data.get('customer_email')
            }
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        # Save order to MongoDB
        order_document = {
            'order_id': order['id'],
            'car_id': car_id,
            'amount': amount,
            'currency': order['currency'],
            'status': 'created',
            'customer_name': data.get('customer_name'),
            'customer_email': data.get('customer_email'),
            'customer_phone': data.get('customer_phone'),
            'created_at': datetime.now()
        }
        payments_collection.insert_one(order_document)
        
        return jsonify({
            'status': 'success',
            'order_id': order['id'],
            'amount': order['amount'],
            'currency': order['currency'],
            'key_id': RAZORPAY_KEY_ID
        })
        
    except Exception as e:
        print(f"Order creation error: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

@app.route('/api/verify-payment', methods=['POST'])
def verify_payment():
    try:
        data = request.json
        order_id = data['order_id']
        payment_id = data['payment_id']
        signature = data['signature']
        
        # Verify signature
        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        if generated_signature == signature:
            # Update payment status in MongoDB
            payments_collection.update_one(
                {'order_id': order_id},
                {
                    '$set': {
                        'payment_id': payment_id,
                        'signature': signature,
                        'status': 'verified',
                        'verified_at': datetime.now()
                    }
                }
            )
            
            return jsonify({'status': 'success'})
        else:
            return jsonify({
                'status': 'error',
                'error': 'Invalid signature'
            }), 400
            
    except Exception as e:
        print(f"Payment verification error: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

@app.route('/api/book-inspection', methods=['POST'])
def book_inspection():
    try:
        data = request.json
        booking_id = f"BOOK_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # Create booking document
        booking_document = {
            'booking_id': booking_id,
            'car_id': data.get('car_id'),
            'order_id': data.get('order_id'),
            'customer_name': data.get('customer_name'),
            'customer_email': data.get('customer_email'),
            'customer_phone': data.get('customer_phone'),
            'address': data.get('address'),
            'inspection_date': data.get('inspection_date'),
            'inspection_time': data.get('inspection_time', '10:00 AM'),
            'status': 'confirmed',
            'created_at': datetime.now()
        }
        
        # Save to MongoDB
        bookings_collection.insert_one(booking_document)
        
        # Update car status
        cars_collection.update_one(
            {'car_id': data.get('car_id')},
            {'$set': {'status': 'inspection_booked'}}
        )
        
        return jsonify({
            'status': 'success',
            'booking_id': booking_id
        })
        
    except Exception as e:
        print(f"Booking error: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

@app.route('/api/bookings/<booking_id>', methods=['GET'])
def get_booking(booking_id):
    try:
        booking = bookings_collection.find_one(
            {'booking_id': booking_id},
            {'_id': 0}
        )
        
        if booking:
            # Convert datetime to string
            booking['created_at'] = booking['created_at'].isoformat()
            return jsonify({
                'status': 'success',
                'booking': booking
            })
        else:
            return jsonify({
                'status': 'error',
                'error': 'Booking not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        total_predictions = cars_collection.count_documents({})
        total_bookings = bookings_collection.count_documents({})
        total_payments = payments_collection.count_documents({'status': 'verified'})
        
        return jsonify({
            'status': 'success',
            'stats': {
                'total_predictions': total_predictions,
                'total_bookings': total_bookings,
                'total_payments': total_payments
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

# IMPORTANT: This must be at the very end of the file
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
