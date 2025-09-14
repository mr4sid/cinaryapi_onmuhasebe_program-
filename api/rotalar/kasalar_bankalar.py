from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db
from datetime import date
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
router = APIRouter(
    prefix="/kasalar_bankalar",
    tags=["Kasa ve Banka Hesapları"]
)

@router.get("/", response_model=modeller.KasaBankaListResponse)
def read_kasalar_bankalar(
    skip: int = 0,
    limit: int = 100,
    arama: Optional[str] = None,
    tip: Optional[semalar.KasaBankaTipiEnum] = None,
    aktif_durum: Optional[bool] = None,
    kullanici_id: int = Query(..., description="Kullanıcı ID"),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.kullanici_id == kullanici_id)

    if arama:
        query = query.filter(
            (semalar.KasaBanka.hesap_adi.ilike(f"%{arama}%")) |
            (semalar.KasaBanka.kod.ilike(f"%{arama}%")) |
            (semalar.KasaBanka.banka_adi.ilike(f"%{arama}%")) |
            (semalar.KasaBanka.hesap_no.ilike(f"%{arama}%"))
        )

    if tip:
        query = query.filter(semalar.KasaBanka.tip == tip)

    if aktif_durum is not None:
        query = query.filter(semalar.KasaBanka.aktif == aktif_durum)

    total_count = query.count()
    hesaplar = query.offset(skip).limit(limit).all()
    
    return {"items": [modeller.KasaBankaRead.model_validate(hesap, from_attributes=True) for hesap in hesaplar], "total": total_count}

@router.get("/{hesap_id}", response_model=modeller.KasaBankaRead)
def read_kasa_banka(hesap_id: int, kullanici_id: int = Query(..., description="Kullanıcı ID"), db: Session = Depends(get_db)):
    hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == hesap_id, semalar.KasaBanka.kullanici_id == kullanici_id).first()
    if not hesap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı")
    return modeller.KasaBankaRead.model_validate(hesap, from_attributes=True)

@router.post("/", response_model=modeller.KasaBankaBase)
def create_kasa_banka(hesap: modeller.KasaBankaCreate, kullanici_id: int = Query(..., description="Kullanıcı ID"), db: Session = Depends(get_db)):
    try:
        db_hesap = semalar.KasaBanka(
            hesap_adi=hesap.hesap_adi,
            kod=hesap.kod,
            tip=hesap.tip,
            bakiye=hesap.bakiye if hesap.bakiye is not None else 0.0,
            para_birimi=hesap.para_birimi if hesap.para_birimi is not None else "TL",
            banka_adi=hesap.banka_adi,
            sube_adi=hesap.sube_adi,
            hesap_no=hesap.hesap_no,
            varsayilan_odeme_turu=hesap.varsayilan_odeme_turu,
            kullanici_id=kullanici_id
        )
        db.add(db_hesap)
        db.commit()
        db.refresh(db_hesap)
        return db_hesap
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"'{hesap.kod}' kodu zaten kullanılıyor. Lütfen farklı bir kod deneyin.")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Veritabanı işlemi sırasında hata oluştu: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Kasa/Banka hesabı oluşturulurken beklenmedik bir hata oluştu: {str(e)}")
            
@router.put("/{hesap_id}", response_model=modeller.KasaBankaRead)
def update_kasa_banka(hesap_id: int, hesap: modeller.KasaBankaUpdate, kullanici_id: int = Query(..., description="Kullanıcı ID"), db: Session = Depends(get_db)):
    db_hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == hesap_id, semalar.KasaBanka.kullanici_id == kullanici_id).first()
    if db_hesap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı")
    
    hesap_data = hesap.model_dump(exclude_unset=True)
    for key, value in hesap_data.items():
        setattr(db_hesap, key, value)
    
    db.commit()
    db.refresh(db_hesap)
    return db_hesap

@router.delete("/{hesap_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kasa_banka(hesap_id: int, kullanici_id: int = Query(..., description="Kullanıcı ID"), db: Session = Depends(get_db)):
    db_hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == hesap_id, semalar.KasaBanka.kullanici_id == kullanici_id).first()
    if not db_hesap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı")
    db.delete(db_hesap)
    db.commit()
    return