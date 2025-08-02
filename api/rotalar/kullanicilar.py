# api/rotalar/kullanicilar.py dosyasının TAMAMI
import os
import requests
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import modeller, semalar
from ..veritabani import get_db

router = APIRouter(prefix="/kullanicilar", tags=["Kullanıcılar"])

@router.get("/", response_model=modeller.KullaniciListResponse)
def read_kullanicilar(skip: int = 0, limit: int = 1000, db: Session = Depends(get_db)):
    query = db.query(semalar.Kullanici)
    kullanicilar = query.offset(skip).limit(limit).all()
    total_count = query.count()
    return {"items": [modeller.KullaniciRead.model_validate(k, from_attributes=True) for k in kullanicilar], "total": total_count}

@router.get("/{kullanici_id}", response_model=modeller.KullaniciRead)
def read_kullanici(kullanici_id: int, db: Session = Depends(get_db)):
    kullanici = db.query(semalar.Kullanici).filter(semalar.Kullanici.id == kullanici_id).first()
    if not kullanici:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı")
    return modeller.KullaniciRead.model_validate(kullanici, from_attributes=True)

@router.delete("/{kullanici_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kullanici(kullanici_id: int, db: Session = Depends(get_db)):
    db_kullanici = db.query(semalar.Kullanici).filter(semalar.Kullanici.id == kullanici_id).first()
    if not db_kullanici:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı")
    db.delete(db_kullanici)
    db.commit()
    return