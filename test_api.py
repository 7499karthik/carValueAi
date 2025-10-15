import requests
import json

API_URL = 'http://localhost:5000/api'

# Test data
test_car = {
    'name': 'Maruti Swift',
    'year': 2018,
    'km_driven': 45000,
    'fuel': 'Petrol',
    'seller_type': 'Individual',
    'transmission': 'Manual',
    'owner': 'First Owner',
    'mileage': 19.5,
    'engine': 1200,
    'max_power': 88.5,
    'seats': 5
}

print("Testing Prediction Endpoint...")
print(f"Sending: {json.dumps(test_car, indent=2)}\n")

try:
    response = requests.post(f'{API_URL}/predict', json=test_car)
    print(f"Status Code: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")