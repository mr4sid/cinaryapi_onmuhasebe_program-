# create_pg_tables.py Dosyasının içeriği.
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database, drop_database # Buraya 'drop_database' eklendi
import logging

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FastAPI modelleri yerine doğrudan SQLAlchemy modellerini içe aktarın.
# Bu script, API'ye bağımlı olmadan tabloları oluşturmalıdır.
# Sizin api/semalar.py dosyanızdaki Base objesini ve tanımlanmış modelleri kullanmalıyız.
from api.semalar import Base, Kullanici, Sirket, Musteri, Tedarikci, Stok, KasaBanka, Fatura, FaturaKalemi, Siparis, SiparisKalemi, CariHareket, GelirGider

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
    # PostgreSQL'in varsayılan "postgres" veritabanına bağlanarak
    # drop/create işlemlerini yapacak URL'i oluşturun.
    # Bu veritabanı genellikle her PostgreSQL kurulumunda bulunur.
    temp_database_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"

    # Geçici bir engine oluşturun
    temp_engine = create_engine(temp_database_url)

    try:
        # Eğer hedef veritabanı varsa, ÖNCE TAMAMEN SİL! (Geliştirme ortamı için)
        # Bu işlem için temp_engine kullanılır.
        if database_exists(DATABASE_URL): # DATABASE_URL'in varlığını kontrol edin
            drop_database(DATABASE_URL, force=True) # force=True ekleyerek bağlantıları kapatmayı zorlayın
            logger.info(f"Mevcut veritabanı '{DB_NAME}' silindi.")

        # Hedef veritabanı yoksa oluşturun.
        # Bu işlem için de temp_engine kullanılır.
        create_database(DATABASE_URL) # DATABASE_URL'i oluşturun
        logger.info(f"Veritabanı '{DB_NAME}' oluşturuldu.")

        # Şimdi, asıl uygulamanın bağlanacağı veritabanına bir engine oluşturun.
        # Bu engine artık mevcut olan 'on_muhasebe_prod' veritabanına başarıyla bağlanabilir.
        engine = create_engine(DATABASE_URL)

        # Tüm tabloları oluştur
        Base.metadata.create_all(bind=engine)
        logger.info("Tüm veritabanı tabloları başarıyla oluşturuldu/güncellendi.")

    except Exception as e:
        logger.critical(f"Veritabanı tabloları oluşturulurken hata: {e}")
        raise
if __name__ == "__main__":
    logger.info("create_pg_tables.py çalıştırılıyor...")
    create_tables()
    logger.info("create_pg_tables.py tamamlandı.")