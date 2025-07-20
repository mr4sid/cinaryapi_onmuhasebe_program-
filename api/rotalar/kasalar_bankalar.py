from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db
from datetime import date # Tarih tipi için import

router = APIRouter(
    prefix="/kasalar_bankalar",
    tags=["Kasa ve Banka Hesapları"]
)

# --- VERİ OKUMA (READ) ---

@router.get("/", response_model=List[modeller.KasaBankaBase])
def read_kasalar_bankalar(
    skip: int = 0, 
    limit: int = 100, 
    arama_terimi: Optional[str] = None,
    tip_filtre: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Tüm kasa/banka hesaplarını listeler. Arama terimi ve tip filtresi ile filtrelenebilir.
    """
    query = db.query(semalar.KasaBanka)

    if arama_terimi:
        query = query.filter(
            (semalar.KasaBanka.hesap_adi.ilike(f"%{arama_terimi}%")) |
            (semalar.KasaBanka.hesap_no.ilike(f"%{arama_terimi}%")) | # Hesap no'ya göre arama
            (semalar.KasaBanka.banka_adi.ilike(f"%{arama_terimi}%")) # Banka adına göre arama
        )
    
    if tip_filtre:
        query = query.filter(semalar.KasaBanka.tip == tip_filtre)

    kasalar_bankalar = query.order_by(semalar.KasaBanka.hesap_adi).offset(skip).limit(limit).all()
    return kasalar_bankalar

@router.get("/{hesap_id}", response_model=modeller.KasaBankaBase)
def read_kasa_banka(hesap_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip tek bir kasa/banka hesabını döndürür.
    """
    db_hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == hesap_id).first()
    if db_hesap is None:
        raise HTTPException(status_code=404, detail="Kasa/Banka hesabı bulunamadı")
    return db_hesap

# --- VERİ OLUŞTURMA (CREATE) ---
class KasaBankaCreate(modeller.KasaBankaBase):
    # Base modeldeki id ve bakiye varsayılanları olmadığı için create modelinde de optional yapıldı.
    # Ancak normalde bakiye float olarak kesin gelmeli.
    # Hesap adına, tipine ve bakiyeye ek olarak diğer alanlar
    hesap_no: Optional[str] = None
    banka_adi: Optional[str] = None
    sube_adi: Optional[str] = None
    para_birimi: Optional[str] = "TL"
    acilis_tarihi: Optional[date] = None
    varsayilan_odeme_turu: Optional[str] = None

@router.post("/", response_model=modeller.KasaBankaBase)
def create_kasa_banka(hesap: modeller.KasaBankaCreate, db: Session = Depends(get_db)):
    """
    Yeni bir kasa/banka hesabı oluşturur.
    """
    db_hesap = semalar.KasaBanka(
        hesap_adi=hesap.hesap_adi,
        bakiye=hesap.bakiye,
        tip=hesap.tip,
        hesap_no=hesap.hesap_no,
        banka_adi=hesap.banka_adi,
        sube_adi=hesap.sube_adi,
        para_birimi=hesap.para_birimi,
        acilis_tarihi=hesap.acilis_tarihi,
        varsayilan_odeme_turu=hesap.varsayilan_odeme_turu
    )
    db.add(db_hesap)
    db.commit()
    db.refresh(db_hesap)
    return db_hesap

# --- VERİ GÜNCELLEME (UPDATE) ---
@router.put("/{hesap_id}", response_model=modeller.KasaBankaBase)
def update_kasa_banka(hesap_id: int, hesap: modeller.KasaBankaCreate, db: Session = Depends(get_db)):
    """
    Mevcut bir kasa/banka hesabının bilgilerini günceller.
    """
    db_hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == hesap_id).first()
    if db_hesap is None:
        raise HTTPException(status_code=404, detail="Kasa/Banka hesabı bulunamadı")
    
    hesap_data = hesap.dict(exclude_unset=True)
    for key, value in hesap_data.items():
        setattr(db_hesap, key, value)
    
    db.commit()
    db.refresh(db_hesap)
    return db_hesap

# --- VERİ SİLME (DELETE) ---
@router.delete("/{hesap_id}", status_code=204)
def delete_kasa_banka(hesap_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip kasa/banka hesabını siler.
    """
    db_hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == hesap_id).first()
    if db_hesap is None:
        raise HTTPException(status_code=404, detail="Kasa/Banka hesabı bulunamadı")
    
    db.delete(db_hesap)
    db.commit()
    return