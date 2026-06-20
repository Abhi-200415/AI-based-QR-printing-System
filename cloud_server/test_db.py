from app.database.connection import engine
from app.database.models import Base

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

print("Database Reset Successful")