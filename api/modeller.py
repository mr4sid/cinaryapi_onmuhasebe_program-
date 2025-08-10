from __future__ import annotations # Model referans sorunlarını çözmek için

from pydantic import BaseModel, EmailStr, Field
from datetime import date, datetime
from typing import List, Optional, Union, Literal # Literal eklendi

# Enumların string değerlerini kullanmak için
from .semalar import (
    FaturaTuruEnum, OdemeTuruEnum, CariTipiEnum, IslemYoneEnum,
    KasaBankaTipiEnum, StokIslemTipiEnum, SiparisTuruEnum, SiparisDurumEnum,
    KaynakTipEnum, GelirGiderTipEnum # GelirGiderTipEnum eklendi
)

# Pydantic'te float kullanıldığı için decimal importu gerekli değil
# import decimal

# Ortak Temel Modeller
class BaseOrmModel(BaseModel):
    class Config:
        from_attributes = True # Pydantic v2 için orm_mode yerine from_attributes kullanılır

# Şirket Bilgileri
class SirketBase(BaseOrmModel):
    sirket_adi: Optional[str] = None
    sirket_adresi: Optional[str] = None
    sirket_telefonu: Optional[str] = None
    sirket_email: Optional[EmailStr] = None
    sirket_vergi_dairesi: Optional[str] = None
    sirket_vergi_no: Optional[str] = None
    sirket_logo_yolu: Optional[str] = None

class SirketCreate(SirketBase):
    sirket_adi: str # Şirket adı zorunlu olmalı

class SirketRead(SirketBase):
    id: int
    sirket_adi: str

class SirketListResponse(BaseModel): # <-- BU MODEL YENİDEN EKLENDİ
    items: List[SirketRead]
    total: int


# Kullanıcı Modelleri
class KullaniciBase(BaseOrmModel):
    kullanici_adi: str
    aktif: Optional[bool] = True
    yetki: Optional[str] = "kullanici"

class KullaniciCreate(KullaniciBase):
    sifre: str

class KullaniciLogin(BaseModel): # Bu bir ORM objesinden gelmediği için BaseModel kalır
    kullanici_adi: str
    sifre: str

class KullaniciRead(KullaniciBase):
    id: int
    olusturma_tarihi: datetime
    son_giris_tarihi: Optional[datetime] = None

class KullaniciUpdate(BaseModel): # Bu da doğrudan bir ORM objesinden gelmediği için BaseModel kalır
    kullanici_adi: Optional[str] = None
    sifre: Optional[str] = None # Şifrenin hashlenmiş hali değil, plain text şifre buraya gelir
    aktif: Optional[bool] = None
    yetki: Optional[str] = None

class Token(BaseModel): # Bu da bir ORM objesinden gelmediği için BaseModel kalır
    access_token: str
    token_type: str

class TokenData(BaseModel): # Token verisi
    kullanici_adi: Optional[str] = None

class KullaniciListResponse(BaseModel): # Liste yanıtı, ORM objesi değil
    items: List[KullaniciRead]
    total: int

# Cari (Müşteri/Tedarikçi) Modelleri
class CariBase(BaseOrmModel):
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
    telefon: Optional[str] = None
    adres: Optional[str] = None
    vergi_dairesi: Optional[str] = None
    vergi_no: Optional[str] = None
    aktif: Optional[bool] = None
    
class MusteriRead(CariBase):
    id: int
    kod: Optional[str] = None
    olusturma_tarihi: datetime
    net_bakiye: Optional[float] = Field(0.0, description="Cari net bakiyesi") # Kafa karışıklığını gidermek için Optional yapıldı

class MusteriListResponse(BaseModel): # Liste yanıtı, ORM objesi değil
    items: List[MusteriRead]
    total: int

class TedarikciCreate(CariBase):
    kod: Optional[str] = None

class TedarikciUpdate(CariBase):
    ad: Optional[str] = None
    kod: Optional[str] = None
    telefon: Optional[str] = None
    adres: Optional[str] = None
    vergi_dairesi: Optional[str] = None
    vergi_no: Optional[str] = None
    aktif: Optional[bool] = None

class TedarikciRead(CariBase):
    id: int
    kod: Optional[str] = None
    olusturma_tarihi: datetime
    net_bakiye: Optional[float] = Field(0.0, description="Cari net bakiyesi") # Kafa karışıklığını gidermek için Optional yapıldı

class TedarikciListResponse(BaseModel): # Liste yanıtı, ORM objesi değil
    items: List[TedarikciRead]
    total: int

class CariListResponse(BaseModel):
    items: List[Union[MusteriRead, TedarikciRead]]
    total: int

# Kasa/Banka Modelleri
class KasaBankaBase(BaseOrmModel):
    hesap_adi: str
    kod: Optional[str] = None 
    tip: str # KASA veya BANKA olarak string
    bakiye: Optional[float] = 0.0 # Yeni kayıtta varsayılan 0.0 olabilir
    para_birimi: str = "TL" 
    banka_adi: Optional[str] = None
    sube_adi: Optional[str] = None
    hesap_no: Optional[str] = None
    varsayilan_odeme_turu: Optional[str] = None # String olarak tutulacak

class KasaBankaCreate(KasaBankaBase):
    pass

class KasaBankaUpdate(KasaBankaBase):
    hesap_adi: Optional[str] = None
    tip: Optional[str] = None # KasaBankaTipiEnum yerine str
    bakiye: Optional[float] = None
    para_birimi: Optional[str] = None
    aktif: Optional[bool] = None
    banka_adi: Optional[str] = None # Güncellemede de optional olsun
    sube_adi: Optional[str] = None
    hesap_no: Optional[str] = None
    varsayilan_odeme_turu: Optional[str] = None # Güncellemede de optional olsun
    
class KasaBankaRead(KasaBankaBase):
    id: int
    aktif: bool
    olusturma_tarihi: datetime

class KasaBankaListResponse(BaseModel): # Liste yanıtı, ORM objesi değil
    items: List[KasaBankaRead]
    total: int

# Stok Modelleri
class StokBase(BaseOrmModel):
    kod: str
    ad: str
    detay: Optional[str] = None
    miktar: float = Field(default=0.0) # condecimal yerine float
    alis_fiyati: float = Field(default=0.0) # condecimal yerine float
    satis_fiyati: float = Field(default=0.0) # condecimal yerine float
    kdv_orani: float = Field(default=20.0) # condecimal yerine float
    min_stok_seviyesi: float = Field(default=0.0) # condecimal yerine float
    aktif: Optional[bool] = True
    urun_resmi_yolu: Optional[str] = None

    kategori_id: Optional[int] = None
    marka_id: Optional[int] = None
    urun_grubu_id: Optional[int] = None
    birim_id: Optional[int] = None
    mense_id: Optional[int] = None
    
class StokCreate(StokBase):
    pass

class StokUpdate(StokBase):
    kod: Optional[str] = None
    ad: Optional[str] = None
    detay: Optional[str] = None
    miktar: Optional[float] = None
    alis_fiyati: Optional[float] = None
    satis_fiyati: Optional[float] = None
    kdv_orani: Optional[float] = None
    min_stok_seviyesi: Optional[float] = None
    aktif: Optional[bool] = None
    urun_resmi_yolu: Optional[str] = None
    kategori_id: Optional[int] = None
    marka_id: Optional[int] = None
    urun_grubu_id: Optional[int] = None
    birim_id: Optional[int] = None
    mense_id: Optional[int] = None

class UrunKategoriRead(BaseOrmModel):
    id: int
    ad: str

class UrunMarkaRead(BaseOrmModel):
    id: int
    ad: str

class UrunGrubuRead(BaseOrmModel):
    id: int
    ad: str

class UrunBirimiRead(BaseOrmModel):
    id: int
    ad: str

class UlkeRead(BaseOrmModel):
    id: int
    ad: str

class StokRead(StokBase):
    id: int
    olusturma_tarihi: datetime
    kategori: Optional[UrunKategoriRead] = None
    marka: Optional[UrunMarkaRead] = None
    urun_grubu: Optional[UrunGrubuRead] = None
    birim: Optional[UrunBirimiRead] = None
    mense_ulke: Optional[UlkeRead] = None

class StokListResponse(BaseModel): # Liste yanıtı
    items: List[StokRead]
    total: int

class AnlikStokMiktariResponse(BaseModel): # Liste yanıtı
    anlik_miktar: float

# Stok Hareket Modelleri
class StokHareketBase(BaseOrmModel):
    stok_id: int
    tarih: date
    islem_tipi: StokIslemTipiEnum # Enum olarak kullanılacak
    miktar: float
    birim_fiyat: float = Field(default=0.0) # Eklendi
    aciklama: Optional[str] = None
    kaynak: KaynakTipEnum # Enum olarak kullanılacak
    kaynak_id: Optional[int] = None

class StokHareketCreate(StokHareketBase):
    pass

class StokHareketRead(StokHareketBase):
    id: int
    olusturma_tarihi_saat: Optional[datetime] = None
    onceki_stok: Optional[float] = None
    sonraki_stok: Optional[float] = None
    stok: Optional[StokRead] = None

class StokHareketListResponse(BaseModel): # Liste yanıtı
    items: List[StokHareketRead]
    total: int

# Fatura Kalem Modelleri
class FaturaKalemiBase(BaseOrmModel):
    urun_id: int
    miktar: float
    birim_fiyat: float # KDV hariç, iskontosuz birim fiyat
    kdv_orani: float
    alis_fiyati_fatura_aninda: Optional[float] = None # Fatura kesildiği anki ürün alış fiyatı
    iskonto_yuzde_1: float = Field(default=0.0)
    iskonto_yuzde_2: float = Field(default=0.0)
    iskonto_tipi: Optional[str] = "YOK" # "YOK", "YUZDE", "TUTAR"
    iskonto_degeri: float = Field(default=0.0)

class FaturaKalemiCreate(FaturaKalemiBase):
    pass

class FaturaKalemiUpdate(FaturaKalemiBase):
    # Tüm alanlar optional, güncellenecek alanlar belirtilir
    urun_id: Optional[int] = None
    miktar: Optional[float] = None
    birim_fiyat: Optional[float] = None
    kdv_orani: Optional[float] = None
    alis_fiyati_fatura_aninda: Optional[float] = None
    iskonto_yuzde_1: Optional[float] = None
    iskonto_yuzde_2: Optional[float] = None
    iskonto_tipi: Optional[str] = None
    iskonto_degeri: Optional[float] = None

class FaturaKalemiRead(FaturaKalemiBase):
    id: int
    fatura_id: int
    urun_adi: Optional[str] = None # İlişkili üründen gelecek
    urun_kodu: Optional[str] = None # İlişkili üründen gelecek
    # Aşağıdaki alanlar ORM objesinden gelecek, hesaplanmış değerler
    kdv_tutari: Optional[float] = None
    kalem_toplam_kdv_haric: Optional[float] = None
    kalem_toplam_kdv_dahil: Optional[float] = None
    
# Fatura Modelleri
class FaturaBase(BaseOrmModel):
    fatura_no: str
    fatura_turu: FaturaTuruEnum # Enum olarak kullanılacak
    tarih: date
    vade_tarihi: Optional[date] = None
    cari_id: int
    misafir_adi: Optional[str] = None # Sadece perakende satışlar için
    odeme_turu: OdemeTuruEnum # Enum olarak kullanılacak
    kasa_banka_id: Optional[int] = None
    fatura_notlari: Optional[str] = None
    genel_iskonto_tipi: str = "YOK" # "YOK", "YUZDE", "TUTAR"
    genel_iskonto_degeri: float = Field(default=0.0)

class FaturaCreate(FaturaBase):
    kalemler: List[FaturaKalemiCreate] = []
    original_fatura_id: Optional[int] = None # İade faturaları için

class FaturaUpdate(FaturaBase):
    fatura_no: Optional[str] = None
    fatura_turu: Optional[FaturaTuruEnum] = None
    tarih: Optional[date] = None
    vade_tarihi: Optional[date] = None
    cari_id: Optional[int] = None
    misafir_adi: Optional[str] = None
    odeme_turu: Optional[OdemeTuruEnum] = None
    kasa_banka_id: Optional[int] = None
    fatura_notlari: Optional[str] = None
    genel_iskonto_tipi: Optional[str] = None
    genel_iskonto_degeri: Optional[float] = None
    original_fatura_id: Optional[int] = None
    kalemler: Optional[List[FaturaKalemiCreate]] = None # Güncellemede kalemler de gönderilebilir

class FaturaRead(FaturaBase):
    id: int
    olusturma_tarihi_saat: datetime
    olusturan_kullanici_id: Optional[int] = None
    son_guncelleme_tarihi_saat: Optional[datetime] = None
    son_guncelleyen_kullanici_id: Optional[int] = None
    
    cari_adi: Optional[str] = None # İlişkili cari bilgisinden gelecek
    cari_kodu: Optional[str] = None # İlişkili cari bilgisinden gelecek
    kasa_banka_adi: Optional[str] = None # İlişkili kasa/banka bilgisinden gelecek
    
    toplam_kdv_haric: float
    toplam_kdv_dahil: float
    genel_toplam: float
    kalemler: List[FaturaKalemiRead] = [] # Read modelde kalemler de olsun

class FaturaListResponse(BaseModel): # Liste yanıtı
    items: List[FaturaRead]
    total: int

class NextFaturaNoResponse(BaseModel): # Liste yanıtı
    fatura_no: str

# Sipariş Kalem Modelleri
class SiparisKalemiBase(BaseOrmModel):
    urun_id: int
    miktar: float
    birim_fiyat: float
    kdv_orani: float
    iskonto_yuzde_1: float = Field(default=0.0)
    iskonto_yuzde_2: float = Field(default=0.0)
    iskonto_tipi: Optional[str] = "YOK"
    iskonto_degeri: float = Field(default=0.0)
    alis_fiyati_siparis_aninda: Optional[float] = None
    satis_fiyati_siparis_aninda: Optional[float] = None

class SiparisKalemiCreate(SiparisKalemiBase):
    pass

class SiparisKalemiUpdate(SiparisKalemiBase):
    # Tüm alanlar optional, güncellenecek alanlar belirtilir
    urun_id: Optional[int] = None
    miktar: Optional[float] = None
    birim_fiyat: Optional[float] = None
    kdv_orani: Optional[float] = None
    iskonto_yuzde_1: Optional[float] = None
    iskonto_yuzde_2: Optional[float] = None
    iskonto_tipi: Optional[str] = None
    iskonto_degeri: Optional[float] = None
    alis_fiyati_siparis_aninda: Optional[float] = None
    satis_fiyati_siparis_aninda: Optional[float] = None

class SiparisKalemiRead(SiparisKalemiBase):
    id: int
    siparis_id: int
    urun_adi: Optional[str] = None # İlişkili üründen gelecek
    urun_kodu: Optional[str] = None # İlişkili üründen gelecek
    # Aşağıdaki alanlar ORM objesinden gelecek, hesaplanmış değerler
    kdv_tutari: Optional[float] = None
    kalem_toplam_kdv_haric: Optional[float] = None
    kalem_toplam_kdv_dahil: Optional[float] = None
    
# Sipariş Modelleri
class SiparisBase(BaseOrmModel):
    siparis_no: str
    siparis_turu: SiparisTuruEnum # Enum olarak kullanılacak
    durum: SiparisDurumEnum # Enum olarak kullanılacak
    tarih: date
    teslimat_tarihi: Optional[date] = None
    cari_id: int
    cari_tip: CariTipiEnum # Enum olarak kullanılacak
    siparis_notlari: Optional[str] = None
    genel_iskonto_tipi: str = "YOK"
    genel_iskonto_degeri: float = Field(default=0.0)
    fatura_id: Optional[int] = None # Siparişin dönüştürüldüğü fatura ID'si
    toplam_tutar: float = Field(default=0.0) # Toplam tutar alanı

class SiparisCreate(SiparisBase):
    kalemler: List[SiparisKalemiCreate] = []

class SiparisUpdate(SiparisBase):
    siparis_no: Optional[str] = None
    siparis_turu: Optional[SiparisTuruEnum] = None
    durum: Optional[SiparisDurumEnum] = None
    tarih: Optional[date] = None
    teslimat_tarihi: Optional[date] = None
    cari_id: Optional[int] = None
    cari_tip: Optional[CariTipiEnum] = None
    siparis_notlari: Optional[str] = None
    genel_iskonto_tipi: Optional[str] = None
    genel_iskonto_degeri: Optional[float] = None
    fatura_id: Optional[int] = None
    toplam_tutar: Optional[float] = None
    kalemler: Optional[List[SiparisKalemiCreate]] = None # Güncellemede kalemler de gönderilebilir

class SiparisRead(SiparisBase):
    id: int
    olusturma_tarihi_saat: datetime
    olusturan_kullanici_id: Optional[int] = None
    son_guncelleme_tarihi_saat: Optional[datetime] = None
    son_guncelleyen_kullanici_id: Optional[int] = None
    
    cari_adi: Optional[str] = None # İlişkili cari bilgisinden gelecek
    cari_kodu: Optional[str] = None # İlişkili cari bilgisinden gelecek
    kalemler: List[SiparisKalemiRead] = [] # Read modelde kalemler de olsun

class SiparisListResponse(BaseModel): # Liste yanıtı
    items: List[SiparisRead]
    total: int

class NextSiparisNoResponse(BaseModel): # Liste yanıtı
    siparis_no: str

# YENİ EKLENEN MODEL: Siparişten faturaya dönüşüm için
class SiparisFaturaDonusum(BaseModel):
    odeme_turu: OdemeTuruEnum # Enum olarak kullanılacak
    kasa_banka_id: Optional[int] = None
    vade_tarihi: Optional[date] = None
    olusturan_kullanici_id: Optional[int] = None # Kimin dönüştürdüğü bilgisi

# Gelir/Gider Modelleri
class GelirGiderBase(BaseOrmModel):
    tarih: date
    tip: GelirGiderTipEnum # Enum olarak kullanılacak
    aciklama: str
    tutar: float
    odeme_turu: Optional[OdemeTuruEnum] = None # Enum olarak kullanılacak
    kasa_banka_id: Optional[int] = None
    cari_id: Optional[int] = None
    cari_tip: Optional[CariTipiEnum] = None
    gelir_siniflandirma_id: Optional[int] = None
    gider_siniflandirma_id: Optional[int] = None

class GelirGiderCreate(GelirGiderBase):
    pass

class GelirGiderUpdate(GelirGiderBase):
    tarih: Optional[date] = None
    tip: Optional[GelirGiderTipEnum] = None
    aciklama: Optional[str] = None
    tutar: Optional[float] = None
    odeme_turu: Optional[OdemeTuruEnum] = None
    kasa_banka_id: Optional[int] = None
    cari_id: Optional[int] = None
    cari_tip: Optional[CariTipiEnum] = None
    gelir_siniflandirma_id: Optional[int] = None
    gider_siniflandirma_id: Optional[int] = None

class GelirGiderRead(GelirGiderBase):
    id: int
    olusturma_tarihi_saat: datetime
    olusturan_kullanici_id: Optional[int] = None
    kasa_banka_adi: Optional[str] = None
    cari_ad: Optional[str] = None
    gelir_siniflandirma_adi: Optional[str] = None
    gider_siniflandirma_adi: Optional[str] = None

class GelirGiderListResponse(BaseModel): # Liste yanıtı
    items: List[GelirGiderRead]
    total: int

# Cari Hareket Modelleri
class CariHareketBase(BaseOrmModel):
    cari_id: int
    cari_turu: CariTipiEnum # Enum olarak kullanılacak
    tarih: date
    islem_turu: str
    islem_yone: IslemYoneEnum # Enum olarak kullanılacak
    tutar: float
    aciklama: Optional[str] = None
    kaynak: KaynakTipEnum # Enum olarak kullanılacak
    kaynak_id: Optional[int] = None
    odeme_turu: Optional[OdemeTuruEnum] = None # Enum olarak kullanılacak
    kasa_banka_id: Optional[int] = None
    vade_tarihi: Optional[date] = None

class CariHareketCreate(CariHareketBase):
    pass

class CariHareketUpdate(CariHareketBase):
    # Tüm alanlar optional, güncellenecek alanlar belirtilir
    cari_id: Optional[int] = None
    cari_turu: Optional[CariTipiEnum] = None
    tarih: Optional[date] = None
    islem_turu: Optional[str] = None
    islem_yone: Optional[IslemYoneEnum] = None
    tutar: Optional[float] = None
    aciklama: Optional[str] = None
    kaynak: Optional[KaynakTipEnum] = None
    kaynak_id: Optional[int] = None
    odeme_turu: Optional[OdemeTuruEnum] = None
    kasa_banka_id: Optional[int] = None
    vade_tarihi: Optional[date] = None

class CariHareketRead(CariHareketBase):
    id: int
    olusturma_tarihi_saat: datetime
    olusturan_kullanici_id: Optional[int] = None
    fatura_no: Optional[str] = None
    fatura_turu: Optional[FaturaTuruEnum] = None # Enum olarak kullanılacak
    islem_saati: Optional[str] = None # Sadece zamanı tutan string

class CariHareketListResponse(BaseModel): # Liste yanıtı
    items: List[CariHareketRead]
    total: int

# Kasa/Banka Hareket Modelleri
class KasaBankaHareketBase(BaseOrmModel):
    kasa_banka_id: int

    tarih: date
    islem_turu: str
    islem_yone: IslemYoneEnum # Enum olarak kullanılacak
    tutar: float
    aciklama: Optional[str] = None
    kaynak: KaynakTipEnum # Enum olarak kullanılacak
    kaynak_id: Optional[int] = None

class KasaBankaHareketCreate(KasaBankaHareketBase):
    pass

class KasaBankaHareketUpdate(KasaBankaHareketBase):
    # Tüm alanlar optional, güncellenecek alanlar belirtilir
    kasa_banka_id: Optional[int] = None
    tarih: Optional[date] = None
    islem_turu: Optional[str] = None
    islem_yone: Optional[IslemYoneEnum] = None
    tutar: Optional[float] = None
    aciklama: Optional[str] = None
    kaynak: Optional[KaynakTipEnum] = None
    kaynak_id: Optional[int] = None

class KasaBankaHareketRead(KasaBankaHareketBase):
    id: int
    olusturma_tarihi_saat: datetime

class KasaBankaHareketListResponse(BaseModel): # Liste yanıtı
    items: List[KasaBankaHareketRead]
    total: int

# Nitelik Modelleri (Kategori, Marka, Grup, Birim, Ülke, Gelir/Gider Sınıflandırma)
class NitelikBase(BaseOrmModel):
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

class NitelikListResponse(BaseModel):
    items: List[Union[UrunKategoriRead, UrunMarkaRead, UrunGrubuRead, UrunBirimiRead, UlkeRead, GelirSiniflandirmaRead, GiderSiniflandirmaRead]]
    total: int

# Rapor Modelleri (Bu modeller ORM objesinden türetilmediği için BaseModel kalır)
class PanoOzetiYanit(BaseModel):
    toplam_satislar: float
    toplam_alislar: float
    toplam_tahsilatlar: float
    toplam_odemeler: float
    kritik_stok_sayisi: int
    en_cok_satan_urunler: List[EnCokSatanUrun]
    vadesi_yaklasan_alacaklar_toplami: float
    vadesi_gecmis_borclar_toplami: float

class EnCokSatanUrun(BaseModel):
    ad: str
    toplam_miktar: float

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

class TopluIslemSonucResponse(BaseModel):
    yeni_eklenen_sayisi: int
    guncellenen_sayisi: int
    hata_sayisi: int
    hatalar: List[str]
    toplam_islenen: int    