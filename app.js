// ===========================
// Configuration
// ===========================
const CONFIG = {
    API_URL: 'https://carvalueai-6.onrender.com/',
    RAZORPAY_KEY: 'rzp_live_RTqBb8Uuk3L4QG'
};

// ===========================
// Global Variables
// ===========================
let currentCarId = null;
let currentOrderId = null;
let predictedPrice = 0;

// ===========================
// Utility Functions
// ===========================

function showLoading(show) {
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = show ? 'flex' : 'none';
    }
}

function showSuccess(message) {
    alert('✅ ' + message);
}

function showError(message) {
    console.error('Error:', message);
    alert('❌ ' + message);
}

function formatCurrency(amount) {
    return '₹' + amount.toLocaleString('en-IN');
}

function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) {
        console.error('Form not found:', formId);
        return false;
    }
    
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    
    for (let input of inputs) {
        if (!input.value.trim()) {
            showError(`Please fill in ${input.previousElementSibling?.textContent || input.name}`);
            input.focus();
            return false;
        }
    }
    return true;
}

function scrollToElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function setMinInspectionDate() {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateStr = tomorrow.toISOString().split('T')[0];
    const dateInput = document.getElementById('inspection_date');
    if (dateInput) {
        dateInput.setAttribute('min', dateStr);
    }
}

// ===========================
// Price Prediction
// ===========================

function getCarData() {
    return {
        name: document.getElementById('model')?.value || document.getElementById('brand')?.value || '',
        year: parseInt(document.getElementById('year')?.value || 2015),
        km_driven: parseInt(document.getElementById('km_driven')?.value || 0),
        fuel: document.getElementById('fuel')?.value || 'Petrol',
        seller_type: document.getElementById('seller_type')?.value || 'Individual',
        transmission: document.getElementById('transmission')?.value || 'Manual',
        owner: document.getElementById('owner')?.value || 'First Owner',
        mileage: parseFloat(document.getElementById('mileage')?.value) || null,
        engine: parseInt(document.getElementById('engine')?.value) || null,
        max_power: parseFloat(document.getElementById('max_power')?.value) || null,
        seats: parseInt(document.getElementById('seats')?.value) || 5
    };
}

async function predictPrice() {
    console.log('Starting price prediction...');
    
    if (!validateForm('predictionForm')) {
        console.log('Form validation failed');
        return;
    }

    showLoading(true);
    const carData = getCarData();
    
    console.log('Car data:', carData);

    try {
        const token = localStorage.getItem('authToken');
        
        if (!token) {
            showError('No authentication token found. Please login again.');
            window.location.href = 'auth.html';
            return;
        }

        const response = await fetch(`${CONFIG.API_URL}/predict`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(carData)
        });

        console.log('Response status:', response.status);

        if (!response.ok) {
            if (response.status === 401) {
                showError('Session expired. Please login again.');
                localStorage.removeItem('authToken');
                window.location.href = 'auth.html';
                return;
            }
            const errorData = await response.text();
            console.error('Error response:', errorData);
            throw new Error(`HTTP ${response.status}: ${errorData}`);
        }

        const data = await response.json();
        console.log('Prediction response:', data);

        if (data.status === 'success') {
            currentCarId = data.car_id;
            predictedPrice = data.predicted_price;
            
            console.log('Prediction successful:', {
                carId: currentCarId,
                price: predictedPrice
            });
            
            displayPredictionResults(data.predicted_price);
            
            const resultsCard = document.getElementById('resultsCard');
            if (resultsCard) {
                resultsCard.style.display = 'block';
            }
            
            setTimeout(() => {
                scrollToElement('resultsCard');
            }, 100);
        } else {
            throw new Error(data.error || 'Failed to predict price');
        }
    } catch (error) {
        console.error('Prediction Error:', error);
        showError(error.message || 'Failed to predict price. Please try again.');
    } finally {
        showLoading(false);
    }
}

function displayPredictionResults(price) {
    const priceElement = document.getElementById('predictedPrice');
    const rangeElement = document.getElementById('priceRange');
    
    if (!priceElement || !rangeElement) {
        console.error('Result elements not found');
        return;
    }
    
    const minPrice = Math.floor(price * 0.9);
    const maxPrice = Math.ceil(price * 1.1);
    
    animateValue(priceElement, 0, price, 1500);
    
    rangeElement.textContent = `${formatCurrency(minPrice)} - ${formatCurrency(maxPrice)}`;
}

function animateValue(element, start, end, duration) {
    let startTimestamp = null;
    
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const currentValue = Math.floor(progress * (end - start) + start);
        element.textContent = formatCurrency(currentValue);
        
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    
    window.requestAnimationFrame(step);
}

// ===========================
// Inspection Booking
// ===========================

function showInspectionForm() {
    const inspectionCard = document.getElementById('inspectionCard');
    if (inspectionCard) {
        inspectionCard.style.display = 'block';
        setTimeout(() => {
            scrollToElement('inspectionCard');
        }, 100);
    }
}

function getCustomerData() {
    return {
        name: document.getElementById('customer_name')?.value || '',
        email: document.getElementById('customer_email')?.value || '',
        phone: document.getElementById('customer_phone')?.value || '',
        address: document.getElementById('address')?.value || '',
        inspection_date: document.getElementById('inspection_date')?.value || ''
    };
}

async function initiatePayment() {
    if (!validateForm('inspectionForm')) {
        return;
    }

    if (!currentCarId) {
        showError('Please predict the car price first');
        return;
    }

    showLoading(true);
    const customerData = getCustomerData();

    try {
        const token = localStorage.getItem('authToken');
        
        if (!token) {
            showError('No authentication token found. Please login again.');
            window.location.href = 'auth.html';
            return;
        }

        const response = await fetch(`${CONFIG.API_URL}/create-order`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                amount: 50000,
                car_id: currentCarId,
                customer_name: customerData.name,
                customer_email: customerData.email,
                customer_phone: customerData.phone
            })
        });

        if (!response.ok) {
            throw new Error('Failed to create order');
        }

        const orderData = await response.json();

        if (orderData.status === 'success') {
            currentOrderId = orderData.order_id;
            openRazorpayCheckout(orderData, customerData);
        } else {
            showError(orderData.error || 'Failed to create payment order');
        }
    } catch (error) {
        console.error('Payment Error:', error);
        showError('Failed to initiate payment. Please try again.');
    } finally {
        showLoading(false);
    }
}

function openRazorpayCheckout(orderData, customerData) {
    const options = {
        key: orderData.key_id || CONFIG.RAZORPAY_KEY,
        amount: orderData.amount,
        currency: orderData.currency || 'INR',
        name: 'CarValueAI',
        description: 'Professional Car Inspection Service',
        image: 'https://via.placeholder.com/100x100?text=🚗',
        order_id: orderData.order_id,
        handler: function(response) {
            verifyPayment(response);
        },
        prefill: {
            name: customerData.name,
            email: customerData.email,
            contact: customerData.phone
        },
        notes: {
            car_id: currentCarId,
            inspection_date: customerData.inspection_date
        },
        theme: {
            color: '#2563eb'
        },
        modal: {
            ondismiss: function() {
                showError('Payment cancelled. Please try again when ready.');
            }
        }
    };

    const rzp = new Razorpay(options);
    
    rzp.on('payment.failed', function(response) {
        showError('Payment failed: ' + response.error.description);
    });
    
    rzp.open();
}

async function verifyPayment(paymentResponse) {
    showLoading(true);

    try {
        const token = localStorage.getItem('authToken');
        
        if (!token) {
            showError('No authentication token found. Please login again.');
            window.location.href = 'auth.html';
            return;
        }

        const response = await fetch(`${CONFIG.API_URL}/verify-payment`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                order_id: paymentResponse.razorpay_order_id,
                payment_id: paymentResponse.razorpay_payment_id,
                signature: paymentResponse.razorpay_signature
            })
        });

        if (!response.ok) {
            throw new Error('Payment verification failed');
        }

        const data = await response.json();

        if (data.status === 'success') {
            await bookInspection(paymentResponse.razorpay_order_id);
        } else {
            showError('Payment verification failed. Please contact support.');
        }
    } catch (error) {
        console.error('Verification Error:', error);
        showError('Failed to verify payment. Please contact support with your payment details.');
    } finally {
        showLoading(false);
    }
}

async function bookInspection(orderId) {
    const customerData = getCustomerData();

    try {
        const token = localStorage.getItem('authToken');
        
        if (!token) {
            showError('No authentication token found. Please login again.');
            window.location.href = 'auth.html';
            return;
        }

        const response = await fetch(`${CONFIG.API_URL}/book-inspection`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                car_id: currentCarId,
                order_id: orderId,
                customer_name: customerData.name,
                customer_email: customerData.email,
                customer_phone: customerData.phone,
                address: customerData.address,
                inspection_date: customerData.inspection_date,
                inspection_time: '10:00 AM'
            })
        });

        if (!response.ok) {
            throw new Error('Failed to book inspection');
        }

        const data = await response.json();

        if (data.status === 'success') {
            showSuccess(
                `Inspection booked successfully!\n\n` +
                `Booking ID: ${data.booking_id}\n` +
                `Date: ${customerData.inspection_date}\n\n` +
                `You will receive a confirmation email shortly.`
            );
            
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showError(data.error || 'Failed to book inspection');
        }
    } catch (error) {
        console.error('Booking Error:', error);
        showError('Failed to book inspection. Please contact support.');
    }
}

// ===========================
// Event Listeners
// ===========================

document.addEventListener('DOMContentLoaded', function() {
    console.log('CarValueAI initialized');
    
    setMinInspectionDate();
    
    const inputs = document.querySelectorAll('.form-input, .form-select, .form-textarea');
    inputs.forEach(input => {
        input.addEventListener('invalid', function(e) {
            e.preventDefault();
            this.classList.add('error');
        });
        
        input.addEventListener('input', function() {
            this.classList.remove('error');
        });
    });
    
    const predictionForm = document.getElementById('predictionForm');
    if (predictionForm) {
        predictionForm.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
                e.preventDefault();
                predictPrice();
            }
        });
    }
    
    console.log('All listeners attached');
});

// ===========================
// Export functions (for testing)
// ===========================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        predictPrice,
        initiatePayment,
        showInspectionForm,
        formatCurrency
    };

}
