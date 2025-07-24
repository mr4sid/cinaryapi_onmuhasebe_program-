import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database
import logging

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FastAPI modelleri yerine doğrudan SQLAlchemy modellerini içe aktarın.
# Bu script, API'ye bağımlı olmadan tabloları oluşturmalıdır.
# Sizin api/semalar.py dosyanızdaki Base objesini ve tanımlanmış modelleri kullanmalıyız.
from api.semalar import Base, User, SirketBilgileri, Musteri, Tedarikci, Stok, KasaBanka, Fatura, FaturaKalemi, Siparis, SiparisKalemi, CariHareket, GelirGider, Nitelik

# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()

# PostgreSQL bağlantı bilgileri ortam değişkenlerinden alınır
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# Veritabanı bağlantı bilgilerinin eksik olup olmadığını kontrol et
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    logger.error("Veritabanı bağlantı bilgileri .env dosyasından eksik veya hatalı. Lütfen .env dosyasını kontrol edin.")
    raise ValueError("Veritabanı bağlantı bilgileri eksik. Tablolar oluşturulamıyor.")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def create_tables():
    """Veritabanı tablolarını oluşturan fonksiyon."""
    try:
        engine = create_engine(DATABASE_URL)

        # Veritabanı yoksa oluştur
        if not database_exists(engine.url):
            create_database(engine.url)
            logger.info(f"Veritabanı '{DB_NAME}' oluşturuldu.")
        else:
            logger.info(f"Veritabanı '{DB_NAME}' zaten mevcut.")

        # Tüm tabloları oluştur
        # api/semalar.py'deki Base objesi kullanılmalı.
        # Bu, tüm tanımlı SQLAlchemy modellerinin tablolarını veritabanında oluşturur.
        Base.metadata.create_all(bind=engine)
        logger.info("Tüm veritabanı tabloları başarıyla oluşturuldu/güncellendi.")

    except Exception as e:
        logger.error(f"Veritabanı tabloları oluşturulurken bir hata oluştu: {e}")
        print(f"Hata: {e}")

if __name__ == "__main__":
    logger.info("create_pg_tables.py çalıştırılıyor...")
    create_tables()
    logger.info("create_pg_tables.py tamamlandı.")