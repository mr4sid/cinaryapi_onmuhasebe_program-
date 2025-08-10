# create_or_update_pg_tables.py Dosyasının tam içeriği.
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
import logging

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FastAPI modelleri yerine doğrudan SQLAlchemy modellerini içe aktarın.
from api.semalar import (
    Base, Musteri, Tedarikci, KasaBanka, UrunBirimi, Ulke,
    GelirSiniflandirma, GiderSiniflandirma
)

# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()

# PostgreSQL bağlantı bilgileri ortam değişkenlerinden alınır
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    logger.error("Veritabanı bağlantı bilgileri .env dosyasından eksik.")
    raise ValueError("Veritabanı bağlantı bilgileri eksik. İşlem durduruldu.")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def create_or_update_tables():
    """Veritabanında eksik olan tabloları oluşturan ve varsayılan verileri ekleyen fonksiyon."""
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # Tüm tabloları oluştur, sadece eksik olanları ekler.
        logger.info("Eksik veritabanı tabloları kontrol ediliyor ve oluşturuluyor...")
        Base.metadata.create_all(bind=engine)
        logger.info("Tablo kontrolü tamamlandı.")

        # Varsayılan verileri eklemeden önce tabloların boş olup olmadığını kontrol et
        if not inspector.get_table_names() or db.query(Musteri).count() == 0:
            logger.info("Varsayılan veriler ekleniyor...")

            # Nitelikler
            urun_birimleri = ["Adet", "Metre", "Kilogram", "Litre", "Kutu"]
            ulkeler = ["Türkiye", "ABD", "Almanya", "Çin", "Fransa"]
            gelir_siniflandirmalari = ["Satış Geliri", "Faiz Geliri", "Diğer Gelirler"]
            gider_siniflandirmalari = ["Kira Gideri", "Personel Gideri", "Fatura Gideri", "Pazarlama Gideri"]
            
            for ad in urun_birimleri:
                if not db.query(UrunBirimi).filter_by(ad=ad).first():
                    db.add(UrunBirimi(ad=ad))
            
            for ad in ulkeler:
                if not db.query(Ulke).filter_by(ad=ad).first():
                    db.add(Ulke(ad=ad))

            for ad in gelir_siniflandirmalari:
                if not db.query(GelirSiniflandirma).filter_by(ad=ad).first():
                    db.add(GelirSiniflandirma(ad=ad))

            for ad in gider_siniflandirmalari:
                if not db.query(GiderSiniflandirma).filter_by(ad=ad).first():
                    db.add(GiderSiniflandirma(ad=ad))

            # Varsayılan Perakende Müşterisi ve Genel Tedarikçi'yi ekle
            if not db.query(Musteri).filter_by(kod="PERAKENDE_MUSTERI").first():
                perakende_musteri = Musteri(ad="Perakende Müşterisi", kod="PERAKENDE_MUSTERI", aktif=True)
                db.add(perakende_musteri)
            
            if not db.query(Tedarikci).filter_by(kod="GENEL_TEDARIKCI").first():
                genel_tedarikci = Tedarikci(ad="Genel Tedarikçi", kod="GENEL_TEDARIKCI", aktif=True)
                db.add(genel_tedarikci)

            # Varsayılan Nakit Kasa'yı ekle
            if not db.query(KasaBanka).filter_by(kod="NAKİT_KASA").first():
                nakit_kasa = KasaBanka(
                    hesap_adi="Nakit Kasa",
                    kod="NAKİT_KASA",
                    tip="KASA",
                    bakiye=0.0,
                    para_birimi="TL",
                    aktif=True,
                    varsayilan_odeme_turu="NAKİT"
                )
                db.add(nakit_kasa)

            db.commit()
            logger.info("Varsayılan veriler başarıyla eklendi.")

    except Exception as e:
        logger.error(f"Veritabanı işlemleri sırasında hata oluştu: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("create_or_update_pg_tables.py çalıştırılıyor...")
    create_or_update_tables()
    logger.info("create_or_update_pg_tables.py tamamlandı.")