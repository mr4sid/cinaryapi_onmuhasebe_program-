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

@router.get("/", response_model=List[modeller.CariHareketBase])
def read_cari_hareketler(
    skip: int = 0,
    limit: int = 100,
    cari_id: Optional[int] = None,
    cari_tip: Optional[str] = None,
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Tüm cari hareketleri, ilişkili kasa/banka adıyla birlikte tek sorguda verimli bir şekilde listeler.
    """
    query = db.query(semalar.CariHareketler, semalar.KasaBanka.hesap_adi.label("kasa_banka_adi"))\
        .outerjoin(semalar.KasaBanka, semalar.KasaBanka.id == semalar.CariHareketler.kasa_banka_id)

    if cari_id:
        query = query.filter(semalar.CariHareketler.cari_id == cari_id)
    if cari_tip:
        query = query.filter(semalar.CariHareketler.cari_tip == cari_tip)
    if baslangic_tarihi:
        query = query.filter(semalar.CariHareketler.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.CariHareketler.tarih <= bitis_tarihi)
    
    hareket_results = query.order_by(semalar.CariHareketler.tarih.desc(), semalar.CariHareketler.id.desc()).offset(skip).limit(limit).all()

    results = []
    for hareket, kasa_banka_adi in hareket_results:
        hareket_model = modeller.CariHareketBase.from_orm(hareket)
        hareket_model.kasa_banka_adi = kasa_banka_adi
        results.append(hareket_model)
        
    return results

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