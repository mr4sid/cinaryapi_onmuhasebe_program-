from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract, case, literal_column
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
import calendar

# Kendi modüllerimiz
from .. import semalar
from .. import modeller
from ..veritabani import get_db

router = APIRouter(
    prefix="/raporlar",
    tags=["Raporlama"]
)

# Yardımcı fonksiyonlar (tarih formatlama, para birimi formatlama vb. - aslında UI'da olanlar)
# Bu fonksiyonlar veritabanından çekilen ham veriyi işleyecektir.

# -- Dashboard Özet Metrikleri --
@router.get("/dashboard_ozet")
def get_dashboard_ozet_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    bugun = date.today()
    # Eğer tarih aralığı verilmemişse varsayılan değerleri ayarla
    if baslangic_tarihi is None:
        baslangic_tarihi = datetime(bugun.year, bugun.month, 1).date() # Ayın başı
    if bitis_tarihi is None:
        bitis_tarihi = bugun # Bugün

    # Toplam Satış (KDV Dahil)
    toplam_satis_sorgusu = db.query(func.sum(semalar.FaturaKalemi.kalem_toplam_kdv_dahil)). \
        join(semalar.Fatura, semalar.Fatura.id == semalar.FaturaKalemi.fatura_id). \
        filter(semalar.Fatura.tip.in_(["SATIŞ", "SATIŞ İADE"])). \
        filter(semalar.Fatura.tarih >= baslangic_tarihi, semalar.Fatura.tarih <= bitis_tarihi)
    toplam_satis = toplam_satis_sorgusu.scalar() or 0.0

    # Toplam Tahsilat
    toplam_tahsilat_sorgusu = db.query(func.sum(semalar.GelirGider.tutar)). \
        filter(semalar.GelirGider.tip == "GELİR"). \
        filter(semalar.GelirGider.tarih >= baslangic_tarihi, semalar.GelirGider.tarih <= bitis_tarihi)
    toplam_tahsilat = toplam_tahsilat_sorgusu.scalar() or 0.0

    # Toplam Ödeme
    toplam_odeme_sorgusu = db.query(func.sum(semalar.GelirGider.tutar)). \
        filter(semalar.GelirGider.tip == "GİDER"). \
        filter(semalar.GelirGider.tarih >= baslangic_tarihi, semalar.GelirGider.tarih <= bitis_tarihi)
    toplam_odeme = toplam_odeme_sorgusu.scalar() or 0.0

    # Kritik Stok Adedi ve Ayın En Çok Satan Ürünü
    # Not: Ayın en çok satan ürünü için daha sofistike bir sorgu gerekebilir.
    # Basitçe son ayın toplam satış miktarını bulan sorgu:
    en_cok_satan_urun = db.query(
            semalar.Stok.urun_adi,
            func.sum(semalar.FaturaKalemi.miktar).label("toplam_miktar")
        ). \
        join(semalar.FaturaKalemi, semalar.Stok.id == semalar.FaturaKalemi.urun_id). \
        join(semalar.Fatura, semalar.Fatura.id == semalar.FaturaKalemi.fatura_id). \
        filter(semalar.Fatura.tip == "SATIŞ"). \
        filter(semalar.Fatura.tarih >= baslangic_tarihi, semalar.Fatura.tarih <= bitis_tarihi). \
        group_by(semalar.Stok.urun_adi). \
        order_by(func.sum(semalar.FaturaKalemi.miktar).desc()). \
        first()

    en_cok_satan_urun_adi = en_cok_satan_urun.urun_adi if en_cok_satan_urun else "---"

    kritik_stok_adet = db.query(semalar.Stok). \
        filter(semalar.Stok.stok_miktari < semalar.Stok.min_stok_seviyesi).count()

    # Vadesi Geçmiş Alacaklar
    # Müşterilerin VADESİ GEÇMİŞ alacaklarını bulmak için:
    # Fatura tipi SATIS_ACIK_HESAP olan ve vade_tarihi geçmiş faturaların toplamı
    vadesi_gecmis_alacak = db.query(func.sum(semalar.Fatura.toplam_kdv_dahil)). \
        filter(
            semalar.Fatura.tip == "SATIŞ",
            semalar.Fatura.odeme_turu == "AÇIK HESAP",
            semalar.Fatura.vade_tarihi < bugun,
            # Henüz ödenmemiş veya kısmen ödenmiş faturalar olmalı (OdemeIslemi tablosu üzerinden kontrol edilebilir)
            # Basitlik adına, şimdilik sadece vade_tarihi geçmiş faturaları topluyoruz.
            # Daha doğru bir bakiye kontrolü için CariHareketler tablosuna bakmak gerekir.
        ).scalar() or 0.0

    # Vadesi Geçmiş Borçlar
    # Tedarikçilerin VADESİ GEÇMİŞ borçlarını bulmak için:
    vadesi_gecmis_borc = db.query(func.sum(semalar.Fatura.toplam_kdv_dahil)). \
        filter(
            semalar.Fatura.tip == "ALIŞ",
            semalar.Fatura.odeme_turu == "AÇIK HESAP",
            semalar.Fatura.vade_tarihi < bugun,
        ).scalar() or 0.0


    return {
        "toplam_satis": toplam_satis,
        "toplam_tahsilat": toplam_tahsilat,
        "toplam_odeme": toplam_odeme,
        "kritik_stok_adet": kritik_stok_adet,
        "en_cok_satan_urun_adi": en_cok_satan_urun_adi,
        "vadesi_gecmis_alacak": vadesi_gecmis_alacak,
        "vadesi_gecmis_borc": vadesi_gecmis_borc
    }

# -- Raporlama Endpoint'leri --

@router.get("/satislar/odeme_turune_gore")
def get_sales_by_payment_type_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        semalar.Fatura.odeme_turu,
        func.sum(semalar.Fatura.toplam_kdv_dahil).label("toplam_tutar")
    ). \
        filter(semalar.Fatura.tip == "SATIŞ")

    if baslangic_tarihi:
        query = query.filter(semalar.Fatura.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.Fatura.tarih <= bitis_tarihi)

    result = query.group_by(semalar.Fatura.odeme_turu).all()
    return [{"odeme_turu": r.odeme_turu, "toplam_tutar": r.toplam_tutar} for r in result]

@router.get("/stoklar/en_cok_satanlar")
def get_top_selling_products_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    query = db.query(
        semalar.Stok.urun_adi,
        func.sum(semalar.FaturaKalemi.miktar).label("toplam_miktar")
    ). \
        join(semalar.FaturaKalemi, semalar.Stok.id == semalar.FaturaKalemi.urun_id). \
        join(semalar.Fatura, semalar.Fatura.id == semalar.FaturaKalemi.fatura_id). \
        filter(semalar.Fatura.tip == "SATIŞ")

    if baslangic_tarihi:
        query = query.filter(semalar.Fatura.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.Fatura.tarih <= bitis_tarihi)

    result = query.group_by(semalar.Stok.urun_adi). \
        order_by(func.sum(semalar.FaturaKalemi.miktar).desc()). \
        limit(limit).all()

    return [{"urun_adi": r.urun_adi, "toplam_miktar": r.toplam_miktar} for r in result]

@router.get("/stoklar/kritik_stoklar")
def get_critical_stock_items_endpoint(db: Session = Depends(get_db)):
    critical_items = db.query(semalar.Stok).filter(semalar.Stok.stok_miktari < semalar.Stok.min_stok_seviyesi).all()
    return [modeller.Stok.model_validate(item) for item in critical_items] # Stok modelini kullanarak döndür

@router.get("/cariler/toplam_bakiye")
def get_cari_total_receivables_payables_endpoint(
    cari_tipi: Optional[str] = None, # 'MUSTERI' veya 'TEDARIKCI'
    db: Session = Depends(get_db)
):
    # Bu sorgu CariHareketler tablosuna dayanmalı ve daha karmaşık olabilir.
    # Basitlik adına, şimdilik direkt müşteri/tedarikçi ana tablosundaki bakiye alanını kullanıyoruz.
    # Ancak, semalar.py'de Musteri ve Tedarikci'nin doğrudan 'bakiye' alanı yok.
    # Cari hareketler üzerinden hesaplama yapmak en doğrusudur.

    toplam_alacak = 0.0
    toplam_borc = 0.0

    if cari_tipi == "MUSTERI":
        # Tüm müşterilerin net bakiyelerini topla (pozitif bakiyeler alacak, negatif borç)
        # CariHareketler tablosu üzerinden hesaplanmalı
        musteri_bakiyeleri_query = db.query(
            func.sum(case(
                (semalar.CariHareket.islem_tipi.in_(["TAHSILAT", "SATIŞ"]), -semalar.CariHareket.tutar), # Müşteri için tahsilat ve satış bakiyeyi azaltır (alacak kapatır)
                else_=semalar.CariHareket.tutar # Borç artırır (borçlandırır)
            )).label("net_bakiye")
        ).filter(semalar.CariHareket.cari_tipi == "MUSTERI").group_by(semalar.CariHareket.cari_id).all()

        for item in musteri_bakiyeleri_query:
            if item.net_bakiye > 0:
                toplam_borc += item.net_bakiye # Müşteri bize borçlu
            else:
                toplam_alacak += abs(item.net_bakiye) # Biz müşteriye borçluyuz (alacak)

    elif cari_tipi == "TEDARIKCI":
        # Tüm tedarikçilerin net bakiyelerini topla
        tedarikci_bakiyeleri_query = db.query(
            func.sum(case(
                (semalar.CariHareket.islem_tipi.in_(["ODEME", "ALIŞ"]), semalar.CariHareket.tutar), # Tedarikçi için ödeme ve alış bakiyeyi artırır (borç artırır)
                else_=-semalar.CariHareket.tutar # Alacak kapatır
            )).label("net_bakiye")
        ).filter(semalar.CariHareket.cari_tipi == "TEDARIKCI").group_by(semalar.CariHareket.cari_id).all()

        for item in tedarikci_bakiyeleri_query:
            if item.net_bakiye > 0:
                toplam_borc += item.net_bakiye # Biz tedarikçiye borçluyuz
            else:
                toplam_alacak += abs(item.net_bakiye) # Tedarikçi bize borçlu (alacak)

    else: # Tüm cariler
        # Bu durum için Musteri ve Tedarikci bakiyelerini ayrı ayrı çekip toplamak gerekir.
        # Şimdilik sadece MUSTERI ve TEDARIKCI tiplerini destekliyoruz.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçerli bir cari_tipi belirtin ('MUSTERI' veya 'TEDARIKCI').")

    return {"toplam_alacak": toplam_alacak, "toplam_borc": toplam_borc}


@router.get("/satislar/toplam_tutar")
def get_total_sales_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(func.sum(semalar.Fatura.toplam_kdv_dahil)).filter(semalar.Fatura.tip == "SATIŞ")
    if baslangic_tarihi:
        query = query.filter(semalar.Fatura.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.Fatura.tarih <= bitis_tarihi)
    toplam_satis_tutari = query.scalar() or 0.0
    return {"toplam_satis_tutari": toplam_satis_tutari}

@router.get("/tahsilatlar/toplam_tutar")
def get_total_collections_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(func.sum(semalar.GelirGider.tutar)).filter(semalar.GelirGider.tip == "GELİR")
    if baslangic_tarihi:
        query = query.filter(semalar.GelirGider.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.GelirGider.tarih <= bitis_tarihi)
    toplam_tahsilat_tutari = query.scalar() or 0.0
    return {"toplam_tahsilat_tutari": toplam_tahsilat_tutari}

@router.get("/odemeler/toplam_tutar")
def get_total_payments_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(func.sum(semalar.GelirGider.tutar)).filter(semalar.GelirGider.tip == "GİDER")
    if baslangic_tarihi:
        query = query.filter(semalar.GelirGider.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.GelirGider.tarih <= bitis_tarihi)
    toplam_odeme_tutari = query.scalar() or 0.0
    return {"toplam_odeme_tutari": toplam_odeme_tutari}

@router.get("/gelir_gider/toplamlar")
def get_kar_zarar_verileri_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    gelir_query = db.query(func.sum(semalar.GelirGider.tutar)).filter(semalar.GelirGider.tip == "GELİR")
    gider_query = db.query(func.sum(semalar.GelirGider.tutar)).filter(semalar.GelirGider.tip == "GİDER")

    if baslangic_tarihi:
        gelir_query = gelir_query.filter(semalar.GelirGider.tarih >= baslangic_tarihi)
        gider_query = gider_query.filter(semalar.GelirGider.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        gelir_query = gelir_query.filter(semalar.GelirGider.tarih <= bitis_tarihi)
        gider_query = gider_query.filter(semalar.GelirGider.tarih <= bitis_tarihi)

    toplam_gelir = gelir_query.scalar() or 0.0
    toplam_gider = gider_query.scalar() or 0.0
    return {"toplam_gelir": toplam_gelir, "toplam_gider": toplam_gider}

@router.get("/satislar/aylik_ozet")
def get_monthly_sales_summary_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    # Ayın ilk ve son günlerini bulma
    if baslangic_tarihi is None:
        baslangic_tarihi = date(date.today().year, 1, 1) # Yılbaşı
    if bitis_tarihi is None:
        bitis_tarihi = date.today()

    # Ay ve yıl bazında toplam satışları hesapla
    results = db.query(
        func.strftime('%Y-%m', semalar.Fatura.tarih).label('ay_yil'),
        func.sum(semalar.Fatura.toplam_kdv_dahil).label('toplam_satis')
    ). \
        filter(semalar.Fatura.tip == "SATIŞ"). \
        filter(semalar.Fatura.tarih >= baslangic_tarihi, semalar.Fatura.tarih <= bitis_tarihi). \
        group_by('ay_yil').order_by('ay_yil').all()

    return [{"ay_yil": r.ay_yil, "toplam_satis": r.toplam_satis} for r in results]

@router.get("/gelir_gider/aylik_ozet")
def get_monthly_income_expense_summary_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    if baslangic_tarihi is None:
        baslangic_tarihi = date(date.today().year, 1, 1)
    if bitis_tarihi is None:
        bitis_tarihi = date.today()

    # Aylık gelir ve giderleri hesapla
    results = db.query(
        func.strftime('%Y-%m', semalar.GelirGider.tarih).label('ay_yil'),
        func.sum(case((semalar.GelirGider.tip == "GELİR", semalar.GelirGider.tutar), else_=0)).label('toplam_gelir'),
        func.sum(case((semalar.GelirGider.tip == "GİDER", semalar.GelirGider.tutar), else_=0)).label('toplam_gider')
    ). \
        filter(semalar.GelirGider.tarih >= baslangic_tarihi, semalar.GelirGider.tarih <= bitis_tarihi). \
        group_by('ay_yil').order_by('ay_yil').all()

    return [{"ay_yil": r.ay_yil, "toplam_gelir": r.toplam_gelir, "toplam_gider": r.toplam_gider} for r in results]

@router.get("/satislar/detayli_rapor")
def tarihsel_satis_raporu_verilerini_al_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        semalar.Fatura.fatura_no,
        semalar.Fatura.tarih,
        semalar.Musteri.ad_soyad.label('cari_adi'),
        semalar.Stok.urun_adi,
        semalar.FaturaKalemi.miktar,
        semalar.FaturaKalemi.birim_fiyat_kdv_dahil,
        semalar.FaturaKalemi.kalem_toplam_kdv_dahil
    ). \
        join(semalar.FaturaKalemi, semalar.Fatura.id == semalar.FaturaKalemi.fatura_id). \
        join(semalar.Stok, semalar.Stok.id == semalar.FaturaKalemi.urun_id). \
        outerjoin(semalar.Musteri, semalar.Musteri.id == semalar.Fatura.cari_id). \
        filter(semalar.Fatura.tip == "SATIŞ") # Sadece satış faturaları

    if baslangic_tarihi:
        query = query.filter(semalar.Fatura.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.Fatura.tarih <= bitis_tarihi)

    results = query.all()
    # Sonuçları dictionary formatında döndür
    return [
        {
            "fatura_no": r.fatura_no,
            "tarih": r.tarih,
            "cari_adi": r.cari_adi,
            "urun_adi": r.urun_adi,
            "miktar": r.miktar,
            "birim_fiyat_kdv_dahil": r.birim_fiyat_kdv_dahil,
            "kalem_toplam_kdv_dahil": r.kalem_toplam_kdv_dahil
        } for r in results
    ]

@router.get("/kar_zarar/brut_kar")
def get_gross_profit_and_cost_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    # Satış Geliri (KDV Dahil)
    satis_geliri_query = db.query(func.sum(semalar.Fatura.toplam_kdv_dahil)). \
        filter(semalar.Fatura.tip == "SATIŞ")
    if baslangic_tarihi:
        satis_geliri_query = satis_geliri_query.filter(semalar.Fatura.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        satis_geliri_query = satis_geliri_query.filter(semalar.Fatura.tarih <= bitis_tarihi)
    toplam_satis_geliri = satis_geliri_query.scalar() or 0.0

    # Satılan Malın Maliyeti (COGS - FaturaKalemi'ndeki alış fiyatı üzerinden)
    cogs_query = db.query(func.sum(semalar.FaturaKalemi.alis_fiyati_fatura_aninda * semalar.FaturaKalemi.miktar)). \
        join(semalar.Fatura, semalar.Fatura.id == semalar.FaturaKalemi.fatura_id). \
        filter(semalar.Fatura.tip == "SATIŞ") # Sadece satış faturalarının maliyeti

    if baslangic_tarihi:
        cogs_query = cogs_query.filter(semalar.Fatura.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        cogs_query = cogs_query.filter(semalar.Fatura.tarih <= bitis_tarihi)
    cogs = cogs_query.scalar() or 0.0

    brut_kar = toplam_satis_geliri - cogs
    brut_kar_orani = (brut_kar / toplam_satis_geliri * 100) if toplam_satis_geliri else 0.0

    return {"brut_kar": brut_kar, "maliyet": cogs, "brut_kar_orani": brut_kar_orani}

@router.get("/kar_zarar/aylik_ozet")
def get_monthly_gross_profit_summary_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    if baslangic_tarihi is None:
        baslangic_tarihi = date(date.today().year, 1, 1)
    if bitis_tarihi is None:
        bitis_tarihi = date.today()

    # Aylık satış geliri ve maliyetini hesapla
    results = db.query(
        func.strftime('%Y-%m', semalar.Fatura.tarih).label('ay_yil'),
        func.sum(case((semalar.Fatura.tip == "SATIŞ", semalar.Fatura.toplam_kdv_dahil), else_=0)).label('toplam_satis_geliri'),
        func.sum(case((semalar.Fatura.tip == "SATIŞ", semalar.FaturaKalemi.alis_fiyati_fatura_aninda * semalar.FaturaKalemi.miktar), else_=0)).label('satilan_malin_maliyeti')
    ). \
        join(semalar.FaturaKalemi, semalar.Fatura.id == semalar.FaturaKalemi.fatura_id). \
        filter(semalar.Fatura.tarih >= baslangic_tarihi, semalar.Fatura.tarih <= bitis_tarihi). \
        group_by('ay_yil').order_by('ay_yil').all()

    return [
        {
            "ay_yil": r.ay_yil,
            "toplam_satis_geliri": r.toplam_satis_geliri,
            "satilan_malin_maliyeti": r.satilan_malin_maliyeti
        } for r in results
    ]

@router.get("/nakit_akis/detayli_rapor")
def get_nakit_akis_verileri_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        semalar.GelirGider.tarih,
        semalar.GelirGider.tip,
        semalar.GelirGider.tutar,
        semalar.GelirGider.aciklama,
        semalar.KasaBanka.hesap_adi.label('hesap_adi'),
        semalar.GelirGider.kaynak
    ). \
        outerjoin(semalar.KasaBanka, semalar.KasaBanka.id == semalar.GelirGider.kasa_banka_id)

    if baslangic_tarihi:
        query = query.filter(semalar.GelirGider.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.GelirGider.tarih <= bitis_tarihi)

    results = query.order_by(semalar.GelirGider.tarih).all()
    return [
        {
            "tarih": r.tarih,
            "tip": r.tip,
            "tutar": r.tutar,
            "aciklama": r.aciklama,
            "hesap_adi": r.hesap_adi,
            "kaynak": r.kaynak
        } for r in results
    ]

@router.get("/nakit_akis/aylik_ozet")
def get_monthly_cash_flow_summary_endpoint(
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    db: Session = Depends(get_db)
):
    if baslangic_tarihi is None:
        baslangic_tarihi = date(date.today().year, 1, 1)
    if bitis_tarihi is None:
        bitis_tarihi = date.today()

    results = db.query(
        func.strftime('%Y-%m', semalar.GelirGider.tarih).label('ay_yil'),
        func.sum(case((semalar.GelirGider.tip == "GELİR", semalar.GelirGider.tutar), else_=0)).label('toplam_giris'),
        func.sum(case((semalar.GelirGider.tip == "GİDER", semalar.GelirGider.tutar), else_=0)).label('toplam_cikis')
    ). \
        filter(semalar.GelirGider.tarih >= baslangic_tarihi, semalar.GelirGider.tarih <= bitis_tarihi). \
        group_by('ay_yil').order_by('ay_yil').all()

    return [
        {
            "ay_yil": r.ay_yil,
            "toplam_giris": r.toplam_giris,
            "toplam_cikis": r.toplam_cikis
        } for r in results
    ]

@router.get("/kasalar_bankalar/toplam_bakiyeler")
def get_tum_kasa_banka_bakiyeleri_endpoint(db: Session = Depends(get_db)):
    # KasaBanka tablosunda bakiye alanı varsa doğrudan çekilir.
    # Eğer bakiye CariHareketler veya GelirGider hareketlerinden hesaplanıyorsa, sorgu daha karmaşık olur.
    # Semalar.KasaBanka'da bakiye alanı olduğunu varsayıyoruz.
    results = db.query(semalar.KasaBanka.id, semalar.KasaBanka.hesap_adi, semalar.KasaBanka.bakiye, semalar.KasaBanka.tip).all()
    return [
        {"id": r.id, "hesap_adi": r.hesap_adi, "bakiye": r.bakiye, "tip": r.tip} for r in results
    ]

@router.get("/cariler/yaslandirma")
def get_cari_yaslandirma_verileri_endpoint(
    tarih: Optional[date] = None,
    db: Session = Depends(get_db)
):
    if tarih is None:
        tarih = date.today()

    musteri_alacaklari = {
        "0-30": [], "31-60": [], "61-90": [], "91+": []
    }
    tedarikci_borclari = {
        "0-30": [], "31-60": [], "61-90": [], "91+": []
    }

    # Müşteri alacakları için sorgu
    musteri_query = db.query(semalar.Musteri).all()
    for musteri in musteri_query:
        # Her müşterinin net bakiyesi ve vadesi geçmiş alacakları hesaplanmalı.
        # Bu, CariHareketler tablosu üzerinden daha detaylı bir iş mantığı gerektirir.
        # Basitlik adına, sadece örnek veri döndürelim veya CariHareketler'den gerçek hesaplama yapalım.

        # Müşteri için toplam borç (alacak) hareketleri
        borc_sorgu = db.query(func.sum(semalar.CariHareket.tutar)).\
            filter(semalar.CariHareket.cari_id == musteri.id,
                   semalar.CariHareket.cari_tipi == "MUSTERI",
                   semalar.CariHareket.islem_tipi.in_(["SATIŞ", "VERESIYE_BORC"])).scalar() or 0

        # Müşteri için toplam alacak (tahsilat) hareketleri
        alacak_sorgu = db.query(func.sum(semalar.CariHareket.tutar)).\
            filter(semalar.CariHareket.cari_id == musteri.id,
                   semalar.CariHareket.cari_tipi == "MUSTERI",
                   semalar.CariHareket.islem_tipi.in_(["TAHSILAT", "ALACAK"])).scalar() or 0

        net_bakiye = borc_sorgu - alacak_sorgu

        if net_bakiye > 0: # Müşteri bize borçluysa (alacak)
            # Vadesi geçen gün hesaplaması (Fatura veya Siparişten)
            # Bu kısım çok basitleştirilmiştir. Her bir faturanın/siparişin vadesi kontrol edilmeli.
            # Şimdilik, sadece bir yaşlandırma grubuna ekleyelim.
            vadesi_gecmis_gun = (tarih - musteri.son_islem_tarihi).days if hasattr(musteri, 'son_islem_tarihi') and musteri.son_islem_tarihi else 0 # Örnek

            if 0 <= vadesi_gecmis_gun <= 30:
                musteri_alacaklari["0-30"].append({"cari_adi": musteri.ad_soyad, "tutar": net_bakiye, "vadesi_gecen_gun": vadesi_gecmis_gun})
            elif 31 <= vadesi_gecmis_gun <= 60:
                musteri_alacaklari["31-60"].append({"cari_adi": musteri.ad_soyad, "tutar": net_bakiye, "vadesi_gecen_gun": vadesi_gecmis_gun})
            elif 61 <= vadesi_gecmis_gun <= 90:
                musteri_alacaklari["61-90"].append({"cari_adi": musteri.ad_soyad, "tutar": net_bakiye, "vadesi_gecen_gun": vadesi_gecmis_gun})
            elif vadesi_gecmis_gun > 90:
                musteri_alacaklari["91+"].append({"cari_adi": musteri.ad_soyad, "tutar": net_bakiye, "vadesi_gecen_gun": vadesi_gecmis_gun})

    # Tedarikçi borçları için sorgu (benzer mantık)
    tedarikci_query = db.query(semalar.Tedarikci).all()
    for tedarikci in tedarikci_query:
        borc_sorgu = db.query(func.sum(semalar.CariHareket.tutar)).\
            filter(semalar.CariHareket.cari_id == tedarikci.id,
                   semalar.CariHareket.cari_tipi == "TEDARIKCI",
                   semalar.CariHareket.islem_tipi.in_(["ALIŞ", "VERESIYE_BORC"])).scalar() or 0

        alacak_sorgu = db.query(func.sum(semalar.CariHareket.tutar)).\
            filter(semalar.CariHareket.cari_id == tedarikci.id,
                   semalar.CariHareket.cari_tipi == "TEDARIKCI",
                   semalar.CariHareket.islem_tipi.in_(["ODEME", "ALACAK"])).scalar() or 0

        net_bakiye = borc_sorgu - alacak_sorgu

        if net_bakiye < 0: # Biz tedarikçiye borçluysak (borç)
            vadesi_gecmis_gun = (tarih - tedarikci.son_islem_tarihi).days if hasattr(tedarikci, 'son_islem_tarihi') and tedarikci.son_islem_tarihi else 0

            if 0 <= vadesi_gecmis_gun <= 30:
                tedarikci_borclari["0-30"].append({"cari_adi": tedarikci.ad_soyad, "tutar": abs(net_bakiye), "vadesi_gecen_gun": vadesi_gecmis_gun})
            elif 31 <= vadesi_gecmis_gun <= 60:
                tedarikci_borclari["31-60"].append({"cari_adi": tedarikci.ad_soyad, "tutar": abs(net_bakiye), "vadesi_gecen_gun": vadesi_gecmis_gun})
            elif 61 <= vadesi_gecmis_gun <= 90:
                tedarikci_borclari["61-90"].append({"cari_adi": tedarikci.ad_soyad, "tutar": abs(net_bakiye), "vadesi_gecen_gun": vadesi_gecmis_gun})
            elif vadesi_gecmis_gun > 90:
                tedarikci_borclari["91+"].append({"cari_adi": tedarikci.ad_soyad, "tutar": abs(net_bakiye), "vadesi_gecen_gun": vadesi_gecmis_gun})

    return {"musteri_alacaklari": musteri_alacaklari, "tedarikci_borclari": tedarikci_borclari}

@router.get("/stoklar/kategoriye_gore_deger")
def get_stock_value_by_category_endpoint(db: Session = Depends(get_db)):
    results = db.query(
        semalar.Kategori.kategori_adi,
        func.sum(semalar.Stok.stok_miktari * semalar.Stok.alis_fiyati_kdv_dahil).label('toplam_deger')
    ). \
        join(semalar.Stok, semalar.Stok.kategori_id == semalar.Kategori.id). \
        group_by(semalar.Kategori.kategori_adi).all()

    return [{"kategori_adi": r.kategori_adi, "toplam_deger": r.toplam_deger} for r in results]