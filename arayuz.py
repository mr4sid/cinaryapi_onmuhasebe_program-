#arayuz.py dosyası içeriği
import os
import shutil
import calendar
import logging
import traceback
import multiprocessing
import threading
from datetime import datetime, date, timedelta
import locale # Yeni: Sayısal formatlama için eklendi
# PySide6 modülleri
from PySide6.QtWidgets import (
    QWidget,QDialog, QLabel, QPushButton, QTabWidget, QMessageBox,
    QGridLayout, QVBoxLayout, QHBoxLayout, QFrame,
    QLineEdit, QMainWindow, QFileDialog, QComboBox, QTreeWidget, QTreeWidgetItem, QAbstractItemView,
    QHeaderView, QTextEdit, QScrollArea, QMenu # QTextEdit, QScrollArea ve QMenu eklendi
)
from PySide6.QtCore import Qt, QTimer, Signal # Qt.Align* için Qt, QTimer ve Signal
from PySide6.QtGui import QIcon, QPixmap, QFont, QBrush, QColor, QDoubleValidator # QBrush, QColor, QDoubleValidator eklendi

# Üçüncü Parti Kütüphaneler (PySide6 ile uyumlu olanlar kalır)
import openpyxl
from PIL import Image
# Matplotlib importları (PySide6 ile entegrasyon için)
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas # PySide6 (Qt) için Matplotlib Canvas
from matplotlib.figure import Figure

# Yerel Uygulama Modülleri
from veritabani import OnMuhasebe
from hizmetler import FaturaService, TopluIslemService
from pencereler import YeniMusteriEklePenceresi, YeniTedarikciEklePenceresi, StokKartiPenceresi,YeniKasaBankaEklePenceresi
from yardimcilar import DatePickerDialog, normalize_turkish_chars, setup_locale
from datetime import datetime
import requests 
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFrame, QVBoxLayout, 
    QHBoxLayout, QGridLayout, QSizePolicy # QSizePolicy eklendi
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from config import API_BASE_URL
# AnaSayfa Sınıfının Tamamı
class AnaSayfa(QWidget):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        
        self.main_layout = QGridLayout(self)
        
        # Header Frame (Şirket Adı)
        self.header_frame = QFrame(self)
        self.header_layout = QHBoxLayout(self.header_frame)
        self.main_layout.addWidget(self.header_frame, 0, 0, 1, 1)
        self.header_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.sirket_adi_label = QLabel("")
        self.sirket_adi_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        self.header_layout.addWidget(self.sirket_adi_label, alignment=Qt.AlignLeft)

        # --- Metrik Kartlar Alanı ---
        self.metrics_container_frame = QFrame(self)
        self.metrics_container_layout = QGridLayout(self.metrics_container_frame)
        self.main_layout.addWidget(self.metrics_container_frame, 1, 0, 1, 1)
        self.metrics_container_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        for i in range(6):
            self.metrics_container_layout.setColumnStretch(i, 1)

        # Metrik Kartları Oluşturma
        self.card_satislar = self._create_metric_card(self.metrics_container_frame, "Bugünkü Satışlar", "Yükleniyor...", "sales")
        self.metrics_container_layout.addWidget(self.card_satislar, 0, 0)

        self.card_tahsilatlar = self._create_metric_card(self.metrics_container_frame, "Bugünkü Tahsilatlar", "Yükleniyor...", "collections")
        self.metrics_container_layout.addWidget(self.card_tahsilatlar, 0, 1)

        self.card_kritik_stok = self._create_metric_card(self.metrics_container_frame, "Kritik Stok Ürün", "Yükleniyor...", "critical_stock")
        self.metrics_container_layout.addWidget(self.card_kritik_stok, 0, 2)
        
        self.card_top_satan_urun = self._create_metric_card(self.metrics_container_frame, "Ayın En Çok Satan Ürünü", "Yükleniyor...", "top_selling")
        self.metrics_container_layout.addWidget(self.card_top_satan_urun, 0, 3)

        self.card_vadesi_gecmis_alacak = self._create_metric_card(self.metrics_container_frame, "Vadesi Geçmiş Alacak", "Yükleniyor...", "overdue_receivables")
        self.metrics_container_layout.addWidget(self.card_vadesi_gecmis_alacak, 0, 4)

        self.card_vadesi_gecmis_borc = self._create_metric_card(self.metrics_container_frame, "Vadesi Geçmiş Borç", "Yükleniyor...", "overdue_payables")
        self.metrics_container_layout.addWidget(self.card_vadesi_gecmis_borc, 0, 5)

        # --- Ana Butonlar Alanı ---
        self.buttons_container_frame = QFrame(self)
        self.buttons_container_layout = QGridLayout(self.buttons_container_frame)
        self.main_layout.addWidget(self.buttons_container_frame, 2, 0, 1, 1)
        self.buttons_container_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        for i in range(3):
            self.buttons_container_layout.setColumnStretch(i, 1)

        buttons_info = [
            ("Yeni Satış Faturası", lambda: self.app.show_invoice_form("SATIŞ"), "🛍️"),
            ("Yeni Alış Faturası", lambda: self.app.show_invoice_form("ALIŞ"), "🛒"),
            ("Fatura Listesi", lambda: self.app.show_tab("Faturalar"), "🧾"),
            ("Stok Yönetimi", lambda: self.app.show_tab("Stok Yönetimi"), "📦"),
            ("Müşteri Yönetimi", lambda: self.app.show_tab("Müşteri Yönetimi"), "👥"),
            ("Gelir/Gider", lambda: self.app.show_tab("Gelir/Gider"), "💸"),
            ("Ödeme/Tahsilat", lambda: self.app.show_tab("Finansal İşlemler"), "💰"),
            ("Sipariş Yönetimi", lambda: self.app.show_tab("Sipariş Yönetimi"), "📋"),
            ("Kasa/Banka Yönetimi", lambda: self.app.show_tab("Kasa/Banka"), "🏦")
        ]

        for i, (text, command, icon) in enumerate(buttons_info):
            row, col = divmod(i, 3) 
            button = QPushButton(f"{icon} {text}")
            button.setFont(QFont("Segoe UI", 20, QFont.Bold))
            button.setStyleSheet("padding: 12px;")
            button.clicked.connect(command)
            self.buttons_container_layout.addWidget(button, row, col)

        self.guncelle_sirket_adi()
        self.guncelle_ozet_bilgiler()

    def _create_metric_card(self, parent_frame, title, initial_value, card_type):
        card_frame = QFrame(parent_frame)
        card_frame.setFrameShape(QFrame.StyledPanel)
        card_frame.setFrameShadow(QFrame.Raised)
        card_frame.setLineWidth(2)
        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(15, 15, 15, 15)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title_label)

        value_label = QLabel(initial_value)
        value_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        value_label.setStyleSheet("color: navy;")
        value_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(value_label)

        setattr(self, f"lbl_metric_{card_type}", value_label)
        return card_frame

    def guncelle_sirket_adi(self):
        # TODO: Bu metot, şirket bilgilerini API'den çekecek şekilde güncellenecek.
        # Şimdilik hata vermemesi için statik bir değer atıyoruz.
        sirket_adi = "Şirket Adı (API'den Gelecek)"
        self.sirket_adi_label.setText(f"Hoş Geldiniz, {sirket_adi}")

    def guncelle_ozet_bilgiler(self):
        # TODO: Bu metot, tüm özet bilgileri API'den çekecek şekilde güncellenecek.
        # Şimdilik hata vermemesi için statik değerler atıyoruz.
        self.lbl_metric_sales.setText("0,00 TL")
        self.lbl_metric_collections.setText("0,00 TL")
        self.lbl_metric_critical_stock.setText("0 adet")
        self.lbl_metric_top_selling.setText("---")
        self.lbl_metric_overdue_receivables.setText("0,00 TL")
        self.lbl_metric_overdue_payables.setText("0,00 TL")
        print("AnaSayfa: Özet bilgiler güncellendi (placeholder).")
                
class FinansalIslemlerSayfasi(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.setLayout(QVBoxLayout(self)) # Ana layout QVBoxLayout

        self.layout().addWidget(QLabel("Finansal İşlemler (Tahsilat / Ödeme)", 
                                       font=QFont("Segoe UI", 16, QFont.Bold)))

        # Finansal işlemler için ana QTabWidget (Tahsilat ve Ödeme sekmeleri için)
        self.main_tab_widget = QTabWidget(self)
        self.layout().addWidget(self.main_tab_widget)

        # Tahsilat Sekmesi (Placeholder - Daha sonra gerçek içeriği eklenecek)
        self.tahsilat_frame = TahsilatSayfasi(self.main_tab_widget, self.db, self.app)
        self.main_tab_widget.addTab(self.tahsilat_frame, "💰 Tahsilat Girişi")

        # Ödeme Sekmesi (Placeholder - Daha sonra gerçek içeriği eklenecek)
        self.odeme_frame = OdemeSayfasi(self.main_tab_widget, self.db, self.app)
        self.main_tab_widget.addTab(self.odeme_frame, "💸 Ödeme Girişi")
        
        # Sekme değiştiğinde ilgili formu yenilemek için bir olay bağlayabiliriz
        self.main_tab_widget.currentChanged.connect(self._on_tab_change)

    def _on_tab_change(self, index):
        selected_widget = self.main_tab_widget.widget(index)
        selected_tab_text = self.main_tab_widget.tabText(index)

        # Bu kısım, TahsilatSayfasi ve OdemeSayfasi PySide6'ya dönüştürüldüğünde etkinleşecektir.
        # Şimdilik placeholder metotları çağırıyoruz.
        if selected_tab_text == "💰 Tahsilat Girişi":
            if hasattr(self.tahsilat_frame, '_yukle_ve_cachele_carileri'):
                self.tahsilat_frame._yukle_ve_cachele_carileri()
            if hasattr(self.tahsilat_frame, '_yukle_kasa_banka_hesaplarini'):
                self.tahsilat_frame._yukle_kasa_banka_hesaplarini()
            if hasattr(self.tahsilat_frame, 'tarih_entry'): # QLineEdit için
                self.tahsilat_frame.tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
            if hasattr(self.tahsilat_frame, 'tutar_entry'): # QLineEdit için
                self.tahsilat_frame.tutar_entry.setText("")
            if hasattr(self.tahsilat_frame, 'odeme_sekli_combo'): # QComboBox için
                self.tahsilat_frame.odeme_sekli_combo.setCurrentText(self.db.ODEME_TURU_NAKIT)
            if hasattr(self.tahsilat_frame, '_odeme_sekli_degisince'):
                self.tahsilat_frame._odeme_sekli_degisince()

        elif selected_tab_text == "💸 Ödeme Girişi":
            if hasattr(self.odeme_frame, '_yukle_ve_cachele_carileri'):
                self.odeme_frame._yukle_ve_cachele_carileri()
            if hasattr(self.odeme_frame, '_yukle_kasa_banka_hesaplarini'):
                self.odeme_frame._yukle_kasa_banka_hesaplarini()
            if hasattr(self.odeme_frame, 'tarih_entry'): # QLineEdit için
                self.odeme_frame.tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
            if hasattr(self.odeme_frame, 'tutar_entry'): # QLineEdit için
                self.odeme_frame.tutar_entry.setText("")
            if hasattr(self.odeme_frame, 'odeme_sekli_combo'): # QComboBox için
                self.odeme_frame.odeme_sekli_combo.setCurrentText(self.db.ODEME_TURU_NAKIT)
            if hasattr(self.odeme_frame, '_odeme_sekli_degisince'):
                self.odeme_frame._odeme_sekli_degisince()

class StokYonetimiSayfasi(QWidget):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager # _format_currency gibi yardımcı metotlar için kalabilir
        self.app = app_ref
        
        self.main_layout = QGridLayout(self)
        
        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)
        
        # Arayüz elemanlarını oluşturma (bu kısım sizin orijinal kodunuzdan alınmıştır)
        # Başlık
        title_label = QLabel("STOK YÖNETİM SİSTEMİ")
        title_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.main_layout.addWidget(title_label, 0, 0, 1, 1, Qt.AlignLeft | Qt.AlignTop)

        # Filtreleme Çerçevesi
        top_filter_and_action_frame = QFrame(self)
        top_filter_and_action_layout = QGridLayout(top_filter_and_action_frame)
        self.main_layout.addWidget(top_filter_and_action_frame, 1, 0, 1, 1)
        top_filter_and_action_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_filter_and_action_layout.setColumnStretch(1, 1)

        row_idx = 0
        top_filter_and_action_layout.addWidget(QLabel("Ürün Kodu/Adı:"), row_idx, 0, Qt.AlignLeft)
        self.arama_entry = QLineEdit()
        self.arama_entry.setPlaceholderText("Ürün Kodu veya Adı ile ara...")
        self.arama_entry.textChanged.connect(self._delayed_stok_yenile)
        top_filter_and_action_layout.addWidget(self.arama_entry, row_idx, 1)

        top_filter_and_action_layout.addWidget(QLabel("Kategori:"), row_idx, 2, Qt.AlignLeft)
        self.kategori_filter_cb = QComboBox()
        self.kategori_filter_cb.currentIndexChanged.connect(self.stok_listesini_yenile)
        top_filter_and_action_layout.addWidget(self.kategori_filter_cb, row_idx, 3)

        top_filter_and_action_layout.addWidget(QLabel("Marka:"), row_idx, 4, Qt.AlignLeft)
        self.marka_filter_cb = QComboBox()
        self.marka_filter_cb.currentIndexChanged.connect(self.stok_listesini_yenile)
        top_filter_and_action_layout.addWidget(self.marka_filter_cb, row_idx, 5)
        
        self.urun_grubu_filter_cb = QComboBox()
        
        sorgula_button = QPushButton("Sorgula")
        sorgula_button.clicked.connect(self.stok_listesini_yenile)
        top_filter_and_action_layout.addWidget(sorgula_button, row_idx, 8)

        temizle_button = QPushButton("Temizle")
        temizle_button.clicked.connect(self._filtreleri_temizle)
        top_filter_and_action_layout.addWidget(temizle_button, row_idx, 9)

        # Özet Bilgiler Çerçevesi
        summary_info_frame = QFrame(self)
        summary_info_layout = QGridLayout(summary_info_frame)
        self.main_layout.addWidget(summary_info_frame, 2, 0, 1, 1)
        summary_info_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        summary_info_layout.setColumnStretch(0,1); summary_info_layout.setColumnStretch(1,1);
        summary_info_layout.setColumnStretch(2,1); summary_info_layout.setColumnStretch(3,1)
        
        font_summary = QFont("Segoe UI", 10, QFont.Bold)
        self.lbl_toplam_listelenen_urun = QLabel("Toplam Listelenen Ürün: 0 adet")
        self.lbl_toplam_listelenen_urun.setFont(font_summary)
        summary_info_layout.addWidget(self.lbl_toplam_listelenen_urun, 0, 0, Qt.AlignLeft)
        self.lbl_stoktaki_toplam_urun = QLabel("Stoktaki Toplam Ürün Miktarı: 0.00")
        self.lbl_stoktaki_toplam_urun.setFont(font_summary)
        summary_info_layout.addWidget(self.lbl_stoktaki_toplam_urun, 0, 1, Qt.AlignLeft)
        self.lbl_toplam_maliyet = QLabel("Listelenen Ürünlerin Toplam Maliyeti: 0.00 TL")
        self.lbl_toplam_maliyet.setFont(font_summary)
        summary_info_layout.addWidget(self.lbl_toplam_maliyet, 0, 2, Qt.AlignLeft)
        self.lbl_toplam_satis_tutari = QLabel("Listelenen Ürünlerin Toplam Satış Tutarı: 0.00 TL")
        self.lbl_toplam_satis_tutari.setFont(font_summary)
        summary_info_layout.addWidget(self.lbl_toplam_satis_tutari, 0, 3, Qt.AlignLeft)

        # Butonlar Çerçevesi
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        self.main_layout.addWidget(button_frame, 3, 0, 1, 1)
        yeni_urun_ekle_button = QPushButton("Yeni Ürün Ekle")
        yeni_urun_ekle_button.clicked.connect(self.yeni_urun_ekle_penceresi)
        button_layout.addWidget(yeni_urun_ekle_button)
        secili_urun_duzenle_button = QPushButton("Seçili Ürünü Düzenle")
        secili_urun_duzenle_button.clicked.connect(self.secili_urun_duzenle)
        button_layout.addWidget(secili_urun_duzenle_button)
        secili_urun_sil_button = QPushButton("Seçili Ürünü Sil")
        secili_urun_sil_button.clicked.connect(self.secili_urun_sil)
        button_layout.addWidget(secili_urun_sil_button)
        kritik_stok_uyarisi_button = QPushButton("Kritik Stok Uyarısı")
        # kritik_stok_uyarisi_button.clicked.connect(self.app.show_critical_stock_warning)
        button_layout.addWidget(kritik_stok_uyarisi_button)
        
        # Treeview ve kaydırma çubukları
        tree_frame = QFrame(self)
        tree_layout = QVBoxLayout(tree_frame)
        self.main_layout.addWidget(tree_frame, 4, 0, 1, 1)
        tree_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols = ("ID", "Ürün Kodu", "Ürün Adı", "Miktar", "Satış Fiyatı (KDV Dahil)", "KDV %", "Min. Stok")
        self.tree = QTreeWidget(tree_frame)
        self.tree.setHeaderLabels(cols)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        tree_layout.addWidget(self.tree)
        
        # Sayfalama
        self.kayit_sayisi_per_sayfa = 25
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0
        pagination_frame = QFrame(self)
        pagination_layout = QHBoxLayout(pagination_frame)
        self.main_layout.addWidget(pagination_frame, 5, 0, 1, 1)
        onceki_sayfa_button = QPushButton("Önceki Sayfa")
        onceki_sayfa_button.clicked.connect(self.onceki_sayfa)
        pagination_layout.addWidget(onceki_sayfa_button)
        self.sayfa_bilgisi_label = QLabel("Sayfa 1 / 1")
        pagination_layout.addWidget(self.sayfa_bilgisi_label)
        sonraki_sayfa_button = QPushButton("Sonraki Sayfa")
        sonraki_sayfa_button.clicked.connect(self.sonraki_sayfa)
        pagination_layout.addWidget(sonraki_sayfa_button)

        self._yukle_filtre_comboboxlari_stok_yonetimi()
        self.stok_listesini_yenile()

    def _yukle_filtre_comboboxlari_stok_yonetimi(self):
        try:
            response_kat = requests.get("http://127.0.0.1:8000/nitelikler/kategoriler")
            response_kat.raise_for_status()
            self.kategoriler_map = {"TÜMÜ": None}
            self.kategori_filter_cb.clear()
            self.kategori_filter_cb.addItem("TÜMÜ", None)
            for kat in response_kat.json():
                self.kategoriler_map[kat['kategori_adi']] = kat['id']
                self.kategori_filter_cb.addItem(kat['kategori_adi'], kat['id'])
            
            response_mar = requests.get("http://127.0.0.1:8000/nitelikler/markalar")
            response_mar.raise_for_status()
            self.markalar_map = {"TÜMÜ": None}
            self.marka_filter_cb.clear()
            self.marka_filter_cb.addItem("TÜMÜ", None)
            for mar in response_mar.json():
                self.markalar_map[mar['marka_adi']] = mar['id']
                self.marka_filter_cb.addItem(mar['marka_adi'], mar['id'])
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Bağlantı Hatası", f"Filtre verileri API'den alınamadı:\n{e}")

    def _filtreleri_temizle(self):
        self.arama_entry.clear()
        self.kategori_filter_cb.setCurrentText("TÜMÜ")
        self.marka_filter_cb.setCurrentText("TÜMÜ")
        self.stok_listesini_yenile()
        self.arama_entry.setFocus()

    def _delayed_stok_yenile(self):
        if self.after_timer.isActive(): self.after_timer.stop()
        self.after_timer.singleShot(300, self.stok_listesini_yenile)
 
    def stok_listesini_yenile(self):
        if not hasattr(self, 'tree'): return
        self.tree.clear()
        
        # Özet bilgi etiketlerini sıfırla
        self.lbl_toplam_listelenen_urun.setText("Toplam Listelenen Ürün: 0 adet")
        self.lbl_stoktaki_toplam_urun.setText("Stoktaki Toplam Ürün Miktarı: 0.00")
        self.lbl_toplam_maliyet.setText("Listelenen Ürünlerin Toplam Maliyeti: 0.00 TL")
        self.lbl_toplam_satis_tutari.setText("Listelenen Ürünlerin Toplam Satış Tutarı: 0.00 TL")

        try:
            api_url = "http://127.0.0.1:8000/stoklar/"
            params = {
                'limit': self.kayit_sayisi_per_sayfa,
                'skip': (self.mevcut_sayfa - 1) * self.kayit_sayisi_per_sayfa,
                'arama_terimi': self.arama_entry.text(),
                'kategori_id': self.kategori_filter_cb.currentData(),
                'marka_id': self.marka_filter_cb.currentData()
            }
            # None veya boş string olan parametreleri temizle.
            # currentData() None döndürebilir, text() boş string döndürebilir.
            params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

            response = requests.get(api_url, params=params)
            response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat.
            stok_listesi = response.json() # JSON yanıtı al.

            # Toplam özet bilgilerini hesaplamak için yeni değişkenler
            toplam_urun_miktari = 0.0
            toplam_maliyet_tutari = 0.0 # Alış fiyatları üzerinden
            toplam_satis_tutari = 0.0 # Satış fiyatları üzerinden

            for urun in stok_listesi:
                # QTreeWidget öğesi oluştur
                item_qt = QTreeWidgetItem(self.tree)
                item_qt.setData(0, Qt.UserRole, urun.get('id', -1)) # ID'yi UserRole'da sakla (sıralama ve düzenleme için)
                item_qt.setText(0, str(urun.get('id', ''))) # ID
                item_qt.setText(1, urun.get('urun_kodu', '')) # Ürün Kodu
                item_qt.setText(2, urun.get('urun_adi', '')) # Ürün Adı
                item_qt.setText(3, f"{urun.get('stok_miktari', 0):.2f}".rstrip('0').rstrip('.')) # Miktar (formatlı)
                item_qt.setText(4, f"{urun.get('satis_fiyati_kdv_dahil', 0):.2f} TL") # Satış Fiyatı (KDV Dahil) (formatlı)
                item_qt.setText(5, f"%{urun.get('kdv_orani', 0):.0f}") # KDV % (formatlı)
                item_qt.setText(6, f"{urun.get('min_stok_seviyesi', 0):.2f}".rstrip('0').rstrip('.')) # Min. Stok (formatlı)

                # Stok miktarı kritik seviyenin altındaysa satırı renklendir
                if urun.get('stok_miktari', 0) < urun.get('min_stok_seviyesi', 0):
                    for i in range(self.tree.columnCount()):
                        item_qt.setBackground(i, QBrush(QColor("red")))
                        item_qt.setForeground(i, QBrush(QColor("white")))
                
                # Toplam özet bilgilerini güncelle
                toplam_urun_miktari += urun.get('stok_miktari', 0)
                # API'den alış_fiyati_kdv_dahil geliyorsa kullan, yoksa 0.0 al
                toplam_maliyet_tutari += urun.get('alis_fiyati_kdv_dahil', 0.0) * urun.get('stok_miktari', 0)
                toplam_satis_tutari += urun.get('satis_fiyati_kdv_dahil', 0.0) * urun.get('stok_miktari', 0)

            # Özet bilgi etiketlerini güncelle
            self.lbl_toplam_listelenen_urun.setText(f"Toplam Listelenen Ürün: {len(stok_listesi)} adet")
            self.lbl_stoktaki_toplam_urun.setText(f"Stoktaki Toplam Ürün Miktarı: {toplam_urun_miktari:.2f}".rstrip('0').rstrip('.'))
            self.lbl_toplam_maliyet.setText(f"Listelenen Ürünlerin Toplam Maliyeti: {self.db._format_currency(toplam_maliyet_tutari)}")
            self.lbl_toplam_satis_tutari.setText(f"Listelenen Ürünlerin Toplam Satış Tutarı: {self.db._format_currency(toplam_satis_tutari)}")

            self.app.set_status_message(f"{len(stok_listesi)} stok kaydı listelendi.")
        
        except requests.exceptions.RequestException as e:
            # Hata durumunda kullanıcıya bilgi ver ve durumu logla
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError: # response.json() başarısız olursa
                    pass
            QMessageBox.critical(self, "API Bağlantı Hatası", f"Stok listesi API'den alınamadı:\n{error_detail}")
            self.app.set_status_message(f"Hata: Stok listesi alınamadı - {error_detail}")
        except Exception as e:
            # Beklenmedik diğer hataları yakala
            QMessageBox.critical(self, "Beklenmeyen Hata", f"Stok listesi yenilenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Stok listesi yenilenirken hata - {e}")

    def yeni_urun_ekle_penceresi(self):
        try:
            dialog = StokKartiPenceresi(
                self, self.db, self.stok_listesini_yenile,
                urun_duzenle=None, app_ref=self.app
            )
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yeni ürün ekleme penceresi açılırken bir hata oluştu:\n{e}")
        
    def secili_urun_duzenle(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek için bir ürün seçin."); return

        urun_id = selected_items[0].data(0, Qt.UserRole)
        if urun_id is None or urun_id == -1:
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir ürün seçimi yaptınız."); return

        try:
            api_url = f"{API_BASE_URL}/stoklar/{urun_id}"
            response = requests.get(api_url); response.raise_for_status()
            urun_detaylari = response.json()

            dialog = StokKartiPenceresi(
                self, self.db, self.stok_listesini_yenile,
                urun_duzenle=urun_detaylari, app_ref=self.app
            )
            dialog.exec()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', error_detail)
                except ValueError: pass
            QMessageBox.critical(self, "API Bağlantı Hatası", f"Ürün detayları API'den alınamadı:\n{error_detail}")
    
    def secili_urun_sil(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir ürün seçin.")
            return

        selected_item = selected_items[0]
        # Ürün ID'si QTreeWidgetItem'ın data(0, Qt.UserRole) kısmında saklı.
        # Bu, QTreeWidget'a öğe eklenirken ayarlanmıştı.
        urun_id = selected_item.data(0, Qt.UserRole)
        urun_adi = selected_item.text(2) # Ürün Adı 2. sütunda

        if urun_id == -1: # Eğer ID placeholder ise (örn: "Ürün Bulunamadı" gibi bir metin)
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir ürün seçimi yaptınız.")
             return

        reply = QMessageBox.question(self, "Ürün Silme Onayı", 
                                     f"'{urun_adi}' adlı ürünü silmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No) # Varsayılan "Hayır" olsun
        
        if reply == QMessageBox.Yes:
            try:
                api_url = f"http://127.0.0.1:8000/stoklar/{urun_id}"
                response = requests.delete(api_url)
                response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat
                
                QMessageBox.information(self, "Başarılı", f"'{urun_adi}' ürünü başarıyla silindi.")
                self.stok_listesini_yenile() # Listeyi yenile
                self.app.set_status_message(f"'{urun_adi}' ürünü başarıyla silindi.")
            except requests.exceptions.RequestException as e:
                # API'den gelen hata detayını yakalamaya çalış
                error_detail = str(e)
                if e.response is not None:
                    try:
                        error_detail = e.response.json().get('detail', error_detail)
                    except ValueError: # response.json() başarısız olursa
                        pass
                QMessageBox.critical(self, "Hata", f"Ürün silinirken bir hata oluştu:\n{error_detail}")
                self.app.set_status_message(f"Ürün silme başarısız: {error_detail}")
        else:
            self.app.set_status_message("Ürün silme işlemi kullanıcı tarafından iptal edildi.")
    
    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.stok_listesini_yenile()

    def sonraki_sayfa(self):
        self.mevcut_sayfa += 1
        self.stok_listesini_yenile()

class KasaBankaYonetimiSayfasi(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.main_layout = QVBoxLayout(self) # Ana layout QVBoxLayout

        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)
        
        self.main_layout.addWidget(QLabel("Kasa ve Banka Hesap Yönetimi", 
                                          font=QFont("Segoe UI", 16, QFont.Bold)), alignment=Qt.AlignLeft)

        # Arama ve Filtreleme Çerçevesi
        arama_frame = QFrame(self)
        arama_layout = QHBoxLayout(arama_frame)
        self.main_layout.addWidget(arama_frame)

        arama_layout.addWidget(QLabel("Hesap Ara (Ad/No/Banka):"))
        self.arama_entry_kb = QLineEdit()
        self.arama_entry_kb.setPlaceholderText("Hesap adı, numarası veya banka adı ile ara...")
        self.arama_entry_kb.textChanged.connect(self._delayed_hesap_yenile)
        arama_layout.addWidget(self.arama_entry_kb)

        arama_layout.addWidget(QLabel("Tip:"))
        self.tip_filtre_kb = QComboBox()
        self.tip_filtre_kb.addItems(["TÜMÜ", "KASA", "BANKA"])
        self.tip_filtre_kb.setCurrentText("TÜMÜ")
        self.tip_filtre_kb.currentIndexChanged.connect(self.hesap_listesini_yenile)
        arama_layout.addWidget(self.tip_filtre_kb)

        yenile_button = QPushButton("Yenile")
        yenile_button.clicked.connect(self.hesap_listesini_yenile)
        arama_layout.addWidget(yenile_button)

        # Hesap Listesi (QTreeWidget)
        tree_frame_kb = QFrame(self)
        tree_layout_kb = QVBoxLayout(tree_frame_kb)
        # Hata burada: QVBoxLayout'a (self.main_layout) addWidget ile satır/sütun verilmez.
        self.main_layout.addWidget(tree_frame_kb) # <-- Burası güncellendi. Satır ve sütun indeksleri kaldırıldı.
        tree_frame_kb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols_kb = ("#", "Hesap Adı", "Tip", "Banka Adı", "Hesap No", "Bakiye", "Para Birimi")
        self.tree_kb = QTreeWidget(tree_frame_kb)
        self.tree_kb.setHeaderLabels(cols_kb)
        self.tree_kb.setColumnCount(len(cols_kb))
        self.tree_kb.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_kb.setSortingEnabled(True)
        
        # Sütun ayarları
        col_definitions_kb = [
            ("#", 40, Qt.AlignRight),
            ("Hesap Adı", 200, Qt.AlignLeft),
            ("Tip", 80, Qt.AlignCenter),
            ("Banka Adı", 150, Qt.AlignLeft),
            ("Hesap No", 150, Qt.AlignLeft),
            ("Bakiye", 120, Qt.AlignRight),
            ("Para Birimi", 80, Qt.AlignCenter)
        ]
        for i, (col_name, width, alignment) in enumerate(col_definitions_kb):
            self.tree_kb.setColumnWidth(i, width)
            self.tree_kb.headerItem().setTextAlignment(i, alignment)
            self.tree_kb.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))

        self.tree_kb.header().setStretchLastSection(False)
        self.tree_kb.header().setSectionResizeMode(1, QHeaderView.Stretch) # Hesap Adı genişlesin
        self.tree_kb.header().setSectionResizeMode(3, QHeaderView.Stretch) # Banka Adı genişlesin
        self.tree_kb.header().setSectionResizeMode(4, QHeaderView.Stretch) # Hesap No genişlesin
        
        tree_layout_kb.addWidget(self.tree_kb)
        
        self.tree_kb.itemDoubleClicked.connect(self.hesap_duzenle_event)

        # Butonlar Çerçevesi
        button_frame_kb = QFrame(self)
        button_layout_kb = QHBoxLayout(button_frame_kb)
        self.main_layout.addWidget(button_frame_kb)

        yeni_hesap_ekle_button = QPushButton("Yeni Hesap Ekle")
        yeni_hesap_ekle_button.clicked.connect(self.yeni_hesap_ekle_penceresi)
        button_layout_kb.addWidget(yeni_hesap_ekle_button)

        secili_hesap_duzenle_button = QPushButton("Seçili Hesabı Düzenle")
        secili_hesap_duzenle_button.clicked.connect(self.secili_hesap_duzenle)
        button_layout_kb.addWidget(secili_hesap_duzenle_button)

        secili_hesap_sil_button = QPushButton("Seçili Hesabı Sil")
        secili_hesap_sil_button.clicked.connect(self.secili_hesap_sil)
        button_layout_kb.addWidget(secili_hesap_sil_button)
        
        self.hesap_listesini_yenile() # İlk yüklemeyi yap

    def hesap_listesini_yenile(self):
        self.tree_kb.clear()
        arama_terimi = self.arama_entry_kb.text()
        tip_filtre = self.tip_filtre_kb.currentText()

        try:
            api_url = f"{API_BASE_URL}/kasalar_bankalar/"
            
            params = {}
            if arama_terimi:
                params['arama_terimi'] = arama_terimi
            if tip_filtre and tip_filtre != "TÜMÜ":
                params['tip_filtre'] = tip_filtre

            response = requests.get(api_url, params=params)
            response.raise_for_status()
            hesap_listesi = response.json()
            
            for h in hesap_listesi:
                item_qt = QTreeWidgetItem(self.tree_kb)
                item_qt.setData(0, Qt.UserRole, h.get('id')) # ID'yi sakla
                item_qt.setText(0, str(h.get('id', '')))
                item_qt.setText(1, h.get('hesap_adi', ''))
                item_qt.setText(2, h.get('tip', ''))
                item_qt.setText(3, h.get('banka_adi') or "-")
                item_qt.setText(4, h.get('hesap_no') or "-")
                item_qt.setText(5, self.db._format_currency(h.get('bakiye', 0.0)))
                item_qt.setText(6, h.get('para_birimi', ''))
                
                item_qt.setData(5, Qt.UserRole, h.get('bakiye', 0.0))

            self.app.set_status_message(f"{len(hesap_listesi)} kasa/banka hesabı API'den listelendi.")

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self, "API Bağlantı Hatası", f"Hesap listesi API'den alınamadı:\n{error_detail}")
        except Exception as e:
            QMessageBox.critical(self, "Beklenmeyen Hata", f"Hesap listesi yüklenirken bir hata oluştu:\n{e}")

    def _delayed_hesap_yenile(self): # event=None kaldırıldı
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self.hesap_listesini_yenile)

    def yeni_hesap_ekle_penceresi(self):
        try:
            dialog = YeniKasaBankaEklePenceresi(
                self,
                self.db,
                self.hesap_listesini_yenile,
                hesap_duzenle=None,
                app_ref=self.app
            )
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yeni hesap ekleme penceresi açılırken bir hata oluştu:\n{e}")

    def hesap_duzenle_event(self, item, column): # item itemDoubleClicked sinyalinden gelir
        selected_item_id = item.text(0) # İlk sütun olan ID'yi al
        self.secili_hesap_duzenle(hesap_id=selected_item_id)

    def secili_hesap_duzenle(self, hesap_id=None):
        if hesap_id is None:
            selected_items = self.tree_kb.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek için bir hesap seçin.")
                return
            hesap_id = int(selected_items[0].text(0))

        try:
            api_url = f"{API_BASE_URL}/kasalar_bankalar/{hesap_id}"
            response = requests.get(api_url)
            response.raise_for_status()
            hesap_detaylari = response.json()

            dialog = YeniKasaBankaEklePenceresi(
                self,
                self.db,
                self.hesap_listesini_yenile,
                hesap_duzenle=hesap_detaylari,
                app_ref=self.app
            )
            dialog.exec()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', error_detail)
                except ValueError: pass
            QMessageBox.critical(self, "API Bağlantı Hatası", f"Hesap detayları API'den alınamadı:\n{error_detail}")

    def secili_hesap_sil(self):
        selected_items = self.tree_kb.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir hesap seçin.")
            return

        selected_item = selected_items[0]
        hesap_id = selected_item.data(0, Qt.UserRole) # ID'yi al
        hesap_adi = selected_item.text(1) # Hesap Adı

        if hesap_id == -1: # Eğer ID placeholder ise
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir hesap seçimi yaptınız.")
             return
        
        reply = QMessageBox.question(self, "Hesap Silme Onayı", 
                                     f"'{hesap_adi}' adlı hesabı silmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No) # Varsayılan "Hayır" olsun
        
        if reply == QMessageBox.Yes:
            try:
                # API'ye DELETE isteği gönder
                api_url = f"http://127.0.0.1:8000/kasalar_bankalar/{hesap_id}"
                response = requests.delete(api_url)
                response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat
                
                QMessageBox.information(self, "Başarılı", f"'{hesap_adi}' hesabı başarıyla silindi.")
                self.hesap_listesini_yenile() # Listeyi yenile
                self.app.set_status_message(f"'{hesap_adi}' hesabı başarıyla silindi.")

                # İlgili diğer sayfaları da güncelle (Finansal İşlemler, Raporlar vb. eğer bu hesabı kullanıyorlarsa)
                if hasattr(self.app, 'finansal_islemler_sayfasi') and hasattr(self.app.finansal_islemler_sayfasi.tahsilat_frame, '_yukle_kasa_banka_hesaplarini'):
                    self.app.finansal_islemler_sayfasi.tahsilat_frame._yukle_kasa_banka_hesaplarini()
                if hasattr(self.app, 'finansal_islemler_sayfasi') and hasattr(self.app.finansal_islemler_sayfasi.odeme_frame, '_yukle_kasa_banka_hesaplarini'):
                    self.app.finansal_islemler_sayfasi.odeme_frame._yukle_kasa_banka_hesaplarini()

            except requests.exceptions.RequestException as e:
                # API'den gelen hata detayını yakalamaya çalış
                error_detail = str(e)
                if e.response is not None:
                    try:
                        error_detail = e.response.json().get('detail', error_detail)
                    except ValueError: # response.json() başarısız olursa
                        pass
                QMessageBox.critical(self, "Hata", f"Hesap silinirken bir hata oluştu:\n{error_detail}")
                self.app.set_status_message(f"Hesap silme başarısız: {error_detail}")
        else:
            self.app.set_status_message("Hesap silme işlemi kullanıcı tarafından iptal edildi.")

class MusteriYonetimiSayfasi(QWidget):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.main_layout = QVBoxLayout(self)

        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)
        
        self.main_layout.addWidget(QLabel("Müşteri Yönetimi", font=QFont("Segoe UI", 16, QFont.Bold)), 
                                   alignment=Qt.AlignLeft)

        # Toplam Özet Bilgiler Kısmı
        summary_frame = QFrame(self)
        summary_layout = QGridLayout(summary_frame)
        self.main_layout.addWidget(summary_frame)
        summary_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        summary_layout.setColumnStretch(0, 1)
        summary_layout.setColumnStretch(1, 1)

        self.lbl_toplam_alacak_musteri = QLabel("Toplam Alacak (Müşteri): Yükleniyor...")
        self.lbl_toplam_alacak_musteri.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_toplam_alacak_musteri.setStyleSheet("color: red;")
        summary_layout.addWidget(self.lbl_toplam_alacak_musteri, 0, 0, Qt.AlignLeft)
        
        self.lbl_toplam_borc_musteri = QLabel("Toplam Borç (Müşteri): Yükleniyor...")
        self.lbl_toplam_borc_musteri.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_toplam_borc_musteri.setStyleSheet("color: green;")
        summary_layout.addWidget(self.lbl_toplam_borc_musteri, 0, 1, Qt.AlignLeft)

        # Arama ve Filtreleme Çerçevesi
        arama_frame = QFrame(self)
        arama_layout = QHBoxLayout(arama_frame)
        self.main_layout.addWidget(arama_frame)
        arama_layout.addWidget(QLabel("Müşteri Ara (Ad/Kod/Tel/Adres):"))
        self.arama_entry = QLineEdit()
        self.arama_entry.setPlaceholderText("Müşteri ara...")
        self.arama_entry.textChanged.connect(self._delayed_musteri_yenile)
        self.arama_entry.returnPressed.connect(self._on_arama_entry_return)
        arama_layout.addWidget(self.arama_entry)
        ara_yenile_button = QPushButton("Ara/Yenile")
        ara_yenile_button.clicked.connect(self.musteri_listesini_yenile)
        arama_layout.addWidget(ara_yenile_button)

        # Müşteri Listesi (QTreeWidget)
        tree_frame = QFrame(self)
        tree_layout = QVBoxLayout(tree_frame)
        self.main_layout.addWidget(tree_frame) # QVBoxLayout olduğu için satır/sütun belirtmiyoruz
        tree_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        cols = ("ID", "Müşteri Kodu", "Müşteri Adı", "Telefon", "Adres")
        self.tree = QTreeWidget(tree_frame)
        self.tree.setHeaderLabels(cols)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setSortingEnabled(True)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        tree_layout.addWidget(self.tree)
        self.tree.itemDoubleClicked.connect(self.secili_musteri_ekstresi_goster)
        self.tree.itemSelectionChanged.connect(self.secili_musteri_ekstre_buton_guncelle)

        # Butonlar Çerçevesi (Alt kısım)
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        self.main_layout.addWidget(button_frame)
        yeni_musteri_ekle_button = QPushButton("Yeni Müşteri Ekle")
        yeni_musteri_ekle_button.clicked.connect(self.yeni_musteri_ekle_penceresi)
        button_layout.addWidget(yeni_musteri_ekle_button)
        secili_musteri_duzenle_button = QPushButton("Seçili Müşteriyi Düzenle")
        secili_musteri_duzenle_button.clicked.connect(self.secili_musteri_duzenle)
        button_layout.addWidget(secili_musteri_duzenle_button)
        secili_musteri_sil_button = QPushButton("Seçili Müşteriyi Sil")
        secili_musteri_sil_button.clicked.connect(self.secili_musteri_sil)
        button_layout.addWidget(secili_musteri_sil_button)
        self.ekstre_button = QPushButton("Seçili Müşteri Ekstresi")
        self.ekstre_button.clicked.connect(self.secili_musteri_ekstresi_goster)
        self.ekstre_button.setEnabled(False)
        button_layout.addWidget(self.ekstre_button)

        # Sayfalama Çerçevesi
        self.kayit_sayisi_per_sayfa = 25
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0
        pagination_frame = QFrame(self)
        pagination_layout = QHBoxLayout(pagination_frame)
        self.main_layout.addWidget(pagination_frame)
        onceki_sayfa_button = QPushButton("Önceki Sayfa")
        onceki_sayfa_button.clicked.connect(self.onceki_sayfa)
        pagination_layout.addWidget(onceki_sayfa_button)
        self.sayfa_bilgisi_label = QLabel("Sayfa 1 / 1")
        pagination_layout.addWidget(self.sayfa_bilgisi_label)
        sonraki_sayfa_button = QPushButton("Sonraki Sayfa")
        sonraki_sayfa_button.clicked.connect(self.sonraki_sayfa)
        pagination_layout.addWidget(sonraki_sayfa_button)
        
        self.musteri_listesini_yenile()
        self.arama_entry.setFocus()

    def secili_musteri_ekstre_buton_guncelle(self):
        selected_items = self.tree.selectedItems()
        self.ekstre_button.setEnabled(bool(selected_items))

    def musteri_listesini_yenile(self):
        self.tree.clear()
        try:
            api_url = "http://127.0.0.1:8000/musteriler/"
            params = {'skip': (self.mevcut_sayfa - 1) * self.kayit_sayisi_per_sayfa, 'limit': self.kayit_sayisi_per_sayfa}
            response = requests.get(api_url, params=params)
            response.raise_for_status()
            musteri_listesi = response.json()
            
            for musteri in musteri_listesi:
                item_qt = QTreeWidgetItem(self.tree)
                item_qt.setData(0, Qt.UserRole, musteri.get('id', -1))
                item_qt.setText(0, str(musteri.get('id', '')))
                item_qt.setText(1, musteri.get('kod', ''))
                item_qt.setText(2, musteri.get('ad', ''))
                item_qt.setText(3, musteri.get('telefon', ''))
                item_qt.setText(4, musteri.get('adres', ''))

            self.app.set_status_message(f"{len(musteri_listesi)} müşteri API'den listelendi.")
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Bağlantı Hatası", f"API sunucusuna bağlanılamadı:\n{e}")

    def secili_musteri_sil(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir müşteri seçin.")
            return

        selected_item = selected_items[0]
        musteri_id = selected_item.data(0, Qt.UserRole)
        musteri_adi = selected_item.text(2)

        reply = QMessageBox.question(self, "Onay", f"'{musteri_adi}' adlı müşteriyi silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                api_url = f"http://127.0.0.1:8000/musteriler/{musteri_id}"
                response = requests.delete(api_url)
                response.raise_for_status()
                
                QMessageBox.information(self, "Başarılı", f"'{musteri_adi}' müşterisi başarıyla silindi.")
                self.musteri_listesini_yenile()
            except requests.exceptions.RequestException as e:
                hata_detayi = str(e)
                try: hata_detayi = e.response.json().get('detail', str(e))
                except: pass
                QMessageBox.critical(self, "Hata", f"Müşteri silinirken hata:\n{hata_detayi}")

    def _on_arama_entry_return(self):
        self.musteri_listesini_yenile()
    
    def _delayed_musteri_yenile(self):
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self.musteri_listesini_yenile)

    def guncelle_toplam_ozet_bilgiler(self):
        self.lbl_toplam_alacak_musteri.setText("Toplam Alacak: -")
        self.lbl_toplam_borc_musteri.setText("Toplam Borç: -")

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.musteri_listesini_yenile()

    def sonraki_sayfa(self):
        # TODO: API'den toplam kayıt sayısı alınarak bu kontrol daha doğru yapılmalı
        self.mevcut_sayfa += 1
        self.musteri_listesini_yenile()

    def yeni_musteri_ekle_penceresi(self):
        """Yeni PySide6 tabanlı müşteri ekleme penceresini açar."""
        try:
            # Yeni QDialog penceremizi oluşturuyoruz
            dialog = YeniMusteriEklePenceresi(
                self,  # Parent olarak mevcut widget'ı (MusteriYonetimiSayfasi) veriyoruz
                self.db,
                self.musteri_listesini_yenile,  # Başarılı kayıttan sonra listeyi yenileyecek fonksiyon
                musteri_duzenle=None,  # Yeni kayıt olduğu için bu parametre None
                app_ref=self.app
            )
            # exec() metodu, pencere kapanana kadar kodun beklemesini sağlar.
            # Pencere "Kaydet" ile kapatılırsa (accept), liste yenilenir.
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yeni müşteri ekleme penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Yeni müşteri ekleme penceresi açılamadı - {e}")

    def secili_musteri_duzenle(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek için bir müşteri seçin.")
            return

        selected_item = selected_items[0]
        musteri_id = selected_item.data(0, Qt.UserRole)

        if musteri_id == -1:
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir müşteri seçimi yaptınız.")
             return

        try:
            # API'den seçili ürünün en güncel detaylarını çekiyoruz
            api_url = f"http://127.0.0.1:8000/musteriler/{musteri_id}"
            response = requests.get(api_url)
            response.raise_for_status()
            musteri_detaylari = response.json()

            dialog = YeniMusteriEklePenceresi(
                self,
                self.db,
                self.musteri_listesini_yenile,
                musteri_duzenle=musteri_detaylari,  # API'den gelen veriyi pencereye gönderiyoruz
                app_ref=self.app
            )
            dialog.exec()

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', error_detail)
                except ValueError: pass
            QMessageBox.critical(self, "API Bağlantı Hatası", f"Müşteri detayları API'den alınamadı:\n{error_detail}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Müşteri düzenleme penceresi açılırken bir hata oluştu:\n{e}")

    def secili_musteri_ekstresi_goster(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen ekstresini görmek için bir müşteri seçin.")
            return

        selected_item = selected_items[0]
        # Müşteri ID'si QTreeWidgetItem'ın data(0, Qt.UserRole) kısmında saklı.
        musteri_id = selected_item.data(0, Qt.UserRole)
        musteri_adi = selected_item.text(2) # Müşteri Adı

        if musteri_id == -1: # Eğer ID placeholder ise
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir müşteri seçimi yaptınız.")
             return
        
        # NOT: pencereler.py dosyasındaki CariHesapEkstresiPenceresi'nin PySide6'ya dönüştürülmüş olması gerekmektedir.
        # Bu fonksiyon, CariHesapEkstresiPenceresi'nin PySide6 versiyonu hazır olduğunda aktif olarak çalışacaktır.

        # Geçici olarak, pencereler modülünü bu fonksiyon içinde import edelim
        try:
            from pencereler import CariHesapEkstresiPenceresi # PySide6 CariHesapEkstresiPenceresi varsayılıyor
            
            # Cari Hesap Ekstresi penceresini başlat
            cari_ekstre_penceresi = CariHesapEkstresiPenceresi(
                self.app, # Ana uygulama penceresi (parent)
                self.db, # Veritabanı yöneticisi
                musteri_id, # Müşteri ID'si
                self.db.CARI_TIP_MUSTERI, # Cari tipi
                musteri_adi, # Pencere başlığı için cari adı
                parent_list_refresh_func=self.musteri_listesini_yenile # Ekstre kapatıldığında ana listeyi yenile
            )
            # Pencereyi göster
            cari_ekstre_penceresi.show()
            self.app.set_status_message(f"'{musteri_adi}' için cari hesap ekstresi açıldı.")

        except ImportError:
            QMessageBox.critical(self, "Hata", "CariHesapEkstresiPenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
            self.app.set_status_message("Hata: Cari Hesap Ekstresi penceresi açılamadı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Cari Hesap Ekstresi penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Cari Hesap Ekstresi penceresi açılamadı - {e}")

# TedarikciYonetimiSayfasi sınıfı (Dönüştürülmüş PySide6 versiyonu)
class TedarikciYonetimiSayfasi(QWidget):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager # Diğer pencereler için şimdilik kalabilir
        self.app = app_ref
        self.main_layout = QVBoxLayout(self)

        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)
        
        self.main_layout.addWidget(QLabel("Tedarikçi Yönetimi", font=QFont("Segoe UI", 16, QFont.Bold)), 
                                   alignment=Qt.AlignLeft)

        # Toplam Özet Bilgiler Kısmı
        summary_frame = QFrame(self)
        summary_layout = QGridLayout(summary_frame)
        self.main_layout.addWidget(summary_frame)
        summary_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        summary_layout.setColumnStretch(0, 1)
        summary_layout.setColumnStretch(1, 1)

        self.lbl_toplam_borc_tedarikci = QLabel("Toplam Borç (Tedarikçi): API'den Yüklenecek...")
        self.lbl_toplam_borc_tedarikci.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_toplam_borc_tedarikci.setStyleSheet("color: red;")
        summary_layout.addWidget(self.lbl_toplam_borc_tedarikci, 0, 0, Qt.AlignLeft)
        
        self.lbl_toplam_alacak_tedarikci = QLabel("Toplam Alacak (Tedarikçi): API'den Yüklenecek...")
        self.lbl_toplam_alacak_tedarikci.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_toplam_alacak_tedarikci.setStyleSheet("color: green;")
        summary_layout.addWidget(self.lbl_toplam_alacak_tedarikci, 0, 1, Qt.AlignLeft)

        # Arama ve Filtreleme Çerçevesi
        arama_frame = QFrame(self)
        arama_layout = QHBoxLayout(arama_frame)
        self.main_layout.addWidget(arama_frame)

        arama_layout.addWidget(QLabel("Tedarikçi Ara (Kod/Ad/Tel/Adres):"))
        self.arama_entry = QLineEdit()
        self.arama_entry.setPlaceholderText("Tedarikçi ara...")
        self.arama_entry.textChanged.connect(self._delayed_tedarikci_yenile)
        self.arama_entry.returnPressed.connect(self._on_arama_entry_return)
        arama_layout.addWidget(self.arama_entry)

        ara_yenile_button = QPushButton("Ara/Yenile")
        ara_yenile_button.clicked.connect(self.tedarikci_listesini_yenile)
        arama_layout.addWidget(ara_yenile_button)

        # Tedarikçi Listesi (QTreeWidget)
        tree_frame = QFrame(self)
        tree_layout = QVBoxLayout(tree_frame)
        self.main_layout.addWidget(tree_frame) # Grid layout yerine doğrudan ekleme
        tree_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Sütunları basitleştiriyoruz, API'den sadece bu veriler geliyor
        cols = ("ID", "Tedarikçi Kodu", "Tedarikçi Adı", "Telefon", "Adres")
        self.tree = QTreeWidget(tree_frame)
        self.tree.setHeaderLabels(cols)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setSortingEnabled(True)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch) # Adı genişlesin
        tree_layout.addWidget(self.tree)
        self.tree.itemDoubleClicked.connect(self.secili_tedarikci_ekstresi_goster)
        self.tree.itemSelectionChanged.connect(self.secili_tedarikci_ekstre_buton_guncelle)

        # Butonlar Çerçevesi (Alt kısım)
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        self.main_layout.addWidget(button_frame)
        yeni_tedarikci_ekle_button = QPushButton("Yeni Tedarikçi Ekle")
        yeni_tedarikci_ekle_button.clicked.connect(self.yeni_tedarikci_ekle_penceresi)
        button_layout.addWidget(yeni_tedarikci_ekle_button)
        secili_tedarikci_duzenle_button = QPushButton("Seçili Tedarikçiyi Düzenle")
        secili_tedarikci_duzenle_button.clicked.connect(self.secili_tedarikci_duzenle)
        button_layout.addWidget(secili_tedarikci_duzenle_button)
        secili_tedarikci_sil_button = QPushButton("Seçili Tedarikçiyi Sil")
        secili_tedarikci_sil_button.clicked.connect(self.secili_tedarikci_sil)
        button_layout.addWidget(secili_tedarikci_sil_button)
        self.ekstre_button_ted = QPushButton("Seçili Tedarikçi Ekstresi")
        self.ekstre_button_ted.clicked.connect(self.secili_tedarikci_ekstresi_goster)
        self.ekstre_button_ted.setEnabled(False)
        button_layout.addWidget(self.ekstre_button_ted)

        # Sayfalama Çerçevesi (Şimdilik devre dışı, ileride API'ye ekleyeceğiz)
        self.kayit_sayisi_per_sayfa = 25
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0
        pagination_frame = QFrame(self)
        pagination_layout = QHBoxLayout(pagination_frame)
        self.main_layout.addWidget(pagination_frame)
        onceki_sayfa_button = QPushButton("Önceki Sayfa")
        onceki_sayfa_button.clicked.connect(self.onceki_sayfa)
        pagination_layout.addWidget(onceki_sayfa_button)
        self.sayfa_bilgisi_label = QLabel("Sayfa 1 / 1")
        self.sayfa_bilgisi_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        pagination_layout.addWidget(self.sayfa_bilgisi_label)
        sonraki_sayfa_button = QPushButton("Sonraki Sayfa")
        sonraki_sayfa_button.clicked.connect(self.sonraki_sayfa)
        pagination_layout.addWidget(sonraki_sayfa_button)
        
        self.tedarikci_listesini_yenile()
        self.arama_entry.setFocus()

    def secili_tedarikci_ekstre_buton_guncelle(self):
        selected_items = self.tree.selectedItems()
        self.ekstre_button_ted.setEnabled(bool(selected_items))

    def tedarikci_listesini_yenile(self):
        self.tree.clear()
        try:
            # API'den veri çekme
            api_url = "http://127.0.0.1:8000/tedarikciler/"
            params = {'skip': (self.mevcut_sayfa - 1) * self.kayit_sayisi_per_sayfa, 'limit': self.kayit_sayisi_per_sayfa}
            response = requests.get(api_url, params=params)
            response.raise_for_status()
            tedarikci_listesi = response.json()
            
            # Treeview'i doldurma
            for tedarikci in tedarikci_listesi:
                item_qt = QTreeWidgetItem(self.tree)
                item_qt.setData(0, Qt.UserRole, tedarikci.get('id', -1)) # ID'yi sakla
                item_qt.setText(0, str(tedarikci.get('id', '')))
                item_qt.setText(1, tedarikci.get('tedarikci_kodu', ''))
                item_qt.setText(2, tedarikci.get('ad', ''))
                item_qt.setText(3, tedarikci.get('telefon', ''))
                item_qt.setText(4, tedarikci.get('adres', ''))

            self.app.set_status_message(f"{len(tedarikci_listesi)} tedarikçi API'den listelendi.")
            # self.guncelle_toplam_ozet_bilgiler() # Bu metot da API'den veri çekmeli
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Bağlantı Hatası", f"API sunucusuna bağlanılamadı:\n{e}")
            self.app.set_status_message("Hata: API sunucusuna bağlanılamadı.")

    def secili_tedarikci_sil(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir tedarikçi seçin.")
            return

        selected_item = selected_items[0]
        tedarikci_id = selected_item.data(0, Qt.UserRole)
        tedarikci_adi = selected_item.text(2)

        reply = QMessageBox.question(self, "Onay", f"'{tedarikci_adi}' adlı tedarikçiyi silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                api_url = f"http://127.0.0.1:8000/tedarikciler/{tedarikci_id}"
                response = requests.delete(api_url)
                response.raise_for_status()
                
                QMessageBox.information(self, "Başarılı", f"'{tedarikci_adi}' tedarikçisi başarıyla silindi.")
                self.tedarikci_listesini_yenile()
                self.app.set_status_message(f"'{tedarikci_adi}' tedarikçisi silindi.")
            except requests.exceptions.RequestException as e:
                hata_detayi = str(e)
                try:
                    hata_detayi = e.response.json().get('detail', str(e))
                except:
                    pass
                QMessageBox.critical(self, "Hata", f"Tedarikçi silinirken bir hata oluştu:\n{hata_detayi}")
                self.app.set_status_message(f"Tedarikçi silme başarısız: {hata_detayi}")

    def guncelle_toplam_ozet_bilgiler(self):
        # TODO: Bu metot, tedarikçilerin toplam bakiye bilgisini API'den çekecek şekilde güncellenmelidir.
        self.lbl_toplam_borc_tedarikci.setText("Toplam Borç (Tedarikçi): -")
        self.lbl_toplam_alacak_tedarikci.setText("Toplam Alacak (Tedarikçi): -")

    def _on_arama_entry_return(self):
        self.tedarikci_listesini_yenile()
    
    def _delayed_tedarikci_yenile(self):
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self.tedarikci_listesini_yenile)

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.tedarikci_listesini_yenile()

    def sonraki_sayfa(self):
        # TODO: API'den toplam kayıt sayısını alıp sayfa kontrolü yapmak gerekir.
        self.mevcut_sayfa += 1
        self.tedarikci_listesini_yenile()

    def yeni_tedarikci_ekle_penceresi(self):
        try:
            dialog = YeniTedarikciEklePenceresi(
                self,
                self.db,
                self.tedarikci_listesini_yenile,
                tedarikci_duzenle=None,
                app_ref=self.app
            )
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yeni tedarikçi ekleme penceresi açılırken bir hata oluştu:\n{e}")

    def secili_tedarikci_duzenle(self, tedarikci_id=None):
        if tedarikci_id is None:
            selected_items = self.tree.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek için bir tedarikçi seçin.")
                return
            tedarikci_id = selected_items[0].data(0, Qt.UserRole)

        if tedarikci_id == -1:
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir tedarikçi seçimi yaptınız.")
             return

        try:
            api_url = f"{API_BASE_URL}/tedarikciler/{tedarikci_id}"
            response = requests.get(api_url)
            response.raise_for_status()
            tedarikci_detaylari = response.json()

            dialog = YeniTedarikciEklePenceresi(
                self,
                self.db,
                self.tedarikci_listesini_yenile,
                tedarikci_duzenle=tedarikci_detaylari,
                app_ref=self.app
            )
            dialog.exec()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', error_detail)
                except ValueError: pass
            QMessageBox.critical(self, "API Bağlantı Hatası", f"Tedarikçi detayları API'den alınamadı:\n{error_detail}")
    
    def secili_tedarikci_ekstresi_goster(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen ekstresini görmek için bir tedarikçi seçin.")
            return

        selected_item = selected_items[0]
        # Tedarikçi ID'si QTreeWidgetItem'ın data(0, Qt.UserRole) kısmında saklı.
        tedarikci_id = selected_item.data(0, Qt.UserRole)
        tedarikci_adi = selected_item.text(2) # Tedarikçi Adı

        if tedarikci_id == -1: # Eğer ID placeholder ise
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir tedarikçi seçimi yaptınız.")
             return
        
        # NOT: pencereler.py dosyasındaki CariHesapEkstresiPenceresi'nin PySide6'ya dönüştürülmüş olması gerekmektedir.
        # Bu fonksiyon, CariHesapEkstresiPenceresi'nin PySide6 versiyonu hazır olduğunda aktif olarak çalışacaktır.

        # Geçici olarak, pencereler modülünü bu fonksiyon içinde import edelim
        try:
            from pencereler import CariHesapEkstresiPenceresi # PySide6 CariHesapEkstresiPenceresi varsayılıyor
            
            # Cari Hesap Ekstresi penceresini başlat
            cari_ekstre_penceresi = CariHesapEkstresiPenceresi(
                self.app, # Ana uygulama penceresi (parent)
                self.db, # Veritabanı yöneticisi
                tedarikci_id, # Tedarikçi ID'si
                self.db.CARI_TIP_TEDARIKCI, # Cari tipi
                tedarikci_adi, # Pencere başlığı için tedarikçi adı
                parent_list_refresh_func=self.tedarikci_listesini_yenile # Ekstre kapatıldığında ana listeyi yenile
            )
            # Pencereyi göster
            cari_ekstre_penceresi.show()
            self.app.set_status_message(f"'{tedarikci_adi}' için cari hesap ekstresi açıldı.")

        except ImportError:
            QMessageBox.critical(self, "Hata", "CariHesapEkstresiPenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
            self.app.set_status_message("Hata: Cari Hesap Ekstresi penceresi açılamadı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Cari Hesap Ekstresi penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Cari Hesap Ekstresi penceresi açılamadı - {e}")

# FaturaListesiSayfasi sınıfı (Dönüştürülmüş PySide6 versiyonu)
class FaturaListesiSayfasi(QWidget):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.main_layout = QVBoxLayout(self)

        self.main_layout.addWidget(QLabel("Faturalar", font=QFont("Segoe UI", 16, QFont.Bold)), 
                                   alignment=Qt.AlignLeft)

        self.main_tab_widget = QTabWidget(self)
        self.main_layout.addWidget(self.main_tab_widget)

        self.satis_fatura_frame = SatisFaturalariListesi(self.main_tab_widget, self.db, self.app, fatura_tipi='SATIŞ')
        self.main_tab_widget.addTab(self.satis_fatura_frame, "🛍️ Satış Faturaları")

        self.alis_fatura_frame = AlisFaturalariListesi(self.main_tab_widget, self.db, self.app, fatura_tipi='ALIŞ')
        self.main_tab_widget.addTab(self.alis_fatura_frame, "🛒 Alış Faturaları")
        
        self.main_tab_widget.currentChanged.connect(self._on_tab_change)

    def _on_tab_change(self, index):
        selected_widget = self.main_tab_widget.widget(index)
        if hasattr(selected_widget, 'fatura_listesini_yukle'):
            selected_widget.fatura_listesini_yukle()

# SiparisListesiSayfasi sınıfı (Dönüştürülmüş PySide6 versiyonu)
class SiparisListesiSayfasi(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.main_layout = QVBoxLayout(self) # Ana layout QVBoxLayout

        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)

        self.main_layout.addWidget(QLabel("Sipariş Yönetimi", font=QFont("Segoe UI", 16, QFont.Bold)), 
                                   alignment=Qt.AlignLeft)

        # Filtreleme ve Arama Çerçevesi
        filter_top_frame = QFrame(self)
        filter_top_layout = QHBoxLayout(filter_top_frame)
        self.main_layout.addWidget(filter_top_frame)

        filter_top_layout.addWidget(QLabel("Başlangıç Tarihi:"))
        self.bas_tarih_entry = QLineEdit()
        self.bas_tarih_entry.setText((datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        filter_top_layout.addWidget(self.bas_tarih_entry)
        
        takvim_button_bas = QPushButton("🗓️")
        takvim_button_bas.setFixedWidth(30)
        takvim_button_bas.clicked.connect(lambda: DatePickerDialog(self.app, self.bas_tarih_entry))
        filter_top_layout.addWidget(takvim_button_bas)

        filter_top_layout.addWidget(QLabel("Bitiş Tarihi:"))
        self.bit_tarih_entry = QLineEdit()
        self.bit_tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        filter_top_layout.addWidget(self.bit_tarih_entry)
        
        takvim_button_bit = QPushButton("🗓️")
        takvim_button_bit.setFixedWidth(30)
        takvim_button_bit.clicked.connect(lambda: DatePickerDialog(self.app, self.bit_tarih_entry))
        filter_top_layout.addWidget(takvim_button_bit)

        filter_top_layout.addWidget(QLabel("Ara (Sipariş No/Cari/Ürün):"))
        self.arama_siparis_entry = QLineEdit()
        self.arama_siparis_entry.setPlaceholderText("Sipariş No, Cari Adı veya Ürün ara...")
        self.arama_siparis_entry.textChanged.connect(self._delayed_siparis_listesi_yukle)
        filter_top_layout.addWidget(self.arama_siparis_entry)

        temizle_button = QPushButton("Temizle")
        temizle_button.clicked.connect(self._arama_temizle)
        filter_top_layout.addWidget(temizle_button)

        filtre_yenile_button = QPushButton("Filtrele/Yenile")
        filtre_yenile_button.clicked.connect(self.siparis_listesini_yukle)
        filter_top_layout.addWidget(filtre_yenile_button)

        # Filtreleme Alanları (Cari, Durum, Sipariş Tipi)
        filter_bottom_frame = QFrame(self)
        filter_bottom_layout = QHBoxLayout(filter_bottom_frame)
        self.main_layout.addWidget(filter_bottom_frame)

        filter_bottom_layout.addWidget(QLabel("Cari Filtre:"))
        self.cari_filter_cb = QComboBox()
        self.cari_filter_cb.currentIndexChanged.connect(self.siparis_listesini_yukle)
        filter_bottom_layout.addWidget(self.cari_filter_cb)

        filter_bottom_layout.addWidget(QLabel("Durum:"))
        self.durum_filter_cb = QComboBox()
        self.durum_filter_cb.addItems(["TÜMÜ", self.db.SIPARIS_DURUM_BEKLEMEDE, 
                                       self.db.SIPARIS_DURUM_TAMAMLANDI, 
                                       self.db.SIPARIS_DURUM_KISMİ_TESLIMAT, 
                                       self.db.SIPARIS_DURUM_IPTAL_EDILDI])
        self.durum_filter_cb.setCurrentText("TÜMÜ")
        self.durum_filter_cb.currentIndexChanged.connect(self.siparis_listesini_yukle)
        filter_bottom_layout.addWidget(self.durum_filter_cb)

        filter_bottom_layout.addWidget(QLabel("Sipariş Tipi:"))
        self.siparis_tipi_filter_cb = QComboBox()
        self.siparis_tipi_filter_cb.addItems(["TÜMÜ", self.db.SIPARIS_TIP_SATIS, self.db.SIPARIS_TIP_ALIS])
        self.siparis_tipi_filter_cb.setCurrentText("TÜMÜ")
        self.siparis_tipi_filter_cb.currentIndexChanged.connect(self.siparis_listesini_yukle)
        filter_bottom_layout.addWidget(self.siparis_tipi_filter_cb)

        # Butonlar Çerçevesi
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        self.main_layout.addWidget(button_frame)
        
        yeni_musteri_siparisi_button = QPushButton("Yeni Müşteri Siparişi")
        yeni_musteri_siparisi_button.clicked.connect(lambda: self.yeni_siparis_penceresi_ac(self.db.SIPARIS_TIP_SATIS))
        button_layout.addWidget(yeni_musteri_siparisi_button)

        yeni_tedarikci_siparisi_button = QPushButton("Yeni Tedarikçi Siparişi")
        yeni_tedarikci_siparisi_button.clicked.connect(lambda: self.yeni_siparis_penceresi_ac(self.db.SIPARIS_TIP_ALIS))
        button_layout.addWidget(yeni_tedarikci_siparisi_button)

        self.detay_goster_button = QPushButton("Seçili Sipariş Detayları")
        self.detay_goster_button.clicked.connect(self.secili_siparis_detay_goster)
        self.detay_goster_button.setEnabled(False)
        button_layout.addWidget(self.detay_goster_button)

        self.duzenle_button = QPushButton("Seçili Siparişi Düzenle")
        self.duzenle_button.clicked.connect(self.secili_siparisi_duzenle)
        self.duzenle_button.setEnabled(False)
        button_layout.addWidget(self.duzenle_button)

        self.faturaya_donustur_button = QPushButton("Seçili Siparişi Faturaya Dönüştür")
        self.faturaya_donustur_button.clicked.connect(self.secili_siparisi_faturaya_donustur)
        self.faturaya_donustur_button.setEnabled(False)
        button_layout.addWidget(self.faturaya_donustur_button)

        self.sil_button = QPushButton("Seçili Siparişi Sil")
        self.sil_button.clicked.connect(self.secili_siparisi_sil)
        self.sil_button.setEnabled(False)
        button_layout.addWidget(self.sil_button)

        # Sayfalama için gerekli değişkenler ve widget'lar
        self.kayit_sayisi_per_sayfa = 20
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0

        pagination_frame = QFrame(self)
        pagination_layout = QHBoxLayout(pagination_frame)
        self.main_layout.addWidget(pagination_frame)

        onceki_sayfa_button = QPushButton("Önceki Sayfa")
        onceki_sayfa_button.clicked.connect(self.onceki_sayfa)
        pagination_layout.addWidget(onceki_sayfa_button)

        self.sayfa_bilgisi_label = QLabel("Sayfa 1 / 1")
        self.sayfa_bilgisi_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        pagination_layout.addWidget(self.sayfa_bilgisi_label)

        sonraki_sayfa_button = QPushButton("Sonraki Sayfa")
        sonraki_sayfa_button.clicked.connect(self.sonraki_sayfa)
        pagination_layout.addWidget(sonraki_sayfa_button)

        # Sipariş Listesi (QTreeWidget)
        cols = ("ID", "Sipariş No", "Tarih", "Cari Adı", "Sipariş Tipi", "Toplam Tutar", "Durum", "Teslimat Tarihi")
        self.siparis_tree = QTreeWidget(self)
        self.siparis_tree.setHeaderLabels(cols)
        self.siparis_tree.setColumnCount(len(cols))
        self.siparis_tree.setSelectionBehavior(QAbstractItemView.SelectRows) # Satır seçimi
        self.siparis_tree.setSortingEnabled(True) # Sıralama aktif
        
        # Sütun ayarları
        col_definitions = [
            ("ID", 40, Qt.AlignRight),
            ("Sipariş No", 100, Qt.AlignLeft),
            ("Tarih", 85, Qt.AlignCenter),
            ("Cari Adı", 180, Qt.AlignLeft),
            ("Sipariş Tipi", 100, Qt.AlignCenter),
            ("Toplam Tutar", 110, Qt.AlignRight),
            ("Durum", 100, Qt.AlignCenter),
            ("Teslimat Tarihi", 90, Qt.AlignCenter)
        ]
        for i, (col_name, width, alignment) in enumerate(col_definitions):
            self.siparis_tree.setColumnWidth(i, width)
            self.siparis_tree.headerItem().setTextAlignment(i, alignment)
            self.siparis_tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))

        self.siparis_tree.header().setStretchLastSection(False) # Son sütun otomatik genişlemesini kapat
        self.siparis_tree.header().setSectionResizeMode(3, QHeaderView.Stretch) # Cari Adı genişlesin

        self.main_layout.addWidget(self.siparis_tree) # Treeview'i ana layout'a ekle

        # Renk tagleri (PySide6'da doğrudan item üzerine style sheet uygulayacağız)
        # self.siparis_tree.tag_configure('tamamlandi', background='#D5F5E3', foreground='green') # Açık Yeşil
        # self.siparis_tree.tag_configure('beklemede', background='#FCF3CF', foreground='#874F15') # Açık Sarı
        # self.siparis_tree.tag_configure('iptal_edildi', background='#FADBD8', foreground='gray', font=('Segoe UI', 9, 'overstrike')) # Açık Kırmızı ve üzeri çizili

        self.siparis_tree.itemSelectionChanged.connect(self._on_siparis_select)
        self.siparis_tree.itemDoubleClicked.connect(self.on_double_click_detay_goster)

        self._yukle_filtre_comboboxlari()
        self.siparis_listesini_yukle()
        self._on_siparis_select() # Buton durumlarını ayarla

    def _open_date_picker(self, target_entry_qlineedit: QLineEdit):
        """
        PySide6 DatePickerDialog'u açar ve seçilen tarihi target_entry_qlineedit'e yazar.
        """
        # DatePickerDialog'un yeni PySide6 versiyonunu kullanıyoruz.
        # (yardimcilar.py'den import edildiğinden emin olun)

        # Mevcut tarihi al (eğer varsa) ve diyaloğa gönder
        initial_date_str = target_entry_qlineedit.text() if target_entry_qlineedit.text() else None

        dialog = DatePickerDialog(self.app, initial_date_str) # parent: self.app (ana uygulama penceresi)

        # Diyalogtan tarih seçildiğinde (date_selected sinyali)
        # QLineEdit'in setText metoduna bağlanır.
        dialog.date_selected.connect(target_entry_qlineedit.setText)

        # Diyaloğu modal olarak çalıştır
        dialog.exec()

    def _delayed_siparis_listesi_yukle(self): # event=None kaldırıldı
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self.siparis_listesini_yukle)

    def _yukle_filtre_comboboxlari(self):
        cari_display_values = ["TÜMÜ"]
        self.cari_filter_map = {"TÜMÜ": None}

        musteriler = self.db.musteri_listesi_al(perakende_haric=False)
        for m in musteriler:
            display_text = f"{m['ad']} (M: {m['kod']})"
            self.cari_filter_map[display_text] = str(m['id'])
            cari_display_values.append(display_text)

        tedarikciler = self.db.tedarikci_listesi_al()
        for t in tedarikciler:
            display_text = f"{t['ad']} (T: {t['tedarikci_kodu']})"
            self.cari_filter_map[display_text] = str(t['id'])
            cari_display_values.append(display_text)

        self.cari_filter_cb.clear()
        self.cari_filter_cb.addItem("TÜMÜ")
        self.cari_filter_cb.addItems(sorted([v for v in cari_display_values if v != "TÜMÜ"]))
        self.cari_filter_cb.setCurrentText("TÜMÜ")

        self.durum_filter_cb.setCurrentText("TÜMÜ")
        self.siparis_tipi_filter_cb.setCurrentText("TÜMÜ")

    def _on_siparis_select(self): # event=None kaldırıldı
        selected_items = self.siparis_tree.selectedItems()
        if selected_items:
            # Durum sütunu 7. sırada (indeks 6)
            durum = selected_items[0].text(6) 
            self.detay_goster_button.setEnabled(True)
            self.sil_button.setEnabled(True)
            
            # TAMAMLANDI veya İPTAL EDİLDİ ise Düzenle ve Faturaya Dönüştür pasif olsun
            if durum == 'TAMAMLANDI' or durum == 'İPTAL_EDİLDİ':
                self.duzenle_button.setEnabled(False)
                self.faturaya_donustur_button.setEnabled(False)
            else: # BEKLEMEDE veya KISMİ_TESLİMAT ise aktif olsun
                self.duzenle_button.setEnabled(True)
                self.faturaya_donustur_button.setEnabled(True)
        else:
            self.detay_goster_button.setEnabled(False)
            self.duzenle_button.setEnabled(False)
            self.faturaya_donustur_button.setEnabled(False)
            self.sil_button.setEnabled(False)

    def _arama_temizle(self):
        self.arama_siparis_entry.clear()
        self.cari_filter_cb.setCurrentText("TÜMÜ")
        self.durum_filter_cb.setCurrentText("TÜMÜ")
        self.siparis_tipi_filter_cb.setCurrentText("TÜMÜ")
        self.siparis_listesini_yukle()

    def siparis_listesini_yukle(self):
        self.siparis_tree.clear() # QTreeWidget'ı temizle
        
        bas_t = self.bas_tarih_entry.text()
        bit_t = self.bit_tarih_entry.text()
        arama_terimi = self.arama_siparis_entry.text().strip()

        selected_cari_filter_text = self.cari_filter_cb.currentText()
        cari_id_filter_val = self.cari_filter_map.get(selected_cari_filter_text, None)

        selected_durum_filter = self.durum_filter_cb.currentText()
        durum_filter_val = selected_durum_filter if selected_durum_filter != "TÜMÜ" else None
        
        selected_siparis_tipi_filter = self.siparis_tipi_filter_cb.currentText()
        
        siparis_tipi_filter_val = None
        if selected_siparis_tipi_filter == self.db.SIPARIS_TIP_SATIS:
            siparis_tipi_filter_val = self.db.CARI_TIP_MUSTERI
        elif selected_siparis_tipi_filter == self.db.SIPARIS_TIP_ALIS:
            siparis_tipi_filter_val = self.db.CARI_TIP_TEDARIKCI
            
        offset = (self.mevcut_sayfa - 1) * self.kayit_sayisi_per_sayfa
        limit = self.kayit_sayisi_per_sayfa        
        
        siparis_verileri = self.db.siparis_listele(
            baslangic_tarih=bas_t if bas_t else None, 
            bitis_tarih=bit_t if bit_t else None, 
            arama_terimi=arama_terimi if arama_terimi else None,
            cari_id_filter=cari_id_filter_val,
            durum_filter=durum_filter_val,
            siparis_tipi_filter=siparis_tipi_filter_val,
            limit=limit,
            offset=offset
        )
        
        for item in siparis_verileri:
            siparis_id = item['id']
            siparis_no = item['siparis_no']
            tarih_obj = item['tarih']
            cari_tip_db = item['cari_tip']
            cari_id_db = item['cari_id']
            toplam_tutar = item['toplam_tutar']
            durum = item['durum']
            teslimat_tarihi_obj = item['teslimat_tarihi']

            siparis_tipi_gosterim = "Satış Siparişi" if cari_tip_db == 'MUSTERI' else "Alış Siparişi"

            cari_adi_display = "Bilinmiyor"
            if cari_tip_db == 'MUSTERI':
                cari_bilgi = self.db.musteri_getir_by_id(cari_id_db)
                cari_adi_display = f"{cari_bilgi['ad']} (M: {cari_bilgi['kod']})" if cari_bilgi else "Bilinmiyor"
            elif cari_tip_db == 'TEDARIKCI':
                cari_bilgi = self.db.tedarikci_getir_by_id(cari_id_db)
                cari_adi_display = f"{cari_bilgi['ad']} (T: {cari_bilgi['tedarikci_kodu']})" if cari_bilgi else "Bilinmiyor"

            formatted_tarih = tarih_obj.strftime('%d.%m.%Y') if isinstance(tarih_obj, (date, datetime)) else str(tarih_obj or "")
            formatted_teslimat_tarihi = teslimat_tarihi_obj.strftime('%d.%m.%Y') if isinstance(teslimat_tarihi_obj, (date, datetime)) else (teslimat_tarihi_obj or "-")
            
            item_qt = QTreeWidgetItem(self.siparis_tree)
            item_qt.setText(0, str(siparis_id))
            item_qt.setText(1, siparis_no)
            item_qt.setText(2, formatted_tarih)
            item_qt.setText(3, cari_adi_display)
            item_qt.setText(4, siparis_tipi_gosterim)
            item_qt.setText(5, self.db._format_currency(toplam_tutar))
            item_qt.setText(6, durum)
            item_qt.setText(7, formatted_teslimat_tarihi)

            # Renk tagleri
            if durum == 'TAMAMLANDI':
                for col_idx in range(self.siparis_tree.columnCount()):
                    item_qt.setBackground(col_idx, QBrush(QColor("#D5F5E3"))) # Açık Yeşil
                    item_qt.setForeground(col_idx, QBrush(QColor("green")))
            elif durum in ['BEKLEMEDE', 'KISMİ_TESLİMAT']:
                for col_idx in range(self.siparis_tree.columnCount()):
                    item_qt.setBackground(col_idx, QBrush(QColor("#FCF3CF"))) # Açık Sarı
                    item_qt.setForeground(col_idx, QBrush(QColor("#874F15"))) # Kahverengi
            elif durum == 'İPTAL_EDİLDİ':
                for col_idx in range(self.siparis_tree.columnCount()):
                    item_qt.setBackground(col_idx, QBrush(QColor("#FADBD8"))) # Açık Kırmızı
                    item_qt.setForeground(col_idx, QBrush(QColor("gray")))
                    font = item_qt.font(col_idx) # Üzeri çizili font
                    font.setStrikeOut(True)
                    item_qt.setFont(col_idx, font)
            
            # Sayısal sütunlar için sıralama anahtarları
            item_qt.setData(0, Qt.UserRole, siparis_id) # ID
            item_qt.setData(5, Qt.UserRole, toplam_tutar) # Toplam Tutar
            
        self.toplam_kayit_sayisi = self.db.get_siparis_count(
            baslangic_tarih=bas_t if bas_t else None, 
            bitis_tarih=bit_t if bit_t else None, 
            arama_terimi=arama_terimi if arama_terimi else None,
            cari_id_filter=cari_id_filter_val, 
            durum_filter=durum_filter_val,
            siparis_tipi_filter=siparis_tipi_filter_val
        )
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0: toplam_sayfa = 1

        if self.mevcut_sayfa > toplam_sayfa:
            self.mevcut_sayfa = toplam_sayfa
            
        self.app.set_status_message(f"{len(siparis_verileri)} sipariş listelendi. Toplam {self.toplam_kayit_sayisi} kayıt.")
        self.sayfa_bilgisi_label.setText(f"Sayfa {self.mevcut_sayfa} / {toplam_sayfa}")
        self._on_siparis_select() # Buton durumlarını ayarla

    def on_item_double_click(self, item, column): # item ve column sinyalden gelir
        QMessageBox.information(self.app, "Bilgi", "Bu işlem bir fatura değildir, detayı görüntülenemez (Placeholder).")

    def yeni_siparis_penceresi_ac(self, siparis_tipi):
        # NOT: pencereler.py dosyasındaki SiparisPenceresi'nin PySide6'ya dönüştürülmüş olması gerekmektedir.
        # Bu fonksiyon, SiparisPenceresi'nin PySide6 versiyonu hazır olduğunda aktif olarak çalışacaktır.

        # Geçici olarak, pencereler modülünü bu fonksiyon içinde import edelim
        try:
            from pencereler import SiparisPenceresi # PySide6 SiparisPenceresi varsayılıyor
            
            # Yeni sipariş ekleme modunda SiparisPenceresi'ni başlat
            siparis_penceresi = SiparisPenceresi(
                self.app, # Ana uygulama penceresi (parent)
                self.db, # Veritabanı yöneticisi
                self.app, # app_ref (App sınıfının kendisi)
                siparis_tipi, # 'SATIŞ_SIPARIS' veya 'ALIŞ_SIPARIS'
                siparis_id_duzenle=None, # Yeni sipariş eklediğimiz için None
                yenile_callback=self.siparis_listesini_yukle # Pencere kapatıldığında listeyi yenilemek için callback
            )
            # Pencereyi göster
            siparis_penceresi.show()
            self.app.set_status_message(f"Yeni {siparis_tipi.lower().replace('_', ' ')} penceresi açıldı.")

        except ImportError:
            QMessageBox.critical(self, "Hata", "SiparisPenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
            self.app.set_status_message(f"Hata: Yeni {siparis_tipi.lower().replace('_', ' ')} penceresi açılamadı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yeni sipariş penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Yeni sipariş penceresi açılamadı - {e}")

    def secili_siparis_detay_goster(self):
        selected_items = self.siparis_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen detaylarını görmek için bir sipariş seçin.")
            return
        
        selected_item = selected_items[0]
        siparis_id = int(selected_item.text(0)) # Sipariş ID'si ilk sütunda

        if siparis_id == -1: # Eğer ID placeholder ise
             QMessageBox.warning(self.app, "Uyarı", "Geçersiz bir sipariş seçimi yaptınız.")
             return

        # NOT: pencereler.py dosyasındaki SiparisDetayPenceresi'nin PySide6'ya dönüştürülmüş olması gerekmektedir.
        # Bu fonksiyon, SiparisDetayPenceresi'nin PySide6 versiyonu hazır olduğunda aktif olarak çalışacaktır.

        # Geçici olarak, pencereler modülünü bu fonksiyon içinde import edelim
        try:
            from pencereler import SiparisDetayPenceresi # PySide6 SiparisDetayPenceresi varsayılıyor
            
            # Sipariş Detay penceresini başlat
            siparis_detay_penceresi = SiparisDetayPenceresi(
                self.app, # Ana uygulama penceresi (parent)
                self.db, # Veritabanı yöneticisi
                siparis_id, # Sipariş ID'si
                yenile_callback=self.siparis_listesini_yukle # Detay penceresi kapatıldığında listeyi yenilemek için callback
            )
            # Pencereyi göster
            siparis_detay_penceresi.show()
            self.app.set_status_message(f"Sipariş ID: {siparis_id} için detay penceresi açıldı.")

        except ImportError:
            QMessageBox.critical(self.app, "Hata", "SiparisDetayPenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
            self.app.set_status_message(f"Hata: Sipariş Detay penceresi açılamadı.")
        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Sipariş Detay penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Sipariş Detay penceresi açılamadı - {e}")

    def on_double_click_detay_goster(self, item, column): # item ve column sinyalden gelir
        self.secili_siparis_detay_goster()

    def secili_siparisi_duzenle(self):
        selected_items = self.siparis_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen düzenlemek için bir sipariş seçin.")
            return
            
        selected_item = selected_items[0]
        siparis_id = int(selected_item.text(0)) # Sipariş ID'si ilk sütunda

        if siparis_id == -1: # Eğer ID placeholder ise
             QMessageBox.warning(self.app, "Uyarı", "Geçersiz bir sipariş seçimi yaptınız.")
             return

        try:
            # API'den seçili siparişin detaylarını çek
            api_url = f"http://127.0.0.1:8000/siparisler/{siparis_id}" 
            response = requests.get(api_url)
            response.raise_for_status()
            siparis_detaylari = response.json() # Siparişin tüm detayları JSON olarak gelir
            
            if not siparis_detaylari:
                QMessageBox.critical(self.app, "Hata", "Seçili sipariş API'den bulunamadı.")
                self.siparis_listesini_yukle() # Listeyi yenile
                return

            # NOT: pencereler.py dosyasındaki SiparisPenceresi'nin PySide6'ya dönüştürülmüş olması gerekmektedir.
            # Bu fonksiyon, SiparisPenceresi'nin PySide6 versiyonu hazır olduğunda aktif olarak çalışacaktır.

            # Geçici olarak, pencereler modülünü bu fonksiyon içinde import edelim
            try:
                from pencereler import SiparisPenceresi # PySide6 SiparisPenceresi varsayılıyor
                
                # Sipariş düzenleme modunda SiparisPenceresi'ni başlat
                siparis_penceresi = SiparisPenceresi(
                    self.app, # Ana uygulama penceresi (parent)
                    self.db, # Veritabanı yöneticisi
                    self.app, # app_ref (App sınıfının kendisi)
                    siparis_detaylari['siparis_tipi'], # API'den gelen sipariş tipi
                    siparis_id_duzenle=siparis_id, # Düzenlenecek siparişin ID'si
                    yenile_callback=self.siparis_listesini_yukle, # Pencere kapatıldığında listeyi yenilemek için callback
                    initial_data=siparis_detaylari # Sipariş detaylarını initial_data olarak gönderiyoruz
                )
                # Pencereyi göster
                siparis_penceresi.show()
                self.app.set_status_message(f"Sipariş ID: {siparis_id} için düzenleme penceresi açıldı.")

            except ImportError:
                QMessageBox.critical(self.app, "Hata", "SiparisPenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
                self.app.set_status_message(f"Hata: Sipariş düzenleme penceresi açılamadı.")
            except Exception as e:
                QMessageBox.critical(self.app, "Hata", f"Sipariş düzenleme penceresi açılırken bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Hata: Sipariş düzenleme penceresi açılamadı - {e}")

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self.app, "API Bağlantı Hatası", f"Sipariş detayları API'den alınamadı:\n{error_detail}")
            self.app.set_status_message(f"Hata: Sipariş detayları alınamadı - {error_detail}")

    def secili_siparisi_faturaya_donustur(self):
        selected_items = self.siparis_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen faturaya dönüştürmek için bir sipariş seçin.")
            return

        selected_item = selected_items[0]
        siparis_id = int(selected_item.text(0)) # Sipariş ID'si
        siparis_no = selected_item.text(1) # Sipariş No

        if siparis_id == -1: # Eğer ID placeholder ise
             QMessageBox.warning(self.app, "Uyarı", "Geçersiz bir sipariş seçimi yaptınız.")
             return
        
        # Siparişin detaylarını API'den çekelim, böylece cari_id ve cari_tip gibi bilgilere erişebiliriz
        try:
            api_url = f"http://127.0.0.1:8000/siparisler/{siparis_id}"
            response = requests.get(api_url)
            response.raise_for_status()
            siparis_detaylari = response.json()

            if not siparis_detaylari:
                QMessageBox.critical(self.app, "Hata", "Sipariş detayları API'den alınamadı.")
                self.siparis_listesini_yukle()
                return

            # Cari ID ve tipi al
            initial_cari_id = siparis_detaylari['cari_id']
            # API'den gelen siparis_tipi, 'SATIŞ_SIPARIS' veya 'ALIŞ_SIPARIS' olabilir.
            # OdemeTuruSecimDialog'a 'SATIŞ' veya 'ALIŞ' olarak iletmeliyiz.
            fatura_tipi_for_dialog = 'SATIŞ' if siparis_detaylari['cari_tip'] == self.db.CARI_TIP_MUSTERI else 'ALIŞ'

            # NOT: pencereler.py dosyasındaki OdemeTuruSecimDialog'un PySide6'ya dönüştürülmüş olması gerekmektedir.
            # Bu fonksiyon, OdemeTuruSecimDialog'un PySide6 versiyonu hazır olduğunda aktif olarak çalışacaktır.

            # Geçici olarak, pencereler modülünü bu fonksiyon içinde import edelim
            try:
                from pencereler import OdemeTuruSecimDialog # PySide6 OdemeTuruSecimDialog varsayılıyor
                
                # OdemeTuruSecimDialog'u başlat
                dialog = OdemeTuruSecimDialog(
                    self.app, # parent_app
                    self.db, # db_manager
                    fatura_tipi_for_dialog, # 'SATIŞ' veya 'ALIŞ'
                    initial_cari_id, # Cari ID
                    lambda odeme_turu, kasa_banka_id, vade_tarihi: self._on_fatura_donustur_dialog_closed(
                        siparis_id, siparis_no, odeme_turu, kasa_banka_id, vade_tarihi
                    ) # Callback fonksiyonu
                )
                dialog.show() # Modeless olarak göster

            except ImportError:
                QMessageBox.critical(self.app, "Hata", "OdemeTuruSecimDialog modülü veya PySide6 uyumlu versiyonu bulunamadı.")
                self.app.set_status_message(f"Hata: Ödeme Türü Seçim penceresi açılamadı.")
            except Exception as e:
                QMessageBox.critical(self.app, "Hata", f"Ödeme Türü Seçim penceresi açılırken bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Hata: Ödeme Türü Seçim penceresi açılamadı - {e}")

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self.app, "API Bağlantı Hatası", f"Sipariş detayları API'den alınamadı:\n{error_detail}")
            self.app.set_status_message(f"Hata: Sipariş detayları alınamadı - {error_detail}")

    def _on_fatura_donustur_dialog_closed(self, siparis_id, s_no, odeme_turu, kasa_banka_id, vade_tarihi):
        """
        OdemeTuruSecimDialog kapatıldığında ve onaylandığında çağrılır.
        Siparişi faturaya dönüştürme işlemini başlatır.
        """
        if odeme_turu is None: # Kullanıcı iptal ettiyse
            self.app.set_status_message("Siparişi faturaya dönüştürme işlemi iptal edildi.")
            return

        confirm_msg = (f"'{s_no}' numaralı siparişi '{odeme_turu}' ödeme türü ile faturaya dönüştürmek istediğinizden emin misiniz?\n"
                       f"Bu işlem sonucunda yeni bir fatura oluşturulacak ve sipariş durumu güncellenecektir.")
        if odeme_turu == "AÇIK HESAP" and vade_tarihi:
            confirm_msg += f"\nVade Tarihi: {vade_tarihi}"
        if kasa_banka_id:
            # Kasa/banka adını almak için API'ye istek atabiliriz, şimdilik ID ile idare edelim.
            # Veya bu bilgi OdemeTuruSecimDialog'dan da döndürülebilir.
            confirm_msg += f"\nİşlem Kasa/Banka ID: {kasa_banka_id}"

        reply = QMessageBox.question(self.app, "Faturaya Dönüştür Onayı", confirm_msg,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # Kullanıcı ID'sini al (Örnek olarak self.app.current_user[0] veya bir varsayılan)
                olusturan_kullanici_id = self.app.current_user[0] if hasattr(self.app, 'current_user') and self.app.current_user else 1 # Varsayılan olarak 1 (admin)
                
                # FaturaService üzerinden API çağrısı
                # NOT: hizmetler.py içindeki FaturaService.siparis_faturaya_donustur metodu API'den çağrılmıyor.
                # Bu kısım API backend'ine eklenmeli ve requests.post ile çağrılmalıdır.
                # Şimdilik direkt hizmetler.py metodunu çağırıyoruz.

                # FaturaService bir veritabanı yöneticisiyle başlatıldığı için ona erişmemiz gerekiyor.
                # self.app.fatura_servisi doğrudan hizmetler.py'deki FaturaService'e bir referans olmalıdır.
                success, message = self.app.fatura_servisi.siparis_faturaya_donustur(
                    siparis_id,
                    olusturan_kullanici_id,
                    odeme_turu,
                    kasa_banka_id,
                    vade_tarihi
                )

                if success:
                    QMessageBox.information(self.app, "Başarılı", message)
                    self.siparis_listesini_yukle() # Sipariş listesini yenile
                    # İlgili Fatura listelerini de yenile
                    if hasattr(self.app, 'fatura_listesi_sayfasi'):
                        if hasattr(self.app.fatura_listesi_sayfasi.satis_fatura_frame, 'fatura_listesini_yukle'):
                            self.app.fatura_listesi_sayfasi.satis_fatura_frame.fatura_listesini_yukle()
                        if hasattr(self.app.fatura_listesi_sayfasi.alis_fatura_frame, 'fatura_listesini_yukle'):
                            self.app.fatura_listesi_sayfasi.alis_fatura_frame.fatura_listesini_yukle()
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self.app, "Hata", message)
                    self.app.set_status_message(f"Siparişi faturaya dönüştürme başarısız: {message}")

            except Exception as e:
                logging.error(f"Siparişi faturaya dönüştürürken beklenmeyen bir hata oluştu: {e}\n{traceback.format_exc()}")
                QMessageBox.critical(self.app, "Kritik Hata", f"Siparişi faturaya dönüştürürken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Hata: Siparişi faturaya dönüştürme - {e}")
        else:
            self.app.set_status_message("Siparişi faturaya dönüştürme işlemi kullanıcı tarafından iptal edildi.")

    def secili_siparisi_sil(self):
        selected_items = self.siparis_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir sipariş seçin.")
            return

        siparis_id = int(selected_items[0].text(0))
        siparis_no = selected_items[0].text(1)

        reply = QMessageBox.question(self.app, "Sipariş Silme Onayı", 
                                     f"'{siparis_no}' numaralı siparişi silmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            success, message = self.db.siparis_sil(siparis_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.siparis_listesini_yukle()
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self.app, "Hata", message)
                self.app.set_status_message(f"Sipariş silme başarısız: {message}")

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.siparis_listesini_yukle()

    def sonraki_sayfa(self):
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0: toplam_sayfa = 1

        if self.mevcut_sayfa < toplam_sayfa:
            self.mevcut_sayfa += 1
            self.siparis_listesini_yukle()

class BaseFaturaListesi(QWidget):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.fatura_tipi = fatura_tipi
        self.main_layout = QVBoxLayout(self)

        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)
        
        self.kayit_sayisi_per_sayfa = 20
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0
        
        self.cari_filter_map = {"TÜMÜ": None}

        if self.fatura_tipi == self.db.FATURA_TIP_SATIS:
            self.fatura_tipleri_filter_options = ["TÜMÜ", self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE]
        elif self.fatura_tipi == self.db.FATURA_TIP_ALIS:
            self.fatura_tipleri_filter_options = ["TÜMÜ", self.db.FATURA_TIP_ALIS, self.db.FATURA_TIP_DEVIR_GIRIS, self.db.FATURA_TIP_ALIS_IADE]
        
        self._create_ui_elements()
        self._yukle_filtre_comboboxlari()
        self.fatura_listesini_yukle()
        self._on_fatura_select()

    def _create_ui_elements(self):
        """Tüm UI elemanlarını (filtreler, butonlar, treeview) oluşturan yardımcı metod."""
        
        # Filtreleme Üst Çerçevesi
        filter_top_frame = QFrame(self)
        filter_top_layout = QHBoxLayout(filter_top_frame)
        self.main_layout.addWidget(filter_top_frame)

        filter_top_layout.addWidget(QLabel("Başlangıç Tarihi:"))
        self.bas_tarih_entry = QLineEdit((datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        filter_top_layout.addWidget(self.bas_tarih_entry)
        
        takvim_button_bas = QPushButton("🗓️")
        takvim_button_bas.setFixedWidth(30)
        # takvim_button_bas.clicked.connect(lambda: DatePickerDialog(self.app, self.bas_tarih_entry))
        filter_top_layout.addWidget(takvim_button_bas)

        filter_top_layout.addWidget(QLabel("Bitiş Tarihi:"))
        self.bit_tarih_entry = QLineEdit(datetime.now().strftime('%Y-%m-%d'))
        filter_top_layout.addWidget(self.bit_tarih_entry)
        
        takvim_button_bit = QPushButton("🗓️")
        takvim_button_bit.setFixedWidth(30)
        # takvim_button_bit.clicked.connect(lambda: DatePickerDialog(self.app, self.bit_tarih_entry))
        filter_top_layout.addWidget(takvim_button_bit)

        filter_top_layout.addWidget(QLabel("Fatura Tipi:"))
        self.fatura_tipi_filter_cb = QComboBox()
        self.fatura_tipi_filter_cb.addItems(self.fatura_tipleri_filter_options)
        self.fatura_tipi_filter_cb.currentIndexChanged.connect(self.fatura_listesini_yukle)
        filter_top_layout.addWidget(self.fatura_tipi_filter_cb)

        filter_top_layout.addWidget(QLabel("Ara (F.No/Cari/Misafir/Ürün):"))
        self.arama_fatura_entry = QLineEdit()
        self.arama_fatura_entry.setPlaceholderText("Fatura No, Cari Adı, Misafir veya Ürün ara...")
        self.arama_fatura_entry.textChanged.connect(self._delayed_fatura_listesi_yukle)
        filter_top_layout.addWidget(self.arama_fatura_entry)
        
        temizle_button = QPushButton("Temizle")
        temizle_button.clicked.connect(self._arama_temizle)
        filter_top_layout.addWidget(temizle_button)

        filtre_yenile_button = QPushButton("Filtrele/Yenile")
        filtre_yenile_button.clicked.connect(self.fatura_listesini_yukle)
        filter_top_layout.addWidget(filtre_yenile_button)

        # Diğer Filtreleme Alanları (Cari, Ödeme Türü, Kasa/Banka)
        filter_bottom_frame = QFrame(self)
        filter_bottom_layout = QHBoxLayout(filter_bottom_frame)
        self.main_layout.addWidget(filter_bottom_frame)

        filter_bottom_layout.addWidget(QLabel("Cari Filtre:"))
        self.cari_filter_cb = QComboBox()
        self.cari_filter_cb.currentIndexChanged.connect(self.fatura_listesini_yukle)
        filter_bottom_layout.addWidget(self.cari_filter_cb)
        self.cari_filter_dropdown_button = QPushButton("▼")
        self.cari_filter_dropdown_button.setFixedWidth(30)
        self.cari_filter_dropdown_button.clicked.connect(lambda: self._open_filter_dropdown(filter_type='cari', is_manual_open=True))
        filter_bottom_layout.addWidget(self.cari_filter_dropdown_button)

        filter_bottom_layout.addWidget(QLabel("Ödeme Türü:"))
        self.odeme_turu_filter_entry = QLineEdit()
        self.odeme_turu_filter_entry.setPlaceholderText("Ödeme türü ara...")
        self.odeme_turu_filter_entry.textChanged.connect(lambda: self._open_filter_dropdown_delayed('odeme_turu'))
        self.odeme_turu_filter_entry.returnPressed.connect(lambda: self._select_first_from_dropdown_and_filter('odeme_turu'))
        filter_bottom_layout.addWidget(self.odeme_turu_filter_entry)

        self.odeme_turu_filter_dropdown_button = QPushButton("▼")
        self.odeme_turu_filter_dropdown_button.setFixedWidth(30)
        self.odeme_turu_filter_dropdown_button.clicked.connect(lambda: self._open_filter_dropdown(filter_type='odeme_turu', is_manual_open=True))
        filter_bottom_layout.addWidget(self.odeme_turu_filter_dropdown_button)


        filter_bottom_layout.addWidget(QLabel("Kasa/Banka:"))
        self.kasa_banka_filter_entry = QLineEdit()
        self.kasa_banka_filter_entry.setPlaceholderText("Kasa/Banka ara...")
        self.kasa_banka_filter_entry.textChanged.connect(lambda: self._open_filter_dropdown_delayed('kasa_banka'))
        self.kasa_banka_filter_entry.returnPressed.connect(lambda: self._select_first_from_dropdown_and_filter('kasa_banka'))
        filter_bottom_layout.addWidget(self.kasa_banka_filter_entry)

        self.kasa_banka_filter_dropdown_button = QPushButton("▼")
        self.kasa_banka_filter_dropdown_button.setFixedWidth(30)
        self.kasa_banka_filter_dropdown_button.clicked.connect(lambda: self._open_filter_dropdown(filter_type='kasa_banka', is_manual_open=True))
        filter_bottom_layout.addWidget(self.kasa_banka_filter_dropdown_button)

        # Butonlar Çerçevesi (orta kısım)
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        self.main_layout.addWidget(button_frame)

        self.btn_fatura_detay = QPushButton("Seçili Fatura Detayları")
        self.btn_fatura_detay.clicked.connect(self.secili_fatura_detay_goster)
        button_layout.addWidget(self.btn_fatura_detay)

        self.btn_fatura_pdf_yazdir = QPushButton("Seçili Faturayı PDF Yazdır")
        self.btn_fatura_pdf_yazdir.clicked.connect(self.secili_faturayi_yazdir)
        button_layout.addWidget(self.btn_fatura_pdf_yazdir)

        self.btn_fatura_guncelle = QPushButton("Seçili Faturayı Güncelle")
        self.btn_fatura_guncelle.clicked.connect(self.secili_faturayi_guncelle)
        button_layout.addWidget(self.btn_fatura_guncelle)

        self.btn_fatura_sil = QPushButton("Seçili Faturayı Sil")
        self.btn_fatura_sil.clicked.connect(self.secili_faturayi_sil)
        button_layout.addWidget(self.btn_fatura_sil)

        self.btn_iade_faturasi = QPushButton("İade Faturası Oluştur")
        self.btn_iade_faturasi.clicked.connect(self._iade_faturasi_olustur_ui)
        button_layout.addWidget(self.btn_iade_faturasi)

        # Sayfalama Çerçevesi (Alt kısım)
        pagination_frame = QFrame(self)
        pagination_layout = QHBoxLayout(pagination_frame)
        self.main_layout.addWidget(pagination_frame)

        onceki_sayfa_button = QPushButton("Önceki Sayfa")
        onceki_sayfa_button.clicked.connect(self.onceki_sayfa)
        pagination_layout.addWidget(onceki_sayfa_button)

        self.sayfa_bilgisi_label = QLabel("Sayfa 1 / 1")
        pagination_layout.addWidget(self.sayfa_bilgisi_label)

        sonraki_sayfa_button = QPushButton("Sonraki Sayfa")
        sonraki_sayfa_button.clicked.connect(self.sonraki_sayfa)
        pagination_layout.addWidget(sonraki_sayfa_button)

        # Fatura Listesi QTreeWidget
        cari_adi_col_text = "Müşteri/Cari Adı" if self.fatura_tipi == 'SATIŞ' else "Tedarikçi/Cari Adı"
        cols = ("ID", "Fatura No", "Tarih", cari_adi_col_text, "Fatura Tipi", "Ödeme Türü", "Toplam Tutar", "Vade Tarihi")
        self.fatura_tree = QTreeWidget(self)
        self.fatura_tree.setHeaderLabels(cols)
        self.main_layout.addWidget(self.fatura_tree)
        self.fatura_tree.itemSelectionChanged.connect(self._on_fatura_select)

    def _iade_faturasi_olustur_ui(self):
        selected_items = self.fatura_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen iade faturası oluşturmak için bir fatura seçin.")
            return

        selected_item = selected_items[0]
        fatura_id = int(selected_item.data(0, Qt.UserRole)) # Fatura ID'si
        fatura_no = selected_item.text(1) # Fatura No
        fatura_tipi = selected_item.text(4) # Fatura Tipi (SATIŞ, ALIŞ vb.)

        if fatura_id == -1: # Eğer ID placeholder ise
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir fatura seçimi yaptınız.")
             return

        # Sadece SATIŞ veya ALIŞ faturaları için iade oluşturulabilir. İade faturalarının iadesi olmaz.
        if fatura_tipi not in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_ALIS]:
            QMessageBox.warning(self, "Uyarı", f"Sadece '{self.db.FATURA_TIP_SATIS}' veya '{self.db.FATURA_TIP_ALIS}' tipi faturalar için iade oluşturulabilir. Seçilen fatura tipi: {fatura_tipi}")
            return
        
        # API'den orijinal faturanın detaylarını çek
        try:
            api_url = f"http://127.0.0.1:8000/faturalar/{fatura_id}" # API'de bu endpoint henüz yok, ama olması gerekiyor
            # NOT: api/rotalar/faturalar.py dosyasında tek bir faturayı getiren bir GET endpoint'i henüz bulunmamaktadır.
            # Bu fonksiyonun düzgün çalışabilmesi için o endpoint'in de eklenmesi gerekecektir.
            # Şimdilik, veritabanından direkt çekiyoruz.
            original_fatura_detaylari = self.db.fatura_getir_by_id(fatura_id) # API endpoint'i yerine geçici olarak DB'den çekiyoruz

            if not original_fatura_detaylari:
                QMessageBox.critical(self, "Hata", "Orijinal fatura detayları veritabanında bulunamadı.")
                self.fatura_listesini_yukle()
                return

            # NOT: pencereler.py dosyasındaki FaturaPenceresi'nin PySide6'ya dönüştürülmüş olması gerekmektedir.
            # Bu fonksiyon, FaturaPenceresi'nin PySide6 versiyonu hazır olduğunda aktif olarak çalışacaktır.

            # Geçici olarak, pencereler modülünü bu fonksiyon içinde import edelim
            try:
                from pencereler import FaturaPenceresi # PySide6 FaturaPenceresi varsayılıyor
                
                # İade faturası modu için initial_data hazırla
                # FaturaPenceresi'ne iade_modu ve orijinal_fatura_id bilgisini gönderiyoruz.
                initial_data_for_iade = {
                    'iade_modu': True,
                    'orijinal_fatura_id': fatura_id,
                    'fatura_no': fatura_no, # Başlıkta göstermek için orijinal fatura no
                    # Diğer alanlar FaturaPenceresi içinde orijinal faturadan çekilecek
                    # veya burada daha fazla bilgi eklenebilir.
                }

                # FaturaPenceresi'ni iade modu ve orijinal fatura detayları ile başlat
                iade_fatura_penceresi = FaturaPenceresi(
                    self.app, # Ana uygulama penceresi (parent)
                    self.db, # Veritabanı yöneticisi
                    self.app, # app_ref
                    fatura_tipi, # Orijinal fatura tipi (SATIŞ veya ALIŞ)
                    duzenleme_id=None, # Bu yeni bir fatura olduğu için None
                    yenile_callback=self.fatura_listesini_yukle, # İade faturası kaydedilince listeyi yenile
                    initial_data=initial_data_for_iade
                )
                # Pencereyi göster
                iade_fatura_penceresi.show()
                self.app.set_status_message(f"'{fatura_no}' için iade faturası oluşturma penceresi açıldı.")

            except ImportError:
                QMessageBox.critical(self, "Hata", "FaturaPenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
                self.app.set_status_message("Hata: İade Faturası penceresi açılamadı.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"İade faturası penceresi açılırken bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Hata: İade Faturası penceresi açılamadı - {e}")

        except Exception as e: # requests.exceptions.RequestException yerine genel Exception
            QMessageBox.critical(self, "Hata", f"Orijinal fatura detayları alınırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Orijinal fatura detayları alınamadı - {e}")

    def _open_date_picker(self, target_entry_qlineedit: QLineEdit):
        """
        PySide6 DatePickerDialog'u açar ve seçilen tarihi target_entry_qlineedit'e yazar.
        """
        # DatePickerDialog'un yeni PySide6 versiyonunu kullanıyoruz.
        # (yardimcilar.py'den import edildiğinden emin olun)

        # Mevcut tarihi al (eğer varsa) ve diyaloğa gönder
        initial_date_str = target_entry_qlineedit.text() if target_entry_qlineedit.text() else None

        dialog = DatePickerDialog(self.app, initial_date_str) # parent: self.app (ana uygulama penceresi)

        # Diyalogtan tarih seçildiğinde (date_selected sinyali)
        # QLineEdit'in setText metoduna bağlanır.
        dialog.date_selected.connect(target_entry_qlineedit.setText)

        # Diyaloğu modal olarak çalıştır
        dialog.exec()

    def _delayed_fatura_listesi_yukle(self):
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self.fatura_listesini_yukle)

    def _yukle_filtre_comboboxlari(self):
        self.cari_filter_cb.clear()
        self.cari_filter_map = {"TÜMÜ": None}
        self.cari_filter_cb.addItem("TÜMÜ", None)
        try:
            api_url = ""
            if self.fatura_tipi == 'SATIŞ':
                api_url = "http://127.0.0.1:8000/nitelikler/musteriler"
            elif self.fatura_tipi == 'ALIŞ':
                api_url = "http://127.0.0.1:8000/nitelikler/tedarikciler"
            if api_url:
                response = requests.get(api_url)
                response.raise_for_status()
                cariler = response.json()
                for cari in cariler:
                    display_text = f"{cari.get('ad')} (Kod: {cari.get('kod') or cari.get('tedarikci_kodu')})"
                    self.cari_filter_map[display_text] = cari.get('id')
                    self.cari_filter_cb.addItem(display_text, cari.get('id'))
        except requests.exceptions.RequestException as e:
            self.app.set_status_message(f"Hata: Cari filtresi verileri alınamadı: {e}")

    def _arama_temizle(self):
        self.arama_fatura_entry.clear()
        self.fatura_listesini_yukle()

    def fatura_listesini_yukle(self):
        self.fatura_tree.clear()
        self.sayfa_bilgisi_label.setText("Sayfa 0 / 0")

        try:
            # Filtreleri UI elemanlarından al
            bas_t = self.bas_tarih_entry.text()
            bit_t = self.bit_tarih_entry.text()
            arama_terimi = self.arama_fatura_entry.text().strip()
            selected_fatura_tipi_filter = self.fatura_tipi_filter_cb.currentText()
            fatura_tipi_filter_val = selected_fatura_tipi_filter if selected_fatura_tipi_filter != "TÜMÜ" else None
            selected_cari_filter_text = self.cari_filter_cb.currentText()
            cari_id_filter_val = self.cari_filter_map.get(selected_cari_filter_text, None)
            
            offset = (self.mevcut_sayfa - 1) * self.kayit_sayisi_per_sayfa
            limit = self.kayit_sayisi_per_sayfa
            
            # API'ye gönderilecek parametreleri oluştur
            list_params = {
                'skip': offset,
                'limit': limit,
                'tip': fatura_tipi_filter_val,
                'bas_t': bas_t,
                'bit_t': bit_t,
                'arama': arama_terimi,
                'cari_id': cari_id_filter_val
            }
            # Sadece dolu olan parametreleri gönder
            list_params = {k: v for k, v in list_params.items() if v is not None and str(v).strip() != ""}

            # API isteğini doğru metotla (`GET`) ve parametrelerle yap
            list_api_url = "http://127.0.0.1:8000/faturalar/"
            list_response = requests.get(list_api_url, params=list_params)
            list_response.raise_for_status()
            fatura_listesi = list_response.json()


            for fatura in fatura_listesi:
                item_qt = QTreeWidgetItem(self.fatura_tree)
                item_qt.setData(0, Qt.UserRole, fatura.get('id', -1))
                item_qt.setText(0, str(fatura.get('id', '')))
                item_qt.setText(1, fatura.get('fatura_no', ''))
                
                # Tarih objesi kontrolü ve formatlama
                tarih_obj = fatura.get('tarih', '')
                if isinstance(tarih_obj, str):
                    try:
                        tarih_obj = datetime.strptime(tarih_obj, '%Y-%m-%d').date()
                    except ValueError:
                        pass # Hatalı tarih formatı ise string olarak kalsın

                item_qt.setText(2, tarih_obj.strftime('%d.%m.%Y') if isinstance(tarih_obj, (datetime, date)) else str(tarih_obj))
                
                item_qt.setText(3, fatura.get('cari_adi', '')) # Cari Adı API'den gelmeli
                item_qt.setText(4, fatura.get('tip', ''))
                item_qt.setText(5, fatura.get('odeme_turu', '-'))
                item_qt.setText(6, f"{fatura.get('toplam_kdv_dahil', 0):.2f} TL")
                
                # Vade Tarihi için kontrol ve formatlama
                vade_tarihi_obj = fatura.get('vade_tarihi', '')
                if isinstance(vade_tarihi_obj, str):
                    try:
                        vade_tarihi_obj = datetime.strptime(vade_tarihi_obj, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                item_qt.setText(7, vade_tarihi_obj.strftime('%d.%m.%Y') if isinstance(vade_tarihi_obj, (datetime, date)) else (str(vade_tarihi_obj) if vade_tarihi_obj else '-'))


            # Sayfalama bilgisi güncel
            toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
            if toplam_sayfa == 0: toplam_sayfa = 1

            # Mevcut sayfa toplam sayfa sayısından büyükse ayarla
            if self.mevcut_sayfa > toplam_sayfa:
                self.mevcut_sayfa = toplam_sayfa
            
            self.sayfa_bilgisi_label.setText(f"Sayfa {self.mevcut_sayfa} / {toplam_sayfa}")
            self.app.set_status_message(f"{len(fatura_listesi)} fatura listelendi. Toplam {self.toplam_kayit_sayisi} kayıt.")
        
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self, "API Bağlantı Hatası", f"Fatura listesi API'den alınamadı:\n{error_detail}")
            self.app.set_status_message(f"Hata: Fatura listesi alınamadı - {error_detail}")
        except Exception as e:
            QMessageBox.critical(self, "Beklenmeyen Hata", f"Fatura listesi yenilenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Fatura listesi yenilenirken hata - {e}")

    def _on_fatura_select(self):
        selected_items = self.fatura_tree.selectedItems()
        is_selected = bool(selected_items)
        self.btn_fatura_detay.setEnabled(is_selected)
        self.btn_fatura_sil.setEnabled(is_selected)
        self.btn_iade_faturasi.setEnabled(is_selected)
        self.btn_fatura_guncelle.setEnabled(is_selected)
        self.btn_fatura_pdf_yazdir.setEnabled(is_selected)

    def secili_fatura_detay_goster(self):
        selected_items = self.fatura_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen detaylarını görmek için bir fatura seçin.")
            return

        selected_item = selected_items[0]
        fatura_id = int(selected_item.data(0, Qt.UserRole)) # Fatura ID'si

        if fatura_id == -1: # Eğer ID placeholder ise
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir fatura seçimi yaptınız.")
             return
        
        # NOT: pencereler.py dosyasındaki FaturaDetayPenceresi'nin PySide6'ya dönüştürülmüş olması gerekmektedir.
        # Bu fonksiyon, FaturaDetayPenceresi'nin PySide6 versiyonu hazır olduğunda aktif olarak çalışacaktır.

        # Geçici olarak, pencereler modülünü bu fonksiyon içinde import edelim
        try:
            from pencereler import FaturaDetayPenceresi # PySide6 FaturaDetayPenceresi varsayılıyor
            
            # Fatura Detay penceresini başlat
            fatura_detay_penceresi = FaturaDetayPenceresi(
                self.app, # Ana uygulama penceresi (parent_app)
                self.db, # Veritabanı yöneticisi
                fatura_id # Fatura ID'si
            )
            # Pencereyi göster
            fatura_detay_penceresi.show()
            self.app.set_status_message(f"Fatura ID: {fatura_id} için detay penceresi açıldı.")

        except ImportError:
            QMessageBox.critical(self, "Hata", "FaturaDetayPenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
            self.app.set_status_message(f"Hata: Fatura Detay penceresi açılamadı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Fatura Detay penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Fatura Detay penceresi açılamadı - {e}")

    def _handle_dropdown_close_events(self, event=None):
        # PySide6'da açılır pencerelerin odak yönetimi farklıdır.
        # Bu metodun içeriği, PySide6'ya dönüştürülmüş açılır pencereler için yeniden yazılacaktır.
        print("Dropdown kapatma olayı (Placeholder)")

    def on_double_click_detay_goster(self, item, column): # item ve column sinyalden gelir
        fatura_id = int(item.text(0)) # ID ilk sütunda
        self.secili_fatura_detay_goster() # Existing method for showing details

    def secili_faturayi_yazdir(self):
        selected_items = self.fatura_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen PDF olarak yazdırmak için bir fatura seçin.")
            return

        selected_item = selected_items[0]
        fatura_id = int(selected_item.data(0, Qt.UserRole)) # Fatura ID'si
        fatura_no = selected_item.text(1) # Fatura Numarası
        fatura_tipi = selected_item.text(4) # Fatura Tipi (SATIŞ, ALIŞ vb.)

        if fatura_id == -1: # Eğer ID placeholder ise
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir fatura seçimi yaptınız.")
             return
        
        # Dosya kaydetme diyaloğunu aç
        # initialFile parametresine fatura tipi ve numarasına göre bir isim önerin
        initial_file_name = f"{fatura_tipi.replace(' ', '')}_Faturasi_{fatura_no.replace('/', '-')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self, 
                                                 "Faturayı PDF olarak kaydet", 
                                                 initial_file_name, 
                                                 "PDF Dosyaları (*.pdf);;Tüm Dosyalar (*)")

        if file_path:
            try:
                # NOT: Şu anda bu işlem API üzerinden yapılmıyor, direkt db.fatura_pdf_olustur çağrılıyor.
                # İleride, fatura_pdf_olustur metodunu çağıran bir API endpoint'i (örn. /faturalar/{id}/pdf) oluşturulabilir.
                success, message = self.db.fatura_pdf_olustur(fatura_id, file_path)

                if success:
                    QMessageBox.information(self, "Başarılı", message)
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self, "Hata", message)
                    self.app.set_status_message(f"PDF yazdırma başarısız: {message}")

            except Exception as e:
                logging.error(f"Faturayı PDF olarak yazdırırken beklenmeyen bir hata oluştu: {e}\n{traceback.format_exc()}")
                QMessageBox.critical(self, "Kritik Hata", f"Faturayı PDF olarak yazdırırken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Hata: PDF yazdırma - {e}")
        else:
            self.app.set_status_message("PDF kaydetme işlemi iptal edildi.")

    def secili_faturayi_sil(self):
        selected_items = self.fatura_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir fatura seçin.")
            return

        selected_item = selected_items[0]
        fatura_id = int(selected_item.data(0, Qt.UserRole)) # Fatura ID'si
        fatura_no = selected_item.text(1) # Fatura Numarası
        fatura_tipi = selected_item.text(4) # Fatura Tipi

        if fatura_id == -1: # Eğer ID placeholder ise
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir fatura seçimi yaptınız.")
             return
        
        reply = QMessageBox.question(self, "Fatura Silme Onayı", 
                                     f"'{fatura_no}' numaralı {fatura_tipi} faturasını silmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No) # Varsayılan "Hayır" olsun
        
        if reply == QMessageBox.Yes:
            try:
                # Fatura silme işlemi için API'ye DELETE isteği gönder
                api_url = f"http://127.0.0.1:8000/faturalar/{fatura_id}"
                response = requests.delete(api_url)
                response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat
                
                QMessageBox.information(self, "Başarılı", f"'{fatura_no}' numaralı fatura başarıyla silindi.")
                self.fatura_listesini_yukle() # Fatura listesini yenile
                self.app.set_status_message(f"'{fatura_no}' numaralı fatura başarıyla silindi.")

                # Stok Yönetimi sayfasını da yenile (fatura silindiğinde stok etkilenir)
                if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, 'stok_listesini_yenile'):
                    self.app.stok_yonetimi_sayfasi.stok_listesini_yenile()
                
                # Kasa/Banka Yönetimi sayfasını da yenile (fatura silindiğinde kasa/banka etkilenir)
                if hasattr(self.app, 'kasa_banka_yonetimi_sayfasi') and hasattr(self.app.kasa_banka_yonetimi_sayfasi, 'hesap_listesini_yenile'):
                    self.app.kasa_banka_yonetimi_sayfasi.hesap_listesini_yenile()

            except requests.exceptions.RequestException as e:
                # API'den gelen hata detayını yakalamaya çalış
                error_detail = str(e)
                if e.response is not None:
                    try:
                        error_detail = e.response.json().get('detail', error_detail)
                    except ValueError: # response.json() başarısız olursa
                        pass
                QMessageBox.critical(self, "Hata", f"Fatura silinirken bir hata oluştu:\n{error_detail}")
                self.app.set_status_message(f"Fatura silme başarısız: {error_detail}")
        else:
            self.app.set_status_message("Fatura silme işlemi kullanıcı tarafından iptal edildi.")

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.fatura_listesini_yukle()
        else:
            self.app.set_status_message("İlk sayfadasınız.")

    def sonraki_sayfa(self):
        # API'den toplam kayıt sayısını almamız gerekiyor.
        # Şimdilik, toplam kayıt sayısını tahmin etmeye veya fatura_listesini_yukle içinde toplam kaydı güncellemeye dayanacağız.
        # Bu kısım, API'ye faturalar için bir 'count' endpoint'i eklendiğinde daha doğru çalışacaktır.

        # Geçici olarak, faturaların toplam sayısını almak için bir API çağrısı simüle edelim
        # VEYA fatura_listesini_yukle metodu içinde toplam_kayit_sayisi'nı güncellemeliyiz
        # varsayalım ki fatura_listesini_yukle metodu self.toplam_kayit_sayisi'nı güncelliyor
        
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0: toplam_sayfa = 1 # En az bir sayfa olsun

        if self.mevcut_sayfa < toplam_sayfa:
            self.mevcut_sayfa += 1
            self.fatura_listesini_yukle()
        else:
            self.app.set_status_message("Son sayfadasınız.")

    def secili_faturayi_guncelle(self):
        selected_items = self.fatura_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek için bir fatura seçin.")
            return

        selected_item = selected_items[0]
        fatura_id = int(selected_item.data(0, Qt.UserRole)) # Fatura ID'si

        if fatura_id == -1: # Eğer ID placeholder ise
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir fatura seçimi yaptınız.")
             return
        
        # NOT: pencereler.py dosyasındaki FaturaGuncellemePenceresi'nin PySide6'ya dönüştürülmüş olması gerekmektedir.
        # Bu fonksiyon, FaturaGuncellemePenceresi'nin PySide6 versiyonu hazır olduğunda aktif olarak çalışacaktır.

        # Geçici olarak, pencereler modülünü bu fonksiyon içinde import edelim
        try:
            from pencereler import FaturaGuncellemePenceresi # PySide6 FaturaGuncellemePenceresi varsayılıyor
            
            # Fatura Güncelleme penceresini başlat
            fatura_guncelle_penceresi = FaturaGuncellemePenceresi(
                self.app, # Ana uygulama penceresi (parent)
                self.db, # Veritabanı yöneticisi
                fatura_id, # Güncellenecek faturanın ID'si
                yenile_callback_liste=self.fatura_listesini_yukle # Pencere kapatıldığında listeyi yenilemek için callback
            )
            # Pencereyi göster
            fatura_guncelle_penceresi.show()
            self.app.set_status_message(f"Fatura ID: {fatura_id} için güncelleme penceresi açıldı.")

        except ImportError:
            QMessageBox.critical(self, "Hata", "FaturaGuncellemePenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
            self.app.set_status_message(f"Hata: Fatura Güncelleme penceresi açılamadı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Fatura Güncelleme penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Fatura Güncelleme penceresi açılamadı - {e}")

class SatisFaturalariListesi(BaseFaturaListesi):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi):
        # super().__init__ çağrısına fatura_tipi parametresini ekliyoruz.
        super().__init__(parent, db_manager, app_ref, fatura_tipi=fatura_tipi)

# arayuz.py içindeki AlisFaturalariListesi sınıfını bu kodla değiştirin
class AlisFaturalariListesi(BaseFaturaListesi):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi):
        # super().__init__ çağrısına fatura_tipi parametresini ekliyoruz.
        super().__init__(parent, db_manager, app_ref, fatura_tipi=fatura_tipi)
        
class TumFaturalarListesi(QWidget): # BaseFaturaListesi'nden değil, QWidget'ten miras alıyor.
    def __init__(self, parent, db_manager, app_ref, fatura_tipi):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.fatura_tipi = fatura_tipi
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(QLabel(f"Tüm Faturalar Listesi ({fatura_tipi}) (Placeholder)"))
        self.fatura_listesini_yukle = lambda: print(f"Tüm Fatura Listesini Yükle ({fatura_tipi}) (Placeholder)") # Yer tutucu

# BaseIslemSayfasi sınıfı (Dönüştürülmüş PySide6 versiyonu)
class BaseIslemSayfasi(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent, db_manager, app_ref, islem_tipi, duzenleme_id=None, yenile_callback=None, initial_cari_id=None, initial_urunler=None, initial_data=None, **kwargs):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.parent = parent 

        self.islem_tipi = islem_tipi
        self.duzenleme_id = duzenleme_id
        self.yenile_callback = yenile_callback

        self.initial_cari_id = initial_cari_id
        self.initial_urunler = initial_urunler
        self.initial_data = initial_data

        # Ortak Değişkenler (PySide6'da doğrudan widget'lardan değer alınacak)
        self.fatura_kalemleri_ui = []
        self.tum_urunler_cache = []
        self.urun_map_filtrelenmis = {}
        self.kasa_banka_map = {}

        self.tum_cariler_cache_data = []
        self.cari_map_display_to_id = {}
        self.cari_id_to_display_map = {}
        self.secili_cari_id = None
        self.secili_cari_adi = None

        self.after_timer = QTimer(self) 
        self.after_timer.setSingleShot(True)

        self.sv_genel_iskonto_degeri = "0,00" # Başlangıç değeri
        self.sv_genel_iskonto_tipi = "YOK" # Başlangıç değeri
        self.form_entries_order = [] # Klavye navigasyonu için liste

        # UI elemanlarının oluşturulması ve düzenlenmesi
        self.main_layout = QVBoxLayout(self) # Ana layout dikey
        self._setup_paneller() # Bu metod alt sınıflar tarafından doldurulacak.

        self._carileri_yukle_ve_cachele() # Cari listesini yükle (ortak)
        self._urunleri_yukle_ve_cachele_ve_goster() # Ürün listesini yükle (ortak)
        self._yukle_kasa_banka_hesaplarini() # Kasa/Banka hesaplarını yükle (ortak)

        self._load_initial_data() # Başlangıç verilerini yükle (ortak)
        self._bind_keyboard_navigation() # Klavye navigasyonunu bağla

    # --- ABSTRACT METHODS (Alt sınıflar tarafından doldurulacak) ---
    def _get_baslik(self):
        raise NotImplementedError("Bu metot alt sınıf tarafından ezilmelidir.")
        
    def _setup_ozel_alanlar(self, parent_frame):
        raise NotImplementedError("Bu metot alt sınıf tarafından ezilmelidir.")

    def _load_initial_data(self):
        """
        Başlangıç verilerini (düzenleme modu, dışarıdan gelen veri veya taslak) forma yükler.
        Bu metod BaseIslemSayfasi'nda genel kontrolü yapar, alt sınıflar kendi spesifik
        doldurma mantıklarını içerebilir.
        """
        if self.duzenleme_id:
            # Alt sınıfın _mevcut_faturayi_yukle veya _mevcut_siparisi_yukle metodunu çağırır.
            pass 
        elif self.initial_data:
            self._load_temp_form_data(forced_temp_data=self.initial_data)
            logging.debug(f"BaseIslemSayfasi - initial_data ile taslak veri yüklendi (islem_tipi: {self.islem_tipi}).")
        elif self.initial_cari_id or self.initial_urunler:
            logging.debug(f"BaseIslemSayfasi - initial_cari_id veya initial_urunler ile başlatıldı. Alt sınıfın doldurma mantığı bekleniyor.")
            # Alt sınıfın _populate_from_initial_data veya _populate_from_initial_data_siparis metodunu çağırır.
            pass
        else:
            if not self._load_temp_form_data():
                # Formu sıfırlama (bu metodun alt sınıflarda uygulanması beklenir)
                self._reset_form_explicitly(ask_confirmation=False) # Varsayılan olarak sormadan sıfırla
                logging.debug(f"BaseIslemSayfasi - Yeni kayıt için form sıfırlandı (islem_tipi: {self.islem_tipi}).")
            else:
                logging.debug(f"BaseIslemSayfasi - Uygulama içi taslak veri yüklendi (islem_tipi: {self.islem_tipi}).")
        
    def kaydet(self):
        """
        Faturayı/Siparişi ve ilişkili kalemlerini kaydeder veya günceller.
        Bu metodun alt sınıflar tarafından override edilmesi beklenir.
        """
        raise NotImplementedError("Bu metot alt sınıf tarafından ezilmelidir.")
        
    def _iptal_et(self):
        """Formu kapatır ve geçici veriyi temizler."""
        reply = QMessageBox.question(self.app, "İptal Onayı", "Sayfadaki tüm bilgileri kaydetmeden kapatmak istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # İptal edildiğinde ilgili taslak verisini temizle (App sınıfında tutuluyorsa)
            if hasattr(self.app, 'temp_sales_invoice_data') and self.islem_tipi == 'SATIŞ': self.app.temp_sales_invoice_data = None
            elif hasattr(self.app, 'temp_purchase_invoice_data') and self.islem_tipi == 'ALIŞ': self.app.temp_purchase_invoice_data = None
            elif hasattr(self.app, 'temp_sales_order_data') and self.islem_tipi == 'SATIŞ_SIPARIS': self.app.temp_sales_order_data = None
            elif hasattr(self.app, 'temp_purchase_order_data') and self.islem_tipi == 'ALIŞ_SIPARIS': self.app.temp_purchase_order_data = None

            self.app.set_status_message(f"{self.islem_tipi} işlemi iptal edildi ve taslak temizlendi.")
            if isinstance(self.parent, QDialog): # Eğer parent bir dialog ise
                 self.parent.reject() # Dialog'u kapat
            elif hasattr(self.parent, 'close'): # Diğer widget türleri için genel kapatma
                self.parent.close()
            else:
                # Eğer parent direkt ana penceredeki bir sekme ise, sadece içeriği temizle.
                # Bu durum, sekmenin kendisini yok etmez, sadece içini sıfırlar.
                logging.warning("BaseIslemSayfasi: _iptal_et metodu parent'ı kapatamadı. Muhtemelen bir sekme.")
                self._reset_form_explicitly(ask_confirmation=False)

    def _reset_form_explicitly(self, ask_confirmation=True):
        """
        Formu tamamen sıfırlar ve temizler, varsayılan değerleri atar.
        Bu metod, formdaki tüm giriş alanlarını temizler, sepeti sıfırlar ve
        alt sınıfların (Fatura/Sipariş) kendi sıfırlama mantıklarını çağırır.
        """
        if ask_confirmation:
            reply = QMessageBox.question(self.app, "Sıfırlama Onayı", "Sayfadaki tüm bilgileri temizlemek istediğinizden emin misiniz?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return False # Sıfırlama iptal edildi

        # Ortak alanları temizle/sıfırla
        self.fatura_kalemleri_ui = [] # Sepeti temizle
        self.sepeti_guncelle_ui() # UI'daki sepeti güncelle
        self.toplamlari_hesapla_ui() # Toplamları sıfırla

        # Formdaki QLineEdit ve QTextEdit'leri temizle
        # hasattr kontrolü, bu widget'ların alt sınıflarda mevcut olup olmadığını kontrol eder.
        if hasattr(self, 'f_no_e'): self.f_no_e.clear()
        if hasattr(self, 'fatura_tarihi_entry'): self.fatura_tarihi_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        if hasattr(self, 'entry_misafir_adi'): self.entry_misafir_adi.clear()
        if hasattr(self, 'fatura_notlari_text'): self.fatura_notlari_text.clear()
        if hasattr(self, 'entry_vade_tarihi'): self.entry_vade_tarihi.clear()
        if hasattr(self, 'genel_iskonto_degeri_e'): self.genel_iskonto_degeri_e.setText("0,00")
        if hasattr(self, 'urun_arama_entry'): self.urun_arama_entry.clear()
        if hasattr(self, 'mik_e'): self.mik_e.setText("1")
        if hasattr(self, 'birim_fiyat_e'): self.birim_fiyat_e.setText("0,00")
        if hasattr(self, 'stk_l'): self.stk_l.setText("-")
        if hasattr(self, 'iskonto_yuzde_1_e'): self.iskonto_yuzde_1_e.setText("0,00")
        if hasattr(self, 'iskonto_yuzde_2_e'): self.iskonto_yuzde_2_e.setText("0,00")
        if hasattr(self, 's_no_e'): self.s_no_e.clear() # Sipariş no
        if hasattr(self, 'siparis_tarihi_entry'): self.siparis_tarihi_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        if hasattr(self, 'teslimat_tarihi_entry'): self.teslimat_tarihi_entry.setText((datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        if hasattr(self, 'siparis_notlari_text'): self.siparis_notlari_text.clear()
        
        # QComboBox'ları varsayılan değerlerine döndür
        if hasattr(self, 'odeme_turu_cb'): self.odeme_turu_cb.setCurrentText(self.db.ODEME_TURU_NAKIT)
        if hasattr(self, 'islem_hesap_cb'): self.islem_hesap_cb.clear() # Temizle
        if hasattr(self, 'genel_iskonto_tipi_cb'): self.genel_iskonto_tipi_cb.setCurrentText("YOK")
        if hasattr(self, 'durum_combo'): self.durum_combo.setCurrentText(self.db.SIPARIS_DURUM_BEKLEMEDE)
        
        # Cari seçimi temizle
        self._temizle_cari_secimi()

        # Alt sınıfa özgü sıfırlama metodunu çağır (eğer tanımlıysa)
        # Bu kısım, FaturaOlusturmaSayfasi ve SiparisOlusturmaSayfasi'ndaki
        # _reset_form_for_new_invoice ve _reset_form_for_new_siparis metotlarını
        # çağırarak varsayılan fatura/sipariş numarası ve cari atamasını yapar.
        if self.islem_tipi == self.db.FATURA_TIP_SATIS or self.islem_tipi == self.db.FATURA_TIP_ALIS:
            # Bu metodun BaseIslemSayfasi'nın alt sınıfında (FaturaOlusturmaSayfasi) tanımlı olması beklenir
            if hasattr(self, '_reset_form_for_new_invoice'):
                self._reset_form_for_new_invoice(ask_confirmation=False, skip_default_cari_selection=True) # Varsayılan cariyi atamadan sıfırla

        elif self.islem_tipi == self.db.SIPARIS_TIP_SATIS or self.islem_tipi == self.db.SIPARIS_TIP_ALIS:
            # Bu metodun BaseIslemSayfasi'nın alt sınıfında (SiparisOlusturmaSayfasi) tanımlı olması beklenir
            if hasattr(self, '_reset_form_for_new_siparis'):
                self._reset_form_for_new_siparis(ask_confirmation=False, skip_default_cari_selection=True) # Varsayılan cariyi atamadan sıfırla

        # Diğer dinamik durumları sıfırla
        if hasattr(self, '_on_genel_iskonto_tipi_changed'): self._on_genel_iskonto_tipi_changed() # Genel iskonto alanını güncelle
        if hasattr(self, '_odeme_turu_degisince_event_handler'): self._odeme_turu_degisince_event_handler() # Ödeme türü bağlı alanları güncelle

        # API'den ürünleri tekrar yükle (önbelleği yenile)
        QTimer.singleShot(0, self._urunleri_yukle_ve_cachele_ve_goster)
        
        self.app.set_status_message("Form başarıyla sıfırlandı.")
        self.urun_arama_entry.setFocus() # Genellikle ilk odaklanılacak alan

        return True # Sıfırlama başarılı

    def _setup_paneller(self):
        # Başlık ve "Sayfayı Yenile" butonu
        header_frame = QFrame(self)
        header_layout = QHBoxLayout(header_frame)
        self.main_layout.addWidget(header_frame)

        baslik_label = QLabel(self._get_baslik())
        baslik_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header_layout.addWidget(baslik_label)

        self.btn_sayfa_yenile = QPushButton("Sayfayı Yenile")
        self.btn_sayfa_yenile.clicked.connect(self._reset_form_explicitly)
        header_layout.addWidget(self.btn_sayfa_yenile)

        content_frame = QFrame(self)
        content_layout = QGridLayout(content_frame)
        self.main_layout.addWidget(content_frame, 1, 0) # Satır 1, Sütun 0
        content_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout.setColumnStretch(0, 1) # Sol panel genişlesin
        content_layout.setColumnStretch(1, 1) # Sağ panel genişlesin
        content_layout.setRowStretch(1, 1)    # Sepet paneli dikeyde genişlesin

        # Sol panel (Genel Bilgiler)
        self._setup_sol_panel(content_frame)

        # Sağ panel (Ürün Ekle)
        self._setup_sag_panel(content_frame)

        # Sepet paneli (Kalemler)
        self._setup_sepet_paneli(content_frame)

        # Alt bar (Toplamlar ve Kaydet butonu)
        self._setup_alt_bar()

        self._bind_keyboard_navigation()

    def _yukle_kasa_banka_hesaplarini(self):
        """Kasa/Banka hesaplarını API'den çeker ve ilgili combobox'ı doldurur."""
        # API'den kasa/banka hesaplarını çek
        try:
            api_url = "http://127.0.0.1:8000/kasalar_bankalar/"
            response = requests.get(api_url)
            response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat
            hesaplar = response.json() # JSON yanıtı al

            self.kasa_banka_combo.clear() # Mevcut öğeleri temizle
            self.kasa_banka_map.clear() # Map'i temizle
            
            display_values = []
            if hesaplar:
                for h in hesaplar: # h: KasaBankaBase Pydantic modeline göre JSON objesi
                    display_text = f"{h.get('hesap_adi')} ({h.get('tip')})"
                    if h.get('tip') == "BANKA" and h.get('banka_adi'): 
                        display_text += f" - {h.get('banka_adi')}"
                    if h.get('tip') == "BANKA" and h.get('hesap_no'): 
                        display_text += f" ({h.get('hesap_no')})"
                    
                    self.kasa_banka_map[display_text] = h.get('id')
                    display_values.append(display_text)
                
                self.kasa_banka_combo.addItems(display_values)
                self.kasa_banka_combo.setCurrentIndex(0) # İlk öğeyi seç
                self.kasa_banka_combo.setEnabled(True) # Aktif yap
            else:
                self.kasa_banka_combo.clear() # Temizle
                self.kasa_banka_combo.setPlaceholderText("Hesap Yok")
                self.kasa_banka_combo.setEnabled(False) # Pasif yap

            self.app.set_status_message(f"{len(hesaplar)} kasa/banka hesabı API'den yüklendi.")

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self.app, "API Bağlantı Hatası", f"Kasa/Banka hesapları API'den alınamadı:\n{error_detail}")
            self.app.set_status_message(f"Hata: Kasa/Banka hesapları yüklenemedi - {error_detail}")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Kasa/Banka hesapları yüklenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Kasa/Banka hesapları yüklenirken hata - {e}")

    def _setup_sol_panel(self, parent):
        # Placeholder
        print("BaseIslemSayfasi: _setup_sol_panel çağrıldı (Placeholder)")
        left_panel_frame = QFrame(parent)
        left_panel_layout = QGridLayout(left_panel_frame)
        parent.layout().addWidget(left_panel_frame, 0, 0, Qt.AlignTop) # QGridLayout'un ilk satırının ilk sütununa yerleşir
        left_panel_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # Sıkıştır

        # Bu metoda özgü widget'ları burada ekleyeceğiz
        # Örneğin:
        # left_panel_layout.addWidget(QLabel("Fatura No:"), 0, 0)
        # self.f_no_e = QLineEdit()
        # left_panel_layout.addWidget(self.f_no_e, 0, 1)
        # _setup_ozel_alanlar metodu tarafından doldurulması beklenir.
        self._setup_ozel_alanlar(left_panel_frame)


    def _setup_sag_panel(self, parent):
        # Sağ panel (Ürün Ekle)
        # print("BaseIslemSayfasi: _setup_sag_panel çağrıldı (Placeholder)") # Bu satırı siliyoruz.
        right_panel_frame = QFrame(parent)
        right_panel_layout = QGridLayout(right_panel_frame)
        parent.layout().addWidget(right_panel_frame, 0, 1, Qt.AlignTop) # QGridLayout'un ilk satırının ikinci sütununa yerleşir
        right_panel_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # Sıkıştır

        # Ürün Arama ve Ekleme alanı
        urun_ekle_groupbox = QFrame(right_panel_frame)
        urun_ekle_layout = QGridLayout(urun_ekle_groupbox)
        right_panel_layout.addWidget(urun_ekle_groupbox, 0, 0)

        urun_ekle_layout.addWidget(QLabel("Ürün Ara (Kod/Ad):"), 0, 0)
        self.urun_arama_entry = QLineEdit()
        self.urun_arama_entry.setPlaceholderText("Ürün Kodu veya Adı ile ara...")
        self.urun_arama_entry.textChanged.connect(self._delayed_stok_yenile) # textChanged sinyali
        urun_ekle_layout.addWidget(self.urun_arama_entry, 0, 1)

        self.urun_arama_sonuclari_tree = QTreeWidget()
        self.urun_arama_sonuclari_tree.setHeaderLabels(["Ürün Adı", "Kod", "Fiyat", "Stok"])
        self.urun_arama_sonuclari_tree.setColumnCount(4)
        self.urun_arama_sonuclari_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.urun_arama_sonuclari_tree.setSortingEnabled(True)
        self.urun_arama_sonuclari_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.urun_arama_sonuclari_tree.itemDoubleClicked.connect(self.kalem_ekle_arama_listesinden) # Çift tıklama
        self.urun_arama_sonuclari_tree.itemSelectionChanged.connect(self.secili_urun_bilgilerini_goster_arama_listesinden)
        urun_ekle_layout.addWidget(self.urun_arama_sonuclari_tree, 1, 0, 1, 2) # Row 1, Col 0, span 1 row, 2 cols

        # Miktar, Birim Fiyat, İskonto vb. girişleri
        alt_urun_ekle_frame = QFrame(urun_ekle_groupbox)
        alt_urun_ekle_layout = QHBoxLayout(alt_urun_ekle_frame)
        urun_ekle_layout.addWidget(alt_urun_ekle_frame, 2, 0, 1, 2) # Row 2, Col 0, span 1 row, 2 cols

        alt_urun_ekle_layout.addWidget(QLabel("Miktar:"))
        self.mik_e = QLineEdit("1")
        self.mik_e.setFixedWidth(50)
        
        # QDoubleValidator ataması (0.0'dan sonsuza, 2 ondalık basamak)
        mik_validator = QDoubleValidator(0.0, 999999999.0, 2, self)
        mik_validator.setNotation(QDoubleValidator.StandardNotation)
        self.mik_e.setValidator(mik_validator)
        # textChanged sinyaline bağlanarak her karakter girişi sonrası formatlama yap
        self.mik_e.textChanged.connect(lambda: self._format_numeric_line_edit(self.mik_e, 2))
        # editingFinished sinyaline bağlanarak odak kaybolduğunda/Enter'a basıldığında da formatlama yap
        self.mik_e.editingFinished.connect(lambda: self._format_numeric_line_edit(self.mik_e, 2))
        
        self.mik_e.returnPressed.connect(self.kalem_ekle_arama_listesinden)
        alt_urun_ekle_layout.addWidget(self.mik_e)

        alt_urun_ekle_layout.addWidget(QLabel("Birim Fiyat (KDV Dahil):"))
        self.birim_fiyat_e = QLineEdit("0,00")
        self.birim_fiyat_e.setFixedWidth(80)
        
        # QDoubleValidator ataması (0.0'dan sonsuza, 2 ondalık basamak)
        birim_fiyat_validator = QDoubleValidator(0.0, 999999999.0, 2, self)
        birim_fiyat_validator.setNotation(QDoubleValidator.StandardNotation)
        self.birim_fiyat_e.setValidator(birim_fiyat_validator)
        self.birim_fiyat_e.textChanged.connect(lambda: self._format_numeric_line_edit(self.birim_fiyat_e, 2))
        self.birim_fiyat_e.editingFinished.connect(lambda: self._format_numeric_line_edit(self.birim_fiyat_e, 2))
        
        alt_urun_ekle_layout.addWidget(self.birim_fiyat_e)

        alt_urun_ekle_layout.addWidget(QLabel("Stok:"))
        self.stk_l = QLabel("-")
        self.stk_l.setFont(QFont("Segoe UI", 12, QFont.Bold))
        alt_urun_ekle_layout.addWidget(self.stk_l)

        alt_urun_ekle_layout.addWidget(QLabel("İsk.1(%):"))
        self.iskonto_yuzde_1_e = QLineEdit("0,00")
        self.iskonto_yuzde_1_e.setFixedWidth(50)
        
        # QDoubleValidator ataması (0.0'dan 100.0'a, 2 ondalık basamak)
        iskonto_validator_1 = QDoubleValidator(0.0, 100.0, 2, self)
        iskonto_validator_1.setNotation(QDoubleValidator.StandardNotation)
        self.iskonto_yuzde_1_e.setValidator(iskonto_validator_1)
        self.iskonto_yuzde_1_e.textChanged.connect(lambda: self._format_numeric_line_edit(self.iskonto_yuzde_1_e, 2))
        self.iskonto_yuzde_1_e.editingFinished.connect(lambda: self._format_numeric_line_edit(self.iskonto_yuzde_1_e, 2))
        
        alt_urun_ekle_layout.addWidget(self.iskonto_yuzde_1_e)

        alt_urun_ekle_layout.addWidget(QLabel("İsk.2(%):"))
        self.iskonto_yuzde_2_e = QLineEdit("0,00")
        self.iskonto_yuzde_2_e.setFixedWidth(50)
        
        # QDoubleValidator ataması (0.0'dan 100.0'a, 2 ondalık basamak)
        iskonto_validator_2 = QDoubleValidator(0.0, 100.0, 2, self)
        iskonto_validator_2.setNotation(QDoubleValidator.StandardNotation)
        self.iskonto_yuzde_2_e.setValidator(iskonto_validator_2)
        self.iskonto_yuzde_2_e.textChanged.connect(lambda: self._format_numeric_line_edit(self.iskonto_yuzde_2_e, 2))
        self.iskonto_yuzde_2_e.editingFinished.connect(lambda: self._format_numeric_line_edit(self.iskonto_yuzde_2_e, 2))
        
        alt_urun_ekle_layout.addWidget(self.iskonto_yuzde_2_e)

        self.btn_sepete_ekle = QPushButton("Sepete Ekle")
        self.btn_sepete_ekle.clicked.connect(self.kalem_ekle_arama_listesinden)
        alt_urun_ekle_layout.addWidget(self.btn_sepete_ekle)

    def _select_product_from_search_list_and_focus_quantity(self, item): # item itemDoubleClicked sinyalinden gelir
        self.secili_urun_bilgilerini_goster_arama_listesinden(item) # Ürün bilgilerini doldur
        self.mik_e.setFocus() # Miktar kutusuna odaklan
        self.mik_e.selectAll() # Metni seçili yap

    def _setup_sepet_paneli(self, parent):
        # Sepet paneli (Kalemler)
        sep_f = QFrame(parent)
        sep_layout = QGridLayout(sep_f)
        parent.layout().addWidget(sep_f, 1, 0, 1, 2) # Satır 1, Sütun 0, 1 satır, 2 sütun kapla
        sep_f.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols_s = ("#", "Ürün Adı", "Mik.", "B.Fiyat", "KDV%", "İskonto 1 (%)", "İskonto 2 (%)", "Uyg. İsk. Tutarı", "Tutar(Dah.)", "Fiyat Geçmişi", "Ürün ID")
        self.sep_tree = QTreeWidget(sep_f)
        self.sep_tree.setHeaderLabels(cols_s)
        self.sep_tree.setColumnCount(len(cols_s))
        self.sep_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sep_tree.setSortingEnabled(True)
        self.sep_tree.header().setStretchLastSection(False)
        self.sep_tree.header().setSectionResizeMode(1, QHeaderView.Stretch) # Ürün Adı genişlesin

        sep_layout.addWidget(self.sep_tree, 0, 0, 1, 2) # Row 0, Col 0, span 1 row, 2 cols

        self.sep_tree.itemDoubleClicked.connect(self._kalem_duzenle_penceresi_ac)
        # Sağ tık menüsü için policy ayarlanmalı
        self.sep_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sep_tree.customContextMenuRequested.connect(self._open_sepet_context_menu) # Sağ tık menüsü için

        btn_s_f = QFrame(sep_f)
        btn_s_f_layout = QHBoxLayout(btn_s_f)
        sep_layout.addWidget(btn_s_f, 1, 0, 1, 2) # Row 1, Col 0, span 1 row, 2 cols

        secili_kalemi_sil_button = QPushButton("Seçili Kalemi Sil")
        secili_kalemi_sil_button.clicked.connect(self.secili_kalemi_sil)
        btn_s_f_layout.addWidget(secili_kalemi_sil_button)

        sepeti_temizle_button = QPushButton("Tüm Kalemleri Sil")
        sepeti_temizle_button.clicked.connect(self.sepeti_temizle)
        btn_s_f_layout.addWidget(sepeti_temizle_button)

    def _setup_alt_bar(self):
        # Alt bar (Toplamlar ve Kaydet butonu)
        alt_f = QFrame(self)
        alt_layout = QGridLayout(alt_f)
        self.main_layout.addWidget(alt_f, 2, 0) # Satır 2, Sütun 0
        alt_f.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        font_t = QFont("Segoe UI", 10, QFont.Bold)
        self.tkh_l = QLabel("KDV Hariç Toplam: 0.00 TL")
        self.tkh_l.setFont(font_t)
        alt_layout.addWidget(self.tkh_l, 0, 0, Qt.AlignLeft)

        self.tkdv_l = QLabel("Toplam KDV: 0.00 TL")
        self.tkdv_l.setFont(font_t)
        alt_layout.addWidget(self.tkdv_l, 0, 1, Qt.AlignLeft)

        self.gt_l = QLabel("Genel Toplam: 0.00 TL")
        self.gt_l.setFont(QFont("Segoe UI", 12, QFont.Bold))
        alt_layout.addWidget(self.gt_l, 0, 2, Qt.AlignLeft)

        self.lbl_uygulanan_genel_iskonto = QLabel("Uygulanan Genel İskonto: 0.00 TL")
        self.lbl_uygulanan_genel_iskonto.setFont(font_t)
        alt_layout.addWidget(self.lbl_uygulanan_genel_iskonto, 1, 0, Qt.AlignLeft)

        self.kaydet_buton = QPushButton("Kaydet")
        self.kaydet_buton.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.kaydet_buton.setStyleSheet("padding: 5px 10px;")
        self.kaydet_buton.clicked.connect(self.kaydet)
        alt_layout.addWidget(self.kaydet_buton, 0, 3, 2, 1, Qt.AlignRight) # Row 0, Col 3, span 2 rows, 1 col, Right

    def _open_sepet_context_menu(self, pos): # pos parametresi customContextMenuRequested sinyalinden gelir

        item = self.sep_tree.itemAt(pos) # Tıklanan öğeyi al
        if not item:
            return

        self.sep_tree.setCurrentItem(item) # Tıklanan öğeyi seçili yap

        context_menu = QMenu(self) # Yeni QMenu objesi oluştur

        # Komutları menüye ekleyin
        edit_action = context_menu.addAction("Kalemi Düzenle")
        edit_action.triggered.connect(lambda: self._kalem_duzenle_penceresi_ac(item, None)) # item'ı direkt gönder

        delete_action = context_menu.addAction("Seçili Kalemi Sil")
        delete_action.triggered.connect(self.secili_kalemi_sil)

        history_action = context_menu.addAction("Fiyat Geçmişi")
        history_action.triggered.connect(lambda: self._on_sepet_kalem_click(item, self.sep_tree.columnCount() - 1)) # Fiyat geçmişi sütunu index'i

        # Menüyü göster
        context_menu.exec(self.sep_tree.mapToGlobal(pos)) # Menüyü global koordinatlarda göster

    def _open_urun_arama_context_menu(self, pos): # pos parametresi customContextMenuRequested sinyalinden gelir
        item = self.urun_arama_sonuclari_tree.itemAt(pos)
        if not item:
            return

        self.urun_arama_sonuclari_tree.setCurrentItem(item)

        context_menu = QMenu(self)

        open_product_card_action = context_menu.addAction("Ürün Kartını Aç")
        open_product_card_action.triggered.connect(lambda: self._open_urun_karti_from_search(item, None)) # item'ı direkt gönder

        context_menu.exec(self.urun_arama_sonuclari_tree.mapToGlobal(pos))

    # --- ORTAK METOTLAR ---
    def _on_genel_iskonto_tipi_changed(self): # event=None kaldırıldı
        selected_type = self.genel_iskonto_tipi_cb.currentText() # QComboBox'tan metin al
        if selected_type == "YOK":
            self.genel_iskonto_degeri_e.setEnabled(False)
            self.genel_iskonto_degeri_e.setText("0,00")
        else:
            self.genel_iskonto_degeri_e.setEnabled(True)
        self.toplamlari_hesapla_ui()

    def _carileri_yukle_ve_cachele(self):
        logging.debug(f"BaseIslemSayfasi: _carileri_yukle_ve_cachele çağrıldı. self.islem_tipi: {self.islem_tipi}")

        self.tum_cariler_cache_data = []
        self.cari_map_display_to_id = {}
        self.cari_id_to_display_map = {}
        
        if self.islem_tipi in ['SATIŞ', 'SATIŞ_SIPARIS', 'SATIŞ İADE']:
            cariler_db = self.db.musteri_listesi_al(perakende_haric=False) 
            kod_anahtari_db = 'kod' 
        elif self.islem_tipi in ['ALIŞ', 'ALIŞ_SIPARIS', 'ALIŞ İADE']:
            cariler_db = self.db.tedarikci_listesi_al()
            kod_anahtari_db = 'tedarikci_kodu' 
        else:
            cariler_db = []
            kod_anahtari_db = '' 

        for c in cariler_db: # c: sqlite3.Row objesi
            cari_id = c['id']
            cari_ad = c['ad']
            
            cari_kodu_gosterim = c[kod_anahtari_db] if kod_anahtari_db in c else ''
            
            display_text = f"{cari_ad} (Kod: {cari_kodu_gosterim})" 
            self.cari_map_display_to_id[display_text] = str(cari_id)
            self.cari_id_to_display_map[str(cari_id)] = display_text
            self.tum_cariler_cache_data.append(c)

        logging.debug(f"BaseIslemSayfasi: _carileri_yukle_ve_cachele bitiş. Yüklenen cari sayısı: {len(self.tum_cariler_cache_data)}")
        
    def _cari_secim_penceresi_ac(self):
        # NOT: pencereler.py dosyasındaki CariSecimPenceresi ve TedarikciSecimDialog'un PySide6'ya dönüştürülmüş olması gerekmektedir.
        # Bu fonksiyon, ilgili PySide6 versiyonları hazır olduğunda aktif olarak çalışacaktır.

        # Geçici olarak, pencereler modülünü bu fonksiyon içinde import edelim
        try:
            # Fatura veya Sipariş işlem tipine göre doğru cari tipi belirle
            if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.SIPARIS_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE]:
                cari_tipi_for_selection = 'SATIŞ' # Müşteri seçimi için
            elif self.islem_tipi in [self.db.FATURA_TIP_ALIS, self.db.SIPARIS_TIP_ALIS, self.db.FATURA_TIP_ALIS_IADE]:
                cari_tipi_for_selection = 'ALIŞ' # Tedarikçi seçimi için
            else:
                QMessageBox.critical(self.app, "Hata", "Geçersiz işlem tipi için cari seçimi yapılamaz.")
                self.app.set_status_message("Hata: Geçersiz işlem tipi.")
                return

            # CariSecimPenceresi (PySide6 versiyonu varsayılıyor)
            # Bu pencere, hem müşteri hem de tedarikçi seçimi için kullanılabilir
            from pencereler import CariSecimPenceresi 
            
            # Cari Seçim penceresini başlat
            cari_secim_penceresi = CariSecimPenceresi(
                self.app, # Ana uygulama penceresi (parent_window)
                self.db, # Veritabanı yöneticisi
                cari_tipi_for_selection, # 'SATIŞ' veya 'ALIŞ' olarak gönderilir
                self._on_cari_secildi_callback # Seçim sonrası çağrılacak callback
            )
            # Pencereyi göster
            cari_secim_penceresi.show()
            self.app.set_status_message(f"{cari_tipi_for_selection.lower()} cari seçimi penceresi açıldı.")

        except ImportError:
            QMessageBox.critical(self.app, "Hata", "CariSecimPenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
            self.app.set_status_message("Hata: Cari Seçim penceresi açılamadı.")
        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Cari Seçim penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Cari Seçim penceresi açılamadı - {e}")

    def _on_cari_secildi_callback(self, selected_cari_id, selected_cari_display_text):
        self.secili_cari_id = selected_cari_id 
        self.secili_cari_adi = selected_cari_display_text 
        self.lbl_secili_cari_adi.setText(f"Seçilen Cari: {self.secili_cari_adi}")
        self._on_cari_selected()

    def _on_cari_selected(self): # event=None kaldırıldı
        bakiye_text = ""
        bakiye_color = "black"
        if self.secili_cari_id:
            cari_id = int(self.secili_cari_id)
            if self.islem_tipi in ['SATIŞ', 'SATIŞ_SIPARIS']:
                net_bakiye = self.db.get_musteri_net_bakiye(cari_id)
                if net_bakiye > 0: bakiye_text, bakiye_color = f"Borç: {self.db._format_currency(net_bakiye)}", "red"
                elif net_bakiye < 0: bakiye_text, bakiye_color = f"Alacak: {self.db._format_currency(abs(net_bakiye))}", "green"
                else: bakiye_text = "Bakiye: 0,00 TL"
            elif self.islem_tipi in ['ALIŞ', 'ALIŞ_SIPARIS']:
                net_bakiye = self.db.get_tedarikci_net_bakiye(cari_id)
                if net_bakiye > 0: bakiye_text, bakiye_color = f"Borç: {self.db._format_currency(net_bakiye)}", "red"
                elif net_bakiye < 0: bakiye_text, bakiye_color = f"Alacak: {self.db._format_currency(abs(net_bakiye))}", "green"
                else: bakiye_text = "Bakiye: 0,00 TL"
            self.lbl_cari_bakiye.setText(bakiye_text)
            self.lbl_cari_bakiye.setStyleSheet(f"color: {bakiye_color};")
        else:
            self.lbl_cari_bakiye.setText("")
            self.lbl_cari_bakiye.setStyleSheet("color: black;")

        if hasattr(self, '_odeme_turu_ve_misafir_adi_kontrol'):
            self._odeme_turu_ve_misafir_adi_kontrol()

    def _temizle_cari_secimi(self):
        self.secili_cari_id = None
        self.secili_cari_adi = None
        if hasattr(self, 'lbl_secili_cari_adi'):
            self.lbl_secili_cari_adi.setText("Seçilen Cari: Yok")
        if hasattr(self, 'lbl_cari_bakiye'):
            self.lbl_cari_bakiye.setText("")
            self.lbl_cari_bakiye.setStyleSheet("color: black;")

    def _urunleri_yukle_ve_cachele_ve_goster(self):
        # NOT: Bu fonksiyon, API'deki /stoklar/ endpoint'inden verileri çekecektir.
        # Bu fonksiyonun doğru çalışabilmesi için stoklar.py'deki /stoklar GET endpoint'inin
        # fatura tipi filtresi alacak şekilde genişletilmesi gerekebilir.
        # Şu anki API'de 'arama_terimi', 'kategori_id', 'marka_id' var, 'fatura_tipi' yok.

        # Stok listesini API'den çekmek için kullanılacak parametreleri belirle
        params = {
            'limit': 500, # Geniş bir limit koyalım, arama filtresi UI'da yapılacak
            'skip': 0
        }

        # Hangi fatura tipine göre stok listesi çekileceğini belirle (API'ye filtre olarak gönderilirse)
        # Bu filtre API tarafında uygulanmalıdır. Eğer API desteklemiyorsa, tüm stoklar çekilir ve UI'da filtreleme yapılır.
        # Mevcut API'de böyle bir filtre olmadığı için şimdilik göndermiyoruz.
        # if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.SIPARIS_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE]:
        #     params['fatura_tipi'] = 'SATIŞ' # API'ye özel bir fatura tipi filtresi olarak gönderilebilir
        # elif self.islem_tipi in [self.db.FATURA_TIP_ALIS, self.db.SIPARIS_TIP_ALIS, self.db.FATURA_TIP_ALIS_IADE]:
        #     params['fatura_tipi'] = 'ALIŞ' # API'ye özel bir fatura tipi filtresi olarak gönderilebilir

        try:
            api_url = "http://127.0.0.1:8000/stoklar/"
            response = requests.get(api_url, params=params)
            response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat
            
            self.tum_urunler_cache = response.json() # Tüm ürünleri cache'e al

            self._urun_listesini_filtrele_anlik() # UI'daki arama kutusuna göre listeyi filtrele ve göster
            self.app.set_status_message(f"{len(self.tum_urunler_cache)} ürün API'den önbelleğe alındı.")

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self.app, "API Bağlantı Hatası", f"Ürün listesi API'den alınamadı:\n{error_detail}")
            self.app.set_status_message(f"Hata: Ürün listesi önbelleğe alınamadı - {error_detail}")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Ürün listesi yüklenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Ürün listesi yüklenirken hata - {e}")

    def _urun_listesini_filtrele_anlik(self): # event=None kaldırıldı
        arama_terimi = self.urun_arama_entry.text().lower().strip()
        self.urun_arama_sonuclari_tree.clear() # QTreeWidget'ı temizle

        self.urun_map_filtrelenmis.clear()
        filtered_items_iids = []

        for urun_item in self.tum_urunler_cache:
            urun_id = urun_item['id'] # Dictionary olarak erişim
            urun_kodu_db = urun_item['urun_kodu']
            urun_adi_db = urun_item['urun_adi']
            fiyat_to_display = urun_item['fiyat'] # satis_fiyati_kdv_dahil veya alis_fiyati_kdv_dahil
            kdv_db = urun_item['kdv_orani']
            stok_db = urun_item['stok_miktari']

            if (not arama_terimi or
                (urun_adi_db and arama_terimi in urun_adi_db.lower()) or
                (urun_kodu_db and arama_terimi in urun_kodu_db.lower())):

                item_iid = f"search_{urun_id}"
                
                item_qt = QTreeWidgetItem(self.urun_arama_sonuclari_tree)
                item_qt.setText(0, urun_kodu_db) # Kod
                item_qt.setText(1, urun_adi_db) # Ürün Adı
                item_qt.setText(2, self.db._format_currency(fiyat_to_display)) # Fiyat
                item_qt.setText(3, f"{stok_db:.2f}".rstrip('0').rstrip('.')) # Stok

                # Sayısal sütunlar için sıralama anahtarları
                item_qt.setData(0, Qt.UserRole, urun_kodu_db) # Koda göre sıralama
                item_qt.setData(2, Qt.UserRole, fiyat_to_display) # Fiyata göre sıralama
                item_qt.setData(3, Qt.UserRole, stok_db) # Stoğa göre sıralama

                self.urun_map_filtrelenmis[item_iid] = {"id": urun_id, "kod": urun_kodu_db, "ad": urun_adi_db, "fiyat": fiyat_to_display, "kdv": kdv_db, "stok": stok_db}
                filtered_items_iids.append(item_iid)

        # Eğer filtreleme sonrası sadece bir ürün kalmışsa, o ürünü otomatik seç ve odakla
        if len(filtered_items_iids) == 1:
            self.urun_arama_sonuclari_tree.setCurrentItem(self.urun_arama_sonuclari_tree.topLevelItem(0))
            self.urun_arama_sonuclari_tree.setFocus()

        self.secili_urun_bilgilerini_goster_arama_listesinden(None) # Seçimi güncelle (item=None geçerli)

    def secili_urun_bilgilerini_goster_arama_listesinden(self, item): # item itemSelectionChanged sinyalinden gelir
        selected_items = self.urun_arama_sonuclari_tree.selectedItems()
        if selected_items and len(selected_items) > 0:
            item_qt = selected_items[0]
            item_iid_arama = f"search_{item_qt.data(0, Qt.UserRole).replace('search_', '')}" # ID'yi al
            
            if item_iid_arama in self.urun_map_filtrelenmis:
                urun_detaylari = self.urun_map_filtrelenmis[item_iid_arama]
                birim_fiyat_to_fill = urun_detaylari.get('fiyat', 0.0) 
                self.birim_fiyat_e.setText(f"{birim_fiyat_to_fill:.2f}".replace('.',','))
                self.stk_l.setText(f"{urun_detaylari['stok']:.2f}".rstrip('0').rstrip('.'))
                self.stk_l.setStyleSheet("color: black;")
                self._check_stock_on_quantity_change()
            else:
                self.birim_fiyat_e.setText("0,00")
                self.stk_l.setText("-")
                self.stk_l.setStyleSheet("color: black;")
        else:
            self.birim_fiyat_e.setText("0,00")
            self.stk_l.setText("-")
            self.stk_l.setStyleSheet("color: black;")


    def kalem_ekle_arama_listesinden(self): # event=None kaldırıldı
        selected_items = self.urun_arama_sonuclari_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Geçersiz Ürün", "Lütfen arama listesinden geçerli bir ürün seçin.")
            return

        item_qt = selected_items[0]
        item_iid_arama = f"search_{item_qt.data(0, Qt.UserRole).replace('search_', '')}" # ID'yi al
        
        if item_iid_arama not in self.urun_map_filtrelenmis: # Ek bir kontrol
             QMessageBox.warning(self.app, "Geçersiz Ürün", "Seçili ürün detayları bulunamadı.")
             return

        urun_detaylari = self.urun_map_filtrelenmis[item_iid_arama]
        u_id = urun_detaylari["id"]
        
        eklenecek_miktar = float(self.mik_e.text().replace(',', '.'))
        if eklenecek_miktar <= 0:
            QMessageBox.critical(self.app, "Geçersiz Miktar", "Miktar pozitif bir değer olmalıdır.")
            return

        existing_kalem_index = -1
        for i, kalem in enumerate(self.fatura_kalemleri_ui):
            if kalem[0] == u_id:
                existing_kalem_index = i
                break
            
        istenen_toplam_miktar_sepette = eklenecek_miktar
        if existing_kalem_index != -1:
            eski_miktar = float(self.fatura_kalemleri_ui[existing_kalem_index][2])
            istenen_toplam_miktar_sepette = eski_miktar + eklenecek_miktar
            
        if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.SIPARIS_TIP_SATIS, self.db.FATURA_TIP_ALIS_IADE]:
            urun_db_info = self.db.stok_getir_by_id(u_id)
            mevcut_stok = urun_db_info['stok_miktari'] if urun_db_info else 0.0
            
            orijinal_fatura_kalem_miktari = 0
            if self.duzenleme_id:
                original_items_on_invoice = self.db.fatura_detay_al(self.duzenleme_id)
                for item in original_items_on_invoice:
                    if item['urun_id'] == u_id:
                        orijinal_fatura_kalem_miktari = item['miktar']
                        break
            
            kullanilabilir_stok = mevcut_stok + orijinal_fatura_kalem_miktari

            if istenen_toplam_miktar_sepette > kullanilabilir_stok:
                reply = QMessageBox.question(self.app, "Stok Uyarısı", 
                                             f"'{urun_detaylari['ad']}' için stok yetersiz!\n\n"
                                             f"Kullanılabilir Stok: {kullanilabilir_stok:.2f} adet\n"
                                             f"Talep Edilen Toplam Miktar: {istenen_toplam_miktar_sepette:.2f} adet\n\n"
                                             f"Bu işlem negatif stok yaratacaktır. Devam etmek istiyor musunuz?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No: return

        b_f_kdv_dahil_orijinal = urun_detaylari.get('fiyat', 0.0)
        yeni_iskonto_1 = float(self.iskonto_yuzde_1_e.text().replace(',', '.'))
        yeni_iskonto_2 = float(self.iskonto_yuzde_2_e.text().replace(',', '.'))
        
        urun_tam_detay = self.db.stok_getir_by_id(u_id)
        alis_fiyati_fatura_aninda = urun_tam_detay['alis_fiyati_kdv_dahil'] if urun_tam_detay else 0.0

        if existing_kalem_index != -1:
            self.kalem_guncelle(existing_kalem_index, istenen_toplam_miktar_sepette, b_f_kdv_dahil_orijinal, yeni_iskonto_1, yeni_iskonto_2, alis_fiyati_fatura_aninda)
        else:
            self.kalem_guncelle(None, eklenecek_miktar, b_f_kdv_dahil_orijinal, yeni_iskonto_1, yeni_iskonto_2, alis_fiyati_fatura_aninda, u_id=u_id, urun_adi=urun_detaylari["ad"])

        # Sepete ekledikten sonra arama kutusunu ve miktar kutusunu sıfırlayıp odaklanmayı arama kutusuna verin.
        self.mik_e.setText("1")
        self.iskonto_yuzde_1_e.setText("0,00") 
        self.iskonto_yuzde_2_e.setText("0,00")
        self.birim_fiyat_e.setText("0,00") 
        self.stk_l.setText("-")
        self.stk_l.setStyleSheet("color: black;") 

        self.urun_arama_entry.clear()
        self._urun_listesini_filtrele_anlik() # Arama listesini temizleyip yenileyin
        self.urun_arama_entry.setFocus() # Odaklan
        
    def kalem_guncelle(self, kalem_index, yeni_miktar, yeni_fiyat_kdv_dahil_orijinal, yeni_iskonto_yuzde_1, yeni_iskonto_yuzde_2, yeni_alis_fiyati_fatura_aninda, u_id=None, urun_adi=None):
        """
        Sepetteki bir kalemi günceller (veya yeni ekler).
        Tüm finansal hesaplamaları (KDV hariç fiyat, KDV tutarı, toplamlar, iskontolar) yeniden yapar.
        
        Args:
            kalem_index (int/None): Sepetteki kalemin indeksi. None ise yeni kalemdir.
            yeni_miktar (float): Kalemin yeni miktarı.
            yeni_fiyat_kdv_dahil_orijinal (float): Ürünün KDV dahil, iskonto uygulanmamış orijinal birim fiyatı.
            yeni_iskonto_yuzde_1 (float): Birinci iskonto yüzdesi.
            yeni_iskonto_yuzde_2 (float): İkinci iskonto yüzdesi.
            yeni_alis_fiyati_fatura_aninda (float): Fatura/sipariş anındaki alış fiyatı (KDV Dahil).
            u_id (int, optional): Yeni kalem için ürün ID'si.
            urun_adi (str, optional): Yeni kalem için ürün adı.
        """
        # Eğer varolan bir kalem güncelleniyorsa, mevcut verilerini al.
        # Yeni bir kalem ekleniyorsa, urun_id ve urun_adi zorunludur ve diğerleri varsayılan değerlerle başlar.
        
        if kalem_index is not None:
            # Varolan kalemin kopyasını al (tuple'lar immutable olduğu için listeye çevir)
            item_to_update = list(self.fatura_kalemleri_ui[kalem_index])
            # urun_adi ve u_id zaten mevcut olduğu varsayılır.
            urun_id_current = item_to_update[0]
            kdv_orani_current = item_to_update[4] # Mevcut KDV oranını koru
        else:
            # Yeni kalem ekleniyor, u_id ve urun_adi zorunlu
            if u_id is None or urun_adi is None:
                print("HATA: Yeni kalem eklenirken urun_id veya urun_adi eksik.")
                return
            # Yeni bir kalem oluştururken gerekli tüm placeholder'ları sağla
            urun_detaylari_db = self.db.stok_getir_by_id(u_id)
            if not urun_detaylari_db:
                print(f"HATA: Ürün ID {u_id} için detay bulunamadı, kalem eklenemiyor.")
                return

            kdv_orani_current = urun_detaylari_db['kdv_orani'] # Yeni kalem için KDV oranını DB'den al
            
            # Yeni kalem tuple'ının formatı: (id, ad, miktar, birim_fiyat_kdv_haric, kdv_orani, kdv_tutari, kalem_toplam_kdv_haric, kalem_toplam_kdv_dahil, alis_fiyati_fatura_aninda, kdv_orani_fatura_aninda, iskonto_yuzde_1, iskonto_yuzde_2, iskonto_tipi, iskonto_degeri, iskontolu_birim_fiyat_kdv_dahil)
            # 15 elemanlı bir liste oluşturuyoruz (sıralama önemli!)
            item_to_update = [
                u_id, urun_adi, 0.0, # 0:urun_id, 1:urun_adi, 2:miktar (şimdilik 0.0)
                0.0, kdv_orani_current, # 3:birim_fiyat_kdv_haric (şimdilik 0.0), 4:kdv_orani
                0.0, 0.0, 0.0, # 5:kdv_tutari, 6:kalem_toplam_kdv_haric, 7:kalem_toplam_kdv_dahil (şimdilik 0.0)
                0.0, kdv_orani_current, # 8:alis_fiyati_fatura_aninda (şimdilik 0.0), 9:kdv_orani_fatura_aninda (DB'den alınan)
                0.0, 0.0, # 10:iskonto_yuzde_1, 11:iskonto_yuzde_2 (şimdilik 0.0)
                "YOK", 0.0, # 12:iskonto_tipi, 13:iskonto_degeri (şimdilik 0.0)
                0.0 # 14:iskontolu_birim_fiyat_kdv_dahil (şimdilik 0.0)
            ]
            urun_id_current = u_id # Yeni kalem için urun_id_current'i ayarla

        # Yeni miktar ve iskonto yüzdelerini ata
        item_to_update[2] = yeni_miktar # miktar (index 2)
        item_to_update[10] = yeni_iskonto_yuzde_1 # iskonto_yuzde_1 (index 10)
        item_to_update[11] = yeni_iskonto_yuzde_2 # iskonto_yuzde_2 (index 11)
        item_to_update[8] = yeni_alis_fiyati_fatura_aninda # alis_fiyati_fatura_aninda (index 8)

        # KDV oranını teyit et (varsa yeni fiyattan çıkarırız)
        # yeni_fiyat_kdv_dahil_orijinal, iskonto uygulanmamış KDV dahil fiyattır.
        # Bu fiyatı kullanarak KDV hariç orijinal fiyatı hesapla
        if kdv_orani_current == 0:
            original_birim_fiyat_kdv_haric_calc = yeni_fiyat_kdv_dahil_orijinal
        else:
            original_birim_fiyat_kdv_haric_calc = yeni_fiyat_kdv_dahil_orijinal / (1 + kdv_orani_current / 100)
        
        item_to_update[3] = original_birim_fiyat_kdv_haric_calc # birim_fiyat_kdv_haric (index 3)


        # Ardışık iskonto sonrası birim fiyatı KDV dahil hesapla
        fiyat_iskonto_1_sonrasi_dahil = yeni_fiyat_kdv_dahil_orijinal * (1 - yeni_iskonto_yuzde_1 / 100)
        iskontolu_birim_fiyat_kdv_dahil = fiyat_iskonto_1_sonrasi_dahil * (1 - yeni_iskonto_yuzde_2 / 100)
        
        if iskontolu_birim_fiyat_kdv_dahil < 0: # Negatif fiyata düşerse 0 yap
            iskontolu_birim_fiyat_kdv_dahil = 0.0

        item_to_update[14] = iskontolu_birim_fiyat_kdv_dahil # iskontolu_birim_fiyat_kdv_dahil (index 14)


        # KDV Hariç İskontolu Birim Fiyatı
        if kdv_orani_current == 0:
            iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil
        else:
            iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil / (1 + kdv_orani_current / 100)

        # KDV Tutarı, Kalem Toplam KDV Hariç ve Kalem Toplam KDV Dahil hesapla
        item_to_update[5] = (iskontolu_birim_fiyat_kdv_dahil - iskontolu_birim_fiyat_kdv_haric) * yeni_miktar # kdv_tutari (index 5)
        item_to_update[6] = iskontolu_birim_fiyat_kdv_haric * yeni_miktar # kalem_toplam_kdv_haric (index 6)
        item_to_update[7] = iskontolu_birim_fiyat_kdv_dahil * yeni_miktar # kalem_toplam_kdv_dahil (index 7)

        # Listeyi güncelle veya yeni kalem olarak ekle
        if kalem_index is not None:
            self.fatura_kalemleri_ui[kalem_index] = tuple(item_to_update)
        else:
            self.fatura_kalemleri_ui.append(tuple(item_to_update))

        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()


    def sepeti_guncelle_ui(self):
        """Sepetteki ürünleri QTreeWidget'a yükler."""
        if not hasattr(self, 'sep_tree'):
            print("DEBUG: sepeti_guncelle_ui: sep_tree henüz tanımlanmadı.")
            return

        self.sep_tree.clear() # QTreeWidget'ı temizle

        for i, k in enumerate(self.fatura_kalemleri_ui):
            # Değerleri alırken önce safe_float ile sayıya çevir
            miktar_f = self.db.safe_float(k[2])
            birim_fiyat_gosterim_f = self.db.safe_float(k[14])
            original_bf_haric_f = self.db.safe_float(k[3])
            kdv_orani_f = self.db.safe_float(k[4])
            iskonto_yuzde_1_f = self.db.safe_float(k[10])
            iskonto_yuzde_2_f = self.db.safe_float(k[11])
            kalem_toplam_dahil_f = self.db.safe_float(k[7])
            
            # Hesaplamaları yap
            miktar_gosterim = f"{miktar_f:.2f}".rstrip('0').rstrip('.')
            original_bf_dahil = original_bf_haric_f * (1 + kdv_orani_f / 100)
            uygulanan_iskonto = (original_bf_dahil - birim_fiyat_gosterim_f) * miktar_f

            # QTreeWidget'a ekle
            item_qt = QTreeWidgetItem(self.sep_tree)
            item_qt.setText(0, str(i + 1)) # # Sıra numarası
            item_qt.setText(1, k[1]) # Ürün Adı
            item_qt.setText(2, miktar_gosterim) # Mik.
            item_qt.setText(3, self.db._format_currency(birim_fiyat_gosterim_f)) # B.Fiyat
            item_qt.setText(4, f"%{kdv_orani_f:.0f}") # KDV%
            item_qt.setText(5, f"{iskonto_yuzde_1_f:.2f}".replace('.',',')) # İskonto 1 (%)
            item_qt.setText(6, f"{iskonto_yuzde_2_f:.2f}".replace('.',',')) # İskonto 2 (%)
            item_qt.setText(7, self.db._format_currency(uygulanan_iskonto)) # Uyg. İsk. Tutarı
            item_qt.setText(8, self.db._format_currency(kalem_toplam_dahil_f)) # Tutar(Dah.)
            item_qt.setText(9, "Geçmişi Gör") # Fiyat Geçmişi (QPushButton yerine metin)
            item_qt.setText(10, str(k[0])) # Ürün ID (gizli sütun)

            # Sayısal sütunlar için sıralama anahtarları
            item_qt.setData(2, Qt.UserRole, miktar_f)
            item_qt.setData(3, Qt.UserRole, birim_fiyat_gosterim_f)
            item_qt.setData(4, Qt.UserRole, kdv_orani_f)
            item_qt.setData(5, Qt.UserRole, iskonto_yuzde_1_f)
            item_qt.setData(6, Qt.UserRole, iskonto_yuzde_2_f)
            item_qt.setData(7, Qt.UserRole, uygulanan_iskonto)
            item_qt.setData(8, Qt.UserRole, kalem_toplam_dahil_f)
            item_qt.setData(10, Qt.UserRole, k[0]) # Ürün ID

        self.toplamlari_hesapla_ui()

    def toplamlari_hesapla_ui(self): # event=None kaldırıldı
        """Sipariş/Fatura kalemlerinin toplamlarını hesaplar ve UI'daki etiketleri günceller."""
        if not hasattr(self, 'tkh_l'): # QLabel objelerinin varlığını kontrol et
            print("DEBUG: toplamlari_hesapla_ui: UI etiketleri veya temel değişkenler henüz tanımlanmadı.")
            return 

        toplam_kdv_haric_kalemler = sum(k[6] for k in self.fatura_kalemleri_ui)
        toplam_kdv_dahil_kalemler = sum(k[7] for k in self.fatura_kalemleri_ui)
        toplam_kdv_kalemler = sum(k[5] for k in self.fatura_kalemleri_ui)

        genel_iskonto_tipi = self.genel_iskonto_tipi_cb.currentText() # QComboBox'tan al
        genel_iskonto_degeri = float(self.genel_iskonto_degeri_e.text().replace(',', '.')) # QLineEdit'ten al
        uygulanan_genel_iskonto_tutari = 0.0

        if genel_iskonto_tipi == 'YUZDE' and genel_iskonto_degeri > 0:
            uygulanan_genel_iskonto_tutari = toplam_kdv_haric_kalemler * (genel_iskonto_degeri / 100)
        elif genel_iskonto_tipi == 'TUTAR' and genel_iskonto_degeri > 0:
            uygulanan_genel_iskonto_tutari = genel_iskonto_degeri

        nihai_toplam_kdv_dahil = toplam_kdv_dahil_kalemler - uygulanan_genel_iskonto_tutari
        nihai_toplam_kdv_haric = toplam_kdv_haric_kalemler - uygulanan_genel_iskonto_tutari
        nihai_toplam_kdv = nihai_toplam_kdv_dahil - nihai_toplam_kdv_haric

        self.tkh_l.setText(f"KDV Hariç Toplam: {self.db._format_currency(nihai_toplam_kdv_haric)}")
        self.tkdv_l.setText(f"Toplam KDV: {self.db._format_currency(nihai_toplam_kdv)}")
        self.gt_l.setText(f"Genel Toplam: {self.db._format_currency(nihai_toplam_kdv_dahil)}")
        self.lbl_uygulanan_genel_iskonto.setText(f"Uygulanan Genel İskonto: {self.db._format_currency(uygulanan_genel_iskonto_tutari)}")

    def secili_kalemi_sil(self):
        selected_items = self.sep_tree.selectedItems() # QTreeWidget'tan seçili öğeleri al
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir kalem seçin.")
            return
            
        selected_item_qt = selected_items[0]
        kalem_index_str = selected_item_qt.text(0) # İlk sütun sıra numarası ("1", "2" vb.)
        try:
            kalem_index = int(kalem_index_str) - 1 # Listede 0 tabanlı indeks
        except ValueError:
            QMessageBox.critical(self.app, "Hata", "Seçili kalemin indeksi okunamadı.")
            return

        del self.fatura_kalemleri_ui[kalem_index]
        
        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()
        
    def sepeti_temizle(self):
        if self.fatura_kalemleri_ui and QMessageBox.question(self.app, "Onay", "Tüm kalemleri silmek istiyor musunuz?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.fatura_kalemleri_ui.clear()
            self.sepeti_guncelle_ui()
            self.toplamlari_hesapla_ui()

    def _kalem_duzenle_penceresi_ac(self, item, column): # item ve column sinyalden gelir
        # QTreeWidget'ta tıklanan öğenin verisini al.
        kalem_index_str = item.text(0) # İlk sütun sıra numarası (1 tabanlı)
        try:
            kalem_index = int(kalem_index_str) - 1 # 0 tabanlı indekse çevir
        except ValueError:
            QMessageBox.critical(self.app, "Hata", "Seçili kalemin indeksi okunamadı.")
            return

        kalem_verisi = self.fatura_kalemleri_ui[kalem_index]
        # KalemDuzenlePenceresi'nin PySide6 versiyonu burada çağrılacak.
        QMessageBox.information(self.app, "Kalem Düzenle", f"Kalem {kalem_index_str} için düzenleme penceresi açılacak.")

    def _on_sepet_kalem_click(self, item, column): # item ve column sinyalden gelir
        # QTreeWidget'ta sütun bazlı tıklama algılama (Fiyat Geçmişi butonu için)
        header_text = self.sep_tree.headerItem().text(column)
        if header_text == "Fiyat Geçmişi":
            urun_id_str = item.text(10) # Ürün ID sütunu (gizli sütun)
            kalem_index_str = item.text(0) # Sıra numarası
            try:
                urun_id = int(urun_id_str)
                kalem_index = int(kalem_index_str) - 1
            except ValueError:
                QMessageBox.critical(self.app, "Hata", "Ürün ID veya kalem indeksi okunamadı.")
                return

            if not self.secili_cari_id:
                QMessageBox.warning(self.app, "Uyarı", "Fiyat geçmişini görmek için lütfen önce bir cari seçin.")
                return
            
            # FiyatGecmisiPenceresi'nin PySide6 versiyonu burada çağrılacak.
            QMessageBox.information(self.app, "Fiyat Geçmişi", f"Ürün ID: {urun_id}, Cari ID: {self.secili_cari_id} için fiyat geçmişi açılacak.")

    def _update_sepet_kalem_from_history(self, kalem_index, new_price_kdv_dahil, new_iskonto_1, new_iskonto_2):
        if not (0 <= kalem_index < len(self.fatura_kalemleri_ui)): return
        current_kdv_orani = self.fatura_kalemleri_ui[kalem_index][4]
        iskonto_carpan_1 = (1 - new_iskonto_1 / 100)
        iskonto_carpan_2 = (1 - new_iskonto_2 / 100)
        calculated_original_price_kdv_dahil = new_price_kdv_dahil / (iskonto_carpan_1 * iskonto_carpan_2) if (iskonto_carpan_1 * iskonto_carpan_2) > 0 else new_price_kdv_dahil
        
        # self.kalem_guncelle metodunun yeni_fiyat_kdv_dahil_orijinal parametresini doğru formatta göndermeliyiz.
        # Bu durumda, kalem_guncelle'ye orijinal kdv dahil fiyatı olarak calculated_original_price_kdv_dahil'i ve
        # göstermek için de new_price_kdv_dahil'i göndermeliyiz.
        # Basitçe orijinal birim fiyat ve iskontolu birim fiyatı tekrar hesaplayıp göndereceğiz.
        
        # Bu kısım, kalem_guncelle'nin beklediği orijinal KDV hariç fiyatı yeniden hesaplamayı içerir.
        original_birim_fiyat_kdv_haric_calc = new_price_kdv_dahil / (1 + current_kdv_orani / 100)
        
        self.kalem_guncelle(kalem_index, self.fatura_kalemleri_ui[kalem_index][2], 
                            original_birim_fiyat_kdv_haric_calc, # Yeni KDV hariç orijinal birim fiyat
                            new_iskonto_1, new_iskonto_2, # Yeni iskontolar
                            0.0, # Bu parametre fatura anı alış fiyatı, fiyat geçmişinden gelmez
                            urun_adi=self.fatura_kalemleri_ui[kalem_index][1]) # Ürün adı

    def _check_stock_on_quantity_change(self): # event=None kaldırıldı
        selected_items = self.urun_arama_sonuclari_tree.selectedItems()
        if not selected_items: self.stk_l.setStyleSheet("color: black;"); return
        
        urun_id = selected_items[0].data(0, Qt.UserRole) # Ürün ID'sini UserRole'dan al
        
        urun_detaylari = None
        for iid, details in self.urun_map_filtrelenmis.items():
            if details['id'] == urun_id:
                urun_detaylari = details
                break

        if not urun_detaylari:
            self.stk_l.setStyleSheet("color: black;"); return

        mevcut_stok_db = self.db.get_stok_miktari_for_kontrol(urun_id, self.duzenleme_id)
        
        try:
            girilen_miktar = float(self.mik_e.text().replace(',', '.'))
        except ValueError:
            self.stk_l.setStyleSheet("color: black;"); return

        sepetteki_miktar = sum(k[2] for k in self.fatura_kalemleri_ui if k[0] == urun_id)
        
        if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.SIPARIS_TIP_SATIS, self.db.FATURA_TIP_ALIS_IADE]:
            if (sepetteki_miktar + girilen_miktar) > mevcut_stok_db:
                self.stk_l.setStyleSheet("color: red;")
            else:
                self.stk_l.setStyleSheet("color: green;")
        else: 
            self.stk_l.setStyleSheet("color: black;")

    def _open_urun_karti_from_sep_item(self, item, column): # item ve column sinyalden gelir
        # Ürün ID'si gizli sütunda olduğu için onu alacağız.
        urun_id_str = item.text(10) # 11. sütun (indeks 10)
        try:
            urun_id = int(urun_id_str)
        except ValueError:
            return
        
        # StokKartiPenceresi'nin PySide6 versiyonu burada çağrılacak.
        QMessageBox.information(self.app, "Ürün Kartı", f"Ürün ID: {urun_id} için ürün kartı açılacak (Placeholder).")

    def _open_urun_karti_from_search(self, item, column): # item ve column sinyalden gelir
        # Ürün ID'si QTreeWidgetItem'ın data(0, Qt.UserRole) kısmında saklı.
        urun_id = item.data(0, Qt.UserRole)
        
        if urun_id is None: return

        # StokKartiPenceresi'nin PySide6 versiyonu burada çağrılacak.
        QMessageBox.information(self.app, "Ürün Kartı", f"Ürün ID: {urun_id} için ürün kartı açılacak (Placeholder).")

    def _format_numeric_line_edit(self, line_edit: QLineEdit, decimals: int):
        """
        QLineEdit'teki sayısal değeri Türkçe formatına (virgül ondalık ayracı) göre biçimlendirir.
        Giriş sırasında noktanın virgüle dönüşmesini ve odak kaybedildiğinde veya enter'a basıldığında
        tam formatlamayı sağlar.
        """
        text = line_edit.text()
        if not text:
            return

        if '.' in text and ',' not in text:
            cursor_pos = line_edit.cursorPosition()
            line_edit.setText(text.replace('.', ','))
            line_edit.setCursorPosition(cursor_pos)

        if isinstance(line_edit, QLineEdit) and not line_edit.hasTracking():
            try:
                value = float(line_edit.text().replace(',', '.'))
                formatted_value = locale.format_string(f"%.{decimals}f", value, grouping=True)
                line_edit.setText(formatted_value)
            except ValueError:
                pass

# FaturaOlusturmaSayfasi sınıfı (Dönüştürülmüş PySide6 versiyonu)
class FaturaOlusturmaSayfasi(BaseIslemSayfasi):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi, duzenleme_id=None, yenile_callback=None, initial_cari_id=None, initial_urunler=None, initial_data=None):
        self.iade_modu_aktif = False 
        self.original_fatura_id_for_iade = None

        if initial_data and initial_data.get('iade_modu'):
            self.iade_modu_aktif = True
            self.original_fatura_id_for_iade = initial_data.get('orijinal_fatura_id')

        super().__init__(parent, db_manager, app_ref, fatura_tipi, duzenleme_id, yenile_callback, 
                         initial_cari_id=initial_cari_id, initial_urunler=initial_urunler, initial_data=initial_data)
        
        # islem_tipi ayarı (PySide6'da string sabitleri kullanılabilir)
        if self.iade_modu_aktif:
            if fatura_tipi == self.db.FATURA_TIP_SATIS:
                self.islem_tipi = self.db.FATURA_TIP_SATIS_IADE
            elif fatura_tipi == self.db.FATURA_TIP_ALIS:
                self.islem_tipi = self.db.FATURA_TIP_ALIS_IADE

        # StringVar'lar yerine QLineEdit veya QComboBox kullanılacak, bu attributelar direkt string tutacak.
        self.sv_fatura_no = "" # QLineEdit'ten alınacak
        self.sv_tarih = datetime.now().strftime('%Y-%m-%d') # QLineEdit'ten alınacak
        self.sv_vade_tarihi = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d') # QLineEdit'ten alınacak
        self.sv_odeme_turu = "" # QComboBox'tan alınacak
        self.sv_kasa_banka = "" # QComboBox'tan alınacak
        self.sv_fatura_notlari = "" # QTextEdit'ten alınacak
        self.sv_misafir_adi = "" # QLineEdit'ten alınacak

        self.cari_id = None
        self.cari_tip = None # Fatura tipi'ne göre Musteri veya Tedarikçi
        self.perakende_musteri_id = self.db.get_perakende_musteri_id()

        if not self.initial_data:
            if not self.duzenleme_id and not self.iade_modu_aktif:
                self.sv_fatura_no = self.db.son_fatura_no_getir(self.islem_tipi)
            self.sv_odeme_turu = self.db.ODEME_TURU_NAKIT

        self._setup_paneller() # UI elemanlarını oluşturur ve yerleştirir.

        # Temel verilerin yüklenmesi
        self._carileri_yukle_ve_cachele() 
        self._urunleri_yukle_ve_cachele_ve_goster()
        self._yukle_kasa_banka_hesaplarini() # Faturaya özel

        self._load_initial_data() # Formu başlangıç verileriyle doldurur.

        # Klavye navigasyonunu bağlar.
        self._bind_keyboard_navigation()

        # UI elemanları kurulduktan sonra iade modu mantığını uygula
        # QTimer.singleShot(0, self._on_iade_modu_changed) # UI hazır olunca çağır

    def _on_iade_modu_changed(self): # *args kaldırıldı
        if isinstance(self.parent(), QDialog):
            self.parent().setWindowTitle(self._get_baslik())
        elif isinstance(self.parent(), QMainWindow): # Eğer main window içinde bir sekme ise
            self.parent().setWindowTitle(self._get_baslik()) # Genellikle main window başlığını değiştirmezsiniz, ama örneğin
        
        if self.iade_modu_aktif:
            if hasattr(self, 'f_no_e'):
                self.f_no_e.setEnabled(False) # Fatura no kilitli kalacak
            if hasattr(self, 'cari_sec_button'):
                self.cari_sec_button.setEnabled(False) # Cari seçimi kilitli kalacak
            
            self.app.set_status_message("İade Faturası oluşturma modu aktif.")
            
            # Ödeme alanlarını KİLİTLEME, düzenlenebilir bırak
            if hasattr(self, 'odeme_turu_cb'):
                self.odeme_turu_cb.setEnabled(True) # Readonly gibi davranır
            if hasattr(self, 'islem_hesap_cb'):
                self.islem_hesap_cb.setEnabled(True) # Readonly gibi davranır
            if hasattr(self, 'entry_vade_tarihi'):
                self.entry_vade_tarihi.setEnabled(True)
            if hasattr(self, 'btn_vade_tarihi'):
                self.btn_vade_tarihi.setEnabled(True)
            
            if hasattr(self, '_odeme_turu_degisince_event_handler'):
                self._odeme_turu_degisince_event_handler()

            if hasattr(self, 'misafir_adi_container_frame'):
                if hasattr(self, 'entry_misafir_adi'):
                    self.entry_misafir_adi.clear() # Misafir adını temizle
                self.misafir_adi_container_frame.setVisible(False)
        else: # Normal fatura modu
            if hasattr(self, 'f_no_e'):
                self.f_no_e.setEnabled(True)
            if hasattr(self, 'cari_sec_button'):
                self.cari_sec_button.setEnabled(True)
            if not self.duzenleme_id and hasattr(self, 'f_no_e'):
                self.f_no_e.setText(self.db.son_fatura_no_getir(self.islem_tipi))
            
            if hasattr(self, '_odeme_turu_ve_misafir_adi_kontrol'):
                self._odeme_turu_ve_misafir_adi_kontrol()

    def _get_baslik(self):
        if self.iade_modu_aktif:
            return "İade Faturası Oluştur"
        if self.duzenleme_id:
            return "Fatura Güncelleme"
        return "Yeni Satış Faturası" if self.islem_tipi == self.db.FATURA_TIP_SATIS else "Yeni Alış Faturası"
        
    def _setup_ozel_alanlar(self, parent_frame):
        """Ana sınıfın sol paneline faturaya özel alanları ekler ve klavye navigasyon sırasını belirler."""
        layout = QGridLayout(parent_frame) # parent_frame'in layout'unu ayarla

        # Fatura No ve Tarih
        layout.addWidget(QLabel("Fatura No:"), 0, 0)
        self.f_no_e = QLineEdit()
        self.f_no_e.setText(self.sv_fatura_no)
        layout.addWidget(self.f_no_e, 0, 1)
        self.form_entries_order.append(self.f_no_e)

        layout.addWidget(QLabel("Tarih:"), 0, 2)
        self.fatura_tarihi_entry = QLineEdit()
        self.fatura_tarihi_entry.setText(self.sv_tarih)
        layout.addWidget(self.fatura_tarihi_entry, 0, 3)
        takvim_button_tarih = QPushButton("🗓️")
        takvim_button_tarih.setFixedWidth(30)
        takvim_button_tarih.clicked.connect(lambda: DatePickerDialog(self.app, self.fatura_tarihi_entry))
        layout.addWidget(takvim_button_tarih, 0, 4)
        self.form_entries_order.append(self.fatura_tarihi_entry)

        # Cari Seçim
        cari_btn_label_text = "Müşteri Seç:" if self.islem_tipi == self.db.FATURA_TIP_SATIS else "Tedarikçi Seç:"
        layout.addWidget(QLabel(cari_btn_label_text), 1, 0)
        self.cari_sec_button = QPushButton("Cari Seç...")
        self.cari_sec_button.clicked.connect(self._cari_sec_dialog_ac)
        layout.addWidget(self.cari_sec_button, 1, 1)
        self.lbl_secili_cari_adi = QLabel("Seçilen Cari: Yok")
        self.lbl_secili_cari_adi.setFont(QFont("Segoe UI", 9, QFont.Bold))
        layout.addWidget(self.lbl_secili_cari_adi, 1, 2, 1, 3) # 1 satır, 3 sütun kapla
        self.form_entries_order.append(self.cari_sec_button)

        # Bakiye ve Misafir Adı
        self.lbl_cari_bakiye = QLabel("Bakiye: ...")
        self.lbl_cari_bakiye.setFont(QFont("Segoe UI", 9, QFont.Bold))
        layout.addWidget(self.lbl_cari_bakiye, 2, 0, 1, 2)
        
        self.misafir_adi_container_frame = QFrame(parent_frame)
        self.misafir_adi_container_layout = QHBoxLayout(self.misafir_adi_container_frame)
        self.misafir_adi_container_layout.setContentsMargins(0,0,0,0) # İç boşlukları sıfırla
        layout.addWidget(self.misafir_adi_container_frame, 2, 2, 1, 3) # Grid'e yerleştir
        self.misafir_adi_container_frame.setVisible(False) # Başlangıçta gizli

        self.misafir_adi_container_layout.addWidget(QLabel("Misafir Adı :"))
        self.entry_misafir_adi = QLineEdit()
        self.entry_misafir_adi.setText(self.sv_misafir_adi)
        self.misafir_adi_container_layout.addWidget(self.entry_misafir_adi)
        self.form_entries_order.append(self.entry_misafir_adi)

        # Ödeme Türü
        layout.addWidget(QLabel("Ödeme Türü:"), 3, 0)
        self.odeme_turu_cb = QComboBox()
        self.odeme_turu_cb.addItems([self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, 
                                     self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, 
                                     self.db.ODEME_TURU_SENET, self.db.ODEME_TURU_ACIK_HESAP, 
                                     self.db.ODEME_TURU_ETKISIZ_FATURA])
        self.odeme_turu_cb.setCurrentText(self.sv_odeme_turu) # Değeri ata
        self.odeme_turu_cb.currentIndexChanged.connect(self._odeme_turu_degisince_event_handler)
        layout.addWidget(self.odeme_turu_cb, 3, 1)
        self.form_entries_order.append(self.odeme_turu_cb)

        # Kasa/Banka
        layout.addWidget(QLabel("İşlem Kasa/Banka:"), 4, 0)
        self.islem_hesap_cb = QComboBox()
        # QComboBox'a değerler _yukle_kasa_banka_hesaplarini metodunda eklenecek.
        self.islem_hesap_cb.setEnabled(False) # Başlangıçta pasif
        layout.addWidget(self.islem_hesap_cb, 4, 1, 1, 3) # 1 satır, 3 sütun kapla
        self.form_entries_order.append(self.islem_hesap_cb)

        # Vade Tarihi
        self.lbl_vade_tarihi = QLabel("Vade Tarihi:")
        layout.addWidget(self.lbl_vade_tarihi, 5, 0)
        self.entry_vade_tarihi = QLineEdit()
        self.entry_vade_tarihi.setText(self.sv_vade_tarihi)
        self.entry_vade_tarihi.setEnabled(False) # Başlangıçta pasif
        layout.addWidget(self.entry_vade_tarihi, 5, 1)
        self.btn_vade_tarihi = QPushButton("🗓️")
        self.btn_vade_tarihi.setFixedWidth(30)
        self.btn_vade_tarihi.clicked.connect(lambda: DatePickerDialog(self.app, self.entry_vade_tarihi))
        self.btn_vade_tarihi.setEnabled(False) # Başlangıçta pasif
        layout.addWidget(self.btn_vade_tarihi, 5, 2)
        self.form_entries_order.append(self.entry_vade_tarihi)


        # Fatura Notları
        layout.addWidget(QLabel("Fatura Notları:"), 6, 0, Qt.AlignTop)
        self.fatura_notlari_text = QTextEdit()
        # self.fatura_notlari_text.setPlainText(self.sv_fatura_notlari) # QTextEdit'in setText'i direkt string alır
        layout.addWidget(self.fatura_notlari_text, 6, 1, 1, 4) # 1 satır, 4 sütun kapla
        self.form_entries_order.append(self.fatura_notlari_text)

        # Genel İskonto
        layout.addWidget(QLabel("Genel İskonto Tipi:"), 7, 0)
        self.genel_iskonto_tipi_cb = QComboBox()
        self.genel_iskonto_tipi_cb.addItems(["YOK", "YUZDE", "TUTAR"])
        self.genel_iskonto_tipi_cb.setCurrentText(self.sv_genel_iskonto_tipi)
        self.genel_iskonto_tipi_cb.currentIndexChanged.connect(self._on_genel_iskonto_tipi_changed)
        layout.addWidget(self.genel_iskonto_tipi_cb, 7, 1)
        self.form_entries_order.append(self.genel_iskonto_tipi_cb)

        layout.addWidget(QLabel("Genel İskonto Değeri:"), 7, 2)
        self.genel_iskonto_degeri_e = QLineEdit()
        self.genel_iskonto_degeri_e.setText(self.sv_genel_iskonto_degeri)
        self.genel_iskonto_degeri_e.setEnabled(False) # Başlangıçta pasif
        self.genel_iskonto_degeri_e.textChanged.connect(self.toplamlari_hesapla_ui) # Klavye inputu için
        layout.addWidget(self.genel_iskonto_degeri_e, 7, 3)
        self.form_entries_order.append(self.genel_iskonto_degeri_e)

        # Column stretch for appropriate columns (Ödeme Türü, Kasa/Banka, Fatura Notları)
        layout.setColumnStretch(1, 1) # Fatura No, Ödeme Türü, Genel İskonto Tipi
        layout.setColumnStretch(3, 1) # Tarih, Genel İskonto Değeri

    def _on_iade_modu_changed(self): # *args kaldırıldı
        # Parent penceresinin başlığını güncelle
        if isinstance(self.parent(), QDialog):
            self.parent().setWindowTitle(self._get_baslik())
        elif isinstance(self.parent(), QMainWindow): # Eğer main window içinde bir sekme ise
            self.parent().setWindowTitle(self._get_baslik()) # Genellikle main window başlığını değiştirmezsiniz.
        
        if self.iade_modu_aktif:
            if hasattr(self, 'f_no_e'):
                self.f_no_e.setEnabled(False) # Fatura no kilitli kalacak
            if hasattr(self, 'cari_sec_button'):
                self.cari_sec_button.setEnabled(False) # Cari seçimi kilitli kalacak
            
            self.app.set_status_message("İade Faturası oluşturma modu aktif.")
            
            # Ödeme alanlarını KİLİTLEME, düzenlenebilir bırak
            if hasattr(self, 'odeme_turu_cb'):
                self.odeme_turu_cb.setEnabled(True) # Readonly gibi davranır
            if hasattr(self, 'islem_hesap_cb'):
                self.islem_hesap_cb.setEnabled(True) # Readonly gibi davranır
            if hasattr(self, 'entry_vade_tarihi'):
                self.entry_vade_tarihi.setEnabled(True)
            if hasattr(self, 'btn_vade_tarihi'):
                self.btn_vade_tarihi.setEnabled(True)
            
            if hasattr(self, '_odeme_turu_degisince_event_handler'):
                self._odeme_turu_degisince_event_handler()

            if hasattr(self, 'misafir_adi_container_frame'):
                if hasattr(self, 'entry_misafir_adi'):
                    self.entry_misafir_adi.clear() # Misafir adını temizle
                self.misafir_adi_container_frame.setVisible(False)
        else: # Normal fatura modu
            if hasattr(self, 'f_no_e'):
                self.f_no_e.setEnabled(True)
            if hasattr(self, 'cari_sec_button'):
                self.cari_sec_button.setEnabled(True)
            if not self.duzenleme_id and hasattr(self, 'f_no_e'):
                self.f_no_e.setText(self.db.son_fatura_no_getir(self.islem_tipi))
            
            if hasattr(self, '_odeme_turu_ve_misafir_adi_kontrol'):
                self._odeme_turu_ve_misafir_adi_kontrol()

    def _get_baslik(self):
        if self.iade_modu_aktif:
            return "İade Faturası Oluştur"
        if self.duzenleme_id:
            return "Fatura Güncelleme"
        return "Yeni Satış Faturası" if self.islem_tipi == self.db.FATURA_TIP_SATIS else "Yeni Alış Faturası"
        
    def _setup_ozel_alanlar(self, parent_frame):
        """Ana sınıfın sol paneline faturaya özel alanları ekler ve klavye navigasyon sırasını belirler."""
        layout = QGridLayout(parent_frame) # parent_frame'in layout'unu ayarla

        # Fatura No ve Tarih
        layout.addWidget(QLabel("Fatura No:"), 0, 0)
        self.f_no_e = QLineEdit()
        self.f_no_e.setText(self.sv_fatura_no) # Değeri ata
        layout.addWidget(self.f_no_e, 0, 1)
        self.form_entries_order.append(self.f_no_e)

        layout.addWidget(QLabel("Tarih:"), 0, 2)
        self.fatura_tarihi_entry = QLineEdit()
        self.fatura_tarihi_entry.setText(self.sv_tarih) # Değeri ata
        layout.addWidget(self.fatura_tarihi_entry, 0, 3)
        takvim_button_tarih = QPushButton("🗓️")
        takvim_button_tarih.setFixedWidth(30)
        takvim_button_tarih.clicked.connect(lambda: DatePickerDialog(self.app, self.fatura_tarihi_entry))
        layout.addWidget(takvim_button_tarih, 0, 4)
        self.form_entries_order.append(self.fatura_tarihi_entry)

        # Cari Seçim
        cari_btn_label_text = "Müşteri Seç:" if self.islem_tipi == self.db.FATURA_TIP_SATIS else "Tedarikçi Seç:"
        layout.addWidget(QLabel(cari_btn_label_text), 1, 0)
        self.cari_sec_button = QPushButton("Cari Seç...")
        self.cari_sec_button.clicked.connect(self._cari_sec_dialog_ac)
        layout.addWidget(self.cari_sec_button, 1, 1)
        self.lbl_secili_cari_adi = QLabel("Seçilen Cari: Yok")
        self.lbl_secili_cari_adi.setFont(QFont("Segoe UI", 9, QFont.Bold))
        layout.addWidget(self.lbl_secili_cari_adi, 1, 2, 1, 3) # 1 satır, 3 sütun kapla
        self.form_entries_order.append(self.cari_sec_button)

        # Bakiye ve Misafir Adı
        self.lbl_cari_bakiye = QLabel("Bakiye: ...")
        self.lbl_cari_bakiye.setFont(QFont("Segoe UI", 9, QFont.Bold))
        layout.addWidget(self.lbl_cari_bakiye, 2, 0, 1, 2)
        
        self.misafir_adi_container_frame = QFrame(parent_frame)
        self.misafir_adi_container_layout = QHBoxLayout(self.misafir_adi_container_frame)
        self.misafir_adi_container_layout.setContentsMargins(0,0,0,0) # İç boşlukları sıfırla
        layout.addWidget(self.misafir_adi_container_frame, 2, 2, 1, 3) # Grid'e yerleştir
        self.misafir_adi_container_frame.setVisible(False) # Başlangıçta gizli

        self.misafir_adi_container_layout.addWidget(QLabel("Misafir Adı :"))
        self.entry_misafir_adi = QLineEdit()
        self.entry_misafir_adi.setText(self.sv_misafir_adi) # Değeri ata
        self.misafir_adi_container_layout.addWidget(self.entry_misafir_adi)
        self.form_entries_order.append(self.entry_misafir_adi)

        # Ödeme Türü
        layout.addWidget(QLabel("Ödeme Türü:"), 3, 0)
        self.odeme_turu_cb = QComboBox()
        self.odeme_turu_cb.addItems([self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, 
                                     self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, 
                                     self.db.ODEME_TURU_SENET, self.db.ODEME_TURU_ACIK_HESAP, 
                                     self.db.ODEME_TURU_ETKISIZ_FATURA])
        self.odeme_turu_cb.setCurrentText(self.sv_odeme_turu) # Değeri ata
        self.odeme_turu_cb.currentIndexChanged.connect(self._odeme_turu_degisince_event_handler)
        layout.addWidget(self.odeme_turu_cb, 3, 1)
        self.form_entries_order.append(self.odeme_turu_cb)

        # Kasa/Banka
        layout.addWidget(QLabel("İşlem Kasa/Banka:"), 4, 0)
        self.islem_hesap_cb = QComboBox()
        # QComboBox'a değerler _yukle_kasa_banka_hesaplarini metodunda eklenecek.
        self.islem_hesap_cb.setEnabled(False) # Başlangıçta pasif
        layout.addWidget(self.islem_hesap_cb, 4, 1, 1, 3) # 1 satır, 3 sütun kapla
        self.form_entries_order.append(self.islem_hesap_cb)

        # Vade Tarihi
        self.lbl_vade_tarihi = QLabel("Vade Tarihi:")
        layout.addWidget(self.lbl_vade_tarihi, 5, 0)
        self.entry_vade_tarihi = QLineEdit()
        self.entry_vade_tarihi.setText(self.sv_vade_tarihi) # Değeri ata
        self.entry_vade_tarihi.setEnabled(False) # Başlangıçta pasif
        layout.addWidget(self.entry_vade_tarihi, 5, 1)
        self.btn_vade_tarihi = QPushButton("🗓️")
        self.btn_vade_tarihi.setFixedWidth(30)
        self.btn_vade_tarihi.clicked.connect(lambda: DatePickerDialog(self.app, self.entry_vade_tarihi))
        self.btn_vade_tarihi.setEnabled(False) # Başlangıçta pasif
        layout.addWidget(self.btn_vade_tarihi, 5, 2)
        self.form_entries_order.append(self.entry_vade_tarihi)


        # Fatura Notları
        layout.addWidget(QLabel("Fatura Notları:"), 6, 0, Qt.AlignTop)
        self.fatura_notlari_text = QTextEdit()
        # self.fatura_notlari_text.setPlainText(self.sv_fatura_notlari) # QTextEdit'in setText'i direkt string alır
        layout.addWidget(self.fatura_notlari_text, 6, 1, 1, 4) # 1 satır, 4 sütun kapla
        self.form_entries_order.append(self.fatura_notlari_text)

        # Genel İskonto
        layout.addWidget(QLabel("Genel İskonto Tipi:"), 7, 0)
        self.genel_iskonto_tipi_cb = QComboBox()
        self.genel_iskonto_tipi_cb.addItems(["YOK", "YUZDE", "TUTAR"])
        self.genel_iskonto_tipi_cb.setCurrentText(self.sv_genel_iskonto_tipi) # Değeri ata
        self.genel_iskonto_tipi_cb.currentIndexChanged.connect(self._on_genel_iskonto_tipi_changed)
        layout.addWidget(self.genel_iskonto_tipi_cb, 7, 1)
        self.form_entries_order.append(self.genel_iskonto_tipi_cb)

        layout.addWidget(QLabel("Genel İskonto Değeri:"), 7, 2)
        self.genel_iskonto_degeri_e = QLineEdit()
        self.genel_iskonto_degeri_e.setText(self.sv_genel_iskonto_degeri) # Değeri ata
        self.genel_iskonto_degeri_e.setEnabled(False) # Başlangıçta pasif
        self.genel_iskonto_degeri_e.textChanged.connect(self.toplamlari_hesapla_ui) # Klavye inputu için
        layout.addWidget(self.genel_iskonto_degeri_e, 7, 3)
        self.form_entries_order.append(self.genel_iskonto_degeri_e)

        # Column stretch for appropriate columns (Ödeme Türü, Kasa/Banka, Fatura Notları)
        layout.setColumnStretch(1, 1) # Fatura No, Ödeme Türü, Genel İskonto Tipi
        layout.setColumnStretch(3, 1) # Tarih, Genel İskonto Değeri

    def _ot_odeme_tipi_degisince(self, *args): # event=None kaldırıldı
        """Hızlı işlem formunda ödeme tipi değiştiğinde kasa/banka seçimini ayarlar."""
        selected_odeme_sekli = self.ot_odeme_tipi_combo.currentText() # QComboBox'tan metin al
        varsayilan_kb_db = self.db.get_kasa_banka_by_odeme_turu(selected_odeme_sekli)

        if varsayilan_kb_db:
            varsayilan_kb_id = varsayilan_kb_db[0]
            found_and_set = False
            for text, id_val in self.kasa_banka_map.items():
                if id_val == varsayilan_kb_id:
                    self.ot_kasa_banka_combo.setCurrentText(text) # QComboBox'a metin ata
                    found_and_set = True
                    break
            if not found_and_set and self.ot_kasa_banka_combo.count() > 1: # İlk öğe boş olabilir
                self.ot_kasa_banka_combo.setCurrentIndex(1) # İlk geçerli hesabı seç
        elif self.ot_kasa_banka_combo.count() > 0: # Eğer varsayılan yoksa, ilkini seç (eğer varsa)
            self.ot_kasa_banka_combo.setCurrentIndex(0) # İlk öğeyi seç
        else:
            self.ot_kasa_banka_combo.clear() # Hiç hesap yoksa temizle

    def _load_initial_data(self):
        """
        Başlangıç verilerini (düzenleme modu, dışarıdan gelen veri veya taslak) forma yükler.
        Bu metod BaseIslemSayfasi'nda genel kontrolü yapar, alt sınıflar kendi spesifik
        doldurma mantıklarını içerebilir.
        """
        if self.duzenleme_id:
            self._mevcut_faturayi_yukle()
            logging.debug("FaturaOlusturmaSayfasi - Düzenleme modunda, mevcut fatura yüklendi.")
        elif self.initial_data:
            self._load_temp_form_data(forced_temp_data=self.initial_data)
            logging.debug("FaturaOlusturmaSayfasi - initial_data ile taslak veri yüklendi.")
        else:
            # Yeni bir fatura oluşturuluyor. Önce formu sıfırla.
            self._reset_form_explicitly(ask_confirmation=False)
            logging.debug("FaturaOlusturmaSayfasi - Yeni fatura için form sıfırlandı.")
            
            # Şimdi varsayılan carileri ata.
            if self.islem_tipi == self.db.FATURA_TIP_SATIS:
                # Satış Faturası ise 'Perakende Satış Müşterisi'ni seç
                if self.db.perakende_musteri_id is not None:
                    perakende_data = self.db.musteri_getir_by_id(self.db.perakende_musteri_id)
                    if perakende_data:
                        self._on_cari_secildi_callback(perakende_data['id'], perakende_data['ad'])
            elif self.islem_tipi == self.db.FATURA_TIP_ALIS:
                # Alış Faturası ise 'Genel Tedarikçi'yi seç
                if self.db.genel_tedarikci_id is not None:
                    genel_tedarikci_data = self.db.tedarikci_getir_by_id(self.db.genel_tedarikci_id)
                    if genel_tedarikci_data:
                        self._on_cari_secildi_callback(genel_tedarikci_data['id'], genel_tedarikci_data['ad'])
        
        # UI elemanları kurulduktan sonra iade modu mantığını uygula (biraz gecikmeyle)
        QTimer.singleShot(0, self._on_iade_modu_changed)

    def kaydet(self):
        fatura_no = self.f_no_e.text().strip()
        
        # Fatura tarihini QLineEdit'ten alıyoruz ve formatını kontrol ediyoruz.
        fatura_tarihi = self.fatura_tarihi_entry.text().strip()
        if not fatura_tarihi:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Fatura Tarihi zorunludur.")
            return
        try:
            datetime.strptime(fatura_tarihi, '%Y-%m-%d')
        except ValueError:
            QMessageBox.critical(self.app, "Hata", "Fatura Tarihi formatı (YYYY-AA-GG) olmalıdır.")
            return

        odeme_turu_secilen = self.odeme_turu_cb.currentText()
        secili_hesap_display = self.islem_hesap_cb.currentText()
        fatura_notlari_val = self.fatura_notlari_text.toPlainText().strip()
        genel_iskonto_tipi_val = self.genel_iskonto_tipi_cb.currentText()
        genel_iskonto_degeri_val = float(self.genel_iskonto_degeri_e.text().replace(',', '.'))
        vade_tarihi_val = None

        if odeme_turu_secilen == self.db.ODEME_TURU_ACIK_HESAP:
            vade_tarihi_val = self.entry_vade_tarihi.text().strip()
            if not vade_tarihi_val:
                QMessageBox.critical(self.app, "Eksik Bilgi", "Açık Hesap için Vade Tarihi zorunludur.")
                return
            try:
                datetime.strptime(vade_tarihi_val, '%Y-%m-%d')
            except ValueError:
                QMessageBox.critical(self.app, "Hata", "Vade Tarihi formatı (YYYY-AA-GG) olmalıdır.")
                return

        kasa_banka_id_val = None
        if odeme_turu_secilen in self.db.pesin_odeme_turleri:
            if secili_hesap_display and secili_hesap_display != "Hesap Yok":
                kasa_banka_id_val = self.kasa_banka_map.get(secili_hesap_display)
            else:
                QMessageBox.critical(self.app, "Eksik Bilgi", "Peşin ödeme için Kasa/Banka seçimi zorunludur.")
                return

        misafir_adi_fatura = self.entry_misafir_adi.text().strip() if self.entry_misafir_adi.isVisible() else None

        if not fatura_no:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Fatura Numarası zorunludur.")
            return
        if not self.secili_cari_id and not misafir_adi_fatura:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Lütfen bir cari seçin veya Misafir Adı girin.")
            return
        if not self.fatura_kalemleri_ui:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Faturada en az bir ürün olmalı.")
            return

        kalemler_data = []
        for i, k_ui in enumerate(self.fatura_kalemleri_ui):
            if not isinstance(k_ui, (list, tuple)) or len(k_ui) < 14:
                QMessageBox.critical(self.app, "Veri Hatası", f"Sepetteki {i+1}. kalem eksik veya hatalı veri içeriyor.")
                return
            kalemler_data.append((k_ui[0], k_ui[2], k_ui[3], k_ui[4], k_ui[8], k_ui[10], k_ui[11], k_ui[12], k_ui[13]))

        try:
            fatura_tip_to_save = self.islem_tipi
            if self.iade_modu_aktif:
                if self.islem_tipi == self.db.FATURA_TIP_SATIS: fatura_tip_to_save = self.db.FATURA_TIP_SATIS_IADE
                elif self.islem_tipi == self.db.FATURA_TIP_ALIS: fatura_tip_to_save = self.db.FATURA_TIP_ALIS_IADE

            if self.duzenleme_id:
                success, message = self.app.fatura_servisi.fatura_guncelle(
                    self.duzenleme_id, fatura_no, fatura_tarihi, str(self.secili_cari_id), odeme_turu_secilen,
                    kalemler_data, 
                    kasa_banka_id_val, misafir_adi_fatura, fatura_notlari_val, vade_tarihi_val,
                    genel_iskonto_tipi_val, genel_iskonto_degeri_val
                )
            else:
                success, message = self.app.fatura_servisi.fatura_olustur(
                    fatura_no, fatura_tarihi, fatura_tip_to_save, self.secili_cari_id, kalemler_data, odeme_turu_secilen,
                    kasa_banka_id_val, misafir_adi_fatura, fatura_notlari_val, vade_tarihi_val,
                    genel_iskonto_tipi_val, genel_iskonto_degeri_val,
                    original_fatura_id=self.original_fatura_id_for_iade if self.iade_modu_aktif else None
                )

            if success:
                kayit_mesaji = "Fatura başarıyla güncellendi." if self.duzenleme_id else f"'{fatura_no}' numaralı fatura başarıyla kaydedildi."
                QMessageBox.information(self.app, "Başarılı", kayit_mesaji)
                
                if self.yenile_callback:
                    self.yenile_callback()
                
                if not self.duzenleme_id:
                    self._reset_form_explicitly(ask_confirmation=False) 
                    self.app.set_status_message(f"Fatura '{fatura_no}' kaydedildi. Yeni fatura girişi için sayfa hazır.")
                else:
                    self.app.set_status_message(f"Fatura '{fatura_no}' başarıyla güncellendi.")
            else:
                QMessageBox.critical(self.app, "Hata", message)

        except Exception as e:
            logging.error(f"Fatura kaydedilirken beklenmeyen bir hata oluştu: {e}\nDetaylar:\n{traceback.format_exc()}")
            QMessageBox.critical(self.app, "Kritik Hata", f"Fatura kaydedilirken beklenmeyen bir hata oluştu:\n{e}")
            
    def _mevcut_faturayi_yukle(self):
        fatura_ana = self.db.fatura_getir_by_id(self.duzenleme_id)
        if not fatura_ana:
            QMessageBox.critical(self.app, "Hata", "Düzenlenecek fatura bilgileri alınamadı.")
            self.parent().close() 
            return

        self._loaded_fatura_data_for_edit = fatura_ana
        
        f_no = fatura_ana['fatura_no']
        tarih_db = fatura_ana['tarih']
        _tip = fatura_ana['tip']
        c_id_db = fatura_ana['cari_id']
        odeme_turu_db = fatura_ana['odeme_turu']
        misafir_adi_db = fatura_ana['misafir_adi']
        fatura_notlari_db = fatura_ana['fatura_notlari']
        vade_tarihi_db = fatura_ana['vade_tarihi']
        genel_iskonto_tipi_db = fatura_ana['genel_iskonto_tipi']
        genel_iskonto_degeri_db = fatura_ana['genel_iskonto_degeri']
        kasa_banka_id_db = fatura_ana['kasa_banka_id']

        # Formu doldurma...
        self.f_no_e.setEnabled(True) 
        self.f_no_e.setText(f_no)
        self.fatura_tarihi_entry.setText(tarih_db)

        if self.fatura_notlari_text:
            self.fatura_notlari_text.setPlainText(fatura_notlari_db if fatura_notlari_db else "")
            
        self.entry_vade_tarihi.setText(vade_tarihi_db if vade_tarihi_db else "")

        self.genel_iskonto_tipi_cb.setCurrentText(genel_iskonto_tipi_db if genel_iskonto_tipi_db else "YOK")
        self.genel_iskonto_degeri_e.setText(f"{genel_iskonto_degeri_db:.2f}".replace('.', ',') if genel_iskonto_degeri_db else "0,00")
        self._on_genel_iskonto_tipi_changed()
        
        self.odeme_turu_cb.setCurrentText(odeme_turu_db if odeme_turu_db else "NAKİT")
        
        display_text_for_cari = self.cari_id_to_display_map.get(str(c_id_db), "Bilinmeyen Cari")
        self._on_cari_secildi_callback(c_id_db, display_text_for_cari)

        if str(c_id_db) == str(self.db.perakende_musteri_id) and misafir_adi_db:
            self.entry_misafir_adi.setText(misafir_adi_db)

        self._odeme_turu_degisince_hesap_combobox_ayarla()
        
        if kasa_banka_id_db is not None:
            for text, kb_id in self.kasa_banka_map.items():
                if kb_id == kasa_banka_id_db:
                    self.islem_hesap_cb.setCurrentText(text)
                    break

        fatura_kalemleri_db = self.db.fatura_detay_al(self.duzenleme_id)
        self.fatura_kalemleri_ui.clear()
        for k_db in fatura_kalemleri_db:
            iskontolu_birim_fiyat_kdv_dahil = (k_db['kalem_toplam_kdv_dahil'] / k_db['miktar']) if k_db['miktar'] != 0 else 0.0
            self.fatura_kalemleri_ui.append((
                k_db['urun_id'], k_db['urun_adi'], k_db['miktar'],
                k_db['birim_fiyat'], k_db['kdv_orani'], k_db['kdv_tutari'],
                k_db['kalem_toplam_kdv_haric'], k_db['kalem_toplam_kdv_dahil'],
                k_db['alis_fiyati_fatura_aninda'], k_db['kdv_orani_fatura_aninda'],
                k_db['iskonto_yuzde_1'], k_db['iskonto_yuzde_2'],
                k_db['iskonto_tipi'], k_db['iskonto_degeri'],
                iskontolu_birim_fiyat_kdv_dahil
            ))

        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()
        self.urun_arama_entry.setFocus()

    def _reset_form_for_new_invoice(self, skip_default_cari_selection=False): # Bu metod _reset_form_explicitly tarafından çağrılır
        self.duzenleme_id = None
        self.fatura_kalemleri_ui = []
        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()

        self.f_no_e.setText(self.db.son_fatura_no_getir(self.islem_tipi))
        self.fatura_tarihi_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        self.odeme_turu_cb.setCurrentText(self.db.ODEME_TURU_NAKIT)
        self._odeme_turu_degisince_event_handler()
        self.fatura_notlari_text.clear()
        self.genel_iskonto_tipi_cb.setCurrentText("YOK")
        self.genel_iskonto_degeri_e.setText("0,00")
        self._on_genel_iskonto_tipi_changed()

        self._temizle_cari_secimi() # Bu metod içinde cari seçimi temizleniyor
        
        # Varsayılan carileri ata (PySide6'da QComboBox.setCurrentText kullanılır)
        if self.islem_tipi == self.db.FATURA_TIP_SATIS and self.db.perakende_musteri_id is not None:
            perakende_data = self.db.musteri_getir_by_id(self.db.perakende_musteri_id)
            if perakende_data:
                self._on_cari_secildi_callback(perakende_data['id'], perakende_data['ad'])
        elif self.islem_tipi == self.db.FATURA_TIP_ALIS and self.db.genel_tedarikci_id is not None:
            genel_tedarikci_data = self.db.tedarikci_getir_by_id(self.db.genel_tedarikci_id)
            if genel_tedarikci_data:
                self._on_cari_secildi_callback(genel_tedarikci_data['id'], genel_tedarikci_data['ad'])
        else:
            self._temizle_cari_secimi() # Diğer fatura tipleri için cariyi temizle

        self.urun_arama_entry.clear()
        self.mik_e.setText("1")
        self.birim_fiyat_e.setText("0,00")
        self.stk_l.setText("-")
        self.stk_l.setStyleSheet("color: black;")
        self.iskonto_yuzde_1_e.setText("0,00")
        self.iskonto_yuzde_2_e.setText("0,00")

        self.app.set_status_message(f"Yeni {self.islem_tipi.lower()} faturası oluşturmak için sayfa sıfırlandı.")
        QTimer.singleShot(0, self._urunleri_yukle_ve_cachele_ve_goster) # UI thread'ini bloklamadan
        self.urun_arama_entry.setFocus()

    def _odeme_turu_degisince_event_handler(self): # event=None kaldırıldı
        # Bu metod sadece ilgili iki ana metodu çağırmalı
        self._odeme_turu_ve_misafir_adi_kontrol()
        self._odeme_turu_degisince_hesap_combobox_ayarla()

    def _odeme_turu_ve_misafir_adi_kontrol(self): # event=None kaldırıldı
        """
        Cari seçimine göre Misafir Adı alanının görünürlüğünü/aktifliğini ve ödeme türü seçeneklerini yönetir.
        """
        secili_cari_id_str = str(self.secili_cari_id) if self.secili_cari_id is not None else None

        # Sadece SATIŞ faturasında ve seçilen cari PERAKENDE MÜŞTERİ ise bu değişken True olur.
        is_perakende_satis = (self.islem_tipi == self.db.FATURA_TIP_SATIS and
                              str(self.secili_cari_id) is not None and
                              str(self.secili_cari_id) == str(self.db.perakende_musteri_id))

        # Misafir Adı alanını yönet
        if hasattr(self, 'misafir_adi_container_frame'):
            # Misafir alanı sadece SATIŞ faturası ve Perakende müşteri seçiliyse ve İADE modu aktif DEĞİLSE gösterilir.
            if is_perakende_satis and (not self.iade_modu_aktif): # iade_modu_aktif doğrudan bir bool
                self.misafir_adi_container_frame.setVisible(True) # Göster
                if hasattr(self, 'entry_misafir_adi'):
                    self.entry_misafir_adi.setEnabled(True)
            else:
                self.misafir_adi_container_frame.setVisible(False) # Gizle
                if hasattr(self, 'entry_misafir_adi'):
                    self.entry_misafir_adi.clear() # Misafir adını temizle
                    self.entry_misafir_adi.setEnabled(False)

        # Basitleştirilmiş Ödeme Türü Mantığı
        all_payment_values = [self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, 
                              self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, 
                              self.db.ODEME_TURU_SENET, self.db.ODEME_TURU_ACIK_HESAP]
        current_selected_odeme_turu = self.odeme_turu_cb.currentText()

        target_payment_values = []
        if is_perakende_satis:
            target_payment_values = [p for p in all_payment_values if p != self.db.ODEME_TURU_ACIK_HESAP]
        else:
            target_payment_values = all_payment_values[:]

        self.odeme_turu_cb.clear() # Mevcutları temizle
        self.odeme_turu_cb.addItems(target_payment_values) # Yenilerini ekle

        if current_selected_odeme_turu not in target_payment_values or not current_selected_odeme_turu:
            if is_perakende_satis:
                self.odeme_turu_cb.setCurrentText(self.db.ODEME_TURU_NAKIT)
            else:
                self.odeme_turu_cb.setCurrentText(self.db.ODEME_TURU_ACIK_HESAP)

        self._odeme_turu_degisince_hesap_combobox_ayarla()

    def _odeme_turu_degisince_hesap_combobox_ayarla(self): # event=None kaldırıldı
        """
        FaturaOlusturmaSayfasi'na özel: Ödeme türü seçimine göre Kasa/Banka ve Vade Tarihi alanlarını yönetir.
        """
        secili_odeme_turu = self.odeme_turu_cb.currentText()
        pesin_odeme_turleri = [self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, 
                               self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, 
                               self.db.ODEME_TURU_SENET]

        # Vade tarihi alanlarının görünürlüğünü ve aktifliğini ayarla
        if secili_odeme_turu == self.db.ODEME_TURU_ACIK_HESAP:
            self.lbl_vade_tarihi.setVisible(True)
            self.entry_vade_tarihi.setVisible(True)
            self.btn_vade_tarihi.setVisible(True)
            self.entry_vade_tarihi.setEnabled(True)
            self.btn_vade_tarihi.setEnabled(True)
            
            # Varsayılan olarak vade tarihini 30 gün sonrası olarak ayarla
            vade_tarihi_varsayilan = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            if not self.entry_vade_tarihi.text(): # Sadece boşsa varsayılan ata
                self.entry_vade_tarihi.setText(vade_tarihi_varsayilan)
        else:
            self.lbl_vade_tarihi.setVisible(False)
            self.entry_vade_tarihi.setVisible(False)
            self.btn_vade_tarihi.setVisible(False)
            self.entry_vade_tarihi.setEnabled(False)
            self.btn_vade_tarihi.setEnabled(False)
            self.entry_vade_tarihi.clear() # Vade tarihini temizle

        # Kasa/Banka alanının görünürlüğünü ve aktifliğini ayarla
        if secili_odeme_turu in pesin_odeme_turleri:
            self.islem_hesap_cb.setEnabled(True) 
            
            # Varsayılan Kasa/Banka Seçimi
            varsayilan_kb_db = self.db.get_kasa_banka_by_odeme_turu(secili_odeme_turu)

            if varsayilan_kb_db:
                varsayilan_kb_id = varsayilan_kb_db[0]
                found_and_set_default = False
                for text, id_val in self.kasa_banka_map.items():
                    if id_val == varsayilan_kb_id:
                        self.islem_hesap_cb.setCurrentText(text) # QComboBox'a metin ata
                        found_and_set_default = True
                        break

                if not found_and_set_default:
                    if self.islem_hesap_cb.count() > 0: # İlk öğe boş olabilir
                        self.islem_hesap_cb.setCurrentIndex(0) # İlk geçerli hesabı seç
                    else:
                        self.islem_hesap_cb.clear() # Temizle
            else:
                if self.islem_hesap_cb.count() > 0:
                    self.islem_hesap_cb.setCurrentIndex(0)
                else:
                    self.islem_hesap_cb.clear()

        else: # "AÇIK HESAP" veya "ETKİSİZ FATURA" seçilirse
            self.islem_hesap_cb.clear()
            self.islem_hesap_cb.setEnabled(False)

class SiparisOlusturmaSayfasi(BaseIslemSayfasi):
    def __init__(self, parent, db_manager, app_ref, islem_tipi, duzenleme_id=None, yenile_callback=None, initial_cari_id=None, initial_urunler=None, initial_data=None):
        self.iade_modu_aktif = False # PySide6'da doğrudan boolean
        self.original_fatura_id_for_iade = None # Siparişler için geçerli değil

        # initial_data'dan iade_modu gibi özel bir durum geliyorsa (fatura iadesi için)
        if initial_data and initial_data.get('iade_modu'):
            self.iade_modu_aktif = True
            self.original_fatura_id_for_iade = initial_data.get('orijinal_fatura_id')


        super().__init__(parent, db_manager, app_ref, islem_tipi, duzenleme_id, yenile_callback,
                         initial_cari_id=initial_cari_id, initial_urunler=initial_urunler, initial_data=initial_data)

        # StringDeğişkenleri (StringVar) yerine QLineEdit/QComboBox'tan doğrudan değer alınacak.
        self.sv_siparis_no = "" # QLineEdit'ten alınacak
        self.sv_siparis_tarihi = datetime.now().strftime('%Y-%m-%d') # QLineEdit'ten alınacak
        self.sv_teslimat_tarihi = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d') # QLineEdit'ten alınacak

        self.cari_id = None
        self.cari_tip = None # Musteri veya Tedarikçi
        self.perakende_musteri_id = self.db.get_perakende_musteri_id()

        self._setup_paneller() # UI panellerini oluşturur ve yerleştirir.
        self._load_initial_data() # Formu başlangıç verileriyle doldurur.

    def _get_baslik(self):
        if self.duzenleme_id:
            return "Sipariş Güncelleme"
        return "Yeni Müşteri Siparişi" if self.islem_tipi == self.db.SIPARIS_TIP_SATIS else "Yeni Tedarikçi Siparişi"

    def _setup_ozel_alanlar(self, parent_frame):
        """Ana sınıfın sol paneline siparişe özel alanları ekler ve klavye navigasyon sırasını belirler."""
        layout = QGridLayout(parent_frame)

        # Satır 0: Sipariş No ve Sipariş Tarihi
        layout.addWidget(QLabel("Sipariş No:"), 0, 0)
        self.s_no_e = QLineEdit()
        self.s_no_e.setText(self.sv_siparis_no)
        layout.addWidget(self.s_no_e, 0, 1)
        self.form_entries_order.append(self.s_no_e)

        layout.addWidget(QLabel("Sipariş Tarihi:"), 0, 2)
        self.siparis_tarihi_entry = QLineEdit()
        self.siparis_tarihi_entry.setText(self.sv_siparis_tarihi)
        layout.addWidget(self.siparis_tarihi_entry, 0, 3)
        takvim_button_siparis_tarihi = QPushButton("🗓️")
        takvim_button_siparis_tarihi.setFixedWidth(30)
        takvim_button_siparis_tarihi.clicked.connect(lambda: DatePickerDialog(self.app, self.siparis_tarihi_entry))
        layout.addWidget(takvim_button_siparis_tarihi, 0, 4)
        self.form_entries_order.append(self.siparis_tarihi_entry)

        # Satır 1: Cari Seçim
        cari_btn_label_text = "Müşteri Seç:" if self.islem_tipi == self.db.SIPARIS_TIP_SATIS else "Tedarikçi Seç:"
        layout.addWidget(QLabel(cari_btn_label_text), 1, 0)
        self.cari_sec_button = QPushButton("Cari Seç...")
        self.cari_sec_button.clicked.connect(self._cari_sec_dialog_ac)
        layout.addWidget(self.cari_sec_button, 1, 1)
        self.lbl_secili_cari_adi = QLabel("Seçilen Cari: Yok")
        self.lbl_secili_cari_adi.setFont(QFont("Segoe UI", 9, QFont.Bold))
        layout.addWidget(self.lbl_secili_cari_adi, 1, 2, 1, 3) # 1 satır, 3 sütun kapla
        self.form_entries_order.append(self.cari_sec_button)

        # Satır 2: Cari Bakiye
        self.lbl_cari_bakiye = QLabel("Bakiye: ...")
        self.lbl_cari_bakiye.setFont(QFont("Segoe UI", 9, QFont.Bold))
        layout.addWidget(self.lbl_cari_bakiye, 2, 0, 1, 2)

        # Satır 3: Teslimat Tarihi
        layout.addWidget(QLabel("Teslimat Tarihi:"), 3, 0)
        self.teslimat_tarihi_entry = QLineEdit()
        self.teslimat_tarihi_entry.setText(self.sv_teslimat_tarihi)
        layout.addWidget(self.teslimat_tarihi_entry, 3, 1)
        teslimat_takvim_button = QPushButton("🗓️")
        teslimat_takvim_button.setFixedWidth(30)
        teslimat_takvim_button.clicked.connect(lambda: DatePickerDialog(self.app, self.teslimat_tarihi_entry))
        layout.addWidget(teslimat_takvim_button, 3, 2)
        self.form_entries_order.append(self.teslimat_tarihi_entry)

        # Satır 4: Durum
        layout.addWidget(QLabel("Durum:"), 4, 0)
        self.durum_combo = QComboBox()
        self.durum_combo.addItems(["BEKLEMEDE", "TAMAMLANDI", "KISMİ_TESLİMAT", "İPTAL_EDİLDİ"])
        self.durum_combo.setCurrentText("BEKLEMEDE")
        layout.addWidget(self.durum_combo, 4, 1)
        self.form_entries_order.append(self.durum_combo)

        # Satır 5: Notlar
        layout.addWidget(QLabel("Sipariş Notları:"), 5, 0, Qt.AlignTop)
        self.siparis_notlari_text = QTextEdit()
        # self.siparis_notlari_text.setPlainText(self.sv_siparis_notlari) # Metni _mevcut_siparisi_yukle dolduracak
        layout.addWidget(self.siparis_notlari_text, 5, 1, 1, 4)
        self.form_entries_order.append(self.siparis_notlari_text)

        # Satır 6: Genel İskonto
        layout.addWidget(QLabel("Genel İskonto Tipi:"), 6, 0)
        self.genel_iskonto_tipi_cb = QComboBox()
        self.genel_iskonto_tipi_cb.addItems(["YOK", "YUZDE", "TUTAR"])
        self.genel_iskonto_tipi_cb.setCurrentText(self.sv_genel_iskonto_tipi)
        self.genel_iskonto_tipi_cb.currentIndexChanged.connect(self._on_genel_iskonto_tipi_changed)
        layout.addWidget(self.genel_iskonto_tipi_cb, 6, 1)
        self.form_entries_order.append(self.genel_iskonto_tipi_cb)

        layout.addWidget(QLabel("Genel İskonto Değeri:"), 6, 2)
        self.genel_iskonto_degeri_e = QLineEdit()
        self.genel_iskonto_degeri_e.setText(self.sv_genel_iskonto_degeri)
        self.genel_iskonto_degeri_e.setEnabled(False) # Başlangıçta pasif
        self.genel_iskonto_degeri_e.textChanged.connect(self.toplamlari_hesapla_ui)
        layout.addWidget(self.genel_iskonto_degeri_e, 6, 3)
        self.form_entries_order.append(self.genel_iskonto_degeri_e)

        # Column stretch
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

    def _load_initial_data(self):
        """
        SiparisOlusturmaSayfasi'na özel başlangıç veri yükleme mantığı.
        """
        if self.duzenleme_id:
            self._mevcut_siparisi_yukle()
            logging.debug("SiparisOlusturmaSayfasi - Düzenleme modunda, mevcut sipariş yüklendi.")
        elif self.initial_data:
            self._load_temp_form_data(forced_temp_data=self.initial_data)
            logging.debug("SiparisOlusturmaSayfasi - initial_data ile taslak veri yüklendi.")
        else:
            # Yeni bir sipariş oluşturuluyor. Önce formu sıfırla.
            self._reset_form_explicitly(ask_confirmation=False) # Sormadan sıfırla
            logging.debug("SiparisOlusturmaSayfasi - Yeni sipariş için form sıfırlandı.")
            
            # Şimdi varsayılan carileri ata.
            if self.islem_tipi == self.db.SIPARIS_TIP_SATIS:
                if self.db.perakende_musteri_id is not None:
                    perakende_data = self.db.musteri_getir_by_id(self.db.perakende_musteri_id)
                    if perakende_data:
                        self._on_cari_secildi_callback(perakende_data['id'], perakende_data['ad'])
            elif self.islem_tipi == self.db.SIPARIS_TIP_ALIS:
                if self.db.genel_tedarikci_id is not None:
                    genel_tedarikci_data = self.db.tedarikci_getir_by_id(self.db.genel_tedarikci_id)
                    if genel_tedarikci_data:
                        self._on_cari_secildi_callback(genel_tedarikci_data['id'], genel_tedarikci_data['ad'])
        
        # UI elemanları kurulduktan sonra ürünleri yükle (PySide6'da QTimer.singleShot ile)
        QTimer.singleShot(0, self._urunleri_yukle_ve_cachele_ve_goster) # UI thread'ini bloklamadan
        
        # Odaklanma (PySide6'da QLineEdit.setFocus() veya QWidget.setFocus() kullanılır)
        if hasattr(self, 'urun_arama_entry'):
            self.urun_arama_entry.setFocus()

    def kaydet(self):
        s_no = self.s_no_e.text().strip()
        durum = self.durum_combo.currentText()
        siparis_notlari = self.siparis_notlari_text.toPlainText().strip()
        teslimat_tarihi = self.teslimat_tarihi_entry.text().strip()
        genel_iskonto_tipi = self.genel_iskonto_tipi_cb.currentText()
        genel_iskonto_degeri = float(self.genel_iskonto_degeri_e.text().replace(',', '.'))

        if not s_no:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Sipariş Numarası zorunludur.")
            return
        if not self.secili_cari_id:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Lütfen bir cari seçin.")
            return
        if not self.fatura_kalemleri_ui:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Siparişte en az bir ürün olmalı.")
            return

        kalemler_to_db = []
        for k in self.fatura_kalemleri_ui:
            # Format: (urun_id, miktar, birim_fiyat(orijinal, KDV Hariç), kdv_orani, alis_fiyati(sipariş anı), iskonto1, iskonto2)
            kalem_tuple = (
                k[0],  # urun_id
                k[2],  # miktar
                k[3],  # birim_fiyat_kdv_haric (orijinal, iskontosuz)
                k[4],  # kdv_orani
                k[8],  # alis_fiyati_fatura_aninda
                k[10], # iskonto_yuzde_1
                k[11]  # iskonto_yuzde_2
            )
            kalemler_to_db.append(kalem_tuple)
            
        success, message = False, ""
        if self.duzenleme_id:
            success, message = self.db.siparis_guncelle(
                self.duzenleme_id, s_no, self.islem_tipi, self.secili_cari_id, 0, # Toplam tutar db'de hesaplanacak
                durum, kalemler_to_db, siparis_notlari, teslimat_tarihi,
                genel_iskonto_tipi, genel_iskonto_degeri
            )
        else:
            success, message = self.db.siparis_ekle(
                s_no, self.islem_tipi, self.secili_cari_id, 0, # Toplam tutar db'de hesaplanacak
                durum, kalemler_to_db, siparis_notlari, teslimat_tarihi,
                genel_iskonto_tipi, genel_iskonto_degeri
            )

        if success:
            msg_title = "Sipariş Güncellendi" if self.duzenleme_id else "Sipariş Oluşturuldu"
            QMessageBox.information(self.app, msg_title, message)
            self.app.set_status_message(message)
            if self.yenile_callback:
                self.yenile_callback()
            
            # Parent'ı kapatma (eğer bir dialog ise)
            if isinstance(self.parent(), QDialog):
                self.parent().accept() # Dialog'u kapat
            else:
                # Eğer parent direkt ana penceredeki bir sekme ise, sadece içeriği sıfırla.
                self._reset_form_explicitly(ask_confirmation=False)
        else:
            QMessageBox.critical(self.app, "Hata", message)

    def _mevcut_siparisi_yukle(self):
        siparis_ana = self.db.get_siparis_by_id(self.duzenleme_id)
        if not siparis_ana:
            QMessageBox.critical(self.app, "Hata", "Düzenlenecek sipariş bilgileri alınamadı.")
            self.parent().close() # Parent'ı kapat (QDialog ise)
            return

        # Formu doldurma...
        self.s_no_e.setEnabled(True) # NORMAL state
        self.s_no_e.setText(siparis_ana['siparis_no'])
        self.s_no_e.setEnabled(False) # DISABLED state

        self.siparis_tarihi_entry.setText(siparis_ana['tarih'])
        self.teslimat_tarihi_entry.setText(siparis_ana['teslimat_tarihi'] if siparis_ana['teslimat_tarihi'] else "")
        
        self.durum_combo.setCurrentText(siparis_ana['durum'])
        
        self.siparis_notlari_text.setPlainText(siparis_ana['siparis_notlari'] if siparis_ana['siparis_notlari'] else "")

        genel_iskonto_tipi_db = siparis_ana['genel_iskonto_tipi']
        genel_iskonto_degeri_db = siparis_ana['genel_iskonto_degeri']

        self.genel_iskonto_tipi_cb.setCurrentText(genel_iskonto_tipi_db if genel_iskonto_tipi_db else "YOK")
        self.genel_iskonto_degeri_e.setText(f"{float(genel_iskonto_degeri_db):.2f}".replace('.', ',') if genel_iskonto_degeri_db else "0,00")
        
        self._on_genel_iskonto_tipi_changed() # İskonto alanını aktif/pasif yapar

        c_id_db = siparis_ana['cari_id']
        cari_tip_for_callback = self.db.CARI_TIP_MUSTERI if siparis_ana['cari_tip'] == self.db.CARI_TIP_MUSTERI else self.db.CARI_TIP_TEDARIKCI
        cari_bilgi_for_display = self.db.musteri_getir_by_id(c_id_db) if cari_tip_for_callback == self.db.CARI_TIP_MUSTERI else self.db.tedarikci_getir_by_id(c_id_db)
        
        if cari_bilgi_for_display:
            kod_anahtari = 'kod' if 'kod' in cari_bilgi_for_display else 'tedarikci_kodu'
            display_text_for_cari = f"{cari_bilgi_for_display['ad']} (Kod: {cari_bilgi_for_display[kod_anahtari]})"
            self._on_cari_secildi_callback(c_id_db, display_text_for_cari)
        else:
            self._temizle_cari_secimi()

        siparis_kalemleri_db_list = self.db.get_siparis_kalemleri(self.duzenleme_id)
        self.fatura_kalemleri_ui.clear()
        for k_db in siparis_kalemleri_db_list:
            urun_info = self.db.stok_getir_by_id(k_db['urun_id'])
            if not urun_info: continue

            iskontolu_birim_fiyat_kdv_dahil = (k_db['kalem_toplam_kdv_dahil'] / k_db['miktar']) if k_db['miktar'] != 0 else 0.0

            self.fatura_kalemleri_ui.append((
                k_db['urun_id'], urun_info['urun_adi'], k_db['miktar'], k_db['birim_fiyat'], k_db['kdv_orani'],
                k_db['kdv_tutari'], k_db['kalem_toplam_kdv_haric'], k_db['kalem_toplam_kdv_dahil'],
                k_db['alis_fiyati_siparis_aninda'], k_db['kdv_orani'],
                k_db['iskonto_yuzde_1'], k_db['iskonto_yuzde_2'],
                "YOK", 0.0, iskontolu_birim_fiyat_kdv_dahil
            ))

        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()
        
        QTimer.singleShot(0, self._urunleri_yukle_ve_cachele_ve_goster) # UI thread'ini bloklamadan

    def _reset_form_for_new_siparis(self, skip_default_cari_selection=False):
        """
        Sipariş formundaki özel alanları yeni bir sipariş oluşturmak için sıfırlar.
        """
        next_siparis_no_prefix = "MS" if self.islem_tipi == self.db.SIPARIS_TIP_SATIS else "AS"
        generated_siparis_no = self.db.get_next_siparis_no(next_siparis_no_prefix)
        
        self.s_no_e.setText(generated_siparis_no)
        self.siparis_tarihi_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        self.teslimat_tarihi_entry.setText((datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        
        if hasattr(self, 'durum_combo'): self.durum_combo.setCurrentText(self.db.SIPARIS_DURUM_BEKLEMEDE)
        if hasattr(self, 'siparis_notlari_text'): self.siparis_notlari_text.clear()

        if hasattr(self, 'genel_iskonto_tipi_cb'): self.genel_iskonto_tipi_cb.setCurrentText(self.db.ISKONTO_TIP_YOK)
        if hasattr(self, 'genel_iskonto_degeri_e'): self.genel_iskonto_degeri_e.setText("0,00")
        if hasattr(self, '_on_genel_iskonto_tipi_changed'): self._on_genel_iskonto_tipi_changed()

        self._temizle_cari_secimi()
        if not skip_default_cari_selection:
            if self.islem_tipi == self.db.SIPARIS_TIP_SATIS and self.db.perakende_musteri_id is not None:
                perakende_data = self.db.musteri_getir_by_id(self.db.perakende_musteri_id)
                if perakende_data:
                    self._on_cari_secildi_callback(perakende_data['id'], perakende_data['ad'])
            elif self.islem_tipi == self.db.SIPARIS_TIP_ALIS and self.db.genel_tedarikci_id is not None:
                genel_tedarikci_data = self.db.tedarikci_getir_by_id(self.db.genel_tedarikci_id)
                if genel_tedarikci_data:
                    self._on_cari_secildi_callback(genel_tedarikci_data['id'], genel_tedarikci_data['ad'])
        
        # Bu çağrı, ürün listesinin yüklenmesini garanti eder.
        QTimer.singleShot(0, self._urunleri_yukle_ve_cachele_ve_goster)
        
        if hasattr(self, 'urun_arama_entry'):
            self.urun_arama_entry.setFocus()
            
    def _populate_from_initial_data_siparis(self):
        logging.debug("_populate_from_initial_data_siparis metodu çağrıldı.")
        logging.debug(f"Initial Cari ID (Sipariş): {self.initial_cari_id}")
        logging.debug(f"Initial Ürünler (Sipariş): {self.initial_urunler}")

        if self.initial_cari_id:
            selected_cari_data = None
            if self.islem_tipi == 'ALIŞ_SIPARIS':
                selected_cari_data = self.db.tedarikci_getir_by_id(self.initial_cari_id)
            elif self.islem_tipi == 'SATIŞ_SIPARIS':
                selected_cari_data = self.db.musteri_getir_by_id(self.initial_cari_id)

            if selected_cari_data:
                kod_anahtari = 'tedarikci_kodu' if 'tedarikci_kodu' in selected_cari_data else 'kod'
                display_text = f"{selected_cari_data['ad']} (Kod: {selected_cari_data[kod_anahtari]})"
                self._on_cari_secildi_callback(selected_cari_data['id'], display_text)
                self.app.set_status_message(f"Sipariş cari: {display_text} olarak önceden dolduruldu.")
            else:
                self.app.set_status_message("Önceden doldurulacak cari bulunamadı.")

        if self.initial_urunler:
            self.fatura_kalemleri_ui.clear()
            for urun_data in self.initial_urunler:
                urun_id = urun_data['id']
                miktar = urun_data['miktar']

                urun_db_info = self.db.stok_getir_by_id(urun_id)
                if not urun_db_info:
                    continue

                # Sipariş tipi Alış ise alış fiyatını, Satış ise satış fiyatını kullan
                if self.islem_tipi == 'ALIŞ_SIPARIS':
                    birim_fiyat_kdv_haric = urun_db_info['alis_fiyati_kdv_haric']
                    birim_fiyat_kdv_dahil_display = urun_db_info['alis_fiyati_kdv_dahil']
                else: # SATIŞ_SIPARIS
                    birim_fiyat_kdv_haric = urun_db_info['satis_fiyati_kdv_haric']
                    birim_fiyat_kdv_dahil_display = urun_db_info['satis_fiyati_kdv_dahil']

                self.kalem_guncelle(
                    None, miktar, birim_fiyat_kdv_dahil_display, birim_fiyat_kdv_dahil_display, 0.0, 0.0,
                    u_id=urun_id, urun_adi=urun_db_info['urun_adi']
                )

            self.sepeti_guncelle_ui()
            self.toplamlari_hesapla_ui()
            self.app.set_status_message(f"Kritik stok ürünleri sepete eklendi.")
        logging.debug("SiparisOlusturmaSayfasi - _populate_from_initial_data_siparis metodu tamamlandı.")

class BaseGelirGiderListesi(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent, db_manager, app_ref, islem_tipi):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.islem_tipi = islem_tipi # 'GELİR', 'GİDER' veya 'TÜMÜ'
        self.main_layout = QVBoxLayout(self) # Ana layout QVBoxLayout

        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)
        
        # Filtreleme alanı
        filter_frame = QFrame(self)
        filter_layout = QHBoxLayout(filter_frame)
        self.main_layout.addWidget(filter_frame)

        filter_layout.addWidget(QLabel("Başlangıç Tarihi:"))
        self.bas_tarih_entry = QLineEdit()
        self.bas_tarih_entry.setText((datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        filter_layout.addWidget(self.bas_tarih_entry)
        
        takvim_button_bas = QPushButton("🗓️")
        takvim_button_bas.setFixedWidth(30)
        takvim_button_bas.clicked.connect(lambda: DatePickerDialog(self.app, self.bas_tarih_entry))
        filter_layout.addWidget(takvim_button_bas)
 
        filter_layout.addWidget(QLabel("Bitiş Tarihi:"))
        self.bit_tarih_entry = QLineEdit()
        self.bit_tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        filter_layout.addWidget(self.bit_tarih_entry)
        
        takvim_button_bit = QPushButton("🗓️")
        takvim_button_bit.setFixedWidth(30)
        takvim_button_bit.clicked.connect(lambda: DatePickerDialog(self.app, self.bit_tarih_entry))
        filter_layout.addWidget(takvim_button_bit)

        filter_layout.addWidget(QLabel("Açıklama Ara:"))
        self.aciklama_arama_entry = QLineEdit()
        self.aciklama_arama_entry.setPlaceholderText("Açıklama ile ara...")
        self.aciklama_arama_entry.textChanged.connect(self._delayed_gg_listesi_yukle)
        filter_layout.addWidget(self.aciklama_arama_entry)

        filtrele_yenile_button = QPushButton("Filtrele ve Yenile")
        filtrele_yenile_button.clicked.connect(self.gg_listesini_yukle)
        filter_layout.addWidget(filtrele_yenile_button)
        
        # Butonlar
        button_frame_gg = QFrame(self)
        button_layout_gg = QHBoxLayout(button_frame_gg)
        self.main_layout.addWidget(button_frame_gg)

        yeni_manuel_kayit_button = QPushButton("Yeni Manuel Kayıt Ekle")
        yeni_manuel_kayit_button.clicked.connect(self.yeni_gg_penceresi_ac)
        button_layout_gg.addWidget(yeni_manuel_kayit_button)

        self.sil_button = QPushButton("Seçili Manuel Kaydı Sil")
        self.sil_button.clicked.connect(self.secili_gg_sil)
        self.sil_button.setEnabled(False) # Başlangıçta pasif
        button_layout_gg.addWidget(self.sil_button)

        # --- Gelir/Gider Listesi (QTreeWidget) ---
        tree_frame_gg = QFrame(self)
        tree_layout_gg = QVBoxLayout(tree_frame_gg)
        self.main_layout.addWidget(tree_frame_gg, 1, 0) # Ana layout'a ekleniyor
        tree_frame_gg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Sütun başlıkları
        cols_gg = ("ID", "Tarih", "Tip", "Tutar", "Açıklama", "Kaynak", "Kaynak ID", "Kasa/Banka Adı") # Sıralama güncellendi
        self.gg_tree = QTreeWidget(tree_frame_gg)
        self.gg_tree.setHeaderLabels(cols_gg)
        self.gg_tree.setColumnCount(len(cols_gg))
        self.gg_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.gg_tree.setSortingEnabled(True)
        
        # Sütun tanımlamaları
        col_defs_gg = [
            ("ID", 60, Qt.AlignRight),
            ("Tarih", 100, Qt.AlignCenter),
            ("Tip", 80, Qt.AlignCenter),
            ("Tutar", 120, Qt.AlignRight),
            ("Açıklama", 300, Qt.AlignLeft),
            ("Kaynak", 100, Qt.AlignCenter),
            ("Kaynak ID", 80, Qt.AlignCenter),
            ("Kasa/Banka Adı", 120, Qt.AlignLeft)
        ]

        for i, (col_name, width, alignment) in enumerate(col_defs_gg):
            self.gg_tree.setColumnWidth(i, width)
            self.gg_tree.headerItem().setTextAlignment(i, alignment)
            self.gg_tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
        
        self.gg_tree.header().setStretchLastSection(False)
        self.gg_tree.header().setSectionResizeMode(4, QHeaderView.Stretch) # Açıklama sütunu genişlesin

        tree_layout_gg.addWidget(self.gg_tree)
        self.gg_tree.itemSelectionChanged.connect(self.on_tree_select)

        # Sayfalama için gerekli değişkenler ve widget'lar
        self.kayit_sayisi_per_sayfa = 20
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0

        pagination_frame_gg = QFrame(self)
        pagination_layout_gg = QHBoxLayout(pagination_frame_gg)
        self.main_layout.addWidget(pagination_frame_gg)

        onceki_sayfa_button = QPushButton("Önceki Sayfa")
        onceki_sayfa_button.clicked.connect(self.onceki_sayfa)
        pagination_layout_gg.addWidget(onceki_sayfa_button)

        self.sayfa_bilgisi_label = QLabel("Sayfa 1 / 1")
        self.sayfa_bilgisi_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        pagination_layout_gg.addWidget(self.sayfa_bilgisi_label)

        sonraki_sayfa_button = QPushButton("Sonraki Sayfa")
        sonraki_sayfa_button.clicked.connect(self.sonraki_sayfa)
        pagination_layout_gg.addWidget(sonraki_sayfa_button)
        
        self.gg_listesini_yukle() # İlk yüklemeyi yap

    def on_tree_select(self): # event=None kaldırıldı
        """QTreeWidget'ta bir öğe seçildiğinde silme butonunun durumunu ayarlar."""
        selected_items = self.gg_tree.selectedItems()
        can_delete = False
        
        if selected_items:
            # QTreeWidget'ta değerlere erişim item.text(column_index) ile olur.
            # Kaynak sütunu 6. sütun (indeks 5)
            kaynak_bilgisi = selected_items[0].text(5) 
            
            # Sadece 'MANUEL' kaynaklı kayıtlar silinebilir.
            if kaynak_bilgisi == 'MANUEL':
                can_delete = True
                
        self.sil_button.setEnabled(can_delete)

    def _delayed_gg_listesi_yukle(self): # event=None kaldırıldı
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self.gg_listesini_yukle)

    def gg_listesini_yukle(self):
        self.gg_tree.clear() # QTreeWidget'ı temizle
        
        bas_t = self.bas_tarih_entry.text()
        bit_t = self.bit_tarih_entry.text()
        tip_f = self.islem_tipi if self.islem_tipi != "TÜMÜ" else None
        aciklama_f = self.aciklama_arama_entry.text().strip()

        try:
            if bas_t: datetime.strptime(bas_t, '%Y-%m-%d')
            if bit_t: datetime.strptime(bit_t, '%Y-%m-%d')
        except ValueError:
            QMessageBox.critical(self.app, "Tarih Formatı Hatası", "Tarih formati 'YYYY-AA-GG' şeklinde olmalıdır.")
            return

        offset = (self.mevcut_sayfa - 1) * self.kayit_sayisi_per_sayfa
        limit = self.kayit_sayisi_per_sayfa

        gelir_gider_kayitlari = self.db.gelir_gider_listele(
            baslangic_tarih=bas_t if bas_t else None,
            bitis_tarih=bit_t if bit_t else None,
            tip_filtre=tip_f, # 'GELİR' veya 'GİDER' veya None
            aciklama_filtre=aciklama_f,
            limit=limit,
            offset=offset
        )

        if not gelir_gider_kayitlari:
            item_qt = QTreeWidgetItem(self.gg_tree)
            item_qt.setText(0, "") # ID
            item_qt.setText(1, "") # Tarih
            item_qt.setText(2, "") # Tip
            item_qt.setText(3, "") # Tutar
            item_qt.setText(4, "Kayıt Bulunamadı") # Açıklama
            item_qt.setText(5, "") # Kaynak
            item_qt.setText(6, "") # Kaynak ID
            item_qt.setText(7, "") # Kasa/Banka Adı
            self.app.set_status_message("Hiç gelir/gider kaydı bulunamadı.")
        else:
            for gg in gelir_gider_kayitlari:
                tarih_formatted = gg['tarih'].strftime('%d.%m.%Y') if isinstance(gg['tarih'], (date, datetime)) else str(gg['tarih'])
                tutar_formatted = self.db._format_currency(gg['tutar'])
                
                item_qt = QTreeWidgetItem(self.gg_tree)
                item_qt.setText(0, str(gg['id']))
                item_qt.setText(1, tarih_formatted)
                item_qt.setText(2, gg['tip'])
                item_qt.setText(3, tutar_formatted)
                item_qt.setText(4, gg['aciklama'] if gg['aciklama'] else "-")
                item_qt.setText(5, gg['kaynak'] if gg['kaynak'] else "-")
                item_qt.setText(6, str(gg['kaynak_id']) if gg['kaynak_id'] else "-")
                item_qt.setText(7, gg['kasa_banka_adi'] if gg['kasa_banka_adi'] else "-")
                
                # Sayısal sütunlar için sıralama anahtarları
                item_qt.setData(0, Qt.UserRole, gg['id']) # ID
                item_qt.setData(3, Qt.UserRole, gg['tutar']) # Tutar

                # Kaynak ve tipe göre stil (arka plan ve metin rengi)
                if gg['kaynak'] == 'MANUEL':
                    for col_idx in range(self.gg_tree.columnCount()):
                        item_qt.setBackground(col_idx, QBrush(QColor("#DCEFFB"))) # Açık Mavi
                        item_qt.setForeground(col_idx, QBrush(QColor("navy"))) # Mavi metin
                
                if gg['tip'] == 'GELİR':
                    for col_idx in range(self.gg_tree.columnCount()):
                        item_qt.setBackground(col_idx, QBrush(QColor("#D5F5E3"))) # Açık Yeşil
                        item_qt.setForeground(col_idx, QBrush(QColor("green"))) # Yeşil metin
                elif gg['tip'] == 'GİDER':
                    for col_idx in range(self.gg_tree.columnCount()):
                        item_qt.setBackground(col_idx, QBrush(QColor("#FADBD8"))) # Açık Kırmızı
                        item_qt.setForeground(col_idx, QBrush(QColor("red"))) # Kırmızı metin
            
            # Toplam kayıt sayısını da güncelle
            self.toplam_kayit_sayisi = self.db.get_gelir_gider_count(
                baslangic_tarih=bas_t if bas_t else None,
                bitis_tarih=bit_t if bit_t else None,
                tip_filtre=tip_f,
                aciklama_filtre=aciklama_f
            )
            toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
            if toplam_sayfa == 0: toplam_sayfa = 1

            self.app.set_status_message(f"{len(gelir_gider_kayitlari)} gelir/gider kaydı listelendi. Toplam {self.toplam_kayit_sayisi} kayıt.")
            self.sayfa_bilgisi_label.setText(f"Sayfa {self.mevcut_sayfa} / {toplam_sayfa}")

        self.on_tree_select() # Buton durumlarını güncelleyin

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.gg_listesini_yukle()

    def sonraki_sayfa(self):
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0:
            toplam_sayfa = 1

        if self.mevcut_sayfa < toplam_sayfa:
            self.mevcut_sayfa += 1
            self.gg_listesini_yukle()
    
    def yeni_gg_penceresi_ac(self):
        initial_tip = self.islem_tipi if self.islem_tipi != "TÜMÜ" else "GELİR"

        # NOT: pencereler.py dosyasındaki YeniGelirGiderEklePenceresi'nin PySide6'ya dönüştürülmüş olması gerekmektedir.
        # Bu fonksiyon, YeniGelirGiderEklePenceresi'nin PySide6 versiyonu hazır olduğunda aktif olarak çalışacaktır.

        # Geçici olarak, pencereler modülünü bu fonksiyon içinde import edelim
        try:
            from pencereler import YeniGelirGiderEklePenceresi # PySide6 YeniGelirGiderEklePenceresi varsayılıyor
            
            # Yeni Gelir/Gider Ekleme penceresini başlat
            gg_ekle_penceresi = YeniGelirGiderEklePenceresi(
                self.app, # Ana uygulama penceresi (parent_app)
                self.db, # Veritabanı yöneticisi
                self.gg_listesini_yukle, # Pencere kapatıldığında listeyi yenilemek için callback
                initial_tip=initial_tip # Varsayılan işlem tipi (GELİR veya GİDER)
            )
            # Pencereyi göster
            gg_ekle_penceresi.show()
            self.app.set_status_message(f"Yeni manuel {initial_tip.lower()} kayıt penceresi açıldı.")

        except ImportError:
            QMessageBox.critical(self.app, "Hata", "YeniGelirGiderEklePenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
            self.app.set_status_message(f"Hata: Yeni manuel {initial_tip.lower()} kayıt penceresi açılamadı.")
        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Yeni manuel gelir/gider kayıt penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Yeni manuel gelir/gider kayıt penceresi açılamadı - {e}")
        
    def secili_gg_sil(self):
        selected_items = self.gg_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için listeden bir kayıt seçin.")
            return

        selected_item = selected_items[0]
        gg_id = int(selected_item.text(0)) # ID'yi al
        kaynak_bilgisi = selected_item.text(5) # Kaynak sütunu (API'de 'kaynak' alanına denk gelir)
        aciklama_gg = selected_item.text(4) # Açıklama sütunu

        # UI tarafında da kontrol edelim, API de zaten bu kontrolü yapacaktır
        if kaynak_bilgisi != 'MANUEL':
            QMessageBox.warning(self.app, "Silme Engellendi", "Sadece 'MANUEL' kaynaklı kayıtlar silinebilir.\nOtomatik oluşan kayıtlar (Fatura vb.) ilgili modüllerden yönetilmelidir.")
            return

        reply = QMessageBox.question(self.app, "Silme Onayı", 
                                     f"'{aciklama_gg}' açıklamalı manuel kaydı silmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No) # Varsayılan "Hayır" olsun
        
        if reply == QMessageBox.Yes:
            try:
                # API'ye DELETE isteği gönder
                api_url = f"http://127.0.0.1:8000/gelir_gider/{gg_id}"
                response = requests.delete(api_url)
                response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat
                
                QMessageBox.information(self.app, "Başarılı", f"Gelir/Gider kaydı başarıyla silindi: {aciklama_gg}")
                self.gg_listesini_yukle() # Listeyi yenile
                self.app.set_status_message(f"Gelir/Gider kaydı başarıyla silindi: {aciklama_gg}")

                # Kasa/Banka Yönetimi sayfasını da yenile (bakiye değiştiyse)
                if hasattr(self.app, 'kasa_banka_yonetimi_sayfasi') and hasattr(self.app.kasa_banka_yonetimi_sayfasi, 'hesap_listesini_yenile'):
                    self.app.kasa_banka_yonetimi_sayfasi.hesap_listesini_yenile()

            except requests.exceptions.RequestException as e:
                # API'den gelen hata detayını yakalamaya çalış
                error_detail = str(e)
                if e.response is not None:
                    try:
                        error_detail = e.response.json().get('detail', error_detail)
                    except ValueError: # response.json() başarısız olursa
                        pass
                QMessageBox.critical(self.app, "Hata", f"Gelir/Gider kaydı silinirken bir hata oluştu:\n{error_detail}")
                self.app.set_status_message(f"Gelir/Gider silme başarısız: {error_detail}")
        else:
            self.app.set_status_message("Gelir/Gider kaydı silme işlemi kullanıcı tarafından iptal edildi.")

class GelirListesi(BaseGelirGiderListesi):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent, db_manager, app_ref, islem_tipi='GELİR')

# GiderListesi sınıfı (Dönüştürülmüş PySide6 versiyonu)
class GiderListesi(BaseGelirGiderListesi):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent, db_manager, app_ref, islem_tipi='GİDER')

class BaseFinansalIslemSayfasi(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent, db_manager, app_ref, islem_tipi):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.islem_tipi = islem_tipi
        self.main_layout = QVBoxLayout(self) # Ana layout QVBoxLayout

        self.tum_cariler_cache = []
        self.cari_map = {} # Display text -> ID map
        self.kasa_banka_map = {} # Kasa/Banka display text -> ID map

        if self.islem_tipi == 'TAHSILAT':
            self.cari_tip = self.db.CARI_TIP_MUSTERI
        elif self.islem_tipi == 'ODEME':
            self.cari_tip = self.db.CARI_TIP_TEDARIKCI
        else:
            self.cari_tip = None

        # Başlık
        baslik_text = "Müşteriden Tahsilat Girişi" if self.islem_tipi == 'TAHSILAT' else "Tedarikçiye Ödeme Girişi"
        self.main_layout.addWidget(QLabel(baslik_text, font=QFont("Segoe UI", 16, QFont.Bold)), 
                                   alignment=Qt.AlignLeft)

        # Giriş Formu Çerçevesi
        entry_frame = QFrame(self)
        entry_layout = QGridLayout(entry_frame)
        self.main_layout.addWidget(entry_frame)
        entry_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Cari Seçimi
        cari_label_text = "Müşteri (*):" if self.islem_tipi == 'TAHSILAT' else "Tedarikçi (*):"
        entry_layout.addWidget(QLabel(cari_label_text), 0, 0, Qt.AlignLeft)

        self.cari_combo = QComboBox()
        self.cari_combo.setEditable(True) # Kullanıcının yazmasına izin ver
        self.cari_combo.setFixedWidth(250) # Genişlik ayarı
        # ComboBox'a metin yazıldığında veya seçim değiştiğinde sinyalleri bağla
        self.cari_combo.currentTextChanged.connect(self._filtre_carileri_anlik) # Yazdıkça filtrele
        self.cari_combo.activated.connect(self._on_cari_selected) # Seçim yapıldığında
        self.cari_combo.lineEdit().editingFinished.connect(self._cari_secimi_dogrula) # Odak kaybolduğunda
        entry_layout.addWidget(self.cari_combo, 0, 1, Qt.AlignLeft)

        self.lbl_cari_bakiye = QLabel("Bakiye: Yükleniyor...")
        self.lbl_cari_bakiye.setFont(QFont("Segoe UI", 10, QFont.Bold))
        entry_layout.addWidget(self.lbl_cari_bakiye, 0, 2, 1, 2, Qt.AlignLeft) # 2 sütun kapla

        # Tarih
        entry_layout.addWidget(QLabel("Tarih (*):"), 1, 0, Qt.AlignLeft)
        self.tarih_entry = QLineEdit()
        self.tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        entry_layout.addWidget(self.tarih_entry, 1, 1, Qt.AlignLeft)
        takvim_button_tarih = QPushButton("🗓️")
        takvim_button_tarih.setFixedWidth(30)
        takvim_button_tarih.clicked.connect(lambda: DatePickerDialog(self.app, self.tarih_entry))
        entry_layout.addWidget(takvim_button_tarih, 1, 2, Qt.AlignLeft)

        # Tutar
        entry_layout.addWidget(QLabel("Tutar (TL) (*):"), 2, 0, Qt.AlignLeft)
        self.tutar_entry = QLineEdit()
        self.tutar_entry.setPlaceholderText("0,00")

        # QDoubleValidator ataması: minimum 0.0, maksimum 999999999.0, 2 ondalık basamak
        tutar_validator = QDoubleValidator(0.0, 999999999.0, 2, self)
        tutar_validator.setNotation(QDoubleValidator.StandardNotation)

        self.tutar_entry.setValidator(tutar_validator)
        self.tutar_entry.textChanged.connect(lambda: self._format_numeric_line_edit(self.tutar_entry, 2))
        self.tutar_entry.editingFinished.connect(lambda: self._format_numeric_line_edit(self.tutar_entry, 2))

        entry_layout.addWidget(self.tutar_entry, 2, 1, Qt.AlignLeft)

        # Ödeme Şekli
        entry_layout.addWidget(QLabel("Ödeme Şekli (*):"), 3, 0, Qt.AlignLeft)
        self.odeme_sekli_combo = QComboBox()
        self.odeme_sekli_combo.addItems([self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, 
                                        self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, 
                                        self.db.ODEME_TURU_SENET])
        self.odeme_sekli_combo.setCurrentText(self.db.ODEME_TURU_NAKIT)
        self.odeme_sekli_combo.currentIndexChanged.connect(self._odeme_sekli_degisince) # Sinyali bağla
        entry_layout.addWidget(self.odeme_sekli_combo, 3, 1, Qt.AlignLeft)

        # İşlem Kasa/Banka
        entry_layout.addWidget(QLabel("İşlem Kasa/Banka (*):"), 4, 0, Qt.AlignLeft)
        self.kasa_banka_combo = QComboBox()
        self.kasa_banka_combo.setPlaceholderText("Kasa veya Banka seçin...")
        # Değerler _yukle_kasa_banka_hesaplarini metodunda eklenecek
        entry_layout.addWidget(self.kasa_banka_combo, 4, 1, 1, 2, Qt.AlignLeft) # 1 satır, 2 sütun kapla

        # Açıklama
        entry_layout.addWidget(QLabel("Açıklama (*):"), 5, 0, Qt.AlignTop | Qt.AlignLeft)
        self.aciklama_text = QTextEdit()
        self.aciklama_text.setPlaceholderText("Açıklama girin...")
        entry_layout.addWidget(self.aciklama_text, 5, 1, 1, 3) # 1 satır, 3 sütun kapla

        entry_layout.setColumnStretch(1, 1) # İkinci sütun genişlesin

        # Kaydet Butonu
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        self.main_layout.addWidget(button_frame)
        
        kaydet_button = QPushButton("Kaydet")
        kaydet_button.clicked.connect(self.kaydet_islem)
        button_layout.addWidget(kaydet_button, alignment=Qt.AlignCenter) # Ortala

        # Hızlı İşlem Listesi (Son İşlemler)
        recent_transactions_frame = QFrame(self)
        recent_transactions_layout = QVBoxLayout(recent_transactions_frame)
        self.main_layout.addWidget(recent_transactions_frame)
        recent_transactions_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        recent_transactions_layout.addWidget(QLabel("Son İşlemler", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignLeft)

        cols_recent = ("Tarih", "Tip", "Tutar", "Açıklama", "Kasa/Banka")
        self.tree_recent_transactions = QTreeWidget(recent_transactions_frame)
        self.tree_recent_transactions.setHeaderLabels(cols_recent)
        self.tree_recent_transactions.setColumnCount(len(cols_recent))
        self.tree_recent_transactions.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_recent_transactions.setSortingEnabled(True)
        
        # Sütun ayarları
        col_defs_recent = [
            ("Tarih", 90, Qt.AlignCenter),
            ("Tip", 70, Qt.AlignCenter),
            ("Tutar", 120, Qt.AlignRight),
            ("Açıklama", 350, Qt.AlignLeft),
            ("Kasa/Banka", 100, Qt.AlignLeft)
        ]
        for i, (col_name, width, alignment) in enumerate(col_defs_recent):
            self.tree_recent_transactions.setColumnWidth(i, width)
            self.tree_recent_transactions.headerItem().setTextAlignment(i, alignment)
            self.tree_recent_transactions.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))

        self.tree_recent_transactions.header().setStretchLastSection(False)
        self.tree_recent_transactions.header().setSectionResizeMode(3, QHeaderView.Stretch) # Açıklama sütunu genişlesin

        recent_transactions_layout.addWidget(self.tree_recent_transactions)

        # Buradaki çağrıları doğru yerlere taşıyoruz.
        # İlk yüklemede, bu metodlar tüm widgetlar tanımlandıktan sonra çağrılmalı.
        self._yukle_ve_cachele_carileri()
        self._yukle_kasa_banka_hesaplarini()

        # cari_combo boş değilse ilk öğeyi seçin.
        if self.cari_combo.count() > 0: # count() > 0 PySide'da item olup olmadığını kontrol eder.
            self.cari_combo.setCurrentIndex(0) # İlk öğeyi seç
        self._on_cari_selected() # _on_cari_selected çağrılınca _load_recent_transactions de çağrılır

        # İlk olarak ödeme şeklini tetikleyerek varsayılan kasa/bankayı ayarla
        self._odeme_sekli_degisince()
        
    def _yukle_ve_cachele_carileri(self):
        self.tum_cariler_cache = []
        self.cari_map = {} # Görünen metin -> ID map

        try:
            api_url = ""
            if self.islem_tipi == 'TAHSILAT':
                api_url = "http://127.0.0.1:8000/nitelikler/musteriler" # Müşteri listesi API endpoint'i
            elif self.islem_tipi == 'ODEME':
                api_url = "http://127.0.0.1:8000/nitelikler/tedarikciler" # Tedarikçi listesi API endpoint'i
            
            if not api_url:
                QMessageBox.critical(self.app, "Hata", "Geçersiz işlem tipi için cari listesi çekilemiyor.")
                return

            response = requests.get(api_url)
            response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat
            cariler_data = response.json() # JSON yanıtı al

            display_values = []
            for c in cariler_data: # c: Pydantic modeline göre JSON objesi
                display_text = ""
                if self.islem_tipi == 'TAHSILAT':
                    display_text = f"{c.get('ad')} (Kod: {c.get('kod')})"
                elif self.islem_tipi == 'ODEME':
                    display_text = f"{c.get('ad')} (Kod: {c.get('tedarikci_kodu')})"
                
                self.cari_map[display_text] = c.get('id')
                display_values.append(display_text)
                self.tum_cariler_cache.append(c) # Tüm cari verilerini de cache'e al

            # self.cari_combo'ya değerleri ekle
            self.cari_combo.blockSignals(True) # Sinyalleri geçici olarak engelle
            self.cari_combo.clear() # Mevcut öğeleri temizle
            self.cari_combo.addItems(display_values) # Yeni değerleri ekle
            
            # İlk seçeneği ayarlarken, listenin boş olma durumunu kontrol etmeliyiz.
            if self.cari_combo.count() > 0:
                # Perakende müşteriyi otomatik seçmemek için özel kontrol
                if self.islem_tipi == 'TAHSILAT' and self.db.perakende_musteri_id is not None:
                    perakende_musteri_display_text = None
                    for text, _id in self.cari_map.items():
                        if _id == self.db.perakende_musteri_id:
                            perakende_musteri_display_text = text
                            break
                    if perakende_musteri_display_text and perakende_musteri_display_text in display_values:
                        # Perakende müşteri varsa onu otomatik seçme, diğer ilk geçerliyi seç
                        # Veya hiçbirini seçme ve kullanıcıdan seçim bekle
                        self.cari_combo.setCurrentText("") # İlk başta hiçbirini seçme
                else:
                    self.cari_combo.setCurrentIndex(0) # İlk öğeyi seç (eğer varsa)
            else:
                self.cari_combo.clear() # Eğer hiç cari yoksa temizle

            self.cari_combo.blockSignals(False) # Sinyalleri tekrar etkinleştir

            self.app.set_status_message(f"{len(cariler_data)} cari API'den önbelleğe alındı.")
            self._on_cari_selected() # Varsayılan cariyi seçtikten sonra bakiye ve son işlemleri güncelle

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self.app, "API Bağlantı Hatası", f"Cari listesi API'den alınamadı:\n{error_detail}")
            self.app.set_status_message(f"Hata: Cari listesi yüklenemedi - {error_detail}")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Cari listesi yüklenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Cari listesi yüklenirken hata - {e}")

    def _load_recent_transactions(self):
        self.tree_recent_transactions.clear() # QTreeWidget'ı temizle

        selected_cari_text = self.cari_combo.currentText()
        cari_id = self.cari_map.get(selected_cari_text) # Seçili cari ID'sini al

        if cari_id is None:
            item_qt = QTreeWidgetItem(self.tree_recent_transactions)
            item_qt.setText(3, "Cari seçilmedi.") # Açıklama sütunu
            return

        try:
            api_url = "http://127.0.0.1:8000/cari_hareketler/"
            params = {
                'cari_id': cari_id,
                'cari_tip': self.cari_tip, # 'MUSTERI' veya 'TEDARIKCI'
                'limit': 10 # Son 10 hareketi çekelim
                # Baslangic/bitis tarihleri burada genellikle kullanılmaz, çünkü son hareketler istenir.
            }
            # None olan parametreleri temizle (örneğin cari_id None ise)
            params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

            response = requests.get(api_url, params=params)
            response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat
            recent_data = response.json() # JSON yanıtı al

            if not recent_data:
                item_qt = QTreeWidgetItem(self.tree_recent_transactions)
                item_qt.setText(3, "Son işlem bulunamadı.") # Açıklama sütunu
                return

            for item in recent_data: # item: CariHareketBase Pydantic modeline göre JSON objesi
                tarih_obj = item.get('tarih', '')
                if isinstance(tarih_obj, str):
                    try:
                        tarih_obj = datetime.strptime(tarih_obj, '%Y-%m-%d').date()
                    except ValueError:
                        pass # Hatalı tarih formatı ise string olarak kalsın

                tarih_formatted = tarih_obj.strftime('%d.%m.%Y') if isinstance(tarih_obj, (date, datetime)) else str(tarih_obj)
                tutar_formatted = self.db._format_currency(item.get('tutar', 0.0))

                item_qt = QTreeWidgetItem(self.tree_recent_transactions)
                item_qt.setText(0, tarih_formatted) # Tarih
                item_qt.setText(1, item.get('islem_tipi', '')) # Tip
                item_qt.setText(2, tutar_formatted) # Tutar
                item_qt.setText(3, item.get('aciklama', '-') if item.get('aciklama') else "-") # Açıklama
                item_qt.setText(4, item.get('kasa_banka_adi', '-') if item.get('kasa_banka_adi') else "-") # Kasa/Banka Adı

                # Sayısal sütunlar için sıralama anahtarları
                item_qt.setData(2, Qt.UserRole, item.get('tutar', 0.0)) # Tutar (sayısal)
            
            self.app.set_status_message(f"Son {len(recent_data)} cari hareketi yüklendi.")

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self.app, "API Bağlantı Hatası", f"Son cari hareketler API'den alınamadı:\n{error_detail}")
            self.app.set_status_message(f"Hata: Son cari hareketler yüklenemedi - {error_detail}")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Son cari hareketler yüklenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Son cari hareketler yüklenirken hata - {e}")

    def _filtre_carileri_anlik(self, text): # text textChanged sinyalinden gelir
        """
        Cari arama combobox'ına yazıldıkça cari listesini anlık olarak filtreler.
        Arama terimine göre eşleşen carileri Combobox'ın item'larına atar.
        """
        arama_terimi = text.lower().strip() # Kullanıcının girdiği metni al

        self.cari_combo.blockSignals(True) # Sinyalleri geçici olarak engelle

        self.cari_combo.clear() # Mevcut öğeleri temizle

        filtered_display_values = [
            display_text for display_text in self.cari_map.keys()
            if arama_terimi in display_text.lower()
        ]
        
        self.cari_combo.addItems(sorted(filtered_display_values))

        # Eğer arama terimi tam bir eşleşmeyse, otomatik seç
        exact_match_found = False
        if arama_terimi: # Arama terimi boş değilse
            for i in range(self.cari_combo.count()):
                if self.cari_combo.itemText(i).lower() == arama_terimi:
                    self.cari_combo.setCurrentIndex(i)
                    exact_match_found = True
                    break
        
        if not exact_match_found and self.cari_combo.count() > 0:
            self.cari_combo.setCurrentIndex(0) # İlk öğeyi seç

        self.cari_combo.blockSignals(False) # Sinyalleri tekrar etkinleştir

    def _odeme_sekli_degisince(self): # event=None kaldırıldı
        selected_odeme_sekli = self.odeme_sekli_combo.currentText()
        varsayilan_kb_db = self.db.get_kasa_banka_by_odeme_turu(selected_odeme_sekli)

        self.kasa_banka_combo.blockSignals(True) # Sinyalleri geçici olarak engelle
        self.kasa_banka_combo.clear() # Tüm öğeleri temizle

        display_values_kb = []
        hesaplar = self.db.kasa_banka_listesi_al()
        for h_id, h_ad, h_no, h_bakiye, h_para_birimi, h_tip, h_acilis_tarihi, h_banka, h_sube_adi, h_varsayilan_odeme_turu in hesaplar:
            display_text = f"{h_ad} ({h_tip})"
            if h_tip == "BANKA" and h_banka: display_text += f" - {h_banka}"
            if h_tip == "BANKA" and h_no: display_text += f" ({h_no})"
            self.kasa_banka_map[display_text] = h_id
            display_values_kb.append(display_text)
        
        self.kasa_banka_combo.addItems(display_values_kb) # QComboBox'a öğeleri ekle

        if varsayilan_kb_db:
            varsayilan_kb_id = varsayilan_kb_db[0]
            found_and_set = False
            for i in range(self.kasa_banka_combo.count()):
                item_text = self.kasa_banka_combo.itemText(i)
                if self.kasa_banka_map.get(item_text) == varsayilan_kb_id:
                    self.kasa_banka_combo.setCurrentIndex(i)
                    found_and_set = True
                    break
            if not found_and_set and self.kasa_banka_combo.count() > 0:
                self.kasa_banka_combo.setCurrentIndex(0)
        elif self.kasa_banka_combo.count() > 0:
            self.kasa_banka_combo.setCurrentIndex(0)
        else:
            self.kasa_banka_combo.clear()

        self.kasa_banka_combo.blockSignals(False) # Sinyalleri tekrar etkinleştir

    def _cari_secimi_dogrula(self): # event=None kaldırıldı
        current_text = self.cari_combo.currentText().strip()
        if current_text and current_text not in self.cari_map:
            QMessageBox.warning(self.app, "Geçersiz Cari", "Seçili müşteri/tedarikçi listede bulunamadı.\nLütfen listeden geçerli bir seçim yapın veya yeni bir cari ekleyin.")
            self.cari_combo.clear()
            self.lbl_cari_bakiye.setText("")
            self.lbl_cari_bakiye.setStyleSheet("color: black;")
        self._on_cari_selected()

    def _on_cari_selected(self): # event=None kaldırıldı
        selected_cari_text = self.cari_combo.currentText()
        secilen_cari_id = self.cari_map.get(selected_cari_text)

        bakiye_text = ""
        bakiye_color = "black"

        if secilen_cari_id:
            cari_id_int = int(secilen_cari_id)
            if self.cari_tip == self.db.CARI_TIP_MUSTERI:
                net_bakiye = self.db.get_musteri_net_bakiye(cari_id_int)
                if net_bakiye > 0:
                    bakiye_text = f"Borç: {self.db._format_currency(net_bakiye)}"
                    bakiye_color = "red"
                elif net_bakiye < 0:
                    bakiye_text = f"Alacak: {self.db._format_currency(abs(net_bakiye))}"
                    bakiye_color = "green"
                else:
                    bakiye_text = "Bakiye: 0,00 TL"
                    bakiye_color = "black"
            elif self.cari_tip == self.db.CARI_TIP_TEDARIKCI:
                net_bakiye = self.db.get_tedarikci_net_bakiye(cari_id_int)
                if net_bakiye > 0:
                    bakiye_text = f"Borç: {self.db._format_currency(net_bakiye)}"
                    bakiye_color = "red"
                elif net_bakiye < 0:
                    bakiye_text = f"Alacak: {self.db._format_currency(abs(net_bakiye))}"
                    bakiye_color = "green"
                else:
                    bakiye_text = "Bakiye: 0,00 TL"
                    bakiye_color = "black"
            self.lbl_cari_bakiye.setText(bakiye_text)
            self.lbl_cari_bakiye.setStyleSheet(f"color: {bakiye_color};")
        else:
            self.lbl_cari_bakiye.setText("")
            self.lbl_cari_bakiye.setStyleSheet("color: black;")

        self._load_recent_transactions() # Seçim değişince son işlemleri de yükle

    def _yukle_carileri(self): # Bu metod FaturaOlusturmaSayfasi'ndan _cari_secim_dialog_ac içinde çağrılıyor.
        self.tum_cariler_cache_data = []
        self.cari_map_display_to_id = {}
        
        if self.fatura_tipi == 'SATIŞ': # Fatura tipi burada bu metoda gelmez. islem_tipi veya cari_tip'e göre belirlenmeli.
            cariler_db = self.db.musteri_listesi_al(perakende_haric=False)
        else: # ALIŞ
            cariler_db = self.db.tedarikci_listesi_al()
        
        for c in cariler_db:
            cari_id = c['id']
            cari_ad = c['ad']
            
            cari_kodu = c['kod'] if 'kod' in c else c['tedarikci_kodu']
            
            display_text = f"{cari_ad} (Kod: {cari_kodu})"
            self.cari_map_display_to_id[display_text] = str(cari_id)
            self.tum_cariler_cache_data.append(c)

    def _yukle_kasa_banka_hesaplarini(self):
        """Kasa/Banka hesaplarını veritabanından çeker ve ilgili combobox'ı doldurur."""
        self.kasa_banka_combo.clear() # Tüm öğeleri temizle
        self.kasa_banka_map.clear() # Map'i temizle
        hesaplar = self.db.kasa_banka_listesi_al()
        
        display_values = []
        if hesaplar:
            for h_id, h_ad, h_no, h_bakiye, h_para_birimi, h_tip, h_acilis_tarihi, h_banka, h_sube_adi, h_varsayilan_odeme_turu in hesaplar:
                display_text = f"{h_ad} ({h_tip})"
                if h_tip == "BANKA" and h_banka: display_text += f" - {h_banka}"
                if h_tip == "BANKA" and h_no: display_text += f" ({h_no})"
                self.kasa_banka_map[display_text] = h_id
                display_values.append(display_text)
            self.kasa_banka_combo.addItems(display_values)
            self.kasa_banka_combo.setCurrentIndex(0) # İlk öğeyi seç
        else:
            self.kasa_banka_combo.clear() # Temizle
            self.kasa_banka_combo.setPlaceholderText("Hesap Yok")
            self.kasa_banka_combo.setEnabled(False) # Pasif yap

    def kaydet_islem(self):
        selected_cari_str = self.cari_combo.currentText().strip()
        tarih_str = self.tarih_entry.text().strip()
        tutar_str = self.tutar_entry.text().strip()
        odeme_sekli_str = self.odeme_sekli_combo.currentText()
        aciklama_str = self.aciklama_text.toPlainText().strip()
        selected_kasa_banka_str = self.kasa_banka_combo.currentText()

        cari_id_val = None
        if selected_cari_str and selected_cari_str in self.cari_map:
            cari_id_val = self.cari_map.get(selected_cari_str)
        else:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Lütfen geçerli bir müşteri/tedarikçi seçin.")
            return

        kasa_banka_id_val = None
        if selected_kasa_banka_str and selected_kasa_banka_str != "Hesap Yok" and selected_kasa_banka_str in self.kasa_banka_map:
            kasa_banka_id_val = self.kasa_banka_map.get(selected_kasa_banka_str)
        else:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Lütfen bir İşlem Kasa/Banka hesabı seçin.")
            return

        if not all([tarih_str, tutar_str, odeme_sekli_str, aciklama_str]):
            QMessageBox.critical(self.app, "Eksik Bilgi", "Lütfen tüm zorunlu (*) alanları doldurun.")
            return

        try:
            tutar_f = float(tutar_str.replace(',', '.'))
            if tutar_f <= 0:
                QMessageBox.critical(self.app, "Geçersiz Tutar", "Tutar pozitif bir sayı olmalıdır.")
                return
        except ValueError:
            QMessageBox.critical(self.app, "Giriş Hatası", "Tutar sayısal bir değer olmalıdır.")
            return
        
        # API'ye gönderilecek veri hazırlığı
        gelir_gider_data = {
            "tarih": tarih_str,
            "tip": self.islem_tipi, # 'TAHSILAT' veya 'ODEME'
            "tutar": tutar_f,
            "aciklama": aciklama_str,
            "kaynak": "MANUEL", # Bu tür işlemler manuel olarak kaydedilir
            "kasa_banka_id": kasa_banka_id_val
            # Diğer alanlar API tarafından yönetilebilir (örn: gelir_siniflandirma_id, gider_siniflandirma_id)
        }

        try:
            api_url = "http://127.0.0.1:8000/gelir_gider/"
            response = requests.post(api_url, json=gelir_gider_data)
            response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat
            
            # API'den dönen başarılı yanıtı al (genellikle oluşturulan nesne)
            kaydedilen_islem = response.json()
            
            QMessageBox.information(self.app, "Başarılı", f"İşlem başarıyla kaydedildi: {kaydedilen_islem.get('aciklama')}")
            
            # İlişkili cari hareketleri de güncelleyelim (bu kısım db_manager.tahsilat_ekle veya odeme_ekle içinde yapılır)
            # Şu an API'ye direkt gelir/gider kaydı atıyoruz. Cari hareketin de oluşması için
            # API'de ayrı bir endpoint veya servis tarafında entegrasyon gerekecek.
            # Şimdilik, sadece gelir/gider tablosuna yazıyoruz.

            # Formu temizle
            self.cari_combo.clear() # Combobox'ı temizle
            self.tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
            self.tutar_entry.clear()
            self.odeme_sekli_combo.setCurrentText(self.db.ODEME_TURU_NAKIT)
            self.aciklama_text.clear()
            # Kasa/Banka combobox'ını da varsayılanına sıfırlayalım
            self._odeme_sekli_degisince() # Bu metod aynı zamanda kasa/bankayı da sıfırlar
            self.cari_combo.setFocus() # Odakla

            # İlgili listeleri yenile
            if hasattr(self.app, 'gelir_gider_sayfasi'):
                if hasattr(self.app.gelir_gider_sayfasi, 'gelir_listesi_frame'): self.app.gelir_gider_sayfasi.gelir_listesi_frame.gg_listesini_yukle()
                if hasattr(self.app.gelir_gider_sayfasi, 'gider_listesi_frame'): self.app.gelir_gider_sayfasi.gider_listesi_frame.gg_listesini_yukle()
            if hasattr(self.app, 'kasa_banka_yonetimi_sayfasi') and hasattr(self.app.kasa_banka_yonetimi_sayfasi, 'hesap_listesini_yenile'):
                self.app.kasa_banka_yonetimi_sayfasi.hesap_listesini_yenile()
            
            # Cari bakiyeyi ve son işlemleri güncelle
            self._on_cari_selected() 
            self.app.set_status_message(f"Finansal işlem başarıyla kaydedildi.")

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self.app, "Hata", f"Finansal işlem kaydedilirken bir hata oluştu:\n{error_detail}")
            self.app.set_status_message(f"Hata: Finansal işlem kaydedilemedi - {error_detail}")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Finansal işlem kaydedilirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Finansal işlem kaydedilirken hata - {e}")

class TahsilatSayfasi(BaseFinansalIslemSayfasi):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent, db_manager, app_ref, islem_tipi='TAHSILAT')

# OdemeSayfasi sınıfı (Dönüştürülmüş PySide6 versiyonu)
class OdemeSayfasi(BaseFinansalIslemSayfasi):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent, db_manager, app_ref, islem_tipi='ODEME')

class RaporlamaMerkeziSayfasi(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.main_layout = QVBoxLayout(self) # Ana layout QVBoxLayout

        # --- Temel Sınıf Özellikleri ---
        self.aylik_satis_verileri = []
        self.aylik_gelir_gider_verileri = []
        self.aylik_kar_maliyet_verileri = []
        self.aylik_nakit_akis_verileri = []
        self.top_satis_urunleri = []
        self.cari_yaslandirma_data = {'musteri_alacaklari': {}, 'tedarikci_borclari': {}}
        self.stok_envanter_ozet = []

        # --- Ana UI Elemanları ---
        self.main_layout.addWidget(QLabel("Finansal Raporlar ve Analiz Merkezi", font=QFont("Segoe UI", 22, QFont.Bold)), 
                                   alignment=Qt.AlignLeft)

        # Filtreleme ve Rapor Oluşturma Kontrolleri (Üst kısımda her zaman görünür)
        filter_control_frame = QFrame(self)
        filter_control_layout = QHBoxLayout(filter_control_frame)
        self.main_layout.addWidget(filter_control_frame)

        filter_control_layout.addWidget(QLabel("Başlangıç Tarihi:"))
        self.bas_tarih_entry = QLineEdit()
        self.bas_tarih_entry.setText((datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        filter_control_layout.addWidget(self.bas_tarih_entry)
        
        takvim_button_bas = QPushButton("🗓️")
        takvim_button_bas.setFixedWidth(30)
        takvim_button_bas.clicked.connect(lambda: DatePickerDialog(self.app, self.bas_tarih_entry))
        filter_control_layout.addWidget(takvim_button_bas)

        filter_control_layout.addWidget(QLabel("Bitiş Tarihi:"))
        self.bit_tarih_entry = QLineEdit()
        self.bit_tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        filter_control_layout.addWidget(self.bit_tarih_entry)
        
        takvim_button_bit = QPushButton("🗓️")
        takvim_button_bit.setFixedWidth(30)
        takvim_button_bit.clicked.connect(lambda: DatePickerDialog(self.app, self.bit_tarih_entry))
        filter_control_layout.addWidget(takvim_button_bit)

        rapor_olustur_yenile_button = QPushButton("Rapor Oluştur/Yenile")
        rapor_olustur_yenile_button.clicked.connect(self.raporu_olustur_ve_yenile)
        filter_control_layout.addWidget(rapor_olustur_yenile_button)

        rapor_yazdir_pdf_button = QPushButton("Raporu Yazdır (PDF)")
        rapor_yazdir_pdf_button.clicked.connect(self.raporu_pdf_yazdir_placeholder)
        filter_control_layout.addWidget(rapor_yazdir_pdf_button)

        rapor_disa_aktar_excel_button = QPushButton("Raporu Dışa Aktar (Excel)")
        rapor_disa_aktar_excel_button.clicked.connect(self.raporu_excel_aktar_placeholder)
        filter_control_layout.addWidget(rapor_disa_aktar_excel_button)


        # Rapor sekmeleri için ana QTabWidget
        self.report_notebook = QTabWidget(self)
        self.main_layout.addWidget(self.report_notebook)

        # Sekme 1: Genel Bakış (Dashboard)
        self.tab_genel_bakis = QWidget(self.report_notebook)
        self.report_notebook.addTab(self.tab_genel_bakis, "📊 Genel Bakış")
        self._create_genel_bakis_tab(self.tab_genel_bakis)

        # Sekme 2: Satış Raporları
        self.tab_satis_raporlari = QWidget(self.report_notebook)
        self.report_notebook.addTab(self.tab_satis_raporlari, "📈 Satış Raporları")
        self._create_satis_raporlari_tab(self.tab_satis_raporlari)

        # Sekme 3: Kâr ve Zarar
        self.tab_kar_zarar = QWidget(self.report_notebook)
        self.report_notebook.addTab(self.tab_kar_zarar, "💰 Kâr ve Zarar")
        self._create_kar_zarar_tab(self.tab_kar_zarar)

        # Sekme 4: Nakit Akışı
        self.tab_nakit_akisi = QWidget(self.report_notebook)
        self.report_notebook.addTab(self.tab_nakit_akisi, "🏦 Nakit Akışı")
        self._create_nakit_akisi_tab(self.tab_nakit_akisi)

        # Sekme 5: Cari Hesap Raporları
        self.tab_cari_hesaplar = QWidget(self.report_notebook)
        self.report_notebook.addTab(self.tab_cari_hesaplar, "👥 Cari Hesaplar")
        self._create_cari_hesaplar_tab(self.tab_cari_hesaplar)

        # Sekme 6: Stok Raporları
        self.tab_stok_raporlari = QWidget(self.report_notebook)
        self.report_notebook.addTab(self.tab_stok_raporlari, "📦 Stok Raporları")
        self._create_stok_raporlari_tab(self.tab_stok_raporlari)

        # Rapor notebook sekmesi değiştiğinde güncellemeleri tetikle
        self.report_notebook.currentChanged.connect(self._on_tab_change)

        # Başlangıçta raporları oluştur (Bu, ilk sekmenin içeriğini yükler)
        self.raporu_olustur_ve_yenile()

    # --- Ortak Yardımcı Metotlar ---
    def _open_date_picker(self, target_entry_qlineedit): # QLineEdit objesi alacak
        """
        PySide6 DatePickerDialog'u açar ve seçilen tarihi target_entry_qlineedit'e yazar.
        """
        # DatePickerDialog'un yeni PySide6 versiyonunu kullanıyoruz.
        # (yardimcilar.py'den import edildiğinden emin olun)
        from yardimcilar import DatePickerDialog # PySide6 DatePickerDialog

        # Mevcut tarihi al (eğer varsa) ve diyaloğa gönder
        initial_date_str = target_entry_qlineedit.text() if target_entry_qlineedit.text() else None

        dialog = DatePickerDialog(self.app, initial_date_str) # parent: self.app (ana uygulama penceresi)

        # Diyalogtan tarih seçildiğinde (date_selected sinyali)
        # QLineEdit'in setText metoduna bağlanır.
        dialog.date_selected.connect(target_entry_qlineedit.setText)

        # Diyaloğu modal olarak çalıştır
        dialog.exec()

    def _draw_plot(self, parent_frame, canvas_obj, ax_obj, title, labels, values, plot_type='bar', colors=None, bar_width=0.8, rotation=0, show_legend=True, label_prefix="", show_labels_on_bars=False, tight_layout_needed=True, group_labels=None):
        # Mevcut grafiği temizle (eğer varsa)
        if canvas_obj:
            canvas_obj.deleteLater() # PySide6'da widget'ı silmek için deleteLater kullanılır
            plt.close(ax_obj.figure)

        parent_width = parent_frame.width() # QWidget'ın genişliğini al
        parent_height = parent_frame.height() # QWidget'ın yüksekliğini al

        if parent_width < 100: parent_width = 400
        if parent_height < 100: parent_height = 300

        my_dpi = 100
        fig = Figure(figsize=(parent_width/my_dpi, parent_height/my_dpi), dpi=my_dpi)
        ax = fig.add_subplot(111)

        ax.clear()
        ax.set_title(title, fontsize=10)

        is_data_empty = False
        if plot_type == 'bar':
            if not values or (isinstance(values, list) and all(v == 0 for v in values)):
                is_data_empty = True
        elif plot_type == 'pie':
            valid_values_for_pie = [v for v in values if v != 0]
            if not valid_values_for_pie:
                is_data_empty = True
        elif plot_type == 'grouped_bar':
            if not values or all(not sub_list or all(v == 0 for v in sub_list) for sub_list in values):
                is_data_empty = True

        if is_data_empty:
            ax.text(0.5, 0.5, "Gösterilecek Veri Yok", horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=12)
            ax.set_xticks([])
            ax.set_yticks([])
            
            canvas = FigureCanvas(fig) # PySide6 için FigureCanvas
            parent_frame.layout().addWidget(canvas) # Layout'a ekle
            canvas.draw()
            return canvas, ax

        # Veri doluysa çizim yap
        if plot_type == 'bar':
            bar_label = group_labels[0] if group_labels and len(group_labels) > 0 else title
            bars = ax.bar(labels, values, color=colors if colors else 'skyblue', width=bar_width, label=bar_label)

            ax.set_ylabel("Tutar (TL)", fontsize=8)
            ax.tick_params(axis='x', rotation=rotation, labelsize=7)
            ax.tick_params(axis='y', labelsize=7)
            if show_legend and any(v != 0 for v in values):
                ax.legend(fontsize=7)

            if show_labels_on_bars:
                for bar in bars:
                    yval = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2, yval + (max(values)*0.01 if values and max(values) !=0 else 0.01), f"{label_prefix}{yval:,.0f}", ha='center', va='bottom', fontsize=6, weight='bold')

            if tight_layout_needed:
                fig.tight_layout()

        elif plot_type == 'pie':
            valid_labels = [labels[i] for i, val in enumerate(values) if val != 0]
            valid_values = [val for val in values if val != 0]

            wedges, texts, autotexts = ax.pie(valid_values, labels=valid_labels, autopct='%1.1f%%', startangle=90, colors=colors if colors else plt.cm.Paired.colors)
            ax.axis('equal')
            plt.setp(autotexts, size=8, weight="bold")
            plt.setp(texts, size=9)
            fig.tight_layout()

        elif plot_type == 'grouped_bar':
            num_groups = len(values)
            num_bars_per_group = len(labels)

            bar_width_per_group = bar_width / num_groups
            ind = np.arange(num_bars_per_group)

            has_non_zero_data_in_groups = any(any(v_sub != 0 for v_sub in sub_list) for sub_list in values)

            if show_legend and has_non_zero_data_in_groups:
                for i, group_values in enumerate(values):
                    ax.bar(ind + i * bar_width_per_group, group_values, width=bar_width_per_group,
                           label=group_labels[i] if group_labels and len(group_labels) > i else f'Grup {i+1}',
                           color=colors[i] if isinstance(colors, list) and len(colors) > i else None)
                ax.legend(fontsize=7)

            ax.set_xticks(ind + (num_groups * bar_width_per_group - bar_width_per_group) / 2)
            ax.set_xticklabels(labels, rotation=rotation, ha='right', fontsize=7)
            ax.set_ylabel("Tutar (TL)", fontsize=8)
            ax.tick_params(axis='y', labelsize=7)
            fig.tight_layout()

        canvas = FigureCanvas(fig) # PySide6 için FigureCanvas
        parent_frame.layout().addWidget(canvas) # Layout'a ekle
        canvas.draw()

        return canvas, ax
        
    # --- Rapor Sekmelerinin Oluşturma Metotları ---
    def _create_genel_bakis_tab(self, parent_frame):
        parent_layout = QGridLayout(parent_frame) # Parent frame'e layout ata
        parent_layout.setColumnStretch(0, 1)
        parent_layout.setColumnStretch(1, 1)
        parent_layout.setRowStretch(1, 1) # Grafik dikeyde genişlesin

        metrics_frame = QFrame(parent_frame)
        metrics_layout = QGridLayout(metrics_frame)
        parent_layout.addWidget(metrics_frame, 0, 0, 1, 2) # Row 0, Col 0, span 1 row, 2 cols
        metrics_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # Genişlesin, yükseklik sabit
        
        for i in range(4): # 4 metrik için
            metrics_layout.setColumnStretch(i, 1)

        self.card_total_sales = self._create_metric_card(metrics_frame, "Toplam Satış (KDV Dahil)", "0.00 TL", "sales")
        metrics_layout.addWidget(self.card_total_sales, 0, 0)

        self.card_total_collections = self._create_metric_card(metrics_frame, "Toplam Tahsilat", "0.00 TL", "collections")
        metrics_layout.addWidget(self.card_total_collections, 0, 1)

        self.card_total_payments = self._create_metric_card(metrics_frame, "Toplam Ödeme", "0.00 TL", "payments")
        metrics_layout.addWidget(self.card_total_payments, 0, 2)

        self.card_net_cash_flow = self._create_metric_card(metrics_frame, "Net Nakit Akışı", "0.00 TL", "net_cash")
        metrics_layout.addWidget(self.card_net_cash_flow, 0, 3)

        self.genel_bakis_grafik_frame = QFrame(parent_frame)
        self.genel_bakis_grafik_layout = QVBoxLayout(self.genel_bakis_grafik_frame) # Grafik çerçevesi layout'u
        self.genel_bakis_grafik_layout.addWidget(QLabel("Aylık Finansal Trendler (Satış, Gelir, Gider)", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignLeft)
        parent_layout.addWidget(self.genel_bakis_grafik_frame, 1, 0, 1, 2) # Row 1, Col 0, span 1 row, 2 cols
        self.genel_bakis_grafik_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.canvas_genel_bakis_main_plot = None
        self.ax_genel_bakis_main_plot = None

    def _create_metric_card(self, parent_frame, title, initial_value, card_type):
        """Metrik kartları için ortak bir çerçeve ve label oluşturur."""
        card_frame = QFrame(parent_frame)
        card_frame.setFrameShape(QFrame.StyledPanel)
        card_frame.setFrameShadow(QFrame.Raised)
        card_frame.setLineWidth(2)
        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(15, 15, 15, 15)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title_label)

        value_label = QLabel(initial_value)
        value_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        value_label.setStyleSheet("color: navy;")
        value_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(value_label)

        setattr(self, f"lbl_metric_{card_type}", value_label)

        return card_frame
            
    def _create_satis_raporlari_tab(self, parent_frame):
        parent_layout = QGridLayout(parent_frame)
        parent_layout.setColumnStretch(0, 2)
        parent_layout.setColumnStretch(1, 1)
        parent_layout.setRowStretch(1, 1)

        parent_layout.addWidget(QLabel("Detaylı Satış Raporları ve Analizi", font=QFont("Segoe UI", 16, QFont.Bold)), 0, 0, 1, 2, Qt.AlignLeft)

        left_panel = QFrame(parent_frame)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Satış Faturası Kalem Detayları", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignLeft)
        parent_layout.addWidget(left_panel, 1, 0)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols_satis_detay = ("Fatura No", "Tarih", "Cari Adı", "Ürün Adı", "Miktar", "Birim Fiyat", "Toplam (KDV Dahil)")
        self.tree_satis_detay = QTreeWidget(left_panel)
        self.tree_satis_detay.setHeaderLabels(cols_satis_detay)
        self.tree_satis_detay.setColumnCount(len(cols_satis_detay))
        self.tree_satis_detay.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_satis_detay.setSortingEnabled(True)

        col_widths_satis_detay = {
            "Fatura No": 80, "Tarih": 70, "Cari Adı": 120, "Ürün Adı": 180, 
            "Miktar": 60, "Birim Fiyat": 90, "Toplam (KDV Dahil)": 100
        }
        for i, col_name in enumerate(cols_satis_detay):
            self.tree_satis_detay.setColumnWidth(i, col_widths_satis_detay.get(col_name, 100))
            if col_name == "Ürün Adı":
                self.tree_satis_detay.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                self.tree_satis_detay.header().setSectionResizeMode(i, QHeaderView.Interactive)
            self.tree_satis_detay.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name in ["Tarih", "Miktar", "Birim Fiyat", "Toplam (KDV Dahil)"]:
                self.tree_satis_detay.headerItem().setTextAlignment(i, Qt.AlignCenter if col_name == "Tarih" else Qt.AlignRight)
            else:
                self.tree_satis_detay.headerItem().setTextAlignment(i, Qt.AlignLeft)
        
        left_layout.addWidget(self.tree_satis_detay)

        right_panel = QFrame(parent_frame)
        right_layout = QVBoxLayout(right_panel)
        parent_layout.addWidget(right_panel, 1, 1)
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.satis_odeme_dagilimi_frame = QFrame(right_panel)
        self.satis_odeme_dagilimi_layout = QVBoxLayout(self.satis_odeme_dagilimi_frame)
        self.satis_odeme_dagilimi_layout.addWidget(QLabel("Ödeme Türlerine Göre Satış Dağılımı", font=QFont("Segoe UI", 10, QFont.Bold)))
        right_layout.addWidget(self.satis_odeme_dagilimi_frame)
        self.satis_odeme_dagilimi_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas_satis_odeme_dagilimi = None
        self.ax_satis_odeme_dagilimi = None

        self.en_cok_satan_urunler_frame = QFrame(right_panel)
        self.en_cok_satan_urunler_layout = QVBoxLayout(self.en_cok_satan_urunler_frame)
        self.en_cok_satan_urunler_layout.addWidget(QLabel("En Çok Satan Ürünler (Miktar)", font=QFont("Segoe UI", 10, QFont.Bold)))
        right_layout.addWidget(self.en_cok_satan_urunler_frame)
        self.en_cok_satan_urunler_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas_en_cok_satan = None
        self.ax_en_cok_satan = None

    def _create_kar_zarar_tab(self, parent_frame):
        parent_layout = QGridLayout(parent_frame)
        parent_layout.setColumnStretch(0, 1)
        parent_layout.setColumnStretch(1, 1)
        parent_layout.setRowStretch(1, 1)

        left_panel = QFrame(parent_frame)
        left_layout = QVBoxLayout(left_panel)
        parent_layout.addWidget(left_panel, 0, 0, 2, 1) # Row 0, Col 0, span 2 rows, 1 col
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        row_idx = 0
        left_layout.addWidget(QLabel("Dönem Brüt Kâr (Satış Geliri - Satılan Malın Maliyeti):", font=QFont("Segoe UI", 12, QFont.Bold)), alignment=Qt.AlignLeft)
        self.lbl_brut_kar = QLabel("0.00 TL")
        self.lbl_brut_kar.setFont(QFont("Segoe UI", 20))
        left_layout.addWidget(self.lbl_brut_kar, alignment=Qt.AlignLeft)
        row_idx += 2

        left_layout.addWidget(QLabel("Dönem Brüt Kâr Oranı:", font=QFont("Segoe UI", 16, QFont.Bold)), alignment=Qt.AlignLeft)
        self.lbl_brut_kar_orani = QLabel("%0.00")
        self.lbl_brut_kar_orani.setFont(QFont("Segoe UI", 20))
        left_layout.addWidget(self.lbl_brut_kar_orani, alignment=Qt.AlignLeft)
        row_idx += 2

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        left_layout.addWidget(separator)
        row_idx += 1

        left_layout.addWidget(QLabel("Dönem Satılan Malın Maliyeti (COGS - Alış Fiyatı Üzerinden):", font=QFont("Segoe UI", 16, QFont.Bold)), alignment=Qt.AlignLeft)
        self.lbl_cogs = QLabel("0.00 TL")
        self.lbl_cogs.setFont(QFont("Segoe UI", 20))
        left_layout.addWidget(self.lbl_cogs, alignment=Qt.AlignLeft)

        self.kar_zarar_grafik_frame = QFrame(parent_frame)
        self.kar_zarar_grafik_layout = QVBoxLayout(self.kar_zarar_grafik_frame)
        self.kar_zarar_grafik_layout.addWidget(QLabel("Aylık Kâr ve Maliyet Karşılaştırması", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignLeft)
        parent_layout.addWidget(self.kar_zarar_grafik_frame, 0, 1, 2, 1) # Row 0, Col 1, span 2 rows, 1 col
        self.kar_zarar_grafik_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.canvas_kar_zarar_main_plot = None
        self.ax_kar_zarar_main_plot = None

    def _create_nakit_akisi_tab(self, parent_frame):
        parent_layout = QGridLayout(parent_frame)
        parent_layout.setColumnStretch(0, 1)
        parent_layout.setColumnStretch(1, 1)
        parent_layout.setRowStretch(1, 1)

        parent_layout.addWidget(QLabel("Nakit Akışı Detayları ve Bakiyeler", font=QFont("Segoe UI", 16, QFont.Bold)), 0, 0, 1, 2, Qt.AlignLeft)

        left_panel = QFrame(parent_frame)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("İşlem Detayları", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignLeft)
        parent_layout.addWidget(left_panel, 1, 0)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols_nakit_detay = ("Tarih", "Tip", "Tutar", "Açıklama", "Hesap Adı", "Kaynak")
        self.tree_nakit_akisi_detay = QTreeWidget(left_panel)
        self.tree_nakit_akisi_detay.setHeaderLabels(cols_nakit_detay)
        self.tree_nakit_akisi_detay.setColumnCount(len(cols_nakit_detay))
        self.tree_nakit_akisi_detay.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_nakit_akisi_detay.setSortingEnabled(True)

        col_widths_nakit_detay = {
            "Tarih": 80, "Tip": 60, "Tutar": 90, "Açıklama": 180, "Hesap Adı": 90, "Kaynak": 70
        }
        for i, col_name in enumerate(cols_nakit_detay):
            self.tree_nakit_akisi_detay.setColumnWidth(i, col_widths_nakit_detay.get(col_name, 100))
            if col_name == "Açıklama":
                self.tree_nakit_akisi_detay.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                self.tree_nakit_akisi_detay.header().setSectionResizeMode(i, QHeaderView.Interactive)
            self.tree_nakit_akisi_detay.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name in ["Tarih", "Tip", "Tutar", "Kaynak"]:
                self.tree_nakit_akisi_detay.headerItem().setTextAlignment(i, Qt.AlignCenter)
            else:
                self.tree_nakit_akisi_detay.headerItem().setTextAlignment(i, Qt.AlignLeft)
        
        left_layout.addWidget(self.tree_nakit_akisi_detay)

        self.nakit_akis_grafik_frame = QFrame(parent_frame)
        self.nakit_akis_grafik_layout = QVBoxLayout(self.nakit_akis_grafik_frame)
        self.nakit_akis_grafik_layout.addWidget(QLabel("Aylık Nakit Akışı Trendi", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignLeft)
        parent_layout.addWidget(self.nakit_akis_grafik_frame, 1, 1)
        self.nakit_akis_grafik_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.canvas_nakit_akisi_trend = None
        self.ax_nakit_akisi_trend = None

        # Özet bilgiler ve kasa/banka bakiyeleri
        summary_frame = QFrame(parent_frame)
        summary_layout = QVBoxLayout(summary_frame)
        parent_layout.addWidget(summary_frame, 2, 0, 1, 2) # Row 2, Col 0, span 1 row, 2 cols
        summary_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        summary_layout.addWidget(QLabel("Dönem Nakit Akışı Özetleri (Kasa/Banka Bağlantılı)", font=QFont("Segoe UI", 15, QFont.Bold)), alignment=Qt.AlignLeft)
        self.lbl_nakit_giris = QLabel("Toplam Nakit Girişi: 0.00 TL")
        self.lbl_nakit_giris.setFont(QFont("Segoe UI", 15))
        summary_layout.addWidget(self.lbl_nakit_giris, alignment=Qt.AlignLeft)
        self.lbl_nakit_cikis = QLabel("Toplam Nakit Çıkışı: 0.00 TL")
        self.lbl_nakit_cikis.setFont(QFont("Segoe UI", 15))
        summary_layout.addWidget(self.lbl_nakit_cikis, alignment=Qt.AlignLeft)
        self.lbl_nakit_net = QLabel("Dönem Net Nakit Akışı: 0.00 TL")
        self.lbl_nakit_net.setFont(QFont("Segoe UI", 15, QFont.Bold))
        summary_layout.addWidget(self.lbl_nakit_net, alignment=Qt.AlignLeft)

        self.kasa_banka_bakiye_frame = QFrame(summary_frame)
        self.kasa_banka_bakiye_layout = QHBoxLayout(self.kasa_banka_bakiye_frame)
        summary_layout.addWidget(self.kasa_banka_bakiye_frame)
        self.kasa_banka_bakiye_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _create_cari_hesaplar_tab(self, parent_frame):
        parent_layout = QGridLayout(parent_frame)
        parent_layout.setColumnStretch(0, 1)
        parent_layout.setColumnStretch(1, 1)
        parent_layout.setRowStretch(1, 1)

        parent_layout.addWidget(QLabel("Cari Hesaplar Raporları (Yaşlandırma)", font=QFont("Segoe UI", 16, QFont.Bold)), 0, 0, 1, 2, Qt.AlignLeft)

        musteri_alacak_frame = QFrame(parent_frame)
        musteri_alacak_layout = QVBoxLayout(musteri_alacak_frame)
        musteri_alacak_layout.addWidget(QLabel("Müşteri Alacakları (Bize Borçlu)", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignLeft)
        parent_layout.addWidget(musteri_alacak_frame, 1, 0)
        musteri_alacak_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols_cari_yaslandirma = ("Cari Adı", "Tutar", "Vadesi Geçen Gün")
        self.tree_cari_yaslandirma_alacak = QTreeWidget(musteri_alacak_frame)
        self.tree_cari_yaslandirma_alacak.setHeaderLabels(cols_cari_yaslandirma)
        self.tree_cari_yaslandirma_alacak.setColumnCount(len(cols_cari_yaslandirma))
        self.tree_cari_yaslandirma_alacak.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_cari_yaslandirma_alacak.setSortingEnabled(True)

        col_widths_cari_yaslandirma = {
            "Cari Adı": 150, "Tutar": 100, "Vadesi Geçen Gün": 100
        }
        for i, col_name in enumerate(cols_cari_yaslandirma):
            self.tree_cari_yaslandirma_alacak.setColumnWidth(i, col_widths_cari_yaslandirma.get(col_name, 100))
            if col_name == "Cari Adı":
                self.tree_cari_yaslandirma_alacak.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                self.tree_cari_yaslandirma_alacak.header().setSectionResizeMode(i, QHeaderView.Interactive)
            self.tree_cari_yaslandirma_alacak.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name in ["Tutar", "Vadesi Geçen Gün"]:
                self.tree_cari_yaslandirma_alacak.headerItem().setTextAlignment(i, Qt.AlignRight)
            else:
                self.tree_cari_yaslandirma_alacak.headerItem().setTextAlignment(i, Qt.AlignLeft)
        
        musteri_alacak_layout.addWidget(self.tree_cari_yaslandirma_alacak)
        
        # Stil için QPalette veya item.setBackground() kullanılabilir.
        # Placeholder QBrush and QColor for now.
        # self.tree_cari_yaslandirma_alacak.tag_configure('header', font=('Segoe UI', 9, 'bold'), background='#E0E0E0')
        # self.tree_cari_yaslandirma_alacak.tag_configure('empty', foreground='gray')


        tedarikci_borc_frame = QFrame(parent_frame)
        tedarikci_borc_layout = QVBoxLayout(tedarikci_borc_frame)
        tedarikci_borc_layout.addWidget(QLabel("Tedarikçi Borçları (Biz Borçluyuz)", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignLeft)
        parent_layout.addWidget(tedarikci_borc_frame, 1, 1)
        tedarikci_borc_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.tree_cari_yaslandirma_borc = QTreeWidget(tedarikci_borc_frame)
        self.tree_cari_yaslandirma_borc.setHeaderLabels(cols_cari_yaslandirma)
        self.tree_cari_yaslandirma_borc.setColumnCount(len(cols_cari_yaslandirma))
        self.tree_cari_yaslandirma_borc.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_cari_yaslandirma_borc.setSortingEnabled(True)

        for i, col_name in enumerate(cols_cari_yaslandirma):
            self.tree_cari_yaslandirma_borc.setColumnWidth(i, col_widths_cari_yaslandirma.get(col_name, 100))
            if col_name == "Cari Adı":
                self.tree_cari_yaslandirma_borc.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                self.tree_cari_yaslandirma_borc.header().setSectionResizeMode(i, QHeaderView.Interactive)
            self.tree_cari_yaslandirma_borc.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name in ["Tutar", "Vadesi Geçen Gün"]:
                self.tree_cari_yaslandirma_borc.headerItem().setTextAlignment(i, Qt.AlignRight)
            else:
                self.tree_cari_yaslandirma_borc.headerItem().setTextAlignment(i, Qt.AlignLeft)
        
        tedarikci_borc_layout.addWidget(self.tree_cari_yaslandirma_borc)
        # Stil için QPalette veya item.setBackground() kullanılabilir.
        # self.tree_cari_yaslandirma_borc.tag_configure('header', font=('Segoe UI', 9, 'bold'), background='#E0E0E0')
        # self.tree_cari_yaslandirma_borc.tag_configure('empty', foreground='gray')


        bottom_summary_frame = QFrame(parent_frame)
        bottom_summary_layout = QHBoxLayout(bottom_summary_frame)
        parent_layout.addWidget(bottom_summary_frame, 2, 0, 1, 2) # Row 2, Col 0, span 1 row, 2 cols
        bottom_summary_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.lbl_toplam_alacak_cari = QLabel("Toplam Alacak: 0.00 TL")
        self.lbl_toplam_alacak_cari.setFont(QFont("Segoe UI", 10, QFont.Bold))
        bottom_summary_layout.addWidget(self.lbl_toplam_alacak_cari)

        self.lbl_toplam_borc_cari = QLabel("Toplam Borç: 0.00 TL")
        self.lbl_toplam_borc_cari.setFont(QFont("Segoe UI", 10, QFont.Bold))
        bottom_summary_layout.addWidget(self.lbl_toplam_borc_cari)

        self.lbl_net_bakiye_cari = QLabel("Net Bakiye: 0.00 TL")
        self.lbl_net_bakiye_cari.setFont(QFont("Segoe UI", 12, QFont.Bold))
        bottom_summary_layout.addWidget(self.lbl_net_bakiye_cari, alignment=Qt.AlignRight)

    def _create_stok_raporlari_tab(self, parent_frame):
        parent_layout = QGridLayout(parent_frame)
        parent_layout.setColumnStretch(0, 1)
        parent_layout.setColumnStretch(1, 1)
        parent_layout.setRowStretch(1, 1)

        parent_layout.addWidget(QLabel("Stok Raporları", font=QFont("Segoe UI", 16, QFont.Bold)), 0, 0, 1, 2, Qt.AlignLeft)

        envanter_frame = QFrame(parent_frame)
        envanter_layout = QVBoxLayout(envanter_frame)
        envanter_layout.addWidget(QLabel("Mevcut Stok Envanteri", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignLeft)
        parent_layout.addWidget(envanter_frame, 1, 0)
        envanter_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols_stok = ("Ürün Kodu", "Ürün Adı", "Miktar", "Alış Fyt (KDV Dahil)", "Satış Fyt (KDV Dahil)", "KDV %", "Min. Stok")
        self.tree_stok_envanter = QTreeWidget(envanter_frame)
        self.tree_stok_envanter.setHeaderLabels(cols_stok)
        self.tree_stok_envanter.setColumnCount(len(cols_stok))
        self.tree_stok_envanter.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_stok_envanter.setSortingEnabled(True)

        col_widths_stok = {
            "Ürün Kodu": 100, "Ürün Adı": 150, "Miktar": 80, 
            "Alış Fyt (KDV Dahil)": 120, "Satış Fyt (KDV Dahil)": 120, 
            "KDV %": 55, "Min. Stok": 80
        }
        for i, col_name in enumerate(cols_stok):
            self.tree_stok_envanter.setColumnWidth(i, col_widths_stok.get(col_name, 100))
            if col_name == "Ürün Adı":
                self.tree_stok_envanter.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                self.tree_stok_envanter.header().setSectionResizeMode(i, QHeaderView.Interactive)
            self.tree_stok_envanter.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name in ["Miktar", "Alış Fyt (KDV Dahil)", "Satış Fyt (KDV Dahil)", "KDV %", "Min. Stok"]:
                self.tree_stok_envanter.headerItem().setTextAlignment(i, Qt.AlignRight)
            else:
                self.tree_stok_envanter.headerItem().setTextAlignment(i, Qt.AlignLeft)
        
        envanter_layout.addWidget(self.tree_stok_envanter)

        stok_grafikler_frame = QFrame(parent_frame)
        stok_grafikler_layout = QVBoxLayout(stok_grafikler_frame)
        parent_layout.addWidget(stok_grafikler_frame, 1, 1)
        stok_grafikler_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.stok_kritik_grafik_frame = QFrame(stok_grafikler_frame)
        self.stok_kritik_grafik_layout = QVBoxLayout(self.stok_kritik_grafik_frame)
        self.stok_kritik_grafik_layout.addWidget(QLabel("Kritik Stok Durumu", font=QFont("Segoe UI", 10, QFont.Bold)))
        stok_grafikler_layout.addWidget(self.stok_kritik_grafik_frame)
        self.stok_kritik_grafik_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas_stok_kritik = None
        self.ax_stok_kritik = None

        self.stok_kategori_dagilim_frame = QFrame(stok_grafikler_frame)
        self.stok_kategori_dagilim_layout = QVBoxLayout(self.stok_kategori_dagilim_frame)
        self.stok_kategori_dagilim_layout.addWidget(QLabel("Kategoriye Göre Toplam Stok Değeri", font=QFont("Segoe UI", 10, QFont.Bold)))
        stok_grafikler_layout.addWidget(self.stok_kategori_dagilim_frame)
        self.stok_kategori_dagilim_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas_stok_kategori = None
        self.ax_stok_kategori = None

    def _on_tab_change(self, index): # index parametresi currentChanged sinyalinden gelir
        selected_tab_text = self.report_notebook.tabText(index) # tabText(index) ile metin alınır
        bas_t_str = self.bas_tarih_entry.text()
        bit_t_str = self.bit_tarih_entry.text()

        if selected_tab_text == "📊 Genel Bakış":
            self._update_genel_bakis_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "📈 Satış Raporları":
            self._update_satis_raporlari_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "💰 Kâr ve Zarar":
            self._update_kar_zarar_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "🏦 Nakit Akışı":
            self._update_nakit_akisi_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "👥 Cari Hesaplar":
            self._update_cari_hesaplar_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "📦 Stok Raporları":
            self._update_stok_raporlari_tab(bas_t_str, bit_t_str)

        self.app.set_status_message(f"Rapor güncellendi: {selected_tab_text} ({bas_t_str} - {bit_t_str}).")

    def raporu_olustur_ve_yenile(self):
        bas_t_str = self.bas_tarih_entry.text()
        bit_t_str = self.bit_tarih_entry.text()

        try:
            bas_t = datetime.strptime(bas_t_str, '%Y-%m-%d')
            bit_t = datetime.strptime(bit_t_str, '%Y-%m-%d')
            if bas_t > bit_t:
                QMessageBox.critical(self.app, "Tarih Hatası", "Başlangıç tarihi, bitiş tarihinden sonra olamaz.")
                return
        except ValueError:
            QMessageBox.critical(self.app, "Tarih Formatı Hatası", "Tarih formatı (`YYYY-AA-GG`) olmalıdır (örn: 2023-12-31).")
            return

        selected_tab_text = self.report_notebook.tabText(self.report_notebook.currentIndex()) # current Index ile metin al
        if selected_tab_text == "📊 Genel Bakış":
            self._update_genel_bakis_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "📈 Satış Raporları":
            self._update_satis_raporlari_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "💰 Kâr ve Zarar":
            self._update_kar_zarar_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "🏦 Nakit Akışı":
            self._update_nakit_akisi_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "👥 Cari Hesaplar":
            self._update_cari_hesaplar_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "📦 Stok Raporları":
            self._update_stok_raporlari_tab(bas_t_str, bit_t_str)

        self.app.set_status_message(f"Finansal Raporlar güncellendi ({bas_t_str} - {bit_t_str}).")

    def _update_genel_bakis_tab(self, bas_t_str, bit_t_str):
        # Placeholder Label'ı gizle (veya kaldır) - PySide6'da QLabel'ı destroy etmeye gerek yok, içeriğini temizleyebiliriz
        # if hasattr(self, 'lbl_genel_bakis_placeholder'):
        #     self.lbl_genel_bakis_placeholder.deleteLater() # veya setVisible(False)

        # Verileri çek
        total_sales = self.db.get_total_sales(bas_t_str, bit_t_str)
        total_collections = self.db.get_total_collections(bas_t_str, bit_t_str)
        total_payments = self.db.get_total_payments(bas_t_str, bit_t_str)
        donem_gelir, donem_gider = self.db.get_kar_zarar_verileri(bas_t_str, bit_t_str)
        net_cash_flow = donem_gelir - donem_gider

        # Kartları güncelle
        self.lbl_metric_sales.setText(self.db._format_currency(total_sales))
        self.lbl_metric_collections.setText(self.db._format_currency(total_collections))
        self.lbl_metric_payments.setText(self.db._format_currency(total_payments))
        self.lbl_metric_net_cash.setText(self.db._format_currency(net_cash_flow))
        self.lbl_metric_net_cash.setStyleSheet(f"color: {'green' if net_cash_flow >= 0 else 'red'};")


        # Grafik verilerini çek
        monthly_sales_data = self.db.get_monthly_sales_summary(bas_t_str, bit_t_str)
        monthly_income_expense_data = self.db.get_monthly_income_expense_summary(bas_t_str, bit_t_str)

        all_months_set = set()
        for item in monthly_sales_data: all_months_set.add(item[0])
        for item in monthly_income_expense_data: all_months_set.add(item[0])
        all_months = sorted(list(all_months_set))

        full_sales_values = [0] * len(all_months)
        full_income_values = [0] * len(all_months)
        full_expense_values = [0] * len(all_months)

        for i, month in enumerate(all_months):
            for m_s in monthly_sales_data:
                if m_s[0] == month: full_sales_values[i] = m_s[1]
            for m_ie in monthly_income_expense_data:
                if m_ie[0] == month:
                    full_income_values[i] = m_ie[1]
                    full_expense_values[i] = m_ie[2]

        # Ana çubuk grafik (Satış, Gelir, Gider trendi)
        self.canvas_genel_bakis_main_plot, self.ax_genel_bakis_main_plot = self._draw_plot(
            self.genel_bakis_grafik_frame,
            self.canvas_genel_bakis_main_plot,
            self.ax_genel_bakis_main_plot,
            "Aylık Finansal Trendler",
            all_months,
            [full_sales_values, full_income_values, full_expense_values],
            plot_type='grouped_bar',
            group_labels=['Toplam Satış', 'Toplam Gelir', 'Toplam Gider'],
            colors=['skyblue', 'lightgreen', 'lightcoral']
        )

    def _update_satis_raporlari_tab(self, bas_t_str, bit_t_str):
        # Placeholder Label'ı gizle
        # if hasattr(self, 'lbl_satis_raporlari_placeholder'):
        #     self.lbl_satis_raporlari_placeholder.deleteLater()

        self.tree_satis_detay.clear() # QTreeWidget'ı temizle

        satis_detay_data = self.db.tarihsel_satis_raporu_verilerini_al(bas_t_str, bit_t_str)
        if satis_detay_data:
            for item in satis_detay_data:
                formatted_tarih = item['tarih'].strftime('%d.%m.%Y') if isinstance(item['tarih'], (datetime, date)) else (str(item['tarih']) if item['tarih'] is not None else "")
                
                item_qt = QTreeWidgetItem(self.tree_satis_detay)
                item_qt.setText(0, item['fatura_no'])
                item_qt.setText(1, formatted_tarih)
                item_qt.setText(2, item['cari_adi'])
                item_qt.setText(3, item['urun_adi'])
                item_qt.setText(4, f"{item['miktar']:.2f}".rstrip('0').rstrip('.'))
                item_qt.setText(5, self.db._format_currency(item['birim_fiyat_kdv_dahil'])) # Yeni
                item_qt.setText(6, self.db._format_currency(item['kalem_toplam_kdv_dahil'])) # Yeni
                
                # Sayısal sütunlar için sıralama anahtarları
                item_qt.setData(4, Qt.UserRole, item['miktar'])
                item_qt.setData(5, Qt.UserRole, item['birim_fiyat_kdv_dahil'])
                item_qt.setData(6, Qt.UserRole, item['kalem_toplam_kdv_dahil'])

        else:
            item_qt = QTreeWidgetItem(self.tree_satis_detay)
            item_qt.setText(2, "Veri Yok")


        sales_by_payment_type = self.db.get_sales_by_payment_type(bas_t_str, bit_t_str)
        plot_labels_odeme = [item[0] for item in sales_by_payment_type]
        plot_values_odeme = [item[1] for item in sales_by_payment_type]

        self.canvas_satis_odeme_dagilimi, self.ax_satis_odeme_dagilimi = self._draw_plot(
            self.satis_odeme_dagilimi_frame,
            self.canvas_satis_odeme_dagilimi,
            self.ax_satis_odeme_dagilimi,
            "Ödeme Türlerine Göre Satış Dağılımı",
            plot_labels_odeme, plot_values_odeme, plot_type='pie'
        )

        top_selling_products = self.db.get_top_selling_products(bas_t_str, bit_t_str, limit=5)
        plot_labels_top_satan = [item[0] for item in top_selling_products]
        plot_values_top_satan = [item[1] for item in top_selling_products]

        self.canvas_en_cok_satan, self.ax_en_cok_satan = self._draw_plot(
            self.en_cok_satan_urunler_frame,
            self.canvas_en_cok_satan,
            self.ax_en_cok_satan,
            "En Çok Satan Ürünler (Miktar)",
            plot_labels_top_satan, plot_values_top_satan, plot_type='bar', rotation=30, show_labels_on_bars=True
        )

    def _update_kar_zarar_tab(self, bas_t_str, bit_t_str):
        # Placeholder Label'ı gizle
        # if hasattr(self, 'lbl_kar_zarar_placeholder'):
        #     self.lbl_kar_zarar_placeholder.deleteLater()

        gross_profit, cogs, gross_profit_rate = self.db.get_gross_profit_and_cost(bas_t_str, bit_t_str)
        self.lbl_brut_kar.setText(self.db._format_currency(gross_profit))
        self.lbl_cogs.setText(self.db._format_currency(cogs))
        self.lbl_brut_kar_orani.setText(f"%{gross_profit_rate:,.2f}")

        monthly_gross_profit_data = self.db.get_monthly_gross_profit_summary(bas_t_str, bit_t_str)

        months = sorted(list(set([item[0] for item in monthly_gross_profit_data])))
        full_sales_income = [0] * len(months)
        full_cogs = [0] * len(months)

        for i, month in enumerate(months):
            for mgp in monthly_gross_profit_data:
                if mgp[0] == month:
                    full_sales_income[i] = mgp[1]
                    full_cogs[i] = mgp[2]

        self.canvas_kar_zarar_main_plot, self.ax_kar_zarar_main_plot = self._draw_plot(
            self.kar_zarar_grafik_frame,
            self.canvas_kar_zarar_main_plot,
            self.ax_kar_zarar_main_plot,
            "Aylık Kâr ve Maliyet Karşılaştırması",
            months,
            [full_sales_income, full_cogs],
            plot_type='grouped_bar',
            group_labels=['Toplam Satış Geliri', 'Satılan Malın Maliyeti'],
            colors=['teal', 'darkorange']
        )

    def _update_nakit_akisi_tab(self, bas_t_str, bit_t_str):
        # Placeholder Label'ı gizle
        # if hasattr(self, 'lbl_nakit_akisi_placeholder'):
        #     self.lbl_nakit_akisi_placeholder.deleteLater()

        self.tree_nakit_akisi_detay.clear() # QTreeWidget'ı temizle

        nakit_akis_detay_data = self.db.get_nakit_akis_verileri(bas_t_str, bit_t_str)
        if nakit_akis_detay_data:
            for item in nakit_akis_detay_data:
                formatted_tarih = item['tarih'].strftime('%d.%m.%Y') if isinstance(item['tarih'], (datetime, date)) else (str(item['tarih']) if item['tarih'] is not None else "")
                
                item_qt = QTreeWidgetItem(self.tree_nakit_akisi_detay)
                item_qt.setText(0, formatted_tarih)
                item_qt.setText(1, item['tip'])
                item_qt.setText(2, self.db._format_currency(item['tutar']))
                item_qt.setText(3, item['aciklama'] if item['aciklama'] else "-")
                item_qt.setText(4, item['hesap_adi'] if item['hesap_adi'] else "-")
                item_qt.setText(5, item['kaynak'] if item['kaynak'] else "-")

                # Sayısal sütunlar için sıralama anahtarları
                item_qt.setData(2, Qt.UserRole, item['tutar']) # Tutar

        else:
            item_qt = QTreeWidgetItem(self.tree_nakit_akisi_detay)
            item_qt.setText(2, "Veri Yok")


        nakit_akis_verileri_tum = self.db.get_nakit_akis_verileri(bas_t_str, bit_t_str)
        toplam_nakit_giris = sum(item['tutar'] for item in nakit_akis_verileri_tum if item['tip'] == 'GELİR')
        toplam_nakit_cikis = sum(item['tutar'] for item in nakit_akis_verileri_tum if item['tip'] == 'GİDER')

        self.lbl_nakit_giris.setText(f"Toplam Nakit Girişi: {self.db._format_currency(toplam_nakit_giris)}")
        self.lbl_nakit_cikis.setText(f"Toplam Nakit Çıkışı: {self.db._format_currency(toplam_nakit_cikis)}")
        self.lbl_nakit_net.setText(f"Dönem Net Nakit Akışı: {self.db._format_currency(toplam_nakit_giris - toplam_nakit_cikis)}")

        monthly_cash_flow_data = self.db.get_monthly_cash_flow_summary(bas_t_str, bit_t_str)

        months_cf = sorted(list(set([item[0] for item in monthly_cash_flow_data])))
        full_cash_in = [0] * len(months_cf)
        full_cash_out = [0] * len(months_cf)

        for i, month in enumerate(months_cf):
            for mcf in monthly_cash_flow_data:
                if mcf[0] == month:
                    full_cash_in[i] = mcf[1]
                    full_cash_out[i] = mcf[2]

        self.canvas_nakit_akisi_trend, self.ax_nakit_akisi_trend = self._draw_plot(
            self.nakit_akis_grafik_frame,
            self.canvas_nakit_akisi_trend,
            self.ax_nakit_akisi_trend,
            "Aylık Nakit Akışı",
            months_cf,
            [full_cash_in, full_cash_out],
            plot_type='grouped_bar',
            colors=['mediumseagreen', 'indianred']
        )

        # Kasa/Banka bakiyeleri
        # Önceki widget'ları temizle
        for i in reversed(range(self.kasa_banka_bakiye_layout.count())):
            widget_to_remove = self.kasa_banka_bakiye_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None) # Remove from layout and delete
                widget_to_remove.deleteLater()

        current_balances = self.db.get_tum_kasa_banka_bakiyeleri()
        if current_balances:
            for h_id, h_adi, bakiye, h_tip in current_balances:
                label_text = f"{h_adi} ({h_tip}): {self.db._format_currency(bakiye)}"
                label = QLabel(label_text)
                label.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.kasa_banka_bakiye_layout.addWidget(label)
        else:
            self.kasa_banka_bakiye_layout.addWidget(QLabel("Kasa/Banka Hesabı Bulunamadı.", font=QFont("Segoe UI", 9)))


    def _update_cari_hesaplar_tab(self, bas_t_str, bit_t_str):
        # Placeholder Label'ı gizle
        # if hasattr(self, 'lbl_cari_hesaplar_placeholder'):
        #     self.lbl_cari_hesaplar_placeholder.deleteLater()

        self.cari_yaslandirma_data = self.db.get_cari_yaslandirma_verileri(bit_t_str)

        self.tree_cari_yaslandirma_alacak.clear() # QTreeWidget'ı temizle
        self._populate_yaslandirma_treeview(self.tree_cari_yaslandirma_alacak, self.cari_yaslandirma_data['musteri_alacaklari'])

        self.tree_cari_yaslandirma_borc.clear() # QTreeWidget'ı temizle
        self._populate_yaslandirma_treeview(self.tree_cari_yaslandirma_borc, self.cari_yaslandirma_data['tedarikci_borclari'])


        toplam_alacak = sum(item[2] for group in self.cari_yaslandirma_data['musteri_alacaklari'].values() for item in group)
        toplam_borc = sum(item[2] for group in self.cari_yaslandirma_data['tedarikci_borclari'].values() for item in group)
        net_bakiye_cari = toplam_alacak - toplam_borc

        self.lbl_toplam_alacak_cari.setText(f"Toplam Alacak: {self.db._format_currency(toplam_alacak)}")
        self.lbl_toplam_borc_cari.setText(f"Toplam Borç: {self.db._format_currency(toplam_borc)}")
        self.lbl_net_bakiye_cari.setText(f"Net Bakiye: {self.db._format_currency(net_bakiye_cari)}")


    def _populate_yaslandirma_treeview(self, tree, data_dict):
        # Clear existing items is handled by the caller
        for period, items in data_dict.items():
            header_item = QTreeWidgetItem(tree)
            header_item.setText(0, f"--- {period} Gün ---")
            header_item.setFont(0, QFont("Segoe UI", 9, QFont.Bold))
            for col_idx in range(tree.columnCount()):
                header_item.setBackground(col_idx, QBrush(QColor("#E0E0E0"))) # Arka plan
                header_item.setForeground(col_idx, QBrush(QColor("black"))) # Metin rengi

            if items:
                for item in items:
                    child_item = QTreeWidgetItem(header_item)
                    child_item.setText(0, item[1]) # Cari Adı
                    child_item.setText(1, self.db._format_currency(item[2])) # Tutar
                    child_item.setText(2, str(item[3])) # Vadesi Geçen Gün

                    # Sayısal sütunlar için sıralama anahtarları
                    child_item.setData(1, Qt.UserRole, item[2]) # Tutar
                    child_item.setData(2, Qt.UserRole, item[3]) # Vadesi Geçen Gün
            else:
                child_item = QTreeWidgetItem(header_item)
                child_item.setText(0, "Bu Kategori Boş")
                for col_idx in range(tree.columnCount()):
                    child_item.setForeground(col_idx, QBrush(QColor("gray"))) # Gri metin

        tree.expandAll() # Tüm header'ları aç

    def _update_stok_raporlari_tab(self, bas_t_str, bit_t_str):
        # Placeholder Label'ı gizle
        # if hasattr(self, 'lbl_stok_raporlari_placeholder'):
        #     self.lbl_stok_raporlari_placeholder.deleteLater()

        self.tree_stok_envanter.clear() # QTreeWidget'ı temizle

        all_stock_items = self.db.stok_listele(limit=None, offset=None)

        if all_stock_items:
            for item in all_stock_items:
                item_qt = QTreeWidgetItem(self.tree_stok_envanter)
                item_qt.setText(0, item['urun_kodu'])
                item_qt.setText(1, item['urun_adi'])
                item_qt.setText(2, f"{item['stok_miktari']:.2f}".rstrip('0').rstrip('.'))
                item_qt.setText(3, self.db._format_currency(item['alis_fiyati_kdv_dahil']))
                item_qt.setText(4, self.db._format_currency(item['satis_fiyati_kdv_dahil']))
                item_qt.setText(5, f"{item['kdv_orani']:.0f}%")
                item_qt.setText(6, f"{item['min_stok_seviyesi']:.2f}".rstrip('0').rstrip('.'))

                # Sayısal sütunlar için sıralama anahtarları
                item_qt.setData(2, Qt.UserRole, item['stok_miktari'])
                item_qt.setData(3, Qt.UserRole, item['alis_fiyati_kdv_dahil'])
                item_qt.setData(4, Qt.UserRole, item['satis_fiyati_kdv_dahil'])
                item_qt.setData(5, Qt.UserRole, item['kdv_orani'])
                item_qt.setData(6, Qt.UserRole, item['min_stok_seviyesi'])
        else:
            item_qt = QTreeWidgetItem(self.tree_stok_envanter)
            item_qt.setText(2, "Veri Yok")


        critical_items = self.db.get_critical_stock_items()

        labels_kritik = ["Kritik Stokta", "Normal Stokta"]
        values_kritik = [len(critical_items), len(all_stock_items) - len(critical_items)]

        self.canvas_stok_kritik, self.ax_stok_kritik = self._draw_plot(
            self.stok_kritik_grafik_frame,
            self.canvas_stok_kritik,
            self.ax_stok_kritik,
            "Kritik Stok Durumu",
            labels_kritik, values_kritik, plot_type='pie', colors=['indianred', 'lightgreen']
        )

        stock_value_by_category = self.db.get_stock_value_by_category()
        labels_kategori = [item[0] for item in stock_value_by_category]
        values_kategori = [item[1] for item in stock_value_by_category]

        self.canvas_stok_kategori, self.ax_stok_kategori = self._draw_plot(
            self.stok_kategori_dagilim_frame,
            self.canvas_stok_kategori,
            self.ax_stok_kategori,
            "Kategoriye Göre Toplam Stok Değeri",
            labels_kategori, values_kategori, plot_type='pie'
        )

    def raporu_pdf_yazdir_placeholder(self):
        # Raporu PDF olarak kaydetme işlemi için dosya kaydetme diyaloğu
        initial_file_name = f"Rapor_Ozeti_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self,
                                                 "Raporu PDF olarak kaydet",
                                                 initial_file_name,
                                                 "PDF Dosyaları (*.pdf);;Tüm Dosyalar (*)")

        if file_path:
            try:
                # NOT: Bu işlem şu anda API üzerinden yapılmıyor, direkt db.fatura_pdf_olustur gibi metotlar çağrılıyor.
                # RaporlamaMerkeziSayfasi için farklı rapor türleri olduğundan,
                # burada hangi raporun (Genel Bakış, Satış, Kar/Zarar vb.) PDF'e dönüştürüleceği mantığı eklenmelidir.
                # Şimdilik genel bir bilgilendirme mesajı verelim.

                # Hangi sekmenin aktif olduğunu kontrol et
                current_tab_text = self.report_notebook.tabText(self.report_notebook.currentIndex())

                success = False
                message = f"'{current_tab_text}' raporu için PDF yazdırma özelliği henüz tam olarak entegre edilmedi."

                # Örnek: Eğer "Satış Raporları" sekmesindeysek ve API'de endpoint varsa
                # if current_tab_text == "📈 Satış Raporları":
                #     # API üzerinden satış raporu PDF oluşturma endpoint'i çağrılabilir.
                #     # VEYA db.tarihsel_satis_raporu_pdf_olustur gibi bir metod çağrılır.
                #     bas_t_str = self.bas_tarih_entry.text()
                #     bit_t_str = self.bit_tarih_entry.text()
                #     success, message = self.db.tarihsel_satis_raporu_pdf_olustur(bas_t_str, bit_t_str, file_path)
                # else:
                #     message = f"'{current_tab_text}' raporu için PDF yazdırma özelliği henüz geliştirilmedi."


                if success:
                    QMessageBox.information(self, "Başarılı", message)
                    self.app.set_status_message(message)
                else:
                    QMessageBox.warning(self, "Bilgi", message) # Placeholder için uyarı
                    self.app.set_status_message(f"PDF yazdırma iptal edildi/geliştirilmedi: {message}")

            except Exception as e:
                logging.error(f"Raporu PDF olarak yazdırırken beklenmeyen bir hata oluştu: {e}\n{traceback.format_exc()}")
                QMessageBox.critical(self, "Kritik Hata", f"Raporu PDF olarak yazdırırken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Hata: Rapor PDF yazdırma - {e}")
        else:
            self.app.set_status_message("PDF kaydetme işlemi iptal edildi.")

    def raporu_excel_aktar_placeholder(self):
        # Raporu Excel olarak kaydetme işlemi için dosya kaydetme diyaloğu
        initial_file_name = f"Rapor_Ozeti_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(self,
                                                 "Raporu Excel olarak kaydet",
                                                 initial_file_name,
                                                 "Excel Dosyaları (*.xlsx);;Tüm Dosyalar (*)")

        if file_path:
            try:
                # NOT: Bu işlem şu anda API üzerinden yapılmıyor, direkt db metotları çağrılıyor.
                # RaporlamaMerkeziSayfasi için farklı rapor türleri olduğundan,
                # burada hangi raporun (Genel Bakış, Satış, Kar/Zarar vb.) Excel'e dönüştürüleceği mantığı eklenmelidir.
                # Şimdilik genel bir bilgilendirme mesajı verelim.

                # Hangi sekmenin aktif olduğunu kontrol et
                current_tab_text = self.report_notebook.tabText(self.report_notebook.currentIndex())

                success = False
                message = f"'{current_tab_text}' raporu için Excel'e aktarma özelliği henüz tam olarak entegre edilmedi."

                # Örnek: Eğer "Satış Raporları" sekmesindeysek ve db'de metot varsa
                # if current_tab_text == "📈 Satış Raporları":
                #     # db.tarihsel_satis_raporu_excel_aktar gibi bir metod çağrılır.
                #     bas_t_str = self.bas_tarih_entry.text()
                #     bit_t_str = self.bit_tarih_entry.text()
                #     success, message = self.db.tarihsel_satis_raporu_excel_aktar(bas_t_str, bit_t_str, file_path)
                # else:
                #     message = f"'{current_tab_text}' raporu için Excel'e aktarma özelliği henüz geliştirilmedi."


                if success:
                    QMessageBox.information(self, "Başarılı", message)
                    self.app.set_status_message(message)
                else:
                    QMessageBox.warning(self, "Bilgi", message) # Placeholder için uyarı
                    self.app.set_status_message(f"Excel'e aktarma iptal edildi/geliştirilmedi: {message}")

            except Exception as e:
                logging.error(f"Raporu Excel olarak dışa aktarırken beklenmeyen bir hata oluştu: {e}\n{traceback.format_exc()}")
                QMessageBox.critical(self, "Kritik Hata", f"Raporu Excel olarak dışa aktarırken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Hata: Rapor Excel'e aktarma - {e}")
        else:
            self.app.set_status_message("Excel kaydetme işlemi iptal edildi.")
                
class GelirGiderSayfasi(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref # Ana App sınıfına referans
        self.setLayout(QVBoxLayout()) # Ana layout

        self.layout().addWidget(QLabel("Gelir ve Gider İşlemleri", font=QFont("Segoe UI", 16, QFont.Bold)), alignment=Qt.AlignLeft)

        # Ana Notebook (Sekmeli Yapı)
        self.main_notebook = QTabWidget(self) # ttk.Notebook yerine QTabWidget
        self.layout().addWidget(self.main_notebook)

        # Gelir Listesi Sekmesi
        self.gelir_listesi_frame = GelirListesi(self.main_notebook, self.db, self.app)
        self.main_notebook.addTab(self.gelir_listesi_frame, "💰 Gelirler")

        # Gider Listesi Sekmesi
        self.gider_listesi_frame = GiderListesi(self.main_notebook, self.db, self.app)
        self.main_notebook.addTab(self.gider_listesi_frame, "💸 Giderler")

        # Sekme değiştiğinde ilgili formu yenilemek için bir olay bağlayabiliriz
        self.main_notebook.currentChanged.connect(self._on_tab_change) # Yeni metod

    def _on_tab_change(self, index):
        """Sekme değiştiğinde ilgili listeyi yeniler."""
        selected_widget = self.main_notebook.widget(index)
        if hasattr(selected_widget, 'gg_listesini_yukle'):
            selected_widget.gg_listesini_yukle()
        
class GirisEkrani(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent, db_manager, callback_basarili_giris):
        super().__init__(parent)
        self.db = db_manager
        self.callback = callback_basarili_giris
        self.main_layout = QVBoxLayout(self) # Ana layout QVBoxLayout

        # Giriş formunu ortalamak için bir QFrame ve QVBoxLayout
        center_frame = QFrame(self)
        center_layout = QVBoxLayout(center_frame)
        self.main_layout.addWidget(center_frame, alignment=Qt.AlignCenter) # Ortala

        # Kullanıcı Girişi Başlığı
        title_label = QLabel("Kullanıcı Girişi")
        title_label.setFont(QFont("Segoe UI", 22, QFont.Bold))
        center_layout.addWidget(title_label, alignment=Qt.AlignCenter)

        # Kullanıcı Adı
        center_layout.addWidget(QLabel("Kullanıcı Adı:"), alignment=Qt.AlignLeft)
        self.k_adi_e = QLineEdit()
        self.k_adi_e.setFixedWidth(250) # Genişlik
        self.k_adi_e.setFixedHeight(30) # Yükseklik (padding yerine)
        self.k_adi_e.setFont(QFont("Segoe UI", 11))
        center_layout.addWidget(self.k_adi_e)

        # Şifre
        center_layout.addWidget(QLabel("Şifre:"), alignment=Qt.AlignLeft)
        self.sifre_e = QLineEdit()
        self.sifre_e.setEchoMode(QLineEdit.Password) # Şifreyi gizle
        self.sifre_e.setFixedWidth(250)
        self.sifre_e.setFixedHeight(30)
        self.sifre_e.setFont(QFont("Segoe UI", 11))
        self.sifre_e.returnPressed.connect(self.giris_yap) # Enter tuşu için
        center_layout.addWidget(self.sifre_e)

        # Giriş Butonu
        giris_button = QPushButton("Giriş Yap")
        giris_button.setFixedWidth(150)
        giris_button.setFixedHeight(40) # Padding yerine
        giris_button.setFont(QFont("Segoe UI", 11, QFont.Bold))
        giris_button.clicked.connect(self.giris_yap)
        center_layout.addWidget(giris_button, alignment=Qt.AlignCenter)

        # Kayıtlı kullanıcı adını yükle
        config = self.db.load_config()
        last_username = config.get('last_username', '')
        self.k_adi_e.setText(last_username) # setText ile ata

        # Şirket Adı (Giriş Ekranının Altında)
        sirket_adi_giris = self.db.sirket_bilgileri.get("sirket_adi", "Şirket Adınız")
        sirket_label_bottom = QLabel(sirket_adi_giris)
        sirket_label_bottom.setFont(QFont("Segoe UI", 10))
        # QLabel'ı ana layout'un altına yerleştirmek için (Qt.AlignBottom)
        self.main_layout.addWidget(sirket_label_bottom, alignment=Qt.AlignCenter | Qt.AlignBottom)


        # Odaklanma işlemi en sona alınmalı
        self.k_adi_e.setFocus() # setFocus() ile odaklan

    def giris_yap(self): # event parametresi kaldırıldı
        k_adi = self.k_adi_e.text()
        sifre = self.sifre_e.text()
        kullanici = self.db.kullanici_dogrula(k_adi, sifre)
        if kullanici:
            self.callback(kullanici) # Başarılı giriş callback'ini çağır
        else:
            QMessageBox.critical(self, "Giriş Hatası", "Kullanıcı adı veya şifre hatalı!")
            self.sifre_e.clear() # Şifre alanını temizle
            self.sifre_e.setFocus() # Şifre alanına odaklan

class StokHareketleriSekmesi(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent_notebook, db_manager, app_ref, urun_id, urun_adi, parent_pencere=None):
        super().__init__(parent_notebook)
        self.db = db_manager
        self.app = app_ref
        self.urun_id = urun_id
        self.urun_adi = urun_adi
        self.parent_pencere = parent_pencere # Ürün kartı penceresinin referansı
        
        self.main_layout = QVBoxLayout(self) # Ana layout QVBoxLayout
        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)

        # Filtreleme seçenekleri çerçevesi
        filter_frame = QFrame(self)
        filter_layout = QHBoxLayout(filter_frame)
        self.main_layout.addWidget(filter_frame)

        filter_layout.addWidget(QLabel("İşlem Tipi:"))
        self.stok_hareket_tip_filter_cb = QComboBox()
        self.stok_hareket_tip_filter_cb.addItems(["TÜMÜ", self.db.STOK_ISLEM_TIP_GIRIS_MANUEL_DUZELTME, 
                                                  self.db.STOK_ISLEM_TIP_CIKIS_MANUEL_DUZELTME, 
                                                  self.db.STOK_ISLEM_TIP_GIRIS_MANUEL, 
                                                  self.db.STOK_ISLEM_TIP_CIKIS_MANUEL, 
                                                  self.db.STOK_ISLEM_TIP_SAYIM_FAZLASI, 
                                                  self.db.STOK_ISLEM_TIP_SAYIM_EKSIGI, 
                                                  self.db.STOK_ISLEM_TIP_ZAYIAT, 
                                                  self.db.STOK_ISLEM_TIP_IADE_GIRIS, 
                                                  self.db.STOK_ISLEM_TIP_FATURA_ALIS, 
                                                  self.db.STOK_ISLEM_TIP_FATURA_SATIS])
        self.stok_hareket_tip_filter_cb.setCurrentText("TÜMÜ")
        self.stok_hareket_tip_filter_cb.currentIndexChanged.connect(self._load_stok_hareketleri)
        filter_layout.addWidget(self.stok_hareket_tip_filter_cb)

        filter_layout.addWidget(QLabel("Başlangıç Tarihi:"))
        self.stok_hareket_bas_tarih_entry = QLineEdit()
        self.stok_hareket_bas_tarih_entry.setText((datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
        filter_layout.addWidget(self.stok_hareket_bas_tarih_entry)
        
        takvim_button_bas = QPushButton("🗓️")
        takvim_button_bas.setFixedWidth(30)
        takvim_button_bas.clicked.connect(lambda: DatePickerDialog(self.app, self.stok_hareket_bas_tarih_entry))
        filter_layout.addWidget(takvim_button_bas)

        filter_layout.addWidget(QLabel("Bitiş Tarihi:"))
        self.stok_hareket_bit_tarih_entry = QLineEdit()
        self.stok_hareket_bit_tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        filter_layout.addWidget(self.stok_hareket_bit_tarih_entry)
        
        takvim_button_bit = QPushButton("🗓️")
        takvim_button_bit.setFixedWidth(30)
        takvim_button_bit.clicked.connect(lambda: DatePickerDialog(self.app, self.stok_hareket_bit_tarih_entry))
        filter_layout.addWidget(takvim_button_bit)

        yenile_button = QPushButton("Yenile")
        yenile_button.clicked.connect(self._load_stok_hareketleri)
        filter_layout.addWidget(yenile_button)

        # Stok Hareketleri QTreeWidget
        tree_frame = QFrame(self)
        tree_layout = QVBoxLayout(tree_frame)
        self.main_layout.addWidget(tree_frame)
        tree_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols_stok_hareket = ("ID", "Tarih", "İşlem Tipi", "Miktar", "Önceki Stok", "Sonraki Stok", "Açıklama", "Kaynak")
        self.stok_hareket_tree = QTreeWidget(tree_frame)
        self.stok_hareket_tree.setHeaderLabels(cols_stok_hareket)
        self.stok_hareket_tree.setColumnCount(len(cols_stok_hareket))
        self.stok_hareket_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.stok_hareket_tree.setSortingEnabled(True)

        col_defs_stok_hareket = [
            ("ID", 40, Qt.AlignRight),
            ("Tarih", 80, Qt.AlignCenter),
            ("İşlem Tipi", 150, Qt.AlignLeft),
            ("Miktar", 80, Qt.AlignRight),
            ("Önceki Stok", 90, Qt.AlignRight),
            ("Sonraki Stok", 90, Qt.AlignRight),
            ("Açıklama", 250, Qt.AlignLeft),
            ("Kaynak", 100, Qt.AlignLeft)
        ]
        for i, (col_name, width, alignment) in enumerate(col_defs_stok_hareket):
            self.stok_hareket_tree.setColumnWidth(i, width)
            self.stok_hareket_tree.headerItem().setTextAlignment(i, alignment)
            self.stok_hareket_tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))

        self.stok_hareket_tree.header().setStretchLastSection(False)
        self.stok_hareket_tree.header().setSectionResizeMode(6, QHeaderView.Stretch) # Açıklama sütunu genişlesin
        
        tree_layout.addWidget(self.stok_hareket_tree)

        # Sağ tık menüsünü bağlama
        self.stok_hareket_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.stok_hareket_tree.customContextMenuRequested.connect(self._open_stok_hareket_context_menu)

        self._load_stok_hareketleri()

    def _on_stok_hareket_select(self): # event=None kaldırıldı
        # Bu metod artık sadece QTreeWidget'taki seçimi yönetmek için kullanılabilir.
        # Silme butonu durumu _open_stok_hareket_context_menu'da yönetiliyor.
        pass

    def _open_stok_hareket_context_menu(self, pos): # pos parametresi customContextMenuRequested sinyalinden gelir
        item = self.stok_hareket_tree.itemAt(pos) # Tıklanan öğeyi al
        
        if not item:
            return

        self.stok_hareket_tree.setCurrentItem(item) # Tıklanan öğeyi seçili yap
        
        kaynak_tipi = item.text(7) # Kaynak sütunu (indeks 7)

        context_menu = QMenu(self)
        
        if kaynak_tipi == 'MANUEL':
            delete_action = context_menu.addAction("Stok Hareketini Sil")
            delete_action.triggered.connect(self._secili_stok_hareketini_sil)
        
        # Eğer menüde öğe varsa göster
        if context_menu.actions():
            context_menu.exec(self.stok_hareket_tree.mapToGlobal(pos))
             
    def _secili_stok_hareketini_sil(self):
        selected_items = self.stok_hareket_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir stok hareketi seçin.")
            return
            
        item_qt = selected_items[0]
        
        try:
            hareket_id = int(item_qt.text(0)) # ID
            islem_tipi = item_qt.text(2) # İşlem Tipi
            miktar = float(item_qt.text(3).replace(',', '.')) # Miktar
            kaynak = item_qt.text(7) # Kaynak
        except (ValueError, IndexError):
            QMessageBox.critical(self.app, "Hata", "Seçili hareketin verileri okunamadı.")
            return

        # Sadece MANUEL kaynaklı hareketleri silmeye izin ver.
        if kaynak != 'MANUEL':
            QMessageBox.warning(self.app, "Silme Engellendi", "Sadece 'MANUEL' kaynaklı stok hareketleri silinebilir.\nOtomatik oluşan hareketler (Fatura, Tahsilat, Ödeme vb.) ilgili modüllerden yönetilmelidir.")
            return

        reply = QMessageBox.question(self.app, "Onay", f"'{islem_tipi}' tipindeki {miktar} miktarındaki stok hareketini silmek istediğinizden emin misiniz?\n\nBu işlem, ürünün ana stoğunu da etkileyecektir ve geri alınamaz!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No) # Default No
        
        if reply == QMessageBox.Yes:
            success, message = self.db.manuel_stok_hareketi_sil(hareket_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self._load_stok_hareketleri() # Bu sekmenin kendi listesini yenile
                
                # Parent pencere (StokKartiPenceresi) referansı varsa, onu da yenile
                if self.parent_pencere and hasattr(self.parent_pencere, 'refresh_data_and_ui'):
                    try:
                        self.parent_pencere.refresh_data_and_ui() # Ana ürün kartını yenile
                    except Exception as e_refresh:
                        logging.warning(f"UYARI: Ürün Kartı refresh_data_and_ui çağrılırken hata: {e_refresh}")
                
                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi.stok_listesini_yenile() # Ana stok listesini yenile
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self.app, "Hata", message)
                self.app.set_status_message(f"Stok hareketi silinirken hata: {message}")
        else:
            self.app.set_status_message("Stok hareketi silme işlemi iptal edildi.")

    def refresh_data_and_ui(self):
        """
        Ürüne ait en güncel verileri veritabanından çeker ve tüm arayüzü yeniler.
        Bu metot, alt pencerelerden (Stok Hareketi gibi) gelen sinyaller üzerine çağrılır.
        """
        logging.debug("StokHareketleriSekmesi.refresh_data_and_ui çağrıldı.")
        # Bu metodun ne yapacağı, StokHareketleriSekmesi'nin kendisi değil,
        # onu çağıran StokKartiPenceresi'nin içindeki mantıkla ilgilidir.
        # Bu sekme kendi listesini _load_stok_hareketleri ile yeniler.
        self._load_stok_hareketleri()


    def _load_stok_hareketleri(self): # event=None kaldırıldı
        self.stok_hareket_tree.clear() # QTreeWidget'ı temizle

        if not self.urun_id:
            item_qt = QTreeWidgetItem(self.stok_hareket_tree)
            item_qt.setText(2, "Ürün Seçili Değil") # İşlem Tipi sütunu
            return

        islem_tipi_filtre = self.stok_hareket_tip_filter_cb.currentText()
        bas_tarih_str = self.stok_hareket_bas_tarih_entry.text()
        bit_tarih_str = self.stok_hareket_bit_tarih_entry.text()

        hareketler = self.db.stok_hareketleri_listele(
            self.urun_id,
            islem_tipi=islem_tipi_filtre if islem_tipi_filtre != "TÜMÜ" else None,
            baslangic_tarih=bas_tarih_str if bas_tarih_str else None,
            bitis_tarih=bit_tarih_str if bit_tarih_str else None
        )

        if not hareketler:
            item_qt = QTreeWidgetItem(self.stok_hareket_tree)
            item_qt.setText(2, "Hareket Bulunamadı") # İşlem Tipi sütunu
            return

        for hareket in hareketler:
            # hareket: sqlite3.Row objesi (id, urun_id, tarih, islem_tipi, miktar, onceki_stok, sonraki_stok, aciklama, kaynak)
            tarih_obj = hareket['tarih']
            if isinstance(tarih_obj, (date, datetime)):
                tarih_formatted = tarih_obj.strftime('%d.%m.%Y')
            else:
                tarih_formatted = str(tarih_obj)

            miktar_formatted = f"{hareket['miktar']:.2f}".rstrip('0').rstrip('.')
            onceki_stok_formatted = f"{hareket['onceki_stok']:.2f}".rstrip('0').rstrip('.')
            sonraki_stok_formatted = f"{hareket['sonraki_stok']:.2f}".rstrip('0').rstrip('.')

            item_qt = QTreeWidgetItem(self.stok_hareket_tree)
            item_qt.setText(0, str(hareket['id'])) # ID
            item_qt.setText(1, tarih_formatted) # Tarih
            item_qt.setText(2, hareket['islem_tipi']) # İşlem Tipi
            item_qt.setText(3, miktar_formatted) # Miktar
            item_qt.setText(4, onceki_stok_formatted) # Önceki Stok
            item_qt.setText(5, sonraki_stok_formatted) # Sonraki Stok
            item_qt.setText(6, hareket['aciklama'] if hareket['aciklama'] else "-") # Açıklama
            item_qt.setText(7, hareket['kaynak'] if hareket['kaynak'] else "-") # Kaynak

            # Sayısal sütunlar için sıralama anahtarları
            item_qt.setData(0, Qt.UserRole, hareket['id']) # ID
            item_qt.setData(3, Qt.UserRole, hareket['miktar']) # Miktar
            item_qt.setData(4, Qt.UserRole, hareket['onceki_stok']) # Önceki Stok
            item_qt.setData(5, Qt.UserRole, hareket['sonraki_stok']) # Sonraki Stok

        self.app.set_status_message(f"Ürün '{self.urun_adi}' için {len(hareketler)} stok hareketi listelendi.")

class IlgiliFaturalarSekmesi(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent_notebook, db_manager, app_ref, urun_id, urun_adi):
        super().__init__(parent_notebook)
        self.db = db_manager
        self.app = app_ref
        self.urun_id = urun_id
        self.urun_adi = urun_adi

        self.main_layout = QVBoxLayout(self) # Ana layout QVBoxLayout

        filter_frame = QFrame(self)
        filter_layout = QHBoxLayout(filter_frame)
        self.main_layout.addWidget(filter_frame)

        filter_layout.addWidget(QLabel("Fatura Tipi:"))
        self.fatura_tipi_filter_cb = QComboBox()
        self.fatura_tipi_filter_cb.addItems(["TÜMÜ", "ALIŞ", "SATIŞ"])
        self.fatura_tipi_filter_cb.setCurrentText("TÜMÜ")
        self.fatura_tipi_filter_cb.currentIndexChanged.connect(self._load_ilgili_faturalar)
        filter_layout.addWidget(self.fatura_tipi_filter_cb)

        filtrele_button = QPushButton("Filtrele")
        filtrele_button.clicked.connect(self._load_ilgili_faturalar)
        filter_layout.addWidget(filtrele_button)

        cols_fatura = ("ID", "Fatura No", "Tarih", "Tip", "Cari/Misafir", "KDV Hariç Top.", "KDV Dahil Top.")
        self.ilgili_faturalar_tree = QTreeWidget(self)
        self.ilgili_faturalar_tree.setHeaderLabels(cols_fatura)
        self.ilgili_faturalar_tree.setColumnCount(len(cols_fatura))
        self.ilgili_faturalar_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ilgili_faturalar_tree.setSortingEnabled(True)

        col_defs_fatura = [
            ("ID", 40, Qt.AlignRight),
            ("Fatura No", 120, Qt.AlignLeft),
            ("Tarih", 85, Qt.AlignCenter),
            ("Tip", 70, Qt.AlignCenter),
            ("Cari/Misafir", 200, Qt.AlignLeft),
            ("KDV Hariç Top.", 120, Qt.AlignRight),
            ("KDV Dahil Top.", 120, Qt.AlignRight)
        ]
        for i, (col_name, width, alignment) in enumerate(col_defs_fatura):
            self.ilgili_faturalar_tree.setColumnWidth(i, width)
            self.ilgili_faturalar_tree.headerItem().setTextAlignment(i, alignment)
            self.ilgili_faturalar_tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))

        self.ilgili_faturalar_tree.header().setStretchLastSection(False)
        self.ilgili_faturalar_tree.header().setSectionResizeMode(1, QHeaderView.Stretch) # Fatura No genişlesin
        self.ilgili_faturalar_tree.header().setSectionResizeMode(4, QHeaderView.Stretch) # Cari/Misafir genişlesin

        self.main_layout.addWidget(self.ilgili_faturalar_tree) # Treeview'i ana layout'a ekle

        self.ilgili_faturalar_tree.itemDoubleClicked.connect(self._on_fatura_double_click)

        # _load_ilgili_faturalar'ı ilk yüklemede otomatik çağır (sekme seçildiğinde)
        self._load_ilgili_faturalar()

    def _load_ilgili_faturalar(self): # event=None kaldırıldı
        self.ilgili_faturalar_tree.clear() # QTreeWidget'ı temizle

        if not self.urun_id:
            item_qt = QTreeWidgetItem(self.ilgili_faturalar_tree)
            item_qt.setText(4, "Ürün seçili değil.") # Cari/Misafir sütunu
            return

        fatura_tipi_filtre = self.fatura_tipi_filter_cb.currentText()
        
        faturalar = self.db.get_faturalar_by_urun_id(self.urun_id, fatura_tipi=fatura_tipi_filtre)

        if not faturalar:
            item_qt = QTreeWidgetItem(self.ilgili_faturalar_tree)
            item_qt.setText(4, "Bu ürüne ait fatura bulunamadı.") # Cari/Misafir sütunu
            return

        for fatura_item in faturalar:
            fatura_id = fatura_item['id']
            fatura_no = fatura_item['fatura_no']
            tarih_obj = fatura_item['tarih']
            fatura_tip = fatura_item['tip']
            cari_adi = fatura_item['cari_adi']
            toplam_kdv_haric = fatura_item['toplam_kdv_haric']
            toplam_kdv_dahil = fatura_item['toplam_kdv_dahil']

            # Gelen veri zaten bir tarih nesnesi. Doğrudan formatlıyoruz.
            if isinstance(tarih_obj, (datetime, date)):
                formatted_tarih = tarih_obj.strftime('%d.%m.%Y')
            else:
                formatted_tarih = str(tarih_obj)

            item_qt = QTreeWidgetItem(self.ilgili_faturalar_tree)
            item_qt.setText(0, str(fatura_id)) # ID
            item_qt.setText(1, fatura_no) # Fatura No
            item_qt.setText(2, formatted_tarih) # Tarih
            item_qt.setText(3, fatura_tip) # Tip
            item_qt.setText(4, cari_adi) # Cari/Misafir
            item_qt.setText(5, self.db._format_currency(toplam_kdv_haric)) # KDV Hariç Top.
            item_qt.setText(6, self.db._format_currency(toplam_kdv_dahil)) # KDV Dahil Top.

            # Sayısal sütunlar için sıralama anahtarları
            item_qt.setData(0, Qt.UserRole, fatura_id) # ID
            item_qt.setData(5, Qt.UserRole, toplam_kdv_haric) # KDV Hariç Top.
            item_qt.setData(6, Qt.UserRole, toplam_kdv_dahil) # KDV Dahil Top.

        self.app.set_status_message(f"Ürün '{self.urun_adi}' için {len(faturalar)} fatura listelendi.")

    def _on_fatura_double_click(self, item, column): # item ve column sinyalden gelir
        fatura_id = int(item.text(0)) # ID ilk sütunda
        if fatura_id:
            # FaturaDetayPenceresi'nin PySide6 versiyonu burada çağrılacak.
            QMessageBox.information(self.app, "Fatura Detay", f"Fatura ID: {fatura_id} için Detay penceresi açılacak.")

class KategoriMarkaYonetimiSekmesi(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent_notebook, db_manager, app_ref):
        super().__init__(parent_notebook)
        self.db = db_manager
        self.app = app_ref

        self.main_layout = QHBoxLayout(self) # Ana layout yatay olacak

        # Sol taraf: Kategori Yönetimi
        kategori_frame = QFrame(self)
        kategori_layout = QGridLayout(kategori_frame)
        self.main_layout.addWidget(kategori_frame)
        kategori_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        kategori_layout.addWidget(QLabel("Kategori Yönetimi", font=QFont("Segoe UI", 12, QFont.Bold)), 0, 0, 1, 5, alignment=Qt.AlignLeft)

        kategori_layout.addWidget(QLabel("Kategori Adı:"), 1, 0, Qt.AlignLeft)
        self.kategori_entry = QLineEdit()
        kategori_layout.addWidget(self.kategori_entry, 1, 1, 1, 1) # Genişlesin
        kategori_layout.setColumnStretch(1, 1) # Entry sütunu genişlesin

        ekle_kategori_button = QPushButton("Ekle")
        ekle_kategori_button.clicked.connect(self._kategori_ekle_ui)
        kategori_layout.addWidget(ekle_kategori_button, 1, 2)

        guncelle_kategori_button = QPushButton("Güncelle")
        guncelle_kategori_button.clicked.connect(self._kategori_guncelle_ui)
        kategori_layout.addWidget(guncelle_kategori_button, 1, 3)

        sil_kategori_button = QPushButton("Sil")
        sil_kategori_button.clicked.connect(self._kategori_sil_ui)
        kategori_layout.addWidget(sil_kategori_button, 1, 4)

        self.kategori_tree = QTreeWidget(kategori_frame)
        self.kategori_tree.setHeaderLabels(["ID", "Kategori Adı"])
        self.kategori_tree.setColumnCount(2)
        self.kategori_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.kategori_tree.setSortingEnabled(True)
        
        self.kategori_tree.setColumnWidth(0, 50)
        self.kategori_tree.header().setSectionResizeMode(0, QHeaderView.Fixed) # ID sabit
        self.kategori_tree.header().setSectionResizeMode(1, QHeaderView.Stretch) # Kategori Adı genişlesin
        self.kategori_tree.headerItem().setFont(0, QFont("Segoe UI", 9, QFont.Bold))
        self.kategori_tree.headerItem().setFont(1, QFont("Segoe UI", 9, QFont.Bold))

        kategori_layout.addWidget(self.kategori_tree, 2, 0, 1, 5) # Row 2, Col 0, span 1 row, 5 cols
        
        self.kategori_tree.itemSelectionChanged.connect(self._on_kategori_select)


        # Sağ taraf: Marka Yönetimi
        marka_frame = QFrame(self)
        marka_layout = QGridLayout(marka_frame)
        self.main_layout.addWidget(marka_frame)
        marka_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        marka_layout.addWidget(QLabel("Marka Yönetimi", font=QFont("Segoe UI", 12, QFont.Bold)), 0, 0, 1, 5, alignment=Qt.AlignLeft)

        marka_layout.addWidget(QLabel("Marka Adı:"), 1, 0, Qt.AlignLeft)
        self.marka_entry = QLineEdit()
        marka_layout.addWidget(self.marka_entry, 1, 1, 1, 1) # Genişlesin
        marka_layout.setColumnStretch(1, 1) # Entry sütunu genişlesin

        ekle_marka_button = QPushButton("Ekle")
        ekle_marka_button.clicked.connect(self._marka_ekle_ui)
        marka_layout.addWidget(ekle_marka_button, 1, 2)

        guncelle_marka_button = QPushButton("Güncelle")
        guncelle_marka_button.clicked.connect(self._marka_guncelle_ui)
        marka_layout.addWidget(guncelle_marka_button, 1, 3)

        sil_marka_button = QPushButton("Sil")
        sil_marka_button.clicked.connect(self._marka_sil_ui)
        marka_layout.addWidget(sil_marka_button, 1, 4)

        self.marka_tree = QTreeWidget(marka_frame)
        self.marka_tree.setHeaderLabels(["ID", "Marka Adı"])
        self.marka_tree.setColumnCount(2)
        self.marka_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.marka_tree.setSortingEnabled(True)

        self.marka_tree.setColumnWidth(0, 50)
        self.marka_tree.header().setSectionResizeMode(0, QHeaderView.Fixed) # ID sabit
        self.marka_tree.header().setSectionResizeMode(1, QHeaderView.Stretch) # Marka Adı genişlesin
        self.marka_tree.headerItem().setFont(0, QFont("Segoe UI", 9, QFont.Bold))
        self.marka_tree.headerItem().setFont(1, QFont("Segoe UI", 9, QFont.Bold))

        marka_layout.addWidget(self.marka_tree, 2, 0, 1, 5) # Row 2, Col 0, span 1 row, 5 cols
        
        self.marka_tree.itemSelectionChanged.connect(self._on_marka_select)

        # İlk yüklemeleri yap
        self._kategori_listesini_yukle()
        self._marka_listesini_yukle()

    # Kategori Yönetimi Metotları
    def _kategori_listesini_yukle(self):
        self.kategori_tree.clear()
        kategoriler = self.db.kategori_listele()
        for kat_id, kat_ad in kategoriler:
            item_qt = QTreeWidgetItem(self.kategori_tree)
            item_qt.setText(0, str(kat_id))
            item_qt.setText(1, kat_ad)
            item_qt.setData(0, Qt.UserRole, kat_id) # ID için sıralama verisi
        self.kategori_tree.sortByColumn(1, Qt.AscendingOrder) # Kategori adına göre sırala

    def _on_kategori_select(self): # event=None kaldırıldı
        selected_items = self.kategori_tree.selectedItems()
        if selected_items:
            values = selected_items[0].text(1) # Kategori Adı
            self.kategori_entry.setText(values)
        else:
            self.kategori_entry.clear()

    def _kategori_ekle_ui(self):
        kategori_adi = self.kategori_entry.text().strip()
        if not kategori_adi:
            QMessageBox.warning(self.app, "Uyarı", "Kategori adı boş olamaz.")
            return

        try:
            api_url = "http://127.0.0.1:8000/nitelikler/kategoriler" # API'deki kategori ekleme endpoint'i
            data = {"kategori_adi": kategori_adi}
            response = requests.post(api_url, json=data)
            response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat

            QMessageBox.information(self.app, "Başarılı", f"'{kategori_adi}' kategorisi başarıyla eklendi.")
            self.kategori_entry.clear()
            self._kategori_listesini_yukle() # Listeyi yenile
            # Stok Yönetimi Sayfasındaki combobox'ı da güncelle
            if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
            self.app.set_status_message(f"'{kategori_adi}' kategorisi başarıyla eklendi.")

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self.app, "Hata", f"Kategori eklenirken bir hata oluştu:\n{error_detail}")
            self.app.set_status_message(f"Kategori ekleme başarısız: {error_detail}")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Kategori eklenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Kategori eklenirken hata: {e}")

    def _kategori_guncelle_ui(self):
        selected_items = self.kategori_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen güncellemek için bir kategori seçin.")
            return
        
        selected_item = selected_items[0]
        kategori_id = selected_item.data(0, Qt.UserRole) # ID'yi al
        yeni_kategori_adi = self.kategori_entry.text().strip()
        
        if not yeni_kategori_adi:
            QMessageBox.warning(self.app, "Uyarı", "Kategori adı boş olamaz.")
            return

        try:
            # API'ye PUT isteği gönder
            api_url = f"http://127.0.0.1:8000/nitelikler/kategoriler/{kategori_id}"
            data = {"id": kategori_id, "kategori_adi": yeni_kategori_adi} # ID'yi de modelde göndermeliyiz
            response = requests.put(api_url, json=data)
            response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat

            QMessageBox.information(self.app, "Başarılı", f"'{yeni_kategori_adi}' kategorisi başarıyla güncellendi.")
            self.kategori_entry.clear()
            self._kategori_listesini_yukle() # Listeyi yenile
            # Stok Yönetimi Sayfasındaki combobox'ı da güncelle
            if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
            self.app.set_status_message(f"'{yeni_kategori_adi}' kategorisi başarıyla güncellendi.")

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self.app, "Hata", f"Kategori güncellenirken bir hata oluştu:\n{error_detail}")
            self.app.set_status_message(f"Kategori güncelleme başarısız: {error_detail}")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Kategori güncellenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Kategori güncellenirken hata: {e}")

    def _kategori_sil_ui(self):
        selected_items = self.kategori_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir kategori seçin.")
            return
        
        selected_item = selected_items[0]
        kategori_id = selected_item.data(0, Qt.UserRole) # ID'yi al
        kategori_adi = selected_item.text(1) # Kategori Adı
        
        reply = QMessageBox.question(self.app, "Onay", f"'{kategori_adi}' kategorisini silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # API'ye DELETE isteği gönder
                api_url = f"http://127.0.0.1:8000/nitelikler/kategoriler/{kategori_id}"
                response = requests.delete(api_url)
                response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat
                
                QMessageBox.information(self.app, "Başarılı", f"'{kategori_adi}' kategorisi başarıyla silindi.")
                self.kategori_entry.clear()
                self._kategori_listesini_yukle() # Listeyi yenile
                # Stok Yönetimi Sayfasındaki combobox'ı da güncelle
                if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                self.app.set_status_message(f"'{kategori_adi}' kategorisi başarıyla silindi.")

            except requests.exceptions.RequestException as e:
                error_detail = str(e)
                if e.response is not None:
                    try:
                        error_detail = e.response.json().get('detail', error_detail)
                    except ValueError:
                        pass
                QMessageBox.critical(self.app, "Hata", f"Kategori silinirken bir hata oluştu:\n{error_detail}")
                self.app.set_status_message(f"Kategori silme başarısız: {error_detail}")
            except Exception as e:
                QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Kategori silinirken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Kategori silinirken hata: {e}")

    # Marka Yönetimi Metotları
    def _marka_listesini_yukle(self):
        self.marka_tree.clear()
        markalar = self.db.marka_listele()
        for mar_id, mar_ad in markalar:
            item_qt = QTreeWidgetItem(self.marka_tree)
            item_qt.setText(0, str(mar_id))
            item_qt.setText(1, mar_ad)
            item_qt.setData(0, Qt.UserRole, mar_id) # ID için sıralama verisi
        self.marka_tree.sortByColumn(1, Qt.AscendingOrder) # Marka adına göre sırala

    def _on_marka_select(self): # event=None kaldırıldı
        selected_items = self.marka_tree.selectedItems()
        if selected_items:
            values = selected_items[0].text(1) # Marka Adı
            self.marka_entry.setText(values)
        else:
            self.marka_entry.clear()

    def _marka_ekle_ui(self):
        marka_adi = self.marka_entry.text().strip()
        if not marka_adi:
            QMessageBox.warning(self.app, "Uyarı", "Marka adı boş olamaz.")
            return

        try:
            api_url = "http://127.0.0.1:8000/nitelikler/markalar" # API'deki marka ekleme endpoint'i
            data = {"marka_adi": marka_adi}
            response = requests.post(api_url, json=data)
            response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat

            QMessageBox.information(self.app, "Başarılı", f"'{marka_adi}' markası başarıyla eklendi.")
            self.marka_entry.clear()
            self._marka_listesini_yukle() # Listeyi yenile
            # Stok Yönetimi Sayfasındaki combobox'ı da güncelle
            if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
            self.app.set_status_message(f"'{marka_adi}' markası başarıyla eklendi.")

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self.app, "Hata", f"Marka eklenirken bir hata oluştu:\n{error_detail}")
            self.app.set_status_message(f"Marka ekleme başarısız: {error_detail}")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Marka eklenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Marka eklenirken hata: {e}")

    def _marka_guncelle_ui(self):
        selected_items = self.marka_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen güncellemek için bir marka seçin.")
            return
        
        selected_item = selected_items[0]
        marka_id = selected_item.data(0, Qt.UserRole) # ID'yi al
        yeni_marka_adi = self.marka_entry.text().strip()
        
        if not yeni_marka_adi:
            QMessageBox.warning(self.app, "Uyarı", "Marka adı boş olamaz.")
            return

        try:
            # API'ye PUT isteği gönder
            api_url = f"http://127.0.0.1:8000/nitelikler/markalar/{marka_id}"
            data = {"id": marka_id, "marka_adi": yeni_marka_adi} # ID'yi de modelde göndermeliyiz
            response = requests.put(api_url, json=data)
            response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat

            QMessageBox.information(self.app, "Başarılı", f"'{yeni_marka_adi}' markası başarıyla güncellendi.")
            self.marka_entry.clear()
            self._marka_listesini_yukle() # Listeyi yenile
            # Stok Yönetimi Sayfasındaki combobox'ı da güncelle
            if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
            self.app.set_status_message(f"'{yeni_marka_adi}' markası başarıyla güncellendi.")

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            QMessageBox.critical(self.app, "Hata", f"Marka güncellenirken bir hata oluştu:\n{error_detail}")
            self.app.set_status_message(f"Marka güncelleme başarısız: {error_detail}")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Marka güncellenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Marka güncellenirken hata: {e}")

    def _marka_sil_ui(self):
        selected_items = self.marka_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir marka seçin.")
            return
        
        selected_item = selected_items[0]
        marka_id = selected_item.data(0, Qt.UserRole) # ID'yi al
        marka_adi = selected_item.text(1) # Marka Adı
        
        reply = QMessageBox.question(self.app, "Onay", f"'{marka_adi}' markasını silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # API'ye DELETE isteği gönder
                api_url = f"http://127.0.0.1:8000/nitelikler/markalar/{marka_id}"
                response = requests.delete(api_url)
                response.raise_for_status() # HTTP 200 olmayan durumlar için hata fırlat
                
                QMessageBox.information(self.app, "Başarılı", f"'{marka_adi}' markası başarıyla silindi.")
                self.marka_entry.clear()
                self._marka_listesini_yukle() # Listeyi yenile
                # Stok Yönetimi Sayfasındaki combobox'ı da güncelle
                if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                self.app.set_status_message(f"'{marka_adi}' markası başarıyla silindi.")

            except requests.exceptions.RequestException as e:
                error_detail = str(e)
                if e.response is not None:
                    try:
                        error_detail = e.response.json().get('detail', error_detail)
                    except ValueError:
                        pass
                QMessageBox.critical(self.app, "Hata", f"Marka silinirken bir hata oluştu:\n{error_detail}")
                self.app.set_status_message(f"Marka silme başarısız: {error_detail}")
            except Exception as e:
                QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Marka silinirken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Marka silinirken hata: {e}")

# UrunNitelikYonetimiSekmesi sınıfı (Dönüştürülmüş PySide6 versiyonu)
class UrunNitelikYonetimiSekmesi(QWidget): # ttk.Frame yerine QWidget
    def __init__(self, parent_notebook, db_manager, app_ref):
        super().__init__(parent_notebook)
        self.db = db_manager
        self.app = app_ref

        self.main_layout = QHBoxLayout(self) # Ana layout yatay olacak

        # Sol taraf: Ürün Grubu Yönetimi
        urun_grubu_frame = QFrame(self)
        urun_grubu_layout = QGridLayout(urun_grubu_frame)
        self.main_layout.addWidget(urun_grubu_frame)
        urun_grubu_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        urun_grubu_layout.addWidget(QLabel("Ürün Grubu Yönetimi", font=QFont("Segoe UI", 12, QFont.Bold)), 0, 0, 1, 5, alignment=Qt.AlignLeft)

        urun_grubu_layout.addWidget(QLabel("Grup Adı:"), 1, 0, Qt.AlignLeft)
        self.urun_grubu_entry = QLineEdit()
        urun_grubu_layout.addWidget(self.urun_grubu_entry, 1, 1, 1, 1)
        urun_grubu_layout.setColumnStretch(1, 1)

        ekle_urun_grubu_button = QPushButton("Ekle")
        ekle_urun_grubu_button.clicked.connect(self._urun_grubu_ekle_ui)
        urun_grubu_layout.addWidget(ekle_urun_grubu_button, 1, 2)

        guncelle_urun_grubu_button = QPushButton("Güncelle")
        guncelle_urun_grubu_button.clicked.connect(self._urun_grubu_guncelle_ui)
        urun_grubu_layout.addWidget(guncelle_urun_grubu_button, 1, 3)

        sil_urun_grubu_button = QPushButton("Sil")
        sil_urun_grubu_button.clicked.connect(self._urun_grubu_sil_ui)
        urun_grubu_layout.addWidget(sil_urun_grubu_button, 1, 4)

        self.urun_grubu_tree = QTreeWidget(urun_grubu_frame)
        self.urun_grubu_tree.setHeaderLabels(["ID", "Grup Adı"])
        self.urun_grubu_tree.setColumnCount(2)
        self.urun_grubu_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.urun_grubu_tree.setSortingEnabled(True)

        self.urun_grubu_tree.setColumnWidth(0, 50)
        self.urun_grubu_tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.urun_grubu_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.urun_grubu_tree.headerItem().setFont(0, QFont("Segoe UI", 9, QFont.Bold))
        self.urun_grubu_tree.headerItem().setFont(1, QFont("Segoe UI", 9, QFont.Bold))

        urun_grubu_layout.addWidget(self.urun_grubu_tree, 2, 0, 1, 5)
        self.urun_grubu_tree.itemSelectionChanged.connect(self._on_urun_grubu_select)


        # Orta taraf: Ürün Birimi Yönetimi
        urun_birimi_frame = QFrame(self)
        urun_birimi_layout = QGridLayout(urun_birimi_frame)
        self.main_layout.addWidget(urun_birimi_frame)
        urun_birimi_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        urun_birimi_layout.addWidget(QLabel("Ürün Birimi Yönetimi", font=QFont("Segoe UI", 12, QFont.Bold)), 0, 0, 1, 5, alignment=Qt.AlignLeft)

        urun_birimi_layout.addWidget(QLabel("Birim Adı:"), 1, 0, Qt.AlignLeft)
        self.urun_birimi_entry = QLineEdit()
        urun_birimi_layout.addWidget(self.urun_birimi_entry, 1, 1, 1, 1)
        urun_birimi_layout.setColumnStretch(1, 1)

        ekle_urun_birimi_button = QPushButton("Ekle")
        ekle_urun_birimi_button.clicked.connect(self._urun_birimi_ekle_ui)
        urun_birimi_layout.addWidget(ekle_urun_birimi_button, 1, 2)

        guncelle_urun_birimi_button = QPushButton("Güncelle")
        guncelle_urun_birimi_button.clicked.connect(self._urun_birimi_guncelle_ui)
        urun_birimi_layout.addWidget(guncelle_urun_birimi_button, 1, 3)

        sil_urun_birimi_button = QPushButton("Sil")
        sil_urun_birimi_button.clicked.connect(self._urun_birimi_sil_ui)
        urun_birimi_layout.addWidget(sil_urun_birimi_button, 1, 4)

        self.urun_birimi_tree = QTreeWidget(urun_birimi_frame)
        self.urun_birimi_tree.setHeaderLabels(["ID", "Birim Adı"])
        self.urun_birimi_tree.setColumnCount(2)
        self.urun_birimi_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.urun_birimi_tree.setSortingEnabled(True)

        self.urun_birimi_tree.setColumnWidth(0, 50)
        self.urun_birimi_tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.urun_birimi_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.urun_birimi_tree.headerItem().setFont(0, QFont("Segoe UI", 9, QFont.Bold))
        self.urun_birimi_tree.headerItem().setFont(1, QFont("Segoe UI", 9, QFont.Bold))

        urun_birimi_layout.addWidget(self.urun_birimi_tree, 2, 0, 1, 5)
        self.urun_birimi_tree.itemSelectionChanged.connect(self._on_urun_birimi_select)


        # Sağ taraf: Ülke Yönetimi
        ulke_frame = QFrame(self)
        ulke_layout = QGridLayout(ulke_frame)
        self.main_layout.addWidget(ulke_frame)
        ulke_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        ulke_layout.addWidget(QLabel("Ülke Yönetimi", font=QFont("Segoe UI", 12, QFont.Bold)), 0, 0, 1, 5, alignment=Qt.AlignLeft)

        ulke_layout.addWidget(QLabel("Ülke Adı:"), 1, 0, Qt.AlignLeft)
        self.ulke_entry = QLineEdit()
        ulke_layout.addWidget(self.ulke_entry, 1, 1, 1, 1)
        ulke_layout.setColumnStretch(1, 1)

        ekle_ulke_button = QPushButton("Ekle")
        ekle_ulke_button.clicked.connect(self._ulke_ekle_ui)
        ulke_layout.addWidget(ekle_ulke_button, 1, 2)

        guncelle_ulke_button = QPushButton("Güncelle")
        guncelle_ulke_button.clicked.connect(self._ulke_guncelle_ui)
        ulke_layout.addWidget(guncelle_ulke_button, 1, 3)

        sil_ulke_button = QPushButton("Sil")
        sil_ulke_button.clicked.connect(self._ulke_sil_ui)
        ulke_layout.addWidget(sil_ulke_button, 1, 4)

        self.ulke_tree = QTreeWidget(ulke_frame)
        self.ulke_tree.setHeaderLabels(["ID", "Ülke Adı"])
        self.ulke_tree.setColumnCount(2)
        self.ulke_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ulke_tree.setSortingEnabled(True)

        self.ulke_tree.setColumnWidth(0, 50)
        self.ulke_tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.ulke_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ulke_tree.headerItem().setFont(0, QFont("Segoe UI", 9, QFont.Bold))
        self.ulke_tree.headerItem().setFont(1, QFont("Segoe UI", 9, QFont.Bold))

        ulke_layout.addWidget(self.ulke_tree, 2, 0, 1, 5)
        self.ulke_tree.itemSelectionChanged.connect(self._on_ulke_select)

        # İlk yüklemeler
        self._urun_grubu_listesini_yukle()
        self._urun_birimi_listesini_yukle()
        self._ulke_listesini_yukle()


    # Ürün Grubu Yönetimi Metotları
    def _urun_grubu_listesini_yukle(self):
        self.urun_grubu_tree.clear()
        urun_gruplari = self.db.urun_grubu_listele()
        for grup_id, grup_ad in urun_gruplari:
            item_qt = QTreeWidgetItem(self.urun_grubu_tree)
            item_qt.setText(0, str(grup_id))
            item_qt.setText(1, grup_ad)
            item_qt.setData(0, Qt.UserRole, grup_id)
        self.urun_grubu_tree.sortByColumn(1, Qt.AscendingOrder)

    def _on_urun_grubu_select(self): # event=None kaldırıldı
        selected_items = self.urun_grubu_tree.selectedItems()
        if selected_items:
            values = selected_items[0].text(1)
            self.urun_grubu_entry.setText(values)
        else:
            self.urun_grubu_entry.clear()

    def _urun_grubu_ekle_ui(self):
        grup_adi = self.urun_grubu_entry.text().strip()
        success, message = self.db.urun_grubu_ekle(grup_adi)
        if success:
            QMessageBox.information(self.app, "Başarılı", message)
            self.urun_grubu_entry.clear()
            self._urun_grubu_listesini_yukle()
            if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
        else:
            QMessageBox.critical(self.app, "Hata", message)

    def _urun_grubu_guncelle_ui(self):
        selected_items = self.urun_grubu_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen güncellemek için bir ürün grubu seçin.")
            return
        grup_id = selected_items[0].data(0, Qt.UserRole)
        yeni_grup_adi = self.urun_grubu_entry.text().strip()
        if not yeni_grup_adi:
            QMessageBox.warning(self.app, "Uyarı", "Grup adı boş olamaz.")
            return
        success, message = self.db.urun_grubu_guncelle(grup_id, yeni_grup_adi)
        if success:
            QMessageBox.information(self.app, "Başarılı", message)
            self.urun_grubu_entry.clear()
            self._urun_grubu_listesini_yukle()
            if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
        else:
            QMessageBox.critical(self.app, "Hata", message)

    def _urun_grubu_sil_ui(self):
        selected_items = self.urun_grubu_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir ürün grubu seçin.")
            return
        grup_id = selected_items[0].data(0, Qt.UserRole)
        grup_adi = selected_items[0].text(1)
        reply = QMessageBox.question(self.app, "Onay", f"'{grup_adi}' ürün grubunu silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.db.urun_grubu_sil(grup_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.urun_grubu_entry.clear()
                self._urun_grubu_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
            else:
                QMessageBox.critical(self.app, "Hata", message)

    # Ürün Birimi Yönetimi Metotları
    def _urun_birimi_listesini_yukle(self):
        self.urun_birimi_tree.clear()
        urun_birimleri = self.db.urun_birimi_listele()
        for birim_id, birim_ad in urun_birimleri:
            item_qt = QTreeWidgetItem(self.urun_birimi_tree)
            item_qt.setText(0, str(birim_id))
            item_qt.setText(1, birim_ad)
            item_qt.setData(0, Qt.UserRole, birim_id)
        self.urun_birimi_tree.sortByColumn(1, Qt.AscendingOrder)

    def _on_urun_birimi_select(self): # event=None kaldırıldı
        selected_items = self.urun_birimi_tree.selectedItems()
        if selected_items:
            values = selected_items[0].text(1)
            self.urun_birimi_entry.setText(values)
        else:
            self.urun_birimi_entry.clear()

    def _urun_birimi_ekle_ui(self):
        birim_adi = self.urun_birimi_entry.text().strip()
        success, message = self.db.urun_birimi_ekle(birim_adi)
        if success:
            QMessageBox.information(self.app, "Başarılı", message)
            self.urun_birimi_entry.clear()
            self._urun_birimi_listesini_yukle()
            if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
        else:
            QMessageBox.critical(self.app, "Hata", message)

    def _urun_birimi_guncelle_ui(self):
        selected_items = self.urun_birimi_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen güncellemek için bir ürün birimi seçin.")
            return
        birim_id = selected_items[0].data(0, Qt.UserRole)
        yeni_birim_adi = self.urun_birimi_entry.text().strip()
        if not yeni_birim_adi:
            QMessageBox.warning(self.app, "Uyarı", "Birim adı boş olamaz.")
            return
        success, message = self.db.urun_birimi_guncelle(birim_id, yeni_birim_adi)
        if success:
            QMessageBox.information(self.app, "Başarılı", message)
            self.urun_birimi_entry.clear()
            self._urun_birimi_listesini_yukle()
            if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
        else:
            QMessageBox.critical(self.app, "Hata", message)

    def _urun_birimi_sil_ui(self):
        selected_items = self.urun_birimi_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir ürün birimi seçin.")
            return
        birim_id = selected_items[0].data(0, Qt.UserRole)
        birim_adi = selected_items[0].text(1)
        reply = QMessageBox.question(self.app, "Onay", f"'{birim_adi}' ürün birimini silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.db.urun_birimi_sil(birim_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.urun_birimi_entry.clear()
                self._urun_birimi_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
            else:
                QMessageBox.critical(self.app, "Hata", message)

    # Ülke Yönetimi Metotları
    def _ulke_listesini_yukle(self):
        self.ulke_tree.clear()
        ulkeler = self.db.ulke_listele()
        for ulke_id, ulke_ad in ulkeler:
            item_qt = QTreeWidgetItem(self.ulke_tree)
            item_qt.setText(0, str(ulke_id))
            item_qt.setText(1, ulke_ad)
            item_qt.setData(0, Qt.UserRole, ulke_id)
        self.ulke_tree.sortByColumn(1, Qt.AscendingOrder)

    def _on_ulke_select(self): # event=None kaldırıldı
        selected_items = self.ulke_tree.selectedItems()
        if selected_items:
            values = selected_items[0].text(1)
            self.ulke_entry.setText(values)
        else:
            self.ulke_entry.clear()

    def _ulke_ekle_ui(self):
        ulke_adi = self.ulke_entry.text().strip()
        success, message = self.db.ulke_ekle(ulke_adi)
        if success:
            QMessageBox.information(self.app, "Başarılı", message)
            self.ulke_entry.clear()
            self._ulke_listesini_yukle()
            if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
        else:
            QMessageBox.critical(self.app, "Hata", message)

    def _ulke_guncelle_ui(self):
        selected_items = self.ulke_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen güncellemek için bir ülke seçin.")
            return
        ulke_id = selected_items[0].data(0, Qt.UserRole)
        yeni_ulke_adi = self.ulke_entry.text().strip()
        if not yeni_ulke_adi:
            QMessageBox.warning(self.app, "Uyarı", "Ülke adı boş olamaz.")
            return
        success, message = self.db.ulke_guncelle(ulke_id, yeni_ulke_adi)
        if success:
            QMessageBox.information(self.app, "Başarılı", message)
            self.ulke_entry.clear()
            self._ulke_listesini_yukle()
            if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
        else:
            QMessageBox.critical(self.app, "Hata", message)

    def _ulke_sil_ui(self):
        selected_items = self.ulke_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir ülke seçin.")
            return
        ulke_id = selected_items[0].data(0, Qt.UserRole)
        ulke_adi = selected_items[0].text(1)
        reply = QMessageBox.question(self.app, "Onay", f"'{ulke_adi}' ülkesini silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.db.ulke_sil(ulke_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.ulke_entry.clear()
                self._ulke_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi') and hasattr(self.app.stok_yonetimi_sayfasi, '_yukle_filtre_comboboxlari_stok_yonetimi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
            else:
                QMessageBox.critical(self.app, "Hata", message)                
