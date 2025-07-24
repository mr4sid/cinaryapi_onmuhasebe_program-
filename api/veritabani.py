import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import logging

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# .env dosyasındaki ortam değişkenlerini yükle
# Bu çağrı, projenizin ana dizinindeki .env dosyasını bulacaktır.
load_dotenv()

# PostgreSQL bağlantı bilgileri ortam değişkenlerinden alınır
# Eğer .env dosyasında bu değişkenler bulunamazsa None döner.
# Bu durumda varsayılan değerler veya hata yönetimi ekleyebilirsiniz.
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# Veritabanı URL'si oluşturma
# Ortam değişkenlerinin gelip gelmediğini kontrol edin
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    logger.error("Veritabanı bağlantı bilgileri .env dosyasından eksik veya hatalı. Lütfen .env dosyasını kontrol edin.")
    # Uygulamanın başlamasını engellemek için hata fırlatılabilir
    raise ValueError("Veritabanı bağlantı bilgileri eksik.")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy motoru oluşturma
try:
    engine = create_engine(DATABASE_URL)
    # Bağlantıyı test etmek için basit bir sorgu
    with engine.connect() as connection:
        connection.execute(f"SELECT 1")
    logger.info(f"PostgreSQL veritabanı bağlantısı başarılı: {DB_NAME}@{DB_HOST}:{DB_PORT}")
except Exception as e:
    logger.critical(f"Veritabanı bağlantısı kurulamadı! Lütfen PostgreSQL sunucusunun çalıştığından ve .env bilgilerinin doğru olduğundan emin olun. Hata: {e}")
    raise

# Veritabanı oturumunu yapılandırma
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Deklaratif taban sınıfı
# SQLAlchemy modelleri (api/semalar.py'de tanımlananlar gibi) bu Base sınıfını kullanır.
Base = declarative_base()

# Veritabanı oturumu almak için bağımlılık fonksiyonu
# Bu fonksiyon FastAPI rotaları tarafından kullanılacaktır.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
