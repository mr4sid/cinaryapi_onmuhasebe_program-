from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db

router = APIRouter(
    prefix="/tedarikciler",
    tags=["Tedarikçiler"]
)

# --- VERİ OKUMA (READ) ---

@router.get("/", response_model=List[modeller.TedarikciBase])
def read_tedarikciler(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Tüm tedarikçileri listeler.
    """
    tedarikciler = db.query(semalar.Tedarikci).order_by(semalar.Tedarikci.ad).offset(skip).limit(limit).all()
    return tedarikciler

@router.get("/{tedarikci_id}", response_model=modeller.TedarikciBase)
def read_tedarikci(tedarikci_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip tek bir tedarikçiyi döndürür.
    """
    db_tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.id == tedarikci_id).first()
    if db_tedarikci is None:
        raise HTTPException(status_code=404, detail="Tedarikçi bulunamadı")
    return db_tedarikci

# --- YENİ EKLENDİ: VERİ OLUŞTURMA (CREATE) ---
@router.post("/", response_model=modeller.TedarikciBase)
def create_tedarikci(tedarikci: modeller.TedarikciCreate, db: Session = Depends(get_db)):
    """
    Yeni bir tedarikçi oluşturur. Kodun benzersizliğini kontrol eder.
    """
    db_tedarikci_check = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.tedarikci_kodu == tedarikci.tedarikci_kodu).first()
    if db_tedarikci_check:
        raise HTTPException(status_code=400, detail=f"'{tedarikci.tedarikci_kodu}' tedarikçi kodu zaten kullanılıyor.")

    # Pydantic modelini doğrudan SQLAlchemy modeline dönüştürüyoruz
    db_tedarikci = semalar.Tedarikci(**tedarikci.dict())

    db.add(db_tedarikci)
    db.commit()
    db.refresh(db_tedarikci)
    return db_tedarikci

# --- YENİ EKLENDİ: VERİ GÜNCELLEME (UPDATE) ---
@router.put("/{tedarikci_id}", response_model=modeller.TedarikciBase)
def update_tedarikci(tedarikci_id: int, tedarikci: modeller.TedarikciCreate, db: Session = Depends(get_db)):
    """
    Mevcut bir tedarikçinin bilgilerini günceller.
    """
    db_tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.id == tedarikci_id).first()
    if db_tedarikci is None:
        raise HTTPException(status_code=404, detail="Güncellenecek tedarikçi bulunamadı")
    
    # exclude_unset=True ile sadece gönderilen alanlar güncellenir
    for key, value in tedarikci.dict(exclude_unset=True).items():
        setattr(db_tedarikci, key, value)
    
    db.commit()
    db.refresh(db_tedarikci)
    return db_tedarikci

# --- VERİ SİLME (DELETE) ---

@router.delete("/{tedarikci_id}", status_code=204)
def delete_tedarikci(tedarikci_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip tedarikçiyi siler.
    """
    db_tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.id == tedarikci_id).first()
    if db_tedarikci is None:
        raise HTTPException(status_code=404, detail="Silinecek tedarikçi bulunamadı")
    
    db.delete(db_tedarikci)
    db.commit()
    return