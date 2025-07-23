from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import modeller, semalar
from ..veritabani import get_db

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

    # Her müşteri için net bakiyeyi hesapla ve ekle
    musteriler_with_balance = []
    for musteri in musteriler:
        net_bakiye = calculate_cari_net_bakiye(db, musteri.id, "MUSTERI")
        musteri_dict = modeller.MusteriRead.model_validate(musteri).model_dump()
        musteri_dict["net_bakiye"] = net_bakiye
        musteriler_with_balance.append(musteri_dict)

    return {"items": musteriler_with_balance, "total": total_count}


@router.get("/{musteri_id}", response_model=modeller.MusteriRead)
def read_musteri(musteri_id: int, db: Session = Depends(get_db)):
    musteri = db.query(semalar.Musteri).filter(semalar.Musteri.id == musteri_id).first()
    if not musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")
    
    # Müşteri detayını dönerken net bakiyeyi de ekleyelim
    net_bakiye = calculate_cari_net_bakiye(db, musteri_id, "MUSTERI")
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

# Cari net bakiyeyi hesaplayan yardımcı fonksiyon
def calculate_cari_net_bakiye(db: Session, cari_id: int, cari_turu: str) -> float:
    # `CariHareket` modelini kullanarak alacak ve borç hareketlerini topluyoruz.
    # `alacak` ve `borc` alanları varsa
    alacak_toplami = db.query(func.sum(semalar.CariHareket.tutar)).filter(
        semalar.CariHareket.cari_id == cari_id,
        semalar.CariHareket.cari_turu == cari_turu,
        semalar.CariHareket.islem_yone == "ALACAK" # ALACAK'a gelen tutarlar
    ).scalar() or 0.0

    borc_toplami = db.query(func.sum(semalar.CariHareket.tutar)).filter(
        semalar.CariHareket.cari_id == cari_id,
        semalar.CariHareket.cari_turu == cari_turu,
        semalar.CariHareket.islem_yone == "BORC" # BORC'a giden tutarlar
    ).scalar() or 0.0

    # Net bakiye = Alacak - Borç
    net_bakiye = alacak_toplami - borc_toplami
    return net_bakiye

@router.get("/{musteri_id}/net_bakiye", response_model=modeller.NetBakiyeResponse)
def get_net_bakiye_endpoint(musteri_id: int, db: Session = Depends(get_db)):
    musteri = db.query(semalar.Musteri).filter(semalar.Musteri.id == musteri_id).first()
    if not musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")
    
    net_bakiye = calculate_cari_net_bakiye(db, musteri_id, "MUSTERI")
    return {"net_bakiye": net_bakiye}