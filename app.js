const express = require('express');
const cors = require('cors');
const mongoose = require('mongoose');
require('dotenv').config();

const app = express();

// ===========================
// CORS Configuration (MUST BE FIRST!)
// ===========================
const allowedOrigins = [
    'https://carfrontend10.onrender.com',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:5500',
    'http://127.0.0.1:5500'
];

const corsOptions = {
    origin: function (origin, callback) {
        // Allow requests with no origin (like mobile apps, Postman, curl)
        if (!origin) return callback(null, true);
        
        if (allowedOrigins.includes(origin)) {
            callback(null, true);
        } else {
            console.log('Blocked by CORS:', origin);
            callback(new Error('Not allowed by CORS'));
        }
    },
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With', 'Accept'],
    exposedHeaders: ['Content-Length', 'X-Requested-With'],
    maxAge: 86400 // 24 hours - cache preflight requests
};

// Apply CORS middleware globally
app.use(cors(corsOptions));

// Handle preflight requests explicitly for all routes
app.options('*', cors(corsOptions));

// ===========================
// Body Parser Middleware
// ===========================
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// ===========================
// Request Logging Middleware (optional but helpful)
// ===========================
app.use((req, res, next) => {
    console.log(`${new Date().toISOString()} - ${req.method} ${req.path}`);
    console.log('Origin:', req.headers.origin);
    console.log('Headers:', req.headers);
    next();
});

// ===========================
// Database Connection
// ===========================
const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/carvalueai';

mongoose.connect(MONGODB_URI, {
    useNewUrlParser: true,
    useUnifiedTopology: true
})
.then(() => {
    console.log('✅ Connected to MongoDB');
})
.catch((err) => {
    console.error('❌ MongoDB connection error:', err);
    process.exit(1);
});

// Handle MongoDB connection errors after initial connection
mongoose.connection.on('error', (err) => {
    console.error('MongoDB error:', err);
});

mongoose.connection.on('disconnected', () => {
    console.log('MongoDB disconnected');
});

// ===========================
// Health Check Route (before auth)
// ===========================
app.get('/', (req, res) => {
    res.json({ 
        status: 'ok', 
        message: 'CarValueAI API is running',
        timestamp: new Date().toISOString(),
        cors: 'enabled',
        allowedOrigins: allowedOrigins
    });
});

app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        database: mongoose.connection.readyState === 1 ? 'connected' : 'disconnected',
        uptime: process.uptime(),
        timestamp: new Date().toISOString()
    });
});

// ===========================
// Import Routes
// ===========================
const authRoutes = require('./routes/auth');
const predictionRoutes = require('./routes/prediction');
const paymentRoutes = require('./routes/payment');
const inspectionRoutes = require('./routes/inspection');

// ===========================
// Mount Routes
// ===========================
app.use('/auth', authRoutes);
app.use('/api/predict', predictionRoutes);
app.use('/api/payment', paymentRoutes);
app.use('/api/inspection', inspectionRoutes);

// Alternative route mounting if your frontend calls directly
app.post('/predict', require('./middleware/auth'), require('./controllers/prediction').predict);
app.post('/create-order', require('./middleware/auth'), require('./controllers/payment').createOrder);
app.post('/verify-payment', require('./middleware/auth'), require('./controllers/payment').verifyPayment);
app.post('/book-inspection', require('./middleware/auth'), require('./controllers/inspection').bookInspection);

// ===========================
// 404 Handler
// ===========================
app.use((req, res) => {
    res.status(404).json({
        status: 'error',
        error: 'Route not found',
        path: req.path,
        method: req.method
    });
});

// ===========================
// Global Error Handler
// ===========================
app.use((err, req, res, next) => {
    console.error('Error:', err);
    
    // Handle CORS errors
    if (err.message === 'Not allowed by CORS') {
        return res.status(403).json({
            status: 'error',
            error: 'CORS policy: Origin not allowed',
            origin: req.headers.origin
        });
    }
    
    // Handle JWT errors
    if (err.name === 'JsonWebTokenError') {
        return res.status(401).json({
            status: 'error',
            error: 'Invalid authentication token'
        });
    }
    
    if (err.name === 'TokenExpiredError') {
        return res.status(401).json({
            status: 'error',
            error: 'Authentication token expired'
        });
    }
    
    // Handle Mongoose validation errors
    if (err.name === 'ValidationError') {
        return res.status(400).json({
            status: 'error',
            error: 'Validation error',
            details: err.message
        });
    }
    
    // Default error response
    res.status(err.status || 500).json({
        status: 'error',
        error: err.message || 'Internal server error',
        ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
    });
});

// ===========================
// Graceful Shutdown
// ===========================
process.on('SIGTERM', () => {
    console.log('SIGTERM received, closing server gracefully...');
    mongoose.connection.close(false, () => {
        console.log('MongoDB connection closed');
        process.exit(0);
    });
});

process.on('SIGINT', () => {
    console.log('SIGINT received, closing server gracefully...');
    mongoose.connection.close(false, () => {
        console.log('MongoDB connection closed');
        process.exit(0);
    });
});

// ===========================
// Start Server
// ===========================
const PORT = process.env.PORT || 5000;
const server = app.listen(PORT, () => {
    console.log('=================================');
    console.log(`🚀 Server running on port ${PORT}`);
    console.log(`🌍 Environment: ${process.env.NODE_ENV || 'development'}`);
    console.log(`🔒 CORS enabled for: ${allowedOrigins.join(', ')}`);
    console.log(`📅 Started at: ${new Date().toISOString()}`);
    console.log('=================================');
});

// Handle server errors
server.on('error', (err) => {
    console.error('Server error:', err);
    process.exit(1);
});

module.exports = app;
