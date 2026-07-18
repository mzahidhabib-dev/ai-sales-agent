import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from platform_core.db import get_connection

def migrate():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create memory table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                memory_id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(50) REFERENCES tenants(tenant_id),
                prospect_id INT REFERENCES prospects(prospect_id),
                data JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_memory_tenant_prospect UNIQUE (tenant_id, prospect_id)
            );
        """)
        
        conn.commit()
        print("Successfully created memory table.")
    except Exception as e:
        print(f"Migration failed: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip()
    except Exception as e:
        pass
    migrate()
