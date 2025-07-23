from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from .. import modeller, semalar
from ..veritabani import get_db

router = APIRouter(prefix="/stoklar", tags=["Stoklar"])

@router.post("/", response_model=modeller.StokRead)
def create_stok(stok: modeller.StokCreate, db: Session = Depends(get_db)):
    db_stok = semalar.Stok(**stok.model_dump())
    db.add(db_stok)
    db.commit()
    db.refresh(db_stok)
    return db_stok

@router.get("/", response_model=modeller.StokListResponse)
def read_stoklar(
    skip: int = 0,
    limit: int = 100,
    arama: str = Query(None, min_length=1, max_length=50),
    kategori_id: int = Query(None),
    marka_id: int = Query(None),
    stok_durumu: str = Query(None),
    kritik_stok_altinda: bool = Query(None),
    aktif_durum: bool = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Stok).join(semalar.UrunBirimi, semalar.Stok.birim_id == semalar.UrunBirimi.id, isouter=True) \
                                 .join(semalar.UrunKategori, semalar.Stok.kategori_id == semalar.UrunKategori.id, isouter=True) \
                                 .join(semalar.UrunMarka, semalar.Stok.marka_id == semalar.UrunMarka.id, isouter=True)

    if arama:
        query = query.filter(
            (semalar.Stok.ad.ilike(f"%{arama}%")) |
            (semalar.Stok.kod.ilike(f"%{arama}%"))
        )
    
    if kategori_id:
        query = query.filter(semalar.Stok.kategori_id == kategori_id)
    
    if marka_id:
        query = query.filter(semalar.Stok.marka_id == marka_id)

    if stok_durumu:
        # Stok durumu filtrelemesi eklenebilir (örn: 'Yeterli', 'Az', 'Kritik')
        pass # Mevcut `miktar` üzerinden UI tarafında yönetiliyor olabilir

    if kritik_stok_altinda is not None:
        if kritik_stok_altinda:
            query = query.filter(semalar.Stok.miktar < semalar.Stok.kritik_stok_seviyesi)
        else:
            query = query.filter(semalar.Stok.miktar >= semalar.Stok.kritik_stok_seviyesi)

    if aktif_durum is not None:
        query = query.filter(semalar.Stok.aktif == aktif_durum)

    total_count = query.count()
    stoklar = query.offset(skip).limit(limit).all()

    # Stok modellerini ilişkili verilerle birlikte dön
    return {"items": [
        modeller.StokRead.model_validate(stok, from_attributes=True)
        for stok in stoklar
    ], "total": total_count}

@router.get("/{stok_id}", response_model=modeller.StokRead)
def read_stok(stok_id: int, db: Session = Depends(get_db)):
    stok = db.query(semalar.Stok).filter(semalar.Stok.id == stok_id).first()
    if not stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    return modeller.StokRead.model_validate(stok, from_attributes=True)

@router.put("/{stok_id}", response_model=modeller.StokRead)
def update_stok(stok_id: int, stok: modeller.StokUpdate, db: Session = Depends(get_db)):
    db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == stok_id).first()
    if not db_stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    for key, value in stok.model_dump(exclude_unset=True).items():
        setattr(db_stok, key, value)
    db.commit()
    db.refresh(db_stok)
    return db_stok

@router.delete("/{stok_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stok(stok_id: int, db: Session = Depends(get_db)):
    db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == stok_id).first()
    if not db_stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    db.delete(db_stok)
    db.commit()
    return

@router.get("/{stok_id}/anlik_miktar", response_model=modeller.AnlikStokMiktariResponse)
def get_anlik_stok_miktari_endpoint(stok_id: int, db: Session = Depends(get_db)):
    stok = db.query(semalar.Stok).filter(semalar.Stok.id == stok_id).first()
    if not stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    
    return {"anlik_miktar": stok.miktar}

@router.get("/{stok_id}/hareketler", response_model=modeller.StokHareketListResponse)
def get_stok_hareketleri_endpoint(
    stok_id: int,
    skip: int = 0,
    limit: int = 100,
    islem_tipi: str = Query(None), # Örneğin 'GIRIŞ', 'ÇIKIŞ', 'MANUEL'
    baslangic_tarihi: str = Query(None),
    bitis_tarihi: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.StokHareket).filter(semalar.StokHareket.stok_id == stok_id)

    if islem_tipi:
        query = query.filter(semalar.StokHareket.islem_tipi == islem_tipi.upper())
    
    if baslangic_tarihi:
        query = query.filter(semalar.StokHareket.tarih >= baslangic_tarihi)
    
    if bitis_tarihi:
        query = query.filter(semalar.StokHareket.tarih <= bitis_tarihi)

    total_count = query.count()
    hareketler = query.order_by(semalar.StokHareket.tarih.desc(), semalar.StokHareket.id.desc()).offset(skip).limit(limit).all()

    return {"items": [
        modeller.StokHareketRead.model_validate(hareket, from_attributes=True)
        for hareket in hareketler
    ], "total": total_count}

@router.delete("/hareketler/{hareket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stok_hareket(hareket_id: int, db: Session = Depends(get_db)):
    # Sadece kaynak alanı "MANUEL" olan stok hareketlerini silmeye izin ver
    db_hareket = db.query(semalar.StokHareket).filter(
        and_(
            semalar.StokHareket.id == hareket_id,
            semalar.StokHareket.kaynak == "MANUEL"
        )
    ).first()

    if not db_hareket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Stok hareketi bulunamadı veya manuel olarak silinemez (otomatik oluşturulmuştur)."
        )
    
    # Hareket silindiğinde Stok miktarını da güncelle
    stok = db.query(semalar.Stok).filter(semalar.Stok.id == db_hareket.stok_id).first()
    if stok:
        if db_hareket.islem_tipi == "GIRIŞ":
            stok.miktar -= db_hareket.miktar
        elif db_hareket.islem_tipi == "ÇIKIŞ":
            stok.miktar += db_hareket.miktar
        db.add(stok) # Stok miktarını güncellemek için tekrar ekle
    
    db.delete(db_hareket)
    db.commit()
    return