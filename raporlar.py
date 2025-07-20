# raporlar.py dosyası
import traceback
import os 
from datetime import datetime, date, timedelta
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
import requests
import logging
# PySide6 importları
from PySide6.QtWidgets import (
    QDialog, QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QAbstractItemView, 
    QHeaderView, QMessageBox, QFrame, QComboBox, QLineEdit, QSizePolicy, QTabWidget, QMenu
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QBrush, QColor, QDoubleValidator

# Yerel Uygulama Modülleri
# OnMuhasebe sınıfı veritabanı.py dosyasından geliyor.
# TURKISH_FONT_NORMAL, TURKISH_FONT_BOLD değişkenleri veritabanı.py'de tanımlanmış.
from veritabani import TURKISH_FONT_NORMAL, TURKISH_FONT_BOLD, OnMuhasebe
from yardimcilar import DatePickerDialog, normalize_turkish_chars, setup_locale

# pencereler.py'deki PySide6 sınıflarını import et
from pencereler import CariHesapEkstresiPenceresi, TedarikciSecimDialog, UrunKartiPenceresi, SiparisPenceresi

class CriticalStockWarningPenceresi(QDialog):
    def __init__(self, parent_app, db_manager):
        super().__init__(parent_app)
        self.app = parent_app
        self.db = db_manager # OnMuhasebe objesi
        self.setWindowTitle("Kritik Stok Uyarısı ve Sipariş Önerisi")
        self.setMinimumSize(800, 500)
        self.setModal(True) # Modalı olarak ayarla

        main_layout = QVBoxLayout(self)
        
        # Başlık etiketi
        title_label = QLabel("Kritik Stoktaki Ürünler")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignLeft)
        main_layout.addWidget(title_label, alignment=Qt.AlignTop | Qt.AlignLeft)

        # Bilgi mesajı çerçevesi
        info_frame = QFrame(self)
        info_layout = QVBoxLayout(info_frame)
        main_layout.addWidget(info_frame)
        info_label = QLabel("Minimum stok seviyesinin altında olan ürünler listelenmiştir. İstenilen stok seviyesine ulaşmak için önerilen miktarları sipariş edebilirsiniz.")
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label, alignment=Qt.AlignLeft)

        # Kritik Stok Listesi (TreeWidget)
        tree_frame = QFrame(self)
        tree_layout = QVBoxLayout(tree_frame)
        main_layout.addWidget(tree_frame, 1) # Streç faktör 1, genişlemesini sağlar
        tree_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols = ("Ürün Kodu", "Ürün Adı", "Mevcut Stok", "Min. Stok", "Fark", "Önerilen Sipariş Mik.")
        self.tree = QTreeWidget(tree_frame)
        self.tree.setHeaderLabels(cols)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows) # Tüm satırı seç
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection) # Çoklu seçim
        self.tree.setAlternatingRowColors(True) # Zebra deseni

        # Sütun ayarları
        col_defs = [
            ("Ürün Kodu", 100, Qt.AlignLeft),
            ("Ürün Adı", 250, Qt.AlignLeft),
            ("Mevcut Stok", 100, Qt.AlignRight),
            ("Min. Stok", 100, Qt.AlignRight),
            ("Fark", 80, Qt.AlignRight),
            ("Önerilen Sipariş Mik.", 150, Qt.AlignRight)
        ]
        for i, (col_name, width, alignment) in enumerate(col_defs):
            self.tree.setColumnWidth(i, width)
            self.tree.headerItem().setTextAlignment(i, alignment)
            # FONT KULLANIMI DÜZELTİLDİ
            self.tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name == "Ürün Adı": # Ürün Adı sütunu esnek olsun
                self.tree.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                self.tree.header().setSectionResizeMode(i, QHeaderView.Interactive) # Diğerleri interaktif
        
        tree_layout.addWidget(self.tree)
        
        # Sağ tık menüsü
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._open_context_menu)


        # Butonlar
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame)
        
        btn_yenile = QPushButton("Yenile")
        btn_yenile.clicked.connect(self.load_critical_stock)
        button_layout.addWidget(btn_yenile)
        
        btn_siparis_olustur = QPushButton("Seçili Ürünlerden Sipariş Oluştur")
        btn_siparis_olustur.clicked.connect(self._siparis_olustur_critical_stock)
        button_layout.addWidget(btn_siparis_olustur)

        button_layout.addStretch() # Sağ tarafa yaslamak için boşluk
        
        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.close)
        button_layout.addWidget(btn_kapat)

        self.load_critical_stock() # Pencere açıldığında verileri yükle

    def load_critical_stock(self):
        self.tree.clear()
        
        # db_manager'dan kritik stoktaki ürünleri al
        critical_items = self.db.get_critical_stock_items() # Bu metod db.py içinde tanımlı

        if not critical_items:
            item_qt = QTreeWidgetItem(self.tree)
            item_qt.setText(1, "Kritik Stokta Ürün Bulunmuyor.") # Ürün Adı sütunu
            for i in range(self.tree.columnCount()):
                item_qt.setForeground(i, QBrush(QColor("gray")))
            self.app.set_status_message("Kritik stokta ürün bulunmuyor.")
            return

        for item in critical_items:
            urun_id = item[0]
            urun_kodu = item[1]
            urun_adi = item[2]
            mevcut_stok = item[3]
            min_stok = item[7]
            fark = min_stok - mevcut_stok
            onerilen_siparis = fark # Önerilen miktar, fark kadar

            item_qt = QTreeWidgetItem(self.tree)
            item_qt.setText(0, urun_kodu)
            item_qt.setText(1, urun_adi)
            item_qt.setText(2, f"{mevcut_stok:.2f}".rstrip('0').rstrip('.'))
            item_qt.setText(3, f"{min_stok:.2f}".rstrip('0').rstrip('.'))
            item_qt.setText(4, f"{fark:.2f}".rstrip('0').rstrip('.'))
            item_qt.setText(5, f"{onerilen_siparis:.2f}".rstrip('0').rstrip('.'))
            
            # Ürün ID'sini UserRole olarak sakla
            item_qt.setData(0, Qt.UserRole, urun_id) 

        self.app.set_status_message(f"{len(critical_items)} ürün kritik stok seviyesinin altında.")

    def _open_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return

        self.tree.setCurrentItem(item)

        context_menu = QMenu(self)
        
        open_product_card_action = context_menu.addAction("Ürün Kartını Aç")
        open_product_card_action.triggered.connect(lambda: self._open_urun_karti(item))

        siparis_olustur_action = context_menu.addAction("Bu Üründen Sipariş Oluştur")
        siparis_olustur_action.triggered.connect(lambda: self._siparis_olustur_critical_stock(specific_item=item))

        context_menu.exec(self.tree.mapToGlobal(pos))

    def _open_urun_karti(self, item):
        urun_id = item.data(0, Qt.UserRole)
        if urun_id:
            try:
                # API_BASE_URL'i self.app'ten alıyoruz
                response = requests.get(f"{self.app.API_BASE_URL}/stoklar/{urun_id}")
                response.raise_for_status()
                urun_detaylari = response.json()
                # UrunKartiPenceresi pencereler.py'den import edildi
                dialog = UrunKartiPenceresi(self.app, self.db, self.load_critical_stock, urun_duzenle=urun_detaylari, app_ref=self.app)
                dialog.exec()
            except requests.exceptions.RequestException as e:
                QMessageBox.critical(self.app, "API Hatası", f"Ürün kartı açılamadı: {e}")
                logging.error(f"Kritik stok uyarısı - Ürün kartı açma hatası: {e}")

    def _siparis_olustur_critical_stock(self, specific_item=None):
        """
        Seçili kritik stok ürünlerini toplar ve tedarikçi seçimi sonrası alış siparişi oluşturma akışını başlatır.
        Eğer specific_item verilirse, sadece o üründen sipariş oluşturulur.
        """
        urunler_for_siparis = []
        
        if specific_item:
            selected_items = [specific_item]
        else:
            selected_items = self.tree.selectedItems()

        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen sipariş oluşturmak için bir veya daha fazla ürün seçin.")
            return

        for item_qt in selected_items:
            urun_id = item_qt.data(0, Qt.UserRole)
            urun_adi = item_qt.text(1) # Ürün Adı
            onerilen_miktar_str = item_qt.text(5).replace(',', '.') # Önerilen sipariş miktarı
            
            try:
                onerilen_miktar = float(onerilen_miktar_str)
                if onerilen_miktar <= 0: continue # Negatif veya sıfır önerileri atla
                
                # Ürün detaylarını çek (fiyatlar için)
                # API_BASE_URL'i self.app'ten alıyoruz
                response = requests.get(f"{self.app.API_BASE_URL}/stoklar/{urun_id}")
                response.raise_for_status()
                urun_detay = response.json()

                urunler_for_siparis.append({
                    "id": urun_id,
                    "urun_kodu": urun_detay.get('urun_kodu'),
                    "urun_adi": urun_detay.get('urun_adi'),
                    "miktar": onerilen_miktar,
                    "birim_fiyat": urun_detay.get('alis_fiyati_kdv_haric'), # Alış siparişinde KDV Hariç alış fiyatı
                    "kdv_orani": urun_detay.get('kdv_orani'),
                    "alis_fiyati_siparis_aninda": urun_detay.get('alis_fiyati_kdv_dahil') # KDV dahil alış fiyatı
                })
            except (ValueError, requests.exceptions.RequestException) as e:
                QMessageBox.warning(self, "Hata", f"Ürün '{urun_adi}' için sipariş verisi hazırlanırken hata: {e}")
                logging.error(f"Kritik stok - sipariş hazırlama hatası: {e}")
                return

        if not urunler_for_siparis:
            QMessageBox.information(self, "Bilgi", "Sipariş oluşturmak için geçerli ürün bulunmuyor veya seçilen ürünlerin miktarları sıfırın altında.")
            return

        # TedarikciSecimDialog pencereler.py'den import edildi
        dialog = TedarikciSecimDialog(self, self.db, 
                                     lambda selected_tedarikci_id, selected_tedarikci_ad: 
                                     self._tedarikci_secildi_ve_siparis_olustur(selected_tedarikci_id, selected_tedarikci_ad, urunler_for_siparis))
        dialog.exec() # Modalı olarak göster

    def _tedarikci_secildi_ve_siparis_olustur(self, tedarikci_id, tedarikci_ad, urunler_for_siparis):
        """
        Tedarikçi seçildikten sonra çağrılır. Alış siparişi oluşturma sayfasını başlatır.
        """
        if tedarikci_id:
            # SiparisPenceresi pencereler.py'den import edildi
            try:
                dialog = SiparisPenceresi(
                    self.app, # parent
                    self.db, # db_manager
                    self.app, # app_ref
                    siparis_tipi=self.db.SIPARIS_TIP_ALIS, # Alış siparişi
                    initial_cari_id=tedarikci_id, # Seçili tedarikçiyi gönder
                    initial_urunler=urunler_for_siparis, # Önerilen ürünleri gönder
                    yenile_callback=self.app.siparis_listesi_sayfasi.siparis_listesini_yukle if hasattr(self.app, 'siparis_listesi_sayfasi') else None
                )
                dialog.exec()
                self.app.set_status_message(f"'{tedarikci_ad}' için tedarikçi siparişi oluşturma ekranı açıldı.")
                self.close() # Kritik Stok Uyarısı penceresini kapat
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Sipariş oluşturma penceresi açılamadı: {e}")
                logging.error(f"Kritik stok - sipariş penceresi açma hatası: {e}")
        else:
            self.app.set_status_message("Tedarikçi seçimi iptal edildi. Sipariş oluşturulmadı.")
            QMessageBox.warning(self, "İptal Edildi", "Tedarikçi seçimi yapılmadığı için sipariş oluşturma işlemi iptal edildi.")


class NotificationDetailsPenceresi(QDialog):
    def __init__(self, parent_app, db_manager, notifications_data):
        super().__init__(parent_app)
        self.app = parent_app
        self.db = db_manager
        self.notifications_data = notifications_data 
        self.setWindowTitle("Aktif Bildirim Detayları")
        self.setMinimumSize(900, 600)
        self.setModal(True) # Modalı olarak ayarla

        main_layout = QVBoxLayout(self)

        title_label = QLabel("Aktif Bildirim Detayları")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignLeft)
        main_layout.addWidget(title_label)

        self.notebook_details = QTabWidget(self)
        main_layout.addWidget(self.notebook_details, 1) # Streç faktör 1

        # Kritik Stok Sekmesi
        if 'critical_stock' in self.notifications_data and self.notifications_data['critical_stock']:
            critical_stock_frame = QFrame(self.notebook_details)
            critical_stock_frame.setLayout(QVBoxLayout(critical_stock_frame))
            self.notebook_details.addTab(critical_stock_frame, "📦 Kritik Stok")
            self._create_critical_stock_tab(critical_stock_frame, self.notifications_data['critical_stock'])

        # Vadesi Geçmiş Alacaklar Sekmesi
        if 'overdue_receivables' in self.notifications_data and self.notifications_data['overdue_receivables']:
            overdue_receivables_frame = QFrame(self.notebook_details)
            overdue_receivables_frame.setLayout(QVBoxLayout(overdue_receivables_frame))
            self.notebook_details.addTab(overdue_receivables_frame, "💰 Vadesi Geçmiş Alacaklar")
            self._create_overdue_receivables_tab(overdue_receivables_frame, self.notifications_data['overdue_receivables'])

        # Vadesi Geçmiş Borçlar Sekmesi
        if 'overdue_payables' in self.notifications_data and self.notifications_data['overdue_payables']:
            overdue_payables_frame = QFrame(self.notebook_details)
            overdue_payables_frame.setLayout(QVBoxLayout(overdue_payables_frame))
            self.notebook_details.addTab(overdue_payables_frame, "💸 Vadesi Geçmiş Borçlar")
            self._create_overdue_payables_tab(overdue_payables_frame, self.notifications_data['overdue_payables'])

        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame)
        
        button_layout.addStretch()
        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.close)
        button_layout.addWidget(btn_kapat)

    def _create_critical_stock_tab(self, parent_frame, data):
        cols = ("Ürün Kodu", "Ürün Adı", "Mevcut Stok", "Min. Stok", "Fark", "Önerilen Sipariş Mik.")
        tree = QTreeWidget(parent_frame)
        tree.setHeaderLabels(cols)
        tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        tree.setSelectionMode(QAbstractItemView.ExtendedSelection) # Çoklu seçim
        tree.setAlternatingRowColors(True)

        col_defs = [
            ("Ürün Kodu", 100, Qt.AlignLeft),
            ("Ürün Adı", 250, Qt.AlignLeft),
            ("Mevcut Stok", 100, Qt.AlignRight),
            ("Min. Stok", 100, Qt.AlignRight),
            ("Fark", 80, Qt.AlignRight),
            ("Önerilen Sipariş Mik.", 150, Qt.AlignRight)
        ]
        for i, (col_name, width, alignment) in enumerate(col_defs):
            tree.setColumnWidth(i, width)
            tree.headerItem().setTextAlignment(i, alignment)
            # FONT KULLANIMI DÜZELTİLDİ
            tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name == "Ürün Adı":
                tree.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                tree.header().setSectionResizeMode(i, QHeaderView.Interactive)
        parent_frame.layout().addWidget(tree)

        for item in data:
            urun_id = item[0]
            urun_kodu = item[1]
            urun_adi = item[2]
            mevcut_stok = item[3]
            min_stok = item[7]
            fark = min_stok - mevcut_stok
            onerilen_siparis = fark
            
            item_qt = QTreeWidgetItem(tree)
            item_qt.setText(0, urun_kodu)
            item_qt.setText(1, urun_adi)
            item_qt.setText(2, f"{mevcut_stok:.2f}".rstrip('0').rstrip('.'))
            item_qt.setText(3, f"{min_stok:.2f}".rstrip('0').rstrip('.'))
            item_qt.setText(4, f"{fark:.2f}".rstrip('0').rstrip('.'))
            item_qt.setText(5, f"{onerilen_siparis:.2f}".rstrip('0').rstrip('.'))
            item_qt.setData(0, Qt.UserRole, urun_id) # Ürün ID

    def _create_overdue_receivables_tab(self, parent_frame, data):
        cols = ("Müşteri Adı", "Net Borç", "Vadesi Geçen Gün")
        tree = QTreeWidget(parent_frame)
        tree.setHeaderLabels(cols)
        tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        tree.setSelectionMode(QAbstractItemView.SingleSelection)
        tree.setAlternatingRowColors(True)

        col_defs = [
            ("Müşteri Adı", 250, Qt.AlignLeft),
            ("Net Borç", 120, Qt.AlignRight),
            ("Vadesi Geçen Gün", 120, Qt.AlignRight)
        ]
        for i, (col_name, width, alignment) in enumerate(col_defs):
            tree.setColumnWidth(i, width)
            tree.headerItem().setTextAlignment(i, alignment)
            # FONT KULLANIMI DÜZELTİLDİ: QFont.Bold
            tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name == "Müşteri Adı":
                tree.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                tree.header().setSectionResizeMode(i, QHeaderView.Interactive)
        parent_frame.layout().addWidget(tree)

        for item in data:
            item_qt = QTreeWidgetItem(tree)
            item_qt.setText(0, item[1]) # Müşteri Adı
            item_qt.setText(1, self.db._format_currency(item[2])) # Net Borç
            item_qt.setText(2, str(item[3])) # Vadesi Geçen Gün
            item_qt.setData(0, Qt.UserRole, item[0]) # Cari ID

        tree.itemDoubleClicked.connect(lambda item, col: self._open_cari_ekstresi_from_notification(item, 'MUSTERI'))
            
    def _create_overdue_payables_tab(self, parent_frame, data):
        cols = ("Tedarikçi Adı", "Net Borç", "Vadesi Geçen Gün")
        tree = QTreeWidget(parent_frame)
        tree.setHeaderLabels(cols)
        tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        tree.setSelectionMode(QAbstractItemView.SingleSelection)
        tree.setAlternatingRowColors(True)

        col_defs = [
            ("Tedarikçi Adı", 250, Qt.AlignLeft),
            ("Net Borç", 120, Qt.AlignRight),
            ("Vadesi Geçen Gün", 120, Qt.AlignRight)
        ]
        for i, (col_name, width, alignment) in enumerate(col_defs):
            tree.setColumnWidth(i, width)
            tree.headerItem().setTextAlignment(i, alignment)
            # FONT KULLANIMI DÜZELTİLDİ: QFont.Bold
            tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name == "Tedarikçi Adı":
                tree.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                tree.header().setSectionResizeMode(i, QHeaderView.Interactive)
        parent_frame.layout().addWidget(tree)

        for item in data:
            item_qt = QTreeWidgetItem(tree)
            item_qt.setText(0, item[1]) # Tedarikçi Adı
            item_qt.setText(1, self.db._format_currency(item[2])) # Net Borç
            item_qt.setText(2, str(item[3])) # Vadesi Geçen Gün
            item_qt.setData(0, Qt.UserRole, item[0]) # Cari ID

        tree.itemDoubleClicked.connect(lambda item, col: self._open_cari_ekstresi_from_notification(item, 'TEDARIKCI'))

    def _open_cari_ekstresi_from_notification(self, item, cari_tip):
        cari_id = item.data(0, Qt.UserRole)
        cari_adi = item.text(0) # İlk sütun (Ad)

        if cari_id:
            # CariHesapEkstresiPenceresi pencereler.py'den import edildi
            dialog = CariHesapEkstresiPenceresi(self.app, self.db, cari_id, cari_tip, cari_adi)
            dialog.exec() # Modalı olarak göster
        else:
            QMessageBox.warning(self.app, "Hata", "Cari ID bulunamadı.")