#!/bin/bash

echo "========================================="
echo "  CarValueAI Setup Script"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check Python version
echo -e "${YELLOW}Step 1: Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Python $python_version found${NC}"
echo ""

# Step 2: Create virtual environment
echo -e "${YELLOW}Step 2: Creating virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi
echo ""

# Step 3: Activate virtual environment and install dependencies
echo -e "${YELLOW}Step 3: Installing dependencies...${NC}"
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Step 4: Check for car_data.csv
echo -e "${YELLOW}Step 4: Checking for car_data.csv...${NC}"
if [ -f "car_data.csv" ]; then
    echo -e "${GREEN}✓ car_data.csv found${NC}"
    
    # Step 5: Train the model
    echo -e "${YELLOW}Step 5: Training ML model...${NC}"
    python3 train_model.py
    
    if [ -f "model_artifacts.pkl" ]; then
        echo -e "${GREEN}✓ Model trained successfully${NC}"
    else
        echo -e "${RED}✗ Model training failed${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ car_data.csv not found!${NC}"
    echo -e "${YELLOW}Please place your car_data.csv file in this directory${NC}"
    exit 1
fi
echo ""

# Step 6: Create .env file
echo -e "${YELLOW}Step 6: Setting up environment variables...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ .env file created${NC}"
    echo -e "${YELLOW}⚠ Please edit .env file with your credentials:${NC}"
    echo "   - MongoDB URI"
    echo "   - Razorpay Key ID"
    echo "   - Razorpay Key Secret"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi
echo ""

# Step 7: Test MongoDB connection
echo -e "${YELLOW}Step 7: Testing MongoDB connection...${NC}"
python3 << EOF
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mongodb_uri = os.getenv('MONGODB_URI')

if not mongodb_uri or mongodb_uri == 'your_mongodb_atlas_uri':
    print("⚠ Please configure MONGODB_URI in .env file")
else:
    try:
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        client.server_info()
        print("✓ MongoDB connection successful")
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}")
EOF
echo ""

# Step 8: Test Razorpay credentials
echo -e "${YELLOW}Step 8: Checking Razorpay credentials...${NC}"
python3 << EOF
import os
from dotenv import load_dotenv

load_dotenv()
key_id = os.getenv('RAZORPAY_KEY_ID')
key_secret = os.getenv('RAZORPAY_KEY_SECRET')

if not key_id or key_id == 'your_key_id':
    print("⚠ Please configure RAZORPAY_KEY_ID in .env file")
elif not key_secret or key_secret == 'your_key_secret':
    print("⚠ Please configure RAZORPAY_KEY_SECRET in .env file")
else:
    print("✓ Razorpay credentials configured")
EOF
echo ""

# Step 9: Ready to run
echo "========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "========================================="
echo ""
echo "To start the backend server:"
echo "  1. Ensure .env is configured with your credentials"
echo "  2. Run: source venv/bin/activate"
echo "  3. Run: python3 app.py"
echo ""
echo "For deployment on Render:"
echo "  1. Push code to GitHub"
echo "  2. Create new Web Service on Render"
echo "  3. Add environment variables in Render dashboard"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  • Configure MongoDB Atlas (see DEPLOYMENT_GUIDE.md)"
echo "  • Set up Razorpay account (see DEPLOYMENT_GUIDE.md)"
echo "  • Update frontend app.js with your backend URL"
echo ""