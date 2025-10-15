// ===========================
// Authentication Client-Side Code
// ===========================

const AUTH_CONFIG = {
    API_URL: 'http://localhost:5000/api',
    TOKEN_KEY: 'authToken',
    USER_ID_KEY: 'userId',
    USER_NAME_KEY: 'userName'
};

// ===========================
// Token Management
// ===========================

function saveToken(token, userId, userName) {
    localStorage.setItem(AUTH_CONFIG.TOKEN_KEY, token);
    localStorage.setItem(AUTH_CONFIG.USER_ID_KEY, userId);
    localStorage.setItem(AUTH_CONFIG.USER_NAME_KEY, userName);
}

function getToken() {
    return localStorage.getItem(AUTH_CONFIG.TOKEN_KEY);
}

function removeToken() {
    localStorage.removeItem(AUTH_CONFIG.TOKEN_KEY);
    localStorage.removeItem(AUTH_CONFIG.USER_ID_KEY);
    localStorage.removeItem(AUTH_CONFIG.USER_NAME_KEY);
}

function isAuthenticated() {
    const token = getToken();
    return token !== null && token !== undefined && token !== '';
}

// ===========================
// Authentication Checks
// ===========================

/**
 * Check if user is authenticated, redirect to login if not
 */
function checkAuthentication() {
    if (!isAuthenticated()) {
        // User is not logged in, redirect to auth page
        window.location.href = 'auth.html';
        return false;
    }
    
    // Load user info
    loadUserInfo();
    return true;
}

/**
 * Load and display user information
 */
async function loadUserInfo() {
    const token = getToken();
    
    try {
        const response = await fetch(`${AUTH_CONFIG.API_URL}/auth/me`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const data = await response.json();
            if (data.status === 'success') {
                const userName = data.name;
                const userEmail = data.email;
                
                // Update header with user info
                updateUserHeader(userName, userEmail);
                
                // Save user name
                localStorage.setItem(AUTH_CONFIG.USER_NAME_KEY, userName);
            }
        } else if (response.status === 401) {
            // Token expired or invalid
            removeToken();
            window.location.href = 'auth.html';
        }
    } catch (error) {
        console.error('Error loading user info:', error);
    }
}

/**
 * Update header with user information
 */
function updateUserHeader(name, email) {
    const userNameEl = document.getElementById('userName');
    if (userNameEl) {
        userNameEl.textContent = `Welcome, ${name}`;
    }
}

/**
 * Logout user
 */
async function logout() {
    const token = getToken();
    
    try {
        // Call logout endpoint
        await fetch(`${AUTH_CONFIG.API_URL}/auth/logout`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        // Remove token from storage
        removeToken();
        
        // Redirect to auth page
        window.location.href = 'auth.html';
    }
}

// ===========================
// API Request Helper
// ===========================

/**
 * Make authenticated API request
 */
async function authenticatedFetch(endpoint, options = {}) {
    const token = getToken();
    
    if (!token) {
        console.error('No authentication token found');
        window.location.href = 'auth.html';
        return null;
    }

    const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers
    };

    try {
        const response = await fetch(`${AUTH_CONFIG.API_URL}${endpoint}`, {
            ...options,
            headers
        });

        // If unauthorized, redirect to login
        if (response.status === 401) {
            removeToken();
            window.location.href = 'auth.html';
            return null;
        }

        return response;
    } catch (error) {
        console.error('API request error:', error);
        throw error;
    }
}

// ===========================
// Initialization on Page Load
// ===========================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Auth system initialized');
    
    // Only check auth on main pages (not on auth.html)
    if (!window.location.pathname.includes('auth.html')) {
        checkAuthentication();
    }
});

// ===========================
// Export for use in app.js
// ===========================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getToken,
        removeToken,
        isAuthenticated,
        authenticatedFetch,
        logout
    };
}