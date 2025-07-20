import sys
import os
import logging
import traceback
from datetime import datetime, date, timedelta
import multiprocessing
import threading
import sqlite3
import shutil
# PySide6 modülleri
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QPushButton, QTabWidget, QStatusBar, QMessageBox, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer # QTimer eklendi
from PySide6.QtGui import QIcon, QPixmap, QFont, QPalette, QColor

# Yerel Uygulama Modülleri
from veritabani import OnMuhasebe
from hizmetler import FaturaService, TopluIslemService
from yardimcilar import setup_locale
from arayuz import MusteriYonetimiSayfasi, TedarikciYonetimiSayfasi, AnaSayfa, StokYonetimiSayfasi,FaturaListesiSayfasi,RaporlamaMerkeziSayfasi,GelirGiderSayfasi,FinansalIslemlerSayfasi,SiparisListesiSayfasi,KasaBankaYonetimiSayfasi
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
logging.basicConfig(filename=log_file_path, level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')


# _pdf_olusturma_islemi fonksiyonu, multiprocessing kullandığı için ayrı bir fonksiyon olarak kalabilir.
# Ancak PySide6'da da main thread'i bloklamamak adına thread/process kullanımı önemlidir.
def _pdf_olusturma_islemi(db_name_path, cari_tip, cari_id, bas_t, bit_t, dosya_yolu, result_queue):
    try:
        temp_db_manager = OnMuhasebe(db_name=db_name_path)
        success, message = temp_db_manager.cari_ekstresi_pdf_olustur(cari_tip, cari_id, bas_t, bit_t, dosya_yolu)
        result_queue.put((success, message))
    except Exception as e:
        error_message = f"PDF işleminde hata: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        result_queue.put((False, error_message))
    finally:
        if 'temp_db_manager' in locals() and temp_db_manager.conn:
            temp_db_manager.conn.close()

# main.py içinde PySide6 tabanlı App sınıfı
# main.py dosyasındaki App sınıfının içindeki __init__ metodunun GÜNCELLENMİŞ HALİ
class App(QMainWindow):
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        
        self.pages = {} # Açılan sayfaları (widget'ları) saklamak için bir sözlük

        self.setWindowTitle("Çınar Yapı Ön Muhasebe Programı")
        self.showMaximized()
        self.setMinimumSize(800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.notification_label = QLabel("")
        self.notification_label.setStyleSheet("background-color: #FFD2D2; color: red; font-weight: bold; padding: 5px;")
        self.notification_label.setAlignment(Qt.AlignCenter)
        self.notification_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.status_bar.addPermanentWidget(self.notification_label)
        self.notification_label.setVisible(False)
        
        self.login_user_and_start_main_ui((1, "admin", "admin"))

    def login_user_and_start_main_ui(self, user_info):
        self.current_user = user_info
        self.setWindowTitle(f"Çınar Yapı Ön Muhasebe - Hoş Geldiniz, {self.current_user[1]} ({self.current_user[2].capitalize()})")
        self.set_status_message(f"Hoş geldiniz, {self.current_user[1]}")
        
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.main_layout.addWidget(self.tab_widget)

        self._create_menu_bar()
        
        self.show_tab("Ana Sayfa")

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        # Dosya Menüsü
        file_menu = menu_bar.addMenu("Dosya")
        file_menu.addAction("Şirket Bilgileri", self.show_company_info)
        file_menu.addSeparator()
        file_menu.addAction("Veritabanı Yedekle", self.backup_database)
        file_menu.addAction("Veritabanı Geri Yükle", self.restore_database)
        file_menu.addSeparator()
        file_menu.addAction("Çıkış Yap", self.logout_and_show_login)
        file_menu.addAction("Programdan Çık", self.close) # QMainWindow'un close metodu

        # Yönetim Menüsü (sadece admin ise)
        if self.current_user and self.current_user[2] == 'admin':
            admin_menu = menu_bar.addMenu("Yönetim")
            admin_menu.addAction("Kullanıcı Yönetimi", self.show_user_management)
            admin_menu.addSeparator()
            admin_menu.addAction("Toplu Veri Ekle", self.show_bulk_data_import)
            admin_menu.addAction("Gelir/Gider Sınıflandırma Yönetimi", self.show_income_expense_category_management)
            admin_menu.addAction("Veri Sıfırlama ve Temizleme", self.show_admin_utilities)
            admin_menu.addSeparator()
            admin_menu.addAction("Log Dosyasını Sıfırla", self.clear_log_file_ui)
            admin_menu.addAction("Veritabanını Optimize Et", self.optimize_database_ui)
            admin_menu.addAction("Eksik Stok Hareketlerini Oluştur (Tek Seferlik)", self.run_backfill_script_ui)
        
        # Raporlar Menüsü
        reports_menu = menu_bar.addMenu("Raporlar")
        reports_menu.addAction("Stok Raporu (Excel)", lambda: self.show_report_excel("Stok"))
        reports_menu.addAction("Tarihsel Satış Raporu (Excel)", lambda: self.show_report_excel("Satış"))
        reports_menu.addAction("Tarihsel Satış Raporu (PDF)", lambda: self.show_report_pdf("Satış"))
        reports_menu.addAction("Nakit Akış Raporu", lambda: self.show_report("Nakit Akışı")) # Şimdilik placeholder
        reports_menu.addAction("Kâr/Zarar Raporu", lambda: self.show_report("Kâr ve Zarar")) # Şimdilik placeholder
        reports_menu.addSeparator()
        reports_menu.addAction("Finansal Raporlar ve Analiz", lambda: self.show_report("Genel Bakış")) # QTabWidget'a yönlendirme
        reports_menu.addSeparator()
        reports_menu.addAction("Kritik Stok Uyarısı", self.show_critical_stock_warning)
        reports_menu.addAction("Cari Hesap Yaşlandırma Raporu", lambda: self.show_report("Cari Hesaplar")) # QTabWidget'a yönlendirme

        # Hızlı Erişim Menüsü
        quick_access_menu = menu_bar.addMenu("Hızlı Erişim")
        # Örnek kısayollar. PySide'da kısayollar farklı entegre edilir.
        quick_access_menu.addAction("Ana Sayfa", self.show_home_page)
        quick_access_menu.addAction("Yeni Satış Faturası", lambda: self.show_invoice_form("SATIŞ"))
        quick_access_menu.addAction("Yeni Alış Faturası", lambda: self.show_invoice_form("ALIŞ"))
        quick_access_menu.addAction("Fatura Listesi", lambda: self.show_tab("Faturalar"))
        quick_access_menu.addAction("Stok Yönetimi", lambda: self.show_tab("Stok Yönetimi"))
        quick_access_menu.addAction("Müşteri Yönetimi", lambda: self.show_tab("Müşteri Yönetimi"))
        quick_access_menu.addAction("Tedarikçi Yönetimi", lambda: self.show_tab("Tedarikçi Yönetimi"))
        quick_access_menu.addAction("Finansal İşlemler", lambda: self.show_tab("Finansal İşlemler"))
        quick_access_menu.addAction("Kasa/Banka Yönetimi", lambda: self.show_tab("Kasa/Banka"))
        quick_access_menu.addAction("Yeni Müşteri Siparişi", lambda: self.show_order_form("SATIŞ_SIPARIS"))
        quick_access_menu.addAction("Yeni Tedarikçi Siparişi", lambda: self.show_order_form("ALIŞ_SIPARIS"))
        quick_access_menu.addAction("Sipariş Listesi", lambda: self.show_tab("Sipariş Yönetimi"))


    # --- PySide6'ya özel metotlar ---
    def set_status_message(self, message):
        self.status_bar.showMessage(message)

    def _check_critical_stock(self):
        critical_items = self.db.get_critical_stock_items()
        overdue_receivables = self.db.get_overdue_receivables()
        overdue_payables = self.db.get_overdue_payables()

        notification_messages = []
        self.current_notifications = {} # Detay penceresi için saklanacak veriler

        if critical_items:
            notification_messages.append(f"📦 Kritik Stok: {len(critical_items)} ürün!")
            self.current_notifications['critical_stock'] = critical_items

        if overdue_receivables:
            notification_messages.append(f"💰 Vadesi Geçmiş Alacak: {len(overdue_receivables)} müşteri!")
            self.current_notifications['overdue_receivables'] = overdue_receivables

        if overdue_payables:
            notification_messages.append(f"💸 Vadesi Geçmiş Borç: {len(overdue_payables)} tedarikçi!")
            self.current_notifications['overdue_payables'] = overdue_payables

        if notification_messages:
            full_message = " | ".join(notification_messages)
            self.notification_label.setText(f"UYARI: {full_message}")
            self.notification_label.setVisible(True)
        else:
            self.notification_label.setText("")
            self.notification_label.setVisible(False)

    # --- Menü komutları için placeholder metotlar (şimdilik) ---
    def show_company_info(self):
        QMessageBox.information(self, "Şirket Bilgileri", "Şirket Bilgileri Formu burada açılacak.")

    def backup_database(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Veritabanını Yedekle", "on_muhasebe_yedek.db_backup", "Veritabanı Yedekleri (*.db_backup);;Tüm Dosyalar (*)")
        if file_path:
            try:
                # Kapatma ve kopyalama işlemleri Tkinter dışına taşınmalı ve PySide'a uygun hale getirilmeli
                # Örnek: shutil.copy2(self.db.db_name, file_path)
                # Başarılı mesajı PySide'da QMessageBox ile
                self.set_status_message(f"Veritabanı yedeklendi: {file_path}")
                QMessageBox.information(self, "Yedekleme", f"Veritabanı başarıyla yedeklendi: {file_path}")
            except Exception as e:
                self.set_status_message(f"Yedekleme hatası: {e}")
                QMessageBox.critical(self, "Hata", f"Yedekleme sırasında hata: {e}")

    def restore_database(self):
        if self.current_user is None or self.current_user[2] != 'admin':
            QMessageBox.warning(self, "Yetki Hatası", "Veritabanı geri yükleme işlemi için admin yetkisi gereklidir.")
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "Veritabanı Yedeği Seç", "", "Veritabanı Yedekleri (*.db_backup *.db);;Tüm Dosyalar (*)")
        if file_path:
            reply = QMessageBox.question(self, "Geri Yükleme Onayı", "DİKKAT!\n\nVeritabanını geri yüklemek mevcut tüm verilerinizi SEÇİLEN YEDEKTEKİ VERİLERLE DEĞİŞTİRECEKTİR.\n\nBu işlem geri alınamaz. Devam etmek istediğinizden emin misiniz?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                try:
                    # Mevcut db bağlantısını kapat
                    if self.db.conn:
                        self.db.conn.close()

                    # Yedek dosyayı ana veritabanı dosyasının üzerine kopyala
                    shutil.copy2(file_path, self.db.db_name)

                    # Yeni bağlantıyı kur
                    self.db.conn = sqlite3.connect(self.db.db_name)
                    self.db.conn.row_factory = sqlite3.Row
                    self.db.c = self.db.conn.cursor()
                    self.db.create_tables() # Tabloları yeniden oluştur/kontrol et
                    self.db.ensure_admin_user() # Admin kullanıcısının varlığını kontrol et
                    self.db.sirket_bilgileri = self.db.sirket_bilgilerini_yukle() # Şirket bilgilerini yeniden yükle

                    QMessageBox.information(self, "Geri Yükleme Başarılı", "Veritabanı başarıyla geri yüklendi.\nProgram yeniden başlatılacak.")
                    self.logout_and_show_login() # Programı yeniden başlatmak için giriş ekranına dön
                except Exception as e:
                    QMessageBox.critical(self, "Geri Yükleme Hatası", f"Veritabanı geri yüklenirken hata: {e}")
                    # Hata durumunda bağlantıyı tekrar kapatmak iyi bir uygulama olabilir.
                    if self.db.conn: self.db.conn.close()
                    self.db.conn = None # Bağlantıyı None yap

    def logout_and_show_login(self):
        self.current_user = None
        self.setWindowTitle("Çınar Yapı Ön Muhasebe Programı")
        # Login ekranını burada gösterme mantığı daha sonra eklenecek.
        # Şimdilik uygulamayı yeniden başlatma gibi düşünebiliriz.
        QMessageBox.information(self, "Çıkış Yapıldı", "Başarıyla çıkış yaptınız. Uygulama yeniden başlatılıyor.")
        QApplication.quit() # Uygulamayı kapatıp tekrar çalıştırmasını bekleyeceğiz.

    def show_user_management(self):
        if self.current_user is None or self.current_user[2] != 'admin':
            QMessageBox.warning(self, "Yetki Hatası", "Bu işlem için admin yetkisine sahip olmalısınız.")
            return
        QMessageBox.information(self, "Kullanıcı Yönetimi", "Kullanıcı Yönetimi penceresi burada açılacak.")

    def show_bulk_data_import(self):
        if self.current_user is None or self.current_user[2] != 'admin':
            QMessageBox.warning(self, "Yetki Hatası", "Bu işlem için admin yetkisine sahip olmalısınız.")
            return
        QMessageBox.information(self, "Toplu Veri Ekle", "Toplu Veri Ekleme penceresi burada açılacak.")

    def show_income_expense_category_management(self):
        QMessageBox.information(self, "Gelir/Gider Sınıflandırma", "Gelir/Gider Sınıflandırma Yönetimi penceresi burada açılacak.")

    def show_admin_utilities(self):
        if self.current_user is None or self.current_user[2] != 'admin':
            QMessageBox.warning(self, "Yetki Hatası", "Bu işlem için admin yetkisine sahip olmalısınız.")
            return
        QMessageBox.information(self, "Yönetici Ayarları", "Veri Sıfırlama ve Temizleme penceresi burada açılacak.")

    def clear_log_file_ui(self):
        if self.current_user is None or self.current_user[2] != 'admin':
            QMessageBox.warning(self, "Yetki Gerekli", "Logları sıfırlama işlemi için admin yetkisi gereklidir.")
            return
        reply = QMessageBox.question(self, "Logları Sıfırla Onayı", "Log dosyasının içeriğini sıfırlamak istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.db.clear_log_file()
            if success:
                QMessageBox.information(self, "Başarılı", message)
                self.set_status_message(message)
            else:
                QMessageBox.critical(self, "Hata", message)
                self.set_status_message(f"Logları sıfırlama başarısız: {message}")

    def optimize_database_ui(self):
        if self.current_user is None or self.current_user[2] != 'admin':
            QMessageBox.warning(self, "Yetki Gerekli", "Veritabanı optimizasyonu için admin yetkisi gereklidir.")
            return
        reply = QMessageBox.question(self, "Veritabanı Optimizasyonu", "Veritabanı dosya boyutunu küçültmek ve performansı artırmak için optimize edilsin mi?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.db.optimize_database()
            if success:
                QMessageBox.information(self, "Başarılı", message)
                self.set_status_message(message)
            else:
                QMessageBox.critical(self, "Hata", message)
                self.set_status_message(f"Veritabanı optimizasyonu başarısız: {message}")

    def run_backfill_script_ui(self):
        if self.current_user is None or self.current_user[2] != 'admin':
            QMessageBox.warning(self, "Yetki Gerekli", "Bu işlem için admin yetkisi gereklidir.")
            return
        reply = QMessageBox.question(self, "Onay Gerekli", "Bu işlem, geçmiş tüm faturaları tarayarak eksik stok hareketlerini yeniden oluşturacaktır.\n\nNOT: Bu işlem mevcut fatura kaynaklı tüm stok hareketlerini silip yeniden oluşturur. Sadece bir kez çalıştırmanız yeterlidir.\n\nDevam etmek istiyor musunuz?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.set_status_message("Geçmiş veriler işleniyor, lütfen bekleyiniz...")
            # Arka planda çalışacak işlem için threading kullanacağız
            threading.Thread(target=self._run_backfill_threaded).start()
        else:
            self.set_status_message("İşlem kullanıcı tarafından iptal edildi.")

    def _run_backfill_threaded(self):
        success, message = self.db.geriye_donuk_stok_hareketlerini_olustur()
        # UI güncellemeleri için ana thread'e geri dönmeliyiz
        self.statusBar().showMessage(message) # PyQt'de doğrudan erişim
        if success:
            QMessageBox.information(self, "Başarılı", message)
        else:
            QMessageBox.critical(self, "Hata", message)

    def show_report_excel(self, report_type):
        QMessageBox.information(self, "Raporlama", f"{report_type} Raporu (Excel) burada oluşturulacak.")

    def show_report_pdf(self, report_type):
        QMessageBox.information(self, "Raporlama", f"{report_type} Raporu (PDF) burada oluşturulacak.")

    def show_report(self, tab_name):
        QMessageBox.information(self, "Raporlama", f"Raporlama Merkezi açılacak ve '{tab_name}' sekmesine gidilecek.")

    def show_critical_stock_warning(self):
        # CriticalStockWarningPenceresi'nin PySide6 versiyonu burada çağrılacak.
        # Şimdilik bir mesaj kutusu gösterelim.
        QMessageBox.information(self, "Kritik Stok Uyarısı", "Kritik Stok Uyarısı penceresi burada açılacak.")

    def show_home_page(self):
        self.set_status_message("Ana Sayfa gösteriliyor.")

    def show_invoice_form(self, invoice_type):
        QMessageBox.information(self, "Fatura Oluştur", f"Yeni {invoice_type} faturası formu burada açılacak.")

    def show_tab(self, page_name: str):
        if page_name in self.pages:
            # Eğer sayfa zaten açıksa, o sekmeye geç
            self.tab_widget.setCurrentWidget(self.pages[page_name])
            return

        widget = None
        if page_name == "Ana Sayfa":
            widget = AnaSayfa(self, self.db, self)
        elif page_name == "Stok Yönetimi":
            widget = StokYonetimiSayfasi(self, self.db, self)
        elif page_name == "Müşteri Yönetimi":
            widget = MusteriYonetimiSayfasi(self, self.db, self)
        elif page_name == "Tedarikçi Yönetimi":
            widget = TedarikciYonetimiSayfasi(self, self.db, self)
        elif page_name == "Kasa/Banka":
            widget = KasaBankaYonetimiSayfasi(self, self.db, self)
        elif page_name == "Faturalar":
            widget = FaturaListesiSayfasi(self, self.db, self)
        elif page_name == "Sipariş Yönetimi":
            widget = SiparisListesiSayfasi(self, self.db, self)
        elif page_name == "Finansal İşlemler":
            widget = FinansalIslemlerSayfasi(self, self.db, self)
        elif page_name == "Gelir/Gider":
            widget = GelirGiderSayfasi(self, self.db, self)
        elif page_name == "Raporlama Merkezi":
            widget = RaporlamaMerkeziSayfasi(self, self.db, self)

        if widget:
            self.pages[page_name] = widget
            index = self.tab_widget.addTab(widget, page_name)
            self.tab_widget.setCurrentIndex(index)
            # Sayfa yüklendikten sonra listeyi yenileme (eğer varsa)
            if hasattr(widget, 'stok_listesini_yenile'):
                widget.stok_listesini_yenile()
            elif hasattr(widget, 'musteri_listesini_yenile'):
                widget.musteri_listesini_yenile()
            elif hasattr(widget, 'tedarikci_listesini_yenile'):
                widget.tedarikci_listesini_yenile()
            elif hasattr(widget, 'hesap_listesini_yenile'):
                widget.hesap_listesini_yenile()
            elif hasattr(widget, 'fatura_listesini_yukle'):
                widget.fatura_listesini_yukle()
            elif hasattr(widget, 'siparis_listesini_yukle'):
                widget.siparis_listesini_yukle()
            elif hasattr(widget, 'gg_listesini_yukle'):
                widget.gg_listesini_yukle()
            elif hasattr(widget, 'raporu_olustur_ve_yenile'):
                widget.raporu_olustur_ve_yenile()
            
            # self.app.set_status_message yerine doğrudan self.set_status_message kullan
            self.set_status_message(f"'{page_name}' sekmesi açıldı.") # <-- Burası güncellendi
        else:
            QMessageBox.information(self, "Sekme Değiştir", f"'{page_name}' sekmesi henüz programa eklenmedi.")
            # self.app.set_status_message yerine doğrudan self.set_status_message kullan
            self.set_status_message(f"Hata: '{page_name}' sekmesi açılamadı.") # <-- Burası güncellendi


    def close_tab(self, index):
        widget = self.tab_widget.widget(index)
        if widget is not None:
            page_name = self.tab_widget.tabText(index)
            if page_name in self.pages:
                del self.pages[page_name]
            widget.deleteLater()
            self.tab_widget.removeTab(index)

    def show_order_form(self, order_type):
        QMessageBox.information(self, "Sipariş Oluştur", f"Yeni {order_type} sipariş formu burada açılacak.")

    def show_notification_details(self, event=None):
        if not hasattr(self, 'current_notifications') or not self.current_notifications:
            QMessageBox.information(self, "Bildirim Detayları", "Şu anda aktif bir bildirim bulunmuyor.")
            return
        # NotificationDetailsPenceresi'nin PySide6 versiyonu burada çağrılacak.
        # Şimdilik bir mesaj kutusu gösterelim.
        QMessageBox.information(self, "Bildirim Detayları", "Bildirim detayları penceresi burada açılacak.")


if __name__ == "__main__":
    setup_locale() 
    
    app = QApplication(sys.argv)
    
    # --- GÜNCELLENMİŞ: Beyaz Tema Ayarları ---
    app.setStyle("Fusion")

    # Yeni, özel bir beyaz palet oluşturuyoruz
    beyaz_palet = QPalette()

    # Pencere arka planları için renkleri ayarla
    beyaz_palet.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))        # Ana pencere arka planı (beyaz)
    beyaz_palet.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))            # Ana yazı rengi (siyah)
    
    # Yazı giriş alanları (QLineEdit, QTextEdit vb.) için renkleri ayarla
    beyaz_palet.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))           # Entry arka planı (beyaz)
    beyaz_palet.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))                 # Entry yazı rengi (siyah)
    beyaz_palet.setColor(QPalette.ColorRole.PlaceholderText, QColor(120, 120, 120)) # Placeholder yazı rengi (gri)

    # Butonlar ve diğer arayüz elemanları için renkleri ayarla
    beyaz_palet.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))         # Buton arka planı (hafif gri)
    beyaz_palet.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))           # Buton yazı rengi (siyah)
    
    # Vurgu rengi (örneğin seçili öğeler için)
    beyaz_palet.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))       # Standart mavi
    beyaz_palet.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255)) # Vurgulu yazı (beyaz)

    # Uygulamaya yeni paletimizi tanıtıyoruz
    app.setPalette(beyaz_palet)
    # --- DEĞİŞİKLİK SONU ---
    
    # Kodun geri kalanı aynı
    db_manager = OnMuhasebe(data_dir=data_dir)
    
    main_app_window = App(db_manager=db_manager)
    main_app_window.show() 
    
    sys.exit(app.exec())