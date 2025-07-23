from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from .. import modeller, semalar
from ..veritabani import get_db

router = APIRouter(prefix="/faturalar", tags=["Faturalar"])

@router.post("/", response_model=modeller.FaturaRead)
def create_fatura(fatura: modeller.FaturaCreate, db: Session = Depends(get_db)):
    db_fatura = semalar.Fatura(**fatura.model_dump(exclude={"kalemler"}))
    db.add(db_fatura)
    db.flush() # Fatura ID'sini almak için

    # Stok, Kasa ve Cari Hareketleri için işlem başlat
    # Bu kısmı transaction içinde yönetmek önemlidir.
    try:
        # Fatura Kalemlerini Ekle
        for kalem_data in fatura.kalemler:
            db_kalem = semalar.FaturaKalemi(fatura_id=db_fatura.id, **kalem_data.model_dump())
            db.add(db_kalem)
            
            # Stok Miktarını Güncelle (SATIŞ ise çıkış, ALIŞ ise giriş)
            db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == kalem_data.urun_id).first()
            if db_stok:
                miktar_degisimi = kalem_data.miktar
                if db_fatura.fatura_turu == "SATIŞ":
                    db_stok.miktar -= miktar_degisimi
                    islem_tipi = "ÇIKIŞ"
                elif db_fatura.fatura_turu == "ALIŞ":
                    db_stok.miktar += miktar_degisimi
                    islem_tipi = "GIRIŞ"
                else:
                    islem_tipi = "DİĞER" # Bilinmeyen fatura türü

                db.add(db_stok)

                # Stok Hareketi Ekle
                db_stok_hareket = semalar.StokHareket(
                    stok_id=kalem_data.urun_id,
                    tarih=db_fatura.tarih,
                    islem_tipi=islem_tipi,
                    miktar=miktar_degisimi,
                    kaynak="FATURA",
                    kaynak_id=db_fatura.id,
                    aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu})"
                )
                db.add(db_stok_hareket)

        # Cari Hareket Ekle
        if db_fatura.cari_id:
            islem_yone_cari = ""
            if db_fatura.fatura_turu == "SATIŞ":
                islem_yone_cari = "ALACAK" # Müşteriye satıştan alacak
                cari_turu = "MUSTERI"
            elif db_fatura.fatura_turu == "ALIŞ":
                islem_yone_cari = "BORC" # Tedarikçiden alıştan borç
                cari_turu = "TEDARIKCI"
            
            if islem_yone_cari:
                db_cari_hareket = semalar.CariHareket(
                    cari_id=db_fatura.cari_id,
                    cari_turu=cari_turu,
                    tarih=db_fatura.tarih,
                    islem_turu="FATURA",
                    islem_yone=islem_yone_cari,
                    tutar=db_fatura.genel_toplam,
                    aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu})",
                    kaynak="FATURA",
                    kaynak_id=db_fatura.id
                )
                db.add(db_cari_hareket)

        # Kasa/Banka Hareket Ekle (ödeme türü nakit/banka ise)
        if db_fatura.odeme_turu in ["Nakit", "Banka"] and db_fatura.kasa_banka_id:
            islem_turu_kasa = ""
            if db_fatura.fatura_turu == "SATIŞ":
                islem_turu_kasa = "GIRIS" # Satıştan kasaya/bankaya giriş
            elif db_fatura.fatura_turu == "ALIŞ":
                islem_turu_kasa = "ÇIKIŞ" # Alıştan kasadan/bankadan çıkış
            
            if islem_turu_kasa:
                db_kasa_banka_hareket = semalar.KasaBankaHareket(
                    kasa_banka_id=db_fatura.kasa_banka_id,
                    tarih=db_fatura.tarih,
                    islem_turu=db_fatura.fatura_turu, # Fatura türüyle aynı
                    islem_yone=islem_turu_kasa,
                    tutar=db_fatura.genel_toplam,
                    aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu})",
                    kaynak="FATURA",
                    kaynak_id=db_fatura.id
                )
                db.add(db_kasa_banka_hareket)
                
                # Kasa/Banka bakiyesini güncelle
                db_kasa_banka = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == db_fatura.kasa_banka_id).first()
                if db_kasa_banka:
                    if islem_turu_kasa == "GIRIS":
                        db_kasa_banka.bakiye += db_fatura.genel_toplam
                    else: # ÇIKIŞ
                        db_kasa_banka.bakiye -= db_fatura.genel_toplam
                    db.add(db_kasa_banka)

        db.commit()
        db.refresh(db_fatura)
        return db_fatura
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fatura oluşturulurken bir hata oluştu: {e}")

@router.get("/", response_model=modeller.FaturaListResponse)
def read_faturalar(
    skip: int = 0,
    limit: int = 100,
    arama: str = Query(None, min_length=1, max_length=50),
    fatura_turu: str = Query(None),
    baslangic_tarihi: str = Query(None),
    bitis_tarihi: str = Query(None),
    cari_id: int = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Fatura).join(semalar.Musteri, semalar.Fatura.cari_id == semalar.Musteri.id, isouter=True) \
                                   .join(semalar.Tedarikci, semalar.Fatura.cari_id == semalar.Tedarikci.id, isouter=True)

    if arama:
        query = query.filter(semalar.Fatura.fatura_no.ilike(f"%{arama}%"))
    
    if fatura_turu:
        query = query.filter(semalar.Fatura.fatura_turu == fatura_turu.upper())
    
    if baslangic_tarihi:
        query = query.filter(semalar.Fatura.tarih >= baslangic_tarihi)
    
    if bitis_tarihi:
        query = query.filter(semalar.Fatura.tarih <= bitis_tarihi)
    
    if cari_id:
        query = query.filter(semalar.Fatura.cari_id == cari_id)

    total_count = query.count()
    faturalar = query.order_by(semalar.Fatura.tarih.desc()).offset(skip).limit(limit).all()

    return {"items": [
        modeller.FaturaRead.model_validate(fatura, from_attributes=True)
        for fatura in faturalar
    ], "total": total_count}

@router.get("/{fatura_id}", response_model=modeller.FaturaRead)
def read_fatura(fatura_id: int, db: Session = Depends(get_db)):
    fatura = db.query(semalar.Fatura).filter(semalar.Fatura.id == fatura_id).first()
    if not fatura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura bulunamadı")
    return modeller.FaturaRead.model_validate(fatura, from_attributes=True)

@router.put("/{fatura_id}", response_model=modeller.FaturaRead)
def update_fatura(fatura_id: int, fatura: modeller.FaturaUpdate, db: Session = Depends(get_db)):
    db_fatura = db.query(semalar.Fatura).filter(semalar.Fatura.id == fatura_id).first()
    if not db_fatura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura bulunamadı")
    
    # Existing logic for handling updates (stock, cash, customer/supplier movements)
    # This part is complex and should be handled with care, potentially deleting old movements
    # and creating new ones based on changes, or calculating deltas.
    # For now, we'll assume basic attribute update. Complex update logic needs to be fully implemented.
    for key, value in fatura.model_dump(exclude_unset=True, exclude={"kalemler"}).items():
        setattr(db_fatura, key, value)
    
    # Kalemleri güncelleme veya silme/yeniden oluşturma mantığı buraya eklenecek
    # Şimdilik kalemleri ayrı endpoint üzerinden veya doğrudan burada silip yeniden oluşturma.
    
    db.commit()
    db.refresh(db_fatura)
    return db_fatura

@router.delete("/{fatura_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fatura(fatura_id: int, db: Session = Depends(get_db)):
    db_fatura = db.query(semalar.Fatura).filter(semalar.Fatura.id == fatura_id).first()
    if not db_fatura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura bulunamadı")
    
    # Faturaya bağlı kalemleri, stok hareketlerini, cari hareketleri, kasa/banka hareketlerini de sil
    # Bu işlemler bir transaction içinde olmalı
    try:
        # Fatura kalemlerini sil
        db.query(semalar.FaturaKalemi).filter(semalar.FaturaKalemi.fatura_id == fatura_id).delete(synchronize_session=False)

        # Stok hareketlerini geri al ve sil
        stok_hareketleri = db.query(semalar.StokHareket).filter(
            and_(
                semalar.StokHareket.kaynak == "FATURA",
                semalar.StokHareket.kaynak_id == fatura_id
            )
        ).all()
        for hareket in stok_hareketleri:
            stok = db.query(semalar.Stok).filter(semalar.Stok.id == hareket.stok_id).first()
            if stok:
                if hareket.islem_tipi == "GIRIŞ": # Giriş hareketi siliniyorsa miktar azalır
                    stok.miktar -= hareket.miktar
                elif hareket.islem_tipi == "ÇIKIŞ": # Çıkış hareketi siliniyorsa miktar artar
                    stok.miktar += hareket.miktar
                db.add(stok)
            db.delete(hareket)

        # Cari hareketlerini geri al ve sil
        cari_hareketleri = db.query(semalar.CariHareket).filter(
            and_(
                semalar.CariHareket.kaynak == "FATURA",
                semalar.CariHareket.kaynak_id == fatura_id
            )
        ).all()
        for hareket in cari_hareketleri:
            # Cari bakiyesi otomatik güncelleniyor olmalıydı.
            # Burada manuel bakiye güncelleme ihtiyacı varsa yapılmalı
            db.delete(hareket)
        
        # Kasa/Banka hareketlerini geri al ve sil
        kasa_banka_hareketleri = db.query(semalar.KasaBankaHareket).filter(
            and_(
                semalar.KasaBankaHareket.kaynak == "FATURA",
                semalar.KasaBankaHareket.kaynak_id == fatura_id
            )
        ).all()
        for hareket in kasa_banka_hareketleri:
            # Kasa/Banka bakiyesini geri al
            kasa_banka = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == hareket.kasa_banka_id).first()
            if kasa_banka:
                if hareket.islem_yone == "GIRIS":
                    kasa_banka.bakiye -= hareket.tutar
                elif hareket.islem_yone == "ÇIKIŞ":
                    kasa_banka.bakiye += hareket.tutar
                db.add(kasa_banka)
            db.delete(hareket)

        db.delete(db_fatura)
        db.commit()
        return

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fatura silinirken bir hata oluştu: {e}")


@router.get("/get_next_fatura_number", response_model=modeller.NextFaturaNoResponse)
def get_son_fatura_no_endpoint(fatura_turu: str, db: Session = Depends(get_db)):
    # Fatura türüne göre en yüksek fatura numarasını bul
    last_fatura = db.query(semalar.Fatura).filter(semalar.Fatura.fatura_turu == fatura_turu.upper()) \
                                       .order_by(semalar.Fatura.fatura_no.desc()).first()
    
    prefix = ""
    if fatura_turu.upper() == "SATIŞ":
        prefix = "SF"
    elif fatura_turu.upper() == "ALIŞ":
        prefix = "AF"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz fatura türü. 'SATIŞ' veya 'ALIŞ' olmalıdır.")

    next_sequence = 1
    if last_fatura and last_fatura.fatura_no.startswith(prefix):
        try:
            current_sequence_str = last_fatura.fatura_no[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            # Eğer numara formatı bozuksa, baştan başla
            pass
    
    next_fatura_no = f"{prefix}{next_sequence:09d}" # SF000000001 formatı
    return {"fatura_no": next_fatura_no}

@router.get("/{fatura_id}/kalemler", response_model=list[modeller.FaturaKalemiRead])
def get_fatura_kalemleri_endpoint(fatura_id: int, db: Session = Depends(get_db)):
    kalemler = db.query(semalar.FaturaKalemi).filter(semalar.FaturaKalemi.fatura_id == fatura_id).all()
    if not kalemler:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura kalemleri bulunamadı")
    return [modeller.FaturaKalemiRead.model_validate(kalem, from_attributes=True) for kalem in kalemler]

@router.get("/urun_faturalari", response_model=modeller.FaturaListResponse)
def get_urun_faturalari_endpoint(
    urun_id: int,
    fatura_turu: str = Query(None), # "SATIŞ" veya "ALIŞ"
    db: Session = Depends(get_db)
):
    # Belirli bir ürünü içeren faturaları bul
    query = db.query(semalar.Fatura).join(semalar.FaturaKalemi).filter(semalar.FaturaKalemi.urun_id == urun_id)

    if fatura_turu:
        query = query.filter(semalar.Fatura.fatura_turu == fatura_turu.upper())
    
    # Benzersiz faturaları al (bir fatura birden fazla aynı ürünü içerebilir)
    faturalar = query.distinct(semalar.Fatura.id).order_by(semalar.Fatura.tarih.desc()).all()

    if not faturalar:
        return {"items": [], "total": 0} # Boş liste döndür, 404 yerine
    
    return {"items": [
        modeller.FaturaRead.model_validate(fatura, from_attributes=True)
        for fatura in faturalar
    ], "total": len(faturalar)}