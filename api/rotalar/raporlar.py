from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract, case
from datetime import date, timedelta
from .. import modeller, semalar
from ..veritabani import get_db
from .musteriler import calculate_cari_net_bakiye # Musteriler router'dan helper fonksiyonu import et
from .tedarikciler import calculate_cari_net_bakiye as calculate_tedarikci_net_bakiye # Tedarikciler router'dan helper fonksiyonu import et

router = APIRouter(prefix="/raporlar", tags=["Raporlar"])

@router.get("/dashboard_ozet", response_model=modeller.DashboardSummary)
def get_dashboard_ozet_endpoint(db: Session = Depends(get_db)):
    today = date.today()
    start_of_month = today.replace(day=1)

    # Toplam Satışlar (Bu Ay)
    toplam_satislar = db.query(func.sum(semalar.Fatura.genel_toplam)).filter(
        semalar.Fatura.fatura_turu == "SATIŞ",
        semalar.Fatura.tarih >= start_of_month,
        semalar.Fatura.tarih <= today
    ).scalar() or 0.0

    # Toplam Alışlar (Bu Ay)
    toplam_alislar = db.query(func.sum(semalar.Fatura.genel_toplam)).filter(
        semalar.Fatura.fatura_turu == "ALIŞ",
        semalar.Fatura.tarih >= start_of_month,
        semalar.Fatura.tarih <= today
    ).scalar() or 0.0

    # Toplam Tahsilatlar (Bu Ay)
    toplam_tahsilatlar = db.query(func.sum(semalar.GelirGider.tutar)).filter(
        semalar.GelirGider.islem_turu == "GELIR",
        semalar.GelirGider.tarih >= start_of_month,
        semalar.GelirGider.tarih <= today
    ).scalar() or 0.0

    # Toplam Ödemeler (Bu Ay)
    toplam_odemeler = db.query(func.sum(semalar.GelirGider.tutar)).filter(
        semalar.GelirGider.islem_turu == "GIDER",
        semalar.GelirGider.tarih >= start_of_month,
        semalar.GelirGider.tarih <= today
    ).scalar() or 0.0

    # Kritik Stok Altındaki Ürün Sayısı
    kritik_stok_urun_sayisi = db.query(semalar.Stok).filter(
        semalar.Stok.miktar < semalar.Stok.kritik_stok_seviyesi
    ).count()

    # En Çok Satan Ürünler (Bu Ay - ilk 5)
    en_cok_satan_urunler = db.query(
        semalar.Stok.ad,
        func.sum(semalar.FaturaKalemi.miktar).label("toplam_miktar")
    ).join(semalar.FaturaKalemi, semalar.Stok.id == semalar.FaturaKalemi.urun_id) \
     .join(semalar.Fatura, semalar.FaturaKalemi.fatura_id == semalar.Fatura.id) \
     .filter(
         semalar.Fatura.fatura_turu == "SATIŞ",
         semalar.Fatura.tarih >= start_of_month,
         semalar.Fatura.tarih <= today
     ).group_by(semalar.Stok.ad) \
     .order_by(func.sum(semalar.FaturaKalemi.miktar).desc()) \
     .limit(5).all()
    
    # Vadesi Yaklaşan Alacaklar (Son 7 gün içinde vadesi gelen, henüz ödenmemiş faturalar)
    # Bu daha çok CariHareketler'den çekilmeli veya Faturaların ödeme durumu izlenmeli
    # Basit bir örnek olarak: henüz ödenmemiş satış faturaları
    vadesi_yaklasan_alacaklar_toplami = db.query(func.sum(semalar.Fatura.genel_toplam)).filter(
        semalar.Fatura.fatura_turu == "SATIŞ",
        semalar.Fatura.durum != "Ödendi", # Varsayımsal durum alanı
        semalar.Fatura.vade_tarihi >= today,
        semalar.Fatura.vade_tarihi <= (today + timedelta(days=7))
    ).scalar() or 0.0

    # Vadesi Geçmiş Borçlar (7 günden fazla vadesi geçmiş, henüz ödenmemiş alış faturaları)
    # Basit bir örnek olarak: henüz ödenmemiş alış faturaları
    vadesi_gecmis_borclar_toplami = db.query(func.sum(semalar.Fatura.genel_toplam)).filter(
        semalar.Fatura.fatura_turu == "ALIŞ",
        semalar.Fatura.durum != "Ödendi", # Varsayımsal durum alanı
        semalar.Fatura.vade_tarihi < today - timedelta(days=7)
    ).scalar() or 0.0
    
    return {
        "toplam_satislar": toplam_satislar,
        "toplam_alislar": toplam_alislar,
        "toplam_tahsilatlar": toplam_tahsilatlar,
        "toplam_odemeler": toplam_odemeler,
        "kritik_stok_urun_sayisi": kritik_stok_urun_sayisi,
        "en_cok_satan_urunler": [{"ad": urun.ad, "miktar": urun.toplam_miktar} for urun in en_cok_satan_urunler],
        "vadesi_yaklasan_alacaklar_toplami": vadesi_yaklasan_alacaklar_toplami,
        "vadesi_gecmis_borclar_toplami": vadesi_gecmis_borclar_toplami,
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