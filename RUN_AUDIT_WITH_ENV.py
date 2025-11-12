"""
Production Audit Runner - Loads .env file before running audit
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file
def load_env_file():
    """Load .env file into environment"""
    env_file = Path('.env')
    
    if not env_file.exists():
        print("❌ ERROR: .env file not found!")
        print("   Please create .env file with required variables")
        print("   Copy from .env.example if needed")
        return False
    
    print("📄 Loading environment variables from .env...")
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                # Set environment variable
                os.environ[key] = value
                
    print("✅ Environment variables loaded\n")
    return True

# Load environment first
if not load_env_file():
    sys.exit(1)

# Now import and run the audit
from PRODUCTION_AUDIT_SCRIPT import main

if __name__ == '__main__':
    main()
