from pydantic import BaseModel
from typing import Optional, List
from datetime import date

# Temel yapılandırma. Bu, SQLAlchemy modelleriyle uyumlu çalışmayı sağlar.
class OrmConfig(BaseModel):
    class Config:
        from_attributes = True

# =================================================================
# Nitelik Modelleri (Kategori, Marka vb.)
# =================================================================

class KategoriBase(OrmConfig):
    id: int
    kategori_adi: str

class MarkaBase(OrmConfig):
    id: int
    marka_adi: str

class UrunGrubuBase(OrmConfig):
    id: int
    grup_adi: str

class UrunBirimiBase(OrmConfig):
    id: int
    birim_adi: str

class UlkeBase(OrmConfig):
    id: int
    ulke_adi: str

# =================================================================
# Ana Modüller
# =================================================================

class MusteriBase(OrmConfig):
    id: int
    ad: str
    kod: Optional[str] = None
    telefon: Optional[str] = None
    adres: Optional[str] = None

class MusteriCreate(BaseModel):
    ad: str
    kod: Optional[str] = None
    telefon: Optional[str] = None
    adres: Optional[str] = None
    vergi_dairesi: Optional[str] = None
    vergi_no: Optional[str] = None   

class TedarikciBase(OrmConfig):
    id: int
    ad: str
    tedarikci_kodu: Optional[str] = None
    telefon: Optional[str] = None
    adres: Optional[str] = None

class TedarikciCreate(BaseModel):
    ad: str
    tedarikci_kodu: Optional[str] = None
    telefon: Optional[str] = None
    adres: Optional[str] = None
    vergi_dairesi: Optional[str] = None 
    vergi_no: Optional[str] = None 

class StokBase(OrmConfig):
    id: int
    urun_kodu: str
    urun_adi: str
    stok_miktari: float
    alis_fiyati_kdv_dahil: float 
    satis_fiyati_kdv_dahil: float
    kdv_orani: float
    min_stok_seviyesi: float

class StokCreate(BaseModel):
    urun_kodu: str
    urun_adi: str
    stok_miktari: Optional[float] = 0.0
    alis_fiyati_kdv_dahil: Optional[float] = 0.0
    satis_fiyati_kdv_dahil: Optional[float] = 0.0
    kdv_orani: Optional[float] = 20.0
    min_stok_seviyesi: Optional[float] = 0.0
    kategori_id: Optional[int] = None
    marka_id: Optional[int] = None

class KasaBankaBase(OrmConfig):
    id: int
    hesap_adi: str
    bakiye: float
    tip: str

class KasaBankaCreate(BaseModel):
    hesap_adi: str
    tip: str
    bakiye: float = 0.0
    hesap_no: Optional[str] = None
    banka_adi: Optional[str] = None
    sube_adi: Optional[str] = None
    para_birimi: Optional[str] = "TL"
    acilis_tarihi: Optional[date] = None
    varsayilan_odeme_turu: Optional[str] = None

class FaturaBase(OrmConfig):
    id: int
    fatura_no: str
    tarih: date
    tip: str
    toplam_kdv_dahil: float
    cari_adi: Optional[str] = "Bilinmiyor"
    kasa_banka_adi: Optional[str] = None
    olusturan_kul_adi: Optional[str] = None
    guncelleyen_kul_adi: Optional[str] = None

class FaturaKalemBase(BaseModel): # response_model için temel kalem
    urun_adi: str
    miktar: float
    birim_fiyat: float # iskontolu kdv dahil
    kalem_toplam_kdv_dahil: float

class FaturaKalemCreate(BaseModel):
    urun_id: int
    miktar: float
    birim_fiyat: float
    kdv_orani: float
    alis_fiyati_fatura_aninda: Optional[float] = 0.0
    iskonto_yuzde_1: Optional[float] = 0.0
    iskonto_yuzde_2: Optional[float] = 0.0
    iskonto_tipi: Optional[str] = "YOK"
    iskonto_degeri: Optional[float] = 0.0

class FaturaCreate(BaseModel):
    fatura_no: str
    tarih: date
    tip: str
    cari_id: int
    odeme_turu: str
    kalemler: List[FaturaKalemCreate]
    kasa_banka_id: Optional[int] = None
    misafir_adi: Optional[str] = None
    fatura_notlari: Optional[str] = None
    vade_tarihi: Optional[date] = None
    genel_iskonto_tipi: Optional[str] = "YOK"
    genel_iskonto_degeri: Optional[float] = 0.0
    original_fatura_id: Optional[int] = None

class SiparisKalemCreate(BaseModel):
    urun_id: int
    miktar: float
    birim_fiyat: float # KDV Hariç Orijinal
    kdv_orani: float
    alis_fiyati_siparis_aninda: Optional[float] = 0.0
    satis_fiyati_siparis_aninda: Optional[float] = 0.0
    iskonto_yuzde_1: Optional[float] = 0.0
    iskonto_yuzde_2: Optional[float] = 0.0

class FaturaUpdate(FaturaCreate): # FaturaCreate ile aynı alanları kullanır
    pass

class SiparisCreate(BaseModel):
    siparis_no: str
    siparis_tipi: str # 'SATIŞ_SIPARIS' veya 'ALIŞ_SIPARIS'
    cari_id: int
    durum: str
    kalemler: List[SiparisKalemCreate]
    siparis_notlari: Optional[str] = None
    teslimat_tarihi: Optional[date] = None
    genel_iskonto_tipi: Optional[str] = 'YOK'
    genel_iskonto_degeri: Optional[float] = 0.0

class SiparisUpdate(SiparisCreate): # SiparisCreate ile aynı alanları kullanır
    pass

class SiparisBase(OrmConfig):
    id: int
    siparis_no: str
    tarih: date
    toplam_tutar: float
    durum: str
    teslimat_tarihi: Optional[date] = None
    cari_adi: Optional[str] = "Bilinmiyor"
    siparis_tipi: Optional[str] = "Bilinmiyor"

class GelirGiderBase(OrmConfig):
    id: int
    tarih: date
    tip: str
    tutar: float
    aciklama: Optional[str] = None
    kaynak: Optional[str] = None
    kasa_banka_adi: Optional[str] = None

class GelirGiderCreate(BaseModel):
    tarih: date
    tip: str  # 'GELİR' veya 'GİDER'
    tutar: float
    aciklama: Optional[str] = None
    kasa_banka_id: int
    # Cari Hesap Entegrasyonu için yeni alanlar
    cari_id: Optional[int] = None
    cari_tip: Optional[str] = None 

class CariHareketBase(OrmConfig):
    id: int
    tarih: date
    islem_tipi: str
    tutar: float
    referans_tip: Optional[str] = None
    kasa_banka_adi: Optional[str] = None