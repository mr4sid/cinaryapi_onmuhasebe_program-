from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from .. import semalar, modeller
from ..veritabani import get_db

router = APIRouter(
    prefix="/nitelikler",
    tags=["Ürün Nitelikleri ve Listeler"]
)

class KategoriCreate(modeller.KategoriBase):
    id: Optional[int] = None # ID'nin POST isteğinde zorunlu olmaması için Optional yaptık

@router.post("/kategoriler", response_model=modeller.KategoriBase)
def create_kategori(kategori: KategoriCreate, db: Session = Depends(get_db)):
    """
    Yeni bir ürün kategorisi oluşturur.
    """
    # Kategori adının benzersizliğini kontrol et
    db_kategori = db.query(semalar.UrunKategorileri).filter(semalar.UrunKategorileri.kategori_adi == kategori.kategori_adi).first()
    if db_kategori:
        raise HTTPException(status_code=400, detail="Bu kategori adı zaten mevcut.")

    db_kategori = semalar.UrunKategorileri(kategori_adi=kategori.kategori_adi)
    db.add(db_kategori)
    db.commit()
    db.refresh(db_kategori)
    return db_kategori

@router.get("/kategoriler", response_model=List[modeller.KategoriBase])
def read_kategoriler(db: Session = Depends(get_db)):
    return db.query(semalar.UrunKategorileri).all()

@router.get("/markalar", response_model=List[modeller.MarkaBase])
def read_markalar(db: Session = Depends(get_db)):
    return db.query(semalar.UrunMarkalari).all()

@router.put("/kategoriler/{kategori_id}", response_model=modeller.KategoriBase)
def update_kategori(kategori_id: int, kategori: KategoriCreate, db: Session = Depends(get_db)):
    """
    Mevcut bir ürün kategorisini günceller.
    """
    db_kategori = db.query(semalar.UrunKategorileri).filter(semalar.UrunKategorileri.id == kategori_id).first()
    if db_kategori is None:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")
    
    # Kategori adının benzersizliğini kontrol et (eğer isim değişiyorsa)
    if db_kategori.kategori_adi != kategori.kategori_adi:
        existing_kategori = db.query(semalar.UrunKategorileri).filter(semalar.UrunKategorileri.kategori_adi == kategori.kategori_adi).first()
        if existing_kategori:
            raise HTTPException(status_code=400, detail="Bu kategori adı zaten mevcut.")

    db_kategori.kategori_adi = kategori.kategori_adi
    db.commit()
    db.refresh(db_kategori)
    return db_kategori

@router.delete("/kategoriler/{kategori_id}", status_code=204)
def delete_kategori(kategori_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip ürün kategorisini siler.
    """
    db_kategori = db.query(semalar.UrunKategorileri).filter(semalar.UrunKategorileri.id == kategori_id).first()
    if db_kategori is None:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")
    
    # Kategoriye bağlı ürün olup olmadığını kontrol edebiliriz (isteğe bağlı)
    # Eğer bağlı ürün varsa, silme işlemine izin vermeyebiliriz veya ürünlerin kategori ID'sini NULL yapabiliriz.
    # Şimdilik, doğrudan silme işlemi yapılıyor.

    db.delete(db_kategori)
    db.commit()
    return

# ==================== MARKA ENDPOINT'LERİ ====================
class MarkaCreate(modeller.MarkaBase):
    id: Optional[int] = None

@router.post("/markalar", response_model=modeller.MarkaBase)
def create_marka(marka: modeller.MarkaBase, db: Session = Depends(get_db)):
    """
    Yeni bir ürün markası oluşturur.
    """
    # Marka adının benzersizliğini kontrol et
    db_marka = db.query(semalar.UrunMarkalari).filter(semalar.UrunMarkalari.marka_adi == marka.marka_adi).first()
    if db_marka:
        raise HTTPException(status_code=400, detail="Bu marka adı zaten mevcut.")

    db_marka = semalar.UrunMarkalari(marka_adi=marka.marka_adi)
    db.add(db_marka)
    db.commit()
    db.refresh(db_marka)
    return db_marka

@router.put("/markalar/{marka_id}", response_model=modeller.MarkaBase)
def update_marka(marka_id: int, marka: modeller.MarkaBase, db: Session = Depends(get_db)):
    """
    Mevcut bir ürün markasını günceller.
    """
    db_marka = db.query(semalar.UrunMarkalari).filter(semalar.UrunMarkalari.id == marka_id).first()
    if db_marka is None:
        raise HTTPException(status_code=404, detail="Marka bulunamadı")
    
    # Marka adının benzersizliğini kontrol et (eğer isim değişiyorsa)
    if db_marka.marka_adi != marka.marka_adi:
        existing_marka = db.query(semalar.UrunMarkalari).filter(semalar.UrunMarkalari.marka_adi == marka.marka_adi).first()
        if existing_marka:
            raise HTTPException(status_code=400, detail="Bu marka adı zaten mevcut.")

    db_marka.marka_adi = marka.marka_adi
    db.commit()
    db.refresh(db_marka)
    return db_marka

@router.delete("/markalar/{marka_id}", status_code=204)
def delete_marka(marka_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip ürün markasını siler.
    """
    db_marka = db.query(semalar.UrunMarkalari).filter(semalar.UrunMarkalari.id == marka_id).first()
    if db_marka is None:
        raise HTTPException(status_code=404, detail="Marka bulunamadı")
    
    # Markaya bağlı ürün olup olmadığını kontrol edebiliriz (isteğe bağlı)
    # Eğer bağlı ürün varsa, silme işlemine izin vermeyebiliriz veya ürünlerin marka ID'sini NULL yapabiliriz.
    # Şimdilik, doğrudan silme işlemi yapılıyor.

    db.delete(db_marka)
    db.commit()
    return

# ==================== ÜRÜN GRUBU ENDPOINT'LERİ ====================

class UrunGrubuCreate(modeller.UrunGrubuBase):
    id: Optional[int] = None

# --- Ürün Grubu Endpoint'leri ---
@router.post("/urun_gruplari", response_model=modeller.UrunGrubu)
def urun_grubu_olustur(urun_grubu: modeller.UrunGrubuCreate, db: Session = Depends(get_db)):
    db_urun_grubu = semalar.UrunGrubu(grup_adi=urun_grubu.grup_adi)
    db.add(db_urun_grubu)
    db.commit()
    db.refresh(db_urun_grubu)
    return db_urun_grubu

@router.get("/urun_gruplari", response_model=List[modeller.UrunGrubu])
def urun_gruplarini_listele(db: Session = Depends(get_db)):
    return db.query(semalar.UrunGrubu).all()

@router.put("/urun_gruplari/{grup_id}", response_model=modeller.UrunGrubu)
def urun_grubu_guncelle(grup_id: int, urun_grubu: modeller.UrunGrubuUpdate, db: Session = Depends(get_db)):
    db_urun_grubu = db.query(semalar.UrunGrubu).filter(semalar.UrunGrubu.id == grup_id).first()
    if not db_urun_grubu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün grubu bulunamadı.")

    for key, value in urun_grubu.model_dump(exclude_unset=True).items():
        setattr(db_urun_grubu, key, value)

    db.commit()
    db.refresh(db_urun_grubu)
    return db_urun_grubu

@router.delete("/urun_gruplari/{grup_id}")
def urun_grubu_sil(grup_id: int, db: Session = Depends(get_db)):
    db_urun_grubu = db.query(semalar.UrunGrubu).filter(semalar.UrunGrubu.id == grup_id).first()
    if not db_urun_grubu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün grubu bulunamadı.")

    db.delete(db_urun_grubu)
    db.commit()
    return {"message": "Ürün grubu başarıyla silindi."}

# ==================== ÜRÜN BİRİMİ ENDPOINT'LERİ ====================

class UrunBirimiCreate(modeller.UrunBirimiBase):
    id: Optional[int] = None

# --- Ürün Birimi Endpoint'leri ---
@router.post("/urun_birimleri", response_model=modeller.UrunBirimi)
def urun_birimi_olustur(urun_birimi: modeller.UrunBirimiCreate, db: Session = Depends(get_db)):
    db_urun_birimi = semalar.UrunBirimi(birim_adi=urun_birimi.birim_adi)
    db.add(db_urun_birimi)
    db.commit()
    db.refresh(db_urun_birimi)
    return db_urun_birimi

@router.get("/urun_birimleri", response_model=List[modeller.UrunBirimi])
def urun_birimlerini_listele(db: Session = Depends(get_db)):
    return db.query(semalar.UrunBirimi).all()

@router.put("/urun_birimleri/{birim_id}", response_model=modeller.UrunBirimi)
def urun_birimi_guncelle(birim_id: int, urun_birimi: modeller.UrunBirimiUpdate, db: Session = Depends(get_db)):
    db_urun_birimi = db.query(semalar.UrunBirimi).filter(semalar.UrunBirimi.id == birim_id).first()
    if not db_urun_birimi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün birimi bulunamadı.")

    for key, value in urun_birimi.model_dump(exclude_unset=True).items():
        setattr(db_urun_birimi, key, value)

    db.commit()
    db.refresh(db_urun_birimi)
    return db_urun_birimi

@router.delete("/urun_birimleri/{birim_id}")
def urun_birimi_sil(birim_id: int, db: Session = Depends(get_db)):
    db_urun_birimi = db.query(semalar.UrunBirimi).filter(semalar.UrunBirimi.id == birim_id).first()
    if not db_urun_birimi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün birimi bulunamadı.")

    db.delete(db_urun_birimi)
    db.commit()
    return {"message": "Ürün birimi başarıyla silindi."}

# ==================== ÜLKE ENDPOINT'LERİ ====================

class UlkeCreate(modeller.UlkeBase):
    id: Optional[int] = None

# --- Ülke Endpoint'leri ---
@router.post("/ulkeler", response_model=modeller.Ulke)
def ulke_olustur(ulke: modeller.UlkeCreate, db: Session = Depends(get_db)):
    db_ulke = semalar.Ulke(ulke_adi=ulke.ulke_adi)
    db.add(db_ulke)
    db.commit()
    db.refresh(db_ulke)
    return db_ulke

@router.get("/ulkeler", response_model=List[modeller.Ulke])
def ulkeleri_listele(db: Session = Depends(get_db)):
    return db.query(semalar.Ulke).all()

@router.put("/ulkeler/{ulke_id}", response_model=modeller.Ulke)
def ulke_guncelle(ulke_id: int, ulke: modeller.UlkeUpdate, db: Session = Depends(get_db)):
    db_ulke = db.query(semalar.Ulke).filter(semalar.Ulke.id == ulke_id).first()
    if not db_ulke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ülke bulunamadı.")

    for key, value in ulke.model_dump(exclude_unset=True).items():
        setattr(db_ulke, key, value)

    db.commit()
    db.refresh(db_ulke)
    return db_ulke

@router.delete("/ulkeler/{ulke_id}")
def ulke_sil(ulke_id: int, db: Session = Depends(get_db)):
    db_ulke = db.query(semalar.Ulke).filter(semalar.Ulke.id == ulke_id).first()
    if not db_ulke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ülke bulunamadı.")

    db.delete(db_ulke)
    db.commit()
    return {"message": "Ülke başarıyla silindi."}

@router.get("/musteriler", response_model=List[modeller.MusteriBase])
def read_musteri_listesi(db: Session = Depends(get_db)):
    # perakende_haric=False gibi bir mantık eklenebilir
    return db.query(semalar.Musteri).order_by(semalar.Musteri.ad).all()

@router.get("/tedarikciler", response_model=List[modeller.TedarikciBase])
def read_tedarikci_listesi(db: Session = Depends(get_db)):
    return db.query(semalar.Tedarikci).order_by(semalar.Tedarikci.ad).all()
