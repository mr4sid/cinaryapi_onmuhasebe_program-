from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from .. import modeller, semalar
from ..veritabani import get_db
from typing import List, Optional
from datetime import datetime # datetime objesi için eklendi

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

    # DEBUG_API: Gelen filtreleri ve başlangıç sorgusunu logla
    print(f"DEBUG_API: Stoklar filtreler: arama={arama}, kategori_id={kategori_id}, marka_id={marka_id}, urun_grubu_id={urun_grubu_id}, stok_durumu={stok_durumu}, kritik_stok_altinda={kritik_stok_altinda}, aktif_durum={aktif_durum}")
    print(f"DEBUG_API: Başlangıç sorgusu (SQL): {str(query.statement.compile(compile_kwargs={'literal_binds': True}))}")


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
        if stok_durumu: # Stokta Var
            query = query.filter(semalar.Stok.miktar > 0)
        else: # Stokta Yok
            query = query.filter(semalar.Stok.miktar <= 0)
            
    # Kritik stok filtresi, sadece True olarak açıkça belirtilirse uygulansın
    # Varsayılan olarak False olduğu için bu if bloğuna girmez ve filtre uygulamaz.
    if kritik_stok_altinda:
        query = query.filter(semalar.Stok.miktar <= semalar.Stok.min_stok_seviyesi) 

    # Aktif durum filtresi, sadece True veya False olarak belirtilirse uygulansın
    # Varsayılan olarak True geldiği için her zaman aktif ürünleri çekeriz.
    if aktif_durum is not None:
        query = query.filter(semalar.Stok.aktif == aktif_durum)

    # DEBUG_API: Filtreler uygulandıktan sonraki sorguyu logla
    print(f"DEBUG_API: Filtrelenmiş sorgu (SQL): {str(query.statement.compile(compile_kwargs={'literal_binds': True}))}")

    total_count = query.count()
    stoklar = query.offset(skip).limit(limit).all()

    # DEBUG_API: API'den çekilen ürün sayısını ve toplam kaydı logla
    print(f"DEBUG_API: Çekilen ürün sayısı: {len(stoklar)}, Toplam kayıt: {total_count}")

    stok_read_models = []
    for stok_item in stoklar:
        stok_read_data = modeller.StokRead.model_validate(stok_item).model_dump()
        
        # İlişkili Nitelik verilerini ekleme (varsa)
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

    # DEBUG_API: API yanıtını logla
    print(f"DEBUG_API: StokListResponse items count: {len(stok_read_models)}, total: {total_count}")

    return {"items": stok_read_models, "total": total_count}

@router.get("/{stok_id}", response_model=modeller.StokRead)
def read_stok(stok_id: int, db: Session = Depends(get_db)):
    stok = db.query(semalar.Stok).filter(semalar.Stok.id == stok_id).first()
    if not stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    
    # Pydantic modeline dönüştürme ve ilişkili verileri ekleme
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
            modeller.StokIslemTipiEnum.GIRIS_MANUEL_DUZELTME,
            modeller.StokIslemTipiEnum.SAYIM_FAZLASI,
            modeller.StokIslemTipiEnum.IADE_GIRIS,
            modeller.StokIslemTipiEnum.FATURA_ALIS # Eğer manuel olarak buraya alış faturası girişi yapılacaksa
        ]:
            stok_degisim_net = hareket.miktar
        elif hareket.islem_tipi in [
            modeller.StokIslemTipiEnum.CIKIS_MANUEL_DUZELTME,
            modeller.StokIslemTipiEnum.SAYIM_EKSIGI,
            modeller.StokIslemTipiEnum.ZAYIAT,
            modeller.StokIslemTipiEnum.FATURA_SATIS # Eğer manuel olarak buraya satış faturası çıkışı yapılacaksa
        ]:
            stok_degisim_net = -hareket.miktar
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz işlem tipi.")
        
        # Stok hareketini oluşturmadan önceki stok miktarını kaydet
        onceki_stok_miktari = db_stok.miktar

        db_stok.miktar += stok_degisim_net
        db.add(db_stok) # Değişikliği veritabanına yansıt

        # Stok hareketi kaydını oluştur
        db_hareket = semalar.StokHareket(
            stok_id=stok_id,
            tarih=hareket.tarih,
            islem_tipi=hareket.islem_tipi,
            miktar=hareket.miktar,
            birim_fiyat=hareket.birim_fiyat, # Birim fiyatı da kaydet
            aciklama=hareket.aciklama,
            kaynak=modeller.KaynakTipEnum.MANUEL, # Manuel işlem olduğunu belirt
            kaynak_id=None, # Manuel olduğu için kaynak ID'si olmaz
            olusturma_tarihi_saat=datetime.now(),
            onceki_stok=onceki_stok_miktari, # Önceki stok miktarını kaydet
            sonraki_stok=db_stok.miktar # Sonraki stok miktarını kaydet
        )
        db.add(db_hareket)

        db.commit() # Değişiklikleri kaydet
        db.refresh(db_hareket) # Oluşturulan objeyi yenile
        return modeller.StokHareketRead.model_validate(db_hareket, from_attributes=True) # Oluşturulan hareketi döndür

    except Exception as e:
        db.rollback() # Hata olursa tüm işlemleri geri al
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Stok hareketi oluşturulurken hata: {str(e)}")


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