# api.zip/rotalar/musteriler.py dosyasının tamamını bu şekilde güncelleyin:
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import modeller, semalar
from ..veritabani import get_db
from ..api_servisler import CariHesaplamaService
router = APIRouter(prefix="/musteriler", tags=["Müşteriler"])

@router.post("/", response_model=modeller.MusteriRead)
def create_musteri(musteri: modeller.MusteriCreate, db: Session = Depends(get_db)):
    db_musteri = semalar.Musteri(**musteri.model_dump())
    db.add(db_musteri)
    db.commit()
    db.refresh(db_musteri)
    return db_musteri

@router.get("/", response_model=modeller.MusteriListResponse)
def read_musteriler(
    skip: int = 0,
    limit: int = 100,
    arama: str = Query(None, min_length=1, max_length=50),
    aktif_durum: bool = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Musteri)

    if arama:
        query = query.filter(
            (semalar.Musteri.ad.ilike(f"%{arama}%")) |
            (semalar.Musteri.kod.ilike(f"%{arama}%")) |
            (semalar.Musteri.telefon.ilike(f"%{arama}%")) |
            (semalar.Musteri.vergi_no.ilike(f"%{arama}%"))
        )

    if aktif_durum is not None:
        query = query.filter(semalar.Musteri.aktif == aktif_durum)

    total_count = query.count()
    musteriler = query.offset(skip).limit(limit).all()

    # Yeni hizmet sınıfını kullanarak her müşteri için net bakiyeyi hesapla
    cari_hizmeti = CariHesaplamaService(db)
    musteriler_with_balance = []
    for musteri in musteriler:
        net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(musteri.id, "MUSTERI")
        musteri_dict = modeller.MusteriRead.model_validate(musteri).model_dump()
        musteri_dict["net_bakiye"] = net_bakiye
        musteriler_with_balance.append(musteri_dict)

    return {"items": musteriler_with_balance, "total": total_count}

@router.get("/{musteri_id}", response_model=modeller.MusteriRead)
def read_musteri(musteri_id: int, db: Session = Depends(get_db)):
    musteri = db.query(semalar.Musteri).filter(semalar.Musteri.id == musteri_id).first()
    if not musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")

    # Yeni hizmet sınıfını kullanarak müşterinin net bakiyesini hesapla
    cari_hizmeti = CariHesaplamaService(db)
    net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(musteri_id, "MUSTERI")
    musteri_dict = modeller.MusteriRead.model_validate(musteri).model_dump()
    musteri_dict["net_bakiye"] = net_bakiye
    return musteri_dict

@router.put("/{musteri_id}", response_model=modeller.MusteriRead)
def update_musteri(musteri_id: int, musteri: modeller.MusteriUpdate, db: Session = Depends(get_db)):
    db_musteri = db.query(semalar.Musteri).filter(semalar.Musteri.id == musteri_id).first()
    if not db_musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")
    for key, value in musteri.model_dump(exclude_unset=True).items():
        setattr(db_musteri, key, value)
    db.commit()
    db.refresh(db_musteri)
    return db_musteri

@router.delete("/{musteri_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_musteri(musteri_id: int, db: Session = Depends(get_db)):
    db_musteri = db.query(semalar.Musteri).filter(semalar.Musteri.id == musteri_id).first()
    if not db_musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")
    db.delete(db_musteri)
    db.commit()
    return

@router.get("/{musteri_id}/net_bakiye", response_model=modeller.NetBakiyeResponse)
def get_net_bakiye_endpoint(musteri_id: int, db: Session = Depends(get_db)):
    musteri = db.query(semalar.Musteri).filter(semalar.Musteri.id == musteri_id).first()
    if not musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")

    cari_hizmeti = CariHesaplamaService(db)
    net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(musteri_id, "MUSTERI")
    return {"net_bakiye": net_bakiye}