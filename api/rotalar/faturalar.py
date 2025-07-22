from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db
from sqlalchemy import case, func 
from datetime import date

router = APIRouter(
    prefix="/faturalar",
    tags=["Faturalar"]
)

@router.get("/", response_model=List[modeller.FaturaBase])
def read_faturalar(
    skip: int = 0, 
    limit: int = 100, 
    tip: Optional[str] = None,
    bas_t: Optional[date] = None,
    bit_t: Optional[date] = None,
    arama: Optional[str] = None,
    cari_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    cari_adi_case = case(
        (semalar.Fatura.tip.in_(['SATIŞ', 'SATIŞ İADE']), semalar.Musteri.ad),
        (semalar.Fatura.tip.in_(['ALIŞ', 'ALIŞ İADE', 'DEVİR_GİRİŞ']), semalar.Tedarikci.ad),
        else_ = "Bilinmeyen Cari"
    ).label("cari_adi")

    query = db.query(semalar.Fatura, cari_adi_case)\
        .outerjoin(semalar.Musteri, semalar.Musteri.id == semalar.Fatura.cari_id)\
        .outerjoin(semalar.Tedarikci, semalar.Tedarikci.id == semalar.Fatura.cari_id)

    if tip:
        if tip == 'SATIŞ': query = query.filter(semalar.Fatura.tip.in_(['SATIŞ', 'SATIŞ İADE']))
        elif tip == 'ALIŞ': query = query.filter(semalar.Fatura.tip.in_(['ALIŞ', 'ALIŞ İADE', 'DEVİR_GİRİŞ']))
        else: query = query.filter(semalar.Fatura.tip == tip)
    
    if bas_t: query = query.filter(semalar.Fatura.tarih >= bas_t)
    if bit_t: query = query.filter(semalar.Fatura.tarih <= bit_t)
    if cari_id: query = query.filter(semalar.Fatura.cari_id == cari_id)
    if arama:
        arama_filter = f"%{arama.lower()}%"
        query = query.filter(
            (func.lower(semalar.Fatura.fatura_no).ilike(arama_filter)) |
            (func.lower(semalar.Musteri.ad).ilike(arama_filter)) |
            (func.lower(semalar.Tedarikci.ad).ilike(arama_filter)) |
            (func.lower(semalar.Fatura.misafir_adi).ilike(arama_filter))
        )

    fatura_results = query.order_by(semalar.Fatura.tarih.desc()).offset(skip).limit(limit).all()
    
    results = []
    for fatura, cari_adi in fatura_results:
        fatura_model = modeller.FaturaBase.from_orm(fatura)
        fatura_model.cari_adi = cari_adi
        results.append(fatura_model)
        
    return results

@router.get("/count", response_model=int)
def get_faturalar_count(
    tip: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Filtrelere göre toplam fatura sayısını döndürür.
    """
    query = db.query(semalar.Fatura)
    
    if tip:
        # Gelen tip "SATIŞ" veya "ALIŞ" ise, iadeleri de dahil et
        if tip == 'SATIŞ':
            query = query.filter(semalar.Fatura.tip.in_(['SATIŞ', 'SATIŞ İADE']))
        elif tip == 'ALIŞ':
            query = query.filter(semalar.Fatura.tip.in_(['ALIŞ', 'ALIŞ İADE', 'DEVİR_GİRİŞ']))
        else:
            query = query.filter(semalar.Fatura.tip == tip)
            
    return query.count()

@router.post("/", response_model=modeller.FaturaBase)
def create_fatura(fatura: modeller.FaturaCreate, db: Session = Depends(get_db)):
    """
    Yeni bir fatura oluşturur. Stok, cari ve kasa hareketlerini tek bir transaction içinde yönetir.
    Eski OnMuhasebe sınıfına bağımlılığı yoktur.
    """
    db.begin_nested() # Veritabanı transaction yönetimi için savepoint oluşturuyoruz
    try:
        # 1. Fatura Numarasının Benzersizliğini Kontrol Et
        existing_fatura = db.query(semalar.Fatura).filter(semalar.Fatura.fatura_no == fatura.fatura_no).first()
        if existing_fatura:
            raise HTTPException(status_code=400, detail=f"Fatura numarası '{fatura.fatura_no}' zaten mevcut.")

        # 2. Fatura Toplamlarını ve Kalemleri Hazırla
        toplam_kdv_haric = 0.0
        toplam_kdv_dahil = 0.0
        
        db_kalemler = []
        
        for kalem in fatura.kalemler:
            urun = db.query(semalar.Stok).filter(semalar.Stok.id == kalem.urun_id).first()
            if not urun:
                raise HTTPException(status_code=404, detail=f"ID: {kalem.urun_id} olan ürün bulunamadı.")

            kdv_carpan = 1 + (kalem.kdv_orani / 100)
            birim_fiyat_haric = kalem.birim_fiyat / kdv_carpan
            
            iskontolu_bf_haric = birim_fiyat_haric * (1 - kalem.iskonto_yuzde_1 / 100) * (1 - kalem.iskonto_yuzde_2 / 100)
            
            kalem_toplam_haric = kalem.miktar * iskontolu_bf_haric
            kalem_kdv_tutari = kalem_toplam_haric * (kalem.kdv_orani / 100)
            kalem_toplam_dahil = kalem_toplam_haric + kalem_kdv_tutari

            toplam_kdv_haric += kalem_toplam_haric
            toplam_kdv_dahil += kalem_toplam_dahil
            
            db_kalemler.append(semalar.FaturaKalemleri(
                urun_id=kalem.urun_id, miktar=kalem.miktar, birim_fiyat=birim_fiyat_haric,
                kdv_orani=kalem.kdv_orani, kdv_tutari=kalem_kdv_tutari,
                kalem_toplam_kdv_haric=kalem_toplam_haric, kalem_toplam_kdv_dahil=kalem_toplam_dahil,
                alis_fiyati_fatura_aninda=kalem.alis_fiyati_fatura_aninda,
                iskonto_yuzde_1=kalem.iskonto_yuzde_1, iskonto_yuzde_2=kalem.iskonto_yuzde_2
            ))

        # 3. Genel İskontoyu Uygula
        uygulanan_genel_iskonto = 0.0
        if fatura.genel_iskonto_tipi == 'YUZDE':
            uygulanan_genel_iskonto = toplam_kdv_haric * (fatura.genel_iskonto_degeri / 100)
        elif fatura.genel_iskonto_tipi == 'TUTAR':
            uygulanan_genel_iskonto = fatura.genel_iskonto_degeri

        nihai_toplam_kdv_haric = toplam_kdv_haric - uygulanan_genel_iskonto
        nihai_toplam_kdv_dahil = toplam_kdv_dahil - uygulanan_genel_iskonto

        # 4. Ana Fatura Kaydını Oluştur
        db_fatura = semalar.Fatura(
            fatura_no=fatura.fatura_no, tarih=fatura.fatura_tarihi, tip=fatura.tip,
            cari_id=fatura.cari_id, toplam_kdv_haric=nihai_toplam_kdv_haric,
            toplam_kdv_dahil=nihai_toplam_kdv_dahil, odeme_turu=fatura.odeme_turu,
            kasa_banka_id=fatura.kasa_banka_id, misafir_adi=fatura.misafir_adi,
            fatura_notlari=fatura.fatura_notlari, vade_tarihi=fatura.vade_tarihi,
            genel_iskonto_tipi=fatura.genel_iskonto_tipi, genel_iskonto_degeri=fatura.genel_iskonto_degeri,
            olusturan_kullanici_id=1 # Varsayılan kullanıcı
        )
        db_fatura.kalemler.extend(db_kalemler)

        # 5. Yan Etkileri (Stok, Cari, Kasa Hareketleri) Yönet
        for kalem in fatura.kalemler:
            urun = db.query(semalar.Stok).filter(semalar.Stok.id == kalem.urun_id).first()
            stok_degisim_net = 0.0
            if fatura.tip in ['SATIŞ', 'ALIŞ İADE']: stok_degisim_net = -kalem.miktar
            elif fatura.tip in ['ALIŞ', 'SATIŞ İADE', 'DEVİR_GİRİŞ']: stok_degisim_net = kalem.miktar
            if stok_degisim_net != 0: urun.stok_miktari = (urun.stok_miktari or 0) + stok_degisim_net

        pesin_odeme_turleri = ["NAKİT", "KART", "EFT/HAVALE", "ÇEK", "SENET"]
        if fatura.odeme_turu in pesin_odeme_turleri and fatura.kasa_banka_id:
            kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == fatura.kasa_banka_id).first()
            gelir_gider_tipi = None
            if fatura.tip in ['SATIŞ', 'ALIŞ İADE']:
                kasa_hesabi.bakiye += nihai_toplam_kdv_dahil; gelir_gider_tipi = 'GELİR'
            elif fatura.tip in ['ALIŞ', 'SATIŞ İADE']:
                kasa_hesabi.bakiye -= nihai_toplam_kdv_dahil; gelir_gider_tipi = 'GİDER'
            if gelir_gider_tipi:
                db_fatura.gelir_gider_kaydi = semalar.GelirGider(
                    tarih=fatura.fatura_tarihi, tip=gelir_gider_tipi, tutar=nihai_toplam_kdv_dahil,
                    aciklama=f"'{fatura.fatura_no}' nolu fatura işlemi.", kaynak='FATURA', kasa_banka_id=fatura.kasa_banka_id)

        cari_tip_str = 'MUSTERI' if fatura.tip in ['SATIŞ', 'SATIŞ İADE'] else ('TEDARIKCI' if fatura.tip in ['ALIŞ', 'ALIŞ İADE'] else None)
        if cari_tip_str:
            hareket_tipi = ""
            if fatura.tip == 'SATIŞ': hareket_tipi = 'ALACAK'
            elif fatura.tip == 'ALIŞ': hareket_tipi = 'BORÇ'
            elif fatura.tip == 'SATIŞ İADE': hareket_tipi = 'BORÇ'
            elif fatura.tip == 'ALIŞ İADE': hareket_tipi = 'ALACAK'
            if hareket_tipi:
                db_fatura.cari_hareketleri.append(semalar.CariHareketler(
                    tarih=fatura.fatura_tarihi, cari_tip=cari_tip_str, cari_id=fatura.cari_id,
                    islem_tipi=hareket_tipi, tutar=nihai_toplam_kdv_dahil, referans_tip='FATURA',
                    kasa_banka_id=fatura.kasa_banka_id # Kasa/Banka ID'yi cari harekete de ekle
                ))
            if fatura.odeme_turu in pesin_odeme_turleri:
                odeme_hareket_tipi = 'TAHSILAT' if cari_tip_str == 'MUSTERI' else 'ODEME'
                db_fatura.cari_hareketleri.append(semalar.CariHareketler(
                    tarih=fatura.fatura_tarihi, cari_tip=cari_tip_str, cari_id=fatura.cari_id,
                    islem_tipi=odeme_hareket_tipi, tutar=nihai_toplam_kdv_dahil,
                    referans_tip='FATURA', kasa_banka_id=fatura.kasa_banka_id))

        db.add(db_fatura)
        db.commit()
        db.refresh(db_fatura)
        
        # İlişkili kayıtların referans ID'lerini güncelle
        for hareket in db_fatura.cari_hareketleri:
            hareket.referans_id = db_fatura.id
        if db_fatura.gelir_gider_kaydi:
            db_fatura.gelir_gider_kaydi.kaynak_id = db_fatura.id
        db.commit()

        return db_fatura
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Fatura kaydedilirken bir veritabanı hatası oluştu: {str(e)}")
    
@router.put("/{fatura_id}", response_model=modeller.FaturaBase)
def update_fatura(fatura_id: int, fatura: modeller.FaturaUpdate, db: Session = Depends(get_db)):
    """
    Mevcut bir faturayı günceller. Eski stok, cari ve kasa etkilerini geri alıp yenilerini uygular.
    Tüm işlemler tek bir transaction içinde yönetilir.
    """
    db_fatura = db.query(semalar.Fatura).filter(semalar.Fatura.id == fatura_id).first()
    if not db_fatura:
        raise HTTPException(status_code=404, detail="Güncellenecek fatura bulunamadı.")

    if db_fatura.fatura_no != fatura.fatura_no:
        existing_fatura = db.query(semalar.Fatura).filter(semalar.Fatura.fatura_no == fatura.fatura_no).first()
        if existing_fatura:
            raise HTTPException(status_code=400, detail=f"Fatura numarası '{fatura.fatura_no}' zaten mevcut.")

    db.begin_nested()
    try:
        # 1. ESKİ ETKİLERİ GERİ AL
        eski_toplam_tutar = db_fatura.toplam_kdv_dahil
        eski_kasa_id = db_fatura.kasa_banka_id
        eski_odeme_turu = db_fatura.odeme_turu
        fatura_tipi = db_fatura.tip

        for kalem in db_fatura.kalemler:
            urun = db.query(semalar.Stok).filter(semalar.Stok.id == kalem.urun_id).first()
            if urun:
                stok_iade_miktari = 0
                if fatura_tipi in ['SATIŞ', 'ALIŞ İADE']: stok_iade_miktari = kalem.miktar
                elif fatura_tipi in ['ALIŞ', 'SATIŞ İADE', 'DEVİR_GİRİŞ']: stok_iade_miktari = -kalem.miktar
                urun.stok_miktari = (urun.stok_miktari or 0) + stok_iade_miktari
        
        pesin_odeme_turleri = ["NAKİT", "KART", "EFT/HAVALE", "ÇEK", "SENET"]
        if eski_odeme_turu in pesin_odeme_turleri and eski_kasa_id:
            kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == eski_kasa_id).first()
            if kasa_hesabi:
                if fatura_tipi in ['SATIŞ', 'ALIŞ İADE']: kasa_hesabi.bakiye -= eski_toplam_tutar
                elif fatura_tipi in ['ALIŞ', 'SATIŞ İADE']: kasa_hesabi.bakiye += eski_toplam_tutar

        db.query(semalar.CariHareketler).filter(semalar.CariHareketler.referans_id == fatura_id, semalar.CariHareketler.referans_tip == 'FATURA').delete(synchronize_session=False)
        db.query(semalar.GelirGider).filter(semalar.GelirGider.kaynak_id == fatura_id, semalar.GelirGider.kaynak == 'FATURA').delete(synchronize_session=False)
        db.query(semalar.FaturaKalemleri).filter(semalar.FaturaKalemleri.fatura_id == fatura_id).delete(synchronize_session=False)
        db.flush()

        # 2. YENİ BİLGİLERİ UYGULA
        toplam_kdv_haric = 0.0
        toplam_kdv_dahil = 0.0
        db_kalemler = []

        for kalem in fatura.kalemler:
            kdv_carpan = 1 + (kalem.kdv_orani / 100)
            birim_fiyat_haric = kalem.birim_fiyat / kdv_carpan
            iskontolu_bf_haric = birim_fiyat_haric * (1 - kalem.iskonto_yuzde_1 / 100) * (1 - kalem.iskonto_yuzde_2 / 100)
            kalem_toplam_haric = kalem.miktar * iskontolu_bf_haric
            kalem_kdv_tutari = kalem_toplam_haric * (kalem.kdv_orani / 100)
            kalem_toplam_dahil = kalem_toplam_haric + kalem_kdv_tutari
            toplam_kdv_haric += kalem_toplam_haric
            toplam_kdv_dahil += kalem_toplam_dahil
            
            db_kalemler.append(semalar.FaturaKalemleri(
                fatura_id=fatura_id, urun_id=kalem.urun_id, miktar=kalem.miktar, birim_fiyat=birim_fiyat_haric,
                kdv_orani=kalem.kdv_orani, kdv_tutari=kalem_kdv_tutari,
                kalem_toplam_kdv_haric=kalem_toplam_haric, kalem_toplam_kdv_dahil=kalem_toplam_dahil,
                alis_fiyati_fatura_aninda=kalem.alis_fiyati_fatura_aninda,
                iskonto_yuzde_1=kalem.iskonto_yuzde_1, iskonto_yuzde_2=kalem.iskonto_yuzde_2
            ))
        db.add_all(db_kalemler)
        
        uygulanan_genel_iskonto = 0.0
        if fatura.genel_iskonto_tipi == 'YUZDE':
            uygulanan_genel_iskonto = toplam_kdv_haric * (fatura.genel_iskonto_degeri / 100)
        elif fatura.genel_iskonto_tipi == 'TUTAR':
            uygulanan_genel_iskonto = fatura.genel_iskonto_degeri

        nihai_toplam_kdv_haric = toplam_kdv_haric - uygulanan_genel_iskonto
        nihai_toplam_kdv_dahil = toplam_kdv_dahil - uygulanan_genel_iskonto

        # Ana Fatura tablosunu GÜNCELLE
        db_fatura.fatura_no = fatura.fatura_no
        db_fatura.tarih = fatura.fatura_tarihi
        db_fatura.cari_id = fatura.cari_id
        db_fatura.toplam_kdv_haric = nihai_toplam_kdv_haric
        db_fatura.toplam_kdv_dahil = nihai_toplam_kdv_dahil
        db_fatura.odeme_turu = fatura.odeme_turu
        db_fatura.kasa_banka_id = fatura.kasa_banka_id
        db_fatura.misafir_adi = fatura.misafir_adi
        db_fatura.fatura_notlari = fatura.fatura_notlari
        db_fatura.vade_tarihi = fatura.vade_tarihi
        db_fatura.genel_iskonto_tipi = fatura.genel_iskonto_tipi
        db_fatura.genel_iskonto_degeri = fatura.genel_iskonto_degeri
        db_fatura.son_guncelleyen_kullanici_id = 1 # Varsayılan kullanıcı
        
        # 3. YENİ YAN ETKİLERİ OLUŞTUR
        for kalem in fatura.kalemler:
            urun = db.query(semalar.Stok).filter(semalar.Stok.id == kalem.urun_id).first()
            stok_degisim_net = 0.0
            if fatura_tipi in ['SATIŞ', 'ALIŞ İADE']: stok_degisim_net = -kalem.miktar
            elif fatura_tipi in ['ALIŞ', 'SATIŞ İADE', 'DEVİR_GİRİŞ']: stok_degisim_net = kalem.miktar
            if stok_degisim_net != 0: urun.stok_miktari = (urun.stok_miktari or 0) + stok_degisim_net

        if fatura.odeme_turu in pesin_odeme_turleri and fatura.kasa_banka_id:
            kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == fatura.kasa_banka_id).first()
            gelir_gider_tipi = None
            if fatura_tipi in ['SATIŞ', 'ALIŞ İADE']:
                kasa_hesabi.bakiye += nihai_toplam_kdv_dahil; gelir_gider_tipi = 'GELİR'
            elif fatura_tipi in ['ALIŞ', 'SATIŞ İADE']:
                kasa_hesabi.bakiye -= nihai_toplam_kdv_dahil; gelir_gider_tipi = 'GİDER'
            if gelir_gider_tipi:
                yeni_gelir_gider = semalar.GelirGider(
                    tarih=fatura.fatura_tarihi, tip=gelir_gider_tipi, tutar=nihai_toplam_kdv_dahil,
                    aciklama=f"'{fatura.fatura_no}' nolu fatura işlemi.", kaynak='FATURA', kaynak_id=fatura_id, kasa_banka_id=fatura.kasa_banka_id)
                db.add(yeni_gelir_gider)

        cari_tip_str = 'MUSTERI' if fatura_tipi in ['SATIŞ', 'SATIŞ İADE'] else ('TEDARIKCI' if fatura_tipi in ['ALIŞ', 'ALIŞ İADE'] else None)
        if cari_tip_str:
            hareket_tipi = ""
            if fatura_tipi == 'SATIŞ': hareket_tipi = 'ALACAK'
            elif fatura_tipi == 'ALIŞ': hareket_tipi = 'BORÇ'
            elif fatura_tipi == 'SATIŞ İADE': hareket_tipi = 'BORÇ'
            elif fatura_tipi == 'ALIŞ İADE': hareket_tipi = 'ALACAK'
            if hareket_tipi:
                db.add(semalar.CariHareketler(
                    tarih=fatura.fatura_tarihi, cari_tip=cari_tip_str, cari_id=fatura.cari_id,
                    islem_tipi=hareket_tipi, tutar=nihai_toplam_kdv_dahil, referans_tip='FATURA', referans_id=fatura_id))
            if fatura.odeme_turu in pesin_odeme_turleri:
                odeme_hareket_tipi = 'TAHSILAT' if cari_tip_str == 'MUSTERI' else 'ODEME'
                db.add(semalar.CariHareketler(
                    tarih=fatura.fatura_tarihi, cari_tip=cari_tip_str, cari_id=fatura.cari_id,
                    islem_tipi=odeme_hareket_tipi, tutar=nihai_toplam_kdv_dahil,
                    referans_tip='FATURA', referans_id=fatura_id, kasa_banka_id=fatura.kasa_banka_id))

        db.commit()
        db.refresh(db_fatura)
        return db_fatura
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Fatura güncellenirken bir hata oluştu: {str(e)}")
    
@router.delete("/{fatura_id}", status_code=204)
def delete_fatura(fatura_id: int, db: Session = Depends(get_db)):
    """
    Bir faturayı ve onunla ilişkili tüm hareketleri (stok, cari, kasa) güvenli bir şekilde siler.
    """
    db_fatura = db.query(semalar.Fatura).filter(semalar.Fatura.id == fatura_id).first()
    if not db_fatura:
        raise HTTPException(status_code=404, detail="Silinecek fatura bulunamadı.")

    db.begin_nested()
    try:
        # 1. FATURANIN TÜM ETKİLERİNİ GERİ AL
        # ==================================
        toplam_tutar = db_fatura.toplam_kdv_dahil
        kasa_id = db_fatura.kasa_banka_id
        odeme_turu = db_fatura.odeme_turu
        fatura_tipi = db_fatura.tip

        # Stokları geri al
        for kalem in db_fatura.kalemler:
            urun = db.query(semalar.Stok).filter(semalar.Stok.id == kalem.urun_id).first()
            if urun:
                stok_iade_miktari = 0
                if fatura_tipi in ['SATIŞ', 'ALIŞ İADE']: stok_iade_miktari = kalem.miktar
                elif fatura_tipi in ['ALIŞ', 'SATIŞ İADE', 'DEVİR_GİRİŞ']: stok_iade_miktari = -kalem.miktar
                urun.stok_miktari += stok_iade_miktari
        
        pesin_odeme_turleri = ["NAKİT", "KART", "EFT/HAVALE", "ÇEK", "SENET"]
        if odeme_turu in pesin_odeme_turleri and kasa_id:
            kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == kasa_id).first()
            if kasa_hesabi:
                if fatura_tipi in ['SATIŞ', 'ALIŞ İADE']: kasa_hesabi.bakiye -= toplam_tutar
                elif fatura_tipi in ['ALIŞ', 'SATIŞ İADE']: kasa_hesabi.bakiye += toplam_tutar

        # İlişkili Cari ve Gelir/Gider hareketlerini sil
        db.query(semalar.CariHareketler).filter(semalar.CariHareketler.referans_id == fatura_id, semalar.CariHareketler.referans_tip == 'FATURA').delete()
        db.query(semalar.GelirGider).filter(semalar.GelirGider.kaynak_id == fatura_id, semalar.GelirGider.kaynak == 'FATURA').delete()
        
        # 2. FATURAYI SİL
        # ================
        db.delete(db_fatura)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Fatura silinirken bir hata oluştu: {str(e)}")

    return

@router.get("/{fatura_id}", response_model=modeller.FaturaBase)
def read_fatura_by_id(fatura_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip tek bir faturayı döndürür.
    """
    cari_adi_case = case(
        (semalar.Fatura.tip.in_(['SATIŞ', 'SATIŞ İADE']), semalar.Musteri.ad),
        (semalar.Fatura.tip.in_(['ALIŞ', 'ALIŞ İADE', 'DEVİR_GİRİŞ']), semalar.Tedarikci.ad),
        else_ = "Bilinmeyen Cari"
    ).label("cari_adi")

    # Kasa/Banka adını da almak için JOIN
    kasa_banka_adi_case = case(
        (semalar.Fatura.kasa_banka_id == semalar.KasaBanka.id, semalar.KasaBanka.hesap_adi),
        else_=None
    ).label("kasa_banka_adi")

    # Kullanıcı adlarını almak için JOIN
    olusturan_kul_adi_case = case(
        (semalar.Fatura.olusturan_kullanici_id == semalar.Kullanici.id, semalar.Kullanici.kullanici_adi),
        else_=None
    ).label("olusturan_kul_adi")

    guncelleyen_kul_adi_case = case(
        (semalar.Fatura.son_guncelleyen_kullanici_id == semalar.Kullanici.id, semalar.Kullanici.kullanici_adi),
        else_=None
    ).label("guncelleyen_kul_adi")

    result = db.query(semalar.Fatura, cari_adi_case, kasa_banka_adi_case, olusturan_kul_adi_case, guncelleyen_kul_adi_case)\
        .outerjoin(semalar.Musteri, semalar.Musteri.id == semalar.Fatura.cari_id)\
        .outerjoin(semalar.Tedarikci, semalar.Tedarikci.id == semalar.Fatura.cari_id)\
        .outerjoin(semalar.KasaBanka, semalar.KasaBanka.id == semalar.Fatura.kasa_banka_id)\
        .outerjoin(semalar.Kullanici, semalar.Kullanici.id == semalar.Fatura.olusturan_kullanici_id)\
        .outerjoin(semalar.Kullanici, semalar.Kullanici.id == semalar.Fatura.son_guncelleyen_kullanici_id)\
        .filter(semalar.Fatura.id == fatura_id)\
        .first()

    if not result:
        raise HTTPException(status_code=404, detail="Fatura bulunamadı")

    fatura, cari_adi, kasa_banka_adi, olusturan_kul_adi, guncelleyen_kul_adi = result
    fatura_model = modeller.FaturaBase.from_orm(fatura)
    fatura_model.cari_adi = cari_adi
    fatura_model.kasa_banka_adi = kasa_banka_adi
    fatura_model.olusturan_kul_adi = olusturan_kul_adi
    fatura_model.guncelleyen_kul_adi = guncelleyen_kul_adi
    
    return fatura_model

@router.get("/son_fatura_no") # fatura_id yol parametresi olmadan
def sonraki_fatura_no_getir(fatura_tipi: str, db: Session = Depends(get_db)):
    """Belirtilen fatura tipi için son fatura numarasını getirir ve bir sonraki numarayı önerir."""
    # Son fatura numarasını veritabanından çekin
    # Örnek: "SATIŞ" tipi faturalar için "SF00001", "ALIŞ" için "AF00001" gibi
    prefix_map = {
        "SATIŞ": "SF",
        "ALIŞ": "AF",
        "SATIŞ İADE": "SI",
        "ALIŞ İADE": "AI",
        "DEVİR GİRİŞ": "DG"
    }
    prefix = prefix_map.get(fatura_tipi, "XX") # Bilinmeyen tip için varsayılan prefix

    # Veritabanından bu prefix ile başlayan en büyük fatura numarasını bulun
    # Örneğin: SELECT fatura_no FROM faturalar WHERE fatura_no LIKE 'SF%' ORDER BY fatura_no DESC LIMIT 1;
    last_fatura_no = db.query(semalar.Fatura.fatura_no). \
        filter(semalar.Fatura.fatura_no.like(f"{prefix}%")). \
        order_by(semalar.Fatura.fatura_no.desc()).first()

    if last_fatura_no:
        last_no_str = last_fatura_no[0]
        try:
            # Sayısal kısmı al (prefix'ten sonraki kısım)
            numeric_part = int(last_no_str[len(prefix):])
            next_numeric_part = numeric_part + 1
            next_fatura_no = f"{prefix}{next_numeric_part:09d}" # 9 basamaklı sıfır dolgulu
        except ValueError:
            # Eğer fatura no formatı beklenenden farklıysa
            next_fatura_no = f"{prefix}000000001"
    else:
        next_fatura_no = f"{prefix}000000001"

    return {"next_no": next_fatura_no}

def fatura_kalemlerini_getir(fatura_id: int, db: Session = Depends(get_db)):
    """Belirtilen faturanın kalemlerini döndürür."""
    kalemler = db.query(semalar.FaturaKalemi).filter(semalar.FaturaKalemi.fatura_id == fatura_id).all()
    # Modeller.FaturaKalemi Pydantic modeline dönüştürerek döndürün.
    return [modeller.FaturaKalemi.model_validate(kalem) for kalem in kalemler]