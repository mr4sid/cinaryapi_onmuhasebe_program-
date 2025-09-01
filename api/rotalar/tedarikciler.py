# api.zip/rotalar/tedarikciler.py dosyasının tamamını bu şekilde güncelleyin:
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import modeller, semalar
from ..veritabani import get_db
from ..api_servisler import CariHesaplamaService
router = APIRouter(prefix="/tedarikciler", tags=["Tedarikçiler"])

@router.post("/", response_model=modeller.TedarikciRead)
def create_tedarikci(tedarikci: modeller.TedarikciCreate, db: Session = Depends(get_db)):
    db_tedarikci = semalar.Tedarikci(**tedarikci.model_dump())
    db.add(db_tedarikci)
    db.commit()
    db.refresh(db_tedarikci)
    return db_tedarikci

@router.get("/", response_model=modeller.TedarikciListResponse)
def read_tedarikciler(
    skip: int = 0,
    limit: int = 100,
    arama: str = Query(None, min_length=1, max_length=50),
    aktif_durum: bool = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Tedarikci)

    if arama:
        query = query.filter(
            (semalar.Tedarikci.ad.ilike(f"%{arama}%")) |
            (semalar.Tedarikci.kod.ilike(f"%{arama}%")) |
            (semalar.Tedarikci.telefon.ilike(f"%{arama}%")) |
            (semalar.Tedarikci.vergi_no.ilike(f"%{arama}%"))
        )

    if aktif_durum is not None:
        query = query.filter(semalar.Tedarikci.aktif == aktif_durum)

    total_count = query.count()
    tedarikciler = query.offset(skip).limit(limit).all()

    # Yeni hizmet sınıfını kullanarak her tedarikçi için net bakiyeyi hesapla
    cari_hizmeti = CariHesaplamaService(db)
    tedarikciler_with_balance = []
    for tedarikci in tedarikciler:
        net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci.id, "TEDARIKCI")
        tedarikci_dict = modeller.TedarikciRead.model_validate(tedarikci).model_dump()
        tedarikci_dict["net_bakiye"] = net_bakiye
        tedarikciler_with_balance.append(tedarikci_dict)

    return {"items": tedarikciler_with_balance, "total": total_count}

@router.get("/{tedarikci_id}", response_model=modeller.TedarikciRead)
def read_tedarikci(tedarikci_id: int, db: Session = Depends(get_db)):
    tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.id == tedarikci_id).first()
    if not tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")

    # Yeni hizmet sınıfını kullanarak tedarikçinin net bakiyesini hesapla
    cari_hizmeti = CariHesaplamaService(db)
    net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci_id, "TEDARIKCI")
    tedarikci_dict = modeller.TedarikciRead.model_validate(tedarikci).model_dump()
    tedarikci_dict["net_bakiye"] = net_bakiye
    return tedarikci_dict

@router.put("/{tedarikci_id}", response_model=modeller.TedarikciRead)
def update_tedarikci(tedarikci_id: int, tedarikci: modeller.TedarikciUpdate, db: Session = Depends(get_db)):
    db_tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.id == tedarikci_id).first()
    if not db_tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")
    for key, value in tedarikci.model_dump(exclude_unset=True).items():
        setattr(db_tedarikci, key, value)
    db.commit()
    db.refresh(db_tedarikci)
    return db_tedarikci

@router.delete("/{tedarikci_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tedarikci(tedarikci_id: int, db: Session = Depends(get_db)):
    db_tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.id == tedarikci_id).first()
    if not db_tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")
    db.delete(db_tedarikci)
    db.commit()
    return

@router.get("/{tedarikci_id}/net_bakiye", response_model=modeller.NetBakiyeResponse)
def get_net_bakiye_endpoint(tedarikci_id: int, db: Session = Depends(get_db)):
    tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.id == tedarikci_id).first()
    if not tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")

    cari_hizmeti = CariHesaplamaService(db)
    net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci_id, "TEDARIKCI")
    return {"net_bakiye": net_bakiye}