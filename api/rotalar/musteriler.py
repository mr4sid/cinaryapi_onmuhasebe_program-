from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db

router = APIRouter(
    prefix="/musteriler",
    tags=["Müşteriler"]
)

# --- VERİ OKUMA (READ) ---

@router.get("/", response_model=List[modeller.MusteriBase])
def read_musteriler(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Tüm müşterileri listeler. Sayfalama için 'skip' ve 'limit' parametreleri kullanılabilir.
    """
    musteriler = db.query(semalar.Musteri).order_by(semalar.Musteri.ad).offset(skip).limit(limit).all()
    return musteriler

@router.get("/{musteri_id}", response_model=modeller.MusteriBase)
def read_musteri(musteri_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip tek bir müşteriyi döndürür.
    """
    db_musteri = db.query(semalar.Musteri).filter(semalar.Musteri.id == musteri_id).first()
    if db_musteri is None:
        raise HTTPException(status_code=404, detail="Müşteri bulunamadı")
    return db_musteri

# --- YENİ VERİ OLUŞTURMA (CREATE) ---
@router.post("/", response_model=modeller.MusteriBase)
def create_musteri(musteri: modeller.MusteriCreate, db: Session = Depends(get_db)):
    """
    Yeni bir müşteri oluşturur. Kodun benzersizliğini kontrol eder.
    """
    db_musteri_check = db.query(semalar.Musteri).filter(semalar.Musteri.kod == musteri.kod).first()
    if db_musteri_check:
        raise HTTPException(status_code=400, detail=f"'{musteri.kod}' müşteri kodu zaten kullanılıyor.")

    db_musteri = semalar.Musteri(**musteri.dict())

    db.add(db_musteri)
    db.commit()
    db.refresh(db_musteri)
    return db_musteri
# --- VERİ GÜNCELLEME (UPDATE) ---
@router.put("/{musteri_id}", response_model=modeller.MusteriBase)
def update_musteri(musteri_id: int, musteri: modeller.MusteriCreate, db: Session = Depends(get_db)):
    """
    Mevcut bir müşterinin bilgilerini günceller.
    """
    db_musteri = db.query(semalar.Musteri).filter(semalar.Musteri.id == musteri_id).first()
    if db_musteri is None:
        raise HTTPException(status_code=404, detail="Güncellenecek müşteri bulunamadı")
    
    # exclude_unset=True ile sadece gönderilen alanlar güncellenir
    for key, value in musteri.dict(exclude_unset=True).items():
        setattr(db_musteri, key, value)
    
    db.commit()
    db.refresh(db_musteri)
    return db_musteri

# --- VERİ SİLME (DELETE) ---

@router.delete("/{musteri_id}", status_code=204)
def delete_musteri(musteri_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip müşteriyi siler.
    """
    db_musteri = db.query(semalar.Musteri).filter(semalar.Musteri.id == musteri_id).first()
    if db_musteri is None:
        raise HTTPException(status_code=404, detail="Silinecek müşteri bulunamadı")
    
    db.delete(db_musteri)
    db.commit()
    return