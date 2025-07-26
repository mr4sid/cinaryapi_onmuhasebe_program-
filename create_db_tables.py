# create_db_tables.py
import sys
import os
import logging

# Proje kök dizinini Python yoluna ekle
# Bu, 'api' klasöründeki modülleri bulmasını sağlar.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'api')))

from veritabani import Base, engine # 'api' klasörü içindeki veritabani.py'den import et

# Loglama ayarları (sadece bu script için)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Veritabanı tablolarını oluşturma betiği başlatıldı.")
    try:
        # Tüm tabloları oluştur
        Base.metadata.create_all(bind=engine)
        logger.info("Tüm veritabanı tabloları başarıyla oluşturuldu/güncellendi.")
    except Exception as e:
        logger.error(f"Veritabanı tabloları oluşturulurken hata oluştu: {e}")
        sys.exit(1) # Hata durumunda betiği sonlandır