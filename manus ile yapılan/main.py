# main.py dosyasının içeriği birinci dosya
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import multiprocessing
from datetime import datetime
import threading
import shutil
import logging
import os
import sys
import sqlite3
import traceback # traceback importu eklendi

# Üçüncü Parti Kütüphaneler
from ttkthemes import ThemedTk

# Yerel Uygulama Modülleri
from veritabani import OnMuhasebe
from hizmetler import FaturaService, TopluIslemService
from yardimcilar import setup_locale

# arayuz.py'den SADECE ANA SAYFA/SEKME sınıflarını import ediyoruz.
from arayuz import (GirisEkrani, AnaSayfa, StokYonetimiSayfasi, MusteriYonetimiSayfasi,
                    TedarikciYonetimiSayfasi, FaturaListesiSayfasi, FinansalIslemlerSayfasi,
                    KasaBankaYonetimiSayfasi, RaporlamaMerkeziSayfasi, GelirGiderSayfasi,
                    SiparisListesiSayfasi, FaturaOlusturmaSayfasi, SiparisOlusturmaSayfasi) 

# pencereler.py'den TÜM POP-UP PENCERE sınıflarını import ediyoruz.
# Bu liste pencereler.py'deki tüm Toplevel sınıflarını içermelidir.
from pencereler import (YoneticiAyarlariPenceresi, SirketBilgileriPenceresi, KullaniciYonetimiPenceresi,
                      TopluVeriEklePenceresi, TarihAraligiDialog, BeklemePenceresi,
                      FaturaDetayPenceresi, SiparisDetayPenceresi, StokHareketiPenceresi,
                      UrunKartiPenceresi, KategoriMarkaYonetimiPenceresi, UrunNitelikYonetimiPenceresi,
                      YeniKasaBankaEklePenceresi, YeniTedarikciEklePenceresi, YeniMusteriEklePenceresi,
                      KalemDuzenlePenceresi, FiyatGecmisiPenceresi, YeniGelirGiderEklePenceresi,
                      OdemeTuruSecimDialog, CariSecimPenceresi, TedarikciSecimDialog,
                      SiparisPenceresi, FaturaGuncellemePenceresi, FaturaPenceresi) 
from raporlar import CriticalStockWarningPenceresi, NotificationDetailsPenceresi


# VERİTABANI VE LOG DOSYALARI İÇİN TEMEL DİZİN TANIMLAMA (ANA UYGULAMA GİRİŞ NOKTASI)
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

data_dir = os.path.join(base_dir, 'data')
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# LOGLAMA YAPILANDIRMASI (TÜM UYGULAMA İÇİN SADECE BURADA YAPILACAK)
log_file_path = os.path.join(data_dir, 'application.log')
logging.basicConfig(filename=log_file_path, level=logging.ERROR, # ERROR seviyesinden itibaren logla
                    format='%(asctime)s - %(levelname)s - %(message)s')


def _pdf_olusturma_islemi(db_name_path, cari_tip, cari_id, bas_t, bit_t, dosya_yolu, result_queue):
    """
    Ayrı bir süreçte PDF oluşturma işlemini gerçekleştiren bağımsız fonksiyon.
    """
    try:
        temp_db_manager = OnMuhasebe(db_name=db_name_path) # Tam yolu direkt gönderiyoruz
        success, message = temp_db_manager.cari_ekstresi_pdf_olustur(cari_tip, cari_id, bas_t, bit_t, dosya_yolu)
        result_queue.put((success, message)) # Sonucu kuyruğa koy

    except Exception as e:
        # Hatanın detaylarını yakala ve logla
        error_message = f"PDF işleminde hata: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        result_queue.put((False, error_message)) # Hata mesajını da kuyruğa koy
    finally:
        # Süreç sonunda veritabanı bağlantısını kapatmayı unutmayın
        if 'temp_db_manager' in locals() and temp_db_manager.conn:
            temp_db_manager.conn.close()

# main.py içinde App sınıfı
class App(ThemedTk):
    def __init__(self, db_manager):
        logging.getLogger('matplotlib').setLevel(logging.ERROR)
        super().__init__(theme="awdark")
        self.db = db_manager
        self.db.app = self # <<< BU SATIR YUKARI TAŞINDI >>>
        
        self.current_user = None
        self.fatura_servisi = FaturaService(self.db)
        self.toplu_islem_servisi = TopluIslemService(self.db, self.fatura_servisi)

        self.title("Çınar Yapı Ön Muhasebe Programı")
        self.geometry("1400x820")
        self.minsize(900, 600)

        # Ana layout için grid yapılandırması
        self.grid_rowconfigure(0, weight=1) # Notebook için
        self.grid_rowconfigure(1, weight=0) # Alt bar için
        self.grid_columnconfigure(0, weight=1)

        self.open_cari_ekstre_windows = []
        self.temp_sales_invoice_data = None
        self.temp_purchase_invoice_data = None
        self.temp_sales_order_data = None
        self.temp_purchase_order_data = None

        # Stil ayarları
        self.style = ttk.Style(self)
        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        self.style.configure("Dashboard.TButton", font=("Segoe UI", 20, "bold"), padding=(12,12))
        self.style.configure("Bold.TLabel", font=("Segoe UI", 16, "bold"))
        self.style.configure("Treeview.Heading", font=('Segoe UI', 9, 'bold'))
        self.style.configure("Notification.TLabel", background="#FFD2D2", foreground="red", font=("Segoe UI", 10, "bold"), anchor=tk.CENTER, wraplength=400)
        self.notification_update_interval = 30000

        # Sayfa niteliklerini tanımlama (Başlangıçta None olarak ayarla)
        self.ana_sayfa = None
        self.stok_yonetimi_sayfasi = None
        self.musteri_yonetimi_sayfasi = None
        self.tedarikci_yonetimi_sayfasi = None
        self.fatura_listesi_sayfasi = None
        self.gelir_gider_sayfasi = None
        self.finansal_islemler_sayfasi = None
        self.kasa_banka_yonetimi_sayfasi = None
        self.raporlama_merkezi_sayfasi = None
        self.siparis_listesi_sayfasi = None

        self.notebook = None

        # Durum çubuğu ve bildirim etiketi burada oluşturulur
        self.bottom_bar_frame = ttk.Frame(self)
        self.status_bar = ttk.Label(self.bottom_bar_frame, text="Hazır.", relief=tk.SUNKEN, anchor=tk.W, padding=3)
        self.notification_label = ttk.Label(self.bottom_bar_frame, text="", style="Notification.TLabel", padding=0)

        # Veritabanı kontrol işlemleri...
        try:
            admin_success, admin_message = self.db.ensure_admin_user() # show_messagebox=False parametresi kaldırıldı
            if not admin_success:
                logging.critical(f"Admin kullanıcısı kontrol/oluşturma başarısız: {admin_message}")
                messagebox.showwarning("Kritik Hata", "Admin kullanıcısı oluşturulamadı: " + admin_message + "\nLütfen programı yeniden başlatın.", parent=self)
                self.quit()

            perakende_success, perakende_message = self.db._ensure_perakende_musteri()
            if not perakende_success:
                logging.error(f"Perakende müşteri kontrol/oluşturma başarısız: {perakende_message}")
                messagebox.showwarning("Kritik Hata", "Perakende müşteri oluşturulamadı: " + perakende_message + "\nBazı satış işlemleri düzgün çalışmayabilir.", parent=self)

            genel_tedarikci_success, genel_tedarikci_message = self.db._ensure_genel_tedarikci()
            if not genel_tedarikci_success:
                logging.error(f"Genel tedarikçi kontrol/oluşturma başarısız: {genel_tedarikci_message}")
                messagebox.showwarning("Kritik Hata", "Genel tedarikçi oluşturulamadı: " + genel_tedarikci_message + "\nBazı toplu alış işlemleri düzgün çalışmayabilir.", parent=self)

            default_kasa_success, default_kasa_message = self.db._ensure_default_kasa()
            if not default_kasa_success:
                logging.error(f"Varsayılan kasa oluşturma başarısız: {default_kasa_message}")
                messagebox.showwarning("Kritik Hata", "Varsayılan kasa oluşturulamadı: " + default_kasa_message + "\nFinansal işlemler düzgün çalışmayabilir.", parent=self)

            default_birim_success, default_birim_message = self.db._ensure_default_urun_birimi()
            if not default_birim_success:
                logging.error(f"Varsayılan ürün birimi oluşturma başarısız: {default_birim_message}")
                messagebox.showwarning("Kritik Hata", "Varsayılan ürün birimi oluşturulamadı: " + default_birim_message + "\nÜrün işlemleri etkilenebilir.", parent=self)

            default_ulke_success, default_ulke_message = self.db._ensure_default_ulke()
            if not default_ulke_success:
                logging.error(f"Varsayılan ülke oluşturma başarısız: {default_ulke_message}")
                messagebox.showwarning("Kritik Hata", "Varsayılan ülke oluşturulamadı: " + default_ulke_message + "\nÜrün işlemleri etkilenebilir.", parent=self)

            print("DEBUG: Tüm başlangıç veritabanı ensure işlemleri başarılı.")
            logging.info("Tüm başlangıç veritabanı ensure işlemleri başarılı.")

        except Exception as e:
            logging.critical(f"Veritabanı başlangıç işlemleri sırasında beklenmeyen kritik hata: {e}", exc_info=True)
            messagebox.showwarning("Kritik Hata", f"Veritabanı başlangıç işlemleri sırasında beklenmeyen bir hata oluştu:\n{e}\nLütfen programı yeniden başlatın.", parent=self)
            self.quit()

        self.giris_ekrani_goster() # Bu çağrı init'in sonunda kalmalı

        logging.info("Uygulama başlatıldı. (main.py'den)")
        print("Uygulama başlatıldı. (main.py'den)")

    def _clear_log_file_ui(self):
        if not (self.current_user and self.current_user[2] == 'admin'):
            messagebox.showwarning("Yetki Gerekli", "Logları sıfırlama işlemi için admin yetkisi gereklidir.", parent=self)
            return

        if messagebox.askyesno("Logları Sıfırla Onayı", "Log dosyasının içeriğini sıfırlamak istediğinizden emin misiniz?", icon='warning', parent=self):
            success, message = self.db.clear_log_file()
            if success:
                messagebox.showinfo("Başarılı", message, parent=self)
                self.set_status(message)
            else:
                messagebox.showerror("Hata", message, parent=self)
                self.set_status(f"Logları sıfırlama başarısız: {message}")

    def giris_ekrani_goster(self):
        self._clear_window() 
        GirisEkrani(self, self.db, self.ana_arayuzu_baslat)
    def _check_critical_stock(self):
        """Uygulama başlatıldığında veya menüden çağrıldığında kritik stoktaki ürünleri kontrol eder ve bildirim etiketini günceller."""
        # notification_label'ın varlığını burada kontrol etmeye gerek yok, çünkü init'te oluşturuldu.

        critical_items = self.db.get_critical_stock_items()
        overdue_receivables = self.db.get_overdue_receivables()
        overdue_payables = self.db.get_overdue_payables()

        notification_messages = []
        notification_details = {} # Detay penceresi için saklanacak veriler

        if critical_items:
            notification_messages.append(f"📦 Kritik Stok: {len(critical_items)} ürün!")
            notification_details['critical_stock'] = critical_items

        if overdue_receivables:
            notification_messages.append(f"💰 Vadesi Geçmiş Alacak: {len(overdue_receivables)} müşteri!")
            notification_details['overdue_receivables'] = overdue_receivables

        if overdue_payables:
            notification_messages.append(f"💸 Vadesi Geçmiş Borç: {len(overdue_payables)} tedarikçi!")
            notification_details['overdue_payables'] = overdue_payables

        self.current_notifications = notification_details # Bildirim detaylarını sakla

        if notification_messages:
            full_message = " | ".join(notification_messages)
            self.notification_label.config(text=f"UYARI: {full_message}", style="Notification.TLabel")
            self.notification_label.pack(side=tk.RIGHT, fill=tk.X, padx=5) # Etiketi görünür yap
        else:
            self.notification_label.config(text=" ") # Mesaj yoksa boş bırak
            self.notification_label.pack_forget() # Etiketi gizle

    def _schedule_critical_stock_check(self):
        """Kritik stok kontrolünü düzenli aralıklarla planlar."""
        self.after(self.notification_update_interval, self._check_critical_stock)
        self.after(self.notification_update_interval, self._schedule_critical_stock_check) # Kendini tekrar planla


    def _on_tab_change(self, event):
        selected_tab_id = self.notebook.select()
        selected_tab_widget = self.notebook.nametowidget(selected_tab_id)
        selected_tab_text = self.notebook.tab(selected_tab_id, "text")

        # TASLAK KAYDETME MANTIĞI BURADAN KALDIRILDIĞI İÇİN SATIR YOK

        self.set_status(f"Sekme değiştirildi: {selected_tab_text.strip()}")

        if selected_tab_text == "🏠 33 Ana Sayfa":
            if hasattr(self.ana_sayfa, 'guncelle_ozet_bilgiler'):
                self.ana_sayfa.guncelle_ozet_bilgiler()
            if hasattr(self.ana_sayfa, 'guncelle_sirket_adi'):
                self.ana_sayfa.guncelle_sirket_adi()

        elif selected_tab_text == "📦 Stok Yönetimi":
            if hasattr(self.stok_yonetimi_sayfasi, 'stok_listesini_yenile'):
                print("DEBUG: _on_tab_change - Stok Yönetimi sekmesi seçildi, yenileme tetikleniyor.")
                self.stok_yonetimi_sayfasi.stok_listesini_yenile()

        elif selected_tab_text == "👥 Müşteri Yönetimi":
            if hasattr(self.musteri_yonetimi_sayfasi, 'musteri_listesini_yenile'):
                self.musteri_yonetimi_sayfasi.musteri_listesini_yenile()

        elif selected_tab_text == "🚚 Tedarikçi Yönetimi":
            if hasattr(self.tedarikci_yonetimi_sayfasi, 'tedarikci_listesini_yenile'):
                self.tedarikci_yonetimi_sayfasi.tedarikci_listesini_yenile()

        elif selected_tab_text == "🧾 Faturalar":
            if hasattr(self.fatura_listesi_sayfasi.satis_fatura_frame, 'fatura_listesini_yukle'):
                 self.fatura_listesi_sayfasi.satis_fatura_frame.fatura_listesini_yukle()
            if hasattr(self.fatura_listesi_sayfasi.alis_fatura_frame, 'fatura_listesini_yukle'):
                 self.fatura_listesi_sayfasi.alis_fatura_frame.fatura_listesini_yukle()

        elif selected_tab_text == "💸 Gelir/Gider":
            if hasattr(self.gelir_gider_sayfasi.gelir_listesi_frame, 'gg_listesini_yukle'):
                self.gelir_gider_sayfasi.gelir_listesi_frame.gg_listesini_yukle()
            if hasattr(self.gelir_gider_sayfasi.gider_listesi_frame, 'gg_listesini_yukle'):
                self.gelir_gider_sayfasi.gider_listesi_frame.gg_listesini_yukle()

        elif selected_tab_text == "🏦 Kasa/Banka":
            if hasattr(self.kasa_banka_yonetimi_sayfasi, 'hesap_listesini_yenile'):
                self.kasa_banka_yonetimi_sayfasi.hesap_listesini_yenile()

        elif selected_tab_text == "📊 Raporlar":
            if hasattr(self.raporlama_merkezi_sayfasi, 'raporu_olustur_ve_yenile'):
                self.raporlama_merkezi_sayfasi.raporu_olustur_ve_yenile()

        elif selected_tab_text == "📋 Sipariş Yönetimi":
            if hasattr(self.siparis_listesi_sayfasi, 'siparis_listesini_yukle'):
                self.siparis_listesi_sayfasi.siparis_listesini_yukle()

        elif selected_tab_text == "💵 Finansal İşlemler":
            self.finansal_islemler_sayfasi.tahsilat_frame._yukle_ve_cachele_carileri()
            self.finansal_islemler_sayfasi.tahsilat_frame._yukle_kasa_banka_hesaplarini()
            self.finansal_islemler_sayfasi.tahsilat_frame.tarih_entry.delete(0, tk.END)
            self.finansal_islemler_sayfasi.tahsilat_frame.tarih_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
            self.finansal_islemler_sayfasi.tahsilat_frame.tutar_entry.delete(0, tk.END)

            self.finansal_islemler_sayfasi.odeme_frame._yukle_ve_cachele_carileri()
            self.finansal_islemler_sayfasi.odeme_frame._yukle_kasa_banka_hesaplarini()
            self.finansal_islemler_sayfasi.odeme_frame.tarih_entry.delete(0, tk.END)
            self.finansal_islemler_sayfasi.odeme_frame.tarih_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
            self.finansal_islemler_sayfasi.odeme_frame.tutar_entry.delete(0, tk.END)

        self._last_selected_tab_widget = selected_tab_widget
        self._last_selected_tab_text = selected_tab_text

    def kasa_banka_yonetimi_sayfasi_goster(self):
        self.notebook.select(self.kasa_banka_yonetimi_sayfasi)
        self.set_status("Kasa/Banka Yönetimi ekranı açıldı.")

    def siparis_yonetimi_goster(self):
        self.notebook.select(self.siparis_listesi_sayfasi)
        self.set_status("Sipariş Yönetimi ekranı açıldı.")

    def cari_yaslandirma_raporu_goster(self):
        # Artık doğrudan CariYaslandirmaRaporuPenceresi'ni çağırmıyoruz,
        # RaporlamaMerkeziSayfasi'nı açıp ilgili sekmeye yönlendiriyoruz.
        self._go_to_report_tab("👥 Cari Hesaplar")
        self.set_status("Cari Hesap Yaşlandırma Raporu açıldı.")

    def nakit_akis_raporu_goster_app(self):
        # Artık doğrudan NakitAkisRaporuPenceresi'ni çağırmıyoruz.
        self._go_to_report_tab("🏦 Nakit Akışı")
        self.set_status("Nakit Akış Raporu penceresi açıldı.")

    def kar_zarar_raporu_goster_app(self):
        # Artık doğrudan KarZararRaporuPenceresi'ni çağırmıyoruz.
        self._go_to_report_tab("💰 Kâr ve Zarar")
        self.set_status("Kâr/Zarar Raporu penceresi açıldı.")

    def ana_arayuzu_baslat(self, user_info):
        """
        Kullanıcı başarılı bir şekilde giriş yaptığında veya geçici olarak atlandığında
        ana uygulama arayüzünü başlatır ve menüleri oluşturur.
        """
        self.current_user = user_info
        self._clear_window()
        self.title(f"Çınar Yapı Ön Muhasebe - Hoş Geldiniz, {self.current_user[1]} ({self.current_user[2].capitalize()})")

        menubar = tk.Menu(self)
        self.config(menu=menubar)

        config = self.db.load_config()
        config['last_username'] = self.current_user[1]
        self.db.save_config(config)

        dosya_menu = tk.Menu(menubar, tearoff=0)
        dosya_menu.add_command(label="Şirket Bilgileri", command=self.sirket_bilgileri_penceresi_ac)
        dosya_menu.add_separator()
        dosya_menu.add_separator()
        dosya_menu.add_command(label="Veritabanı Yedekle", command=self.veritabani_yedekle)
        dosya_menu.add_command(label="Veritabanı Geri Yükle", command=self.veritabani_geri_yukle)
        dosya_menu.add_separator()
        dosya_menu.add_command(label="Çıkış Yap", command=self.cikis_yap_ve_giris_ekranina_don)
        dosya_menu.add_command(label="Programdan Çık", command=self.quit)
        menubar.add_cascade(label="Dosya", menu=dosya_menu)

        if self.current_user and self.current_user[2] == 'admin':
            yonetim_menu = tk.Menu(menubar, tearoff=0)
            yonetim_menu.add_command(label="Kullanıcı Yönetimi", command=self.kullanici_yonetimi_penceresi_ac)
            yonetim_menu.add_separator()
            yonetim_menu.add_command(label="Toplu Veri Ekle", command=self.toplu_veri_ekle_penceresi_ac)
            yonetim_menu.add_command(label="Gelir/Gider Sınıflandırma Yönetimi", command=self._gelir_gider_siniflandirma_yonetimi_ac)
            yonetim_menu.add_command(label="Veri Sıfırlama ve Temizleme", command=self.veri_sifirlama_penceresi_ac)
            yonetim_menu.add_separator()
            yonetim_menu.add_command(label="Log Dosyasını Sıfırla", command=self._clear_log_file_ui)
            yonetim_menu.add_command(label="Veritabanını Optimize Et", command=lambda: self._optimize_database_ui())
            yonetim_menu.add_command(label="Eksik Stok Hareketlerini Oluştur (Tek Seferlik)", command=self._run_backfill_script_ui)
            menubar.add_cascade(label="Yönetim", menu=yonetim_menu)


        raporlar_menu = tk.Menu(menubar, tearoff=0)
        raporlar_menu.add_command(label="Stok Raporu (Excel)", command=self.stok_raporu_excel_ui)
        raporlar_menu.add_command(label="Tarihsel Satış Raporu (Excel)", command=lambda: self.tarihsel_satis_raporu_ui('excel'))
        raporlar_menu.add_command(label="Tarihsel Satış Raporu (PDF)", command=lambda: self.tarihsel_satis_raporu_ui('pdf'))
        raporlar_menu.add_command(label="Nakit Akış Raporu", command=self.nakit_akis_raporu_goster_app) # Güncellenecek
        raporlar_menu.add_command(label="Kâr/Zarar Raporu", command=self.kar_zarar_raporu_goster_app) # Güncellenecek
        raporlar_menu.add_separator()
        # Ana raporlama sayfasını açacak yeni menü öğesi
        raporlar_menu.add_command(label="Finansal Raporlar ve Analiz", command=lambda: self._go_to_report_tab("📊 Genel Bakış"))
        raporlar_menu.add_separator()
        raporlar_menu.add_command(label="Kritik Stok Uyarısı", command=self.kritik_stok_uyarisi_goster_app) # Bu hala ayrı bir Toplevel penceresi olabilir.
        raporlar_menu.add_command(label="Cari Hesap Yaşlandırma Raporu", command=self.cari_yaslandirma_raporu_goster) # Güncellenecek

        menubar.add_cascade(label="Raporlar", menu=raporlar_menu)

        siparisler_menu = tk.Menu(menubar, tearoff=0)
        siparisler_menu.add_command(label="Yeni Müşteri Siparişi", command=self.musteri_siparisi_goster)
        siparisler_menu.add_command(label="Yeni Tedarikçi Siparişi", command=self.tedarikci_siparisi_goster)
        siparisler_menu.add_separator()
        siparisler_menu.add_command(label="Sipariş Listesi", command=self.siparis_yonetimi_goster)
        menubar.add_cascade(label="Siparişler", menu=siparisler_menu)

        hizli_erisim_menu = tk.Menu(menubar, tearoff=0)
        hizli_erisim_menu.add_command(label="Ana Sayfa", command=self.ana_sayfa_goster, accelerator="Ctrl+g")
        self.bind_all("<Control-g>", lambda event: self.ana_sayfa_goster())

        hizli_erisim_menu.add_command(label="Yeni Satış Faturası", command=self.satis_faturasi_goster, accelerator="Ctrl+S")
        self.bind_all("<Control-s>", lambda event: self.satis_faturasi_goster())

        hizli_erisim_menu.add_command(label="Yeni Alış Faturası", command=self.alis_faturasi_goster, accelerator="Ctrl+i")
        self.bind_all("<Control-i>", lambda event: self.alis_faturasi_goster())

        hizli_erisim_menu.add_command(label="Fatura Listesi", command=self.fatura_listesi_goster, accelerator="Ctrl+F")
        self.bind_all("<Control-f>", lambda event: self.fatura_listesi_goster())

        hizli_erisim_menu.add_command(label="Stok Yönetimi", command=self.stok_yonetimi_goster, accelerator="Ctrl+E")
        self.bind_all("<Control-e>", lambda event: self.stok_yonetimi_goster())

        hizli_erisim_menu.add_command(label="Müşteri Yönetimi", command=self.musteri_yonetimi_goster, accelerator="Ctrl+M")
        self.bind_all("<Control-m>", lambda event: self.musteri_yonetimi_goster())

        hizli_erisim_menu.add_command(label="Tedarikçi Yönetimi", command=self.tedarikci_yonetimi_goster, accelerator="Ctrl+T")
        self.bind_all("<Control-t>", lambda event: self.tedarikci_yonetimi_goster())

        hizli_erisim_menu.add_command(label="Finansal İşlemler (Ödeme)", command=lambda: self.notebook.select(self.finansal_islemler_sayfasi) and self.finansal_islemler_sayfasi.main_notebook.select(self.finansal_islemler_sayfasi.odeme_frame), accelerator="Ctrl+O")
        self.bind_all("<Control-o>", lambda event: self.notebook.select(self.finansal_islemler_sayfasi) and self.finansal_islemler_sayfasi.main_notebook.select(self.finansal_islemler_sayfasi.odeme_frame))

        hizli_erisim_menu.add_command(label="Kasa/Banka Yönetimi", command=self.kasa_banka_yonetimi_sayfasi_goster, accelerator="Ctrl+K")
        self.bind_all("<Control-k>", lambda event: self.kasa_banka_yonetimi_sayfasi_goster())

        # "Satış Raporu" menü öğesini "Finansal Raporlar ve Analiz" olarak güncelleyin
        hizli_erisim_menu.add_command(label="Finansal Raporlar ve Analiz", command=lambda: self._go_to_report_tab("📊 Genel Bakış"), accelerator="Ctrl+R")
        self.bind_all("<Control-r>", lambda event: self._go_to_report_tab("📊 Genel Bakış"))

        hizli_erisim_menu.add_command(label="Yeni Müşteri Siparişi", command=self.musteri_siparisi_goster, accelerator="Ctrl+Alt+S")
        self.bind_all("<Control-Alt-s>", lambda event: self.musteri_siparisi_goster())

        hizli_erisim_menu.add_command(label="Yeni Tedarikçi Siparişi", command=self.tedarikci_siparisi_goster, accelerator="Ctrl+Alt+A")
        self.bind_all("<Control-Alt-a>", lambda event: self.tedarikci_siparisi_goster())

        hizli_erisim_menu.add_command(label="Sipariş Listesi", command=self.siparis_yonetimi_goster, accelerator="Ctrl+P")
        self.bind_all("<Control-p>", lambda event: self.siparis_yonetimi_goster())

        menubar.add_cascade(label="Hızlı Erişim", menu=hizli_erisim_menu)


        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)

        self.ana_sayfa = AnaSayfa(self.notebook, self.db, self)
        self.notebook.add(self.ana_sayfa, text="🏠 33 Ana Sayfa")

        self.stok_yonetimi_sayfasi = StokYonetimiSayfasi(self.notebook, self.db, self)
        self.notebook.add(self.stok_yonetimi_sayfasi, text="📦 Stok Yönetimi")

        self.musteri_yonetimi_sayfasi = MusteriYonetimiSayfasi(self.notebook, self.db, self)
        self.notebook.add(self.musteri_yonetimi_sayfasi, text="👥 Müşteri Yönetimi")

        self.tedarikci_yonetimi_sayfasi = TedarikciYonetimiSayfasi(self.notebook, self.db, self)
        self.notebook.add(self.tedarikci_yonetimi_sayfasi, text="🚚 Tedarikçi Yönetimi")

        self.fatura_listesi_sayfasi = FaturaListesiSayfasi(self.notebook, self.db, self)
        self.notebook.add(self.fatura_listesi_sayfasi, text="🧾 Faturalar")

        self.gelir_gider_sayfasi = GelirGiderSayfasi(self.notebook, self.db, self)
        self.notebook.add(self.gelir_gider_sayfasi, text="💸 Gelir/Gider")

        self.finansal_islemler_sayfasi = FinansalIslemlerSayfasi(self.notebook, self.db, self)
        self.notebook.add(self.finansal_islemler_sayfasi, text="💵 Finansal İşlemler")

        self.kasa_banka_yonetimi_sayfasi = KasaBankaYonetimiSayfasi(self.notebook, self.db, self)
        self.notebook.add(self.kasa_banka_yonetimi_sayfasi, text="🏦 Kasa/Banka")

        # Raporlama Merkezi sayfasını ekleme
        self.raporlama_merkezi_sayfasi = RaporlamaMerkeziSayfasi(self.notebook, self.db, self)
        self.notebook.add(self.raporlama_merkezi_sayfasi, text="📊 Raporlar") # Daha genel bir sekme metni


        self.siparis_listesi_sayfasi = SiparisListesiSayfasi(self.notebook, self.db, self)
        self.notebook.add(self.siparis_listesi_sayfasi, text="📋 Sipariş Yönetimi")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)
        self.notebook.select(self.ana_sayfa) # AnaSayfa seçildi.
        print("AnaSayfa seçildi.")

        # Alt barı gridle (artık __init__ içinde tanımlı oldukları için)
        self.bottom_bar_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(2, 5))
        self.status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.notification_label.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        self.notification_label.bind("<Button-1>", self.show_notification_details)

        self.set_status(f"Hoş geldiniz {self.current_user[1]}. Şirket: {self.db.sirket_bilgileri.get('sirket_adi', 'Belirtilmemiş')}")
        print("Durum çubuğu ve bildirim alanı ayarlandı.")

        # İlk bildirim kontrolünü ve kendini programlama çağrısını burada başlatıyoruz.
        self._check_critical_stock()
        self._schedule_critical_stock_check()

    def _gelir_gider_siniflandirma_yonetimi_ac(self):
        """Gelir/Gider Sınıflandırma Yönetimi penceresini açar."""
        from pencereler import GelirGiderSiniflandirmaYonetimiPenceresi
        GelirGiderSiniflandirmaYonetimiPenceresi(self, self.db, yenile_callback=None) # Şimdilik callback yok
        self.set_status("Gelir/Gider Sınıflandırma Yönetimi penceresi açıldı.")

    def register_cari_ekstre_window(self, window):
        """Açık olan Cari Hesap Ekstresi pencerelerini takip etmek için ekler."""
        if window not in self.open_cari_ekstre_windows:
            self.open_cari_ekstre_windows.append(window)

    def unregister_cari_ekstre_window(self, window):
        """Kapatılan Cari Hesap Ekstresi pencerelerini takip listesinden çıkarır."""
        if window in self.open_cari_ekstre_windows:
            self.open_cari_ekstre_windows.remove(window)

    def _run_backfill_script_ui(self):
        """Eksik stok hareketlerini oluşturan veritabanı fonksiyonunu arayüzden tetikler."""
        if not messagebox.askyesno(
            "Onay Gerekli",
            "Bu işlem, geçmiş tüm faturaları tarayarak eksik stok hareketlerini yeniden oluşturacaktır.\n\n"
            "NOT: Bu işlem mevcut fatura kaynaklı tüm stok hareketlerini silip yeniden oluşturur. Sadece bir kez çalıştırmanız yeterlidir.\n\n"
            "Devam etmek istiyor musunuz?",
            icon='warning', parent=self
        ):
            self.set_status("İşlem kullanıcı tarafından iptal edildi.")
            return

        # Bekleme penceresini göster
        bekleme_penceresi = BeklemePenceresi(self, message="Geçmiş veriler işleniyor, lütfen bekleyiniz...")


        def islem_thread():
            success, message = self.db.geriye_donuk_stok_hareketlerini_olustur()

            # Ana thread'e dön ve UI'ı güncelle
            self.after(0, bekleme_penceresi.kapat)
            if success:
                self.after(0, lambda: messagebox.showinfo("Başarılı", message, parent=self))
                self.after(0, lambda: self.set_status(message))
            else:
                self.after(0, lambda: messagebox.showerror("Hata", message, parent=self))
                self.after(0, lambda: self.set_status(f"Geçmiş stok hareketleri oluşturulamadı: {message}"))

        # İşlemi ayrı bir thread'de başlat
        threading.Thread(target=islem_thread).start()

    def refresh_cari_ekstre_windows_for_cari(self, cari_id):
        """Belirli bir cari ID'sine sahip tüm açık cari ekstre pencerelerini yeniler."""
        for window in list(self.open_cari_ekstre_windows):
            if window.cari_id == cari_id:
                try:
                    window.ekstreyi_yukle()
                except Exception as e:
                    print(f"Error refreshing cari ekstre window for ID {cari_id}: {e}")
                    self.unregister_cari_ekstre_window(window)

    def _go_to_report_tab(self, tab_text): # Yeni yardımcı metod
        """Raporlama Merkezi sayfasına gider ve belirtilen sekmeye geçiş yapar."""
        self.notebook.select(self.raporlama_merkezi_sayfasi)
        for tab_id in self.raporlama_merkezi_sayfasi.report_notebook.tabs():
            if self.raporlama_merkezi_sayfasi.report_notebook.tab(tab_id, "text") == tab_text:
                self.raporlama_merkezi_sayfasi.report_notebook.select(tab_id)
                break
        self.set_status(f"Raporlama Merkezi açıldı, '{tab_text}' sekmesine gidildi.")

    def set_status(self, message):
        if hasattr(self, 'status_bar') and self.status_bar is not None:
            self.status_bar.config(text=message)
        else:
            print(f"UYARI: Durum çubuğu mevcut değil veya None. Mesaj: {message}")

    def update_notifications(self):
        # notification_label'ın varlığını burada kontrol etmeye gerek yok, çünkü init'te oluşturuldu.

        critical_items = self.db.get_critical_stock_items()
        overdue_receivables = self.db.get_overdue_receivables()
        overdue_payables = self.db.get_overdue_payables()

        notification_messages = []
        notification_details = {}

        if critical_items:
            notification_messages.append(f"📦 Kritik Stok: {len(critical_items)} ürün!")
            notification_details['critical_stock'] = critical_items

        if overdue_receivables:
            notification_messages.append(f"💰 Vadesi Geçmiş Alacak: {len(overdue_receivables)} müşteri!")
            notification_details['overdue_receivables'] = overdue_receivables

        if overdue_payables:
            notification_messages.append(f"💸 Vadesi Geçmiş Borç: {len(overdue_payables)} tedarikçi!")
            notification_details['overdue_payables'] = overdue_payables

        self.current_notifications = notification_details

        if notification_messages:
            full_message = " | ".join(notification_messages)
            self.notification_label.config(text=f"UYARI: {full_message}", style="Notification.TLabel")
            self.notification_label.pack(side=tk.RIGHT, fill=tk.X, padx=5)
        else:
            self.notification_label.config(text=" ")
            self.notification_label.pack_forget()

        self.after(self.notification_update_interval, self.update_notifications)

    def show_notification_details(self, event=None):
        """Bildirim etiketine tıklandığında detayları gösteren bir pencere açar."""
        if not hasattr(self, 'current_notifications') or not self.current_notifications:
            messagebox.showinfo("Bildirim Detayları", "Şu anda aktif bir bildirim bulunmuyor.", parent=self)
            return

        NotificationDetailsPenceresi(self, self.db, self.current_notifications)

    def kritik_stok_uyarisi_goster_app(self): 
        """Kritik Stok Uyarısı penceresini açar (App menüsünden çağrılır)."""
        CriticalStockWarningPenceresi(self, self.db)
        self.set_status("Kritik Stok Uyarısı penceresi açıldı.")

    def sirket_bilgileri_penceresi_ac(self):
        SirketBilgileriPenceresi(self, self.db)

    def kullanici_yonetimi_penceresi_ac(self):
        if self.current_user and self.current_user[2] == 'admin':
            KullaniciYonetimiPenceresi(self, self.db)
        else:
            messagebox.showwarning("Yetki Hatası", "Bu işlem için admin yetkisine sahip olmalısınız.", parent=self)
    def veri_sifirlama_penceresi_ac(self):
        """Yönetici Ayarları ve Veri Temizleme penceresini açar."""
        if self.current_user and self.current_user[2] == 'admin':
            YoneticiAyarlariPenceresi(self, self.db)
        else:
            messagebox.showwarning("Yetki Hatası", "Bu işlem için admin yetkisine sahip olmalısınız.", parent=self)
    def hakkinda_penceresi_ac(self):
        messagebox.showinfo("Çınar Yapı Ön Muhasebe Programı Hakkında", 
                            "Çınar Yapı Ön Muhasebe Programı\nSürüm: 1.1.0\n\nBu program, küçük ve orta ölçekli işletmelerin temel ön muhasebe ihtiyaçlarını karşılamak üzere tasarlanmıştır.\n\nGeliştirici: [Muhammed Reşit]\nİletişim: [mr755397@gmail.com]", 
                            parent=self)

    def cikis_yap_ve_giris_ekranina_don(self):
        self.current_user = None
        self.title("Çınar Yapı Ön Muhasebe Programı")
        if hasattr(self, 'menubar'): self.config(menu=tk.Menu(self)) # Menubar'ı temizle
        self._clear_window()  
        self.giris_ekrani_goster()

    def _clear_window(self):
        # Menü çubuğunu temizle
        if hasattr(self, 'menubar') and self.winfo_exists():
            self.config(menu=tk.Menu(self))
            del self.menubar # Menubar referansını sil

        if self.notebook and self.notebook.winfo_exists():
            self.notebook.destroy()
            self.notebook = None # Referansı temizle

        for widget in self.winfo_children():
            if widget != self.bottom_bar_frame:
                widget.destroy()


    def set_status(self, message):
        if hasattr(self, 'status_bar') and self.status_bar is not None:
            self.status_bar.config(text=message)
        else:
            print(f"UYARI: Durum çubuğu mevcut değil veya None. Mesaj: {message}")

    def veritabani_yedekle(self):
        hedef_dosya = filedialog.asksaveasfilename(
            defaultextension=".db_backup",
            filetypes=[("Veritabanı Yedekleri", "*.db_backup"), ("Tüm Dosyalar", "*.*")],
            title="Veritabanını Farklı Kaydet",
            initialfile=f"on_muhasebe_yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db_backup",
            parent=self
        )
        if hedef_dosya:
            try:
                shutil.copy2(self.db.db_name, hedef_dosya)
                messagebox.showinfo("Yedekleme Başarılı", f"Veritabanı başarıyla '{hedef_dosya}' adresine yedeklendi.", parent=self)
                self.set_status(f"Veritabanı yedeklendi: {hedef_dosya}")
            except Exception as e:
                messagebox.showerror("Yedekleme Hatası", f"Veritabanı yedeklenirken bir hata oluştu:\n{e}", parent=self)
                self.set_status(f"Veritabanı yedekleme hatası: {e}")

    def veritabani_geri_yukle(self):
        if not (self.current_user and self.current_user[2] == 'admin'):
            messagebox.showwarning("Yetki Gerekli", "Veritabanı geri yükleme işlemi için admin yetkisi gereklidir.", parent=self)
            return

        kaynak_dosya = filedialog.askopenfilename(
            defaultextension=".db_backup",
            filetypes=[("Veritabanı Yedekleri", "*.db_backup"), ("Veritabanı Dosyaları", "*.db"), ("Tüm Dosyalar", "*.*")],
            title="Geri Yüklenecek Veritabanı Yedeğini Seçin",
            parent=self
        )
        if kaynak_dosya:
            if messagebox.askyesno("Geri Yükleme Onayı", 
                                   "DİKKAT!\n\nVeritabanını geri yüklemek mevcut tüm verilerinizi SEÇİLEN YEDEKTEKİ VERİLERLE DEĞİŞTİRECEKTİR.\n\nBu işlem geri alınamaz. Devam etmek istediğinizden emin misiniz?", 
                                   icon='warning', parent=self):
                try:
                    if self.db.conn:
                        self.db.conn.close()

                    shutil.copy2(kaynak_dosya, self.db.db_name)

                    self.db.conn = sqlite3.connect(self.db.db_name)
                    self.db.c = self.db.conn.cursor()
                    self.db.create_tables()
                    self.db.ensure_admin_user(show_messagebox=False) 
                    self.db.sirket_bilgileri = self.db.sirket_bilgilerini_yukle() 

                    messagebox.showinfo("Geri Yükleme Başarılı", f"Veritabanı '{kaynak_dosya}' dosyasından başarıyla geri yüklendi.\nProgram yeniden başlatılacak.", parent=self)
                    self.set_status(f"Veritabanı geri yüklendi. Program yeniden başlatılıyor...")

                    self.cikis_yap_ve_giris_ekranina_don()

                except Exception as e:
                    messagebox.showerror("Geri Yükleme Hatası", f"Veritabanı geri yüklenirken bir hata oluştu:\n{e}\n\nLütfen programı manuel olarak yeniden başlatmayı deneyin.", parent=self)
                    self.set_status(f"Veritabanı geri yükleme hatası: {e}")
                    if self.db.conn: self.db.conn.close() 
                    self.db.conn = None 


    def stok_raporu_excel_ui(self):
        dosya_yolu = filedialog.asksaveasfilename(
            initialfile=f"Stok_Raporu_{datetime.now().strftime('%Y%m%d')}.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel Dosyaları", "*.xlsx")],
            title="Stok Raporunu Kaydet",
            parent=self
        )
        if dosya_yolu:
            # Bekleme penceresini göster
            bekleme_penceresi = BeklemePenceresi(self, message="Stok raporu hazırlanıyor, lütfen bekleyiniz...")

            # Raporlama işlemini ayrı bir thread'de başlat
            threading.Thread(target=lambda: self._generate_stock_report_threaded(
                dosya_yolu, bekleme_penceresi
            )).start()
        else:
            self.set_status("Stok raporu kaydetme iptal edildi.")

    def _generate_stock_report_threaded(self, dosya_yolu, bekleme_penceresi):
        """Stok raporunu ayrı bir thread'de oluşturur ve sonucu ana thread'e iletir."""
        success, message = self.db.stok_raporu_excel_olustur(dosya_yolu)

        # Ana thread'e dön ve UI'ı güncelle
        self.after(0, bekleme_penceresi.kapat) # Bekleme penceresini kapat
        if success:
            self.after(0, lambda: messagebox.showinfo("Başarılı", message, parent=self))
            self.after(0, lambda: self.set_status(message))
        else:
            self.after(0, lambda: messagebox.showerror("Hata", message, parent=self))
            self.after(0, lambda: self.set_status(f"Stok raporu Excel'e aktarılırken hata: {message}"))

    def tarihsel_satis_raporu_ui(self, rapor_tipi):
        dialog = TarihAraligiDialog(self, title="Satış Raporu Tarih Aralığı", baslangic_gun_sayisi=30)
        if dialog.sonuc:
            bas_t, bit_t = dialog.sonuc

            # Bekleme penceresini göster
            bekleme_penceresi = BeklemePenceresi(self, message="Rapor hazırlanıyor, lütfen bekleyiniz...")

            # Raporlama işlemini ayrı bir thread'de başlat
            threading.Thread(target=lambda: self._generate_sales_report_threaded(
                bas_t, bit_t, rapor_tipi, bekleme_penceresi
            )).start()
        else:
            self.set_status("Rapor oluşturma iptal edildi (tarih seçilmedi).")

    def _generate_sales_report_threaded(self, bas_t, bit_t, rapor_tipi, bekleme_penceresi):
        """Tarihsel satış raporunu ayrı bir thread'de oluşturur ve sonucu ana thread'e iletir."""
        success = False
        message = ""
        dosya_yolu = None

        try:
            rapor_verileri = self.db.tarihsel_satis_raporu_verilerini_al(bas_t, bit_t)

            if not rapor_verileri:
                message = "Belirtilen tarih aralığında raporlanacak satış verisi bulunamadı."
                success = False
            else:
                dosya_adi_onek = f"Satis_Raporu_{bas_t}_ile_{bit_t}"
                if rapor_tipi == 'excel':
                    dosya_uzantisi = ".xlsx"
                    kaydetme_fonksiyonu = self.db.tarihsel_satis_raporu_excel_olustur
                elif rapor_tipi == 'pdf':
                    dosya_uzantisi = ".pdf"
                    kaydetme_fonksiyonu = self.db.tarihsel_satis_raporu_pdf_olustur
                else:
                    message = "Geçersiz rapor tipi."
                    success = False

                if success is not False: # Eğer rapor tipi geçerliyse devam et
                    # filedialog'ı ana thread'de çalıştırmak için after kullan
                    self.after(0, lambda: self._show_save_dialog_and_generate_report(
                        bas_t, bit_t, rapor_tipi, dosya_adi_onek, dosya_uzantisi, kaydetme_fonksiyonu, rapor_verileri, bekleme_penceresi
                    ))
                    return # Bu fonksiyondan çık, işlemin devamı _show_save_dialog_and_generate_report içinde olacak

        except Exception as e:
            message = f"Rapor oluşturulurken beklenmeyen bir hata oluştu: {e}\n{traceback.format_exc()}"
            success = False
        finally:
            # Sadece hata olursa bekleme penceresini kapat ve mesaj göster
            if success is False:
                self.after(0, bekleme_penceresi.kapat)
                self.after(0, lambda: messagebox.showerror("Hata", message, parent=self))
                self.after(0, lambda: self.set_status(f"Satış raporu ({rapor_tipi.upper()}) oluşturulurken hata: {message}"))

    def _show_save_dialog_and_generate_report(self, bas_t, bit_t, rapor_tipi, dosya_adi_onek, dosya_uzantisi, kaydetme_fonksiyonu, rapor_verileri, bekleme_penceresi):
        """Kaydetme dialogunu gösterir ve raporu kaydetme fonksiyonunu çağırır."""
        dosya_yolu = filedialog.asksaveasfilename(
            initialfile=f"{dosya_adi_onek}{dosya_uzantisi}",
            defaultextension=dosya_uzantisi,
            filetypes=[(f"{rapor_tipi.upper()} Dosyaları", f"*.{rapor_tipi}")],
            title=f"Tarihsel Satış Raporunu Kaydet ({rapor_tipi.upper()})",
            parent=self
        )
        if dosya_yolu:
            success, message = kaydetme_fonksiyonu(rapor_verileri, dosya_yolu, bas_t, bit_t)
            if success:
                self.set_status(message)
                messagebox.showinfo("Başarılı", message, parent=self)
            else:
                self.set_status(f"Satış raporu ({rapor_tipi.upper()}) aktarılırken hata: {message}")
                messagebox.showerror("Hata", message, parent=self)
        else:
            self.set_status("Rapor kaydetme iptal edildi.")

        bekleme_penceresi.kapat() # İşlem sonunda bekleme penceresini kapat

    def _optimize_database_ui(self):
        """Veritabanı optimizasyon işlemini başlatır ve kullanıcıya geri bildirimde bulunur."""
        if not (self.current_user and self.current_user[2] == 'admin'):
            messagebox.showwarning("Yetki Gerekli", "Veritabanı optimizasyonu için admin yetkisi gereklidir.", parent=self)
            return

        confirm = messagebox.askyesno("Veritabanı Optimizasyonu", 
                                       "Veritabanı dosya boyutunu küçültmek ve performansı artırmak için optimize edilsin mi?\n"
                                       "Bu işlem kısa sürebilir.", 
                                       icon='info', 
                                       parent=self)
        if confirm:
            success, message = self.db.optimize_database()
            if success:
                messagebox.showinfo("Başarılı", message, parent=self)
                self.set_status(message)
            else:
                messagebox.showerror("Hata", message, parent=self)
                self.set_status(f"Veritabanı optimizasyonu başarısız: {message}")

    def ana_sayfa_goster(self): self.notebook.select(self.ana_sayfa)
    def stok_yonetimi_goster(self): self.notebook.select(self.stok_yonetimi_sayfasi)
    def musteri_yonetimi_goster(self): self.notebook.select(self.musteri_yonetimi_sayfasi)
    def tedarikci_yonetimi_goster(self): self.notebook.select(self.tedarikci_yonetimi_sayfasi)
    def fatura_listesi_goster(self): self.notebook.select(self.fatura_listesi_sayfasi)
    def gelir_gider_sayfasi_goster(self): self.notebook.select(self.gelir_gider_sayfasi)
    def tahsilat_sayfasi_goster(self): self.notebook.select(self.tahsilat_sayfasi)
    def odeme_sayfasi_goster(self): self.notebook.select(self.odeme_sayfasi)

    def satis_faturasi_goster(self):
        """Yeni veya mevcut satış faturası oluşturma sayfasını gösterir."""
        self._show_or_create_fatura_tab('SATIŞ')

    def alis_faturasi_goster(self, initial_tedarikci_id=None, initial_urunler=None): 
        """Yeni veya mevcut alış faturası oluşturma sayfasını gösterir."""
        self._show_or_create_fatura_tab('ALIŞ', initial_cari_id=initial_tedarikci_id, initial_urunler=initial_urunler) 
 
    def musteri_siparisi_goster(self, initial_cari_id=None, initial_urunler=None, initial_data=None): # <-- DÜZELTME: initial_data eklendi
        """Yeni müşteri siparişi penceresini açar."""
        SiparisPenceresi(self, self.db, self, 'SATIŞ_SIPARIS', yenile_callback=lambda: self.siparis_listesi_sayfasi.siparis_listesini_yukle() if hasattr(self, 'siparis_listesi_sayfasi') else None, initial_cari_id=initial_cari_id, initial_urunler=initial_urunler, initial_data=initial_data) # <-- DÜZELTME: initial_data parametresi eklendi

    def tedarikci_siparisi_goster(self, initial_cari_id=None, initial_urunler=None, initial_data=None): # <-- DÜZELTME: initial_data eklendi
        """Yeni tedarikçi siparişi penceresini açar."""
        SiparisPenceresi(self, self.db, self, 'ALIŞ_SIPARIS', yenile_callback=lambda: self.siparis_listesi_sayfasi.siparis_listesini_yukle() if hasattr(self, 'siparis_listesi_sayfasi') else None, initial_cari_id=initial_cari_id, initial_urunler=initial_urunler, initial_data=initial_data) # <-- DÜZELTME: initial_data parametresi eklendi

    def _show_or_create_siparis_tab(self, siparis_tipi, initial_cari_id=None, initial_urunler=None):
        """Ortak metot: Sipariş oluşturma sekmesini yönetir (yeni pencere olarak açılacak)."""
        tab_title_prefix = "Yeni Müşteri Siparişi" if siparis_tipi == 'SATIŞ_SIPARIS' else "Yeni Tedarikçi Siparişi"

        siparis_frame = SiparisOlusturmaSayfasi(
            self, 
            self.db, 
            self, 
            siparis_tipi,
            siparis_id_duzenle=None, 
            yenile_callback_liste=lambda: self.siparis_listesi_sayfasi.siparis_listesini_yukle(), 
            initial_cari_id=initial_cari_id,
            initial_urunler=initial_urunler
        )
        siparis_frame.title(f"{tab_title_prefix} ({datetime.now().strftime('%H:%M:%S')})") 
        self.set_status(f"Yeni {siparis_tipi.lower()} oluşturma ekranı açıldı.")

    def _show_or_create_fatura_tab(self, fatura_tipi, initial_cari_id=None, initial_urunler=None, initial_data=None, yenile_callback=None):
        """
        Ortak metot: Fatura oluşturma penceresini yönetir.
        Yeni bir fatura penceresi açar ve taslak verilerini veya başlangıç verilerini iletir.
        """

        # Taslak verisini App'ten al (sadece yeni faturalar için)
        current_temp_data = None
        if fatura_tipi == self.db.FATURA_TIP_SATIS:
            current_temp_data = self.temp_sales_invoice_data
        elif fatura_tipi == self.db.FATURA_TIP_ALIS:
            current_temp_data = self.temp_purchase_invoice_data
        
        # bu veriyi 'current_temp_data' üzerine yazarız. Böylece, pop-up penceresine
        # özel olarak doldurulmuş veri setleri gönderilebilir.
        if initial_data:
            current_temp_data = initial_data

        # FaturaPenceresi sınıfını çağır
        fatura_penceresi = FaturaPenceresi(
            self, # parent (App'in kendisi)
            self.db,
            self, # app_ref
            fatura_tipi,
            duzenleme_id=None, # Yeni bir fatura olduğu için None
            yenile_callback=yenile_callback or self.fatura_listesi_sayfasi.fatura_listesini_yukle if hasattr(self, 'fatura_listesi_sayfasi') and hasattr(self.fatura_listesi_sayfasi, 'fatura_listesini_yukle') else None, # Ana fatura listesini yenilemek için callback
            initial_cari_id=initial_cari_id, # Cari ID'si dışarıdan geliyorsa
            initial_urunler=initial_urunler, # Ürünler dışarıdan geliyorsa
            initial_data=current_temp_data # Taslak verisini veya başlangıç verisini iletiyoruz
        )

        self.set_status(f"Yeni {fatura_tipi.lower()} faturası oluşturma penceresi açıldı.")

    def toplu_veri_ekle_penceresi_ac(self):
        """Toplu veri ekleme penceresini açar."""
        if self.current_user and self.current_user[2] == 'admin':
            TopluVeriEklePenceresi(self, self.db)
            self.set_status("Toplu veri ekleme ekranı açıldı.")
        else:
            messagebox.showwarning("Yetki Hatası", "Bu işlem için admin yetkisine sahip olmalısınız.", parent=self)

if __name__ == "__main__":
    db_manager = OnMuhasebe(db_name='on_muhasebe.db', data_dir=data_dir) # data_dir parametresi eklendi
    app = App(db_manager=db_manager)
    db_manager.app = app
    app.ana_arayuzu_baslat((1, "test_admin", "admin"))
    app.mainloop()