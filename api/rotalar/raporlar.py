from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract, case, String
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi.responses import FileResponse
from .. import modeller, semalar
from ..veritabani import get_db
from .musteriler import calculate_cari_net_bakiye
from .tedarikciler import calculate_cari_net_bakiye as calculate_tedarikci_net_bakiye
import openpyxl
import os

router = APIRouter(prefix="/raporlar", tags=["Raporlar"])

REPORTS_DIR = "server_reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

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
        semalar.Fatura.odeme_turu.cast(String) == semalar.OdemeTuruEnum.ACIK_HESAP.value,
        semalar.Fatura.vade_tarihi >= today,
        semalar.Fatura.vade_tarihi <= (today + timedelta(days=30))
    ).scalar() or 0.0

    vadesi_gecmis_borclar_toplami = db.query(func.sum(semalar.Fatura.genel_toplam)).filter(
        semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS,
        semalar.Fatura.odeme_turu.cast(String) == semalar.OdemeTuruEnum.ACIK_HESAP.value,
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
    faturalar = query.all()

    return {"items": [modeller.FaturaRead.model_validate(fatura, from_attributes=True) for fatura in faturalar], "total": total_count}

@router.post("/generate_satis_raporu_excel", status_code=status.HTTP_200_OK)
def generate_tarihsel_satis_raporu_excel_endpoint(
    baslangic_tarihi: date = Query(..., description="Başlangıç tarihi (YYYY-MM-DD)"),
    bitis_tarihi: date = Query(..., description="YYYY-MM-DD formatında bitiş tarihi"),
    cari_id: Optional[int] = Query(None, description="Opsiyonel Cari ID"),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(semalar.Fatura).filter(
            semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS,
            semalar.Fatura.tarih >= baslangic_tarihi,
            semalar.Fatura.tarih <= bitis_tarihi
        ).order_by(semalar.Fatura.tarih.desc())

        if cari_id:
            query = query.filter(semalar.Fatura.cari_id == cari_id)
        
        faturalar = query.all()
        
        detailed_sales_data_response = modeller.FaturaListResponse(
            items=[modeller.FaturaRead.model_validate(fatura, from_attributes=True) for fatura in faturalar],
            total=len(faturalar)
        )
        detailed_sales_data = detailed_sales_data_response.items

        if not detailed_sales_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Belirtilen tarih aralığında satış faturası bulunamadı.")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Satış Raporu"

        headers = [
            "Fatura No", "Tarih", "Cari Adı", "Ürün Kodu", "Ürün Adı", "Miktar", 
            "Birim Fiyat", "KDV (%)", "İskonto 1 (%)", "İskonto 2 (%)", "Uygulanan İskonto Tutarı", 
            "Kalem Toplam (KDV Dahil)", "Fatura Genel Toplam (KDV Dahil)", "Ödeme Türü"
        ]
        ws.append(headers)

        for fatura_item in detailed_sales_data:
            kalemler = db.query(semalar.FaturaKalemi).filter(semalar.FaturaKalemi.fatura_id == fatura_item.id).all()
            
            fatura_no = fatura_item.fatura_no
            tarih = fatura_item.tarih.strftime("%Y-%m-%d") if isinstance(fatura_item.tarih, date) else str(fatura_item.tarih)
            cari_adi = fatura_item.cari_adi if fatura_item.cari_adi else "N/A"
            genel_toplam_fatura = fatura_item.genel_toplam
            odeme_turu = fatura_item.odeme_turu.value if hasattr(fatura_item.odeme_turu, 'value') else str(fatura_item.odeme_turu)

            for kalem in kalemler:
                urun = db.query(semalar.Stok).filter(semalar.Stok.id == kalem.urun_id).first()
                urun_kodu = urun.kod if urun else "N/A"
                urun_adi = urun.ad if urun else "N/A"

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
    toplam_satis_geliri = db.query(func.sum(semalar.Fatura.genel_toplam)).filter(
        semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS,
        semalar.Fatura.tarih >= baslangic_tarihi,
        semalar.Fatura.tarih <= bitis_tarihi
    ).scalar() or 0.0

    toplam_satis_maliyeti = db.query(
        func.sum(semalar.FaturaKalemi.miktar * semalar.FaturaKalemi.alis_fiyati_fatura_aninda)
    ).join(semalar.Fatura, semalar.FaturaKalemi.fatura_id == semalar.Fatura.id) \
     .filter(
         semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS,
         semalar.Fatura.tarih >= baslangic_tarihi,
         semalar.Fatura.tarih <= bitis_tarihi
     ).scalar() or 0.0

    toplam_alis_gideri = db.query(func.sum(semalar.Fatura.genel_toplam)).filter(
        semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS,
        semalar.Fatura.tarih >= baslangic_tarihi,
        semalar.Fatura.tarih <= bitis_tarihi
    ).scalar() or 0.0

    diger_gelirler = db.query(func.sum(semalar.GelirGider.tutar)).filter(
        semalar.GelirGider.tip == semalar.GelirGiderTipEnum.GELIR,
        semalar.GelirGider.tarih >= baslangic_tarihi,
        semalar.GelirGider.tarih <= bitis_tarihi
    ).scalar() or 0.0

    diger_giderler = db.query(func.sum(semalar.GelirGider.tutar)).filter(
        semalar.GelirGider.tip == semalar.GelirGiderTipEnum.GIDER,
        semalar.GelirGider.tarih >= baslangic_tarihi,
        semalar.GelirGider.tarih <= bitis_tarihi
    ).scalar() or 0.0

    brut_kar = toplam_satis_geliri - toplam_satis_maliyeti
    net_kar = brut_kar + diger_gelirler - diger_giderler - toplam_alis_gideri

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
    nakit_girisleri = db.query(func.sum(semalar.KasaBankaHareket.tutar)).filter(
        semalar.KasaBankaHareket.islem_yone == semalar.IslemYoneEnum.GIRIS,
        semalar.KasaBankaHareket.tarih >= baslangic_tarihi,
        semalar.KasaBankaHareket.tarih <= bitis_tarihi
    ).scalar() or 0.0

    nakit_cikislar = db.query(func.sum(semalar.KasaBankaHareket.tutar)).filter(
        semalar.KasaBankaHareket.islem_yone == semalar.IslemYoneEnum.CIKIS,
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

    musteriler = db.query(semalar.Musteri).filter(semalar.Musteri.aktif == True).all()
    for musteri in musteriler:
        net_bakiye = calculate_cari_net_bakiye(db, musteri.id, semalar.CariTipiEnum.MUSTERI)
        if net_bakiye > 0:
            musteri_alacaklar.append({
                "cari_id": musteri.id,
                "cari_ad": musteri.ad,
                "bakiye": net_bakiye,
                "vade_tarihi": None
            })
    
    tedarikciler = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.aktif == True).all()
    for tedarikci in tedarikciler:
        net_bakiye = calculate_tedarikci_net_bakiye(db, tedarikci.id, semalar.CariTipiEnum.TEDARIKCI)
        if net_bakiye < 0:
            tedarikci_borclar.append({
                "cari_id": tedarikci.id,
                "cari_ad": tedarikci.ad,
                "bakiye": abs(net_bakiye),
                "vade_tarihi": None
            })
    
    return {
        "musteri_alacaklar": musteri_alacaklar,
        "tedarikci_borclar": tedarikci_borclar
    }

@router.get("/cari_hesap_ekstresi", response_model=modeller.CariHareketListResponse)
def get_cari_hesap_ekstresi_endpoint(
    cari_id: int = Query(..., description="Cari ID"),
    cari_turu: semalar.CariTipiEnum = Query(..., description="Cari Türü (MUSTERI veya TEDARIKCI)"),
    baslangic_tarihi: date = Query(..., description="Başlangıç tarihi (YYYY-MM-DD)"),
    bitis_tarihi: date = Query(..., description="Bitiş tarihi (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Belirtilen cari için hesap ekstresini getirir.
    """
    # Cari'nin varlığını kontrol et
    if cari_turu == semalar.CariTipiEnum.MUSTERI:
        cari_obj = db.query(semalar.Musteri).filter(semalar.Musteri.id == cari_id).first()
    else:
        cari_obj = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.id == cari_id).first()

    if not cari_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cari bulunamadı")

    # Başlangıç tarihi öncesindeki devreden bakiyeyi hesapla
    devreden_bakiye_alacak = db.query(func.sum(semalar.CariHareket.tutar)).filter(
        semalar.CariHareket.cari_id == cari_id,
        semalar.CariHareket.cari_turu == cari_turu,
        semalar.CariHareket.islem_yone == semalar.IslemYoneEnum.ALACAK,
        semalar.CariHareket.tarih < baslangic_tarihi
    ).scalar() or 0.0

    devreden_bakiye_borc = db.query(func.sum(semalar.CariHareket.tutar)).filter(
        semalar.CariHareket.cari_id == cari_id,
        semalar.CariHareket.cari_turu == cari_turu,
        semalar.CariHareket.islem_yone == semalar.IslemYoneEnum.BORC,
        semalar.CariHareket.tarih < baslangic_tarihi
    ).scalar() or 0.0

    devreden_bakiye = devreden_bakiye_borc - devreden_bakiye_alacak

    # Belirtilen tarih aralığındaki hareketleri çek
    hareketler_query = db.query(semalar.CariHareket).filter(
        semalar.CariHareket.cari_id == cari_id,
        semalar.CariHareket.cari_turu == cari_turu,
        semalar.CariHareket.tarih >= baslangic_tarihi,
        semalar.CariHareket.tarih <= bitis_tarihi
    ).order_by(semalar.CariHareket.tarih.asc(), semalar.CariHareket.id.asc())

    hareketler = hareketler_query.all()
    
    # Pydantic modellerine dönüştürme ve ilişkili verileri ekleme
    hareket_read_models = []
    for hareket in hareketler:
        hareket_model_dict = modeller.CariHareketRead.model_validate(hareket, from_attributes=True).model_dump()
        
        # Fatura bilgisi ekle
        if hareket.kaynak == semalar.KaynakTipEnum.FATURA and hareket.kaynak_id:
            fatura_obj = db.query(semalar.Fatura).filter(semalar.Fatura.id == hareket.kaynak_id).first()
            if fatura_obj:
                hareket_model_dict['fatura_no'] = fatura_obj.fatura_no
                hareket_model_dict['fatura_turu'] = fatura_obj.fatura_turu
        
        # Kasa/Banka adı ekle
        if hareket.kasa_banka_id:
            kasa_banka_obj = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == hareket.kasa_banka_id).first()
            if kasa_banka_obj:
                hareket_model_dict['kasa_banka_adi'] = kasa_banka_obj.hesap_adi

        hareket_read_models.append(hareket_model_dict)

    return {"items": hareket_read_models, "total": len(hareketler), "devreden_bakiye": devreden_bakiye}

@router.get("/stok_deger_raporu", response_model=modeller.StokDegerResponse)
def get_stok_envanter_ozet_endpoint(db: Session = Depends(get_db)):
    toplam_stok_maliyeti = db.query(
        func.sum(semalar.Stok.miktar * semalar.Stok.alis_fiyati)
    ).filter(semalar.Stok.aktif == True).scalar() or 0.0

    return {
        "toplam_stok_maliyeti": toplam_stok_maliyeti
    }

@router.get("/download_report/{filename}", status_code=status.HTTP_200_OK)
async def download_report_excel_endpoint(filename: str, db: Session = Depends(get_db)):
    filepath = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rapor dosyası bulunamadı.")
    
    return FileResponse(path=filepath, filename=filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@router.get("/gelir_gider_aylik_ozet", response_model=modeller.GelirGiderAylikOzetResponse)
def get_gelir_gider_aylik_ozet_endpoint(
    yil: int = Query(..., ge=2000, le=date.today().year),
    db: Session = Depends(get_db)
):
    gelir_gider_ozet = db.query(
        extract('month', semalar.GelirGider.tarih).label('ay'),
        func.sum(case((semalar.GelirGider.tip == semalar.GelirGiderTipEnum.GELIR, semalar.GelirGider.tutar), else_=0)).label('toplam_gelir'),
        func.sum(case((semalar.GelirGider.tip == semalar.GelirGiderTipEnum.GIDER, semalar.GelirGider.tutar), else_=0)).label('toplam_gider')
    ).filter(extract('year', semalar.GelirGider.tarih) == yil) \
     .group_by(extract('month', semalar.GelirGider.tarih)) \
     .order_by(extract('month', semalar.GelirGider.tarih)) \
     .all()

    aylik_data = []
    for i in range(1, 13):
        ay_adlari_dict = {
            1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
            7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
        }
        ay_adi = ay_adlari_dict.get(i, f"{i}. Ay")
        
        gelir = next((item.toplam_gelir for item in gelir_gider_ozet if item.ay == i), 0.0)
        gider = next((item.toplam_gider for item in gelir_gider_ozet if item.ay == i), 0.0)
        aylik_data.append({
            "ay": i,
            "ay_adi": ay_adi,
            "toplam_gelir": gelir,
            "toplam_gider": gider
        })
    
    return {"aylik_ozet": aylik_data}

@router.get("/urun_faturalari", response_model=modeller.FaturaListResponse)
def get_urun_faturalari_endpoint(
    urun_id: int,
    fatura_turu: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Fatura).join(semalar.FaturaKalemi).filter(semalar.FaturaKalemi.urun_id == urun_id)

    if fatura_turu:
        query = query.filter(semalar.Fatura.fatura_turu == fatura_turu.upper())
    
    faturalar = query.distinct(semalar.Fatura.id).order_by(semalar.Fatura.id, semalar.Fatura.tarih.desc()).all()

    if not faturalar:
        return {"items": [], "total": 0}
    
    return {"items": [
        modeller.FaturaRead.model_validate(fatura, from_attributes=True)
        for fatura in faturalar
    ], "total": len(faturalar)}