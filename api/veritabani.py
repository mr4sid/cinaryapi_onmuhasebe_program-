from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# "belirlediğiniz_sifre" KISMINI KENDİ ŞİFRENİZLE DEĞİŞTİRİN
SQLALCHEMY_DATABASE_URL = "postgresql://muhasebe_user:755397.mAmi@localhost/on_muhasebe_prod"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()