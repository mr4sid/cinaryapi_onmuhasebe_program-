from sqlalchemy import Column, Integer, String, Numeric, TIMESTAMP, Date, Boolean, ForeignKey
from .veritabani import Base

class Kullanici(Base):
    __tablename__ = "kullanicilar"
    id = Column(Integer, primary_key=True, index=True)
    kullanici_adi = Column(String, unique=True, nullable=False)

class Musteri(Base):
    __tablename__ = "musteriler"
    id = Column(Integer, primary_key=True, index=True)
    kod = Column(String, unique=True, index=True)
    ad = Column(String, nullable=False)
    telefon = Column(String)
    adres = Column(String)
    vergi_dairesi = Column(String)
    vergi_no = Column(String)

class Tedarikci(Base):
    __tablename__ = "tedarikciler"
    id = Column(Integer, primary_key=True, index=True)
    tedarikci_kodu = Column(String, unique=True, index=True)
    ad = Column(String, nullable=False)
    telefon = Column(String)
    adres = Column(String)
    vergi_dairesi = Column(String)
    vergi_no = Column(String)

class UrunKategorileri(Base):
    __tablename__ = "urun_kategorileri"
    id = Column(Integer, primary_key=True)
    kategori_adi = Column(String, unique=True)

class UrunMarkalari(Base):
    __tablename__ = "urun_markalari"
    id = Column(Integer, primary_key=True)
    marka_adi = Column(String, unique=True)

class UrunGruplari(Base):
    __tablename__ = "urun_gruplari"
    id = Column(Integer, primary_key=True)
    grup_adi = Column(String, unique=True)

class UrunBirimleri(Base):
    __tablename__ = "urun_birimleri"
    id = Column(Integer, primary_key=True)
    birim_adi = Column(String, unique=True)

class UrunUlkeleri(Base):
    __tablename__ = "urun_ulkeleri"
    id = Column(Integer, primary_key=True)
    ulke_adi = Column(String, unique=True)

class Stok(Base):
    __tablename__ = "tbl_stoklar"
    id = Column(Integer, primary_key=True, index=True)
    urun_kodu = Column(String, unique=True, index=True, nullable=False)
    urun_adi = Column(String, nullable=False)
    stok_miktari = Column(Numeric)
    satis_fiyati_kdv_dahil = Column(Numeric)
    kdv_orani = Column(Numeric)
    min_stok_seviyesi = Column(Numeric)
    kategori_id = Column(Integer, ForeignKey("urun_kategorileri.id"))
    marka_id = Column(Integer, ForeignKey("urun_markalari.id"))
    urun_grubu_id = Column(Integer, ForeignKey("urun_gruplari.id"))
    urun_birimi_id = Column(Integer, ForeignKey("urun_birimleri.id"))
    ulke_id = Column(Integer, ForeignKey("urun_ulkeleri.id"))

class KasaBanka(Base):
    __tablename__ = "kasalar_bankalar"
    id = Column(Integer, primary_key=True, index=True)
    hesap_adi = Column(String, unique=True, nullable=False)
    bakiye = Column(Numeric)
    tip = Column(String)

class Fatura(Base):
    __tablename__ = "faturalar"
    id = Column(Integer, primary_key=True, index=True)
    fatura_no = Column(String, unique=True, nullable=False)
    tarih = Column(Date, nullable=False)
    tip = Column(String, nullable=False)
    cari_id = Column(Integer, nullable=False)
    toplam_kdv_dahil = Column(Numeric, nullable=False)
    odeme_turu = Column(String)
    misafir_adi = Column(String)
    kasa_banka_id = Column(Integer, ForeignKey("kasalar_bankalar.id"))
    vade_tarihi = Column(Date)
    olusturan_kullanici_id = Column(Integer)
    son_guncelleyen_kullanici_id = Column(Integer)

class FaturaKalemleri(Base):
    __tablename__ = "fatura_kalemleri"
    id = Column(Integer, primary_key=True, index=True)
    fatura_id = Column(Integer, ForeignKey("faturalar.id"), nullable=False)
    urun_id = Column(Integer, ForeignKey("tbl_stoklar.id"), nullable=False)
    miktar = Column(Numeric, nullable=False)
    birim_fiyat = Column(Numeric, nullable=False)  # KDV Hariç orijinal birim fiyat
    kdv_orani = Column(Numeric, nullable=False)
    kdv_tutari = Column(Numeric)
    kalem_toplam_kdv_haric = Column(Numeric)
    kalem_toplam_kdv_dahil = Column(Numeric)
    iskonto_yuzde_1 = Column(Numeric, default=0.0)
    iskonto_yuzde_2 = Column(Numeric, default=0.0)
    iskonto_tipi = Column(String)
    iskonto_degeri = Column(Numeric)
    alis_fiyati_fatura_aninda = Column(Numeric)
    kdv_orani_fatura_aninda = Column(Numeric)
    olusturma_tarihi_saat = Column(TIMESTAMP)
    olusturan_kullanici_id = Column(Integer)

class Siparis(Base):
    __tablename__ = "siparisler"
    id = Column(Integer, primary_key=True, index=True)
    siparis_no = Column(String, unique=True, nullable=False)
    tarih = Column(Date, nullable=False)
    cari_tip = Column(String, nullable=False)
    cari_id = Column(Integer, nullable=False)
    toplam_tutar = Column(Numeric, nullable=False)
    durum = Column(String, nullable=False)
    teslimat_tarihi = Column(Date)
    fatura_id = Column(Integer, ForeignKey("faturalar.id"))

class GelirGider(Base):
    __tablename__ = "gelir_gider"
    id = Column(Integer, primary_key=True, index=True)
    tarih = Column(Date, nullable=False)
    tip = Column(String, nullable=False)
    tutar = Column(Numeric, nullable=False)
    aciklama = Column(String)
    kaynak = Column(String)
    kasa_banka_id = Column(Integer, ForeignKey("kasalar_bankalar.id"))

class CariHareketler(Base):
    __tablename__ = "cari_hareketler"
    id = Column(Integer, primary_key=True, index=True)
    tarih = Column(Date, nullable=False)
    cari_tip = Column(String, nullable=False)
    cari_id = Column(Integer, nullable=False)
    islem_tipi = Column(String, nullable=False)
    tutar = Column(Numeric, nullable=False)
    referans_tip = Column(String)
    kasa_banka_id = Column(Integer, ForeignKey("kasalar_bankalar.id"))

class SirketBilgileri(Base):
    __tablename__ = "sirket_bilgileri"
    id = Column(Integer, primary_key=True, index=True)
    sirket_adi = Column(String)
    sirket_adresi = Column(String)
    sirket_telefonu = Column(String)
    sirket_email = Column(String)
    sirket_vergi_dairesi = Column(String)
    sirket_vergi_no = Column(String)
    sirket_logo_yolu = Column(String)    

class StokHareketleri(Base):
    __tablename__ = "stok_hareketleri"
    id = Column(Integer, primary_key=True, index=True)
    urun_id = Column(Integer, ForeignKey("tbl_stoklar.id"), nullable=False)
    tarih = Column(Date, nullable=False)
    islem_tipi = Column(String, nullable=False)
    miktar = Column(Numeric, nullable=False)
    onceki_stok = Column(Numeric)
    sonraki_stok = Column(Numeric)
    aciklama = Column(String)
    kaynak_tip = Column(String)  # Örn: 'FATURA', 'MANUEL'
    kaynak_id = Column(Integer)  # Örn: ilgili faturanın ID'si    

class SiparisKalemleri(Base):
    __tablename__ = "siparis_kalemleri"
    id = Column(Integer, primary_key=True, index=True)
    siparis_id = Column(Integer, ForeignKey("siparisler.id"), nullable=False)
    urun_id = Column(Integer, ForeignKey("tbl_stoklar.id"), nullable=False)
    miktar = Column(Numeric, nullable=False)
    birim_fiyat = Column(Numeric, nullable=False)  # KDV Hariç Orijinal Birim Fiyat
    kdv_orani = Column(Numeric, nullable=False)
    iskonto_yuzde_1 = Column(Numeric, default=0.0)
    iskonto_yuzde_2 = Column(Numeric, default=0.0)
    alis_fiyati_siparis_aninda = Column(Numeric)
    satis_fiyati_siparis_aninda = Column(Numeric)
    kdv_tutari = Column(Numeric)
    kalem_toplam_kdv_dahil = Column(Numeric)
    olusturan_kullanici_id = Column(Integer)
    olusturma_tarihi_saat = Column(TIMESTAMP)    

class GelirSiniflandirma(Base):
    __tablename__ = "gelir_siniflandirma"
    id = Column(Integer, primary_key=True, index=True)
    siniflandirma_adi = Column(String, unique=True, nullable=False)

class GiderSiniflandirma(Base):
    __tablename__ = "gider_siniflandirma"
    id = Column(Integer, primary_key=True, index=True)
    siniflandirma_adi = Column(String, unique=True, nullable=False)    

# Sirket Modeli (api/rotalar/sistem.py için)
class Sirket(Base):
    __tablename__ = "sirketler"
    id = Column(Integer, primary_key=True, index=True)
    sirket_adi = Column(String, index=True, unique=True, nullable=False)
    adres = Column(String)
    telefon = Column(String)
    email = Column(String)
    vergi_dairesi = Column(String)
    vergi_no = Column(String)
    ticaret_sicil_no = Column(String)

# Kullanıcı Modeli (api/rotalar/dogrulama.py için)
class Kullanici(Base):
    __tablename__ = "kullanicilar"
    id = Column(Integer, primary_key=True, index=True)
    kullanici_adi = Column(String, unique=True, index=True, nullable=False)
    sifre = Column(String, nullable=False) # Gerçekte hash'lenmiş şifre olmalı
    rol = Column(String, default="USER") # ADMIN, MANAGER, SALES, USER gibi roller

# Ürün Grubu Modeli
class UrunGrubu(Base):
    __tablename__ = "urun_gruplari"
    id = Column(Integer, primary_key=True, index=True)
    grup_adi = Column(String, unique=True, index=True, nullable=False)

# Ürün Birimi Modeli
class UrunBirimi(Base):
    __tablename__ = "urun_birimleri"
    id = Column(Integer, primary_key=True, index=True)
    birim_adi = Column(String, unique=True, index=True, nullable=False)

# Ülke Modeli
class Ulke(Base):
    __tablename__ = "ulkeler"
    id = Column(Integer, primary_key=True, index=True)
    ulke_adi = Column(String, unique=True, index=True, nullable=False)    
