# tedarikci.py dosyasının tam ve şuanki hali
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional

from .. import modeller, semalar
from ..veritabani import get_db
from ..api_servisler import CariHesaplamaService
from .. import guvenlik  # güvenlik modülünü ekledik

router = APIRouter(prefix="/tedarikciler", tags=["Tedarikçiler"])

@router.post("/", response_model=modeller.TedarikciRead)
def create_tedarikci(
    tedarikci: modeller.TedarikciCreate,
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(guvenlik.get_current_user)
):
    db_tedarikci = semalar.Tedarikci(**tedarikci.model_dump(), kullanici_id=current_user.id)
    db.add(db_tedarikci)
    db.commit()
    db.refresh(db_tedarikci)
    return db_tedarikci

@router.get("/", response_model=modeller.TedarikciListResponse)
def read_tedarikciler(
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(guvenlik.get_current_user),
    skip: int = 0,
    limit: int = 25,
    arama: Optional[str] = None,
    aktif_durum: Optional[bool] = None
):
    query = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.kullanici_id == current_user.id)

    if arama:
        search_term = f"%{arama}%"
        query = query.filter(
            or_(
                semalar.Tedarikci.ad.ilike(search_term),
                semalar.Tedarikci.telefon.ilike(search_term),
                semalar.Tedarikci.vergi_no.ilike(search_term)
            )
        )
    
    if aktif_durum is not None:
        query = query.filter(semalar.Tedarikci.aktif == aktif_durum)

    total_count = query.count()
    tedarikciler = query.offset(skip).limit(limit).all()

    cari_hizmeti = CariHesaplamaService(db)
    tedarikciler_with_balance = []
    for tedarikci in tedarikciler:
        net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci.id, "TEDARIKCI")
        tedarikci_dict = modeller.TedarikciRead.model_validate(tedarikci).model_dump()
        tedarikci_dict["net_bakiye"] = net_bakiye
        tedarikciler_with_balance.append(tedarikci_dict)

    return {"items": tedarikciler_with_balance, "total": total_count}

@router.get("/{tedarikci_id}", response_model=modeller.TedarikciRead)
def read_tedarikci(
    tedarikci_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user) # KRİTİK DÜZELTME: Tipi modeller.KullaniciRead olarak ayarlandı.
):
    # KRİTİK DÜZELTME: Sorgularda semalar.Tedarikci yerine modeller.Tedarikci kullanıldı.
    tedarikci = db.query(modeller.Tedarikci).filter(
        modeller.Tedarikci.id == tedarikci_id,
        modeller.Tedarikci.kullanici_id == current_user.id
    ).first()
    if not tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")

    cari_hizmeti = CariHesaplamaService(db)
    net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci_id, "TEDARIKCI")
    
    # ORM objesini Pydantic Read modeline dönüştürürken bakiye bilgisini ekliyoruz.
    tedarikci_read = modeller.TedarikciRead.model_validate(tedarikci, from_attributes=True)
    tedarikci_read.net_bakiye = net_bakiye
    
    return tedarikci_read

@router.put("/{tedarikci_id}", response_model=modeller.TedarikciRead)
def update_tedarikci(
    tedarikci_id: int,
    tedarikci: modeller.TedarikciUpdate,
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(guvenlik.get_current_user)
):
    db_tedarikci = db.query(semalar.Tedarikci).filter(
        semalar.Tedarikci.id == tedarikci_id,
        semalar.Tedarikci.kullanici_id == current_user.id
    ).first()
    if not db_tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")
    for key, value in tedarikci.model_dump(exclude_unset=True).items():
        setattr(db_tedarikci, key, value)
    db.commit()
    db.refresh(db_tedarikci)
    return db_tedarikci

@router.delete("/{tedarikci_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tedarikci(
    tedarikci_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(guvenlik.get_current_user)
):
    db_tedarikci = db.query(semalar.Tedarikci).filter(
        semalar.Tedarikci.id == tedarikci_id,
        semalar.Tedarikci.kullanici_id == current_user.id
    ).first()
    if not db_tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")
    db.delete(db_tedarikci)
    db.commit()
    return

@router.get("/{tedarikci_id}/net_bakiye", response_model=modeller.NetBakiyeResponse)
def get_net_bakiye_endpoint(
    tedarikci_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(guvenlik.get_current_user)
):
    tedarikci = db.query(semalar.Tedarikci).filter(
        semalar.Tedarikci.id == tedarikci_id,
        semalar.Tedarikci.kullanici_id == current_user.id
    ).first()
    if not tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")

    cari_hizmeti = CariHesaplamaService(db)
    net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci_id, "TEDARIKCI")
    return {"net_bakiye": net_bakiye}