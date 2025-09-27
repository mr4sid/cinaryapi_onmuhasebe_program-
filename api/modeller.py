from __future__ import annotations # Model referans sorunlarını çözmek için

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import date, datetime
from typing import List, Optional, Union, Literal # Literal eklendi
import enum
from sqlalchemy.sql import func
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime,
    ForeignKey, Date, Enum, or_
)
from sqlalchemy.orm import relationship, backref, declarative_base # DEĞİŞTİ: relationship ve backref eklendi

# Enumların string değerlerini kullanmak için
from .semalar import (
    FaturaTuruEnum, OdemeTuruEnum, CariTipiEnum, IslemYoneEnum,
    KasaBankaTipiEnum, StokIslemTipiEnum, SiparisTuruEnum, SiparisDurumEnum,
    KaynakTipEnum, GelirGiderTipEnum # GelirGiderTipEnum eklendi
)

Base = declarative_base()

# Pydantic'te float kullanıldığı için decimal importu gerekli değil
# import decimal

# Ortak Temel Modeller
class BaseOrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
class SirketBilgileri(Base):
    __tablename__ = 'sirket_bilgileri'
    id = Column(Integer, primary_key=True, index=True)
    sirket_adi = Column(String(100), nullable=False)
    adres = Column(String(200), nullable=True)
    telefon = Column(String(20), nullable=True)
    email = Column(String(50), nullable=True)
    vergi_dairesi = Column(String(100), nullable=True)
    vergi_no = Column(String(20), nullable=True)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), unique=True, nullable=False)

    kullanici = relationship("Kullanici", back_populates="sirket_bilgisi")

class SirketAyarlari(Base):
    __tablename__ = 'sirket_ayarlari'
    id = Column(Integer, primary_key=True, index=True)
    ayar_adi = Column(String(100), unique=True, index=True, nullable=False)
    ayar_degeri = Column(String(255), nullable=True)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), unique=True, nullable=False)
    
    kullanici = relationship("Kullanici", back_populates="sirket_ayarlari")

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

class Ayarlar(Base):
    __tablename__ = 'ayarlar'
    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String(100), unique=True, index=True, nullable=False) # Örneğin: 'access_token'
    deger = Column(Text, nullable=True) # Token değerini tutar
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True) # Genel ayarlar için None, kullanıcıya özel ayarlar için ID

    kullanici = relationship("Kullanici", backref=backref("ayarlar", cascade="all, delete-orphan"))

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
    kullanici_id: int # Yeni eklendi

class MusteriUpdate(CariBase):
    ad: Optional[str] = None
    kod: Optional[str] = None
    telefon: Optional[str] = None
    adres: Optional[str] = None
    vergi_dairesi: Optional[str] = None
    vergi_no: Optional[str] = None
    aktif: Optional[bool] = None
    kullanici_id: Optional[int] = None # Yeni eklendi

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
    kullanici_id: int # Yeni eklendi

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
    kullanici_id: Optional[int] = None # Yeni eklendi    

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
    kullanici_id: int # Yeni eklendi

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
    kullanici_id: Optional[int] = None # Yeni eklendi

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
    kullanici_id: int # Yeni eklendi

class StokHareketUpdate(StokHareketBase):
    stok_id: Optional[int] = None
    tarih: Optional[date] = None
    islem_tipi: Optional[StokIslemTipiEnum] = None
    miktar: Optional[float] = None
    birim_fiyat: Optional[float] = None
    aciklama: Optional[str] = None
    kaynak: Optional[str] = None
    kaynak_id: Optional[int] = None
    kullanici_id: Optional[int] = None # Yeni eklendi

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
    original_fatura_id: Optional[int] = None
    olusturan_kullanici_id: int
    kullanici_id: int # Yeni eklendi

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
    kullanici_id: Optional[int] = None # Yeni eklendi

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
    kullanici_id: int # Yeni eklendi

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
    kullanici_id: Optional[int] = None # Yeni eklendi

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
    kullanici_id: int # Yeni eklendi

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
    kullanici_id: Optional[int] = None # Yeni eklendi

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
    cari_tip: CariTipiEnum # Enum olarak kullanılacak
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
    kullanici_id: int # Yeni eklendi

class CariHareketUpdate(CariHareketBase):
    # Tüm alanlar optional, güncellenecek alanlar belirtilir
    cari_id: Optional[int] = None
    cari_tip: Optional[CariTipiEnum] = None
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
    kullanici_id: Optional[int] = None # Yeni eklendi

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
    kullanici_id: int # Yeni eklendi

class NitelikUpdate(NitelikBase):
    ad: Optional[str] = None
    kullanici_id: Optional[int] = None # Yeni eklendi

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

class StokOzetResponse(BaseModel):
    toplam_urun_sayisi: int
    toplam_miktar: float
    toplam_maliyet: float
    toplam_satis_tutari: float    

class NextSiparisKoduResponse(BaseModel):
    next_code: str    

class SiparisKalemiRead(BaseModel):
    id: int
    siparis_id: int
    urun_id: int
    miktar: float
    birim_fiyat: float  # KDV hariç birim fiyat
    kdv_orani: float
    alis_fiyati_siparis_aninda: Optional[float]
    iskonto_yuzde_1: float
    iskonto_yuzde_2: float
    iskonto_tipi: Optional[str]
    iskonto_degeri: Optional[float]
    kalem_toplam_kdv_haric: float
    kalem_toplam_kdv_dahil: float
    kdv_tutari: float
    urun_kodu: Optional[str]
    urun_adi: Optional[str]

    # Bu sınıfa da yeni yapılandırmayı ekliyoruz.
    model_config = ConfigDict(from_attributes=True)

class FaturaTuruEnum(str, enum.Enum):
    SATIŞ = "SATIŞ"
    ALIŞ = "ALIŞ"
    SATIŞ_İADE = "SATIŞ İADE"
    ALIŞ_İADE = "ALIŞ İADE"
    DEVİR_GİRİŞ = "DEVİR GİRİŞ"

class OdemeTuruEnum(str, enum.Enum):
    NAKİT = "NAKİT"
    KART = "KART"
    EFT_HAVALE = "EFT/HAVALE"
    ÇEK = "ÇEK"
    SENET = "SENET"
    AÇIK_HESAP = "AÇIK_HESAP"
    ETKİSİZ_FATURA = "ETKİSİZ_FATURA"

class CariTipiEnum(str, enum.Enum):
    MUSTERI = "MUSTERI"
    TEDARIKCI = "TEDARIKCI"

class IslemYoneEnum(str, enum.Enum):
    GİRİŞ = "GİRİŞ"
    ÇIKIŞ = "ÇIKIŞ"
    BORC = "BORC"
    ALACAK = "ALACAK"

class KasaBankaTipiEnum(str, enum.Enum):
    KASA = "KASA"
    BANKA = "BANKA"

class StokIslemTipiEnum(str, enum.Enum):
    GİRİŞ = "GİRİŞ"
    ÇIKIŞ = "ÇIKIŞ"
    SAYIM_FAZLASI = "SAYIM_FAZLASI"
    SAYIM_EKSİĞİ = "SAYIM_EKSİĞİ"
    SATIŞ = "SATIŞ"
    ALIŞ = "ALIŞ"
    SATIŞ_İADE = "SATIŞ_İADE"
    ALIŞ_İADE = "ALIŞ_İADE"
    KONSİNYE_GİRİŞ = "KONSİNYE_GİRİŞ"
    KONSİNYE_ÇIKIŞ = "KONSİNYE_ÇIKIŞ"

class SiparisTuruEnum(str, enum.Enum):
    SATIŞ_SIPARIS = "SATIŞ_SIPARIS"
    ALIŞ_SIPARIS = "ALIŞ_SIPARIS"

class SiparisDurumEnum(str, enum.Enum):
    BEKLEMEDE = "BEKLEMEDE"
    TAMAMLANDI = "TAMAMLANDI"
    KISMİ_TESLIMAT = "KISMİ_TESLİMAT"
    İPTAL_EDİLDİ = "İPTAL_EDİLDİ"
    FATURALAŞTIRILDI = "FATURALAŞTIRILDI"

class KaynakTipEnum(str, enum.Enum):
    FATURA = "FATURA"
    SIPARIS = "SIPARIS"
    GELIR_GIDER = "GELIR_GIDER"
    MANUEL = "MANUEL"
    TAHSILAT = "TAHSİLAT"
    ODEME = "ÖDEME"
    VERESIYE_BORC_MANUEL = "VERESİYE_BORÇ_MANUEL"

class GelirGiderTipEnum(str, enum.Enum):
    GELİR = "GELİR"
    GİDER = "GİDER"

# Tablo Modelleri
class Sirket(Base):
    __tablename__ = 'sirketler'
    id = Column(Integer, primary_key=True)
    sirket_adi = Column(String)
    sirket_adresi = Column(Text, nullable=True)
    sirket_telefonu = Column(String, nullable=True)
    sirket_email = Column(String, nullable=True)
    sirket_vergi_dairesi = Column(String, nullable=True)
    sirket_vergi_no = Column(String, nullable=True)
    sirket_logo_yolu = Column(String, nullable=True)

class Kullanici(Base):
    __tablename__ = 'kullanicilar'
    id = Column(Integer, primary_key=True, index=True)
    kullanici_adi = Column(String(50), unique=True, index=True, nullable=False)
    sifre_hash = Column(String(255), nullable=True)
    ad = Column(String(50), nullable=True)
    soyad = Column(String(50), nullable=True)
    email = Column(String(100), unique=True, index=True, nullable=True)
    telefon = Column(String(20), nullable=True)
    rol = Column(String(20), default="admin")  # admin, user, manager
    aktif = Column(Boolean, default=True)
    olusturma_tarihi = Column(DateTime, server_default=func.now())

    sirket_bilgisi = relationship("SirketBilgileri", back_populates="kullanici", uselist=False)
    sirket_ayarlari = relationship("SirketAyarlari", back_populates="kullanici", uselist=False)
    
    # Relationships
    stoklar = relationship("Stok", back_populates="kullanici")
    musteriler = relationship("Musteri", back_populates="kullanici")
    tedarikciler = relationship("Tedarikci", back_populates="kullanici")
    faturalar = relationship("Fatura", back_populates="kullanici")
    kasalar_bankalar = relationship("KasaBankaHesap", back_populates="kullanici")
    cari_hareketler = relationship("CariHareket", back_populates="kullanici")
    gelir_giderler = relationship("GelirGider", back_populates="kullanici")
    siparisler = relationship("Siparis", back_populates="kullanici")
    urun_nitelikleri = relationship("UrunNitelik", back_populates="kullanici")
    stok_hareketleri = relationship("StokHareket", back_populates="kullanici")

class Musteri(Base):
    __tablename__ = 'musteriler'
    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String(100), index=True)
    kod = Column(String(50), unique=True, index=True, nullable=False)
    adres = Column(String(255))
    telefon = Column(String(20))
    email = Column(String(100))
    vergi_dairesi = Column(String(100))
    vergi_no = Column(String(20))
    aktif = Column(Boolean, default=True)
    olusturma_tarihi = Column(DateTime, server_default=func.now()) # YENİ EKLENEN SATIR
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)
    
    kullanici = relationship("Kullanici", back_populates="musteriler")
    
    faturalar = relationship("Fatura", 
                             primaryjoin="and_(foreign(Fatura.cari_id) == Musteri.id, Fatura.fatura_turu.in_(['SATIŞ', 'SATIŞ_İADE']))",
                             back_populates="musteri",
                             overlaps="faturalar")
                             
    cari_hareketler = relationship("CariHareket",
                                  primaryjoin="and_(foreign(CariHareket.cari_id) == Musteri.id, CariHareket.cari_tip=='MUSTERI')",
                                  back_populates="musteri",
                                  overlaps="cari_hareketler")
                                  
    siparisler = relationship("Siparis",
                              primaryjoin="and_(foreign(Siparis.cari_id) == Musteri.id, Siparis.siparis_turu=='SATIŞ')",
                              back_populates="musteri",
                              overlaps="siparisler")

class Tedarikci(Base):
    __tablename__ = 'tedarikciler'
    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String(100), index=True)
    kod = Column(String(50), unique=True, index=True, nullable=False) 
    adres = Column(String(255))
    telefon = Column(String(20))
    email = Column(String(100))
    vergi_dairesi = Column(String(100))
    vergi_no = Column(String(20))
    aktif = Column(Boolean, default=True)
    olusturma_tarihi = Column(DateTime, server_default=func.now()) 
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)

    kullanici = relationship("Kullanici", back_populates="tedarikciler")
    
    # KRİTİK DÜZELTME: Tüm çakışmaların listesi eklendi.
    faturalar = relationship("Fatura",
                             primaryjoin="and_(foreign(Fatura.cari_id) == Tedarikci.id, Fatura.cari_tip == 'TEDARIKCI')", 
                             back_populates="tedarikci",
                             overlaps="faturalar, musteri") 
                             
    cari_hareketler = relationship("CariHareket",
                                  primaryjoin="and_(foreign(CariHareket.cari_id) == Tedarikci.id, CariHareket.cari_tip=='TEDARIKCI')",
                                  back_populates="tedarikci",
                                  overlaps="cari_hareketler, musteri") 
                                  
    siparisler = relationship("Siparis",
                              primaryjoin="and_(foreign(Siparis.cari_id) == Tedarikci.id, Siparis.cari_tip=='TEDARIKCI')",
                              back_populates="tedarikci",
                              overlaps="siparisler, musteri")

class Stok(Base):
    __tablename__ = 'stoklar'
    id = Column(Integer, primary_key=True, index=True)
    kod = Column(String(50), unique=True, index=True, nullable=False)
    ad = Column(String(200), index=True, nullable=False)
    detay = Column(Text, nullable=True)
    miktar = Column(Float, default=0.0)
    alis_fiyati = Column(Float, default=0.0)
    satis_fiyati = Column(Float, default=0.0)
    kdv_orani = Column(Float, default=20.0)
    min_stok_seviyesi = Column(Float, default=0.0)
    aktif = Column(Boolean, default=True)
    urun_resmi_yolu = Column(String(255), nullable=True)
    olusturma_tarihi = Column(DateTime, server_default=func.now())
    kategori_id = Column(Integer, ForeignKey('urun_nitelikleri.id'), nullable=True)
    marka_id = Column(Integer, ForeignKey('urun_nitelikleri.id'), nullable=True)
    urun_grubu_id = Column(Integer, ForeignKey('urun_nitelikleri.id'), nullable=True)
    birim_id = Column(Integer, ForeignKey('urun_nitelikleri.id'), nullable=True)
    mense_id = Column(Integer, ForeignKey('urun_nitelikleri.id'), nullable=True)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)

    kullanici = relationship("Kullanici", back_populates="stoklar")
    fatura_kalemleri = relationship("FaturaKalemi", back_populates="urun")
    stok_hareketleri = relationship("StokHareket", back_populates="urun", cascade="all, delete-orphan")
    siparis_kalemleri = relationship("SiparisKalemi", back_populates="urun")
    
class Fatura(Base):
    __tablename__ = 'faturalar'
    id = Column(Integer, primary_key=True, index=True)
    fatura_no = Column(String(50), unique=True, index=True, nullable=False)
    tarih = Column(Date, nullable=False)
    fatura_turu = Column(Enum(FaturaTuruEnum), nullable=False)
    cari_id = Column(Integer, nullable=False) # Hangi cari ile ilgili olduğu
    cari_tip = Column(String(20), nullable=False) # Cari tipi: Musteri veya Tedarikci
    odeme_turu = Column(Enum(OdemeTuruEnum), nullable=False)
    odeme_durumu = Column(String(20), default="ÖDENMEDİ")
    toplam_tutar = Column(Float, default=0.0)
    toplam_kdv = Column(Float, default=0.0)
    genel_toplam = Column(Float, default=0.0)
    kasa_banka_id = Column(Integer, ForeignKey('kasalar_bankalar.id'), nullable=True)
    fatura_notlari = Column(Text, nullable=True)
    vade_tarihi = Column(Date, nullable=True)
    genel_iskonto_tipi = Column(String(20), default="YOK")
    genel_iskonto_degeri = Column(Float, default=0.0)
    misafir_adi = Column(String(100), nullable=True)
    olusturma_tarihi = Column(DateTime, server_default=func.now())
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)

    # Relationships
    kullanici = relationship("Kullanici", back_populates="faturalar")
    kalemler = relationship("FaturaKalemi", back_populates="fatura", cascade="all, delete-orphan")
    kasa_banka = relationship("KasaBankaHesap", back_populates="faturalar")
    
    # DÜZELTİLDİ: primaryjoin ve foreign() anotasyonu eklendi
    musteri = relationship("Musteri",
                          primaryjoin="and_(Fatura.cari_id == foreign(Musteri.id), Fatura.cari_tip == 'MUSTERI')",
                          overlaps="faturalar")
                          
    # DÜZELTİLDİ: primaryjoin ve foreign() anotasyonu eklendi
    tedarikci = relationship("Tedarikci",
                             primaryjoin="and_(Fatura.cari_id == foreign(Tedarikci.id), Fatura.cari_tip == 'TEDARIKCI')",
                             overlaps="faturalar")

class FaturaKalemi(Base):
    __tablename__ = 'fatura_kalemleri'
    id = Column(Integer, primary_key=True, index=True)
    fatura_id = Column(Integer, ForeignKey('faturalar.id'))
    urun_id = Column(Integer, ForeignKey('stoklar.id'))
    miktar = Column(Float, nullable=False)
    birim_fiyat = Column(Float, nullable=False)
    kdv_orani = Column(Float, default=0.0)
    iskonto_yuzde_1 = Column(Float, default=0.0)
    iskonto_yuzde_2 = Column(Float, default=0.0)
    alis_fiyati_fatura_aninda = Column(Float, default=0.0)
    kalem_toplam_kdv_haric = Column(Float, default=0.0)
    kalem_toplam_kdv_dahil = Column(Float, default=0.0)
    olusturma_tarihi = Column(DateTime, server_default=func.now())

    fatura = relationship("Fatura", back_populates="kalemler")
    urun = relationship("Stok", back_populates="fatura_kalemleri")

class StokHareket(Base):
    __tablename__ = 'stok_hareketleri'
    id = Column(Integer, primary_key=True, index=True)
    tarih = Column(Date, nullable=False)
    urun_id = Column(Integer, ForeignKey('stoklar.id'), nullable=False)
    islem_tipi = Column(Enum(StokIslemTipiEnum), nullable=False)
    miktar = Column(Float, nullable=False)
    onceki_stok = Column(Float, nullable=False)
    sonraki_stok = Column(Float, nullable=False)
    aciklama = Column(Text, nullable=True)
    kaynak = Column(String(50), nullable=False)
    kaynak_id = Column(Integer, nullable=True)
    olusturma_tarihi = Column(DateTime, server_default=func.now())
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)

    kullanici = relationship("Kullanici", back_populates="stok_hareketleri")
    urun = relationship("Stok", back_populates="stok_hareketleri")

class Siparis(Base):
    __tablename__ = 'siparisler'
    id = Column(Integer, primary_key=True, index=True)
    siparis_no = Column(String(50), unique=True, index=True, nullable=False)
    siparis_turu = Column(Enum(SiparisTuruEnum), nullable=False) # 'SATIŞ' veya 'ALIŞ'
    durum = Column(Enum(SiparisDurumEnum), nullable=False) # 'BEKLEYEN', 'TAMAMLANDI', 'İPTAL'
    tarih = Column(Date, nullable=False)
    teslimat_tarihi = Column(Date, nullable=True)
    cari_id = Column(Integer, nullable=False)
    cari_tip = Column(String(20), nullable=False) # 'MUSTERI' veya 'TEDARIKCI'
    siparis_notlari = Column(Text)
    genel_toplam = Column(Float, default=0.0)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)
    olusturma_tarihi = Column(DateTime, server_default=func.now())

    kullanici = relationship("Kullanici", back_populates="siparisler")
    kalemler = relationship("SiparisKalemi", back_populates="siparis", cascade="all, delete-orphan")

    # DÜZELTİLDİ: foreign() anotasyonu eklendi
    musteri = relationship("Musteri", 
                           primaryjoin="and_(foreign(Siparis.cari_id) == Musteri.id, Siparis.cari_tip == 'MUSTERI')",
                           overlaps="siparisler, kalemler")

    # GÜNCELLEME: overlaps="siparisler, kalemler, musteri" eklendi
    tedarikci = relationship("Tedarikci", 
                             primaryjoin="and_(foreign(Siparis.cari_id) == Tedarikci.id, Siparis.cari_tip == 'TEDARIKCI')",
                             overlaps="siparisler, kalemler, musteri") 
 
class CariHareket(Base):
    __tablename__ = 'cari_hareketler'
    id = Column(Integer, primary_key=True, index=True)
    tarih = Column(Date, nullable=False)
    islem_turu = Column(String(50), nullable=False)  # 'TAHSILAT', 'ODEME', 'FATURA'
    islem_yone = Column(Enum(IslemYoneEnum), nullable=False)  # 'GIRIS' veya 'CIKIS'
    cari_id = Column(Integer, nullable=False) # Hangi cari ile ilgili olduğu
    cari_tip = Column(String, nullable=False)
    tutar = Column(Float, nullable=False)
    odeme_turu = Column(Enum(OdemeTuruEnum), nullable=True)
    aciklama = Column(Text, nullable=True)
    kaynak = Column(String(50), nullable=False) # 'FATURA', 'TAHSILAT', 'ODEME'
    kaynak_id = Column(Integer, nullable=True) # İlgili Fatura/Tahsilat/Ödeme ID'si
    kasa_banka_id = Column(Integer, ForeignKey('kasalar_bankalar.id'), nullable=True)
    olusturma_tarihi = Column(DateTime, server_default=func.now())
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)

    kullanici = relationship("Kullanici", back_populates="cari_hareketler")
    kasa_banka = relationship("KasaBankaHesap", back_populates="cari_hareketler")
    
    # DÜZELTİLDİ: primaryjoin ve foreign() anotasyonu eklendi
    musteri = relationship("Musteri",
                          primaryjoin="and_(foreign(CariHareket.cari_id) == Musteri.id, CariHareket.cari_tip == 'MUSTERI')",
                          overlaps="cari_hareketler") 
                          
    # GÜNCELLEME: overlaps="cari_hareketler, musteri" eklendi
    tedarikci = relationship("Tedarikci",
                             primaryjoin="and_(foreign(CariHareket.cari_id) == Tedarikci.id, CariHareket.cari_tip == 'TEDARIKCI')",
                             overlaps="cari_hareketler, musteri")

class UrunKategori(Base):
    __tablename__ = 'urun_kategorileri'
    id = Column(Integer, primary_key=True)
    ad = Column(String)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)

class UrunMarka(Base):
    __tablename__ = 'urun_markalari'
    id = Column(Integer, primary_key=True)
    ad = Column(String)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)

class UrunGrubu(Base):
    __tablename__ = 'urun_gruplari'
    id = Column(Integer, primary_key=True)
    ad = Column(String)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)

class UrunBirimi(Base):
    __tablename__ = 'urun_birimleri'
    id = Column(Integer, primary_key=True)
    ad = Column(String)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)

class Ulke(Base):
    __tablename__ = 'ulkeler'
    id = Column(Integer, primary_key=True)
    ad = Column(String)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)

class GelirSiniflandirma(Base):
    __tablename__ = 'gelir_siniflandirmalari'
    id = Column(Integer, primary_key=True)
    ad = Column(String)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)

class GiderSiniflandirma(Base):
    __tablename__ = 'gider_siniflandirmalari'
    id = Column(Integer, primary_key=True)
    ad = Column(String)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)

class Nitelik(Base):
    __tablename__ = 'nitelikler'
    id = Column(Integer, primary_key=True, index=True)
    tip = Column(String(50), index=True)
    ad = Column(String, unique=True, index=True, nullable=False)
    aciklama = Column(Text, nullable=True)
    aktif_durum = Column(Boolean, default=True)

class SenkronizasyonKuyrugu(Base):
    __tablename__ = 'senkronizasyon_kuyrugu'
    id = Column(Integer, primary_key=True, index=True)
    kaynak_tablo = Column(String, nullable=False)
    kaynak_id = Column(Integer, nullable=False)
    islem_tipi = Column(String, nullable=False) # 'ekle', 'guncelle', 'sil'
    veri = Column(Text, nullable=True) # JSON formatında veri
    islem_tarihi = Column(DateTime, default=func.now())
    senkronize_edildi = Column(Boolean, default=False)    

class CariHesap(Base):
    __tablename__ = 'cari_hesaplar'
    id = Column(Integer, primary_key=True, index=True)
    cari_id = Column(Integer, nullable=False)
    cari_tip = Column(String(20), nullable=False)
    bakiye = Column(Float, default=0.0)

class SiparisKalemi(Base):
    __tablename__ = 'siparis_kalemleri'
    id = Column(Integer, primary_key=True, index=True)
    siparis_id = Column(Integer, ForeignKey('siparisler.id'))
    urun_id = Column(Integer, ForeignKey('stoklar.id'))
    miktar = Column(Float, default=0.0)
    birim_fiyat = Column(Float, default=0.0)
    kdv_orani = Column(Float, default=0.0)
    iskonto_yuzde_1 = Column(Float, default=0.0) # Yeni eklendi
    iskonto_yuzde_2 = Column(Float, default=0.0) # Yeni eklendi
    birim_fiyat_kdv_haric = Column(Float, default=0.0) # Yeni eklendi
    toplam_tutar = Column(Float, default=0.0)
    olusturma_tarihi = Column(DateTime, server_default=func.now())

    siparis = relationship("Siparis", back_populates="kalemler")
    urun = relationship("Stok", back_populates="siparis_kalemleri")
    
class KasaBankaHesap(Base):
    __tablename__ = 'kasalar_bankalar'
    id = Column(Integer, primary_key=True, index=True)
    hesap_adi = Column(String(100), unique=True, index=True, nullable=False)
    kod = Column(String(50), nullable=True, unique=True, index=True) # KRİTİK DÜZELTME: Bu kolonun varlığından emin olmalıyız.
    tip = Column(Enum(KasaBankaTipiEnum), nullable=False)
    aktif = Column(Boolean, default=True)
    bakiye = Column(Float, default=0.0)
    para_birimi = Column(String(10), default="TL")
    banka_adi = Column(String(100), nullable=True)
    hesap_no = Column(String(50), nullable=True, unique=True, index=True)
    iban = Column(String(50), nullable=True, unique=True, index=True)
    swift_kodu = Column(String(20), nullable=True)
    olusturma_tarihi = Column(DateTime, server_default=func.now())
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)

    kullanici = relationship("Kullanici", back_populates="kasalar_bankalar")
    faturalar = relationship("Fatura", back_populates="kasa_banka")
    cari_hareketler = relationship("CariHareket", back_populates="kasa_banka")

class GelirGider(Base):
    __tablename__ = 'gelir_giderler'
    id = Column(Integer, primary_key=True, index=True)
    tarih = Column(Date, nullable=False)
    tip = Column(Enum(GelirGiderTipEnum), nullable=False)
    tutar = Column(Float, nullable=False)
    aciklama = Column(Text, nullable=False)
    kasa_banka_id = Column(Integer, ForeignKey('kasalar_bankalar.id'), nullable=True)
    cari_id = Column(Integer, nullable=True) # Opsiyonel
    kaynak = Column(String(50), nullable=False) # 'MANUEL'
    kaynak_id = Column(Integer, nullable=True) # Opsiyonel
    olusturma_tarihi = Column(DateTime, server_default=func.now())
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)
    
    kullanici = relationship("Kullanici", back_populates="gelir_giderler")
    kasa_banka = relationship("KasaBankaHesap", foreign_keys=[kasa_banka_id])

class UrunNitelik(Base):
    __tablename__ = 'urun_nitelikleri'
    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String(100), nullable=False)
    nitelik_tipi = Column(String(50), nullable=False) # 'kategori', 'marka', 'urun_grubu'
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)

    kullanici = relationship("Kullanici", back_populates="urun_nitelikleri")    