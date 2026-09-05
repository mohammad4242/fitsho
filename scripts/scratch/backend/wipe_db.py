import os

from sqlalchemy import create_engine
from sqlalchemy.schema import MetaData

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test",
)

engine = create_engine(TEST_DATABASE_URL)
meta = MetaData()
meta.reflect(bind=engine)
meta.drop_all(bind=engine)
print("Wiped!")
