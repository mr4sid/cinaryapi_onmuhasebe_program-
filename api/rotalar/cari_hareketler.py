from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db
from datetime import date, datetime # date ve datetime objeleri için

router = APIRouter(
    prefix="/cari_hareketler",
    tags=["Cari Hareketler"]
)

# --- VERİ OKUMA (READ) ---

@router.get("/", response_model=modeller.CariHareketListResponse)
def read_cari_hareketler(
    skip: int = 0,
    limit: int = 100,
    cari_id: Optional[int] = None,
    cari_tip: Optional[str] = None,
    baslangic_tarihi: Optional[str] = None,
    bitis_tarihi: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # DEĞİŞİKLİK BURADA: semalar.CariHareketler yerine semalar.CariHareket kullanıldı
    query = db.query(semalar.CariHareket, semalar.KasaBanka.hesap_adi.label("kasa_banka_adi"))\
              .outerjoin(semalar.KasaBanka, semalar.CariHareket.kasa_banka_id == semalar.KasaBanka.id)

    if cari_id is not None:
        query = query.filter(semalar.CariHareket.cari_id == cari_id)
    if cari_tip:
        query = query.filter(semalar.CariHareket.cari_turu == cari_tip)
    if baslangic_tarihi:
        query = query.filter(semalar.CariHareket.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.CariHareket.tarih <= bitis_tarihi)

    total_count = query.count()
    hareketler = query.order_by(semalar.CariHareket.tarih.desc(), semalar.CariHareket.olusturma_tarihi_saat.desc()).offset(skip).limit(limit).all()

    # Pydantic modeline dönüştürme ve ilişkili verileri ekleme
    cari_hareket_read_models = []
    for hareket in hareketler:
        # Tuple'dan objeye dönüştürme (SQLAlchemy join sonucu)
        cari_hareket_obj = hareket[0] # İlk eleman CariHareket objesidir
        kasa_banka_adi = hareket[1] # İkinci eleman kasa_banka_adi'dir

        cari_hareket_read_data = modeller.CariHareketRead.model_validate(cari_hareket_obj, from_attributes=True).model_dump()
        cari_hareket_read_data['kasa_banka_adi'] = kasa_banka_adi
        
        cari_hareket_read_models.append(cari_hareket_read_data)

    return {"items": cari_hareket_read_models, "total": total_count}

@router.get("/count", response_model=int)
def get_cari_hareketler_count(
    cari_id: Optional[int] = None,
    cari_tip: Optional[str] = None,
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Filtrelere göre toplam cari hareket sayısını döndürür.
    """
    query = db.query(semalar.CariHareketler)

    if cari_id:
        query = query.filter(semalar.CariHareketler.cari_id == cari_id)
    if cari_tip:
        query = query.filter(semalar.CariHareketler.cari_tip == cari_tip)
    if baslangic_tarihi:
        query = query.filter(semalar.CariHareketler.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.CariHareketler.tarih <= bitis_tarihi)
            
    return query.count()

# --- VERİ SİLME (DELETE) ---
@router.delete("/{hareket_id}", status_code=204)
def delete_cari_hareket(hareket_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip manuel cari hareketi siler.
    İlişkili kasa/banka hesabının bakiyesini de işlemi geri alacak şekilde günceller.
    """
    db_hareket = db.query(semalar.CariHareketler).filter(semalar.CariHareketler.id == hareket_id).first()
    if db_hareket is None:
        raise HTTPException(status_code=404, detail="Cari hareket bulunamadı")
    
    # Sadece manuel (TAHSILAT/ODEME) kaynaklı hareketler buradan silinebilir. Fatura kaynaklılar fatura silinince silinir.
    if db_hareket.referans_tip not in ["MANUEL", "TAHSILAT", "ODEME"]:
        raise HTTPException(status_code=400, detail="Bu türde bir cari hareket API üzerinden doğrudan silinemez.")
    
    db.begin_nested()
    try:
        # Kasa/Banka bakiyesini geri al
        if db_hareket.kasa_banka_id:
            kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == db_hareket.kasa_banka_id).first()
            if kasa_hesabi:
                if db_hareket.islem_tipi == 'TAHSILAT': # Tahsilat siliniyorsa, kasadan para çıkmış gibi düşünülür.
                    kasa_hesabi.bakiye -= db_hareket.tutar
                elif db_hareket.islem_tipi == 'ODEME': # Ödeme siliniyorsa, kasaya para girmiş gibi düşünülür.
                    kasa_hesabi.bakiye += db_hareket.tutar
        
        db.delete(db_hareket)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Cari hareket silinirken hata: {str(e)}")
        
    return