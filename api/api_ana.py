# api/api_ana.py dosyasının TAMAMI
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text # EKLENDİ: text objesi için import
import logging
from datetime import datetime
from contextlib import asynccontextmanager # EKLENDİ: asynccontextmanager için import
# Gerekli içe aktarmalar
# Base ve engine, veritabani.py'den import edilmeli
from .veritabani import Base

# Başlangıç verileri için kullanılacak modeller
from .semalar import Musteri, KasaBanka, Tedarikci # EKLENDİ: Tedarikci modeli için import

# Mevcut rotaların içe aktarılması
from .rotalar import (
    dogrulama, musteriler, tedarikciler, stoklar,
    kasalar_bankalar, cari_hareketler,
    gelir_gider, nitelikler, sistem, raporlar, yedekleme, kullanicilar,
    siparis_faturalar, yonetici
)

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Varsayılan verileri ekleyen fonksiyon
def create_initial_data(db: Session):
    try:
        logger.info("Varsayılan veriler kontrol ediliyor ve ekleniyor...")

        # Varsayılan perakende müşteriyi kontrol et ve ekle
        perakende_musteri = db.query(Musteri).filter(Musteri.kod == "PERAKENDE_MUSTERI").first()
        if not perakende_musteri:
            yeni_musteri = Musteri(
                ad="Perakende Müşteri",
                kod="PERAKENDE_MUSTERI",
                aktif=True,
                olusturma_tarihi=datetime.now()
            )
            db.add(yeni_musteri)
            db.commit()
            db.refresh(yeni_musteri)
            logger.info("Varsayılan 'Perakende Müşteri' başarıyla eklendi.")
        else:
            logger.info("Varsayılan 'Perakende Müşteri' zaten mevcut.")

        # Varsayılan Genel Tedarikçi (YENİ EKLENEN KISIM)
        genel_tedarikci = db.query(Tedarikci).filter(Tedarikci.kod == "GENEL_TEDARIKCI").first()
        if not genel_tedarikci:
            yeni_tedarikci = Tedarikci(
                ad="Genel Tedarikçi",
                kod="GENEL_TEDARIKCI",
                aktif=True,
                olusturma_tarihi=datetime.now()
            )
            db.add(yeni_tedarikci)
            db.commit()
            db.refresh(yeni_tedarikci)
            logger.info("Varsayılan 'Genel Tedarikçi' başarıyla eklendi.")
        else:
            logger.info("Varsayılan 'Genel Tedarikçi' zaten mevcut.")

        # Varsayılan NAKİT hesabını kontrol et ve ekle
        nakit_kasa = db.query(KasaBanka).filter(KasaBanka.kod == "NAKİT_KASA").first()
        if not nakit_kasa:
            yeni_kasa = KasaBanka(
                hesap_adi="Nakit Kasa",
                kod="NAKİT_KASA",
                tip="KASA",
                bakiye=0.0,
                para_birimi="TL",
                aktif=True,
                varsayilan_odeme_turu="NAKİT",
                olusturma_tarihi=datetime.now()
            )
            db.add(yeni_kasa)
            db.commit()
            db.refresh(yeni_kasa)
            logger.info("Varsayılan 'NAKİT KASA' hesabı başarıyla eklendi.")
        else:
            logger.info("Varsayılan 'NAKİT KASA' hesabı zaten mevcut.")

    except Exception as e:
        logger.error(f"Varsayılan veriler eklenirken bir hata oluştu: {e}")
        db.rollback()

app = FastAPI(
    title="Ön Muhasebe Sistemi API",
    description="Ön muhasebe sistemi için RESTful API",
    version="1.0.0",
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uygulama başladıktan sonra çalışacak olay
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Uygulama başladığında ve kapandığında çalışacak olay yönetimi.
    """
    logger.info("API başlatılıyor...")
    
    # Yeni yaklaşıma göre, veritabanı tablolarının oluşturulması veya başlangıç verilerinin eklenmesi
    # FastAPI'nin değil, ayrı bir script'in görevi olmalıdır (ör. create_or_update_pg_tables.py).
    # Bu, uygulamanın her başladığında bu işlemleri tekrarlamasını engeller ve daha sağlam bir yapı sunar.
    # Bu nedenle, buradaki veritabanı oluşturma ve veri ekleme kodları kaldırıldı.
    
    yield
    
    logger.info("API kapanıyor...")

app = FastAPI(
    lifespan=lifespan,
    title="Ön Muhasebe Sistemi API",
    description="Ön muhasebe sistemi için RESTful API",
    version="1.0.0",
)

# CORS ayarları
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları (rotaları) uygulamaya dahil etme
app.include_router(dogrulama.router, tags=["Kimlik Doğrulama"])
app.include_router(kullanicilar.router, tags=["Kullanıcılar"])
app.include_router(musteriler.router, tags=["Müşteriler"])
app.include_router(tedarikciler.router, tags=["Tedarikçiler"])
app.include_router(stoklar.router, tags=["Stoklar"])
app.include_router(kasalar_bankalar.router, tags=["Kasalar ve Bankalar"])
app.include_router(cari_hareketler.router, tags=["Cari Hareketler"])
app.include_router(gelir_gider.router, tags=["Gelir ve Giderler"])
app.include_router(nitelikler.router, tags=["Nitelikler"])
app.include_router(sistem.router, tags=["Sistem"])
app.include_router(raporlar.router, tags=["Raporlar"])
app.include_router(yedekleme.router, tags=["Veritabanı Yedekleme"])
app.include_router(siparis_faturalar.siparisler_router, tags=["Siparişler"])
app.include_router(siparis_faturalar.faturalar_router, tags=["Faturalar"])
app.include_router(yonetici.router, tags=["Yönetici İşlemleri"])

@app.get("/")
def read_root():
    return {"message": "On Muhasebe API'sine hoş geldiniz!"}