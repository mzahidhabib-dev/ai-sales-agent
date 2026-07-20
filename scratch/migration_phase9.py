from platform_core.db import get_connection
from platform_core.logging_config import get_logger

logger = get_logger("migration_phase9")

def run_migration():
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Step 9.1: Create evaluations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                eval_id SERIAL PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                agent_name VARCHAR NOT NULL,
                prompt_version VARCHAR,
                metrics JSONB NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        logger.info("Successfully created evaluations table.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
