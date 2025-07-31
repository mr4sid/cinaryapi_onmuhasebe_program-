from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_
from typing import List, Optional
from datetime import datetime # datetime objesi için eklendi
from .. import modeller, semalar
from ..veritabani import get_db

router = APIRouter(prefix="/siparisler", tags=["Siparişler"])

@router.post("/", response_model=modeller.SiparisRead)
def create_siparis(siparis: modeller.SiparisCreate, db: Session = Depends(get_db)):
    db_siparis = semalar.Siparis(
        siparis_no=siparis.siparis_no,
        siparis_turu=siparis.siparis_turu,
        durum=siparis.durum,
        tarih=siparis.tarih,
        teslimat_tarihi=siparis.teslimat_tarihi,
        cari_id=siparis.cari_id,
        cari_tip=siparis.cari_tip,
        siparis_notlari=siparis.siparis_notlari,
        genel_iskonto_tipi=siparis.genel_iskonto_tipi,
        genel_iskonto_degeri=siparis.genel_iskonto_degeri,
        fatura_id=siparis.fatura_id # Fatura ID eklendi (eğer varsa)
    )

    # Toplam tutar kalemlerden hesaplanacak (API tarafında veya DB trigger ile)
    # Burada direkt Pydantic modelinden alınan toplam_tutar kullanılabilir eğer client hesaplayıp gönderiyorsa
    # Aksi takdirde, kalemler eklendikten sonra hesaplanıp güncellenmelidir.
    # Şimdilik varsayılan olarak 0.0 veya API tarafından otomatik hesaplandığı varsayılıyor.

    db.add(db_siparis)
    db.flush() # Sipariş ID'sini almak için

    # Sipariş Kalemlerini Ekle
    for kalem_data in siparis.kalemler:
        db_kalem = semalar.SiparisKalemi(siparis_id=db_siparis.id, **kalem_data.model_dump())
        db.add(db_kalem)

        # Stok Miktarını Güncelle (SATIŞ_SIPARIS ise çıkış, ALIS_SIPARIS ise giriş)
        db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == kalem_data.urun_id).first()
        if db_stok:
            miktar_degisimi = kalem_data.miktar
            islem_tipi_stok = None

            if db_siparis.siparis_turu == semalar.SiparisTuruEnum.SATIS_SIPARIS:
                islem_tipi_stok = semalar.StokIslemTipiEnum.FATURA_SATIŞ # Sipariş faturaya dönüşürken stok değişimi olur
            elif db_siparis.siparis_turu == semalar.SiparisTuruEnum.ALIS_SIPARIS:
                islem_tipi_stok = semalar.StokIslemTipiEnum.FATURA_ALIS # Sipariş faturaya dönüşürken stok değişimi olur
            
            # Stok hareketleri sipariş oluşturulduğunda değil, sipariş faturaya dönüştürüldüğünde oluşur.
            # Bu nedenle, bu kısım sipariş oluşturma anında stok değişimi YAPMAMALI.
            # Stok değişimi ve hareketi siparişin faturaya dönüştürüldüğü yerde yönetilmelidir.
            # Bu yorum bloğu sadece örnek olarak bırakılmıştır.

            # if islem_tipi_stok:
            #     # Stok hareket kaydı oluşturulabilir, ancak miktar değişimi olmamalı
            #     db_stok_hareket = semalar.StokHareket(
            #         stok_id=kalem_data.urun_id,
            #         tarih=db_siparis.tarih,
            #         islem_tipi=islem_tipi_stok,
            #         miktar=miktar_degisimi,
            #         birim_fiyat=kalem_data.birim_fiyat,
            #         kaynak=semalar.KaynakTipEnum.SIPARIS,
            #         kaynak_id=db_siparis.id,
            #         aciklama=f"{db_siparis.siparis_no} nolu sipariş ({db_siparis.siparis_turu.value})"
            #     )
            #     db.add(db_stok_hareket)

    db.commit() # Tüm değişiklikleri kaydet
    db.refresh(db_siparis)
    return db_siparis

@router.get("/", response_model=modeller.SiparisListResponse)
def read_siparisler(
    skip: int = 0,
    limit: int = 20,
    arama_terimi: str = Query(None),
    cari_id_filter: Optional[int] = None,
    durum_filter: Optional[semalar.SiparisDurumEnum] = None,
    siparis_tipi_filter: Optional[semalar.SiparisTuruEnum] = None,
    baslangic_tarih: Optional[str] = None,
    bitis_tarih: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Siparis) \
        .options(joinedload(semalar.Siparis.musteri_siparis)) \
        .options(joinedload(semalar.Siparis.tedarikci_siparis)) \
        .options(joinedload(semalar.Siparis.kalemler).joinedload(semalar.SiparisKalemi.urun))

    if arama_terimi:
        query = query.filter(
            (semalar.Siparis.siparis_no.ilike(f"%{arama_terimi}%")) |
            (semalar.Siparis.siparis_notlari.ilike(f"%{arama_terimi}%")) |
            (semalar.Siparis.musteri_siparis.has(semalar.Musteri.ad.ilike(f"%{arama_terimi}%"))) |
            (semalar.Siparis.tedarikci_siparis.has(semalar.Tedarikci.ad.ilike(f"%{arama_terimi}%"))) |
            (semalar.Siparis.kalemler.any(semalar.SiparisKalemi.urun.has(semalar.Stok.ad.ilike(f"%{arama_terimi}%"))))
        )
    
    if cari_id_filter is not None:
        query = query.filter(semalar.Siparis.cari_id == cari_id_filter)

    if durum_filter is not None:
        query = query.filter(semalar.Siparis.durum == durum_filter)

    if siparis_tipi_filter is not None:
        query = query.filter(semalar.Siparis.siparis_turu == siparis_tipi_filter)

    if baslangic_tarih:
        query = query.filter(semalar.Siparis.tarih >= baslangic_tarih)
    
    if bitis_tarih:
        query = query.filter(semalar.Siparis.tarih <= bitis_tarih)

    # DISTINCT ON hatasını düzeltmek için ORDER BY'a siparisler.id eklendi
    total_count = query.distinct(semalar.Siparis.id).order_by(semalar.Siparis.id, semalar.Siparis.tarih.desc()).count() # <-- BURASI GÜNCELLENDİ (count'tan önce distinct)
    siparisler = query.distinct(semalar.Siparis.id).order_by(semalar.Siparis.id, semalar.Siparis.tarih.desc()).offset(skip).limit(limit).all() # <-- BURASI GÜNCELLENDİ

    siparis_read_models = [
        modeller.SiparisRead.model_validate(siparis, from_attributes=True)
        for siparis in siparisler
    ]
    return {"items": siparis_read_models, "total": total_count}

@router.get("/{siparis_id}", response_model=modeller.SiparisRead)
def read_siparis(siparis_id: int, db: Session = Depends(get_db)):
    siparis = db.query(semalar.Siparis) \
        .options(joinedload(semalar.Siparis.musteri_siparis)) \
        .options(joinedload(semalar.Siparis.tedarikci_siparis)) \
        .options(joinedload(semalar.Siparis.kalemler).joinedload(semalar.SiparisKalemi.urun)) \
        .filter(semalar.Siparis.id == siparis_id).first()
    if not siparis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş bulunamadı")
    return modeller.SiparisRead.model_validate(siparis, from_attributes=True)

@router.put("/{siparis_id}", response_model=modeller.SiparisRead)
def update_siparis(siparis_id: int, siparis_update: modeller.SiparisUpdate, db: Session = Depends(get_db)):
    db_siparis = db.query(semalar.Siparis).filter(semalar.Siparis.id == siparis_id).first()
    if not db_siparis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş bulunamadı")
    
    db.begin_nested() # Transaction başlat

    try:
        # Eski sipariş kalemlerini al
        old_kalemler = db.query(semalar.SiparisKalemi).filter(semalar.SiparisKalemi.siparis_id == siparis_id).all()

        # Eski sipariş kalemlerini sil
        db.query(semalar.SiparisKalemi).filter(semalar.SiparisKalemi.siparis_id == siparis_id).delete(synchronize_session=False)

        # Sipariş ana bilgilerini güncelle
        update_data = siparis_update.model_dump(exclude_unset=True, exclude={"kalemler"})
        for key, value in update_data.items():
            setattr(db_siparis, key, value)
        db.add(db_siparis)

        # Yeni sipariş kalemlerini ekle
        for kalem_data in siparis_update.kalemler or []:
            db_kalem = semalar.SiparisKalemi(siparis_id=db_siparis.id, **kalem_data.model_dump())
            db.add(db_kalem)
        
        db.commit()
        db.refresh(db_siparis)
        return modeller.SiparisRead.model_validate(db_siparis, from_attributes=True)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Sipariş güncellenirken bir hata oluştu: {e}")

@router.delete("/{siparis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_siparis(siparis_id: int, db: Session = Depends(get_db)):
    db_siparis = db.query(semalar.Siparis).filter(semalar.Siparis.id == siparis_id).first()
    if not db_siparis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş bulunamadı")
    
    # Siparişe bağlı kalemleri sil
    db.query(semalar.SiparisKalemi).filter(semalar.SiparisKalemi.siparis_id == siparis_id).delete(synchronize_session=False)

    db.delete(db_siparis)
    db.commit()
    return

@router.post("/{siparis_id}/faturaya_donustur", response_model=modeller.FaturaRead)
def convert_siparis_to_fatura(
    siparis_id: int, 
    fatura_donusum: modeller.SiparisFaturaDonusum, # Yeni Pydantic modeli
    db: Session = Depends(get_db)
):
    db_siparis = db.query(semalar.Siparis).filter(semalar.Siparis.id == siparis_id).first()
    if not db_siparis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş bulunamadı.")
    
    if db_siparis.durum == semalar.SiparisDurumEnum.FATURALASTIRILDI:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sipariş zaten faturalaştırılmış.")
    
    if not db_siparis.kalemler:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Siparişin kalemi bulunmuyor, faturaya dönüştürülemez.")

    # Sipariş tipi Satış ise Satış Faturası, Alış ise Alış Faturası oluştur
    fatura_turu_olustur = semalar.FaturaTuruEnum.SATIS if db_siparis.siparis_turu == semalar.SiparisTuruEnum.SATIS_SIPARIS else semalar.FaturaTuruEnum.ALIS

    # Yeni bir fatura numarası al
    # Bu kısmı API içinde bir utility fonksiyonu olarak tutmak daha iyi olabilir.
    last_fatura = db.query(semalar.Fatura).filter(semalar.Fatura.fatura_turu == fatura_turu_olustur) \
                                       .order_by(semalar.Fatura.fatura_no.desc()).first()
    
    prefix = "SF" if fatura_turu_olustur == semalar.FaturaTuruEnum.SATIS else "AF"
    next_sequence = 1
    if last_fatura and last_fatura.fatura_no.startswith(prefix):
        try:
            current_sequence_str = last_fatura.fatura_no[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            pass # Eğer numara formatı bozuksa, baştan başla
    
    new_fatura_no = f"{prefix}{next_sequence:09d}"

    # Faturayı oluştur
    db_fatura = semalar.Fatura(
        fatura_no=new_fatura_no,
        fatura_turu=fatura_turu_olustur,
        tarih=datetime.now().date(), # Fatura tarihi bugün
        vade_tarihi=fatura_donusum.vade_tarihi,
        cari_id=db_siparis.cari_id,
        odeme_turu=fatura_donusum.odeme_turu,
        kasa_banka_id=fatura_donusum.kasa_banka_id,
        fatura_notlari=f"Sipariş No: {db_siparis.siparis_no} üzerinden oluşturuldu.",
        genel_iskonto_tipi=db_siparis.genel_iskonto_tipi, # Siparişten gelen genel iskonto
        genel_iskonto_degeri=db_siparis.genel_iskonto_degeri # Siparişten gelen genel iskonto değeri
    )
    db.add(db_fatura)
    db.flush() # Fatura ID'sini almak için

    toplam_kdv_haric_temp = 0.0
    toplam_kdv_dahil_temp = 0.0

    # Sipariş kalemlerini fatura kalemlerine kopyala
    for siparis_kalem in db_siparis.kalemler:
        # Stoktan ürünün güncel alış/satış fiyatını ve KDV oranını al
        urun_info = db.query(semalar.Stok).filter(semalar.Stok.id == siparis_kalem.urun_id).first()
        if not urun_info:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ürün ID {siparis_kalem.urun_id} bulunamadı.")
        
        # Fatura anındaki alış fiyatı
        alis_fiyati_fatura_aninda = urun_info.alis_fiyati

        # İskontolu birim fiyatı KDV hariç ve dahil hesapla
        birim_fiyat_kdv_haric_calc = siparis_kalem.birim_fiyat
        birim_fiyat_kdv_dahil_calc = siparis_kalem.birim_fiyat * (1 + siparis_kalem.kdv_orani / 100)

        fiyat_iskonto_1_sonrasi_dahil = birim_fiyat_kdv_dahil_calc * (1 - siparis_kalem.iskonto_yuzde_1 / 100)
        iskontolu_birim_fiyat_kdv_dahil = fiyat_iskonto_1_sonrasi_dahil * (1 - siparis_kalem.iskonto_yuzde_2 / 100)
        
        if iskontolu_birim_fiyat_kdv_dahil < 0: iskontolu_birim_fiyat_kdv_dahil = 0.0

        iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil / (1 + siparis_kalem.kdv_orani / 100) if siparis_kalem.kdv_orani != 0 else iskontolu_birim_fiyat_kdv_dahil

        # Kalem toplamlarını hesapla
        kalem_toplam_kdv_haric = iskontolu_birim_fiyat_kdv_haric * siparis_kalem.miktar
        kalem_toplam_kdv_dahil = iskontolu_birim_fiyat_kdv_dahil * siparis_kalem.miktar
        kdv_tutari = kalem_toplam_kdv_dahil - kalem_toplam_kdv_haric

        db_fatura_kalem = semalar.FaturaKalemi(
            fatura_id=db_fatura.id,
            urun_id=siparis_kalem.urun_id,
            miktar=siparis_kalem.miktar,
            birim_fiyat=birim_fiyat_kdv_haric_calc, # KDV hariç birim fiyat
            kdv_orani=siparis_kalem.kdv_orani,
            alis_fiyati_fatura_aninda=alis_fiyati_fatura_aninda,
            iskonto_yuzde_1=siparis_kalem.iskonto_yuzde_1,
            iskonto_yuzde_2=siparis_kalem.iskonto_yuzde_2,
            iskonto_tipi=siparis_kalem.iskonto_tipi,
            iskonto_degeri=siparis_kalem.iskonto_degeri,
            # Bu alanlar Pydantic modelde yoktu, eklenmeli veya hesaplanmalı
            # kalem_toplam_kdv_haric=kalem_toplam_kdv_haric,
            # kalem_toplam_kdv_dahil=kalem_toplam_kdv_dahil,
            # kdv_tutari=kdv_tutari
        )
        db.add(db_fatura_kalem)

        toplam_kdv_haric_temp += kalem_toplam_kdv_haric
        toplam_kdv_dahil_temp += kalem_toplam_kdv_dahil

        # Stok Miktarını Güncelle ve Stok Hareketi Ekle
        if fatura_turu_olustur == semalar.FaturaTuruEnum.SATIS:
            urun_info.miktar -= siparis_kalem.miktar # Satış, stoktan düşer
            islem_tipi_stok = semalar.StokIslemTipiEnum.FATURA_SATIŞ
        elif fatura_turu_olustur == semalar.FaturaTuruEnum.ALIS:
            urun_info.miktar += siparis_kalem.miktar # Alış, stoka ekler
            islem_tipi_stok = semalar.StokIslemTipiEnum.FATURA_ALIS
        else:
            islem_tipi_stok = None # Diğer tipler için stok hareketi yok (veya farklı bir enum)

        if islem_tipi_stok:
            db.add(urun_info) # Güncellenen stoğu kaydet

            db_stok_hareket = semalar.StokHareket(
                stok_id=siparis_kalem.urun_id,
                tarih=db_fatura.tarih,
                islem_tipi=islem_tipi_stok,
                miktar=siparis_kalem.miktar,
                birim_fiyat=siparis_kalem.birim_fiyat, # Sipariş kalemindeki birim fiyatı kullan
                kaynak=semalar.KaynakTipEnum.FATURA,
                kaynak_id=db_fatura.id,
                aciklama=f"{db_fatura.fatura_no} nolu fatura ({fatura_turu_olustur.value})",
                onceki_stok=urun_info.miktar - siparis_kalem.miktar if fatura_turu_olustur == semalar.FaturaTuruEnum.SATIS else urun_info.miktar + siparis_kalem.miktar, # Geri almadan önceki miktar
                sonraki_stok=urun_info.miktar # Güncel miktar
            )
            db.add(db_stok_hareket)

    # Genel iskontoyu uygula ve fatura toplamlarını güncelle
    if db_fatura.genel_iskonto_tipi == semalar.modeller.GenelIskontoTipiEnum.YUZDE and db_fatura.genel_iskonto_degeri > 0:
        uygulanan_genel_iskonto_tutari = toplam_kdv_haric_temp * (db_fatura.genel_iskonto_degeri / 100)
    elif db_fatura.genel_iskonto_tipi == semalar.modeller.GenelIskontoTipiEnum.TUTAR and db_fatura.genel_iskonto_degeri > 0:
        uygulanan_genel_iskonto_tutari = db_fatura.genel_iskonto_degeri
    else:
        uygulanan_genel_iskonto_tutari = 0.0
    
    db_fatura.toplam_kdv_haric = toplam_kdv_haric_temp - uygulanan_genel_iskonto_tutari
    db_fatura.toplam_kdv_dahil = toplam_kdv_dahil_temp - uygulanan_genel_iskonto_tutari
    db_fatura.genel_toplam = db_fatura.toplam_kdv_dahil

    db.add(db_fatura) # Güncellenen faturayı kaydet

    # Cari Hareket Oluştur
    if db_fatura.cari_id:
        islem_yone_cari = None
        cari_turu = db_siparis.cari_tip # Siparişten gelen cari tipi kullan

        if fatura_turu_olustur == semalar.FaturaTuruEnum.SATIS:
            islem_yone_cari = semalar.IslemYoneEnum.ALACAK # Satış faturası alacak
        elif fatura_turu_olustur == semalar.FaturaTuruEnum.ALIS:
            islem_yone_cari = semalar.IslemYoneEnum.BORC # Alış faturası borç

        if islem_yone_cari:
            db_cari_hareket = semalar.CariHareket(
                cari_id=db_fatura.cari_id,
                cari_turu=cari_turu,
                tarih=db_fatura.tarih,
                islem_turu=semalar.KaynakTipEnum.FATURA.value,
                islem_yone=islem_yone_cari,
                tutar=db_fatura.genel_toplam,
                aciklama=f"{db_fatura.fatura_no} nolu fatura ({fatura_turu_olustur.value})",
                kaynak=semalar.KaynakTipEnum.FATURA,
                kaynak_id=db_fatura.id,
                odeme_turu=db_fatura.odeme_turu,
                kasa_banka_id=db_fatura.kasa_banka_id,
                vade_tarihi=db_fatura.vade_tarihi
            )
            db.add(db_cari_hareket)

    # Kasa/Banka Hareketi Oluştur (ödeme türü nakit/banka ise)
    if fatura_donusum.odeme_turu in [semalar.OdemeTuruEnum.NAKIT, semalar.OdemeTuruEnum.KART, semalar.OdemeTuruEnum.EFT_HAVALE, semalar.OdemeTuruEnum.CEK, semalar.OdemeTuruEnum.SENET] and fatura_donusum.kasa_banka_id:
        islem_yone_kasa = None
        if fatura_turu_olustur == semalar.FaturaTuruEnum.SATIS:
            islem_yone_kasa = semalar.IslemYoneEnum.GIRIS
        elif fatura_turu_olustur == semalar.FaturaTuruEnum.ALIS:
            islem_yone_kasa = semalar.IslemYoneEnum.CIKIS

        if islem_yone_kasa:
            db_kasa_banka_hareket = semalar.KasaBankaHareket(
                kasa_banka_id=fatura_donusum.kasa_banka_id,
                tarih=db_fatura.tarih,
                islem_turu=fatura_turu_olustur.value,
                islem_yone=islem_yone_kasa,
                tutar=db_fatura.genel_toplam,
                aciklama=f"{db_fatura.fatura_no} nolu fatura ({fatura_turu_olustur.value})",
                kaynak=semalar.KaynakTipEnum.FATURA,
                kaynak_id=db_fatura.id
            )
            db.add(db_kasa_banka_hareket)
            
            # Kasa/Banka bakiyesini güncelle
            db_kasa_banka = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == fatura_donusum.kasa_banka_id).first()
            if db_kasa_banka:
                if islem_yone_kasa == semalar.IslemYoneEnum.GIRIS:
                    db_kasa_banka.bakiye += db_fatura.genel_toplam
                else: # ÇIKIŞ
                    db_kasa_banka.bakiye -= db_fatura.genel_toplam
                db.add(db_kasa_banka)

    # Sipariş durumunu güncelle
    db_siparis.durum = semalar.SiparisDurumEnum.FATURALASTIRILDI
    db_siparis.fatura_id = db_fatura.id # Siparişe fatura ID'sini ata
    db.add(db_siparis)

    db.commit() # Tüm işlemleri onayla
    db.refresh(db_fatura)
    return db_fatura

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