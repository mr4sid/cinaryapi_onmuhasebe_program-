from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from .. import modeller, semalar
from ..veritabani import get_db
from typing import List, Optional

router = APIRouter(prefix="/nitelikler", tags=["Nitelikler"])

# Kategori endpointleri
@router.post("/kategoriler/", response_model=modeller.UrunKategoriRead)
def create_kategori(kategori: modeller.UrunKategoriCreate, db: Session = Depends(get_db)):
    db_kategori = semalar.UrunKategori(**kategori.model_dump())
    db.add(db_kategori)
    db.commit()
    db.refresh(db_kategori)
    return db_kategori

@router.get("/kategoriler", response_model=modeller.NitelikListResponse)
def read_kategoriler(skip: int = 0, limit: int = 1000, arama: str = Query(None), db: Session = Depends(get_db)):
    query = db.query(semalar.UrunKategori)
    if arama:
        query = query.filter(semalar.UrunKategori.ad.ilike(f"%{arama}%"))
    kategoriler = query.offset(skip).limit(limit).all()
    total_count = query.count()
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
    
    # Kategoriye bağlı ürünleri kontrol et
    if db_kategori.stoklar:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu kategoriye bağlı ürünler olduğu için silinemez.")
    
    db.delete(db_kategori)
    db.commit()
    return

# Marka endpointleri
@router.post("/markalar/", response_model=modeller.UrunMarkaRead)
def create_marka(marka: modeller.UrunMarkaCreate, db: Session = Depends(get_db)):
    db_marka = semalar.UrunMarka(**marka.model_dump())
    db.add(db_marka)
    db.commit()
    db.refresh(db_marka)
    return db_marka

@router.get("/markalar", response_model=modeller.NitelikListResponse)
def read_markalar(skip: int = 0, limit: int = 1000, arama: str = Query(None), db: Session = Depends(get_db)):
    query = db.query(semalar.UrunMarka)
    if arama:
        query = query.filter(semalar.UrunMarka.ad.ilike(f"%{arama}%"))
    markalar = query.offset(skip).limit(limit).all()
    total_count = query.count()
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
    
    # Markaya bağlı ürünleri kontrol et
    if db_marka.stoklar:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu markaya bağlı ürünler olduğu için silinemez.")
    
    db.delete(db_marka)
    db.commit()
    return

# Ürün Grubu endpointleri
@router.post("/urun_gruplari/", response_model=modeller.UrunGrubuRead)
def create_urun_grubu(urun_grubu: modeller.UrunGrubuCreate, db: Session = Depends(get_db)):
    db_urun_grubu = semalar.UrunGrubu(**urun_grubu.model_dump())
    db.add(db_urun_grubu)
    db.commit()
    db.refresh(db_urun_grubu)
    return db_urun_grubu

@router.get("/urun_gruplari", response_model=modeller.NitelikListResponse)
def read_urun_gruplari(skip: int = 0, limit: int = 1000, arama: str = Query(None), db: Session = Depends(get_db)):
    query = db.query(semalar.UrunGrubu)
    if arama:
        query = query.filter(semalar.UrunGrubu.ad.ilike(f"%{arama}%"))
    urun_gruplari = query.offset(skip).limit(limit).all()
    total_count = query.count()
    return {"items": [modeller.UrunGrubuRead.model_validate(ug, from_attributes=True) for ug in urun_gruplari], "total": total_count}

@router.get("/urun_gruplari/{urun_grubu_id}", response_model=modeller.UrunGrubuRead)
def read_urun_grubu(urun_grubu_id: int, db: Session = Depends(get_db)):
    urun_grubu = db.query(semalar.UrunGrubu).filter(semalar.UrunGrubu.id == urun_grubu_id).first()
    if not urun_grubu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün grubu bulunamadı")
    return urun_grubu

@router.put("/urun_gruplari/{urun_grubu_id}", response_model=modeller.UrunGrubuRead)
def update_urun_grubu(urun_grubu_id: int, urun_grubu: modeller.UrunGrubuUpdate, db: Session = Depends(get_db)):
    db_urun_grubu = db.query(semalar.UrunGrubu).filter(semalar.UrunGrubu.id == urun_grubu_id).first()
    if not db_urun_grubu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün grubu bulunamadı")
    for key, value in urun_grubu.model_dump(exclude_unset=True).items():
        setattr(db_urun_grubu, key, value)
    db.commit()
    db.refresh(db_urun_grubu)
    return db_urun_grubu

@router.delete("/urun_gruplari/{urun_grubu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_urun_grubu(urun_grubu_id: int, db: Session = Depends(get_db)):
    db_urun_grubu = db.query(semalar.UrunGrubu).filter(semalar.UrunGrubu.id == urun_grubu_id).first()
    if not db_urun_grubu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün grubu bulunamadı")
    
    # Ürün grubuna bağlı ürünleri kontrol et
    if db_urun_grubu.stoklar:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu ürün grubuna bağlı ürünler olduğu için silinemez.")
    
    db.delete(db_urun_grubu)
    db.commit()
    return

# Birim endpointleri
@router.post("/urun_birimleri/", response_model=modeller.UrunBirimiRead)
def create_urun_birimi(urun_birimi: modeller.UrunBirimiCreate, db: Session = Depends(get_db)):
    db_urun_birimi = semalar.UrunBirimi(**urun_birimi.model_dump())
    db.add(db_urun_birimi)
    db.commit()
    db.refresh(db_urun_birimi)
    return db_urun_birimi

@router.get("/urun_birimleri", response_model=modeller.NitelikListResponse)
def read_urun_birimleri(skip: int = 0, limit: int = 1000, arama: str = Query(None), db: Session = Depends(get_db)):
    query = db.query(semalar.UrunBirimi)
    if arama:
        query = query.filter(semalar.UrunBirimi.ad.ilike(f"%{arama}%"))
    urun_birimleri = query.offset(skip).limit(limit).all()
    total_count = query.count()
    return {"items": [modeller.UrunBirimiRead.model_validate(ub, from_attributes=True) for ub in urun_birimleri], "total": total_count}

@router.get("/urun_birimleri/{urun_birimi_id}", response_model=modeller.UrunBirimiRead)
def read_urun_birimi(urun_birimi_id: int, db: Session = Depends(get_db)):
    urun_birimi = db.query(semalar.UrunBirimi).filter(semalar.UrunBirimi.id == urun_birimi_id).first()
    if not urun_birimi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün birimi bulunamadı")
    return urun_birimi

@router.put("/urun_birimleri/{urun_birimi_id}", response_model=modeller.UrunBirimiRead)
def update_urun_birimi(urun_birimi_id: int, urun_birimi: modeller.UrunBirimiUpdate, db: Session = Depends(get_db)):
    db_urun_birimi = db.query(semalar.UrunBirimi).filter(semalar.UrunBirimi.id == urun_birimi_id).first()
    if not db_urun_birimi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün birimi bulunamadı")
    for key, value in urun_birimi.model_dump(exclude_unset=True).items():
        setattr(db_urun_birimi, key, value)
    db.commit()
    db.refresh(db_urun_birimi)
    return db_urun_birimi

@router.delete("/urun_birimleri/{urun_birimi_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_urun_birimi(urun_birimi_id: int, db: Session = Depends(get_db)):
    db_urun_birimi = db.query(semalar.UrunBirimi).filter(semalar.UrunBirimi.id == urun_birimi_id).first()
    if not db_urun_birimi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün birimi bulunamadı")
    
    # Birime bağlı ürünleri kontrol et
    if db_urun_birimi.stoklar:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu birime bağlı ürünler olduğu için silinemez.")
    
    db.delete(db_urun_birimi)
    db.commit()
    return

# Ülke endpointleri
@router.post("/ulkeler/", response_model=modeller.UlkeRead)
def create_ulke(ulke: modeller.UlkeCreate, db: Session = Depends(get_db)):
    db_ulke = semalar.Ulke(**ulke.model_dump())
    db.add(db_ulke)
    db.commit()
    db.refresh(db_ulke)
    return db_ulke

@router.get("/ulkeler", response_model=modeller.NitelikListResponse)
def read_ulkeler(skip: int = 0, limit: int = 1000, arama: str = Query(None), db: Session = Depends(get_db)):
    query = db.query(semalar.Ulke)
    if arama:
        query = query.filter(semalar.Ulke.ad.ilike(f"%{arama}%"))
    ulkeler = query.offset(skip).limit(limit).all()
    total_count = query.count()
    return {"items": [modeller.UlkeRead.model_validate(u, from_attributes=True) for u in ulkeler], "total": total_count}

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
    
    # Ülkeye bağlı ürünleri kontrol et
    if db_ulke.stoklar:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu ülkeye bağlı ürünler olduğu için silinemez.")
    
    db.delete(db_ulke)
    db.commit()
    return

# Gelir Sınıflandırma endpointleri
@router.post("/gelir_siniflandirmalari/", response_model=modeller.GelirSiniflandirmaRead)
def create_gelir_siniflandirma(siniflandirma: modeller.GelirSiniflandirmaCreate, db: Session = Depends(get_db)):
    db_siniflandirma = semalar.GelirSiniflandirma(**siniflandirma.model_dump())
    db.add(db_siniflandirma)
    db.commit()
    db.refresh(db_siniflandirma)
    return db_siniflandirma

@router.get("/gelir_siniflandirmalari", response_model=List[modeller.GelirSiniflandirmaRead])
def read_gelir_siniflandirmalari(
    skip: int = 0,
    limit: int = 100,
    id: Optional[int] = None, # YENİ PARAMETRE EKLENDİ
    db: Session = Depends(get_db)
):
    query = db.query(semalar.GelirSiniflandirma)
    if id: # YENİ KOD: id'ye göre filtrele
        query = query.filter(semalar.GelirSiniflandirma.id == id)
    return query.offset(skip).limit(limit).all()

@router.get("/gelir_siniflandirmalari/{siniflandirma_id}", response_model=modeller.GelirSiniflandirmaRead)
def read_gelir_siniflandirma(siniflandirma_id: int, db: Session = Depends(get_db)):
    siniflandirma = db.query(semalar.GelirSiniflandirma).filter(semalar.GelirSiniflandirma.id == siniflandirma_id).first()
    if not siniflandirma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gelir sınıflandırması bulunamadı")
    return siniflandirma

@router.put("/gelir_siniflandirmalari/{siniflandirma_id}", response_model=modeller.GelirSiniflandirmaRead)
def update_gelir_siniflandirma(siniflandirma_id: int, siniflandirma: modeller.GelirSiniflandirmaUpdate, db: Session = Depends(get_db)):
    db_siniflandirma = db.query(semalar.GelirSiniflandirma).filter(semalar.GelirSiniflandirma.id == siniflandirma_id).first()
    if not db_siniflandirma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gelir sınıflandırması bulunamadı")
    for key, value in siniflandirma.model_dump(exclude_unset=True).items():
        setattr(db_siniflandirma, key, value)
    db.commit()
    db.refresh(db_siniflandirma)
    return db_siniflandirma

@router.delete("/gelir_siniflandirmalari/{siniflandirma_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gelir_siniflandirma(siniflandirma_id: int, db: Session = Depends(get_db)):
    db_siniflandirma = db.query(semalar.GelirSiniflandirma).filter(semalar.GelirSiniflandirma.id == siniflandirma_id).first()
    if not db_siniflandirma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gelir sınıflandırması bulunamadı")
    
    # Sınıflandırmaya bağlı gelir/gider hareketlerini kontrol et
    if db_siniflandirma.gelir_giderler:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu gelir sınıflandırmasına bağlı hareketler olduğu için silinemez.")
    
    db.delete(db_siniflandirma)
    db.commit()
    return

# Gider Sınıflandırma endpointleri
@router.post("/gider_siniflandirmalari/", response_model=modeller.GiderSiniflandirmaRead)
def create_gider_siniflandirma(siniflandirma: modeller.GiderSiniflandirmaCreate, db: Session = Depends(get_db)):
    db_siniflandirma = semalar.GiderSiniflandirma(**siniflandirma.model_dump())
    db.add(db_siniflandirma)
    db.commit()
    db.refresh(db_siniflandirma)
    return db_siniflandirma

@router.get("/gider_siniflandirmalari", response_model=List[modeller.GiderSiniflandirmaRead])
def read_gider_siniflandirmalari(
    skip: int = 0,
    limit: int = 100,
    id: Optional[int] = None, # YENİ PARAMETRE EKLENDİ
    db: Session = Depends(get_db)
):
    query = db.query(semalar.GiderSiniflandirma)
    if id: # YENİ KOD: id'ye göre filtrele
        query = query.filter(semalar.GiderSiniflandirma.id == id)
    return query.offset(skip).limit(limit).all()

@router.get("/gider_siniflandirmalari/{siniflandirma_id}", response_model=modeller.GiderSiniflandirmaRead)
def read_gider_siniflandirma(siniflandirma_id: int, db: Session = Depends(get_db)):
    siniflandirma = db.query(semalar.GiderSiniflandirma).filter(semalar.GiderSiniflandirma.id == siniflandirma_id).first()
    if not siniflandirma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gider sınıflandırması bulunamadı")
    return siniflandirma

@router.put("/gider_siniflandirmalari/{siniflandirma_id}", response_model=modeller.GiderSiniflandirmaRead)
def update_gider_siniflandirma(siniflandirma_id: int, siniflandirma: modeller.GiderSiniflandirmaUpdate, db: Session = Depends(get_db)):
    db_siniflandirma = db.query(semalar.GiderSiniflandirma).filter(semalar.GiderSiniflandirma.id == siniflandirma_id).first()
    if not db_siniflandirma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gider sınıflandırması bulunamadı")
    for key, value in siniflandirma.model_dump(exclude_unset=True).items():
        setattr(db_siniflandirma, key, value)
    db.commit()
    db.refresh(db_siniflandirma)
    return db_siniflandirma

@router.delete("/gider_siniflandirmalari/{siniflandirma_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gider_siniflandirma(siniflandirma_id: int, db: Session = Depends(get_db)):
    db_siniflandirma = db.query(semalar.GiderSiniflandirma).filter(semalar.GiderSiniflandirma.id == siniflandirma_id).first()
    if not db_siniflandirma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gider sınıflandırması bulunamadı")
    
    # Sınıflandırmaya bağlı gelir/gider hareketlerini kontrol et
    if db_siniflandirma.gelir_giderler:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu gider sınıflandırmasına bağlı hareketler olduğu için silinemez.")
    
    db.delete(db_siniflandirma)
    db.commit()
    return