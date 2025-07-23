from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from .. import modeller, semalar
from ..veritabani import get_db

router = APIRouter(prefix="/siparisler", tags=["Siparişler"])

@router.post("/", response_model=modeller.SiparisRead)
def create_siparis(siparis: modeller.SiparisCreate, db: Session = Depends(get_db)):
    db_siparis = semalar.Siparis(**siparis.model_dump(exclude={"kalemler"}))
    db.add(db_siparis)
    db.flush() # Sipariş ID'sini almak için

    try:
        # Sipariş Kalemlerini Ekle
        for kalem_data in siparis.kalemler:
            db_kalem = semalar.SiparisKalemi(siparis_id=db_siparis.id, **kalem_data.model_dump())
            db.add(db_kalem)
            # Sipariş oluştuğunda stoktan düşme veya arttırma yapılmaz. Bu Fatura'ya dönüşünce olur.
            # Stok Hareketi Ekle (Sipariş için stok hareketleri genellikle yapılmaz veya pasif olur)
            # İstenirse buraya 'AYIRMA' veya 'REZERV' gibi stok hareketleri eklenebilir.

        # Cari Hareket Ekle (Sipariş için cari hareket genellikle yapılmaz veya pasif olur)
        # Sadece fatura kesildiğinde cari hareket oluşur.

        db.commit()
        db.refresh(db_siparis)
        return db_siparis
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Sipariş oluşturulurken bir hata oluştu: {e}")

@router.get("/", response_model=modeller.SiparisListResponse)
def read_siparisler(
    skip: int = 0,
    limit: int = 100,
    arama: str = Query(None, min_length=1, max_length=50),
    siparis_turu: str = Query(None),
    durum: str = Query(None),
    baslangic_tarihi: str = Query(None),
    bitis_tarihi: str = Query(None),
    cari_id: int = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Siparis).join(semalar.Musteri, semalar.Siparis.cari_id == semalar.Musteri.id, isouter=True) \
                                    .join(semalar.Tedarikci, semalar.Siparis.cari_id == semalar.Tedarikci.id, isouter=True)

    if arama:
        query = query.filter(semalar.Siparis.siparis_no.ilike(f"%{arama}%"))
    
    if siparis_turu:
        query = query.filter(semalar.Siparis.siparis_turu == siparis_turu.upper())
    
    if durum:
        query = query.filter(semalar.Siparis.durum == durum.upper())

    if baslangic_tarihi:
        query = query.filter(semalar.Siparis.tarih >= baslangic_tarihi)
    
    if bitis_tarihi:
        query = query.filter(semalar.Siparis.tarih <= bitis_tarihi)
    
    if cari_id:
        query = query.filter(semalar.Siparis.cari_id == cari_id)

    total_count = query.count()
    siparisler = query.order_by(semalar.Siparis.tarih.desc()).offset(skip).limit(limit).all()

    return {"items": [
        modeller.SiparisRead.model_validate(siparis, from_attributes=True)
        for siparis in siparisler
    ], "total": total_count}

@router.get("/{siparis_id}", response_model=modeller.SiparisRead)
def read_siparis(siparis_id: int, db: Session = Depends(get_db)):
    siparis = db.query(semalar.Siparis).filter(semalar.Siparis.id == siparis_id).first()
    if not siparis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş bulunamadı")
    return modeller.SiparisRead.model_validate(siparis, from_attributes=True)

@router.put("/{siparis_id}", response_model=modeller.SiparisRead)
def update_siparis(siparis_id: int, siparis: modeller.SiparisUpdate, db: Session = Depends(get_db)):
    db_siparis = db.query(semalar.Siparis).filter(semalar.Siparis.id == siparis_id).first()
    if not db_siparis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş bulunamadı")
    
    for key, value in siparis.model_dump(exclude_unset=True, exclude={"kalemler"}).items():
        setattr(db_siparis, key, value)
    
    # Kalemleri güncelleme veya silme/yeniden oluşturma mantığı buraya eklenecek
    # Şimdilik kalemleri ayrı endpoint üzerinden veya doğrudan burada silip yeniden oluşturma.

    db.commit()
    db.refresh(db_siparis)
    return db_siparis

@router.delete("/{siparis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_siparis(siparis_id: int, db: Session = Depends(get_db)):
    db_siparis = db.query(semalar.Siparis).filter(semalar.Siparis.id == siparis_id).first()
    if not db_siparis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş bulunamadı")
    
    # Sipariş kalemlerini sil
    db.query(semalar.SiparisKalemi).filter(semalar.SiparisKalemi.siparis_id == siparis_id).delete(synchronize_session=False)

    db.delete(db_siparis)
    db.commit()
    return

@router.get("/next_siparis_no", response_model=modeller.NextSiparisNoResponse)
def get_next_siparis_no_endpoint(prefix: str = Query("MS", max_length=2), db: Session = Depends(get_db)):
    # Belirtilen prefix'e göre en yüksek sipariş numarasını bul
    last_siparis = db.query(semalar.Siparis).filter(semalar.Siparis.siparis_no.ilike(f"{prefix}%")) \
                                           .order_by(semalar.Siparis.siparis_no.desc()).first()
    
    next_sequence = 1
    if last_siparis and last_siparis.siparis_no.startswith(prefix):
        try:
            current_sequence_str = last_siparis.siparis_no[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            # Eğer numara formatı bozuksa, baştan başla
            pass
    
    next_siparis_no = f"{prefix}{next_sequence:09d}" # MS000000001 formatı
    return {"siparis_no": next_siparis_no}

@router.get("/{siparis_id}/kalemler", response_model=list[modeller.SiparisKalemiRead])
def get_siparis_kalemleri_endpoint(siparis_id: int, db: Session = Depends(get_db)):
    kalemler = db.query(semalar.SiparisKalemi).filter(semalar.SiparisKalemi.siparis_id == siparis_id).all()
    if not kalemler:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş kalemleri bulunamadı")
    return [modeller.SiparisKalemiRead.model_validate(kalem, from_attributes=True) for kalem in kalemler]