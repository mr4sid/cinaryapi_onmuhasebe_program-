from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import modeller, semalar
from ..veritabani import get_db

router = APIRouter(prefix="/nitelikler", tags=["Nitelikler"])

# KATEGORİLER
@router.post("/kategoriler", response_model=modeller.UrunKategoriRead)
def create_kategori(kategori: modeller.UrunKategoriCreate, db: Session = Depends(get_db)):
    db_kategori = semalar.UrunKategori(**kategori.model_dump())
    db.add(db_kategori)
    db.commit()
    db.refresh(db_kategori)
    return db_kategori

@router.get("/kategoriler", response_model=dict) # response_model dict olarak değiştirildi
def read_kategoriler(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(semalar.UrunKategori)
    total_count = query.count() # Toplam kayıt sayısı alındı
    kategoriler = query.offset(skip).limit(limit).all()
    
    # ORM objelerini Pydantic modellerine dönüştürerek döndür
    return {"items": [modeller.UrunKategoriRead.model_validate(k, from_attributes=True) for k in kategoriler], "total": total_count}

@router.get("/kategoriler/{kategori_id}", response_model=modeller.UrunKategoriRead)
def read_kategori(kategori_id: int, db: Session = Depends(get_db)):
    kategori = db.query(semalar.UrunKategori).filter(semalar.UrunKategori.id == kategori_id).first()
    if not kategori:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori bulunamadı")
    return kategori

@router.put("/kategoriler/{kategori_id}", response_model=modeller.UrunKategoriRead)
def update_kategori(kategori_id: int, kategori: modeller.UrunKategoriUpdate, db: Session = Depends(get_db)):
    db_kategori = db.query(semalar.UrunKategori).filter(semalar.UrunKategori.id == kategori_id).first()
    if not db_kategori:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori bulunamadı")
    for key, value in kategori.model_dump(exclude_unset=True).items():
        setattr(db_kategori, key, value)
    db.commit()
    db.refresh(db_kategori)
    return db_kategori

@router.delete("/kategoriler/{kategori_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kategori(kategori_id: int, db: Session = Depends(get_db)):
    db_kategori = db.query(semalar.UrunKategori).filter(semalar.UrunKategori.id == kategori_id).first()
    if not db_kategori:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori bulunamadı")
    db.delete(db_kategori)
    db.commit()
    return

# MARKALAR (Mevcut, kontrol amaçlı tam halini ekledik)
@router.post("/markalar", response_model=modeller.UrunMarkaRead)
def create_marka(marka: modeller.UrunMarkaCreate, db: Session = Depends(get_db)):
    db_marka = semalar.UrunMarka(**marka.model_dump())
    db.add(db_marka)
    db.commit()
    db.refresh(db_marka)
    return db_marka

@router.get("/markalar", response_model=dict)
def read_markalar(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(semalar.UrunMarka)
    total_count = query.count()
    markalar = query.offset(skip).limit(limit).all()
    
    # ORM objelerini Pydantic modellerine dönüştürerek döndür
    return {"items": [modeller.UrunMarkaRead.model_validate(m, from_attributes=True) for m in markalar], "total": total_count}

@router.get("/markalar/{marka_id}", response_model=modeller.UrunMarkaRead)
def read_marka(marka_id: int, db: Session = Depends(get_db)):
    marka = db.query(semalar.UrunMarka).filter(semalar.UrunMarka.id == marka_id).first()
    if not marka:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marka bulunamadı")
    return marka

@router.put("/markalar/{marka_id}", response_model=modeller.UrunMarkaRead)
def update_marka(marka_id: int, marka: modeller.UrunMarkaUpdate, db: Session = Depends(get_db)):
    db_marka = db.query(semalar.UrunMarka).filter(semalar.UrunMarka.id == marka_id).first()
    if not db_marka:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marka bulunamadı")
    for key, value in marka.model_dump(exclude_unset=True).items():
        setattr(db_marka, key, value)
    db.commit()
    db.refresh(db_marka)
    return db_marka

@router.delete("/markalar/{marka_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_marka(marka_id: int, db: Session = Depends(get_db)):
    db_marka = db.query(semalar.UrunMarka).filter(semalar.UrunMarka.id == marka_id).first()
    if not db_marka:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marka bulunamadı")
    db.delete(db_marka)
    db.commit()
    return

# ÜRÜN GRUPLARI (YENİ EKLENEN KISIM)
@router.post("/urun_gruplari", response_model=modeller.UrunGrubuRead)
def create_urun_grubu(urun_grubu: modeller.UrunGrubuCreate, db: Session = Depends(get_db)):
    db_urun_grubu = semalar.UrunGrubu(**urun_grubu.model_dump())
    db.add(db_urun_grubu)
    db.commit()
    db.refresh(db_urun_grubu)
    return db_urun_grubu

@router.get("/urun_gruplari", response_model=dict)
def read_urun_gruplari(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(semalar.UrunGrubu)
    total_count = query.count()
    urun_gruplari = query.offset(skip).limit(limit).all()
    
    # ORM objelerini Pydantic modellerine dönüştürerek döndür
    return {"items": [modeller.UrunGrubuRead.model_validate(g, from_attributes=True) for g in urun_gruplari], "total": total_count}

@router.get("/urun_gruplari/{grup_id}", response_model=modeller.UrunGrubuRead)
def read_urun_grubu(grup_id: int, db: Session = Depends(get_db)):
    urun_grubu = db.query(semalar.UrunGrubu).filter(semalar.UrunGrubu.id == grup_id).first()
    if not urun_grubu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün grubu bulunamadı")
    return urun_grubu

@router.put("/urun_gruplari/{grup_id}", response_model=modeller.UrunGrubuRead)
def update_urun_grubu(grup_id: int, urun_grubu: modeller.UrunGrubuUpdate, db: Session = Depends(get_db)):
    db_urun_grubu = db.query(semalar.UrunGrubu).filter(semalar.UrunGrubu.id == grup_id).first()
    if not db_urun_grubu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün grubu bulunamadı")
    for key, value in urun_grubu.model_dump(exclude_unset=True).items():
        setattr(db_urun_grubu, key, value)
    db.commit()
    db.refresh(db_urun_grubu)
    return db_urun_grubu

@router.delete("/urun_gruplari/{grup_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_urun_grubu(grup_id: int, db: Session = Depends(get_db)):
    db_urun_grubu = db.query(semalar.UrunGrubu).filter(semalar.UrunGrubu.id == grup_id).first()
    if not db_urun_grubu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün grubu bulunamadı")
    db.delete(db_urun_grubu)
    db.commit()
    return

# ÜRÜN BİRİMLERİ (YENİ EKLENEN KISIM)
@router.post("/urun_birimleri", response_model=modeller.UrunBirimiRead)
def create_urun_birimi(urun_birimi: modeller.UrunBirimiCreate, db: Session = Depends(get_db)):
    db_urun_birimi = semalar.UrunBirimi(**urun_birimi.model_dump())
    db.add(db_urun_birimi)
    db.commit()
    db.refresh(db_urun_birimi)
    return db_urun_birimi

@router.get("/urun_birimleri", response_model=dict)
def read_urun_birimleri(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(semalar.UrunBirimi)
    total_count = query.count()
    urun_birimleri = query.offset(skip).limit(limit).all()
    
    # ORM objelerini Pydantic modellerine dönüştürerek döndür
    return {"items": [modeller.UrunBirimiRead.model_validate(b, from_attributes=True) for b in urun_birimleri], "total": total_count}

@router.get("/urun_birimleri/{birim_id}", response_model=modeller.UrunBirimiRead)
def read_urun_birimi(birim_id: int, db: Session = Depends(get_db)):
    urun_birimi = db.query(semalar.UrunBirimi).filter(semalar.UrunBirimi.id == birim_id).first()
    if not urun_birimi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün birimi bulunamadı")
    return urun_birimi

@router.put("/urun_birimleri/{birim_id}", response_model=modeller.UrunBirimiRead)
def update_urun_birimi(birim_id: int, urun_birimi: modeller.UrunBirimiUpdate, db: Session = Depends(get_db)):
    db_urun_birimi = db.query(semalar.UrunBirimi).filter(semalar.UrunBirimi.id == birim_id).first()
    if not db_urun_birimi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün birimi bulunamadı")
    for key, value in urun_birimi.model_dump(exclude_unset=True).items():
        setattr(db_urun_birimi, key, value)
    db.commit()
    db.refresh(db_urun_birimi)
    return db_urun_birimi

@router.delete("/urun_birimleri/{birim_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_urun_birimi(birim_id: int, db: Session = Depends(get_db)):
    db_urun_birimi = db.query(semalar.UrunBirimi).filter(semalar.UrunBirimi.id == birim_id).first()
    if not db_urun_birimi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün birimi bulunamadı")
    db.delete(db_urun_birimi)
    db.commit()
    return

# ÜLKELER (YENİ EKLENEN KISIM)
@router.post("/ulkeler", response_model=modeller.UlkeRead)
def create_ulke(ulke: modeller.UlkeCreate, db: Session = Depends(get_db)):
    db_ulke = semalar.Ulke(**ulke.model_dump())
    db.add(db_ulke)
    db.commit()
    db.refresh(db_ulke)
    return db_ulke

@router.get("/ulkeler", response_model=dict)
def read_ulkeler(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(semalar.Ulke)
    total_count = query.count()
    ulkeler = query.offset(skip).limit(limit).all()
    
    # ORM objelerini Pydantic modellerine dönüştürerek döndür
    return {"items": [modeller.UlkeRead.model_validate(u, from_attributes=True) for u in ulkeler], "total": total_count}

@router.get("/gelir_siniflandirmalari", response_model=dict)
def read_gelir_siniflandirmalari(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(semalar.GelirSiniflandirma)
    total_count = query.count()
    siniflandirmalar = query.offset(skip).limit(limit).all()
    return {"items": siniflandirmalar, "total": total_count}

@router.get("/gider_siniflandirmalari", response_model=dict)
def read_gider_siniflandirmalari(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(semalar.GiderSiniflandirma)
    total_count = query.count()
    siniflandirmalar = query.offset(skip).limit(limit).all()
    return {"items": siniflandirmalar, "total": total_count}

@router.get("/ulkeler/{ulke_id}", response_model=modeller.UlkeRead)
def read_ulke(ulke_id: int, db: Session = Depends(get_db)):
    ulke = db.query(semalar.Ulke).filter(semalar.Ulke.id == ulke_id).first()
    if not ulke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ülke bulunamadı")
    return ulke

@router.put("/ulkeler/{ulke_id}", response_model=modeller.UlkeRead)
def update_ulke(ulke_id: int, ulke: modeller.UlkeUpdate, db: Session = Depends(get_db)):
    db_ulke = db.query(semalar.Ulke).filter(semalar.Ulke.id == ulke_id).first()
    if not db_ulke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ülke bulunamadı")
    for key, value in ulke.model_dump(exclude_unset=True).items():
        setattr(db_ulke, key, value)
    db.commit()
    db.refresh(db_ulke)
    return db_ulke

@router.delete("/ulkeler/{ulke_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ulke(ulke_id: int, db: Session = Depends(get_db)):
    db_ulke = db.query(semalar.Ulke).filter(semalar.Ulke.id == ulke_id).first()
    if not db_ulke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ülke bulunamadı")
    db.delete(db_ulke)
    db.commit()
    return