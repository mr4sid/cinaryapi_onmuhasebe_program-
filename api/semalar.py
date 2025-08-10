# api.zip/semalar.py dosyasının TAMAMI -
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, Text, Enum,
    create_engine, and_
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker, Mapped, mapped_column, foreign
from sqlalchemy.dialects import postgresql
from datetime import datetime, date
import enum
from typing import List, Optional
from .veritabani import Base

# Enum tanımları
class FaturaTuruEnum(str, enum.Enum):
    SATIS = "SATIŞ"
    ALIS = "ALIŞ"
    SATIS_IADE = "SATIŞ İADE"
    ALIS_IADE = "ALIŞ İADE"
    DEVIR_GIRIS = "DEVİR GİRİŞ"

class OdemeTuruEnum(str, enum.Enum):
    NAKIT = "NAKİT"
    KART = "KART"
    EFT_HAVALE = "EFT/HAVALE"
    CEK = "ÇEK"
    SENET = "SENET"
    ACIK_HESAP = "AÇIK_HESAP"
    ETKISIZ_FATURA = "ETKİSİZ_FATURA"

class CariTipiEnum(str, enum.Enum):
    MUSTERI = "MUSTERI"
    TEDARIKCI = "TEDARIKCI"

class IslemYoneEnum(str, enum.Enum): # İşlem yönü için kullanılan enum (ALACAK/BORC)
    GIRIS = "GİRİŞ"
    CIKIS = "ÇIKIŞ"
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
    SATIS_SIPARIS = "SATIŞ_SIPARIS"
    ALIS_SIPARIS = "ALIŞ_SIPARIS"

class SiparisDurumEnum(str, enum.Enum):
    BEKLEMEDE = "BEKLEMEDE"
    TAMAMLANDI = "TAMAMLANDI"
    KISMİ_TESLIMAT = "KISMİ_TESLİMAT"
    IPTAL_EDILDI = "İPTAL_EDİLDİ"
    FATURALASTIRILDI = "FATURALAŞTIRILDI"

class KaynakTipEnum(str, enum.Enum):
    FATURA = "FATURA"
    SIPARIS = "SIPARIS"
    GELIR_GIDER = "GELIR_GIDER"
    MANUEL = "MANUEL"
    TAHSILAT = "TAHSİLAT"
    ODEME = "ÖDEME"
    VERESIYE_BORC_MANUEL = "VERESİYE_BORÇ_MANUEL"

# YENİ EKLENEN ENUM: Gelir/Gider tipi için özel enum
class GelirGiderTipEnum(str, enum.Enum):
    GELIR = "GELİR"
    GIDER = "GİDER"

# Tablo Modelleri
class Sirket(Base):
    __tablename__ = 'sirketler'
    __table_args__ = {'extend_existing': True} 

    id = Column(Integer, primary_key=True, index=True)
    sirket_adi = Column(String, index=True)
    sirket_adresi = Column(Text, nullable=True)
    sirket_telefonu = Column(String, nullable=True)
    sirket_email = Column(String, nullable=True)
    sirket_vergi_dairesi = Column(String, nullable=True)
    sirket_vergi_no = Column(String, nullable=True)
    sirket_logo_yolu = Column(String, nullable=True)

class Kullanici(Base):
    __tablename__ = 'kullanicilar'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    kullanici_adi = Column(String, unique=True, index=True)
    hashed_sifre = Column(String)
    yetki = Column(String, default="kullanici")
    aktif = Column(Boolean, default=True)
    olusturma_tarihi = Column(DateTime, default=datetime.now)
    son_giris_tarihi = Column(DateTime, nullable=True)

# CariHareket sınıfı, Musteri ve Tedarikci'den önce tanımlanmalı
class CariHareket(Base):
    __tablename__ = 'cari_hareketler'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    cari_id = Column(Integer, index=True) 
    cari_turu = Column(Enum(CariTipiEnum), index=True)
    tarih = Column(Date)
    islem_turu = Column(String)
    islem_yone = Column(Enum(IslemYoneEnum))
    tutar = Column(Float)
    aciklama = Column(Text, nullable=True)
    kaynak = Column(String) 
    kaynak_id = Column(Integer, nullable=True)
    odeme_turu = Column(Enum(OdemeTuruEnum), nullable=True)
    kasa_banka_id = Column(Integer, ForeignKey('kasalar_bankalar.id'), nullable=True)
    vade_tarihi = Column(Date, nullable=True)

    olusturma_tarihi_saat = Column(DateTime, default=datetime.now)
    olusturan_kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)

    musteri_iliski = relationship(
        "Musteri", 
        primaryjoin=lambda: and_(foreign(CariHareket.cari_id) == Musteri.id, CariHareket.cari_turu == 'MUSTERI'),
        viewonly=True,
        overlaps="cari_hareketler"
    )
    tedarikci_iliski = relationship(
        "Tedarikci", 
        primaryjoin=lambda: and_(foreign(CariHareket.cari_id) == Tedarikci.id, CariHareket.cari_turu == 'TEDARIKCI'),
        viewonly=True,
        overlaps="cari_hareketler"
    )
    kasa_banka_hesabi = relationship("KasaBanka", backref="cari_hareketler_iliski")

# StokHareket sınıfı Stok sınıfından önce tanımlanmalı
class StokHareket(Base):
    __tablename__ = 'stok_hareketleri'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    stok_id = Column(Integer, ForeignKey('stoklar.id'), index=True)
    tarih = Column(Date)
    islem_tipi = Column(Enum(StokIslemTipiEnum))
    miktar = Column(Float)
    birim_fiyat = Column(Float) # Bu alan Stok tablosundan farklı olarak, hareket anındaki birim fiyatı tutar.
    aciklama = Column(Text, nullable=True)
    kaynak = Column(String) # KaynakTipEnum ile uyumlu olmalı
    kaynak_id = Column(Integer, nullable=True)
    onceki_stok = Column(Float, nullable=True) # Eklendi
    sonraki_stok = Column(Float, nullable=True) # Eklendi

    stok = relationship("Stok", back_populates="stok_hareketleri") 

class Musteri(Base):
    __tablename__ = 'musteriler'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String, index=True)
    kod = Column(String, unique=True, index=True, nullable=True)
    telefon = Column(String, nullable=True)
    adres = Column(Text, nullable=True)
    vergi_dairesi = Column(String, nullable=True)
    vergi_no = Column(String, nullable=True)
    aktif = Column(Boolean, default=True)
    olusturma_tarihi = Column(DateTime, default=datetime.now)

    cari_hareketler = relationship(
        "CariHareket",
        primaryjoin=lambda: and_(Musteri.id == foreign(CariHareket.cari_id), CariHareket.cari_turu == 'MUSTERI'), 
        back_populates="musteri_iliski",
        cascade="all, delete-orphan",
        overlaps="musteri_iliski" 
    )
    faturalar = relationship("Fatura", foreign_keys="[Fatura.cari_id]", primaryjoin="Musteri.id == Fatura.cari_id and Fatura.fatura_turu.in_(['SATIŞ', 'SATIŞ_IADE'])", back_populates="ilgili_musteri", cascade="all, delete-orphan", overlaps="ilgili_musteri")
    siparisler = relationship("Siparis", foreign_keys="Siparis.cari_id", primaryjoin="Musteri.id == Siparis.cari_id and Siparis.siparis_turu == 'SATIŞ_SIPARIS'", back_populates="musteri_siparis", overlaps="musteri_siparis")

class Tedarikci(Base):
    __tablename__ = 'tedarikciler'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String, index=True)
    kod = Column(String, unique=True, index=True, nullable=True)
    telefon = Column(String, nullable=True)
    adres = Column(Text, nullable=True)
    vergi_dairesi = Column(String, nullable=True)
    vergi_no = Column(String, nullable=True)
    aktif = Column(Boolean, default=True)
    olusturma_tarihi = Column(DateTime, default=datetime.now)

    cari_hareketler = relationship(
        "CariHareket",
        primaryjoin=lambda: and_(Tedarikci.id == foreign(CariHareket.cari_id), CariHareket.cari_turu == 'TEDARIKCI'),
        back_populates="tedarikci_iliski",
        cascade="all, delete-orphan",
        overlaps="tedarikci_iliski" 
    )
    faturalar = relationship(
        "Fatura",
        foreign_keys="[Fatura.cari_id]",
        primaryjoin="Tedarikci.id == Fatura.cari_id and Fatura.fatura_turu.in_(['ALIŞ', 'ALIŞ_IADE', 'DEVİR GİRİŞ'])",
        back_populates="ilgili_tedarikci",
        cascade="all, delete-orphan",
        overlaps="ilgili_tedarikci"
    )
    siparisler = relationship(
        "Siparis",
        foreign_keys="Siparis.cari_id",
        primaryjoin="Tedarikci.id == Siparis.cari_id and Siparis.siparis_turu == 'ALIŞ_SIPARIS'",
        back_populates="tedarikci_siparis",
        cascade="all, delete-orphan",
        overlaps="tedarikci_siparis"
    )
    
class KasaBanka(Base):
    __tablename__ = 'kasalar_bankalar'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    hesap_adi = Column(String, index=True)
    kod = Column(String, unique=True, index=True, nullable=True)
    tip = Column(String, default="KASA")
    bakiye = Column(Float, default=0.0)
    para_birimi = Column(String, default="TL")
    banka_adi = Column(String, nullable=True)
    sube_adi = Column(String, nullable=True)
    hesap_no = Column(String, nullable=True)
    varsayilan_odeme_turu = Column(String, nullable=True)
    aktif = Column(Boolean, default=True)
    olusturma_tarihi = Column(DateTime, default=datetime.now)

    hareketler = relationship("KasaBankaHareket", back_populates="kasa_banka_hesabi", cascade="all, delete-orphan")

class Stok(Base):
    __tablename__ = 'stoklar'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    kod = Column(String, unique=True, index=True)
    ad = Column(String, index=True)
    detay = Column(Text, nullable=True)
    miktar = Column(Float, default=0.0)
    alis_fiyati = Column(Float, default=0.0)
    satis_fiyati = Column(Float, default=0.0)
    kdv_orani = Column(Float, default=20.0)
    min_stok_seviyesi = Column(Float, default=0.0)
    aktif = Column(Boolean, default=True)
    urun_resmi_yolu = Column(String, nullable=True)
    olusturma_tarihi = Column(DateTime, default=datetime.now)

    kategori_id = Column(Integer, ForeignKey('urun_kategorileri.id'), nullable=True)
    marka_id = Column(Integer, ForeignKey('urun_markalari.id'), nullable=True)
    urun_grubu_id = Column(Integer, ForeignKey('urun_gruplari.id'), nullable=True)
    birim_id = Column(Integer, ForeignKey('urun_birimleri.id'), nullable=True)
    mense_id = Column(Integer, ForeignKey('ulkeler.id'), nullable=True)

    kategori = relationship("UrunKategori", back_populates="stoklar")
    marka = relationship("UrunMarka", back_populates="stoklar")
    urun_grubu = relationship("UrunGrubu", back_populates="stoklar")
    birim = relationship("UrunBirimi", back_populates="stoklar")
    mense_ulke = relationship("Ulke", back_populates="stoklar")

    stok_hareketleri = relationship("StokHareket", back_populates="stok", cascade="all, delete-orphan")
    fatura_kalemleri = relationship("FaturaKalemi", back_populates="urun", cascade="all, delete-orphan")
    siparis_kalemleri = relationship("SiparisKalemi", back_populates="urun", cascade="all, delete-orphan")

class Fatura(Base):
    __tablename__ = 'faturalar'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    fatura_no = Column(String, unique=True, index=True)
    fatura_turu = Column(Enum(FaturaTuruEnum), index=True)
    tarih = Column(Date)
    vade_tarihi = Column(Date, nullable=True)
    cari_id = Column(Integer, index=True)
    misafir_adi = Column(String, nullable=True)
    odeme_turu = Column(Enum(OdemeTuruEnum), default=OdemeTuruEnum.NAKIT)
    kasa_banka_id = Column(Integer, ForeignKey('kasalar_bankalar.id'), nullable=True)
    fatura_notlari = Column(Text, nullable=True)
    genel_iskonto_tipi = Column(String, default="YOK")
    genel_iskonto_degeri = Column(Float, default=0.0)
    original_fatura_id = Column(Integer, ForeignKey('faturalar.id'), nullable=True)

    genel_toplam = Column(Float, nullable=False, default=0.0)
    toplam_kdv_haric = Column(Float, nullable=False, default=0.0)
    toplam_kdv_dahil = Column(Float, nullable=False, default=0.0)

    toplam_kdv_haric = Column(Float, nullable=False, default=0.0)
    toplam_kdv_dahil = Column(Float, nullable=False, default=0.0)

    olusturma_tarihi_saat = Column(DateTime, default=datetime.now)
    olusturan_kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)
    son_guncelleme_tarihi_saat = Column(DateTime, onupdate=datetime.now, nullable=True)
    son_guncelleyen_kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)

    kasa_banka_hesabi = relationship("KasaBanka", backref="faturalar_iliski")
    olusturan_kullanici = relationship("Kullanici", foreign_keys=[olusturan_kullanici_id])
    son_guncelleyen_kullanici = relationship("Kullanici", foreign_keys=[son_guncelleyen_kullanici_id])

    ilgili_musteri = relationship("Musteri", foreign_keys=[cari_id], primaryjoin="Musteri.id == Fatura.cari_id and Fatura.fatura_turu.in_(['SATIŞ', 'SATIŞ_IADE'])", back_populates="faturalar", viewonly=True, overlaps="faturalar")
    ilgili_tedarikci = relationship("Tedarikci", foreign_keys=[cari_id], primaryjoin="Tedarikci.id == Fatura.cari_id and Fatura.fatura_turu.in_(['ALIŞ', 'ALIŞ_IADE', 'DEVİR GİRİŞ'])", back_populates="faturalar", viewonly=True, overlaps="faturalar")

    kalemler = relationship("FaturaKalemi", back_populates="fatura", cascade="all, delete-orphan")

class FaturaKalemi(Base):
    __tablename__ = 'fatura_kalemleri'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    fatura_id = Column(Integer, ForeignKey('faturalar.id'), index=True)
    urun_id = Column(Integer, ForeignKey('stoklar.id'), index=True)
    miktar = Column(Float)
    birim_fiyat = Column(Float)
    kdv_orani = Column(Float)
    alis_fiyati_fatura_aninda = Column(Float, nullable=True)
    iskonto_yuzde_1 = Column(Float, default=0.0)
    iskonto_yuzde_2 = Column(Float, default=0.0)
    iskonto_tipi = Column(String, default="YOK")
    iskonto_degeri = Column(Float, default=0.0)

    fatura = relationship("Fatura", back_populates="kalemler")
    urun = relationship("Stok", back_populates="fatura_kalemleri")

class Siparis(Base):
    __tablename__ = 'siparisler'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    siparis_no = Column(String, unique=True, index=True)
    siparis_turu = Column(Enum(SiparisTuruEnum), index=True)
    durum = Column(Enum(SiparisDurumEnum), default=SiparisDurumEnum.BEKLEMEDE)
    tarih = Column(Date)
    teslimat_tarihi = Column(Date, nullable=True)
    cari_id = Column(Integer, index=True)
    cari_tip = Column(Enum(CariTipiEnum), index=True)
    siparis_notlari = Column(Text, nullable=True)
    genel_iskonto_tipi = Column(String, default="YOK")
    genel_iskonto_degeri = Column(Float, default=0.0)
    fatura_id = Column(Integer, ForeignKey('faturalar.id'), nullable=True)

    olusturma_tarihi_saat = Column(DateTime, default=datetime.now)
    olusturan_kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)
    son_guncelleme_tarihi_saat = Column(DateTime, onupdate=datetime.now, nullable=True)
    son_guncelleyen_kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)

    olusturan_kullanici = relationship("Kullanici", foreign_keys=[olusturan_kullanici_id])
    son_guncelleyen_kullanici = relationship("Kullanici", foreign_keys=[son_guncelleyen_kullanici_id])

    musteri_siparis = relationship("Musteri", foreign_keys=[cari_id], primaryjoin="Siparis.cari_id == Musteri.id and Siparis.siparis_turu == 'SATIŞ_SIPARIS'", viewonly=True, overlaps="siparisler")
    tedarikci_siparis = relationship("Tedarikci", foreign_keys=[cari_id], primaryjoin="Siparis.cari_id == Tedarikci.id and Siparis.siparis_turu == 'ALIŞ_SIPARIS'", viewonly=True, overlaps="siparisler")

    kalemler = relationship("SiparisKalemi", back_populates="siparis", cascade="all, delete-orphan")

class SiparisKalemi(Base):
    __tablename__ = 'siparis_kalemleri'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    siparis_id = Column(Integer, ForeignKey('siparisler.id'), index=True)
    urun_id = Column(Integer, ForeignKey('stoklar.id'), index=True)
    miktar = Column(Float)
    birim_fiyat = Column(Float)
    kdv_orani = Column(Float)
    iskonto_yuzde_1 = Column(Float, default=0.0)
    iskonto_yuzde_2 = Column(Float, default=0.0)
    iskonto_tipi = Column(String, default="YOK")
    iskonto_degeri = Column(Float, default=0.0)
    alis_fiyati_siparis_aninda = Column(Float, nullable=True)
    satis_fiyati_siparis_aninda = Column(Float, nullable=True)

    siparis = relationship("Siparis", back_populates="kalemler")
    urun = relationship("Stok", back_populates="siparis_kalemleri")

class GelirGider(Base):
    __tablename__ = 'gelir_giderler'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    tarih = Column(Date)
    tip = Column(Enum(GelirGiderTipEnum), index=True)
    aciklama = Column(Text)
    tutar = Column(Float)
    odeme_turu = Column(Enum(OdemeTuruEnum), nullable=True)
    kasa_banka_id = Column(Integer, ForeignKey('kasalar_bankalar.id'), nullable=True)
    cari_id = Column(Integer, nullable=True)
    cari_tip = Column(Enum(CariTipiEnum), nullable=True)
    gelir_siniflandirma_id = Column(Integer, ForeignKey('gelir_siniflandirmalari.id'), nullable=True)
    gider_siniflandirma_id = Column(Integer, ForeignKey('gider_siniflandirmalari.id'), nullable=True)

    olusturma_tarihi_saat = Column(DateTime, default=datetime.now)
    olusturan_kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)

    kasa_banka_hesabi = relationship("KasaBanka", backref="gelir_gider_iliski")
    gelir_siniflandirma = relationship("GelirSiniflandirma", back_populates="gelir_giderler")
    gider_siniflandirma = relationship("GiderSiniflandirma", back_populates="gelir_giderler")
    olusturan_kullanici = relationship("Kullanici", foreign_keys=[olusturan_kullanici_id])

class KasaBankaHareket(Base):
    __tablename__ = 'kasa_banka_hareketleri'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    kasa_banka_id = Column(Integer, ForeignKey('kasalar_bankalar.id'), index=True)
    tarih = Column(Date)
    islem_turu = Column(String)
    islem_yone = Column(Enum(IslemYoneEnum))
    tutar = Column(Float)
    aciklama = Column(Text, nullable=True)
    kaynak = Column(String) # KaynakTipEnum ile uyumlu olmalı
    kaynak_id = Column(Integer, nullable=True)

    kasa_banka_hesabi = relationship("KasaBanka", back_populates="hareketler")

class UrunKategori(Base):
    __tablename__ = 'urun_kategorileri'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String, unique=True, index=True)
    stoklar = relationship("Stok", back_populates="kategori")

class UrunMarka(Base):
    __tablename__ = 'urun_markalari'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String, unique=True, index=True)
    stoklar = relationship("Stok", back_populates="marka")

class UrunGrubu(Base):
    __tablename__ = 'urun_gruplari'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String, unique=True, index=True)
    stoklar = relationship("Stok", back_populates="urun_grubu")

class UrunBirimi(Base):
    __tablename__ = 'urun_birimleri'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String, unique=True, index=True)
    stoklar = relationship("Stok", back_populates="birim")

class Ulke(Base):
    __tablename__ = 'ulkeler'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String, unique=True, index=True)
    stoklar = relationship("Stok", back_populates="mense_ulke")

class GelirSiniflandirma(Base):
    __tablename__ = 'gelir_siniflandirmalari'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String, unique=True, index=True)
    gelir_giderler = relationship("GelirGider", back_populates="gelir_siniflandirma")

class GiderSiniflandirma(Base):
    __tablename__ = 'gider_siniflandirmalari'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String, unique=True, index=True)
    gelir_giderler = relationship("GelirGider", back_populates="gider_siniflandirma")