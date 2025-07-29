from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract, case, String
from datetime import date, datetime, timedelta # datetime eklendi
from typing import Optional
from fastapi.responses import FileResponse
from .. import modeller, semalar
from ..veritabani import get_db
from .musteriler import calculate_cari_net_bakiye
from .tedarikciler import calculate_cari_net_bakiye as calculate_tedarikci_net_bakiye
import openpyxl # openpyxl import edildi
import os # os modülü import edildi

router = APIRouter(prefix="/raporlar", tags=["Raporlar"])

# Raporların saklanacağı dizin (uygulamanın kök dizininde 'server_reports' klasörü)
REPORTS_DIR = "server_reports"
os.makedirs(REPORTS_DIR, exist_ok=True) # Dizin yoksa oluştur

@router.get("/dashboard_ozet", response_model=modeller.PanoOzetiYanit)
def get_dashboard_ozet_endpoint(
    baslangic_tarihi: date = Query(None, description="Başlangıç tarihi (YYYY-MM-DD)"),
    bitis_tarihi: date = Query(None, description="Bitiş tarihi (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    query_fatura = db.query(semalar.Fatura)
    query_gelir_gider = db.query(semalar.GelirGider)
    query_stok = db.query(semalar.Stok)

    if baslangic_tarihi:
        query_fatura = query_fatura.filter(semalar.Fatura.tarih >= baslangic_tarihi)
        query_gelir_gider = query_gelir_gider.filter(semalar.GelirGider.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query_fatura = query_fatura.filter(semalar.Fatura.tarih <= bitis_tarihi)
        query_gelir_gider = query_gelir_gider.filter(semalar.GelirGider.tarih <= bitis_tarihi)

    toplam_satislar = query_fatura.filter(semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS).with_entities(func.sum(semalar.Fatura.genel_toplam)).scalar() or 0.0
    toplam_alislar = query_fatura.filter(semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS).with_entities(func.sum(semalar.Fatura.genel_toplam)).scalar() or 0.0
    toplam_tahsilatlar = query_gelir_gider.filter(semalar.GelirGider.tip == semalar.GelirGiderTipEnum.GELIR).with_entities(func.sum(semalar.GelirGider.tutar)).scalar() or 0.0
    toplam_odemeler = query_gelir_gider.filter(semalar.GelirGider.tip == semalar.GelirGiderTipEnum.GIDER).with_entities(func.sum(semalar.GelirGider.tutar)).scalar() or 0.0

    en_cok_satan_urunler_query = db.query(
        semalar.Stok.ad,
        func.sum(semalar.FaturaKalemi.miktar).label('toplam_miktar')
    ).join(
        semalar.FaturaKalemi, semalar.Stok.id == semalar.FaturaKalemi.urun_id
    ).join(
        semalar.Fatura, semalar.FaturaKalemi.fatura_id == semalar.Fatura.id
    ).filter(
        semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS
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
        {"ad": item.ad, "toplam_miktar": float(item.toplam_miktar or 0.0)} for item in en_cok_satan_urunler
    ]

    kritik_stok_sayisi = query_stok.filter(
        semalar.Stok.aktif == True,
        semalar.Stok.miktar <= semalar.Stok.min_stok_seviyesi
    ).count()

    today = date.today()
    vadesi_yaklasan_alacaklar_toplami = db.query(func.sum(semalar.Fatura.genel_toplam)).filter(
        semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS,
        semalar.Fatura.odeme_turu.cast(String) == semalar.OdemeTuruEnum.ACIK_HESAP.value, # Filtre güncellendi
        semalar.Fatura.vade_tarihi >= today,
        semalar.Fatura.vade_tarihi <= (today + timedelta(days=30))
    ).scalar() or 0.0

    vadesi_gecmis_borclar_toplami = db.query(func.sum(semalar.Fatura.genel_toplam)).filter(
        semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS,
        semalar.Fatura.odeme_turu.cast(String) == semalar.OdemeTuruEnum.ACIK_HESAP.value, # Filtre güncellendi
        semalar.Fatura.vade_tarihi < today
    ).scalar() or 0.0


    return {
        "toplam_satislar": toplam_satislar,
        "toplam_alislar": toplam_alislar,
        "toplam_tahsilatlar": toplam_tahsilatlar,
        "toplam_odemeler": toplam_odemeler,
        "kritik_stok_sayisi": kritik_stok_sayisi,
        "en_cok_satan_urunler": formatted_top_sellers,
        "vadesi_yaklasan_alacaklar_toplami": vadesi_yaklasan_alacaklar_toplami,
        "vadesi_gecmis_borclar_toplami": vadesi_gecmis_borclar_toplami
    }

@router.get("/satislar_detayli_rapor", response_model=modeller.FaturaListResponse)
def get_satislar_detayli_rapor_endpoint(
    baslangic_tarihi: date = Query(..., description="YYYY-MM-DD formatında başlangıç tarihi"),
    bitis_tarihi: date = Query(..., description="YYYY-MM-DD formatında bitiş tarihi"),
    cari_id: int = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Fatura).filter(
        semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS,
        semalar.Fatura.tarih >= baslangic_tarihi,
        semalar.Fatura.tarih <= bitis_tarihi
    ).order_by(semalar.Fatura.tarih.desc())

    if cari_id:
        query = query.filter(semalar.Fatura.cari_id == cari_id)
    
    total_count = query.count()
    faturalar = query.all() # Tümünü çek, pagination rapor için uygun olmayabilir

    return {"items": [modeller.FaturaRead.model_validate(fatura, from_attributes=True) for fatura in faturalar], "total": total_count}

@router.post("/generate_satis_raporu_excel", status_code=status.HTTP_200_OK)
def generate_tarihsel_satis_raporu_excel_endpoint(
    baslangic_tarihi: date = Query(..., description="Başlangıç tarihi (YYYY-MM-DD)"),
    bitis_tarihi: date = Query(..., description="Bitiş tarihi (YYYY-MM-DD)"),
    cari_id: Optional[int] = Query(None, description="Opsiyonel Cari ID"),
    db: Session = Depends(get_db)
):
    try:
        # Step 1: Get data (similar to get_satislar_detayli_rapor_endpoint)
        query = db.query(semalar.Fatura).filter(
            semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS,
            semalar.Fatura.tarih >= baslangic_tarihi,
            semalar.Fatura.tarih <= bitis_tarihi
        ).order_by(semalar.Fatura.tarih.desc())

        if cari_id:
            query = query.filter(semalar.Fatura.cari_id == cari_id)
        
        faturalar = query.all()
        
        # We also need FaturaKalemleri data for detailed sales report
        # This requires joining or iterating to get kalemler for each fatura.
        # For simplicity in this step, let's assume `get_satislar_detayli_rapor_endpoint`
        # returns data in a way that can be directly used, or we fetch kalemler here.
        # Let's adjust to fetch kalemler here as per the original `tarihsel_satis_raporu_excel_olustur`'s expectation of detailed items.
        
        # Reusing the logic from `get_satislar_detayli_rapor_endpoint` but getting actual data
        detailed_sales_data_response = modeller.FaturaListResponse(
            items=[modeller.FaturaRead.model_validate(fatura, from_attributes=True) for fatura in faturalar],
            total=len(faturalar)
        )
        detailed_sales_data = detailed_sales_data_response.items # This is a list of FaturaRead objects

        if not detailed_sales_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Belirtilen tarih aralığında satış faturası bulunamadı.")

        # Step 2: Create Excel file using openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Satış Raporu"

        # Headers
        headers = [
            "Fatura No", "Tarih", "Cari Adı", "Ürün Kodu", "Ürün Adı", "Miktar", 
            "Birim Fiyat", "KDV (%)", "İskonto 1 (%)", "İskonto 2 (%)", "Uygulanan İskonto Tutarı", 
            "Kalem Toplam (KDV Dahil)", "Fatura Genel Toplam (KDV Dahil)", "Ödeme Türü"
        ]
        ws.append(headers)

        # Data rows
        for fatura_item in detailed_sales_data:
            # Fetch kalemler for each fatura
            kalemler = db.query(semalar.FaturaKalemi).filter(semalar.FaturaKalemi.fatura_id == fatura_item.id).all()
            
            # Populate basic fatura info
            fatura_no = fatura_item.fatura_no
            tarih = fatura_item.tarih.strftime("%Y-%m-%d") if isinstance(fatura_item.tarih, date) else str(fatura_item.tarih)
            cari_adi = fatura_item.cari_adi if fatura_item.cari_adi else "N/A"
            genel_toplam_fatura = fatura_item.genel_toplam
            odeme_turu = fatura_item.odeme_turu.value if hasattr(fatura_item.odeme_turu, 'value') else str(fatura_item.odeme_turu) # Enum'sa .value al

            for kalem in kalemler:
                # Get product info from Stok table for code and name
                urun = db.query(semalar.Stok).filter(semalar.Stok.id == kalem.urun_id).first()
                urun_kodu = urun.kod if urun else "N/A"
                urun_adi = urun.ad if urun else "N/A"

                # Calculate item totals (re-calculate to be safe)
                birim_fiyat_kdv_dahil_kalem_orig = kalem.birim_fiyat * (1 + kalem.kdv_orani / 100)
                iskontolu_birim_fiyat_kdv_dahil = birim_fiyat_kdv_dahil_kalem_orig * (1 - kalem.iskonto_yuzde_1 / 100) * (1 - kalem.iskonto_yuzde_2 / 100)
                uygulanan_iskonto_tutari = (birim_fiyat_kdv_dahil_kalem_orig - iskontolu_birim_fiyat_kdv_dahil) * kalem.miktar
                kalem_toplam_kdv_dahil = iskontolu_birim_fiyat_kdv_dahil * kalem.miktar

                row_data = [
                    fatura_no, tarih, cari_adi, urun_kodu, urun_adi, kalem.miktar,
                    iskontolu_birim_fiyat_kdv_dahil, kalem.kdv_orani, kalem.iskonto_yuzde_1, 
                    kalem.iskonto_yuzde_2, uygulanan_iskonto_tutari, kalem_toplam_kdv_dahil,
                    genel_toplam_fatura, odeme_turu
                ]
                ws.append(row_data)

        # Step 3: Save the Excel file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"satis_raporu_{timestamp}.xlsx"
        filepath = os.path.join(REPORTS_DIR, filename)
        wb.save(filepath)

        return {"message": f"Satış raporu başarıyla oluşturuldu: {filename}", "filepath": filepath}
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Rapor oluşturulurken beklenmedik bir hata oluştu: {e}")

@router.get("/kar_zarar_verileri", response_model=modeller.KarZararResponse)
def get_kar_zarar_verileri_endpoint(
    baslangic_tarihi: date = Query(..., description="YYYY-MM-DD formatında başlangıç tarihi"),
    bitis_tarihi: date = Query(..., description="YYYY-MM-DD formatında bitiş tarihi"),
    db: Session = Depends(get_db)
):
    # Toplam Satış Geliri
    toplam_satis_geliri = db.query(func.sum(semalar.Fatura.genel_toplam)).filter( # genel_toplam yerine toplam_kdv_dahil kullanıldı
        semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS,
        semalar.Fatura.tarih >= baslangic_tarihi,
        semalar.Fatura.tarih <= bitis_tarihi
    ).scalar() or 0.0

    # Toplam Satış Maliyeti (satılan ürünlerin alış maliyeti)
    # Her fatura kalemindeki ürünün alış fiyatı ile miktarını çarpıp topluyoruz
    toplam_satis_maliyeti = db.query(
        func.sum(semalar.FaturaKalemi.miktar * semalar.FaturaKalemi.alis_fiyati_fatura_aninda) # semalar.Stok.alis_fiyati_kdv_dahil yerine FaturaKalemi.alis_fiyati_fatura_aninda
    ).join(semalar.Fatura, semalar.FaturaKalemi.fatura_id == semalar.Fatura.id) \
     .filter(
         semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS,
         semalar.Fatura.tarih >= baslangic_tarihi,
         semalar.Fatura.tarih <= bitis_tarihi
     ).scalar() or 0.0

    # Toplam Alış Gideri
    toplam_alis_gideri = db.query(func.sum(semalar.Fatura.genel_toplam)).filter( # genel_toplam yerine toplam_kdv_dahil kullanıldı
        semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS,
        semalar.Fatura.tarih >= baslangic_tarihi,
        semalar.Fatura.tarih <= bitis_tarihi
    ).scalar() or 0.0

    # Diğer Gelirler
    diger_gelirler = db.query(func.sum(semalar.GelirGider.tutar)).filter(
        semalar.GelirGider.tip == semalar.GelirGiderTipEnum.GELIR, # islem_turu yerine tip kullanıldı
        semalar.GelirGider.tarih >= baslangic_tarihi,
        semalar.GelirGider.tarih <= bitis_tarihi
    ).scalar() or 0.0

    # Diğer Giderler
    diger_giderler = db.query(func.sum(semalar.GelirGider.tutar)).filter(
        semalar.GelirGider.tip == semalar.GelirGiderTipEnum.GIDER, # islem_turu yerine tip kullanıldı
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
        semalar.KasaBankaHareket.islem_yone == semalar.IslemYoneEnum.GIRIS, # Enum kullanıldı
        semalar.KasaBankaHareket.tarih >= baslangic_tarihi,
        semalar.KasaBankaHareket.tarih <= bitis_tarihi
    ).scalar() or 0.0

    # Bu ayki çıkışlar (ödemeler, alış faturalarından giden nakit/banka)
    nakit_cikislar = db.query(func.sum(semalar.KasaBankaHareket.tutar)).filter(
        semalar.KasaBankaHareket.islem_yone == semalar.IslemYoneEnum.CIKIS, # Enum kullanıldı
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
        net_bakiye = calculate_cari_net_bakiye(db, musteri.id, semalar.CariTipiEnum.MUSTERI) # Enum kullanıldı
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
        net_bakiye = calculate_tedarikci_net_bakiye(db, tedarikci.id, semalar.CariTipiEnum.TEDARIKCI) # Enum kullanıldı
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
    # Stok.alis_fiyati_kdv_dahil alanı kaldırıldı, alis_fiyati üzerinden devam edilecek
    toplam_stok_maliyeti = db.query(
        func.sum(semalar.Stok.miktar * semalar.Stok.alis_fiyati) # alis_fiyati_kdv_dahil yerine alis_fiyati
    ).filter(semalar.Stok.aktif == True).scalar() or 0.0

    return {
        "toplam_stok_maliyeti": toplam_stok_maliyeti
    }

@router.get("/download_report/{filename}", status_code=status.HTTP_200_OK)
async def download_report_excel_endpoint(filename: str, db: Session = Depends(get_db)):
    filepath = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rapor dosyası bulunamadı.")
    
    # Return the file directly
    return FileResponse(path=filepath, filename=filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@router.get("/gelir_gider_aylik_ozet", response_model=modeller.GelirGiderAylikOzetResponse)
def get_gelir_gider_aylik_ozet_endpoint(
    yil: int = Query(..., ge=2000, le=date.today().year),
    db: Session = Depends(get_db)
):
    gelir_gider_ozet = db.query(
        extract('month', semalar.GelirGider.tarih).label('ay'),
        func.sum(case((semalar.GelirGider.tip == semalar.GelirGiderTipEnum.GELIR, semalar.GelirGider.tutar), else_=0)).label('toplam_gelir'), # islem_turu yerine tip kullanıldı
        func.sum(case((semalar.GelirGider.tip == semalar.GelirGiderTipEnum.GIDER, semalar.GelirGider.tutar), else_=0)).label('toplam_gider') # islem_turu yerine tip kullanıldı
    ).filter(extract('year', semalar.GelirGider.tarih) == yil) \
     .group_by(extract('month', semalar.GelirGider.tarih)) \
     .order_by(extract('month', semalar.GelirGider.tarih)) \
     .all()

    aylik_data = []
    for i in range(1, 13): # 1'den 12'ye kadar her ay için veri oluştur
        # Ay adını alırken Türkçe locale sorunları olabileceği için manuel bir liste tercih edilebilir
        # Şimdilik strftime kullanmaya devam edelim
        ay_adlari_dict = {
            1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
            7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
        }
        ay_adi = ay_adlari_dict.get(i, f"{i}. Ay") # Türkçe ay adları için güncellendi
        
        gelir = next((item.toplam_gelir for item in gelir_gider_ozet if item.ay == i), 0.0)
        gider = next((item.toplam_gider for item in gelir_gider_ozet if item.ay == i), 0.0)
        aylik_data.append({
            "ay": i,
            "ay_adi": ay_adi,
            "toplam_gelir": gelir,
            "toplam_gider": gider
        })
    
    return {"aylik_ozet": aylik_data}