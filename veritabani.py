# veritabani.py dosyasının içeriği
import logging
import sqlite3
import os
import sys
import hashlib
import json
import shutil
import traceback
from datetime import datetime, date
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas as rp_canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
import calendar
from yardimcilar import normalize_turkish_chars
# VERİTABANI VE LOG DOSYALARI İÇİN TEMEL DİZİN TANIMLAMA (GLOBAL ALAN)
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

data_dir = os.path.join(base_dir, 'data') # <-- BURASI GLOBAL TANIMLANMIŞ
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# LOGLAMA YAPILANDIRMASI
log_file_path = os.path.join(data_dir, 'application.log')

logging.basicConfig(filename=log_file_path, level=logging.DEBUG, # <-- Level'ı DEBUG yapın
                    format='%(asctime)s - %(levelname)s - %(message)s')

TURKISH_FONT_NORMAL = "Helvetica"
TURKISH_FONT_BOLD = "Helvetica-Bold"
try:
    dejavu_sans_normal_path = os.path.join(data_dir, 'DejaVuSans.ttf') # <-- Burayı güncelleyin
    dejavu_sans_bold_path = os.path.join(data_dir, 'DejaVuSans-Bold.ttf') # <-- Burayı güncelleyin

    # Font dosyalarının varlığını kontrol et ve sadece varsa kaydet
    if os.path.exists(dejavu_sans_normal_path):
        pdfmetrics.registerFont(TTFont('DejaVuSans', dejavu_sans_normal_path))
        TURKISH_FONT_NORMAL = "DejaVuSans"
    else:
        print(f"UYARI: {dejavu_sans_normal_path} bulunamadı. Varsayılan font kullanılacak.")

    if os.path.exists(dejavu_sans_bold_path):
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', dejavu_sans_bold_path))
        TURKISH_FONT_BOLD = "DejaVuSans-Bold"
    else:
        print(f"UYARI: {dejavu_sans_bold_path} bulunamadı. Varsayılan font kullanılacak.")

except Exception as e:
    print(f"KRİTİK FONT YÜKLEME HATASI: {e} - PDF'lerde Türkçe karakter sorunu olabilir.")

class OnMuhasebe:
    FATURA_TIP_ALIS = "ALIŞ"
    FATURA_TIP_SATIS = "SATIŞ"
    FATURA_TIP_DEVIR_GIRIS = "DEVİR_GİRİŞ"
    FATURA_TIP_SATIS_IADE = "SATIŞ İADE"
    FATURA_TIP_ALIS_IADE = "ALIŞ İADE"

    # Ödeme Türleri
    ODEME_TURU_NAKIT = "NAKİT"
    ODEME_TURU_KART = "KART"
    ODEME_TURU_EFT_HAVALE = "EFT/HAVALE"
    ODEME_TURU_CEK = "ÇEK"
    ODEME_TURU_SENET = "SENET"
    ODEME_TURU_ACIK_HESAP = "AÇIK HESAP"
    ODEME_TURU_ETKISIZ_FATURA = "ETKİSİZ FATURA"
    # Peşin Ödeme Türleri (Liste olarak tanımlanmıştır)
    # self.pesin_odeme_turleri = ["NAKİT", "KART", "EFT/HAVALE", "ÇEK", "SENET"] # Bu, __init__ içinde tanımlanmalı

    # Cari Tipleri
    CARI_TIP_MUSTERI = "MUSTERI"
    CARI_TIP_TEDARIKCI = "TEDARIKCI"

    # İşlem Tipleri (Cari Hareketler ve Gelir/Gider)
    ISLEM_TIP_ALACAK = "ALACAK"
    ISLEM_TIP_BORC = "BORC"
    ISLEM_TIP_TAHSILAT = "TAHSILAT"
    ISLEM_TIP_ODEME = "ODEME"
    ISLEM_TIP_GELIR = "GELİR"
    ISLEM_TIP_GIDER = "GİDER"

    # Kaynak Tipleri (Stok Hareketleri, Gelir/Gider, Cari Hareketler)
    KAYNAK_TIP_MANUEL = "MANUEL"
    KAYNAK_TIP_FATURA = "FATURA"
    KAYNAK_TIP_SIPARIS = "SIPARIS"
    KAYNAK_TIP_TAHSILAT = "TAHSILAT"
    KAYNAK_TIP_ODEME = "ODEME"
    KAYNAK_TIP_VERESIYE_BORC_MANUEL = "VERESIYE_BORC_MANUEL"
    KAYNAK_TIP_FATURA_SATIS_PESIN = "FATURA_SATIS_PESIN"
    KAYNAK_TIP_FATURA_ALIS_PESIN = "FATURA_ALIS_PESIN"
    KAYNAK_TIP_IADE_FATURA = "İADE_FATURA"
    KAYNAK_TIP_IADE_FATURA_SATIS_PESIN = "İADE_FATURA_SATIS_PESIN"
    KAYNAK_TIP_IADE_FATURA_ALIS_PESIN = "İADE_FATURA_ALIS_PESIN"

    # Stok Hareketleri İşlem Tipleri (Daha spesifik, açıklamada kullanılabilir)
    STOK_ISLEM_TIP_GIRIS_MANUEL = "Giriş (Manuel)"
    STOK_ISLEM_TIP_CIKIS_MANUEL = "Çıkış (Manuel)"
    STOK_ISLEM_TIP_SAYIM_FAZLASI = "Sayım Fazlası"
    STOK_ISLEM_TIP_SAYIM_EKSIGI = "Sayım Eksiği"
    STOK_ISLEM_TIP_ZAYIAT = "Zayiat"
    STOK_ISLEM_TIP_IADE_GIRIS = "İade Girişi"
    STOK_ISLEM_TIP_FATURA_ALIS = "Fatura Alış"
    STOK_ISLEM_TIP_FATURA_SATIS = "Fatura Satış"
    STOK_ISLEM_TIP_FATURA_SATIS_IADE = "Fatura Satış İade"
    STOK_ISLEM_TIP_FATURA_ALIS_IADE = "Fatura Alış İade"
    STOK_ISLEM_TIP_DEVIR_GIRIS = "Devir Giriş" # Genellikle 'DEVİR_GİRİŞ' fatura tipi için kullanılır.
    STOK_ISLEM_TIP_GIRIS_MANUEL_DUZELTME = "Giriş (Manuel Düzeltme)" # Stok kartından manuel düzeltme
    STOK_ISLEM_TIP_CIKIS_MANUEL_DUZELTME = "Çıkış (Manuel Düzeltme)" # Stok kartından manuel düzeltme

    # Sipariş Durumları
    SIPARIS_DURUM_BEKLEMEDE = "BEKLEMEDE"
    SIPARIS_DURUM_TAMAMLANDI = "TAMAMLANDI"
    SIPARIS_DURUM_KISMİ_TESLIMAT = "KISMİ_TESLİMAT"
    SIPARIS_DURUM_IPTAL_EDILDI = "İPTAL_EDİLDİ"

    # Sipariş Tipleri (arayüzdeki combobox için)
    SIPARIS_TIP_SATIS = "SATIŞ_SIPARIS"
    SIPARIS_TIP_ALIS = "ALIŞ_SIPARIS"

    # Genel İskonto Tipleri
    ISKONTO_TIP_YOK = "YOK"
    ISKONTO_TIP_YUZDE = "YUZDE"
    ISKONTO_TIP_TUTAR = "TUTAR"
    
    def __init__(self, db_name='on_muhasebe.db', data_dir=None): # data_dir parametresi eklendi
        self.app = None
        # data_dir'i parametre olarak al, eğer yoksa varsayılanı kullan (test veya direkt çağrımlar için)
        self.data_dir = data_dir if data_dir else os.path.dirname(os.path.abspath(__file__))
        self.db_name = os.path.join(self.data_dir, db_name)
        logging.debug(f"Veritabanı yolu: {self.db_name}")

        self.conn = sqlite3.connect(self.db_name, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        self.conn.row_factory = sqlite3.Row
        self.c = self.conn.cursor()
        self.c.execute("PRAGMA foreign_keys = ON;")

        self.PERAKENDE_MUSTERI_KODU = "PER000"
        self.perakende_musteri_id = None

        self.genel_tedarikci_id = None
        self.pesin_odeme_turleri = ["NAKİT", "KART", "EFT/HAVALE", "ÇEK", "SENET"]

        self.create_tables()

        self._ensure_perakende_musteri()
        self._ensure_genel_tedarikci()
        self._ensure_default_kasa()
        self._ensure_default_urun_birimi()
        self._ensure_default_ulke()

        self.sirket_bilgileri = self.sirket_bilgilerini_yukle()

        # Fontları burada kaydetmek, her yeni OnMuhasebe objesi oluştuğunda çalışmasını sağlar
        try:
            dejavu_sans_normal_path = os.path.join(self.data_dir, 'DejaVuSans.ttf')
            dejavu_sans_bold_path = os.path.join(self.data_dir, 'DejaVuSans-Bold.ttf')

            if os.path.exists(dejavu_sans_normal_path):
                if 'DejaVuSans' not in pdfmetrics.getRegisteredFontNames(): # Sadece kayıtlı değilse kaydet
                    pdfmetrics.registerFont(TTFont('DejaVuSans', dejavu_sans_normal_path))
                    global TURKISH_FONT_NORMAL
                    TURKISH_FONT_NORMAL = "DejaVuSans"
            else:
                print(f"UYARI: {dejavu_sans_normal_path} bulunamadı. Varsayılan font kullanılacak.")

            if os.path.exists(dejavu_sans_bold_path):
                if 'DejaVuSans-Bold' not in pdfmetrics.getRegisteredFontNames(): # Sadece kayıtlı değilse kaydet
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', dejavu_sans_bold_path))
                    global TURKISH_FONT_BOLD
                    TURKISH_FONT_BOLD = "DejaVuSans-Bold"
            else:
                print(f"UYARI: {dejavu_sans_bold_path} bulunamadı. Varsayılan font kullanılacak.")

        except Exception as e:
            print(f"KRİTİK FONT YÜKLEME HATASI: {e} - PDF'lerde Türkçe karakter sorunu olabilir.")

    def get_cari_bakiye_snapshot(self, cari_id, cari_tip, tarih_str):
        """
        Belirli bir tarihteki cari bakiyesini hesaplar.
        Bu metod, bir faturanın kesildiği tarihteki anlık bakiye durumunu almak için kullanılır.
        tarih_str: 'YYYY-MM-DD' formatında tarih.
        Dönüş: {'onceki_bakiye': float, 'bugun_odenen': float, 'kalan_borc': float}
        """
        onceki_bakiye = 0.0 # Belirtilen tarihten önceki bakiyeler için
        bugun_odenen_tahsil_edilen = 0.0 # Sadece fatura tarihiyle aynı günkü tahsilat/ödeme hareketleri

        try:
            # 1. Adım: Önceki Bakiye - Belirtilen tarihten önceki tüm hareketlerin net toplamı
            # Bu sorgu, 'tarih_str' ile belirtilen günden önceki tüm işlemleri kapsar.
            query_onceki = """
                SELECT islem_tipi, tutar, referans_tip FROM cari_hareketler
                WHERE cari_id = ? AND cari_tip = ? AND tarih < ?
            """
            self.c.execute(query_onceki, (cari_id, cari_tip, tarih_str))
            onceki_hareketler = self.c.fetchall()

            for h in onceki_hareketler:
                tutar_h = h['tutar'] or 0.0
                islem_tipi_h = h['islem_tipi']
                referans_tip_h = h['referans_tip']

                if cari_tip == self.CARI_TIP_MUSTERI:
                    # Müşteri bize borçlandı (bizim alacağımız)
                    if islem_tipi_h == self.ISLEM_TIP_ALACAK or referans_tip_h == self.KAYNAK_TIP_FATURA or referans_tip_h == self.KAYNAK_TIP_VERESIYE_BORC_MANUEL:
                        onceki_bakiye += tutar_h
                    # Müşteriden tahsilat veya satış iadesi
                    elif islem_tipi_h == self.ISLEM_TIP_TAHSILAT or referans_tip_h == self.KAYNAK_TIP_FATURA_SATIS_PESIN or referans_tip_h == self.KAYNAK_TIP_IADE_FATURA:
                        onceki_bakiye -= tutar_h
                elif cari_tip == self.CARI_TIP_TEDARIKCI:
                    # Biz tedarikçiye borçlandık (bizim borcumuz)
                    if islem_tipi_h == self.ISLEM_TIP_BORC or referans_tip_h == self.KAYNAK_TIP_FATURA or referans_tip_h == self.KAYNAK_TIP_VERESIYE_BORC_MANUEL:
                        onceki_bakiye += tutar_h
                    # Tedarikçiye ödeme veya alış iadesi
                    elif islem_tipi_h == self.ISLEM_TIP_ODEME or referans_tip_h == self.KAYNAK_TIP_FATURA_ALIS_PESIN or referans_tip_h == self.KAYNAK_TIP_IADE_FATURA:
                        onceki_bakiye -= tutar_h

            # 2. Adım: Bugün Yapılan Ödeme/Tahsilat - Sadece fatura tarihiyle AYNI GÜNE ait olan tahsilat/ödeme hareketleri
            # Bu sorgu, 'tarih_str' ile belirtilen GÜNDEKİ tüm işlemleri kapsar.
            query_bugun = """
                SELECT islem_tipi, tutar, referans_tip FROM cari_hareketler
                WHERE cari_id = ? AND cari_tip = ? AND tarih = ?
            """
            self.c.execute(query_bugun, (cari_id, cari_tip, tarih_str))
            bugun_hareketler = self.c.fetchall()

            # Kalan borç/alacak: Önceki bakiye + (bugünkü tüm ALACAK/BORÇ hareketleri) - (bugünkü tüm TAHSİLAT/ÖDEME hareketleri)
            kalan_borc_anlik = onceki_bakiye
            for h in bugun_hareketler:
                tutar_h = h['tutar'] or 0.0
                islem_tipi_h = h['islem_tipi']
                referans_tip_h = h['referans_tip']

                if cari_tip == self.CARI_TIP_MUSTERI:
                    if islem_tipi_h == self.ISLEM_TIP_ALACAK or referans_tip_h == self.KAYNAK_TIP_FATURA or referans_tip_h == self.KAYNAK_TIP_VERESIYE_BORC_MANUEL:
                        kalan_borc_anlik += tutar_h
                    elif islem_tipi_h == self.ISLEM_TIP_TAHSILAT or referans_tip_h == self.KAYNAK_TIP_FATURA_SATIS_PESIN or referans_tip_h == self.KAYNAK_TIP_IADE_FATURA:
                        kalan_borc_anlik -= tutar_h
                        # Bugüne ait tahsilatları toplama
                        if islem_tipi_h == self.ISLEM_TIP_TAHSILAT or referans_tip_h == self.KAYNAK_TIP_FATURA_SATIS_PESIN:
                            bugun_odenen_tahsil_edilen += tutar_h

                elif cari_tip == self.CARI_TIP_TEDARIKCI:
                    if islem_tipi_h == self.ISLEM_TIP_BORC or referans_tip_h == self.KAYNAK_TIP_FATURA or referans_tip_h == self.KAYNAK_TIP_VERESIYE_BORC_MANUEL:
                        kalan_borc_anlik += tutar_h
                    elif islem_tipi_h == self.ISLEM_TIP_ODEME or referans_tip_h == self.KAYNAK_TIP_FATURA_ALIS_PESIN or referans_tip_h == self.KAYNAK_TIP_IADE_FATURA:
                        kalan_borc_anlik -= tutar_h
                        # Bugüne ait ödemeleri toplama
                        if islem_tipi_h == self.ISLEM_TIP_ODEME or referans_tip_h == self.KAYNAK_TIP_FATURA_ALIS_PESIN:
                            bugun_odenen_tahsil_edilen += tutar_h

            return {
                'onceki_bakiye': onceki_bakiye,
                'bugun_odenen': bugun_odenen_tahsil_edilen,
                'kalan_borc': kalan_borc_anlik
            }
        except Exception as e:
            import logging
            import traceback
            logging.error(f"Cari bakiye anlık görüntü hatası: {e}\n{traceback.format_exc()}")
            return {
                'onceki_bakiye': 0.0,
                'bugun_odenen': 0.0,
                'kalan_borc': 0.0
            }



    def kasa_banka_hareket_ekle(self, kasa_banka_id, tutar, aciklama, referans_id):
        """
        Kasa/Banka hareketini gelir_gider tablosuna kaydeder ve kasa/banka bakiyesini günceller.
        Bu metot, dış bir transaction (örneğin fatura_olustur) içinde çağrılmalıdır.
        Kendi içinde BEGIN/COMMIT yapmaz.
        """
        if kasa_banka_id is None:
            logging.warning(f"Kasa/Banka ID boş olduğu için hareket kaydedilemedi: {aciklama}")
            return False, "Kasa/Banka hesabı belirtilmediği için hareket kaydedilemedi."

        current_time = self.get_current_datetime_str()
        olusturan_id = self._get_current_user_id() 

        try:
            # Gelir/Gider tablosuna kaydı ekle
            gg_tip = self.ISLEM_TIP_GELIR if tutar >= 0 else self.ISLEM_TIP_GIDER 
            
            self.c.execute("""
                INSERT INTO gelir_gider (
                    tarih, tip, tutar, aciklama, kaynak, kaynak_id, kasa_banka_id,
                    olusturma_tarihi_saat, olusturan_kullanici_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime('%Y-%m-%d'),
                gg_tip,
                abs(tutar), 
                aciklama,
                'KASA_BANKA_HAREKET', # Bu kaydın kaynağının Kasa/Banka hareketi olduğunu belirt
                referans_id, 
                kasa_banka_id,
                current_time,
                olusturan_id
            ))
            
            # Kasa/Banka bakiyesini güncelle
            is_bakiye_artir = (tutar >= 0)
            # kasa_banka_bakiye_guncelle metodu artık kendi transaction'ını yönetmiyor.
            self.kasa_banka_bakiye_guncelle(kasa_banka_id, abs(tutar), artir=is_bakiye_artir)
            
            return True, "Kasa/Banka hareketi ve bakiye başarıyla güncellendi."
        except Exception as e:
            # Bu hata durumunda dış transaction tarafından rollback yapılacağı için burada ayrıca rollback yapmıyoruz.
            logging.error(f"Kasa/Banka hareketi eklenirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Kasa/Banka hareketi eklenirken bir hata oluştu: {e}"

    def _get_current_user_id(self):
        """
        Eğer uygulama context'inde geçerli bir kullanıcı varsa ID'sini döndürür.
        Aksi takdirde varsayılan bir sistem kullanıcısı ID'si (1, genelde admin) döndürür.
        """
        if self.app and hasattr(self.app, 'current_user') and self.app.current_user and len(self.app.current_user) > 0:
            return self.app.current_user[0] # current_user[0] kullanıcının ID'sidir
        return 1 # Varsayılan olarak admin kullanıcısının ID'si kabul edilebilir.

    def _ensure_genel_tedarikci(self):
        try:
            self.c.execute("SELECT id FROM tedarikciler WHERE tedarikci_kodu=?", ("GENEL_TEDARIKCI",))
            result = self.c.fetchone()
            if result:
                self.genel_tedarikci_id = result[0]
                return True, "Genel Tedarikçi bulundu."
            else:
                olusturan_id = 1 # Genellikle 'admin' kullanıcısının ID'si
                current_time = self.get_current_datetime_str()
                self.c.execute("INSERT INTO tedarikciler (tedarikci_kodu, ad, telefon, adres, vergi_dairesi, vergi_no, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                               ("GENEL_TEDARIKCI", "Genel Tedarikçi (Toplu İşlem)", "-", "-", "-", "-", current_time, olusturan_id))
                self.genel_tedarikci_id = self.c.lastrowid
                self.conn.commit()
                return True, "Genel Tedarikçi başarıyla oluşturuldu."
        except Exception as e:
            return False, f"Genel tedarikçi oluşturulurken/kontrol edilirken kritik hata: {e}"
       
    def clear_log_file(self):
        try:
            log_file_path = os.path.join(self.data_dir, 'application.log')
            if os.path.exists(log_file_path):
                with open(log_file_path, 'w') as f:
                    f.truncate(0) # Dosyanın içeriğini sıfırlar
                return True, "Log dosyası başarıyla sıfırlandı."
            else:
                return True, "Log dosyası bulunamadı, sıfırlama gerekmiyor."
        except Exception as e:
            logging.error(f"Log dosyası sıfırlanırken hata oluştu: {e}")
            return False, f"Log dosyası sıfırlanırken hata oluştu: {e}"


    def get_perakende_musteri_id(self):
        """
        Veritabanındaki "Perakende Satış Müşterisi"nin ID'sini döndürür.
        Eğer yoksa, oluşturur ve ID'sini döndürür.
        """
        conn = self.conn
        cursor = conn.cursor()

        # Perakende Müşterisi'ni ara
        # Artık 'kod' sütununu kullanabiliriz.
        cursor.execute("SELECT id FROM musteriler WHERE ad = ? AND kod = ?", ('Perakende Satış Müşterisi', 'PER000'))
        perakende_musteri = cursor.fetchone()

        if perakende_musteri:
            return perakende_musteri['id']
        else:
            # Eğer yoksa, oluştur
            try:
                default_user_id = 1 
                if self.app and self.app.current_user:
                    default_user_id = self.app.current_user[0] 

                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute("""
                    INSERT INTO musteriler (ad, soyad, kod, vergi_dairesi, vergi_no, adres, telefon, email, notlar,
                                            olusturma_tarihi_saat, olusturan_kullanici_id,
                                            son_guncelleme_tarihi_saat, son_guncelleyen_kullanici_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, ('Perakende Satış Müşterisi', '', 'PER000', '', '', '', '', '', 'Sistem tarafından otomatik oluşturulan perakende satış müşterisi.',
                      current_time, default_user_id, 
                      current_time, default_user_id))
                conn.commit()
                return cursor.lastrowid
            except Exception as e:
                print(f"Perakende müşteri oluşturulurken hata oluştu: {e}")
                if self.app:
                    self.app.set_status(f"Hata: Perakende müşteri oluşturulamadı: {e}")
                return None

    def get_monthly_sales_summary(self, baslangic_tarih, bitis_tarih):
        """Belirtilen tarih aralığındaki aylık satış toplamlarını döndürür."""
        query = """
            SELECT
                STRFTIME('%Y-%m', tarih) AS ay,
                SUM(toplam_kdv_dahil) AS toplam_satis
            FROM faturalar
            WHERE tip = 'SATIŞ' AND tarih BETWEEN ? AND ?
            GROUP BY ay
            ORDER BY ay;
        """
        self.c.execute(query, (baslangic_tarih, bitis_tarih))
        return self.c.fetchall()

    def get_monthly_income_expense_summary(self, baslangic_tarih, bitis_tarih):
        """Belirtilen tarih aralığındaki aylık toplam gelir ve giderleri döndürür."""
        query = """
            SELECT
                STRFTIME('%Y-%m', tarih) AS ay,
                SUM(CASE WHEN tip = 'GELİR' THEN tutar ELSE 0 END) AS toplam_gelir,
                SUM(CASE WHEN tip = 'GİDER' THEN tutar ELSE 0 END) AS toplam_gider
            FROM gelir_gider
            WHERE tarih BETWEEN ? AND ?
            GROUP BY ay
            ORDER BY ay;
        """
        self.c.execute(query, (baslangic_tarih, bitis_tarih))
        return self.c.fetchall()

    def get_monthly_gross_profit_summary(self, baslangic_tarih, bitis_tarih):
        """
        Belirtilen tarih aralığındaki aylık brüt kâr ve satılan malın maliyetini döndürür.
        """
        query = """
            SELECT
                STRFTIME('%Y-%m', f.tarih) AS ay,
                SUM(f.toplam_kdv_dahil) AS toplam_satis_geliri,
                SUM(fk.miktar * fk.alis_fiyati_fatura_aninda) AS toplam_alis_maliyeti
            FROM faturalar f
            JOIN fatura_kalemleri fk ON f.id = fk.fatura_id
            WHERE f.tip = 'SATIŞ' AND f.tarih BETWEEN ? AND ?
            GROUP BY ay
            ORDER BY ay;
        """
        self.c.execute(query, (baslangic_tarih, bitis_tarih))
        return self.c.fetchall()

    def get_monthly_cash_flow_summary(self, baslangic_tarih, bitis_tarih):
        """
        Belirtilen tarih aralığındaki aylık toplam nakit girişi ve çıkışını (kasa/banka ile ilişkili) döndürür.
        """
        query = """
            SELECT
                STRFTIME('%Y-%m', gg.tarih) AS ay,
                SUM(CASE WHEN gg.tip = 'GELİR' THEN gg.tutar ELSE 0 END) AS toplam_nakit_giris,
                SUM(CASE WHEN gg.tip = 'GİDER' THEN gg.tutar ELSE 0 END) AS toplam_nakit_cikis
            FROM gelir_gider gg
            WHERE gg.kasa_banka_id IS NOT NULL AND gg.tarih BETWEEN ? AND ?
            GROUP BY ay
            ORDER BY ay;
        """
        self.c.execute(query, (baslangic_tarih, bitis_tarih))
        return self.c.fetchall()

    def get_top_selling_product_of_month(self):
        """
        Mevcut ayda en çok satılan ürünü (miktara göre) döndürür.
        Dönüş: (urun_adi, toplam_miktar) veya None
        """
        current_month_start = datetime.now().strftime('%Y-%m-01')
        current_month_end_day = calendar.monthrange(datetime.now().year, datetime.now().month)[1]
        current_month_end = datetime.now().strftime(f'%Y-%m-{current_month_end_day}')

        query = """
            SELECT 
                s.urun_adi, 
                SUM(fk.miktar) AS toplam_miktar
            FROM fatura_kalemleri fk
            JOIN faturalar f ON fk.fatura_id = f.id
            JOIN tbl_stoklar s ON fk.urun_id = s.id
            WHERE f.tip = 'SATIŞ' AND f.tarih BETWEEN ? AND ?
            GROUP BY s.urun_adi
            ORDER BY toplam_miktar DESC
            LIMIT 1
        """
        self.c.execute(query, (current_month_start, current_month_end))
        result = self.c.fetchone()
        return result if result else None

    def get_today_transaction_summary(self):
        """
        Bugün yapılan tüm önemli hareketlerin (satış/alış faturaları, tahsilatlar, ödemeler) özetini döndürür.
        Dönüş: {'toplam_satis_tutari': float, 'toplam_alis_tutari': float, 'toplam_tahsilat_tutari': float, 'toplam_odeme_tutari': float, 'toplam_fatura_sayisi': int, 'toplam_cari_hareket_sayisi': int}
        """
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        # Bugün kesilen satış ve alış faturalarının toplam tutarı ve sayısı
        self.c.execute("SELECT SUM(toplam_kdv_dahil) FROM faturalar WHERE tarih = ? AND tip = ?", (today_str, self.FATURA_TIP_SATIS))
        toplam_satis_tutari = self.c.fetchone()[0] or 0.0

        self.c.execute("SELECT SUM(toplam_kdv_dahil) FROM faturalar WHERE tarih = ? AND tip = ?", (today_str, self.FATURA_TIP_ALIS))
        toplam_alis_tutari = self.c.fetchone()[0] or 0.0

        self.c.execute("SELECT COUNT(id) FROM faturalar WHERE tarih = ? AND tip IN (?, ?)", (today_str, self.FATURA_TIP_SATIS, self.FATURA_TIP_ALIS))
        toplam_fatura_sayisi = self.c.fetchone()[0] or 0

        # Bugün yapılan tüm tahsilatların toplam tutarı (manuel veya peşin fatura kaynaklı)
        self.c.execute("SELECT SUM(tutar) FROM cari_hareketler WHERE tarih = ? AND islem_tipi = ?", (today_str, self.ISLEM_TIP_TAHSILAT))
        toplam_tahsilat_tutari = self.c.fetchone()[0] or 0.0

        # Bugün yapılan tüm ödemelerin toplam tutarı (manuel veya peşin fatura kaynaklı)
        self.c.execute("SELECT SUM(tutar) FROM cari_hareketler WHERE tarih = ? AND islem_tipi = ?", (today_str, self.ISLEM_TIP_ODEME))
        toplam_odeme_tutari = self.c.fetchone()[0] or 0.0

        # Bugün yapılan tüm cari hareketlerin (faturalar, tahsilatlar, ödemeler, veresiye borçlar) sayısı
        self.c.execute("SELECT COUNT(id) FROM cari_hareketler WHERE tarih = ?", (today_str,))
        toplam_cari_hareket_sayisi = self.c.fetchone()[0] or 0


        return {
            'toplam_satis_tutari': toplam_satis_tutari,
            'toplam_alis_tutari': toplam_alis_tutari, # Alışları da ekledim
            'toplam_tahsilat_tutari': toplam_tahsilat_tutari,
            'toplam_odeme_tutari': toplam_odeme_tutari,
            'toplam_fatura_sayisi': toplam_fatura_sayisi,
            'toplam_cari_hareket_sayisi': toplam_cari_hareket_sayisi
        }

    def get_top_selling_products(self, baslangic_tarih, bitis_tarih, limit=5):
        """
        Belirtilen tarih aralığında en çok satılan ürünleri (miktara göre) döndürür.
        """
        query = """
            SELECT
                s.urun_adi,
                SUM(fk.miktar) AS toplam_miktar
            FROM faturalar f
            JOIN fatura_kalemleri fk ON f.id = fk.fatura_id
            JOIN tbl_stoklar s ON fk.urun_id = s.id
            WHERE f.tip = 'SATIŞ' AND f.tarih BETWEEN ? AND ?
            GROUP BY s.urun_adi
            ORDER BY toplam_miktar DESC
            LIMIT ?;
        """
        self.c.execute(query, (baslangic_tarih, bitis_tarih, limit))
        return self.c.fetchall()

    def get_stock_value_by_category(self):
        """
        Mevcut stoktaki ürünlerin kategori bazında toplam KDV dahil alış değerini döndürür.
        """
        query = """
            SELECT
                uk.kategori_adi,
                SUM(s.stok_miktari * s.alis_fiyati_kdv_dahil) AS toplam_deger
            FROM tbl_stoklar s
            LEFT JOIN urun_kategorileri uk ON s.kategori_id = uk.id
            GROUP BY uk.kategori_adi
            HAVING SUM(s.stok_miktari * s.alis_fiyati_kdv_dahil) > 0 -- Değeri olan kategorileri al
            ORDER BY toplam_deger DESC;
        """
        self.c.execute(query)
        return self.c.fetchall()


    def son_fatura_no_getir(self, fatura_tipi):
        """
        Belirtilen fatura tipi için benzersiz bir fatura numarası oluşturur.
        Format: TIP-YYYYAA_HHMMSSms (örn: SAT-20250703150649123456)
        """
        prefix = ""
        if fatura_tipi == 'SATIŞ':
            prefix = 'SAT'
        elif fatura_tipi == 'ALIŞ':
            prefix = 'AL'
        else: # Diğer tipler için varsayılan
            prefix = 'FAT'
        
        # YYYYMMDDHHMMSSms formatında benzersiz bir zaman damgası kullanarak fatura numarası oluştur
        return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    def get_son_fatura_kalemi_bilgisi(self, cari_id, urun_id, fatura_tipi):
        """
        Belirli bir cari (müşteri/tedarikçi) ve ürün için son fatura kalemi bilgilerini döndürür.
        Bu, son fiyatlandırma ve iskonto bilgilerini hatırlamak için kullanılır.
        Dönüş: (birim_fiyat, kdv_orani, iskonto_yuzde_1, iskonto_yuzde_2) veya None
        Not: birim_fiyat burada iskonto uygulanmış KDV Dahil Birim Fiyatıdır.
        """
        query = """
            SELECT
                fk.birim_fiyat,           -- Orijinal KDV Hariç Birim Fiyatı (3)
                fk.kdv_orani,             -- KDV Oranı (4)
                fk.iskonto_yuzde_1,       -- İskonto Yüzde 1 (10)
                fk.iskonto_yuzde_2,       -- İskonto Yüzde 2 (11)
                f.tarih                   -- Fatura Tarihi (Sıralama için)
            FROM fatura_kalemleri fk
            JOIN faturalar f ON fk.fatura_id = f.id
            WHERE f.cari_id = ? AND fk.urun_id = ? AND f.tip = ?
            ORDER BY f.tarih DESC, f.id DESC -- En yeni faturadan başla
            LIMIT 1
        """
        params = (cari_id, urun_id, fatura_tipi)
        self.c.execute(query, params)
        result = self.c.fetchone()

        if result:
            # birim_fiyat (original_kdv_haric_bf) , kdv_orani, iskonto_yuzde_1, iskonto_yuzde_2
            original_kdv_haric_bf = result[0]
            kdv_orani = result[1]
            iskonto_yuzde_1 = result[2]
            iskonto_yuzde_2 = result[3]

            # Fatura oluşturma ekranında Birim Fiyat (KDV Dahil) gösterildiği için
            # ve bu fiyat aynı zamanda iskontoları da içereceği için,
            # burada iskonto uygulanmış KDV Dahil birim fiyatını hesaplayıp dönelim.
            
            # 1. Orijinal (iskontosuz) KDV Dahil Birim Fiyatı
            original_kdv_dahil_bf = original_kdv_haric_bf * (1 + kdv_orani / 100)

            # 2. İskonto 1'i uygula
            fiyat_iskonto_1_sonrasi_dahil = original_kdv_dahil_bf * (1 - iskonto_yuzde_1 / 100)
            
            # 3. İskonto 2'yi uygula
            nihai_iskontolu_kdv_dahil_bf = fiyat_iskonto_1_sonrasi_dahil * (1 - iskonto_yuzde_2 / 100)

            return (nihai_iskontolu_kdv_dahil_bf, kdv_orani, iskonto_yuzde_1, iskonto_yuzde_2)
        else:
            return None # Kayıt bulunamazsa None döndür

    def manuel_stok_hareketi_sil(self, hareket_id):
        """
        Sadece 'MANUEL' kaynaklı bir stok hareketini siler ve stok miktarını tersine günceller.
        """
        try:
            self.conn.execute("BEGIN TRANSACTION")

            # 1. Adım: Hareketin detaylarını ve kaynağını kontrol et
            self.c.execute("SELECT urun_id, miktar, islem_tipi, kaynak FROM stok_hareketleri WHERE id=?", (hareket_id,))
            hareket = self.c.fetchone()

            if not hareket:
                self.conn.rollback()
                return False, "Silinecek stok hareketi bulunamadı."

            if hareket['kaynak'] != 'MANUEL':
                self.conn.rollback()
                return False, "Sadece manuel olarak eklenmiş stok hareketleri silinebilir."

            urun_id = hareket['urun_id']
            miktar = hareket['miktar']
            islem_tipi = hareket['islem_tipi']

            # 2. Adım: Stok miktarını tersine çevir
            stok_fark_tersi = 0.0
            if 'Giriş' in islem_tipi or 'Fazlası' in islem_tipi or 'İade Girişi' in islem_tipi:
                stok_fark_tersi = -miktar # Giriş siliniyorsa stoktan düş
            elif 'Çıkış' in islem_tipi or 'Eksiği' in islem_tipi or 'Zayiat' in islem_tipi:
                stok_fark_tersi = miktar # Çıkış siliniyorsa stoka ekle

            if stok_fark_tersi != 0:
                # _stok_guncelle_ve_hareket_kaydet metodunu kullanarak stok ve yeni bir hareket kaydı oluşturun.
                # Bu aslında manuel silme işlemini "geri alma" hareketi olarak kaydedecektir.
                # Ancak burada istenen direkt kaydı silmek ve ana stoku düzeltmek.
                # Eğer stok hareketi geçmişini "silinen hareket" olarak tutmak istemiyorsak, manuel UPDATE yapmalıyız.
                # Mevcut mantık, kaydı silip stoğu manuel düzeltmektir.
                self.c.execute("UPDATE tbl_stoklar SET stok_miktari = stok_miktari + ? WHERE id = ?", (stok_fark_tersi, urun_id))

            # 3. Adım: Stok hareket kaydını sil
            self.c.execute("DELETE FROM stok_hareketleri WHERE id=?", (hareket_id,))

            self.conn.commit()
            return True, f"ID: {hareket_id} numaralı manuel stok hareketi başarıyla silindi ve stok güncellendi."

        except Exception as e:
            self.conn.rollback()
            error_details = traceback.format_exc()
            logging.error(f"Manuel stok hareketi silinirken hata: {e}\nDetaylar: {error_details}")
            return False, "Manuel stok hareketi silinirken beklenmeyen bir hata oluştu."

    def get_gecmis_fatura_kalemi_bilgileri(self, cari_id, urun_id, fatura_tipi, limit=5):
        """
        Belirli bir cari (müşteri/tedarikçi) ve ürün için geçmiş fatura kalemi bilgilerini döndürür.
        Bu, "Fiyat Geçmişi" butonu pop-up'ı için kullanılır.
        Dönüş: [(fatura_id, fatura_no, fatura_tarihi, iskontolu_kdv_dahil_bf, iskonto_yuzde_1, iskonto_yuzde_2), ...]
        Not: birim_fiyat burada iskonto uygulanmış KDV Dahil Birim Fiyatıdır.
        """
        query = """
            SELECT
                    f.id,                      -- Fatura ID
                f.fatura_no,               -- Fatura Numarası
                f.tarih,                   -- Fatura Tarihi
                fk.birim_fiyat,            -- Orijinal KDV Hariç Birim Fiyatı
                fk.kdv_orani,              -- KDV Oranı
                fk.iskonto_yuzde_1,        -- İskonto Yüzde 1
                fk.iskonto_yuzde_2         -- İskonto Yüzde 2
            FROM fatura_kalemleri fk
            JOIN faturalar f ON fk.fatura_id = f.id
            WHERE f.cari_id = ? AND fk.urun_id = ? AND f.tip = ?
            ORDER BY f.tarih DESC, f.id DESC -- En yeni faturalardan başla
            LIMIT ?
        """
        params = (cari_id, urun_id, fatura_tipi, limit)
        self.c.execute(query, params)
        raw_results = self.c.fetchall()

        formatted_results = []
        for result in raw_results:
            fatura_id = result['id']
            fatura_no = result['fatura_no']
            fatura_tarihi_obj = result['tarih'] # Veritabanından gelen tarih nesnesi
            original_kdv_haric_bf = result['birim_fiyat']
            kdv_orani = result['kdv_orani']
            iskonto_yuzde_1 = result['iskonto_yuzde_1']
            iskonto_yuzde_2 = result['iskonto_yuzde_2']

            # Fatura oluşturma ekranında Birim Fiyat (KDV Dahil) gösterildiği için
            # ve bu fiyat aynı zamanda iskontoları da içereceği için,
            # burada iskonto uygulanmış KDV Dahil birim fiyatını hesaplayıp dönelim.
        
            # 1. Orijinal (iskontosuz) KDV Dahil Birim Fiyatı
            original_kdv_dahil_bf = original_kdv_haric_bf * (1 + kdv_orani / 100)

            # 2. İskonto 1'i uygula
            fiyat_iskonto_1_sonrasi_dahil = original_kdv_dahil_bf * (1 - iskonto_yuzde_1 / 100)

            # 3. İskonto 2'yi uygula
            nihai_iskontolu_kdv_dahil_bf = fiyat_iskonto_1_sonrasi_dahil * (1 - iskonto_yuzde_2 / 100)

            # ### HATA DÜZELTMESİ BURADA ###
            # Gelen veri zaten bir tarih nesnesi olduğu için strptime kullanmıyoruz.
            # Doğrudan strftime ile formatlıyoruz.
            if isinstance(fatura_tarihi_obj, (datetime, date)):
                formatted_date = fatura_tarihi_obj.strftime('%d.%m.%Y')
            else:
                # Beklenmedik bir durum (veri string ise veya None ise) için yedek kontrol
                formatted_date = str(fatura_tarihi_obj)

            formatted_results.append((
                fatura_id,
                fatura_no,
                formatted_date,
                nihai_iskontolu_kdv_dahil_bf,
                iskonto_yuzde_1,
                iskonto_yuzde_2
            ))
        return formatted_results

    def get_stok_miktari_for_kontrol(self, urun_id, fatura_id_hariç=None):
        """
        Bir ürünün güncel stok miktarını döndürür.
        Eğer fatura_id_hariç belirtilirse (yani bir fatura düzenleniyorsa),
        o faturadaki kalemlerin stok etkisi geçici olarak hesaptan düşülür (geri alınır).
        Bu, düzenleme anında o faturadaki ürünlerin hala stokta "gibi" kabul edilmesini sağlar,
        böylece anlamsız stok yetersizliği uyarıları önlenir.
        """
        # Veritabanından ürünün mevcut fiziksel stok miktarını al.
        self.c.execute("SELECT stok_miktari FROM tbl_stoklar WHERE id=?", (urun_id,))
        mevcut_stok = self.c.fetchone()
        if not mevcut_stok:
            # Eğer ürün bulunamazsa veya stok miktarı boşsa 0.0 kabul et.
            return 0.0 

        stok_miktari_db = mevcut_stok[0]
        # Kontrol için kullanılacak başlangıç stok miktarı, mevcut veritabanı stoğudur.
        stok_miktari_kontrolde_kullanilacak = stok_miktari_db

        # Eğer bir fatura düzenleniyorsa (fatura_id_hariç parametresi varsa)
        # o faturadaki bu ürünün miktarını hesaptan düşürmeliyiz.
        # Neden? Çünkü fatura düzenlenirken, fatura zaten var ve stok etkisi zaten gerçekleşti.
        # Bu miktarı tekrar stoktan düşersek hatalı bir stok kontrolü yapmış oluruz.
        if fatura_id_hariç is not None:
            # Düzenlenen faturadaki bu ürünün miktarını ve fatura tipini al.
            self.c.execute("""
                SELECT SUM(fk.miktar), f.tip
                FROM fatura_kalemleri fk
                JOIN faturalar f ON fk.fatura_id = f.id
                WHERE fk.fatura_id = ? AND fk.urun_id = ?
            """, (fatura_id_hariç, urun_id))
            fatura_kalem_miktari_data = self.c.fetchone()

            if fatura_kalem_miktari_data and fatura_kalem_miktari_data[0] is not None:
                miktar_bu_faturada = fatura_kalem_miktari_data[0]
                fatura_tipi_bu_faturada = fatura_kalem_miktari_data[1]

                # Eğer bu bir SATIŞ faturası ise:
                # Fatura oluşturulduğunda bu miktar stoktan düşülmüştür.
                # Düzenlerken, bu miktarı geçici olarak stoğa "geri ekleyerek"
                # yani stoktaymış gibi kabul ederek kontrol yapmalıyız.
                # Böylece, kullanıcının "zaten sattığı" ürün için "stok yetersiz" uyarısı alması engellenir.
                if fatura_tipi_bu_faturada == 'SATIŞ':
                    stok_miktari_kontrolde_kullanilacak += miktar_bu_faturada
                # Eğer bu bir ALIŞ faturası ise:
                # Fatura oluşturulduğunda bu miktar stoka eklenmiştir.
                # Düzenlerken, bu miktarı geçici olarak stoktan "çıkararak"
                # yani stokta yokmuş gibi kabul ederek kontrol yapmalıyız.
                # Bu senaryoda aslında çok bir fark yaratmayabilir, çünkü alış faturasında stok artışı beklenir.
                # Ancak tutarlılık için eklenmiştir.
                elif fatura_tipi_bu_faturada == 'ALIŞ':
                    stok_miktari_kontrolde_kullanilacak -= miktar_bu_faturada
        
        # Son olarak, hesaplanan stok miktarını döndür.
        return stok_miktari_kontrolde_kullanilacak

    def get_recent_cari_hareketleri(self, cari_tip, cari_id, limit=10):
        """
        Belirli bir cari hesabın son işlemlerini döndürür.
        """
        query = """
            SELECT 
                ch.tarih, 
                ch.islem_tipi, 
                ch.tutar, 
                ch.aciklama, 
                kb.hesap_adi 
            FROM cari_hareketler ch
            LEFT JOIN kasalar_bankalar kb ON ch.kasa_banka_id = kb.id
            WHERE ch.cari_tip = ? AND ch.cari_id = ?
            ORDER BY ch.tarih DESC, ch.olusturma_tarihi_saat DESC
            LIMIT ?
        """
        self.c.execute(query, (cari_tip, cari_id, limit))
        return self.c.fetchall()

    def get_current_datetime_str(self):
        """Geçerli tarih ve saati 'YYYY-AA-GG HH:MM:SS' formatında döndürür."""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


    def _get_config_path(self):
        return os.path.join(data_dir, 'config.json')

    def _log_audit_action(self, action_type, table_name, record_id, details):
        """
        Veritabanı üzerinde yapılan önemli eylemleri denetim kaydına (audit log) kaydeder.
        Şimdilik sadece konsola yazdırıyoruz. Gerçek bir sistemde ayrı bir tabloya kaydedilmelidir.
        """
        # self.app'in var olup olmadığını kontrol edin
        user_info = self.app.current_user if self.app and hasattr(self.app, 'current_user') and self.app.current_user else (None, "Sistem", "Bilinmeyen")
        user_id = user_info[0]
        username = user_info[1]

        log_message = f"AUDIT: [{self.get_current_datetime_str()}] User: {username} (ID: {user_id}) | " \
                      f"Action: {action_type} | Table: {table_name} | Record ID: {record_id} | Details: {details}"
        print(log_message)
        # TODO: İleride denetim kaydını ayrı bir veritabanı tablosuna kaydetmek için burayı geliştirin.

    def get_cari_genel_bakiyeler(self, cari_id, cari_tip):
        """
        Bir cari hesabın tüm zamanlara ait toplam alacak, borç, tahsilat ve ödeme tutarlarını döndürür.
        `toplam_alacak` = Müşterinin bize olan borcu (bizim alacağımız).
        `toplam_borc` = Bizim cariye olan borcumuz (bizim borcumuz).
        `toplam_tahsilat` = Müşteriden alınan tahsilatların toplamı.
        `toplam_odeme` = Tedarikçiye yapılan ödemelerin toplamı.
        """
        # Müşterinin bize olan borcu (Bizim alacağımız)
        # MUSTERI: islem_tipi = 'ALACAK' veya referans_tip = 'FATURA' (SATIŞ) veya 'VERESIYE_BORC_MANUEL' (Müşteriden)
        query_musteri_alacaklari_bize = """
            SELECT SUM(tutar) FROM cari_hareketler
            WHERE cari_id = ? AND cari_tip = 'MUSTERI' 
            AND (islem_tipi = 'ALACAK' OR referans_tip = 'FATURA' OR referans_tip = 'VERESIYE_BORC_MANUEL')
        """
        self.c.execute(query_musteri_alacaklari_bize, (cari_id,))
        musteri_borcu_bize = self.c.fetchone()[0] or 0.0

        # Müşteriden gelen tahsilatlar (bizim tahsilatımız)
        # MUSTERI: islem_tipi = 'TAHSILAT' veya referans_tip = 'FATURA_SATIS_PESIN'
        query_musteri_tahsilatlari = """
            SELECT SUM(tutar) FROM cari_hareketler
            WHERE cari_id = ? AND cari_tip = 'MUSTERI' 
            AND (islem_tipi = 'TAHSILAT' OR referans_tip = 'FATURA_SATIS_PESIN')
        """
        self.c.execute(query_musteri_tahsilatlari, (cari_id,))
        musteri_tahsilati = self.c.fetchone()[0] or 0.0

        # Tedarikçiye olan bizim borcumuz
        # TEDARIKCI: islem_tipi = 'BORC' veya referans_tip = 'FATURA' (ALIŞ) veya 'VERESIYE_BORC_MANUEL' (Tedarikçiden)
        query_tedarikci_borclari_bize = """
            SELECT SUM(tutar) FROM cari_hareketler
            WHERE cari_id = ? AND cari_tip = 'TEDARIKCI' 
            AND (islem_tipi = 'BORC' OR referans_tip = 'FATURA' OR referans_tip = 'VERESIYE_BORC_MANUEL')
        """
        self.c.execute(query_tedarikci_borclari_bize, (cari_id,))
        tedarikci_borcu_bize = self.c.fetchone()[0] or 0.0

        # Tedarikçiye yapılan ödemeler
        # TEDARIKCI: islem_tipi = 'ODEME' veya referans_tip = 'FATURA_ALIS_PESIN'
        query_tedarikci_odemeleri = """
            SELECT SUM(tutar) FROM cari_hareketler
            WHERE cari_id = ? AND cari_tip = 'TEDARIKCI' 
            AND (islem_tipi = 'ODEME' OR referans_tip = 'FATURA_ALIS_PESIN')
        """
        self.c.execute(query_tedarikci_odemeleri, (cari_id,))
        tedarikci_odemesi = self.c.fetchone()[0] or 0.0

        # Nihai dönüş değerleri:
        # `toplam_alacak` = Müşterinin bize olan NET borcu (bizim genel alacağımız)
        # `toplam_borc` = Bizim tedarikçiye olan NET borcumuz (bizim genel borcumuz)
        # BU HESAPLAMA DOĞRU, MUSTERI VE TEDARIKCI İÇİN AYRI HESAPLANIYOR
        # RETURN DEĞERLERİNDE: musteri_borcu_bize - musteri_tahsilati KULLANILMIŞ, bu zaten NET alacak.
        # tedarikci_borcu_bize - tedarikci_odemesi KULLANILMIŞ, bu zaten NET borç.
        return musteri_borcu_bize, tedarikci_borcu_bize, musteri_tahsilati, tedarikci_odemesi # musterinin_borcu_bize yerine toplam_alacak kullanıldı.

    def load_config(self):
        config_path = self._get_config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                print(f"Hata: Config dosyası bozuk veya boş. Yeni dosya oluşturulacak. Detay: {e}")
                return {}
            except Exception as e:
                print(f"Hata: Config dosyası okunurken beklenmeyen bir hata oluştu: {e}")
                return {}
        return {}

    def save_config(self, config_data):
        config_path = self._get_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            print(f"Hata: Config dosyası yazılırken hata oluştu: {e}")


    def get_critical_stock_items(self):
        """
        Minimum stok seviyesinin altında olan ürünleri döndürür.
        (id, urun_kodu, urun_adi, stok_miktari, alis_fiyati, satis_fiyati, kdv_orani, min_stok_seviyesi, alis_fiyati_kdv_dahil)
        """
        # alis_fiyati_kdv_dahil sütununu da sorguya ekleyin (9. eleman, indeks 8 olacaktır)
        self.c.execute("SELECT id, urun_kodu, urun_adi, stok_miktari, alis_fiyati_kdv_haric, satis_fiyati_kdv_haric, kdv_orani, min_stok_seviyesi, alis_fiyati_kdv_dahil FROM tbl_stoklar WHERE stok_miktari < min_stok_seviyesi ORDER BY urun_adi ASC")
        return self.c.fetchall()
    
    def kullanici_adi_guncelle(self, user_id, yeni_kullanici_adi):
        try:
            self.conn.execute("BEGIN TRANSACTION")
            # Güncellenecek kullanıcının mevcut bilgilerini al
            self.c.execute("SELECT kullanici_adi FROM kullanicilar WHERE id=?", (user_id,))
            mevcut_kullanici_adi_tuple = self.c.fetchone()
            if not mevcut_kullanici_adi_tuple:
                self.conn.rollback()
                return False, "Güncellenecek kullanıcı bulunamadı."

            mevcut_kullanici_adi = mevcut_kullanici_adi_tuple[0]

            # Başka bir kullanıcının aynı adı almasını engelle
            self.c.execute("SELECT id FROM kullanicilar WHERE kullanici_adi=? AND id != ?", (yeni_kullanici_adi, user_id))
            if self.c.fetchone():
                self.conn.rollback()
                return False, f"'{yeni_kullanici_adi}' kullanıcı adı zaten başka bir kullanıcı tarafından kullanılıyor."

            current_time = self.get_current_datetime_str()
            guncelleyen_id = self._get_current_user_id() # Değişiklik

            self.c.execute("UPDATE kullanicilar SET kullanici_adi=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                       (yeni_kullanici_adi, current_time, guncelleyen_id, user_id))
            self.conn.commit()

            return True, "Kullanıcı adı başarıyla güncellendi."

        except Exception as e:
            self.conn.rollback()
            return False, f"Kullanıcı adı güncellenirken bir hata oluştu: {e}"
        
    def get_faturalar_by_urun_id(self, urun_id, fatura_tipi=None): 
        """
        Belirli bir ürün ID'sinin yer aldığı faturaları (hem alış hem satış) döndürür.
        İsteğe bağlı olarak fatura tipine göre (ALIŞ/SATIŞ) filtreler.
        Dönüş formatı: (fatura_id, fatura_no, tarih, tip, cari_adi, toplam_kdv_haric, toplam_kdv_dahil)
        """
        query = """
            SELECT
                f.id,
                f.fatura_no,
                f.tarih,
                f.tip,
                CASE
                    WHEN f.cari_id = ? AND f.tip = 'SATIŞ' THEN IFNULL(f.misafir_adi, 'Perakende Satış')
                    WHEN f.tip = 'ALIŞ' THEN ted.ad
                    WHEN f.tip = 'SATIŞ' THEN mus.ad
                    ELSE 'Bilinmeyen Cari'
                END AS cari_adi,
                f.toplam_kdv_haric,
                f.toplam_kdv_dahil
            FROM faturalar f
            JOIN fatura_kalemleri fk ON f.id = fk.fatura_id
            LEFT JOIN musteriler mus ON f.cari_id = mus.id AND f.tip = 'SATIŞ'
            LEFT JOIN tedarikciler ted ON f.cari_id = ted.id AND f.tip = 'ALIŞ'
            WHERE fk.urun_id = ?
        """
        # Perakende müşteri ID'si her zaman sorgudaki ilk parametre olacak
        perakende_id_param = self.perakende_musteri_id if self.perakende_musteri_id is not None else -999
        
        params = [perakende_id_param, urun_id] # Parametre listesi

        if fatura_tipi and fatura_tipi != "TÜMÜ":
            query += " AND f.tip = ?"
            params.append(fatura_tipi)

        query += " ORDER BY f.tarih DESC, f.fatura_no DESC"
        
        self.c.execute(query, params)
        return self.c.fetchall()


    def get_kasa_banka_by_odeme_turu(self, odeme_turu):
        """
        Belirtilen ödeme türüne varsayılan olarak atanmış kasa/banka hesabını döndürür.
        Dönüş: (id, hesap_adi, hesap_no, bakiye, para_birimi, tip, acilis_tarihi, banka_adi, sube_adi, varsayilan_odeme_turu)
        Veya bulunamazsa None.
        """
        self.c.execute("SELECT id, hesap_adi, hesap_no, bakiye, para_birimi, tip, acilis_tarihi, banka_adi, sube_adi, varsayilan_odeme_turu FROM kasalar_bankalar WHERE varsayilan_odeme_turu = ?", (odeme_turu,))
        return self.c.fetchone()


    def get_next_tedarikci_kodu(self, length=6):
        """
        Mevcut tedarikçi kodları arasında en yüksek sayısal değeri bulur ve bir sonraki kodu döndürür.
        Belirtilen uzunluğa kadar baştan sıfırlarla doldurur.
        """
        self.c.execute("SELECT tedarikci_kodu FROM tedarikciler")
        existing_codes = self.c.fetchall()
        
        max_numeric_code = 0
        for code_tuple in existing_codes:
            code = code_tuple[0]
            # Sadece sayısal kodları dikkate al
            if code.isdigit():
                try:
                    numeric_code = int(code)
                    if numeric_code > max_numeric_code:
                        max_numeric_code = numeric_code
                except ValueError:
                    pass
        
        next_code = max_numeric_code + 1
        # Belirtilen uzunluğa kadar baştan sıfırlarla doldur
        return str(next_code).zfill(length)
    
    def get_total_sales(self, baslangic_tarih, bitis_tarih):
        """Belirtilen tarih aralığındaki toplam satış tutarını (KDV Dahil) döndürür."""
        query = "SELECT SUM(toplam_kdv_dahil) FROM faturalar WHERE tip = 'SATIŞ' AND tarih BETWEEN ? AND ?"
        self.c.execute(query, (baslangic_tarih, bitis_tarih))
        result = self.c.fetchone()[0]
        return result if result is not None else 0.0

    def get_sales_by_payment_type(self, baslangic_tarih, bitis_tarih):
        """Belirtilen tarih aralığındaki satışları ödeme türüne göre gruplayarak toplam tutarları döndürür."""
        query = """
            SELECT odeme_turu, SUM(toplam_kdv_dahil)
            FROM faturalar
            WHERE tip = 'SATIŞ' AND tarih BETWEEN ? AND ?
            GROUP BY odeme_turu
            ORDER BY odeme_turu
        """
        self.c.execute(query, (baslangic_tarih, bitis_tarih))
        return self.c.fetchall()

    def get_cari_yaslandirma_verileri(self, rapor_tarihi_str=None):
        """
        Belirtilen rapor tarihine göre müşteri alacaklarını ve tedarikçi borçlarını yaşlandırma yapar.
        Dönüş: {
            'musteri_alacaklari': {
                '0-30': [], '31-60': [], '61-90': [], '90+': []
            },
            'tedarikci_borclari': {
                '0-30': [], '31-60': [], '61-90': [], '90+': []
            }
        }
        Her bir liste: (cari_id, cari_adi, tutar, vadesi_gecen_gun_sayisi)
        """
        if rapor_tarihi_str:
            rapor_tarihi = datetime.strptime(rapor_tarihi_str, '%Y-%m-%d')
        else:
            rapor_tarihi = datetime.now()
    
        yaslandirma_sonuclari = {
            'musteri_alacaklari': {'0-30': [], '31-60': [], '61-90': [], '90+': []},
            'tedarikci_borclari': {'0-30': [], '31-60': [], '61-90': [], '90+': []}
        }
    
        # SQL sorgusu güncellendi: islem_tipi = 'ALACAK' ve 'TAHSILAT' olarak netleştirildi.
        # Ayrıca FATURA referans tipleri de dahil edildi.
        self.c.execute("""
            SELECT
                c.cari_id,
                CASE
                    WHEN c.cari_tip = 'MUSTERI' THEN m.ad
                    WHEN c.cari_tip = 'TEDARIKCI' THEN t.ad
                END AS cari_adi,
                -- Müşteri Alacakları (Bize olan borçları: Fatura, Manuel Alacak, Manuel Veresiye Borç)
                SUM(CASE WHEN c.cari_tip = 'MUSTERI' AND (c.islem_tipi = 'ALACAK' OR c.referans_tip = 'FATURA' OR c.referans_tip = 'VERESIYE_BORC_MANUEL') THEN c.tutar ELSE 0 END) AS musteri_toplam_alacak,
                -- Müşteri Tahsilatları (Müşteriden aldıklarımız: Tahsilat, Peşin Satış Faturası)
                SUM(CASE WHEN c.cari_tip = 'MUSTERI' AND (c.islem_tipi = 'TAHSILAT' OR c.referans_tip = 'FATURA_SATIS_PESIN') THEN c.tutar ELSE 0 END) AS musteri_toplam_tahsilat,
                -- Tedarikçi Borçları (Bizim onlara olan borcumuz: Fatura, Manuel Borç, Manuel Veresiye Borç)
                SUM(CASE WHEN c.cari_tip = 'TEDARIKCI' AND (c.islem_tipi = 'BORC' OR c.referans_tip = 'FATURA' OR c.referans_tip = 'VERESIYE_BORC_MANUEL') THEN c.tutar ELSE 0 END) AS tedarikci_toplam_borc,
                -- Tedarikçi Ödemeleri (Tedarikçiye ödediklerimiz: Ödeme, Peşin Alış Faturası)
                SUM(CASE WHEN c.cari_tip = 'TEDARIKCI' AND (c.islem_tipi = 'ODEME' OR c.referans_tip = 'FATURA_ALIS_PESIN') THEN c.tutar ELSE 0 END) AS tedarikci_toplam_odeme,
                c.cari_tip,
                MAX(c.tarih) AS son_islem_tarihi
            FROM cari_hareketler c
            LEFT JOIN musteriler m ON c.cari_id = m.id AND c.cari_tip = 'MUSTERI'
            LEFT JOIN tedarikciler t ON c.cari_id = t.id AND c.cari_tip = 'TEDARIKCI'
            WHERE c.tarih <= ?
            GROUP BY c.cari_id, c.cari_tip
            HAVING (musteri_toplam_alacak - musteri_toplam_tahsilat) != 0 OR (tedarikci_toplam_borc - tedarikci_toplam_odeme) != 0
        """, (rapor_tarihi_str,))
    
        raw_results = self.c.fetchall()
    
        # DÜZELTME: Artık satırlara indeks ile değil, sütun adlarıyla erişiyoruz.
        for row in raw_results:
            cari_id = row['cari_id']
            cari_adi = row['cari_adi']
            musteri_toplam_alacak = row['musteri_toplam_alacak'] or 0.0
            musteri_toplam_tahsilat = row['musteri_toplam_tahsilat'] or 0.0
            tedarikci_toplam_borc = row['tedarikci_toplam_borc'] or 0.0
            tedarikci_toplam_odeme = row['tedarikci_toplam_odeme'] or 0.0
            cari_tip_from_db = row['cari_tip']
            son_islem_tarihi_str = row['son_islem_tarihi']

            if not cari_adi: continue
    
            net_bakiye_musteri = musteri_toplam_alacak - musteri_toplam_tahsilat
            net_bakiye_tedarikci = tedarikci_toplam_borc - tedarikci_toplam_odeme
    
            if net_bakiye_musteri == 0 and net_bakiye_tedarikci == 0: continue
    
            try:
                son_islem_tarihi = datetime.strptime(son_islem_tarihi_str, '%Y-%m-%d')
            except (ValueError, TypeError):
                son_islem_tarihi = rapor_tarihi
    
            vadesi_gecen_gun_sayisi = (rapor_tarihi - son_islem_tarihi).days
    
            if cari_tip_from_db == 'MUSTERI' and net_bakiye_musteri > 0: # Müşteri bize borçlu
                if vadesi_gecen_gun_sayisi <= 30:
                    yaslandirma_sonuclari['musteri_alacaklari']['0-30'].append((cari_id, cari_adi, net_bakiye_musteri, vadesi_gecen_gun_sayisi))
                elif vadesi_gecen_gun_sayisi <= 60:
                    yaslandirma_sonuclari['musteri_alacaklari']['31-60'].append((cari_id, cari_adi, net_bakiye_musteri, vadesi_gecen_gun_sayisi))
                elif vadesi_gecen_gun_sayisi <= 90:
                    yaslandirma_sonuclari['musteri_alacaklari']['61-90'].append((cari_id, cari_adi, net_bakiye_musteri, vadesi_gecen_gun_sayisi))
                else:
                    yaslandirma_sonuclari['musteri_alacaklari']['90+'].append((cari_id, cari_adi, net_bakiye_musteri, vadesi_gecen_gun_sayisi))
    
            elif cari_tip_from_db == 'TEDARIKCI' and net_bakiye_tedarikci > 0: # Biz tedarikçiye borçluyuz
                if vadesi_gecen_gun_sayisi <= 30:
                    yaslandirma_sonuclari['tedarikci_borclari']['0-30'].append((cari_id, cari_adi, net_bakiye_tedarikci, vadesi_gecen_gun_sayisi))
                elif vadesi_gecen_gun_sayisi <= 60:
                    yaslandirma_sonuclari['tedarikci_borclari']['31-60'].append((cari_id, cari_adi, net_bakiye_tedarikci, vadesi_gecen_gun_sayisi))
                elif vadesi_gecen_gun_sayisi <= 90:
                    yaslandirma_sonuclari['tedarikci_borclari']['61-90'].append((cari_id, cari_adi, net_bakiye_tedarikci, vadesi_gecen_gun_sayisi))
                else:
                    yaslandirma_sonuclari['tedarikci_borclari']['90+'].append((cari_id, cari_adi, net_bakiye_tedarikci, vadesi_gecen_gun_sayisi))
    
        return yaslandirma_sonuclari

    def get_total_collections(self, baslangic_tarih, bitis_tarih):
        """Belirtilen tarih aralığındaki toplam tahsilat tutarını döndürür."""
        # Tahsilatlar hem manuel tahsilatlardan hem de peşin satış faturalarından gelir.
        query = """
            SELECT SUM(tutar) FROM gelir_gider
            WHERE tip = 'GELİR' AND (kaynak = 'TAHSILAT' OR kaynak = 'FATURA') AND tarih BETWEEN ? AND ?
        """
        self.c.execute(query, (baslangic_tarih, bitis_tarih))
        result = self.c.fetchone()[0]
        return result if result is not None else 0.0

    def get_total_payments(self, baslangic_tarih, bitis_tarih):
        """Belirtilen tarih aralığındaki toplam ödeme tutarını döndürür."""
        # Ödemeler hem manuel ödemelerden hem de peşin alış faturalarından gelir.
        query = """
            SELECT SUM(tutar) FROM gelir_gider
            WHERE tip = 'GİDER' AND (kaynak = 'ODEME' OR kaynak = 'FATURA') AND tarih BETWEEN ? AND ?
        """
        self.c.execute(query, (baslangic_tarih, bitis_tarih))
        result = self.c.fetchone()[0]
        return result if result is not None else 0.0

    def get_manual_income_expenses(self, baslangic_tarih, bitis_tarih):
        """Belirtilen tarih aralığındaki manuel gelir ve gider toplamlarını döndürür."""
        query_gelir = "SELECT SUM(tutar) FROM gelir_gider WHERE tip = 'GELİR' AND kaynak = 'MANUEL' AND tarih BETWEEN ? AND ?"
        self.c.execute(query_gelir, (baslangic_tarih, bitis_tarih))
        total_manual_income = self.c.fetchone()[0]
        total_manual_income = total_manual_income if total_manual_income is not None else 0.0

        query_gider = "SELECT SUM(tutar) FROM gelir_gider WHERE tip = 'GİDER' AND kaynak = 'MANUEL' AND tarih BETWEEN ? AND ?"
        self.c.execute(query_gider, (baslangic_tarih, bitis_tarih))
        total_manual_expense = self.c.fetchone()[0]
        total_manual_expense = total_manual_expense if total_manual_expense is not None else 0.0

        return total_manual_income, total_manual_expense
    
    def get_gross_profit_and_cost(self, baslangic_tarih, bitis_tarih):
        """
        Belirtilen tarih aralığındaki satışlardan elde edilen brüt kârı (KDV Dahil Fiyatlar Üzerinden),
        satılan malın maliyetini (KDV Dahil Alış Fiyatları Üzerinden) ve brüt kâr oranını hesaplar.
        """
        # Toplam Satış Geliri (KDV Dahil)
        query_sales_revenue = """
            SELECT SUM(toplam_kdv_dahil) FROM faturalar
            WHERE tip = 'SATIŞ' AND tarih BETWEEN ? AND ?
        """
        self.c.execute(query_sales_revenue, (baslangic_tarih, bitis_tarih))
        total_sales_revenue = self.c.fetchone()[0]
        total_sales_revenue = total_sales_revenue if total_sales_revenue is not None else 0.0

        # Satılan Malın Maliyeti (COGS - Cost of Goods Sold)
        # Her satış kalemindeki ürünün ALIŞ FİYATI (KDV DAHİL) üzerinden hesaplanır.
        # Stok tablosundaki alis_fiyati KDV hariçtir, bu yüzden KDV oranını kullanarak KDV dahil alış fiyatını hesaplamalıyız.
        query_cogs = """
            SELECT SUM(fk.miktar * fk.alis_fiyati_fatura_aninda)
            FROM fatura_kalemleri fk
            JOIN faturalar f ON fk.fatura_id = f.id
            WHERE f.tip = 'SATIŞ' AND f.tarih BETWEEN ? AND ?
        """
        self.c.execute(query_cogs, (baslangic_tarih, bitis_tarih))
        total_cogs = self.c.fetchone()[0]
        total_cogs = total_cogs if total_cogs is not None else 0.0

        gross_profit = total_sales_revenue - total_cogs
        gross_profit_rate = (gross_profit / total_sales_revenue * 100) if total_sales_revenue > 0 else 0.0

        return gross_profit, total_cogs, gross_profit_rate    
        
    def get_next_musteri_kodu(self, length=6):
        """
        Mevcut müşteri kodları arasında en yüksek sayısal değeri bulur ve bir sonraki kodu döndürür.
        Belirtilen uzunluğa kadar baştan sıfırlarla doldurur.
        """
        self.c.execute("SELECT musteri_kodu FROM musteriler")
        existing_codes = self.c.fetchall()
        
        max_numeric_code = 0
        for code_tuple in existing_codes:
            code = code_tuple[0]
            # Sadece sayısal kodları dikkate al (örn: 'PER000' gibi özel kodları atla)
            if code.isdigit():
                try:
                    numeric_code = int(code)
                    if numeric_code > max_numeric_code:
                        max_numeric_code = numeric_code
                except ValueError:
                    pass
        
        next_code = max_numeric_code + 1
        # Belirtilen uzunluğa kadar baştan sıfırlarla doldur
        return str(next_code).zfill(length)
    
    def _ensure_perakende_musteri(self):
        # Perakende müşteri ID'sinin zaten ayarlanıp ayarlanmadığını kontrol et
        if self.perakende_musteri_id is not None:
            # Eğer zaten ayarlıysa, tekrar işlem yapmaya gerek yok.
            # Bu, App.__init__ içinde birden fazla çağrıyı optimize eder.
            # Eğer DB bağlantısı kesilip tekrar kurulursa, bu kontrol hala faydalıdır.
            self.c.execute("SELECT id FROM musteriler WHERE kod = ?", (self.PERAKENDE_MUSTERI_KODU,))
            musteri = self.c.fetchone()
            if musteri:
                # ID'yi güncelle (eğer None ise) ve başarılı say
                self.perakende_musteri_id = musteri['id']
                return True, "Perakende müşteri bulundu ve ID güncellendi."
            # Eğer ID ayarlıydı ama DB'de yoksa, aşağıdaki oluşturma akışına devam et.

        try:
            self.c.execute("SELECT id FROM musteriler WHERE kod = ?", (self.PERAKENDE_MUSTERI_KODU,))
            musteri = self.c.fetchone()
            if musteri:
                self.perakende_musteri_id = musteri['id']
                return True, "Perakende müşteri bulundu."
            else:
                default_user_id = 1 
                # self.app ve self.app.current_user kontrolü sadece eğer app referansı başlatma sırasında ayarlandıysa geçerlidir.
                # Genellikle bu `_ensure_` metodları App sınıfı oluşmadan önce çağrılabilir.
                # Bu yüzden güvenli bir varsayılan kullanıcı ID'si kullanmak daha iyidir.
                # Eğer App sınıfının init'i içinde çağrılıyorsa, self.app.current_user kontrolü uygun olabilir.
                if self.app and self.app.current_user:
                    default_user_id = self.app.current_user[0] 

                current_time = self.get_current_datetime_str()

                self.c.execute("""
                    INSERT INTO musteriler (ad, soyad, kod, vergi_dairesi, vergi_no, adres, telefon, email, notlar,
                                            olusturma_tarihi_saat, olusturan_kullanici_id,
                                            son_guncelleme_tarihi_saat, son_guncelleyen_kullanici_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, ('Perakende Satış Müşterisi', '', self.PERAKENDE_MUSTERI_KODU, '', '', '', '', '', 'Sistem tarafından otomatik oluşturulan perakende satış müşterisi.',
                      current_time, default_user_id, 
                      current_time, default_user_id))
                self.conn.commit()
                self.perakende_musteri_id = self.c.lastrowid
                return True, "Perakende müşteri başarıyla oluşturuldu."
        except sqlite3.IntegrityError as e:
            # Bu genellikle UNIQUE constraint hatasıdır, yani müşteri zaten vardır.
            self.conn.rollback() # Hata durumunda rollback
            self.c.execute("SELECT id FROM musteriler WHERE kod = ?", (self.PERAKENDE_MUSTERI_KODU,))
            musteri = self.c.fetchone()
            if musteri:
                self.perakende_musteri_id = musteri['id']
                return True, f"Perakende müşteri zaten mevcut (IntegrityError: {e})."
            else:
                return False, f"Perakende müşteri kontrol edilirken bütünlük hatası oluştu: {e}"
        except Exception as e:
            self.conn.rollback()
            return False, f"Perakende müşteri oluşturulurken/kontrol edilirken kritik hata: {e}"

    def _add_column_if_not_exists(self, table_name, column_name, column_type, is_unique=False):
        try:
            self.c.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in self.c.fetchall()]
            if column_name not in columns:
                self.c.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                self.conn.commit()
                # print(f"DEBUG: Sütun eklendi: Tablo={table_name}, Sütun={column_name}") # Bu satır kaldırıldı
                
            if is_unique:
                try:
                    index_name = f"idx_{table_name}_{column_name}_unique"
                    self.c.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})")
                    self.conn.commit()
                except sqlite3.OperationalError as e:
                    logging.warning(f"UYARI: UNIQUE INDEX oluşturulurken hata oluştu: {e}. Bu genellikle '{table_name}.{column_name}' sütununda zaten yinelenen veri olduğu anlamına gelir.") # print yerine logging.warning
                except Exception as e:
                    logging.error(f"UYARI: UNIQUE INDEX oluşturulurken beklenmeyen bir hata oluştu: {e}", exc_info=True) # print yerine logging.error
        except sqlite3.OperationalError as e:
            logging.error(f"HATA: Sütun eklenirken veritabanı hatası: {e}", exc_info=True) # print yerine logging.error
        except Exception as e:
            logging.error(f"HATA: Sütun ekleme kontrolü sırasında beklenmeyen hata: {e}", exc_info=True) # print yerine logging.error

    def create_tables(self):
        self.c.execute('''CREATE TABLE IF NOT EXISTS sirket_ayarlari
                            (anahtar TEXT PRIMARY KEY,
                            deger TEXT)''')

        # Kullanıcılar Tablosu
        self.c.execute('''CREATE TABLE IF NOT EXISTS kullanicilar
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            kullanici_adi TEXT UNIQUE NOT NULL, 
                            sifre TEXT NOT NULL, 
                            yetki TEXT CHECK(yetki IN ('admin', 'kullanici')) NOT NULL)''')
        self._add_column_if_not_exists('kullanicilar', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('kullanicilar', 'olusturan_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('kullanicilar', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('kullanicilar', 'son_guncelleyen_kullanici_id', 'INTEGER')

        # Müşteriler Tablosu
        self.c.execute(
            """CREATE TABLE IF NOT EXISTS musteriler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ad TEXT NOT NULL,
                    soyad TEXT,
                    kod TEXT UNIQUE,
                    vergi_dairesi TEXT,
                    vergi_no TEXT,
                    adres TEXT,
                    telefon TEXT,
                    email TEXT,
                    notlar TEXT,
                    olusturma_tarihi_saat TEXT,
                    olusturan_kullanici_id INTEGER,
                    son_guncelleme_tarihi_saat TEXT,
                    son_guncelleyen_kullanici_id INTEGER
                )"""
        )
        self._add_column_if_not_exists('musteriler', 'soyad', 'TEXT')
        self._add_column_if_not_exists('musteriler', 'kod', 'TEXT', is_unique=True)
        self._add_column_if_not_exists('musteriler', 'email', 'TEXT')
        self._add_column_if_not_exists('musteriler', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('musteriler', 'olusturan_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('musteriler', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('musteriler', 'son_guncelleyen_kullanici_id', 'INTEGER')
        
        # Tedarikçiler Tablosu
        self.c.execute('''CREATE TABLE IF NOT EXISTS tedarikciler
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            tedarikci_kodu TEXT UNIQUE,
                            ad TEXT NOT NULL, 
                            telefon TEXT, 
                            adres TEXT, 
                            vergi_dairesi TEXT, 
                            vergi_no TEXT
                            )'''
        )
        self._add_column_if_not_exists('tedarikciler', 'tedarikci_kodu', 'TEXT', is_unique=True)
        self._add_column_if_not_exists('tedarikciler', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('tedarikciler', 'olusturan_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('tedarikciler', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('tedarikciler', 'son_guncelleyen_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('musteriler', 'bakiye', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('tedarikciler', 'bakiye', 'REAL DEFAULT 0.0')

        # <<< DÜZELTİLMİŞ STOK TABLOSU OLUŞTURMA SIRASI >>>

        # 1. Adım: Temel Stok Tablosunu Oluştur
        self.c.execute('''CREATE TABLE IF NOT EXISTS tbl_stoklar
                                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                urun_kodu TEXT UNIQUE NOT NULL,
                                urun_adi TEXT NOT NULL,
                                stok_miktari REAL DEFAULT 0.0,
                                alis_fiyati_kdv_haric REAL DEFAULT 0.0,
                                satis_fiyati_kdv_haric REAL DEFAULT 0.0,
                                kdv_orani REAL DEFAULT 20.0,
                                min_stok_seviyesi REAL DEFAULT 0.0)''')

        # 2. Adım: Önce TÜM SÜTUNLARI Ekle (UNIQUE olmayanlar dahil)
        self._add_column_if_not_exists('tbl_stoklar', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('tbl_stoklar', 'olusturan_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('tbl_stoklar', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('tbl_stoklar', 'son_guncelleyen_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('tbl_stoklar', 'min_stok_seviyesi', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('tbl_stoklar', 'alis_fiyati_kdv_dahil', 'REAL DEFAULT 0.0') 
        self._add_column_if_not_exists('tbl_stoklar', 'satis_fiyati_kdv_dahil', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('tbl_stoklar', 'kategori_id', 'INTEGER')
        self._add_column_if_not_exists('tbl_stoklar', 'marka_id', 'INTEGER')
        self._add_column_if_not_exists('tbl_stoklar', 'urun_detayi', 'TEXT')
        self._add_column_if_not_exists('tbl_stoklar', 'urun_resmi_yolu', 'TEXT')
        self._add_column_if_not_exists('tbl_stoklar', 'fiyat_degisiklik_tarihi', 'DATE')
        self._add_column_if_not_exists('tbl_stoklar', 'urun_grubu_id', 'INTEGER')
        self._add_column_if_not_exists('tbl_stoklar', 'urun_birimi_id', 'INTEGER')
        self._add_column_if_not_exists('tbl_stoklar', 'ulke_id', 'INTEGER')

        # 3. Adım: Sütunlar eklendikten sonra INDEX'leri oluştur
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_tbl_stoklar_urun_adi ON tbl_stoklar (urun_adi);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_tbl_stoklar_kategori_id ON tbl_stoklar (kategori_id);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_tbl_stoklar_marka_id ON tbl_stoklar (marka_id);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_tbl_stoklar_urun_grubu_id ON tbl_stoklar (urun_grubu_id);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_tbl_stoklar_urun_birimi_id ON tbl_stoklar (urun_birimi_id);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_tbl_stoklar_ulke_id ON tbl_stoklar (ulke_id);")
        
        # Diğer tablolar...
        self.c.execute('''CREATE TABLE IF NOT EXISTS stok_hareketleri
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            urun_id INTEGER NOT NULL, 
                            tarih DATE NOT NULL, 
                            islem_tipi TEXT NOT NULL, 
                            miktar REAL NOT NULL, 
                            onceki_stok REAL NOT NULL,
                            sonraki_stok REAL NOT NULL,
                            aciklama TEXT,
                            kaynak TEXT, 
                            kaynak_id INTEGER, 
                            olusturma_tarihi_saat TEXT,
                            olusturan_kullanici_id INTEGER,
                            FOREIGN KEY(urun_id) REFERENCES tbl_stoklar(id) ON DELETE CASCADE)''') 
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_stok_hareketleri_urun_tarih_tip ON stok_hareketleri (urun_id, tarih, islem_tipi);")

        self.c.execute('''CREATE TABLE IF NOT EXISTS urun_gruplari
                                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                grup_adi TEXT UNIQUE NOT NULL)''')
        self._add_column_if_not_exists('urun_gruplari', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('urun_gruplari', 'olusturan_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('urun_gruplari', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('urun_gruplari', 'son_guncelleyen_kullanici_id', 'INTEGER')
        
        self.c.execute('''CREATE TABLE IF NOT EXISTS urun_birimleri
                                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                birim_adi TEXT UNIQUE NOT NULL)''')
        self._add_column_if_not_exists('urun_birimleri', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('urun_birimleri', 'olusturan_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('urun_birimleri', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('urun_birimleri', 'son_guncelleyen_kullanici_id', 'INTEGER')
        
        self.c.execute('''CREATE TABLE IF NOT EXISTS urun_ulkeleri
                                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                ulke_adi TEXT UNIQUE NOT NULL)''')
        self._add_column_if_not_exists('urun_ulkeleri', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('urun_ulkeleri', 'olusturan_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('urun_ulkeleri', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('urun_ulkeleri', 'son_guncelleyen_kullanici_id', 'INTEGER')
        
        self.c.execute('''CREATE TABLE IF NOT EXISTS kasalar_bankalar
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            hesap_adi TEXT NOT NULL UNIQUE,
                            hesap_no TEXT, 
                            bakiye REAL DEFAULT 0.0,
                            para_birimi TEXT DEFAULT 'TL',
                            tip TEXT CHECK(tip IN ('KASA', 'BANKA')) NOT NULL,
                            acilis_tarihi DATE, 
                            banka_adi TEXT, 
                            sube_adi TEXT
                            )''')
        self._add_column_if_not_exists('kasalar_bankalar', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('kasalar_bankalar', 'olusturan_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('kasalar_bankalar', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('kasalar_bankalar', 'son_guncelleyen_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('kasalar_bankalar', 'varsayilan_odeme_turu', 'TEXT') 
        
        self.c.execute('''CREATE TABLE IF NOT EXISTS faturalar
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            fatura_no TEXT UNIQUE NOT NULL, 
                            tarih DATE NOT NULL, 
                            tip TEXT CHECK(tip IN ('ALIŞ', 'SATIŞ', 'DEVİR_GİRİŞ', 'SATIŞ İADE', 'ALIŞ İADE')) NOT NULL,
                            cari_id INTEGER NOT NULL,
                            toplam_kdv_haric REAL NOT NULL, 
                            toplam_kdv_dahil REAL NOT NULL, 
                            odeme_turu TEXT,
                            misafir_adi TEXT,
                            kasa_banka_id INTEGER REFERENCES kasalar_bankalar(id)
                            )''') 
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_faturalar_tarih_tip_cari ON faturalar (tarih, tip, cari_id);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_faturalar_odeme_turu ON faturalar (odeme_turu);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_faturalar_kasa_banka_id ON faturalar (kasa_banka_id);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_faturalar_fatura_no ON faturalar (fatura_no);")
        self._add_column_if_not_exists('faturalar', 'fatura_notlari', 'TEXT')
        self._add_column_if_not_exists('faturalar', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('faturalar', 'olusturan_kullanici_id', 'INTEGER') # Buradaki "o" harfi düzeltildi
        self._add_column_if_not_exists('faturalar', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('faturalar', 'son_guncelleyen_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('faturalar', 'odeme_turu', 'TEXT')
        self._add_column_if_not_exists('faturalar', 'misafir_adi', 'TEXT')
        self._add_column_if_not_exists('faturalar', 'kasa_banka_id', 'INTEGER')
        self._add_column_if_not_exists('faturalar', 'vade_tarihi', 'DATE')
        self._add_column_if_not_exists('faturalar', 'genel_iskonto_tipi', 'TEXT DEFAULT \'YOK\'')
        self._add_column_if_not_exists('faturalar', 'genel_iskonto_degeri', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('faturalar', 'original_fatura_id', 'INTEGER') # <<< Bu satırın var olduğundan emin olun

        self.c.execute('''CREATE TABLE IF NOT EXISTS fatura_kalemleri
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            fatura_id INTEGER NOT NULL, 
                            urun_id INTEGER NOT NULL, 
                            miktar REAL NOT NULL,
                            birim_fiyat REAL NOT NULL, 
                            kdv_orani REAL NOT NULL, 
                            kdv_tutari REAL NOT NULL, 
                            kalem_toplam_kdv_haric REAL NOT NULL, 
                            kalem_toplam_kdv_dahil REAL NOT NULL, 
                            FOREIGN KEY(fatura_id) REFERENCES faturalar(id) ON DELETE CASCADE, 
                            FOREIGN KEY(urun_id) REFERENCES tbl_stoklar(id))''')
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_faturakalemleri_fatura_urun ON fatura_kalemleri (fatura_id, urun_id);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_faturakalemleri_urun_id ON fatura_kalemleri (urun_id);")
        self._add_column_if_not_exists('fatura_kalemleri', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('fatura_kalemleri', 'olusturan_kullanici_id', 'INTEGER') # Buradaki "o" harfi düzeltildi
        self._add_column_if_not_exists('fatura_kalemleri', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('fatura_kalemleri', 'son_guncelleyen_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('fatura_kalemleri', 'alis_fiyati_fatura_aninda', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('fatura_kalemleri', 'kdv_orani_fatura_aninda', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('fatura_kalemleri', 'iskonto_yuzde_1', 'REAL DEFAULT 0.0') 
        self._add_column_if_not_exists('fatura_kalemleri', 'iskonto_yuzde_2', 'REAL DEFAULT 0.0') 
        self._add_column_if_not_exists('fatura_kalemleri', 'iskonto_tipi', 'TEXT DEFAULT \'YOK\'') 
        self._add_column_if_not_exists('fatura_kalemleri', 'iskonto_degeri', 'REAL DEFAULT 0.0') 
        
        self.c.execute('''CREATE TABLE IF NOT EXISTS gelir_gider
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            tarih DATE NOT NULL, 
                            tip TEXT CHECK(tip IN ('GELİR', 'GİDER')) NOT NULL, 
                            tutar REAL NOT NULL, 
                            aciklama TEXT,
                            kaynak TEXT DEFAULT 'MANUEL',
                            kaynak_id INTEGER,
                            kasa_banka_id INTEGER REFERENCES kasalar_bankalar(id)
                            )''') 
        self._add_column_if_not_exists('gelir_gider', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('gelir_gider', 'olusturan_kullanici_id', 'INTEGER') # Buradaki "o" harfi düzeltildi
        self._add_column_if_not_exists('gelir_gider', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('gelir_gider', 'son_guncelleyen_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('gelir_gider', 'kaynak', 'TEXT DEFAULT \'MANUEL\'')
        self._add_column_if_not_exists('gelir_gider', 'kaynak_id', 'INTEGER')
        self._add_column_if_not_exists('gelir_gider', 'kasa_banka_id', 'INTEGER')
        self._add_column_if_not_exists('gelir_gider', 'gelir_siniflandirma_id', 'INTEGER')
        self._add_column_if_not_exists('gelir_gider', 'gider_siniflandirma_id', 'INTEGER')

        self.c.execute("CREATE INDEX IF NOT EXISTS idx_gelir_gider_tarih_tip ON gelir_gider (tarih, tip);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_gelir_gider_kaynak ON gelir_gider (kaynak, kaynak_id);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_gelir_gider_kasa_banka_id ON gelir_gider (kasa_banka_id);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_gelir_gider_gelir_siniflandirma_id ON gelir_gider (gelir_siniflandirma_id);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_gelir_gider_gider_siniflandirma_id ON gelir_gider (gider_siniflandirma_id);")

        self.c.execute('''CREATE TABLE IF NOT EXISTS cari_hareketler
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            tarih DATE NOT NULL, 
                            cari_tip TEXT CHECK(cari_tip IN ('MUSTERI', 'TEDARIKCI')) NOT NULL, 
                            cari_id INTEGER NOT NULL, 
                            islem_tipi TEXT CHECK(islem_tipi IN ('ALACAK', 'BORC', 'TAHSILAT', 'ODEME')) NOT NULL, 
                            tutar REAL NOT NULL, 
                            aciklama TEXT,
                            referans_id INTEGER,
                            referans_tip TEXT,
                            kasa_banka_id INTEGER REFERENCES kasalar_bankalar(id)
                            )''') 
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_cari_hareketler_cari_tarih_tip ON cari_hareketler (cari_id, cari_tip, tarih, islem_tipi);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_cari_hareketler_referans ON cari_hareketler (referans_id, referans_tip);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_cari_hareketler_kasa_banka_id ON cari_hareketler (kasa_banka_id);")
        self._add_column_if_not_exists('cari_hareketler', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('cari_hareketler', 'olusturan_kullanici_id', 'INTEGER') # Buradaki "o" harfi düzeltildi
        self._add_column_if_not_exists('cari_hareketler', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('cari_hareketler', 'son_guncelleyen_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('cari_hareketler', 'referans_id', 'INTEGER')
        self._add_column_if_not_exists('cari_hareketler', 'referans_tip', 'TEXT')
        self._add_column_if_not_exists('cari_hareketler', 'kasa_banka_id', 'INTEGER')

        self.c.execute('''CREATE TABLE IF NOT EXISTS siparisler
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            siparis_no TEXT UNIQUE NOT NULL, 
                            tarih DATE NOT NULL, 
                            cari_tip TEXT CHECK(cari_tip IN ('MUSTERI', 'TEDARIKCI')) NOT NULL, 
                            cari_id INTEGER NOT NULL, 
                            toplam_tutar REAL NOT NULL, 
                            durum TEXT CHECK(durum IN ('BEKLEMEDE', 'TAMAMLANDI', 'İPTAL_EDİLDİ')) NOT NULL)''') # Düzeltildi
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_siparisler_tarih_tip_cari ON siparisler (tarih, cari_tip, cari_id);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_siparisler_durum ON siparisler (durum);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_siparisler_siparis_no ON siparisler (siparis_no);")
        self._add_column_if_not_exists('siparisler', 'fatura_id', 'INTEGER')
        self._add_column_if_not_exists('siparisler', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('siparisler', 'olusturan_kullanici_id', 'INTEGER') # Buradaki "o" harfi düzeltildi
        self._add_column_if_not_exists('siparisler', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('siparisler', 'son_guncelleyen_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('siparisler', 'siparis_notlari', 'TEXT')
        self._add_column_if_not_exists('siparisler', 'onay_durumu', 'TEXT DEFAULT \'ONAY_BEKLIYOR\'')
        self._add_column_if_not_exists('siparisler', 'teslimat_tarihi', 'DATE')
        self._add_column_if_not_exists('siparisler', 'genel_iskonto_tipi', 'TEXT DEFAULT \'YOK\'')
        self._add_column_if_not_exists('siparisler', 'genel_iskonto_degeri', 'REAL DEFAULT 0.0')

        self.c.execute('''CREATE TABLE IF NOT EXISTS siparis_kalemleri
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            siparis_id INTEGER NOT NULL, 
                            urun_id INTEGER NOT NULL, 
                            miktar REAL NOT NULL, 
                            birim_fiyat REAL NOT NULL, 
                            kdv_orani REAL NOT NULL, 
                            kdv_tutari REAL NOT NULL, 
                            kalem_toplam_kdv_haric REAL NOT NULL, 
                            kalem_toplam_kdv_dahil REAL NOT NULL, 
                            FOREIGN KEY (siparis_id) REFERENCES siparisler(id) ON DELETE CASCADE, 
                            FOREIGN KEY (urun_id) REFERENCES tbl_stoklar(id))''')
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_siparis_kalemleri_siparis_urun ON siparis_kalemleri (siparis_id, urun_id);")
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_siparis_kalemleri_urun_id ON siparis_kalemleri (urun_id);")
        self._add_column_if_not_exists('siparis_kalemleri', 'alis_fiyati_siparis_aninda', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('siparis_kalemleri', 'satis_fiyati_siparis_aninda', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('siparis_kalemleri', 'iskonto_yuzde_1', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('siparis_kalemleri', 'iskonto_yuzde_2', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('siparis_kalemleri', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('siparis_kalemleri', 'olusturan_kullanici_id', 'INTEGER') # Buradaki "o" harfi düzeltildi
        self._add_column_if_not_exists('siparis_kalemleri', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('siparis_kalemleri', 'son_guncelleyen_kullanici_id', 'INTEGER')

        self.c.execute('''CREATE TABLE IF NOT EXISTS teklifler
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            teklif_no TEXT UNIQUE NOT NULL, 
                            tarih DATE NOT NULL, 
                            musteri_id INTEGER NOT NULL, 
                            toplam_tutar REAL NOT NULL, 
                            durum TEXT CHECK(durum IN ('BEKLEMEDE', 'KABUL EDİLDİ', 'REDDEDİLDİ')) NOT NULL, 
                            FOREIGN KEY (musteri_id) REFERENCES musteriler(id) ON DELETE CASCADE)''')

        self._add_column_if_not_exists('teklifler', 'siparis_id', 'INTEGER')
        self._add_column_if_not_exists('teklifler', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('teklifler', 'olusturan_kullanici_id', 'INTEGER') # Buradaki "o" harfi düzeltildi
        self._add_column_if_not_exists('teklifler', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('teklifler', 'son_guncelleyen_kullanici_id', 'INTEGER')
        self._add_column_if_not_exists('teklifler', 'teklif_notlari', 'TEXT')
        self._add_column_if_not_exists('teklifler', 'genel_iskonto_tipi', 'TEXT DEFAULT \'YOK\'')
        self._add_column_if_not_exists('teklifler', 'genel_iskonto_degeri', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('teklifler', 'gecerlilik_tarihi', 'DATE')
        
        self.c.execute('''CREATE TABLE IF NOT EXISTS urun_kategorileri
                                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                kategori_adi TEXT UNIQUE NOT NULL)''')
        self._add_column_if_not_exists('urun_kategorileri', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('urun_kategorileri', 'olusturan_kullanici_id', 'INTEGER') # Buradaki "o" harfi düzeltildi
        self._add_column_if_not_exists('urun_kategorileri', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('urun_kategorileri', 'son_guncelleyen_kullanici_id', 'INTEGER')

        self.c.execute('''CREATE TABLE IF NOT EXISTS urun_markalari
                                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                marka_adi TEXT UNIQUE NOT NULL)''')
        self._add_column_if_not_exists('urun_markalari', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('urun_markalari', 'olusturan_kullanici_id', 'INTEGER') # Buradaki "o" harfi düzeltildi
        self._add_column_if_not_exists('urun_markalari', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('urun_markalari', 'son_guncelleyen_kullanici_id', 'INTEGER')

        self.c.execute('''CREATE TABLE IF NOT EXISTS teklif_kalemleri
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            teklif_id INTEGER NOT NULL, 
                            urun_id INTEGER NOT NULL, 
                            miktar REAL NOT NULL,
                            birim_fiyat REAL NOT NULL, 
                            kdv_orani REAL NOT NULL, 
                            kdv_tutari REAL NOT NULL, 
                            kalem_toplam_kdv_haric REAL NOT NULL, 
                            kalem_toplam_kdv_dahil REAL NOT NULL, 
                            FOREIGN KEY (teklif_id) REFERENCES teklifler(id) ON DELETE CASCADE, 
                            FOREIGN KEY (urun_id) REFERENCES tbl_stoklar(id))''')
        self._add_column_if_not_exists('teklif_kalemleri', 'alis_fiyati_teklif_aninda', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('teklif_kalemleri', 'satis_fiyati_teklif_aninda', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('teklif_kalemleri', 'iskonto_yuzde_1', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('teklif_kalemleri', 'iskonto_yuzde_2', 'REAL DEFAULT 0.0')
        self._add_column_if_not_exists('teklif_kalemleri', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('teklif_kalemleri', 'olusturan_kullanici_id', 'INTEGER') # Buradaki "o" harfi düzeltildi
        self._add_column_if_not_exists('teklif_kalemleri', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('teklif_kalemleri', 'son_guncelleyen_kullanici_id', 'INTEGER')
        
        self.c.execute('''CREATE TABLE IF NOT EXISTS gelir_siniflandirmalari
                                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                siniflandirma_adi TEXT UNIQUE NOT NULL)''')
        self._add_column_if_not_exists('gelir_siniflandirmalari', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('gelir_siniflandirmalari', 'olusturan_kullanici_id', 'INTEGER') # Buradaki "o" harfi düzeltildi
        self._add_column_if_not_exists('gelir_siniflandirmalari', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('gelir_siniflandirmalari', 'son_guncelleyen_kullanici_id', 'INTEGER')

        self.c.execute('''CREATE TABLE IF NOT EXISTS gider_siniflandirmalari
                                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                siniflandirma_adi TEXT UNIQUE NOT NULL)''')
        self._add_column_if_not_exists('gider_siniflandirmalari', 'olusturma_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('gider_siniflandirmalari', 'olusturan_kullanici_id', 'INTEGER') # Buradaki "o" harfi düzeltildi
        self._add_column_if_not_exists('gider_siniflandirmalari', 'son_guncelleme_tarihi_saat', 'TEXT')
        self._add_column_if_not_exists('gider_siniflandirmalari', 'son_guncelleyen_kullanici_id', 'INTEGER')

        self.conn.commit()
        
    def sirket_bilgilerini_yukle(self):
        defaults = {
            "sirket_adi": "ŞİRKET ADINIZ",
            "sirket_adresi": "Şirket Adresiniz, Şehir, Posta Kodu",
            "sirket_telefonu": "Şirket Telefon Numaranız",
            "sirket_email": "sirket@emailadresiniz.com",
            "sirket_vergi_dairesi": "Bağlı Olduğunuz Vergi Dairesi",
            "sirket_vergi_no": "Vergi Numaranız",
            "sirket_logo_yolu": "" # Logo dosya yolu
        }
        ayarlar = {}
        for anahtar, varsayilan_deger in defaults.items():
            self.c.execute("SELECT deger FROM sirket_ayarlari WHERE anahtar=?", (anahtar,))
            sonuc = self.c.fetchone()
            ayarlar[anahtar] = sonuc[0] if sonuc else varsayilan_deger
            if not sonuc: # Eğer ayar yoksa, varsayılan değerle ekle
                self.c.execute("INSERT INTO sirket_ayarlari (anahtar, deger) VALUES (?,?)", (anahtar, varsayilan_deger))
        return ayarlar

    def sirket_bilgilerini_kaydet(self, yeni_bilgiler):
        try:
            self.conn.execute("BEGIN TRANSACTION")
            for anahtar, deger in yeni_bilgiler.items():
                self.c.execute("UPDATE sirket_ayarlari SET deger=? WHERE anahtar=?", (deger, anahtar))
            self.conn.commit()
            self.sirket_bilgileri = self.sirket_bilgilerini_yukle() # Bilgileri yeniden yükle
            return True, "Şirket bilgileri başarıyla kaydedildi." # Mesaj eklendi
        except Exception as e:
            self.conn.rollback()
            return False, f"Şirket bilgileri kaydedilirken hata oluştu: {e}"

    def ensure_admin_user(self):
        try:
            self.c.execute("SELECT COUNT(*) FROM kullanicilar WHERE yetki='admin'")
            if self.c.fetchone()[0] == 0:
                # Sadece admin kullanıcısı yoksa şifreyi hash'le ve ekle
                admin_password_hashed = self._hash_sifre("admin123")
                self.c.execute("INSERT INTO kullanicilar (kullanici_adi, sifre, yetki, olusturma_tarihi_saat) VALUES (?,?,?,?)",
                               ("admin", admin_password_hashed, "admin", self.get_current_datetime_str()))
                self.conn.commit()
                return True, "Varsayılan 'admin' kullanıcısı başarıyla oluşturuldu."
            return True, "Varsayılan 'admin' kullanıcısı zaten mevcut."
        except Exception as e:
            return False, f"Admin kullanıcısı oluşturulurken/kontrol edilirken hata: {e}"
        
    def _hash_sifre(self, sifre):
        return hashlib.sha256(sifre.encode()).hexdigest()

    def kullanici_dogrula(self, kullanici_adi, sifre):
        self.c.execute("SELECT id,kullanici_adi,yetki FROM kullanicilar WHERE kullanici_adi=? AND sifre=?", 
                       (kullanici_adi, self._hash_sifre(sifre)))
        return self.c.fetchone()

    def kullanici_ekle(self, kullanici_adi, sifre, yetki):
        try:
            current_time = self.get_current_datetime_str()
            olusturan_id = self._get_current_user_id() # Değişiklik
            # Sütunlar ve değerler aynı sayıda olmalı
            self.c.execute("INSERT INTO kullanicilar (kullanici_adi,sifre,yetki,olusturma_tarihi_saat,olusturan_kullanici_id) VALUES (?,?,?,?,?)",
                       (kullanici_adi, self._hash_sifre(sifre), yetki, current_time, olusturan_id))
            self.conn.commit()
            return True, "Kullanıcı başarıyla eklendi."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu kullanıcı adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            return False, f"Kullanıcı ekleme sırasında bir hata oluştu: {e}"

    def kullanici_guncelle_sifre_yetki(self, user_id, sifre_hashed, yetki):
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            guncelleyen_id = self._get_current_user_id() # Değişiklik
            self.c.execute("UPDATE kullanicilar SET sifre=?, yetki=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                           (sifre_hashed, yetki, current_time, guncelleyen_id, user_id))
            self.conn.commit()

            return True, "Kullanıcı şifre/yetki bilgileri başarıyla güncellendi."

        except Exception as e:
            self.conn.rollback()
            return False, f"Kullanıcı şifre/yetki güncellenirken hata: {e}"

    def kullanici_listele(self):
        self.c.execute("SELECT id,kullanici_adi,yetki FROM kullanicilar")
        return self.c.fetchall()

    def kullanici_sil(self, user_id):
        try:
            self.conn.execute("BEGIN TRANSACTION")
            # Ana admin kullanıcısının silinmesini engelle
            self.c.execute("SELECT kullanici_adi,yetki FROM kullanicilar WHERE id=?",(user_id,))
            user_data = self.c.fetchone()
            if user_data and user_data['kullanici_adi']=="admin" and user_data['yetki']=="admin":
                self.conn.rollback()
                return False, "Ana 'admin' kullanıcısı silinemez."
            
            self.c.execute("DELETE FROM kullanicilar WHERE id=?",(user_id,))
            self.conn.commit()
            return self.c.rowcount > 0 # Silme başarılıysa True döner
        except Exception as e:
            self.conn.rollback()
            return False, f"Kullanıcı silme sırasında bir hata oluştu: {e}"

    def musteri_ekle(self, kod, ad, telefon, adres, vergi_dairesi, vergi_no):
        if not (kod and ad):
            return False, "Müşteri Kodu ve Adı zorunludur."
        if kod == self.PERAKENDE_MUSTERI_KODU:
            return False, f"'{self.PERAKENDE_MUSTERI_KODU}' özel bir koddur ve manuel olarak eklenemez/kullanılamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            olusturan_id = self._get_current_user_id() # Değişiklik
            self.c.execute("INSERT INTO musteriler (ad, kod, telefon, adres, vergi_dairesi, vergi_no, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?)",
                           (ad, kod, telefon, adres, vergi_dairesi, vergi_no, current_time, olusturan_id))
            self.conn.commit()
            return True, self.c.lastrowid # Başarı durumu ve ID

        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu müşteri kodu zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            return False, f"Müşteri ekleme sırasında hata: {e}"

    def get_cari_list_summary_data(self, cari_tip, arama_terimi=None, limit=None, offset=None, perakende_haric=False):
        """
        Belirtilen cari tipi için özet listeleme verilerini (fatura sayısı, açık hesap, tahsilat/ödeme, kalan borç, vadesi geçmiş, son işlem tarihi) döndürür.
        """
        data_list = []
        
        # Ana carileri filtreleyerek alalım (arama terimi ve sayfalama ile)
        if cari_tip == self.CARI_TIP_MUSTERI:
            cariler = self.musteri_listesi_al(arama_terimi=arama_terimi, perakende_haric=perakende_haric, limit=limit, offset=offset)
        elif cari_tip == self.CARI_TIP_TEDARIKCI:
            cariler = self.tedarikci_listesi_al(arama_terimi=arama_terimi, limit=limit, offset=offset)
        else:
            return []

        for cari in cariler:
            cari_id = cari['id']
            cari_adi = cari['ad']

            # Fatura Sayısı (Bu kısım doğru, tüm faturaları sayar)
            query_fatura_sayisi = "SELECT COUNT(id) FROM faturalar WHERE cari_id = ? AND (tip = ? OR tip = ?)"
            if cari_tip == self.CARI_TIP_MUSTERI:
                self.c.execute(query_fatura_sayisi, (cari_id, self.FATURA_TIP_SATIS, self.FATURA_TIP_SATIS_IADE))
            else: # TEDARIKCI
                self.c.execute(query_fatura_sayisi, (cari_id, self.FATURA_TIP_ALIS, self.FATURA_TIP_ALIS_IADE))
            fatura_sayisi = self.c.fetchone()[0] or 0

            # AÇIK HESAP FATURA TOPLAMI (TÜM ZAMANLAR) (Sadece 'AÇIK HESAP' olanları toplar)
            query_acik_hesap_toplam = """
                SELECT SUM(toplam_kdv_dahil) FROM faturalar
                WHERE cari_id = ? AND odeme_turu = ? AND (tip = ? OR tip = ?)
            """
            if cari_tip == self.CARI_TIP_MUSTERI:
                self.c.execute(query_acik_hesap_toplam, (cari_id, self.ODEME_TURU_ACIK_HESAP, self.FATURA_TIP_SATIS, self.FATURA_TIP_SATIS_IADE))
            else: # TEDARIKCI
                self.c.execute(query_acik_hesap_toplam, (cari_id, self.ODEME_TURU_ACIK_HESAP, self.FATURA_TIP_ALIS, self.FATURA_TIP_ALIS_IADE))
            acik_hesap_fatura_toplam = self.c.fetchone()[0] or 0.0

            # ÖDEME/TAHSİLAT (TÜM ZAMANLAR) ve Son Ödeme/Tahsilat Tarihi
            # SADECE MANUEL TAHSİLAT/ÖDEME VE PEŞİN FATURALARIN TAHSİLAT/ÖDEMELERİNİ DAHİL EDİYORUZ.
            # AÇIK HESAP FATURALARI BU TOPLAMA DAHİL EDİLMEYECEKTİR.
            son_odeme_tarihi = "-"
            if cari_tip == self.CARI_TIP_MUSTERI:
                query_tahsilat = """
                    SELECT SUM(ch.tutar), MAX(ch.tarih) FROM cari_hareketler ch
                    WHERE ch.cari_id = ? AND ch.cari_tip = ? AND ch.islem_tipi = ? -- SADECE TAHSILAT
                """
                self.c.execute(query_tahsilat, (cari_id, self.CARI_TIP_MUSTERI, self.ISLEM_TIP_TAHSILAT))
                
                tahsilat_sonuc = self.c.fetchone()
                odeme_tahsilat_toplam = tahsilat_sonuc[0] or 0.0
                if tahsilat_sonuc[1]:
                    son_odeme_tarihi = datetime.strptime(tahsilat_sonuc[1], '%Y-%m-%d').strftime('%d.%m.%Y')
                
                # Kalan Borç (Net Bakiye) - Bu kısım zaten doğru şekilde filtreliyor
                kalan_borc = self.get_musteri_net_bakiye(cari_id)

            else: # TEDARIKCI
                query_odeme = """
                    SELECT SUM(ch.tutar), MAX(ch.tarih) FROM cari_hareketler ch
                    WHERE ch.cari_id = ? AND ch.cari_tip = ? AND ch.islem_tipi = ? -- SADECE ODEME
                """
                self.c.execute(query_odeme, (cari_id, self.CARI_TIP_TEDARIKCI, self.ISLEM_TIP_ODEME))
                
                odeme_sonuc = self.c.fetchone()
                odeme_tahsilat_toplam = odeme_sonuc[0] or 0.0
                if odeme_sonuc[1]:
                    son_odeme_tarihi = datetime.strptime(odeme_sonuc[1], '%Y-%m-%d').strftime('%d.%m.%Y')

                # Kalan Borç (Net Bakiye) - Bu kısım zaten doğru şekilde filtreliyor
                kalan_borc = self.get_tedarikci_net_bakiye(cari_id)

            # Vadesi Geçmiş Borç (Bu kısım zaten doğru şekilde _get_vade_durumu çağırıyor)
            vadesi_gecmis_borc = 0.0
            vade_durumu = self._get_vade_durumu(cari_id, cari_tip)
            if kalan_borc > 0: # Sadece cari borçlu ise ve vadesi geçmiş borcu varsa
                 vadesi_gecmis_borc = vade_durumu["vadesi_gelmis"]

            data_list.append({
                'id': cari_id,
                'cari_adi': cari_adi,
                'fatura_sayisi': fatura_sayisi,
                'acik_hesap_toplam': acik_hesap_fatura_toplam,
                'odeme_tahsilat_toplam': odeme_tahsilat_toplam,
                'kalan_borc': kalan_borc,
                'vadesi_gecmis_borc': vadesi_gecmis_borc,
                'son_odeme_tarihi': son_odeme_tarihi
            })
        return data_list
        
    def get_cari_count(self, cari_tip, arama_terimi=None, perakende_haric=False):
        """Müşteri veya tedarikçi sayısını arama terimine göre döndürür."""
        if cari_tip == self.CARI_TIP_MUSTERI:
            return self.get_musteri_count(arama_terimi=arama_terimi, perakende_haric=perakende_haric)
        elif cari_tip == self.CARI_TIP_TEDARIKCI:
            return self.get_tedarikci_count(arama_terimi=arama_terimi)
        return 0

    def siparis_listele(self, baslangic_tarih=None, bitis_tarih=None, arama_terimi=None, cari_id_filter=None, durum_filter=None, siparis_tipi_filter=None, limit=None, offset=None):
        """
        Belirtilen kriterlere göre siparişleri listeler.
        Dönüş: (id, siparis_no, tarih, cari_tip, cari_id, toplam_tutar, durum, teslimat_tarihi)
        """
        q = """
            SELECT 
                s.id, s.siparis_no, s.tarih, s.cari_tip, s.cari_id, s.toplam_tutar, s.durum, s.teslimat_tarihi
            FROM siparisler s
            LEFT JOIN musteriler m ON s.cari_id = m.id AND s.cari_tip = 'MUSTERI'
            LEFT JOIN tedarikciler t ON s.cari_id = t.id AND s.cari_tip = 'TEDARIKCI'
            LEFT JOIN siparis_kalemleri sk ON s.id = sk.siparis_id
            LEFT JOIN tbl_stoklar urun ON sk.urun_id = urun.id 
        """
        p = []
        conditions = []

        if baslangic_tarih:
            conditions.append("s.tarih >= ?")
            p.append(baslangic_tarih)
        if bitis_tarih:
            conditions.append("s.tarih <= ?")
            p.append(bitis_tarih)

        if cari_id_filter:
            conditions.append("s.cari_id = ?")
            p.append(cari_id_filter)

        if durum_filter and durum_filter != "TÜMÜ":
            conditions.append("s.durum = ?")
            p.append(durum_filter)
        
        if siparis_tipi_filter and siparis_tipi_filter != "TÜMÜ":
            conditions.append("s.cari_tip = ?") # Sipariş tipi 'cari_tip' sütununda tutuluyor
            p.append(siparis_tipi_filter)

        if arama_terimi:
            term = f"%{arama_terimi}%"
            conditions.append("""(
                                s.siparis_no LIKE ? OR
                                m.ad LIKE ? OR
                                t.ad LIKE ? OR
                                urun.urun_adi LIKE ? OR
                                urun.urun_kodu LIKE ?
                              )""")
            p.extend([term, term, term, term, term])

        if conditions:
            q += " WHERE " + " AND ".join(conditions)

        q += " GROUP BY s.id ORDER BY s.tarih DESC, s.id DESC" # Gruplayarak her siparişi bir kez al

        if limit is not None:
            q += " LIMIT ?"
            p.append(limit)
        if offset is not None:
            q += " OFFSET ?"
            p.append(offset)
        
        self.c.execute(q, p)
        return self.c.fetchall()


    def get_siparis_count(self, baslangic_tarih=None, bitis_tarih=None, arama_terimi=None, cari_id_filter=None, durum_filter=None, siparis_tipi_filter=None):
        """
        Belirtilen kriterlere uyan toplam sipariş sayısını döndürür.
        """
        q = """
            SELECT COUNT(DISTINCT s.id)
            FROM siparisler s
            LEFT JOIN musteriler m ON s.cari_id = m.id AND s.cari_tip = 'MUSTERI'
            LEFT JOIN tedarikciler t ON s.cari_id = t.id AND s.cari_tip = 'TEDARIKCI'
            LEFT JOIN siparis_kalemleri sk ON s.id = sk.siparis_id
            LEFT JOIN tbl_stoklar urun ON sk.urun_id = urun.id 
        """
        p = []
        conditions = []

        if baslangic_tarih:
            conditions.append("s.tarih >= ?")
            p.append(baslangic_tarih)
        if bitis_tarih:
            conditions.append("s.tarih <= ?")
            p.append(bitis_tarih)

        if cari_id_filter:
            conditions.append("s.cari_id = ?")
            p.append(cari_id_filter)

        if durum_filter and durum_filter != "TÜMÜ":
            conditions.append("s.durum = ?")
            p.append(durum_filter)
        
        if siparis_tipi_filter and siparis_tipi_filter != "TÜMÜ":
            conditions.append("s.cari_tip = ?")
            p.append(siparis_tipi_filter)

        if arama_terimi:
            term = f"%{arama_terimi}%"
            conditions.append("""(
                                s.siparis_no LIKE ? OR
                                m.ad LIKE ? OR
                                t.ad LIKE ? OR
                                urun.urun_adi LIKE ? OR
                                urun.urun_kodu LIKE ?
                              )""")
            p.extend([term, term, term, term, term])

        if conditions:
            q += " WHERE " + " AND ".join(conditions)
            
        self.c.execute(q, p)
        return self.c.fetchone()[0]

    def get_next_stok_kodu(self, length=10):
        """
        Mevcut stok kodları arasında en yüksek sayısal değeri bulur ve bir sonraki kodu döndürür.
        Belirtilen uzunluğa kadar baştan sıfırlarla doldurur.
        """
        self.c.execute("SELECT urun_kodu FROM tbl_stoklar")
        existing_codes = self.c.fetchall()
        
        max_numeric_code = 0
        for code_tuple in existing_codes:
            code = code_tuple[0]
            if code.isdigit():
                try:
                    numeric_code = int(code)
                    if numeric_code > max_numeric_code:
                        max_numeric_code = numeric_code
                except ValueError:
                    pass
        
        next_code = max_numeric_code + 1
        return str(next_code).zfill(length)

    def get_next_siparis_no(self, prefix="", length=6): # prefix eklendi (örneğin "MS", "AS")
        """
        Mevcut sipariş kodları arasında en yüksek sayısal değeri bulur ve bir sonraki kodu döndürür.
        Belirtilen uzunluğa kadar baştan sıfırlarla doldurur.
        Opsiyonel olarak bir önek alabilir (örn. 'MS' için Müşteri Siparişi, 'AS' için Alış Siparişi).
        """
        self.c.execute("SELECT siparis_no FROM siparisler WHERE siparis_no LIKE ? || '%'", (prefix,))
        existing_codes = self.c.fetchall()
        
        max_numeric_code = 0
        for code_tuple in existing_codes:
            code = code_tuple[0]
            # Önekten sonraki sayısal kısmı ayır
            numeric_part = code[len(prefix):]
            if numeric_part.isdigit():
                try:
                    numeric_code = int(numeric_part)
                    if numeric_code > max_numeric_code:
                        max_numeric_code = numeric_code
                except ValueError:
                    pass # Sayısal olmayan kısmı atla
        
        next_code = max_numeric_code + 1
        return prefix + str(next_code).zfill(length)

    def siparis_ekle(self, siparis_no, siparis_tipi, cari_id, toplam_tutar, durum, kalemler, siparis_notlari=None, teslimat_tarihi=None, genel_iskonto_tipi='YOK', genel_iskonto_degeri=0.0):
        try:
            self.conn.execute("BEGIN TRANSACTION")
            self.c.execute("SELECT id FROM siparisler WHERE siparis_no = ?", (siparis_no,))
            if self.c.fetchone():
                self.conn.rollback(); return False, f"'{siparis_no}' sipariş numarası zaten mevcut."

            cari_tip_for_db = self.CARI_TIP_MUSTERI if siparis_tipi == self.SIPARIS_TIP_SATIS else self.CARI_TIP_TEDARIKCI
            
            toplam_kdv_haric_kalemler, toplam_kdv_dahil_kalemler = 0.0, 0.0
            kalemler_for_insert = []
            
            for item in kalemler:
                urun_id, miktar, birim_fiyat_haric, kdv_orani, alis_fiyati, isk1, isk2 = item
                iskontolu_bf_haric = self.safe_float(birim_fiyat_haric) * (1 - self.safe_float(isk1) / 100) * (1 - self.safe_float(isk2) / 100)
                kalem_tkh = iskontolu_bf_haric * self.safe_float(miktar)
                kdv_tutari = kalem_tkh * (self.safe_float(kdv_orani) / 100)
                kalem_tkd = kalem_tkh + kdv_tutari
                toplam_kdv_haric_kalemler += kalem_tkh
                toplam_kdv_dahil_kalemler += kalem_tkd
                satis_fiyati = birim_fiyat_haric * (1 + self.safe_float(kdv_orani) / 100)
                
                kalemler_for_insert.append((urun_id, miktar, birim_fiyat_haric, kdv_orani, kdv_tutari, kalem_tkh, kalem_tkd, alis_fiyati, satis_fiyati, isk1, isk2))

            uygulanan_genel_iskonto = genel_iskonto_degeri if genel_iskonto_tipi == self.ISKONTO_TIP_TUTAR else toplam_kdv_haric_kalemler * (genel_iskonto_degeri / 100)
            final_total_tutar = toplam_kdv_dahil_kalemler - uygulanan_genel_iskonto

            current_time, olusturan_id, tarih_str = self.get_current_datetime_str(), self._get_current_user_id(), datetime.now().strftime('%Y-%m-%d')

            self.c.execute("INSERT INTO siparisler (siparis_no, tarih, cari_tip, cari_id, toplam_tutar, durum, siparis_notlari, teslimat_tarihi, genel_iskonto_tipi, genel_iskonto_degeri, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (siparis_no, tarih_str, cari_tip_for_db, cari_id, final_total_tutar, durum, siparis_notlari, teslimat_tarihi, genel_iskonto_tipi, genel_iskonto_degeri, current_time, olusturan_id))
            siparis_id = self.c.lastrowid

            for urun_id, miktar, bf, kdv, ktutar, tkh, tkd, af, sf, i1, i2 in kalemler_for_insert:
                 self.c.execute("INSERT INTO siparis_kalemleri (siparis_id, urun_id, miktar, birim_fiyat, kdv_orani, kdv_tutari, kalem_toplam_kdv_haric, kalem_toplam_kdv_dahil, alis_fiyati_siparis_aninda, satis_fiyati_siparis_aninda, iskonto_yuzde_1, iskonto_yuzde_2, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                  (siparis_id, urun_id, miktar, bf, kdv, ktutar, tkh, tkd, af, sf, i1, i2, current_time, olusturan_id))

            self.conn.commit()
            return True, f"'{siparis_no}' numaralı sipariş başarıyla oluşturuldu."
        except Exception as e:
            self.conn.rollback()
            return False, f"Sipariş oluşturulurken hata: {e}\n{traceback.format_exc()}"
        
    def _ensure_default_urun_birimi(self):
        try:
            self.c.execute("SELECT id FROM urun_birimleri WHERE birim_adi=?", ("Adet",))
            result = self.c.fetchone()
            if result:
                return True, "Adet ürün birimi bulundu."
            else:
                olusturan_id = 1 # Genellikle 'admin' kullanıcısının ID'si
                current_time = self.get_current_datetime_str()
                self.c.execute("INSERT INTO urun_birimleri (birim_adi, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?)",
                               ("Adet", current_time, olusturan_id))
                self.conn.commit()
                return True, "Adet ürün birimi başarıyla oluşturuldu."
        except Exception as e:
            return False, f"Adet ürün birimi oluşturulurken/kontrol edilirken hata: {e}"

    def _ensure_default_ulke(self):
        try:
            self.c.execute("SELECT id FROM urun_ulkeleri WHERE ulke_adi=?", ("Türkiye",))
            result = self.c.fetchone()
            if result:
                return True, "Türkiye ülkesi bulundu."
            else:
                olusturan_id = 1 # Genellikle 'admin' kullanıcısının ID'si
                current_time = self.get_current_datetime_str()
                self.c.execute("INSERT INTO urun_ulkeleri (ulke_adi, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?)",
                               ("Türkiye", current_time, olusturan_id))
                self.conn.commit()
                return True, "Türkiye ülkesi başarıyla oluşturuldu."
        except Exception as e:
            return False, f"Türkiye ülkesi oluşturulurken/kontrol edilirken hata: {e}"

    def siparis_guncelle(self, siparis_id, yeni_siparis_no, yeni_siparis_tipi, yeni_cari_id, yeni_toplam_tutar, yeni_durum, yeni_kalemler, yeni_siparis_notlari=None, yeni_teslimat_tarihi=None, genel_iskonto_tipi='YOK', genel_iskonto_degeri=0.0):
        try:
            self.conn.execute("BEGIN TRANSACTION")
            self.c.execute("DELETE FROM siparis_kalemleri WHERE siparis_id = ?", (siparis_id,))

            toplam_kdv_haric_kalemler, toplam_kdv_dahil_kalemler = 0.0, 0.0
            kalemler_for_insert = []
            for item in yeni_kalemler:
                urun_id, miktar, birim_fiyat_haric, kdv_orani, alis_fiyati, isk1, isk2 = item
                iskontolu_bf_haric = self.safe_float(birim_fiyat_haric) * (1 - self.safe_float(isk1) / 100) * (1 - self.safe_float(isk2) / 100)
                kalem_tkh = iskontolu_bf_haric * self.safe_float(miktar)
                kdv_tutari = kalem_tkh * (self.safe_float(kdv_orani) / 100)
                kalem_tkd = kalem_tkh + kdv_tutari
                toplam_kdv_haric_kalemler += kalem_tkh
                toplam_kdv_dahil_kalemler += kalem_tkd
                satis_fiyati = birim_fiyat_haric * (1 + self.safe_float(kdv_orani) / 100)
                
                kalemler_for_insert.append((urun_id, miktar, birim_fiyat_haric, kdv_orani, kdv_tutari, kalem_tkh, kalem_tkd, alis_fiyati, satis_fiyati, isk1, isk2))

            uygulanan_genel_iskonto = genel_iskonto_degeri if genel_iskonto_tipi == self.ISKONTO_TIP_TUTAR else toplam_kdv_haric_kalemler * (genel_iskonto_degeri / 100)
            final_total_tutar = toplam_kdv_dahil_kalemler - uygulanan_genel_iskonto

            current_time, guncelleyen_id, tarih_str = self.get_current_datetime_str(), self._get_current_user_id(), datetime.now().strftime('%Y-%m-%d')
            cari_tip_for_db = self.CARI_TIP_MUSTERI if yeni_siparis_tipi == self.SIPARIS_TIP_SATIS else self.CARI_TIP_TEDARIKCI

            self.c.execute("UPDATE siparisler SET siparis_no=?, tarih=?, cari_tip=?, cari_id=?, toplam_tutar=?, durum=?, siparis_notlari=?, teslimat_tarihi=?, genel_iskonto_tipi=?, genel_iskonto_degeri=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                            (yeni_siparis_no, tarih_str, cari_tip_for_db, yeni_cari_id, final_total_tutar, yeni_durum, yeni_siparis_notlari, yeni_teslimat_tarihi, genel_iskonto_tipi, genel_iskonto_degeri, current_time, guncelleyen_id, siparis_id))

            for urun_id, miktar, bf, kdv, ktutar, tkh, tkd, af, sf, i1, i2 in kalemler_for_insert:
                self.c.execute("INSERT INTO siparis_kalemleri (siparis_id, urun_id, miktar, birim_fiyat, kdv_orani, kdv_tutari, kalem_toplam_kdv_haric, kalem_toplam_kdv_dahil, alis_fiyati_siparis_aninda, satis_fiyati_siparis_aninda, iskonto_yuzde_1, iskonto_yuzde_2, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 (siparis_id, urun_id, miktar, bf, kdv, ktutar, tkh, tkd, af, sf, i1, i2, current_time, guncelleyen_id))

            self.conn.commit()
            return True, f"Sipariş '{yeni_siparis_no}' başarıyla güncellendi."
        except Exception as e:
            self.conn.rollback()
            return False, f"Sipariş güncellenirken hata: {e}\n{traceback.format_exc()}"
                        
    def get_siparis_by_id(self, siparis_id):
        """
        Belirli bir siparişin tüm ana bilgilerini döndürür.
        """
        self.c.execute("SELECT id, siparis_no, tarih, cari_tip, cari_id, toplam_tutar, durum, fatura_id, olusturma_tarihi_saat, olusturan_kullanici_id, son_guncelleme_tarihi_saat, son_guncelleyen_kullanici_id, siparis_notlari, onay_durumu, teslimat_tarihi, genel_iskonto_tipi, genel_iskonto_degeri FROM siparisler WHERE id=?", (siparis_id,))
        return self.c.fetchone()


    def siparis_sil(self, siparis_id):
        """
        Belirli bir siparişi ve ilişkili sipariş kalemlerini siler.
        Eğer sipariş bir faturaya dönüştürüldüyse silinmesine izin vermez.
        Dönüş: (bool, mesaj)
        """
        try:
            # Sipariş bilgilerini al
            siparis_bilgisi = self.get_siparis_by_id(siparis_id)
            if not siparis_bilgisi:
                return False, "Silinecek sipariş bulunamadı."
            
            # Eğer sipariş bir faturaya dönüştürüldüyse silinemez
            # siparis_bilgisi[7] -> fatura_id sütunu (eğer doluysa, yani bir fatura ID'si varsa)
            if siparis_bilgisi[7] is not None:
                # Fatura numarasını da alıp mesajda gösterebiliriz.
                # fatura_id_ref_db = siparis_bilgisi[7]
                # fatura_info = self.fatura_getir_by_id(fatura_id_ref_db)
                # fatura_no = fatura_info[1] if fatura_info else "Bilinmiyor"
                return False, f"Bu sipariş bir faturaya dönüştürülmüştür. Lütfen önce ilgili faturayı silin."

            self.conn.execute("BEGIN TRANSACTION")

            # Sipariş kalemlerini sil
            self.c.execute("DELETE FROM siparis_kalemleri WHERE siparis_id=?", (siparis_id,))
            
            # Ana sipariş kaydını sil
            self.c.execute("DELETE FROM siparisler WHERE id=?", (siparis_id,))
            
            self.conn.commit()
            return True, f"Sipariş '{siparis_bilgisi[1]}' başarıyla silindi."
        except Exception as e:
            self.conn.rollback()
            return False, f"Sipariş silinirken bir hata oluştu: {e}\n{traceback.format_exc()}"


    def get_siparis_kalemleri(self, siparis_id):
        """
        Belirli bir siparişin kalemlerini döndürür.
        """
        self.c.execute("SELECT sk.id, sk.siparis_id, sk.urun_id, sk.miktar, sk.birim_fiyat, sk.kdv_orani, sk.kdv_tutari, sk.kalem_toplam_kdv_haric, sk.kalem_toplam_kdv_dahil, sk.alis_fiyati_siparis_aninda, sk.satis_fiyati_siparis_aninda, sk.iskonto_yuzde_1, sk.iskonto_yuzde_2, sk.olusturma_tarihi_saat, sk.olusturan_kullanici_id, sk.son_guncelleme_tarihi_saat, sk.son_guncelleyen_kullanici_id FROM siparis_kalemleri sk JOIN tbl_stoklar s ON sk.urun_id=s.id WHERE sk.siparis_id=?", (siparis_id,))
        return self.c.fetchall()

    def musteri_guncelle(self, id, kod, ad, telefon, adres, vergi_dairesi, vergi_no):
        if not (kod and ad):
            return False, "Müşteri Kodu ve Adı zorunludur."

        if str(id) == str(self.perakende_musteri_id) and kod != self.PERAKENDE_MUSTERI_KODU:
            kod = self.PERAKENDE_MUSTERI_KODU
        elif kod == self.PERAKENDE_MUSTERI_KODU and str(id) != str(self.perakende_musteri_id):
            return False, f"'{self.PERAKENDE_MUSTERI_KODU}' özel bir koddur ve başka bir müşteriye atanamaz."

        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            guncelleyen_id = self._get_current_user_id() # Değişiklik
            self.c.execute("UPDATE musteriler SET kod=?,ad=?,telefon=?,adres=?,vergi_dairesi=?,vergi_no=?,son_guncelleme_tarihi_saat=?,son_guncelleyen_kullanici_id=? WHERE id=?",
                           (kod,ad,telefon,adres,vergi_dairesi,vergi_no,current_time,guncelleyen_id,id))
            self.conn.commit()

            # ### HATA DÜZELTMESİ BURADA ###
            # Metot artık her zaman iki değer döndürecek.
            if self.c.rowcount > 0:
                return True, "Müşteri bilgileri başarıyla güncellendi."
            else:
                return True, "Müşteri bilgileri güncellendi (değişiklik yapılmadı)."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu müşteri kodu başka bir müşteri için kullanılıyor."
        except Exception as e:
            self.conn.rollback()
            return False, f"Müşteri güncelleme sırasında hata: {e}"

    def musteri_listesi_al(self, arama_terimi=None, perakende_haric=False, limit=None, offset=None):
        query = """
            SELECT id, ad, soyad, kod, vergi_dairesi, vergi_no, adres, telefon, email, notlar
            FROM musteriler
        """
        params = []
        conditions = []

        if perakende_haric:
            conditions.append("kod != ?")
            params.append(self.PERAKENDE_MUSTERI_KODU)
        
        if arama_terimi:
            # Arama terimini Python tarafında normalleştir
            normalized_term = normalize_turkish_chars(arama_terimi)
            term_wildcard = f"%{normalized_term}%" # LIKE için %

            # SQLite'da direkt olarak TR karşılığı olmadığı için her sütun için replace zinciri kullanacağız.
            # Bu performanslı bir çözüm değildir, sadece arama yeteneğini genişletir.
            # Daha iyi bir çözüm için veritabanında normalize sütunlar tutmak gerekir.
            turkish_normalize_sql = lambda col: f"""
                LOWER(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(
                                        REPLACE(
                                            REPLACE(
                                                REPLACE(
                                                    REPLACE(
                                                        REPLACE(
                                                            REPLACE(
                                                                REPLACE(
                                                                    REPLACE(
                                                                        REPLACE({col}, 'Ş', 'S'),
                                                                    'İ', 'I'),
                                                                'Ç', 'C'),
                                                            'Ğ', 'G'),
                                                        'Ö', 'O'),
                                                    'Ü', 'U'),
                                                'ş', 's'),
                                            'ı', 'i'),
                                        'ç', 'c'),
                                    'ğ', 'g'),
                                'ö', 'o'),
                            'ü', 'u'),
                        'I', 'i'), -- Büyük I'yi küçük i'ye çevir
                    'İ', 'i')  -- Büyük İ'yi küçük i'ye çevir
                )
            """

            search_clauses = [
                f"{turkish_normalize_sql('kod')} LIKE ?",
                f"{turkish_normalize_sql('ad')} LIKE ?",
                f"{turkish_normalize_sql('soyad')} LIKE ?",
                f"{turkish_normalize_sql('telefon')} LIKE ?",
                f"{turkish_normalize_sql('adres')} LIKE ?",
                f"{turkish_normalize_sql('vergi_dairesi')} LIKE ?",
                f"{turkish_normalize_sql('vergi_no')} LIKE ?"
            ]
            
            conditions.append(f"({ ' OR '.join(search_clauses) })")
            params.extend([term_wildcard] * len(search_clauses))

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY ad ASC"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)

        self.c.execute(query, params)
        return self.c.fetchall()


    def get_musteri_sayisi(self, arama_terimi="", perakende_haric=False):
        """
        Belirtilen filtre kriterlerine göre toplam müşteri sayısını döner.
        """
        query = "SELECT COUNT(id) FROM musteriler"
        params = []
        
        conditions = []

        if perakende_haric:
            conditions.append("kod != ?")
            params.append(self.PERAKENDE_MUSTERI_KODU)
        
        if arama_terimi:
            # Arama terimini 'ad', 'soyad', 'kod', 'telefon' gibi ilgili sütunlarda arayabilirsiniz.
            # '%{}%' kullanarak LIKE operatörü ile arama yaparız.
            search_query = " (ad LIKE ? OR soyad LIKE ? OR kod LIKE ? OR telefon LIKE ?) "
            conditions.append(search_query)
            search_param = f"%{arama_terimi}%"
            params.extend([search_param, search_param, search_param, search_param])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        self.c.execute(query, params)
        return self.c.fetchone()[0] # İlk sütunu (COUNT değeri) döner

    def get_musteri_count(self, arama_terimi=None, perakende_haric=False):
        query = "SELECT COUNT(id) FROM musteriler"
        params = []
        conditions = []

        if perakende_haric and self.perakende_musteri_id is not None:
            conditions.append("id != ?")
            params.append(self.PERAKENDE_MUSTERI_KODU) # ID değil, KOD kullanıyoruz
            
        if arama_terimi:
            normalized_term = normalize_turkish_chars(arama_terimi)
            term_wildcard = f"%{normalized_term}%"

            turkish_normalize_sql = lambda col: f"""
                LOWER(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(
                                        REPLACE(
                                            REPLACE(
                                                REPLACE(
                                                    REPLACE(
                                                        REPLACE(
                                                            REPLACE(
                                                                REPLACE(
                                                                    REPLACE(
                                                                        REPLACE({col}, 'Ş', 'S'),
                                                                    'İ', 'I'),
                                                                'Ç', 'C'),
                                                            'Ğ', 'G'),
                                                        'Ö', 'O'),
                                                    'Ü', 'U'),
                                                'ş', 's'),
                                            'ı', 'i'),
                                        'ç', 'c'),
                                    'ğ', 'g'),
                                'ö', 'o'),
                            'ü', 'u'),
                        'I', 'i'), -- Büyük I'yi küçük i'ye çevir
                    'İ', 'i')  -- Büyük İ'yi küçük i'ye çevir
                )
            """
            search_clauses = [
                f"{turkish_normalize_sql('kod')} LIKE ?",
                f"{turkish_normalize_sql('ad')} LIKE ?",
                f"{turkish_normalize_sql('soyad')} LIKE ?",
                f"{turkish_normalize_sql('telefon')} LIKE ?",
                f"{turkish_normalize_sql('adres')} LIKE ?",
                f"{turkish_normalize_sql('vergi_dairesi')} LIKE ?",
                f"{turkish_normalize_sql('vergi_no')} LIKE ?"
            ]
            
            conditions.append(f"({ ' OR '.join(search_clauses) })")
            params.extend([term_wildcard] * len(search_clauses))
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        self.c.execute(query, params)
        return self.c.fetchone()[0]

    def musteri_getir_by_id(self, musteri_id):
        # 'musteri_kodu' sütunu yerine 'kod' sütununu seçiyoruz
        self.c.execute("SELECT id,kod,ad,telefon,adres,vergi_dairesi,vergi_no FROM musteriler WHERE id=?",(musteri_id,))
        result = self.c.fetchone()
        if result:
            # Debug mesajını da 'kod' sütununa göre güncelleyelim
            logging.debug(f"Müşteri adı: {result['ad']}, Kodu: {result['kod']}")
        return result

    def musteri_sil(self, musteri_id):
        if str(musteri_id) == str(self.perakende_musteri_id):
            return False, "Genel perakende müşteri kaydı silinemez."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            # Müşteriye ait fatura, tahsilat vb. var mı kontrol et
            self.c.execute("SELECT COUNT(*) FROM cari_hareketler WHERE cari_id=? AND cari_tip='MUSTERI'",(musteri_id,))
            if self.c.fetchone()[0]>0:
                self.conn.rollback()
                return False, "Bu müşteriye ait cari hareketler (fatura, tahsilat vb.) bulunmaktadır.\nBir müşteriyi silebilmek için öncelikle tüm ilişkili kayıtların (faturalar, tahsilatlar vb.) silinmesi gerekir."
            
            self.c.execute("DELETE FROM musteriler WHERE id=?",(musteri_id,))
            self.conn.commit()
            # DÜZELTME BAŞLANGICI: Başarı durumu ve mesaj döndürüyoruz
            if self.c.rowcount > 0:
                return True, "Müşteri başarıyla silindi."
            else:
                return False, "Müşteri bulunamadı veya silinemedi."
            
        except Exception as e:
            self.conn.rollback()
            return False, f"Müşteri silme sırasında hata: {e}"
        
    def tedarikci_ekle(self, kod, ad, telefon, adres, vergi_dairesi, vergi_no):
        if not (kod and ad):
            return False, "Tedarikçi Kodu ve Adı zorunludur."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            olusturan_id = self._get_current_user_id() # Değişiklik
            self.c.execute("INSERT INTO tedarikciler (tedarikci_kodu, ad, telefon, adres, vergi_dairesi, vergi_no,olusturma_tarihi_saat,olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?)",
                           (kod, ad, telefon, adres, vergi_dairesi, vergi_no,current_time,olusturan_id))
            self.conn.commit()
            # DÜZELTME BAŞLANGICI: İki değer döndürüyoruz
            return True, self.c.lastrowid # Başarı durumu ve ID
            # DÜZELTME BİTİŞI
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu tedarikçi kodu zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            return False, f"Tedarikçi ekleme sırasında hata: {e}"
        
    def tedarikci_guncelle(self, id, kod, ad, telefon, adres, vergi_dairesi, vergi_no):
        if not (kod and ad):
            return False, "Tedarikçi Kodu ve Adı zorunludur."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            guncelleyen_id = self._get_current_user_id() # Değişiklik
            self.c.execute("UPDATE tedarikciler SET tedarikci_kodu=?, ad=?, telefon=?, adres=?, vergi_dairesi=?, vergi_no=?,son_guncelleme_tarihi_saat=?,son_guncelleyen_kullanici_id=? WHERE id=?",
                           (kod, ad, telefon, adres, vergi_dairesi, vergi_no,current_time,guncelleyen_id,id))
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, "Tedarikçi bilgileri başarıyla güncellendi."
            else:
                return False, "Tedarikçi bulunamadı veya bir değişiklik yapılmadı."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu tedarikçi kodu başka bir tedarikçi için kullanılıyor."
        except Exception as e:
            self.conn.rollback()
            return False, f"Tedarikçi güncelleme sırasında hata: {e}"
        
    def tedarikci_listesi_al(self, arama_terimi=None, limit=None, offset=None): 
        query = "SELECT id, tedarikci_kodu, ad, telefon, adres, vergi_dairesi, vergi_no FROM tedarikciler"
        params = []
        conditions = []
        
        if arama_terimi:
            normalized_term = normalize_turkish_chars(arama_terimi)
            term_wildcard = f"%{normalized_term}%"

            turkish_normalize_sql = lambda col: f"""
                LOWER(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(
                                        REPLACE(
                                            REPLACE(
                                                REPLACE(
                                                    REPLACE(
                                                        REPLACE(
                                                            REPLACE(
                                                                REPLACE(
                                                                    REPLACE(
                                                                        REPLACE({col}, 'Ş', 'S'),
                                                                    'İ', 'I'),
                                                                'Ç', 'C'),
                                                            'Ğ', 'G'),
                                                        'Ö', 'O'),
                                                    'Ü', 'U'),
                                                'ş', 's'),
                                            'ı', 'i'),
                                        'ç', 'c'),
                                    'ğ', 'g'),
                                'ö', 'o'),
                            'ü', 'u'),
                        'I', 'i'), -- Büyük I'yi küçük i'ye çevir
                    'İ', 'i')  -- Büyük İ'yi küçük i'ye çevir
                )
            """
            search_clauses = [
                f"{turkish_normalize_sql('tedarikci_kodu')} LIKE ?",
                f"{turkish_normalize_sql('ad')} LIKE ?",
                f"{turkish_normalize_sql('telefon')} LIKE ?",
                f"{turkish_normalize_sql('adres')} LIKE ?",
                f"{turkish_normalize_sql('vergi_dairesi')} LIKE ?",
                f"{turkish_normalize_sql('vergi_no')} LIKE ?"
            ]
            
            conditions.append(f"({ ' OR '.join(search_clauses) })")
            params.extend([term_wildcard] * len(search_clauses))

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY ad ASC"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)

        self.c.execute(query, params)
        return self.c.fetchall()

    def get_tedarikci_count(self, arama_terimi=None):
        query = "SELECT COUNT(id) FROM tedarikciler"
        params = []
        conditions = []
        
        if arama_terimi:
            normalized_term = normalize_turkish_chars(arama_terimi)
            term_wildcard = f"%{normalized_term}%"

            turkish_normalize_sql = lambda col: f"""
                LOWER(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(
                                        REPLACE(
                                            REPLACE(
                                                REPLACE(
                                                    REPLACE(
                                                        REPLACE(
                                                            REPLACE(
                                                                REPLACE(
                                                                    REPLACE(
                                                                        REPLACE({col}, 'Ş', 'S'),
                                                                    'İ', 'I'),
                                                                'Ç', 'C'),
                                                            'Ğ', 'G'),
                                                        'Ö', 'O'),
                                                    'Ü', 'U'),
                                                'ş', 's'),
                                            'ı', 'i'),
                                        'ç', 'c'),
                                    'ğ', 'g'),
                                'ö', 'o'),
                            'ü', 'u'),
                        'I', 'i'), -- Büyük I'yi küçük i'ye çevir
                    'İ', 'i')  -- Büyük İ'yi küçük i'ye çevir
                )
            """
            search_clauses = [
                f"{turkish_normalize_sql('tedarikci_kodu')} LIKE ?",
                f"{turkish_normalize_sql('ad')} LIKE ?",
                f"{turkish_normalize_sql('telefon')} LIKE ?",
                f"{turkish_normalize_sql('adres')} LIKE ?",
                f"{turkish_normalize_sql('vergi_dairesi')} LIKE ?",
                f"{turkish_normalize_sql('vergi_no')} LIKE ?"
            ]
            
            conditions.append(f"({ ' OR '.join(search_clauses) })")
            params.extend([term_wildcard] * len(search_clauses))

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        self.c.execute(query, params)
        return self.c.fetchone()[0]

    def tedarikci_getir_by_id(self, tedarikci_id):
        self.c.execute("SELECT id, tedarikci_kodu, ad, telefon, adres, vergi_dairesi, vergi_no,olusturma_tarihi_saat,olusturan_kullanici_id,son_guncelleme_tarihi_saat,son_guncelleyen_kullanici_id FROM tedarikciler WHERE id=?", (tedarikci_id,))
        return self.c.fetchone()

    def tedarikci_sil(self, tedarikci_id):
        try:
            self.c.execute("BEGIN TRANSACTION")
            self.c.execute("SELECT COUNT(*) FROM cari_hareketler WHERE cari_id=? AND cari_tip='TEDARIKCI'",(tedarikci_id,))
            if self.c.fetchone()[0]>0:
                self.conn.rollback()
                return False, "Bu tedarikçiye ait cari hareketler (fatura, ödeme vb.) bulunmaktadır.\nBir tedarikçiyi silebilmek için öncelikle tüm ilişkili kayıtları silinmesi gerekir."
            self.c.execute("DELETE FROM tedarikciler WHERE id=?", (tedarikci_id,))
            self.conn.commit()
            # DÜZELTME BAŞLANGICI: Başarı durumu ve mesaj döndürüyoruz
            if self.c.rowcount > 0:
                return True, "Tedarikçi başarıyla silindi."
            else:
                return False, "Tedarikçi bulunamadı veya silinemedi."
            
        except Exception as e:
            self.conn.rollback()
            return False, f"Tedarikçi silme sırasında hata: {e}"
        
    def kategori_ekle(self, kategori_adi):
        if not kategori_adi:
            return False, "Kategori adı boş olamaz."
        try:
            current_time = self.get_current_datetime_str()
            olusturan_id = self._get_current_user_id() # Değişiklik
            self.c.execute("INSERT INTO urun_kategorileri (kategori_adi, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?)",
                           (kategori_adi, current_time, olusturan_id))
            self.conn.commit()
            return True, f"'{kategori_adi}' kategorisi başarıyla eklendi."
        except sqlite3.IntegrityError:
            self.conn.rollback() # Add rollback on integrity error
            return False, "Bu kategori adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            return False, f"Kategori eklenirken hata: {e}"
    
    def kategori_guncelle(self, kategori_id, yeni_kategori_adi):
        if not yeni_kategori_adi:
            return False, "Kategori adı boş olamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            guncelleyen_id = self._get_current_user_id() # Değişiklik
            self.c.execute("UPDATE urun_kategorileri SET kategori_adi=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                           (yeni_kategori_adi, current_time, guncelleyen_id, kategori_id))
            self.conn.commit()
            # DÜZELTME: Başarılı durumda (True, mesaj) döndür
            if self.c.rowcount > 0:
                return True, "Kategori başarıyla güncellendi."
            else:
                return False, "Kategori bulunamadı veya bir değişiklik yapılmadı."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu kategori adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            return False, f"Kategori güncellenirken hata: {e}"

    def kategori_sil(self, kategori_id):
        try:
            # Bu kategoriye ait ürün var mı kontrol et
            self.c.execute("SELECT COUNT(*) FROM tbl_stoklar WHERE kategori_id=?", (kategori_id,))
            if self.c.fetchone()[0] > 0:
                return False, "Bu kategoriye bağlı ürünler bulunmaktadır. Lütfen önce ürünlerin kategorisini değiştirin veya ürünleri silin."
            self.c.execute("DELETE FROM urun_kategorileri WHERE id=?", (kategori_id,))
            return self.c.rowcount > 0
        except Exception as e:
            return False, f"Kategori silinirken hata: {e}"

    def kategori_listele(self):
        self.c.execute("SELECT id, kategori_adi FROM urun_kategorileri ORDER BY kategori_adi ASC")
        return self.c.fetchall()

    def kategori_getir_by_id(self, kategori_id):
        self.c.execute("SELECT id, kategori_adi FROM urun_kategorileri WHERE id=?", (kategori_id,))
        return self.c.fetchone()

    # --- Marka Yönetimi Metotları ---
    def marka_ekle(self, marka_adi):
        if not marka_adi:
            return False, "Marka adı boş olamaz."
        try:
            current_time = self.get_current_datetime_str()
            olusturan_id = self._get_current_user_id() # Değişiklik
            self.c.execute("INSERT INTO urun_markalari (marka_adi, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?)",
                           (marka_adi, current_time, olusturan_id))
            self.conn.commit() # Commit here
            return True, f"'{marka_adi}' markası başarıyla eklendi." # Return tuple
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu marka adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            return False, f"Marka eklenirken hata: {e}"

    def marka_guncelle(self, marka_id, yeni_marka_adi):
        if not yeni_marka_adi:
            return False, "Marka adı boş olamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            guncelleyen_id = self._get_current_user_id() # Değişiklik
            self.c.execute("UPDATE urun_markalari SET marka_adi=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                           (yeni_marka_adi, current_time, guncelleyen_id, marka_id))
            self.conn.commit()
            # DÜZELTME: Başarılı durumda (True, mesaj) döndür
            if self.c.rowcount > 0:
                return True, "Marka başarıyla güncellendi."
            else:
                return False, "Marka bulunamadı veya bir değişiklik yapılmadı."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu marka adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            return False, f"Marka güncellenirken hata: {e}"

    def marka_sil(self, marka_id):
        try:
            # Bu markaya ait ürün var mı kontrol et
            self.c.execute("SELECT COUNT(*) FROM tbl_stoklar WHERE marka_id=?", (marka_id,))
            if self.c.fetchone()[0] > 0:
                self.conn.rollback()
                return False, "Bu markaya bağlı ürünler bulunmaktadır. Lütfen önce ürünlerin markasını değiştirin veya ürünleri silin."
            self.c.execute("DELETE FROM urun_markalari WHERE id=?", (marka_id,))
            self.conn.commit()
            return self.c.rowcount > 0
        except Exception as e:
            self.conn.rollback()
            return False, f"Marka silinirken hata: {e}"

    def marka_listele(self):
        self.c.execute("SELECT id, marka_adi FROM urun_markalari ORDER BY marka_adi ASC")
        return self.c.fetchall()

    def marka_getir_by_id(self, marka_id):
        self.c.execute("SELECT id, marka_adi FROM urun_markalari WHERE id=?", (marka_id,))
        return self.c.fetchone()

    def stok_ekle(self, kod, ad, stok_miktari, alis_haric, satis_haric, kdv_orani, min_stok_seviyesi, alis_kdv_dahil, satis_kdv_dahil, kategori_id=None, marka_id=None, urun_detayi=None, urun_resmi_yolu=None, fiyat_degisiklik_tarihi=None, urun_grubu_id=None, urun_birimi_id=None, ulke_id=None):
        if not (kod and ad):
            return False, "Ürün Kodu ve Adı zorunludur."
        try:
            s_m = self.safe_float(stok_miktari)
            a_f_h = self.safe_float(alis_haric)
            s_f_h = self.safe_float(satis_haric)
            k_o = self.safe_float(kdv_orani)
            min_s_s = self.safe_float(min_stok_seviyesi)
            a_f_d = self.safe_float(alis_kdv_dahil)
            s_f_d = self.safe_float(satis_kdv_dahil)
        except ValueError:
            return False, "Sayısal alanlar doğru formatta olmalıdır."
        
        try: # Bu try bloğu kalan tek doğru try bloğu olmalı
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            olusturan_id = self._get_current_user_id() 
            self.c.execute("INSERT INTO tbl_stoklar (urun_kodu, urun_adi, stok_miktari, alis_fiyati_kdv_haric, satis_fiyati_kdv_haric, kdv_orani, min_stok_seviyesi, alis_fiyati_kdv_dahil, satis_fiyati_kdv_dahil, kategori_id, marka_id, urun_detayi, urun_resmi_yolu, fiyat_degisiklik_tarihi, urun_grubu_id, urun_birimi_id, ulke_id, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (kod, ad, s_m, a_f_h, s_f_h, k_o, min_s_s, a_f_d, s_f_d, kategori_id, marka_id, urun_detayi, urun_resmi_yolu, fiyat_degisiklik_tarihi, urun_grubu_id, urun_birimi_id, ulke_id, current_time, olusturan_id))

            yeni_urun_id = self.c.lastrowid
            self.conn.commit()

            return True, yeni_urun_id

        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu ürün kodu zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            error_details = traceback.format_exc()
            logging.error(f"Stok ekleme sırasında beklenmeyen hata: {e}\nDetay: {error_details}")
            return False, f"Stok ekleme sırasında bir hata oluştu. Detaylar için log dosyasına bakınız."

    def stok_guncelle(self, id, kod, ad, stok_miktari, alis_haric, satis_haric, kdv_orani, min_stok_seviyesi, alis_kdv_dahil, satis_kdv_dahil, kategori_id=None, marka_id=None, urun_detayi=None, urun_resmi_yolu=None, fiyat_degisiklik_tarihi=None, urun_grubu_id=None, urun_birimi_id=None, ulke_id=None):
        if not (kod and ad):
            return False, "Ürün Kodu ve Adı zorunludur."
        
        try:
            # Gelen tüm sayısal değerleri güvenli bir şekilde float'a çevir
            yeni_stok_miktari_f = self.safe_float(stok_miktari)
            a_f_h = self.safe_float(alis_haric)
            s_f_h = self.safe_float(satis_haric)
            k_o = self.safe_float(kdv_orani)
            min_s_s = self.safe_float(min_stok_seviyesi)
            a_f_d = self.safe_float(alis_kdv_dahil)
            s_f_d = self.safe_float(satis_kdv_dahil)
        except ValueError:
            return False, "Sayısal alanlar doğru formatta olmalıdır."

        try:
            self.conn.execute("BEGIN TRANSACTION")

            # ADIM 1: Güncellemeden önce ürünün mevcut (eski) stok miktarını al
            self.c.execute("SELECT stok_miktari FROM tbl_stoklar WHERE id=?", (id,))
            eski_stok_miktari_tuple = self.c.fetchone()
            if not eski_stok_miktari_tuple:
                self.conn.rollback()
                return False, "Güncellenecek ürün bulunamadı."
            eski_stok_miktari_f = eski_stok_miktari_tuple[0]

            # ADIM 2: Ürünün stok miktarı dışındaki ana bilgilerini güncelle
            current_time = self.get_current_datetime_str()
            guncelleyen_id = self._get_current_user_id() 
            
            self.c.execute("""
                UPDATE tbl_stoklar SET
                    urun_kodu=?, urun_adi=?, alis_fiyati_kdv_haric=?,
                    satis_fiyati_kdv_haric=?, kdv_orani=?, min_stok_seviyesi=?,
                    alis_fiyati_kdv_dahil=?, satis_fiyati_kdv_dahil=?, kategori_id=?,
                    marka_id=?, urun_detayi=?, urun_resmi_yolu=?, fiyat_degisiklik_tarihi=?,
                    urun_grubu_id=?, urun_birimi_id=?, ulke_id=?,
                    son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=?
                WHERE id=?
            """, (kod, ad, a_f_h, s_f_h, k_o, min_s_s, a_f_d, s_f_d,
                  kategori_id, marka_id, urun_detayi, urun_resmi_yolu, fiyat_degisiklik_tarihi,
                  urun_grubu_id, urun_birimi_id, ulke_id, current_time, guncelleyen_id, id))

            # ADIM 3: Yeni stok miktarı ile eski stok miktarını karşılaştır ve fark varsa stok hareketi oluştur.
            stok_farki = yeni_stok_miktari_f - eski_stok_miktari_f

            if stok_farki != 0:
                islem_tipi = ""
                # Eğer fark pozitifse, bu bir manuel giriştir.
                if stok_farki > 0:
                    islem_tipi = self.STOK_ISLEM_TIP_GIRIS_MANUEL_DUZELTME
                # Eğer fark negatifse, bu bir manuel çıkıştır.
                else: 
                    islem_tipi = self.STOK_ISLEM_TIP_CIKIS_MANUEL_DUZELTME

                # Merkezi stok güncelleme ve hareket kaydetme metodunu çağır.
                # Bu metot hem stoğu günceller hem de hareketi kaydeder.
                self._stok_guncelle_ve_hareket_kaydet(
                    urun_id=id,
                    miktar_degisimi_net=stok_farki, # Net fark (pozitif veya negatif olabilir)
                    islem_tipi_aciklamasi=islem_tipi,
                    kaynak_tipi=self.KAYNAK_TIP_MANUEL, # Kaynak her zaman MANUEL olacak
                    kaynak_id=None,
                    referans_no=f"Ürün Kartı Düzeltme"
                )

            self.conn.commit()
            return True, f"Ürün '{ad}' başarıyla güncellendi."

        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu ürün kodu başka bir ürün için kullanılıyor."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Stok güncelleme sırasında hata: {e}\n{traceback.format_exc()}")
            return False, f"Stok güncelleme sırasında bir hata oluştu: {e}"
    
    def stok_listele(self, arama_terimi=None, limit=None, offset=None, kategori_id_filter=None, marka_id_filter=None, urun_grubu_id_filter=None, urun_birimi_id_filter=None, ulke_id_filter=None): # Yeni filtre parametreleri
        # DÜZELTME: Sorguda 'stok' yerine 'tbl_stoklar' kullanıldığından emin olun.
        # Sizin kodunuzda zaten 'tbl_stoklar s' olarak kullanılmış, bu doğru.
        query = """
            SELECT
                s.id, s.urun_kodu, s.urun_adi, s.stok_miktari,
                s.alis_fiyati_kdv_haric, s.satis_fiyati_kdv_haric, s.kdv_orani, s.min_stok_seviyesi,
                s.alis_fiyati_kdv_dahil, s.satis_fiyati_kdv_dahil,
                uk.kategori_adi, um.marka_adi,
                s.urun_detayi, s.urun_resmi_yolu, s.fiyat_degisiklik_tarihi,
                ug.grup_adi, ub.birim_adi, ul.ulke_adi,
                s.kategori_id, s.marka_id, s.urun_grubu_id, s.urun_birimi_id, s.ulke_id
            FROM tbl_stoklar s  -- Burası önemli!
            LEFT JOIN urun_kategorileri uk ON s.kategori_id = uk.id
            LEFT JOIN urun_markalari um ON s.marka_id = um.id
            LEFT JOIN urun_gruplari ug ON s.urun_grubu_id = ug.id
            LEFT JOIN urun_birimleri ub ON s.urun_birimi_id = ub.id
            LEFT JOIN urun_ulkeleri ul ON s.ulke_id = ul.id
        """
        params = []
        conditions = []

        if arama_terimi:
            conditions.append("(s.urun_kodu LIKE ? OR s.urun_adi LIKE ?)")
            term = f"%{arama_terimi}%"
            params.extend([term, term])
        
        if kategori_id_filter is not None:
            conditions.append("s.kategori_id = ?")
            params.append(kategori_id_filter)

        if marka_id_filter is not None:
            conditions.append("s.marka_id = ?")
            params.append(marka_id_filter)

        if urun_grubu_id_filter is not None:
            conditions.append("s.urun_grubu_id = ?")
            params.append(urun_grubu_id_filter)
        
        if urun_birimi_id_filter is not None:
            conditions.append("s.urun_birimi_id = ?")
            params.append(urun_birimi_id_filter)

        if ulke_id_filter is not None:
            conditions.append("s.ulke_id = ?")
            params.append(ulke_id_filter)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY s.urun_adi ASC"
    
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)
    
        self.c.execute(query, params) # Hatanın alındığı satır bu.
        return self.c.fetchall()

        
    def get_stok_count(self, arama_terimi=None, kategori_id_filter=None, marka_id_filter=None, urun_grubu_id_filter=None, urun_birimi_id_filter=None, ulke_id_filter=None): # Yeni filtre parametreleri
        query = "SELECT COUNT(s.id) FROM tbl_stoklar s"
        params = []
        conditions = []

        if arama_terimi:
            conditions.append("(s.urun_kodu LIKE ? OR s.urun_adi LIKE ?)")
            term = f"%{arama_terimi}%"
            params.extend([term, term])
        
        if kategori_id_filter is not None:
            conditions.append("s.kategori_id = ?")
            params.append(kategori_id_filter)

        if marka_id_filter is not None:
            conditions.append("s.marka_id = ?")
            params.append(marka_id_filter)

        if urun_grubu_id_filter is not None:
            conditions.append("s.urun_grubu_id = ?")
            params.append(urun_grubu_id_filter)

        if urun_birimi_id_filter is not None:
            conditions.append("s.urun_birimi_id = ?")
            params.append(urun_birimi_id_filter)

        if ulke_id_filter is not None:
            conditions.append("s.ulke_id = ?")
            params.append(ulke_id_filter)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        self.c.execute(query, params)
        return self.c.fetchone()[0]


    def stok_getir_by_id(self, urun_id):
        query = """
            SELECT
                s.id,                  -- 0
                s.urun_kodu,           -- 1
                s.urun_adi,            -- 2
                s.stok_miktari,        -- 3
                s.alis_fiyati_kdv_haric, -- 4 (KDV Hariç Alış)
                s.satis_fiyati_kdv_haric, -- 5 (KDV Hariç Satış)
                s.kdv_orani,           -- 6
                s.min_stok_seviyesi,   -- 7
                s.alis_fiyati_kdv_dahil, -- 8 (KDV Dahil Alış)
                s.satis_fiyati_kdv_dahil, -- 9 (KDV Dahil Satış)
                s.olusturma_tarihi_saat,   -- 10
                s.olusturan_kullanici_id,  -- 11
                s.son_guncelleme_tarihi_saat, -- 12
                s.son_guncelleyen_kullanici_id, -- 13
                uk.kategori_adi,           -- 14 (LEFT JOIN'den gelir)
                um.marka_adi,              -- 15 (LEFT JOIN'den gelir)
                s.urun_detayi,             -- 16
                s.urun_resmi_yolu,         -- 17
                s.fiyat_degisiklik_tarihi, -- 18
                ug.grup_adi,               -- 19 (LEFT JOIN'den gelir)
                ub.birim_adi,              -- 20 (LEFT JOIN'den gelir)
                ul.ulke_adi,               -- 21 (LEFT JOIN'den gelir)
                s.kategori_id,             -- 22 (FK)
                s.marka_id,                -- 23 (FK)
                s.urun_grubu_id,           -- 24 (FK)
                s.urun_birimi_id,          -- 25 (FK)
                s.ulke_id                  -- 26 (FK)
            FROM tbl_stoklar s
            LEFT JOIN urun_kategorileri uk ON s.kategori_id = uk.id
            LEFT JOIN urun_markalari um ON s.marka_id = um.id
            LEFT JOIN urun_gruplari ug ON s.urun_grubu_id = ug.id
            LEFT JOIN urun_birimleri ub ON s.urun_birimi_id = ub.id
            LEFT JOIN urun_ulkeleri ul ON s.ulke_id = ul.id
            WHERE s.id=?
        """
        self.c.execute(query, (urun_id,))
        return self.c.fetchone()
    
    def get_kategoriler_for_combobox(self):
        self.c.execute("SELECT id, kategori_adi FROM urun_kategorileri ORDER BY kategori_adi ASC")
        return {row['kategori_adi']: row['id'] for row in self.c.fetchall()}

    def get_markalar_for_combobox(self):
        self.c.execute("SELECT id, marka_adi FROM urun_markalari ORDER BY marka_adi ASC")
        return {row['marka_adi']: row['id'] for row in self.c.fetchall()}

    def get_urun_gruplari_for_combobox(self):
        self.c.execute("SELECT id, grup_adi FROM urun_gruplari ORDER BY grup_adi ASC")
        return {row['grup_adi']: row['id'] for row in self.c.fetchall()}

    def get_urun_birimleri_for_combobox(self):
        self.c.execute("SELECT id, birim_adi FROM urun_birimleri ORDER BY birim_adi ASC")
        return {row['birim_adi']: row['id'] for row in self.c.fetchall()}

    def get_ulkeler_for_combobox(self):
        self.c.execute("SELECT id, ulke_adi FROM urun_ulkeleri ORDER BY ulke_adi ASC")
        return {row['ulke_adi']: row['id'] for row in self.c.fetchall()}

    def stok_getir_by_kod(self, urun_kodu):
        
        self.c.execute("SELECT id,urun_kodu,urun_adi,stok_miktari,alis_fiyati_kdv_haric,satis_fiyati_kdv_haric,kdv_orani FROM tbl_stoklar WHERE urun_kodu=?",(urun_kodu,))
        return self.c.fetchone()

    def stok_hareketi_ekle(self, urun_id, islem_tipi, miktar, tarih, aciklama=""):
        """
        Belirli bir ürün için stok hareketi kaydeder ve stok miktarını günceller.
        İşlem öncesi ve sonrası stok miktarlarını da kaydeder.
        """
        if miktar <= 0:
            return False, "Miktar pozitif bir sayı olmalıdır."

        try:
            self.conn.execute("BEGIN TRANSACTION")

            self.c.execute("SELECT stok_miktari, urun_adi FROM tbl_stoklar WHERE id = ?", (urun_id,))
            urun_info = self.c.fetchone()
            if not urun_info:
                self.conn.rollback()
                return False, "Ürün bulunamadı."

            mevcut_stok = urun_info[0]
            urun_adi = urun_info[1]

            sonraki_stok = mevcut_stok

            if islem_tipi in ["Giriş (Artış)", "Giriş (Manuel)", "Sayım Fazlası", "İade Girişi"]:
                sonraki_stok = mevcut_stok + miktar
            elif islem_tipi in ["Çıkış (Azalış)", "Çıkış (Manuel)", "Sayım Eksiği", "Zayiat"]:
                sonraki_stok = mevcut_stok - miktar
            else:
                self.conn.rollback()
                return False, "Geçersiz işlem tipi. Lütfen geçerli bir işlem tipi seçin."

            self.c.execute("UPDATE tbl_stoklar SET stok_miktari = ? WHERE id = ?", (sonraki_stok, urun_id))

            hareket_aciklamasi = f"{islem_tipi} - {urun_adi} ({miktar:.2f} adet). "
            if aciklama:
                hareket_aciklamasi += f"Not: {aciklama}"

            # ### HATA DÜZELTMESİ BURADA ###
            # INSERT komutuna eksik olan "olusturan_kullanici_id" sütunu eklendi ve
            # VALUES kısmına bu sütun için "_get_current_user_id()" değeri verildi.
            current_time = self.get_current_datetime_str()
            olusturan_id = self._get_current_user_id() # Değişiklik
            self.c.execute("""
                INSERT INTO stok_hareketleri
                (urun_id, tarih, islem_tipi, miktar, onceki_stok, sonraki_stok, aciklama, kaynak, kaynak_id, olusturma_tarihi_saat, olusturan_kullanici_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (urun_id, tarih, islem_tipi, miktar, mevcut_stok, sonraki_stok, hareket_aciklamasi, "MANUEL", None, current_time, olusturan_id))

            self.conn.commit()
            return True, f"'{urun_adi}' için stok başarıyla güncellendi. Yeni Stok: {sonraki_stok:.2f} adet."

        except ValueError:
            self.conn.rollback()
            return False, "Miktar veya tarih formatı hatalı."
        except Exception as e:
            self.conn.rollback()
            error_details = traceback.format_exc()
            logging.error(f"Stok hareketi kaydedilirken hata oluştu: {e}\nDetaylar: {error_details}")
            return False, f"Stok hareketi kaydedilirken beklenmeyen bir hata oluştu. Detaylar için log dosyasına bakınız."

    def geriye_donuk_stok_hareketlerini_olustur(self):
        """
        Tüm mevcut faturaları tarar ve eksik olan stok hareketlerini oluşturur.
        Bu işlem, kendi geçici veritabanı bağlantısını oluşturarak thread-safe hale getirilmiştir.
        """
        conn_thread = None  # Thread'e özel bağlantı nesnesi
        try:
            # Adım 1: Bu thread için yeni, geçici bir veritabanı bağlantısı ve cursor oluştur.
            conn_thread = sqlite3.connect(self.db_name, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            cursor_thread = conn_thread.cursor()
            cursor_thread.row_factory = sqlite3.Row # Row factory ekleyin
            conn_thread.execute("PRAGMA foreign_keys = ON;") # Foreign key desteğini açın


            conn_thread.execute("BEGIN TRANSACTION")

            # ÖNLEM: Mükerrer kayıt olmaması için mevcut fatura kaynaklı stok hareketlerini temizle.
            cursor_thread.execute("DELETE FROM stok_hareketleri WHERE kaynak IN ('FATURA', 'İADE_FATURA')") # İade faturalarını da temizle
            print("Mevcut fatura kaynaklı stok hareketleri temizlendi.")

            # Stok miktarlarını sıfırla (önceki hatalı hesaplamaları sıfırdan başlatmak için)
            cursor_thread.execute("UPDATE tbl_stoklar SET stok_miktari = 0.0")
            print("Tüm ürünlerin stok miktarları sıfırlandı.")


            # Tüm faturaları ve kalemlerini çek (oluşturulma tarihine göre sıralı)
            cursor_thread.execute("""
                SELECT f.id, f.fatura_no, f.tarih, f.tip, fk.urun_id, fk.miktar
                FROM faturalar f
                JOIN fatura_kalemleri fk ON f.id = fk.fatura_id
                ORDER BY f.tarih ASC, f.olusturma_tarihi_saat ASC, f.id ASC
            """)
            fatura_kalemleri = cursor_thread.fetchall()

            if not fatura_kalemleri:
                conn_thread.commit()
                return True, "İşlenecek fatura bulunamadı. Stok hareketi oluşturulmadı."

            hareket_sayisi = 0
            for kalem in fatura_kalemleri:
                fatura_id, fatura_no, tarih_str, tip, urun_id, miktar = kalem

                # Stok hareketinin tipini ve miktar değişimini belirle
                islem_tipi_hareket = ""
                miktar_degisimi_net = 0.0
                kaynak_tipi_hareket = 'FATURA'

                if tip == 'SATIŞ':
                    islem_tipi_hareket = "Fatura Satış"
                    miktar_degisimi_net = -miktar # Satışta stok azalır
                elif tip == 'ALIŞ':
                    islem_tipi_hareket = "Fatura Alış"
                    miktar_degisimi_net = miktar # Alışta stok artar
                elif tip == 'SATIŞ İADE':
                    islem_tipi_hareket = "Fatura Satış İade"
                    miktar_degisimi_net = miktar # Satış iadesinde stok artar
                    kaynak_tipi_hareket = 'İADE_FATURA'
                elif tip == 'ALIŞ İADE':
                    islem_tipi_hareket = "Fatura Alış İade"
                    miktar_degisimi_net = -miktar # Alış iadesinde stok azalır
                    kaynak_tipi_hareket = 'İADE_FATURA'
                else: # Diğer tipler için (DEVİR_GİRİŞ) özel işlem
                    # Devir girişleri sadece stok hareketi olarak kaydedilir, fatura tipi olarak özel bir işleme sahip olabilir.
                    islem_tipi_hareket = "Devir Giriş"
                    miktar_degisimi_net = miktar
                    kaynak_tipi_hareket = 'FATURA' # Kaynak fatura olarak kalır

                # Ürünün mevcut stok miktarını al (sıfırlandıktan sonraki anlık miktar)
                cursor_thread.execute("SELECT stok_miktari, urun_adi FROM tbl_stoklar WHERE id = ?", (urun_id,))
                urun_info_current = cursor_thread.fetchone()
                if not urun_info_current:
                    print(f"UYARI: Ürün ID {urun_id} bulunamadı, stok hareketi oluşturulamadı.")
                    continue

                onceki_stok = urun_info_current['stok_miktari']
                sonraki_stok = onceki_stok + miktar_degisimi_net

                # Stok miktarını güncelle
                cursor_thread.execute("UPDATE tbl_stoklar SET stok_miktari = ? WHERE id = ?", (sonraki_stok, urun_id))

                # Stok hareketini kaydet
                current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                olusturan_id = self._get_current_user_id() # Kullanıcı ID'si

                cursor_thread.execute("""
                    INSERT INTO stok_hareketleri
                    (urun_id, tarih, islem_tipi, miktar, onceki_stok, sonraki_stok, aciklama, kaynak, kaynak_id, olusturma_tarihi_saat, olusturan_kullanici_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (urun_id, tarih_str, islem_tipi_hareket, abs(miktar), onceki_stok, sonraki_stok, f"Geçmiş Fatura No: {fatura_no}", kaynak_tipi_hareket, fatura_id, current_time_str, olusturan_id))
                hareket_sayisi += 1

            conn_thread.commit()
            return True, f"Geçmişe dönük {hareket_sayisi} adet stok hareketi başarıyla oluşturuldu ve stoklar yeniden hesaplandı."

        except Exception as e:
            if conn_thread:
                conn_thread.rollback()
            error_details = traceback.format_exc()
            logging.error(f"Geçmiş stok hareketleri oluşturulurken hata: {e}\nDetaylar: {error_details}")
            return False, f"Geçmiş stok hareketleri oluşturulurken hata: {e}\n{error_details}"
        finally:
            if conn_thread:
                conn_thread.close()

    def stok_sil(self, urun_id):
        try:
            self.conn.execute("BEGIN TRANSACTION")
            # Ürünün fatura, sipariş, teklif kalemlerinde ve stok hareketlerinde kullanılıp kullanılmadığını kontrol et
            for tablo_adi in ["fatura_kalemleri", "siparis_kalemleri", "teklif_kalemleri", "stok_hareketleri"]: # stok_hareketleri eklendi
                self.c.execute(f"SELECT COUNT(*) FROM {tablo_adi} WHERE urun_id=?", (urun_id,))
                if self.c.fetchone()[0] > 0:
                    self.conn.rollback()
                    return False, f"Bu ürün '{tablo_adi}' tablosunda kullanılıyor.\nÖnce ilgili kayıtları düzenlemelisiniz."

            self.c.execute("DELETE FROM tbl_stoklar WHERE id=?",(urun_id,))
            self.conn.commit()
            # DÜZELTME: Başarılı durumda da (True, mesaj) tuple'ı döndür.
            if self.c.rowcount > 0:
                return True, "Ürün başarıyla silindi."
            else:
                return False, "Ürün bulunamadı veya silinemedi."
        except Exception as e:
            self.conn.rollback()
            return False, f"Stok silme sırasında hata: {e}"

    def _fatura_hareketlerini_geri_al(self, fatura_ana_bilgileri, fatura_kalemleri_tuple_listesi):
        try:
            fatura_tipi = fatura_ana_bilgileri['tip']
            fatura_id = fatura_ana_bilgileri['id']
            odeme_turu = fatura_ana_bilgileri['odeme_turu']
            kasa_banka_id = fatura_ana_bilgileri['kasa_banka_id']
            toplam_kdv_dahil = fatura_ana_bilgileri['toplam_kdv_dahil']

            logging.info(f"_fatura_hareketlerini_geri_al çağrıldı. Fatura ID: {fatura_id}, Tip: {fatura_tipi}, Toplam KDV Dahil: {toplam_kdv_dahil}")

            # Stok hareketlerini geri al (bu kısım zaten doğru)
            for kalem in fatura_kalemleri_tuple_listesi:
                urun_id = kalem[0] # urun_id
                miktar = kalem[1]   # miktar

                miktar_degisimi = 0
                if fatura_tipi == self.FATURA_TIP_SATIS:
                    miktar_degisimi = miktar
                elif fatura_tipi == self.FATURA_TIP_ALIS:
                    miktar_degisimi = -miktar
                elif fatura_tipi == self.FATURA_TIP_SATIS_IADE:
                    miktar_degisimi = -miktar
                elif fatura_tipi == self.FATURA_TIP_ALIS_IADE:
                    miktar_degisimi = miktar

                self.c.execute("UPDATE tbl_stoklar SET stok_miktari = stok_miktari + ? WHERE id=?", (miktar_degisimi, urun_id))
                logging.info(f"Stok geri alındı: Ürün ID {urun_id}, Miktar Değişimi {miktar_degisimi}")


            # Kasa/Banka hareketlerini geri al
            if odeme_turu in self.pesin_odeme_turleri and kasa_banka_id:
                logging.info(f"Kasa/Banka hareketi geri alınıyor. Kasa/Banka ID: {kasa_banka_id}, Tutar: {toplam_kdv_dahil}, Fatura Tipi: {fatura_tipi}")
                if fatura_tipi == self.FATURA_TIP_SATIS:
                    self.kasa_banka_bakiye_guncelle(kasa_banka_id, toplam_kdv_dahil, artir=False)
                    logging.info(f"Kasa/Banka bakiyesi satış faturası geri alımı için azaltıldı: {toplam_kdv_dahil}")
                elif fatura_tipi == self.FATURA_TIP_ALIS:
                    self.kasa_banka_bakiye_guncelle(kasa_banka_id, toplam_kdv_dahil, artir=True)
                    logging.info(f"Kasa/Banka bakiyesi alış faturası geri alımı için artırıldı: {toplam_kdv_dahil}")
                elif fatura_tipi == self.FATURA_TIP_SATIS_IADE:
                    self.kasa_banka_bakiye_guncelle(kasa_banka_id, toplam_kdv_dahil, artir=True)
                    logging.info(f"Kasa/Banka bakiyesi satış iade faturası geri alımı için artırıldı: {toplam_kdv_dahil}")
                elif fatura_tipi == self.FATURA_TIP_ALIS_IADE:
                    self.kasa_banka_bakiye_guncelle(kasa_banka_id, toplam_kdv_dahil, artir=False)
                    logging.info(f"Kasa/Banka bakiyesi alış iade faturası geri alımı için azaltıldı: {toplam_kdv_dahil}")

            return True, "Hareketler başarıyla geri alındı."
        except Exception as e:
            logging.error(f"Fatura hareketlerini geri alma sırasında beklenmeyen hata: {e}\n{traceback.format_exc()}")
            return False, f"Fatura hareketleri geri alınırken beklenmeyen bir hata oluştu: {e}"

    def _fatura_hareketlerini_kaydet(self, fatura_ana_bilgileri, fatura_kalemleri_tuple_listesi):
        try:
            fatura_id = fatura_ana_bilgileri['id']
            fatura_tipi = fatura_ana_bilgileri['tip']
            odeme_turu = fatura_ana_bilgileri['odeme_turu']
            kasa_banka_id = fatura_ana_bilgileri['kasa_banka_id']
            toplam_kdv_dahil = fatura_ana_bilgileri['toplam_kdv_dahil']

            logging.info(f"_fatura_hareketlerini_kaydet çağrıldı. Fatura ID: {fatura_id}, Tip: {fatura_tipi}, Toplam KDV Dahil: {toplam_kdv_dahil}")

            # Stok hareketlerini kaydet (bu kısım zaten doğru)
            for kalem in fatura_kalemleri_tuple_listesi:
                urun_id = kalem[0] 
                miktar = kalem[1]   

                miktar_degisimi = 0
                if fatura_tipi == self.FATURA_TIP_SATIS: 
                    miktar_degisimi = -miktar
                elif fatura_tipi == self.FATURA_TIP_ALIS: 
                    miktar_degisimi = miktar
                elif fatura_tipi == self.FATURA_TIP_SATIS_IADE: 
                    miktar_degisimi = miktar
                elif fatura_tipi == self.FATURA_TIP_ALIS_IADE: 
                    miktar_degisimi = -miktar

                self.c.execute("UPDATE tbl_stoklar SET stok_miktari = stok_miktari + ? WHERE id=?", (miktar_degisimi, urun_id))
                logging.info(f"Stok kaydedildi: Ürün ID {urun_id}, Miktar Değişimi {miktar_degisimi}")


            # Kasa/Banka hareketlerini kaydet
            if odeme_turu in self.pesin_odeme_turleri and kasa_banka_id:
                logging.info(f"Kasa/Banka hareketi kaydediliyor. Kasa/Banka ID: {kasa_banka_id}, Tutar: {toplam_kdv_dahil}, Fatura Tipi: {fatura_tipi}")
                if fatura_tipi == self.FATURA_TIP_SATIS: 
                    self.kasa_banka_bakiye_guncelle(kasa_banka_id, toplam_kdv_dahil, artir=True)
                    logging.info(f"Kasa/Banka bakiyesi satış faturası için artırıldı: {toplam_kdv_dahil}")
                elif fatura_tipi == self.FATURA_TIP_ALIS: 
                    self.kasa_banka_bakiye_guncelle(kasa_banka_id, toplam_kdv_dahil, artir=False)
                    logging.info(f"Kasa/Banka bakiyesi alış faturası için azaltıldı: {toplam_kdv_dahil}")
                elif fatura_tipi == self.FATURA_TIP_SATIS_IADE: 
                    self.kasa_banka_bakiye_guncelle(kasa_banka_id, toplam_kdv_dahil, artir=False)
                    logging.info(f"Kasa/Banka bakiyesi satış iade faturası için azaltıldı: {toplam_kdv_dahil}")
                elif fatura_tipi == self.FATURA_TIP_ALIS_IADE: 
                    self.kasa_banka_bakiye_guncelle(kasa_banka_id, toplam_kdv_dahil, artir=True)
                    logging.info(f"Kasa/Banka bakiyesi alış iade faturası için artırıldı: {toplam_kdv_dahil}")

            return True, "Hareketler başarıyla kaydedildi."
        except Exception as e:
            logging.error(f"Fatura hareketlerini kaydetme sırasında beklenmeyen hata: {e}\n{traceback.format_exc()}")
            return False, f"Fatura hareketleri kaydedilirken beklenmeyen bir hata oluştu: {e}"

    def stok_getir_for_fatura(self, fatura_tipi='SATIŞ', arama_terimi=None): # <-- DÜZELTME: 'arama_termi' -> 'arama_terimi'
        print(f"DEBUG_DB: stok_getir_for_fatura çağrıldı. fatura_tipi: {fatura_tipi}, arama_terimi: {arama_terimi}")

        fiyat_kolonu = "satis_fiyati_kdv_dahil" if fatura_tipi == 'SATIŞ' else "alis_fiyati_kdv_dahil"

        query = f"SELECT id, urun_kodu, urun_adi, {fiyat_kolonu}, kdv_orani, stok_miktari FROM tbl_stoklar"

        params = []
        if arama_terimi:
            query += " WHERE (urun_kodu LIKE ? OR urun_adi LIKE ?)"
            term = f"%{arama_terimi}%"
            params.extend([term, term])
        query += " ORDER BY urun_adi ASC"

        logging.debug(f"Query: {query}")
        logging.debug(f"Params: {params}")

        self.c.execute(query, params)
        results = self.c.fetchall()

        logging.debug(f"Sorgu sonuçları (ilk 5 kayıt): {results[:5]}")
        # Her bir sonucun fiyat kolonundaki değerini de kontrol edelim
        for idx, row in enumerate(results):
            if idx < 5: # İlk 5 kaydı detaylı incele
                logging.debug(f"Row {idx}: id={row[0]}, kod={row[1]}, ad={row[2]}, fiyat={row[3]}, kdv={row[4]}, stok={row[5]}")

        return results

    def _format_currency(self, value):
        try:
            val_float = float(value)
            # Locale ayarları doğru yapıldıysa (yardimcilar.py'deki setup_locale),
            # bu formatlama otomatik olarak Türkçe formatı (virgül ondalık, nokta binlik) kullanır.
            return f"{val_float:,.2f} TL"
        except (ValueError, TypeError):
            return "0,00 TL"

    def _stok_guncelle_ve_hareket_kaydet(self, urun_id, miktar_degisimi_net, islem_tipi_aciklamasi, kaynak_tipi, kaynak_id, referans_no):
        """
        Belirli bir ürünün stok miktarını günceller ve ilgili stok hareketi kaydını oluşturur.
        Bu metodun çağrıldığı ana transaction içinde çalışır.
        
        Args:
            urun_id (int): Stok miktarı güncellenecek ürünün ID'si.
            miktar_degisimi_net (float): Stoğa eklenecek (+) veya çıkarılacak (-) net miktar.
            islem_tipi_aciklamasi (str): Stok hareketi tipi (örn: 'Fatura Satış', 'Manuel Giriş').
            kaynak_tipi (str): Stok hareketinin kaynağı (örn: 'FATURA', 'MANUEL', 'İADE_FATURA').
            kaynak_id (int, optional): Kaynak faturanın/siparişin/işlemin ID'si. None olabilir.
            referans_no (str, optional): Kaynak faturanın/siparişin/işlemin numarası/açıklaması.
        
        Returns:
            tuple: (bool success, str message)
        """
        print(f"DEBUG_STOK_GUNCELLE: _stok_guncelle_ve_hareket_kaydet BAŞLADI - Ürün ID: {urun_id}, Net Değişim: {miktar_degisimi_net}, İşlem Tipi: {islem_tipi_aciklamasi}")
        if miktar_degisimi_net == 0:
            print(f"DEBUG_STOK_GUNCELLE: Net değişim sıfır, stok güncellenmiyor.")
            return True, "Stok değişimi sıfır, işlem yapılmadı."

        # Ürünün mevcut stok miktarını al
        self.c.execute("SELECT stok_miktari, urun_adi FROM tbl_stoklar WHERE id=?", (urun_id,))
        urun_info = self.c.fetchone()
        if not urun_info:
            print(f"DEBUG_STOK_GUNCELLE: Ürün ID {urun_id} bulunamadı.")
            return False, "Ürün bulunamadı."

        stok_oncesi = urun_info['stok_miktari']
        urun_adi = urun_info['urun_adi']
        stok_sonrasi = stok_oncesi + miktar_degisimi_net

        print(f"DEBUG_STOK_GUNCELLE: Ürün: {urun_adi} (ID: {urun_id}) - Önceki Stok: {stok_oncesi}, Net Değişim: {miktar_degisimi_net}, Sonraki Stok Hesaplandı: {stok_sonrasi}")

        # tbl_stoklar tablosundaki stok miktarını güncelle
        self.c.execute("UPDATE tbl_stoklar SET stok_miktari = ? WHERE id=?", (stok_sonrasi, urun_id))

        aciklama_hareket_tam = f"{islem_tipi_aciklamasi} - Ürün: {urun_adi}. Referans No: {referans_no if referans_no else ''}"

        current_time = self.get_current_datetime_str()
        olusturan_id = self._get_current_user_id() # Güncel kullanıcı ID'sini alın
        print(f"DEBUG_STOK_GUNCELLE: Oluşturan Kullanıcı ID: {olusturan_id}")

        # Stok hareketi kaydını oluştur
        self.c.execute("""
            INSERT INTO stok_hareketleri
            (urun_id, tarih, islem_tipi, miktar, onceki_stok, sonraki_stok, aciklama, kaynak, kaynak_id, olusturma_tarihi_saat, olusturan_kullanici_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (urun_id, datetime.now().strftime('%Y-%m-%d'), islem_tipi_aciklamasi, abs(miktar_degisimi_net), stok_oncesi, stok_sonrasi, aciklama_hareket_tam, kaynak_tipi, kaynak_id, current_time, olusturan_id))

        print(f"DEBUG_STOK_GUNCELLE: _stok_guncelle_ve_hareket_kaydet BAŞARILI BİTTİ.")
        return True, "Stok hareketi başarıyla kaydedildi."
                        
    def stok_hareketleri_listele(self, urun_id, islem_tipi=None, baslangic_tarih=None, bitis_tarih=None):
        """
        Belirli bir ürünün stok hareketlerini listeler.
        İsteğe bağlı olarak işlem tipine, başlangıç ve bitiş tarihlerine göre filtreleme yapar.
        Dönüş: (id, urun_id, tarih, islem_tipi, miktar, onceki_stok, sonraki_stok, aciklama, kaynak)
        """
        query = """
            SELECT
                id, urun_id, tarih, islem_tipi, miktar, onceki_stok, sonraki_stok, aciklama, kaynak
            FROM stok_hareketleri
            WHERE urun_id = ?
        """
        params = [urun_id]
        conditions = []

        if islem_tipi and islem_tipi != "TÜMÜ":
            conditions.append("islem_tipi = ?")
            params.append(islem_tipi)

        if baslangic_tarih:
            conditions.append("tarih >= ?")
            params.append(baslangic_tarih)

        if bitis_tarih:
            conditions.append("tarih <= ?")
            params.append(bitis_tarih)

        if conditions:
            query += " AND " + " AND ".join(conditions)

        query += " ORDER BY tarih DESC, id DESC" # En yeni hareketler başta

        self.c.execute(query, params)
        return self.c.fetchall()

    def siparis_faturaya_donustur(self, siparis_id, olusturan_kullanici_id, odeme_turu_secilen, kasa_banka_id_secilen, vade_tarihi_secilen):
        """
        Belirtilen siparişi bir faturaya dönüştürür. Tüm mantık artık bu servistedir.
        """
        try:
            self.db.conn.execute("BEGIN TRANSACTION")
            siparis_ana = self.db.get_siparis_by_id(siparis_id)
            if not siparis_ana:
                return False, "Dönüştürülecek sipariş bulunamadı."
            
            if siparis_ana['fatura_id']:
                return False, f"Bu sipariş zaten bir faturaya dönüştürülmüş."
            if siparis_ana['durum'] == 'İPTAL EDİLDİ':
                return False, "İptal edilmiş bir sipariş faturaya dönüştürülemez."

            siparis_kalemleri = self.db.get_siparis_kalemleri(siparis_id)
            if not siparis_kalemleri:
                return False, "Sipariş kalemleri bulunamadı. Fatura oluşturulamıyor."

            fatura_tipi = 'SATIŞ' if siparis_ana['cari_tip'] == 'MUSTERI' else 'ALIŞ'
            fatura_no = self.db.son_fatura_no_getir(fatura_tipi)

            kalemler_for_fatura = []
            for sk in siparis_kalemleri:
                # fatura_olustur metodunun beklediği format:
                # (urun_id, miktar, birim_fiyat, kdv_orani, alis_fiyati, isk1, isk2, isk_tip, isk_deger)
                kalemler_for_fatura.append((
                    sk['urun_id'], sk['miktar'], sk['birim_fiyat'], sk['kdv_orani'], 
                    sk['alis_fiyati_siparis_aninda'], sk['iskonto_yuzde_1'], sk['iskonto_yuzde_2'], 
                    "YOK", 0.0
                ))

            success_fatura, message_fatura_id = self.fatura_olustur(
                fatura_no, fatura_tipi, siparis_ana['cari_id'], kalemler_for_fatura,
                odeme_turu=odeme_turu_secilen,
                kasa_banka_id=kasa_banka_id_secilen,
                fatura_notlari=f"Sipariş No: {siparis_ana['siparis_no']} ile oluşturulmuştur. {siparis_ana['siparis_notlari'] or ''}".strip(),
                vade_tarihi=vade_tarihi_secilen,
                genel_iskonto_tipi=siparis_ana['genel_iskonto_tipi'],
                genel_iskonto_degeri=siparis_ana['genel_iskonto_degeri'],
                manage_transaction=False
            )

            if success_fatura:
                yeni_fatura_id = message_fatura_id
                current_time = self.db.get_current_datetime_str()
                self.db.c.execute("UPDATE siparisler SET durum=?, fatura_id=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                                  ('TAMAMLANDI', yeni_fatura_id, current_time, olusturan_kullanici_id, siparis_id))
                self.db.conn.commit()
                return True, f"Sipariş '{siparis_ana['siparis_no']}' başarıyla '{fatura_no}' nolu faturaya dönüştürüldü."
            else:
                self.db.conn.rollback()
                return False, f"Sipariş faturaya dönüştürülürken hata oluştu: {message_fatura_id}"

        except Exception as e:
            if self.db.conn: self.db.conn.rollback()
            return False, f"Sipariş faturaya dönüştürülürken beklenmeyen bir hata oluştu: {e}\n{traceback.format_exc()}"
                                        
    def get_siparisler_by_cari(self, cari_tip, cari_id):
        """
        Belirli bir müşteriye veya tedarikçiye ait tüm siparişleri,
        ilişkili fatura ve kullanıcı bilgileriyle birlikte getirir.
        """
        try:
            query = """
                SELECT 
                    s.id, s.siparis_no, s.tarih, s.teslimat_tarihi,
                    s.toplam_tutar, s.durum, s.siparis_notlari,
                    f.fatura_no AS iliskili_fatura_no,
                    u.kullanici_adi AS olusturan_kullanici
                FROM siparisler s
                LEFT JOIN faturalar f ON s.fatura_id = f.id
                LEFT JOIN kullanicilar u ON s.olusturan_kullanici_id = u.id
                WHERE s.cari_tip = ? AND s.cari_id = ?
                ORDER BY s.tarih DESC, s.id DESC
            """
            self.c.execute(query, (cari_tip, cari_id))
            return self.c.fetchall()
        except Exception as e:
            logging.error(f"get_siparisler_by_cari hatası: {e}\n{traceback.format_exc()}")
            return []
                
    def _get_or_create_id(self, table_name, name_column, name_value, manage_transaction=True): # manage_transaction parametresi eklendi
        if name_value is None or str(name_value).strip() == '':
            return None

        try:
            self.c.execute(f"SELECT id FROM {table_name} WHERE {name_column}=?", (name_value,))
            result = self.c.fetchone()
            if result:
                return result[0]
            else:
                if manage_transaction: # Sadece kendi transaction'ını yönetecekse başlat
                    self.conn.execute("BEGIN TRANSACTION")

                current_time = self.get_current_datetime_str()
                olusturan_id = self.app.current_user[0] if self.app and self.app.current_user else None 
                self.c.execute(f"INSERT INTO {table_name} ({name_column}, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?)",
                               (name_value, current_time, olusturan_id))
                new_id = self.c.lastrowid

                if manage_transaction: # Sadece kendi transaction'ını yönetecekse commit yap
                    self.conn.commit() 
                return new_id
        except sqlite3.IntegrityError as e: # Hata objesini yakala
            if manage_transaction: self.conn.rollback() 
            # Yeniden sorgula. Eğer bu bir UNIQUE hatasıysa, kayıt zaten eklenmiş demektir.
            self.c.execute(f"SELECT id FROM {table_name} WHERE {name_column}=?", (name_value,))
            result = self.c.fetchone()
            if result:
                return result[0]
            else:
                # Bu durum, IntegrityError'ın farklı bir tipi (FK ihlali vb.) veya yarış durumu olabilir.
                # Ya da kayıt eklenirken aynı anda başka bir işlem tarafından eklendiği için
                # tekrar SELECT yapıldığında bulunamaması durumu.
                print(f"KRİTİK HATA (IntegrityError): '{table_name}' tablosunda '{name_value}' için benzersizlik/bütünlük hatası: {e}. Kayıt tekrar bulunamadı.")
                return None
        except Exception as e:
            if manage_transaction: self.conn.rollback() 
            print(f"UYARI: '{table_name}' tablosunda '{name_value}' için ID bulunamadı veya oluşturulamadı: {e}\n{traceback.format_exc()}") # traceback ekle
            return None
            
    def fatura_listele_urun_ad_dahil(self, tip=None, baslangic_tarih=None, bitis_tarih=None, arama_terimi=None, cari_id_filter=None, odeme_turu_filter=None, kasa_banka_id_filter=None, limit=None, offset=None):
        
        # Bu metod, iade faturalarını da içerecek şekilde güncellendi.
        # Sorgu, farklı tablolardan (musteriler, tedarikciler, kullanicilar vb.) veri almak için JOIN'ler kullanır.
        
        perakende_id_param = self.perakende_musteri_id if self.perakende_musteri_id is not None else -999

        q = """SELECT f.id, f.fatura_no, f.tarih, f.tip,
                       CASE
                           WHEN f.cari_id = ? AND f.tip = 'SATIŞ' THEN IFNULL(f.misafir_adi, 'Perakende Satış')
                           WHEN f.tip IN ('SATIŞ', 'SATIŞ İADE') THEN mus.ad
                           WHEN f.tip IN ('ALIŞ', 'ALIŞ İADE', 'DEVİR_GİRİŞ') THEN ted.ad
                           ELSE 'Bilinmeyen Cari'
                       END AS cari_adi,
                       f.toplam_kdv_dahil, 
                       f.odeme_turu,
                       kb.hesap_adi AS kasa_banka_adi,
                       f.vade_tarihi,
                       f.genel_iskonto_degeri,
                       olusturan.kullanici_adi AS olusturan_kul_adi,
                       guncelleyen.kullanici_adi AS guncelleyen_kul_adi
               FROM faturalar f
               LEFT JOIN musteriler mus ON f.cari_id = mus.id
               LEFT JOIN tedarikciler ted ON f.cari_id = ted.id
               LEFT JOIN kasalar_bankalar kb ON f.kasa_banka_id = kb.id
               LEFT JOIN kullanicilar olusturan ON f.olusturan_kullanici_id = olusturan.id
               LEFT JOIN kullanicilar guncelleyen ON f.son_guncelleyen_kullanici_id = guncelleyen.id
               """
        p = [perakende_id_param] 
        conditions = []

        if tip:
            if isinstance(tip, list):
                placeholders = ','.join(['?'] * len(tip))
                conditions.append(f"f.tip IN ({placeholders})")
                p.extend(tip)
            elif tip != "TÜMÜ":
                conditions.append("f.tip=?")
                p.append(tip)

        if baslangic_tarih:
            conditions.append("f.tarih>=?")
            p.append(baslangic_tarih)
        if bitis_tarih:
            conditions.append("f.tarih<=?")
            p.append(bitis_tarih)

        if cari_id_filter is not None:
            conditions.append("f.cari_id = ?")
            p.append(int(cari_id_filter))

        if odeme_turu_filter is not None and odeme_turu_filter != "TÜMÜ":
            conditions.append("f.odeme_turu = ?")
            p.append(odeme_turu_filter)

        if kasa_banka_id_filter is not None:
            conditions.append("f.kasa_banka_id = ?")
            p.append(kasa_banka_id_filter)

        if arama_terimi:
            term = f"%{normalize_turkish_chars(arama_terimi)}%"
            # Arama sorgusunu daha basit ve okunabilir hale getirelim
            # NOT: Bu arama performansı büyük veritabanlarında yavaş olabilir.
            # Daha iyi performans için FTS5 gibi SQLite eklentileri gerekir.
            search_conditions = [
                "f.fatura_no LIKE ?",
                "f.misafir_adi LIKE ?",
                "mus.ad LIKE ?",
                "ted.ad LIKE ?",
                "kb.hesap_adi LIKE ?",
                """EXISTS (
                    SELECT 1 FROM fatura_kalemleri fk 
                    JOIN tbl_stoklar s ON fk.urun_id = s.id 
                    WHERE fk.fatura_id = f.id AND (s.urun_adi LIKE ? OR s.urun_kodu LIKE ?)
                )"""
            ]
            conditions.append(f"({' OR '.join(search_conditions)})")
            # Her bir LIKE için parametre ekle
            p.extend([term, term, term, term, term, term, term])

        if conditions:
            q += " WHERE " + " AND ".join(conditions)

        q += " ORDER BY f.tarih DESC, f.id DESC"

        if limit is not None:
            q += " LIMIT ?"
            p.append(limit)
        if offset is not None:
            q += " OFFSET ?"
            p.append(offset)
        
        self.c.execute(q, p)
        return self.c.fetchall()

    def get_fatura_count(self, tip=None, baslangic_tarih=None, bitis_tarih=None, arama_terimi=None, cari_id_filter=None, odeme_turu_filter=None, kasa_banka_id_filter=None):
        perakende_id_param = self.perakende_musteri_id if self.perakende_musteri_id is not None else -999

        q = """SELECT COUNT(DISTINCT f.id)
               FROM faturalar f
               LEFT JOIN musteriler mus ON f.cari_id = mus.id
               LEFT JOIN tedarikciler ted ON f.cari_id = ted.id
               LEFT JOIN kasalar_bankalar kb ON f.kasa_banka_id = kb.id
               LEFT JOIN fatura_kalemleri fk ON f.id = fk.fatura_id
               LEFT JOIN tbl_stoklar s ON fk.urun_id = s.id
               """

        p = []
        conditions = []

        conditions.append("""
            (
                (f.tip = 'SATIŞ' AND f.cari_id = ? AND IFNULL(f.misafir_adi, '') IS NOT NULL) OR 
                (f.tip = 'SATIŞ' AND f.cari_id != ?) OR 
                (f.tip = 'ALIŞ') OR
                (f.tip = 'SATIŞ İADE') OR 
                (f.tip = 'ALIŞ İADE')
            )
        """)
        p.append(perakende_id_param)
        p.append(perakende_id_param)
        
        # Düzeltme burada: tip parametresi artık bir liste veya string olabilir.
        if tip:
            if isinstance(tip, list): # Eğer tip bir liste ise
                placeholders = ','.join(['?'] * len(tip))
                conditions.append(f"f.tip IN ({placeholders})")
                p.extend(tip)
            elif tip != "TÜMÜ": # Tek bir string ise ve "TÜMÜ" değilse
                conditions.append("f.tip=?")
                p.append(tip)

        if baslangic_tarih:
            conditions.append("f.tarih>=?")
            p.append(baslangic_tarih)
        if bitis_tarih:
            conditions.append("f.tarih<=?")
            p.append(bitis_tarih)

        if cari_id_filter is not None:
            conditions.append("f.cari_id = ?")
            p.append(int(cari_id_filter))

        if odeme_turu_filter is not None:
            conditions.append("f.odeme_turu = ?")
            p.append(odeme_turu_filter)

        if kasa_banka_id_filter is not None:
            conditions.append("f.kasa_banka_id = ?")
            p.append(kasa_banka_id_filter)

        if arama_terimi:
            term = f"%{normalize_turkish_chars(arama_terimi)}%"
            conditions.append("""(
                                f.fatura_no LIKE ? OR
                                (f.tip IN ('SATIŞ', 'SATIŞ İADE') AND IFNULL(f.misafir_adi, 'Perakende Satış') LIKE ?) OR
                                (f.tip IN ('SATIŞ', 'SATIŞ İADE') AND REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(mus.ad), 'ş', 's'), 'ı', 'i'), 'ç', 'c'), 'ğ', 'g'), 'ö', 'o'), 'ü', 'u') LIKE ?) OR
                                (f.tip IN ('ALIŞ', 'ALIŞ İADE') AND REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(ted.ad), 'ş', 's'), 'ı', 'i'), 'ç', 'c'), 'ğ', 'g'), 'ö', 'o'), 'ü', 'u') LIKE ?) OR
                                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(kb.hesap_adi), 'ş', 's'), 'ı', 'i'), 'ç', 'c'), 'ğ', 'g'), 'ö', 'o'), 'ü', 'u') LIKE ? OR
                                EXISTS (SELECT 1 FROM fatura_kalemleri fk JOIN tbl_stoklar s ON fk.urun_id = s.id WHERE fk.fatura_id = f.id AND (REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(s.urun_adi), 'ş', 's'), 'ı', 'i'), 'ç', 'c'), 'ğ', 'g'), 'ö', 'o'), 'ü', 'u') LIKE ? OR REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(s.urun_kodu), 'ş', 's'), 'ı', 'i'), 'ç', 'c'), 'ğ', 'g'), 'ö', 'o'), 'ü', 'u') LIKE ?))
                              )""")
            p.extend([term, term, term, term, term, term, term])

        if conditions:
            q += " WHERE " + " AND ".join(conditions)

        print(f"DEBUG SQL Query (get_fatura_count): {q}")
        print(f"DEBUG SQL Params (get_fatura_count): {p}")

        self.c.execute(q, p)
        return self.c.fetchone()[0]
            
    def fatura_getir_by_id(self, fatura_id):
        self.c.execute("SELECT id,fatura_no,tarih,tip,cari_id,toplam_kdv_haric,toplam_kdv_dahil,odeme_turu,misafir_adi,kasa_banka_id,olusturma_tarihi_saat,olusturan_kullanici_id,son_guncelleme_tarihi_saat,son_guncelleyen_kullanici_id, fatura_notlari, vade_tarihi, genel_iskonto_tipi, genel_iskonto_degeri, orijinal_fatura_id FROM faturalar WHERE id=?", (fatura_id,))
        return self.c.fetchone()
    
    def fatura_detay_al(self, fatura_id):
        self.c.execute("SELECT s.urun_kodu, s.urun_adi, fk.miktar, fk.birim_fiyat, fk.kdv_orani, fk.kdv_tutari, fk.kalem_toplam_kdv_haric, fk.kalem_toplam_kdv_dahil, s.id as urun_id, fk.alis_fiyati_fatura_aninda, fk.kdv_orani_fatura_aninda, fk.iskonto_yuzde_1, fk.iskonto_yuzde_2, fk.iskonto_tipi, fk.iskonto_degeri FROM fatura_kalemleri fk JOIN tbl_stoklar s ON fk.urun_id=s.id WHERE fk.fatura_id=?",(fatura_id,))
        return self.c.fetchall()

    def gelir_siniflandirma_ekle(self, siniflandirma_adi):
        if not siniflandirma_adi:
            return False, "Gelir sınıflandırma adı boş olamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            olusturan_id = self._get_current_user_id() # Değişiklik
            self.c.execute("INSERT INTO gelir_siniflandirmalari (siniflandirma_adi, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?)",
                           (siniflandirma_adi, current_time, olusturan_id))
            self.conn.commit()
            return True, f"'{siniflandirma_adi}' gelir sınıflandırması başarıyla eklendi."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu gelir sınıflandırma adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Gelir sınıflandırma eklenirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Gelir sınıflandırma eklenirken beklenmeyen hata: {e}"

    def gelir_siniflandirma_listele(self):
        self.c.execute("SELECT id, siniflandirma_adi FROM gelir_siniflandirmalari ORDER BY siniflandirma_adi ASC")
        return self.c.fetchall()

    def gelir_siniflandirma_guncelle(self, siniflandirma_id, yeni_siniflandirma_adi):
        if not yeni_siniflandirma_adi:
            return False, "Gelir sınıflandırma adı boş olamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            guncelleyen_id = self.app.current_user[0] if self.app and self.app.current_user else None
            self.c.execute("UPDATE gelir_siniflandirmalari SET siniflandirma_adi=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                           (yeni_siniflandirma_adi, current_time, guncelleyen_id, siniflandirma_id))
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, "Gelir sınıflandırması başarıyla güncellendi."
            else:
                return False, "Gelir sınıflandırması bulunamadı veya bir değişiklik yapılmadı."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu gelir sınıflandırma adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Gelir sınıflandırma güncellenirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Gelir sınıflandırma güncellenirken beklenmeyen hata: {e}"

    def gelir_siniflandirma_sil(self, siniflandirma_id):
        try:
            self.conn.execute("BEGIN TRANSACTION")
            # Bu sınıflandırmaya bağlı gelir kaydı var mı kontrol et
            self.c.execute("SELECT COUNT(*) FROM gelir_gider WHERE gelir_siniflandirma_id=?", (siniflandirma_id,))
            if self.c.fetchone()[0] > 0:
                self.conn.rollback()
                return False, "Bu gelir sınıflandırmasına bağlı gelir kayıtları bulunmaktadır. Lütfen önce kayıtları güncelleyin veya silin."
            self.c.execute("DELETE FROM gelir_siniflandirmalari WHERE id=?", (siniflandirma_id,))
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, "Gelir sınıflandırması başarıyla silindi."
            else:
                return False, "Gelir sınıflandırması bulunamadı veya silinemedi."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Gelir sınıflandırma silinirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Gelir sınıflandırma silinirken beklenmeyen hata: {e}"

    # --- Gider Sınıflandırma Yönetimi Metotları ---
    def gider_siniflandirma_ekle(self, siniflandirma_adi):
        if not siniflandirma_adi:
            return False, "Gider sınıflandırma adı boş olamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            olusturan_id = self._get_current_user_id() # Değişiklik
            self.c.execute("INSERT INTO gider_siniflandirmalari (siniflandirma_adi, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?)",
                           (siniflandirma_adi, current_time, olusturan_id))
            self.conn.commit()
            return True, f"'{siniflandirma_adi}' gider sınıflandırması başarıyla eklendi."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu gider sınıflandırma adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Gider sınıflandırma eklenirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Gider sınıflandırma eklenirken beklenmeyen hata: {e}"

    def gider_siniflandirma_listele(self):
        self.c.execute("SELECT id, siniflandirma_adi FROM gider_siniflandirmalari ORDER BY siniflandirma_adi ASC")
        return self.c.fetchall()

    def gider_siniflandirma_guncelle(self, siniflandirma_id, yeni_siniflandirma_adi):
        if not yeni_siniflandirma_adi:
            return False, "Gider sınıflandırma adı boş olamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            guncelleyen_id = self.app.current_user[0] if self.app and self.app.current_user else None
            self.c.execute("UPDATE gider_siniflandirmalari SET siniflandirma_adi=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                           (yeni_siniflandirma_adi, current_time, guncelleyen_id, siniflandirma_id))
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, "Gider sınıflandırması başarıyla güncellendi."
            else:
                return False, "Gider sınıflandırması bulunamadı veya bir değişiklik yapılmadı."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu gider sınıflandırma adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Gider sınıflandırma güncellenirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Gider sınıflandırma güncellenirken beklenmeyen hata: {e}"

    def gider_siniflandirma_sil(self, siniflandirma_id):
        try:
            self.conn.execute("BEGIN TRANSACTION")
            # Bu sınıflandırmaya bağlı gider kaydı var mı kontrol et
            self.c.execute("SELECT COUNT(*) FROM gelir_gider WHERE gider_siniflandirma_id=?", (siniflandirma_id,))
            if self.c.fetchone()[0] > 0:
                self.conn.rollback()
                return False, "Bu gider sınıflandırmasına bağlı gider kayıtları bulunmaktadır. Lütfen önce kayıtları güncelleyin veya silin."
            self.c.execute("DELETE FROM gider_siniflandirmalari WHERE id=?", (siniflandirma_id,))
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, "Gider sınıflandırması başarıyla silindi."
            else:
                return False, "Gider sınıflandırması bulunamadı veya silinemedi."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Gider sınıflandırma silinirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Gider sınıflandırma silinirken beklenmeyen hata: {e}"

    # --- Yardımcı Metot: Sınıflandırma ID'sini ada göre getir (combobox'lar için) ---
    def get_gelir_siniflandirmalari_for_combobox(self):
        self.c.execute("SELECT id, siniflandirma_adi FROM gelir_siniflandirmalari ORDER BY siniflandirma_adi ASC")
        return {row['siniflandirma_adi']: row['id'] for row in self.c.fetchall()}

    def get_gider_siniflandirmalari_for_combobox(self):
        self.c.execute("SELECT id, siniflandirma_adi FROM gider_siniflandirmalari ORDER BY siniflandirma_adi ASC")
        return {row['siniflandirma_adi']: row['id'] for row in self.c.fetchall()}

    def gelir_gider_ekle(self, tarih, tip, tutar, aciklama, kasa_banka_id=None, gelir_siniflandirma_id=None, gider_siniflandirma_id=None):
        if not (tarih and tip and aciklama):
            return False, "Tarih, Tip ve Açıklama alanları zorunludur."
        
        tutar_f = 0.0
        try:
            tutar_f = float(str(tutar).replace(',','.'))
            if tutar_f <= 0:
                return False, "Tutar pozitif bir sayı olmalıdır."
            datetime.strptime(tarih, '%Y-%m-%d') # Tarih formatını doğrula
        except ValueError:
            return False, "Tutar sayısal ve geçerli bir değer olmalı.\nTarih formatı (YYYY-AA-GG) şeklinde olmalıdır (örn: 2024-12-31)."
        
        try:
            self.conn.execute("BEGIN TRANSACTION") # Transaction başlatıldı
            current_time = self.get_current_datetime_str()
            olusturan_id = self.app.current_user[0] if self.app and self.app.current_user else None
            
            # Düzeltilen kısım: 'kaynak' için '?' ve parametre listesine 'MANUEL' eklendi.
            self.c.execute("INSERT INTO gelir_gider (tarih, tip, tutar, aciklama, kaynak, kasa_banka_id, gelir_siniflandirma_id, gider_siniflandirma_id, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (tarih, tip, tutar_f, aciklama, 'MANUEL', kasa_banka_id, gelir_siniflandirma_id, gider_siniflandirma_id, current_time, olusturan_id))
            
            gg_id = self.c.lastrowid
            
            if kasa_banka_id: # Kasa/Banka seçiliyse bakiyeyi güncelle
                is_bakiye_artir_gg = True if tip == 'GELİR' else False
                if not self.kasa_banka_bakiye_guncelle(kasa_banka_id, tutar_f, artir=is_bakiye_artir_gg):
                    self.conn.rollback() # Bakiye güncellenemezse rollback
                    return False, f"Manuel gelir/gider eklenirken bir hata oluştu: {e}\n\nDetaylar:\n{traceback.format_exc()}" # traceback eklendi

            self.conn.commit() # Tüm işlemler başarılıysa commit et
            return True, f"Manuel {tip.lower()} kaydı başarıyla eklendi." # Mesaj eklendi
        except Exception as e:
            self.conn.rollback() # Hata durumunda rollback
            error_details = traceback.format_exc()
            return False, f"Manuel gelir/gider eklenirken bir hata oluştu: {e}\n\nDetaylar:\n{error_details}"

    def gelir_gider_listele(self, baslangic_tarih=None, bitis_tarih=None, tip_filtre=None, aciklama_filtre=None, limit=None, offset=None): 
        q="SELECT gg.id, gg.tarih, gg.tip, gg.tutar, gg.aciklama, gg.kaynak, gg.kaynak_id, kb.hesap_adi as kasa_banka_adi FROM gelir_gider gg LEFT JOIN kasalar_bankalar kb ON gg.kasa_banka_id = kb.id"
        p=[]; cond=[]
        if baslangic_tarih: cond.append("gg.tarih>=?"); p.append(baslangic_tarih)
        if bitis_tarih: cond.append("gg.tarih<=?"); p.append(bitis_tarih)
        if tip_filtre and tip_filtre!="TÜMÜ": cond.append("gg.tip=?"); p.append(tip_filtre)
        if aciklama_filtre: cond.append("(gg.aciklama LIKE ? OR kb.hesap_adi LIKE ?)"); p.extend([f"%{aciklama_filtre}%", f"%{aciklama_filtre}%"])
        if cond: q+=" WHERE "+" AND ".join(cond)
        q+=" ORDER BY gg.tarih DESC,gg.id DESC"
        
        # Sayfalama için LIMIT ve OFFSET ekle
        if limit is not None:
            q += " LIMIT ?"
            p.append(limit)
        if offset is not None:
            q += " OFFSET ?"
            p.append(offset)
        
        self.c.execute(q,p)
        return self.c.fetchall()
    
    def get_gelir_gider_count(self, baslangic_tarih=None, bitis_tarih=None, tip_filtre=None, aciklama_filtre=None):
        q = "SELECT COUNT(gg.id) FROM gelir_gider gg LEFT JOIN kasalar_bankalar kb ON gg.kasa_banka_id = kb.id"
        p = []; cond = []
        if baslangic_tarih: cond.append("gg.tarih>=?"); p.append(baslangic_tarih)
        if bitis_tarih: cond.append("gg.tarih<=?"); p.append(bitis_tarih)
        if tip_filtre and tip_filtre != "TÜMÜ": cond.append("gg.tip=?"); p.append(tip_filtre)
        if aciklama_filtre: cond.append("(gg.aciklama LIKE ? OR kb.hesap_adi LIKE ?)"); p.extend([f"%{aciklama_filtre}%", f"%{aciklama_filtre}%"])
        if cond: q += " WHERE " + " AND ".join(cond)
        self.c.execute(q, p)
        return self.c.fetchone()[0]  

    def gelir_gider_sil(self, gg_id):
        try:
            self.conn.execute("BEGIN TRANSACTION")
            # Sadece manuel eklenenler silinebilir
            self.c.execute("SELECT kaynak, tutar, tip, kasa_banka_id FROM gelir_gider WHERE id=?",(gg_id,))
            kaynak_bilgisi = self.c.fetchone()
            if not kaynak_bilgisi:
                self.conn.rollback()
                return False, "Silinecek gelir/gider kaydı bulunamadı."
            kaynak, tutar_gg, tip_gg, kasa_banka_id_gg = kaynak_bilgisi
            if kaynak !='MANUEL':
                self.conn.rollback()
                return False, "Sadece manuel olarak eklenmiş gelir/gider kayıtları silinebilir.\nOtomatik oluşan kayıtlar (Fatura, Tahsilat, Ödeme vb.) ilgili modüllerden yönetilmelidir."

            if kasa_banka_id_gg: # Kasa/Banka seçiliyse bakiyeyi düzelt
                is_ters_bakiye_artir_gg = False # Varsayılan: azalt
                if tip_gg == 'GELİR':
                    is_ters_bakiye_artir_gg = False # Gelir silinirse kasa bakiyesi azalır (artır=False)
                elif tip_gg == 'GİDER':
                    is_ters_bakiye_artir_gg = True # Gider silinirse kasa bakiyesi artar (artır=True)

                if not self.kasa_banka_bakiye_guncelle(kasa_banka_id_gg, tutar_gg, artir=is_ters_bakiye_artir_gg):
                    self.conn.rollback()
                    return False, "Manuel gelir/gider silinirken kasa/banka bakiyesi düzeltilemedi."
            
            self.c.execute("DELETE FROM gelir_gider WHERE id=?",(gg_id,))
            self.conn.commit()
            # DÜZELTME BAŞLANGICI: Başarı durumu ve mesaj döndürüyoruz
            if self.c.rowcount > 0:
                return True, "Gelir/Gider kaydı başarıyla silindi."
            else:
                return False, "Gelir/Gider kaydı bulunamadı veya silinemedi."
            
        except Exception as e:
            self.conn.rollback()
            return False, f"Gelir/Gider silme hatası: {e}"

    def tahsilat_ekle(self, musteri_id, tarih, tutar, odeme_sekli, aciklama, kasa_banka_id=None):
        if str(musteri_id) == str(self.perakende_musteri_id):
            return False, "Perakende müşterisinden manuel tahsilat yapılamaz.\nPerakende satışlar zaten peşin kabul edilir."
        if not (musteri_id and tarih and odeme_sekli and aciklama and kasa_banka_id): 
            return False, "Müşteri, Tarih, Ödeme Şekli, Açıklama ve İşlem Kasa/Banka zorunludur."
        try:
            tutar_f = float(str(tutar).replace(",","."))
            if tutar_f <= 0:
                return False, "Tutar pozitif bir sayı olmalıdır."
            datetime.strptime(tarih, '%Y-%m-%d')
        except ValueError:
            return False, "Tutar sayısal olmalı, Tarih (%Y-%m-%d) formatında olmalıdır."
    
        try:
            self.conn.execute("BEGIN TRANSACTION")
            musteri_bilgi = self.musteri_getir_by_id(musteri_id)
            musteri_adi = musteri_bilgi[2] if musteri_bilgi else f"ID: {musteri_id}"

            ch_aciklama = f"Tahsilat: {aciklama} (Ödeme: {odeme_sekli}) - Müşteri: {musteri_adi}"
            current_time = self.get_current_datetime_str()
            olusturan_id = self.app.current_user[0] if self.app and self.app.current_user else None
            self.c.execute("INSERT INTO cari_hareketler (tarih, cari_tip, cari_id, islem_tipi, tutar, aciklama, referans_tip, kasa_banka_id,olusturma_tarihi_saat,olusturan_kullanici_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (tarih, 'MUSTERI', musteri_id, 'TAHSILAT', tutar_f, ch_aciklama, "TAHSILAT", kasa_banka_id, current_time, olusturan_id))
            tahsilat_ref_id = self.c.lastrowid

            gelir_aciklama = f"Müşteri Tahsilatı: {musteri_adi} - {aciklama} (Ödeme: {odeme_sekli})"
            current_time_gg = self.get_current_datetime_str()
            olusturan_id_gg = self.app.current_user[0] if self.app and self.app.current_user else None
            self.c.execute("INSERT INTO gelir_gider (tarih, tip, tutar, aciklama, kaynak, kaynak_id, kasa_banka_id,olusturma_tarihi_saat,olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?)",
                           (tarih, 'GELİR', tutar_f, gelir_aciklama, 'TAHSILAT', tahsilat_ref_id, kasa_banka_id, current_time_gg, olusturan_id_gg))            

            if not self.kasa_banka_bakiye_guncelle(kasa_banka_id, tutar_f, artir=True):
                self.conn.rollback()
                return False, "Tahsilat kaydedilirken kasa/banka bakiyesi güncellenemedi."
        
            self.conn.commit()
            # DÜZELTME BURADA: Başarılı durumda (True, "mesaj") formatında dönüyoruz.
            return True, f"Tahsilat (ID: {tahsilat_ref_id}) başarıyla kaydedildi."
        except Exception as e:
            self.conn.rollback()
            return False, f"Tahsilat eklenirken hata: {e}\n{traceback.format_exc()}"

    def odeme_ekle(self, tedarikci_id, tarih, tutar, odeme_sekli, aciklama, kasa_banka_id):
        if not (tedarikci_id and tarih and odeme_sekli and aciklama and kasa_banka_id):
            return False, "Tedarikçi, Tarih, Ödeme Şekli, Açıklama ve İşlem Kasa/Banka zorunludur."
        try:
            tutar_f = float(str(tutar).replace(",", "."))
            if tutar_f <= 0:
                return False, "Tutar pozitif bir sayı olmalıdır."
            datetime.strptime(tarih, '%Y-%m-%d')
        except ValueError:
            return False, "Tutar sayısal olmalı, Tarih (YYYY-AA-GG) formatında olmalıdır."

        try:
            self.conn.execute("BEGIN TRANSACTION")
            tedarikci_bilgi = self.tedarikci_getir_by_id(tedarikci_id)
            tedarikci_adi = tedarikci_bilgi[2] if tedarikci_bilgi else f"ID: {tedarikci_id}"

            ch_aciklama = f"Ödeme: {aciklama} (Ödeme: {odeme_sekli}) - Tedarikçi: {tedarikci_adi}"
            current_time = self.get_current_datetime_str()
            olusturan_id = self.app.current_user[0] if self.app and self.app.current_user else None
            
            self.c.execute("INSERT INTO cari_hareketler (tarih, cari_tip, cari_id, islem_tipi, tutar, aciklama, referans_id, referans_tip, kasa_banka_id, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (tarih, 'TEDARIKCI', tedarikci_id, 'ODEME', tutar_f, ch_aciklama, None, "ODEME", kasa_banka_id, current_time, olusturan_id))
            odeme_ref_id = self.c.lastrowid

            gider_aciklama = f"Tedarikçi Ödemesi: {tedarikci_adi} - {aciklama} (Ödeme: {odeme_sekli})"
            current_time_gg = self.get_current_datetime_str()
            olusturan_id_gg = self.app.current_user[0] if self.app and self.app.current_user else None
            self.c.execute("INSERT INTO gelir_gider (tarih, tip, tutar, aciklama, kaynak, kaynak_id, kasa_banka_id,olusturma_tarihi_saat,olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?)",
                           (tarih, 'GİDER', tutar_f, gider_aciklama, 'ODEME', odeme_ref_id, kasa_banka_id, current_time_gg, olusturan_id_gg))

            if not self.kasa_banka_bakiye_guncelle(kasa_banka_id, tutar_f, artir=False):
                self.conn.rollback()
                return False, "Ödeme kaydedilirken kasa/banka bakiyesi güncellenemedi."

            self.conn.commit()
            # DÜZELTME BURADA: Başarılı durumda (True, "mesaj") formatında dönüyoruz.
            return True, f"Ödeme (ID: {odeme_ref_id}) başarıyla kaydedildi."
        except Exception as e:
            self.conn.rollback()
            return False, f"Ödeme eklenirken hata: {e}\n{traceback.format_exc()}"

    def tahsilat_odeme_sil(self, cari_hareket_id):
        referans_tipi = "" 
        try:
            self.conn.execute("BEGIN TRANSACTION") # Transaction başlatıldı
            # Silinecek cari hareketin detaylarını al
            self.c.execute("SELECT referans_tip, referans_id, tutar, kasa_banka_id, cari_tip FROM cari_hareketler WHERE id=?", (cari_hareket_id,))
            hareket_bilgisi = self.c.fetchone()
            if not hareket_bilgisi:
                self.conn.rollback() # Kayıt bulunamazsa rollback
                return False, "Silinecek kayıt bulunamadı."
            
            referans_tipi, referans_id, tutar_silinecek_ch, kasa_banka_id_ch, cari_tip_ch = hareket_bilgisi
    
            # Sadece nakit akışı yaratan işlemler için kasa/banka bakiyesini düzelt
            if referans_tipi in ['TAHSILAT', 'ODEME', 'FATURA_SATIS_PESIN', 'FATURA_ALIS_PESIN'] and kasa_banka_id_ch is not None:
                is_ters_bakiye_artir_ch = False # Varsayılan: azalt
                if referans_tipi == 'TAHSILAT' or referans_tipi == 'FATURA_SATIS_PESIN':
                    # Tahsilat silinirse (kasaya para girmişti) kasadan para AZALMALI (artir=False)
                    is_ters_bakiye_artir_ch = False 
                elif referans_tipi == 'ODEME' or referans_tipi == 'FATURA_ALIS_PESIN':
                    # Ödeme silinirse (kasadan para çıkmıştı) kasaya para ARTMALI (artir=True)
                    is_ters_bakiye_artir_ch = True 
        
                if not self.kasa_banka_bakiye_guncelle(kasa_banka_id_ch, tutar_silinecek_ch, artir=is_ters_bakiye_artir_ch):
                    self.conn.rollback() # Bakiye düzeltme başarısız olursa rollback
                    return False, "İşlem silinirken bakiye düzeltilemedi."

            # Eğer bu hareket peşin bir faturadan otomatik oluşmuşsa (FATURA_SATIS_PESIN veya FATURA_ALIS_PESIN)
            # Hem cari hareketi hem de ilişkili gelir/gider kaydını sil. Faturayı "AÇIK HESAP" durumuna getir.
            if referans_tipi in ['FATURA_SATIS_PESIN', 'FATURA_ALIS_PESIN']:
                if referans_id: # Fatura ID'si varsa
                    self.c.execute("UPDATE faturalar SET odeme_turu = 'AÇIK HESAP', kasa_banka_id = NULL WHERE id = ?", (referans_id,))
                self.c.execute("DELETE FROM cari_hareketler WHERE id=?", (cari_hareket_id,))
                # İlişkili gelir/gider kaydını sil (FATURA_SATIS_PESIN ve FATURA_ALIS_PESIN'den gelen gelir/giderler)
                self.c.execute("DELETE FROM gelir_gider WHERE kaynak='FATURA' AND kaynak_id = ?", (referans_id,)) 
    
            # Eğer bu hareket manuel bir tahsilat veya ödeme ise (TAHSILAT veya ODEME)
            # Hem cari hareketi hem de ilişkili gelir/gider kaydını sil
            elif referans_tipi in ['TAHSILAT', 'ODEME']:
                self.c.execute("DELETE FROM gelir_gider WHERE kaynak=? AND kaynak_id=? AND kasa_banka_id=?", (referans_tipi, cari_hareket_id, kasa_banka_id_ch))
                self.c.execute("DELETE FROM cari_hareketler WHERE id=?", (cari_hareket_id,))
            elif referans_tipi == 'VERESIYE_BORC_MANUEL': # Manuel veresiye borç silme
                # Bu sadece cari hareketler tablosunda bir kayıttır, gelir_gider tablosunda karşılığı yoktur
                # ve kasa/banka bakiyesi üzerinde etkisi yoktur.
                self.c.execute("DELETE FROM cari_hareketler WHERE id=?", (cari_hareket_id,))
            elif referans_tipi == 'FATURA': # Bu durum `arayuz.py`'deki `secili_islemi_sil` metodunda ele alınıyor olmalı.
                # Burada sadece mesaj gösterip `rollback` yapacağız, asıl silme `fatura_sil` metodu üzerinden olmalı.
                self.conn.rollback() # Mevcut işlemi geri al
                return False, "Bu işlem tipi (FATURA) buradan doğrudan silinemez. Lütfen fatura modülünden fatura silme işlemini kullanın."
            else: # Diğer işlem tipleri buradan silinemez
                self.conn.rollback() # Bilinmeyen tipse rollback
                return False, "Bu işlem tipi buradan silinemez veya tanımlanamadı.\nFatura kaynaklı borç/alacak hareketleri fatura silinerek veya güncellenerek yönetilir."
            
            self.conn.commit() # Tüm işlemler başarılıysa commit et       
            return True, f"{referans_tipi.capitalize().replace('_',' ')} başarıyla silindi."
        except Exception as e:
            self.conn.rollback() # Hata durumunda rollback
            error_details = traceback.format_exc()
            return False, f"{referans_tipi.capitalize() if referans_tipi else 'İşlem'} silinirken hata: {e}\n\nDetaylar:\n{error_details}"
        


    def veresiye_borc_ekle(self, cari_id, cari_tip, tarih, tutar, aciklama):
        if not all([cari_id, cari_tip, tarih, tutar, aciklama]):
                return False, "Lütfen tüm zorunlu (*) alanları (Cari, Tarih, Tutar, Açıklama) doldurun."

        try:
            tutar_f = float(str(tutar).replace(',', '.'))
            if tutar_f <= 0:
                return False, "Tutar pozitif bir sayı olmalıdır."
            datetime.strptime(tarih, '%Y-%m-%d')
        except ValueError:
            return False, "Tutar sayısal bir değer olmalı veya Tarih formatı (YYYY-AA-GG) olmalıdır."

        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            olusturan_id = self.app.current_user[0] if self.app and self.app.current_user else None

            if cari_tip == 'MUSTERI':
                islem_tipi_ch = 'ALACAK'
                cari_bilgi = self.musteri_getir_by_id(cari_id)
                ch_aciklama = f"Manuel Veresiye Borç (Alacak): {aciklama} - Müşteri: {cari_bilgi[2] if cari_bilgi else 'Bilinmiyor'}"
            elif cari_tip == 'TEDARIKCI':
                islem_tipi_ch = 'BORC'
                cari_bilgi = self.tedarikci_getir_by_id(cari_id)
                ch_aciklama = f"Manuel Veresiye Borç (Borç): {aciklama} - Tedarikçi: {cari_bilgi[2] if cari_bilgi else 'Bilinmiyor'}"
            else:
                self.conn.rollback()
                return False, "Geçersiz cari tipi. Veresiye borç eklenemiyor."

            self.c.execute("""
                INSERT INTO cari_hareketler
                (tarih, cari_tip, cari_id, islem_tipi, tutar, aciklama, referans_id, referans_tip, kasa_banka_id, olusturma_tarihi_saat, olusturan_kullanici_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tarih, cari_tip, cari_id, islem_tipi_ch, tutar_f, ch_aciklama, None, "VERESIYE_BORC_MANUEL", None, current_time, olusturan_id))

            self.conn.commit()
            # DÜZELTME BURADA: Başarılı durumda (True, "mesaj") formatında dönüyoruz.
            return True, "Veresiye borç başarıyla eklendi."
        except Exception as e:
            self.conn.rollback() 
            return False, f"Veresiye borç eklenirken bir hata oluştu: {e}"
    
    def get_kar_zarar_verileri(self, baslangic_tarih=None, bitis_tarih=None):
        """
        Belirtilen tarih aralığındaki toplam gelir ve toplam gideri hesaplar.
        """
        toplam_gelir = 0.0
        toplam_gider = 0.0

        query = "SELECT tip, tutar FROM gelir_gider"
        params = []
        conditions = []

        if baslangic_tarih:
            conditions.append("tarih >= ?")
            params.append(baslangic_tarih)
        if bitis_tarih:
            conditions.append("tarih <= ?")
            params.append(bitis_tarih)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        self.c.execute(query, params)
        results = self.c.fetchall()

        for tip, tutar in results:
            if tip == 'GELİR':
                toplam_gelir += tutar
            elif tip == 'GİDER':
                toplam_gider += tutar
        
        return toplam_gelir, toplam_gider        
    def get_overdue_receivables(self):
        """
        Vadesi geçmiş alacakları (müşteri borçlarını) getirir.
        """
        self.c.execute("""
            SELECT 
                f.id AS fatura_id,
                f.fatura_no,
                f.tarih AS fatura_tarihi,
                f.vade_tarihi,
                (f.toplam_kdv_dahil - COALESCE(SUM(ch.tutar), 0)) AS kalan_tutar,
                m.ad || ' ' || m.soyad AS musteri_adi,
                m.kod AS musteri_kodu, -- <<<< BURAYI DİKKATLİCE DÜZELTİN: 'm.musteri_kodu' yerine 'm.kod' >>>>>
                m.telefon AS musteri_telefon
            FROM faturalar f
            JOIN musteriler m ON f.cari_id = m.id
            LEFT JOIN cari_hareketler ch ON ch.referans_id = f.id 
                                        AND ch.referans_tip = 'FATURA' 
                                        AND ch.cari_tip = 'MUSTERI' 
                                        AND ch.islem_tipi IN ('TAHSILAT', 'IADE_FATURASI') -- İade faturalarını da tahsilat gibi düşmeli
            WHERE f.tip = 'SATIŞ' 
            AND f.vade_tarihi IS NOT NULL 
            AND f.vade_tarihi < CURRENT_DATE 
            GROUP BY f.id
            HAVING kalan_tutar > 0
            ORDER BY f.vade_tarihi ASC
        """)
        return self.c.fetchall()

    def get_overdue_payables(self, current_date_str=None):
        """
        Vadesi geçmiş tedarikçi borçlarını (net borçları) döndürür.
        current_date_str: 'YYYY-AA-GG' formatında raporun alınacağı tarih. Yoksa bugünün tarihi kullanılır.
        Dönüş: [(cari_id, tedarikci_adi, net_borc, vadesi_gecen_gun)]
        """
        if current_date_str:
            current_date = datetime.strptime(current_date_str, '%Y-%m-%d')
        else:
            current_date = datetime.now()

        # Tedarikçilerin net bakiyelerini al (sadece bizim borçlu olduğumuz tedarikçiler)
        # SQL sorgusu güncellendi: islem_tipi = 'BORC' ve 'ODEME' olarak netleştirildi.
        self.c.execute("""
            SELECT 
                c.cari_id,
                t.ad AS tedarikci_adi,
                SUM(CASE WHEN c.islem_tipi = 'BORC' THEN c.tutar ELSE 0 END) - 
                SUM(CASE WHEN c.islem_tipi = 'ODEME' THEN c.tutar ELSE 0 END) AS net_borc,
                MAX(c.tarih) AS son_islem_tarihi -- Vade hesaplaması için son işlem tarihi
            FROM cari_hareketler c
            JOIN tedarikciler t ON c.cari_id = t.id
            WHERE c.cari_tip = 'TEDARIKCI'
            GROUP BY c.cari_id, t.ad
            HAVING net_borc > 0
        """)
        
        results = self.c.fetchall()
        overdue_payables = []

        for cari_id, tedarikci_adi, net_borc, son_islem_tarihi_str in results:
            try:
                # Tarih formatı 'YYYY-MM-DD' olarak varsayılıyor
                son_islem_tarihi = datetime.strptime(son_islem_tarihi_str, '%Y-%m-%d')
                vadesi_gecen_gun = (current_date - son_islem_tarihi).days
                if vadesi_gecen_gun > 0: # Sadece vadesi geçmiş olanları al
                    overdue_payables.append((cari_id, tedarikci_adi, net_borc, vadesi_gecen_gun))
            except ValueError:
                # Tarih formatı hatası olursa bu tedarikçiyi atla veya farklı ele al
                print(f"Uyarı: Tedarikçi ID {cari_id} için son işlem tarihi formatı hatalı: {son_islem_tarihi_str}")
                pass
        
        # En vadesi geçmiş olanları öne almak için sırala
        overdue_payables.sort(key=lambda x: x[3], reverse=True)
        return overdue_payables
    
    def get_tedarikci_net_bakiye(self, tedarikci_id, tarih_filtresi=None):
        net_bakiye = 0.0
        try:
            query = """
                SELECT ch.islem_tipi, ch.tutar, ch.referans_tip, f.odeme_turu
                FROM cari_hareketler ch
                LEFT JOIN faturalar f ON ch.referans_id = f.id
                WHERE ch.cari_id = ? AND ch.cari_tip = 'TEDARIKCI'
            """
            params = [tedarikci_id]
            if tarih_filtresi:
                query += " AND ch.tarih < ?"
                params.append(tarih_filtresi)

            self.c.execute(query, tuple(params))
            for hareket in self.c.fetchall():
                tutar = hareket['tutar'] or 0.0
                referans_tip = hareket['referans_tip']
                odeme_turu = hareket['odeme_turu']

                # SADECE AÇIK HESAP FATURALAR VE MANUEL ÖDEME/VERESİYE HAREKETLERİ DAHİL EDİLİR.
                # Peşin alış faturaları (FATURA_ALIS_PESIN) ve onların ödemeleri bu bakiyeyi etkilemez.
                # İade faturaları da sadece açık hesap ise etkiler.

                # Borç artırıcı hareketler (Bizim tedarikçiye borcumuz)
                if (referans_tip == self.KAYNAK_TIP_FATURA and odeme_turu == self.ODEME_TURU_ACIK_HESAP) or \
                   referans_tip == self.KAYNAK_TIP_VERESIYE_BORC_MANUEL:
                    net_bakiye += tutar
                # Borç azaltıcı hareketler (Tedarikçiye ödeme veya Alış İade Faturası)
                elif referans_tip == self.KAYNAK_TIP_ODEME or \
                     (referans_tip == self.KAYNAK_TIP_IADE_FATURA and odeme_turu == self.ODEME_TURU_ACIK_HESAP):
                    net_bakiye -= tutar

            return net_bakiye
        except Exception as e:
            logging.error(f"Tedarikçi net bakiye hesaplanırken hata: {e}\n{traceback.format_exc()}")
            return 0.0
                
    def get_musteri_net_bakiye(self, musteri_id, tarih_filtresi=None):
        net_bakiye = 0.0
        try:
            query = """
                SELECT ch.islem_tipi, ch.tutar, ch.referans_tip, f.odeme_turu
                FROM cari_hareketler ch
                LEFT JOIN faturalar f ON ch.referans_id = f.id
                WHERE ch.cari_id = ? AND ch.cari_tip = 'MUSTERI'
            """
            params = [musteri_id]
            if tarih_filtresi:
                query += " AND ch.tarih < ?"
                params.append(tarih_filtresi)
                
            self.c.execute(query, tuple(params))
            for hareket in self.c.fetchall():
                tutar = hareket['tutar'] or 0.0
                referans_tip = hareket['referans_tip']
                odeme_turu = hareket['odeme_turu']
                # Alacak artırıcı hareketler (Müşterinin bize borcu)
                if (referans_tip == self.KAYNAK_TIP_FATURA and odeme_turu == self.ODEME_TURU_ACIK_HESAP) or \
                   referans_tip == self.KAYNAK_TIP_VERESIYE_BORC_MANUEL:
                    net_bakiye += tutar
                # Borç azaltıcı hareketler (Müşteriden tahsilat veya İade Faturası)
                elif referans_tip == self.KAYNAK_TIP_TAHSILAT or \
                     (referans_tip == self.KAYNAK_TIP_IADE_FATURA and odeme_turu == self.ODEME_TURU_ACIK_HESAP):
                    net_bakiye -= tutar

            return net_bakiye
        except Exception as e:
            logging.error(f"Müşteri net bakiye hesaplanırken hata: {e}\n{traceback.format_exc()}")
            return 0.0
                        
    def _get_cari_devir_bakiye(self, cari_tip, cari_id, baslangic_tarih_str):
        devir_bakiye = 0.0
        try:
            # SADECE AÇIK HESAP VE MANUEL HAREKETLER DAHİL EDİLECEK.
            query = """
                SELECT ch.islem_tipi, ch.tutar, ch.referans_tip, f.odeme_turu
                FROM cari_hareketler ch
                LEFT JOIN faturalar f ON ch.referans_id = f.id
                WHERE ch.cari_tip = ? AND ch.cari_id = ? AND ch.tarih < ?
            """
            self.c.execute(query, (cari_tip, cari_id, baslangic_tarih_str))
            hareketler_oncesi = self.c.fetchall()

            for hareket in hareketler_oncesi:
                tutar = hareket['tutar'] or 0.0
                referans_tip = hareket['referans_tip']
                odeme_turu = hareket['odeme_turu'] # Faturadan gelen ödeme türü (None olabilir)

                if cari_tip == self.CARI_TIP_MUSTERI:
                    # Alacak artırıcı hareketler (Müşterinin bize borcu - sadece açık hesap faturalar veya manuel veresiye)
                    if (referans_tip == self.KAYNAK_TIP_FATURA and odeme_turu == self.ODEME_TURU_ACIK_HESAP) or \
                       referans_tip == self.KAYNAK_TIP_VERESIYE_BORC_MANUEL:
                        devir_bakiye += tutar
                    # Borç azaltıcı hareketler (Müşteriden tahsilat veya Satış İadesi - sadece açık hesaplar veya manuel tahsilat)
                    elif referans_tip == self.KAYNAK_TIP_TAHSILAT or \
                         (referans_tip == self.KAYNAK_TIP_IADE_FATURA and odeme_turu == self.ODEME_TURU_ACIK_HESAP):
                        devir_bakiye -= tutar
                elif cari_tip == self.CARI_TIP_TEDARIKCI:
                    # Borç artırıcı hareketler (Bizim tedarikçiye borcumuz - sadece açık hesap faturalar veya manuel veresiye)
                    if (referans_tip == self.KAYNAK_TIP_FATURA and odeme_turu == self.ODEME_TURU_ACIK_HESAP) or \
                       referans_tip == self.KAYNAK_TIP_VERESIYE_BORC_MANUEL:
                        devir_bakiye += tutar
                    # Borç azaltıcı hareketler (Tedarikçiye ödeme veya Alış İadesi - sadece açık hesaplar veya manuel ödeme)
                    elif referans_tip == self.KAYNAK_TIP_ODEME or \
                         (referans_tip == self.KAYNAK_TIP_IADE_FATURA and odeme_turu == self.ODEME_TURU_ACIK_HESAP):
                        devir_bakiye -= tutar
            
            logging.debug(f"Devir bakiye hesaplandı: {devir_bakiye}")
            return devir_bakiye
        except Exception as e:
            logging.error(f"_get_cari_devir_bakiye hatası: {e}\n{traceback.format_exc()}")
            return 0.0
                        
    def cari_hesap_ekstresi_al(self, cari_id, cari_tip, baslangic_tarihi=None, bitis_tarihi=None):
        """
        Belirli bir cariye ait hesap ekstresini (tüm cari hareketleri) getirir ve devreden bakiyeyi hesaplar.
        Dönüş: (ekstre_hareketleri_listesi, devreden_bakiye_float, success_bool, message_str)
        """
        try:
            # Devreden bakiyeyi al
            devreden_bakiye = self._get_cari_devir_bakiye(cari_tip, cari_id, baslangic_tarihi)

            query = """
                SELECT
                    ch.id,
                    ch.tarih,
                    STRFTIME('%H:%M:%S', ch.olusturma_tarihi_saat) AS islem_saati,
                    ch.islem_tipi,
                    ch.tutar,
                    ch.aciklama,
                    ch.referans_tip,
                    ch.referans_id,
                    COALESCE(f.fatura_no, '') AS fatura_no,
                    COALESCE(f.odeme_turu, '') AS odeme_turu,
                    COALESCE(f.vade_tarihi, '') AS vade_tarihi,
                    COALESCE(f.tip, '') AS fatura_tipi -- faturalar.tip
                FROM
                    cari_hareketler ch
                LEFT JOIN
                    faturalar f ON ch.referans_id = f.id 
                               AND ch.referans_tip IN (?, ?, ?, ?, ?) -- Referans tiplerini genişletiyoruz
                WHERE
                    ch.cari_id = ? AND ch.cari_tip = ?
            """
            params = [
                self.KAYNAK_TIP_FATURA, 
                self.KAYNAK_TIP_IADE_FATURA, 
                self.KAYNAK_TIP_FATURA_SATIS_PESIN, # Peşin satış faturalarını dahil et
                self.KAYNAK_TIP_FATURA_ALIS_PESIN,  # Peşin alış faturalarını dahil et
                self.KAYNAK_TIP_VERESIYE_BORC_MANUEL, # Veresiye borçlar da burada JOIN'e dahil edilebilir, mantığına göre.
                                                    # Ancak genellikle sadece faturalar için JOIN yaparız.
                                                    # Şimdilik sadece peşin faturaları ekliyorum.
                cari_id, 
                cari_tip
            ]

            if baslangic_tarihi:
                query += " AND ch.tarih >= ?"
                params.append(baslangic_tarihi)
            if bitis_tarihi:
                query += " AND ch.tarih <= ?"
                params.append(bitis_tarihi)
            
            query += " ORDER BY ch.tarih ASC, ch.olusturma_tarihi_saat ASC"

            self.c.execute(query, params)
            ekstre_hareketleri_raw = self.c.fetchall()

            ekstre_sonuclari_islenmis = []
            for hareket in ekstre_hareketleri_raw:
                hareket_bilgisi = {
                    'id': hareket['id'],
                    'tarih': hareket['tarih'],
                    'islem_saati': hareket['islem_saati'],
                    'islem_tipi': hareket['islem_tipi'],
                    'tutar': self.safe_float(hareket['tutar']),
                    'aciklama': hareket['aciklama'],
                    'referans_tip': hareket['referans_tip'],
                    'referans_id': hareket['referans_id'],
                    'fatura_no': hareket['fatura_no'],
                    'odeme_turu': hareket['odeme_turu'],
                    'vade_tarihi': hareket['vade_tarihi'],
                    'fatura_tipi': hareket['fatura_tipi'] # Fatura tipi de eklendi
                }
                ekstre_sonuclari_islenmis.append(hareket_bilgisi)
            
            return ekstre_sonuclari_islenmis, devreden_bakiye, True, "Ekstre başarıyla alındı."

        except Exception as e:
            logging.error(f"Cari hesap ekstresi alınırken hata: {e}\n{traceback.format_exc()}")
            return [], 0.0, False, f"Cari hesap ekstresi alınırken hata oluştu: {e}"
                            
    def get_cari_ozet_bilgileri(self, cari_id, cari_tip):
        ozet = {
            "donem_basi_bakiye": 0.0,
            "donem_sonu_bakiye": 0.0,
            "donem_toplam_borc_hareketi": 0.0,
            "donem_toplam_alacak_hareketi": 0.0,
            "toplam_tahsilat": 0.0, # Sadece tahsilat
            "toplam_odeme": 0.0,     # Sadece ödeme
            "vadesi_gelmis_borc_alacak": 0.0,
            "vadesi_gelecek_borc_alacak": 0.0
        }
        try:
            # Dönem başı bakiyeyi almak için (bugünden önceki tüm hareketler)
            ozet["donem_basi_bakiye"] = self.get_musteri_net_bakiye(cari_id) if cari_tip == self.CARI_TIP_MUSTERI else self.get_tedarikci_net_bakiye(cari_id)

            baslangic_tarih = "1900-01-01" 
            bitis_tarih = datetime.now().strftime('%Y-%m-%d')

            if cari_tip == 'MUSTERI':
                # Toplam Alacak Hareketi: Müşterinin borcunu artıran hareketler (Açık Fatura, Manuel Veresiye Borç)
                self.c.execute("""
                    SELECT SUM(ch.tutar) FROM cari_hareketler ch
                    LEFT JOIN faturalar f ON ch.referans_id = f.id
                    WHERE ch.cari_id = ? AND ch.cari_tip = ? AND ch.tarih BETWEEN ? AND ? AND (
                        ch.referans_tip = ? OR -- VERESIYE_BORC_MANUEL
                        (ch.referans_tip = ? AND f.odeme_turu = ?) -- FATURA ve AÇIK HESAP
                    )
                """, (cari_id, self.CARI_TIP_MUSTERI, baslangic_tarih, bitis_tarih, self.KAYNAK_TIP_VERESIYE_BORC_MANUEL, self.KAYNAK_TIP_FATURA, self.ODEME_TURU_ACIK_HESAP))
                ozet["donem_toplam_alacak_hareketi"] = self.c.fetchone()[0] or 0.0
                
                # Toplam Borç Hareketi: Müşterinin borcunu azaltan hareketler (Manuel Tahsilat, Açık Hesap İade Faturası)
                self.c.execute("""
                    SELECT SUM(ch.tutar) FROM cari_hareketler ch
                    LEFT JOIN faturalar f ON ch.referans_id = f.id
                    WHERE ch.cari_id = ? AND ch.cari_tip = ? AND ch.tarih BETWEEN ? AND ? AND (
                        ch.referans_tip = ? OR -- TAHSILAT
                        (ch.referans_tip = ? AND f.odeme_turu = ?) -- İADE_FATURA ve AÇIK HESAP
                    )
                """, (cari_id, self.CARI_TIP_MUSTERI, baslangic_tarih, bitis_tarih, self.KAYNAK_TIP_TAHSILAT, self.KAYNAK_TIP_IADE_FATURA, self.ODEME_TURU_ACIK_HESAP))
                ozet["donem_toplam_borc_hareketi"] = self.c.fetchone()[0] or 0.0

                # Toplam Tahsilat: SADECE fiili tahsilat hareketlerini toplamalı
                # Referans tipi TAHSILAT veya FATURA_SATIS_PESIN olan cari hareketleri topla.
                # NOT: Bu sorgu içinde odeme_turu='AÇIK HESAP' faturaları hariç tutulmalı
                self.c.execute("""
                    SELECT SUM(tutar) FROM cari_hareketler
                    WHERE cari_id = ? AND cari_tip = ? AND (
                        referans_tip = ? OR -- Manuel tahsilatlar
                        referans_tip = ? -- Peşin satış faturalarından gelen tahsilatlar
                    ) AND tarih BETWEEN ? AND ?
                """, (cari_id, self.CARI_TIP_MUSTERI, self.KAYNAK_TIP_TAHSILAT, self.KAYNAK_TIP_FATURA_SATIS_PESIN, baslangic_tarih, bitis_tarih))
                ozet["toplam_tahsilat"] = self.c.fetchone()[0] or 0.0
                
                current_net_bakiye = self.get_musteri_net_bakiye(cari_id)
                ozet["net_bakiye"] = current_net_bakiye
                ozet["donem_sonu_bakiye"] = current_net_bakiye

                vade_durumu = self._get_vade_durumu(cari_id, cari_tip)
                ozet["vadesi_gelmis_borc_alacak"] = vade_durumu["vadesi_gelmis"]
                ozet["vadesi_gelecek_borc_alacak"] = vade_durumu["vadesi_gelecek"]


            elif cari_tip == 'TEDARIKCI':
                # Toplam Borç Hareketi: Tedarikçiye borcumuzu artıran hareketler (Açık Fatura, Manuel Veresiye Borç)
                self.c.execute("""
                    SELECT SUM(ch.tutar) FROM cari_hareketler ch
                    LEFT JOIN faturalar f ON ch.referans_id = f.id
                    WHERE ch.cari_id = ? AND ch.cari_tip = ? AND ch.tarih BETWEEN ? AND ? AND (
                        ch.referans_tip = ? OR -- VERESIYE_BORC_MANUEL
                        (ch.referans_tip = ? AND f.odeme_turu = ?) -- FATURA ve AÇIK HESAP
                    )
                """, (cari_id, self.CARI_TIP_TEDARIKCI, baslangic_tarih, bitis_tarih, self.KAYNAK_TIP_VERESIYE_BORC_MANUEL, self.KAYNAK_TIP_FATURA, self.ODEME_TURU_ACIK_HESAP))
                ozet["donem_toplam_borc_hareketi"] = self.c.fetchone()[0] or 0.0

                # Toplam Alacak Hareketi: Tedarikçiye borcumuzu azaltan hareketler (Manuel Ödeme, Açık Hesap Alış İade Faturası)
                self.c.execute("""
                    SELECT SUM(ch.tutar) FROM cari_hareketler ch
                    LEFT JOIN faturalar f ON ch.referans_id = f.id
                    WHERE ch.cari_id = ? AND ch.cari_tip = ? AND ch.tarih BETWEEN ? AND ? AND (
                        ch.referans_tip = ? OR -- ODEME
                        (ch.referans_tip = ? AND f.odeme_turu = ?) -- İADE_FATURA ve AÇIK HESAP
                    )
                """, (cari_id, self.CARI_TIP_TEDARIKCI, baslangic_tarih, bitis_tarih, self.KAYNAK_TIP_ODEME, self.KAYNAK_TIP_IADE_FATURA, self.ODEME_TURU_ACIK_HESAP))
                ozet["donem_toplam_alacak_hareketi"] = self.c.fetchone()[0] or 0.0

                # Toplam Ödeme: SADECE fiili ödeme hareketlerini toplamalı
                # Referans tipi ODEME veya FATURA_ALIS_PESIN olan cari hareketleri topla.
                self.c.execute("""
                    SELECT SUM(tutar) FROM cari_hareketler
                    WHERE cari_id = ? AND cari_tip = ? AND (
                        referans_tip = ? OR -- Manuel ödemeler
                        referans_tip = ? -- Peşin alış faturalarından gelen ödemeler
                    ) AND tarih BETWEEN ? AND ?
                """, (cari_id, self.CARI_TIP_TEDARIKCI, self.KAYNAK_TIP_ODEME, self.KAYNAK_TIP_FATURA_ALIS_PESIN, baslangic_tarih, bitis_tarih))
                ozet["toplam_odeme"] = self.c.fetchone()[0] or 0.0

                current_net_bakiye = self.get_tedarikci_net_bakiye(cari_id)
                ozet["net_bakiye"] = current_net_bakiye
                ozet["donem_sonu_bakiye"] = current_net_bakiye

                vade_durumu = self._get_vade_durumu(cari_id, cari_tip)
                ozet["vadesi_gelmis_borc_alacak"] = vade_durumu["vadesi_gelmis"]
                ozet["vadesi_gelecek_borc_alacak"] = vade_durumu["vadesi_gelecek"]
            
            return ozet
        except Exception as e:
            logging.error(f"get_cari_ozet_bilgileri hatası: {e}\n{traceback.format_exc()}")
            return ozet
                        
    def _fatura_finansal_etki_olustur(self, fatura_id, fatura_no, fatura_tarihi, fatura_tipi, cari_id, nihai_toplam_kdv_dahil, odeme_turu, kasa_banka_id, misafir_adi):
        try:
            current_time = self.get_current_datetime_str()
            olusturan_id = self._get_current_user_id()

            cari_adi = ""
            # <<< DÜZELTME BAŞLANGICI: 'cari_tip_for_db' adında yeni bir değişken tanımlıyoruz >>>
            cari_tip_for_db = ""
            if fatura_tipi in (self.FATURA_TIP_SATIS, self.FATURA_TIP_SATIS_IADE):
                cari_data = self.musteri_getir_by_id(cari_id)
                cari_adi = cari_data['ad'] if cari_data else "Bilinmeyen Müşteri"
                cari_tip_for_db = self.CARI_TIP_MUSTERI # Müşteri ise 'MUSTERI'
            elif fatura_tipi in (self.FATURA_TIP_ALIS, self.FATURA_TIP_ALIS_IADE, self.FATURA_TIP_DEVIR_GIRIS):
                cari_data = self.tedarikci_getir_by_id(cari_id)
                cari_adi = cari_data['ad'] if cari_data else "Bilinmeyen Tedarikçi"
                cari_tip_for_db = self.CARI_TIP_TEDARIKCI # Tedarikçi ise 'TEDARIKCI'
            # <<< DÜZELTME BİTİŞİ >>>
            
            if misafir_adi and fatura_tipi == self.FATURA_TIP_SATIS:
                cari_adi = f"{cari_adi} (Misafir: {misafir_adi})"

            # A. Cari Hareket Kaydı
            cari_islem_tipi = ""
            cari_referans_tipi = self.KAYNAK_TIP_FATURA # Varsayılan olarak fatura

            if odeme_turu in self.pesin_odeme_turleri:
                if fatura_tipi == self.FATURA_TIP_SATIS:
                    cari_islem_tipi = self.ISLEM_TIP_TAHSILAT
                    cari_referans_tipi = self.KAYNAK_TIP_FATURA_SATIS_PESIN
                elif fatura_tipi == self.FATURA_TIP_ALIS:
                    cari_islem_tipi = self.ISLEM_TIP_ODEME
                    cari_referans_tipi = self.KAYNAK_TIP_FATURA_ALIS_PESIN
                elif fatura_tipi == self.FATURA_TIP_SATIS_IADE:
                    cari_islem_tipi = self.ISLEM_TIP_BORC
                    cari_referans_tipi = self.KAYNAK_TIP_IADE_FATURA
                elif fatura_tipi == self.FATURA_TIP_ALIS_IADE:
                    cari_islem_tipi = self.ISLEM_TIP_ALACAK
                    cari_referans_tipi = self.KAYNAK_TIP_IADE_FATURA
                elif fatura_tipi == self.FATURA_TIP_DEVIR_GIRIS:
                    return True, "Devir girişi için cari hareket oluşturulmadı."
                
            elif odeme_turu == self.ODEME_TURU_ACIK_HESAP:
                if fatura_tipi == self.FATURA_TIP_SATIS or fatura_tipi == self.FATURA_TIP_DEVIR_GIRIS:
                    cari_islem_tipi = self.ISLEM_TIP_ALACAK
                elif fatura_tipi == self.FATURA_TIP_ALIS:
                    cari_islem_tipi = self.ISLEM_TIP_BORC
                elif fatura_tipi == self.FATURA_TIP_SATIS_IADE:
                    cari_islem_tipi = self.ISLEM_TIP_BORC
                    cari_referans_tipi = self.KAYNAK_TIP_IADE_FATURA
                elif fatura_tipi == self.FATURA_TIP_ALIS_IADE:
                    cari_islem_tipi = self.ISLEM_TIP_ALACAK
                    cari_referans_tipi = self.KAYNAK_TIP_IADE_FATURA

            ch_aciklama = f"Fatura No: {fatura_no} ({fatura_tipi} Faturası) - Cari: {cari_adi}"

            self.c.execute("""
                INSERT INTO cari_hareketler (
                    tarih, cari_tip, cari_id, islem_tipi, tutar, aciklama,
                    referans_id, referans_tip, kasa_banka_id,
                    olusturma_tarihi_saat, olusturan_kullanici_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fatura_tarihi, cari_tip_for_db, cari_id, cari_islem_tipi, nihai_toplam_kdv_dahil, ch_aciklama, # <<< BURADA cari_tip_for_db KULLANILDI >>>
                fatura_id, cari_referans_tipi, kasa_banka_id,
                current_time, olusturan_id
            ))
            
            # B. Gelir/Gider Kaydı
            if odeme_turu in self.pesin_odeme_turleri:
                gg_tipi = ""
                if fatura_tipi == self.FATURA_TIP_SATIS or fatura_tipi == self.FATURA_TIP_ALIS_IADE:
                    gg_tipi = self.ISLEM_TIP_GELIR
                elif fatura_tipi == self.FATURA_TIP_ALIS or fatura_tipi == self.FATURA_TIP_SATIS_IADE:
                    gg_tipi = self.ISLEM_TIP_GIDER
                
                gg_aciklama = f"{fatura_tipi} Faturası: {fatura_no} - {cari_adi}"
                
                self.c.execute("""
                    INSERT INTO gelir_gider (
                        tarih, tip, tutar, aciklama, kaynak, kaynak_id, kasa_banka_id,
                        olusturma_tarihi_saat, olusturan_kullanici_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fatura_tarihi, gg_tipi, nihai_toplam_kdv_dahil, gg_aciklama,
                    self.KAYNAK_TIP_FATURA, fatura_id, kasa_banka_id,
                    current_time, olusturan_id
                ))
            
            return True, "Finansal etkiler başarıyla oluşturuldu."
        except Exception as e:
            logging.error(f"Fatura finansal etkileri oluşturulurken hata: {e}\n{traceback.format_exc()}")
            raise # Hatanın yukarıya yayılmasını sağlar
        
    def _fatura_finansal_etki_geri_al(self, fatura_id):
        """
        Belirli bir fatura ID'sine ait tüm cari hareketleri ve gelir/gider kayıtlarını siler.
        Bu metod kendi transaction'ını yönetmez, çağrıldığı transaction'ın bir parçasıdır.
        """
        try:
            # Fatura ile ilişkili tüm cari hareketleri sil
            self.c.execute("""
                DELETE FROM cari_hareketler 
                WHERE referans_id = ? AND referans_tip IN (?, ?, ?, ?)
            """, (fatura_id, self.KAYNAK_TIP_FATURA, self.KAYNAK_TIP_IADE_FATURA, 
                  self.KAYNAK_TIP_FATURA_SATIS_PESIN, self.KAYNAK_TIP_FATURA_ALIS_PESIN))
            
            # Fatura ile ilişkili tüm gelir/gider kayıtlarını sil (sadece kaynak FATURA olanlar)
            self.c.execute("DELETE FROM gelir_gider WHERE kaynak = ? AND kaynak_id = ?", (self.KAYNAK_TIP_FATURA, fatura_id))
            
            return True, "Finansal etkiler başarıyla geri alındı."
        except Exception as e:
            logging.error(f"Fatura finansal etkileri geri alınırken hata: {e}\n{traceback.format_exc()}")
            raise # Hatanın yukarıya yayılmasını sağlar

    def _get_vade_durumu(self, cari_id, cari_tip):
        """
        Bir cari hesabın vadesi gelmiş ve vadesi gelecek borç/alacaklarını hesaplar.
        Sadece Açık Hesap faturalarını dikkate alır.
        """
        vade_durumu = {"vadesi_gelmis": 0.0, "vadesi_gelecek": 0.0}
        
        # Sadece açık hesap faturalarını ve vadesi olanları çek
        query = """
            SELECT SUM(toplam_kdv_dahil) AS tutar, vade_tarihi, tip
            FROM faturalar
            WHERE cari_id = ? AND odeme_turu = ? AND vade_tarihi IS NOT NULL
            GROUP BY vade_tarihi, tip
        """
        
        self.c.execute(query, (cari_id, self.ODEME_TURU_ACIK_HESAP))
        results = self.c.fetchall()

        bugunun_tarihi = date.today()

        for row in results:
            tutar = row['tutar'] or 0.0
            try:
                vade_tarihi = datetime.strptime(row['vade_tarihi'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                continue # Geçersiz tarih formatı veya boş tarihleri atla

            # Fatura tipine göre tutarın yönünü belirle
            # Müşteri alacakları (Satış faturaları) ve Tedarikçi borçları (Alış faturaları)
            # İade faturaları da ters etki yapar.
            if (cari_tip == self.CARI_TIP_MUSTERI and row['tip'] == self.FATURA_TIP_SATIS) or \
               (cari_tip == self.CARI_TIP_TEDARIKCI and row['tip'] == self.FATURA_TIP_ALIS):
                
                if vade_tarihi < bugunun_tarihi:
                    vade_durumu["vadesi_gelmis"] += tutar
                else:
                    vade_durumu["vadesi_gelecek"] += tutar
            
            # İade faturaları ters etki yapar (müşteri borcu azaltır, tedarikçi alacağı azaltır)
            elif (cari_tip == self.CARI_TIP_MUSTERI and row['tip'] == self.FATURA_TIP_SATIS_IADE) or \
                 (cari_tip == self.CARI_TIP_TEDARIKCI and row['tip'] == self.FATURA_TIP_ALIS_IADE):
                
                # İade faturaları için vade mantığı daha karmaşık olabilir.
                # Genellikle iade faturasının vadesi hemen gelir.
                # Ancak burada orijinal fatura ile aynı vade mantığını sürdürmüş olduk.
                if vade_tarihi < bugunun_tarihi:
                    vade_durumu["vadesi_gelmis"] -= tutar # Vadesi geçmiş iade, borcu azaltır
                else:
                    vade_durumu["vadesi_gelecek"] -= tutar # Vadesi gelecek iade, borcu azaltır

        return vade_durumu

    def stok_envanterini_yeniden_hesapla(self):
        """
        Tüm ürünlerin stok miktarlarını, stok_hareketleri tablosundaki TÜM giriş ve çıkışları
        dikkate alarak sıfırdan yeniden hesaplar. Bu, tüm tutarsızlıkları düzeltir.
        """
        try:
            self.conn.execute("BEGIN TRANSACTION")

            # 1. Adım: Stok hareketleri olan tüm benzersiz ürün ID'lerini al.
            self.c.execute("SELECT DISTINCT urun_id FROM stok_hareketleri")
            urun_idler = self.c.fetchall()
            
            if not urun_idler:
                self.conn.commit()
                return True, "Hesaplanacak stok hareketi bulunamadı."

            # 2. Adım: Her bir ürün için net stok farkını hesapla.
            for urun in urun_idler:
                urun_id = urun['urun_id']
                
                # Tüm girişleri topla
                self.c.execute("""
                    SELECT SUM(miktar) FROM stok_hareketleri 
                    WHERE urun_id = ? AND (
                        islem_tipi LIKE '%Giriş%' OR 
                        islem_tipi LIKE '%Alış%' OR 
                        islem_tipi LIKE '%Fazlası%' OR
                        islem_tipi LIKE '%İptal%')
                """, (urun_id,))
                toplam_giris = self.c.fetchone()[0] or 0.0

                # Tüm çıkışları topla
                self.c.execute("""
                    SELECT SUM(miktar) FROM stok_hareketleri 
                    WHERE urun_id = ? AND (
                        islem_tipi LIKE '%Çıkış%' OR 
                        islem_tipi LIKE '%Satış%' OR 
                        islem_tipi LIKE '%Eksiği%' OR
                        islem_tipi LIKE '%Zayiat%')
                """, (urun_id,))
                toplam_cikis = self.c.fetchone()[0] or 0.0
                
                # Nihai doğru stoku hesapla
                dogru_stok = toplam_giris - toplam_cikis

                # 3. Adım: tbl_stoklar tablosundaki stok miktarını bu doğru rakamla güncelle.
                self.c.execute("UPDATE tbl_stoklar SET stok_miktari = ? WHERE id = ?", (dogru_stok, urun_id))

            self.conn.commit()
            return True, f"{len(urun_idler)} adet ürünün stoku, tüm hareketlere göre başarıyla yeniden hesaplandı."

        except Exception as e:
            self.conn.rollback()
            error_details = traceback.format_exc()
            logging.error(f"Stok envanteri yeniden hesaplanırken hata: {e}\nDetay: {error_details}")
            return False, "Stoklar yeniden hesaplanırken beklenmeyen bir hata oluştu."

    def get_toplam_musteri_sayisi(self): # Eğer böyle bir metodunuz varsa
        # self.connect() # Bu satırı sildiğinizden emin olun
        self.c.execute("SELECT COUNT(id) FROM musteriler WHERE kod != ?", (self.PERAKENDE_MUSTERI_KODU,)) # musteri_kodu yerine KOD
        return self.c.fetchone()[0]

    def get_toplam_tedarikci_sayisi(self):
        self.c.execute("SELECT COUNT(id) FROM tedarikciler")
        sonuc = self.c.fetchone()
        return sonuc[0] if sonuc else 0

    def get_toplam_stok_cesidi_sayisi(self):
        self.c.execute("SELECT COUNT(id) FROM tbl_stoklar")
        sonuc = self.c.fetchone()
        return sonuc[0] if sonuc else 0
    def get_nakit_akis_verileri(self, baslangic_tarih=None, bitis_tarih=None, limit=None, offset=None):
        """
        Belirtilen tarih aralığındaki kasa ve banka hareketlerini (nakit akışını) getirir.
        GELİR (kasaya/bankaya giren) ve GİDER (kasadan/bankadan çıkan) hareketleri dahil eder.
        """
        query = """
            SELECT 
                gg.tarih,
                gg.tip, -- GELİR/GİDER
                gg.tutar,
                gg.aciklama,
                kb.hesap_adi, -- Kasa/Banka Adı
                kb.tip, -- KASA/BANKA
                gg.kaynak, -- FATURA, TAHSILAT, ODEME, MANUEL
                gg.kaynak_id -- İlişkili ID (fatura_id, cari_hareket_id)
            FROM gelir_gider gg
            JOIN kasalar_bankalar kb ON gg.kasa_banka_id = kb.id
            WHERE gg.kasa_banka_id IS NOT NULL -- Sadece kasa/banka ile ilişkili hareketler
        """
        params = []
        conditions = []

        if baslangic_tarih:
            conditions.append("gg.tarih >= ?")
            params.append(baslangic_tarih)
        if bitis_tarih:
            conditions.append("gg.tarih <= ?")
            params.append(bitis_tarih)
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
            
        query += " ORDER BY gg.tarih ASC, gg.id ASC"
        
        # Sayfalama için LIMIT ve OFFSET ekle
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)
        
        self.c.execute(query, params)
        return self.c.fetchall()
    
    def get_nakit_akis_count(self, baslangic_tarih=None, bitis_tarih=None): # Yeni metot: toplam nakit akışı sayısını alır
        query = """
            SELECT COUNT(gg.id)
            FROM gelir_gider gg
            JOIN kasalar_bankalar kb ON gg.kasa_banka_id = kb.id
            WHERE gg.kasa_banka_id IS NOT NULL
        """
        params = []
        conditions = []

        if baslangic_tarih:
            conditions.append("gg.tarih >= ?")
            params.append(baslangic_tarih)
        if bitis_tarih:
            conditions.append("gg.tarih <= ?")
            params.append(bitis_tarih)
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
            
        self.c.execute(query, params)
        return self.c.fetchone()[0]    

    def get_kasa_banka_toplam_bakiye(self, hesap_id):
        """Belirli bir kasa/banka hesabının toplam bakiyesini döndürür."""
        self.c.execute("SELECT bakiye FROM kasalar_bankalar WHERE id = ?", (hesap_id,))
        result = self.c.fetchone()
        return result[0] if result else 0.0

    def get_tum_kasa_banka_bakiyeleri(self):
        """Tüm kasa ve banka hesaplarının güncel bakiyelerini döndürür."""
        self.c.execute("SELECT id, hesap_adi, bakiye, tip FROM kasalar_bankalar ORDER BY tip DESC, hesap_adi ASC")
        return self.c.fetchall()
    
    # --- Excel ve PDF İşlemleri ---
    def stok_raporu_excel_olustur(self, dosya_yolu):
        try:
            stok_listesi = self.stok_listele() # Tüm stokları al
            if not stok_listesi:
                return False

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Stok_Raporu"

            # Başlıklar
            headers = ["Ürün Kodu", "Ürün Adı", "Mevcut Stok", "Alış Fiyatı (TL)", "Satış Fiyatı (TL)", "KDV Oranı (%)"]
            ws.append(headers)

            # Başlık Stili
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            for col_idx, header_text in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = len(header_text) + 5
            # Verileri yazdır
            for stok_item in stok_listesi:
                # stok_item: (id, urun_kodu, urun_adi, stok_miktari, alis_fiyati, satis_fiyati, kdv_orani)
                urun_kodu = stok_item[1]
                urun_adi = stok_item[2]
                stok_miktari = stok_item[3]
                alis_fiyati = stok_item[4]
                satis_fiyati = stok_item[5]
                kdv_orani = stok_item[6]
                ws.append([urun_kodu, urun_adi, stok_miktari, alis_fiyati, satis_fiyati, kdv_orani])
            
            # Para birimi ve sayı formatları (isteğe bağlı)
            for row in ws.iter_rows(min_row=2, max_col=ws.max_column, max_row=ws.max_row):
                if row[2].value is not None: row[2].number_format = '#,##0.00' # Stok miktarı
                if row[3].value is not None: row[3].number_format = '#,##0.00₺' # Alış fiyatı
                if row[4].value is not None: row[4].number_format = '#,##0.00₺' # Satış fiyatı
                if row[5].value is not None: row[5].number_format = '0"%"' # KDV

            wb.save(dosya_yolu)
            return True
        except Exception as e:
            traceback.print_exc()
            return False

    def mevcut_stok_verilerini_excel_disa_aktar(self, dosya_yolu):
        return self.stok_raporu_excel_olustur(dosya_yolu)

    def _get_cari_bakiye_snapshot(self, cari_id, cari_tip, tarih_str):
        """
        Belirli bir tarihteki cari bakiyesini hesaplar.
        tarih_str: 'YYYY-MM-DD' formatında tarih.
        Dönüş: {'onceki_bakiye': float, 'bugun_odenen': float, 'kalan_borc': float}
        """
        onceki_bakiye = 0.0
        bugun_odenen = 0.0
        bugun_tahsil_edilen = 0.0 # Müşteri için
        
        try:
            # Önceki Bakiye: Belirtilen tarihten önceki tüm hareketlerin toplamı
            query_onceki = """
                SELECT islem_tipi, tutar FROM cari_hareketler
                WHERE cari_id = ? AND cari_tip = ? AND tarih < ?
            """
            self.c.execute(query_onceki, (cari_id, cari_tip, tarih_str))
            onceki_hareketler = self.c.fetchall()

            for h in onceki_hareketler:
                if cari_tip == 'MUSTERI':
                    if h['islem_tipi'] == 'ALACAK': onceki_bakiye += h['tutar'] # Müşterinin bize borcu
                    elif h['islem_tipi'] == 'TAHSILAT': onceki_bakiye -= h['tutar'] # Müşteriden tahsilat
                elif cari_tip == 'TEDARIKCI':
                    if h['islem_tipi'] == 'BORC': onceki_bakiye += h['tutar'] # Bizim tedarikçiye borcumuz
                    elif h['islem_tipi'] == 'ODEME': onceki_bakiye -= h['tutar'] # Tedarikçiye ödeme

            # Bugün Yapılan Ödeme/Tahsilat (Fatura tarihi ile aynı güne ait cari hareketler)
            query_bugun = """
                SELECT islem_tipi, tutar FROM cari_hareketler
                WHERE cari_id = ? AND cari_tip = ? AND tarih = ?
            """
            self.c.execute(query_bugun, (cari_id, cari_tip, tarih_str))
            bugun_hareketler = self.c.fetchall()

            for h in bugun_hareketler:
                if cari_tip == 'MUSTERI':
                    if h['islem_tipi'] == 'TAHSILAT': bugun_tahsil_edilen += h['tutar']
                elif cari_tip == 'TEDARIKCI':
                    if h['islem_tipi'] == 'ODEME': bugun_odenen += h['tutar']

            # Kalan Borç: Önceki bakiye + (bugünkü ALACAK/BORÇ hareketleri) - (bugünkü TAHSİLAT/ÖDEME hareketleri)
            # Bu, faturanın kendisi haricindeki gün içi hareketleri hesaba katar.
            kalan_borc = onceki_bakiye
            for h in bugun_hareketler:
                if cari_tip == 'MUSTERI':
                    if h['islem_tipi'] == 'ALACAK': kalan_borc += h['tutar']
                    elif h['islem_tipi'] == 'TAHSILAT': kalan_borc -= h['tutar']
                elif cari_tip == 'TEDARIKCI':
                    if h['islem_tipi'] == 'BORC': kalan_borc += h['tutar']
                    elif h['islem_tipi'] == 'ODEME': kalan_borc -= h['tutar']

            return {
                'onceki_bakiye': onceki_bakiye,
                'bugun_odenen': bugun_tahsil_edilen if cari_tip == 'MUSTERI' else bugun_odenen,
                'kalan_borc': kalan_borc
            }
        except Exception as e:
            logging.error(f"Cari bakiye anlık görüntü hatası: {e}", exc_info=True)
            return {
                'onceki_bakiye': 0.0,
                'bugun_odenen': 0.0,
                'kalan_borc': 0.0
            }

    def _get_cari_bakiye_snapshot(self, cari_id, cari_tip, tarih_str):
        """
        Belirli bir tarihteki cari bakiyesini hesaplar.
        tarih_str: 'YYYY-MM-DD' formatında tarih.
        Dönüş: {'onceki_bakiye': float, 'bugun_odenen': float, 'kalan_borc': float}
        """
        onceki_bakiye = 0.0
        bugun_odenen = 0.0
        bugun_tahsil_edilen = 0.0 # Müşteri için
        
        try:
            # Önceki Bakiye: Belirtilen tarihten önceki tüm hareketlerin toplamı
            query_onceki = """
                SELECT islem_tipi, tutar FROM cari_hareketler
                WHERE cari_id = ? AND cari_tip = ? AND tarih < ?
            """
            self.c.execute(query_onceki, (cari_id, cari_tip, tarih_str))
            onceki_hareketler = self.c.fetchall()

            for h in onceki_hareketler:
                if cari_tip == 'MUSTERI':
                    if h['islem_tipi'] == 'ALACAK': onceki_bakiye += h['tutar'] # Müşterinin bize borcu
                    elif h['islem_tipi'] == 'TAHSILAT': onceki_bakiye -= h['tutar'] # Müşteriden tahsilat
                elif cari_tip == 'TEDARIKCI':
                    if h['islem_tipi'] == 'BORC': onceki_bakiye += h['tutar'] # Bizim tedarikçiye borcumuz
                    elif h['islem_tipi'] == 'ODEME': onceki_bakiye -= h['tutar'] # Tedarikçiye ödeme

            # Bugün Yapılan Ödeme/Tahsilat (Fatura tarihi ile aynı güne ait cari hareketler)
            query_bugun = """
                SELECT islem_tipi, tutar FROM cari_hareketler
                WHERE cari_id = ? AND cari_tip = ? AND tarih = ?
            """
            self.c.execute(query_bugun, (cari_id, cari_tip, tarih_str))
            bugun_hareketler = self.c.fetchall()

            for h in bugun_hareketler:
                if cari_tip == 'MUSTERI':
                    if h['islem_tipi'] == 'TAHSILAT': bugun_tahsil_edilen += h['tutar']
                elif cari_tip == 'TEDARIKCI':
                    if h['islem_tipi'] == 'ODEME': bugun_odenen += h['tutar']

            # Kalan Borç: Önceki bakiye + (bugünkü ALACAK/BORÇ hareketleri) - (bugünkü TAHSİLAT/ÖDEME hareketleri)
            # Bu, faturanın kendisi haricindeki gün içi hareketleri hesaba katar.
            kalan_borc = onceki_bakiye
            for h in bugun_hareketler:
                if cari_tip == 'MUSTERI':
                    if h['islem_tipi'] == 'ALACAK': kalan_borc += h['tutar']
                    elif h['islem_tipi'] == 'TAHSILAT': kalan_borc -= h['tutar']
                elif cari_tip == 'TEDARIKCI':
                    if h['islem_tipi'] == 'BORC': kalan_borc += h['tutar']
                    elif h['islem_tipi'] == 'ODEME': kalan_borc -= h['tutar']

            return {
                'onceki_bakiye': onceki_bakiye,
                'bugun_odenen': bugun_tahsil_edilen if cari_tip == 'MUSTERI' else bugun_odenen,
                'kalan_borc': kalan_borc
            }
        except Exception as e:
            logging.error(f"Cari bakiye anlık görüntü hatası: {e}", exc_info=True)
            return {
                'onceki_bakiye': 0.0,
                'bugun_odenen': 0.0,
                'kalan_borc': 0.0
            }

    def cari_ekstresi_pdf_olustur(self, cari_tip, cari_id, baslangic_tarih_str, bitis_tarih_str, dosya_yolu):
        conn_thread = None # DEĞİŞİKLİK BURADA BAŞLIYOR
        try:
            conn_thread = sqlite3.connect(self.db_name, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            conn_thread.row_factory = sqlite3.Row
            cursor_thread = conn_thread.cursor() # Yeni cursor

            # Sayfa kenar boşlukları ve temel boyutlar
            page_margin_x = 2.0 * cm
            page_margin_y = 2.0 * cm

            # 1. Cari bilgilerini çek
            cari_bilgi = None
            if cari_tip == 'MUSTERI':
                cursor_thread.execute("SELECT ad, musteri_kodu FROM musteriler WHERE id=?", (cari_id,)) # self.c yerine cursor_thread
                cari_bilgi = cursor_thread.fetchone()
                cari_adi = cari_bilgi['ad'] if cari_bilgi else "Bilinmiyor"
                cari_kodu = cari_bilgi['musteri_kodu'] if cari_bilgi else ""
            else: # TEDARIKCI
                cursor_thread.execute("SELECT ad, tedarikci_kodu FROM tedarikciler WHERE id=?", (cari_id,)) # self.c yerine cursor_thread
                cari_bilgi = cursor_thread.fetchone()
                cari_adi = cari_bilgi['ad'] if cari_bilgi else "Bilinmiyor"
                cari_kodu = cari_bilgi['tedarikci_kodu'] if cari_bilgi else ""

            rapor_baslik = f"Cari Hesap Ekstresi: {cari_adi} (Kod: {cari_kodu})"

            # 2. Ekstre verilerini çek
            # Devreden bakiye için de cursor_thread kullanın
            cursor_thread.execute("""
                SELECT islem_tipi, tutar FROM cari_hareketler
                WHERE cari_tip = ? AND cari_id = ? AND tarih < ?
            """, (cari_tip, cari_id, baslangic_tarih_str))
            hareketler_oncesi = cursor_thread.fetchall() # self.c yerine cursor_thread

            devreden_bakiye = 0.0
            for hareket in hareketler_oncesi:
                tutar = hareket['tutar'] or 0.0
                islem_tipi = hareket['islem_tipi']

                if cari_tip == 'MUSTERI':
                    if islem_tipi in ['BORC', 'ALACAK']:
                        devreden_bakiye += tutar
                    elif islem_tipi in ['TAHSILAT', 'ODEME']:
                        devreden_bakiye -= tutar
                elif cari_tip == 'TEDARIKCI':
                    if islem_tipi in ['BORC', 'ALACAK']:
                        devreden_bakiye += tutar
                    elif islem_tipi in ['TAHSILAT', 'ODEME']:
                        devreden_bakiye -= tutar

            # Ana hareketler listesi için cursor_thread kullanın
            query_hareketler = """
                SELECT
                    ch.id, ch.tarih, STRFTIME('%H:%M:%S', ch.olusturma_tarihi_saat) AS islem_saati,
                    ch.islem_tipi, ch.tutar, ch.aciklama, ch.referans_id, ch.referans_tip,
                    f.fatura_no, f.odeme_turu
                FROM cari_hareketler ch
                LEFT JOIN faturalar f ON ch.referans_id = f.id AND ch.referans_tip LIKE 'FATURA%'
                WHERE ch.cari_tip = ? AND ch.cari_id = ? AND ch.tarih >= ? AND ch.tarih <= ?
                ORDER BY ch.tarih ASC, ch.olusturma_tarihi_saat ASC
            """
            params_hareketler = [cari_tip, cari_id, baslangic_tarih_str, bitis_tarih_str]
            cursor_thread.execute(query_hareketler, params_hareketler) # self.c yerine cursor_thread
            hareketler_listesi = cursor_thread.fetchall()

            if not hareketler_listesi and devreden_bakiye == 0:
                return False, "PDF oluşturulacak cari ekstre verisi bulunamadı."

            # 3. PDF Dokümanı oluştur (SimpleDocTemplate)
            doc = SimpleDocTemplate(dosya_yolu, pagesize=A4,
                                    rightMargin=page_margin_x, leftMargin=page_margin_x,
                                    topMargin=page_margin_y, bottomMargin=page_margin_y)

            # Stil yönetimi
            styles = getSampleStyleSheet()
            styles.add(ParagraphStyle(name='TitleStyle', fontName=TURKISH_FONT_BOLD, fontSize=14, alignment=1))
            styles.add(ParagraphStyle(name='SubtitleStyle', fontName=TURKISH_FONT_NORMAL, fontSize=10, alignment=1))
            styles.add(ParagraphStyle(name='HeaderDetail', fontName=TURKISH_FONT_NORMAL, fontSize=8, alignment=0))
            styles.add(ParagraphStyle(name='TableHeading', fontName=TURKISH_FONT_BOLD, fontSize=7, alignment=1))
            styles.add(ParagraphStyle(name='TableNormal', fontName=TURKISH_FONT_NORMAL, fontSize=7, alignment=0))
            styles.add(ParagraphStyle(name='TableRight', fontName=TURKISH_FONT_NORMAL, fontSize=7, alignment=2))
            styles.add(ParagraphStyle(name='TableBold', fontName=TURKISH_FONT_BOLD, fontSize=7, alignment=0))

            # Story (PDF içeriği) oluştur
            story = []

            # Ana Başlıklar
            story.append(Paragraph("Cari Hesap Ekstresi", styles['TitleStyle']))
            story.append(Paragraph(rapor_baslik, styles['SubtitleStyle']))
            story.append(Paragraph(f"Tarih Aralığı: {baslangic_tarih_str} - {bitis_tarih_str}", styles['SubtitleStyle']))
            story.append(Spacer(0, 0.5*cm))

            # Şirket Bilgileri (Sol üstte)
            sirket_bilgileri_pdf_local = self.sirket_bilgilerini_yukle() # self.sirket_bilgilerini_yukle
            story.append(Paragraph(f"Şirket Adı: {sirket_bilgileri_pdf_local.get('sirket_adi', 'Şirket Adı')}", styles['HeaderDetail']))
            story.append(Paragraph(f"Adres: {sirket_bilgileri_pdf_local.get('sirket_adresi', '')}", styles['HeaderDetail']))
            story.append(Spacer(0, 0.5*cm))

            # Tablo Başlıkları
            table_headers = [
                Paragraph("ID", styles['TableHeading']), Paragraph("Tarih", styles['TableHeading']), Paragraph("Saat", styles['TableHeading']),
                Paragraph("İşlem Tipi", styles['TableHeading']), Paragraph("Referans", styles['TableHeading']), Paragraph("Ödeme Türü", styles['TableHeading']),
                Paragraph("Açıklama/Detay", styles['TableHeading']), Paragraph("Borç", styles['TableHeading']), Paragraph("Alacak", styles['TableHeading']),
                Paragraph("Bakiye", styles['TableHeading'])
            ]

            col_widths = [0.8*cm, 1.8*cm, 1.2*cm, 2.0*cm, 2.0*cm, 2.0*cm, 5.0*cm, 2.0*cm, 2.0*cm, 2.0*cm]
            table_data_rows = []

            # Devir bakiyesi satırı
            table_data_rows.append([
                Paragraph("", styles['TableNormal']), Paragraph("", styles['TableNormal']), Paragraph("", styles['TableNormal']),
                Paragraph("DEVİR", styles['TableBold']), Paragraph("", styles['TableNormal']), Paragraph("", styles['TableNormal']),
                Paragraph("", styles['TableNormal']), Paragraph("", styles['TableNormal']), Paragraph(self._format_currency(devreden_bakiye), styles['TableRight']),
                Paragraph(self._format_currency(devreden_bakiye), styles['TableRight'])
            ])

            bakiye_current = devreden_bakiye
            for hareket in hareketler_listesi:
                tarih_formatted = datetime.strptime(str(hareket['tarih']), '%Y-%m-%d').strftime('%d.%m.%Y')
                islem_saati = hareket['islem_saati'] if hareket['islem_saati'] else ''
                odeme_turu = hareket['odeme_turu'] if hareket['odeme_turu'] else ''
                aciklama = hareket['aciklama'] if hareket['aciklama'] else ''
                referans_display = hareket['fatura_no'] if hareket['referans_tip'] == 'FATURA' else (hareket['referans_tip'] if hareket['referans_tip'] else '')

                borc_val, alacak_val = "", ""
                if cari_tip == 'MUSTERI':
                    if hareket['islem_tipi'] == 'ALACAK' or hareket['referans_tip'] == 'FATURA' or hareket['referans_tip'] == 'VERESIYE_BORC_MANUEL':
                        alacak_val = self._format_currency(hareket['tutar'])
                        bakiye_current += hareket['tutar']
                    elif hareket['islem_tipi'] == 'TAHSILAT' or hareket['referans_tip'] == 'FATURA_SATIS_PESIN':
                        borc_val = self._format_currency(hareket['tutar'])
                        bakiye_current -= hareket['tutar']
                elif cari_tip == 'TEDARIKCI':
                    if hareket['islem_tipi'] == 'BORC' or hareket['referans_tip'] == 'FATURA' or hareket['referans_tip'] == 'VERESIYE_BORC_MANUEL':
                        alacak_val = self._format_currency(hareket['tutar'])
                        bakiye_current += hareket['tutar']
                    elif hareket['islem_tipi'] == 'ODEME' or hareket['referans_tip'] == 'FATURA_ALIS_PESIN':
                        borc_val = self._format_currency(hareket['tutar'])
                        bakiye_current -= hareket['tutar']

                table_data_rows.append([
                    Paragraph(str(hareket['id']), styles['TableNormal']), Paragraph(tarih_formatted, styles['TableNormal']), Paragraph(islem_saati, styles['TableNormal']),
                    Paragraph(hareket['islem_tipi'], styles['TableNormal']), Paragraph(referans_display, styles['TableNormal']), Paragraph(odeme_turu, styles['TableNormal']),
                    Paragraph(aciklama, styles['TableNormal']), Paragraph(borc_val, styles['TableRight']), Paragraph(alacak_val, styles['TableRight']),
                    Paragraph(self._format_currency(bakiye_current), styles['TableRight'])
                ])

            table = Table([table_headers] + table_data_rows, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#D0D0D0")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                ('ALIGN', (0,0), (-1,0), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), TURKISH_FONT_BOLD),
                ('FONTSIZE', (0,0), (-1,0), 7),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('TOPPADDING', (0,0), (-1,0), 6),

                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

                ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#EFEFEF")),
                ('FONTNAME', (0,1), (-1,1), TURKISH_FONT_BOLD),

                ('LEFTPADDING', (0,0), (-1,-1), 2),
                ('RIGHTPADDING', (0,0), (-1,-1), 2),
            ]))

            final_bakiye_row = Table([[
                Paragraph(f"Son Bakiye:", styles['TableBold']),
                Paragraph(self._format_currency(bakiye_current), styles['TableRight'])
            ]], [sum(col_widths) - 2*cm, 2*cm])

            def handle_page_footer(canvas, doc):
                canvas.saveState()
                canvas.setFont(TURKISH_FONT_NORMAL, 7)
                canvas.drawString(page_margin_x, page_margin_y / 2, "Bu ekstre On Muhasebe Programı ile oluşturulmuştur.")
                canvas.drawCentredString(A4[0] / 2, page_margin_y / 2, f"Sayfa {doc.page}")
                canvas.restoreState()

            story.append(table)
            story.append(Spacer(0, 0.5*cm))
            story.append(final_bakiye_row)

            doc.build(story, onFirstPage=handle_page_footer, onLaterPages=handle_page_footer)

            return True, f"Cari Ekstresi PDF olarak kaydedildi: {dosya_yolu}"

        except Exception as e:
            logging.error(f"Cari Ekstresi PDF oluşturulurken hata: {e}", exc_info=True)
            return False, f"Cari Ekstresi PDF oluşturulurken bir hata oluştu: {e}"
        finally: 
            if conn_thread:
                conn_thread.close()


    def fatura_pdf_olustur(self, fatura_id, dosya_yolu):
        """
        Belirtilen fatura ID'sine göre modern ve detaylı bir PDF fatura çıktısı oluşturur.
        İskonto detayları, cari bakiye, şirket bilgileri, imza alanı, sayfa numarası içerir.
        """
        try:
            fatura_ana = self.fatura_getir_by_id(fatura_id)
            if not fatura_ana:
                return False, "PDF oluşturulacak fatura bilgileri bulunamadı."


            _id, f_no, tarih_db, tip, c_id, toplam_kdv_haric_fatura_ana, toplam_kdv_dahil_fatura_ana, odeme_turu_db, misafir_adi_db, kb_id_db, \
            olusturma_tarihi_saat, olusturan_kullanici_id, son_guncelleme_tarihi_saat, \
            son_guncelleyen_kullanici_id, fatura_notlari_db, vade_tarihi_db, genel_iskonto_tipi_db, genel_iskonto_degeri_db = fatura_ana

            fatura_kalemleri_db = self.fatura_detay_al(fatura_id)

            # --- Şirket Bilgilerini Çekme ---
            sirket_bilgileri = self.sirket_bilgilerini_yukle()

            # --- Cari Bilgilerini Çekme ve Hazırlama ---
            is_perakende_satis_pdf = (str(c_id) == str(self.perakende_musteri_id) and tip == 'SATIŞ')
            cari_bilgileri_pdf = {}
            cari_tip_for_db_query = 'MUSTERI' if tip == 'SATIŞ' else 'TEDARIKCI'

            if is_perakende_satis_pdf:
                cari_adi_pdf = "Perakende Satış Müşterisi"
                if misafir_adi_db: cari_adi_pdf += f" (Misafir: {misafir_adi_db})"
                cari_bilgileri_pdf = {
                    "ad": cari_adi_pdf, "adres": "N/A", "telefon": "N/A",
                    "vergi_dairesi": "N/A", "vergi_no": "N/A"
                }
            else:
                if tip == 'SATIŞ': cari_db = self.musteri_getir_by_id(c_id)
                else: cari_db = self.tedarikci_getir_by_id(c_id)
                if cari_db:
                    cari_bilgileri_pdf = {
                        "ad": cari_db['ad'], "adres": cari_db['adres'] or "N/A", "telefon": cari_db['telefon'] or "N/A",
                        "vergi_dairesi": cari_db['vergi_dairesi'] or "N/A", "vergi_no": cari_db['vergi_no'] or "N/A"
                    }
                else:
                    cari_bilgileri_pdf = {"ad": "Bilinmeyen Cari", "adres": "N/A", "telefon": "N/A", "vergi_dairesi": "N/A", "vergi_no": "N/A"}

            # --- Kasa/Banka Bilgilerini Çekme ---
            kb_bilgi = None
            if kb_id_db:
                kb_bilgi = self.kasa_banka_getir_by_id(kb_id_db)

            # --- Cari Bakiye Bilgilerini Çekme (Anlık Görüntü) ---
            # Faturanın kesildiği tarihteki bakiye durumunu almak için
            cari_bakiye_snapshot = self._get_cari_bakiye_snapshot(c_id, cari_tip_for_db_query, tarih_db)


            # --- Kullanıcı Adlarını Çekme ---
            kullanicilar_map = {k['id']: k['kullanici_adi'] for k in self.kullanici_listele()}
            olusturan_adi = kullanicilar_map.get(olusturan_kullanici_id, "Bilinmiyor")
            son_guncelleyen_adi = kullanicilar_map.get(son_guncelleyen_kullanici_id, "Bilinmiyor")


            # --- PDF Oluşturma Başlangıcı ---
            c = rp_canvas.Canvas(dosya_yolu, pagesize=A4)
            width, height = A4 # Sayfa boyutları
            page_margin_x = 30 # Yatay kenar boşluğu
            page_margin_top = 50 # Üst kenar boşluğu
            page_margin_bottom_min = 100 # Alt kenar boşluğu (toplamlar ve dipnotlar için minimum)

            # Stil sözlüğünü güncelle
            styles = getSampleStyleSheet()
            styles.add(ParagraphStyle(name='TurkishNormal', fontName=TURKISH_FONT_NORMAL, fontSize=9, leading=11))
            styles.add(ParagraphStyle(name='TurkishBold', fontName=TURKISH_FONT_BOLD, fontSize=9, leading=11))
            styles.add(ParagraphStyle(name='TurkishNormalSmall', fontName=TURKISH_FONT_NORMAL, fontSize=7, leading=9))
            styles.add(ParagraphStyle(name='TurkishBoldSmall', fontName=TURKISH_FONT_BOLD, fontSize=7, leading=9))
            styles.add(ParagraphStyle(name='TitleStyle', fontName=TURKISH_FONT_BOLD, fontSize=14, alignment=1)) # CENTER
            styles.add(ParagraphStyle(name='HeaderDetail', fontName=TURKISH_FONT_NORMAL, fontSize=10, alignment=2)) # RIGHT
            styles.add(ParagraphStyle(name='Footer', fontName=TURKISH_FONT_NORMAL, fontSize=7, alignment=1)) # CENTER

            # Ortak TableStyle objesi tanımlaması - ARKA PLAN RENGİ VE SATIR STİLLERİ DÜZELTİLDİ
            kalem_table_style = TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F0F0F0")), # Açık gri arka plan
                ('TEXTCOLOR', (0,0), (-1,0), colors.black), # Başlık metin rengi siyah
                ('ALIGN', (0,0), (-1,0), 'CENTER'), # Başlık hizalaması
                ('FONTNAME', (0,0), (-1,0), TURKISH_FONT_BOLD),
                ('FONTSIZE', (0,0), (-1,0), 7),
                ('BOTTOMPADDING', (0,0), (-1,0), 3), # Başlık altında boşluğu azalttık
                ('TOPPADDING', (0,0), (-1,0), 3),    # Başlık üstünde boşluğu azalttık
                ('LINEBELOW', (0,0), (-1,0), 0.5, colors.HexColor("#D0D0D0")), # Başlık altında ince çizgi

                # Veri satırları
                ('BACKGROUND', (0,1), (-1,-1), colors.white), # Tüm veri satırları beyaz arka plan
                ('TEXTCOLOR', (0,1), (-1,-1), colors.black), # Veri metin rengi siyah
                ('ALIGN', (0,1), (0,-1), 'CENTER'), # Sıra no ortala
                ('ALIGN', (1,1), (1,-1), 'LEFT'), # Ürünler sola yaslı
                ('ALIGN', (2,1), (-1,-1), 'RIGHT'), # Diğer sayısal değerler sağa yaslı
                ('FONTNAME', (0,1), (-1,-1), TURKISH_FONT_NORMAL),
                ('FONTSIZE', (0,1), (-1,-1), 7),
                ('BOTTOMPADDING', (0,1), (-1,-1), 2), # Veri satırları altında boşluğu azalttık
                ('TOPPADDING', (0,1), (-1,-1), 2),    # Veri satırları üstünde boşluğu azalttık
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F0F0F0")]), # Zebra deseni

                ('GRID', (0,0), (-1,-1), 0, colors.white), # Grid çizgilerini kaldır
            ])

            # PDF'e çizmeyi kolaylaştırmak için ana döngü fonksiyonu
            # table_header_row: Tablo başlık satırı (Paragraph objeleri içeren liste)
            # table_data_rows_on_page: Bu sayfada çizilecek kalem veri satırları (Paragraph objeleri içeren listeler)
            def draw_page_content(canvas_obj, current_page_num, total_page_num, header_start_y, table_header_row, table_data_rows_on_page):
                canvas_obj.setFillColor(colors.black)

                # Sol Üst: Şirket Bilgileri
                textobject = canvas_obj.beginText(page_margin_x, header_start_y)
                textobject.setFont(TURKISH_FONT_BOLD, 12)
                textobject.textLine(sirket_bilgileri.get("sirket_adi", "ŞİRKET ADI"))
                textobject.setFont(TURKISH_FONT_NORMAL, 8)
                s_adres_parcalari = sirket_bilgileri.get("sirket_adresi", "").split(',')
                for parca in s_adres_parcalari:
                    textobject.textLine(parca.strip())
                textobject.textLine(f"Tel: {sirket_bilgileri.get('sirket_telefonu', '')}")
                textobject.textLine(f"Email: {sirket_bilgileri.get('sirket_email', '')}")
                textobject.textLine(f"VD: {sirket_bilgileri.get('sirket_vergi_dairesi', '')} / VN: {sirket_bilgileri.get('sirket_vergi_no', '')}")
                canvas_obj.drawText(textobject)

                # Sağ Üst: Fatura Bilgileri
                canvas_obj.setFont(TURKISH_FONT_BOLD, 10) # Örnekteki gibi daha küçük font
                canvas_obj.drawRightString(width - page_margin_x, height - 50, "Satış Kodu") # Örnekteki "Satış Kodu"
                canvas_obj.setFont(TURKISH_FONT_NORMAL, 10)
                canvas_obj.drawRightString(width - page_margin_x, height - 65, f_no) # Fatura No (Örnekteki "2507020015-CT")
                canvas_obj.setFont(TURKISH_FONT_BOLD, 10) # Örnekteki gibi bold isim
                canvas_obj.drawRightString(width - page_margin_x, height - 80, cari_bilgileri_pdf["ad"].split('(')[0].strip()) # Sadece isim kısmı
                canvas_obj.setFont(TURKISH_FONT_NORMAL, 9)
                try: formatted_tarih = datetime.strptime(tarih_db, '%Y-%m-%d').strftime('%d/%m/%Y %H:%M:%S') # Saat de eklendi
                except: formatted_tarih = tarih_db
                canvas_obj.drawRightString(width - page_margin_x, height - 95, f"Tarih: {formatted_tarih}")
                canvas_obj.drawRightString(width - page_margin_x, height - 110, f"Ödeme Tipi: {odeme_turu_db if odeme_turu_db else '-'}")

                # İmza alanının hemen altında bir yerde oluşturulma bilgisi
                canvas_obj.setFont(TURKISH_FONT_NORMAL, 7)
                canvas_obj.drawString(width - page_margin_x - 535, height - 130, f"Oluşturan: {olusturan_adi}")
                if son_guncelleyen_adi and son_guncelleyen_adi != olusturan_adi:
                    canvas_obj.drawString(width - page_margin_x - 535, height - 140, f"Güncelleyen: {son_guncelleyen_adi}")

                # Ortalanmış Logo
                logo_path = sirket_bilgileri.get("sirket_logo_yolu", "")
                if logo_path and os.path.exists(logo_path):
                    try:
                        img = Image.open(logo_path)
                        aspect_ratio = img.width / img.height
                        desired_height_logo = 40
                        desired_width_logo = desired_height_logo * aspect_ratio
                        x_pos_logo = (width / 2) - (desired_width_logo / 2)
                        y_pos_logo = height - 70 # Örnekteki gibi daha aşağıda ve ortalanmış
                        canvas_obj.drawImage(logo_path, x_pos_logo, y_pos_logo - desired_height_logo / 2,
                                             width=desired_width_logo, height=desired_height_logo, preserveAspectRatio=True)
                    except Exception as e_logo:
                        logging.warning(f"Logo çizim hatası: {e_logo}")

                # --- Cari Bilgileri Alanı (Örnekteki gibi kutu dışı) ---
                # Fatura bilgisinin hemen altından başlayacak, örnekte "Sayın" yok
                current_y_for_blocks = height - 150 # Ortak Y koordinatı
                canvas_obj.setFont(TURKISH_FONT_BOLD, 9) # Örnekteki gibi daha küçük font
                # Cari Bilgileri kısmının başlığı yok gibi, direkt "Müşteri Bilgileri" altına alınmış.
                # Şimdilik, örnekteki gibi sadece bilgileri yerleştirelim.

                # Cari bilgi kutusunu kaldırdık, sadece bir çizgiyle ayıracağız.
                canvas_obj.line(page_margin_x, current_y_for_blocks, width - page_margin_x, current_y_for_blocks) 
                current_y_for_blocks -= 15 # Çizgi sonrası boşluk

                current_table_y_pos_in_draw = current_y_for_blocks # Kalemler tablosunun başlangıç Y konumu

                # Tablo başlık satırını çiz
                header_table = Table([table_header_row], colWidths=kalem_col_widths)
                header_table.setStyle(kalem_table_style) # Ortak TableStyle objesini kullanıyoruz
                header_table.wrapOn(canvas_obj, width - 2 * page_margin_x, height)
                header_table.drawOn(canvas_obj, page_margin_x, current_table_y_pos_in_draw)
                current_table_y_pos_in_draw -= header_table._height # Başlık sonrası boşluk

                # Kalemleri çiz
                for row_data in table_data_rows_on_page:
                    row_obj = Table([row_data], colWidths=kalem_col_widths)
                    row_obj.setStyle(kalem_table_style) # Ortak kalem stilini uygula
                    row_obj.wrapOn(canvas_obj, width - 2 * page_margin_x, height)

                    if current_table_y_pos_in_draw - row_obj._height < page_margin_bottom_min:
                        return False, current_table_y_pos_in_draw

                    row_obj.drawOn(canvas_obj, page_margin_x, current_table_y_pos_in_draw - row_obj._height)
                    current_table_y_pos_in_draw -= row_obj._height

                return True, current_table_y_pos_in_draw # Başarılı ve kalan Y pozisyonunu döndür

            # --- Ana PDF Oluşturma ve Sayfalama Döngüsü ---
            c = rp_canvas.Canvas(dosya_yolu, pagesize=A4)

            kalem_data_for_table = [] # Sadece veri satırları (başlık hariç)

            # Yeni sütun genişlikleri, örnek PDF'e göre ayarlandı.
            # Metinlerin sığması için Paragraf objelerini kullanıyoruz, bu yüzden wrapOn metodu işe yarayacak.
            kalem_col_widths = [
                0.6 * cm,   # Sıra
                7.8 * cm,   # Ürünler (Ürün Kodu + Adı) - Geniş tutuldu
                1.0* cm,   # Miktar
                2.0 * cm,   # Birim Fiyat (TL 75,00 gibi)
                1.0 * cm,   # KDV%
                1.35 * cm,   # İsk.1(%)
                1.35 * cm,   # İsk.2(%)
                1.5 * cm,   # İsk Tutarı
                2.6 * cm    # Tutar (KDV Dahil) - En sağda
            ]
            # Toplam genişlik: 0.8+7.0+1.5+2.0+1.0+1.0+1.0+2.0+2.5 = 18.8 cm. Bu A4'e rahat sığar.


            # Fatura kalemlerini topla ve formatla
            sira_no = 1
            for kalem in fatura_kalemleri_db:
                miktar_gosterim = f"{kalem['miktar']:.2f}".rstrip('0').rstrip('.')
                
                # İskontolu Birim Fiyat (KDV Dahil) Hesapla
                iskontolu_birim_fiyat_kdv_dahil = (kalem['kalem_toplam_kdv_dahil'] / kalem['miktar']) if kalem['miktar'] != 0 else 0.0

                # Uygulanan Kalem İskonto Tutarı (KDV Dahil) Hesapla
                original_birim_fiyat_kdv_dahil_kalem = kalem['birim_fiyat'] * (1 + kalem['kdv_orani'] / 100) # orijinal kdv hariç * (1+kdv)
                uygulanan_kalem_iskonto_tutari = (original_birim_fiyat_kdv_dahil_kalem - iskontolu_birim_fiyat_kdv_dahil) * kalem['miktar']
                
                # "Ürünler" sütununa ürün kodu ve adını birlikte alıyoruz (örnekteki gibi)
                urunler_text = f"{kalem['urun_adi']}\n({kalem['urun_kodu']})"


                kalem_data_for_table.append([
                    Paragraph(str(sira_no), styles['TurkishNormalSmall']),
                    Paragraph(urunler_text, styles['TurkishNormalSmall']), # Ürünler sütunu
                    Paragraph(miktar_gosterim, styles['TurkishNormalSmall']),
                    Paragraph(self._format_currency(iskontolu_birim_fiyat_kdv_dahil), styles['TurkishNormalSmall']),
                    Paragraph(f"{kalem['kdv_orani']:.0f}%", styles['TurkishNormalSmall']),
                    Paragraph(f"{kalem['iskonto_yuzde_1']:.2f}".rstrip('0').rstrip('.') if kalem['iskonto_yuzde_1'] is not None else "0", styles['TurkishNormalSmall']),
                    Paragraph(f"{kalem['iskonto_yuzde_2']:.2f}".rstrip('0').rstrip('.') if kalem['iskonto_yuzde_2'] is not None else "0", styles['TurkishNormalSmall']),
                    Paragraph(self._format_currency(uygulanan_kalem_iskonto_tutari), styles['TurkishNormalSmall']),
                    Paragraph(self._format_currency(kalem['kalem_toplam_kdv_dahil']), styles['TurkishNormalSmall'])
                ])
                sira_no += 1

            # Tablo başlığı (sütunlar "Ürün Kodu" ve "Ürün Adı" yerine "Ürünler" olacak şekilde güncellendi)
            kalem_table_header = [
                Paragraph("#", styles['TurkishBoldSmall']),
                Paragraph("Ürünler", styles['TurkishBoldSmall']),
                Paragraph("Mik", styles['TurkishBoldSmall']),
                Paragraph("B.Fiyat", styles['TurkishBoldSmall']),
                Paragraph("KDV%", styles['TurkishBoldSmall']),
                Paragraph("İsk.1(%)", styles['TurkishBoldSmall']),
                Paragraph("İsk.2(%)", styles['TurkishBoldSmall']),
                Paragraph("İsk Tutarı", styles['TurkishBoldSmall']),
                Paragraph("Tutar (KDV Dahil)", styles['TurkishBoldSmall'])
            ]

            total_data_rows_count = len(kalem_data_for_table)

            # Sayfa hesaplamaları
            approx_row_height = 13 # Tek bir veri satırının yaklaşık yüksekliği (point)
            available_table_height_for_rows_per_page = height - page_margin_top - 180 - page_margin_bottom_min # Üst boşluklar, cari bilgiler ve alt boşluklar hariç
            max_rows_per_page = int(available_table_height_for_rows_per_page / approx_row_height)

            if max_rows_per_page <= 0: # En az 1 satır sığmalı
                max_rows_per_page = 1

            total_pages = (total_data_rows_count + max_rows_per_page -1) // max_rows_per_page
            if total_pages == 0 and total_data_rows_count == 0:
                total_pages = 1 # Hiç kalem olmasa bile 1 sayfa olmalı


            current_row_idx_for_drawing = 0
            page_count = 0
            
            # Sayfa döngüsü
            while current_row_idx_for_drawing <= total_data_rows_count:
                page_count += 1

                if page_count > 1: # İlk sayfa dışındaki tüm sayfalarda yeni sayfa başlat
                    c.showPage()

                start_data_idx_for_page = current_row_idx_for_drawing
                end_data_idx_for_page = min(start_data_idx_for_page + max_rows_per_page, total_data_rows_count)
                
                rows_to_draw_on_this_page = kalem_data_for_table[start_data_idx_for_page : end_data_idx_for_page]

                # draw_page_content'ı çağır
                # last_y_pos_on_page değişkeni artık kalemlerin altındaki boşluğun kontrolünde kullanılacak.
                success_drawing, last_y_pos_on_page = draw_page_content(
                    c,
                    page_count,
                    total_pages,
                    height - page_margin_top, # Header'ın başlangıç Y konumu
                    kalem_table_header, # Başlık satırını gönder
                    rows_to_draw_on_this_page # Bu sayfadaki kalem veri satırlarını gönder
                )

                if not success_drawing:
                    if page_count == 1 and len(kalem_data_for_table) == 0:
                        c.setFont(TURKISH_FONT_NORMAL, 9)
                        c.drawCentredString(width/2, height/2, "Bu faturada herhangi bir kalem bulunmamaktadır.")
                    current_row_idx_for_drawing = total_data_rows_count + 1
                    break
                elif total_data_rows_count > 0 and len(rows_to_draw_on_this_page) == 0 and page_count > 1:
                    break
                elif total_data_rows_count == 0 and page_count == 1:
                    break

                current_row_idx_for_drawing += len(rows_to_draw_on_this_page)

                if current_row_idx_for_drawing >= total_data_rows_count and total_data_rows_count > 0:
                    break
                elif total_data_rows_count == 0 and page_count == 1:
                    break

            # --- Alt Bilgiler (Footer) Alanı - Sadece son sayfada çizilir ---
            # Hesaplanan genel iskonto tutarı (faturanın kendi değeri)
            genel_iskonto_uygulanan_tutari_fatura = 0.0
            if genel_iskonto_tipi_db == 'YUZDE' and genel_iskonto_degeri_db > 0:
                genel_iskonto_uygulanan_tutari_fatura = toplam_kdv_haric_fatura_ana * (genel_iskonto_degeri_db / 100)
            elif genel_iskonto_tipi_db == 'TUTAR' and genel_iskonto_degeri_db > 0:
                genel_iskonto_uygulanan_tutari_fatura = genel_iskonto_degeri_db

            # Toplamlar
            total_block_x_label = page_margin_x + 300
            total_block_x_value = width - page_margin_x

            c.setFont(TURKISH_FONT_NORMAL, 9)
            c.drawString(total_block_x_label, 85, "Toplam KDV Hariç:")
            c.drawString(total_block_x_label, 70, "Toplam KDV:")

            if genel_iskonto_uygulanan_tutari_fatura > 0:
                c.drawString(total_block_x_label, 55, "Genel İskonto:")
            
            c.setFont(TURKISH_FONT_BOLD, 10)
            c.drawString(total_block_x_label, 40, "GENEL TOPLAM:")


            c.setFont(TURKISH_FONT_NORMAL, 9)
            c.drawRightString(total_block_x_value, 85, self._format_currency(toplam_kdv_haric_fatura_ana))
            c.drawRightString(total_block_x_value, 70, self._format_currency(toplam_kdv_dahil_fatura_ana - toplam_kdv_haric_fatura_ana))
            if genel_iskonto_uygulanan_tutari_fatura > 0:
                c.drawRightString(total_block_x_value, 55, self._format_currency(genel_iskonto_uygulanan_tutari_fatura))
            
            c.setFont(TURKISH_FONT_BOLD, 10)
            c.drawRightString(total_block_x_value, 40, self._format_currency(toplam_kdv_dahil_fatura_ana))


            # Müşteri Bilgileri (Daha yukarıya ve sade)
            left_bottom_y_start_musteri = 85 # Y koordinatını yukarı çektik
            c.setFont(TURKISH_FONT_BOLD, 9)
            c.drawString(page_margin_x, left_bottom_y_start_musteri, "Müşteri Bilgileri")
            c.setFont(TURKISH_FONT_NORMAL, 8)
            c.drawString(page_margin_x, left_bottom_y_start_musteri - 12, f"Müşteri: {cari_bilgileri_pdf['ad']}")
            c.drawString(page_margin_x, left_bottom_y_start_musteri - 24, f"Önceki bakiye: {self._format_currency(cari_bakiye_snapshot['onceki_bakiye'])}")
            c.drawString(page_margin_x, left_bottom_y_start_musteri - 36, f"Bugün yapılan {'ödeme' if cari_tip_for_db_query == 'TEDARIKCI' else 'tahsilat'}: {self._format_currency(cari_bakiye_snapshot['bugun_odenen'])}")
            c.drawString(page_margin_x, left_bottom_y_start_musteri - 48, f"Kalan borç: {self._format_currency(cari_bakiye_snapshot['kalan_borc'])}")
            
            # Notlar / Açıklamalar (Müşteri bilgilerinin altına veya yanına konumlandırılabilir)
            if fatura_notlari_db:
                c.setFont(TURKISH_FONT_BOLD, 9)
                c.drawString(page_margin_x + 200, left_bottom_y_start_musteri, "Açıklamalar") # Yana kaydırdım
                notes_paragraph = Paragraph(fatura_notlari_db, styles['TurkishNormalSmall'])
                notes_paragraph.wrapOn(c, (width / 2) - page_margin_x - 20, 50)
                notes_paragraph.drawOn(c, page_margin_x + 200, left_bottom_y_start_musteri - 12 - notes_paragraph._height)

            # Banka Bilgileri (Açıklamaların altına veya yanına)
            if sirket_bilgileri.get('sirket_banka_adi') and sirket_bilgileri.get('sirket_iban'):
                c.setFont(TURKISH_FONT_BOLD, 9)
                c.drawString(page_margin_x + 400, left_bottom_y_start_musteri, "Banka Bilgileri") # En sağa hizala
                bank_info_text = f"Banka Adı: {sirket_bilgileri.get('sirket_banka_adi', 'N/A')}\nIBAN: {sirket_bilgileri.get('sirket_iban', 'N/A')}"
                bank_info_paragraph = Paragraph(bank_info_text, styles['TurkishNormalSmall'])
                bank_info_paragraph.wrapOn(c, (width / 2) - page_margin_x, 30)
                bank_info_paragraph.drawOn(c, page_margin_x + 400, left_bottom_y_start_musteri - 12 - bank_info_paragraph._height)


            # "Tanzim Eden" ve çizgisi kaldırıldı.

            # Dipnot
            c.setFont(TURKISH_FONT_NORMAL, 7)
            c.drawCentredString(width/2, 20, "Bu fatura Çınar Yapı Ön Muhasebe Programı ile oluşturulmuştur. Elektronik ortamda hazırlanmıştır.")


            c.save()
            return True, f"Fatura başarıyla PDF olarak kaydedildi: {dosya_yolu}"

        except Exception as e:
            logging.error(f"PDF oluşturulurken beklenmeyen bir hata oluştu: {e}\nDetaylar:\n{traceback.format_exc()}")
            return False, f"PDF oluşturulurken beklenmeyen bir hata oluştu: {e}\nDetaylar için log dosyasına bakınız."

    def tarihsel_satis_raporu_verilerini_al(self, baslangic_tarih_str, bitis_tarih_str):
        """Belirtilen tarih aralığındaki satış faturalarını ve kalemlerini getirir."""
        query = """
            SELECT 
                f.fatura_no, f.tarih, 
                CASE 
                    WHEN f.cari_id = ? THEN IFNULL(f.misafir_adi, 'Perakende Satış')
                    ELSE m.ad 
                END AS musteri_adi, 
                s.urun_kodu, s.urun_adi, 
                fk.miktar, fk.birim_fiyat, fk.kdv_orani, fk.kdv_tutari, 
                fk.kalem_toplam_kdv_haric, fk.kalem_toplam_kdv_dahil
            FROM faturalar f
            JOIN fatura_kalemleri fk ON f.id = fk.fatura_id
            JOIN tbl_stoklar s ON fk.urun_id = s.id
            LEFT JOIN musteriler m ON f.cari_id = m.id AND f.cari_id != ? -- Perakende olmayanlar için join
            WHERE f.tip = 'SATIŞ' AND f.tarih BETWEEN ? AND ?
            ORDER BY f.tarih, f.fatura_no, s.urun_adi
        """
        perakende_id_param = self.perakende_musteri_id if self.perakende_musteri_id is not None else -999
        params = (perakende_id_param, perakende_id_param, baslangic_tarih_str, bitis_tarih_str)
        self.c.execute(query, params)
        return self.c.fetchall()

    def tarihsel_satis_raporu_excel_olustur(self, rapor_verileri, dosya_yolu, bas_t, bit_t):
        try:
            if not rapor_verileri:
                return False, "Belirtilen tarih aralığında raporlanacak satış verisi bulunamadı."

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = f"Satis_Raporu_{bas_t}_to_{bit_t}"

            headers = [
                "Fatura No", "Tarih", "Müşteri Adı", "Ürün Kodu", "Ürün Adı",
                "Miktar", "Birim Fiyat (TL)", "KDV Oranı (%)", "KDV Tutarı (TL)",
                "Toplam (KDV Hariç TL)", "Toplam (KDV Dahil TL)"
            ]
            ws.append(headers)

            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid") # Koyu Mavi
            for col_idx, header_text in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center")
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = max(len(header_text) + 2, 15)

            for row_data in rapor_verileri:
                ws.append(list(row_data)) # Gelen veri zaten tuple listesi

            # Sayısal sütunlara formatlama
            for row_idx, row_cells in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row), start=2):
                # Miktar (F sütunu, index 5)
                if row_cells[5].value is not None: row_cells[5].number_format = '#,##0.00'
                # Birim Fiyat (G sütunu, index 6)
                if row_cells[6].value is not None: row_cells[6].number_format = '#,##0.00₺'
                # KDV Oranı (H sütunu, index 7)
                if row_cells[7].value is not None: row_cells[7].number_format = '0"%"'
                # KDV Tutarı (I sütunu, index 8)
                if row_cells[8].value is not None: row_cells[8].number_format = '#,##0.00₺'
                # Toplam KDV Hariç (J sütunu, index 9)
                if row_cells[9].value is not None: row_cells[9].number_format = '#,##0.00₺'
                # Toplam KDV Dahil (K sütunu, index 10)
                if row_cells[10].value is not None: row_cells[10].number_format = '#,##0.00₺'
            
            ws.freeze_panes = 'A2' # Başlık satırını dondur

            wb.save(dosya_yolu)
            return True
        except Exception as e:
            traceback.print_exc()
            return False, f"Satış raporu Excel'e aktarılırken bir hata oluştu:\n{e}"

    def tarihsel_satis_raporu_pdf_olustur(self, rapor_verileri, dosya_yolu, bas_t, bit_t):
        try:
            if not rapor_verileri:
                return False, "Belirtilen tarih aralığında raporlanacak satış verisi bulunamadı."

            c = rp_canvas.Canvas(dosya_yolu, pagesize=landscape(A4)) # Yatay A4
            width, height = landscape(A4)

            styles = getSampleStyleSheet()
            styleN = styles['Normal']
            styleN.fontName = TURKISH_FONT_NORMAL
            styleN.fontSize = 7 # Daha küçük font
            styleH = styles['Normal']
            styleH.fontName = TURKISH_FONT_BOLD
            styleH.fontSize = 7
            styleH.alignment = 1 # TA_CENTER
            styleRight = styles['Normal']
            styleRight.fontName = TURKISH_FONT_NORMAL
            styleRight.fontSize = 7
            styleRight.alignment = 2 # TA_RIGHT

            # Başlık
            c.setFont(TURKISH_FONT_BOLD, 14)
            c.drawCentredString(width/2, height - 40, f"Satış Raporu ({bas_t} - {bit_t})")
            c.setFont(TURKISH_FONT_NORMAL, 9)
            c.drawCentredString(width/2, height - 55, self.sirket_bilgileri.get("sirket_adi", ""))
            y_pos = height - 80

            data = [
                [Paragraph(h, styleH) for h in ["F.No", "Tarih", "Müşteri", "Ü.Kodu", "Ürün Adı", "Mik.", "B.Fyt", "KDV%", "KDV Tut.", "Tutar(Har.)", "Tutar(Dah.)"]]
            ]
            
            genel_toplam_kdv_haric_rapor = 0
            genel_toplam_kdv_tutar_rapor = 0
            genel_toplam_kdv_dahil_rapor = 0

            for item in rapor_verileri:
                # item: (f_no, tarih, musteri, u_kodu, u_adi, mik, bfyt, kdvo, kdvt, tkh, tkd)
                tarih_f = datetime.strptime(item[1], '%Y-%m-%d').strftime('%d.%m.%y') if item[1] else '-'
                miktar_f = f"{item[5]:.2f}".rstrip('0').rstrip('.') if isinstance(item[5], float) else str(item[5])
                data.append([
                    Paragraph(str(item[0]), styleN), Paragraph(tarih_f, styleN), Paragraph(str(item[2])[:25], styleN), # Müşteri adı kısaltılabilir
                    Paragraph(str(item[3]), styleN), Paragraph(str(item[4])[:30], styleN), # Ürün adı kısaltılabilir
                    Paragraph(miktar_f, styleRight), Paragraph(self._format_currency(item[6]), styleRight),
                    Paragraph(f"{item[7]:.0f}%", styleRight), Paragraph(self._format_currency(item[8]), styleRight),
                    Paragraph(self._format_currency(item[9]), styleRight), Paragraph(self._format_currency(item[10]), styleRight)
                ])
                genel_toplam_kdv_haric_rapor += item[9]
                genel_toplam_kdv_tutar_rapor += item[8]
                genel_toplam_kdv_dahil_rapor += item[10]

            col_widths = [1.8*cm, 1.5*cm, 4*cm, 2*cm, 5*cm, 1.2*cm, 2*cm, 1.2*cm, 2*cm, 2.3*cm, 2.3*cm]
            
            # Sayfa başına satır sayısı tahmini (deneme yanılma ile ayarlanabilir)
            rows_per_page = 25 
            num_pages = (len(data) -1 + rows_per_page - 1) // rows_per_page # Başlık hariç
            if num_pages == 0: num_pages = 1


            for page_num in range(num_pages):
                start_row = page_num * rows_per_page + (1 if page_num > 0 else 0) # İlk sayfada başlık var
                end_row = min((page_num + 1) * rows_per_page, len(data) -1 )
                
                page_data = [data[0]] + data[start_row+1 : end_row+1] # Başlığı her sayfaya ekle, sonra o sayfanın verilerini
                if not page_data[1:]: # Eğer veri kalmadıysa (sadece başlık)
                    if page_num > 0 : break # İlk sayfa değilse ve veri yoksa bitir
                    elif not data[1:]: # İlk sayfa ve hiç veri yoksa (sadece başlık)
                         page_data.append(["Veri Yok"]*len(col_widths)) # Boş satır ekle


                table = Table(page_data, colWidths=col_widths)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1F4E78")),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('ALIGN', (2,1), (2,-1), 'LEFT'), # Müşteri Adı
                    ('ALIGN', (4,1), (4,-1), 'LEFT'), # Ürün Adı
                    ('ALIGN', (5,1), (-1,-1), 'RIGHT'), # Sayısal
                    ('FONTNAME', (0,0), (-1,-1), TURKISH_FONT_NORMAL),
                    ('FONTNAME', (0,0), (-1,0), TURKISH_FONT_BOLD),
                    ('FONTSIZE', (0,0), (-1,-1), 7),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ]))
                
                table.wrapOn(c, width - 80, height - 100)
                table_h = table._height
                table.drawOn(c, 40, y_pos - table_h)
                
                # Sayfa Numarası
                c.setFont(TURKISH_FONT_NORMAL, 8)
                c.drawRightString(width - 40, 30, f"Sayfa {page_num + 1} / {num_pages}")
                
                if page_num < num_pages - 1:
                    c.showPage()
                    c.setFont(TURKISH_FONT_BOLD, 14) # Yeni sayfada başlık fontunu ayarla
                    c.drawCentredString(width/2, height - 40, f"Satış Raporu ({bas_t} - {bit_t}) - Devam")
                    c.setFont(TURKISH_FONT_NORMAL, 9)
                    c.drawCentredString(width/2, height - 55, self.sirket_bilgileri.get("sirket_adi", ""))
                    y_pos = height - 80
            
            # Rapor Sonu Toplamları (Son Sayfaya)
            y_pos_summary = y_pos - table_h - 20 # Son tablonun altına
            if y_pos_summary < 80 : # Eğer yer kalmadıysa yeni sayfa açıp oraya yaz
                c.showPage()
                c.setFont(TURKISH_FONT_BOLD, 14)
                c.drawCentredString(width/2, height - 40, f"Satış Raporu ({bas_t} - {bit_t}) - Toplamlar")
                y_pos_summary = height - 70
                c.setFont(TURKISH_FONT_NORMAL, 8) # Sayfa numarasını da ekleyelim
                c.drawRightString(width - 40, 30, f"Sayfa {num_pages} / {num_pages}")


            c.setFont(TURKISH_FONT_BOLD, 9)
            c.drawRightString(width - 50, y_pos_summary, f"Genel Toplam (KDV Hariç): {self._format_currency(genel_toplam_kdv_haric_rapor)}")
            y_pos_summary -= 15
            c.drawRightString(width - 50, y_pos_summary, f"Genel Toplam KDV: {self._format_currency(genel_toplam_kdv_tutar_rapor)}")
            y_pos_summary -= 15
            c.setFont(TURKISH_FONT_BOLD, 10)
            c.drawRightString(width - 50, y_pos_summary, f"Genel Toplam (KDV Dahil): {self._format_currency(genel_toplam_kdv_dahil_rapor)}")

            c.save()
        except Exception as e:
            return False, f"Satış raporu PDF oluşturulurken hata: {e}"

    def __del__(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception as e:
                print(f"Veritabanı bağlantısı kapatılırken hata: {e}")

    def kasa_banka_ekle(self, hesap_adi, hesap_no, bakiye, para_birimi, tip, acilis_tarihi=None, banka_adi=None, sube_adi=None, varsayilan_odeme_turu=None):
        if not (hesap_adi and tip):
            return False, "Hesap Adı ve Tip zorunludur."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            olusturan_id = self.app.current_user[0] if self.app and self.app.current_user else None
            bakiye_f = float(str(bakiye).replace(',', '.')) if bakiye else 0.0

            self.c.execute("INSERT INTO kasalar_bankalar (hesap_adi, hesap_no, bakiye, para_birimi, tip, acilis_tarihi, banka_adi, sube_adi, varsayilan_odeme_turu, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           (hesap_adi, hesap_no, bakiye_f, para_birimi, tip, acilis_tarihi, banka_adi, sube_adi, varsayilan_odeme_turu, current_time, olusturan_id))
            yeni_hesap_id = self.c.lastrowid
            self.conn.commit()
            return True, f"'{hesap_adi}' adlı hesap başarıyla eklendi. (ID: {yeni_hesap_id})"
        except sqlite3.IntegrityError as e:
            self.conn.rollback()
            if "UNIQUE constraint failed: kasalar_bankalar.hesap_adi" in str(e):
                return False, "Bu hesap adı zaten mevcut."
            elif "UNIQUE constraint failed: kasalar_bankalar.varsayilan_odeme_turu" in str(e):
                return False, f"'{varsayilan_odeme_turu}' ödeme türü zaten başka bir kasa/banka hesabına atanmış. Bir ödeme türü sadece bir hesaba atanabilir."
            else:
                return False, f"Veritabanı bütünlüğü hatası: {e}"
        except ValueError:
            self.conn.rollback()
            return False, "Bakiye sayısal olmalıdır."
        except Exception as e:
            self.conn.rollback()
            return False, f"Kasa/Banka ekleme sırasında hata: {e}"

    def kasa_banka_guncelle(self, hesap_id, hesap_adi, hesap_no, bakiye, para_birimi, tip, acilis_tarihi=None, banka_adi=None, sube_adi=None, varsayilan_odeme_turu=None):
        if not (hesap_adi and tip):
            return False, "Hesap Adı ve Tip zorunludur."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            bakiye_f = float(str(bakiye).replace(',', '.')) if bakiye else 0.0
            current_time = self.get_current_datetime_str()
            guncelleyen_id = self.app.current_user[0] if self.app and self.app.current_user else None
            self.c.execute("UPDATE kasalar_bankalar SET hesap_adi=?, hesap_no=?, bakiye=?, para_birimi=?, tip=?, acilis_tarihi=?, banka_adi=?, sube_adi=?, varsayilan_odeme_turu=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                           (hesap_adi, hesap_no, bakiye_f, para_birimi, tip, acilis_tarihi, banka_adi, sube_adi, varsayilan_odeme_turu, current_time, guncelleyen_id, hesap_id))
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, "Hesap başarıyla güncellendi."
            else:
                return False, "Hesap bulunamadı veya bir değişiklik yapılmadı."
        except sqlite3.IntegrityError as e:
            self.conn.rollback()
        except ValueError:
            self.conn.rollback()
            return False, "Bakiye sayısal olmalıdır."
        except Exception as e:
            self.conn.rollback()
            return False, f"Kasa/Banka güncelleme sırasında hata: {e}"


    def kasa_banka_listesi_al(self, tip_filtre=None, arama_terimi=None):
        query = "SELECT id, hesap_adi, hesap_no, bakiye, para_birimi, tip, acilis_tarihi, banka_adi, sube_adi, varsayilan_odeme_turu FROM kasalar_bankalar"
        params = []; conditions = []
        if tip_filtre and tip_filtre != "TÜMÜ": conditions.append("tip = ?"); params.append(tip_filtre)
        if arama_terimi: term = f"%{arama_terimi}%"; conditions.append("(hesap_adi LIKE ? OR hesap_no LIKE ? OR banka_adi LIKE ?)"); params.extend([term, term, term])
        if conditions: query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY tip, hesap_adi ASC"; self.c.execute(query, params); return self.c.fetchall()

    def kasa_banka_getir_by_id(self, hesap_id):
        self.c.execute("SELECT id, hesap_adi, hesap_no, bakiye, para_birimi, tip, acilis_tarihi, banka_adi, sube_adi, varsayilan_odeme_turu, olusturma_tarihi_saat, olusturan_kullanici_id, son_guncelleme_tarihi_saat, son_guncelleyen_kullanici_id FROM kasalar_bankalar WHERE id=?", (hesap_id,))
        return self.c.fetchone()

    def kasa_banka_sil(self, hesap_id):
        if self.default_nakit_kasa_id is not None and str(hesap_id) == str(self.default_nakit_kasa_id):
            return False, "MERKEZİ NAKİT kasa hesabı silinemez. Sadece adı güncellenebilir."

        try:
            self.conn.execute("BEGIN TRANSACTION")
            for table_name in ['faturalar', 'cari_hareketler', 'gelir_gider']:
                self.c.execute(f"SELECT COUNT(*) FROM {table_name} WHERE kasa_banka_id=?", (hesap_id,))
                if self.c.fetchone()[0] > 0:
                    self.conn.rollback()
                    return False, f"Bu kasa/banka hesabı '{table_name}' tablosunda kullanılıyor.\nİlişkili kayıtları silmeden bu hesabı silemezsiniz."
            
            self.c.execute("DELETE FROM kasalar_bankalar WHERE id=?", (hesap_id,))
            
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, "Kasa/Banka hesabı başarıyla silindi."
            else:
                return False, "Kasa/Banka hesabı bulunamadı veya silinemedi."
        except Exception as e:
            self.conn.rollback()
            return False, f"Kasa/Banka silme sırasında hata: {e}"

    def kasa_banka_bakiye_guncelle(self, kasa_banka_id, islem_tutari, artir=True):
        """
        Belirli bir kasa/banka hesabının bakiyesini günceller.
        Bu metot kendi başına bir transaction başlatmaz/kapatmaz,
        çağrıldığı transaction'ın bir parçası olarak çalışır.
        """
        if kasa_banka_id is None: 
            logging.warning("kasa_banka_bakiye_guncelle: Kasa/Banka ID boş geldi, işlem yapılmadı.")
            return True 
        try:
            self.c.execute("SELECT bakiye FROM kasalar_bankalar WHERE id=?", (kasa_banka_id,))
            mevcut_bakiye_tuple = self.c.fetchone()
            if not mevcut_bakiye_tuple:
                logging.error(f"kasa_banka_bakiye_guncelle: Hesap ID {kasa_banka_id} bulunamadı. Bakiye güncellenemedi.")
                return False 

            mevcut_bakiye = mevcut_bakiye_tuple[0]
            yeni_bakiye = mevcut_bakiye + islem_tutari if artir else mevcut_bakiye - islem_tutari

            logging.info(f"Kasa/Banka Bakiye Güncelleme: ID={kasa_banka_id}, Mevcut Bakiye={mevcut_bakiye}, İşlem Tutarı={islem_tutari}, Artır={artir}, Yeni Bakiye (Hesaplanan)={yeni_bakiye}")

            self.c.execute("UPDATE kasalar_bankalar SET bakiye=? WHERE id=?", (yeni_bakiye, kasa_banka_id))

            # Güncelleme sonrası kontrol (isteğe bağlı, hata ayıklama için)
            self.c.execute("SELECT bakiye FROM kasalar_bankalar WHERE id=?", (kasa_banka_id,))
            guncel_bakiye = self.c.fetchone()[0]
            logging.info(f"Kasa/Banka Bakiye Güncelleme: ID={kasa_banka_id}, Veritabanındaki Güncel Bakiye={guncel_bakiye}")

            return True
        except Exception as e:
            logging.error(f"Kasa/banka bakiyesi güncellenirken hata: Hesap ID {kasa_banka_id}, Tutar: {islem_tutari}, Artır: {artir}. Hata: {e}\n{traceback.format_exc()}")
            return False 
            
    def clear_stok_data(self):
        try:
            self.conn.execute("BEGIN TRANSACTION")
            self.c.execute("DELETE FROM fatura_kalemleri")
            self.c.execute("DELETE FROM siparis_kalemleri")
            self.c.execute("DELETE FROM teklif_kalemleri")
            self.c.execute("DELETE FROM tbl_stoklar")
            self.conn.commit()
            return True, "Tüm stok verileri başarıyla temizlendi." # Düzeltme: Mesaj eklendi
        except Exception as e:
            self.conn.rollback()
            return False, f"Stok verileri temizlenirken hata oluştu: {e}" # Düzeltme: Mesaj eklendi

    def clear_musteri_data(self):
        """Perakende müşteri hariç tüm müşteri verilerini ve ilişkili hareketleri temizler."""
        try:
            self.conn.execute("BEGIN TRANSACTION")
            
            # Perakende müşterinin ID'sini al
            perakende_id = self.perakende_musteri_id
            
            # Müşterilere ait faturaları, cari hareketleri, siparişleri, teklifleri sil
            self.c.execute("DELETE FROM fatura_kalemleri WHERE fatura_id IN (SELECT id FROM faturalar WHERE cari_id IN (SELECT id FROM musteriler WHERE id != ?))", (perakende_id,))
            self.c.execute("DELETE FROM faturalar WHERE cari_id IN (SELECT id FROM musteriler WHERE id != ?)", (perakende_id,))
            self.c.execute("DELETE FROM cari_hareketler WHERE cari_id IN (SELECT id FROM musteriler WHERE id != ?) AND cari_tip='MUSTERI'", (perakende_id,))
            self.c.execute("DELETE FROM siparis_kalemleri WHERE siparis_id IN (SELECT id FROM siparisler WHERE cari_id IN (SELECT id FROM musteriler WHERE id != ?) AND cari_tip='MUSTERI')", (perakende_id,))
            self.c.execute("DELETE FROM siparisler WHERE cari_id IN (SELECT id FROM musteriler WHERE id != ?) AND cari_tip='MUSTERI'", (perakende_id,))
            self.c.execute("DELETE FROM teklif_kalemleri WHERE teklif_id IN (SELECT id FROM teklifler WHERE musteri_id IN (SELECT id FROM musteriler WHERE id != ?))", (perakende_id,))
            self.c.execute("DELETE FROM teklifler WHERE musteri_id IN (SELECT id FROM musteriler WHERE id != ?)", (perakende_id,))

            # Perakende müşteri hariç tüm müşterileri sil
            self.c.execute("DELETE FROM musteriler WHERE id != ?", (perakende_id,))
            self.conn.commit()
            return True, "Tüm müşteri verileri (perakende hariç) başarıyla temizlendi." # Düzeltme: Mesaj eklendi
        except Exception as e:
            self.conn.rollback()
            return False, f"Müşteri verileri temizlenirken hata oluştu: {e}" # Düzeltme: Mesaj eklendi
        
    def clear_tedarikci_data(self):
        """Tüm tedarikçi verilerini ve ilişkili hareketleri temizler."""
        try:
            self.conn.execute("BEGIN TRANSACTION")
            # Tedarikçilere ait faturaları, cari hareketleri, siparişleri sil
            self.c.execute("DELETE FROM fatura_kalemleri WHERE fatura_id IN (SELECT id FROM faturalar WHERE cari_id IN (SELECT id FROM tedarikciler))")
            self.c.execute("DELETE FROM faturalar WHERE cari_id IN (SELECT id FROM tedarikciler)")
            self.c.execute("DELETE FROM cari_hareketler WHERE cari_id IN (SELECT id FROM tedarikciler) AND cari_tip='TEDARIKCI'")
            self.c.execute("DELETE FROM siparis_kalemleri WHERE siparis_id IN (SELECT id FROM siparisler WHERE cari_id IN (SELECT id FROM tedarikciler) AND cari_tip='TEDARIKCI')")
            self.c.execute("DELETE FROM siparisler WHERE cari_id IN (SELECT id FROM tedarikciler) AND cari_tip='TEDARIKCI'")
            
            # Tedarikçi tablosunu temizle
            self.c.execute("DELETE FROM tedarikciler")       
            self.conn.commit()
            return True, "Tüm tedarikçi verileri başarıyla temizlendi." # Düzeltme: Mesaj eklendi
        except Exception as e:
            self.conn.rollback()
            return False, f"Tedarikçi verileri temizlenirken hata oluştu: {e}" # Düzeltme: Mesaj eklendi

    def clear_kasa_banka_data(self):
        """Tüm kasa/banka verilerini ve ilişkili hareketleri temizler."""
        try:
            self.conn.execute("BEGIN TRANSACTION")
            # İlişkili faturaları, gelir/gider ve cari hareketleri sil
            
            # Faturalardaki kasa_banka_id'yi NULL yap
            self.c.execute("UPDATE faturalar SET kasa_banka_id = NULL WHERE kasa_banka_id IS NOT NULL")
            # Cari hareketlerdeki kasa_banka_id'yi NULL yap
            self.c.execute("UPDATE cari_hareketler SET kasa_banka_id = NULL WHERE kasa_banka_id IS NOT NULL")
            # Gelir/giderlerdeki kasa_banka_id'yi NULL yap
            self.c.execute("UPDATE gelir_gider SET kasa_banka_id = NULL WHERE kasa_banka_id IS NOT NULL")

            # Kasa/Banka tablosunu temizle
            self.c.execute("DELETE FROM kasalar_bankalar")
            self.conn.commit()
            return True, "Tüm kasa/banka verileri başarıyla temizlendi." # Düzeltme: Mesaj eklendi
        except Exception as e:
            self.conn.rollback()
            return False, f"Kasa/Banka verileri temizlenirken hata oluştu: {e}" # Düzeltme: Mesaj eklendi

    def clear_all_transaction_data(self):
        """Tüm işlem (fatura, gelir/gider, cari hareket, sipariş, teklif) verilerini temizler.
        Stok, müşteri, tedarikçi, kasa/banka, kullanıcı ve şirket ayarları korunur."""
        try:
            self.conn.execute("BEGIN TRANSACTION")
            self.c.execute("DELETE FROM fatura_kalemleri")
            self.c.execute("DELETE FROM faturalar")
            self.c.execute("DELETE FROM gelir_gider")
            self.c.execute("DELETE FROM cari_hareketler")
            self.c.execute("DELETE FROM siparis_kalemleri")
            self.c.execute("DELETE FROM siparisler")
            self.c.execute("DELETE FROM teklif_kalemleri")
            self.c.execute("DELETE FROM teklifler")

            # Stok miktarlarını sıfırla (ürünleri silmeden)
            self.c.execute("UPDATE tbl_stoklar SET stok_miktari = 0.0")
            
            # Kasa/Banka bakiyelerini sıfırla (hesapları silmeden)
            self.c.execute("UPDATE kasalar_bankalar SET bakiye = 0.0")
            self.conn.commit()

            return True, "Tüm işlem verileri başarıyla temizlendi. Stok ve kasa/banka bakiyeleri sıfırlandı." # Düzeltme: Mesaj eklendi
        except Exception as e:
            self.conn.rollback()
            return False, f"Tüm işlem verileri temizlenirken hata oluştu: {e}" # Düzeltme: Mesaj eklendi

    def clear_all_data(self):
        """Kullanıcılar ve şirket ayarları hariç tüm veritabanı tablolarını temizler."""
        try:
            self.conn.execute("BEGIN TRANSACTION")
            
            # Tüm tabloları sil (kullanicilar ve sirket_ayarlari hariç)
            # Bağımlı tabloları önce sil
            self.c.execute("DELETE FROM fatura_kalemleri")
            self.c.execute("DELETE FROM gelir_gider")
            self.c.execute("DELETE FROM cari_hareketler")
            self.c.execute("DELETE FROM siparis_kalemleri")
            self.c.execute("DELETE FROM teklif_kalemleri")
            
            # Sonra ana tabloları sil
            self.c.execute("DELETE FROM faturalar")
            self.c.execute("DELETE FROM siparisler")
            self.c.execute("DELETE FROM teklifler")
            self.c.execute("DELETE FROM tbl_stoklar")
            self.c.execute("DELETE FROM tedarikciler")
            self.c.execute("DELETE FROM kasalar_bankalar")
            
            # Müşteriler tablosunu temizle, perakende müşteriyi yeniden oluşturmak için
            self.c.execute("DELETE FROM musteriler")
            self.conn.commit()
            
            return True, "Tüm veritabanı başarıyla temizlendi (kullanıcılar ve şirket ayarları hariç)." # Düzeltme: Mesaj eklendi
        except Exception as e:
            self.conn.rollback()
            return False, f"Tüm veriler temizlenirken hata oluştu: {e}" 

    def optimize_database(self):
        """
        SQLite veritabanını sıkıştırır (VACUUM komutu).
        Bu işlem, veritabanı boyutunu küçültür ve performansı artırabilir.
        """
        try:
            self.conn.execute("VACUUM;")
            self.conn.commit()
            return True, "Veritabanı başarıyla optimize edildi."
        except Exception as e:
            return False, f"Veritabanı optimize edilirken hata oluştu: {e}"


    def _ensure_default_kasa(self):
        try:
            self.c.execute("SELECT id FROM kasalar_bankalar WHERE hesap_adi=? AND varsayilan_odeme_turu=?",
                           ("MERKEZİ NAKİT", "NAKİT"))
            result = self.c.fetchone()
            if result:
                self.default_nakit_kasa_id = result[0]
                return True, "MERKEZİ NAKİT kasa hesabı bulundu."
            else:
                olusturan_id = 1 # Genellikle 'admin' kullanıcısının ID'si
                current_time = self.get_current_datetime_str()
                self.c.execute("INSERT INTO kasalar_bankalar (hesap_adi, hesap_no, bakiye, para_birimi, tip, acilis_tarihi, banka_adi, sube_adi, varsayilan_odeme_turu, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               ("MERKEZİ NAKİT", None, 0.0, "TL", "KASA", datetime.now().strftime('%Y-%m-%d'), None, None, "NAKİT", current_time, olusturan_id))
                self.default_nakit_kasa_id = self.c.lastrowid
                self.conn.commit()
                return True, "MERKEZİ NAKİT kasa hesabı başarıyla oluşturuldu."
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: kasalar_bankalar.varsayilan_odeme_turu" in str(e):
                return False, "NAKİT ödeme türü zaten başka bir kasa/banka hesabına atanmış. Lütfen kontrol edin."
            else:
                return False, f"Veritabanı bütünlüğü hatası: {e}"
        except Exception as e:
            return False, f"MERKEZİ NAKİT kasa hesabı kontrol edilirken/oluşturulurken kritik hata: {e}\n{traceback.format_exc()}"

    def safe_float(self, val):
        """
        Gelen değeri güvenli bir şekilde float'a dönüştürür.
        Boş değerler, boşluklar, para birimi sembolleri ve yüzde işaretleri kaldırılır.
        Türkçe ve İngilizce ondalık/binlik ayraçlarını destekler (virgülü ondalık, noktayı binlik olarak kabul eder).
        Geçersiz dönüşümlerde 0.0 döndürür.
        """
        if val is None:
            return 0.0

        if isinstance(val, (int, float)):
            return float(val)

        s_val = str(val).strip()

        # Eğer boş bir string ise
        if not s_val:
            return 0.0

        try:
            # Para birimi sembollerini, yüzde işaretlerini ve binlik ayraçlarını kaldır.
            cleaned_val_str = s_val.replace(' ', '').replace('TL', '').replace('₺', '').replace('%', '')

            # Türkçe ve İngilizce ondalık/binlik ayrımı kontrolü:
            last_comma_idx = cleaned_val_str.rfind(',')
            last_dot_idx = cleaned_val_str.rfind('.')

            if last_comma_idx != -1 and last_dot_idx != -1:
                if last_comma_idx > last_dot_idx:
                    # Virgül en son. Noktaları kaldır, virgülü noktaya çevir. (Türkçe format)
                    cleaned_val_str = cleaned_val_str.replace('.', '') # Binlik noktaları kaldır
                    cleaned_val_str = cleaned_val_str.replace(',', '.') # Ondalık virgülü noktaya çevir
                else:
                    # Nokta en son. Virgülleri kaldır. (İngilizce format)
                    cleaned_val_str = cleaned_val_str.replace(',', '') # Binlik virgülleri kaldır
                    # Nokta zaten ondalık olarak kalacak
            elif last_comma_idx != -1:
                # Sadece virgül var. Virgülü noktaya çevir (Türkçe ondalık)
                cleaned_val_str = cleaned_val_str.replace(',', '.')
            # Eğer sadece nokta varsa, zaten İngilizce ondalık formatındadır, dokunma.

            result = float(cleaned_val_str)
            return result
        except ValueError:
            # Dönüşüm hatası durumunda 0.0 döndür (örn: "abc" veya "--")
            return 0.0
        except Exception as e:
            # Beklenmeyen diğer hatalar için
            print(f"UYARI: safe_float sırasında beklenmeyen hata: '{val}' -> {e}")
            return 0.0

    def gecmis_hatali_kayitlari_temizle(self):
        """
        Veritabanını tarar ve artık 'faturalar' tablosunda var olmayan faturalara ait
        'cari_hareketler' ve 'gelir_gider' kayıtlarını (hayalet kayıtları) siler.
        Bu, geçmişte yapılan hatalı silme işlemlerini düzeltmek için tek seferlik bir işlemdir.
        """
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR >>>
        try:
            self.conn.execute("BEGIN TRANSACTION")
            
            # Adım 1: Artık var olmayan faturalara ait cari hareketleri bul ve sil
            # LEFT JOIN tekniği, faturalar tablosunda karşılığı olmayan kayıtları (f.id IS NULL) bulmada daha güvenilirdir.
            self.c.execute("""
                DELETE FROM cari_hareketler 
                WHERE id IN (
                    SELECT ch.id 
                    FROM cari_hareketler ch
                    LEFT JOIN faturalar f ON ch.referans_id = f.id
                    WHERE (ch.referans_tip LIKE '%FATURA%' OR ch.referans_tip LIKE '%IADE_FATURA%') AND f.id IS NULL
                )
            """)
            cari_hareket_sayisi = self.c.rowcount
            if cari_hareket_sayisi > 0:
                logging.info(f"{cari_hareket_sayisi} adet hayalet cari hareketi silindi.")

            # Adım 2: Artık var olmayan faturalara ait gelir/gider hareketlerini bul ve sil
            self.c.execute("""
                DELETE FROM gelir_gider
                WHERE id IN (
                    SELECT gg.id
                    FROM gelir_gider gg
                    LEFT JOIN faturalar f ON gg.kaynak_id = f.id
                    WHERE (gg.kaynak LIKE '%FATURA%' OR gg.kaynak LIKE '%IADE_FATURA%') AND f.id IS NULL
                )
            """)
            gg_hareket_sayisi = self.c.rowcount
            if gg_hareket_sayisi > 0:
                logging.info(f"{gg_hareket_sayisi} adet hayalet gelir/gider hareketi silindi.")

            self.conn.commit()
            toplam_silinen = cari_hareket_sayisi + gg_hareket_sayisi
            if toplam_silinen > 0:
                return True, f"Temizlik tamamlandı. Toplam {toplam_silinen} adet geçmiş hatalı kayıt silindi."
            else:
                return True, "Geçmişe dönük hatalı bir kayıt bulunamadı. Veritabanınız temiz görünüyor."

        except Exception as e:
            self.conn.rollback()
            logging.error(f"Geçmiş hatalı kayıtlar temizlenirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Temizleme sırasında bir hata oluştu: {e}"

    def urun_grubu_ekle(self, grup_adi):
        if not grup_adi:
            return False, "Ürün grubu adı boş olamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            olusturan_id = self._get_current_user_id() # Değişiklik
            self.c.execute("INSERT INTO urun_gruplari (grup_adi, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?)",
                           (grup_adi, current_time, olusturan_id))
            self.conn.commit()
            return True, f"'{grup_adi}' ürün grubu başarıyla eklendi."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu ürün grubu adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Ürün grubu eklenirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Ürün grubu eklenirken beklenmeyen hata: {e}"

    def urun_grubu_listele(self):
        self.c.execute("SELECT id, grup_adi FROM urun_gruplari ORDER BY grup_adi ASC")
        return self.c.fetchall()

    def urun_grubu_guncelle(self, grup_id, yeni_grup_adi):
        if not yeni_grup_adi:
            return False, "Ürün grubu adı boş olamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION") # Atomik işlem başlat
            current_time = self.get_current_datetime_str()
            guncelleyen_id = self.app.current_user[0] if self.app and self.app.current_user else None
            self.c.execute("UPDATE urun_gruplari SET grup_adi=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                           (yeni_grup_adi, current_time, guncelleyen_id, grup_id))
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, "Ürün grubu başarıyla güncellendi."
            else:
                return False, "Ürün grubu bulunamadı veya bir değişiklik yapılmadı."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu ürün grubu adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Ürün grubu güncellenirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Ürün grubu güncellenirken beklenmeyen hata: {e}"

    def urun_grubu_sil(self, grup_id):
        try:
            self.conn.execute("BEGIN TRANSACTION") # Atomik işlem başlat
            self.c.execute("SELECT COUNT(*) FROM tbl_stoklar WHERE urun_grubu_id=?", (grup_id,))
            if self.c.fetchone()[0] > 0:
                self.conn.rollback()
                return False, "Bu ürün grubuna bağlı ürünler bulunmaktadır. Lütfen önce ürünlerin grubunu değiştirin veya ürünleri silin."
            self.c.execute("DELETE FROM urun_gruplari WHERE id=?", (grup_id,))
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, "Ürün grubu başarıyla silindi."
            else:
                return False, "Ürün grubu bulunamadı veya silinemedi."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Ürün grubu silinirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Ürün grubu silinirken beklenmeyen hata: {e}"

    # --- Ürün Birimi Yönetimi Metotları ---
    def urun_birimi_ekle(self, birim_adi):
        if not birim_adi:
            return False, "Ürün birimi adı boş olamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION")
            current_time = self.get_current_datetime_str()
            olusturan_id = self._get_current_user_id() # Değişiklik
            self.c.execute("INSERT INTO urun_birimleri (birim_adi, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?)",
                           (birim_adi, current_time, olusturan_id))
            self.conn.commit()
            return True, f"'{birim_adi}' ürün birimi başarıyla eklendi."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu ürün birimi adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Ürün birimi eklenirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Ürün birimi eklenirken beklenmeyen hata: {e}"
        
    def urun_birimi_listele(self):
        self.c.execute("SELECT id, birim_adi FROM urun_birimleri ORDER BY birim_adi ASC")
        return self.c.fetchall()

    def urun_birimi_guncelle(self, birim_id, yeni_birim_adi):
        if not yeni_birim_adi:
            return False, "Ürün birimi adı boş olamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION") # Atomik işlem başlat
            current_time = self.get_current_datetime_str()
            guncelleyen_id = self.app.current_user[0] if self.app and self.app.current_user else None
            self.c.execute("UPDATE urun_birimleri SET birim_adi=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                           (yeni_birim_adi, current_time, guncelleyen_id, birim_id))
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, "Ürün birimi başarıyla güncellendi."
            else:
                return False, "Ürün birimi bulunamadı veya bir değişiklik yapılmadı."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu ürün birimi adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Ürün birimi güncellenirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Ürün birimi güncellenirken beklenmeyen hata: {e}"

    def urun_birimi_sil(self, birim_id):
        try:
            self.conn.execute("BEGIN TRANSACTION") # Atomik işlem başlat
            self.c.execute("SELECT COUNT(*) FROM tbl_stoklar WHERE urun_birimi_id=?", (birim_id,))
            if self.c.fetchone()[0] > 0:
                self.conn.rollback()
                return False, "Bu ürün birimi başka ürünlere bağlı olduğu için silinemez."
            self.c.execute("DELETE FROM urun_birimleri WHERE id=?", (birim_id,))
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, f"Ürün birimi ID {birim_id} başarıyla silindi."
            else:
                return False, f"Ürün birimi ID {birim_id} bulunamadı veya silinemedi."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Ürün birimi silinirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Ürün birimi silinirken beklenmeyen hata: {e}"

    # --- Ülke Yönetimi Metotları (Menşe için) ---
    def ulke_ekle(self, ulke_adi):
        if not ulke_adi:
            return False, "Ülke adı boş olamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION") # Atomik işlem başlat
            current_time = self.get_current_datetime_str()
            olusturan_id = self.app.current_user[0] if self.app and self.app.current_user else None
            self.c.execute("INSERT INTO urun_ulkeleri (ulke_adi, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?)",
                           (ulke_adi, current_time, olusturan_id))
            self.conn.commit()
            return True, f"'{ulke_adi}' ülkesi başarıyla eklendi."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu ülke adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Ülke eklenirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Ülke eklenirken beklenmeyen hata: {e}"

    def ulke_listele(self):
        self.c.execute("SELECT id, ulke_adi FROM urun_ulkeleri ORDER BY ulke_adi ASC")
        return self.c.fetchall()

    def ulke_guncelle(self, ulke_id, yeni_ulke_adi):
        if not yeni_ulke_adi:
            return False, "Ülke adı boş olamaz."
        try:
            self.conn.execute("BEGIN TRANSACTION") # Atomik işlem başlat
            current_time = self.get_current_datetime_str()
            guncelleyen_id = self.app.current_user[0] if self.app and self.app.current_user else None
            self.c.execute("UPDATE urun_ulkeleri SET ulke_adi=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                           (yeni_ulke_adi, current_time, guncelleyen_id, ulke_id))
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, f"Ülke başarıyla güncellendi."
            else:
                return False, "Ülke bulunamadı veya bir değişiklik yapılmadı."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Bu ülke adı zaten mevcut."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Ülke güncellenirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Ülke güncellenirken beklenmeyen hata: {e}"

    def ulke_sil(self, ulke_id):
        try:
            self.conn.execute("BEGIN TRANSACTION") # Atomik işlem başlat
            self.c.execute("SELECT COUNT(*) FROM tbl_stoklar WHERE ulke_id=?", (ulke_id,))
            if self.c.fetchone()[0] > 0:
                self.conn.rollback()
                return False, "Bu ülkeye bağlı ürünler bulunmaktadır. Lütfen önce ürünlerin ülkesini değiştirin veya ürünleri silin."
            self.c.execute("DELETE FROM urun_ulkeleri WHERE id=?", (ulke_id,))
            self.conn.commit()
            if self.c.rowcount > 0:
                return True, f"Ülke başarıyla silindi."
            else:
                return False, f"Ülke bulunamadı veya silinemedi."
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Ülke silinirken hata: {e}\n{traceback.format_exc()}")
            return False, f"Ülke silinirken beklenmeyen hata: {e}"