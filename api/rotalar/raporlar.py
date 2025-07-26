from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract, case
from datetime import date, timedelta
from .. import modeller, semalar
from ..veritabani import get_db
from .musteriler import calculate_cari_net_bakiye # Musteriler router'dan helper fonksiyonu import et
from .tedarikciler import calculate_cari_net_bakiye as calculate_tedarikci_net_bakiye # Tedarikciler router'dan helper fonksiyonu import et

router = APIRouter(prefix="/raporlar", tags=["Raporlar"])

# api.zip/rotalar/raporlar.py dosyası içinde get_dashboard_ozet_endpoint metodunun tamamı:
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, datetime, timedelta
from typing import Optional, List

from .. import modeller, semalar
from ..veritabani import get_db

router = APIRouter(prefix="/raporlar", tags=["Raporlar"])

@router.get("/dashboard_ozet", response_model=modeller.PanoOzetiYanit) # Düzeltildi: DashboardOzetiResponse yerine PanoOzetiYanit
def get_dashboard_ozet_endpoint(
    baslangic_tarihi: date = Query(None, description="Başlangıç tarihi (YYYY-MM-DD)"),
    bitis_tarihi: date = Query(None, description="Bitiş tarihi (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    query_fatura = db.query(semalar.Fatura)
    query_gelir_gider = db.query(semalar.GelirGider)
    query_cari_hareket = db.query(semalar.CariHareket)
    query_stok_hareket = db.query(semalar.StokHareket)
    query_stok = db.query(semalar.Stok)

    # Tarih filtrelerini uygula
    if baslangic_tarihi:
        query_fatura = query_fatura.filter(semalar.Fatura.tarih >= baslangic_tarihi)
        query_gelir_gider = query_gelir_gider.filter(semalar.GelirGider.tarih >= baslangic_tarihi)
        query_cari_hareket = query_cari_hareket.filter(semalar.CariHareket.tarih >= baslangic_tarihi)
        query_stok_hareket = query_stok_hareket.filter(semalar.StokHareket.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query_fatura = query_fatura.filter(semalar.Fatura.tarih <= bitis_tarihi)
        query_gelir_gider = query_gelir_gider.filter(semalar.GelirGider.tarih <= bitis_tarihi)
        query_cari_hareket = query_cari_hareket.filter(semalar.CariHareket.tarih <= bitis_tarihi)
        query_stok_hareket = query_stok_hareket.filter(semalar.StokHareket.tarih <= bitis_tarihi)

    # Toplam Satışlar (KDV Dahil)
    toplam_satislar = query_fatura.filter(semalar.Fatura.fatura_turu == "SATIŞ").with_entities(func.sum(semalar.Fatura.toplam_kdv_dahil)).scalar() or 0.0

    # Toplam Alışlar (KDV Dahil)
    toplam_alislar = query_fatura.filter(semalar.Fatura.fatura_turu == "ALIŞ").with_entities(func.sum(semalar.Fatura.toplam_kdv_dahil)).scalar() or 0.0

    # Toplam Tahsilatlar (Cari hareketlerden veya direkt kasa/banka girişlerinden)
    toplam_tahsilatlar = query_gelir_gider.filter(semalar.GelirGider.tip == "GELİR").with_entities(func.sum(semalar.GelirGider.tutar)).scalar() or 0.0

    # Toplam Ödemeler (Cari hareketlerden veya direkt kasa/banka çıkışlarından)
    toplam_odemeler = query_gelir_gider.filter(semalar.GelirGider.tip == "GİDER").with_entities(func.sum(semalar.GelirGider.tutar)).scalar() or 0.0

    # En Çok Satan Ürünler (miktar bazında)
    en_cok_satan_urunler_query = db.query(
        semalar.Stok.ad,
        func.sum(semalar.FaturaKalemi.miktar).label('toplam_miktar')
    ).join(
        semalar.FaturaKalemi, semalar.Stok.id == semalar.FaturaKalemi.urun_id
    ).join(
        semalar.Fatura, semalar.FaturaKalemi.fatura_id == semalar.Fatura.id
    ).filter(
        semalar.Fatura.fatura_turu == "SATIŞ"
    )
    if baslangic_tarihi:
        en_cok_satan_urunler_query = en_cok_satan_urunler_query.filter(semalar.Fatura.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        en_cok_satan_urunler_query = en_cok_satan_urunler_query.filter(semalar.Fatura.tarih <= bitis_tarihi)

    en_cok_satan_urunler = en_cok_satan_urunler_query.group_by(
        semalar.Stok.ad
    ).order_by(
        func.sum(semalar.FaturaKalemi.miktar).desc()
    ).limit(5).all()

    formatted_top_sellers = [
        {"ad": item.ad, "toplam_miktar": float(item.toplam_miktar)} for item in en_cok_satan_urunler
    ]

    # Kritik Stok Seviyesi Altındaki Ürün Sayısı
    kritik_stok_sayisi = query_stok.filter(
        semalar.Stok.aktif == True,
        semalar.Stok.miktar <= semalar.Stok.min_stok_seviyesi
    ).count()

    return {
        "toplam_satislar": toplam_satislar,
        "toplam_alislar": toplam_alislar,
        "toplam_tahsilatlar": toplam_tahsilatlar,
        "toplam_odemeler": toplam_odemeler,
        "kritik_stok_sayisi": kritik_stok_sayisi,
        "en_cok_satan_urunler": formatted_top_sellers
    }

@router.get("/satislar_detayli_rapor", response_model=modeller.FaturaListResponse)
def get_satislar_detayli_rapor_endpoint(
    baslangic_tarihi: date = Query(..., description="YYYY-MM-DD formatında başlangıç tarihi"),
    bitis_tarihi: date = Query(..., description="YYYY-MM-DD formatında bitiş tarihi"),
    cari_id: int = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Fatura).filter(
        semalar.Fatura.fatura_turu == "SATIŞ",
        semalar.Fatura.tarih >= baslangic_tarihi,
        semalar.Fatura.tarih <= bitis_tarihi
    ).order_by(semalar.Fatura.tarih.desc())

    if cari_id:
        query = query.filter(semalar.Fatura.cari_id == cari_id)
    
    total_count = query.count()
    faturalar = query.all() # Tümünü çek, pagination rapor için uygun olmayabilir

    return {"items": [modeller.FaturaRead.model_validate(fatura, from_attributes=True) for fatura in faturalar], "total": total_count}

@router.get("/kar_zarar_verileri", response_model=modeller.KarZararResponse)
def get_kar_zarar_verileri_endpoint(
    baslangic_tarihi: date = Query(..., description="YYYY-MM-DD formatında başlangıç tarihi"),
    bitis_tarihi: date = Query(..., description="YYYY-MM-DD formatında bitiş tarihi"),
    db: Session = Depends(get_db)
):
    # Toplam Satış Geliri
    toplam_satis_geliri = db.query(func.sum(semalar.Fatura.genel_toplam)).filter(
        semalar.Fatura.fatura_turu == "SATIŞ",
        semalar.Fatura.tarih >= baslangic_tarihi,
        semalar.Fatura.tarih <= bitis_tarihi
    ).scalar() or 0.0

    # Toplam Satış Maliyeti (satılan ürünlerin alış maliyeti)
    # Her fatura kalemindeki ürünün alış fiyatı ile miktarını çarpıp topluyoruz
    toplam_satis_maliyeti = db.query(
        func.sum(semalar.FaturaKalemi.miktar * semalar.Stok.alis_fiyati_kdv_dahil)
    ).join(semalar.Fatura, semalar.FaturaKalemi.fatura_id == semalar.Fatura.id) \
     .join(semalar.Stok, semalar.FaturaKalemi.urun_id == semalar.Stok.id) \
     .filter(
         semalar.Fatura.fatura_turu == "SATIŞ",
         semalar.Fatura.tarih >= baslangic_tarihi,
         semalar.Fatura.tarih <= bitis_tarihi
     ).scalar() or 0.0

    # Toplam Alış Gideri
    toplam_alis_gideri = db.query(func.sum(semalar.Fatura.genel_toplam)).filter(
        semalar.Fatura.fatura_turu == "ALIŞ",
        semalar.Fatura.tarih >= baslangic_tarihi,
        semalar.Fatura.tarih <= bitis_tarihi
    ).scalar() or 0.0

    # Diğer Gelirler
    diger_gelirler = db.query(func.sum(semalar.GelirGider.tutar)).filter(
        semalar.GelirGider.islem_turu == "GELIR",
        semalar.GelirGider.kategori != "Hızlı Gelir", # Fatura dışı gelirleri al
        semalar.GelirGider.tarih >= baslangic_tarihi,
        semalar.GelirGider.tarih <= bitis_tarihi
    ).scalar() or 0.0

    # Diğer Giderler
    diger_giderler = db.query(func.sum(semalar.GelirGider.tutar)).filter(
        semalar.GelirGider.islem_turu == "GIDER",
        semalar.GelirGider.kategori != "Hızlı Gider", # Fatura dışı giderleri al
        semalar.GelirGider.tarih >= baslangic_tarihi,
        semalar.GelirGider.tarih <= bitis_tarihi
    ).scalar() or 0.0

    brut_kar = toplam_satis_geliri - toplam_satis_maliyeti
    net_kar = brut_kar + diger_gelirler - diger_giderler - toplam_alis_gideri # Basit bir kar/zarar hesabı

    return {
        "toplam_satis_geliri": toplam_satis_geliri,
        "toplam_satis_maliyeti": toplam_satis_maliyeti,
        "toplam_alis_gideri": toplam_alis_gideri,
        "diger_gelirler": diger_gelirler,
        "diger_giderler": diger_giderler,
        "brut_kar": brut_kar,
        "net_kar": net_kar
    }

@router.get("/nakit_akisi_raporu", response_model=modeller.NakitAkisiResponse)
def get_nakit_akisi_raporu_endpoint(
    baslangic_tarihi: date = Query(..., description="YYYY-MM-DD formatında başlangıç tarihi"),
    bitis_tarihi: date = Query(..., description="YYYY-MM-DD formatında bitiş tarihi"),
    db: Session = Depends(get_db)
):
    # Bu ayki girişler (tahsilatlar, satış faturalarından gelen nakit/banka)
    nakit_girisleri = db.query(func.sum(semalar.KasaBankaHareket.tutar)).filter(
        semalar.KasaBankaHareket.islem_yone == "GIRIS",
        semalar.KasaBankaHareket.tarih >= baslangic_tarihi,
        semalar.KasaBankaHareket.tarih <= bitis_tarihi
    ).scalar() or 0.0

    # Bu ayki çıkışlar (ödemeler, alış faturalarından giden nakit/banka)
    nakit_cikislar = db.query(func.sum(semalar.KasaBankaHareket.tutar)).filter(
        semalar.KasaBankaHareket.islem_yone == "ÇIKIŞ",
        semalar.KasaBankaHareket.tarih >= baslangic_tarihi,
        semalar.KasaBankaHareket.tarih <= bitis_tarihi
    ).scalar() or 0.0

    net_nakit_akisi = nakit_girisleri - nakit_cikislar

    return {
        "nakit_girisleri": nakit_girisleri,
        "nakit_cikislar": nakit_cikislar,
        "net_nakit_akisi": net_nakit_akisi
    }

@router.get("/cari_yaslandirma_raporu", response_model=modeller.CariYaslandirmaResponse)
def get_cari_yaslandirma_verileri_endpoint(db: Session = Depends(get_db)):
    today = date.today()
    
    musteri_alacaklar = []
    tedarikci_borclar = []

    # Tüm aktif müşterileri al
    musteriler = db.query(semalar.Musteri).filter(semalar.Musteri.aktif == True).all()
    for musteri in musteriler:
        net_bakiye = calculate_cari_net_bakiye(db, musteri.id, "MUSTERI")
        if net_bakiye > 0: # Müşteriden alacaklıysak
            musteri_alacaklar.append({
                "cari_id": musteri.id,
                "cari_ad": musteri.ad,
                "bakiye": net_bakiye,
                "vade_tarihi": None # Bu rapor için faturaların vade tarihi çekilmeli
            })
    
    # Tüm aktif tedarikçileri al
    tedarikciler = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.aktif == True).all()
    for tedarikci in tedarikciler:
        net_bakiye = calculate_tedarikci_net_bakiye(db, tedarikci.id, "TEDARIKCI")
        if net_bakiye < 0: # Tedarikçiye borçluysak (bakiye eksi)
            tedarikci_borclar.append({
                "cari_id": tedarikci.id,
                "cari_ad": tedarikci.ad,
                "bakiye": abs(net_bakiye), # Borç pozitif gösterilsin
                "vade_tarihi": None # Bu rapor için faturaların vade tarihi çekilmeli
            })
    
    # Daha detaylı yaşlandırma için faturaların vade tarihleri ve ödenen miktarları takip edilmelidir.
    # Bu implementasyon, sadece net bakiyeyi kullanarak basit bir özet sunar.
    # Gerçek yaşlandırma raporları için `CariHareket` ve `Fatura` tablolarının detaylı analizi gereklidir.

    return {
        "musteri_alacaklar": musteri_alacaklar,
        "tedarikci_borclar": tedarikci_borclar
    }

@router.get("/stok_deger_raporu", response_model=modeller.StokDegerResponse)
def get_stok_envanter_ozet_endpoint(db: Session = Depends(get_db)):
    toplam_stok_maliyeti = db.query(
        func.sum(semalar.Stok.miktar * semalar.Stok.alis_fiyati_kdv_dahil)
    ).filter(semalar.Stok.aktif == True).scalar() or 0.0

    return {
        "toplam_stok_maliyeti": toplam_stok_maliyeti
    }

@router.get("/gelir_gider_aylik_ozet", response_model=modeller.GelirGiderAylikOzetResponse)
def get_gelir_gider_aylik_ozet_endpoint(
    yil: int = Query(..., ge=2000, le=date.today().year),
    db: Session = Depends(get_db)
):
    gelir_gider_ozet = db.query(
        extract('month', semalar.GelirGider.tarih).label('ay'),
        func.sum(case((semalar.GelirGider.islem_turu == 'GELIR', semalar.GelirGider.tutar), else_=0)).label('toplam_gelir'),
        func.sum(case((semalar.GelirGider.islem_turu == 'GIDER', semalar.GelirGider.tutar), else_=0)).label('toplam_gider')
    ).filter(extract('year', semalar.GelirGider.tarih) == yil) \
     .group_by(extract('month', semalar.GelirGider.tarih)) \
     .order_by(extract('month', semalar.GelirGider.tarih)) \
     .all()

    aylik_data = []
    for i in range(1, 13): # 1'den 12'ye kadar her ay için veri oluştur
        ay_adi = date(yil, i, 1).strftime("%B") # Ay adını al
        gelir = next((item.toplam_gelir for item in gelir_gider_ozet if item.ay == i), 0.0)
        gider = next((item.toplam_gider for item in gelir_gider_ozet if item.ay == i), 0.0)
        aylik_data.append({
            "ay": i,
            "ay_adi": ay_adi,
            "toplam_gelir": gelir,
            "toplam_gider": gider
        })
    
    return {"aylik_ozet": aylik_data}