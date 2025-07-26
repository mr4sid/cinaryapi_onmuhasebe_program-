# api/rotalar/kasalar_bankalar.py Dosyasının tam içeriği şu şekildedir. Lütfen. Güncellenmiş. Halinin tamamını yaz. Herhangi bir eksik olmadan? Veya hata olmadan.
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db
from datetime import date # Tarih tipi için import
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
router = APIRouter(
    prefix="/kasalar_bankalar",
    tags=["Kasa ve Banka Hesapları"]
)

# --- VERİ OKUMA (READ) ---

@router.get("/", response_model=modeller.KasaBankaListResponse) # response_model list[modeller.KasaBankaRead] yerine
def read_kasalar_bankalar(
    skip: int = 0,
    limit: int = 100,
    arama: Optional[str] = None, # Optional eklendi
    tip: Optional[str] = None, # tip parametresi eklendi
    aktif_durum: Optional[bool] = None, # aktif_durum parametresi eklendi
    db: Session = Depends(get_db)
):
    query = db.query(semalar.KasaBanka)

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
    
    # List yerine sözlük döndürüyoruz
    return {"items": [modeller.KasaBankaRead.model_validate(hesap, from_attributes=True) for hesap in hesaplar], "total": total_count}

@router.get("/{hesap_id}", response_model=modeller.KasaBankaRead)
def read_kasa_banka(hesap_id: int, db: Session = Depends(get_db)):
    hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == hesap_id).first()
    if not hesap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı")
    return modeller.KasaBankaRead.model_validate(hesap, from_attributes=True)

# --- VERİ OLUŞTURMA (CREATE) ---
class KasaBankaCreate(modeller.KasaBankaBase):
    # Base modeldeki id ve bakiye varsayılanları olmadığı için create modelinde de optional yapıldı.
    # Ancak normalde bakiye float olarak kesin gelmeli.
    # Hesap adına, tipine ve bakiyeye ek olarak diğer alanlar
    hesap_no: Optional[str] = None
    banka_adi: Optional[str] = None
    sube_adi: Optional[str] = None
    para_birimi: Optional[str] = "TL"
    acilis_tarihi: Optional[date] = None
    varsayilan_odeme_turu: Optional[str] = None

@router.post("/", response_model=modeller.KasaBankaBase)
def create_kasa_banka(hesap: modeller.KasaBankaCreate, db: Session = Depends(get_db)):
    """
    Yeni bir kasa/banka hesabı oluşturur.
    """
    print(f"DEBUG: create_kasa_banka - Gelen hesap verisi: {hesap.dict()}") # Debug print

    try:
        db_hesap = semalar.KasaBanka(
            hesap_adi=hesap.hesap_adi,
            kod=hesap.kod,
            tip=hesap.tip,
            bakiye=hesap.bakiye if hesap.bakiye is not None else 0.0, # None gelirse default değer ata
            para_birimi=hesap.para_birimi if hesap.para_birimi is not None else "TL", # None gelirse default değer ata
            banka_adi=hesap.banka_adi,
            sube_adi=hesap.sube_adi,
            hesap_no=hesap.hesap_no,
            varsayilan_odeme_turu=hesap.varsayilan_odeme_turu
        )
        print(f"DEBUG: create_kasa_banka - Oluşturulan db_hesap objesi: {db_hesap.__dict__}") # Debug print

        db.add(db_hesap)
        print("DEBUG: create_kasa_banka - db.add() başarılı.") # Debug print

        db.commit()
        print("DEBUG: create_kasa_banka - db.commit() başarılı.") # Debug print

        db.refresh(db_hesap)
        print("DEBUG: create_kasa_banka - db.refresh() başarılı.") # Debug print

        return db_hesap
    except IntegrityError:
        db.rollback()
        print(f"ERROR: create_kasa_banka - IntegrityError: Kod zaten kullanılıyor: {hesap.kod}") # Debug print
        raise HTTPException(status_code=400, detail=f"'{hesap.kod}' kodu zaten kullanılıyor. Lütfen farklı bir kod deneyin.")
    except SQLAlchemyError as e: # SQLAlchemy'ye özgü hataları yakala
        db.rollback()
        print(f"ERROR: create_kasa_banka - SQLAlchemyError: {str(e)}") # Debug print
        raise HTTPException(status_code=500, detail=f"Veritabanı işlemi sırasında hata oluştu: {str(e)}")
    except Exception as e: # Diğer tüm beklenmedik hataları yakala
        db.rollback()
        print(f"ERROR: create_kasa_banka - Genel Hata: {str(e)}") # Debug print
        raise HTTPException(status_code=500, detail=f"Kasa/Banka hesabı oluşturulurken beklenmedik bir hata oluştu: {str(e)}")
        
# --- VERİ GÜNCELLEME (UPDATE) ---
@router.put("/{hesap_id}", response_model=modeller.KasaBankaBase)
def update_kasa_banka(hesap_id: int, hesap: modeller.KasaBankaCreate, db: Session = Depends(get_db)):
    """
    Mevcut bir kasa/banka hesabının bilgilerini günceller.
    """
    db_hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == hesap_id).first()
    if db_hesap is None:
        raise HTTPException(status_code=404, detail="Kasa/Banka hesabı bulunamadı")
    
    hesap_data = hesap.dict(exclude_unset=True)
    for key, value in hesap_data.items():
        setattr(db_hesap, key, value)
    
    db.commit()
    db.refresh(db_hesap)
    return db_hesap

# --- VERİ SİLME (DELETE) ---
@router.delete("/{hesap_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kasa_banka(hesap_id: int, db: Session = Depends(get_db)):
    db_hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == hesap_id).first()
    if not db_hesap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı")
    db.delete(db_hesap)
    db.commit()
    return