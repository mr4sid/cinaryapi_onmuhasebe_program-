# api.zip/rotalar/cari_hareketler.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db
from datetime import date, datetime # date ve datetime objeleri için
from .. import guvenlik # Yeni eklenen import

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
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user), # Güvenli kullanıcı kimliği
    db: Session = Depends(get_db)
):
    query = db.query(semalar.CariHareket, semalar.KasaBanka.hesap_adi.label("kasa_banka_adi"))\
              .outerjoin(semalar.KasaBanka, semalar.CariHareket.kasa_banka_id == semalar.KasaBanka.id)\
              .filter(semalar.CariHareket.kullanici_id == current_user.id) # Sorgu güncellendi

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

    cari_hareket_read_models = []
    for hareket in hareketler:
        cari_hareket_obj = hareket[0]
        kasa_banka_adi = hareket[1]

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
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user), # Güvenli kullanıcı kimliği
    db: Session = Depends(get_db)
):
    query = db.query(semalar.CariHareket).filter(semalar.CariHareket.kullanici_id == current_user.id) # Sorgu güncellendi

    if cari_id:
        query = query.filter(semalar.CariHareket.cari_id == cari_id)
    if cari_tip:
        query = query.filter(semalar.CariHareket.cari_turu == cari_tip)
    if baslangic_tarihi:
        query = query.filter(semalar.CariHareket.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.CariHareket.tarih <= bitis_tarihi)
            
    return query.count()

# --- VERİ OLUŞTURMA (CREATE) ---
@router.post("/manuel", response_model=modeller.CariHareketRead)
def create_manuel_cari_hareket(
    hareket: modeller.CariHareketCreate,
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user), # Güvenli kullanıcı kimliği
    db: Session = Depends(get_db)
):
    db_hareket = semalar.CariHareket(**hareket.model_dump(), kullanici_id=current_user.id) # Kullanıcı ID'si eklendi
    db.add(db_hareket)
    db.commit()
    db.refresh(db_hareket)

    return db_hareket

# --- VERİ SİLME (DELETE) ---
@router.delete("/{hareket_id}", status_code=204)
def delete_cari_hareket(
    hareket_id: int, 
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user), # Güvenli kullanıcı kimliği
    db: Session = Depends(get_db)
):
    db_hareket = db.query(semalar.CariHareket).filter(semalar.CariHareket.id == hareket_id, semalar.CariHareket.kullanici_id == current_user.id).first() # Sorgu güncellendi
    if db_hareket is None:
        raise HTTPException(status_code=404, detail="Cari hareket bulunamadı")
    
    if db_hareket.kaynak not in [semalar.KaynakTipEnum.MANUEL, semalar.KaynakTipEnum.TAHSILAT, semalar.KaynakTipEnum.ODEME]:
        raise HTTPException(status_code=400, detail="Bu türde bir cari hareket API üzerinden doğrudan silinemez.")
    
    db.begin_nested()
    try:
        if db_hareket.kasa_banka_id:
            kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == db_hareket.kasa_banka_id).first()
            if kasa_hesabi:
                if db_hareket.islem_turu == 'TAHSILAT':
                    kasa_hesabi.bakiye -= db_hareket.tutar
                elif db_hareket.islem_turu == 'ODEME':
                    kasa_hesabi.bakiye += db_hareket.tutar
        
        db.delete(db_hareket)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Cari hareket silinirken hata: {str(e)}")
        
    return