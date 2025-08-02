from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from .. import modeller, semalar
from ..veritabani import get_db
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String

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
    kategori_id: Optional[int] = None,
    marka_id: Optional[int] = None,
    urun_grubu_id: Optional[int] = None,
    stok_durumu: Optional[bool] = None, # True = Stokta Var, False = Stokta Yok
    kritik_stok_altinda: Optional[bool] = False, # True ise kritik stok altındakiler
    aktif_durum: Optional[bool] = True, # True ise aktif ürünler
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Stok)

    if arama:
        query = query.filter(
            (semalar.Stok.ad.ilike(f"%{arama}%")) |
            (semalar.Stok.kod.ilike(f"%{arama}%"))
        )
    
    if kategori_id is not None:
        query = query.filter(semalar.Stok.kategori_id == kategori_id)
    
    if marka_id is not None:
        query = query.filter(semalar.Stok.marka_id == marka_id)

    if urun_grubu_id is not None:
        query = query.filter(semalar.Stok.urun_grubu_id == urun_grubu_id)

    if stok_durumu is not None:
        if stok_durumu:
            query = query.filter(semalar.Stok.miktar > 0)
        else:
            query = query.filter(semalar.Stok.miktar <= 0)
            
    if kritik_stok_altinda:
        query = query.filter(semalar.Stok.miktar <= semalar.Stok.min_stok_seviyesi) 

    if aktif_durum is not None:
        query = query.filter(semalar.Stok.aktif == aktif_durum)

    total_count = query.count()
    stoklar = query.offset(skip).limit(limit).all()

    stok_read_models = []
    for stok_item in stoklar:
        stok_read_data = modeller.StokRead.model_validate(stok_item).model_dump()
        
        if stok_item.kategori:
            stok_read_data['kategori'] = modeller.UrunKategoriRead.model_validate(stok_item.kategori).model_dump()
        if stok_item.marka:
            stok_read_data['marka'] = modeller.UrunMarkaRead.model_validate(stok_item.marka).model_dump()
        if stok_item.urun_grubu:
            stok_read_data['urun_grubu'] = modeller.UrunGrubuRead.model_validate(stok_item.urun_grubu).model_dump()
        if stok_item.birim:
            stok_read_data['birim'] = modeller.UrunBirimiRead.model_validate(stok_item.birim).model_dump()
        if stok_item.mense_ulke:
            stok_read_data['mense_ulke'] = modeller.UlkeRead.model_validate(stok_item.mense_ulke).model_dump()
            
        stok_read_models.append(stok_read_data)

    return {"items": stok_read_models, "total": total_count}

@router.get("/{stok_id}", response_model=modeller.StokRead)
def read_stok(stok_id: int, db: Session = Depends(get_db)):
    stok = db.query(semalar.Stok).filter(semalar.Stok.id == stok_id).first()
    if not stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    
    stok_read_data = modeller.StokRead.model_validate(stok).model_dump()
    
    if stok.kategori:
        stok_read_data['kategori'] = modeller.UrunKategoriRead.model_validate(stok.kategori).model_dump()
    if stok.marka:
        stok_read_data['marka'] = modeller.UrunMarkaRead.model_validate(stok.marka).model_dump()
    if stok.urun_grubu:
        stok_read_data['urun_grubu'] = modeller.UrunGrubuRead.model_validate(stok.urun_grubu).model_dump()
    if stok.birim:
        stok_read_data['birim'] = modeller.UrunBirimiRead.model_validate(stok.birim).model_dump()
    if stok.mense_ulke:
        stok_read_data['mense_ulke'] = modeller.UlkeRead.model_validate(stok.mense_ulke).model_dump()
        
    return stok_read_data

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

@router.post("/{stok_id}/hareket", response_model=modeller.StokHareketRead)
def create_stok_hareket(stok_id: int, hareket: modeller.StokHareketCreate, db: Session = Depends(get_db)):
    db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == stok_id).first()
    if not db_stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı.")
    
    if hareket.miktar <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Miktar pozitif bir değer olmalıdır.")

    db.begin_nested() # Transaction başlat

    try:
        # Stok miktarını güncelle
        stok_degisim_net = 0.0
        if hareket.islem_tipi in [
            semalar.StokIslemTipiEnum.GİRİŞ,
            semalar.StokIslemTipiEnum.SAYIM_FAZLASI,
            semalar.StokIslemTipiEnum.SATIŞ_İADE, # Satış iadesi stoğu artırır
            semalar.StokIslemTipiEnum.ALIŞ # Alış stoğu artırır
        ]:
            stok_degisim_net = hareket.miktar
        elif hareket.islem_tipi in [
            semalar.StokIslemTipiEnum.ÇIKIŞ,
            semalar.StokIslemTipiEnum.SAYIM_EKSİĞİ,
            semalar.StokIslemTipiEnum.ZAYIAT,
            semalar.StokIslemTipiEnum.SATIŞ, # Satış stoğu azaltır
            semalar.StokIslemTipiEnum.ALIŞ_İADE # Alış iadesi stoğu azaltır
        ]:
            stok_degisim_net = -hareket.miktar
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz işlem tipi.")
        
        onceki_stok_miktari = db_stok.miktar

        db_stok.miktar += stok_degisim_net
        db.add(db_stok)

        db_hareket = semalar.StokHareket(
            stok_id=stok_id,
            tarih=hareket.tarih,
            islem_tipi=hareket.islem_tipi,
            miktar=hareket.miktar,
            birim_fiyat=hareket.birim_fiyat,
            aciklama=hareket.aciklama,
            kaynak=semalar.KaynakTipEnum.MANUEL,
            kaynak_id=None,
            onceki_stok=onceki_stok_miktari,
            sonraki_stok=db_stok.miktar
        )
        db.add(db_hareket)

        db.commit()
        db.refresh(db_hareket)
        return modeller.StokHareketRead.model_validate(db_hareket, from_attributes=True)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Stok hareketi oluşturulurken hata: {str(e)}")


@router.get("/{stok_id}/hareketler", response_model=modeller.StokHareketListResponse)
def get_stok_hareketleri_endpoint(
    stok_id: int,
    skip: int = 0,
    limit: int = 100,
    islem_tipi: str = Query(None),
    baslangic_tarih: str = Query(None),
    bitis_tarihi: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.StokHareket).filter(semalar.StokHareket.stok_id == stok_id)

    if islem_tipi:
        query = query.filter(semalar.StokHareket.islem_tipi.cast(String) == islem_tipi)
    
    if baslangic_tarih:
        query = query.filter(semalar.StokHareket.tarih >= baslangic_tarih)
    
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
    
    stok = db.query(semalar.Stok).filter(semalar.Stok.id == db_hareket.stok_id).first()
    if stok:
        if db_hareket.islem_tipi == semalar.StokIslemTipiEnum.GİRİŞ:
            stok.miktar -= db_hareket.miktar
        elif db_hareket.islem_tipi == semalar.StokIslemTipiEnum.ÇIKIŞ:
            stok.miktar += db_hareket.miktar
        db.add(stok)
    
    db.delete(db_hareket)
    db.commit()
    return {"detail": "Stok hareketi başarıyla silindi."}