# local_semalar.py
import enum
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, Text, Enum
)
from sqlalchemy.orm import declarative_base

# Deklaratif taban sınıfı
Base = declarative_base()

# Enum tanımları - Sunucudaki enumlar ile aynı olmalı
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
    id = Column(Integer, primary_key=True)
    kullanici_adi = Column(String, unique=True)
    hashed_sifre = Column(String)
    yetki = Column(String)
    aktif = Column(Boolean)
    olusturma_tarihi = Column(DateTime, default=datetime.now)
    son_giris_tarihi = Column(DateTime, nullable=True)

class Musteri(Base):
    __tablename__ = 'musteriler'
    id = Column(Integer, primary_key=True)
    ad = Column(String)
    kod = Column(String, unique=True, nullable=True)
    telefon = Column(String, nullable=True)
    adres = Column(Text, nullable=True)
    vergi_dairesi = Column(String, nullable=True)
    vergi_no = Column(String, nullable=True)
    aktif = Column(Boolean)
    olusturma_tarihi = Column(DateTime, default=datetime.now)

class Tedarikci(Base):
    __tablename__ = 'tedarikciler'
    id = Column(Integer, primary_key=True)
    ad = Column(String)
    kod = Column(String, unique=True, nullable=True)
    telefon = Column(String, nullable=True)
    adres = Column(Text, nullable=True)
    vergi_dairesi = Column(String, nullable=True)
    vergi_no = Column(String, nullable=True)
    aktif = Column(Boolean)
    olusturma_tarihi = Column(DateTime, default=datetime.now)
    
class KasaBanka(Base):
    __tablename__ = 'kasalar_bankalar'
    id = Column(Integer, primary_key=True)
    hesap_adi = Column(String)
    kod = Column(String, unique=True, nullable=True)
    tip = Column(String)
    bakiye = Column(Float)
    para_birimi = Column(String)
    banka_adi = Column(String, nullable=True)
    sube_adi = Column(String, nullable=True)
    hesap_no = Column(String, nullable=True)
    varsayilan_odeme_turu = Column(String, nullable=True)
    aktif = Column(Boolean)
    olusturma_tarihi = Column(DateTime, default=datetime.now)

class Stok(Base):
    __tablename__ = 'stoklar'
    id = Column(Integer, primary_key=True)
    kod = Column(String, unique=True)
    ad = Column(String)
    detay = Column(Text, nullable=True)
    miktar = Column(Float)
    alis_fiyati = Column(Float)
    satis_fiyati = Column(Float)
    kdv_orani = Column(Float)
    min_stok_seviyesi = Column(Float)
    aktif = Column(Boolean)
    urun_resmi_yolu = Column(String, nullable=True)
    olusturma_tarihi = Column(DateTime, default=datetime.now)
    kategori_id = Column(Integer)
    marka_id = Column(Integer)
    urun_grubu_id = Column(Integer)
    birim_id = Column(Integer)
    mense_id = Column(Integer)
    
class Fatura(Base):
    __tablename__ = 'faturalar'
    id = Column(Integer, primary_key=True)
    fatura_no = Column(String, unique=True)
    fatura_turu = Column(Enum(FaturaTuruEnum))
    tarih = Column(Date)
    vade_tarihi = Column(Date, nullable=True)
    cari_id = Column(Integer)
    misafir_adi = Column(String, nullable=True)
    odeme_turu = Column(Enum(OdemeTuruEnum))
    kasa_banka_id = Column(Integer, nullable=True)
    fatura_notlari = Column(Text, nullable=True)
    genel_iskonto_tipi = Column(String)
    genel_iskonto_degeri = Column(Float)
    original_fatura_id = Column(Integer, nullable=True)
    genel_toplam = Column(Float)
    toplam_kdv_haric = Column(Float)
    toplam_kdv_dahil = Column(Float)
    olusturma_tarihi_saat = Column(DateTime, default=datetime.now)
    olusturan_kullanici_id = Column(Integer, nullable=True)
    son_guncelleme_tarihi_saat = Column(DateTime, nullable=True)
    son_guncelleyen_kullanici_id = Column(Integer, nullable=True)

class FaturaKalemi(Base):
    __tablename__ = 'fatura_kalemleri'
    id = Column(Integer, primary_key=True)
    fatura_id = Column(Integer)
    urun_id = Column(Integer)
    miktar = Column(Float)
    birim_fiyat = Column(Float)
    kdv_orani = Column(Float)
    alis_fiyati_fatura_aninda = Column(Float, nullable=True)
    iskonto_yuzde_1 = Column(Float)
    iskonto_yuzde_2 = Column(Float)
    iskonto_tipi = Column(String)
    iskonto_degeri = Column(Float)

class StokHareket(Base):
    __tablename__ = 'stok_hareketleri'
    id = Column(Integer, primary_key=True)
    stok_id = Column(Integer)
    tarih = Column(Date)
    islem_tipi = Column(Enum(StokIslemTipiEnum))
    miktar = Column(Float)
    birim_fiyat = Column(Float)
    aciklama = Column(Text, nullable=True)
    kaynak = Column(String)
    kaynak_id = Column(Integer, nullable=True)
    onceki_stok = Column(Float, nullable=True)
    sonraki_stok = Column(Float, nullable=True)

class Siparis(Base):
    __tablename__ = 'siparisler'
    id = Column(Integer, primary_key=True)
    siparis_no = Column(String)
    siparis_turu = Column(Enum(SiparisTuruEnum))
    durum = Column(Enum(SiparisDurumEnum))
    tarih = Column(Date)
    teslimat_tarihi = Column(Date, nullable=True)
    cari_id = Column(Integer)
    cari_tip = Column(Enum(CariTipiEnum))
    siparis_notlari = Column(Text, nullable=True)
    genel_iskonto_tipi = Column(String)
    genel_iskonto_degeri = Column(Float)
    fatura_id = Column(Integer, nullable=True)
    toplam_tutar = Column(Float)
    olusturma_tarihi_saat = Column(DateTime, default=datetime.now)
    olusturan_kullanici_id = Column(Integer, nullable=True)
    son_guncelleme_tarihi_saat = Column(DateTime, nullable=True)
    son_guncelleyen_kullanici_id = Column(Integer, nullable=True)

class CariHareket(Base):
    __tablename__ = 'cari_hareketler'
    id = Column(Integer, primary_key=True)
    cari_id = Column(Integer)
    cari_turu = Column(Enum(CariTipiEnum))
    tarih = Column(Date)
    islem_turu = Column(String)
    islem_yone = Column(Enum(IslemYoneEnum))
    tutar = Column(Float)
    aciklama = Column(Text, nullable=True)
    kaynak = Column(String)
    kaynak_id = Column(Integer, nullable=True)
    odeme_turu = Column(Enum(OdemeTuruEnum), nullable=True)
    kasa_banka_id = Column(Integer, nullable=True)
    vade_tarihi = Column(Date, nullable=True)
    olusturma_tarihi_saat = Column(DateTime, default=datetime.now)
    olusturan_kullanici_id = Column(Integer, nullable=True)

class UrunKategori(Base):
    __tablename__ = 'urun_kategorileri'
    id = Column(Integer, primary_key=True)
    ad = Column(String)

class UrunMarka(Base):
    __tablename__ = 'urun_markalari'
    id = Column(Integer, primary_key=True)
    ad = Column(String)

class UrunGrubu(Base):
    __tablename__ = 'urun_gruplari'
    id = Column(Integer, primary_key=True)
    ad = Column(String)

class UrunBirimi(Base):
    __tablename__ = 'urun_birimleri'
    id = Column(Integer, primary_key=True)
    ad = Column(String)

class Ulke(Base):
    __tablename__ = 'ulkeler'
    id = Column(Integer, primary_key=True)
    ad = Column(String)

class GelirSiniflandirma(Base):
    __tablename__ = 'gelir_siniflandirmalari'
    id = Column(Integer, primary_key=True)
    ad = Column(String)

class GiderSiniflandirma(Base):
    __tablename__ = 'gider_siniflandirmalari'
    id = Column(Integer, primary_key=True)
    ad = Column(String)