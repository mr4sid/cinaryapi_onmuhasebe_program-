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
from .semalar import Musteri, KasaBanka, Tedarikci

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