from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from .. import semalar, modeller
from ..veritabani import get_db

router = APIRouter(
    prefix="/stoklar",
    tags=["Stoklar"]
)

# --- VERİ OLUŞTURMA (CREATE) ---
@router.post("/", response_model=modeller.StokBase)
def create_stok(stok: modeller.StokCreate, db: Session = Depends(get_db)):
    db_stok_check = db.query(semalar.Stok).filter(semalar.Stok.urun_kodu == stok.urun_kodu).first()
    if db_stok_check:
        raise HTTPException(status_code=400, detail=f"'{stok.urun_kodu}' ürün kodu zaten kullanılıyor.")
    
    db_stok = semalar.Stok(**stok.dict())
    db.add(db_stok)
    db.commit()
    db.refresh(db_stok)
    return db_stok

# --- VERİ OKUMA (READ) ---
@router.get("/", response_model=List[modeller.StokBase])
def read_stoklar(
    skip: int = 0, 
    limit: int = 100, 
    arama_terimi: Optional[str] = None,
    kategori_id: Optional[int] = None,
    marka_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Stok)
    if arama_terimi:
        query = query.filter(
            (semalar.Stok.urun_adi.ilike(f"%{arama_terimi}%")) | 
            (semalar.Stok.urun_kodu.ilike(f"%{arama_terimi}%")) # Ürün koduna göre arama eklendi
        )
    if kategori_id:
        query = query.filter(semalar.Stok.kategori_id == kategori_id)
    if marka_id:
        query = query.filter(semalar.Stok.marka_id == marka_id)
    
    stoklar = query.order_by(semalar.Stok.urun_adi).offset(skip).limit(limit).all()
    
    return stoklar

@router.get("/{stok_id}", response_model=modeller.StokBase)
def read_stok(stok_id: int, db: Session = Depends(get_db)):
    db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == stok_id).first()
    if db_stok is None:
        raise HTTPException(status_code=404, detail="Stok kalemi bulunamadı")
    return db_stok

# --- VERİ GÜNCELLEME (UPDATE) ---
@router.put("/{stok_id}", response_model=modeller.StokBase)
def update_stok(stok_id: int, stok: modeller.StokCreate, db: Session = Depends(get_db)):
    db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == stok_id).first()
    if db_stok is None:
        raise HTTPException(status_code=404, detail="Güncellenecek stok kalemi bulunamadı")
    
    stok_data = stok.dict(exclude_unset=True)
    for key, value in stok_data.items():
        setattr(db_stok, key, value)
    
    db.commit()
    db.refresh(db_stok)
    return db_stok

# --- VERİ SİLME (DELETE) ---
@router.delete("/{stok_id}", status_code=204)
def delete_stok(stok_id: int, db: Session = Depends(get_db)):
    db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == stok_id).first()
    if db_stok is None:
        raise HTTPException(status_code=404, detail="Silinecek stok kalemi bulunamadı")
    
    db.delete(db_stok)
    db.commit()
    return

class StokHareketCreate(BaseModel):
    islem_tipi: str
    miktar: float
    tarih: date
    aciklama: Optional[str] = None

@router.post("/{stok_id}/hareket", response_model=modeller.StokBase)
def create_stok_hareketi(stok_id: int, hareket: StokHareketCreate, db: Session = Depends(get_db)):
    db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == stok_id).first()
    if not db_stok:
        raise HTTPException(status_code=404, detail="Stok kalemi bulunamadı")

    stok_degisim_net = 0.0
    if hareket.islem_tipi in ["Giriş (Manuel)", "Sayım Fazlası", "İade Girişi"]:
        stok_degisim_net = hareket.miktar
    elif hareket.islem_tipi in ["Çıkış (Manuel)", "Sayım Eksiği", "Zayiat"]:
        stok_degisim_net = -hareket.miktar
    
    if stok_degisim_net == 0.0:
        raise HTTPException(status_code=400, detail="Geçersiz işlem tipi veya sıfır miktar.")

    db_hareket = semalar.StokHareketleri(
        urun_id=stok_id, tarih=hareket.tarih, islem_tipi=hareket.islem_tipi,
        miktar=stok_degisim_net, onceki_stok=db_stok.stok_miktari,
        sonraki_stok=db_stok.stok_miktari + stok_degisim_net,
        aciklama=hareket.aciklama, kaynak_tip="MANUEL"
    )
    db.add(db_hareket)
    db_stok.stok_miktari += stok_degisim_net
    
    db.commit()
    db.refresh(db_stok)
    return db_stok