"""
Cache Service - Production Ready
Redis-based caching for all M&A analysis services
Provides distributed caching with TTL, versioning, and automatic expiration
"""

import os
import json
import logging
import hashlib
from flask import Flask, request, jsonify
from functools import wraps
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import redis
from redis.connection import ConnectionPool

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service configurations
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
REDIS_DB = int(os.getenv('REDIS_DB', 0))

class CacheService:
    """Production-ready distributed cache service"""
    
    def __init__(self):
        """Initialize Redis connection with connection pooling"""
        try:
            # Use connection pooling for better performance
            self.pool = ConnectionPool(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD if REDIS_PASSWORD else None,
                db=REDIS_DB,
                max_connections=50,
                socket_keepalive=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                decode_responses=True
            )
            
            self.redis_client = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Cache service connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            logger.warning("⚠️  Cache service will operate in degraded mode (no caching)")
            self.redis_client = None
    
    def _generate_cache_key(self, namespace: str, identifier: str, **kwargs) -> str:
        """Generate a unique cache key with namespace and parameters"""
        
        # Sort kwargs for consistent key generation
        sorted_params = sorted(kwargs.items())
        params_str = json.dumps(sorted_params, sort_keys=True)
        
        # Create hash of parameters for shorter keys
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        
        # Format: namespace:identifier:params_hash
        cache_key = f"{namespace}:{identifier}:{params_hash}"
        
        return cache_key
    
    def get(self, namespace: str, identifier: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Get value from cache
        
        Args:
            namespace: Cache namespace (e.g., 'company_data', 'peer_analysis', 'valuation')
            identifier: Primary identifier (e.g., stock symbol)
            **kwargs: Additional parameters for cache key generation
            
        Returns:
            Cached value or None if not found
        """
        
        if not self.redis_client:
            return None
        
        try:
            cache_key = self._generate_cache_key(namespace, identifier, **kwargs)
            
            cached_value = self.redis_client.get(cache_key)
            
            if cached_value:
                logger.info(f"✅ Cache HIT: {cache_key}")
                data = json.loads(cached_value)
                
                # Check if expired (additional TTL check)
                if 'expires_at' in data:
                    expires_at = datetime.fromisoformat(data['expires_at'])
                    if datetime.now() > expires_at:
                        logger.info(f"⏰ Cache EXPIRED: {cache_key}")
                        self.delete(namespace, identifier, **kwargs)
                        return None
                
                return data.get('value')
            else:
                logger.info(f"❌ Cache MISS: {cache_key}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Cache GET error for {namespace}:{identifier}: {e}")
            return None
    
    def set(self, namespace: str, identifier: str, value: Any, ttl_seconds: int = 3600, **kwargs) -> bool:
        """
        Set value in cache with TTL
        
        Args:
            namespace: Cache namespace
            identifier: Primary identifier
            value: Value to cache (must be JSON serializable)
            ttl_seconds: Time to live in seconds (default: 1 hour)
            **kwargs: Additional parameters for cache key generation
            
        Returns:
            True if successful, False otherwise
        """
        
        if not self.redis_client:
            return False
        
        try:
            cache_key = self._generate_cache_key(namespace, identifier, **kwargs)
            
            # Wrap value with metadata
            cache_data = {
                'value': value,
                'cached_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat(),
                'namespace': namespace,
                'identifier': identifier,
                'params': kwargs
            }
            
            # Serialize and store
            serialized_data = json.dumps(cache_data)
            
            # Set with TTL
            self.redis_client.setex(cache_key, ttl_seconds, serialized_data)
            
            logger.info(f"✅ Cache SET: {cache_key} (TTL: {ttl_seconds}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cache SET error for {namespace}:{identifier}: {e}")
            return False
    
    def delete(self, namespace: str, identifier: str, **kwargs) -> bool:
        """Delete value from cache"""
        
        if not self.redis_client:
            return False
        
        try:
            cache_key = self._generate_cache_key(namespace, identifier, **kwargs)
            deleted = self.redis_client.delete(cache_key)
            
            if deleted:
                logger.info(f"✅ Cache DELETE: {cache_key}")
            
            return bool(deleted)
            
        except Exception as e:
            logger.error(f"❌ Cache DELETE error for {namespace}:{identifier}: {e}")
            return False
    
    def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace"""
        
        if not self.redis_client:
            return 0
        
        try:
            # Find all keys matching namespace pattern
            pattern = f"{namespace}:*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"✅ Cache CLEAR: {namespace} ({deleted} keys deleted)")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"❌ Cache CLEAR error for namespace {namespace}: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        
        if not self.redis_client:
            return {'status': 'unavailable'}
        
        try:
            info = self.redis_client.info()
            
            return {
                'status': 'healthy',
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory_human', '0'),
                'total_keys': self.redis_client.dbsize(),
                'hit_rate': self._calculate_hit_rate(),
                'uptime_seconds': info.get('uptime_in_seconds', 0)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting cache stats: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        
        try:
            info = self.redis_client.info('stats')
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            
            total = hits + misses
            if total == 0:
                return 0.0
            
            return (hits / total) * 100
            
        except:
            return 0.0
    
    def health_check(self) -> Dict[str, Any]:
        """Health check for cache service"""
        
        if not self.redis_client:
            return {
                'status': 'unhealthy',
                'redis_connected': False,
                'error': 'Redis connection not established'
            }
        
        try:
            # Ping Redis
            self.redis_client.ping()
            
            # Test read/write
            test_key = '_health_check_test'
            test_value = {'timestamp': datetime.now().isoformat()}
            
            self.redis_client.setex(test_key, 10, json.dumps(test_value))
            retrieved = self.redis_client.get(test_key)
            self.redis_client.delete(test_key)
            
            if retrieved:
                return {
                    'status': 'healthy',
                    'redis_connected': True,
                    'read_write': 'ok',
                    'latency_ms': 'low'
                }
            else:
                return {
                    'status': 'degraded',
                    'redis_connected': True,
                    'read_write': 'failed'
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'redis_connected': False,
                'error': str(e)
            }

# Global cache service instance
cache_service = CacheService()

def require_api_key(f):
    """Decorator to require API key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != SERVICE_API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    health = cache_service.health_check()
    status_code = 200 if health['status'] == 'healthy' else 503
    return jsonify(health), status_code

@app.route('/cache/get', methods=['POST'])
@require_api_key
def get_cache():
    """Get value from cache"""
    try:
        data = request.get_json()
        namespace = data.get('namespace')
        identifier = data.get('identifier')
        params = data.get('params', {})
        
        if not namespace or not identifier:
            return jsonify({'error': 'namespace and identifier required'}), 400
        
        value = cache_service.get(namespace, identifier, **params)
        
        if value is not None:
            return jsonify({'found': True, 'value': value})
        else:
            return jsonify({'found': False}), 404
            
    except Exception as e:
        logger.error(f"Error in get_cache: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/cache/set', methods=['POST'])
@require_api_key
def set_cache():
    """Set value in cache"""
    try:
        data = request.get_json()
        namespace = data.get('namespace')
        identifier = data.get('identifier')
        value = data.get('value')
        ttl_seconds = data.get('ttl_seconds', 3600)
        params = data.get('params', {})
        
        if not namespace or not identifier or value is None:
            return jsonify({'error': 'namespace, identifier, and value required'}), 400
        
        success = cache_service.set(namespace, identifier, value, ttl_seconds, **params)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to set cache'}), 500
            
    except Exception as e:
        logger.error(f"Error in set_cache: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/cache/delete', methods=['POST'])
@require_api_key
def delete_cache():
    """Delete value from cache"""
    try:
        data = request.get_json()
        namespace = data.get('namespace')
        identifier = data.get('identifier')
        params = data.get('params', {})
        
        if not namespace or not identifier:
            return jsonify({'error': 'namespace and identifier required'}), 400
        
        success = cache_service.delete(namespace, identifier, **params)
        
        return jsonify({'success': success})
            
    except Exception as e:
        logger.error(f"Error in delete_cache: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/cache/clear/<namespace>', methods=['DELETE'])
@require_api_key
def clear_namespace(namespace):
    """Clear all keys in a namespace"""
    try:
        deleted = cache_service.clear_namespace(namespace)
        
        return jsonify({
            'success': True,
            'namespace': namespace,
            'keys_deleted': deleted
        })
            
    except Exception as e:
        logger.error(f"Error in clear_namespace: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/cache/stats', methods=['GET'])
@require_api_key
def get_stats():
    """Get cache statistics"""
    try:
        stats = cache_service.get_stats()
        return jsonify(stats)
            
    except Exception as e:
        logger.error(f"Error in get_stats: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8090))
    app.run(host='0.0.0.0', port=port, debug=False)
