from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from .. import modeller, semalar
from ..veritabani import get_db
from typing import List, Optional, Any
from datetime import datetime
from sqlalchemy import String

# DEĞİŞİKLİK: Doğru içe aktarma yolu kullanıldı
from hizmetler import FaturaService
import logging
from ..guvenlik import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stoklar", tags=["Stoklar"])


@router.post("/", response_model=modeller.StokRead)
def create_stok(
    stok: modeller.StokCreate,
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(get_current_user)
):
    db_stok = semalar.Stok(**stok.model_dump(), kullanici_id=current_user.id)
    db.add(db_stok)
    db.commit()
    db.refresh(db_stok)
    return db_stok

@router.get("/", response_model=modeller.StokListResponse)
def read_stoklar(
    skip: int = 0,
    limit: int = 25,
    arama: Optional[str] = None,
    aktif_durum: Optional[bool] = True,
    kritik_stok_altinda: Optional[bool] = False,
    kategori_id: Optional[int] = None,
    marka_id: Optional[int] = None,
    urun_grubu_id: Optional[int] = None,
    stokta_var: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(get_current_user)
):
    query = db.query(semalar.Stok).filter(semalar.Stok.kullanici_id == current_user.id)
    
    if arama:
        search_filter = or_(
            semalar.Stok.kod.ilike(f"%{arama}%"),
            semalar.Stok.ad.ilike(f"%{arama}%")
        )
        query = query.filter(search_filter)

    if aktif_durum is not None:
        query = query.filter(semalar.Stok.aktif == aktif_durum)

    if kritik_stok_altinda:
        query = query.filter(semalar.Stok.miktar <= semalar.Stok.min_stok_seviyesi)

    if kategori_id:
        query = query.filter(semalar.Stok.kategori_id == kategori_id)

    if marka_id:
        query = query.filter(semalar.Stok.marka_id == marka_id)

    if urun_grubu_id:
        query = query.filter(semalar.Stok.urun_grubu_id == urun_grubu_id)

    if stokta_var is not None:
        if stokta_var:
            query = query.filter(semalar.Stok.miktar > 0)
        else:
            query = query.filter(semalar.Stok.miktar <= 0)

    total_count = query.count()
    
    stoklar = query.offset(skip).limit(limit).all()
    
    return {"items": [
        modeller.StokRead.model_validate(s, from_attributes=True)
        for s in stoklar
    ], "total": total_count}

@router.get("/ozet", response_model=modeller.StokOzetResponse)
def get_stok_ozet(
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(get_current_user)
):
    query = db.query(semalar.Stok).filter(semalar.Stok.kullanici_id == current_user.id)
    
    toplam_miktar = query.with_entities(func.sum(semalar.Stok.miktar)).scalar() or 0
    toplam_alis_fiyati = query.with_entities(func.sum(semalar.Stok.alis_fiyati * semalar.Stok.miktar)).scalar() or 0
    toplam_satis_fiyati = query.with_entities(func.sum(semalar.Stok.satis_fiyati * semalar.Stok.miktar)).scalar() or 0
    
    toplam_urun_sayisi = query.filter(semalar.Stok.aktif == True).count()
    
    return {
        "toplam_urun_sayisi": toplam_urun_sayisi,
        "toplam_miktar": toplam_miktar,
        "toplam_maliyet": toplam_alis_fiyati,
        "toplam_satis_tutari": toplam_satis_fiyati
    }

@router.get("/{stok_id}", response_model=modeller.StokRead)
def read_stok(
    stok_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(get_current_user)
):
    stok = db.query(semalar.Stok).filter(
        semalar.Stok.id == stok_id,
        semalar.Stok.kullanici_id == current_user.id
    ).first()
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
def update_stok(
    stok_id: int,
    stok: modeller.StokUpdate,
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(get_current_user)
):
    db_stok = db.query(semalar.Stok).filter(
        semalar.Stok.id == stok_id,
        semalar.Stok.kullanici_id == current_user.id
    ).first()
    if not db_stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    for key, value in stok.model_dump(exclude_unset=True).items():
        setattr(db_stok, key, value)
    db.commit()
    db.refresh(db_stok)
    return db_stok

@router.delete("/{stok_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stok(
    stok_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(get_current_user)
):
    db_stok = db.query(semalar.Stok).filter(
        semalar.Stok.id == stok_id,
        semalar.Stok.kullanici_id == current_user.id
    ).first()
    if not db_stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    db.delete(db_stok)
    db.commit()
    return

@router.get("/{stok_id}/anlik_miktar", response_model=modeller.AnlikStokMiktariResponse)
def get_anlik_stok_miktari_endpoint(
    stok_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(get_current_user)
):
    stok = db.query(semalar.Stok).filter(
        semalar.Stok.id == stok_id,
        semalar.Stok.kullanici_id == current_user.id
    ).first()
    if not stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    
    return {"anlik_miktar": stok.miktar}

@router.post("/{stok_id}/hareket", response_model=modeller.StokHareketRead)
def create_stok_hareket(
    stok_id: int,
    hareket: modeller.StokHareketCreate,
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(get_current_user)
):
    db_stok = db.query(semalar.Stok).filter(
        semalar.Stok.id == stok_id,
        semalar.Stok.kullanici_id == current_user.id
    ).first()
    if not db_stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı.")
    
    if hareket.miktar <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Miktar pozitif bir değer olmalıdır.")

    db.begin_nested()

    try:
        stok_degisim_net = 0.0
        if hareket.islem_tipi in [
            semalar.StokIslemTipiEnum.GİRİŞ,
            semalar.StokIslemTipiEnum.SAYIM_FAZLASI,
            semalar.StokIslemTipiEnum.SATIŞ_İADE,
            semalar.StokIslemTipiEnum.ALIŞ
        ]:
            stok_degisim_net = hareket.miktar
        elif hareket.islem_tipi in [
            semalar.StokIslemTipiEnum.ÇIKIŞ,
            semalar.StokIslemTipiEnum.SAYIM_EKSİĞİ,
            semalar.StokIslemTipiEnum.ZAYIAT,
            semalar.StokIslemTipiEnum.SATIŞ,
            semalar.StokIslemTipiEnum.ALIŞ_İADE
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
            sonraki_stok=db_stok.miktar,
            kullanici_id=current_user.id
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
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(get_current_user)
):
    query = db.query(semalar.StokHareket).filter(
        semalar.StokHareket.stok_id == stok_id,
        semalar.StokHareket.kullanici_id == current_user.id
    )

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
def delete_stok_hareket(
    hareket_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(get_current_user)
):
    db_hareket = db.query(semalar.StokHareket).filter(
        and_(
            semalar.StokHareket.id == hareket_id,
            semalar.StokHareket.kaynak == semalar.KaynakTipEnum.MANUEL,
            semalar.StokHareket.kullanici_id == current_user.id
        )
    ).first()

    if not db_hareket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Stok hareketi bulunamadı veya manuel olarak silinemez (otomatik oluşturulmuştur)."
        )
    
    stok = db.query(semalar.Stok).filter(
        semalar.Stok.id == db_hareket.stok_id,
        semalar.Stok.kullanici_id == current_user.id
    ).first()
    if stok:
        if db_hareket.islem_tipi == semalar.StokIslemTipiEnum.GİRİŞ:
            stok.miktar -= db_hareket.miktar
        elif db_hareket.islem_tipi == semalar.StokIslemTipiEnum.ÇIKIŞ:
            stok.miktar += db_hareket.miktar
        db.add(stok)
    
    db.delete(db_hareket)
    db.commit()
    return {"detail": "Stok hareketi başarıyla silindi."}

@router.post("/bulk_upsert", response_model=modeller.TopluIslemSonucResponse)
def bulk_stok_upsert_endpoint(
    stok_listesi: List[modeller.StokCreate],
    db: Session = Depends(get_db),
    current_user: modeller.Kullanici = Depends(get_current_user)
):
    db.begin_nested()
    try:
        yeni_eklenen = 0
        guncellenen = 0
        hata_veren = 0
        hatalar = []

        pozitif_kalemler = []
        negatif_kalemler = []
        
        for stok_data in stok_listesi:
            try:
                db_stok = db.query(semalar.Stok).filter(
                    semalar.Stok.kod == stok_data.kod,
                    semalar.Stok.kullanici_id == current_user.id
                ).first()
                
                if db_stok:
                    if db_stok.kullanici_id != current_user.id:
                         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu stok kaydını güncelleme yetkiniz yok.")
                    for key, value in stok_data.model_dump(exclude_unset=True).items():
                        setattr(db_stok, key, value)
                    db.add(db_stok)
                    guncellenen += 1
                else:
                    yeni_stok = semalar.Stok(**stok_data.model_dump(), kullanici_id=current_user.id)
                    db.add(yeni_stok)
                    db.flush()
                    yeni_eklenen += 1
                    
                    if yeni_stok.miktar != 0:
                        alis_fiyati_kdv_haric = yeni_stok.alis_fiyati / (1 + yeni_stok.kdv_orani / 100)
                        
                        kalem_bilgisi = {
                            "urun_id": yeni_stok.id,
                            "miktar": yeni_stok.miktar,
                            "birim_fiyat": alis_fiyati_kdv_haric,
                            "kdv_orani": yeni_stok.kdv_orani,
                            "alis_fiyati_fatura_aninda": alis_fiyati_kdv_haric
                        }
                        
                        if kalem_bilgisi["miktar"] > 0:
                            pozitif_kalemler.append(kalem_bilgisi)
                        else:
                            negatif_kalemler.append(kalem_bilgisi)

            except Exception as e:
                hata_veren += 1
                hatalar.append(f"Stok kodu '{stok_data.kod}' işlenirken hata: {e}")

        if pozitif_kalemler:
            fatura_no=f"TOPLU-ALIS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            tarih=datetime.now().strftime('%Y-%m-%d')
            
            db_fatura = semalar.Fatura(
                fatura_no=fatura_no,
                fatura_turu=semalar.FaturaTuruEnum.ALIS,
                tarih=tarih,
                cari_id=1,
                odeme_turu=semalar.OdemeTuruEnum.ETKISIZ_FATURA,
                fatura_notlari="Toplu stok ekleme işlemiyle otomatik oluşturulan alış faturası.",
                toplam_kdv_haric=sum(k['birim_fiyat'] * k['miktar'] for k in pozitif_kalemler),
                toplam_kdv_dahil=sum(k['birim_fiyat'] * (1 + k['kdv_orani'] / 100) * k['miktar'] for k in pozitif_kalemler),
                genel_toplam=sum(k['birim_fiyat'] * (1 + k['kdv_orani'] / 100) * k['miktar'] for k in pozitif_kalemler),
                kullanici_id=current_user.id
            )
            db.add(db_fatura)
            db.flush()

            for kalem_bilgisi in pozitif_kalemler:
                db_kalem = semalar.FaturaKalemi(
                    fatura_id=db_fatura.id,
                    urun_id=kalem_bilgisi['urun_id'],
                    miktar=kalem_bilgisi['miktar'],
                    birim_fiyat=kalem_bilgisi['birim_fiyat'],
                    kdv_orani=kalem_bilgisi['kdv_orani'],
                    alis_fiyati_fatura_aninda=kalem_bilgisi['alis_fiyati_fatura_aninda']
                )
                db.add(db_kalem)
                
                db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == kalem_bilgisi['urun_id']).first()
                if db_stok:
                    db_stok_hareket = semalar.StokHareket(
                        stok_id=kalem_bilgisi['urun_id'],
                        tarih=db_fatura.tarih,
                        islem_tipi=semalar.StokIslemTipiEnum.ALIŞ,
                        miktar=kalem_bilgisi['miktar'],
                        birim_fiyat=kalem_bilgisi['birim_fiyat'],
                        aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})",
                        kaynak=semalar.KaynakTipEnum.FATURA,
                        kaynak_id=db_fatura.id,
                        onceki_stok=db_stok.miktar - kalem_bilgisi['miktar'],
                        sonraki_stok=db_stok.miktar,
                        kullanici_id=current_user.id
                    )
                    db.add(db_stok_hareket)

        if negatif_kalemler:
            fatura_no=f"TOPLU-ALIS-IADE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            tarih=datetime.now().strftime('%Y-%m-%d')
            
            db_fatura_iade = semalar.Fatura(
                fatura_no=fatura_no,
                fatura_turu=semalar.FaturaTuruEnum.ALIS_IADE,
                tarih=tarih,
                cari_id=1,
                odeme_turu=semalar.OdemeTuruEnum.ETKISIZ_FATURA,
                fatura_notlari="Toplu stok ekleme işlemiyle otomatik oluşturulan alış iade faturası.",
                toplam_kdv_haric=sum(k['birim_fiyat'] * abs(k['miktar']) for k in negatif_kalemler),
                toplam_kdv_dahil=sum(k['birim_fiyat'] * (1 + k['kdv_orani'] / 100) * abs(k['miktar']) for k in negatif_kalemler),
                genel_toplam=sum(k['birim_fiyat'] * (1 + k['kdv_orani'] / 100) * abs(k['miktar']) for k in negatif_kalemler),
                kullanici_id=current_user.id
            )
            db.add(db_fatura_iade)
            db.flush()

            for kalem_bilgisi in negatif_kalemler:
                db_kalem = semalar.FaturaKalemi(
                    fatura_id=db_fatura_iade.id,
                    urun_id=kalem_bilgisi['urun_id'],
                    miktar=abs(kalem_bilgisi['miktar']),
                    birim_fiyat=kalem_bilgisi['birim_fiyat'],
                    kdv_orani=kalem_bilgisi['kdv_orani'],
                    alis_fiyati_fatura_aninda=kalem_bilgisi['alis_fiyati_fatura_aninda']
                )
                db.add(db_kalem)
                
                db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == kalem_bilgisi['urun_id']).first()
                if db_stok:
                    db_stok_hareket = semalar.StokHareket(
                        stok_id=kalem_bilgisi['urun_id'],
                        tarih=db_fatura_iade.tarih,
                        islem_tipi=semalar.StokIslemTipiEnum.ALIŞ_İADE,
                        miktar=abs(kalem_bilgisi['miktar']),
                        birim_fiyat=kalem_bilgisi['birim_fiyat'],
                        aciklama=f"{db_fatura_iade.fatura_no} nolu fatura ({db_fatura_iade.fatura_turu.value})",
                        kaynak=semalar.KaynakTipEnum.FATURA,
                        kaynak_id=db_fatura_iade.id,
                        onceki_stok=db_stok.miktar + abs(kalem_bilgisi['miktar']),
                        sonraki_stok=db_stok.miktar,
                        kullanici_id=current_user.id
                    )
                    db.add(db_stok_hareket)

        db.commit()
        
        toplam_islenen = yeni_eklenen + guncellenen + hata_veren
        
        return {
            "yeni_eklenen_sayisi": yeni_eklenen,
            "guncellenen_sayisi": guncellenen,
            "hata_sayisi": hata_veren,
            "hatalar": hatalar,
            "toplam_islenen": toplam_islenen
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Toplu stok ekleme/güncelleme sırasında kritik hata: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Toplu stok ekleme sırasında hata: {e}")