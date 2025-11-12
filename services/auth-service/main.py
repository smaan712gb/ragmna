"""
Authentication Service
Handles user authentication, JWT tokens, and session management
"""

import os
import json
import logging
import jwt
import bcrypt
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from typing import Dict, Any, Optional
import secrets

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', secrets.token_urlsafe(32))
JWT_ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRY = int(os.getenv('ACCESS_TOKEN_EXPIRY_MINUTES', 60))  # 60 minutes
REFRESH_TOKEN_EXPIRY = int(os.getenv('REFRESH_TOKEN_EXPIRY_DAYS', 7))  # 7 days
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')

# CORS configuration
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS(app, resources={
    r"/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True
    }
})

# In-memory storage (replace with database in production)
# Format: {user_id: {password_hash, email, role, created_at}}
USERS_DB = {}
# Format: {refresh_token: {user_id, expires_at}}
REFRESH_TOKENS_DB = {}

class AuthService:
    """Handles authentication operations"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    @staticmethod
    def generate_access_token(user_id: str, email: str, role: str = 'user') -> str:
        """Generate a JWT access token"""
        payload = {
            'user_id': user_id,
            'email': email,
            'role': role,
            'type': 'access',
            'exp': datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRY),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    @staticmethod
    def generate_refresh_token(user_id: str) -> str:
        """Generate a refresh token"""
        refresh_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRY)
        
        REFRESH_TOKENS_DB[refresh_token] = {
            'user_id': user_id,
            'expires_at': expires_at
        }
        
        return refresh_token
    
    @staticmethod
    def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT access token"""
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            if payload.get('type') != 'access':
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Access token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid access token: {e}")
            return None
    
    @staticmethod
    def verify_refresh_token(refresh_token: str) -> Optional[str]:
        """Verify refresh token and return user_id"""
        token_data = REFRESH_TOKENS_DB.get(refresh_token)
        if not token_data:
            return None
        
        if datetime.utcnow() > token_data['expires_at']:
            # Token expired, remove it
            del REFRESH_TOKENS_DB[refresh_token]
            return None
        
        return token_data['user_id']
    
    @staticmethod
    def revoke_refresh_token(refresh_token: str):
        """Revoke a refresh token"""
        if refresh_token in REFRESH_TOKENS_DB:
            del REFRESH_TOKENS_DB[refresh_token]
    
    @staticmethod
    def create_user(email: str, password: str, role: str = 'user') -> Dict[str, Any]:
        """Create a new user"""
        if email in USERS_DB:
            raise ValueError("User already exists")
        
        user_id = secrets.token_urlsafe(16)
        password_hash = AuthService.hash_password(password)
        
        USERS_DB[email] = {
            'user_id': user_id,
            'email': email,
            'password_hash': password_hash,
            'role': role,
            'created_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"User created: {email} with role {role}")
        return {'user_id': user_id, 'email': email, 'role': role}
    
    @staticmethod
    def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate a user with email and password"""
        user = USERS_DB.get(email)
        if not user:
            logger.warning(f"Authentication failed: user not found - {email}")
            return None
        
        if not AuthService.verify_password(password, user['password_hash']):
            logger.warning(f"Authentication failed: invalid password - {email}")
            return None
        
        logger.info(f"User authenticated: {email}")
        return {
            'user_id': user['user_id'],
            'email': user['email'],
            'role': user['role']
        }

def require_authentication(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid authorization header'}), 401
        
        token = auth_header.split(' ')[1]
        payload = AuthService.verify_access_token(token)
        
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Add user info to request context
        request.user = payload
        return f(*args, **kwargs)
    
    return decorated_function

def require_role(required_role: str):
    """Decorator to require specific role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(request, 'user'):
                return jsonify({'error': 'Unauthorized'}), 401
            
            if request.user.get('role') != required_role:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# API Endpoints

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'auth-service',
        'version': '1.0.0'
    })

@app.route('/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        user = AuthService.create_user(email, password)
        
        # Generate tokens
        access_token = AuthService.generate_access_token(
            user['user_id'], user['email'], user['role']
        )
        refresh_token = AuthService.generate_refresh_token(user['user_id'])
        
        return jsonify({
            'user': {
                'user_id': user['user_id'],
                'email': user['email'],
                'role': user['role']
            },
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': ACCESS_TOKEN_EXPIRY * 60  # in seconds
        }), 201
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/auth/login', methods=['POST'])
def login():
    """Login a user"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        user = AuthService.authenticate_user(email, password)
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Generate tokens
        access_token = AuthService.generate_access_token(
            user['user_id'], user['email'], user['role']
        )
        refresh_token = AuthService.generate_refresh_token(user['user_id'])
        
        return jsonify({
            'user': user,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': ACCESS_TOKEN_EXPIRY * 60  # in seconds
        })
    
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/auth/refresh', methods=['POST'])
def refresh():
    """Refresh access token using refresh token"""
    try:
        data = request.get_json()
        refresh_token = data.get('refresh_token')
        
        if not refresh_token:
            return jsonify({'error': 'Refresh token is required'}), 400
        
        user_id = AuthService.verify_refresh_token(refresh_token)
        if not user_id:
            return jsonify({'error': 'Invalid or expired refresh token'}), 401
        
        # Find user by user_id
        user = next((u for u in USERS_DB.values() if u['user_id'] == user_id), None)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Generate new access token
        access_token = AuthService.generate_access_token(
            user['user_id'], user['email'], user['role']
        )
        
        return jsonify({
            'access_token': access_token,
            'expires_in': ACCESS_TOKEN_EXPIRY * 60
        })
    
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/auth/logout', methods=['POST'])
@require_authentication
def logout():
    """Logout a user (revoke refresh token)"""
    try:
        data = request.get_json()
        refresh_token = data.get('refresh_token')
        
        if refresh_token:
            AuthService.revoke_refresh_token(refresh_token)
        
        return jsonify({'message': 'Logged out successfully'})
    
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/auth/verify', methods=['GET'])
@require_authentication
def verify():
    """Verify if token is valid"""
    return jsonify({
        'valid': True,
        'user': {
            'user_id': request.user['user_id'],
            'email': request.user['email'],
            'role': request.user['role']
        }
    })

@app.route('/auth/me', methods=['GET'])
@require_authentication
def get_current_user():
    """Get current user information"""
    return jsonify({
        'user': {
            'user_id': request.user['user_id'],
            'email': request.user['email'],
            'role': request.user['role']
        }
    })

# Service-to-Service Authentication
@app.route('/auth/forward', methods=['POST'])
@require_authentication
def forward_with_service_key():
    """
    Forward authenticated request with service API key
    This endpoint validates user JWT and returns SERVICE_API_KEY for service calls
    """
    return jsonify({
        'service_api_key': SERVICE_API_KEY,
        'user_context': {
            'user_id': request.user['user_id'],
            'email': request.user['email'],
            'role': request.user['role']
        }
    })

if __name__ == '__main__':
    # Create a default admin user for testing
    try:
        AuthService.create_user(
            email='admin@example.com',
            password='admin123',  # Change in production!
            role='admin'
        )
        logger.info("Default admin user created: admin@example.com / admin123")
    except ValueError:
        logger.info("Default admin user already exists")
    
    port = int(os.getenv('PORT', 8016))
    app.run(host='0.0.0.0', port=port, debug=False)
