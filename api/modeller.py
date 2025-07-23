from __future__ import annotations # Model referans sorunlarını çözmek için

from pydantic import BaseModel, EmailStr, Field
from datetime import date, datetime
from typing import List, Optional, Literal

# Enumların string değerlerini kullanmak için
from .semalar import (
    FaturaTuruEnum, OdemeTuruEnum, CariTipiEnum, IslemYoneEnum, # IslemYoneEnum burada doğru import ediliyor
    KasaBankaTipiEnum, StokIslemTipiEnum, SiparisTuruEnum, SiparisDurumEnum,
    KaynakTipEnum
)

# Ortak Temel Modeller
class BaseOrmModel(BaseModel):
    class Config:
        from_attributes = True

# Şirket Bilgileri
class SirketBase(BaseModel):
    sirket_adi: Optional[str] = None
    sirket_adresi: Optional[str] = None
    sirket_telefonu: Optional[str] = None
    sirket_email: Optional[EmailStr] = None
    sirket_vergi_dairesi: Optional[str] = None
    sirket_vergi_no: Optional[str] = None
    sirket_logo_yolu: Optional[str] = None

class SirketCreate(SirketBase):
    sirket_adi: str

class SirketRead(SirketBase):
    id: int
    sirket_adi: str

# Kullanıcı Modelleri
class UserBase(BaseModel):
    kullanici_adi: str
    aktif: Optional[bool] = True
    yetki: Optional[str] = "kullanici"

class UserCreate(UserBase):
    sifre: str

class UserLogin(BaseModel):
    kullanici_adi: str
    sifre: str

class UserRead(UserBase):
    id: int
    olusturma_tarihi: datetime
    son_giris_tarihi: Optional[datetime] = None

class UserUpdate(BaseModel):
    kullanici_adi: Optional[str] = None
    hashed_sifre: Optional[str] = None
    aktif: Optional[bool] = None
    yetki: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class UserListResponse(BaseModel):
    items: List[UserRead]
    total: int

# Cari (Müşteri/Tedarikçi) Modelleri
class CariBase(BaseModel):
    ad: str
    telefon: Optional[str] = None
    adres: Optional[str] = None
    vergi_dairesi: Optional[str] = None
    vergi_no: Optional[str] = None
    aktif: Optional[bool] = True

class MusteriCreate(CariBase):
    kod: Optional[str] = None

class MusteriUpdate(CariBase):
    ad: Optional[str] = None
    kod: Optional[str] = None
    
class MusteriRead(CariBase):
    id: int
    kod: Optional[str] = None
    olusturma_tarihi: datetime
    net_bakiye: Optional[float] = Field(0.0, description="Cari net bakiyesi")

class MusteriListResponse(BaseModel):
    items: List[MusteriRead]
    total: int

class TedarikciCreate(CariBase):
    kod: Optional[str] = None

class TedarikciUpdate(CariBase):
    ad: Optional[str] = None
    kod: Optional[str] = None

class TedarikciRead(CariBase):
    id: int
    kod: Optional[str] = None
    olusturma_tarihi: datetime
    net_bakiye: Optional[float] = Field(0.0, description="Cari net bakiyesi")

class TedarikciListResponse(BaseModel):
    items: List[TedarikciRead]
    total: int

# Kasa/Banka Modelleri
class KasaBankaBase(BaseModel):
    hesap_adi: str
    tip: KasaBankaTipiEnum
    bakiye: Optional[float] = 0.0
    para_birimi: Optional[str] = "TL"
    banka_adi: Optional[str] = None
    sube_adi: Optional[str] = None
    hesap_no: Optional[str] = None
    varsayilan_odeme_turu: Optional[str] = None

class KasaBankaCreate(KasaBankaBase):
    pass

class KasaBankaUpdate(KasaBankaBase):
    hesap_adi: Optional[str] = None
    tip: Optional[KasaBankaTipiEnum] = None
    bakiye: Optional[float] = None
    para_birimi: Optional[str] = None
    
class KasaBankaRead(KasaBankaBase):
    id: int
    aktif: bool
    olusturma_tarihi: datetime

class KasaBankaListResponse(BaseModel):
    items: List[KasaBankaRead]
    total: int

# Stok Modelleri
class StokBase(BaseModel):
    kod: str
    ad: str
    detay: Optional[str] = None
    miktar: Optional[float] = 0.0
    alis_fiyati: Optional[float] = 0.0
    satis_fiyati: Optional[float] = 0.0
    kdv_orani: Optional[float] = 20.0
    min_stok_seviyesi: Optional[float] = 0.0
    aktif: Optional[bool] = True
    urun_resmi_yolu: Optional[str] = None
    
class StokCreate(StokBase):
    kategori_id: Optional[int] = None
    marka_id: Optional[int] = None
    urun_grubu_id: Optional[int] = None
    birim_id: Optional[int] = None
    mense_id: Optional[int] = None

class StokUpdate(StokBase):
    kod: Optional[str] = None
    ad: Optional[str] = None
    kategori_id: Optional[int] = None
    marka_id: Optional[int] = None
    urun_grubu_id: Optional[int] = None
    birim_id: Optional[int] = None
    mense_id: Optional[int] = None

class StokRead(StokBase):
    id: int
    olusturma_tarihi: datetime
    kategori: Optional[UrunKategoriRead] = None
    marka: Optional[UrunMarkaRead] = None
    urun_grubu: Optional[UrunGrubuRead] = None
    birim: Optional[UrunBirimiRead] = None
    mense_ulke: Optional[UlkeRead] = None

class StokListResponse(BaseModel):
    items: List[StokRead]
    total: int

class AnlikStokMiktariResponse(BaseModel):
    anlik_miktar: float

# Stok Hareket Modelleri
class StokHareketBase(BaseModel):
    stok_id: int
    tarih: date
    islem_tipi: StokIslemTipiEnum
    miktar: float
    kaynak: KaynakTipEnum
    kaynak_id: Optional[int] = None
    aciklama: Optional[str] = None
    islem_saati: Optional[str] = None

class StokHareketCreate(StokHareketBase):
    pass

class StokHareketRead(StokHareketBase):
    id: int
    stok: Optional[StokRead] = None
    olusturma_tarihi_saat: datetime

class StokHareketListResponse(BaseModel):
    items: List[StokHareketRead]
    total: int

# Fatura Kalem Modelleri
class FaturaKalemiBase(BaseModel):
    urun_id: int
    miktar: float
    birim_fiyat: float
    kdv_orani: float
    alis_fiyati_fatura_aninda: Optional[float] = None
    iskonto_yuzde_1: Optional[float] = 0.0
    iskonto_yuzde_2: Optional[float] = 0.0
    iskonto_tipi: Optional[str] = "YOK"
    iskonto_degeri: Optional[float] = 0.0

class FaturaKalemiCreate(FaturaKalemiBase):
    pass

class FaturaKalemiUpdate(FaturaKalemiBase):
    pass

class FaturaKalemiRead(FaturaKalemiBase):
    id: int
    fatura_id: int
    urun: Optional[StokRead] = None
    kalem_toplam_kdv_haric: Optional[float] = None
    kalem_toplam_kdv_dahil: Optional[float] = None
    kdv_tutari: Optional[float] = None


# Fatura Modelleri
class FaturaBase(BaseModel):
    fatura_no: str
    fatura_turu: FaturaTuruEnum
    tarih: date
    vade_tarihi: Optional[date] = None
    cari_id: Optional[int] = None
    misafir_adi: Optional[str] = None
    odeme_turu: OdemeTuruEnum
    kasa_banka_id: Optional[int] = None
    fatura_notlari: Optional[str] = None
    genel_iskonto_tipi: Optional[str] = "YOK"
    genel_iskonto_degeri: Optional[float] = 0.0

class FaturaCreate(FaturaBase):
    kalemler: List[FaturaKalemiCreate] = []

class FaturaUpdate(FaturaBase):
    fatura_no: Optional[str] = None
    fatura_turu: Optional[FaturaTuruEnum] = None
    tarih: Optional[date] = None
    kalemler: Optional[List[FaturaKalemiUpdate]] = None

class FaturaRead(FaturaBase):
    id: int
    olusturma_tarihi_saat: datetime
    olusturan_kullanici_id: Optional[int] = None
    son_guncelleme_tarihi_saat: Optional[datetime] = None
    son_guncelleyen_kullanici_id: Optional[int] = None
    
    cari_adi: Optional[str] = None
    kasa_banka_adi: Optional[str] = None
    toplam_kdv_haric: Optional[float] = None
    toplam_kdv_dahil: Optional[float] = None
    genel_toplam: Optional[float] = None

class FaturaListResponse(BaseModel):
    items: List[FaturaRead]
    total: int

class NextFaturaNoResponse(BaseModel):
    fatura_no: str


# Sipariş Kalem Modelleri
class SiparisKalemiBase(BaseModel):
    urun_id: int
    miktar: float
    birim_fiyat: float
    kdv_orani: float
    iskonto_yuzde_1: Optional[float] = 0.0
    iskonto_yuzde_2: Optional[float] = 0.0
    iskonto_tipi: Optional[str] = "YOK"
    iskonto_degeri: Optional[float] = 0.0
    alis_fiyati_siparis_aninda: Optional[float] = None
    satis_fiyati_siparis_aninda: Optional[float] = None

class SiparisKalemiCreate(SiparisKalemiBase):
    pass

class SiparisKalemiUpdate(SiparisKalemiBase):
    pass

class SiparisKalemiRead(SiparisKalemiBase):
    id: int
    siparis_id: int
    urun: Optional[StokRead] = None
    kalem_toplam_kdv_haric: Optional[float] = None
    kalem_toplam_kdv_dahil: Optional[float] = None
    kdv_tutari: Optional[float] = None


# Sipariş Modelleri
class SiparisBase(BaseModel):
    siparis_no: str
    siparis_turu: SiparisTuruEnum
    durum: SiparisDurumEnum
    tarih: date
    teslimat_tarihi: Optional[date] = None
    cari_id: Optional[int] = None
    cari_tip: Optional[CariTipiEnum] = None
    siparis_notlari: Optional[str] = None
    genel_iskonto_tipi: Optional[str] = "YOK"
    genel_iskonto_degeri: Optional[float] = 0.0
    fatura_id: Optional[int] = None

class SiparisCreate(SiparisBase):
    kalemler: List[SiparisKalemiCreate] = []

class SiparisUpdate(SiparisBase):
    siparis_no: Optional[str] = None
    siparis_turu: Optional[SiparisTuruEnum] = None
    durum: Optional[SiparisDurumEnum] = None
    tarih: Optional[date] = None
    kalemler: Optional[List[SiparisKalemiUpdate]] = None

class SiparisRead(SiparisBase):
    id: int
    olusturma_tarihi_saat: datetime
    olusturan_kullanici_id: Optional[int] = None
    son_guncelleme_tarihi_saat: Optional[datetime] = None
    son_guncelleyen_kullanici_id: Optional[int] = None
    
    cari_adi: Optional[str] = None
    toplam_tutar: Optional[float] = None

class SiparisListResponse(BaseModel):
    items: List[SiparisRead]
    total: int


# Gelir/Gider Modelleri
class GelirGiderBase(BaseModel):
    tarih: date
    tip: IslemYoneEnum
    aciklama: str
    tutar: float
    odeme_turu: Optional[OdemeTuruEnum] = None
    kasa_banka_id: Optional[int] = None
    cari_id: Optional[int] = None
    cari_tip: Optional[CariTipiEnum] = None
    gelir_siniflandirma_id: Optional[int] = None
    gider_siniflandirma_id: Optional[int] = None

class GelirGiderCreate(GelirGiderBase):
    pass

class GelirGiderUpdate(GelirGiderBase):
    pass

class GelirGiderRead(GelirGiderBase):
    id: int
    olusturma_tarihi_saat: datetime
    olusturan_kullanici_id: Optional[int] = None
    kasa_banka_adi: Optional[str] = None
    cari_ad: Optional[str] = None
    gelir_siniflandirma_adi: Optional[str] = None
    gider_siniflandirma_adi: Optional[str] = None

class GelirGiderListResponse(BaseModel):
    items: List[GelirGiderRead]
    total: int


# Cari Hareket Modelleri
class CariHareketBase(BaseModel):
    cari_id: int
    cari_turu: CariTipiEnum
    tarih: date
    islem_turu: str
    islem_yone: IslemYoneEnum
    tutar: float
    aciklama: Optional[str] = None
    kaynak: KaynakTipEnum
    kaynak_id: Optional[int] = None
    odeme_turu: Optional[OdemeTuruEnum] = None
    kasa_banka_id: Optional[int] = None
    vade_tarihi: Optional[date] = None

class CariHareketCreate(CariHareketBase):
    pass

class CariHareketUpdate(CariHareketBase):
    pass

class CariHareketRead(CariHareketBase):
    id: int
    olusturma_tarihi_saat: datetime
    olusturan_kullanici_id: Optional[int] = None
    fatura_no: Optional[str] = None
    fatura_turu: Optional[FaturaTuruEnum] = None
    islem_saati: Optional[str] = None

class CariHareketListResponse(BaseModel):
    items: List[CariHareketRead]
    total: int


# Kasa/Banka Hareket Modelleri
class KasaBankaHareketBase(BaseModel):
    kasa_banka_id: int
    tarih: date
    islem_turu: str
    islem_yone: IslemYoneEnum
    tutar: float
    aciklama: Optional[str] = None
    kaynak: KaynakTipEnum
    kaynak_id: Optional[int] = None

class KasaBankaHareketCreate(KasaBankaHareketBase):
    pass

class KasaBankaHareketUpdate(KasaBankaHareketBase):
    pass

class KasaBankaHareketRead(KasaBankaHareketBase):
    id: int
    olusturma_tarihi_saat: datetime

class KasaBankaHareketListResponse(BaseModel):
    items: List[KasaBankaHareketRead]
    total: int


# Nitelik Modelleri (Kategori, Marka, Grup, Birim, Ülke, Gelir/Gider Sınıflandırma)
class NitelikBase(BaseModel):
    ad: str

class UrunKategoriCreate(NitelikBase):
    pass
class UrunKategoriUpdate(NitelikBase):
    ad: Optional[str] = None
class UrunKategoriRead(NitelikBase):
    id: int

class UrunMarkaCreate(NitelikBase):
    pass
class UrunMarkaUpdate(NitelikBase):
    ad: Optional[str] = None
class UrunMarkaRead(NitelikBase):
    id: int

class UrunGrubuCreate(NitelikBase):
    pass
class UrunGrubuUpdate(NitelikBase):
    ad: Optional[str] = None
class UrunGrubuRead(NitelikBase):
    id: int

class UrunBirimiCreate(NitelikBase):
    pass
class UrunBirimiUpdate(NitelikBase):
    ad: Optional[str] = None
class UrunBirimiRead(NitelikBase):
    id: int

class UlkeCreate(NitelikBase):
    pass
class UlkeUpdate(NitelikBase):
    ad: Optional[str] = None
class UlkeRead(NitelikBase):
    id: int

class GelirSiniflandirmaCreate(NitelikBase):
    pass
class GelirSiniflandirmaUpdate(NitelikBase):
    ad: Optional[str] = None
class GelirSiniflandirmaRead(NitelikBase):
    id: int

class GiderSiniflandirmaCreate(NitelikBase):
    pass
class GiderSiniflandirmaUpdate(NitelikBase):
    ad: Optional[str] = None
class GiderSiniflandirmaRead(NitelikBase):
    id: int

# Rapor Modelleri
class DashboardSummary(BaseModel):
    toplam_satislar: float
    toplam_alislar: float
    toplam_tahsilatlar: float
    toplam_odemeler: float
    kritik_stok_urun_sayisi: int
    en_cok_satan_urunler: List[dict]
    vadesi_yaklasan_alacaklar_toplami: float
    vadesi_gecmis_borclar_toplami: float

class KarZararResponse(BaseModel):
    toplam_satis_geliri: float
    toplam_satis_maliyeti: float
    toplam_alis_gideri: float
    diger_gelirler: float
    diger_giderler: float
    brut_kar: float
    net_kar: float

class NakitAkisiResponse(BaseModel):
    nakit_girisleri: float
    nakit_cikislar: float
    net_nakit_akisi: float

class CariYaslandirmaEntry(BaseModel):
    cari_id: int
    cari_ad: str
    bakiye: float
    vade_tarihi: Optional[date] = None

class CariYaslandirmaResponse(BaseModel):
    musteri_alacaklar: List[CariYaslandirmaEntry]
    tedarikci_borclar: List[CariYaslandirmaEntry]

class StokDegerResponse(BaseModel):
    toplam_stok_maliyeti: float

class GelirGiderAylikOzetEntry(BaseModel):
    ay: int
    ay_adi: str
    toplam_gelir: float
    toplam_gider: float

class GelirGiderAylikOzetResponse(BaseModel):
    aylik_ozet: List[GelirGiderAylikOzetEntry]

class DefaultIdResponse(BaseModel):
    id: int

class NetBakiyeResponse(BaseModel):
    net_bakiye: float