import pandas as pd
import numpy as np
import pickle
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings('ignore')

def load_and_preprocess_data(csv_path='car_data.csv'):
    """Load and preprocess the car data"""
    print("Loading data...")
    df = pd.read_csv(csv_path)
    
    print(f"Dataset shape: {df.shape}")
    print(f"\nColumns found: {df.columns.tolist()}")
    
    # Handle missing values
    print("\nHandling missing values...")
    df = df.dropna()
    
    # Remove duplicates
    df = df.drop_duplicates()
    
    print(f"Dataset shape after cleaning: {df.shape}")
    
    return df

def add_missing_features(df):
    """Add missing features with estimated values based on car data"""
    print("\nAdding estimated features (mileage, engine, max_power, seats)...")
    
    # Estimate based on year and fuel type
    def estimate_mileage(row):
        base_mileage = {
            'Petrol': 18,
            'Diesel': 22,
            'CNG': 25,
            'Electric': 30,
            'LPG': 20
        }
        mileage = base_mileage.get(row['fuel'], 18)
        # Older cars tend to have lower mileage
        age = 2024 - row['year']
        mileage = mileage * (1 - age * 0.01)
        return max(10, mileage)
    
    def estimate_engine(row):
        # Estimate based on selling price and year
        if row['selling_price'] > 1000000:
            return np.random.randint(1800, 2500)
        elif row['selling_price'] > 500000:
            return np.random.randint(1200, 1800)
        else:
            return np.random.randint(800, 1200)
    
    def estimate_power(row):
        # Power roughly correlates with engine size
        if 'engine' in row:
            return row['engine'] * 0.07 + np.random.uniform(-10, 10)
        return 70
    
    def estimate_seats(row):
        # Most cars are 5-seaters
        if row['selling_price'] > 1500000:
            return np.random.choice([5, 7], p=[0.6, 0.4])
        return 5
    
    # Add missing columns if they don't exist
    if 'mileage' not in df.columns:
        df['mileage'] = df.apply(estimate_mileage, axis=1)
    
    if 'engine' not in df.columns:
        df['engine'] = df.apply(estimate_engine, axis=1)
    
    if 'max_power' not in df.columns:
        df['max_power'] = df.apply(estimate_power, axis=1)
    
    if 'seats' not in df.columns:
        df['seats'] = df.apply(estimate_seats, axis=1)
    
    return df

def feature_engineering(df):
    """Engineer features from the data"""
    print("\nEngineering features...")
    
    # Create car age feature
    current_year = 2024
    df['car_age'] = current_year - df['year']
    
    # Create mileage per year
    df['km_per_year'] = df['km_driven'] / (df['car_age'] + 1)
    
    # Create power to weight ratio
    df['power_efficiency'] = df['max_power'] / df['engine']
    
    # Handle categorical variables
    categorical_cols = ['name', 'fuel', 'seller_type', 'transmission', 'owner']
    
    # Label encoding for categorical variables
    label_encoders = {}
    for col in categorical_cols:
        le = LabelEncoder()
        df[col + '_encoded'] = le.fit_transform(df[col].astype(str))
        label_encoders[col] = le
    
    return df, label_encoders

def train_model(df):
    """Train the Random Forest model"""
    print("\nPreparing training data...")
    
    # Select features for training
    feature_cols = [
        'year', 'km_driven', 'mileage', 'engine', 'max_power', 'seats',
        'car_age', 'km_per_year', 'power_efficiency',
        'name_encoded', 'fuel_encoded', 'seller_type_encoded',
        'transmission_encoded', 'owner_encoded'
    ]
    
    X = df[feature_cols]
    y = df['selling_price']
    
    print(f"Training with {len(X)} samples and {len(feature_cols)} features")
    
    # Split the data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    print("\nTraining Random Forest model...")
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train_scaled, y_train)
    
    # Evaluate model
    print("\nEvaluating model...")
    y_pred_train = model.predict(X_train_scaled)
    y_pred_test = model.predict(X_test_scaled)
    
    train_r2 = r2_score(y_train, y_pred_train)
    test_r2 = r2_score(y_test, y_pred_test)
    mae = mean_absolute_error(y_test, y_pred_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
    
    print(f"\n{'='*60}")
    print("MODEL PERFORMANCE METRICS")
    print(f"{'='*60}")
    print(f"Training R² Score:    {train_r2:.4f} ({train_r2*100:.2f}%)")
    print(f"Testing R² Score:     {test_r2:.4f} ({test_r2*100:.2f}%)")
    print(f"Mean Absolute Error:  ₹{mae:,.2f}")
    print(f"Root Mean Sq Error:   ₹{rmse:,.2f}")
    print(f"{'='*60}")
    
    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 10 Most Important Features:")
    print("-" * 50)
    for idx, row in feature_importance.head(10).iterrows():
        print(f"  {row['feature']:.<30} {row['importance']:.4f}")
    
    return model, scaler, feature_cols

def save_model_artifacts(model, scaler, label_encoders, feature_cols):
    """Save all model artifacts"""
    print("\nSaving model artifacts...")
    
    artifacts = {
        'model': model,
        'scaler': scaler,
        'label_encoders': label_encoders,
        'feature_cols': feature_cols
    }
    
    with open('model_artifacts.pkl', 'wb') as f:
        pickle.dump(artifacts, f)
    
    print("✓ Model artifacts saved to 'model_artifacts.pkl'")

def main():
    """Main training pipeline"""
    print("="*60)
    print("CAR PRICE PREDICTION MODEL TRAINING")
    print("="*60)
    
    try:
        # Load and preprocess data
        df = load_and_preprocess_data('car_data.csv')
        
        # Add missing features
        df = add_missing_features(df)
        
        # Feature engineering
        df, label_encoders = feature_engineering(df)
        
        # Train model
        model, scaler, feature_cols = train_model(df)
        
        # Save artifacts
        save_model_artifacts(model, scaler, label_encoders, feature_cols)
        
        print("\n" + "="*60)
        print("✓ TRAINING COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nYou can now:")
        print("  1. Run 'python app.py' to start the backend")
        print("  2. Open 'index.html' in your browser")
        print("  3. Test the car price prediction!")
        print("="*60)
        
    except Exception as e:
        print("\n" + "="*60)
        print("✗ ERROR DURING TRAINING")
        print("="*60)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()