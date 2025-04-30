from sqlalchemy import create_engine

# Connection string with SSL enabled
engine = create_engine(
    'postgresql+psycopg2://postgres:shanto8616@db.flidrqugtnmhnqspqthb.supabase.co:5432/postgres?sslmode=require'
)

# Optional: test connection
with engine.connect() as conn:
    print("✅ Connection successful!")
