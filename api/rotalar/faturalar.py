# api/rotalar/faturalar.py dosyasının tam içeriği
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional
from datetime import date
from .. import modeller, semalar
from ..veritabani import get_db

router = APIRouter(prefix="/faturalar", tags=["Faturalar"])

@router.post("/", response_model=modeller.FaturaRead)
def create_fatura(fatura: modeller.FaturaCreate, db: Session = Depends(get_db)):
    """Yeni bir fatura oluşturur ve stok, cari, kasa/banka hareketlerini günceller."""
    # original_fatura_id'yi güvenli bir şekilde alın.
    original_fatura_id_val = getattr(fatura, 'original_fatura_id', None)

    db_fatura = semalar.Fatura(
        fatura_no=fatura.fatura_no,
        fatura_turu=fatura.fatura_turu,
        tarih=fatura.tarih,
        vade_tarihi=fatura.vade_tarihi,
        cari_id=fatura.cari_id,
        misafir_adi=fatura.misafir_adi,
        odeme_turu=fatura.odeme_turu,
        kasa_banka_id=fatura.kasa_banka_id,
        fatura_notlari=fatura.fatura_notlari,
        genel_iskonto_tipi=fatura.genel_iskonto_tipi,
        genel_iskonto_degeri=fatura.genel_iskonto_degeri,
        original_fatura_id=original_fatura_id_val
    )

    # Toplam KDV Hariç ve Toplam KDV Dahil değerlerini hesapla
    toplam_kdv_haric_temp = 0.0
    toplam_kdv_dahil_temp = 0.0
    for kalem_data in fatura.kalemler:
        birim_fiyat_kdv_haric_temp = kalem_data.birim_fiyat
        if kalem_data.kdv_orani > 0:
            birim_fiyat_kdv_dahil_temp_calc = kalem_data.birim_fiyat * (1 + kalem_data.kdv_orani / 100)
        else:
            birim_fiyat_kdv_dahil_temp_calc = kalem_data.birim_fiyat

        fiyat_iskonto_1_sonrasi_dahil = birim_fiyat_kdv_dahil_temp_calc * (1 - kalem_data.iskonto_yuzde_1 / 100)
        iskontolu_birim_fiyat_kdv_dahil = fiyat_iskonto_1_sonrasi_dahil * (1 - kalem_data.iskonto_yuzde_2 / 100)
        
        if iskontolu_birim_fiyat_kdv_dahil < 0: iskontolu_birim_fiyat_kdv_dahil = 0.0

        if kalem_data.kdv_orani > 0:
            iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil / (1 + kalem_data.kdv_orani / 100)
        else:
            iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil

        toplam_kdv_haric_temp += iskontolu_birim_fiyat_kdv_haric * kalem_data.miktar
        toplam_kdv_dahil_temp += iskontolu_birim_fiyat_kdv_dahil * kalem_data.miktar

    if fatura.genel_iskonto_tipi == "YUZDE" and fatura.genel_iskonto_degeri > 0:
        uygulanan_genel_iskonto_tutari = toplam_kdv_haric_temp * (fatura.genel_iskonto_degeri / 100)
    elif fatura.genel_iskonto_tipi == "TUTAR" and fatura.genel_iskonto_degeri > 0:
        uygulanan_genel_iskonto_tutari = fatura.genel_iskonto_degeri
    else:
        uygulanan_genel_iskonto_tutari = 0.0
    
    db_fatura.toplam_kdv_haric = toplam_kdv_haric_temp - uygulanan_genel_iskonto_tutari
    db_fatura.toplam_kdv_dahil = toplam_kdv_dahil_temp - uygulanan_genel_iskonto_tutari
    db_fatura.genel_toplam = db_fatura.toplam_kdv_dahil

    db.add(db_fatura)
    db.flush()

    try:
        for kalem_data in fatura.kalemler:
            db_kalem = semalar.FaturaKalemi(fatura_id=db_fatura.id, **kalem_data.model_dump())
            db.add(db_kalem)
            
            db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == kalem_data.urun_id).first()
            if db_stok:
                miktar_degisimi = kalem_data.miktar
                islem_tipi = None

                if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS:
                    db_stok.miktar -= miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.SATIŞ  # Düzeltildi
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS:
                    db_stok.miktar += miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.ALIŞ  # Düzeltildi
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE:
                    db_stok.miktar += miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.SATIŞ_İADE
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE:
                    db_stok.miktar -= miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.ALIŞ_İADE
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS:
                    db_stok.miktar += miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.GİRİŞ

                if islem_tipi:
                    db.add(db_stok)
                    db_stok_hareket = semalar.StokHareket(
                        stok_id=kalem_data.urun_id,
                        tarih=db_fatura.tarih,
                        islem_tipi=islem_tipi,
                        miktar=miktar_degisimi,
                        birim_fiyat=kalem_data.birim_fiyat,
                        kaynak=semalar.KaynakTipEnum.FATURA,
                        kaynak_id=db_fatura.id,
                        aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})"
                    )
                    db.add(db_stok_hareket)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fatura oluşturulurken bir hata oluştu: {e}")

    # ... (kodun geri kalanı aynı)
    # Yeni cari hareket ekle
    if db_fatura.cari_id:
        islem_yone_cari = None
        cari_turu = None

        if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS:
            islem_yone_cari = semalar.IslemYoneEnum.ALACAK
            cari_turu = semalar.CariTipiEnum.MUSTERI
        elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS:
            islem_yone_cari = semalar.IslemYoneEnum.BORC
            cari_turu = semalar.CariTipiEnum.TEDARIKCI
        elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE:
            islem_yone_cari = semalar.IslemYoneEnum.BORC
            cari_turu = semalar.CariTipiEnum.MUSTERI
        elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE:
            islem_yone_cari = semalar.IslemYoneEnum.ALACAK
            cari_turu = semalar.CariTipiEnum.TEDARIKCI
        elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS:
            islem_yone_cari = semalar.IslemYoneEnum.BORC
            cari_turu = semalar.CariTipiEnum.TEDARIKCI

        if islem_yone_cari and cari_turu:
            db_cari_hareket = semalar.CariHareket(
                cari_id=db_fatura.cari_id,
                cari_turu=cari_turu,
                tarih=db_fatura.tarih,
                islem_turu=semalar.KaynakTipEnum.FATURA.value,
                islem_yone=islem_yone_cari,
                tutar=db_fatura.genel_toplam,
                aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})",
                kaynak=semalar.KaynakTipEnum.FATURA,
                kaynak_id=db_fatura.id,
                odeme_turu=db_fatura.odeme_turu,
                kasa_banka_id=db_fatura.kasa_banka_id,
                vade_tarihi=db_fatura.vade_tarihi
            )
            db.add(db_cari_hareket)

    # Yeni kasa/banka hareket ekle (ödeme türü nakit/banka ise)
    if db_fatura.odeme_turu in [semalar.OdemeTuruEnum.NAKIT, semalar.OdemeTuruEnum.KART, semalar.OdemeTuruEnum.EFT_HAVALE, semalar.OdemeTuruEnum.CEK, semalar.OdemeTuruEnum.SENET] and db_fatura.kasa_banka_id:
        islem_yone_kasa = None
        if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS:
            islem_yone_kasa = semalar.IslemYoneEnum.GIRIS
        elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS:
            islem_yone_kasa = semalar.IslemYoneEnum.CIKIS
        elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE:
            islem_yone_kasa = semalar.IslemYoneEnum.CIKIS
        elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE:
            islem_yone_kasa = semalar.IslemYoneEnum.GIRIS
        elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS:
            islem_yone_kasa = semalar.IslemYoneEnum.GIRIS

        if islem_yone_kasa:
            db_kasa_banka_hareket = semalar.KasaBankaHareket(
                kasa_banka_id=db_fatura.kasa_banka_id,
                tarih=db_fatura.tarih,
                islem_turu=db_fatura.fatura_turu.value,
                islem_yone=islem_yone_kasa,
                tutar=db_fatura.genel_toplam,
                aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})",
                kaynak=semalar.KaynakTipEnum.FATURA,
                kaynak_id=db_fatura.id
            )
            db.add(db_kasa_banka_hareket)
            
            db_kasa_banka = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == db_fatura.kasa_banka_id).first()
            if db_kasa_banka:
                if islem_yone_kasa == semalar.IslemYoneEnum.GIRIS:
                    db_kasa_banka.bakiye += db_fatura.genel_toplam
                else:
                    db_kasa_banka.bakiye -= db_fatura.genel_toplam
                db.add(db_kasa_banka)

    db.commit()
    db.refresh(db_fatura)
    return db_fatura
    
@router.get("/", response_model=modeller.FaturaListResponse)
def read_faturalar(
    skip: int = 0,
    limit: int = 100,
    arama: str = Query(None, min_length=1, max_length=50),
    fatura_turu: Optional[semalar.FaturaTuruEnum] = Query(None),
    baslangic_tarihi: date = Query(None),
    bitis_tarihi: date = Query(None),
    cari_id: int = Query(None),
    odeme_turu: Optional[semalar.OdemeTuruEnum] = Query(None),
    kasa_banka_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Fatura).join(semalar.Musteri, semalar.Fatura.cari_id == semalar.Musteri.id, isouter=True) \
                                   .join(semalar.Tedarikci, semalar.Fatura.cari_id == semalar.Tedarikci.id, isouter=True)

    if arama:
        query = query.filter(
            (semalar.Fatura.fatura_no.ilike(f"%{arama}%")) |
            (semalar.Musteri.ad.ilike(f"%{arama}%")) |
            (semalar.Tedarikci.ad.ilike(f"%{arama}%")) |
            (semalar.Fatura.misafir_adi.ilike(f"%{arama}%"))
        )
    
    if fatura_turu:
        query = query.filter(semalar.Fatura.fatura_turu == fatura_turu)
    
    if baslangic_tarihi:
        query = query.filter(semalar.Fatura.tarih >= baslangic_tarihi)
    
    if bitis_tarihi:
        query = query.filter(semalar.Fatura.tarih <= bitis_tarihi)
    
    if cari_id:
        query = query.filter(semalar.Fatura.cari_id == cari_id)

    if odeme_turu:
        query = query.filter(semalar.Fatura.odeme_turu == odeme_turu)
        
    if kasa_banka_id:
        query = query.filter(semalar.Fatura.kasa_banka_id == kasa_banka_id)

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
    
    db.begin_nested() # Transaction başlat

    try: # Bu 'try' bloğu metodun 4 boşluk içine girintili olmalı
        # Eski fatura kalemlerini al
        old_kalemler = db.query(semalar.FaturaKalemi).filter(semalar.FaturaKalemi.fatura_id == fatura_id).all()

        # Eski stok hareketlerini ve cari/kasa hareketlerini geri al
        for old_kalem in old_kalemler:
            # Stok hareketini geri al
            stok = db.query(semalar.Stok).filter(semalar.Stok.id == old_kalem.urun_id).first()
            if stok:
                # İlgili fatura kaleminin türüne göre stoku geri al
                if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS: # ENUM kullanıldı
                    stok.miktar += old_kalem.miktar # Satış, stoktan düşmüştü, şimdi geri ekle
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS: # ENUM kullanıldı
                    stok.miktar -= old_kalem.miktar # Alış, stoka eklemişti, şimdi geri çıkar
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE: # ENUM kullanıldı
                    stok.miktar -= old_kalem.miktar # Satış iadesi, stoku artırmıştı, şimdi geri azalt
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE: # ENUM kullanıldı
                    stok.miktar += old_kalem.miktar # Alış iadesi, stoku azaltmıştı, şimdi geri artır
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS: # ENUM kullanıldı
                    stok.miktar -= old_kalem.miktar # Devir girişi, stoku artırmıştı, şimdi geri azalt
                db.add(stok)

            # Eski stok hareketlerini sil (kaynak_id'si bu fatura olanları)
            db.query(semalar.StokHareket).filter(
                and_(
                    semalar.StokHareket.kaynak == semalar.KaynakTipEnum.FATURA, # ENUM kullanıldı
                    semalar.StokHareket.kaynak_id == fatura_id,
                    semalar.StokHareket.stok_id == old_kalem.urun_id # Sadece ilgili ürünün hareketini sil
                )
            ).delete(synchronize_session=False)

        # Eski cari hareketlerini geri al
        old_cari_hareketler = db.query(semalar.CariHareket).filter(
            and_(
                semalar.CariHareket.kaynak == semalar.KaynakTipEnum.FATURA, # ENUM kullanıldı
                semalar.CariHareket.kaynak_id == fatura_id
            )
        ).all()
        for old_cari_hareket in old_cari_hareketler:
            db.delete(old_cari_hareket)

        # Eski kasa/banka hareketlerini geri al
        old_kasa_banka_hareketler = db.query(semalar.KasaBankaHareket).filter(
            and_(
                semalar.KasaBankaHareket.kaynak == semalar.KaynakTipEnum.FATURA, # ENUM kullanıldı
                semalar.KasaBankaHareket.kaynak_id == fatura_id
            )
        ).all()
        for old_kasa_banka_hareket in old_kasa_banka_hareketler:
            kasa_banka = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == old_kasa_banka_hareket.kasa_banka_id).first()
            if kasa_banka:
                if old_kasa_banka_hareket.islem_yone == semalar.IslemYoneEnum.GIRIS: # ENUM kullanıldı
                    kasa_banka.bakiye -= old_kasa_banka_hareket.tutar
                elif old_kasa_banka_hareket.islem_yone == semalar.IslemYoneEnum.CIKIS: # ENUM kullanıldı
                    kasa_banka.bakiye += old_kasa_banka_hareket.tutar
                db.add(kasa_banka)
            db.delete(old_kasa_banka_hareket)

        # Eski fatura kalemlerini sil
        db.query(semalar.FaturaKalemi).filter(semalar.FaturaKalemi.fatura_id == fatura_id).delete(synchronize_session=False)

        # Yeni fatura bilgilerini güncelle
        update_data = fatura.model_dump(exclude_unset=True, exclude={"kalemler"})
        for key, value in update_data.items():
            setattr(db_fatura, key, value)
        
        # Yeni toplamları hesapla ve güncelle
        new_toplam_kdv_haric_temp = 0.0
        new_toplam_kdv_dahil_temp = 0.0
        for kalem_data in fatura.kalemler or []: # fatura.kalemler boş olabilir
            # İskontolu birim fiyatı KDV hariç ve dahil hesapla
            birim_fiyat_kdv_haric_temp = kalem_data.birim_fiyat
            if kalem_data.kdv_orani > 0:
                birim_fiyat_kdv_dahil_temp_calc = kalem_data.birim_fiyat * (1 + kalem_data.kdv_orani / 100)
            else:
                birim_fiyat_kdv_dahil_temp_calc = kalem_data.birim_fiyat

            fiyat_iskonto_1_sonrasi_dahil = birim_fiyat_kdv_dahil_temp_calc * (1 - kalem_data.iskonto_yuzde_1 / 100)
            iskontolu_birim_fiyat_kdv_dahil = fiyat_iskonto_1_sonrasi_dahil * (1 - kalem_data.iskonto_yuzde_2 / 100)
            
            if iskontolu_birim_fiyat_kdv_dahil < 0: iskontolu_birim_fiyat_kdv_dahil = 0.0

            if kalem_data.kdv_orani > 0:
                iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil / (1 + kalem_data.kdv_orani / 100)
            else:
                iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil

            new_toplam_kdv_haric_temp += iskontolu_birim_fiyat_kdv_haric * kalem_data.miktar
            new_toplam_kdv_dahil_temp += iskontolu_birim_fiyat_kdv_dahil * kalem_data.miktar

        # Yeni genel iskontoyu uygula
        if db_fatura.genel_iskonto_tipi == "YUZDE" and db_fatura.genel_iskonto_degeri > 0:
            uygulanan_genel_iskonto_tutari_yeni = new_toplam_kdv_haric_temp * (db_fatura.genel_iskonto_degeri / 100)
        elif db_fatura.genel_iskonto_tipi == "TUTAR" and db_fatura.genel_iskonto_degeri > 0:
            uygulanan_genel_iskonto_tutari_yeni = db_fatura.genel_iskonto_degeri
        else:
            uygulanan_genel_iskonto_tutari_yeni = 0.0
        
        db_fatura.toplam_kdv_haric = new_toplam_kdv_haric_temp - uygulanan_genel_iskonto_tutari_yeni
        db_fatura.toplam_kdv_dahil = new_toplam_kdv_dahil_temp - uygulanan_genel_iskonto_tutari_yeni
        db_fatura.genel_toplam = db_fatura.toplam_kdv_dahil # Genel toplamı güncelle

        db.add(db_fatura) # Güncellenen faturayı ekle

        # Yeni fatura kalemlerini ekle
        for kalem_data in fatura.kalemler or []: # fatura.kalemler boş olabilir
            db_kalem = semalar.FaturaKalemi(fatura_id=db_fatura.id, **kalem_data.model_dump())
            db.add(db_kalem)

            # Stok miktarını tekrar güncelle (yeni kalemlere göre)
            db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == kalem_data.urun_id).first()
            if db_stok:
                miktar_degisimi = kalem_data.miktar
                islem_tipi = None

                if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS: # ENUM kullanıldı
                    db_stok.miktar -= miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.FATURA_SATIS
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS: # ENUM kullanıldı
                    db_stok.miktar += miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.FATURA_ALIS
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE: # ENUM kullanıldı
                    db_stok.miktar += miktar_degisimi # Satış iadesi stoğu artırır
                    islem_tipi = semalar.StokIslemTipiEnum.IADE_GIRIS
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE: # ENUM kullanıldı
                    db_stok.miktar -= miktar_degisimi # Alış iadesi stoğu azaltır
                    islem_tipi = semalar.StokIslemTipiEnum.CIKIS_MANUEL_DUZELTME # veya yeni bir enum
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS: # ENUM kullanıldı
                    db_stok.miktar += miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.GIRIS_MANUEL_DUZELTME # veya yeni bir enum

                if islem_tipi:
                    db.add(db_stok)

                    # Stok Hareketi Ekle
                    db_stok_hareket = semalar.StokHareket(
                        stok_id=kalem_data.urun_id,
                        tarih=db_fatura.tarih,
                        islem_tipi=islem_tipi,
                        miktar=miktar_degisimi,
                        birim_fiyat=kalem_data.birim_fiyat,
                        kaynak=semalar.KaynakTipEnum.FATURA, # ENUM kullanıldı
                        kaynak_id=db_fatura.id,
                        aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})" # ENUM değeri kullanıldı
                    )
                    db.add(db_stok_hareket)

        # Yeni cari hareket ekle
        if db_fatura.cari_id:
            islem_yone_cari = None
            cari_turu = None

            if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS: # ENUM kullanıldı
                islem_yone_cari = semalar.IslemYoneEnum.ALACAK
                cari_turu = semalar.CariTipiEnum.MUSTERI
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS: # ENUM kullanıldı
                islem_yone_cari = semalar.IslemYoneEnum.BORC
                cari_turu = semalar.CariTipiEnum.TEDARIKCI
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE: # ENUM kullanıldı
                islem_yone_cari = semalar.IslemYoneEnum.BORC
                cari_turu = semalar.CariTipiEnum.MUSTERI
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE: # ENUM kullanıldı
                islem_yone_cari = semalar.IslemYoneEnum.ALACAK
                cari_turu = semalar.CariTipiEnum.TEDARIKCI
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS: # ENUM kullanıldı
                islem_yone_cari = semalar.IslemYoneEnum.BORC
                cari_turu = semalar.CariTipiEnum.TEDARIKCI

            if islem_yone_cari and cari_turu:
                db_cari_hareket = semalar.CariHareket(
                    cari_id=db_fatura.cari_id,
                    cari_turu=cari_turu,
                    tarih=db_fatura.tarih,
                    islem_turu=semalar.KaynakTipEnum.FATURA.value, # ENUM değeri kullanıldı
                    islem_yone=islem_yone_cari,
                    tutar=db_fatura.genel_toplam,
                    aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})", # ENUM değeri kullanıldı
                    kaynak=semalar.KaynakTipEnum.FATURA, # ENUM kullanıldı
                    kaynak_id=db_fatura.id,
                    odeme_turu=db_fatura.odeme_turu,
                    kasa_banka_id=db_fatura.kasa_banka_id,
                    vade_tarihi=db_fatura.vade_tarihi
                )
                db.add(db_cari_hareket)

        # Yeni kasa/banka hareket ekle (ödeme türü nakit/banka ise)
        if db_fatura.odeme_turu in [semalar.OdemeTuruEnum.NAKIT, semalar.OdemeTuruEnum.KART, semalar.OdemeTuruEnum.EFT_HAVALE, semalar.OdemeTuruEnum.CEK, semalar.OdemeTuruEnum.SENET] and db_fatura.kasa_banka_id: # ENUM kullanıldı
            islem_yone_kasa = None
            if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS: # ENUM kullanıldı
                islem_yone_kasa = semalar.IslemYoneEnum.GIRIS
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS: # ENUM kullanıldı
                islem_yone_kasa = semalar.IslemYoneEnum.CIKIS
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE: # ENUM kullanıldı
                islem_yone_kasa = semalar.IslemYoneEnum.CIKIS
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE: # ENUM kullanıldı
                islem_yone_kasa = semalar.IslemYoneEnum.GIRIS
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS: # ENUM kullanıldı
                islem_yone_kasa = semalar.IslemYoneEnum.GIRIS

            if islem_yone_kasa:
                db_kasa_banka_hareket = semalar.KasaBankaHareket(
                    kasa_banka_id=db_fatura.kasa_banka_id,
                    tarih=db_fatura.tarih,
                    islem_turu=db_fatura.fatura_turu.value, # ENUM değeri kullanıldı
                    islem_yone=islem_yone_kasa,
                    tutar=db_fatura.genel_toplam,
                    aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})", # ENUM değeri kullanıldı
                    kaynak=semalar.KaynakTipEnum.FATURA, # ENUM kullanıldı
                    kaynak_id=db_fatura.id
                )
                db.add(db_kasa_banka_hareket)
                
                # Kasa/Banka bakiyesini güncelle
                db_kasa_banka = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == db_fatura.kasa_banka_id).first()
                if db_kasa_banka:
                    if islem_yone_kasa == semalar.IslemYoneEnum.GIRIS:
                        db_kasa_banka.bakiye += db_fatura.genel_toplam
                    else: # ÇIKIŞ
                        db_kasa_banka.bakiye -= db_fatura.genel_toplam
                    db.add(db_kasa_banka)

        db.commit() # Tüm yeni işlemleri onayla
        db.refresh(db_fatura)
        return db_fatura
    except Exception as e:  
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Fatura güncellenirken bir hata oluştu")
    
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
                semalar.StokHareket.kaynak == semalar.KaynakTipEnum.FATURA,
                semalar.StokHareket.kaynak_id == fatura_id
            )
        ).all()
        for hareket in stok_hareketleri:
            stok = db.query(semalar.Stok).filter(semalar.Stok.id == hareket.stok_id).first()
            if stok:
                # Hareketin tipi, orijinal faturanın tipine göre tersine çevrilmeli
                if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIŞ:
                    stok.miktar += hareket.miktar # Satıştı, geri ekle
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS:
                    stok.miktar -= hareket.miktar # Alıştı, geri çıkar
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE:
                    stok.miktar -= hareket.miktar # Satış iadesiydi, geri çıkar
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE:
                    stok.miktar += hareket.miktar # Alış iadesiydi, geri ekle
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS:
                    stok.miktar -= hareket.miktar # Devir girişiydi, geri çıkar

                db.add(stok)
            db.delete(hareket)

        # Cari hareketlerini geri al ve sil
        cari_hareketleri = db.query(semalar.CariHareket).filter(
            and_(
                semalar.CariHareket.kaynak == semalar.KaynakTipEnum.FATURA,
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
                semalar.KasaBankaHareket.kaynak == semalar.KaynakTipEnum.FATURA,
                semalar.KasaBankaHareket.kaynak_id == fatura_id
            )
        ).all()
        for hareket in kasa_banka_hareketleri:
            # Kasa/Banka bakiyesini geri al
            kasa_banka = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == hareket.kasa_banka_id).first()
            if kasa_banka:
                # İşlem yönüne göre bakiyeyi tersine çevir
                if hareket.islem_yone == semalar.IslemYoneEnum.GIRIS:
                    kasa_banka.bakiye -= hareket.tutar
                elif hareket.islem_yone == semalar.IslemYoneEnum.CIKIS:
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