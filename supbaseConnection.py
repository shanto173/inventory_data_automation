import logging
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Database connection string with SSL enabled
DATABASE_URL = 'postgresql+psycopg2://postgres:shanto8616@db.flidrqugtnmhnqspqthb.supabase.co:5432/postgres?sslmode=disable'

# Create engine
logger.info("Setting up database connection...")
try:
    engine = create_engine(DATABASE_URL)
    logger.info("Engine created successfully.")

    # Test connection
    with engine.connect() as conn:
        logger.info("✅ Connection successful!")
        # You can also print out some basic info about the connection
        logger.info(f"Database connected: {conn.dialect.name} on {conn.engine.url.host}")
    
except OperationalError as e:
    logger.error(f"Connection failed: {e}")
