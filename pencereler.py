import locale
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QFileDialog,
    QWidget, QMenuBar, QStatusBar, QDialog, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox,
    QTreeWidget, QTreeWidgetItem, QAbstractItemView, QHeaderView, QTextEdit,
    QCheckBox, QFrame, QTableWidget, QTableWidgetItem, QGroupBox,
    QMenu, QTabWidget,QSizePolicy, QProgressBar, QListWidget, QListWidgetItem )
from PySide6.QtGui import QFont, QPixmap, QImage, QDoubleValidator, QIntValidator, QBrush, QColor
from PySide6.QtCore import Qt, QDate, QTimer, Signal, Slot
import requests # Bu import, bazı eski direct request'ler için kalmış olabilir, ama kullanılmamalı.
from datetime import datetime, date, timedelta
import os
import shutil
import traceback
import threading
import calendar
import multiprocessing
import logging
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill 
from veritabani import OnMuhasebe
from yardimcilar import DatePickerDialog, normalize_turkish_chars, setup_locale
from config import API_BASE_URL # Bu UI tarafında doğrudan kullanılmamalı, OnMuhasebe sınıfı kullanmalı

# Logger kurulumu
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def setup_numeric_entry(parent_app, entry_widget, allow_negative=False, decimal_places=2, max_value=None):
    validator = QDoubleValidator()
    validator.setBottom(0.0 if not allow_negative else -999999999.0)
    validator.setTop(999999999.0 if max_value is None else float(max_value))
    validator.setDecimals(decimal_places)
    validator.setNotation(QDoubleValidator.StandardNotation)
    entry_widget.setValidator(validator)
    entry_widget.textChanged.connect(lambda text: format_and_validate_numeric_input(entry_widget, decimal_places))


def format_and_validate_numeric_input(line_edit: QLineEdit, decimals: int):
    text = line_edit.text()
    if not text:
        return

    cursor_pos = line_edit.cursorPosition()

    if ',' in text:
        text = text.replace(',', '.')
        line_edit.setText(text)
        if cursor_pos <= len(text):
            line_edit.setCursorPosition(cursor_pos)
        else:
            line_edit.setCursorPosition(len(text))

    if text == '.' or text == '-':
        return
    
    try:
        value = float(text)
        formatted_text = f"{value:.{decimals}f}"

        if line_edit.text() != formatted_text.replace('.', ','):
            block_signals = line_edit.blockSignals(True)
            parts = text.split('.')
            if len(parts) > 1 and len(parts[1]) <= decimals:
                pass
            else:
                current_cursor_pos = line_edit.cursorPosition()
                line_edit.setText(formatted_text.replace('.', ','))
                if '.' in text and ',' not in formatted_text:
                    line_edit.setCursorPosition(current_cursor_pos)
                else:
                     line_edit.setCursorPosition(current_cursor_pos)
            line_edit.blockSignals(block_signals)

    except ValueError:
        pass

def setup_date_entry(parent_app, entry_widget):
    pass

class SiparisPenceresi(QDialog):
    def __init__(self, parent, db_manager, app_ref, siparis_tipi, siparis_id_duzenle=None, yenile_callback=None, initial_cari_id=None, initial_urunler=None, initial_data=None):
        super().__init__(parent)
        self.app = app_ref
        self.db = db_manager
        
        self.siparis_tipi = siparis_tipi
        self.siparis_id_duzenle = siparis_id_duzenle
        self.yenile_callback = yenile_callback
        self.initial_cari_id = initial_cari_id
        self.initial_urunler = initial_urunler
        self.initial_data = initial_data

        title = "Yeni Sipariş"
        if siparis_id_duzenle:
            try:
                siparis_info = self.db.siparis_getir_by_id(siparis_id_duzenle)
                siparis_no_display = siparis_info.get('siparis_no', 'Bilinmiyor')
                title = f"Sipariş Güncelleme: {siparis_no_display}"
            except Exception as e:
                logging.error(f"Sipariş bilgisi çekilirken hata: {e}")
                QMessageBox.critical(self, "Hata", "Sipariş bilgisi yüklenirken hata oluştu.")
                title = "Sipariş Güncelleme: Hata"
        else:
            title = "Yeni Müşteri Siparişi" if siparis_tipi == "SATIŞ_SIPARIS" else "Yeni Tedarikçi Siparişi"

        self.setWindowTitle(title)
        self.setWindowState(Qt.WindowMaximized)
        self.setModal(True)

        dialog_layout = QVBoxLayout(self)

        from arayuz import SiparisOlusturmaSayfasi
        self.siparis_form = SiparisOlusturmaSayfasi(
            self,
            self.db,
            self.app,
            self.siparis_tipi,
            duzenleme_id=self.siparis_id_duzenle,
            yenile_callback=self.yenile_callback,
            initial_cari_id=self.initial_cari_id,
            initial_urunler=self.initial_urunler,
            initial_data=self.initial_data
        )
        dialog_layout.addWidget(self.siparis_form)

        self.siparis_form.saved_successfully.connect(self.accept)
        self.siparis_form.cancelled_successfully.connect(self.reject)

        self.finished.connect(self.on_dialog_finished)

    def on_dialog_finished(self, result):
        if result == QDialog.Rejected and self.siparis_id_duzenle is None:
            self.siparis_form._save_current_form_data_to_temp()
        
        if self.yenile_callback:
            self.yenile_callback()

# pencereler.py dosyasındaki CariHesapEkstresiPenceresi sınıfının TAMAMI

class CariHesapEkstresiPenceresi(QDialog):
    def __init__(self, parent_app, db_manager, cari_id, cari_tip, pencere_basligi, parent_list_refresh_func=None):
        super().__init__(parent_app)
        self.app = parent_app
        self.db = db_manager
        self.cari_id = cari_id
        self.cari_tip = cari_tip
        self.cari_ad_gosterim = pencere_basligi
        self.parent_list_refresh_func = parent_list_refresh_func
        self.hareket_detay_map = {}

        self.setWindowTitle(f"Cari Hesap Ekstresi: {self.cari_ad_gosterim}")
        self.setWindowState(Qt.WindowMaximized)
        self.setModal(True)

        main_container = QWidget(self)
        self.setLayout(QVBoxLayout(main_container))
        
        self.ozet_ve_bilgi_frame = QGroupBox("Cari Özet Bilgileri", self)
        self.layout().addWidget(self.ozet_ve_bilgi_frame)
        self._create_ozet_bilgi_alani()

        self.notebook = QTabWidget(self)
        self.layout().addWidget(self.notebook)
        self.notebook.currentChanged.connect(self._on_tab_change)

        self.hesap_hareketleri_tab = QWidget(self.notebook)
        self.notebook.addTab(self.hesap_hareketleri_tab, "Hesap Hareketleri")
        self._create_hesap_hareketleri_tab()

        self.siparisler_tab = QWidget(self.notebook)
        self.notebook.addTab(self.siparisler_tab, "Siparişler")
        self._create_siparisler_tab()

        self.hizli_islemler_ana_frame = QFrame(self)
        self.layout().addWidget(self.hizli_islemler_ana_frame)
        self._create_hizli_islem_alanlari()

        today = date.today()
        start_date = today - timedelta(days=3 * 365) if self.cari_tip == "TEDARIKCI" else today - timedelta(days=6 * 30)
        self.bas_tarih_entry.setText(start_date.strftime('%Y-%m-%d'))
        self.bit_tarih_entry.setText(today.strftime('%Y-%m-%d'))

        self._yukle_ozet_bilgileri()
        self.ekstreyi_yukle()

        self.finished.connect(self.on_dialog_finished)
        self.app.register_cari_ekstre_window(self)

    def on_dialog_finished(self, result):
        self.app.unregister_cari_ekstre_window(self)
        if self.parent_list_refresh_func:
            self.parent_list_refresh_func()

    def _on_tab_change(self, index):
        selected_tab_text = self.notebook.tabText(index)
        if selected_tab_text == "Siparişler":
            self._siparisleri_yukle()
        elif selected_tab_text == "Hesap Hareketleri":
            self.ekstreyi_yukle()

    def _yukle_cari_bilgileri(self):
        try:
            cari_adi = "Bilinmiyor"
            cari_telefon = ""
            
            if self.cari_tip == "MUSTERI":
                cari_data = self.db.musteri_getir_by_id(self.cari_id)
                if cari_data:
                    cari_adi = cari_data.get("ad", "Bilinmeyen Müşteri")
                    cari_telefon = cari_data.get("telefon", "")
                
            elif self.cari_tip == "TEDARIKCI":
                cari_data = self.db.tedarikci_getir_by_id(self.cari_id)
                if cari_data:
                    cari_adi = cari_data.get("ad", "Bilinmeyen Tedarikçi")
                    cari_telefon = cari_data.get("telefon", "")
            
            self.setWindowTitle(f"{cari_adi} - Cari Hesap Ekstresi")
        except Exception as e:
            logger.error(f"Cari bilgileri yüklenirken hata oluştu: {e}")
            QMessageBox.warning(self, "Hata", f"Cari bilgileri yüklenirken bir hata oluştu: {e}")

    def _create_hesap_hareketleri_tab(self):
        parent_frame = self.hesap_hareketleri_tab
        parent_frame.setLayout(QVBoxLayout(parent_frame))
        
        filter_frame = QFrame(parent_frame)
        parent_frame.layout().addWidget(filter_frame)
        self._create_filter_alani(filter_frame)

        tree_frame = QFrame(parent_frame)
        parent_frame.layout().addWidget(tree_frame)
        self._create_treeview_alani(tree_frame)

    def _create_siparisler_tab(self):
        parent_frame = self.siparisler_tab
        parent_frame.setLayout(QVBoxLayout(parent_frame))
        
        cols = ("ID", "Sipariş No", "Tarih", "Teslimat Tarihi", "Toplam Tutar", "Durum", "Fatura No")
        self.siparisler_tree = QTreeWidget(parent_frame)
        self.siparisler_tree.setHeaderLabels(cols)
        self.siparisler_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.siparisler_tree.setSortingEnabled(True)

        col_defs = [
            ("ID", 40, Qt.AlignCenter), ("Sipariş No", 150, Qt.AlignCenter), ("Tarih", 100, Qt.AlignCenter),
            ("Teslimat Tarihi", 100, Qt.AlignCenter), ("Toplam Tutar", 120, Qt.AlignRight), ("Durum", 120, Qt.AlignCenter),
            ("Fatura No", 150, Qt.AlignCenter)
        ]
        for i, (col_id, w, a) in enumerate(col_defs):
            self.siparisler_tree.setColumnWidth(i, w)
            self.siparisler_tree.headerItem().setTextAlignment(i, a)
            self.siparisler_tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))

        self.siparisler_tree.header().setStretchLastSection(False)
        self.siparisler_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        
        parent_frame.layout().addWidget(self.siparisler_tree)
        self.siparisler_tree.itemDoubleClicked.connect(self._on_siparis_double_click)

    def _siparisleri_yukle(self):
        self.siparisler_tree.clear()
        
        try:
            params = {
                'cari_id': self.cari_id,
                'cari_turu': self.cari_tip
            }
            siparisler_data_response = self.db.siparis_listesi_al(**params) 
            siparisler_data = siparisler_data_response.get("items", []) 

            for siparis in siparisler_data:
                item_qt = QTreeWidgetItem(self.siparisler_tree)
                item_qt.setData(0, Qt.UserRole, siparis.get('id', -1))

                tarih_obj = datetime.strptime(str(siparis.get('tarih')), '%Y-%m-%d').date() if siparis.get('tarih') else None
                teslimat_tarihi_obj = datetime.strptime(str(siparis.get('teslimat_tarihi')), '%Y-%m-%d').date() if siparis.get('teslimat_tarihi') else None
                
                formatted_tarih = tarih_obj.strftime('%d.%m.%Y') if isinstance(tarih_obj, date) else '-'
                formatted_teslimat_tarihi = teslimat_tarihi_obj.strftime('%d.%m.%Y') if isinstance(teslimat_tarihi_obj, date) else '-'

                item_qt.setText(0, str(siparis.get('id', '')))
                item_qt.setText(1, siparis.get('siparis_no', ''))
                item_qt.setText(2, formatted_tarih)
                item_qt.setText(3, formatted_teslimat_tarihi)
                item_qt.setText(4, self.db._format_currency(siparis.get('toplam_tutar', 0.0)))
                item_qt.setText(5, siparis.get('durum', ''))
                
                fatura_no_text = "-"
                if siparis.get('fatura_id'):
                    try:
                        fatura_data = self.db.fatura_getir_by_id(siparis.get('fatura_id'))
                        fatura_no_text = fatura_data.get('fatura_no', '-')
                    except Exception:
                        fatura_no_text = "Hata"
                item_qt.setText(6, fatura_no_text)

                if siparis.get('durum') == "TAMAMLANDI":
                    for col_idx in range(self.siparisler_tree.columnCount()):
                        item_qt.setBackground(col_idx, QBrush(QColor("lightgreen")))
                elif siparis.get('durum') == "İPTAL_EDİLDİ":
                    for col_idx in range(self.siparisler_tree.columnCount()):
                        item_qt.setBackground(col_idx, QBrush(QColor("lightgray")))
                        item_qt.setForeground(col_idx, QBrush(QColor("gray")))
                        font = item_qt.font(col_idx)
                        font.setStrikeOut(True)
                        item_qt.setFont(col_idx, font)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Siparişler yüklenirken hata: {e}")
            logging.error(f"Cari Hesap Ekstresi - Siparişler yükleme hatası: {e}", exc_info=True)
        self.app.set_status_message(f"{self.cari_ad_gosterim} için {len(siparisler_data)} sipariş listelendi.", "blue")

    def _on_siparis_double_click(self, item, column):
        siparis_id = item.data(0, Qt.UserRole)
        if siparis_id:
            from pencereler import SiparisDetayPenceresi
            SiparisDetayPenceresi(self.app, self.db, siparis_id).exec()

    def _create_ozet_bilgi_alani(self):
        frame = self.ozet_ve_bilgi_frame
        frame.setLayout(QGridLayout(frame))

        label_font_buyuk = QFont("Segoe UI", 12, QFont.Bold)
        deger_font_buyuk = QFont("Segoe UI", 12)
        label_font_kucuk = QFont("Segoe UI", 9, QFont.Bold)
        deger_font_kucuk = QFont("Segoe UI", 9)

        finans_ozet_cerceve = QGroupBox("Finansal Özet", frame)
        finans_ozet_cerceve.setLayout(QGridLayout(finans_ozet_cerceve))
        frame.layout().addWidget(finans_ozet_cerceve, 0, 0)

        row_idx_finans = 0
        finans_ozet_cerceve.layout().addWidget(QLabel("Dönem Başı Bakiye:", font=label_font_kucuk), row_idx_finans, 0)
        self.lbl_donem_basi_bakiye = QLabel("0,00 TL", font=deger_font_kucuk)
        finans_ozet_cerceve.layout().addWidget(self.lbl_donem_basi_bakiye, row_idx_finans, 1)
        row_idx_finans += 1

        finans_ozet_cerceve.layout().addWidget(QLabel("Toplam Borç Hareketi:", font=label_font_kucuk), row_idx_finans, 0)
        self.lbl_toplam_borc_hareketi = QLabel("0,00 TL", font=deger_font_kucuk)
        finans_ozet_cerceve.layout().addWidget(self.lbl_toplam_borc_hareketi, row_idx_finans, 1)
        row_idx_finans += 1

        finans_ozet_cerceve.layout().addWidget(QLabel("Toplam Alacak Hareketi:", font=label_font_kucuk), row_idx_finans, 0)
        self.lbl_toplam_alacak_hareketi = QLabel("0,00 TL", font=deger_font_kucuk)
        finans_ozet_cerceve.layout().addWidget(self.lbl_toplam_alacak_hareketi, row_idx_finans, 1)
        row_idx_finans += 1
        
        finans_ozet_cerceve.layout().addWidget(QLabel("Toplam Tahsilat/Ödeme:", font=label_font_kucuk), row_idx_finans, 0)
        self.lbl_toplam_tahsilat_odeme = QLabel("0,00 TL", font=deger_font_kucuk)
        finans_ozet_cerceve.layout().addWidget(self.lbl_toplam_tahsilat_odeme, row_idx_finans, 1)
        row_idx_finans += 1

        finans_ozet_cerceve.layout().addWidget(QLabel("Vadesi Gelmiş Borç/Alacak:", font=label_font_kucuk), row_idx_finans, 0)
        self.lbl_vadesi_gelmis = QLabel("0,00 TL", font=deger_font_kucuk, styleSheet="color: red;")
        finans_ozet_cerceve.layout().addWidget(self.lbl_vadesi_gelmis, row_idx_finans, 1)
        row_idx_finans += 1

        finans_ozet_cerceve.layout().addWidget(QLabel("Vadesi Gelecek Borç/Alacak:", font=label_font_kucuk), row_idx_finans, 0)
        self.lbl_vadesi_gelecek = QLabel("0,00 TL", font=deger_font_kucuk, styleSheet="color: blue;")
        finans_ozet_cerceve.layout().addWidget(self.lbl_vadesi_gelecek, row_idx_finans, 1)
        row_idx_finans += 1

        finans_ozet_cerceve.layout().addWidget(QLabel("Dönem Sonu Bakiye:", font=label_font_buyuk), row_idx_finans, 0)
        self.lbl_ozet_net_bakiye = QLabel("0,00 TL", font=deger_font_buyuk)
        finans_ozet_cerceve.layout().addWidget(self.lbl_ozet_net_bakiye, row_idx_finans, 1)

        cari_detay_cerceve = QGroupBox("Cari Detay Bilgileri", frame)
        cari_detay_cerceve.setLayout(QGridLayout(cari_detay_cerceve))
        frame.layout().addWidget(cari_detay_cerceve, 0, 1)

        row_idx_cari = 0
        cari_detay_cerceve.layout().addWidget(QLabel("Cari Adı:", font=label_font_kucuk), row_idx_cari, 0)
        self.lbl_cari_detay_ad = QLabel("-", font=deger_font_kucuk)
        cari_detay_cerceve.layout().addWidget(self.lbl_cari_detay_ad, row_idx_cari, 1)
        row_idx_cari += 1

        cari_detay_cerceve.layout().addWidget(QLabel("Telefon:", font=label_font_kucuk), row_idx_cari, 0)
        self.lbl_cari_detay_tel = QLabel("-", font=deger_font_kucuk)
        cari_detay_cerceve.layout().addWidget(self.lbl_cari_detay_tel, row_idx_cari, 1)
        row_idx_cari += 1

        cari_detay_cerceve.layout().addWidget(QLabel("Adres:", font=label_font_kucuk), row_idx_cari, 0, Qt.AlignTop)
        self.lbl_cari_detay_adres = QLabel("-", font=deger_font_kucuk, wordWrap=True)
        cari_detay_cerceve.layout().addWidget(self.lbl_cari_detay_adres, row_idx_cari, 1)
        row_idx_cari += 1

        cari_detay_cerceve.layout().addWidget(QLabel("Vergi No:", font=label_font_kucuk), row_idx_cari, 0)
        self.lbl_cari_detay_vergi = QLabel("-", font=deger_font_kucuk)
        cari_detay_cerceve.layout().addWidget(self.lbl_cari_detay_vergi, row_idx_cari, 1)
        row_idx_cari += 1

        export_buttons_frame = QFrame(frame)
        export_buttons_frame.setLayout(QVBoxLayout(export_buttons_frame))
        frame.layout().addWidget(export_buttons_frame, 0, 2, Qt.AlignTop)

        btn_pdf = QPushButton("PDF'e Aktar")
        btn_pdf.clicked.connect(self.pdf_aktar)
        export_buttons_frame.layout().addWidget(btn_pdf)

        btn_excel = QPushButton("Excel'e Aktar")
        btn_excel.clicked.connect(self.excel_aktar)
        export_buttons_frame.layout().addWidget(btn_excel)
        
        btn_update_cari = QPushButton("Cari Bilgilerini Güncelle")
        btn_update_cari.clicked.connect(self._cari_bilgileri_guncelle)
        cari_detay_cerceve.layout().addWidget(btn_update_cari, row_idx_cari, 0, 1, 2)

    def _create_filter_alani(self, filter_frame):
        filter_frame.setLayout(QHBoxLayout(filter_frame))
        
        filter_frame.layout().addWidget(QLabel("Başlangıç Tarihi:"))
        self.bas_tarih_entry = QLineEdit()
        filter_frame.layout().addWidget(self.bas_tarih_entry)
        
        btn_date_start = QPushButton("🗓️")
        btn_date_start.setFixedWidth(30)
        btn_date_start.clicked.connect(lambda: DatePickerDialog(self.app, self.bas_tarih_entry))
        filter_frame.layout().addWidget(btn_date_start)

        filter_frame.layout().addWidget(QLabel("Bitiş Tarihi:"))
        self.bit_tarih_entry = QLineEdit()
        filter_frame.layout().addWidget(self.bit_tarih_entry)
        
        btn_date_end = QPushButton("🗓️")
        btn_date_end.setFixedWidth(30)
        btn_date_end.clicked.connect(lambda: DatePickerDialog(self.app, self.bit_tarih_entry))
        filter_frame.layout().addWidget(btn_date_end)

        btn_filter = QPushButton("Filtrele")
        btn_filter.clicked.connect(self.ekstreyi_yukle)
        filter_frame.layout().addWidget(btn_filter)
        
    def _create_treeview_alani(self, tree_frame):
        tree_frame.setLayout(QVBoxLayout(tree_frame))
        
        cols = ("ID", "Tarih", "Saat", "İşlem Tipi", "Referans", "Ödeme Türü", "Açıklama/Detay", "Borç", "Alacak", "Bakiye", "Vade Tarihi")
        self.ekstre_tree = QTreeWidget(tree_frame)
        self.ekstre_tree.setHeaderLabels(cols)
        self.ekstre_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ekstre_tree.setSortingEnabled(True)

        col_defs = [
            ("ID", 40, Qt.AlignCenter), ("Tarih", 80, Qt.AlignCenter),
            ("Saat", 60, Qt.AlignCenter), ("İşlem Tipi", 120, Qt.AlignCenter),
            ("Referans", 120, Qt.AlignCenter), ("Ödeme Türü", 100, Qt.AlignCenter),
            ("Açıklama/Detay", 300, Qt.AlignLeft),
            ("Borç", 100, Qt.AlignRight),
            ("Alacak", 100, Qt.AlignRight),
            ("Bakiye", 120, Qt.AlignRight),
            ("Vade Tarihi", 90, Qt.AlignCenter)
        ]
        for i, (col_name, width, alignment) in enumerate(col_defs):
            self.ekstre_tree.setColumnWidth(i, width)
            self.ekstre_tree.headerItem().setTextAlignment(i, alignment)
            self.ekstre_tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
        
        self.ekstre_tree.header().setStretchLastSection(False)
        self.ekstre_tree.header().setSectionResizeMode(6, QHeaderView.Stretch)

        tree_frame.layout().addWidget(self.ekstre_tree)
        
        self.ekstre_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ekstre_tree.customContextMenuRequested.connect(self._show_context_menu)
        self.ekstre_tree.itemDoubleClicked.connect(self.on_double_click_hareket_detay)

    def _create_hizli_islem_alanlari(self):
        self.hizli_islemler_ana_frame.setLayout(QHBoxLayout(self.hizli_islemler_ana_frame))

        ot_frame_text = "Ödeme Ekle" if self.cari_tip == "TEDARIKCI" else "Tahsilat Ekle"
        odeme_tahsilat_frame = QGroupBox(ot_frame_text, self.hizli_islemler_ana_frame)
        odeme_tahsilat_frame.setLayout(QGridLayout(odeme_tahsilat_frame))
        self.hizli_islemler_ana_frame.layout().addWidget(odeme_tahsilat_frame)

        odeme_tahsilat_frame.layout().addWidget(QLabel("Ödeme Tipi:"), 0, 0)
        self.ot_odeme_tipi_combo = QComboBox()
        self.ot_odeme_tipi_combo.addItems([self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, 
                                            self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, 
                                            self.db.ODEME_TURU_SENET])
        self.ot_odeme_tipi_combo.setCurrentText(self.db.ODEME_TURU_NAKIT)
        self.ot_odeme_tipi_combo.currentIndexChanged.connect(self._ot_odeme_tipi_degisince)
        odeme_tahsilat_frame.layout().addWidget(self.ot_odeme_tipi_combo, 0, 1)

        odeme_tahsilat_frame.layout().addWidget(QLabel("Tutar:"), 1, 0)
        self.ot_tutar_entry = QLineEdit("0,00")
        setup_numeric_entry(self.app, self.ot_tutar_entry, decimal_places=2)
        odeme_tahsilat_frame.layout().addWidget(self.ot_tutar_entry, 1, 1)

        odeme_tahsilat_frame.layout().addWidget(QLabel("Kasa/Banka:"), 2, 0)
        self.ot_kasa_banka_combo = QComboBox()
        self.ot_kasa_banka_combo.setEnabled(False)
        odeme_tahsilat_frame.layout().addWidget(self.ot_kasa_banka_combo, 2, 1)

        odeme_tahsilat_frame.layout().addWidget(QLabel("Not:"), 3, 0)
        self.ot_not_entry = QLineEdit()
        odeme_tahsilat_frame.layout().addWidget(self.ot_not_entry, 3, 1)

        btn_ot_save = QPushButton(ot_frame_text)
        btn_ot_save.clicked.connect(self._hizli_odeme_tahsilat_kaydet)
        odeme_tahsilat_frame.layout().addWidget(btn_ot_save, 4, 0, 1, 2)

        borc_frame = QGroupBox("Veresiye Borç Ekle", self.hizli_islemler_ana_frame)
        borc_frame.setLayout(QGridLayout(borc_frame))
        self.hizli_islemler_ana_frame.layout().addWidget(borc_frame)

        borc_frame.layout().addWidget(QLabel("Türü Seçiniz:"), 0, 0)
        self.borc_tur_combo = QComboBox()
        self.borc_tur_combo.addItems(["Diğer Borç", "Satış Faturası"])
        borc_frame.layout().addWidget(self.borc_tur_combo, 0, 1)

        borc_frame.layout().addWidget(QLabel("Tutar:"), 1, 0)
        self.borc_tutar_entry = QLineEdit("0,00")
        setup_numeric_entry(self.app, self.borc_tutar_entry, decimal_places=2)
        borc_frame.layout().addWidget(self.borc_tutar_entry, 1, 1)

        borc_frame.layout().addWidget(QLabel("Not:"), 2, 0)
        self.borc_not_entry = QLineEdit()
        borc_frame.layout().addWidget(self.borc_not_entry, 2, 1)

        btn_borc_save = QPushButton("Veresiye Ekle")
        btn_borc_save.clicked.connect(self._hizli_veresiye_borc_kaydet)
        borc_frame.layout().addWidget(btn_borc_save, 3, 0, 1, 2)

        alacak_frame = QGroupBox("Alacak Ekleme", self.hizli_islemler_ana_frame)
        alacak_frame.setLayout(QGridLayout(alacak_frame))
        self.hizli_islemler_ana_frame.layout().addWidget(alacak_frame)

        alacak_frame.layout().addWidget(QLabel("Türü Seçiniz:"), 0, 0)
        self.alacak_tur_combo = QComboBox()
        self.alacak_tur_combo.addItems(["Diğer Alacak", "İade Faturası"])
        alacak_frame.layout().addWidget(self.alacak_tur_combo, 0, 1)

        alacak_frame.layout().addWidget(QLabel("Tutar:"), 1, 0)
        self.alacak_tutar_entry = QLineEdit("0,00")
        setup_numeric_entry(self.app, self.alacak_tutar_entry, decimal_places=2)
        alacak_frame.layout().addWidget(self.alacak_tutar_entry, 1, 1)

        alacak_frame.layout().addWidget(QLabel("Not:"), 2, 0)
        self.alacak_not_entry = QLineEdit()
        alacak_frame.layout().addWidget(self.alacak_not_entry, 2, 1)

        btn_alacak_save = QPushButton("Alacak Kaydet")
        btn_alacak_save.clicked.connect(self._hizli_alacak_kaydet)
        alacak_frame.layout().addWidget(btn_alacak_save, 3, 0, 1, 2)

    def _yukle_kasa_banka_hesaplarini_hizli_islem_formu(self):
        self.ot_kasa_banka_combo.clear()
        self.kasa_banka_map.clear()
        
        try:
            hesaplar_response = self.db.kasa_banka_listesi_al()
            # API'den gelen yanıtın dict içinde 'items' anahtarı olup olmadığını kontrol et
            if isinstance(hesaplar_response, dict) and "items" in hesaplar_response:
                hesaplar = hesaplar_response["items"]
            elif isinstance(hesaplar_response, list):
                hesaplar = hesaplar_response
                # Hata mesajı düzeltildi: 3. argüman kaldırıldı
                self.app.set_status_message("Uyarı: Kasa/Banka listesi API yanıtı beklenen formatta değil. Doğrudan liste olarak işleniyor.", "orange")
            else:
                hesaplar = []
                # Hata mesajı düzeltildi: 3. argüman kaldırıldı
                self.app.set_status_message("Hata: Kasa/Banka listesi API'den alınamadı veya formatı geçersiz.", "red")
                logging.error(f"Kasa/Banka listesi API'den beklenen formatta gelmedi: {type(hesaplar_response)} - {hesaplar_response}", exc_info=True)
                self.ot_kasa_banka_combo.addItem("Hesap Yok", None)
                self.ot_kasa_banka_combo.setEnabled(False)
                return


            if hesaplar:
                for h in hesaplar:
                    display_text = f"{h.get('hesap_adi')} ({h.get('tip')}) - Bakiye: {self.db._format_currency(h.get('bakiye', 0.0))}"
                    if h.get('tip') == "BANKA" and h.get('banka_adi'):
                        display_text += f" ({h.get('banka_adi')})"
                    if h.get('tip') == "BANKA" and h.get('hesap_no'):
                        display_text += f" ({h.get('hesap_no')})"
                    self.kasa_banka_map[display_text] = h.get('id')
                    self.ot_kasa_banka_combo.addItem(display_text, h.get('id'))
                self.ot_kasa_banka_combo.setCurrentIndex(0)
                self.ot_kasa_banka_combo.setEnabled(True)
            else:
                self.ot_kasa_banka_combo.clear()
                self.ot_kasa_banka_combo.addItem("Hesap Yok", None)
                self.ot_kasa_banka_combo.setEnabled(False)

            # Hata mesajı düzeltildi: 3. argüman kaldırıldı
            self.app.set_status_message(f"{len(hesaplar)} kasa/banka hesabı API'den yüklendi.", "blue")

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kasa/Banka hesapları yüklenirken hata: {e}")
            logging.error(f"Kasa/Banka yükleme hatası: {e}", exc_info=True)
            self.ot_kasa_banka_combo.addItem("Hesap Yok", None)
            self.ot_kasa_banka_combo.setEnabled(False)

    def _ot_odeme_tipi_degisince(self):
        selected_odeme_sekli = self.ot_odeme_tipi_combo.currentText()
        
        self.ot_kasa_banka_combo.blockSignals(True)
        
        default_account_id = None
        try:
            default_account_data = self.db.get_varsayilan_kasa_banka(selected_odeme_sekli)
            if default_account_data:
                default_account_id = default_account_data.get('id')
        except Exception as e:
            logging.warning(f"Default kasa/banka for {selected_odeme_sekli} could not be fetched: {e}")

        if default_account_id:
            for i in range(self.ot_kasa_banka_combo.count()):
                if self.ot_kasa_banka_combo.itemData(i) == default_account_id:
                    self.ot_kasa_banka_combo.setCurrentIndex(i)
                    break
            else:
                if self.ot_kasa_banka_combo.count() > 0 and self.ot_kasa_banka_combo.itemData(0) is not None:
                    self.ot_kasa_banka_combo.setCurrentIndex(0)
                else:
                    self.ot_kasa_banka_combo.setCurrentText("")
        elif self.ot_kasa_banka_combo.count() > 0 and self.ot_kasa_banka_combo.itemData(0) is not None:
            self.ot_kasa_banka_combo.setCurrentIndex(0)
        else:
            self.ot_kasa_banka_combo.setCurrentText("")

        self.ot_kasa_banka_combo.blockSignals(False)

    def _yukle_ozet_bilgileri(self):
        try:
            cari_detail = None
            if self.cari_tip == "MUSTERI":
                cari_detail = self.db.musteri_getir_by_id(self.cari_id)
            else:
                cari_detail = self.db.tedarikci_getir_by_id(self.cari_id)
            
            if not cari_detail:
                # Hata mesajı düzeltildi: 3. argüman kaldırıldı
                self.app.set_status_message(f"Hata: Cari bilgiler yüklenemedi. ID {self.cari_id} bulunamadı.", "red")
                return

            self.lbl_cari_detay_ad.setText(cari_detail.get('ad', '-'))
            self.lbl_cari_detay_tel.setText(cari_detail.get('telefon', '-'))
            self.lbl_cari_detay_adres.setText(cari_detail.get('adres', '-'))
            vergi_info = f"{cari_detail.get('vergi_dairesi', '-')} / {cari_detail.get('vergi_no', '-')}"
            self.lbl_cari_detay_vergi.setText(vergi_info)

            net_bakiye = cari_detail.get("net_bakiye", 0.0)
            
            bakiye_metni = self.db._format_currency(net_bakiye)
            if net_bakiye > 0:
                bakiye_metni = f"<b style='color: green;'>{bakiye_metni} ALACAKLI</b>"
            elif net_bakiye < 0:
                bakiye_metni = f"<b style='color: red;'>{bakiye_metni} BORÇLU</b>"
            else:
                bakiye_metni = f"<b style='color: blue;'>{bakiye_metni}</b>"
            self.lbl_ozet_net_bakiye.setText(bakiye_metni)

            self.lbl_donem_basi_bakiye.setText(self.db._format_currency(0.0))
            self.lbl_toplam_borc_hareketi.setText(self.db._format_currency(0.0))
            self.lbl_toplam_alacak_hareketi.setText(self.db._format_currency(0.0))
            self.lbl_toplam_tahsilat_odeme.setText(self.db._format_currency(0.0))
            self.lbl_vadesi_gelmis.setText(self.db._format_currency(0.0))
            self.lbl_vadesi_gelecek.setText(self.db._format_currency(0.0))
            
            # Hata mesajı düzeltildi: 3. argüman kaldırıldı
            self.app.set_status_message("Cari özet bilgileri güncellendi.", "green")

        except Exception as e:
            logger.error(f"Cari özet bilgileri yüklenirken hata oluştu: {e}", exc_info=True)
            # Hata mesajı düzeltildi: 3. argüman kaldırıldı
            self.app.set_status_message(f"Hata: Cari özet bilgileri yüklenemedi. Detay: {e}", "red")

    def _cari_bilgileri_guncelle(self):
        try:
            cari_data = None
            if self.cari_tip == "MUSTERI":
                cari_data = self.db.musteri_getir_by_id(self.cari_id)
                if cari_data:
                    from pencereler import YeniMusteriEklePenceresi
                    dialog = YeniMusteriEklePenceresi(self, self.db, self._ozet_ve_liste_yenile, musteri_duzenle=cari_data, app_ref=self.app)
                    dialog.exec()
                else:
                    # Hata mesajı düzeltildi: 3. argüman kaldırıldı
                    self.app.set_status_message(f"Hata: Müşteri bilgileri yüklenemedi. ID {self.cari_id} bulunamadı.", "red")
                    return
            elif self.cari_tip == "TEDARIKCI":
                cari_data = self.db.tedarikci_getir_by_id(self.cari_id)
                if cari_data:
                    from pencereler import YeniTedarikciEklePenceresi
                    dialog = YeniTedarikciEklePenceresi(self, self.db, self._ozet_ve_liste_yenile, tedarikci_duzenle=cari_data, app_ref=self.app)
                    dialog.exec()
                else:
                    # Hata mesajı düzeltildi: 3. argüman kaldırıldı
                    self.app.set_status_message(f"Hata: Tedarikçi bilgileri yüklenemedi. ID {self.cari_id} bulunamadı.", "red")
                    return
            
            # Hata mesajı düzeltildi: 3. argüman kaldırıldı
            self.app.set_status_message(f"{self.cari_tip} kartı açıldı.", "blue")

        except Exception as e:
            logger.error(f"Cari bilgiler güncellenmek üzere yüklenirken hata oluştu: {e}", exc_info=True)
            # Hata mesajı düzeltildi: 3. argüman kaldırıldı
            self.app.set_status_message(f"Hata: Cari bilgiler yüklenemedi. Detay: {e}", "red")

    def _ozet_ve_liste_yenile(self):
        self._yukle_ozet_bilgileri()
        self.ekstreyi_yukle()

    def _hizli_odeme_tahsilat_kaydet(self):
        islem_turu = self.sender().text()
        islem_turu_enum = "GIDER" if islem_turu == "Ödeme Yap" else "GELIR"

        tutar_str = self.ot_tutar_entry.text().replace(".", "").replace(",", ".")
        try:
            tutar = float(tutar_str)
            if tutar <= 0:
                self.app.set_status_message("Tutar sıfırdan büyük olmalıdır.", "orange")
                return
        except ValueError:
            self.app.set_status_message("Geçerli bir tutar girin.", "orange")
            return

        aciklama = self.ot_not_entry.text().strip()
        if not aciklama:
            self.app.set_status_message("Açıklama alanı boş bırakılamaz.", "orange")
            return

        selected_hesap_idx = self.ot_kasa_banka_combo.currentIndex()
        if selected_hesap_idx < 0:
            self.app.set_status_message("Lütfen bir Kasa/Banka hesabı seçin.", "orange")
            return
        
        kasa_banka_id = self.ot_kasa_banka_combo.currentData()

        gelir_gider_data = {
            "tarih": date.today().strftime('%Y-%m-%d'),
            "tip": islem_turu_enum,
            "tutar": tutar,
            "aciklama": aciklama,
            "kasa_banka_id": kasa_banka_id,
            "cari_id": self.cari_id,
            "cari_tip": self.cari_tip,
        }

        try:
            success = self.db.gelir_gider_ekle(gelir_gider_data)
            if success:
                self.app.set_status_message(f"Hızlı {islem_turu.lower()} kaydı başarıyla oluşturuldu.", "green")
                self.ot_tutar_entry.clear()
                self.ot_not_entry.clear()
                self.ot_odeme_tipi_combo.setCurrentText(self.db.ODEME_TURU_NAKIT)
                self._ot_odeme_tipi_degisince()
                self._ozet_ve_liste_yenile()
            else:
                self.app.set_status_message(f"Hızlı {islem_turu.lower()} kaydı oluşturulamadı.", "red")
        except Exception as e:
            logger.error(f"Hızlı {islem_turu.lower()} kaydı oluşturulurken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Hızlı {islem_turu.lower()} kaydı oluşturulamadı. Detay: {e}", "red")

    def _hizli_veresiye_borc_kaydet(self):
        borc_tur = self.borc_tur_combo.currentText()
        tutar_str = self.borc_tutar_entry.text().replace(',', '.')
        not_str = self.borc_not_entry.text()

        if not tutar_str or float(tutar_str) <= 0:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen geçerli bir tutar giriniz.")
            return

        if borc_tur == "Satış Faturası":
            QMessageBox.information(self, "Yönlendirme", "Fatura oluşturmak için lütfen ana menüden 'Yeni Satış Faturası' ekranını kullanın.")
        else:
            try:
                tutar_f = float(tutar_str)
                data = {
                    "cari_id": self.cari_id,
                    "cari_turu": self.cari_tip,
                    "tarih": date.today().strftime('%Y-%m-%d'),
                    "tutar": tutar_f,
                    "aciklama": not_str,
                    "islem_turu": "VERESİYE_BORÇ",
                    "islem_yone": "BORC",
                    "kaynak": self.db.KAYNAK_TIP_VERESIYE_BORC_MANUEL
                }
                success = self.db.cari_hareket_ekle_manuel(data)

                if success:
                    QMessageBox.information(self, "Başarılı", "Veresiye borç başarıyla eklendi.")
                    self.borc_tutar_entry.clear()
                    self.borc_not_entry.clear()
                    self._ozet_ve_liste_yenile()
                else:
                    QMessageBox.critical(self, "Hata", "Veresiye borç eklenirken hata.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Veresiye borç eklenirken hata: {e}")
                logging.error(f"Hızlı veresiye borç kaydetme hatası: {e}", exc_info=True)

    def _hizli_alacak_kaydet(self):
        QMessageBox.information(self, "Geliştirme Aşamasında", "Alacak ekleme özelliği henüz tamamlanmamıştır.")

    def excel_aktar(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Cari Hesap Ekstresini Excel'e Kaydet", 
                                                 f"Cari_Ekstresi_{self.cari_ad_gosterim.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx", 
                                                 "Excel Dosyaları (*.xlsx);;Tüm Dosyalar (*)")
        if file_path:
            bekleme_penceresi = BeklemePenceresi(self, message="Ekstre Excel'e aktarılıyor, lütfen bekleyiniz...")
            threading.Thread(target=lambda: self._generate_ekstre_excel_threaded(
                self.cari_tip, self.cari_id, self.bas_tarih_entry.text(), self.bit_tarih_entry.text(),
                file_path, bekleme_penceresi
            )).start()
        else:
            self.app.set_status_message("Excel'e aktarma iptal edildi.", "blue")

    def pdf_aktar(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Cari Hesap Ekstresini PDF'e Kaydet", 
                                                 f"Cari_Ekstresi_{self.cari_ad_gosterim.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf", 
                                                 "PDF Dosyaları (*.pdf);;Tüm Dosyalar (*)")
        if file_path:
            bekleme_penceresi = BeklemePenceresi(self, message="Ekstre PDF'e aktarılıyor, lütfen bekleyiniz...")
            
            result_queue = multiprocessing.Queue()
            pdf_process = multiprocessing.Process(target=self.db.cari_ekstresi_pdf_olustur, args=(
                self.db.data_dir,
                self.cari_tip,
                self.cari_id,
                self.bas_tarih_entry.text(),
                self.bit_tarih_entry.text(),
                file_path,
                result_queue
            ))
            pdf_process.start()

            self.app.process_queue_timer = QTimer(self.app)
            self.app.process_queue_timer.timeout.connect(lambda: self._check_pdf_process_completion(result_queue, pdf_process, bekleme_penceresi))
            self.app.process_queue_timer.start(100)
        else:
            self.app.set_status_message("PDF'e aktarma iptal edildi.", "blue")

    def _check_pdf_process_completion(self, result_queue, pdf_process, bekleme_penceresi):
        if not result_queue.empty():
            success, message = result_queue.get()
            bekleme_penceresi.close()
            self.app.process_queue_timer.stop()

            if success:
                QMessageBox.information(self, "Başarılı", message)
                self.app.set_status_message(message, "green")
            else:
                QMessageBox.critical(self, "Hata", message)
                self.app.set_status_message(f"Ekstre PDF'e aktarılırken hata: {message}", "red")
            pdf_process.join()
            
        elif not pdf_process.is_alive():
            bekleme_penceresi.close()
            self.app.process_queue_timer.stop()
            QMessageBox.critical(self, "Hata", "PDF işlemi beklenmedik şekilde sonlandı.")
            self.app.set_status_message("PDF işlemi beklenmedik şekilde sonlandı.", "red")
            pdf_process.join()

    def _generate_ekstre_excel_threaded(self, cari_tip, cari_id, bas_t, bit_t, dosya_yolu, bekleme_penceresi):
        local_db_manager = self.db.__class__(api_base_url=self.db.api_base_url, app_ref=self.app)
        
        success = False
        message = ""
        try:
            hareketler_listesi, devreden_bakiye, success_db, message_db = local_db_manager.cari_hesap_ekstresi_al(
                cari_id, cari_tip, bas_t, bit_t
            )
            
            if not success_db:
                message = f"Ekstre verisi alınırken hata: {message_db}"
            elif not hareketler_listesi and devreden_bakiye == 0:
                message = "Excel'e aktarılacak cari ekstre verisi bulunamadı."
            else:
                success, message = local_db_manager.tarihsel_satis_raporu_excel_olustur(
                    rapor_verileri=hareketler_listesi,
                    dosya_yolu=dosya_yolu,
                    bas_t=bas_t,
                    bit_t=bit_t
                )
                if not success: message = f"Excel oluşturulurken hata: {message}"

        except Exception as e:
            message = f"Rapor Excel'e aktarılırken bir hata oluştu:\n{e}"
            logging.error(f"Excel export thread error: {e}", exc_info=True)
        finally:
            self.app.set_status_message(message, "blue" if success else "red")
            self.app.after(0, bekleme_penceresi.kapat)
            self.app.after(0, lambda: QMessageBox.information(self, "Excel Aktarım", message) if success else QMessageBox.critical(self, "Excel Aktarım Hatası", message))

    def ekstreyi_yukle(self):
        self.ekstre_tree.clear()
        self.hareket_detay_map.clear()

        bas_tarih_str = self.bas_tarih_entry.text()
        bit_tarih_str = self.bit_tarih_entry.text()

        try:
            datetime.strptime(bas_tarih_str, '%Y-%m-%d')
            datetime.strptime(bit_tarih_str, '%Y-%m-%d')
        except ValueError:
            QMessageBox.critical(self, "Hata", "Tarih formatı 'YYYY-AA-GG' şeklinde olmalıdır.")
            return
        
        hareketler_listesi, devreden_bakiye, success_db, message_db = self.db.cari_hesap_ekstresi_al(
            self.cari_id, self.cari_tip, bas_tarih_str, bit_tarih_str
        )

        if not success_db:
            QMessageBox.critical(self, "Hata", f"Ekstre verisi alınırken hata: {message_db}")
            self.app.set_status_message(f"{self.cari_ad_gosterim} için ekstre yüklenemedi: {message_db}", "red")
            return
        
        devir_item = QTreeWidgetItem(self.ekstre_tree)
        devir_item.setText(0, "")
        devir_item.setText(1, bas_tarih_str)
        devir_item.setText(2, "")
        devir_item.setText(3, "DEVİR")
        devir_item.setText(4, "")
        devir_item.setText(5, "Devreden Bakiye")
        devir_item.setText(6, "")
        devir_item.setText(7, self.db._format_currency(devreden_bakiye) if devreden_bakiye > 0 else "")
        devir_item.setText(8, self.db._format_currency(abs(devreden_bakiye)) if devreden_bakiye < 0 else "")
        devir_item.setText(9, self.db._format_currency(devreden_bakiye))
        devir_item.setText(10, "")
        
        for col_idx in range(self.ekstre_tree.columnCount()):
            devir_item.setBackground(col_idx, QBrush(QColor("#EFEFEF")))
            devir_item.setFont(col_idx, QFont("Segoe UI", 9, QFont.Bold))


        current_bakiye = devreden_bakiye
        
        for hareket in hareketler_listesi:
            item_qt = QTreeWidgetItem(self.ekstre_tree)
            
            tarih_formatted = hareket['tarih'].strftime('%d.%m.%Y') if isinstance(hareket['tarih'], date) else str(hareket['tarih'])
            vade_tarihi_formatted = hareket['vade_tarihi'].strftime('%d.%m.%Y') if isinstance(hareket['vade_tarihi'], date) else (str(hareket['vade_tarihi']) if hareket['vade_tarihi'] else '-')
            
            borc_val = ""
            alacak_val = ""
            
            if self.cari_tip == 'MUSTERI':
                if hareket['islem_yone'] == 'ALACAK':
                    alacak_val = self.db._format_currency(hareket['tutar'])
                    current_bakiye += hareket['tutar']
                elif hareket['islem_yone'] == 'BORC':
                    borc_val = self.db._format_currency(hareket['tutar'])
                    current_bakiye -= hareket['tutar']
            elif self.cari_tip == 'TEDARIKCI':
                if hareket['islem_yone'] == 'ALACAK':
                    alacak_val = self.db._format_currency(hareket['tutar'])
                    current_bakiye += hareket['tutar']
                elif hareket['islem_yone'] == 'BORC':
                    borc_val = self.db._format_currency(hareket['tutar'])
                    current_bakiye -= hareket['tutar']
            
            display_islem_tipi = hareket['islem_turu']
            display_ref_gosterim = hareket['fatura_no'] if hareket.get('fatura_no') else (hareket.get('kaynak') or '-')

            if hareket.get('kaynak') in (self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA):
                if hareket.get('fatura_turu') == self.db.FATURA_TIP_SATIS:
                    display_islem_tipi = "Satış Faturası"
                elif hareket.get('fatura_turu') == self.db.FATURA_TIP_ALIS:
                    display_islem_tipi = "Alış Faturası"
                elif hareket.get('fatura_turu') == self.db.FATURA_TIP_SATIS_IADE:
                    display_islem_tipi = "Satış İade Faturası"
                elif hareket.get('fatura_turu') == self.db.FATURA_TIP_ALIS_IADE:
                    display_islem_tipi = "Alış İade Faturası"
                display_ref_gosterim = hareket['fatura_no']
            elif hareket.get('kaynak') in (self.db.KAYNAK_TIP_TAHSILAT, self.db.KAYNAK_TIP_ODEME):
                display_islem_tipi = "Tahsilat" if hareket.get('islem_turu') == "GELIR" else "Ödeme"
                display_ref_gosterim = hareket.get('kaynak')

            item_qt.setText(0, str(hareket['id']))
            item_qt.setText(1, tarih_formatted)
            item_qt.setText(2, hareket.get('islem_saati') or '')
            item_qt.setText(3, display_islem_tipi)
            item_qt.setText(4, display_ref_gosterim)
            item_qt.setText(5, hareket.get('odeme_turu') or '-')
            item_qt.setText(6, hareket.get('aciklama') or '-')
            item_qt.setText(7, borc_val)
            item_qt.setText(8, alacak_val)
            item_qt.setText(9, self.db._format_currency(current_bakiye))
            item_qt.setText(10, vade_tarihi_formatted)

            self.hareket_detay_map[hareket['id']] = hareket

            if hareket.get('kaynak') in (self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA):
                if hareket.get('odeme_turu') in self.db.pesin_odeme_turleri:
                    for col_idx in range(self.ekstre_tree.columnCount()):
                        item_qt.setBackground(col_idx, QBrush(QColor("lightgray")))
                        item_qt.setForeground(col_idx, QBrush(QColor("darkgray")))
                else:
                    for col_idx in range(self.ekstre_tree.columnCount()):
                        item_qt.setForeground(col_idx, QBrush(QColor("red")))
                if "İADE" in hareket.get('fatura_turu', ''):
                    for col_idx in range(self.ekstre_tree.columnCount()):
                        item_qt.setBackground(col_idx, QBrush(QColor("#FFF2CC")))
                        item_qt.setForeground(col_idx, QBrush(QColor("#A67400")))
            elif hareket.get('kaynak') in (self.db.KAYNAK_TIP_TAHSILAT, self.db.KAYNAK_TIP_ODEME, self.db.KAYNAK_TIP_VERESIYE_BORC_MANUEL):
                for col_idx in range(self.ekstre_tree.columnCount()):
                    item_qt.setForeground(col_idx, QBrush(QColor("green")))

        self.app.set_status_message(f"{self.cari_ad_gosterim} için {len(hareketler_listesi)} hareket yüklendi.", "blue")

    def _show_context_menu(self, pos):
        item = self.ekstre_tree.itemAt(pos)
        if not item: return

        item_id = int(item.text(0))
        if item.text(3) == "DEVİR": return

        hareket_detayi = self.hareket_detay_map.get(item_id)
        if not hareket_detayi: return

        ref_tip = hareket_detayi.get('kaynak')

        context_menu = QMenu(self)
        
        if ref_tip in [self.db.KAYNAK_TIP_MANUEL, self.db.KAYNAK_TIP_TAHSILAT, self.db.KAYNAK_TIP_ODEME, self.db.KAYNAK_TIP_VERESIYE_BORC_MANUEL, self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA, self.db.KAYNAK_TIP_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_FATURA_ALIS_PESIN]:
            context_menu.addAction("İşlemi Sil").triggered.connect(self.secili_islemi_sil)
        
        if ref_tip in [self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA, self.db.KAYNAK_TIP_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_FATURA_ALIS_PESIN]:
            context_menu.addAction("Faturayı Güncelle").triggered.connect(self.secili_islemi_guncelle)
        
        if context_menu.actions():
            context_menu.exec(self.ekstre_tree.mapToGlobal(pos))

    def secili_islemi_sil(self):
        selected_items = self.ekstre_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir işlem seçin.")
            return

        item_qt = selected_items[0]
        hareket_id = int(item_qt.text(0))

        hareket_detayi = self.hareket_detay_map.get(hareket_id)
        if not hareket_detayi:
            QMessageBox.critical(self, "Hata", "İşlem detayları bulunamadı.")
            return
        
        ref_id = hareket_detayi.get('kaynak_id')
        ref_tip = hareket_detayi.get('kaynak')
        aciklama_text = hareket_detayi.get('aciklama')
        fatura_no = hareket_detayi.get('fatura_no')
        
        confirm_msg = f"'{aciklama_text}' açıklamalı işlemi silmek istediğinizden emin misiniz?\nBu işlem geri alınamaz."
        if ref_tip in [self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA, self.db.KAYNAK_TIP_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_FATURA_ALIS_PESIN]:
            confirm_msg = f"'{fatura_no}' numaralı FATURA ve ilişkili tüm hareketlerini silmek istediğinizden emin misiniz?\nBu işlem geri alınamaz."

        reply = QMessageBox.question(self, "Silme Onayı", confirm_msg, QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            success = False
            message = "Bilinmeyen işlem tipi."
            try:
                if ref_tip in [self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA, self.db.KAYNAK_TIP_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_FATURA_ALIS_PESIN]:
                    success = self.db.fatura_sil(ref_id)
                    message = f"Fatura {fatura_no} başarıyla silindi."
                else:
                    if ref_tip in [self.db.KAYNAK_TIP_TAHSILAT, self.db.KAYNAK_TIP_ODEME]:
                        success = self.db.gelir_gider_sil(hareket_id)
                    elif ref_tip == self.db.KAYNAK_TIP_VERESIYE_BORC_MANUEL:
                        success = self.db.cari_hareket_sil_manuel(hareket_id)
                        if not success:
                            QMessageBox.critical(self, "Hata", f"{ref_tip} türündeki hareket silinemiyor. API desteği gerekli olabilir.")
                    else:
                         QMessageBox.critical(self, "Hata", f"İşlem tipi ({ref_tip}) silinemiyor. API desteği gerekli.")
                         return

                if success:
                    QMessageBox.information(self, "Başarılı", message)
                    self._ozet_ve_liste_yenile()
                    
                    if hasattr(self.app, 'fatura_listesi_sayfasi'):
                        if hasattr(self.app.fatura_listesi_sayfasi, 'satis_fatura_frame'):
                            self.app.fatura_listesi_sayfasi.satis_fatura_frame.fatura_listesini_yukle()
                        if hasattr(self.app.fatura_listesi_sayfasi, 'alis_fatura_frame'):
                            self.app.fatura_listesi_sayfasi.alis_fatura_frame.fatura_listesini_yukle()
                    if hasattr(self.app, 'gelir_gider_sayfasi'):
                        if hasattr(self.app.gelir_gider_sayfasi, 'gelir_listesi_frame'):
                            self.app.gelir_gider_sayfasi.gelir_listesi_frame.gg_listesini_yukle()
                        if hasattr(self.app.gelir_gider_sayfasi, 'gider_listesi_frame'):
                            self.app.gelir_gider_sayfasi.gider_listesi_frame.gg_listesini_yukle()
                    if hasattr(self.app, 'kasa_banka_yonetimi_sayfasi'):
                        self.app.kasa_banka_yonetimi_sayfasi.hesap_listesini_yenile()
                else:
                    QMessageBox.critical(self, "Hata", message)
            except Exception as e:
                error_detail = str(e)
                QMessageBox.critical(self, "Hata", f"Silinirken hata: {error_detail}")
                logging.error(f"Cari Ekstresi silme hatası: {error_detail}", exc_info=True)
        else:
            self.app.set_status_message("Silme işlemi iptal edildi.", "blue")

    def secili_islemi_guncelle(self):
        selected_items = self.ekstre_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen güncellemek için bir fatura işlemi seçin.")
            return

        item_qt = selected_items[0]
        hareket_id = int(item_qt.text(0))

        hareket_detayi = self.hareket_detay_map.get(hareket_id)
        if not hareket_detayi:
            QMessageBox.critical(self, "Hata", "İşlem detayları bulunamadı.")
            return
        
        ref_id = hareket_detayi.get('kaynak_id')
        ref_tip = hareket_detayi.get('kaynak')

        if ref_tip in [self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA, self.db.KAYNAK_TIP_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_FATURA_ALIS_PESIN]:
            if ref_id:
                from pencereler import FaturaGuncellemePenceresi
                FaturaGuncellemePenceresi(self, self.db, ref_id, self._ozet_ve_liste_yenile).exec()
            else:
                QMessageBox.information(self, "Detay", "Fatura referansı bulunamadı.")
        else:
            QMessageBox.information(self, "Bilgi", "Sadece fatura işlemleri güncellenebilir.")

    def on_double_click_hareket_detay(self, item, column):
        if item.text(3) == "DEVİR":
            QMessageBox.warning(self, "Uyarı", "Devir satırı için detay görüntülenemez.")
            return

        hareket_id = int(item.text(0))
        hareket_detay = self.hareket_detay_map.get(hareket_id)

        if not hareket_detay:
            QMessageBox.critical(self, "Hata", "Seçilen işlemin detayları bulunamadı.")
            return

        ref_id = hareket_detay.get('kaynak_id')
        ref_tip_str = hareket_detay.get('kaynak')

        if ref_tip_str in [self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA, self.db.KAYNAK_TIP_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_FATURA_ALIS_PESIN]:
            if ref_id:
                from pencereler import FaturaDetayPenceresi
                FaturaDetayPenceresi(self.app, self.db, ref_id).exec()
            else:
                QMessageBox.information(self, "Detay", "Fatura referansı bulunamadı.")
        elif ref_tip_str in [self.db.KAYNAK_TIP_TAHSILAT, self.db.KAYNAK_TIP_ODEME, self.db.KAYNAK_TIP_VERESIYE_BORC_MANUEL]:
            tarih_gosterim = hareket_detay.get('tarih').strftime('%d.%m.%Y') if isinstance(hareket_detay.get('tarih'), date) else str(hareket_detay.get('tarih'))
            tutar_gosterim = self.db._format_currency(hareket_detay.get('tutar'))
            aciklama_gosterim = hareket_detay.get('aciklama') or "Açıklama yok."
            
            QMessageBox.information(self, "İşlem Detayı",
                                 f"Bu bir {ref_tip_str} işlemidir.\n"
                                 f"Tarih: {tarih_gosterim}\n"
                                 f"Tutar: {tutar_gosterim}\n" 
                                 f"Açıklama: {aciklama_gosterim}\n"
                                 f"Referans ID: {hareket_id}")
        else:
            QMessageBox.information(self, "Detay", "Bu işlem tipi için detay görüntüleme mevcut değil.")
            
class FaturaGuncellemePenceresi(QDialog):
    def __init__(self, parent, db_manager, fatura_id_duzenle, yenile_callback_liste=None):
        super().__init__(parent)
        self.app = parent.app if hasattr(parent, 'app') else parent
        self.db = db_manager
        self.yenile_callback_liste = yenile_callback_liste
        self.fatura_id_duzenle = fatura_id_duzenle

        try:
            fatura_ana_bilgileri = self.db.fatura_getir_by_id(self.fatura_id_duzenle)
            if not fatura_ana_bilgileri:
                QMessageBox.critical(self, "Hata", f"ID {self.fatura_id_duzenle} olan fatura bulunamadı.")
                self.reject()
                return

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Fatura bilgileri çekilirken bir hata oluştu: {e}")
            logger.error(f"Fatura bilgileri yüklenirken hata oluştu: {e}", exc_info=True)
            self.reject()
            return

        faturanın_gercek_islem_tipi = fatura_ana_bilgileri.get('fatura_turu')

        self.setWindowTitle(f"Fatura Güncelleme: {fatura_ana_bilgileri.get('fatura_no', 'Bilinmiyor')}")
        self.setWindowState(Qt.WindowMaximized)
        self.setModal(True)

        dialog_layout = QVBoxLayout(self)

        from arayuz import FaturaOlusturmaSayfasi
        self.fatura_olusturma_form = FaturaOlusturmaSayfasi(
            self,
            self.db,
            self.app,
            faturanın_gercek_islem_tipi,
            duzenleme_id=self.fatura_id_duzenle,
            yenile_callback=self._fatura_guncellendi_callback
        )
        dialog_layout.addWidget(self.fatura_olusturma_form)

        self.fatura_olusturma_form.saved_successfully.connect(self.accept)
        self.fatura_olusturma_form.cancelled_successfully.connect(self.reject)

        self.finished.connect(self.on_dialog_finished)

    def _fatura_guncellendi_callback(self):
        pass

    def on_dialog_finished(self, result):
        if self.yenile_callback_liste:
            self.yenile_callback_liste()

class FaturaPenceresi(QDialog):
    FATURA_TIP_ALIS = "ALIŞ"
    FATURA_TIP_SATIS = "SATIŞ"
    FATURA_TIP_DEVIR_GIRIS = "DEVİR GİRİŞ"
    FATURA_TIP_SATIS_IADE = "SATIŞ İADE"
    FATURA_TIP_ALIS_IADE = "ALIŞ İADE"

    ODEME_TURU_NAKIT = "NAKİT"
    ODEME_TURU_KART = "KART"
    ODEME_TURU_EFT_HAVALE = "EFT/HAVALE"
    ODEME_TURU_CEK = "ÇEK"
    ODEME_TURU_SENET = "SENET"
    ODEME_TURU_ACIK_HESAP = "AÇIK HESAP"
    ODEME_TURU_ETKISIZ_FATURA = "ETKİSİZ FATURA"

    pesin_odeme_turleri = ["NAKİT", "KART", "EFT/HAVALE", "ÇEK", "SENET"]

    CARI_TIP_MUSTERI = "MUSTERI"
    CARI_TIP_TEDARIKCI = "TEDARIKCI"

    def __init__(self, parent=None, db_manager=None, app_ref=None, fatura_tipi=None, duzenleme_id=None, yenile_callback=None, initial_data=None):
        super().__init__(parent)
        
        self.app = app_ref
        self.db = db_manager
        self.yenile_callback = yenile_callback
        self.duzenleme_id = duzenleme_id
        self.initial_data = initial_data or {}
        self.islem_tipi = fatura_tipi

        self.iade_modu_aktif = self.initial_data.get('iade_modu', False)
        self.original_fatura_id_for_iade = self.initial_data.get('orijinal_fatura_id')

        if self.iade_modu_aktif:
            if self.islem_tipi == self.FATURA_TIP_SATIS: self.islem_tipi = self.FATURA_TIP_SATIS_IADE
            elif self.islem_tipi == self.FATURA_TIP_ALIS: self.islem_tipi = self.FATURA_TIP_ALIS_IADE

        self.fatura_kalemleri_ui = []
        self.tum_urunler_cache = []
        self.urun_map_filtrelenmis = {}
        self.kasa_banka_map = {}
        self.cari_map_display_to_id = {}
        self.cari_id_to_display_map = {}

        self.secili_cari_id = None
        self.secili_cari_adi = ""
        self.perakende_musteri_id = None

        self.setWindowTitle(self._get_baslik())
        self.setWindowState(Qt.WindowMaximized)
        self.setModal(True)

        self.main_layout = QVBoxLayout(self)
        
        self._create_ui()
        self._connect_signals()
        self._load_initial_data()

        QTimer.singleShot(0, self._on_iade_modu_changed)

    def _connect_signals(self):
        self.btn_cari_sec.clicked.connect(self._cari_secim_penceresi_ac)
        self.odeme_turu_cb.currentIndexChanged.connect(self._odeme_turu_degisince_event_handler)
        self.genel_iskonto_tipi_cb.currentIndexChanged.connect(self._on_genel_iskonto_tipi_changed)
        self.genel_iskonto_degeri_e.textChanged.connect(self.toplamlari_hesapla_ui)

        self.urun_arama_entry.textChanged.connect(self._delayed_stok_yenile)
        self.urun_arama_sonuclari_tree.itemDoubleClicked.connect(self._select_product_from_search_list_and_focus_quantity)
        self.urun_arama_sonuclari_tree.itemSelectionChanged.connect(self._secili_urun_bilgilerini_goster_arama_listesinden)

        self.mik_e.textChanged.connect(lambda: format_and_validate_numeric_input(self.mik_e, 2))
        self.birim_fiyat_e.textChanged.connect(lambda: format_and_validate_numeric_input(self.birim_fiyat_e, 2))
        self.iskonto_yuzde_1_e.textChanged.connect(lambda: format_and_validate_numeric_input(self.iskonto_yuzde_1_e, 2))
        self.iskonto_yuzde_2_e.textChanged.connect(lambda: format_and_validate_numeric_input(self.iskonto_yuzde_2_e, 2))
        self.genel_iskonto_degeri_e.textChanged.connect(lambda: format_and_validate_numeric_input(self.genel_iskonto_degeri_e, 2))

        self.btn_sepete_ekle.clicked.connect(self._kalem_ekle_arama_listesinden)
        self.btn_secili_kalemi_sil.clicked.connect(self._secili_kalemi_sil)
        self.btn_sepeti_temizle.clicked.connect(self._sepeti_temizle)
        self.btn_kaydet.clicked.connect(self._kaydet_fatura)

        self.sep_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sep_tree.customContextMenuRequested.connect(self._open_sepet_context_menu)

    def _load_initial_data(self):
        try:
            self.perakende_musteri_id = self.db.get_perakende_musteri_id()

            self._yukle_carileri()
            self._yukle_kasa_banka_hesaplarini()
            self._urunleri_yukle_ve_cachele_ve_goster()
        except Exception as e:
            # Hata mesajı düzeltildi: 3. argüman kaldırıldı
            self.app.set_status_message(f"Hata: Başlangıç verileri yüklenemedi. Detay: {e}", "red")
            logging.error(f"FaturaPenceresi initial data yükleme hatası: {e}", exc_info=True)

        if self.duzenleme_id:
            self._mevcut_faturayi_yukle()
        elif self.initial_data:
            self._load_data_from_initial_data()
        else:
            self._reset_form_for_new_invoice()
        
        QTimer.singleShot(0, self._on_iade_modu_changed)

    def _get_baslik(self):
        if self.iade_modu_aktif:
            return "İade Faturası Oluştur"
        if self.duzenleme_id:
            return "Fatura Güncelleme"
        if self.islem_tipi == self.FATURA_TIP_SATIS:
            return "Yeni Satış Faturası"
        elif self.islem_tipi == self.FATURA_TIP_ALIS:
            return "Yeni Alış Faturası"
        return "Fatura"

    def _create_ui(self):
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(15)

        top_main_h_layout = QHBoxLayout()
        top_main_h_layout.setSpacing(15)
        self.main_layout.addLayout(top_main_h_layout)

        fatura_detay_groupbox = QGroupBox("Fatura Bilgileri", self) 
        fatura_detay_groupbox.setFont(QFont("Segoe UI", 10, QFont.Bold))
        fatura_detay_layout = QGridLayout(fatura_detay_groupbox)
        fatura_detay_layout.setContentsMargins(10, 20, 10, 10)
        fatura_detay_layout.setSpacing(8)
        fatura_detay_layout.setHorizontalSpacing(15)

        top_main_h_layout.addWidget(fatura_detay_groupbox, 3)

        fatura_detay_layout.addWidget(QLabel("Fatura No:", fatura_detay_groupbox), 0, 0, Qt.AlignRight)
        self.f_no_e = QLineEdit(fatura_detay_groupbox)
        fatura_detay_layout.addWidget(self.f_no_e, 0, 1)

        fatura_detay_layout.addWidget(QLabel("Tarih:", fatura_detay_groupbox), 0, 2, Qt.AlignRight)
        self.fatura_tarihi_entry = QLineEdit(datetime.now().strftime('%Y-%m-%d'), fatura_detay_groupbox)
        self.fatura_tarihi_entry.setReadOnly(True)
        fatura_detay_layout.addWidget(self.fatura_tarihi_entry, 0, 3)
        self.btn_fatura_tarihi = QPushButton("🗓️", fatura_detay_groupbox)
        self.btn_fatura_tarihi.setFixedWidth(30)
        self.btn_fatura_tarihi.clicked.connect(lambda: DatePickerDialog(self.app, self.fatura_tarihi_entry))
        fatura_detay_layout.addWidget(self.btn_fatura_tarihi, 0, 4)

        fatura_detay_layout.addWidget(QLabel("Cari Seç:", fatura_detay_groupbox), 1, 0, Qt.AlignRight)
        self.btn_cari_sec = QPushButton("Cari Seç...", fatura_detay_groupbox)
        self.btn_cari_sec.clicked.connect(self._cari_secim_penceresi_ac)
        fatura_detay_layout.addWidget(self.btn_cari_sec, 1, 1)
        
        self.lbl_secili_cari_adi = QLabel("Seçilen Cari: Yok", fatura_detay_groupbox)
        self.lbl_secili_cari_adi.setWordWrap(True)
        fatura_detay_layout.addWidget(self.lbl_secili_cari_adi, 1, 2, 1, 3, Qt.AlignLeft | Qt.AlignVCenter)

        self.lbl_cari_bakiye = QLabel("Bakiye: ---", fatura_detay_groupbox)
        self.lbl_cari_bakiye.setFont(QFont("Segoe UI", 9, QFont.Bold))
        fatura_detay_layout.addWidget(self.lbl_cari_bakiye, 2, 2, 1, 3, Qt.AlignRight | Qt.AlignVCenter)

        self.misafir_adi_container_frame = QFrame(fatura_detay_groupbox)
        misafir_layout = QHBoxLayout(self.misafir_adi_container_frame)
        misafir_layout.setContentsMargins(0, 0, 0, 0)
        misafir_layout.setSpacing(5)
        misafir_layout.addWidget(QLabel("Misafir Adı:", self.misafir_adi_container_frame))
        self.entry_misafir_adi = QLineEdit(self.misafir_adi_container_frame)
        misafir_layout.addWidget(self.entry_misafir_adi)
        fatura_detay_layout.addWidget(self.misafir_adi_container_frame, 2, 0, 1, 2)
        self.misafir_adi_container_frame.setVisible(False)

        fatura_detay_layout.addWidget(QLabel("Ödeme Türü:", fatura_detay_groupbox), 3, 0, Qt.AlignRight)
        self.odeme_turu_cb = QComboBox(fatura_detay_groupbox)
        self.odeme_turu_cb.addItems([self.ODEME_TURU_NAKIT, self.ODEME_TURU_KART, self.ODEME_TURU_EFT_HAVALE, self.ODEME_TURU_CEK, self.ODEME_TURU_SENET, self.ODEME_TURU_ACIK_HESAP, self.ODEME_TURU_ETKISIZ_FATURA])
        fatura_detay_layout.addWidget(self.odeme_turu_cb, 3, 1)

        fatura_detay_layout.addWidget(QLabel("Kasa/Banka:", fatura_detay_groupbox), 4, 0, Qt.AlignRight)
        self.islem_hesap_cb = QComboBox(fatura_detay_groupbox)
        self.islem_hesap_cb.setEnabled(False)
        fatura_detay_layout.addWidget(self.islem_hesap_cb, 4, 1, 1, 3)
        
        self.lbl_vade_tarihi = QLabel("Vade Tarihi:", fatura_detay_groupbox)
        fatura_detay_layout.addWidget(self.lbl_vade_tarihi, 5, 0, Qt.AlignRight)
        self.entry_vade_tarihi = QLineEdit(fatura_detay_groupbox)
        self.entry_vade_tarihi.setReadOnly(True)
        self.entry_vade_tarihi.setEnabled(False)
        fatura_detay_layout.addWidget(self.entry_vade_tarihi, 5, 1)
        self.btn_vade_tarihi = QPushButton("🗓️", fatura_detay_groupbox)
        self.btn_vade_tarihi.setFixedWidth(30)
        self.btn_vade_tarihi.clicked.connect(lambda: DatePickerDialog(self.app, self.entry_vade_tarihi))
        self.btn_vade_tarihi.setEnabled(False)
        fatura_detay_layout.addWidget(self.btn_vade_tarihi, 5, 2)
        
        fatura_detay_layout.addWidget(QLabel("Fatura Notları:", fatura_detay_groupbox), 6, 0, Qt.AlignTop | Qt.AlignRight)
        self.fatura_notlari_text = QTextEdit(fatura_detay_groupbox)
        self.fatura_notlari_text.setFixedHeight(60)
        fatura_detay_layout.addWidget(self.fatura_notlari_text, 6, 1, 1, 4)

        urun_ekle_groupbox = QGroupBox("Ürün Ekleme", self)
        urun_ekle_groupbox.setFont(QFont("Segoe UI", 10, QFont.Bold))
        urun_ekle_layout = QGridLayout(urun_ekle_groupbox)
        urun_ekle_layout.setContentsMargins(10, 20, 10, 10)
        urun_ekle_layout.setSpacing(8)
        urun_ekle_layout.setHorizontalSpacing(15)

        top_main_h_layout.addWidget(urun_ekle_groupbox, 2)

        urun_ekle_layout.addWidget(QLabel("Ürün Ara (Kod/Ad):", urun_ekle_groupbox), 0, 0, Qt.AlignRight)
        self.urun_arama_entry = QLineEdit(urun_ekle_groupbox)
        self.urun_arama_entry.setPlaceholderText("Ürün kodu veya adı ile ara...")
        urun_ekle_layout.addWidget(self.urun_arama_entry, 0, 1)

        self.urun_arama_sonuclari_tree = QTreeWidget(urun_ekle_groupbox)
        self.urun_arama_sonuclari_tree.setHeaderLabels(["Ürün Adı", "Kod", "Fiyat", "Stok"])
        self.urun_arama_sonuclari_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.urun_arama_sonuclari_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.urun_arama_sonuclari_tree.setRootIsDecorated(False)
        self.urun_arama_sonuclari_tree.setAlternatingRowColors(True)
        
        header = self.urun_arama_sonuclari_tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        urun_ekle_layout.addWidget(self.urun_arama_sonuclari_tree, 1, 0, 1, 2)

        urun_ekle_layout.addWidget(QLabel("Miktar:", urun_ekle_groupbox), 2, 0, Qt.AlignRight)
        self.mik_e = QLineEdit("1", urun_ekle_groupbox)
        setup_numeric_entry(self.app, self.mik_e, decimal_places=2)
        urun_ekle_layout.addWidget(self.mik_e, 2, 1)

        urun_ekle_layout.addWidget(QLabel("Birim Fiyat (KDV Dahil):", urun_ekle_groupbox), 3, 0, Qt.AlignRight)
        self.birim_fiyat_e = QLineEdit("0,00", urun_ekle_groupbox)
        setup_numeric_entry(self.app, self.birim_fiyat_e, decimal_places=2)
        urun_ekle_layout.addWidget(self.birim_fiyat_e, 3, 1)
        
        urun_ekle_layout.addWidget(QLabel("Stok:", urun_ekle_groupbox), 4, 0, Qt.AlignRight)
        self.stk_l = QLabel("-", urun_ekle_groupbox)
        self.stk_l.setFont(QFont("Segoe UI", 9, QFont.Bold))
        urun_ekle_layout.addWidget(self.stk_l, 4, 1)

        urun_ekle_layout.addWidget(QLabel("İsk.1(%):", urun_ekle_groupbox), 5, 0, Qt.AlignRight)
        self.iskonto_yuzde_1_e = QLineEdit("0,00", urun_ekle_groupbox)
        setup_numeric_entry(self.app, self.iskonto_yuzde_1_e, decimal_places=2, max_value=100)
        urun_ekle_layout.addWidget(self.iskonto_yuzde_1_e, 5, 1)

        urun_ekle_layout.addWidget(QLabel("İsk.2(%):", urun_ekle_groupbox), 6, 0, Qt.AlignRight)
        self.iskonto_yuzde_2_e = QLineEdit("0,00", urun_ekle_groupbox)
        setup_numeric_entry(self.app, self.iskonto_yuzde_2_e, decimal_places=2, max_value=100)
        urun_ekle_layout.addWidget(self.iskonto_yuzde_2_e, 6, 1)

        self.btn_sepete_ekle = QPushButton("Sepete Ekle", urun_ekle_groupbox)
        self.btn_sepete_ekle.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_sepete_ekle.setStyleSheet("padding: 8px;")
        urun_ekle_layout.addWidget(self.btn_sepete_ekle, 7, 0, 1, 2)

        sepet_groupbox = QGroupBox("Fatura Kalemleri", self)
        sepet_groupbox.setFont(QFont("Segoe UI", 10, QFont.Bold))
        sepet_layout = QVBoxLayout(sepet_groupbox)
        sepet_layout.setContentsMargins(10, 20, 10, 10)
        sepet_layout.setSpacing(10)
        self.main_layout.addWidget(sepet_groupbox, 1)

        self.sep_tree = QTreeWidget(sepet_groupbox)
        self.sep_tree.setHeaderLabels(["#", "Ürün Adı", "Mik.", "B.Fiyat", "KDV%", "İskonto 1 (%)", "İskonto 2 (%)", "Uyg. İsk. Tutarı", "Tutar(Dah.)", "Fiyat Geçmişi", "Ürün ID"])
        self.sep_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sep_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.sep_tree.setAlternatingRowColors(True)
        
        header = self.sep_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.Fixed)
        header.setSectionResizeMode(10, QHeaderView.Fixed)
        self.sep_tree.setColumnWidth(9, 90)
        self.sep_tree.setColumnHidden(10, True)

        sepet_layout.addWidget(self.sep_tree)

        btn_sepet_islemleri_frame = QFrame(sepet_groupbox)
        btn_sepet_islemleri_layout = QHBoxLayout(btn_sepet_islemleri_frame)
        btn_sepet_islemleri_layout.setContentsMargins(0, 5, 0, 0)
        btn_sepet_islemleri_layout.addStretch()
        self.btn_secili_kalemi_sil = QPushButton("Seçili Kalemi Sil", btn_sepet_islemleri_frame)
        btn_sepet_islemleri_layout.addWidget(self.btn_secili_kalemi_sil)

        self.btn_sepeti_temizle = QPushButton("Tüm Kalemleri Sil", btn_sepet_islemleri_frame)
        btn_sepet_islemleri_layout.addWidget(self.btn_sepeti_temizle)
        sepet_layout.addWidget(btn_sepet_islemleri_frame)


        footer_groupbox = QGroupBox("Genel Toplamlar", self)
        footer_groupbox.setFont(QFont("Segoe UI", 10, QFont.Bold))
        footer_layout = QGridLayout(footer_groupbox)
        footer_layout.setContentsMargins(10, 20, 10, 10)
        footer_layout.setSpacing(8)
        self.main_layout.addWidget(footer_groupbox)

        footer_layout.addWidget(QLabel("Genel İskonto Tipi:", footer_groupbox), 0, 0, Qt.AlignRight)
        self.genel_iskonto_tipi_cb = QComboBox(footer_groupbox)
        self.genel_iskonto_tipi_cb.addItems(["YOK", "YUZDE", "TUTAR"])
        footer_layout.addWidget(self.genel_iskonto_tipi_cb, 0, 1, Qt.AlignLeft)

        footer_layout.addWidget(QLabel("Genel İskonto Değeri:", footer_groupbox), 1, 0, Qt.AlignRight)
        self.genel_iskonto_degeri_e = QLineEdit("0,00", footer_groupbox)
        setup_numeric_entry(self.app, self.genel_iskonto_degeri_e, decimal_places=2)
        self.genel_iskonto_degeri_e.setEnabled(False)
        footer_layout.addWidget(self.genel_iskonto_degeri_e, 1, 1, Qt.AlignLeft)
        
        self.lbl_uygulanan_genel_iskonto = QLabel("Uygulanan Genel İskonto: 0,00 TL", footer_groupbox)
        self.lbl_uygulanan_genel_iskonto.setFont(QFont("Segoe UI", 9, italic=True))
        footer_layout.addWidget(self.lbl_uygulanan_genel_iskonto, 2, 0, 1, 2, Qt.AlignLeft)

        self.tkh_l = QLabel("KDV Hariç Toplam: 0,00 TL", footer_groupbox)
        self.tkh_l.setFont(QFont("Segoe UI", 10, QFont.Bold))
        footer_layout.addWidget(self.tkh_l, 0, 2, Qt.AlignRight)

        self.tkdv_l = QLabel("Toplam KDV: 0,00 TL", footer_groupbox)
        self.tkdv_l.setFont(QFont("Segoe UI", 10, QFont.Bold))
        footer_layout.addWidget(self.tkdv_l, 1, 2, Qt.AlignRight)

        self.gt_l = QLabel("Genel Toplam: 0,00 TL", footer_groupbox)
        self.gt_l.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.gt_l.setStyleSheet("color: navy;")
        footer_layout.addWidget(self.gt_l, 2, 2, Qt.AlignRight)

        self.btn_kaydet = QPushButton("Kaydet", footer_groupbox)
        self.btn_kaydet.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.btn_kaydet.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; border-radius: 5px;")
        footer_layout.addWidget(self.btn_kaydet, 0, 3, 3, 1, Qt.AlignRight | Qt.AlignVCenter)

    def _mevcut_faturayi_yukle(self):
        """
        Düzenleme modunda mevcut faturanın bilgilerini API'den çeker ve forma yükler.
        """
        try:
            fatura_ana = self.db.fatura_getir_by_id(self.duzenleme_id)
            if not fatura_ana:
                self.app.set_status_message(f"Hata: Fatura ID {self.duzenleme_id} bulunamadı.", "red")
                return

            fatura_kalemleri_api = self.db.fatura_kalemleri_al(self.duzenleme_id)
            
            self.f_no_e.setText(fatura_ana.get('fatura_no', ''))
            self.fatura_tarihi_entry.setText(fatura_ana.get('tarih', ''))

            self.secili_cari_id = fatura_ana.get('cari_id')
            self.lbl_secili_cari_adi.setText(f"Seçilen Cari: {fatura_ana.get('cari_adi', 'Yok')}")
            self._on_cari_selected()

            self.odeme_turu_cb.setCurrentText(fatura_ana.get('odeme_turu', self.ODEME_TURU_NAKIT))
            
            if fatura_ana.get('kasa_banka_id'):
                for i in range(self.islem_hesap_cb.count()):
                    if self.islem_hesap_cb.itemData(i) == fatura_ana.get('kasa_banka_id'):
                        self.islem_hesap_cb.setCurrentIndex(i)
                        break

            self.entry_vade_tarihi.setText(fatura_ana.get('vade_tarihi', ''))
            self.fatura_notlari_text.setPlainText(fatura_ana.get('fatura_notlari', ''))
            self.genel_iskonto_tipi_cb.setCurrentText(fatura_ana.get('genel_iskonto_tipi', "YOK"))
            self.genel_iskonto_degeri_e.setText(f"{fatura_ana.get('genel_iskonto_degeri', 0.0):.2f}".replace('.', ','))
            self._on_genel_iskonto_tipi_changed()

            self.fatura_kalemleri_ui.clear()
            for k_api in fatura_kalemleri_api:
                urun_adi = self._get_urun_adi_by_id(k_api.get('urun_id'))

                self.fatura_kalemleri_ui.append((
                    k_api.get('urun_id'),
                    urun_adi,
                    k_api.get('miktar'),
                    k_api.get('birim_fiyat'),
                    k_api.get('kdv_orani'),
                    k_api.get('kdv_tutari', 0.0),
                    k_api.get('kalem_toplam_kdv_haric', 0.0),
                    k_api.get('kalem_toplam_kdv_dahil', 0.0),
                    k_api.get('alis_fiyati_fatura_aninda', 0.0),
                    k_api.get('kdv_orani_fatura_aninda', k_api.get('kdv_orani')),
                    k_api.get('iskonto_yuzde_1', 0.0),
                    k_api.get('iskonto_yuzde_2', 0.0),
                    k_api.get('iskonto_tipi', "YOK"),
                    k_api.get('iskonto_degeri', 0.0),
                    (k_api.get('kalem_toplam_kdv_dahil') / k_api.get('miktar')) if k_api.get('miktar') else 0.0
                ))
            
            self._sepeti_guncelle_ui()
            self.toplamlari_hesapla_ui()
            self.f_no_e.setEnabled(False)
            self.btn_cari_sec.setEnabled(False)

            if self.iade_modu_aktif:
                self.f_no_e.setEnabled(False)
                self.btn_cari_sec.setEnabled(False)
        
        except Exception as e:
            self.app.set_status_message(f"Hata: Fatura bilgileri yüklenemedi. Detay: {e}", "red")
            logging.error(f"Fatura yükleme hatası: {e}", exc_info=True)

    def _load_data_from_initial_data(self):
        self.f_no_e.setText(self.initial_data.get('fatura_no', self.db.son_fatura_no_getir(self.islem_tipi)))
        self.fatura_tarihi_entry.setText(self.initial_data.get('tarih', datetime.now().strftime('%Y-%m-%d')))
        
        self.odeme_turu_cb.setCurrentText(self.initial_data.get('odeme_turu', self.ODEME_TURU_NAKIT))
        self._odeme_turu_degisince_event_handler()

        self.secili_cari_id = self.initial_data.get('cari_id')
        self.lbl_secili_cari_adi.setText(f"Seçilen Cari: {self.initial_data.get('cari_adi', 'Yok')}")
        self._on_cari_selected()

        self.entry_vade_tarihi.setText(self.initial_data.get('vade_tarihi', ''))
        self.fatura_notlari_text.setPlainText(self.initial_data.get('fatura_notlari', ''))
        self.genel_iskonto_tipi_cb.setCurrentText(self.initial_data.get('genel_iskonto_tipi', "YOK"))
        self.genel_iskonto_degeri_e.setText(f"{self.initial_data.get('genel_iskonto_degeri', 0.0):.2f}".replace('.',','))
        self._on_genel_iskonto_tipi_changed()

        self.fatura_kalemleri_ui.clear()
        for k_init in self.initial_data.get('kalemler', []):
            urun_adi = self._get_urun_adi_by_id(k_init.get('urun_id'))

            kdv_orani_init = k_init.get('kdv_orani', 0.0)
            original_bf_haric_init = k_init.get('birim_fiyat')
            
            iskonto_yuzde_1_init = k_init.get('iskonto_yuzde_1', 0.0)
            iskonto_yuzde_2_init = k_init.get('iskonto_yuzde_2', 0.0)
            
            fiyat_iskonto_1_sonrasi_dahil_calc = original_bf_haric_init * (1 + kdv_orani_init / 100) * (1 - iskonto_yuzde_1_init / 100)
            iskontolu_birim_fiyat_kdv_dahil_calc = fiyat_iskonto_1_sonrasi_dahil_calc * (1 - iskonto_yuzde_2_init / 100)

            alis_fiyati_fatura_aninda_init = k_init.get('alis_fiyati_fatura_aninda', 0.0)

            self.fatura_kalemleri_ui.append((
                k_init.get('urun_id'), urun_adi, k_init.get('miktar'), 
                original_bf_haric_init,
                kdv_orani_init,
                0.0, 0.0, 0.0,
                alis_fiyati_fatura_aninda_init,
                kdv_orani_init,
                iskonto_yuzde_1_init,
                iskonto_yuzde_2_init,
                k_init.get('iskonto_tipi', "YOK"),
                k_init.get('iskonto_degeri', 0.0),
                iskontolu_birim_fiyat_kdv_dahil_calc
            ))
        
        self._sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()

    def _reset_form_for_new_invoice(self):
        self.duzenleme_id = None
        self.fatura_kalemleri_ui.clear()
        self._sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()

        self.f_no_e.setText(self.db.son_fatura_no_getir(self.islem_tipi))
        self.fatura_tarihi_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        self.odeme_turu_cb.setCurrentText(self.ODEME_TURU_NAKIT)
        self.entry_vade_tarihi.clear()
        self.fatura_notlari_text.clear()
        self.genel_iskonto_tipi_cb.setCurrentText("YOK")
        self.genel_iskonto_degeri_e.setText("0,00")
        self.btn_cari_sec.setEnabled(True)
        self._on_genel_iskonto_tipi_changed()

        self._temizle_cari_secimi()

        self.urun_arama_entry.clear()
        self.mik_e.setText("1")
        self.birim_fiyat_e.setText("0,00")
        self.stk_l.setText("-")
        self.iskonto_yuzde_1_e.setText("0,00")
        self.iskonto_yuzde_2_e.setText("0,00")

        QTimer.singleShot(0, self._urunleri_yukle_ve_cachele_ve_goster)
        self.f_no_e.setFocus()

    def _temizle_cari_secimi(self):
        self.secili_cari_id = None
        self.secili_cari_adi = ""
        self.lbl_secili_cari_adi.setText("Seçilen Cari: Yok")
        if hasattr(self, 'misafir_adi_container_frame'):
            self.misafir_adi_container_frame.setVisible(False)
            if hasattr(self, 'entry_misafir_adi'):
                self.entry_misafir_adi.clear()

    def _on_iade_modu_changed(self):
        self.setWindowTitle(self._get_baslik())

        if self.iade_modu_aktif:
            self.f_no_e.setEnabled(False)
            self.btn_cari_sec.setEnabled(False)
            
            self.odeme_turu_cb.setEnabled(True)
            self.islem_hesap_cb.setEnabled(True)
            self.entry_vade_tarihi.setEnabled(True)
            self.btn_vade_tarihi.setEnabled(True)

            self.fatura_notlari_text.setPlainText(f"Orijinal Fatura ID: {self.original_fatura_id_for_iade} için iade faturasıdır.")
            
            if hasattr(self, 'misafir_adi_container_frame'):
                self.misafir_adi_container_frame.setVisible(False)

            self._odeme_turu_degisince_event_handler()
            QMessageBox.information(self, "Bilgi", "İade Faturası modu aktif. Fatura No ve Cari kilitlenmiştir.")
        else:
            self.f_no_e.setEnabled(True)
            self.btn_cari_sec.setEnabled(True)
            self.fatura_notlari_text.clear()
            self._odeme_turu_degisince_event_handler()
    
    def _on_genel_iskonto_tipi_changed(self):
        selected_type = self.genel_iskonto_tipi_cb.currentText()
        if selected_type == "YOK":
            self.genel_iskonto_degeri_e.setEnabled(False)
            self.genel_iskonto_degeri_e.setText("0,00")
        else:
            self.genel_iskonto_degeri_e.setEnabled(True)
        self.toplamlari_hesapla_ui()

    def _odeme_turu_degisince_event_handler(self):
        selected_odeme_turu = self.odeme_turu_cb.currentText()
        
        is_acik_hesap = (selected_odeme_turu == self.ODEME_TURU_ACIK_HESAP)
        self.lbl_vade_tarihi.setVisible(is_acik_hesap)
        self.entry_vade_tarihi.setVisible(is_acik_hesap)
        self.btn_vade_tarihi.setVisible(is_acik_hesap)
        self.entry_vade_tarihi.setEnabled(is_acik_hesap)
        self.btn_vade_tarihi.setEnabled(is_acik_hesap)

        if is_acik_hesap and not self.entry_vade_tarihi.text():
            self.entry_vade_tarihi.setText((datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'))
        elif not is_acik_hesap:
            self.entry_vade_tarihi.clear()

        is_pesin_odeme = (selected_odeme_turu in self.pesin_odeme_turleri)
        self.islem_hesap_cb.setEnabled(is_pesin_odeme)

        if is_pesin_odeme:
            try:
                varsayilan_kb_list_response = self.db.get_varsayilan_kasa_banka(selected_odeme_turu)
                if varsayilan_kb_list_response:
                    varsayilan_kb_id = varsayilan_kb_list_response.get('id')
                    for i in range(self.islem_hesap_cb.count()):
                        if self.islem_hesap_cb.itemData(i) == varsayilan_kb_id:
                            self.islem_hesap_cb.setCurrentIndex(i)
                            break
                elif self.islem_hesap_cb.count() > 0:
                    self.islem_hesap_cb.setCurrentIndex(0)
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Varsayılan kasa/banka çekilirken hata: {e}")
                logging.warning(f"Varsayılan KB çekme hatası: {e}")
                if self.islem_hesap_cb.count() > 0: self.islem_hesap_cb.setCurrentIndex(0)
        else:
            self.islem_hesap_cb.clear()

        is_perakende_satis_current = (self.islem_tipi == self.FATURA_TIP_SATIS and
                                      self.secili_cari_id == self.perakende_musteri_id)
        
        if hasattr(self, 'misafir_adi_container_frame'):
            self.misafir_adi_container_frame.setVisible(is_perakende_satis_current and not self.iade_modu_aktif)
            if hasattr(self, 'entry_misafir_adi'):
                self.entry_misafir_adi.setEnabled(is_perakende_satis_current and not self.iade_modu_aktif)
                if not (is_perakende_satis_current and not self.iade_modu_aktif):
                    self.entry_misafir_adi.clear()

    def _yukle_carileri(self):
        self.tum_cariler_cache_data = []
        self.cari_map_display_to_id = {}
        self.cari_id_to_display_map = {}
        
        api_url = ""
        
        if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE]:
            api_url = "/musteriler/"
        elif self.islem_tipi in [self.db.FATURA_TIP_ALIS, self.db.FATURA_TIP_ALIS_IADE, self.db.FATURA_TIP_DEVIR_GIRIS]:
            api_url = "/tedarikciler/"
        
        if api_url:
            try:
                # `cariler_data`'nın `dict` mi yoksa `list` mi olduğunu kontrol ederek robust hale getirildi
                cariler_response = self.db.musteri_listesi_al() if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE] else self.db.tedarikci_listesi_al()
                
                cariler = []
                if isinstance(cariler_response, dict) and "items" in cariler_response:
                    cariler = cariler_response["items"]
                elif isinstance(cariler_response, list): # Eğer API doğrudan liste dönüyorsa
                    cariler = cariler_response
                else:
                    logging.warning("Cari listesi API yanıtı beklenen formatta değil.")
                    self.app.set_status_message("Uyarı: Cari listesi API yanıtı beklenen formatta değil.", "orange")
                    return # Veri formatı uyumsuzsa işlemi durdur

                for c in cariler:
                    cari_id = c.get('id')
                    cari_ad = c.get('ad')
                    cari_kodu_gosterim = c.get('kod', "") if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE] else c.get('tedarikci_kodu', "")
                    
                    display_text = f"{cari_ad} (Kod: {cari_kodu_gosterim})"
                    self.cari_map_display_to_id[display_text] = str(cari_id)
                    self.cari_id_to_display_map[str(cari_id)] = display_text
                    self.tum_cariler_cache_data.append(c)
                
                self.app.set_status_message(f"{len(cariler)} cari API'den yüklendi.")

            except Exception as e:
                QMessageBox.critical(self.app, "Hata", f"Cari listesi çekilirken hata: {e}")
                logging.error(f"FaturaPenceresi cari listesi yükleme hatası: {e}", exc_info=True)
        else:
            self.app.set_status_message("Cari listesi yüklenemedi (geçersiz fatura tipi).")

    def _cari_secim_penceresi_ac(self):
        try:
            cari_tip_for_dialog = None
            if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE]:
                cari_tip_for_dialog = self.CARI_TIP_MUSTERI
            elif self.islem_tipi in [self.db.FATURA_TIP_ALIS, self.db.FATURA_TIP_ALIS_IADE, self.db.FATURA_TIP_DEVIR_GIRIS]:
                cari_tip_for_dialog = self.CARI_TIP_TEDARIKCI

            from pencereler import CariSecimPenceresi
            dialog = CariSecimPenceresi(self, self.db, cari_tip_for_dialog, self._on_cari_secildi_callback)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Cari seçim penceresi açılırken hata: {e}")
            logging.error(f"Cari seçim penceresi açma hatası: {e}")

    def _on_cari_secildi_callback(self, selected_cari_id, selected_cari_display_text):
        self.secili_cari_id = selected_cari_id
        self.secili_cari_adi = selected_cari_display_text
        self.lbl_secili_cari_adi.setText(f"Seçilen Cari: {self.secili_cari_adi}")
        self._on_cari_selected()

    def _on_cari_selected(self):
        if not self.secili_cari_id:
            self.lbl_cari_bakiye.setText("Bakiye: ---")
            self._odeme_turu_degisince_event_handler()
            return
        
        cari_tip_for_bakiye = None
        if self.islem_tipi in [self.FATURA_TIP_SATIS, self.FATURA_TIP_SATIS_IADE]:
            cari_tip_for_bakiye = self.CARI_TIP_MUSTERI
        elif self.islem_tipi in [self.FATURA_TIP_ALIS, self.FATURA_TIP_ALIS_IADE, self.FATURA_TIP_DEVIR_GIRIS]:
            cari_tip_for_bakiye = self.CARI_TIP_TEDARIKCI
        
        if cari_tip_for_bakiye:
            bakiye_bilgisi = None
            try:
                bakiye_bilgisi = self.db.get_musteri_net_bakiye(self.secili_cari_id) if cari_tip_for_bakiye == self.CARI_TIP_MUSTERI else self.db.get_tedarikci_net_bakiye(self.secili_cari_id)
                
                if bakiye_bilgisi is not None:
                    bakiye_str = self.db._format_currency(bakiye_bilgisi)
                    if bakiye_bilgisi > 0:
                        self.lbl_cari_bakiye.setText(f"Borç: {bakiye_str}")
                        self.lbl_cari_bakiye.setStyleSheet("color: red;")
                    elif bakiye_bilgisi < 0:
                        self.lbl_cari_bakiye.setText(f"Alacak: {bakiye_str}")
                        self.lbl_cari_bakiye.setStyleSheet("color: green;")
                    else:
                        self.lbl_cari_bakiye.setText("Bakiye: 0,00 TL")
                        self.lbl_cari_bakiye.setStyleSheet("color: black;")
                else:
                    self.lbl_cari_bakiye.setText("Bakiye: ---")
                    self.lbl_cari_bakiye.setStyleSheet("color: black;")
            except Exception as e:
                self.lbl_cari_bakiye.setText("Bakiye: Hata")
                self.lbl_cari_bakiye.setStyleSheet("color: red;")
                logging.error(f"Cari bakiye çekilirken hata: {e}")

        self._odeme_turu_degisince_event_handler()

    def _urunleri_yukle_ve_cachele_ve_goster(self):
        try:
            filters = {"limit": 10000, "aktif_durum": True}
            stok_listeleme_sonucu = self.db.stok_listesi_al(**filters)
            
            # API'den gelen yanıtın dict içinde 'items' anahtarı olup olmadığını kontrol et
            # Yoksa, doğrudan listeyi kullan (eski API davranışı veya hata durumunda)
            if isinstance(stok_listeleme_sonucu, dict) and "items" in stok_listeleme_sonucu:
                urunler = stok_listeleme_sonucu["items"]
            elif isinstance(stok_listeleme_sonucu, list): # Eğer API doğrudan liste dönüyorsa
                urunler = stok_listeleme_sonucu
                self.app.set_status_message("Uyarı: Stok listesi API yanıtı beklenen formatta değil. Doğrudan liste olarak işleniyor.", "orange")
            else: # Beklenmeyen bir format gelirse
                urunler = []
                self.app.set_status_message("Hata: Stok listesi API'den alınamadı veya formatı geçersiz.", "red")
                logging.error(f"Stok listesi API'den beklenen formatta gelmedi: {type(stok_listeleme_sonucu)} - {stok_listeleme_sonucu}")
                return # Hata durumunda fonksiyonu sonlandır

            self.tum_urunler_cache = urunler
            self.urun_map_filtrelenmis.clear()

            # Hata veren urun_arama_list_widget yerine doğru isimlendirilmiş urun_arama_sonuclari_tree kullanıldı
            self.urun_arama_sonuclari_tree.clear()
            for urun in urunler:
                item_text = f"{urun.get('kod', '')} - {urun.get('ad', '')} ({urun.get('miktar', 0):.2f} {urun.get('birim', {}).get('ad', '')})"
                item = QTreeWidgetItem(self.urun_arama_sonuclari_tree) # QTreeWidgetItem doğrudan QTreeWidget'a eklenir
                item.setText(0, item_text) # İlk sütun için metin
                item.setData(0, Qt.UserRole, urun["id"]) # ID'yi UserRole olarak sakla
                # Diğer sütunları da burada ayarlamanız gerekebilir, örneğin item.setText(1, urun["kod"])
            
            # urun_arama_list_widget yerine urun_arama_sonuclari_tree kullanıldı
            # QTreeWidget'ın .hide() metodu yoktur, bunun yerine setVisible(False) kullanılır.
            self.urun_arama_sonuclari_tree.setVisible(False) # QTreeWidget'ı gizle
            
            self.app.set_status_message(f"{len(urunler)} ürün API'den önbelleğe alındı.")

        except Exception as e:
            logger.error(f"Ürün listesi yüklenirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Ürünler yüklenemedi. Detay: {e}", "red")
            
    def _delayed_stok_yenile(self):
        if hasattr(self, '_delayed_timer') and self._delayed_timer.isActive():
            self._delayed_timer.stop()
        self._delayed_timer = QTimer(self)
        self._delayed_timer.setSingleShot(True)
        self._delayed_timer.timeout.connect(self._urun_listesini_filtrele_anlik)
        self._delayed_timer.start(300)

    def _urun_listesini_filtrele_anlik(self):
        arama_terimi = self.urun_arama_entry.text().lower().strip()
        self.urun_arama_sonuclari_tree.clear()
        self.urun_map_filtrelenmis.clear()

        for urun_item in self.tum_urunler_cache:
            urun_kodu = urun_item.get('kod', '').lower()
            urun_adi = urun_item.get('ad', '').lower()

            if arama_terimi in urun_kodu or arama_terimi in urun_adi:
                item_qt = QTreeWidgetItem(self.urun_arama_sonuclari_tree)
                item_qt.setText(0, urun_item.get('ad', ''))
                item_qt.setText(1, urun_item.get('kod', ''))
                
                if self.islem_tipi == self.FATURA_TIP_SATIS:
                    fiyat_gosterim = urun_item.get('satis_fiyati', 0.0)
                elif self.islem_tipi == self.FATURA_TIP_ALIS:
                    fiyat_gosterim = urun_item.get('alis_fiyati', 0.0)
                elif self.islem_tipi == self.FATURA_TIP_SATIS_IADE:
                    fiyat_gosterim = urun_item.get('alis_fiyati', 0.0)
                elif self.islem_tipi == self.FATURA_TIP_ALIS_IADE:
                    fiyat_gosterim = urun_item.get('satis_fiyati', 0.0)
                else:
                    fiyat_gosterim = 0.0

                item_qt.setText(2, self.db._format_currency(fiyat_gosterim))
                item_qt.setText(3, f"{urun_item.get('miktar', 0.0):.2f}".rstrip('0').rstrip('.'))
                
                item_qt.setData(0, Qt.UserRole, urun_item['id'])

                self.urun_map_filtrelenmis[urun_item['id']] = {
                    "id": urun_item['id'],
                    "kod": urun_item['kod'],
                    "ad": urun_item['ad'],
                    "alis_fiyati": urun_item.get('alis_fiyati'),
                    "satis_fiyati": urun_item.get('satis_fiyati'),
                    "kdv_orani": urun_item.get('kdv_orani'),
                    "miktar": urun_item.get('miktar')
                }
        self.urun_arama_sonuclari_tree.sortByColumn(0, Qt.AscendingOrder)
        self._secili_urun_bilgilerini_goster_arama_listesinden(None)

    def _select_product_from_search_list_and_focus_quantity(self, item):
        self._secili_urun_bilgilerini_goster_arama_listesinden(item)
        self.mik_e.setFocus()
        self.mik_e.selectAll()

    def _secili_urun_bilgilerini_goster_arama_listesinden(self, item):
        selected_items = self.urun_arama_sonuclari_tree.selectedItems()
        if selected_items:
            urun_id = selected_items[0].data(0, Qt.UserRole)
            if urun_id in self.urun_map_filtrelenmis:
                urun_detaylari = self.urun_map_filtrelenmis[urun_id]
                
                if self.islem_tipi == self.FATURA_TIP_SATIS:
                    birim_fiyat_to_fill = urun_detaylari.get('satis_fiyati', 0.0)
                elif self.islem_tipi == self.FATURA_TIP_ALIS:
                    birim_fiyat_to_fill = urun_detaylari.get('alis_fiyati', 0.0)
                elif self.islem_tipi == self.FATURA_TIP_SATIS_IADE:
                    birim_fiyat_to_fill = urun_detaylari.get('alis_fiyati', 0.0)
                elif self.islem_tipi == self.FATURA_TIP_ALIS_IADE:
                    birim_fiyat_to_fill = urun_detaylari.get('satis_fiyati', 0.0)
                else:
                    birim_fiyat_to_fill = 0.0

                self.birim_fiyat_e.setText(f"{birim_fiyat_to_fill:.2f}".replace('.',','))
                self.stk_l.setText(f"{urun_detaylari['miktar']:.2f}".rstrip('0').rstrip('.'))
                self.stk_l.setStyleSheet("color: black;")
            else:
                self.birim_fiyat_e.setText("0,00")
                self.stk_l.setText("-")
                self.stk_l.setStyleSheet("color: black;")
        else:
            self.birim_fiyat_e.setText("0,00")
            self.stk_l.setText("-")
            self.stk_l.setStyleSheet("color: black;")

    def _kalem_ekle_arama_listesinden(self):
        selected_items = self.urun_arama_sonuclari_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Geçersiz Ürün", "Lütfen arama listesinden bir ürün seçin.")
            return
        
        urun_id = selected_items[0].data(0, Qt.UserRole)
        if urun_id not in self.urun_map_filtrelenmis:
            QMessageBox.warning(self.app, "Geçersiz Ürün", "Seçili ürün detayları bulunamadı.")
            return
        
        urun_detaylari = self.urun_map_filtrelenmis[urun_id]
        
        try:
            miktar_str = self.mik_e.text().replace(',', '.')
            eklenecek_miktar = float(miktar_str) if miktar_str else 0.0
            if eklenecek_miktar <= 0:
                QMessageBox.critical(self.app, "Geçersiz Miktar", "Miktar pozitif bir sayı olmalıdır.")
                return

            birim_fiyat_str = self.birim_fiyat_e.text().replace(',', '.')
            birim_fiyat_kdv_dahil_input = float(birim_fiyat_str) if birim_fiyat_str else 0.0

            iskonto_1_str = self.iskonto_yuzde_1_e.text().replace(',', '.')
            iskonto_yuzde_1 = float(iskonto_1_str) if iskonto_1_str else 0.0
            
            iskonto_2_str = self.iskonto_yuzde_2_e.text().replace(',', '.')
            iskonto_yuzde_2 = float(iskonto_2_str) if iskonto_2_str else 0.0

        except ValueError:
            QMessageBox.critical(self.app, "Giriş Hatası", "Miktar veya fiyat alanlarına geçerli sayısal değerler girin.")
            return

        if self.islem_tipi in [self.FATURA_TIP_SATIS, self.FATURA_TIP_ALIS_IADE]:
            mevcut_stok = urun_detaylari.get('miktar', 0.0)
            
            sepetteki_urun_miktari = sum(k[2] for k in self.fatura_kalemleri_ui if k[0] == urun_id)
            
            if self.duzenleme_id:
                original_fatura_kalemleri = self._get_original_invoice_items_from_db(self.duzenleme_id)
                for orig_kalem in original_fatura_kalemleri:
                    if orig_kalem['urun_id'] == urun_id:
                        mevcut_stok += orig_kalem['miktar']
                        break
            
            if (sepetteki_urun_miktari + eklenecek_miktar) > mevcut_stok:
                reply = QMessageBox.question(self.app, "Stok Uyarısı",
                                             f"'{urun_detaylari['ad']}' için stok yetersiz!\n"
                                             f"Mevcut stok: {mevcut_stok:.2f} adet\n"
                                             f"Sepete eklenecek toplam: {sepetteki_urun_miktari + eklenecek_miktar:.2f} adet\n\n"
                                             "Devam etmek negatif stok oluşturacaktır. Emin misiniz?",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No: return

        existing_kalem_index = -1
        for i, kalem in enumerate(self.fatura_kalemleri_ui):
            if kalem[0] == urun_id:
                existing_kalem_index = i
                break

        urun_tam_detay_db = self.db.stok_getir_by_id(urun_id)
        if not urun_tam_detay_db:
            QMessageBox.critical(self.app, "Hata", "Ürün detayları veritabanında bulunamadı. Kalem eklenemiyor.")
            return

        original_birim_fiyat_kdv_haric = urun_tam_detay_db.get('alis_fiyati_kdv_haric') if self.islem_tipi == self.FATURA_TIP_ALIS else urun_tam_detay_db.get('satis_fiyati_kdv_haric')
        kdv_orani = urun_tam_detay_db.get('kdv_orani')
        alis_fiyati_fatura_aninda = urun_tam_detay_db.get('alis_fiyati')

        self.kalem_guncelle(
            kalem_index=existing_kalem_index, 
            yeni_miktar=eklenecek_miktar, 
            yeni_fiyat_kdv_dahil_orijinal=birim_fiyat_kdv_dahil_input,
            yeni_iskonto_yuzde_1=iskonto_yuzde_1, 
            yeni_iskonto_yuzde_2=iskonto_yuzde_2, 
            yeni_alis_fiyati_fatura_aninda=alis_fiyati_fatura_aninda,
            u_id=urun_id, 
            urun_adi=urun_detaylari['ad'],
            kdv_orani=kdv_orani
        )
        self.mik_e.setText("1")
        self.birim_fiyat_e.setText("0,00")
        self.iskonto_yuzde_1_e.setText("0,00")
        self.iskonto_yuzde_2_e.setText("0,00")
        self.urun_arama_entry.clear()
        self.urun_arama_entry.setFocus()
    
    def kalem_guncelle(self, kalem_index, yeni_miktar, yeni_fiyat_kdv_dahil_orijinal, yeni_iskonto_yuzde_1, yeni_iskonto_yuzde_2, yeni_alis_fiyati_fatura_aninda, u_id=None, urun_adi=None, kdv_orani=None):
        if kalem_index is not None:
            item_to_update = list(self.fatura_kalemleri_ui[kalem_index])
            urun_id_current = item_to_update[0]
            kdv_orani_current = item_to_update[4]
        else:
            if u_id is None or urun_adi is None or kdv_orani is None:
                QMessageBox.critical(self.app, "Hata", "Yeni kalem eklenirken ürün bilgileri eksik.")
                return
            urun_id_current = u_id
            kdv_orani_current = kdv_orani
            
            item_to_update = [
                u_id, urun_adi, 0.0,
                0.0, kdv_orani_current,
                0.0, 0.0, 0.0,
                0.0, kdv_orani_current,
                0.0, 0.0,
                "YOK", 0.0,
                0.0
            ]

        item_to_update[2] = self.db.safe_float(yeni_miktar)
        item_to_update[10] = self.db.safe_float(yeni_iskonto_yuzde_1)
        item_to_update[11] = self.db.safe_float(yeni_iskonto_yuzde_2)
        item_to_update[8] = self.db.safe_float(yeni_alis_fiyati_fatura_aninda)

        if kdv_orani_current == 0:
            original_birim_fiyat_kdv_haric_calc = self.db.safe_float(yeni_fiyat_kdv_dahil_orijinal)
        else:
            original_birim_fiyat_kdv_haric_calc = self.db.safe_float(yeni_fiyat_kdv_dahil_orijinal) / (1 + self.db.safe_float(kdv_orani_current) / 100)
        item_to_update[3] = original_birim_fiyat_kdv_haric_calc

        fiyat_iskonto_1_sonrasi_dahil = self.db.safe_float(yeni_fiyat_kdv_dahil_orijinal) * (1 - self.db.safe_float(yeni_iskonto_yuzde_1) / 100)
        iskontolu_birim_fiyat_kdv_dahil = fiyat_iskonto_1_sonrasi_dahil * (1 - self.db.safe_float(yeni_iskonto_yuzde_2) / 100)
        
        if iskontolu_birim_fiyat_kdv_dahil < 0: iskontolu_birim_fiyat_kdv_dahil = 0.0
        item_to_update[14] = iskontolu_birim_fiyat_kdv_dahil

        iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil / (1 + self.db.safe_float(kdv_orani_current) / 100) if self.db.safe_float(kdv_orani_current) != 0 else iskontolu_birim_fiyat_kdv_dahil

        item_to_update[5] = (iskontolu_birim_fiyat_kdv_dahil - iskontolu_birim_fiyat_kdv_haric) * self.db.safe_float(yeni_miktar)
        item_to_update[6] = iskontolu_birim_fiyat_kdv_haric * self.db.safe_float(yeni_miktar)
        item_to_update[7] = iskontolu_birim_fiyat_kdv_dahil * self.db.safe_float(yeni_miktar)

        if kalem_index is not None:
            self.fatura_kalemleri_ui[kalem_index] = tuple(item_to_update)
        else:
            self.fatura_kalemleri_ui.append(tuple(item_to_update))

        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()

    def sepeti_guncelle_ui(self):
        if not hasattr(self, 'sep_tree'): return
        self.sep_tree.clear()

        for i, k in enumerate(self.fatura_kalemleri_ui):
            miktar_f = self.db.safe_float(k[2])
            birim_fiyat_gosterim_f = self.db.safe_float(k[14])
            original_bf_haric_f = self.db.safe_float(k[3])
            kdv_orani_f = self.db.safe_float(k[4])
            iskonto_yuzde_1_f = self.db.safe_float(k[10])
            iskonto_yuzde_2_f = self.db.safe_float(k[11])
            kalem_toplam_dahil_f = self.db.safe_float(k[7])
            
            miktar_gosterim = f"{miktar_f:.2f}".rstrip('0').rstrip('.')
            original_bf_dahil = original_bf_haric_f * (1 + kdv_orani_f / 100)
            uygulanan_iskonto = (original_bf_dahil - birim_fiyat_gosterim_f) * miktar_f

            item_qt = QTreeWidgetItem(self.sep_tree)
            item_qt.setText(0, str(i + 1))
            item_qt.setText(1, k[1])
            item_qt.setText(2, miktar_gosterim)
            item_qt.setText(3, self.db._format_currency(birim_fiyat_gosterim_f))
            item_qt.setText(4, f"%{kdv_orani_f:.0f}")
            item_qt.setText(5, f"{iskonto_yuzde_1_f:.2f}".replace('.',','))
            item_qt.setText(6, f"{iskonto_yuzde_2_f:.2f}".replace('.',','))
            item_qt.setText(7, self.db._format_currency(uygulanan_iskonto))
            item_qt.setText(8, self.db._format_currency(kalem_toplam_dahil_f))
            item_qt.setText(9, "Geçmişi Gör")
            item_qt.setText(10, str(k[0]))

            item_qt.setData(2, Qt.UserRole, miktar_f)
            item_qt.setData(3, Qt.UserRole, birim_fiyat_gosterim_f)
            item_qt.setData(4, Qt.UserRole, kdv_orani_f)
            item_qt.setData(5, Qt.UserRole, iskonto_yuzde_1_f)
            item_qt.setData(6, Qt.UserRole, iskonto_yuzde_2_f)
            item_qt.setData(7, Qt.UserRole, uygulanan_iskonto)
            item_qt.setData(8, Qt.UserRole, kalem_toplam_dahil_f)
            item_qt.setData(10, Qt.UserRole, k[0])

        self.toplamlari_hesapla_ui()

    def toplamlari_hesapla_ui(self):
        if not hasattr(self, 'tkh_l'): return

        toplam_kdv_haric_kalemler = sum(self.db.safe_float(k[6]) for k in self.fatura_kalemleri_ui)
        toplam_kdv_dahil_kalemler = sum(self.db.safe_float(k[7]) for k in self.fatura_kalemleri_ui)
        toplam_kdv_kalemler = sum(self.db.safe_float(k[5]) for k in self.fatura_kalemleri_ui)

        genel_iskonto_tipi = self.genel_iskonto_tipi_cb.currentText()
        genel_iskonto_degeri_str = self.genel_iskonto_degeri_e.text()
        genel_iskonto_degeri = self.db.safe_float(genel_iskonto_degeri_str) if self.genel_iskonto_degeri_e.isEnabled() else 0.0
        
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
        selected_items = self.sep_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir kalem seçin.")
            return
            
        selected_item_qt = selected_items[0]
        kalem_index_str = selected_item_qt.text(0)
        try:
            kalem_index = int(kalem_index_str) - 1
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

    def _open_sepet_context_menu(self, pos):
        item = self.sep_tree.itemAt(pos)
        if not item: return

        self.sep_tree.setCurrentItem(item)

        context_menu = QMenu(self)

        edit_action = context_menu.addAction("Kalemi Düzenle")
        edit_action.triggered.connect(lambda: self._kalem_duzenle_penceresi_ac(item, None))

        delete_action = context_menu.addAction("Seçili Kalemi Sil")
        delete_action.triggered.connect(self.secili_kalemi_sil)

        history_action = context_menu.addAction("Fiyat Geçmişi")
        history_action.triggered.connect(lambda: self._on_sepet_kalem_click(item, 9))
        
        urun_karti_action = context_menu.addAction("Ürün Kartını Aç")
        urun_karti_action.triggered.connect(lambda: self._open_urun_karti_from_sep_item(item, None))

        context_menu.exec(self.sep_tree.mapToGlobal(pos))

    def _kalem_duzenle_penceresi_ac(self, item, column):
        kalem_index_str = item.text(0)
        try: kalem_index = int(kalem_index_str) - 1
        except ValueError:
            QMessageBox.critical(self.app, "Hata", "Seçili kalemin indeksi okunamadı."); return

        kalem_verisi = self.fatura_kalemleri_ui[kalem_index]
        from pencereler import KalemDuzenlePenceresi
        dialog = KalemDuzenlePenceresi(self, self.db, kalem_index, kalem_verisi, self.islem_tipi, self.duzenleme_id)
        dialog.exec()

    def _on_sepet_kalem_click(self, item, column):
        header_text = self.sep_tree.headerItem().text(column)
        if header_text == "Fiyat Geçmişi":
            urun_id_str = item.text(10)
            kalem_index_str = item.text(0)
            try:
                urun_id = int(urun_id_str)
                kalem_index = int(kalem_index_str) - 1
            except ValueError:
                QMessageBox.critical(self.app, "Hata", "Ürün ID veya kalem indeksi okunamadı."); return

            if not self.secili_cari_id:
                QMessageBox.warning(self.app, "Uyarı", "Fiyat geçmişini görmek için lütfen önce bir cari seçin."); return
            
            from pencereler import FiyatGecmisiPenceresi
            dialog = FiyatGecmisiPenceresi(self.app, self.db, self.secili_cari_id, urun_id, self.islem_tipi, self._update_sepet_kalem_from_history, kalem_index)
            dialog.exec()

    def _update_sepet_kalem_from_history(self, kalem_index, new_price_kdv_dahil, new_iskonto_1, new_iskonto_2):
        if not (0 <= kalem_index < len(self.fatura_kalemleri_ui)): return
        
        current_kalem_data = list(self.fatura_kalemleri_ui[kalem_index])
        
        urun_id = current_kalem_data[0]
        urun_adi = current_kalem_data[1]
        miktar = current_kalem_data[2]
        kdv_orani = current_kalem_data[4]
        alis_fiyati_fatura_aninda = current_kalem_data[8]

        self.kalem_guncelle(kalem_index=kalem_index, yeni_miktar=miktar, yeni_fiyat_kdv_dahil_orijinal=new_price_kdv_dahil, yeni_iskonto_yuzde_1=new_iskonto_1, yeni_iskonto_yuzde_2=new_iskonto_2, yeni_alis_fiyati_fatura_aninda=alis_fiyati_fatura_aninda, u_id=urun_id, urun_adi=urun_adi, kdv_orani=kdv_orani)


    def _get_urun_adi_by_id(self, urun_id):
        for urun in self.tum_urunler_cache:
            if urun.get('id') == urun_id:
                return urun.get('ad')
        return "Bilinmeyen Ürün"

    def _get_urun_full_details_by_id(self, urun_id):
        for urun in self.tum_urunler_cache:
            if urun.get('id') == urun_id:
                return urun
        return None

    def _get_original_invoice_items_from_db(self, fatura_id):
        try:
            return self.db.fatura_kalemleri_al(fatura_id)
        except Exception as e:
            logging.error(f"Orijinal fatura kalemleri çekilirken hata: {e}", exc_info=True)
            return []
        
    def _open_urun_karti_from_sep_item(self, item, column):
        urun_id_str = item.text(10)
        try: urun_id = int(urun_id_str)
        except ValueError: QMessageBox.critical(self.app, "Hata", "Ürün ID okunamadı."); return
        
        try:
            urun_detaylari = self.db.stok_getir_by_id(urun_id)
            if not urun_detaylari:
                QMessageBox.critical(self.app, "Hata", "Ürün detayları bulunamadı.")
                return
            from pencereler import StokKartiPenceresi
            dialog = StokKartiPenceresi(self.app, self.db, urun_duzenle=urun_detaylari, app_ref=self.app)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Ürün kartı açılamadı: {e}")
            logging.error(f"Ürün kartı açma hatası: {e}", exc_info=True)

    def _secili_kalemi_sil(self):
        selected_items = self.sep_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir kalem seçin.")
            return

        reply = QMessageBox.question(self.app, "Silme Onayı", "Seçili kalemi sepetten silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            item_qt = selected_items[0]
            kalem_sira_no = int(item_qt.text(0))
            kalem_index = kalem_sira_no - 1

            if 0 <= kalem_index < len(self.fatura_kalemleri_ui):
                del self.fatura_kalemleri_ui[kalem_index]
                self._sepeti_guncelle_ui()
                self.toplamlari_hesapla_ui()
                QMessageBox.information(self.app, "Başarılı", "Kalem sepetten silindi.")
            else:
                QMessageBox.critical(self.app, "Hata", "Geçersiz kalem seçimi.")

    def _sepeti_temizle(self):
        if not self.fatura_kalemleri_ui:
            return

        reply = QMessageBox.question(self.app, "Temizleme Onayı", "Tüm kalemleri sepetten silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.fatura_kalemleri_ui.clear()
            self._sepeti_guncelle_ui()
            self.toplamlari_hesapla_ui()
            QMessageBox.information(self.app, "Başarılı", "Sepet temizlendi.")

    def _sepeti_guncelle_ui(self):
        if not hasattr(self, 'sep_tree'):
            return

        self.sep_tree.clear()

        for i, k in enumerate(self.fatura_kalemleri_ui):
            miktar_f = self.db.safe_float(k[2])
            birim_fiyat_gosterim_f = self.db.safe_float(k[14])
            original_bf_haric_f = self.db.safe_float(k[3])
            kdv_orani_f = self.db.safe_float(k[4])
            iskonto_yuzde_1_f = self.db.safe_float(k[10])
            iskonto_yuzde_2_f = self.db.safe_float(k[11])
            kalem_toplam_dahil_f = self.db.safe_float(k[7])
            
            miktar_gosterim = f"{miktar_f:.2f}".rstrip('0').rstrip('.')
            original_bf_dahil = original_bf_haric_f * (1 + kdv_orani_f / 100)
            uygulanan_iskonto = (original_bf_dahil - birim_fiyat_gosterim_f) * miktar_f

            item_qt = QTreeWidgetItem(self.sep_tree)
            item_qt.setText(0, str(i + 1))
            item_qt.setText(1, k[1])
            item_qt.setText(2, miktar_gosterim)
            item_qt.setText(3, self.db._format_currency(birim_fiyat_gosterim_f))
            item_qt.setText(4, f"%{kdv_orani_f:.0f}")
            item_qt.setText(5, f"{iskonto_yuzde_1_f:.2f}".replace('.',','))
            item_qt.setText(6, f"{iskonto_yuzde_2_f:.2f}".replace('.',','))
            item_qt.setText(7, self.db._format_currency(uygulanan_iskonto))
            item_qt.setText(8, self.db._format_currency(kalem_toplam_dahil_f))
            item_qt.setText(9, "Geçmişi Gör")
            item_qt.setText(10, str(k[0]))

            item_qt.setData(2, Qt.UserRole, miktar_f)
            item_qt.setData(3, Qt.UserRole, birim_fiyat_gosterim_f)
            item_qt.setData(4, Qt.UserRole, kdv_orani_f)
            item_qt.setData(5, Qt.UserRole, iskonto_yuzde_1_f)
            item_qt.setData(6, Qt.UserRole, iskonto_yuzde_2_f)
            item_qt.setData(7, Qt.UserRole, uygulanan_iskonto)
            item_qt.setData(8, Qt.UserRole, kalem_toplam_dahil_f)
            item_qt.setData(10, Qt.UserRole, k[0])

        self.toplamlari_hesapla_ui()

    def _format_numeric_line_edit(self, line_edit: QLineEdit, decimals: int):
        text = line_edit.text()
        if not text: return

        if '.' in text and ',' not in text:
            cursor_pos = line_edit.cursorPosition()
            line_edit.setText(text.replace('.', ','))
            line_edit.setCursorPosition(cursor_pos)
            text = line_edit.text()

        try:
            value = float(text.replace(',', '.'))
        except ValueError:
            pass

    def _kaydet_fatura(self):
        fatura_no = self.f_no_e.text().strip()
        fatura_tarihi = self.fatura_tarihi_entry.text().strip()
        odeme_turu = self.odeme_turu_cb.currentText()
        vade_tarihi = self.entry_vade_tarihi.text().strip() if self.entry_vade_tarihi.isVisible() else None
        fatura_notlari = self.fatura_notlari_text.toPlainText().strip()
        genel_iskonto_tipi = self.genel_iskonto_tipi_cb.currentText()
        genel_iskonto_degeri = float(self.genel_iskonto_degeri_e.text().replace(',', '.')) if self.genel_iskonto_degeri_e.isEnabled() else 0.0
        misafir_adi = self.entry_misafir_adi.text().strip() if self.misafir_adi_container_frame.isVisible() else None

        kasa_banka_id = None
        if self.islem_hesap_cb.isEnabled() and self.islem_hesap_cb.currentData():
            kasa_banka_id = self.islem_hesap_cb.currentData()

        if not fatura_no: QMessageBox.critical(self, "Eksik Bilgi", "Fatura Numarası boş olamaz."); return
        try: datetime.strptime(fatura_tarihi, '%Y-%m-%d')
        except ValueError: QMessageBox.critical(self, "Hata", "Fatura Tarihi formatı (YYYY-AA-GG) olmalıdır."); return

        if not self.secili_cari_id and not misafir_adi: QMessageBox.critical(self, "Eksik Bilgi", "Lütfen bir cari seçin veya Misafir Adı girin."); return
        if self.secili_cari_id == self.perakende_musteri_id and misafir_adi == "": QMessageBox.critical(self, "Eksik Bilgi", "Perakende satışlar için Misafir Adı boş bırakılamaz."); return

        if odeme_turu == self.ODEME_TURU_ACIK_HESAP and not vade_tarihi: QMessageBox.critical(self, "Eksik Bilgi", "Açık Hesap için Vade Tarihi zorunludur."); return
        if vade_tarihi:
            try: datetime.strptime(vade_tarihi, '%Y-%m-%d')
            except ValueError: QMessageBox.critical(self, "Hata", "Vade Tarihi formatı (YYYY-AA-GG) olmalıdır."); return

        if odeme_turu in self.pesin_odeme_turleri and kasa_banka_id is None: QMessageBox.critical(self, "Eksik Bilgi", "Peşin ödeme türleri için Kasa/Banka seçimi zorunludur."); return
        if not self.fatura_kalemleri_ui: QMessageBox.critical(self, "Eksik Bilgi", "Faturada en az bir kalem olmalıdır."); return

        kalemler_to_send_to_api = []
        for k_ui in self.fatura_kalemleri_ui:
            kalemler_to_send_to_api.append({
                "urun_id": k_ui[0], "miktar": self.db.safe_float(k_ui[2]), "birim_fiyat": self.db.safe_float(k_ui[3]),
                "kdv_orani": self.db.safe_float(k_ui[4]), "alis_fiyati_fatura_aninda": self.db.safe_float(k_ui[8]),
                "iskonto_yuzde_1": self.db.safe_float(k_ui[10]), "iskonto_yuzde_2": self.db.safe_float(k_ui[11]),
                "iskonto_tipi": k_ui[12], "iskonto_degeri": self.db.safe_float(k_ui[13])
            })
        
        fatura_data = {
            "fatura_no": fatura_no, "tarih": fatura_tarihi, "fatura_turu": self.islem_tipi,
            "cari_id": self.secili_cari_id, "odeme_turu": odeme_turu, "kalemler": kalemler_to_send_to_api,
            "kasa_banka_id": kasa_banka_id, "misafir_adi": misafir_adi, "fatura_notlari": fatura_notlari,
            "vade_tarihi": vade_tarihi, "genel_iskonto_tipi": genel_iskonto_tipi,
            "genel_iskonto_degeri": genel_iskonto_degeri,
            "original_fatura_id": self.iade_modu_aktif and self.original_fatura_id_for_iade or None # Simplified condition
        }

        try:
            if self.duzenleme_id: response = self.db.fatura_guncelle(self.duzenleme_id, fatura_data)
            else: response = self.db.fatura_ekle(fatura_data)
            
            QMessageBox.information(self, "Başarılı", "Fatura başarıyla kaydedildi!")
            
            if self.yenile_callback: self.yenile_callback()
            
            if not self.duzenleme_id: self.accept()
            else: self._reset_form_for_new_invoice()
            
        except Exception as e:
            error_detail = str(e)
            QMessageBox.critical(self, "Hata", f"Fatura kaydedilirken bir hata oluştu:\n{error_detail}")
            logging.error(f"Fatura kaydetme hatası: {e}", exc_info=True)

    def _yukle_kasa_banka_hesaplarini(self):
        self.islem_hesap_cb.clear()
        self.kasa_banka_map.clear()
        
        try:
            hesaplar_response = self.db.kasa_banka_listesi_al()
            # API'den gelen yanıtın dict içinde 'items' anahtarı olup olmadığını kontrol et
            if isinstance(hesaplar_response, dict) and "items" in hesaplar_response:
                hesaplar = hesaplar_response["items"]
            elif isinstance(hesaplar_response, list): # Eğer API doğrudan liste dönüyorsa
                hesaplar = hesaplar_response
                self.app.set_status_message("Uyarı: Kasa/Banka listesi API yanıtı beklenen formatta değil. Doğrudan liste olarak işleniyor.", "orange")
            else: # Beklenmeyen bir format gelirse
                hesaplar = []
                self.app.set_status_message("Hata: Kasa/Banka listesi API'den alınamadı veya formatı geçersiz.", "red")
                logging.error(f"Kasa/Banka listesi API'den beklenen formatta gelmedi: {type(hesaplar_response)} - {hesaplar_response}")
                # Hata durumunda fonksiyonu sonlandır
                self.islem_hesap_cb.addItem("Hesap Yok", None)
                self.islem_hesap_cb.setEnabled(False)
                return


            if hesaplar:
                for h in hesaplar:
                    display_text = f"{h.get('hesap_adi')} ({h.get('tip')})"
                    if h.get('tip') == "BANKA" and h.get('banka_adi'):
                        display_text += f" - {h.get('banka_adi')}"
                    self.kasa_banka_map[display_text] = h.get('id')
                    self.islem_hesap_cb.addItem(display_text, h.get('id'))
                self.islem_hesap_cb.setCurrentIndex(0)
                self.islem_hesap_cb.setEnabled(True)
            else:
                self.islem_hesap_cb.clear()
                self.islem_hesap_cb.addItem("Hesap Yok", None)
                self.islem_hesap_cb.setEnabled(False)

            self.app.set_status_message(f"{len(hesaplar)} kasa/banka hesabı API'den yüklendi.")

        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Kasa/Banka hesapları çekilirken hata: {e}")
            logging.error(f"FaturaPenceresi Kasa/Banka yükleme hatası: {e}", exc_info=True)
            self.islem_hesap_cb.clear()
            self.islem_hesap_cb.addItem("Hesap Yok", None)
            self.islem_hesap_cb.setEnabled(False)

class FaturaDetayPenceresi(QDialog):
    def __init__(self, parent_app, db_manager, fatura_id):
        super().__init__(parent_app)
        self.db = db_manager
        self.app = parent_app
        self.fatura_id = fatura_id
        
        self.fatura_ana = None
        self.fatura_kalemleri_db = None

        # Fatura tip sabitlerini db_manager'dan veya API'den al
        # (FaturaPenceresi'ndeki sabitlerin aynısı)
        self.FATURA_TIP_ALIS = "ALIŞ"
        self.FATURA_TIP_SATIS = "SATIŞ"
        self.FATURA_TIP_DEVIR_GIRIS = "DEVİR_GİRİŞ"
        self.FATURA_TIP_SATIS_IADE = "SATIŞ İADE"
        self.FATURA_TIP_ALIS_IADE = "ALIŞ İADE"

        self.ODEME_TURU_NAKIT = "NAKİT"
        self.ODEME_TURU_KART = "KART"
        self.ODEME_TURU_EFT_HAVALE = "EFT/HAVALE"
        self.ODEME_TURU_CEK = "ÇEK"
        self.ODEME_TURU_SENET = "SENET"
        self.ODEME_TURU_ACIK_HESAP = "AÇIK HESAP"
        self.ODEME_TURU_ETKISIZ_FATURA = "ETKİSİZ FATURA"


        # Fetch fatura data immediately to check existence
        try:
            response = requests.get(f"{API_BASE_URL}/faturalar/{self.fatura_id}")
            response.raise_for_status()
            self.fatura_ana = response.json()

            response_kalemler = requests.get(f"{API_BASE_URL}/faturalar/{self.fatura_id}/kalemler") # Assuming this endpoint exists
            response_kalemler.raise_for_status()
            self.fatura_kalemleri_db = response_kalemler.json()

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self.app, "API Hatası", f"Fatura bilgileri çekilemedi: {e}")
            self.close() # Close dialog if data cannot be fetched
            return

        if not self.fatura_ana:
            QMessageBox.critical(self.app, "Fatura Bulunamadı", "Detayları görüntülenecek fatura bulunamadı.")
            self.close()
            return

        self.f_no = self.fatura_ana.get('fatura_no')
        self.tip = self.fatura_ana.get('tip')
        
        self.setWindowTitle(f"Fatura Detayları: {self.f_no} ({self.tip})")
        self.setWindowState(Qt.WindowMaximized)
        self.setModal(True)

        self.main_layout = QVBoxLayout(self) # Main layout for the dialog

        self._create_ui_and_populate_data() # Yeni metodu çağır

        # self.finished.connect(self.on_dialog_finished) # Bu pencere kapanınca özel bir şey yapmaya gerek yok şimdilik

    def _create_ui_and_populate_data(self):
        """
        Bu metod, faturaya ait tüm verileri API'den çeker ve
        arayüzü sıfırdan oluşturup doldurur.
        """
        # Mevcut layout'u temizle (eğer daha önce oluşturulduysa)
        if self.main_layout.layout():
            self.clear_layout(self.main_layout)

        tarih_db = self.fatura_ana.get('tarih')
        c_id = self.fatura_ana.get('cari_id')
        toplam_kdv_haric_fatura_ana_db = self.fatura_ana.get('toplam_kdv_haric')
        toplam_kdv_dahil_fatura_ana_db = self.fatura_ana.get('toplam_kdv_dahil')
        odeme_turu_db = self.fatura_ana.get('odeme_turu')
        misafir_adi_db = self.fatura_ana.get('misafir_adi')
        kasa_banka_id_db = self.fatura_ana.get('kasa_banka_id')
        olusturma_tarihi_saat = self.fatura_ana.get('olusturma_tarihi_saat')
        olusturan_kullanici_id = self.fatura_ana.get('olusturan_kullanici_id')
        son_guncelleme_tarihi_saat = self.fatura_ana.get('son_guncelleme_tarihi_saat')
        son_guncelleyen_kullanici_id = self.fatura_ana.get('son_guncelleyen_kullanici_id')
        fatura_notlari_db = self.fatura_ana.get('fatura_notlari')
        vade_tarihi_db = self.fatura_ana.get('vade_tarihi')
        genel_iskonto_tipi_db = self.fatura_ana.get('genel_iskonto_tipi')
        genel_iskonto_degeri_db = self.fatura_ana.get('genel_iskonto_degeri')

        # Kullanıcı bilgisi çek
        kullanicilar_map_response = requests.get(f"{API_BASE_URL}/nitelikler/kullanicilar") # Varsayılan endpoint
        kullanicilar_map = {k.get('id'): k.get('kullanici_adi') for k in kullanicilar_map_response.json()}

        olusturan_adi = kullanicilar_map.get(olusturan_kullanici_id, "Bilinmiyor")
        son_guncelleyen_adi = kullanicilar_map.get(son_guncelleyen_kullanici_id, "Bilinmiyor")

        cari_adi_text = "Bilinmiyor"
        if str(c_id) == str(self.db.perakende_musteri_id) and self.tip == self.FATURA_TIP_SATIS:
            cari_adi_text = "Perakende Satış Müşterisi"
            if misafir_adi_db: cari_adi_text += f" (Misafir: {misafir_adi_db})"
        else:
            cari_bilgi_db = None
            if self.tip in [self.FATURA_TIP_SATIS, self.FATURA_TIP_SATIS_IADE]:
                cari_bilgi_response = requests.get(f"{API_BASE_URL}/musteriler/{c_id}")
                cari_bilgi_response.raise_for_status()
                cari_bilgi_db = cari_bilgi_response.json()
                if cari_bilgi_db and cari_bilgi_db.get('kod'):
                    cari_adi_text = f"{cari_bilgi_db.get('ad')} (Kod: {cari_bilgi_db.get('kod')})"
            elif self.tip in [self.FATURA_TIP_ALIS, self.FATURA_TIP_ALIS_IADE]:
                cari_bilgi_response = requests.get(f"{API_BASE_URL}/tedarikciler/{c_id}")
                cari_bilgi_response.raise_for_status()
                cari_bilgi_db = cari_bilgi_response.json()
                if cari_bilgi_db and cari_bilgi_db.get('tedarikci_kodu'):
                    cari_adi_text = f"{cari_bilgi_db.get('ad')} (Kod: {cari_bilgi_db.get('tedarikci_kodu')})"
        
        self.ust_frame = QGroupBox(f"Fatura Genel Bilgileri: {self.f_no}", self)
        self.ust_frame_layout = QGridLayout(self.ust_frame)
        self.main_layout.addWidget(self.ust_frame)
        
        # Sütun streç ayarları
        self.ust_frame_layout.setColumnStretch(1, 1)
        self.ust_frame_layout.setColumnStretch(3, 1)
        
        row_idx = 0
        self.ust_frame_layout.addWidget(QLabel("Fatura No:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0, Qt.AlignLeft)
        self.ust_frame_layout.addWidget(QLabel(self.f_no, font=QFont("Segoe UI", 9)), row_idx, 1, Qt.AlignLeft)
        try: fatura_tarihi_formatted = datetime.strptime(str(tarih_db), '%Y-%m-%d').strftime('%d.%m.%Y')
        except: fatura_tarihi_formatted = str(tarih_db)
        self.ust_frame_layout.addWidget(QLabel("Tarih:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 2, Qt.AlignLeft)
        self.ust_frame_layout.addWidget(QLabel(fatura_tarihi_formatted, font=QFont("Segoe UI", 9)), row_idx, 3, Qt.AlignLeft)
        row_idx += 1
        self.ust_frame_layout.addWidget(QLabel("Fatura Tipi:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0, Qt.AlignLeft)
        self.ust_frame_layout.addWidget(QLabel(self.tip, font=QFont("Segoe UI", 9)), row_idx, 1, Qt.AlignLeft)
        self.ust_frame_layout.addWidget(QLabel("Ödeme Türü:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 2, Qt.AlignLeft)
        self.ust_frame_layout.addWidget(QLabel(odeme_turu_db or "-", font=QFont("Segoe UI", 9)), row_idx, 3, Qt.AlignLeft)
        row_idx += 1
        cari_label_tipi = "Müşteri/Misafir:" if self.tip == self.FATURA_TIP_SATIS else "Tedarikçi:"
        self.ust_frame_layout.addWidget(QLabel(cari_label_tipi, font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0, Qt.AlignLeft)
        self.ust_frame_layout.addWidget(QLabel(cari_adi_text, font=QFont("Segoe UI", 9)), row_idx, 1, 1, 3, Qt.AlignLeft) # columnspan 3
        row_idx += 1
        if kasa_banka_id_db:
            try:
                kb_response = requests.get(f"{API_BASE_URL}/kasalar_bankalar/{kasa_banka_id_db}")
                kb_response.raise_for_status()
                kb_bilgi = kb_response.json()
                self.ust_frame_layout.addWidget(QLabel("Kasa/Banka:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0, Qt.AlignLeft)
                self.ust_frame_layout.addWidget(QLabel(kb_bilgi.get('hesap_adi', '-'), font=QFont("Segoe UI", 9)), row_idx, 1, Qt.AlignLeft)
                row_idx += 1
            except requests.exceptions.RequestException as e:
                logging.error(f"Kasa/Banka bilgisi çekilirken hata: {e}")
        if odeme_turu_db == self.ODEME_TURU_ACIK_HESAP and vade_tarihi_db:
            self.ust_frame_layout.addWidget(QLabel("Vade Tarihi:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0, Qt.AlignLeft)
            self.ust_frame_layout.addWidget(QLabel(str(vade_tarihi_db), font=QFont("Segoe UI", 9)), row_idx, 1, Qt.AlignLeft)
            row_idx += 1
        genel_iskonto_gosterim_text = "Uygulanmadı"
        if genel_iskonto_tipi_db == 'YUZDE' and genel_iskonto_degeri_db is not None and genel_iskonto_degeri_db > 0:
            genel_iskonto_gosterim_text = f"Yüzde %{genel_iskonto_degeri_db:.2f}".replace('.', ',').rstrip('0').rstrip(',')
        elif genel_iskonto_tipi_db == 'TUTAR' and genel_iskonto_degeri_db is not None and genel_iskonto_degeri_db > 0:
            genel_iskonto_gosterim_text = self.db._format_currency(genel_iskonto_degeri_db)
        self.ust_frame_layout.addWidget(QLabel("Genel İskonto:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0, Qt.AlignLeft)
        self.ust_frame_layout.addWidget(QLabel(genel_iskonto_gosterim_text, font=QFont("Segoe UI", 9)), row_idx, 1, 1, 3, Qt.AlignLeft)
        row_idx += 1
        # Düzeltilen Satır: `italic=True` parametresi kullanıldı.
        self.ust_frame_layout.addWidget(QLabel("Oluşturulma:", font=QFont("Segoe UI", 8, QFont.Normal, italic=True)), row_idx, 0, Qt.AlignLeft) 
        self.ust_frame_layout.addWidget(QLabel(f"{olusturma_tarihi_saat or '-'} ({olusturan_adi})", font=QFont("Segoe UI", 8, QFont.Normal, italic=True)), row_idx, 1, 1, 3, Qt.AlignLeft) # Düzeltildi
        row_idx += 1
        if son_guncelleme_tarihi_saat:
            # Düzeltilen Satır: `italic=True` parametresi kullanıldı.
            self.ust_frame_layout.addWidget(QLabel("Son Güncelleme:", font=QFont("Segoe UI", 8, QFont.Normal, italic=True)), row_idx, 0, Qt.AlignLeft)
            self.ust_frame_layout.addWidget(QLabel(f"{son_guncelleme_tarihi_saat} ({son_guncelleyen_adi})", font=QFont("Segoe UI", 8, QFont.Normal, italic=True)), row_idx, 1, 1, 3, Qt.AlignLeft) # Düzeltildi
            row_idx += 1
        self.ust_frame_layout.addWidget(QLabel("Fatura Notları:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0, Qt.AlignTop | Qt.AlignLeft)
        fatura_notlari_display_widget = QTextEdit()
        fatura_notlari_display_widget.setPlainText(fatura_notlari_db or "-")
        fatura_notlari_display_widget.setReadOnly(True)
        fatura_notlari_display_widget.setFixedHeight(50)
        self.ust_frame_layout.addWidget(fatura_notlari_display_widget, row_idx, 1, 1, 3, Qt.AlignLeft) # columnspan 3
        
        kalemler_frame = QGroupBox("Fatura Kalemleri", self)
        kalemler_frame_layout = QVBoxLayout(kalemler_frame)
        self.main_layout.addWidget(kalemler_frame)
        cols_kalem = ("Sıra", "Ürün Kodu", "Ürün Adı", "Miktar", "Birim Fiyat", "KDV %", "İskonto 1 (%)", "İskonto 2 (%)", "Uyg. İsk. Tutarı", "Tutar (Dah.)", "Alış Fiyatı (Fatura Anı)")
        self.kalem_tree = QTreeWidget(kalemler_frame)
        self.kalem_tree.setHeaderLabels(cols_kalem)
        self.kalem_tree.setSelectionBehavior(QAbstractItemView.SelectRows) # Select entire row
        self.kalem_tree.setSortingEnabled(True) # Enable sorting

        from PySide6.QtWidgets import QHeaderView # Added for QHeaderView
        col_defs_kalem = [
            ("Sıra", 40, Qt.AlignCenter), ("Ürün Kodu", 90, Qt.AlignLeft), ("Ürün Adı", 180, Qt.AlignLeft), 
            ("Miktar", 60, Qt.AlignRight), ("Birim Fiyat", 90, Qt.AlignRight), ("KDV %", 60, Qt.AlignRight), 
            ("İskonto 1 (%)", 75, Qt.AlignRight), ("İskonto 2 (%)", 75, Qt.AlignRight), 
            ("Uyg. İsk. Tutarı", 100, Qt.AlignRight), ("Tutar (Dah.)", 110, Qt.AlignRight), 
            ("Alış Fiyatı (Fatura Anı)", 120, Qt.AlignRight)
        ]
        for i, (col_name, width, alignment) in enumerate(col_defs_kalem): 
            self.kalem_tree.setColumnWidth(i, width)
            self.kalem_tree.headerItem().setTextAlignment(i, alignment)
            self.kalem_tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
        self.kalem_tree.header().setStretchLastSection(False) 
        self.kalem_tree.header().setSectionResizeMode(2, QHeaderView.Stretch) # Ürün Adı genişlesin

        kalemler_frame_layout.addWidget(self.kalem_tree)
        self._load_fatura_kalemleri_to_treeview(self.fatura_kalemleri_db) # API'den çekilen kalemleri yükle

        alt_toplam_iskonto_frame = QFrame(self)
        alt_toplam_iskonto_frame_layout = QGridLayout(alt_toplam_iskonto_frame)
        self.main_layout.addWidget(alt_toplam_iskonto_frame)

        toplam_kdv_hesaplanan_detay = toplam_kdv_dahil_fatura_ana_db - toplam_kdv_haric_fatura_ana_db
        # Kalemler zaten API'den geldiği için buradaki hesaplamayı kullanabiliriz
        toplam_kdv_dahil_kalemler_genel_iskonto_oncesi = sum(k.get('kalem_toplam_kdv_dahil',0) for k in self.fatura_kalemleri_db) # db'den gelen fatura kalemleri
        gercek_uygulanan_genel_iskonto = toplam_kdv_dahil_kalemler_genel_iskonto_oncesi - toplam_kdv_dahil_fatura_ana_db
        
        self.tkh_l = QLabel(f"Toplam KDV Hariç: {self.db._format_currency(toplam_kdv_haric_fatura_ana_db)}", font=QFont("Segoe UI", 9, QFont.Bold))
        alt_toplam_iskonto_frame_layout.addWidget(self.tkh_l, 0, 1, Qt.AlignRight)
        
        self.tkdv_l = QLabel(f"Toplam KDV: {self.db._format_currency(toplam_kdv_hesaplanan_detay)}", font=QFont("Segoe UI", 9, QFont.Bold))
        alt_toplam_iskonto_frame_layout.addWidget(self.tkdv_l, 1, 1, Qt.AlignRight)
        
        self.gt_l = QLabel(f"Genel Toplam: {self.db._format_currency(toplam_kdv_dahil_fatura_ana_db)}", font=QFont("Segoe UI", 10, QFont.Bold))
        alt_toplam_iskonto_frame_layout.addWidget(self.gt_l, 2, 1, Qt.AlignRight)
        
        self.lbl_uygulanan_genel_iskonto = QLabel(f"Uygulanan Genel İskonto: {self.db._format_currency(gercek_uygulanan_genel_iskonto if gercek_uygulanan_genel_iskonto > 0 else 0.0)}", font=QFont("Segoe UI", 9, QFont.Bold))
        alt_toplam_iskonto_frame_layout.addWidget(self.lbl_uygulanan_genel_iskonto, 3, 1, Qt.AlignRight)
        
        alt_toplam_iskonto_frame_layout.setColumnStretch(0, 1) # Sol tarafı esnet

        self._butonlari_olustur()

    def _butonlari_olustur(self):
        button_frame_alt = QFrame(self)
        button_layout_alt = QHBoxLayout(button_frame_alt)
        self.main_layout.addWidget(button_frame_alt)

        btn_guncelle = QPushButton("Güncelle")
        btn_guncelle.clicked.connect(self._open_fatura_guncelleme_penceresi)
        button_layout_alt.addWidget(btn_guncelle)
        
        btn_pdf_yazdir = QPushButton("PDF Yazdır")
        btn_pdf_yazdir.clicked.connect(self._handle_pdf_print)
        button_layout_alt.addWidget(btn_pdf_yazdir)

        button_layout_alt.addStretch() # Sağ tarafa yasla
        
        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.close)
        button_layout_alt.addWidget(btn_kapat)

    def _handle_pdf_print(self):
        """Fatura detay penceresinden PDF yazdırma işlemini başlatır."""
        dosya_adi_onek = f"{self.tip.capitalize()}Faturasi"
        file_path, _ = QFileDialog.getSaveFileName(self, f"{self.tip.capitalize()} Faturasını PDF Kaydet", 
                                                 f"{dosya_adi_onek}_{self.f_no.replace('/','_')}.pdf", 
                                                 "PDF Dosyaları (*.pdf);;Tüm Dosyalar (*)")
        if file_path:
            from pencereler import BeklemePenceresi # PySide6 BeklemePenceresi
            bekleme_penceresi = BeklemePenceresi(self, message="Fatura PDF'e aktarılıyor, lütfen bekleyiniz...")
            QTimer.singleShot(0, bekleme_penceresi.exec) # Modalı olarak göster

            # PDF oluşturma işlemini ayrı bir thread'de veya process'te yap
            # multiprocessing.Process kullanmak PySide6 UI'sını dondurmayı engeller
            result_queue = multiprocessing.Queue()
            pdf_process = multiprocessing.Process(target=self.db.fatura_pdf_olustur, args=(self.fatura_id, file_path, result_queue))
            pdf_process.start()

            # Process tamamlandığında sonucu kontrol etmek için QTimer kullan
            self.pdf_check_timer = QTimer(self)
            self.pdf_check_timer.timeout.connect(lambda: self._check_pdf_process_completion(result_queue, pdf_process, bekleme_penceresi))
            self.pdf_check_timer.start(100) # Her 100ms'de bir kontrol et
        else:
            self.app.set_status_message("PDF kaydetme iptal edildi.")

    def _check_pdf_process_completion(self, result_queue, pdf_process, bekleme_penceresi):
        if not result_queue.empty():
            success, message = result_queue.get()
            bekleme_penceresi.close()
            self.pdf_check_timer.stop()

            if success:
                QMessageBox.information(self, "Başarılı", message)
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self, "Hata", message)
                self.app.set_status_message(f"PDF kaydetme başarısız: {message}")
            pdf_process.join() # Sürecin tamamen kapanmasını bekle
            
        elif not pdf_process.is_alive():
            # Process beklenmedik şekilde bitti veya queue'ya bir şey koymadı
            bekleme_penceresi.close()
            self.pdf_check_timer.stop()
            QMessageBox.critical(self, "Hata", "PDF işlemi beklenmedik şekilde sonlandı.")
            pdf_process.join()


    def _open_fatura_guncelleme_penceresi(self):
        """Faturayı güncellemek için FaturaGuncellemePenceresi'ni açar."""
        from pencereler import FaturaGuncellemePenceresi
        dialog = FaturaGuncellemePenceresi(
            self.app, # parent olarak App objesi veriliyor
            self.db,
            self.fatura_id, # Güncellenecek faturanın ID'si
            yenile_callback_liste=self._fatura_guncellendi_callback_detay # Güncelleme sonrası bu pencereyi yenileyecek callback
        )
        dialog.exec()

    def _fatura_guncellendi_callback_detay(self):
        """Güncelleme sonrası FaturaDetay penceresindeki bilgileri yeniler."""
        # API'den faturanın en güncel halini tekrar çek
        try:
            response = requests.get(f"{API_BASE_URL}/faturalar/{self.fatura_id}")
            response.raise_for_status()
            self.fatura_ana = response.json()

            response_kalemler = requests.get(f"{API_BASE_URL}/faturalar/{self.fatura_id}/kalemler")
            response_kalemler.raise_for_status()
            self.fatura_kalemleri_db = response_kalemler.json()
            
            # Arayüzü yeniden oluştur ve doldur
            self._create_ui_and_populate_data()
            self.app.set_status_message(f"Fatura '{self.f_no}' detayları güncellendi.")

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self.app, "API Hatası", f"Fatura detayları yenilenirken hata: {e}")
            logging.error(f"Fatura detay yenileme hatası: {e}", exc_info=True)
            self.close() # Hata durumunda pencereyi kapat
            return
        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Fatura detayları yenilenirken beklenmeyen bir hata oluştu: {e}")
            logging.error(f"Fatura detay yenileme beklenmeyen hata: {e}", exc_info=True)
            self.close() # Hata durumunda pencereyi kapat
            return
                
        # Ana fatura listesini de yenile (her ihtimale karşı)
        if hasattr(self.app, 'fatura_listesi_sayfasi'):
            if hasattr(self.app.fatura_listesi_sayfasi, 'satis_fatura_frame') and hasattr(self.app.fatura_listesi_sayfasi.satis_fatura_frame, 'fatura_listesini_yukle'):
                self.app.fatura_listesi_sayfasi.satis_fatura_frame.fatura_listesini_yukle()
            if hasattr(self.app.fatura_listesi_sayfasi, 'alis_fatura_frame') and hasattr(self.app.fatura_listesi_sayfasi.alis_fatura_frame, 'fatura_listesini_yukle'):
                self.app.fatura_listesi_sayfasi.alis_fatura_frame.fatura_listesini_yukle()
                
    def _load_fatura_kalemleri_to_treeview(self, kalemler_list):
        self.kalem_tree.clear()

        sira_idx = 1
        for kalem_item in kalemler_list:
            miktar_db = kalem_item.get('miktar', 0.0)
            toplam_dahil_db = kalem_item.get('kalem_toplam_kdv_dahil', 0.0)
            original_birim_fiyat_kdv_haric_item = kalem_item.get('birim_fiyat', 0.0)
            original_kdv_orani_item = kalem_item.get('kdv_orani', 0.0)

            # İskontolu Birim Fiyat (KDV Dahil) Hesapla
            iskontolu_birim_fiyat_kdv_dahil = (toplam_dahil_db / miktar_db) if miktar_db != 0 else 0.0

            # Uygulanan Kalem İskonto Tutarı (KDV Dahil) Hesapla
            original_birim_fiyat_kdv_dahil_kalem = original_birim_fiyat_kdv_haric_item * (1 + original_kdv_orani_item / 100)
            uygulanan_kalem_iskonto_tutari = (original_birim_fiyat_kdv_dahil_kalem - iskontolu_birim_fiyat_kdv_dahil) * miktar_db

            item_qt = QTreeWidgetItem(self.kalem_tree)
            item_qt.setText(0, str(sira_idx))
            item_qt.setText(1, kalem_item.get('urun_kodu', ''))
            item_qt.setText(2, kalem_item.get('urun_adi', ''))
            item_qt.setText(3, f"{miktar_db:.2f}".rstrip('0').rstrip('.'))
            item_qt.setText(4, self.db._format_currency(iskontolu_birim_fiyat_kdv_dahil))
            item_qt.setText(5, f"%{kalem_item.get('kdv_orani', 0):.0f}")
            item_qt.setText(6, f"{kalem_item.get('iskonto_yuzde_1', 0):.2f}".replace('.', ',').rstrip('0').rstrip('.'))
            item_qt.setText(7, f"{kalem_item.get('iskonto_yuzde_2', 0):.2f}".replace('.', ',').rstrip('0').rstrip('.'))
            item_qt.setText(8, self.db._format_currency(uygulanan_kalem_iskonto_tutari))
            item_qt.setText(9, self.db._format_currency(toplam_dahil_db))
            item_qt.setText(10, self.db._format_currency(kalem_item.get('alis_fiyati_fatura_aninda', 0.0)))
            
            sira_idx += 1

    # clear_layout metodu, PySide6 için yardımcı
    def clear_layout(self, layout):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item is None: # takeAt(0) bazen None döndürebilir
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else: # Bu bir layout ise, içindeki widget'ları da temizle
                self.clear_layout(item.layout())

class SiparisDetayPenceresi(QDialog):
    def __init__(self, parent_app, db_manager, siparis_id, yenile_callback=None):
        super().__init__(parent_app)
        self.db = db_manager
        self.app = parent_app
        self.siparis_id = siparis_id
        self.yenile_callback = yenile_callback

        # Fetch siparis data immediately to check existence
        try:
            # API'den sipariş bilgilerini çek
            response = requests.get(f"{API_BASE_URL}/siparisler/{self.siparis_id}")
            response.raise_for_status()
            self.siparis_ana = response.json()

            # API'den sipariş kalemlerini çek
            response_kalemler = requests.get(f"{API_BASE_URL}/siparisler/{self.siparis_id}/kalemler") # Bu endpoint'in var olduğu varsayılıyor
            response_kalemler.raise_for_status()
            self.siparis_kalemleri_db = response_kalemler.json()

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self.app, "API Hatası", f"Sipariş bilgileri çekilemedi: {e}")
            self.close() # Close dialog if data cannot be fetched
            return

        if not self.siparis_ana:
            QMessageBox.critical(self.app, "Sipariş Bulunamadı", "Detayları görüntülenecek sipariş bulunamadı.")
            self.close()
            return

        self.s_no = self.siparis_ana.get('siparis_no')
        durum_db = self.siparis_ana.get('durum')
        
        self.setWindowTitle(f"Sipariş Detayları: {self.s_no} ({durum_db})")
        self.setWindowState(Qt.WindowMaximized) # Maximize on start
        self.setModal(True)

        self.main_layout = QVBoxLayout(self) # Main layout for the dialog

        self._create_ui_and_populate_data()

        self.finished.connect(self.on_dialog_finished)
        
    def _create_ui_and_populate_data(self):
        # Bu metod, faturaya ait tüm verileri API'den çeker ve
        # arayüzü sıfırdan oluşturup doldurur.
        
        # Sipariş Genel Bilgileri
        self.ust_frame = QGroupBox(f"Sipariş Genel Bilgileri: {self.s_no}", self)
        self.ust_frame_layout = QGridLayout(self.ust_frame)
        self.main_layout.addWidget(self.ust_frame)

        # Kullanıcı bilgileri
        kullanicilar_map_response = requests.get(f"{API_BASE_URL}/nitelikler/kullanicilar") # Varsayılan bir endpoint
        kullanicilar_map = {k.get('id'): k.get('kullanici_adi') for k in kullanicilar_map_response.json()}

        olusturan_adi = kullanicilar_map.get(self.siparis_ana.get('olusturan_kullanici_id'), "Bilinmiyor")
        son_guncelleyen_adi = kullanicilar_map.get(self.siparis_ana.get('son_guncelleyen_kullanici_id'), "Bilinmiyor")

        # Cari Bilgisi
        cari_adi_text = "Bilinmiyor"
        if self.siparis_ana.get('cari_tip') == 'MUSTERI':
            cari_bilgi_response = requests.get(f"{API_BASE_URL}/musteriler/{self.siparis_ana.get('cari_id')}")
            cari_bilgi = cari_bilgi_response.json()
            cari_adi_text = f"{cari_bilgi.get('ad')} (Kod: {cari_bilgi.get('kod')})" if cari_bilgi else "Bilinmiyor"
        elif self.siparis_ana.get('cari_tip') == 'TEDARIKCI':
            cari_bilgi_response = requests.get(f"{API_BASE_URL}/tedarikciler/{self.siparis_ana.get('cari_id')}")
            cari_bilgi = cari_bilgi_response.json()
            cari_adi_text = f"{cari_bilgi.get('ad')} (Kod: {cari_bilgi.get('tedarikci_kodu')})" if cari_bilgi else "Bilinmiyor"

        row_idx = 0
        self.ust_frame_layout.addWidget(QLabel("Sipariş No:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0)
        self.ust_frame_layout.addWidget(QLabel(self.s_no, font=QFont("Segoe UI", 9)), row_idx, 1)
        try: siparis_tarihi_formatted = datetime.strptime(self.siparis_ana.get('tarih'), '%Y-%m-%d').strftime('%d.%m.%Y')
        except: siparis_tarihi_formatted = self.siparis_ana.get('tarih')
        self.ust_frame_layout.addWidget(QLabel("Tarih:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 2)
        self.ust_frame_layout.addWidget(QLabel(siparis_tarihi_formatted, font=QFont("Segoe UI", 9)), row_idx, 3)
        row_idx += 1
        self.ust_frame_layout.addWidget(QLabel("Cari Tipi:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0)
        self.ust_frame_layout.addWidget(QLabel(self.siparis_ana.get('cari_tip'), font=QFont("Segoe UI", 9)), row_idx, 1)
        self.ust_frame_layout.addWidget(QLabel("Durum:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 2)
        self.ust_frame_layout.addWidget(QLabel(self.siparis_ana.get('durum'), font=QFont("Segoe UI", 9)), row_idx, 3)
        row_idx += 1
        self.ust_frame_layout.addWidget(QLabel("Cari Bilgisi:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0)
        self.ust_frame_layout.addWidget(QLabel(cari_adi_text, font=QFont("Segoe UI", 9)), row_idx, 1, 1, 3)
        row_idx += 1
        self.ust_frame_layout.addWidget(QLabel("Teslimat Tarihi:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0)
        try: teslimat_tarihi_formatted = datetime.strptime(self.siparis_ana.get('teslimat_tarihi'), '%Y-%m-%d').strftime('%d.%m.%Y')
        except: teslimat_tarihi_formatted = self.siparis_ana.get('teslimat_tarihi')
        self.ust_frame_layout.addWidget(QLabel(teslimat_tarihi_formatted if teslimat_tarihi_formatted else "-", font=QFont("Segoe UI", 9)), row_idx, 1)
        row_idx += 1
        genel_iskonto_gosterim_text = "Uygulanmadı"
        genel_iskonto_tipi_db = self.siparis_ana.get('genel_iskonto_tipi')
        genel_iskonto_degeri_db = self.siparis_ana.get('genel_iskonto_degeri')
        if genel_iskonto_tipi_db == 'YUZDE' and genel_iskonto_degeri_db is not None and genel_iskonto_degeri_db > 0:
            genel_iskonto_gosterim_text = f"Yüzde %{genel_iskonto_degeri_db:.2f}".replace('.', ',').rstrip('0').rstrip(',')
        elif genel_iskonto_tipi_db == 'TUTAR' and genel_iskonto_degeri_db is not None and genel_iskonto_degeri_db > 0:
            genel_iskonto_gosterim_text = self.db._format_currency(genel_iskonto_degeri_db)
        self.ust_frame_layout.addWidget(QLabel("Genel İskonto:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0)
        self.ust_frame_layout.addWidget(QLabel(genel_iskonto_gosterim_text, font=QFont("Segoe UI", 9)), row_idx, 1, 1, 3)
        row_idx += 1
        self.ust_frame_layout.addWidget(QLabel("Oluşturulma:", font=QFont("Segoe UI", 8, QFont.StyleItalic)), row_idx, 0)
        self.ust_frame_layout.addWidget(QLabel(f"{self.siparis_ana.get('olusturma_tarihi_saat', '-') if self.siparis_ana.get('olusturma_tarihi_saat') else '-'} ({olusturan_adi})", font=QFont("Segoe UI", 8, QFont.StyleItalic)), row_idx, 1, 1, 3)
        row_idx += 1
        if self.siparis_ana.get('son_guncelleme_tarihi_saat'):
            self.ust_frame_layout.addWidget(QLabel("Son Güncelleme:", font=QFont("Segoe UI", 8, QFont.StyleItalic)), row_idx, 0)
            self.ust_frame_layout.addWidget(QLabel(f"{self.siparis_ana.get('son_guncelleme_tarihi_saat')} ({son_guncelleyen_adi})", font=QFont("Segoe UI", 8, QFont.StyleItalic)), row_idx, 1, 1, 3)
            row_idx += 1
        self.ust_frame_layout.addWidget(QLabel("Sipariş Notları:", font=QFont("Segoe UI", 9, QFont.Bold)), row_idx, 0, alignment=Qt.AlignTop) 
        siparis_notlari_display = QTextEdit()
        siparis_notlari_display.setPlainText(self.siparis_ana.get('siparis_notlari', '-') if self.siparis_ana.get('siparis_notlari') else "")
        siparis_notlari_display.setReadOnly(True)
        siparis_notlari_display.setFixedHeight(60)
        self.ust_frame_layout.addWidget(siparis_notlari_display, row_idx, 1, 1, 3)

        # Sipariş Kalemleri
        kalemler_frame = QGroupBox("Sipariş Kalemleri", self)
        kalemler_frame_layout = QVBoxLayout(kalemler_frame)
        self.main_layout.addWidget(kalemler_frame)
        
        cols_kalem = ("Sıra", "Ürün Kodu", "Ürün Adı", "Miktar", "Birim Fiyat", "KDV %", "İskonto 1 (%)", "İskonto 2 (%)", "Uyg. İsk. Tutarı", "Tutar (Dah.)", "Alış Fiyatı (Sipariş Anı)", "Satış Fiyatı (Sipariş Anı)")
        self.kalem_tree = QTreeWidget(kalemler_frame)
        self.kalem_tree.setHeaderLabels(cols_kalem)
        self.kalem_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.kalem_tree.setSortingEnabled(True)

        from PySide6.QtWidgets import QHeaderView
        col_defs_kalem = [
            ("Sıra", 40, Qt.AlignCenter), ("Ürün Kodu", 90, Qt.AlignLeft), ("Ürün Adı", 180, Qt.AlignLeft),
            ("Miktar", 60, Qt.AlignRight), ("Birim Fiyat", 90, Qt.AlignRight), ("KDV %", 60, Qt.AlignRight),
            ("İskonto 1 (%)", 75, Qt.AlignRight), ("İskonto 2 (%)", 75, Qt.AlignRight),
            ("Uyg. İsk. Tutarı", 100, Qt.AlignRight), ("Tutar (Dah.)", 110, Qt.AlignRight),
            ("Alış Fiyatı (Sipariş Anı)", 120, Qt.AlignRight), ("Satış Fiyatı (Sipariş Anı)", 120, Qt.AlignRight)
        ]
        for i, (col_name, width, alignment) in enumerate(col_defs_kalem):
            self.kalem_tree.setColumnWidth(i, width)
            self.kalem_tree.headerItem().setTextAlignment(i, alignment)
            self.kalem_tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
        self.kalem_tree.header().setStretchLastSection(False)
        self.kalem_tree.header().setSectionResizeMode(2, QHeaderView.Stretch) # Ürün Adı genişlesin

        kalemler_frame_layout.addWidget(self.kalem_tree)
        self._load_siparis_kalemleri_to_treeview(self.siparis_kalemleri_db)


        # Alt Toplamlar ve İskonto Bilgileri
        alt_toplam_iskonto_frame = QFrame(self)
        alt_toplam_iskonto_frame_layout = QGridLayout(alt_toplam_iskonto_frame)
        self.main_layout.addWidget(alt_toplam_iskonto_frame)

        self.lbl_genel_toplam = QLabel(f"Genel Toplam (KDV Dahil): {self.db._format_currency(self.siparis_ana.get('toplam_tutar'))}", font=QFont("Segoe UI", 10, QFont.Bold))
        alt_toplam_iskonto_frame_layout.addWidget(self.lbl_genel_toplam, 0, 1, 1, 2, Qt.AlignRight)
        alt_toplam_iskonto_frame_layout.setColumnStretch(0, 1) # Sol tarafı esnet
        
        self._butonlari_olustur()

    def _load_siparis_kalemleri_to_treeview(self, kalemler_list):
        self.kalem_tree.clear()
        sira_idx = 1
        for k_db in kalemler_list:
            urun_info_response = requests.get(f"{API_BASE_URL}/stoklar/{k_db.get('urun_id')}")
            urun_info_response.raise_for_status()
            urun_info = urun_info_response.json()

            urun_kodu_db = urun_info.get('urun_kodu')
            urun_adi_db = urun_info.get('urun_adi')
            
            miktar_gosterim = f"{k_db.get('miktar'):.2f}".rstrip('0').rstrip('.')
            iskontolu_birim_fiyat_kdv_dahil_display = (k_db.get('kalem_toplam_kdv_dahil') / k_db.get('miktar')) if k_db.get('miktar') != 0 else 0.0
            iskonto_yuzde_1_display = f"{k_db.get('iskonto_yuzde_1'):.2f}".replace('.', ',').rstrip('0').rstrip(',')
            iskonto_yuzde_2_display = f"{k_db.get('iskonto_yuzde_2'):.2f}".replace('.', ',').rstrip('0').rstrip(',')
            
            original_birim_fiyat_kdv_dahil_kalem = k_db.get('birim_fiyat') * (1 + k_db.get('kdv_orani') / 100)
            iskonto_farki_per_birim_detay = original_birim_fiyat_kdv_dahil_kalem - iskontolu_birim_fiyat_kdv_dahil_display
            uygulanan_toplam_iskonto_tutari_detay = iskonto_farki_per_birim_detay * k_db.get('miktar')

            item_qt = QTreeWidgetItem(self.kalem_tree)
            item_qt.setText(0, str(sira_idx))
            item_qt.setText(1, urun_kodu_db)
            item_qt.setText(2, urun_adi_db)
            item_qt.setText(3, miktar_gosterim)
            item_qt.setText(4, self.db._format_currency(iskontolu_birim_fiyat_kdv_dahil_display))
            item_qt.setText(5, f"%{k_db.get('kdv_orani'):.0f}")
            item_qt.setText(6, iskonto_yuzde_1_display)
            item_qt.setText(7, iskonto_yuzde_2_display)
            item_qt.setText(8, self.db._format_currency(uygulanan_toplam_iskonto_tutari_detay))
            item_qt.setText(9, self.db._format_currency(k_db.get('kalem_toplam_kdv_dahil')))
            item_qt.setText(10, self.db._format_currency(k_db.get('alis_fiyati_siparis_aninda')))
            item_qt.setText(11, self.db._format_currency(k_db.get('satis_fiyati_siparis_aninda')))
            
            sira_idx += 1

    def _butonlari_olustur(self):
        button_frame_alt = QFrame(self)
        button_frame_alt_layout = QHBoxLayout(button_frame_alt)
        self.main_layout.addWidget(button_frame_alt)

        self.faturaya_donustur_button_detail = QPushButton("Faturaya Dönüştür")
        self.faturaya_donustur_button_detail.clicked.connect(self._faturaya_donustur)
        button_frame_alt_layout.addWidget(self.faturaya_donustur_button_detail)
        
        btn_siparisi_duzenle = QPushButton("Siparişi Düzenle")
        btn_siparisi_duzenle.clicked.connect(self._siparisi_duzenle)
        button_frame_alt_layout.addWidget(btn_siparisi_duzenle)
        
        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.close) # QDialog'u kapat
        button_frame_alt_layout.addWidget(btn_kapat)

        if self.siparis_ana.get('fatura_id'):
            self.faturaya_donustur_button_detail.setEnabled(False)
            fatura_no_text = ""
            try:
                fatura_response = requests.get(f"{API_BASE_URL}/faturalar/{self.siparis_ana.get('fatura_id')}")
                fatura_response.raise_for_status()
                fatura_data = fatura_response.json()
                fatura_no_text = fatura_data.get('fatura_no', '-')
            except requests.exceptions.RequestException:
                fatura_no_text = "Hata"
            
            lbl_fatura_iliskisi = QLabel(f"Bu sipariş Fatura No: '{fatura_no_text}' ile ilişkilendirilmiştir.")
            lbl_fatura_iliskisi.setStyleSheet("color: blue; font-style: italic;")
            button_frame_alt_layout.addWidget(lbl_fatura_iliskisi)

    def _faturaya_donustur(self):
        """Bu siparişi satış veya alış faturasına dönüştürür."""
        
        # Ödeme Türü Seçim Diyaloğunu açın
        from pencereler import OdemeTuruSecimDialog

        # Cari tipine göre fatura tipi belirlenmeli
        fatura_tipi_for_dialog = 'SATIŞ' if self.siparis_ana.get('cari_tip') == 'MUSTERI' else 'ALIŞ'
        
        # Callback fonksiyonu olarak _faturaya_donustur_on_dialog_confirm'i gönderiyoruz.
        dialog = OdemeTuruSecimDialog(
            self.app, 
            self.db, # db_manager'ı geç
            fatura_tipi_for_dialog, 
            self.siparis_ana.get('cari_id'), 
            self._faturaya_donustur_on_dialog_confirm
        )
        dialog.exec() # Modalı olarak göster

    def _faturaya_donustur_on_dialog_confirm(self, selected_odeme_turu, selected_kasa_banka_id, selected_vade_tarihi):
        if selected_odeme_turu is None:
            self.app.set_status_message("Faturaya dönüştürme iptal edildi (ödeme türü seçilmedi).")
            return

        confirm_msg = (f"'{self.s_no}' numaralı siparişi '{selected_odeme_turu}' ödeme türü ile faturaya dönüştürmek istediğinizden emin misiniz?\n"
                       f"Bu işlem sonucunda yeni bir fatura oluşturulacak ve sipariş durumu güncellenecektir.")
        if selected_odeme_turu == "AÇIK HESAP" and selected_vade_tarihi:
            confirm_msg += f"\nVade Tarihi: {selected_vade_tarihi}"
        if selected_kasa_banka_id:
            # Kasa/banka bilgisi API'den çekilmeli
            try:
                kb_response = requests.get(f"{API_BASE_URL}/kasalar_bankalar/{selected_kasa_banka_id}")
                kb_response.raise_for_status()
                kb_bilgi = kb_response.json()
                if kb_bilgi:
                    confirm_msg += f"\nİşlem Kasa/Banka: {kb_bilgi.get('hesap_adi')}"
            except requests.exceptions.RequestException as e:
                logging.error(f"Kasa/Banka bilgisi çekilirken hata: {e}")
                confirm_msg += "\nİşlem Kasa/Banka: Bilgi çekilemedi"

        reply = QMessageBox.question(self, "Faturaya Dönüştür Onayı", confirm_msg, QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No:
            return

        # Hizmetler sınıfından FaturaService kullanılıyor varsayımı
        from hizmetler import FaturaService # FaturaService'i import et
        fatura_service = FaturaService(self.db) # db_manager'ı service'e geç
        
        success, message = fatura_service.siparis_faturaya_donustur(
            self.siparis_id,
            self.app.current_user[0] if self.app and hasattr(self.app, 'current_user') and self.app.current_user else None,
            selected_odeme_turu,
            selected_kasa_banka_id,
            selected_vade_tarihi
        )

        if success:
            QMessageBox.information(self, "Başarılı", message)
            self.close() 
            # Ana listeleri yenileme
            if hasattr(self.app, 'siparis_listesi_sayfasi'):
                self.app.siparis_listesi_sayfasi.siparis_listesini_yukle()
            if hasattr(self.app, 'fatura_listesi_sayfasi'):
                if hasattr(self.app.fatura_listesi_sayfasi, 'satis_fatura_frame'):
                    self.app.fatura_listesi_sayfasi.satis_fatura_frame.fatura_listesini_yukle()
                if hasattr(self.app.fatura_listesi_sayfasi, 'alis_fatura_frame'):
                    self.app.fatura_listesi_sayfasi.alis_fatura_frame.fatura_listesini_yukle()
        else:
            QMessageBox.critical(self, "Hata", message)

    def _siparisi_duzenle(self):
        """Bu siparişi düzenleme penceresinde açar."""
        from pencereler import SiparisPenceresi # SiparisPenceresi'nin PySide6 versiyonu
        siparis_tipi_db = 'SATIŞ_SIPARIS' if self.siparis_ana.get('cari_tip') == 'MUSTERI' else 'ALIŞ_SIPARIS'
        dialog = SiparisPenceresi(
            parent=self.app, 
            db_manager=self.db, # db_manager'ı geç
            app_ref=self.app,
            siparis_tipi=siparis_tipi_db,
            siparis_id_duzenle=self.siparis_id,
            yenile_callback=self.yenile_callback # Ana listeden gelen yenileme fonksiyonunu aktarıyoruz
        )
        dialog.exec()
        self.close() # Sipariş detay penceresini kapat

    def on_dialog_finished(self, result):
        if self.yenile_callback:
            self.yenile_callback()

class YoneticiAyarlariPenceresi(QDialog):
    def __init__(self, parent_app, db_manager):
        super().__init__(parent_app)
        self.app = parent_app
        self.db = db_manager
        self.setWindowTitle("Yönetici Ayarları ve Veri İşlemleri")
        self.setMinimumSize(600, 500)
        self.setModal(True) # Modalı olarak ayarla

        main_layout = QVBoxLayout(self)
        title_label = QLabel("Veri Sıfırlama ve Bakım")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        main_frame = QWidget(self)
        main_frame_layout = QVBoxLayout(main_frame)
        main_layout.addWidget(main_frame)

        buttons_info = [
            ("Geçmiş Hatalı Kayıtları Temizle", "Var olmayan faturalara ait 'hayalet' cari ve gelir/gider hareketlerini siler. (Tek seferlik çalıştırın)", self.db.gecmis_hatali_kayitlari_temizle),
            ("Stok Envanterini Yeniden Hesapla", "Tüm stokları faturalara göre sıfırdan hesaplar. Geçmiş hatalı silme işlemlerini düzeltir.", self.db.stok_envanterini_yeniden_hesapla),
            ("Stok Verilerini Temizle", "Bu işlem tüm ürünleri ve ilişkili kalemleri siler.", self.db.clear_stok_data),
            ("Müşteri Verilerini Temizle", "Bu işlem perakende müşteri hariç tüm müşterileri ve ilişkili hareketlerini siler.", self.db.clear_musteri_data),
            ("Tedarikçi Verilerini Temizle", "Bu işlem tüm tedarikçileri ve ilişkili hareketlerini siler.", self.db.clear_tedarikci_data),
            ("Kasa/Banka Verilerini Temizle", "Bu işlem tüm kasa/banka hesaplarını temizler ve ilişkili referansları kaldırır.", self.db.clear_kasa_banka_data),
            ("Tüm İşlem Verilerini Temizle", "Faturalar, gelir/gider, cari hareketler, siparişler ve teklifler gibi tüm operasyonel verileri siler. Ana kayıtlar korunur.", self.db.clear_all_transaction_data),
            ("Tüm Verileri Temizle (Kullanıcılar Hariç)", "Kullanıcılar ve şirket ayarları hariç tüm veritabanını temizler. Program yeniden başlatılacaktır.", self.db.clear_all_data)
        ]

        for i, (text, desc, func) in enumerate(buttons_info):
            btn_frame = QFrame()
            btn_frame_layout = QHBoxLayout(btn_frame)
            
            btn = QPushButton(text)
            btn.clicked.connect(lambda f=func, t=text: self._confirm_and_run_utility(f, t))
            btn_frame_layout.addWidget(btn)
            
            desc_label = QLabel(desc)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("font-size: 8pt;")
            btn_frame_layout.addWidget(desc_label, 1) # Streç faktör 1
            
            main_frame_layout.addWidget(btn_frame)
        
        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.close)
        main_layout.addWidget(btn_kapat, alignment=Qt.AlignRight)

    def _confirm_and_run_utility(self, utility_function, button_text):
        confirm_message = f"'{button_text}' işlemini gerçekleştirmek istediğinizden emin misiniz?\n\nBU İŞLEM GERİ ALINAMAZ!"
        if "Tüm Verileri Temizle" in button_text:
             confirm_message += "\n\nBu işlemden sonra program yeniden başlatılacaktır."

        reply = QMessageBox.question(self, "Onay Gerekli", confirm_message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                success, message = utility_function()

                if success:
                    QMessageBox.information(self, "Başarılı", message)
                    self.app.set_status_message(message)

                    # İlgili pencereleri yenileme ihtiyacı olabilir
                    # Bu kısımlar app ana objesindeki sekme widget'larına bağlıdır.
                    # Örneğin: self.app.musteri_yonetimi_sayfasi.musteri_listesini_yenile()
                    # Şimdilik genel bir mesajla geçiyoruz.
                    # Eğer bu metodlar App sınıfında mevcutsa, çağrılmaları gerekir.
                    # Örn: if hasattr(self.app, 'musteri_yonetimi_sayfasi'): self.app.musteri_yonetimi_sayfasi.musteri_listesini_yenile()
                    
                    if "Tüm Verileri Temizle" in button_text:
                        # self.app.cikis_yap_ve_giris_ekranina_don() # Bu metod app'te yoksa hata verir.
                        QMessageBox.information(self, "Bilgi", "Tüm veriler temizlendi. Uygulama yeniden başlatılıyor.")
                        QApplication.quit() # Uygulamayı kapat

                else:
                    QMessageBox.critical(self, "Hata", message)
                    self.app.set_status_message(f"'{button_text}' işlemi sırasında hata oluştu: {message}")
            except Exception as e:
                QMessageBox.critical(self, "Kritik Hata", f"İşlem sırasında beklenmedik bir hata oluştu: {e}")
                logging.error(f"'{button_text}' yardımcı programı çalıştırılırken hata: {traceback.format_exc()}")
        else:
            self.app.set_status_message(f"'{button_text}' işlemi iptal edildi.")

class SirketBilgileriPenceresi(QDialog):
    def __init__(self, parent, db_manager):
        super().__init__(parent)
        self.db = db_manager
        self.app_parent = parent # Ana App referansı
        self.setWindowTitle("Şirket Bilgileri")
        self.setMinimumSize(550, 400)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        title_label = QLabel("Şirket Bilgileri Yönetimi")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        main_frame = QWidget(self)
        main_frame_layout = QGridLayout(main_frame)
        main_layout.addWidget(main_frame)

        self.field_definitions = [
            ("Şirket Adı:", "sirket_adi", QLineEdit),
            ("Adres:", "sirket_adresi", QTextEdit),
            ("Telefon:", "sirket_telefonu", QLineEdit),
            ("E-mail:", "sirket_email", QLineEdit),
            ("Vergi Dairesi:", "sirket_vergi_dairesi", QLineEdit),
            ("Vergi No:", "sirket_vergi_no", QLineEdit),
            ("Logo Yolu:", "sirket_logo_yolu", QLineEdit)
        ]
        self.entries = {}

        for i, (label_text, db_key_name, widget_type) in enumerate(self.field_definitions):
            main_frame_layout.addWidget(QLabel(label_text), i, 0, alignment=Qt.AlignLeft)
            
            if widget_type == QTextEdit:
                widget = QTextEdit()
                widget.setFixedHeight(60) # Yükseklik ayarı
            else: # QLineEdit
                widget = QLineEdit()
            
            self.entries[db_key_name] = widget
            main_frame_layout.addWidget(widget, i, 1)
            
            if db_key_name == "sirket_logo_yolu":
                logo_button = QPushButton("Gözat...")
                logo_button.clicked.connect(self.logo_gozat)
                main_frame_layout.addWidget(logo_button, i, 2)

        main_frame_layout.setColumnStretch(1, 1) # Entry'lerin genişlemesi için

        self.yukle_bilgiler()

        button_layout = QHBoxLayout()
        button_layout.addStretch() # Butonları sağa yasla
        kaydet_button = QPushButton("Kaydet")
        kaydet_button.clicked.connect(self.kaydet_bilgiler)
        button_layout.addWidget(kaydet_button)
        iptal_button = QPushButton("İptal")
        iptal_button.clicked.connect(self.close)
        button_layout.addWidget(iptal_button)
        main_layout.addLayout(button_layout)

    def logo_gozat(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Logo Seçin", "", "Resim Dosyaları (*.png *.jpg *.jpeg);;Tüm Dosyalar (*)")
        if file_path:
            self.entries["sirket_logo_yolu"].setText(file_path)

    def yukle_bilgiler(self):
        mevcut_bilgiler = self.db.sirket_bilgilerini_yukle()
        for db_key_name, entry_widget in self.entries.items():
            if isinstance(entry_widget, QTextEdit):
                entry_widget.setPlainText(mevcut_bilgiler.get(db_key_name, ""))
            else:
                entry_widget.setText(mevcut_bilgiler.get(db_key_name, ""))
    
    def kaydet_bilgiler(self):
        yeni_bilgiler = {}
        for db_key_name, entry_widget in self.entries.items():
            if isinstance(entry_widget, QTextEdit):
                yeni_bilgiler[db_key_name] = entry_widget.toPlainText().strip()
            else:
                yeni_bilgiler[db_key_name] = entry_widget.text().strip()

        print(f"DEBUG: kaydet_bilgiler - yeni_bilgiler sözlüğü: {yeni_bilgiler}")
        success, message = self.db.sirket_bilgilerini_kaydet(yeni_bilgiler)
        if success:
            if hasattr(self.app_parent, 'ana_sayfa') and hasattr(self.app_parent.ana_sayfa, 'guncelle_sirket_adi'):
                self.app_parent.ana_sayfa.guncelle_sirket_adi()
            if hasattr(self.app_parent, 'set_status_message'):
                 self.app_parent.set_status_message(message)
            QMessageBox.information(self, "Başarılı", message)
            self.close()
        else:
            QMessageBox.critical(self, "Hata", message)
            
class StokHareketiPenceresi(QDialog):
    def __init__(self, parent, urun_id, urun_adi, mevcut_stok, hareket_yonu, yenile_callback):
        super().__init__(parent)
        self.urun_id = urun_id
        self.yenile_callback = yenile_callback

        title = "Stok Girişi" if hareket_yonu == "EKLE" else "Stok Çıkışı"
        self.setWindowTitle(f"{title}: {urun_adi}")
        self.setMinimumWidth(400)
        self.setModal(True)

        self.main_layout = QVBoxLayout(self)
        self.form_layout = QGridLayout()

        self.main_layout.addWidget(QLabel(f"<b>{title}</b><br>Ürün: {urun_adi}<br>Mevcut Stok: {mevcut_stok:.2f}"), alignment=Qt.AlignCenter)
        self.main_layout.addLayout(self.form_layout)

        self.entries = {}
        self.form_layout.addWidget(QLabel("İşlem Tipi:"), 0, 0)
        self.entries['islem_tipi'] = QComboBox()
        if hareket_yonu == "EKLE": self.entries['islem_tipi'].addItems(["Giriş (Manuel)", "Sayım Fazlası", "İade Girişi"])
        else: self.entries['islem_tipi'].addItems(["Çıkış (Manuel)", "Sayım Eksiği", "Zayiat"])
        self.form_layout.addWidget(self.entries['islem_tipi'], 0, 1)

        self.form_layout.addWidget(QLabel("Miktar:"), 1, 0)
        self.entries['miktar'] = QLineEdit("0,00"); self.entries['miktar'].setValidator(QDoubleValidator(0.01, 999999.0, 2))
        self.form_layout.addWidget(self.entries['miktar'], 1, 1)

        self.form_layout.addWidget(QLabel("Tarih:"), 2, 0)
        self.entries['tarih'] = QLineEdit(datetime.now().strftime('%Y-%m-%d'))
        self.form_layout.addWidget(self.entries['tarih'], 2, 1)

        self.form_layout.addWidget(QLabel("Açıklama:"), 3, 0, alignment=Qt.AlignTop)
        self.entries['aciklama'] = QTextEdit()
        self.form_layout.addWidget(self.entries['aciklama'], 3, 1)

        button_layout = QHBoxLayout(); button_layout.addStretch()
        kaydet_button = QPushButton("Kaydet"); kaydet_button.clicked.connect(self.kaydet)
        iptal_button = QPushButton("İptal"); iptal_button.clicked.connect(self.reject)
        button_layout.addWidget(kaydet_button); button_layout.addWidget(iptal_button)
        self.main_layout.addLayout(button_layout)

    def kaydet(self):
        try:
            miktar = float(self.entries['miktar'].text().replace(',', '.'))
            if miktar <= 0: raise ValueError("Miktar pozitif bir değer olmalıdır.")
        except (ValueError, TypeError):
            QMessageBox.warning(self, "Geçersiz Değer", "Lütfen miktar alanına geçerli bir sayı girin."); return

        data = {
            "islem_tipi": self.entries['islem_tipi'].currentText(),
            "miktar": miktar, "tarih": self.entries['tarih'].text(),
            "aciklama": self.entries['aciklama'].toPlainText().strip()
        }
        try:
            api_url = f"{API_BASE_URL}/stoklar/{self.urun_id}/hareket"
            response = requests.post(api_url, json=data); response.raise_for_status()
            QMessageBox.information(self, "Başarılı", "Stok hareketi başarıyla kaydedildi.")
            if self.yenile_callback: self.yenile_callback()
            self.accept()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Stok hareketi kaydedilirken bir hata oluştu:\n{error_detail}")

class IlgiliFaturalarDetayPenceresi(QDialog):
    def __init__(self, parent_app, db_manager, urun_id, urun_adi):
        super().__init__(parent_app)
        self.app = parent_app
        self.db = db_manager
        self.urun_id = urun_id
        self.urun_adi = urun_adi
        self.setWindowTitle(f"{self.urun_adi} - İlgili Faturalar")
        self.setMinimumSize(1000, 600)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        title_label = QLabel(f"{self.urun_adi} Ürününün Yer Aldığı Faturalar")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignLeft)
        main_layout.addWidget(title_label)

        filter_frame = QFrame(self)
        filter_layout = QHBoxLayout(filter_frame)
        main_layout.addWidget(filter_frame)

        filter_layout.addWidget(QLabel("Fatura Tipi:"))
        self.fatura_tipi_filter_cb = QComboBox()
        self.fatura_tipi_filter_cb.addItems(["TÜMÜ", "ALIŞ", "SATIŞ"])
        self.fatura_tipi_filter_cb.currentIndexChanged.connect(self._load_ilgili_faturalar)
        filter_layout.addWidget(self.fatura_tipi_filter_cb)
        filter_layout.addStretch() # Sağa yaslama için

        # Filtreleme butonu kaldırıldı, combobox değişince tetikleniyor.
        # btn_filter = QPushButton("Filtrele")
        # btn_filter.clicked.connect(self._load_ilgili_faturalar)
        # filter_layout.addWidget(btn_filter)

        cols_fatura = ("ID", "Fatura No", "Tarih", "Tip", "Cari/Misafir", "KDV Hariç Top.", "KDV Dahil Top.")
        self.ilgili_faturalar_tree = QTreeWidget(self)
        self.ilgili_faturalar_tree.setHeaderLabels(cols_fatura)
        self.ilgili_faturalar_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ilgili_faturalar_tree.setSortingEnabled(True)

        from PySide6.QtWidgets import QHeaderView
        col_defs_fatura = [
            ("ID", 40, Qt.AlignRight), # Sağa hizala
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
        self.ilgili_faturalar_tree.header().setSectionResizeMode(4, QHeaderView.Stretch) # Cari/Misafir genişlesin

        main_layout.addWidget(self.ilgili_faturalar_tree)

        self.ilgili_faturalar_tree.itemDoubleClicked.connect(self._on_fatura_double_click)

        self._load_ilgili_faturalar() # İlk yükleme

        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.close)
        main_layout.addWidget(btn_kapat, alignment=Qt.AlignRight)

    def _load_ilgili_faturalar(self, index=None): # index parametresi QComboBox'tan gelir, kullanılmıyor
        self.ilgili_faturalar_tree.clear()

        if not self.urun_id:
            item_qt = QTreeWidgetItem(self.ilgili_faturalar_tree)
            item_qt.setText(4, "Ürün seçili değil.")
            return

        fatura_tipi_filtre = self.fatura_tipi_filter_cb.currentText()
        if fatura_tipi_filtre == "TÜMÜ":
            fatura_tipi_filtre = None # API'ye tüm tipleri çekmesi için None gönder
        
        # API'den veri çek
        try:
            params = {'urun_id': self.urun_id}
            if fatura_tipi_filtre:
                params['fatura_tipi'] = fatura_tipi_filtre

            response = requests.get(f"{API_BASE_URL}/faturalar/ilgili-faturalar", params=params) # Yeni endpoint varsayımı
            response.raise_for_status()
            faturalar = response.json()
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Hatası", f"İlgili faturalar çekilirken hata: {e}")
            logging.error(f"İlgili faturalar yükleme hatası: {e}")
            return

        if not faturalar:
            item_qt = QTreeWidgetItem(self.ilgili_faturalar_tree)
            item_qt.setText(4, "Bu ürüne ait fatura bulunamadı.")
            return

        for fatura_item in faturalar:
            item_qt = QTreeWidgetItem(self.ilgili_faturalar_tree)
            
            fatura_id = fatura_item.get('id')
            fatura_no = fatura_item.get('fatura_no')
            tarih_str = fatura_item.get('tarih')
            fatura_tip = fatura_item.get('tip')
            cari_adi = fatura_item.get('cari_adi') # API'den gelmesi beklenir
            misafir_adi = fatura_item.get('misafir_adi') # API'den gelmesi beklenir
            toplam_kdv_haric = fatura_item.get('toplam_kdv_haric')
            toplam_kdv_dahil = fatura_item.get('toplam_kdv_dahil')

            try:
                formatted_tarih = datetime.strptime(tarih_str, '%Y-%m-%d').strftime('%d.%m.%Y')
            except ValueError:
                formatted_tarih = tarih_str
            
            display_cari_info = cari_adi
            if fatura_tip == "SATIŞ" and misafir_adi:
                display_cari_info = f"Perakende ({misafir_adi})"

            item_qt.setText(0, str(fatura_id))
            item_qt.setText(1, fatura_no)
            item_qt.setText(2, formatted_tarih)
            item_qt.setText(3, fatura_tip)
            item_qt.setText(4, display_cari_info)
            item_qt.setText(5, self.db._format_currency(toplam_kdv_haric))
            item_qt.setText(6, self.db._format_currency(toplam_kdv_dahil))

        self.app.set_status_message(f"Ürün '{self.urun_adi}' için {len(faturalar)} fatura listelendi.")

    def _on_fatura_double_click(self, item, column): # item and column from QTreeWidget signal
        fatura_id = item.text(0) # ID ilk sütunda
        if fatura_id:
            from pencereler import FaturaDetayPenceresi
            FaturaDetayPenceresi(self.app, self.db, int(fatura_id)).exec() # fatura_id int olmalı

class KategoriMarkaYonetimiPenceresi(QDialog):
    def __init__(self, parent_app, db_manager, refresh_callback=None):
        super().__init__(parent_app)
        self.app = parent_app
        self.db = db_manager
        self.refresh_callback = refresh_callback # Ürün kartı combobox'larını yenilemek için callback
        self.setWindowTitle("Kategori & Marka Yönetimi")
        self.setMinimumSize(800, 500)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        title_label = QLabel("Kategori & Marka Yönetimi")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignLeft)
        main_layout.addWidget(title_label)

        # Ana içerik çerçevesi
        main_frame = QWidget(self)
        main_frame_layout = QHBoxLayout(main_frame) # Yatay layout
        main_layout.addWidget(main_frame)
        main_frame_layout.setStretch(0, 1) # Kategori Frame için
        main_frame_layout.setStretch(1, 1) # Marka Frame için

        # Sol taraf: Kategori Yönetimi
        kategori_frame = QGroupBox("Kategori Yönetimi", main_frame)
        kategori_frame_layout = QGridLayout(kategori_frame)
        main_frame_layout.addWidget(kategori_frame)
        kategori_frame_layout.setColumnStretch(1, 1) # Entry için

        kategori_frame_layout.addWidget(QLabel("Kategori Adı:"), 0, 0)
        self.kategori_entry = QLineEdit()
        kategori_frame_layout.addWidget(self.kategori_entry, 0, 1)
        kategori_frame_layout.addWidget(QPushButton("Ekle", clicked=self._kategori_ekle_ui), 0, 2)
        kategori_frame_layout.addWidget(QPushButton("Güncelle", clicked=self._kategori_guncelle_ui), 0, 3)
        kategori_frame_layout.addWidget(QPushButton("Sil", clicked=self._kategori_sil_ui), 0, 4)

        self.kategori_tree = QTreeWidget()
        self.kategori_tree.setHeaderLabels(["ID", "Kategori Adı"])
        self.kategori_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.kategori_tree.setColumnWidth(0, 50) # ID sütun genişliği
        self.kategori_tree.header().setSectionResizeMode(1, QHeaderView.Stretch) # Kategori Adı genişlesin
        kategori_frame_layout.addWidget(self.kategori_tree, 1, 0, 1, 5) # Tüm sütunlara yayılsın
        self.kategori_tree.itemSelectionChanged.connect(self._on_kategori_select)
        
        # Sağ tık menüsü
        self.kategori_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.kategori_tree.customContextMenuRequested.connect(self._open_kategori_context_menu)
        self._kategori_listesini_yukle()


        # Sağ taraf: Marka Yönetimi
        marka_frame = QGroupBox("Marka Yönetimi", main_frame)
        marka_frame_layout = QGridLayout(marka_frame)
        main_frame_layout.addWidget(marka_frame)
        marka_frame_layout.setColumnStretch(1, 1) # Entry için

        marka_frame_layout.addWidget(QLabel("Marka Adı:"), 0, 0)
        self.marka_entry = QLineEdit()
        marka_frame_layout.addWidget(self.marka_entry, 0, 1)
        marka_frame_layout.addWidget(QPushButton("Ekle", clicked=self._marka_ekle_ui), 0, 2)
        marka_frame_layout.addWidget(QPushButton("Güncelle", clicked=self._marka_guncelle_ui), 0, 3)
        marka_frame_layout.addWidget(QPushButton("Sil", clicked=self._marka_sil_ui), 0, 4)

        self.marka_tree = QTreeWidget()
        self.marka_tree.setHeaderLabels(["ID", "Marka Adı"])
        self.marka_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.marka_tree.setColumnWidth(0, 50) # ID sütun genişliği
        self.marka_tree.header().setSectionResizeMode(1, QHeaderView.Stretch) # Marka Adı genişlesin
        marka_frame_layout.addWidget(self.marka_tree, 1, 0, 1, 5) # Tüm sütunlara yayılsın
        self.marka_tree.itemSelectionChanged.connect(self._on_marka_select)

        # Sağ tık menüsü
        self.marka_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.marka_tree.customContextMenuRequested.connect(self._open_marka_context_menu)
        self._marka_listesini_yukle()

        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self._on_close)
        main_layout.addWidget(btn_kapat, alignment=Qt.AlignRight)

    def _on_close(self):
        if self.refresh_callback:
            self.refresh_callback() # Ürün kartı combobox'larını yenile
        self.close()

    def _kategori_listesini_yukle(self):
        self.kategori_tree.clear()
        try:
            response = requests.get(f"{API_BASE_URL}/nitelikler/kategoriler")
            response.raise_for_status()
            kategoriler = response.json()
            for kat in kategoriler: 
                item_qt = QTreeWidgetItem(self.kategori_tree)
                item_qt.setText(0, str(kat.get('id')))
                item_qt.setText(1, kat.get('kategori_adi'))
                item_qt.setData(0, Qt.UserRole, kat.get('id')) # ID'yi UserRole olarak sakla
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Hatası", f"Kategori listesi çekilirken hata: {e}")
            logging.error(f"Kategori listesi yükleme hatası: {e}")

    def _on_kategori_select(self):
        selected_items = self.kategori_tree.selectedItems()
        if selected_items:
            values = selected_items[0].text(1) # Kategori Adı
            self.kategori_entry.setText(values)
        else:
            self.kategori_entry.clear()

    def _kategori_ekle_ui(self):
        kategori_adi = self.kategori_entry.text().strip()
        if not kategori_adi:
            QMessageBox.warning(self, "Uyarı", "Kategori adı boş olamaz.")
            return
        try:
            response = requests.post(f"{API_BASE_URL}/nitelikler/kategoriler", json={"kategori_adi": kategori_adi})
            response.raise_for_status()
            QMessageBox.information(self, "Başarılı", "Kategori başarıyla eklendi.")
            self.kategori_entry.clear()
            self._kategori_listesini_yukle()
            if self.refresh_callback: self.refresh_callback()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Kategori eklenirken hata: {error_detail}")

    def _kategori_guncelle_ui(self):
        selected_items = self.kategori_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen güncellemek için bir kategori seçin.")
            return
        kategori_id = selected_items[0].data(0, Qt.UserRole)
        yeni_kategori_adi = self.kategori_entry.text().strip()
        if not yeni_kategori_adi:
            QMessageBox.warning(self, "Uyarı", "Kategori adı boş olamaz.")
            return
        try:
            response = requests.put(f"{API_BASE_URL}/nitelikler/kategoriler/{kategori_id}", json={"kategori_adi": yeni_kategori_adi})
            response.raise_for_status()
            QMessageBox.information(self, "Başarılı", "Kategori başarıyla güncellendi.")
            self.kategori_entry.clear()
            self._kategori_listesini_yukle()
            if self.refresh_callback: self.refresh_callback()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Kategori güncellenirken hata: {error_detail}")

    def _kategori_sil_ui(self):
        selected_items = self.kategori_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir kategori seçin.")
            return
        kategori_id = selected_items[0].data(0, Qt.UserRole)
        kategori_adi = selected_items[0].text(1)
        reply = QMessageBox.question(self, "Onay", f"'{kategori_adi}' kategorisini silmek istediğinizden emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                response = requests.delete(f"{API_BASE_URL}/nitelikler/kategoriler/{kategori_id}")
                response.raise_for_status()
                QMessageBox.information(self, "Başarılı", "Kategori başarıyla silindi.")
                self.kategori_entry.clear()
                self._kategori_listesini_yukle()
                if self.refresh_callback: self.refresh_callback()
            except requests.exceptions.RequestException as e:
                error_detail = str(e)
                if e.response is not None:
                    try: error_detail = e.response.json().get('detail', str(e.response.content))
                    except ValueError: pass
                QMessageBox.critical(self, "API Hatası", f"Kategori silinirken hata: {error_detail}")

    def _open_kategori_context_menu(self, pos):
        item = self.kategori_tree.itemAt(pos)
        if not item: return

        context_menu = QMenu(self)
        context_menu.addAction("Güncelle").triggered.connect(self._kategori_guncelle_ui)
        context_menu.addAction("Sil").triggered.connect(self._kategori_sil_ui)
        context_menu.exec(self.kategori_tree.mapToGlobal(pos))

    def _marka_listesini_yukle(self):
        self.marka_tree.clear()
        try:
            response = requests.get(f"{API_BASE_URL}/nitelikler/markalar")
            response.raise_for_status()
            markalar = response.json()
            for mar in markalar:
                item_qt = QTreeWidgetItem(self.marka_tree)
                item_qt.setText(0, str(mar.get('id')))
                item_qt.setText(1, mar.get('marka_adi'))
                item_qt.setData(0, Qt.UserRole, mar.get('id'))
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Hatası", f"Marka listesi çekilirken hata: {e}")
            logging.error(f"Marka listesi yükleme hatası: {e}")

    def _on_marka_select(self):
        selected_items = self.marka_tree.selectedItems()
        if selected_items:
            values = selected_items[0].text(1) # Marka Adı
            self.marka_entry.setText(values)
        else:
            self.marka_entry.clear()

    def _marka_ekle_ui(self):
        marka_adi = self.marka_entry.text().strip()
        if not marka_adi:
            QMessageBox.warning(self, "Uyarı", "Marka adı boş olamaz.")
            return
        try:
            response = requests.post(f"{API_BASE_URL}/nitelikler/markalar", json={"marka_adi": marka_adi})
            response.raise_for_status()
            QMessageBox.information(self, "Başarılı", "Marka başarıyla eklendi.")
            self.marka_entry.clear()
            self._marka_listesini_yukle()
            if self.refresh_callback: self.refresh_callback()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Marka eklenirken hata: {error_detail}")

    def _marka_guncelle_ui(self):
        selected_items = self.marka_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen güncellemek için bir marka seçin.")
            return
        marka_id = selected_items[0].data(0, Qt.UserRole)
        yeni_marka_adi = self.marka_entry.text().strip()
        if not yeni_marka_adi:
            QMessageBox.warning(self, "Uyarı", "Marka adı boş olamaz.")
            return
        try:
            response = requests.put(f"{API_BASE_URL}/nitelikler/markalar/{marka_id}", json={"marka_adi": yeni_marka_adi})
            response.raise_for_status()
            QMessageBox.information(self, "Başarılı", "Marka başarıyla güncellendi.")
            self.marka_entry.clear()
            self._marka_listesini_yukle()
            if self.refresh_callback: self.refresh_callback()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Marka güncellenirken hata: {error_detail}")

    def _marka_sil_ui(self):
        selected_items = self.marka_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir marka seçin.")
            return
        marka_id = selected_items[0].data(0, Qt.UserRole)
        marka_adi = selected_items[0].text(1)
        reply = QMessageBox.question(self, "Onay", f"'{marka_adi}' markasını silmek istediğinizden emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                response = requests.delete(f"{API_BASE_URL}/nitelikler/markalar/{marka_id}")
                response.raise_for_status()
                QMessageBox.information(self, "Başarılı", "Marka başarıyla silindi.")
                self.marka_entry.clear()
                self._marka_listesini_yukle()
                if self.refresh_callback: self.refresh_callback()
            except requests.exceptions.RequestException as e:
                error_detail = str(e)
                if e.response is not None:
                    try: error_detail = e.response.json().get('detail', str(e.response.content))
                    except ValueError: pass
                QMessageBox.critical(self, "API Hatası", f"Marka silinirken hata: {error_detail}")
    
    def _open_marka_context_menu(self, pos):
        item = self.marka_tree.itemAt(pos)
        if not item: return

        context_menu = QMenu(self)
        context_menu.addAction("Güncelle").triggered.connect(self._marka_guncelle_ui)
        context_menu.addAction("Sil").triggered.connect(self._marka_sil_ui)
        context_menu.exec(self.marka_tree.mapToGlobal(pos))

class UrunNitelikYonetimiPenceresi(QDialog):
    def __init__(self, parent_notebook, db_manager, app_ref, refresh_callback=None):
        super().__init__(parent_notebook)
        self.db = db_manager
        self.app = app_ref
        self.refresh_callback = refresh_callback

        self.setWindowTitle("Ürün Grubu, Birimi ve Menşe Ülke Yönetimi")
        self.setMinimumSize(800, 600)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        title_label = QLabel("Ürün Grubu, Birimi ve Menşe Ülke Yönetimi")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignLeft)
        main_layout.addWidget(title_label)

        # Ana içerik çerçevesi (grid gibi düzenleme için)
        main_frame = QWidget(self)
        main_frame_layout = QGridLayout(main_frame)
        main_layout.addWidget(main_frame)
        main_frame_layout.setColumnStretch(0, 1)
        main_frame_layout.setColumnStretch(1, 1)
        main_frame_layout.setRowStretch(0, 1)
        main_frame_layout.setRowStretch(1, 1)


        # --- Ürün Grubu Yönetimi ---
        urun_grubu_frame = QGroupBox("Ürün Grubu Yönetimi", main_frame)
        urun_grubu_frame_layout = QGridLayout(urun_grubu_frame)
        main_frame_layout.addWidget(urun_grubu_frame, 0, 0)
        urun_grubu_frame_layout.setColumnStretch(1, 1)

        urun_grubu_frame_layout.addWidget(QLabel("Grup Adı:"), 0, 0)
        self.urun_grubu_entry = QLineEdit()
        urun_grubu_frame_layout.addWidget(self.urun_grubu_entry, 0, 1)
        urun_grubu_frame_layout.addWidget(QPushButton("Ekle", clicked=self._urun_grubu_ekle_ui), 0, 2)
        urun_grubu_frame_layout.addWidget(QPushButton("Sil", clicked=self._urun_grubu_sil_ui), 0, 3)

        self.urun_grubu_tree = QTreeWidget()
        self.urun_grubu_tree.setHeaderLabels(["ID", "Grup Adı"])
        self.urun_grubu_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.urun_grubu_tree.setColumnWidth(0, 50)
        self.urun_grubu_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        urun_grubu_frame_layout.addWidget(self.urun_grubu_tree, 1, 0, 1, 4)
        self.urun_grubu_tree.itemSelectionChanged.connect(self._on_urun_grubu_select)
        
        self.urun_grubu_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.urun_grubu_tree.customContextMenuRequested.connect(self._open_urun_grubu_context_menu) 
        self._urun_grubu_listesini_yukle()

        # --- Ürün Birimi Yönetimi ---
        urun_birimi_frame = QGroupBox("Ürün Birimi Yönetimi", main_frame)
        urun_birimi_frame_layout = QGridLayout(urun_birimi_frame)
        main_frame_layout.addWidget(urun_birimi_frame, 0, 1)
        urun_birimi_frame_layout.setColumnStretch(1, 1)

        urun_birimi_frame_layout.addWidget(QLabel("Birim Adı:"), 0, 0)
        self.urun_birimi_entry = QLineEdit()
        urun_birimi_frame_layout.addWidget(self.urun_birimi_entry, 0, 1)
        urun_birimi_frame_layout.addWidget(QPushButton("Ekle", clicked=self._urun_birimi_ekle_ui), 0, 2)
        urun_birimi_frame_layout.addWidget(QPushButton("Sil", clicked=self._urun_birimi_sil_ui), 0, 3)

        self.urun_birimi_tree = QTreeWidget()
        self.urun_birimi_tree.setHeaderLabels(["ID", "Birim Adı"])
        self.urun_birimi_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.urun_birimi_tree.setColumnWidth(0, 50)
        self.urun_birimi_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        urun_birimi_frame_layout.addWidget(self.urun_birimi_tree, 1, 0, 1, 4)
        self.urun_birimi_tree.itemSelectionChanged.connect(self._on_urun_birimi_select)
        
        self.urun_birimi_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.urun_birimi_tree.customContextMenuRequested.connect(self._open_birim_context_menu)
        self._urun_birimi_listesini_yukle()

        # --- Ülke (Menşe) Yönetimi ---
        ulke_frame = QGroupBox("Menşe Ülke Yönetimi", main_frame)
        ulke_frame_layout = QGridLayout(ulke_frame)
        main_frame_layout.addWidget(ulke_frame, 1, 0, 1, 2) # İki sütuna yay
        ulke_frame_layout.setColumnStretch(1, 1)

        ulke_frame_layout.addWidget(QLabel("Ülke Adı:"), 0, 0)
        self.ulke_entry = QLineEdit()
        ulke_frame_layout.addWidget(self.ulke_entry, 0, 1)
        ulke_frame_layout.addWidget(QPushButton("Ekle", clicked=self._ulke_ekle_ui), 0, 2)
        ulke_frame_layout.addWidget(QPushButton("Sil", clicked=self._ulke_sil_ui), 0, 3)

        self.ulke_tree = QTreeWidget()
        self.ulke_tree.setHeaderLabels(["ID", "Ülke Adı"])
        self.ulke_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ulke_tree.setColumnWidth(0, 50)
        self.ulke_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        ulke_frame_layout.addWidget(self.ulke_tree, 1, 0, 1, 4)
        self.ulke_tree.itemSelectionChanged.connect(self._on_ulke_select)
        
        self.ulke_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ulke_tree.customContextMenuRequested.connect(self._open_ulke_context_menu)
        self._ulke_listesini_yukle()

        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self._on_close)
        main_layout.addWidget(btn_kapat, alignment=Qt.AlignRight)

    def _on_close(self):
        if self.refresh_callback:
            self.refresh_callback() # Ürün kartı combobox'larını yenile
        self.close()

    # Ürün Grubu Yönetimi Metotları
    def _urun_grubu_listesini_yukle(self):
        self.urun_grubu_tree.clear()
        try:
            response = requests.get(f"{API_BASE_URL}/nitelikler/urun_gruplari")
            response.raise_for_status()
            urun_gruplari = response.json()
            for grup in urun_gruplari:
                item_qt = QTreeWidgetItem(self.urun_grubu_tree)
                item_qt.setText(0, str(grup.get('id')))
                item_qt.setText(1, grup.get('grup_adi'))
                item_qt.setData(0, Qt.UserRole, grup.get('id'))
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Hatası", f"Ürün grubu listesi çekilirken hata: {e}")
            logging.error(f"Ürün grubu listesi yükleme hatası: {e}")

    def _on_urun_grubu_select(self):
        selected_items = self.urun_grubu_tree.selectedItems()
        if selected_items:
            values = selected_items[0].text(1)
            self.urun_grubu_entry.setText(values)
        else:
            self.urun_grubu_entry.clear()

    def _urun_grubu_ekle_ui(self):
        grup_adi = self.urun_grubu_entry.text().strip()
        if not grup_adi:
            QMessageBox.warning(self, "Uyarı", "Ürün grubu adı boş olamaz.")
            return
        try:
            response = requests.post(f"{API_BASE_URL}/nitelikler/urun_gruplari", json={"grup_adi": grup_adi})
            response.raise_for_status()
            QMessageBox.information(self, "Başarılı", "Ürün grubu başarıyla eklendi.")
            self.urun_grubu_entry.clear()
            self._urun_grubu_listesini_yukle()
            if self.refresh_callback: self.refresh_callback()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Ürün grubu eklenirken hata: {error_detail}")

    def _urun_grubu_guncelle_ui(self):
        selected_items = self.urun_grubu_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen güncellemek için bir ürün grubu seçin.")
            return
        grup_id = selected_items[0].data(0, Qt.UserRole)
        yeni_grup_adi = self.urun_grubu_entry.text().strip()
        if not yeni_grup_adi:
            QMessageBox.warning(self, "Uyarı", "Ürün grubu adı boş olamaz.")
            return
        try:
            response = requests.put(f"{API_BASE_URL}/nitelikler/urun_gruplari/{grup_id}", json={"grup_adi": yeni_grup_adi})
            response.raise_for_status()
            QMessageBox.information(self, "Başarılı", "Ürün grubu başarıyla güncellendi.")
            self.urun_grubu_entry.clear()
            self._urun_grubu_listesini_yukle()
            if self.refresh_callback: self.refresh_callback()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Ürün grubu güncellenirken hata: {error_detail}")

    def _urun_grubu_sil_ui(self):
        selected_items = self.urun_grubu_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir ürün grubu seçin.")
            return
        grup_id = selected_items[0].data(0, Qt.UserRole)
        grup_adi = selected_items[0].text(1)
        reply = QMessageBox.question(self, "Onay", f"'{grup_adi}' ürün grubunu silmek istediğinizden emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                response = requests.delete(f"{API_BASE_URL}/nitelikler/urun_gruplari/{grup_id}")
                response.raise_for_status()
                QMessageBox.information(self, "Başarılı", "Ürün grubu başarıyla silindi.")
                self.urun_grubu_entry.clear()
                self._urun_grubu_listesini_yukle()
                if self.refresh_callback: self.refresh_callback()
            except requests.exceptions.RequestException as e:
                error_detail = str(e)
                if e.response is not None:
                    try: error_detail = e.response.json().get('detail', str(e.response.content))
                    except ValueError: pass
                QMessageBox.critical(self, "API Hatası", f"Ürün grubu silinirken hata: {error_detail}")

    # Ürün Birimi Yönetimi Metotları
    def _urun_birimi_listesini_yukle(self):
        self.urun_birimi_tree.clear()
        try:
            response = requests.get(f"{API_BASE_URL}/nitelikler/urun_birimleri")
            response.raise_for_status()
            urun_birimleri = response.json()
            for birim in urun_birimleri:
                item_qt = QTreeWidgetItem(self.urun_birimi_tree)
                item_qt.setText(0, str(birim.get('id')))
                item_qt.setText(1, birim.get('birim_adi'))
                item_qt.setData(0, Qt.UserRole, birim.get('id'))
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Hatası", f"Ürün birimi listesi çekilirken hata: {e}")
            logging.error(f"Ürün birimi listesi yükleme hatası: {e}")

    def _on_urun_birimi_select(self):
        selected_items = self.urun_birimi_tree.selectedItems()
        if selected_items:
            values = selected_items[0].text(1)
            self.urun_birimi_entry.setText(values)
        else:
            self.urun_birimi_entry.clear()

    def _urun_birimi_ekle_ui(self):
        birim_adi = self.urun_birimi_entry.text().strip()
        if not birim_adi:
            QMessageBox.warning(self, "Uyarı", "Ürün birimi adı boş olamaz.")
            return
        try:
            response = requests.post(f"{API_BASE_URL}/nitelikler/urun_birimleri", json={"birim_adi": birim_adi})
            response.raise_for_status()
            QMessageBox.information(self, "Başarılı", "Ürün birimi başarıyla eklendi.")
            self.urun_birimi_entry.clear()
            self._urun_birimi_listesini_yukle()
            if self.refresh_callback: self.refresh_callback()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Ürün birimi eklenirken hata: {error_detail}")

    def _urun_birimi_guncelle_ui(self):
        selected_items = self.urun_birimi_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen güncellemek için bir ürün birimi seçin.")
            return
        birim_id = selected_items[0].data(0, Qt.UserRole)
        yeni_birim_adi = self.urun_birimi_entry.text().strip()
        if not yeni_birim_adi:
            QMessageBox.warning(self, "Uyarı", "Ürün birimi adı boş olamaz.")
            return
        try:
            response = requests.put(f"{API_BASE_URL}/nitelikler/urun_birimleri/{birim_id}", json={"birim_adi": yeni_birim_adi})
            response.raise_for_status()
            QMessageBox.information(self, "Başarılı", "Ürün birimi başarıyla güncellendi.")
            self.urun_birimi_entry.clear()
            self._urun_birimi_listesini_yukle()
            if self.refresh_callback: self.refresh_callback()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Ürün birimi güncellenirken hata: {error_detail}")

    def _urun_birimi_sil_ui(self):
        selected_items = self.urun_birimi_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir ürün birimi seçin.")
            return
        birim_id = selected_items[0].data(0, Qt.UserRole)
        birim_adi = selected_items[0].text(1)
        reply = QMessageBox.question(self, "Onay", f"'{birim_adi}' ürün birimini silmek istediğinizden emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                response = requests.delete(f"{API_BASE_URL}/nitelikler/urun_birimleri/{birim_id}")
                response.raise_for_status()
                QMessageBox.information(self, "Başarılı", "Ürün birimi başarıyla silindi.")
                self.urun_birimi_entry.clear()
                self._urun_birimi_listesini_yukle()
                if self.refresh_callback: self.refresh_callback()
            except requests.exceptions.RequestException as e:
                error_detail = str(e)
                if e.response is not None:
                    try: error_detail = e.response.json().get('detail', str(e.response.content))
                    except ValueError: pass
                QMessageBox.critical(self, "API Hatası", f"Ürün birimi silinirken hata: {error_detail}")

    def _open_urun_grubu_context_menu(self, pos):
        item = self.urun_grubu_tree.itemAt(pos)
        if not item: return

        context_menu = QMenu(self)
        context_menu.addAction("Güncelle").triggered.connect(self._urun_grubu_guncelle_ui)
        context_menu.addAction("Sil").triggered.connect(self._urun_grubu_sil_ui)
        context_menu.exec(self.urun_grubu_tree.mapToGlobal(pos))

    def _open_birim_context_menu(self, pos):
        item = self.urun_birimi_tree.itemAt(pos)
        if not item: return

        context_menu = QMenu(self)
        context_menu.addAction("Güncelle").triggered.connect(self._urun_birimi_guncelle_ui)
        context_menu.addAction("Sil").triggered.connect(self._urun_birimi_sil_ui)
        context_menu.exec(self.urun_birimi_tree.mapToGlobal(pos))

    def _open_ulke_context_menu(self, pos):
        item = self.ulke_tree.itemAt(pos)
        if not item: return

        context_menu = QMenu(self)
        context_menu.addAction("Güncelle").triggered.connect(self._ulke_guncelle_ui)
        context_menu.addAction("Sil").triggered.connect(self._ulke_sil_ui)
        context_menu.exec(self.ulke_tree.mapToGlobal(pos))

    # Ülke (Menşe) Yönetimi Metotları
    def _ulke_listesini_yukle(self):
        self.ulke_tree.clear()
        try:
            response = requests.get(f"{API_BASE_URL}/nitelikler/ulkeler")
            response.raise_for_status()
            ulkeler = response.json()
            for ulke in ulkeler:
                item_qt = QTreeWidgetItem(self.ulke_tree)
                item_qt.setText(0, str(ulke.get('id')))
                item_qt.setText(1, ulke.get('ulke_adi'))
                item_qt.setData(0, Qt.UserRole, ulke.get('id'))
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Hatası", f"Ülke listesi çekilirken hata: {e}")
            logging.error(f"Ülke listesi yükleme hatası: {e}")

    def _on_ulke_select(self):
        selected_items = self.ulke_tree.selectedItems()
        if selected_items:
            values = selected_items[0].text(1)
            self.ulke_entry.setText(values)
        else:
            self.ulke_entry.clear()

    def _ulke_ekle_ui(self):
        ulke_adi = self.ulke_entry.text().strip()
        if not ulke_adi:
            QMessageBox.warning(self, "Uyarı", "Ülke adı boş olamaz.")
            return
        try:
            response = requests.post(f"{API_BASE_URL}/nitelikler/ulkeler", json={"ulke_adi": ulke_adi})
            response.raise_for_status()
            QMessageBox.information(self, "Başarılı", "Ülke başarıyla eklendi.")
            self.ulke_entry.clear()
            self._ulke_listesini_yukle()
            if self.refresh_callback: self.refresh_callback()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Ülke eklenirken hata: {error_detail}")

    def _ulke_guncelle_ui(self):
        selected_items = self.ulke_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen güncellemek için bir ülke seçin.")
            return
        ulke_id = selected_items[0].data(0, Qt.UserRole)
        yeni_ulke_adi = self.ulke_entry.text().strip()
        if not yeni_ulke_adi:
            QMessageBox.warning(self, "Uyarı", "Ülke adı boş olamaz.")
            return
        try:
            response = requests.put(f"{API_BASE_URL}/nitelikler/ulkeler/{ulke_id}", json={"ulke_adi": yeni_ulke_adi})
            response.raise_for_status()
            QMessageBox.information(self, "Başarılı", "Ülke başarıyla güncellendi.")
            self.ulke_entry.clear()
            self._ulke_listesini_yukle()
            if self.refresh_callback: self.refresh_callback()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Ülke güncellenirken hata: {error_detail}")

    def _ulke_sil_ui(self):
        selected_items = self.ulke_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir ülke seçin.")
            return
        ulke_id = selected_items[0].data(0, Qt.UserRole)
        ulke_adi = selected_items[0].text(1)
        reply = QMessageBox.question(self, "Onay", f"'{ulke_adi}' ülkesini silmek istediğinizden emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                response = requests.delete(f"{API_BASE_URL}/nitelikler/ulkeler/{ulke_id}")
                response.raise_for_status()
                QMessageBox.information(self, "Başarılı", "Ülke başarıyla silindi.")
                self.ulke_entry.clear()
                self._ulke_listesini_yukle()
                if self.refresh_callback: self.refresh_callback()
            except requests.exceptions.RequestException as e:
                error_detail = str(e)
                if e.response is not None:
                    try: error_detail = e.response.json().get('detail', str(e.response.content))
                    except ValueError: pass
                QMessageBox.critical(self, "API Hatası", f"Ülke silinirken hata: {error_detail}")

    def _yukle_kategori_marka_comboboxlari(self):
        # Kategoriler
        try:
            response = requests.get(f"{API_BASE_URL}/nitelikler/kategoriler")
            response.raise_for_status()
            kategoriler = response.json()
            self.kategoriler_map = {"Seçim Yok": None}
            kategori_display_values = ["Seçim Yok"]
            for k in kategoriler:
                self.kategoriler_map[k.get('kategori_adi')] = k.get('id')
                kategori_display_values.append(k.get('kategori_adi'))
        except requests.exceptions.RequestException as e:
            logging.error(f"Kategoriler combobox yüklenirken hata: {e}")

        # Markalar
        try:
            response = requests.get(f"{API_BASE_URL}/nitelikler/markalar")
            response.raise_for_status()
            markalar = response.json()
            self.markalar_map = {"Seçim Yok": None}
            marka_display_values = ["Seçim Yok"]
            for m in markalar:
                self.markalar_map[m.get('marka_adi')] = m.get('id')
                marka_display_values.append(m.get('marka_adi'))
        except requests.exceptions.RequestException as e:
            logging.error(f"Markalar combobox yüklenirken hata: {e}")


    def _yukle_urun_grubu_birimi_ulke_comboboxlari(self):
        # Ürün Grupları
        try:
            response = requests.get(f"{API_BASE_URL}/nitelikler/urun_gruplari")
            response.raise_for_status()
            urun_gruplari = response.json()
            self.urun_gruplari_map = {"Seçim Yok": None}
            urun_grubu_display_values = ["Seçim Yok"]
            for g in urun_gruplari:
                self.urun_gruplari_map[g.get('grup_adi')] = g.get('id')
                urun_grubu_display_values.append(g.get('grup_adi'))
        except requests.exceptions.RequestException as e:
            logging.error(f"Ürün grupları combobox yüklenirken hata: {e}")

        # Ürün Birimleri
        try:
            response = requests.get(f"{API_BASE_URL}/nitelikler/urun_birimleri")
            response.raise_for_status()
            urun_birimleri = response.json()
            self.urun_birimleri_map = {"Seçim Yok": None}
            urun_birimi_display_values = ["Seçim Yok"]
            for b in urun_birimleri:
                self.urun_birimleri_map[b.get('birim_adi')] = b.get('id')
                urun_birimi_display_values.append(b.get('birim_adi'))
        except requests.exceptions.RequestException as e:
            logging.error(f"Ürün birimleri combobox yüklenirken hata: {e}")

        # Ülkeler (Menşe)
        try:
            response = requests.get(f"{API_BASE_URL}/nitelikler/ulkeler")
            response.raise_for_status()
            ulkeler = response.json()
            self.ulkeler_map = {"Seçim Yok": None}
            ulke_display_values = ["Seçim Yok"]
            for u in ulkeler:
                self.ulkeler_map[u.get('ulke_adi')] = u.get('id')
                ulke_display_values.append(u.get('ulke_adi'))
        except requests.exceptions.RequestException as e:
            logging.error(f"Ülkeler combobox yüklenirken hata: {e}")

class StokKartiPenceresi(QDialog):
    data_updated = Signal() # Veri güncellendiğinde ana pencereye sinyal göndermek için

    # __init__ metodunu sizin sağladığınız yapıya göre güncelledim
    def __init__(self, parent=None, db_manager=None, stok_duzenle=None, app_ref=None):
        super().__init__(parent)
        self.db = db_manager # API tabanlı db_manager
        self.app = app_ref # setup_numeric_entry için tutuluyor, ancak kaldırılacak
        self.stok_duzenle_data = stok_duzenle # Düzenlenecek stokun verileri
        self.stok_id = self.stok_duzenle_data.get('id') if self.stok_duzenle_data else None

        title = "Yeni Stok Kartı" if not self.stok_id else f"Stok Düzenle: {self.stok_duzenle_data.get('ad', '')}"
        self.setWindowTitle(title)
        self.setMinimumSize(950, 750)
        self.setModal(True)

        # Arayüz elemanları için sözlükler
        self.entries = {}
        self.combos = {}
        self.combo_maps = {'kategori': {}, 'marka': {}, 'urun_grubu': {}, 'urun_birimi': {}, 'mense': {}}
        self.label_kar_orani = QLabel("% 0,00")
        self.urun_resmi_label = QLabel("Resim Yok") # İsim değişmedi, UI'da böyle kalabilir
        self.original_pixmap = None
        self.urun_resmi_path = "" # Veritabanında (API üzerinden) saklanacak resim yolu
        
        self.main_layout = QVBoxLayout(self)
        self.notebook = QTabWidget()
        self.main_layout.addWidget(self.notebook)

        self._create_genel_bilgiler_tab()
        self._create_placeholder_tabs()
        self._add_bottom_buttons()
        
        self._set_validators_and_signals() # Validator ve sinyal bağlantılarını burada kur
        self._verileri_yukle()
        self.entries['ad'].setFocus() # 'urun_adi' yerine 'ad' kullanıldı

    def _create_genel_bilgiler_tab(self):
        tab_genel = QWidget()
        layout_genel = QGridLayout(tab_genel)
        self.notebook.addTab(tab_genel, "Genel Bilgiler")

        left_panel_vbox = QVBoxLayout()
        right_panel_vbox = QVBoxLayout()
        layout_genel.addLayout(left_panel_vbox, 0, 0)
        layout_genel.addLayout(right_panel_vbox, 0, 1)
        layout_genel.setColumnStretch(0, 3)
        layout_genel.setColumnStretch(1, 1)

        gbox_temel = QGroupBox("Temel Stok Bilgileri") # "Ürün" yerine "Stok"
        ltemel = QGridLayout(gbox_temel)
        self.entries['kod'] = QLineEdit(); self.entries['kod'].setReadOnly(True) # 'urun_kodu' yerine 'kod'
        self.entries['ad'] = QLineEdit() # 'urun_adi' yerine 'ad'
        self.entries['detay'] = QTextEdit(); self.entries['detay'].setFixedHeight(60) # 'urun_detayi' yerine 'detay'
        ltemel.addWidget(QLabel("Stok Kodu:"), 0, 0); ltemel.addWidget(self.entries['kod'], 0, 1)
        ltemel.addWidget(QLabel("Stok Adı (*):"), 0, 2); ltemel.addWidget(self.entries['ad'], 0, 3)
        ltemel.addWidget(QLabel("Stok Detayı:"), 1, 0, alignment=Qt.AlignTop); ltemel.addWidget(self.entries['detay'], 1, 1, 1, 3)
        left_panel_vbox.addWidget(gbox_temel)

        gbox_fiyat = QGroupBox("Fiyatlandırma Bilgileri")
        lfiyat = QGridLayout(gbox_fiyat)
        self.entries['alis_fiyati'] = QLineEdit("0,00") # 'alis_fiyati_kdv_haric' yerine 'alis_fiyati' (API'de tek fiyat var)
        self.entries['satis_fiyati'] = QLineEdit("0,00") # 'satis_fiyati_kdv_haric' yerine 'satis_fiyati' (API'de tek fiyat var)
        self.entries['kdv_orani'] = QLineEdit("20"); self.label_kar_orani.setFont(QFont("Segoe UI", 9, QFont.Bold))
        
        # API'de KDV dahil/hariç ayrımı yok, tek fiyat alanı var.
        # Bu yüzden UI'daki KDV dahil/hariç inputlarını tek inputa düşürdüm.
        # Eğer API'de KDV dahil/hariç fiyatlar ayrı ayrı tutuluyorsa, API şemasının güncellenmesi gerekir.
        # Şu anki API şemasına göre 'alis_fiyati' ve 'satis_fiyati' var.
        lfiyat.addWidget(QLabel("Alış Fiyatı:"), 0, 0); lfiyat.addWidget(self.entries['alis_fiyati'], 0, 1)
        lfiyat.addWidget(QLabel("Satış Fiyatı:"), 1, 0); lfiyat.addWidget(self.entries['satis_fiyati'], 1, 1)
        lfiyat.addWidget(QLabel("KDV Oranı (%):"), 2, 0); lfiyat.addWidget(self.entries['kdv_orani'], 2, 1)
        lfiyat.addWidget(QLabel("Kar Oranı:"), 2, 2); lfiyat.addWidget(self.label_kar_orani, 2, 3)
        left_panel_vbox.addWidget(gbox_fiyat)

        gbox_nitelik = QGroupBox("Ek Nitelikler"); lnitelik = QGridLayout(gbox_nitelik)
        self.combos['kategori'] = QComboBox(); self.combos['marka'] = QComboBox()
        self.combos['urun_grubu'] = QComboBox(); self.combos['birim'] = QComboBox(); self.combos['mense'] = QComboBox() # 'urun_birimi' yerine 'birim'
        lnitelik.addWidget(QLabel("Kategori:"), 0, 0); lnitelik.addWidget(self.combos['kategori'], 0, 1)
        lnitelik.addWidget(QLabel("Marka:"), 0, 2); lnitelik.addWidget(self.combos['marka'], 0, 3)
        lnitelik.addWidget(QLabel("Ürün Grubu:"), 1, 0); lnitelik.addWidget(self.combos['urun_grubu'], 1, 1)
        lnitelik.addWidget(QLabel("Birim:"), 1, 2); lnitelik.addWidget(self.combos['birim'], 1, 3) # 'Ürün Birimi' yerine 'Birim'
        lnitelik.addWidget(QLabel("Menşe:"), 2, 0); lnitelik.addWidget(self.combos['mense'], 2, 1)
        left_panel_vbox.addWidget(gbox_nitelik); left_panel_vbox.addStretch()

        gbox_stok_sag = QGroupBox("Stok Durumu"); layout_stok_sag = QGridLayout(gbox_stok_sag)
        self.entries['stok_miktari'] = QLineEdit("0,00"); self.entries['stok_miktari'].setReadOnly(True)
        self.entries['min_stok_seviyesi'] = QLineEdit("0,00")
        layout_stok_sag.addWidget(QLabel("Mevcut Stok:"), 0, 0); layout_stok_sag.addWidget(self.entries['stok_miktari'], 0, 1)
        layout_stok_sag.addWidget(QLabel("Min. Stok Seviyesi:"), 1, 0); layout_stok_sag.addWidget(self.entries['min_stok_seviyesi'], 1, 1)
        right_panel_vbox.addWidget(gbox_stok_sag)

        gbox_gorsel = QGroupBox("Stok Görseli"); layout_gorsel = QVBoxLayout(gbox_gorsel) # "Ürün Görseli" yerine "Stok Görseli"
        self.urun_resmi_label.setAlignment(Qt.AlignCenter); self.urun_resmi_label.setMinimumSize(200, 200)
        self.urun_resmi_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored); self.urun_resmi_label.setStyleSheet("border: 1px solid grey;")
        layout_gorsel.addWidget(self.urun_resmi_label)
        btn_gorsel_layout = QHBoxLayout(); btn_resim_sec = QPushButton("Resim Seç"); btn_resim_sec.clicked.connect(self._resim_sec)
        btn_resim_sil = QPushButton("Resmi Sil"); btn_resim_sil.clicked.connect(self._resim_sil)
        btn_gorsel_layout.addWidget(btn_resim_sec); btn_gorsel_layout.addWidget(btn_resim_sil)
        layout_gorsel.addLayout(btn_gorsel_layout)
        right_panel_vbox.addWidget(gbox_gorsel)
        
        gbox_operasyon = QGroupBox("Operasyonlar"); layout_operasyon = QVBoxLayout(gbox_operasyon)
        btn_stok_ekle = QPushButton("Stok Ekle"); btn_stok_ekle.clicked.connect(self._stok_ekle_penceresi_ac)
        btn_stok_eksilt = QPushButton("Stok Eksilt"); btn_stok_eksilt.clicked.connect(self._stok_eksilt_penceresi_ac)
        layout_operasyon.addWidget(btn_stok_ekle); layout_operasyon.addWidget(btn_stok_eksilt)
        right_panel_vbox.addWidget(gbox_operasyon)
        right_panel_vbox.addStretch()

    def _create_placeholder_tabs(self):
        # Bu sekmelerin içeriği, arayuz.py'deki ilgili sınıfın PySide6'ya dönüştürülmesinden sonra eklenecektir.
        self.notebook.addTab(QWidget(), "Stok Hareketleri") 
        self.notebook.addTab(QWidget(), "İlgili Faturalar") 
        # Nitelik Yönetimi sekmesi ayrı bir pencereye taşındığı için burada placeholder olarak tutulmayabilir.
        self.notebook.addTab(QLabel("Nitelik yönetimi ayrı bir pencereye taşınmıştır."), "Nitelik Yönetimi")

    def _add_bottom_buttons(self):
        button_layout = QHBoxLayout()
        self.btn_sil = QPushButton("Stoku Sil"); self.btn_sil.clicked.connect(self._stok_sil); self.btn_sil.setVisible(bool(self.stok_id))
        button_layout.addWidget(self.btn_sil, alignment=Qt.AlignLeft)
        button_layout.addStretch()
        self.kaydet_button = QPushButton("Kaydet"); self.kaydet_button.clicked.connect(self.kaydet)
        button_layout.addWidget(self.kaydet_button)
        iptal_button = QPushButton("İptal"); iptal_button.clicked.connect(self.reject)
        button_layout.addWidget(iptal_button)
        self.main_layout.addLayout(button_layout)

    def _set_validators_and_signals(self):
        # Sayısal alanlar için validator'lar
        double_validator = QDoubleValidator(0.0, 999999999.0, 2, self)
        double_validator.setNotation(QDoubleValidator.StandardNotation)
        
        self.entries['alis_fiyati'].setValidator(double_validator)
        self.entries['satis_fiyati'].setValidator(double_validator)
        self.entries['min_stok_seviyesi'].setValidator(double_validator)
        self.entries['stok_miktari'].setValidator(double_validator) # ReadOnly olmasına rağmen validator olsun
        
        # KDV oranı için int validator
        int_validator = QIntValidator(0, 100)
        self.entries['kdv_orani'].setValidator(int_validator)

        # Otomatik fiyat hesaplama için sinyal-slot bağlantıları
        # API'de KDV dahil/hariç fiyat ayrımı olmadığı için bu kısım sadeleştirildi.
        # Sadece KDV oranı değiştiğinde kar oranını yeniden hesapla.
        self.entries['alis_fiyati'].textChanged.connect(self._calculate_kar_orani)
        self.entries['satis_fiyati'].textChanged.connect(self._calculate_kar_orani)
        self.entries['kdv_orani'].textChanged.connect(self._calculate_kar_orani)

        # Klavye navigasyonu (Enter tuşu ile odak değiştirme)
        self.entries['ad'].returnPressed.connect(self.entries['min_stok_seviyesi'].setFocus)
        self.entries['min_stok_seviyesi'].returnPressed.connect(self.entries['alis_fiyati'].setFocus)
        self.entries['alis_fiyati'].returnPressed.connect(self.entries['satis_fiyati'].setFocus)
        self.entries['satis_fiyati'].returnPressed.connect(self.kaydet_button.setFocus)
        
    def _verileri_yukle(self):
        self._yukle_combobox_verileri()
        if self.stok_duzenle_data:
            # API'den gelen veriye göre alanları doldur
            self.entries['kod'].setText(self.stok_duzenle_data.get('kod', ''))
            self.entries['ad'].setText(self.stok_duzenle_data.get('ad', ''))
            self.entries['detay'].setPlainText(self.stok_duzenle_data.get('detay', ''))
            self.entries['alis_fiyati'].setText(f"{self.stok_duzenle_data.get('alis_fiyati', 0.0):.2f}".replace('.',','))
            self.entries['satis_fiyati'].setText(f"{self.stok_duzenle_data.get('satis_fiyati', 0.0):.2f}".replace('.',','))
            self.entries['kdv_orani'].setText(f"{self.stok_duzenle_data.get('kdv_orani', 0):.0f}") # API'den gelen KDV oranı
            self.entries['stok_miktari'].setText(f"{self.stok_duzenle_data.get('stok_miktari', 0.0):.2f}".replace('.',','))
            self.entries['min_stok_seviyesi'].setText(f"{self.stok_duzenle_data.get('min_stok_seviyesi', 0.0):.2f}".replace('.',','))
            
            self.urun_resmi_path = self.stok_duzenle_data.get('urun_resmi_yolu') # API'den gelen resim yolu
            self._load_urun_resmi()
            QTimer.singleShot(150, self._set_combobox_defaults)
            self._calculate_kar_orani() # Kar oranını yüklenen verilere göre hesapla
        else:
            # Yeni stok için kod otomatik API tarafından atanacaksa boş bırakılır,
            # aksi takdirde manuel giriş veya db.get_next_stok_kodu() gibi bir API çağrısı gerekir.
            # Şu anki API'nin stok kodu otomatik atadığını varsayıyoruz.
            self.entries['kod'].setText("Otomatik Atanacak") # Kullanıcıya bilgi ver
            self.entries['kod'].setReadOnly(True) # Kodu manuel değiştirmeyi engelle
    
    def _set_combobox_defaults(self):
        if not self.stok_duzenle_data: return
        
        # Nitelik tiplerini ve ilgili combobox'ları eşle
        nitelik_tipleri_map = {
            'kategori': 'kategori_id',
            'marka': 'marka_id',
            'urun_grubu': 'urun_grubu_id',
            'birim': 'birim_id', # 'urun_birimi_id' yerine 'birim_id'
            'mense': 'mense_id'
        }

        for combo_key, data_key in nitelik_tipleri_map.items():
            combo = self.combos[combo_key]
            target_id = self.stok_duzenle_data.get(data_key)
            if target_id is not None:
                # findData, userData ile eşleşir
                index = combo.findData(target_id)
                if index != -1:
                    combo.setCurrentIndex(index)
                else:
                    logger.warning(f"Combobox '{combo_key}' için ID '{target_id}' bulunamadı.")
    
    def _yukle_combobox_verileri(self):
        """API'den tüm nitelikleri çeker ve ilgili combobox'lara doldurur."""
        try:
            all_nitelikler = self.db.nitelik_listesi_al()
        except Exception as e:
            logger.error(f"Nitelik verileri çekilemedi: {e}")
            QMessageBox.warning(self, "Hata", f"Nitelik verileri yüklenirken bir hata oluştu: {e}")
            return

        # Nitelik tiplerini ve ilgili combobox'ları eşle
        nitelik_tipleri_map = {
            'kategori': 'Kategori',
            'marka': 'Marka',
            'urun_grubu': 'Ürün Grubu',
            'birim': 'Birim', # API'deki değer tipi 'Birim' olmalı
            'mense': 'Menşe' # API'deki değer tipi 'Menşe' olmalı
        }

        for combo_key, nitelik_tipi in nitelik_tipleri_map.items():
            combo = self.combos[combo_key]
            combo.clear()
            combo.addItem("Seçim Yok", None) # İlk öğe olarak "Seçim Yok" ekle

            filtered_nitelikler = [n for n in all_nitelikler if n.get('deger_tipi') == nitelik_tipi]
            
            for item in filtered_nitelikler:
                # Nitelik objesinde 'ad' alanı olduğunu varsayıyoruz
                item_ad = item.get('ad')
                item_id = item.get('id')
                if item_ad and item_id is not None:
                    combo.addItem(item_ad, item_id)
            logger.info(f"{nitelik_tipi} combobox başarıyla yüklendi.")

    # Otomatik fiyat doldurma fonksiyonları sadeleştirildi, çünkü API'de tek fiyat alanı var
    def _calculate_kar_orani(self):
        """Alış ve satış fiyatlarına göre kar oranını hesaplar."""
        try:
            alis_fiyati_str = self.entries['alis_fiyati'].text().replace(',', '.'); alis_fiyati = float(alis_fiyati_str) if alis_fiyati_str else 0.0
            satis_fiyati_str = self.entries['satis_fiyati'].text().replace(',', '.'); satis_fiyati = float(satis_fiyati_str) if satis_fiyati_str else 0.0
            
            # KDV oranı da kar oranını etkileyebilir, ancak API'de KDV dahil/hariç fiyat ayrımı kaldırıldı.
            # Eğer KDV'nin kar oranına etkisi hesaplanacaksa, bu mantık buraya eklenebilir.
            # Şu an için sadece alış ve satış fiyatları üzerinden basit kar oranı hesaplanıyor.
            
            kar_orani = ((satis_fiyati - alis_fiyati) / alis_fiyati) * 100 if alis_fiyati > 0 else 0.0
            self.label_kar_orani.setText(f"% {kar_orani:,.2f}".replace('.',','))
        except (ValueError, ZeroDivisionError):
            self.label_kar_orani.setText("Hesaplanamadı")
            logger.warning("Kar oranı hesaplanırken hata oluştu (geçersiz değer veya sıfıra bölme).")

    def kaydet(self):
        """Formdaki bilgileri toplayıp API üzerinden stok ekler veya günceller."""
        if not self.entries['ad'].text().strip(): # 'urun_adi' yerine 'ad'
            QMessageBox.warning(self, "Eksik Bilgi", "Stok Adı alanı boş bırakılamaz."); return
        
        data = {}
        try:
            for key, widget in self.entries.items():
                if key == 'kod' and not self.stok_id: # Yeni ürün eklerken kodu gönderme, API atayacak
                    continue
                text_value = widget.text() if isinstance(widget, QLineEdit) else widget.toPlainText()
                if any(substr in key for substr in ['fiyati', 'stok', 'seviye', 'kdv']): # 'fiyat' yerine 'fiyati'
                    data[key] = float(text_value.replace(',', '.') if text_value else 0.0)
                else:
                    data[key] = text_value.strip()
            
            # Combobox'lardan seçilen nitelik ID'lerini ekle
            data['kategori_id'] = self.combos['kategori'].currentData()
            data['marka_id'] = self.combos['marka'].currentData()
            data['urun_grubu_id'] = self.combos['urun_grubu'].currentData()
            data['birim_id'] = self.combos['birim'].currentData() # 'urun_birimi_id' yerine 'birim_id'
            data['mense_id'] = self.combos['mense'].currentData()

        except ValueError:
            QMessageBox.critical(self, "Geçersiz Değer", "Lütfen sayısal alanları doğru formatta girin."); return
        
        data['urun_resmi_yolu'] = self.urun_resmi_path # Resim yolu veri tabanına kaydedilecek

        try:
            if self.stok_id:
                # Mevcut stoku güncelle
                response = self.db.stok_guncelle(self.stok_id, data)
            else:
                # Yeni stok ekle
                response = self.db.stok_ekle(data)
            
            QMessageBox.information(self, "Başarılı", "Stok bilgileri başarıyla kaydedildi.")
            self.data_updated.emit() # Ana pencereye veri güncellendi sinyali gönder
            self.accept() # Pencereyi kapat
            logger.info(f"Stok kaydedildi/güncellendi: ID {self.stok_id if self.stok_id else 'Yeni'}")
        except Exception as e:
            error_message = f"Stok kaydedilirken bir hata oluştu: {e}"
            QMessageBox.critical(self, "API Hatası", error_message)
            logger.error(f"Stok kaydetme/güncelleme hatası: {e}", exc_info=True)

    def _stok_sil(self): # 'urun_sil' yerine '_stok_sil'
        """Seçili stoku API üzerinden siler."""
        if not self.stok_id:
            QMessageBox.warning(self, "Uyarı", "Silinecek bir stok seçilmedi."); return
        
        reply = QMessageBox.question(self, "Onay", f"'{self.entries['ad'].text()}' stokunu silmek istediğinizden emin misiniz?", # 'urun_adi' yerine 'ad'
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db.stok_sil(self.stok_id)
                QMessageBox.information(self, "Başarılı", "Stok başarıyla silindi.")
                self.data_updated.emit()
                self.accept()
                logger.info(f"Stok silindi: ID {self.stok_id}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Stok silinirken bir hata oluştu: {e}")
                logger.error(f"Stok silme hatası: {e}", exc_info=True)

    def _resim_sec(self):
        """Ürün resmi seçme ve kopyalama işlemi."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Stok Resmi Seç", "", "Resim Dosyaları (*.png *.jpg *.jpeg)")
        if file_path:
            try:
                # Resim dosyalarını uygulamanın 'data/urun_resimleri' klasörüne kopyala
                # Bu kısım, API'nin resim yükleme endpoint'i varsa gelecekte değiştirilmelidir.
                # Şimdilik yerel dosya kopyalama devam ediyor.
                base_dir = os.path.dirname(os.path.abspath(__file__)) # pencereler.py'nin bulunduğu dizin
                data_dir = os.path.join(base_dir, 'data') # data klasörü
                urun_resimleri_klasoru = os.path.join(data_dir, "urun_resimleri")
                
                os.makedirs(urun_resimleri_klasoru, exist_ok=True)
                yeni_path = os.path.join(urun_resimleri_klasoru, os.path.basename(file_path))
                shutil.copy2(file_path, yeni_path)
                self.urun_resmi_path = yeni_path
                logger.info(f"Resim kopyalandı: {yeni_path}")
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Resim kopyalanamadı: {e}")
                logger.error(f"Resim kopyalama hatası: {e}", exc_info=True)
                self.urun_resmi_path = "" # Hata durumunda yolu temizle
            self._load_urun_resmi()

    def _resim_sil(self):
        """Ürün resmini temizler."""
        self.urun_resmi_path = ""
        self._load_urun_resmi()
        logger.info("Ürün resmi silindi.")
    
    def _load_urun_resmi(self):
        """Kaydedilen resim yolundan resmi yükler ve QLabel'de gösterir."""
        if self.urun_resmi_path and os.path.exists(self.urun_resmi_path):
            self.original_pixmap = QPixmap(self.urun_resmi_path)
            self._resize_image()
            self.urun_resmi_label.setText("") # Resim varsa metni temizle
            logger.debug(f"Resim yüklendi: {self.urun_resmi_path}")
        else:
            self.original_pixmap = None
            self.urun_resmi_label.setText("Resim Yok")
            self.urun_resmi_label.setPixmap(QPixmap()) # Pixmap'i temizle
            logger.debug("Resim yok veya bulunamadı.")

    def resizeEvent(self, event):
        """Pencere boyutu değiştiğinde resmi yeniden boyutlandırır."""
        super().resizeEvent(event)
        QTimer.singleShot(50, self._resize_image) # Küçük bir gecikme ekle

    def _resize_image(self):
        """Resmi QLabel boyutuna göre ölçekler."""
        if self.original_pixmap and not self.original_pixmap.isNull():
            scaled_pixmap = self.original_pixmap.scaled(self.urun_resmi_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.urun_resmi_label.setPixmap(scaled_pixmap)
            
    def _stok_ekle_penceresi_ac(self):
        """Stok ekleme penceresini açar."""
        if not self.stok_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce stoku kaydedin.")
            return
        
        # Güncel stok miktarını API'den çekerek al
        try:
            current_stok_data = self.db.stok_getir_by_id(self.stok_id)
            mevcut_stok = current_stok_data.get('stok_miktari', 0.0)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Mevcut stok miktarı alınırken hata oluştu: {e}")
            logger.error(f"Stok miktarı alınırken hata: {e}", exc_info=True)
            return

        from pencereler import StokHareketiPenceresi # Döngüsel bağımlılığı önlemek için burada import edildi
        dialog = StokHareketiPenceresi(
            self, # parent
            self.db, # db_manager
            self.stok_id,
            self.entries['ad'].text(), # 'urun_adi' yerine 'ad'
            mevcut_stok,
            "EKLE",
            self.refresh_data_and_ui # Bu pencereyi yenileyecek callback
        )
        dialog.exec()
        
    def _stok_eksilt_penceresi_ac(self):
        """Stok eksiltme penceresini açar."""
        if not self.stok_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce stoku kaydedin.")
            return

        # Güncel stok miktarını API'den çekerek al
        try:
            current_stok_data = self.db.stok_getir_by_id(self.stok_id)
            mevcut_stok = current_stok_data.get('stok_miktari', 0.0)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Mevcut stok miktarı alınırken hata oluştu: {e}")
            logger.error(f"Stok miktarı alınırken hata: {e}", exc_info=True)
            return
        
        from pencereler import StokHareketiPenceresi # Döngüsel bağımlılığı önlemek için burada import edildi
        dialog = StokHareketiPenceresi(
            self, # parent
            self.db, # db_manager
            self.stok_id,
            self.entries['ad'].text(), # 'urun_adi' yerine 'ad'
            mevcut_stok,
            "EKSILT",
            self.refresh_data_and_ui # Bu pencereyi yenileyecek callback
        )
        dialog.exec()

    def refresh_data_and_ui(self):
        """Stok kartı verilerini yeniden yükler ve UI'ı günceller."""
        if not self.stok_id: return # Stok ID yoksa yenileme yapma

        try:
            # API'den ürünün güncel verilerini çek
            updated_stok_data = self.db.stok_getir_by_id(self.stok_id)

            # UI elementlerini güncel verilerle doldur
            self.entries['stok_miktari'].setText(f"{updated_stok_data.get('stok_miktari', 0.0):.2f}".replace('.',','))
            self.entries['min_stok_seviyesi'].setText(f"{updated_stok_data.get('min_stok_seviyesi', 0.0):.2f}".replace('.',','))
            
            # Diğer ilgili alanları da güncelleyebilirsiniz
            self.entries['alis_fiyati'].setText(f"{updated_stok_data.get('alis_fiyati', 0.0):.2f}".replace('.',','))
            self.entries['satis_fiyati'].setText(f"{updated_stok_data.get('satis_fiyati', 0.0):.2f}".replace('.',','))
            self.entries['kdv_orani'].setText(f"{updated_stok_data.get('kdv_orani', 0):.0f}")

            # Kar oranını yeniden hesapla
            self._calculate_kar_orani()

            # Dışarıdaki listeyi de yenile (main.py'deki _initial_load_data gibi)
            self.data_updated.emit()
                
            QMessageBox.information(self, "Başarılı", "Stok verileri güncellendi.")
            logger.info(f"Stok kartı verileri yenilendi: ID {self.stok_id}")

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Stok verileri yenilenirken hata oluştu:\n{e}")
            logger.error(f"StokKartiPenceresi refresh_data_and_ui hatası: {e}", exc_info=True)


class YeniKasaBankaEklePenceresi(QDialog):
    def __init__(self, parent, db_manager, yenile_callback, hesap_duzenle=None, app_ref=None):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.yenile_callback = yenile_callback
        self.hesap_duzenle_data = hesap_duzenle

        self.hesap_duzenle_id = self.hesap_duzenle_data.get('id') if self.hesap_duzenle_data else None

        title = "Yeni Kasa/Banka Hesabı" if not self.hesap_duzenle_id else "Hesap Düzenle"
        self.setWindowTitle(title)
        self.setMinimumSize(480, 450)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        main_layout.addWidget(title_label)

        form_layout = QGridLayout()
        main_layout.addLayout(form_layout)
        
        self.entries = {}
        self.odeme_turleri = ["YOK", "NAKİT", "KART", "EFT/HAVALE", "ÇEK", "SENET", "AÇIK HESAP"]
        
        # Form elemanları
        form_layout.addWidget(QLabel("Hesap Adı (*):"), 0, 0)
        self.entries['hesap_adi'] = QLineEdit()
        form_layout.addWidget(self.entries['hesap_adi'], 0, 1)

        form_layout.addWidget(QLabel("Hesap Tipi (*):"), 1, 0)
        self.entries['tip'] = QComboBox()
        self.entries['tip'].addItems(["KASA", "BANKA"])
        self.entries['tip'].currentTextChanged.connect(self._tip_degisince_banka_alanlarini_ayarla)
        form_layout.addWidget(self.entries['tip'], 1, 1)

        self.banka_labels = {
            'banka_adi': QLabel("Banka Adı:"),
            'sube_adi': QLabel("Şube Adı:"),
            'hesap_no': QLabel("Hesap No/IBAN:")
        }
        form_layout.addWidget(self.banka_labels['banka_adi'], 2, 0)
        self.entries['banka_adi'] = QLineEdit()
        form_layout.addWidget(self.entries['banka_adi'], 2, 1)
        
        form_layout.addWidget(self.banka_labels['sube_adi'], 3, 0)
        self.entries['sube_adi'] = QLineEdit()
        form_layout.addWidget(self.entries['sube_adi'], 3, 1)

        form_layout.addWidget(self.banka_labels['hesap_no'], 4, 0)
        self.entries['hesap_no'] = QLineEdit()
        form_layout.addWidget(self.entries['hesap_no'], 4, 1)
        
        form_layout.addWidget(QLabel("Açılış Bakiyesi:"), 5, 0)
        self.entries['bakiye'] = QLineEdit("0,00")
        setup_numeric_entry(self.app, self.entries['bakiye'], decimal_places=2) # setup_numeric_entry'ye self.app geçildi
        form_layout.addWidget(self.entries['bakiye'], 5, 1)

        form_layout.addWidget(QLabel("Para Birimi:"), 6, 0)
        self.entries['para_birimi'] = QLineEdit("TL")
        form_layout.addWidget(self.entries['para_birimi'], 6, 1)

        form_layout.addWidget(QLabel("Varsayılan Ödeme Türü:"), 7, 0)
        self.entries['varsayilan_odeme_turu'] = QComboBox()
        self.entries['varsayilan_odeme_turu'].addItems(self.odeme_turleri)
        form_layout.addWidget(self.entries['varsayilan_odeme_turu'], 7, 1)

        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)
        button_layout.addStretch()
        kaydet_button = QPushButton("Kaydet")
        kaydet_button.clicked.connect(self.kaydet)
        button_layout.addWidget(kaydet_button)
        iptal_button = QPushButton("İptal")
        iptal_button.clicked.connect(self.reject)
        button_layout.addWidget(iptal_button)
        
        self._verileri_yukle()
        self._tip_degisince_banka_alanlarini_ayarla()

    def _tip_degisince_banka_alanlarini_ayarla(self):
        is_banka = self.entries['tip'].currentText() == "BANKA"
        for key, widget in self.banka_labels.items():
            widget.setVisible(is_banka)
        for key in ['banka_adi', 'sube_adi', 'hesap_no']:
            self.entries[key].setVisible(is_banka)
        if not is_banka:
            for key in ['banka_adi', 'sube_adi', 'hesap_no']:
                self.entries[key].clear()

    def _verileri_yukle(self):
        if self.hesap_duzenle_data:
            self.entries['hesap_adi'].setText(self.hesap_duzenle_data.get('hesap_adi', ''))
            self.entries['tip'].setCurrentText(self.hesap_duzenle_data.get('tip', 'KASA'))
            self.entries['banka_adi'].setText(self.hesap_duzenle_data.get('banka_adi', ''))
            self.entries['sube_adi'].setText(self.hesap_duzenle_data.get('sube_adi', ''))
            self.entries['hesap_no'].setText(self.hesap_duzenle_data.get('hesap_no', ''))
            bakiye = self.hesap_duzenle_data.get('bakiye', 0.0)
            self.entries['bakiye'].setText(f"{bakiye:.2f}".replace('.', ','))
            self.entries['para_birimi'].setText(self.hesap_duzenle_data.get('para_birimi', 'TL'))
            varsayilan_odeme_turu = self.hesap_duzenle_data.get('varsayilan_odeme_turu')
            self.entries['varsayilan_odeme_turu'].setCurrentText(varsayilan_odeme_turu if varsayilan_odeme_turu else "YOK")
            self.entries['bakiye'].setReadOnly(True) # Açılış bakiyesi düzenlemede değiştirilemez

    def kaydet(self):
        hesap_adi = self.entries['hesap_adi'].text().strip()
        if not hesap_adi:
            QMessageBox.warning(self, "Eksik Bilgi", "Hesap Adı alanı boş bırakılamaz.")
            return

        bakiye_str = self.entries['bakiye'].text().replace(',', '.')
        
        data = {
            "hesap_adi": hesap_adi,
            "tip": self.entries['tip'].currentText(),
            "bakiye": float(bakiye_str) if bakiye_str else 0.0,
            "banka_adi": self.entries['banka_adi'].text().strip(),
            "sube_adi": self.entries['sube_adi'].text().strip(),
            "hesap_no": self.entries['hesap_no'].text().strip(),
            "para_birimi": self.entries['para_birimi'].text().strip(),
            "varsayilan_odeme_turu": self.entries['varsayilan_odeme_turu'].currentText()
        }
        if data["varsayilan_odeme_turu"] == "YOK":
            data["varsayilan_odeme_turu"] = None

        try:
            if self.hesap_duzenle_id:
                # GÜNCELLEME (PUT isteği)
                success = self.db.kasa_banka_guncelle(self.hesap_duzenle_id, data)
            else:
                # YENİ KAYIT (POST isteği)
                success = self.db.kasa_banka_ekle(data)

            if success:
                QMessageBox.information(self, "Başarılı", "Kasa/Banka hesabı başarıyla kaydedildi.")
                if self.yenile_callback:
                    self.yenile_callback()
                self.accept()
            else:
                QMessageBox.critical(self, "Hata", "Kasa/Banka hesabı kaydedilirken bir hata oluştu.")

        except Exception as e:
            error_detail = str(e)
            QMessageBox.critical(self, "Hata", f"Hesap kaydedilirken bir hata oluştu:\n{error_detail}")
            logging.error(f"Kasa/Banka kaydetme hatası: {error_detail}", exc_info=True)

class YeniTedarikciEklePenceresi(QDialog):
    def __init__(self, parent, db_manager, yenile_callback, tedarikci_duzenle=None, app_ref=None):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.yenile_callback = yenile_callback
        self.tedarikci_duzenle_data = tedarikci_duzenle

        self.tedarikci_duzenle_id = self.tedarikci_duzenle_data.get('id') if self.tedarikci_duzenle_data else None

        title = "Yeni Tedarikçi Ekle" if not self.tedarikci_duzenle_id else "Tedarikçi Düzenle"
        self.setWindowTitle(title)
        self.setMinimumSize(500, 420)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        main_layout.addWidget(title_label)

        form_layout = QGridLayout()
        main_layout.addLayout(form_layout)
        
        self.entries = {}
        labels_entries = {
            "Tedarikçi Kodu:": "entry_kod",
            "Ad Soyad (*):": "entry_ad",
            "Telefon:": "entry_tel",
            "Adres:": "entry_adres",
            "Vergi Dairesi:": "entry_vd",
            "Vergi No:": "entry_vn"
        }

        for i, (label_text, entry_name) in enumerate(labels_entries.items()):
            form_layout.addWidget(QLabel(label_text), i, 0, alignment=Qt.AlignLeft)
            widget = QTextEdit() if entry_name == "entry_adres" else QLineEdit()
            if isinstance(widget, QTextEdit): widget.setFixedHeight(80)
            self.entries[entry_name] = widget
            form_layout.addWidget(widget, i, 1)

        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)
        button_layout.addStretch()
        self.kaydet_button = QPushButton("Kaydet")
        self.kaydet_button.clicked.connect(self.kaydet)
        button_layout.addWidget(self.kaydet_button)
        self.iptal_button = QPushButton("İptal")
        self.iptal_button.clicked.connect(self.reject)
        button_layout.addWidget(self.iptal_button)
        
        self._verileri_yukle()

    def _verileri_yukle(self):
        if self.tedarikci_duzenle_data:
            self.entries["entry_kod"].setText(self.tedarikci_duzenle_data.get('tedarikci_kodu', ''))
            self.entries["entry_ad"].setText(self.tedarikci_duzenle_data.get('ad', ''))
            self.entries["entry_tel"].setText(self.tedarikci_duzenle_data.get('telefon', ''))
            self.entries["entry_adres"].setPlainText(self.tedarikci_duzenle_data.get('adres', ''))
            self.entries["entry_vd"].setText(self.tedarikci_duzenle_data.get('vergi_dairesi', ''))
            self.entries["entry_vn"].setText(self.tedarikci_duzenle_data.get('vergi_no', ''))
            self.entries["entry_kod"].setReadOnly(True)
        else:
            generated_code = self.db.get_next_tedarikci_kodu()
            self.entries["entry_kod"].setText(generated_code)
            self.entries["entry_kod"].setReadOnly(True)

    def kaydet(self):
        ad = self.entries["entry_ad"].text().strip()
        if not ad:
            QMessageBox.warning(self, "Eksik Bilgi", "Tedarikçi Adı alanı boş bırakılamaz.")
            return

        data = {
            "ad": ad,
            "tedarikci_kodu": self.entries["entry_kod"].text().strip(),
            "telefon": self.entries["entry_tel"].text().strip(),
            "adres": self.entries["entry_adres"].toPlainText().strip(),
            "vergi_dairesi": self.entries["entry_vd"].text().strip(),
            "vergi_no": self.entries["entry_vn"].text().strip()
        }

        try:
            if self.tedarikci_duzenle_id:
                # GÜNCELLEME (PUT isteği)
                success = self.db.tedarikci_guncelle(self.tedarikci_duzenle_id, data)
            else:
                # YENİ KAYIT (POST isteği)
                success = self.db.tedarikci_ekle(data)

            if success:
                QMessageBox.information(self, "Başarılı", "Tedarikçi bilgileri başarıyla kaydedildi.")
                if self.yenile_callback:
                    self.yenile_callback()
                self.accept()
            else:
                QMessageBox.critical(self, "Hata", "Tedarikçi kaydedilirken bir hata oluştu.")

        except Exception as e:
            error_detail = str(e)
            QMessageBox.critical(self, "Hata", f"Tedarikçi kaydedilirken bir hata oluştu:\n{error_detail}")
            logging.error(f"Tedarikçi kaydetme hatası: {error_detail}", exc_info=True)

class YeniMusteriEklePenceresi(QDialog):
    def __init__(self, parent, db_manager, yenile_callback, musteri_duzenle=None, app_ref=None):
        super().__init__(parent)
        self.db = db_manager # Otomatik kod üretme gibi yardımcı fonksiyonlar için hala gerekli olabilir
        self.app = app_ref
        self.yenile_callback = yenile_callback
        self.musteri_duzenle_data = musteri_duzenle # API'den gelen düzenleme verisi

        # Eğer düzenleme modundaysak, ID'yi sakla
        self.musteri_duzenle_id = self.musteri_duzenle_data.get('id') if self.musteri_duzenle_data else None

        title = "Yeni Müşteri Ekle" if not self.musteri_duzenle_id else "Müşteri Düzenle"
        self.setWindowTitle(title)
        self.setMinimumSize(500, 420)
        self.setModal(True) # Bu pencere açıkken ana pencereye tıklamayı engeller

        # Ana layout
        main_layout = QVBoxLayout(self)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        main_layout.addWidget(title_label)

        # Form için grid layout
        form_layout = QGridLayout()
        main_layout.addLayout(form_layout)
        
        # Form elemanları
        self.entries = {}
        labels_entries = {
            "Müşteri Kodu:": "entry_kod",
            "Ad Soyad (*):": "entry_ad",
            "Telefon:": "entry_tel",
            "Adres:": "entry_adres",
            "Vergi Dairesi:": "entry_vd",
            "Vergi No:": "entry_vn"
        }

        for i, (label_text, entry_name) in enumerate(labels_entries.items()):
            form_layout.addWidget(QLabel(label_text), i, 0, alignment=Qt.AlignLeft)
            if entry_name == "entry_adres":
                widget = QTextEdit()
                widget.setFixedHeight(80) # Adres alanı için yükseklik
            else:
                widget = QLineEdit()
            
            self.entries[entry_name] = widget
            form_layout.addWidget(widget, i, 1)

        # Butonlar için yatay layout
        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)
        button_layout.addStretch() # Butonları sağa yaslamak için boşluk ekle

        self.kaydet_button = QPushButton("Kaydet")
        self.kaydet_button.clicked.connect(self.kaydet)
        button_layout.addWidget(self.kaydet_button)
        
        self.iptal_button = QPushButton("İptal")
        self.iptal_button.clicked.connect(self.reject) # QDialog'u kapatır
        button_layout.addWidget(self.iptal_button)
        
        self._verileri_yukle()

    def _verileri_yukle(self):
        """Mevcut müşteri verilerini düzenleme modunda forma yükler."""
        if self.musteri_duzenle_data:
            # Düzenleme modu
            self.entries["entry_kod"].setText(self.musteri_duzenle_data.get('kod', ''))
            self.entries["entry_ad"].setText(self.musteri_duzenle_data.get('ad', ''))
            self.entries["entry_tel"].setText(self.musteri_duzenle_data.get('telefon', ''))
            self.entries["entry_adres"].setPlainText(self.musteri_duzenle_data.get('adres', ''))
            self.entries["entry_vd"].setText(self.musteri_duzenle_data.get('vergi_dairesi', ''))
            self.entries["entry_vn"].setText(self.musteri_duzenle_data.get('vergi_no', ''))
            # Düzenleme modunda kodu değiştirilemez yapalım
            self.entries["entry_kod"].setReadOnly(True)
        else:
            # Yeni kayıt modu
            generated_code = self.db.get_next_musteri_kodu()
            self.entries["entry_kod"].setText(generated_code)
            self.entries["entry_kod"].setReadOnly(True)

    def kaydet(self):
        """Formdaki verileri toplar ve API'ye gönderir."""
        ad = self.entries["entry_ad"].text().strip()
        if not ad:
            QMessageBox.warning(self, "Eksik Bilgi", "Müşteri Adı alanı boş bırakılamaz.")
            return

        data = {
            "ad": ad,
            "kod": self.entries["entry_kod"].text().strip(),
            "telefon": self.entries["entry_tel"].text().strip(),
            "adres": self.entries["entry_adres"].toPlainText().strip(),
            "vergi_dairesi": self.entries["entry_vd"].text().strip(),
            "vergi_no": self.entries["entry_vn"].text().strip()
        }

        try:
            if self.musteri_duzenle_id:
                # GÜNCELLEME (PUT isteği)
                success = self.db.musteri_guncelle(self.musteri_duzenle_id, data)
            else:
                # YENİ KAYIT (POST isteği)
                success = self.db.musteri_ekle(data)

            if success:
                QMessageBox.information(self, "Başarılı", "Müşteri bilgileri başarıyla kaydedildi.")
                
                if self.yenile_callback:
                    self.yenile_callback()
                
                self.accept()
            else:
                QMessageBox.critical(self, "Hata", "Müşteri kaydedilirken bir hata oluştu.")

        except Exception as e:
            error_detail = str(e)
            # Eğer hata nesnesinde response varsa, API'den dönen detayı almaya çalış.
            # self.db metotları zaten HTTPException'ı yakalayıp mesaj döndürüyor olmalı.
            # Eğer Exception fırlatıyorsa, bu beklenmedik bir durumdur.
            QMessageBox.critical(self, "Hata", f"Müşteri kaydedilirken bir hata oluştu:\n{error_detail}")
            logging.error(f"Müşteri kaydetme hatası: {error_detail}", exc_info=True)
            
class KalemDuzenlePenceresi(QDialog):
    def __init__(self, parent_page, db_manager, kalem_index, kalem_verisi, islem_tipi, fatura_id_duzenle=None):
        super().__init__(parent_page)
        self.parent_page = parent_page # FaturaPenceresi objesi
        self.db = db_manager # db_manager artık direkt parametre olarak alınıyor
        self.kalem_index = kalem_index
        self.islem_tipi = islem_tipi
        self.fatura_id_duzenle = fatura_id_duzenle

        self.urun_id = kalem_verisi[0]
        self.urun_adi = kalem_verisi[1]
        self.mevcut_miktar = self.db.safe_float(kalem_verisi[2])
        self.orijinal_birim_fiyat_kdv_haric = self.db.safe_float(kalem_verisi[3])
        self.kdv_orani = self.db.safe_float(kalem_verisi[4])
        self.mevcut_alis_fiyati_fatura_aninda = self.db.safe_float(kalem_verisi[8])
        
        self_initial_iskonto_yuzde_1 = self.db.safe_float(kalem_verisi[10])
        self_initial_iskonto_yuzde_2 = self.db.safe_float(kalem_verisi[11])

        self.orijinal_birim_fiyat_kdv_dahil = self.orijinal_birim_fiyat_kdv_haric * (1 + self.kdv_orani / 100)

        self.setWindowTitle(f"Kalem Düzenle: {self.urun_adi}")
        self.setFixedSize(450, 550) # geometry yerine setFixedSize kullanıldı
        self.setModal(True) # Modalı olarak ayarla

        main_layout = QVBoxLayout(self)
        main_frame = QFrame(self)
        main_layout.addWidget(main_frame)
        main_frame_layout = QGridLayout(main_frame) # Izgara düzenleyici
        
        main_frame_layout.addWidget(QLabel(f"Ürün: <b>{self.urun_adi}</b>", font=QFont("Segoe UI", 12, QFont.Bold)), 0, 0, 1, 3, Qt.AlignLeft)
        main_frame_layout.setColumnStretch(1, 1) # İkinci sütun genişlesin

        current_row = 1
        main_frame_layout.addWidget(QLabel("Miktar:"), current_row, 0)
        self.miktar_e = QLineEdit()
        setup_numeric_entry(self.parent_page.app, self.miktar_e, decimal_places=2) 
        self.miktar_e.setText(f"{self.mevcut_miktar:.2f}".replace('.',','))
        self.miktar_e.textChanged.connect(self._anlik_hesaplama_ve_guncelleme)
        main_frame_layout.addWidget(self.miktar_e, current_row, 1)

        current_row += 1
        main_frame_layout.addWidget(QLabel("Birim Fiyat (KDV Dahil):"), current_row, 0)
        self.fiyat_e = QLineEdit()
        setup_numeric_entry(self.parent_page.app, self.fiyat_e, decimal_places=2) 
        self.fiyat_e.setText(f"{self.orijinal_birim_fiyat_kdv_dahil:.2f}".replace('.',','))
        self.fiyat_e.textChanged.connect(self._anlik_hesaplama_ve_guncelleme)
        main_frame_layout.addWidget(self.fiyat_e, current_row, 1)

        current_row += 1
        self.alis_fiyati_aninda_e = None
        if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.SIPARIS_TIP_SATIS]:
            main_frame_layout.addWidget(QLabel("Fatura Anı Alış Fiyatı (KDV Dahil):"), current_row, 0)
            self.alis_fiyati_aninda_e = QLineEdit()
            setup_numeric_entry(self.parent_page.app, self.alis_fiyati_aninda_e, decimal_places=2) 
            self.alis_fiyati_aninda_e.setText(f"{self.mevcut_alis_fiyati_fatura_aninda:.2f}".replace('.',','))
            self.alis_fiyati_aninda_e.textChanged.connect(self._anlik_hesaplama_ve_guncelleme)
            main_frame_layout.addWidget(self.alis_fiyati_aninda_e, current_row, 1)
            current_row += 1
        
        main_frame_layout.addWidget(QFrame(), current_row, 0, 1, 3) # Separator yerine boş QFrame
        current_row += 1

        main_frame_layout.addWidget(QLabel("İskonto 1 (%):"), current_row, 0)
        self.iskonto_yuzde_1_e = QLineEdit()
        setup_numeric_entry(self.parent_page.app, self.iskonto_yuzde_1_e, decimal_places=2) 
        self.iskonto_yuzde_1_e.setText(f"{self_initial_iskonto_yuzde_1:.2f}".replace('.',','))
        self.iskonto_yuzde_1_e.textChanged.connect(self._anlik_hesaplama_ve_guncelleme)
        main_frame_layout.addWidget(self.iskonto_yuzde_1_e, current_row, 1)
        main_frame_layout.addWidget(QLabel("%"), current_row, 2)
        current_row += 1

        main_frame_layout.addWidget(QLabel("İskonto 2 (%):"), current_row, 0)
        self.iskonto_yuzde_2_e = QLineEdit()
        setup_numeric_entry(self.parent_page.app, self.iskonto_yuzde_2_e, decimal_places=2, max_value=100)
        self.iskonto_yuzde_2_e.setText(f"{self_initial_iskonto_yuzde_2:.2f}".replace('.',','))
        self.iskonto_yuzde_2_e.textChanged.connect(self._anlik_hesaplama_ve_guncelleme)
        main_frame_layout.addWidget(self.iskonto_yuzde_2_e, current_row, 1)
        main_frame_layout.addWidget(QLabel("%"), current_row, 2)
        current_row += 1

        main_frame_layout.addWidget(QFrame(), current_row, 0, 1, 3) # Separator yerine boş QFrame
        current_row += 1

        main_frame_layout.addWidget(QLabel("Toplam İskonto Yüzdesi:", font=QFont("Segoe UI", 9, QFont.Bold)), current_row, 0)
        self.lbl_toplam_iskonto_yuzdesi = QLabel("0,00 %", font=QFont("Segoe UI", 9))
        main_frame_layout.addWidget(self.lbl_toplam_iskonto_yuzdesi, current_row, 1, 1, 2)
        current_row += 1

        main_frame_layout.addWidget(QLabel("Uygulanan İskonto Tutarı (KDV Dahil):", font=QFont("Segoe UI", 9, QFont.Bold)), current_row, 0)
        self.lbl_uygulanan_iskonto_dahil = QLabel("0,00 TL", font=QFont("Segoe UI", 9))
        main_frame_layout.addWidget(self.lbl_uygulanan_iskonto_dahil, current_row, 1, 1, 2)
        current_row += 1

        main_frame_layout.addWidget(QLabel("İskontolu Birim Fiyat (KDV Dahil):", font=QFont("Segoe UI", 9, QFont.Bold)), current_row, 0)
        self.lbl_iskontolu_bf_dahil = QLabel("0,00 TL", font=QFont("Segoe UI", 9))
        main_frame_layout.addWidget(self.lbl_iskontolu_bf_dahil, current_row, 1, 1, 2)
        current_row += 1

        main_frame_layout.addWidget(QLabel("Kalem Toplam (KDV Dahil):", font=QFont("Segoe UI", 10, QFont.Bold)), current_row, 0)
        self.lbl_kalem_toplam_dahil = QLabel("0,00 TL", font=QFont("Segoe UI", 10, QFont.Bold))
        main_frame_layout.addWidget(self.lbl_kalem_toplam_dahil, current_row, 1, 1, 2)
        current_row += 1

        btn_f = QFrame(self)
        btn_layout = QHBoxLayout(btn_f)
        main_layout.addWidget(btn_f, alignment=Qt.AlignRight)
        
        btn_guncelle = QPushButton("Güncelle")
        btn_guncelle.clicked.connect(self._kalemi_kaydet)
        btn_layout.addWidget(btn_guncelle)

        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self.close) # QDialog'u kapat
        btn_layout.addWidget(btn_iptal)

        self._anlik_hesaplama_ve_guncelleme()
        self.miktar_e.setFocus()
        self.miktar_e.selectAll()

    def _anlik_hesaplama_ve_guncelleme(self):
        try:
            miktar = self.db.safe_float(self.miktar_e.text())
            birim_fiyat_kdv_dahil_orijinal = self.db.safe_float(self.fiyat_e.text())

            yuzde_iskonto_1 = self.db.safe_float(self.iskonto_yuzde_1_e.text())
            yuzde_iskonto_2 = self.db.safe_float(self.iskonto_yuzde_2_e.text())

            if not (0 <= yuzde_iskonto_1 <= 100):
                self.iskonto_yuzde_1_e.setText("0,00")
                yuzde_iskonto_1 = 0.0

            if not (0 <= yuzde_iskonto_2 <= 100):
                self.iskonto_yuzde_2_e.setText("0,00")
                yuzde_iskonto_2 = 0.0

            fiyat_iskonto_1_sonrasi_dahil = birim_fiyat_kdv_dahil_orijinal * (1 - yuzde_iskonto_1 / 100)
            iskontolu_birim_fiyat_dahil = fiyat_iskonto_1_sonrasi_dahil * (1 - yuzde_iskonto_2 / 100)
            
            if iskontolu_birim_fiyat_dahil < 0:
                iskontolu_birim_fiyat_dahil = 0.0

            toplam_uygulanan_iskonto_dahil = birim_fiyat_kdv_dahil_orijinal - iskontolu_birim_fiyat_dahil
            
            kalem_toplam_dahil = miktar * iskontolu_birim_fiyat_dahil

            if birim_fiyat_kdv_dahil_orijinal > 0:
                toplam_iskonto_yuzdesi = (toplam_uygulanan_iskonto_dahil / birim_fiyat_kdv_dahil_orijinal) * 100
            else:
                toplam_iskonto_yuzdesi = 0.0 

            self.lbl_toplam_iskonto_yuzdesi.setText(f"{toplam_iskonto_yuzdesi:,.2f} %")
            self.lbl_uygulanan_iskonto_dahil.setText(self.db._format_currency(toplam_uygulanan_iskonto_dahil))
            self.lbl_iskontolu_bf_dahil.setText(self.db._format_currency(iskontolu_birim_fiyat_dahil))
            self.lbl_kalem_toplam_dahil.setText(self.db._format_currency(kalem_toplam_dahil))

        except ValueError:
            self.lbl_toplam_iskonto_yuzdesi.setText("0,00 %")
            self.lbl_uygulanan_iskonto_dahil.setText("0,00 TL")
            self.lbl_iskontolu_bf_dahil.setText("0,00 TL")
            self.lbl_kalem_toplam_dahil.setText("0,00 TL")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Hesaplama sırasında beklenmeyen bir hata oluştu: {e}")
            logging.error(f"Anlık hesaplama hatası: {e}", exc_info=True)


    def _kalemi_kaydet(self):
        yeni_miktar = 0.0
        yeni_fiyat_kdv_dahil_orijinal = 0.0
        yuzde_iskonto_1 = 0.0
        yuzde_iskonto_2 = 0.0
        yeni_alis_fiyati_aninda = self.mevcut_alis_fiyati_fatura_aninda

        try:
            yeni_miktar = self.db.safe_float(self.miktar_e.text())
            yeni_fiyat_kdv_dahil_orijinal = self.db.safe_float(self.fiyat_e.text())
            
            yuzde_iskonto_1 = self.db.safe_float(self.iskonto_yuzde_1_e.text())
            yuzde_iskonto_2 = self.db.safe_float(self.iskonto_yuzde_2_e.text())
            
            if (self.islem_tipi == self.db.FATURA_TIP_SATIS or self.islem_tipi == self.db.SIPARIS_TIP_SATIS) and self.alis_fiyati_aninda_e:
                yeni_alis_fiyati_aninda = self.db.safe_float(self.alis_fiyati_aninda_e.text())

            if yeni_miktar <= 0:
                QMessageBox.critical(self, "Geçersiz Miktar", "Miktar pozitif bir sayı olmalıdır.")
                return
            if yeni_fiyat_kdv_dahil_orijinal < 0:
                QMessageBox.critical(self, "Geçersiz Fiyat", "Birim fiyat negatif olamaz.")
                return
            if not (0 <= yuzde_iskonto_1 <= 100):
                QMessageBox.critical(self, "Geçersiz İskonto 1 Yüzdesi", "İskonto 1 yüzdesi 0 ile 100 arasında olmalıdır.")
                return
            if not (0 <= yuzde_iskonto_2 <= 100):
                QMessageBox.critical(self, "Geçersiz İskonto 2 Yüzdesi", "İskonto 2 yüzdesi 0 ile 100 arasında olmalıdır.")
                return
            if (self.islem_tipi == self.db.FATURA_TIP_SATIS or self.islem_tipi == self.db.SIPARIS_TIP_SATIS) and self.alis_fiyati_aninda_e and yeni_alis_fiyati_aninda < 0:
                QMessageBox.critical(self, "Geçersiz Fiyat", "Fatura anı alış fiyatı negatif olamaz.")
                return
            
            self.parent_page._kalem_guncelle(
                self.kalem_index, 
                yeni_miktar, 
                yeni_fiyat_kdv_dahil_orijinal, 
                yuzde_iskonto_1,       
                yuzde_iskonto_2,       
                yeni_alis_fiyati_aninda 
            )
            self.accept() # QDialog'u kapat.

        except ValueError as ve:
            QMessageBox.critical(self, "Giriş Hatası", f"Sayısal alanlarda geçersiz değerler var: {ve}")
            logging.error(f"Kalem Guncelle ValueError: {ve}", exc_info=True)
        except IndexError as ie:
            QMessageBox.critical(self, "Hata", f"Güncellenecek kalem bulunamadı (indeks hatası): {ie}")
            logging.error(f"Kalem Guncelle IndexError: {ie}", exc_info=True)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kalem güncellenirken beklenmeyen bir hata oluştu: {e}")
            logging.error(f"Kalem Guncelle Genel Hata: {e}", exc_info=True)

class FiyatGecmisiPenceresi(QDialog):
    def __init__(self, parent_app, db_manager, cari_id, urun_id, fatura_tipi, update_callback, current_kalem_index):
        super().__init__(parent_app)
        self.db = db_manager
        self.app = parent_app
        self.cari_id = cari_id
        self.urun_id = urun_id
        self.fatura_tipi = fatura_tipi
        self.update_callback = update_callback # FaturaOlusturmaSayfasi'ndaki kalemi güncelleme callback'i
        self.current_kalem_index = current_kalem_index # Sepetteki güncel kalemin indeksi

        self.setWindowTitle("Fiyat Geçmişi Seç")
        self.setFixedSize(600, 400) # Boyut ayarı (resizable=False yerine)
        self.setModal(True) # Diğer pencerelere tıklamayı engeller

        main_layout = QVBoxLayout(self)
        title_label = QLabel("Geçmiş Fiyat Listesi")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # Fiyat Geçmişi Listesi (Treeview)
        tree_frame = QFrame(self)
        tree_layout = QVBoxLayout(tree_frame)
        main_layout.addWidget(tree_frame)

        # Sütunlar: Fatura No, Tarih, Fiyat (KDV Dahil), İskonto 1 (%), İskonto 2 (%)
        cols = ("Fatura No", "Tarih", "Fiyat (KDV Dahil)", "İskonto 1 (%)", "İskonto 2 (%)")
        self.price_history_tree = QTreeWidget()
        self.price_history_tree.setHeaderLabels(cols)
        self.price_history_tree.setSelectionBehavior(QAbstractItemView.SelectRows) # Tek satır seçimi
        self.price_history_tree.setSortingEnabled(True)

        from PySide6.QtWidgets import QHeaderView # PySide6'ya özel import
        col_defs = [
            ("Fatura No", 120, Qt.AlignLeft),
            ("Tarih", 90, Qt.AlignCenter),
            ("Fiyat (KDV Dahil)", 120, Qt.AlignRight),
            ("İskonto 1 (%)", 90, Qt.AlignRight),
            ("İskonto 2 (%)", 90, Qt.AlignRight)
        ]

        for i, (col_name, width, alignment) in enumerate(col_defs):
            self.price_history_tree.setColumnWidth(i, width)
            self.price_history_tree.headerItem().setTextAlignment(i, alignment)
            self.price_history_tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
        
        self.price_history_tree.header().setStretchLastSection(True) # Son sütunu esnet

        tree_layout.addWidget(self.price_history_tree)

        # Çift tıklama veya seçip butona basma ile fiyatı seçme
        self.price_history_tree.itemDoubleClicked.connect(self._on_price_selected_double_click)

        self._load_price_history() # Geçmiş fiyatları yükle

        # Alt Butonlar
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame)

        btn_onayla = QPushButton("Seç ve Uygula")
        btn_onayla.clicked.connect(self._on_price_selected_button)
        button_layout.addWidget(btn_onayla)
        
        button_layout.addStretch() # Sağ tarafa yaslamak için boşluk

        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.close) # QDialog'u kapat
        button_layout.addWidget(btn_kapat)

    def _load_price_history(self):
        """Veritabanından geçmiş fiyat bilgilerini çeker ve Treeview'e doldurur."""
        self.price_history_tree.clear()
        # db.get_gecmis_fatura_kalemi_bilgileri metodunu çağır
        history_data = self.db.get_gecmis_fatura_kalemi_bilgileri(self.cari_id, self.urun_id, self.fatura_tipi) 

        if not history_data:
            item_qt = QTreeWidgetItem(self.price_history_tree)
            item_qt.setText(2, "Geçmiş Fiyat Yok")
            return

        for item in history_data:
            # item: (fatura_id, fatura_no, formatted_date, nihai_iskontolu_kdv_dahil_bf, iskonto_yuzde_1, iskonto_yuzde_2)
            fatura_id = item[0]
            fatura_no = item[1]
            tarih = item[2]
            fiyat = self.db._format_currency(item[3])
            iskonto_1 = f"{item[4]:.2f}".replace('.', ',').rstrip('0').rstrip(',')
            iskonto_2 = f"{item[5]:.2f}".replace('.', ',').rstrip('0').rstrip(',')

            item_qt = QTreeWidgetItem(self.price_history_tree)
            item_qt.setText(0, fatura_no)
            item_qt.setText(1, tarih)
            item_qt.setText(2, fiyat)
            item_qt.setText(3, iskonto_1)
            item_qt.setText(4, iskonto_2)
            item_qt.setData(0, Qt.UserRole, fatura_id) # Fatura ID'yi sakla (opsiyonel)


    def _on_price_selected_double_click(self, item, column): # item ve column QTreeWidget sinyalinden gelir
        self._on_price_selected_button()

    def _on_price_selected_button(self):
        """Seçilen fiyatı alır ve FaturaOlusturmaSayfasi'na geri gönderir."""
        selected_items = self.price_history_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen uygulamak için bir geçmiş fiyat seçin.")
            return

        item_values = [selected_items[0].text(i) for i in range(self.price_history_tree.columnCount())]
        
        # item_values formatı: ["Fatura No", "Tarih", "Fiyat (KDV Dahil)", "İskonto 1 (%)", "İskonto 2 (%)"]
        # Fiyatı, İskonto 1 ve İskonto 2'yi al
        selected_price_str = item_values[2] 
        selected_iskonto1_str = item_values[3] 
        selected_iskonto2_str = item_values[4] 

        try:
            cleaned_price_str = selected_price_str.replace(' TL', '').replace('₺', '').strip()
            cleaned_iskonto1_str = selected_iskonto1_str.replace('%', '').strip()
            cleaned_iskonto2_str = selected_iskonto2_str.replace('%', '').strip()

            selected_price = self.db.safe_float(cleaned_price_str)
            selected_iskonto1 = self.db.safe_float(cleaned_iskonto1_str)
            selected_iskonto2 = self.db.safe_float(cleaned_iskonto2_str)

            logging.debug(f"Secilen Fiyat (temizlenmis): '{cleaned_price_str}' -> {selected_price}")
            logging.debug(f"Secilen Iskonto 1 (temizlenmis): '{cleaned_iskonto1_str}' -> {selected_iskonto1}")
            logging.debug(f"Secilen Iskonto 2 (temizlenmis): '{cleaned_iskonto2_str}' -> {selected_iskonto2}")

        except ValueError:
            QMessageBox.critical(self, "Hata", "Seçilen fiyat verisi geçersiz. (Dönüştürme hatası)")
            return
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Fiyat geçmişi verisi işlenirken beklenmeyen bir hata oluştu: {e}")
            logging.error(f"Fiyat geçmişi verisi işleme hatası: {e}", exc_info=True)
            return

        # update_callback metodu, (kalem_index, yeni_birim_fiyat_kdv_dahil, yeni_iskonto_1, yeni_iskonto_2) alacak.
        self.update_callback(self.current_kalem_index, selected_price, selected_iskonto1, selected_iskonto2)
        self.close() # Pencereyi kapat

class KullaniciYonetimiPenceresi(QDialog):
    def __init__(self, parent_app, db_manager):
        super().__init__(parent_app)
        self.db = db_manager
        self.app = parent_app # Ana App referansı
        self.setWindowTitle("Kullanıcı Yönetimi")
        self.setMinimumSize(600, 650)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        title_label = QLabel("Kullanıcı Listesi ve Yönetimi")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # Kullanıcı Listesi
        list_frame = QFrame(self)
        list_layout = QHBoxLayout(list_frame)
        main_layout.addWidget(list_frame)
        
        cols_kul = ("ID", "Kullanıcı Adı", "Yetki")
        self.tree_kul = QTreeWidget()
        self.tree_kul.setHeaderLabels(cols_kul)
        self.tree_kul.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_kul.setSortingEnabled(True) # Sıralama özelliği

        self.tree_kul.setColumnWidth(0, 50)
        self.tree_kul.headerItem().setTextAlignment(0, Qt.AlignRight)
        self.tree_kul.headerItem().setTextAlignment(2, Qt.AlignCenter)
        self.tree_kul.header().setSectionResizeMode(1, QHeaderView.Stretch) # Kullanıcı Adı genişlesin

        list_layout.addWidget(self.tree_kul)
        
        self.kullanici_listesini_yenile() # İlk yüklemede listeyi doldur

        # Yeni Kullanıcı Ekleme Formu
        form_frame = QGroupBox("Yeni Kullanıcı Ekle / Güncelle", self)
        form_layout = QGridLayout(form_frame)
        main_layout.addWidget(form_frame)

        form_layout.addWidget(QLabel("Kullanıcı Adı:"), 0, 0, Qt.AlignLeft)
        self.k_adi_yeni_e = QLineEdit()
        form_layout.addWidget(self.k_adi_yeni_e, 0, 1)
        form_layout.setColumnStretch(1, 1) # Genişlesin

        form_layout.addWidget(QLabel("Yeni Şifre:"), 1, 0, Qt.AlignLeft)
        self.sifre_yeni_e = QLineEdit()
        self.sifre_yeni_e.setEchoMode(QLineEdit.Password) # Şifre gizleme
        form_layout.addWidget(self.sifre_yeni_e, 1, 1)

        form_layout.addWidget(QLabel("Yetki:"), 0, 2, Qt.AlignLeft)
        self.yetki_yeni_cb = QComboBox()
        self.yetki_yeni_cb.addItems(["kullanici", "admin"])
        self.yetki_yeni_cb.setCurrentText("kullanici") # Varsayılan
        form_layout.addWidget(self.yetki_yeni_cb, 0, 3)

        # Butonlar
        button_frame_kul = QFrame(self)
        button_layout_kul = QHBoxLayout(button_frame_kul)
        main_layout.addWidget(button_frame_kul)
        
        self.ekle_guncelle_btn = QPushButton("Ekle / Güncelle")
        self.ekle_guncelle_btn.clicked.connect(self.yeni_kullanici_ekle)
        button_layout_kul.addWidget(self.ekle_guncelle_btn)
        
        btn_sil_kul = QPushButton("Seçili Kullanıcıyı Sil")
        btn_sil_kul.clicked.connect(self.secili_kullanici_sil)
        button_layout_kul.addWidget(btn_sil_kul)
        
        button_layout_kul.addStretch() # Sağa yaslama
        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.close)
        button_layout_kul.addWidget(btn_kapat)

        self.tree_kul.itemSelectionChanged.connect(self.secili_kullaniciyi_forma_yukle) # Seçim değiştiğinde formu doldur

    def kullanici_listesini_yenile(self):
        self.tree_kul.clear()
        try:
            # API'den kullanıcı listesini çekmek için uygun bir endpoint varsayımı
            # Eğer API'de böyle bir endpoint yoksa, doğrudan db_manager kullanılmalıdır.
            # Şimdilik db_manager'dan çekiliyor.
            kullanicilar = self.db.kullanici_listele()
            
            for kul in kullanicilar:
                item_qt = QTreeWidgetItem(self.tree_kul)
                item_qt.setText(0, str(kul.get('id'))) # 'id' alanı
                item_qt.setText(1, kul.get('kullanici_adi')) # 'kullanici_adi' alanı
                item_qt.setText(2, kul.get('yetki')) # 'yetki' alanı
                item_qt.setData(0, Qt.UserRole, kul.get('id')) # ID'yi UserRole olarak sakla
                
            self.app.set_status_message(f"{len(kullanicilar)} kullanıcı listelendi.")

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kullanıcı listesi çekilirken hata: {e}")
            logging.error(f"Kullanıcı listesi yükleme hatası: {e}", exc_info=True)
    
    def secili_kullaniciyi_forma_yukle(self):
        selected_items = self.tree_kul.selectedItems()
        if selected_items:
            item = selected_items[0]
            kullanici_adi = item.text(1)
            yetki = item.text(2)
            self.k_adi_yeni_e.setText(kullanici_adi)
            self.yetki_yeni_cb.setCurrentText(yetki)
            self.sifre_yeni_e.clear() # Şifre alanı temizlensin
            self.ekle_guncelle_btn.setText("Güncelle")
        else: # Seçim yoksa formu temizle
            self.k_adi_yeni_e.clear()
            self.sifre_yeni_e.clear()
            self.yetki_yeni_cb.setCurrentText("kullanici")
            self.ekle_guncelle_btn.setText("Ekle / Güncelle")

    def yeni_kullanici_ekle(self):
        k_adi = self.k_adi_yeni_e.text().strip()
        sifre = self.sifre_yeni_e.text().strip()
        yetki = self.yetki_yeni_cb.currentText()

        if not (k_adi and yetki):
            QMessageBox.critical(self, "Eksik Bilgi", "Kullanıcı adı ve yetki boş bırakılamaz.")
            return

        selected_items = self.tree_kul.selectedItems()
        
        if selected_items: # Güncelleme
            user_id = selected_items[0].data(0, Qt.UserRole)
            mevcut_k_adi = selected_items[0].text(1)

            success_name_update = True
            message_name_update = ""

            if k_adi != mevcut_k_adi:
                try:
                    # API endpoint'i üzerinden kullanıcı adını güncelleme (varsayalım mevcut)
                    # response = requests.put(f"{API_BASE_URL}/kullanicilar/{user_id}/kullanici_adi", json={"kullanici_adi": k_adi})
                    # response.raise_for_status()
                    # success_name_update, message_name_update = True, "Kullanıcı adı güncellendi."
                    success_name_update, message_name_update = self.db.kullanici_adi_guncelle(user_id, k_adi)

                except Exception as e:
                    success_name_update = False
                    message_name_update = f"Kullanıcı adı güncellenirken hata: {e}"
                    logging.error(f"Kullanıcı adı güncelleme hatası: {e}", exc_info=True)
                
                if not success_name_update:
                    QMessageBox.critical(self, "Hata", message_name_update)
                    return

            sifre_to_hash = None
            if sifre:
                sifre_to_hash = self.db._hash_sifre(sifre)
            else: # Şifre boş bırakılırsa mevcut şifreyi koru
                try:
                    # API'den şifre çekme veya doğrudan db_manager'dan çekme
                    # response = requests.get(f"{API_BASE_URL}/kullanicilar/{user_id}/sifre_hash")
                    # response.raise_for_status()
                    # sifre_to_hash = response.json().get('sifre_hash')
                    self.db.c.execute("SELECT sifre FROM kullanicilar WHERE id=?", (user_id,))
                    sifre_to_hash = self.db.c.fetchone()[0]
                except Exception as e:
                    QMessageBox.critical(self, "Hata", f"Mevcut şifre alınırken bir hata oluştu: {e}")
                    logging.error(f"Mevcut şifre alma hatası: {e}", exc_info=True)
                    return

            try:
                # API endpoint'i üzerinden kullanıcıyı güncelleme
                # response = requests.put(f"{API_BASE_URL}/kullanicilar/{user_id}", json={"sifre": sifre_to_hash, "yetki": yetki})
                # response.raise_for_status()
                # success, message = True, "Kullanıcı başarıyla güncellendi."
                success, message = self.db.kullanici_guncelle_sifre_yetki(user_id, sifre_to_hash, yetki)

                if success:
                    QMessageBox.information(self, "Başarılı", message)
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self, "Hata", message)
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kullanıcı güncellenirken hata: {e}")
                logging.error(f"Kullanıcı güncelleme hatası: {e}", exc_info=True)

            self.kullanici_listesini_yenile()
            self.k_adi_yeni_e.clear()
            self.sifre_yeni_e.clear()
            self.tree_kul.clearSelection()
            self.secili_kullaniciyi_forma_yukle() # Formu temizle (butonu da "Ekle / Güncelle" yapar)

        else: # Yeni kullanıcı ekleme
            if not sifre:
                QMessageBox.critical(self, "Eksik Bilgi", "Yeni kullanıcı eklerken şifre boş bırakılamaz.")
                return

            try:
                # API endpoint'i üzerinden yeni kullanıcı ekleme
                # response = requests.post(f"{API_BASE_URL}/kullanicilar/", json={"kullanici_adi": k_adi, "sifre": sifre, "yetki": yetki})
                # response.raise_for_status()
                # success, message = True, "Yeni kullanıcı başarıyla eklendi."
                success, message = self.db.kullanici_ekle(k_adi, sifre, yetki)

                if success:
                    QMessageBox.information(self, "Başarılı", message)
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self, "Hata", message)
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Yeni kullanıcı eklenirken hata: {e}")
                logging.error(f"Yeni kullanıcı ekleme hatası: {e}", exc_info=True)

            self.kullanici_listesini_yenile()
            self.k_adi_yeni_e.clear()
            self.sifre_yeni_e.clear()
            self.tree_kul.clearSelection()
            self.secili_kullaniciyi_forma_yukle()

    def secili_kullanici_sil(self):
        selected_items = self.tree_kul.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Seçim Yok", "Lütfen silmek istediğiniz kullanıcıyı seçin.")
            return
        
        k_adi_secili = selected_items[0].text(1)
        user_id_to_delete = selected_items[0].data(0, Qt.UserRole)

        if k_adi_secili == self.app.current_user[1]: 
             QMessageBox.warning(self, "Engellendi", "Aktif olarak giriş yapmış olduğunuz kendi kullanıcı hesabınızı silemezsiniz.")
             return

        reply = QMessageBox.question(self, "Onay", f"'{k_adi_secili}' kullanıcısını silmek istediğinizden emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                # API endpoint'i üzerinden kullanıcı silme
                # response = requests.delete(f"{API_BASE_URL}/kullanicilar/{user_id_to_delete}")
                # response.raise_for_status()
                # success, message = True, "Kullanıcı başarıyla silindi."
                success, message = self.db.kullanici_sil(user_id_to_delete)

                if success:
                    QMessageBox.information(self, "Başarılı", message)
                    self.kullanici_listesini_yenile()
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self, "Hata", message)
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kullanıcı silinirken hata: {e}")
                logging.error(f"Kullanıcı silme hatası: {e}", exc_info=True)

class YeniGelirGiderEklePenceresi(QDialog):
    def __init__(self, parent_app, db_manager, yenile_callback, initial_tip=None):
        super().__init__(parent_app)
        self.db = db_manager
        self.yenile_callback = yenile_callback
        self.app = parent_app # parent_app'i app olarak kaydet

        self.kasa_banka_map = {}
        self.gelir_siniflandirma_map = {}
        self.gider_siniflandirma_map = {}

        self.setWindowTitle("Yeni Manuel Gelir/Gider Kaydı")
        self.setFixedSize(450, 450) # resizable=False yerine setFixedSize kullanıldı
        self.setModal(True) # Modalı olarak ayarla

        main_layout = QVBoxLayout(self)
        entry_frame = QFrame(self)
        main_layout.addWidget(entry_frame)
        entry_frame_layout = QGridLayout(entry_frame)
        
        current_row = 0

        entry_frame_layout.addWidget(QLabel("Tarih (YYYY-AA-GG):"), current_row, 0, Qt.AlignLeft)
        self.tarih_entry = QLineEdit()
        self.tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        # setup_date_entry PySide6 için placeholder, validator ile manuel kontrol daha iyi
        self.tarih_entry.setPlaceholderText("YYYY-AA-GG")
        entry_frame_layout.addWidget(self.tarih_entry, current_row, 1)
        btn_date = QPushButton("🗓️")
        btn_date.setFixedWidth(30)
        btn_date.clicked.connect(lambda: DatePickerDialog(self.app, self.tarih_entry)) # app referansı kullanıldı
        entry_frame_layout.addWidget(btn_date, current_row, 2)
        current_row += 1

        entry_frame_layout.addWidget(QLabel("İşlem Tipi:"), current_row, 0, Qt.AlignLeft)
        self.tip_combo = QComboBox()
        self.tip_combo.addItems(["GELİR", "GİDER"])
        if initial_tip and initial_tip in ["GELİR", "GİDER"]:
            self.tip_combo.setCurrentText(initial_tip)
        else:
            self.tip_combo.setCurrentIndex(0)
        self.tip_combo.currentIndexChanged.connect(self._on_tip_changed)
        entry_frame_layout.addWidget(self.tip_combo, current_row, 1)
        current_row += 1

        entry_frame_layout.addWidget(QLabel("Sınıflandırma:"), current_row, 0, Qt.AlignLeft)
        self.siniflandirma_combo = QComboBox()
        entry_frame_layout.addWidget(self.siniflandirma_combo, current_row, 1)
        current_row += 1

        entry_frame_layout.addWidget(QLabel("Tutar (TL):"), current_row, 0, Qt.AlignLeft)
        self.tutar_entry = QLineEdit("0,00")
        setup_numeric_entry(self.app, self.tutar_entry, allow_negative=False, decimal_places=2) # app referansı kullanıldı
        entry_frame_layout.addWidget(self.tutar_entry, current_row, 1)
        current_row += 1

        entry_frame_layout.addWidget(QLabel("İşlem Kasa/Banka (*):"), current_row, 0, Qt.AlignLeft)
        self.kasa_banka_combobox = QComboBox()
        entry_frame_layout.addWidget(self.kasa_banka_combobox, current_row, 1)
        current_row += 1
        
        entry_frame_layout.addWidget(QLabel("Açıklama:"), current_row, 0, Qt.AlignLeft)
        self.aciklama_entry = QLineEdit()
        entry_frame_layout.addWidget(self.aciklama_entry, current_row, 1)
        current_row += 1
        
        entry_frame_layout.setColumnStretch(1, 1) # İkinci sütun genişlesin

        main_layout.addStretch() # Üst kısımdaki elemanları yukarı it

        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame, alignment=Qt.AlignCenter) # Butonları ortala

        btn_kaydet = QPushButton("Kaydet")
        btn_kaydet.clicked.connect(self._kaydet)
        button_layout.addWidget(btn_kaydet)

        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self.close)
        button_layout.addWidget(btn_iptal)
        
        self._yukle_siniflandirmalar_comboboxlari_ve_ayarla()
        self.tarih_entry.setFocus()
        self.adjustSize() # Pencere boyutunu içeriğe göre ayarla


    def _yukle_siniflandirmalar_comboboxlari_ve_ayarla(self):
        self._yukle_kasa_banka_hesaplarini() 

        # API'den sınıflandırmaları çek
        try:
            response_gelir = requests.get(f"{API_BASE_URL}/nitelikler/gelir_siniflandirmalari")
            response_gelir.raise_for_status()
            gelir_siniflandirmalar_api = response_gelir.json()
            self.gelir_siniflandirma_map = {item.get('siniflandirma_adi'): item.get('id') for item in gelir_siniflandirmalar_api}

            response_gider = requests.get(f"{API_BASE_URL}/nitelikler/gider_siniflandirmalari")
            response_gider.raise_for_status()
            gider_siniflandirmalar_api = response_gider.json()
            self.gider_siniflandirma_map = {item.get('siniflandirma_adi'): item.get('id') for item in gider_siniflandirmalar_api}

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Hatası", f"Sınıflandırmalar yüklenirken hata: {e}")
            logging.error(f"Sınıflandırma yükleme hatası: {e}", exc_info=True)

        self._on_tip_changed()

    def _on_tip_changed(self):
        selected_tip = self.tip_combo.currentText()
        display_values = ["Seçim Yok"]
        selected_map = {}

        if selected_tip == "GELİR":
            selected_map = self.gelir_siniflandirma_map
        elif selected_tip == "GİDER":
            selected_map = self.gider_siniflandirma_map

        display_values.extend(sorted(selected_map.keys()))
        self.siniflandirma_combo.clear()
        self.siniflandirma_combo.addItems(display_values)
        self.siniflandirma_combo.setCurrentText("Seçim Yok")
        # combobox'ın state'i QComboBox'ta otomatik olarak readonly'dir.

    def _yukle_kasa_banka_hesaplarini(self):
        self.kasa_banka_combobox.clear()
        self.kasa_banka_map.clear()
        
        try:
            response = requests.get(f"{API_BASE_URL}/kasalar_bankalar/")
            response.raise_for_status()
            hesaplar = response.json()

            if hesaplar:
                for h in hesaplar:
                    # Kasa/Banka listelemede kullanılan formatı burada da uygulayalım
                    display_text = f"{h.get('hesap_adi')} ({h.get('tip')})"
                    if h.get('tip') == "BANKA" and h.get('banka_adi'):
                        display_text += f" - {h.get('banka_adi')}"
                    if h.get('bakiye') is not None:
                         display_text += f" (Bakiye: {self.db._format_currency(h.get('bakiye'))})"

                    self.kasa_banka_map[display_text] = h.get('id')
                    self.kasa_banka_combobox.addItem(display_text, h.get('id'))

                # Varsayılan "MERKEZİ NAKİT" hesabı bul ve seç
                default_hesap_text = None
                for text in self.kasa_banka_map.keys():
                    if text.strip().startswith("MERKEZİ NAKİT"):
                        default_hesap_text = text
                        break

                if default_hesap_text:
                    self.kasa_banka_combobox.setCurrentText(default_hesap_text)
                elif self.kasa_banka_combobox.count() > 0:
                    self.kasa_banka_combobox.setCurrentIndex(0) # Hiç varsayılan yoksa ilk hesabı seç
            else:
                self.kasa_banka_combobox.addItem("Hesap Yok", None)
                self.kasa_banka_combobox.setEnabled(False) # Hiç hesap yoksa devre dışı bırak

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Hatası", f"Kasa/Banka hesapları yüklenirken hata: {e}")
            logging.error(f"Kasa/Banka yükleme hatası: {e}", exc_info=True)
            self.kasa_banka_combobox.addItem("Hesap Yok", None)
            self.kasa_banka_combobox.setEnabled(False)

    def _kaydet(self):
        tarih_str = self.tarih_entry.text().strip()
        tip_str = self.tip_combo.currentText()
        tutar_str = self.tutar_entry.text().strip()
        aciklama_str = self.aciklama_entry.text().strip()

        secili_hesap_id = self.kasa_banka_combobox.currentData()
        
        secili_siniflandirma_adi = self.siniflandirma_combo.currentText()
        gelir_siniflandirma_id_val = None
        gider_siniflandirma_id_val = None

        if secili_siniflandirma_adi == "Seçim Yok" or not secili_siniflandirma_adi:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir sınıflandırma seçin.")
            return

        if tip_str == "GELİR":
            gelir_siniflandirma_id_val = self.gelir_siniflandirma_map.get(secili_siniflandirma_adi)
        elif tip_str == "GİDER":
            gider_siniflandirma_id_val = self.gider_siniflandirma_map.get(secili_siniflandirma_adi)

        if secili_hesap_id is None:
            QMessageBox.critical(self, "Eksik Bilgi", "Lütfen bir İşlem Kasa/Banka hesabı seçin.")
            return

        # Tarih formatı kontrolü
        try:
            datetime.strptime(tarih_str, '%Y-%m-%d')
        except ValueError:
            QMessageBox.critical(self, "Hata", "Tarih formatı 'YYYY-AA-GG' şeklinde olmalıdır.")
            return
            
        if not all([tarih_str, tutar_str, aciklama_str]):
            QMessageBox.critical(self, "Eksik Bilgi", "Lütfen tüm zorunlu alanları doldurun.")
            return

        try:
            tutar_f = float(tutar_str.replace(',', '.'))
            if tutar_f <= 0:
                QMessageBox.critical(self, "Geçersiz Tutar", "Tutar pozitif bir sayı olmalıdır.")
                return
        except ValueError:
            QMessageBox.critical(self, "Giriş Hatası", "Tutar sayısal bir değer olmalıdır.")
            return

        try:
            # self.db.gelir_gider_ekle metodunu çağırıyoruz
            data = {
                "tarih": tarih_str,
                "tip": tip_str,
                "tutar": tutar_f,
                "aciklama": aciklama_str,
                "kasa_banka_id": secili_hesap_id,
                "gelir_siniflandirma_id": gelir_siniflandirma_id_val,
                "gider_siniflandirma_id": gider_siniflandirma_id_val
            }
            success = self.db.gelir_gider_ekle(data)

            if success:
                QMessageBox.information(self, "Başarılı", "Gelir/Gider kaydı başarıyla eklendi.")
                if self.yenile_callback:
                    self.yenile_callback()
                self.accept() # QDialog'u kapat
            else:
                QMessageBox.critical(self, "Hata", "Gelir/Gider kaydı eklenirken bir hata oluştu.")

        except Exception as e:
            error_detail = str(e)
            QMessageBox.critical(self, "Hata", f"Kaydedilirken bir hata oluştu:\n{error_detail}")
            logging.error(f"Gelir/Gider kaydetme hatası: {error_detail}", exc_info=True)
            
class TarihAraligiDialog(QDialog): # simpledialog.Dialog yerine QDialog kullanıldı
    def __init__(self, parent_app, title=None, baslangic_gun_sayisi=30):
        super().__init__(parent_app)
        self.app = parent_app # Ana uygulama referansını tut
        self.bas_tarih_str = (datetime.now() - timedelta(days=baslangic_gun_sayisi)).strftime('%Y-%m-%d')
        self.bit_tarih_str = datetime.now().strftime('%Y-%m-%d')
        self.sonuc = None # Kullanıcının seçtiği tarih aralığını tutacak

        self.setWindowTitle(title if title else "Tarih Aralığı Seçin")
        self.setFixedSize(350, 180) # Sabit boyut
        self.setModal(True) # Modalı olarak ayarla

        main_layout = QVBoxLayout(self)
        form_layout = QGridLayout()
        main_layout.addLayout(form_layout)

        form_layout.addWidget(QLabel("Başlangıç Tarihi (YYYY-AA-GG):"), 0, 0, Qt.AlignLeft)
        self.bas_tarih_entry_dialog = QLineEdit()
        self.bas_tarih_entry_dialog.setText(self.bas_tarih_str)
        form_layout.addWidget(self.bas_tarih_entry_dialog, 0, 1)
        btn_bas_tarih = QPushButton("🗓️")
        btn_bas_tarih.setFixedWidth(30)
        btn_bas_tarih.clicked.connect(lambda: DatePickerDialog(self.app, self.bas_tarih_entry_dialog)) # app referansı kullanıldı
        form_layout.addWidget(btn_bas_tarih, 0, 2)

        form_layout.addWidget(QLabel("Bitiş Tarihi (YYYY-AA-GG):"), 1, 0, Qt.AlignLeft)
        self.bit_tarih_entry_dialog = QLineEdit()
        self.bit_tarih_entry_dialog.setText(self.bit_tarih_str)
        form_layout.addWidget(self.bit_tarih_entry_dialog, 1, 1)
        btn_bit_tarih = QPushButton("🗓️")
        btn_bit_tarih.setFixedWidth(30)
        btn_bit_tarih.clicked.connect(lambda: DatePickerDialog(self.app, self.bit_tarih_entry_dialog)) # app referansı kullanıldı
        form_layout.addWidget(btn_bit_tarih, 1, 2)

        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)
        button_layout.addStretch()

        btn_ok = QPushButton("Onayla")
        btn_ok.clicked.connect(self._apply)
        button_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(self.reject) # QDialog'u reject ile kapat
        button_layout.addWidget(btn_cancel)

        self.bas_tarih_entry_dialog.setFocus() # İlk odaklanılacak widget

    def _apply(self): 
        bas_t_str_dialog = self.bas_tarih_entry_dialog.text()
        bit_t_str_dialog = self.bit_tarih_entry_dialog.text()
        try:
            bas_dt_dialog = datetime.strptime(bas_t_str_dialog, '%Y-%m-%d')
            bit_dt_dialog = datetime.strptime(bit_t_str_dialog, '%Y-%m-%d')
            if bas_dt_dialog > bit_dt_dialog:
                QMessageBox.critical(self, "Tarih Hatası", "Başlangıç tarihi, bitiş tarihinden sonra olamaz.")
                self.sonuc = None 
                return
            self.sonuc = (bas_t_str_dialog, bit_t_str_dialog) 
            self.accept() # QDialog'u accept ile kapat
        except ValueError:
            QMessageBox.critical(self, "Format Hatası", "Tarih formatı YYYY-AA-GG olmalıdır (örn: 2023-12-31).")
            self.sonuc = None
            return

class OdemeTuruSecimDialog(QDialog):
    def __init__(self, parent_app, db_manager, fatura_tipi, initial_cari_id, callback_func):
        super().__init__(parent_app)
        self.app = parent_app
        self.db = db_manager
        self.fatura_tipi = fatura_tipi # 'SATIŞ' veya 'ALIŞ'
        self.initial_cari_id = initial_cari_id
        self.callback_func = callback_func # Seçim sonrası çağrılacak fonksiyon

        self.setWindowTitle("Ödeme Türü Seçimi")
        self.setFixedSize(400, 300) # geometry yerine setFixedSize kullanıldı
        self.setModal(True) # Diğer pencerelere tıklamayı engeller

        self.kasa_banka_map = {} # Kasa/Banka hesaplarını display_text -> ID olarak tutar
        
        main_layout = QVBoxLayout(self)
        title_label = QLabel("Fatura Ödeme Türünü Seçin")
        title_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        form_frame = QFrame(self)
        form_layout = QGridLayout(form_frame)
        main_layout.addWidget(form_frame)

        # Ödeme Türü Seçimi Combobox
        form_layout.addWidget(QLabel("Ödeme Türü (*):"), 0, 0, Qt.AlignLeft)
        self.odeme_turu_cb = QComboBox()
        # Perakende satışsa 'AÇIK HESAP' ve 'ETKİSİZ FATURA' hariç, değilse 'ETKİSİZ FATURA' hariç
        self._set_odeme_turu_values() # Değerleri burada ayarla
        form_layout.addWidget(self.odeme_turu_cb, 0, 1)
        self.odeme_turu_cb.currentIndexChanged.connect(self._odeme_turu_degisince_hesap_combobox_ayarla)
        self.odeme_turu_cb.setCurrentIndex(0) # İlk değeri varsayılan yap

        # İşlem Kasa/Banka Seçimi Combobox
        form_layout.addWidget(QLabel("İşlem Kasa/Banka (*):"), 1, 0, Qt.AlignLeft)
        self.islem_hesap_cb = QComboBox()
        self.islem_hesap_cb.setEnabled(False) # Başlangıçta devre dışı
        form_layout.addWidget(self.islem_hesap_cb, 1, 1)

        # Vade Tarihi Alanı (isteğe bağlı, "AÇIK HESAP" için)
        self.lbl_vade_tarihi = QLabel("Vade Tarihi:")
        self.entry_vade_tarihi = QLineEdit()
        self.entry_vade_tarihi.setEnabled(False) 
        self.btn_vade_tarihi = QPushButton("🗓️")
        self.btn_vade_tarihi.setFixedWidth(30)
        self.btn_vade_tarihi.clicked.connect(lambda: DatePickerDialog(self.app, self.entry_vade_tarihi)) # app referansı kullanıldı
        self.btn_vade_tarihi.setEnabled(False)
        
        # Grid'e ekle ama başlangıçta gizle
        form_layout.addWidget(self.lbl_vade_tarihi, 2, 0, Qt.AlignLeft)
        form_layout.addWidget(self.entry_vade_tarihi, 2, 1)
        form_layout.addWidget(self.btn_vade_tarihi, 2, 2)
        
        self.lbl_vade_tarihi.hide() # Başlangıçta gizle
        self.entry_vade_tarihi.hide()
        self.btn_vade_tarihi.hide()


        form_layout.setColumnStretch(1, 1) # Entry/Combobox sütunu genişleyebilir

        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame)

        btn_onayla = QPushButton("Onayla")
        btn_onayla.clicked.connect(self._onayla)
        button_layout.addWidget(btn_onayla)
        
        button_layout.addStretch() # Sağ tarafa yaslamak için boşluk

        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self.close) # QDialog'u kapat
        button_layout.addWidget(btn_iptal)

        self._yukle_kasa_banka_hesaplarini() # Kasa/Banka hesaplarını yükle
        self._odeme_turu_degisince_hesap_combobox_ayarla() # İlk seçime göre combobox'ı ayarla

    def _set_odeme_turu_values(self):
        """Ödeme türü combobox'ının değerlerini fatura tipine göre ayarlar."""
        all_payment_values = ["NAKİT", "KART", "EFT/HAVALE", "ÇEK", "SENET", "AÇIK HESAP", "ETKİSİZ FATURA"]
        
        # Perakende müşteri mi kontrol et
        is_perakende_musteri = False
        if self.fatura_tipi == 'SATIŞ' and self.initial_cari_id is not None and \
           str(self.initial_cari_id) == str(self.db.perakende_musteri_id):
            is_perakende_musteri = True

        if is_perakende_musteri:
            # Perakende satışsa 'AÇIK HESAP' ve 'ETKİSİZ FATURA' hariç
            self.odeme_turu_cb.addItems([p for p in all_payment_values if p != "AÇIK HESAP" and p != "ETKİSİZ FATURA"])
        else:
            # Diğer durumlarda 'ETKİSİZ FATURA' hariç (çünkü faturalara dönüştürülürken bu tür kullanılmaz)
            self.odeme_turu_cb.addItems([p for p in all_payment_values if p != "ETKİSİZ FATURA"])

    def _yukle_kasa_banka_hesaplarini(self):
        self.islem_hesap_cb.clear()
        self.kasa_banka_map.clear()
        
        try:
            response = requests.get(f"{API_BASE_URL}/kasalar_bankalar/")
            response.raise_for_status()
            hesaplar = response.json()

            if hesaplar:
                for h in hesaplar:
                    # Bakiye formatlaması için db_manager kullanıldı
                    display_text = f"{h.get('hesap_adi')} ({h.get('tip')})"
                    if h.get('tip') == "BANKA" and h.get('banka_adi'):
                        display_text += f" - {h.get('banka_adi')}"
                    if h.get('bakiye') is not None:
                        display_text += f" (Bakiye: {self.db._format_currency(h.get('bakiye'))})"
                        
                    self.kasa_banka_map[display_text] = h.get('id')
                    self.islem_hesap_cb.addItem(display_text, h.get('id'))
    
                self.islem_hesap_cb.setEnabled(True)
                self.islem_hesap_cb.setCurrentIndex(0) # İlk elemanı seç
            else:
                self.islem_hesap_cb.addItem("Hesap Yok", None)
                self.islem_hesap_cb.setEnabled(False)

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Hatası", f"Kasa/Banka hesapları yüklenirken hata: {e}")
            logging.error(f"Kasa/Banka yükleme hatası: {e}", exc_info=True)
            self.islem_hesap_cb.addItem("Hesap Yok", None)
            self.islem_hesap_cb.setEnabled(False)

    def _odeme_turu_degisince_hesap_combobox_ayarla(self):
        secili_odeme_turu = self.odeme_turu_cb.currentText()
        pesin_odeme_turleri = ["NAKİT", "KART", "EFT/HAVALE", "ÇEK", "SENET"]

        # Vade tarihi alanlarının görünürlüğünü ve aktifliğini ayarla
        if secili_odeme_turu == "AÇIK HESAP":
            self.lbl_vade_tarihi.show()
            self.entry_vade_tarihi.show()
            self.btn_vade_tarihi.show()
            self.entry_vade_tarihi.setEnabled(True)
            self.btn_vade_tarihi.setEnabled(True)
            if not self.entry_vade_tarihi.text(): # Eğer boşsa bugünün tarihini varsayılan olarak ata
                self.entry_vade_tarihi.setText(datetime.now().strftime('%Y-%m-%d'))
        else:
            self.lbl_vade_tarihi.hide()
            self.entry_vade_tarihi.hide()
            self.btn_vade_tarihi.hide()
            self.entry_vade_tarihi.setEnabled(False)
            self.entry_vade_tarihi.clear()

        # Kasa/Banka alanının görünürlüğünü ve aktifliğini ayarla
        if secili_odeme_turu in pesin_odeme_turleri:
            self.islem_hesap_cb.setEnabled(True) # Aktif hale getir
            # Varsayılan kasa/bankayı ayarla
            try:
                params = {"varsayilan_odeme_turu": secili_odeme_turu}
                response = requests.get(f"{API_BASE_URL}/kasalar_bankalar/", params=params)
                response.raise_for_status()
                varsayilan_kb_list = response.json()
                
                if varsayilan_kb_list:
                    varsayilan_kb_id = varsayilan_kb_list[0].get('id')
                    index = self.islem_hesap_cb.findData(varsayilan_kb_id)
                    if index != -1:
                        self.islem_hesap_cb.setCurrentIndex(index)
                    else: # Eğer varsayılan bulunamadıysa ama listede başka eleman varsa
                        if self.islem_hesap_cb.count() > 0:
                            self.islem_hesap_cb.setCurrentIndex(0)
                elif self.islem_hesap_cb.count() > 0: # Eğer varsayılan yoksa ama başka eleman varsa
                    self.islem_hesap_cb.setCurrentIndex(0)
                else: # Hiç hesap yoksa
                    self.islem_hesap_cb.clear() # Clear existing items
                    self.islem_hesap_cb.addItem("Hesap Yok", None)
                    self.islem_hesap_cb.setEnabled(False) # Devre dışı bırak

            except requests.exceptions.RequestException as e:
                logging.warning(f"Varsayılan kasa/banka çekilirken hata: {e}")
                if self.islem_hesap_cb.count() > 0: # Hata olursa ilkini seç
                    self.islem_hesap_cb.setCurrentIndex(0)
                else:
                    self.islem_hesap_cb.clear()
                    self.islem_hesap_cb.addItem("Hesap Yok", None)
                    self.islem_hesap_cb.setEnabled(False)
        else: # "AÇIK HESAP" veya "ETKİSİZ FATURA" seçilirse
            self.islem_hesap_cb.clear()
            self.islem_hesap_cb.addItem("Hesap Yok", None)
            self.islem_hesap_cb.setEnabled(False) # Devre dışı bırak

    def _onayla(self):
        """Kullanıcının seçtiği ödeme türü ve kasa/banka bilgilerini ana forma geri gönderir."""
        secili_odeme_turu = self.odeme_turu_cb.currentText()
        secili_hesap_display = self.islem_hesap_cb.currentText()
        vade_tarihi_val = self.entry_vade_tarihi.text().strip()

        kasa_banka_id_val = None
        if secili_hesap_display and secili_hesap_display != "Hesap Yok":
            kasa_banka_id_val = self.kasa_banka_map.get(secili_hesap_display)

        # Zorunlu alan kontrolü
        if not secili_odeme_turu:
            QMessageBox.critical(self, "Eksik Bilgi", "Lütfen bir Ödeme Türü seçin.")
            return

        pesin_odeme_turleri = ["NAKİT", "KART", "EFT/HAVALE", "ÇEK", "SENET"]
        if secili_odeme_turu in pesin_odeme_turleri and kasa_banka_id_val is None:
            QMessageBox.critical(self, "Eksik Bilgi", "Peşin ödeme türleri için bir İşlem Kasa/Banka hesabı seçmelisiniz.")
            return
        
        if secili_odeme_turu == "AÇIK HESAP":
            if not vade_tarihi_val:
                QMessageBox.critical(self, "Eksik Bilgi", "Açık Hesap ödeme türü için Vade Tarihi boş olamaz.")
                return
            try:
                datetime.strptime(vade_tarihi_val, '%Y-%m-%d')
            except ValueError:
                QMessageBox.critical(self, "Tarih Formatı Hatası", "Vade Tarihi formatı (YYYY-AA-GG) olmalıdır.")
                return

        # Callback fonksiyonunu çağır
        self.callback_func(secili_odeme_turu, kasa_banka_id_val, vade_tarihi_val)
        self.accept() # Pencereyi kapat

class TopluVeriEklePenceresi(QDialog):
    def __init__(self, parent_app, db_manager):
        super().__init__(parent_app)
        self.app = parent_app
        self.db = db_manager
        self.setWindowTitle("Toplu Veri Ekleme (Excel)")
        self.setFixedSize(600, 650) # geometry yerine setFixedSize kullanıldı
        self.setModal(True) # Modalı olarak ayarla

        main_layout = QVBoxLayout(self)
        title_label = QLabel("Toplu Veri Ekleme (Excel)")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        main_frame = QFrame(self)
        main_frame_layout = QGridLayout(main_frame)
        main_layout.addWidget(main_frame)

        main_frame_layout.addWidget(QLabel("Veri Tipi:"), 0, 0, Qt.AlignLeft)
        self.veri_tipi_combo = QComboBox()
        self.veri_tipi_combo.addItems(["Müşteri", "Tedarikçi", "Stok/Ürün Ekle/Güncelle"])
        self.veri_tipi_combo.setCurrentText("Müşteri")
        self.veri_tipi_combo.currentIndexChanged.connect(self._show_template_info_and_options)
        main_frame_layout.addWidget(self.veri_tipi_combo, 0, 1)

        main_frame_layout.addWidget(QLabel("Excel Dosyası:"), 1, 0, Qt.AlignLeft)
        self.dosya_yolu_entry = QLineEdit()
        main_frame_layout.addWidget(self.dosya_yolu_entry, 1, 1)
        btn_gozat = QPushButton("Gözat...")
        btn_gozat.clicked.connect(self._gozat_excel_dosyasi)
        main_frame_layout.addWidget(btn_gozat, 1, 2)

        self.stok_guncelleme_options_frame = QGroupBox("Stok/Ürün Güncelleme Seçenekleri", main_frame)
        self.stok_guncelleme_options_layout = QVBoxLayout(self.stok_guncelleme_options_frame)
        main_frame_layout.addWidget(self.stok_guncelleme_options_frame, 2, 0, 1, 3) # Tüm sütunlara yay
        self.stok_guncelleme_options_frame.hide() # Başlangıçta gizli

        self.cb_vars = {} # Boolean değişkenleri için sözlük gibi kullanılacak
        self.cb_vars['fiyat_bilgileri'] = QCheckBox("Fiyat Bilgileri (Alış/Satış/KDV)")
        self.stok_guncelleme_options_layout.addWidget(self.cb_vars['fiyat_bilgileri'])
        self.cb_vars['urun_nitelikleri'] = QCheckBox("Ürün Nitelikleri (Kategori/Marka/Grup/Birim/Menşe/Detay)")
        self.stok_guncelleme_options_layout.addWidget(self.cb_vars['urun_nitelikleri'])
        self.cb_vars['stok_miktari'] = QCheckBox("Stok Miktarı (Mevcut/Minimum)")
        self.stok_guncelleme_options_layout.addWidget(self.cb_vars['stok_miktari'])
        
        self.cb_tumu = QCheckBox("Tümü (Yukarıdakilerin hepsi)")
        self.cb_tumu.stateChanged.connect(self._toggle_all_checkboxes)
        self.stok_guncelleme_options_layout.addWidget(self.cb_tumu)
        
        self.template_info_label = QLabel()
        self.template_info_label.setWordWrap(True)
        self.template_info_label.setAlignment(Qt.AlignLeft)
        main_frame_layout.addWidget(self.template_info_label, 3, 0, 1, 2) # İki sütuna yay

        self.detayli_aciklama_button = QPushButton("Detaylı Bilgi / Şablon Açıklaması")
        self.detayli_aciklama_button.clicked.connect(self._show_detayli_aciklama_penceresi)
        main_frame_layout.addWidget(self.detayli_aciklama_button, 3, 2, Qt.AlignRight | Qt.AlignTop)
        self.detayli_aciklama_button.hide() # Başlangıçta gizli

        main_frame_layout.setColumnStretch(1, 1) # Excel Dosyası entry'sinin genişlemesi için

        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame)

        btn_yukle = QPushButton("Verileri Yükle")
        btn_yukle.clicked.connect(self._verileri_yukle)
        button_layout.addWidget(btn_yukle)
        
        btn_sablon_indir = QPushButton("Örnek Şablon İndir")
        btn_sablon_indir.clicked.connect(self._excel_sablonu_indir)
        button_layout.addWidget(btn_sablon_indir)
        
        button_layout.addStretch() # Sağa yaslama
        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self.close)
        button_layout.addWidget(btn_iptal)

        self.analysis_results = None
        self._show_template_info_and_options() # Başlangıç durumunu ayarla
        self.adjustSize() # Pencere boyutunu içeriğe göre ayarla


    def _show_template_info_and_options(self):
        selected_type = self.veri_tipi_combo.currentText()
        short_info_text = ""
        if selected_type == "Stok/Ürün Ekle/Güncelle":
            self.stok_guncelleme_options_frame.show()
            self.detayli_aciklama_button.show()
        else:
            self.stok_guncelleme_options_frame.hide()
            self.detayli_aciklama_button.hide()
            self.cb_tumu.setChecked(False) # "Tümü" checkbox'ını kaldır
            self._toggle_all_checkboxes(Qt.Unchecked, force_off=True) # Tüm diğer checkbox'ları kapat
            
        if selected_type == "Müşteri":
            short_info_text = "Müşteri Excel dosyası:\n`Müşteri Kodu`, `Ad Soyad` (ZORUNLU) ve diğer detaylar."
        elif selected_type == "Tedarikçi":
            short_info_text = "Tedarikçi Excel dosyası:\n`Tedarikçi Kodu`, `Ad Soyad` (ZORUNLU) ve diğer detaylar."
        elif selected_type == "Stok/Ürün Ekle/Güncelle":
            short_info_text = "Stok/Ürün Excel dosyası:\n`Ürün Kodu`, `Ürün Adı` (ZORUNLU) ve diğer detaylar.\nGüncellemek istediğiniz alanları yukarıdan seçin. Detaylı şablon bilgisi için butona tıklayın."
        self.template_info_label.setText(short_info_text)

    def _excel_sablonu_indir(self):
        veri_tipi = self.veri_tipi_combo.currentText()
        if not veri_tipi: 
            QMessageBox.warning(self, "Uyarı", "Lütfen şablon indirmek için bir veri tipi seçin.")
            return
        
        file_name_prefix, headers = "", []
        if veri_tipi == "Müşteri": file_name_prefix, headers = "Musteri_Sablonu", ["Müşteri Kodu", "Ad Soyad", "Telefon", "Adres", "Vergi Dairesi", "Vergi No"]
        elif veri_tipi == "Tedarikçi": file_name_prefix, headers = "Tedarikci_Sablonu", ["Tedarikçi Kodu", "Ad Soyad", "Telefon", "Adres", "Vergi Dairesi", "Vergi No"]
        elif veri_tipi == "Stok/Ürün Ekle/Güncelle": file_name_prefix, headers = "Stok_Urun_Sablonu", ["Ürün Kodu", "Ürün Adı", "Miktar", "Alış Fiyatı (KDV Dahil)", "Satış Fiyatı (KDV Dahil)", "KDV Oranı (%)", "Minimum Stok Seviyesi", "Kategori Adı", "Marka Adı", "Ürün Grubu Adı", "Ürün Birimi Adı", "Menşe Ülke Adı", "Ürün Detayı", "Ürün Resmi Yolu"]
        else: 
            QMessageBox.critical(self, "Hata", "Geçersiz veri tipi seçimi.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Excel Şablonunu Kaydet", 
                                                    f"{file_name_prefix}_{datetime.now().strftime('%Y%m%d')}.xlsx", 
                                                    "Excel Dosyaları (*.xlsx);;Tüm Dosyalar (*)")
        if file_path:
            try:
                workbook = openpyxl.Workbook(); sheet = workbook.active; sheet.title = "Veri Şablonu"; sheet.append(headers)
                for col_idx, header in enumerate(headers, 1):
                    cell = sheet.cell(row=1, column=col_idx); cell.font = openpyxl.styles.Font(bold=True)
                    sheet.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = max(len(header) + 2, 15)
                workbook.save(file_path)
                QMessageBox.information(self, "Başarılı", f"'{veri_tipi}' şablonu başarıyla oluşturuldu:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Şablon oluşturulurken bir hata oluştu: {e}")

    def _show_detayli_aciklama_penceresi(self):
        selected_type = self.veri_tipi_combo.currentText()
        title = f"{selected_type} Şablon Açıklaması"
        message = ""
        if selected_type == "Müşteri": message = "Müşteri Veri Şablonu Detayları:\n\nExcel dosyasının ilk satırı başlık (header) olmalıdır. Veriler ikinci satırdan başlamalıdır.\n\nSütun Sırası ve Açıklamaları:\n1.  **Müşteri Kodu (ZORUNLU):** Müşterinin benzersiz kodu.\n2.  **Ad Soyad (ZORUNLU):** Müşterinin tam adı veya şirket adı.\n3.  **Telefon (İsteğe Bağlı)**\n4.  **Adres (İsteğe Bağlı)**\n5.  **Vergi Dairesi (İsteğe Bağlı)**\n6.  **Vergi No (İsteğe Bağlı)**"
        elif selected_type == "Tedarikçi": message = "Tedarikçi Veri Şablonu Detayları:\n\nExcel dosyasının ilk satırı başlık (header) olmalıdır. Veriler ikinci satırdan başlamalıdır.\n\nSütun Sırası ve Açıklamaları:\n1.  **Tedarikçi Kodu (ZORUNLU):** Tedarikçinin benzersiz kodu.\n2.  **Ad Soyad (ZORUNLU):** Tedarikçinin tam adı veya şirket adı.\n3.  **Telefon (İsteğe Bağlı)**\n4.  **Adres (İsteğe Bağlı)**\n5.  **Vergi Dairesi (İsteğe Bağlı)**\n6.  **Vergi No (İsteğe Bağlı)**"
        elif selected_type == "Stok/Ürün Ekle/Güncelle": message = "Stok/Ürün Veri Şablonu Detayları:\n\n'Ürün Kodu' eşleşirse güncelleme, eşleşmezse yeni kayıt yapılır.\n\nSütunlar:\n1.  **Ürün Kodu (ZORUNLU)**\n2.  **Ürün Adı (Yeni ürün için ZORUNLU)**\n3.  **Miktar (İsteğe Bağlı):** Pozitif girilirse, mevcut stoğa eklemek için bir 'ALIŞ' faturası oluşturulur.\n4.  **Alış Fiyatı (KDV Dahil) (İsteğe Bağlı)**\n5.  **Satış Fiyatı (KDV Dahil) (İsteğe Bağlı)**\n6.  **KDV Oranı (%) (İsteğe Bağlı)**\n7.  **Minimum Stok Seviyesi (İsteğe Bağlı)**\n8.  **Kategori Adı (İsteğe Bağlı)**\n9.  **Marka Adı (İsteğe Bağlı)**\n10. **Ürün Grubu Adı (İsteğe Bağlı)**\n11. **Ürün Birimi Adı (İsteğe Bağlı)**\n12. **Menşe Ülke Adı (İsteğe Bağlı)**\n13. **Ürün Detayı (İsteğe Bağlı)**\n14. **Ürün Resmi Yolu (İsteğe Bağlı):** Resim dosyasının tam yolu (ör: C:/resimler/urun1.png)."
        from pencereler import AciklamaDetayPenceresi # PySide6 dialog
        AciklamaDetayPenceresi(self, title, message).exec()

    def _gozat_excel_dosyasi(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Excel Dosyası Seç", "", "Excel Dosyaları (*.xlsx;*.xls);;Tüm Dosyalar (*)")
        if file_path:
            self.dosya_yolu_entry.setText(file_path)

    def _toggle_all_checkboxes(self, state, force_off=False):
        # state QCheckBox.Checked (2) veya QCheckBox.Unchecked (0) olabilir
        is_checked = (state == Qt.Checked) if not force_off else False
        for key, checkbox in self.cb_vars.items():
            checkbox.setChecked(is_checked)

    def _verileri_yukle(self):
        dosya_yolu = self.dosya_yolu_entry.text().strip()
        veri_tipi = self.veri_tipi_combo.currentText()
        if not dosya_yolu or not os.path.exists(dosya_yolu):
            QMessageBox.critical(self, "Dosya Hatası", "Lütfen geçerli bir Excel dosyası seçin.")
            return
        
        # Seçili güncelleme alanlarını al
        selected_update_fields = []
        if self.cb_tumu.isChecked():
            # "Tümü" seçiliyse, tüm alt seçenekleri ekle
            selected_update_fields = [key for key in self.cb_vars.keys()]
        else:
            # "Tümü" seçili değilse, tek tek seçili olanları ekle
            selected_update_fields = [key for key, checkbox in self.cb_vars.items() if checkbox.isChecked()]
            
        from pencereler import BeklemePenceresi # PySide6 dialog
        bekleme_penceresi = BeklemePenceresi(self, message="Excel okunuyor ve veriler analiz ediliyor...")
        # PySide6'da QTimer.singleShot ile UI güncellemeleri main thread'de yapılmalı.
        # Threading başlatmadan önce bekleme penceresini göster
        QTimer.singleShot(0, bekleme_penceresi.exec) # Modalı olarak göster

        # Analizi ayrı bir thread'de çalıştır
        threading.Thread(target=self._analiz_et_ve_onizle_threaded, 
                         args=(dosya_yolu, veri_tipi, selected_update_fields, bekleme_penceresi)).start()

    def _analiz_et_ve_onizle_threaded(self, dosya_yolu, veri_tipi, selected_update_fields, bekleme_penceresi):
        analysis_results = {}
        try:
            workbook = openpyxl.load_workbook(dosya_yolu, data_only=True)
            sheet = workbook.active
            
            raw_data_from_excel_list = []
            for row_obj in sheet.iter_rows(min_row=2):
                if any(cell.value is not None and str(cell.value).strip() != '' for cell in row_obj):
                    row_values = [cell.value for cell in row_obj]
                    raw_data_from_excel_list.append(row_values)

            if not raw_data_from_excel_list:
                raise ValueError("Excel dosyasında okunacak geçerli veri bulunamadı.")
            
            # Hizmetler sınıfından TopluIslemService kullanılıyor varsayımı
            from hizmetler import TopluIslemService # TopluIslemService'i import et
            # Geçici bir db_manager ve FaturaService örneği oluştur (threading için)
            local_db_manager = self.db.__class__(data_dir=self.db.data_dir) # Aynı db örneğini yeniden yarat
            # FaturaService'in OnMuhasebe (SQLite) ile uyumlu constructor'ı varsayılıyor
            from hizmetler import FaturaService 
            local_fatura_service = FaturaService(local_db_manager)
            local_toplu_islem_service = TopluIslemService(local_db_manager, local_fatura_service)

            if veri_tipi == "Müşteri":
                analysis_results = local_toplu_islem_service.toplu_musteri_analiz_et(raw_data_from_excel_list)
            elif veri_tipi == "Tedarikçi":
                analysis_results = local_toplu_islem_service.toplu_tedarikci_analiz_et(raw_data_from_excel_list)
            elif veri_tipi == "Stok/Ürün Ekle/Güncelle":
                analysis_results = local_toplu_islem_service.toplu_stok_analiz_et(raw_data_from_excel_list, selected_update_fields)
            
            # UI güncellemeleri ana thread'e gönderilmeli
            QTimer.singleShot(0, bekleme_penceresi.close) # Bekleme penceresini kapat
            QTimer.singleShot(0, lambda: self._onizleme_penceresini_ac(veri_tipi, analysis_results))

        except Exception as e:
            QTimer.singleShot(0, bekleme_penceresi.close)
            QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Hata", f"Veri analizi başarısız oldu:\n{e}"))
            logging.error(f"Toplu veri analizi thread'inde hata: {e}", exc_info=True)
        finally:
            if 'local_db_manager' in locals() and local_db_manager.conn:
                local_db_manager.conn.close() # Thread'e özgü DB bağlantısını kapat

    def _onizleme_penceresini_ac(self, veri_tipi, analysis_results):
        from pencereler import TopluVeriOnizlemePenceresi
        dialog = TopluVeriOnizlemePenceresi(self.app, self.db, veri_tipi, analysis_results, 
                                            callback_on_confirm=self._gercek_yazma_islemini_yap_threaded_from_onizleme)
        dialog.exec() # Modalı olarak göster

    def _gercek_yazma_islemini_yap_threaded_from_onizleme(self, veri_tipi, analysis_results):
        from pencereler import BeklemePenceresi # PySide6 dialog
        bekleme_penceresi_gercek_islem = BeklemePenceresi(
            self.app, 
            message=f"Toplu {veri_tipi} veritabanına yazılıyor, lütfen bekleyiniz..."
        )
        QTimer.singleShot(0, bekleme_penceresi_gercek_islem.exec)

        threading.Thread(target=self._yazma_islemi_threaded, args=(
            veri_tipi, 
            analysis_results, 
            bekleme_penceresi_gercek_islem
        )).start()

    def _yazma_islemi_threaded(self, veri_tipi, analysis_results, bekleme_penceresi):
        local_db_manager = None
        try:
            from veritabani import OnMuhasebe 
            from hizmetler import FaturaService, TopluIslemService

            local_db_manager = OnMuhasebe(data_dir=self.db.data_dir) # db_name parametresi kaldırıldı, data_dir yeterli
            local_db_manager.app = self.app 

            local_fatura_service = FaturaService(local_db_manager)
            local_toplu_islem_service = TopluIslemService(local_db_manager, local_fatura_service)

            # Transaction'ı burada, bu thread içinde başlat
            local_db_manager.conn.execute("BEGIN TRANSACTION")

            data_to_process = analysis_results.get('all_processed_data', [])
            success, message = False, f"Bilinmeyen veri tipi: {veri_tipi}"
            
            if veri_tipi == "Müşteri":
                success, message = local_toplu_islem_service.toplu_musteri_ekle_guncelle(data_to_process)
            elif veri_tipi == "Tedarikçi":
                success, message = local_toplu_islem_service.toplu_tedarikci_ekle_guncelle(data_to_process)
            elif veri_tipi == "Stok/Ürün Ekle/Güncelle":
                success, message = local_toplu_islem_service.toplu_stok_ekle_guncelle(data_to_process, analysis_results.get('selected_update_fields_from_ui', []))
            
            if success:
                local_db_manager.conn.commit() 
            else:
                local_db_manager.conn.rollback() 

            QTimer.singleShot(0, bekleme_penceresi.close)
            if success:
                QTimer.singleShot(0, lambda: QMessageBox.information(self, "Başarılı", f"Toplu {veri_tipi} işlemi tamamlandı:\n{message}"))
                QTimer.singleShot(0, lambda: self._refresh_related_lists(veri_tipi))
                QTimer.singleShot(0, self.accept) # Pencereyi kapat
            else:
                QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Hata", f"Toplu {veri_tipi} işlemi başarısız oldu:\n{message}"))
        
        except Exception as e:
            if local_db_manager and local_db_manager.conn: 
                local_db_manager.conn.rollback()
            QTimer.singleShot(0, bekleme_penceresi.close)
            QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Kritik Hata", f"Yazma işlemi sırasında beklenmedik bir hata oluştu: {e}"))
            logging.error(f"Toplu yazma işlemi thread'inde hata: {e}", exc_info=True)
        
        finally:
            if local_db_manager and local_db_manager.conn:
                local_db_manager.conn.close()

    def _refresh_related_lists(self, veri_tipi):
        # UI'daki sekme sayfalarını yenileme
        if veri_tipi == "Müşteri" and hasattr(self.app, 'musteri_yonetimi_sayfasi'): 
            self.app.musteri_yonetimi_sayfasi.musteri_listesini_yenile()
        elif veri_tipi == "Tedarikçi" and hasattr(self.app, 'tedarikci_yonetimi_sayfasi'):
            self.app.tedarikci_yonetimi_sayfasi.tedarikci_listesini_yenile()
        elif veri_tipi == "Stok/Ürün Ekle/Güncelle" and hasattr(self.app, 'stok_yonetimi_sayfasi'):
            self.app.stok_yonetimi_sayfasi.stok_listesini_yenile()
        if hasattr(self.app, 'ana_sayfa'):
            self.app.ana_sayfa.guncelle_ozet_bilgiler()

class AciklamaDetayPenceresi(QDialog):
    def __init__(self, parent_app, title="Detaylı Bilgi", message_text=""):
        super().__init__(parent_app)
        self.setWindowTitle(title)
        self.setFixedSize(600, 400) # geometry yerine setFixedSize kullanıldı
        self.setModal(True) # Modalı olarak ayarla

        # Pencereyi ortalamak için
        self.move(parent_app.pos() + parent_app.rect().center() - self.rect().center())

        main_layout = QVBoxLayout(self)
        self.text_widget = QTextEdit() # tk.Text yerine QTextEdit kullanıldı
        self.text_widget.setPlainText(message_text)
        self.text_widget.setReadOnly(True) # config(state=tk.DISABLED) yerine setReadOnly
        
        main_layout.addWidget(self.text_widget)

        # QScrollArea içinde QTextEdit otomatik kaydırma çubuklarını yönetir, ek scrollbar gerekmez
        # tk.Text'teki vsb kısmı kaldırıldı

        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.close) # QDialog'u kapat
        main_layout.addWidget(btn_kapat, alignment=Qt.AlignCenter) # Ortala

class CariSecimPenceresi(QDialog):
    def __init__(self, parent_window, db_manager, fatura_tipi, callback_func):
        super().__init__(parent_window) 
        self.app = parent_window.app # parent_window'un içindeki app referansını al
        self.db = db_manager
        # Fatura tipini (müşteri/tedarikçi seçimi için) kesinleştir
        if fatura_tipi in ['SATIŞ', 'SATIŞ İADE']:
            self.fatura_tipi = 'SATIŞ' # Cari seçim penceresi için sadece 'SATIŞ' veya 'ALIŞ' olmalı
        elif fatura_tipi in ['ALIŞ', 'ALIŞ İADE']:
            self.fatura_tipi = 'ALIŞ'
        else:
            self.fatura_tipi = 'SATIŞ' # Varsayılan
        self.callback_func = callback_func

        self.setWindowTitle("Cari Seçimi")
        self.setFixedSize(600, 450) # geometry yerine setFixedSize kullanıldı
        self.setModal(True) # Diğer pencerelere tıklamayı engeller

        self.tum_cariler_cache_data = [] 
        self.cari_map_display_to_id = {} 

        # Pencere başlığını fatura_tipi'ne göre doğru ayarla (artık self.fatura_tipi sadece 'SATIŞ' veya 'ALIŞ' olacak)
        if self.fatura_tipi == 'SATIŞ':
            baslik_text = "Müşteri Seçimi"
        elif self.fatura_tipi == 'ALIŞ':
            baslik_text = "Tedarikçi Seçimi"
        else: 
            baslik_text = "Cari Seçimi (Hata)" 

        title_label = QLabel(baslik_text)
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(title_label)

        # Arama Çerçevesi
        search_frame = QFrame(self)
        search_layout = QHBoxLayout(search_frame)
        main_layout.addWidget(search_frame)

        search_layout.addWidget(QLabel("Ara (Ad/Kod):"), Qt.AlignLeft)
        self.search_entry = QLineEdit()
        self.search_entry.textChanged.connect(self._filtre_liste)
        search_layout.addWidget(self.search_entry)
        search_layout.setStretchFactor(self.search_entry, 1) # Genişlemesi için

        # Cari Listesi Treeview
        tree_frame = QFrame(self)
        tree_layout = QVBoxLayout(tree_frame)
        main_layout.addWidget(tree_frame)

        self.cari_tree = QTreeWidget()
        self.cari_tree.setHeaderLabels(["Cari Adı", "Kodu"])
        self.cari_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cari_tree.setSortingEnabled(True) # Sıralama özelliği
        
        self.cari_tree.setColumnWidth(0, 300) # Cari Adı sütun genişliği
        self.cari_tree.header().setSectionResizeMode(0, QHeaderView.Stretch) # Cari Adı genişlesin
        self.cari_tree.setColumnWidth(1, 100) # Kodu sütun genişliği
        self.cari_tree.headerItem().setTextAlignment(1, Qt.AlignCenter) # Kodu sütununu ortala

        tree_layout.addWidget(self.cari_tree)
        
        self.cari_tree.itemDoubleClicked.connect(self._sec) # Çift tıklama ile seçim

        # Butonlar
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame)

        btn_sec = QPushButton("Seç")
        btn_sec.clicked.connect(self._sec)
        button_layout.addWidget(btn_sec)
        
        button_layout.addStretch() # Sağ tarafa yaslamak için boşluk

        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self.close) # QDialog'u kapat
        button_layout.addWidget(btn_iptal)

        # Başlangıç yüklemesi
        self._yukle_carileri()
        self.search_entry.setFocus()
    
    def _yukle_carileri(self):
        """Tüm carileri (müşteri veya tedarikçi) API'den çeker ve listeler."""
        self.tum_cariler_cache_data = [] 
        self.cari_map_display_to_id = {} 
        
        try:
            api_url = ""
            kod_anahtari_db = ''
            if self.fatura_tipi == 'SATIŞ': 
                api_url = f"{API_BASE_URL}/musteriler/"
                kod_anahtari_db = 'kod' 
            elif self.fatura_tipi == 'ALIŞ': 
                api_url = f"{API_BASE_URL}/tedarikciler/"
                kod_anahtari_db = 'tedarikci_kodu' 
            
            if api_url:
                response = requests.get(api_url)
                response.raise_for_status()
                cariler = response.json() # API'den gelen JSON verisi
                
                for c in cariler: # c: dict objesi
                    cari_id = c.get('id')
                    cari_ad = c.get('ad')
                    cari_kodu = c.get(kod_anahtari_db, "")
                    
                    display_text = f"{cari_ad} (Kod: {cari_kodu})" 
                    self.cari_map_display_to_id[display_text] = str(cari_id) 
                    self.tum_cariler_cache_data.append(c) 
            
            self._filtre_liste() 

            # Varsayılan seçimi yap
            default_id_str = None
            if self.fatura_tipi == 'SATIŞ' and self.db.perakende_musteri_id is not None:
                default_id_str = str(self.db.perakende_musteri_id)
            elif self.fatura_tipi == 'ALIŞ' and self.db.genel_tedarikci_id is not None:
                default_id_str = str(self.db.genel_tedarikci_id)
            
            if default_id_str:
                # Treeview'deki item'ı ID'sine göre bul ve seç
                for i in range(self.cari_tree.topLevelItemCount()):
                    item = self.cari_tree.topLevelItem(i)
                    if item.data(0, Qt.UserRole) == int(default_id_str): # UserRole'a kaydettiğimiz ID ile karşılaştır
                        item.setSelected(True)
                        self.cari_tree.scrollToItem(item)
                        break

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Hatası", f"Cari listesi çekilirken hata: {e}")
            logging.error(f"Cari listesi yükleme hatası: {e}", exc_info=True)


    def _filtre_liste(self): # event parametresi kaldırıldı
        # Arama terimini al ve normalleştir
        arama_terimi = self.search_entry.text().lower().strip()
        normalized_arama_terimi = normalize_turkish_chars(arama_terimi) 

        # Treeview'i temizle
        self.cari_tree.clear()

        # Önbelleğe alınmış cari verileri üzerinde döngü
        for cari_row in self.tum_cariler_cache_data: # cari_row: dict objesi
            cari_id = cari_row.get('id')
            cari_ad = cari_row.get('ad')
            
            cari_kodu = ""
            try:
                if self.fatura_tipi == 'SATIŞ': 
                    cari_kodu = cari_row.get('kod', '')
                else: # ALIŞ
                    cari_kodu = cari_row.get('tedarikci_kodu', '')
            except KeyError:
                cari_kodu = "" 
            
            # Cari adını ve kodunu normalleştirerek karşılaştırma yapalım.
            normalized_cari_ad = normalize_turkish_chars(cari_ad) if cari_ad else ''
            normalized_cari_kodu = normalize_turkish_chars(cari_kodu) if cari_kodu else ''

            # Filtreleme koşulu
            if (not normalized_arama_terimi or
                (normalized_cari_ad and normalized_arama_terimi in normalized_cari_ad) or
                (normalized_cari_kodu and normalized_arama_terimi in normalized_cari_kodu)
               ):
                item_qt = QTreeWidgetItem(self.cari_tree)
                item_qt.setText(0, cari_ad)
                item_qt.setText(1, cari_kodu)
                item_qt.setData(0, Qt.UserRole, cari_id) # ID'yi UserRole olarak sakla


    def _sec(self, item=None, column=None): # item ve column QTreeWidget sinyalinden gelir
        selected_items = self.cari_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Seçim Yok", "Lütfen bir cari seçin.")
            return

        selected_cari_id = selected_items[0].data(0, Qt.UserRole) # UserRole'dan ID'yi al
        selected_cari_display_text = selected_items[0].text(0) # Cari Adı sütunu
        
        self.callback_func(selected_cari_id, selected_cari_display_text) # Callback'i çağır
        self.accept() # QDialog'u kapat

class TedarikciSecimDialog(QDialog):
    def __init__(self, parent_window, db_manager, callback_func):
        super().__init__(parent_window) 
        self.app = parent_window.app # parent_window'un içindeki app referansını al
        self.db = db_manager
        self.callback_func = callback_func

        self.setWindowTitle("Tedarikçi Seçimi")
        self.setFixedSize(600, 400) # geometry yerine setFixedSize kullanıldı
        self.setModal(True) # Modalı olarak ayarla

        self.tum_tedarikciler_cache = [] # Data dict'lerini saklar

        main_layout = QVBoxLayout(self)
        title_label = QLabel("Tedarikçi Seçimi")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # Arama Çerçevesi
        search_frame = QFrame(self)
        search_layout = QHBoxLayout(search_frame)
        main_layout.addWidget(search_frame)

        search_layout.addWidget(QLabel("Ara (Ad/Kod):"), Qt.AlignLeft)
        self.search_entry = QLineEdit()
        self.search_entry.textChanged.connect(self._filtre_liste)
        search_layout.addWidget(self.search_entry)
        search_layout.setStretchFactor(self.search_entry, 1) # Genişlemesi için

        # Tedarikçi Listesi Treeview
        tree_frame = QFrame(self)
        tree_layout = QVBoxLayout(tree_frame)
        main_layout.addWidget(tree_frame)

        self.tedarikci_tree = QTreeWidget()
        self.tedarikci_tree.setHeaderLabels(["Tedarikçi Adı", "Kodu"])
        self.tedarikci_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tedarikci_tree.setSortingEnabled(True)

        self.tedarikci_tree.setColumnWidth(0, 300) # Tedarikçi Adı sütun genişliği
        self.tedarikci_tree.header().setSectionResizeMode(0, QHeaderView.Stretch) # Tedarikçi Adı genişlesin
        self.tedarikci_tree.setColumnWidth(1, 100) # Kodu sütun genişliği
        self.tedarikci_tree.headerItem().setTextAlignment(1, Qt.AlignCenter) # Kodu sütununu ortala

        tree_layout.addWidget(self.tedarikci_tree)
        
        self.tedarikci_tree.itemDoubleClicked.connect(self._sec) # Çift tıklama ile seçim

        # Butonlar
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame)

        btn_sec = QPushButton("Seç")
        btn_sec.clicked.connect(self._sec)
        button_layout.addWidget(btn_sec)
        
        button_layout.addStretch() # Sağ tarafa yaslamak için boşluk

        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self.close) # QDialog'u kapat
        button_layout.addWidget(btn_iptal)

        # Başlangıç yüklemesi
        self._yukle_tedarikcileri()
        self.search_entry.setFocus()
    
    def _yukle_tedarikcileri(self):
        """Tüm tedarikçileri API'den çeker ve listeler."""
        self.tum_tedarikciler_cache = [] 
                
        try:
            response = requests.get(f"{API_BASE_URL}/tedarikciler/")
            response.raise_for_status()
            tedarikciler = response.json() # API'den gelen JSON verisi
            self.tum_tedarikciler_cache = tedarikciler
            self._filtre_liste() 

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Hatası", f"Tedarikçi listesi çekilirken hata: {e}")
            logging.error(f"Tedarikçi listesi yükleme hatası: {e}", exc_info=True)


    def _filtre_liste(self): # event parametresi kaldırıldı
        """Arama kutusuna yazıldıkça tedarikçi listesini filtreler."""
        # Arama terimini al ve normalleştir
        arama_terimi = self.search_entry.text().lower().strip()
        normalized_arama_terimi = normalize_turkish_chars(arama_terimi) 
        
        # Treeview'i temizle
        self.tedarikci_tree.clear()
        
        # Önbelleğe alınmış tedarikçi verileri üzerinde döngü.
        for tedarikci_row in self.tum_tedarikciler_cache: # tedarikci_row: dict objesi
            tedarikci_id = tedarikci_row.get('id')
            tedarikci_kodu = tedarikci_row.get('tedarikci_kodu', '')
            tedarikci_ad = tedarikci_row.get('ad')
            
            # Tedarikçi adını ve kodunu normalleştirerek karşılaştırma yapalım.
            normalized_tedarikci_ad = normalize_turkish_chars(tedarikci_ad) if tedarikci_ad else ''
            normalized_tedarikci_kodu = normalize_turkish_chars(tedarikci_kodu) if tedarikci_kodu else ''
            
            # Filtreleme koşulu
            if (not normalized_arama_terimi or
                (normalized_tedarikci_ad and normalized_arama_terimi in normalized_tedarikci_ad) or
                (normalized_tedarikci_kodu and normalized_arama_terimi in normalized_tedarikci_kodu)
               ):
                item_qt = QTreeWidgetItem(self.tedarikci_tree)
                item_qt.setText(0, tedarikci_ad)
                item_qt.setText(1, tedarikci_kodu)
                item_qt.setData(0, Qt.UserRole, tedarikci_id) # ID'yi UserRole olarak sakla

    def _sec(self, item=None, column=None): # item ve column QTreeWidget sinyalinden gelir
        """Seçili tedarikçiyi onaylar ve callback fonksiyonunu çağırır."""
        selected_items = self.tedarikci_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Seçim Yok", "Lütfen bir tedarikçi seçin.")
            return

        selected_tedarikci_id = selected_items[0].data(0, Qt.UserRole) # UserRole'dan ID'yi al
        selected_tedarikci_ad = selected_items[0].text(0) # Tedarikçi Adı sütunu
        
        self.callback_func(selected_tedarikci_id, selected_tedarikci_ad) # Callback'i çağır
        self.accept() # Pencereyi kapat  

class BeklemePenceresi(QDialog):
    def __init__(self, parent_app, title="İşlem Devam Ediyor...", message="Lütfen bekleyiniz..."):
        super().__init__(parent_app)
        self.setWindowTitle(title)
        self.setFixedSize(300, 120) # geometry yerine setFixedSize kullanıldı
        self.setModal(True) # Modalı olarak ayarla ve diğer etkileşimleri engelle

        # Pencereyi ana pencerenin ortasına konumlandır
        if parent_app:
            parent_rect = parent_app.geometry()
            x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
            y = parent_rect.y() + (parent_rect.height() - self.height()) // 2
            self.move(x, y)

        main_layout = QVBoxLayout(self)
        message_label = QLabel(message)
        message_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(message_label)
        
        self.progressbar = QProgressBar() # ttk.Progressbar yerine QProgressBar kullanıldı
        self.progressbar.setRange(0, 0) # Belirsiz (indeterminate) mod için
        main_layout.addWidget(self.progressbar, alignment=Qt.AlignCenter)
        
        self.setWindowFlags(Qt.FramelessWindowHint) # Çerçevesiz pencere
        self.setAttribute(Qt.WA_DeleteOnClose) # Kapatıldığında otomatik sil
        
        # Pencere kapatma olayını engelle (kullanıcının kapatmasını önle)
        self.setWindowModality(Qt.ApplicationModal)
        self.closeEvent = self._do_nothing_close_event

    def _do_nothing_close_event(self, event):
        # Kullanıcının pencereyi kapatmasını engelle
        event.ignore()

    def kapat(self):
        self.close() # QDialog'u kapat
        
class GelirGiderSiniflandirmaYonetimiPenceresi(QDialog):
    def __init__(self, parent_app, db_manager, yenile_callback):
        super().__init__(parent_app)
        self.db = db_manager
        self.app = parent_app
        self.yenile_callback = yenile_callback # Ana pencereyi yenilemek için

        self.setWindowTitle("Gelir/Gider Sınıflandırma Yönetimi")
        self.setMinimumSize(600, 450)
        self.setModal(True)

        main_layout = QVBoxLayout(self)

        # Notebook (Sekmeler) oluştur
        self.notebook = QTabWidget(self)
        main_layout.addWidget(self.notebook)

        # Gelir Sınıflandırmaları Sekmesi
        self.gelir_frame = QWidget()
        self.notebook.addTab(self.gelir_frame, "Gelir Sınıflandırmaları")
        self._setup_siniflandirma_sekmesi(self.gelir_frame, "GELİR")

        # Gider Sınıflandırmaları Sekmesi
        self.gider_frame = QWidget()
        self.notebook.addTab(self.gider_frame, "Gider Sınıflandırmaları")
        self._setup_siniflandirma_sekmesi(self.gider_frame, "GİDER")

        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.close)
        main_layout.addWidget(btn_kapat, alignment=Qt.AlignRight)

        # Sağ tık menüsü (Ortak olabilir)
        self.context_menu = QMenu(self)
        self.context_menu.addAction("Güncelle").triggered.connect(self._siniflandirma_guncelle)
        self.context_menu.addAction("Sil").triggered.connect(self._siniflandirma_sil)


    def _setup_siniflandirma_sekmesi(self, parent_frame, tip):
        frame_layout = QVBoxLayout(parent_frame) # Çerçeveye bir layout ata

        # Arama ve Ekleme alanı
        top_frame = QFrame(parent_frame)
        top_layout = QHBoxLayout(top_frame)
        frame_layout.addWidget(top_frame)

        top_layout.addWidget(QLabel("Yeni Sınıflandırma Adı:"))
        entry = QLineEdit()
        top_layout.addWidget(entry)
        
        add_button = QPushButton("Ekle")
        add_button.clicked.connect(lambda: self._siniflandirma_ekle(tip, entry.text().strip(), entry))
        top_layout.addWidget(add_button)

        # Treeview alanı
        tree_frame = QFrame(parent_frame)
        tree_layout = QVBoxLayout(tree_frame)
        frame_layout.addWidget(tree_frame)

        tree = QTreeWidget()
        tree.setHeaderLabels(["ID", "Sınıflandırma Adı"])
        tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        tree.setColumnWidth(0, 50)
        tree.header().setSectionResizeMode(1, QHeaderView.Stretch) # Sınıflandırma Adı genişlesin
        tree_layout.addWidget(tree)

        # Treeview'i kaydet
        if tip == "GELİR":
            self.gelir_tree = tree
        else:
            self.gider_tree = tree
        
        # Sağ tık menüsünü treeview'e bağla
        tree.setContextMenuPolicy(Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(self._on_treeview_right_click)

        self._load_siniflandirmalar(tip)

    def _load_siniflandirmalar(self, tip):
        tree = self.gelir_tree if tip == "GELİR" else self.gider_tree
        
        tree.clear() # Mevcut öğeleri temizle
        
        siniflandirmalar = []
        try:
            if tip == "GELİR":
                response = requests.get(f"{API_BASE_URL}/nitelikler/gelir_siniflandirmalari")
            else:
                response = requests.get(f"{API_BASE_URL}/nitelikler/gider_siniflandirmalari")
            response.raise_for_status()
            siniflandirmalar = response.json()
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "API Hatası", f"{tip} sınıflandırmaları çekilirken hata: {e}")
            logging.error(f"{tip} sınıflandırma yükleme hatası: {e}", exc_info=True)
            return

        for s_item in siniflandirmalar:
            item_qt = QTreeWidgetItem(tree)
            item_qt.setText(0, str(s_item.get('id')))
            item_qt.setText(1, s_item.get('siniflandirma_adi'))
            item_qt.setData(0, Qt.UserRole, s_item.get('id')) # ID'yi UserRole olarak sakla

    def _siniflandirma_ekle(self, tip, siniflandirma_adi, entry_widget):
        if not siniflandirma_adi:
            QMessageBox.warning(self, "Uyarı", "Sınıflandırma adı boş olamaz.")
            return

        try:
            data = {"siniflandirma_adi": siniflandirma_adi}
            if tip == "GELİR":
                response = requests.post(f"{API_BASE_URL}/nitelikler/gelir_siniflandirmalari", json=data)
            else:
                response = requests.post(f"{API_BASE_URL}/nitelikler/gider_siniflandirmalari", json=data)
            response.raise_for_status()
            
            QMessageBox.information(self, "Başarılı", "Sınıflandırma başarıyla eklendi.")
            entry_widget.clear() # Giriş alanını temizle
            self._load_siniflandirmalar(tip) # Listeyi yenile
            if self.yenile_callback:
                self.yenile_callback() # Ana pencereyi yenile
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Sınıflandırma eklenirken hata: {error_detail}")
            logging.error(f"Sınıflandırma ekleme hatası: {error_detail}", exc_info=True)


    def _on_treeview_right_click(self, pos): # pos parametresi QWidget.customContextMenuRequested sinyalinden gelir
        current_tab_text = self.notebook.tabText(self.notebook.currentIndex()) # currentIndex() kullanılır
        
        tree = None
        if "Gelir Sınıflandırmaları" in current_tab_text:
            tree = self.gelir_tree
        else:
            tree = self.gider_tree

        item = tree.itemAt(pos) # Position'dan öğeyi al

        if item:
            tree.setCurrentItem(item) # Öğeyi seçili hale getir (sağ tıklama ile seçilmemiş olabilir)
            self.context_menu.exec(tree.mapToGlobal(pos)) # Global pozisyonda menüyü aç
        else:
            # Boş alana tıklandığında menüyü gizle/kapat (eğer açıksa)
            if hasattr(self, 'context_menu') and self.context_menu.isVisible():
                self.context_menu.hide()


    def _siniflandirma_guncelle(self):
        current_tab_text = self.notebook.tabText(self.notebook.currentIndex())
        
        tree = None
        tip = ""
        if "Gelir Sınıflandırmaları" in current_tab_text:
            tree = self.gelir_tree
            tip = "GELİR"
        else:
            tree = self.gider_tree
            tip = "GİDER"

        selected_items = tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen güncellemek istediğiniz sınıflandırmayı seçin.")
            return

        siniflandirma_id = selected_items[0].data(0, Qt.UserRole) # UserRole'dan ID'yi al
        siniflandirma_adi = selected_items[0].text(1) # Adı al

        siniflandirma_info = {'id': siniflandirma_id, 'siniflandirma_adi': siniflandirma_adi}
        
        from pencereler import SiniflandirmaDuzenlePenceresi # PySide6 dialog
        dialog = SiniflandirmaDuzenlePenceresi(self, self.db, tip, siniflandirma_info, 
                                      lambda: self._load_siniflandirmalar(tip)) # Yenile callback
        dialog.exec()

    def _siniflandirma_sil(self):
        current_tab_text = self.notebook.tabText(self.notebook.currentIndex())
        
        tree = None
        tip = ""
        if "Gelir Sınıflandırmaları" in current_tab_text:
            tree = self.gelir_tree
            tip = "GELİR"
        else:
            tree = self.gider_tree
            tip = "GİDER"

        selected_items = tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz sınıflandırmayı seçin.")
            return

        siniflandirma_id = selected_items[0].data(0, Qt.UserRole) # UserRole'dan ID'yi al
        siniflandirma_adi = selected_items[0].text(1) # Adı al

        reply = QMessageBox.question(self, "Onay", f"'{siniflandirma_adi}' sınıflandırmasını silmek istediğinizden emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                if tip == "GELİR":
                    response = requests.delete(f"{API_BASE_URL}/nitelikler/gelir_siniflandirmalari/{siniflandirma_id}")
                else: # GİDER
                    response = requests.delete(f"{API_BASE_URL}/nitelikler/gider_siniflandirmalari/{siniflandirma_id}")
                response.raise_for_status()

                QMessageBox.information(self, "Başarılı", "Sınıflandırma başarıyla silindi.")
                self._load_siniflandirmalar(tip) # Listeyi yenile
                if self.yenile_callback:
                    self.yenile_callback() # Ana pencereyi yenile
            except requests.exceptions.RequestException as e:
                error_detail = str(e)
                if e.response is not None:
                    try: error_detail = e.response.json().get('detail', str(e.response.content))
                    except ValueError: pass
                QMessageBox.critical(self, "API Hatası", f"Sınıflandırma silinirken hata: {error_detail}")
                logging.error(f"Sınıflandırma silme hatası: {error_detail}", exc_info=True)

class BirimDuzenlePenceresi(QDialog):
    def __init__(self, parent_window, db_manager, birim_info, yenile_callback):
        super().__init__(parent_window)
        self.db = db_manager
        self.parent_window = parent_window
        self.birim_id = birim_info['id']
        self.mevcut_birim_adi = birim_info['birim_adi']
        self.yenile_callback = yenile_callback

        self.setWindowTitle(f"Birim Düzenle: {self.mevcut_birim_adi}")
        self.setFixedSize(350, 200) # geometry yerine setFixedSize kullanıldı
        self.setModal(True) # Modalı olarak ayarla

        main_layout = QVBoxLayout(self)
        main_frame = QFrame(self)
        main_layout.addWidget(main_frame)
        main_frame_layout = QGridLayout(main_frame)

        main_frame_layout.addWidget(QLabel("Birim Adı:"), 0, 0, Qt.AlignLeft)
        self.birim_adi_entry = QLineEdit()
        self.birim_adi_entry.setText(self.mevcut_birim_adi)
        main_frame_layout.addWidget(self.birim_adi_entry, 0, 1)
        main_frame_layout.setColumnStretch(1, 1) # Genişlesin

        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame, alignment=Qt.AlignRight) # Butonları sağa yasla

        btn_kaydet = QPushButton("Kaydet")
        btn_kaydet.clicked.connect(self._kaydet)
        button_layout.addWidget(btn_kaydet)

        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self.close) # QDialog'u kapat
        button_layout.addWidget(btn_iptal)

    def _kaydet(self):
        yeni_birim_adi = self.birim_adi_entry.text().strip()
        if not yeni_birim_adi:
            QMessageBox.warning(self, "Uyarı", "Birim adı boş olamaz.")
            return

        try:
            response = requests.put(f"{API_BASE_URL}/nitelikler/urun_birimleri/{self.birim_id}", json={"birim_adi": yeni_birim_adi})
            response.raise_for_status()

            QMessageBox.information(self, "Başarılı", "Birim başarıyla güncellendi.")
            self.yenile_callback() # Ana listedeki birimleri yenile
            self.accept() # Pencereyi kapat
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Birim güncellenirken hata: {error_detail}")
            logging.error(f"Birim güncelleme hatası: {error_detail}", exc_info=True)

class GrupDuzenlePenceresi(QDialog):
    def __init__(self, parent_window, db_manager, grup_info, yenile_callback):
        super().__init__(parent_window)
        self.db = db_manager
        self.parent_window = parent_window
        self.grup_id = grup_info['id']
        self.mevcut_grup_adi = grup_info['grup_adi']
        self.yenile_callback = yenile_callback

        self.setWindowTitle(f"Grup Düzenle: {self.mevcut_grup_adi}")
        self.setFixedSize(350, 200) # geometry yerine setFixedSize kullanıldı
        self.setModal(True) # Modalı olarak ayarla

        main_layout = QVBoxLayout(self)
        main_frame = QFrame(self)
        main_layout.addWidget(main_frame)
        main_frame_layout = QGridLayout(main_frame)

        main_frame_layout.addWidget(QLabel("Grup Adı:"), 0, 0, Qt.AlignLeft)
        self.grup_adi_entry = QLineEdit()
        self.grup_adi_entry.setText(self.mevcut_grup_adi)
        main_frame_layout.addWidget(self.grup_adi_entry, 0, 1)
        main_frame_layout.setColumnStretch(1, 1) # Genişlesin

        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame, alignment=Qt.AlignRight) # Butonları sağa yasla

        btn_kaydet = QPushButton("Kaydet")
        btn_kaydet.clicked.connect(self._kaydet)
        button_layout.addWidget(btn_kaydet)

        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self.close) # QDialog'u kapat
        button_layout.addWidget(btn_iptal)

    def _kaydet(self):
        yeni_grup_adi = self.grup_adi_entry.text().strip()
        if not yeni_grup_adi:
            QMessageBox.warning(self, "Uyarı", "Grup adı boş olamaz.")
            return

        try:
            response = requests.put(f"{API_BASE_URL}/nitelikler/urun_gruplari/{self.grup_id}", json={"grup_adi": yeni_grup_adi})
            response.raise_for_status()

            QMessageBox.information(self, "Başarılı", "Grup başarıyla güncellendi.")
            self.yenile_callback()
            self.accept()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Grup güncellenirken hata: {error_detail}")
            logging.error(f"Grup güncelleme hatası: {error_detail}", exc_info=True)

# UlkeDuzenlePenceresi sınıfı
class UlkeDuzenlePenceresi(QDialog):
    def __init__(self, parent_window, db_manager, ulke_info, yenile_callback):
        super().__init__(parent_window)
        self.db = db_manager
        self.parent_window = parent_window
        self.ulke_id = ulke_info['id']
        self.mevcut_ulke_adi = ulke_info['ulke_adi']
        self.yenile_callback = yenile_callback

        self.setWindowTitle(f"Ülke Düzenle: {self.mevcut_ulke_adi}")
        self.setFixedSize(350, 200) # geometry yerine setFixedSize kullanıldı
        self.setModal(True) # Modalı olarak ayarla

        main_layout = QVBoxLayout(self)
        main_frame = QFrame(self)
        main_layout.addWidget(main_frame)
        main_frame_layout = QGridLayout(main_frame)

        main_frame_layout.addWidget(QLabel("Ülke Adı:"), 0, 0, Qt.AlignLeft)
        self.ulke_adi_entry = QLineEdit()
        self.ulke_adi_entry.setText(self.mevcut_ulke_adi)
        main_frame_layout.addWidget(self.ulke_adi_entry, 0, 1)
        main_frame_layout.setColumnStretch(1, 1) # Genişlesin

        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame, alignment=Qt.AlignRight) # Butonları sağa yasla

        btn_kaydet = QPushButton("Kaydet")
        btn_kaydet.clicked.connect(self._kaydet)
        button_layout.addWidget(btn_kaydet)

        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self.close) # QDialog'u kapat
        button_layout.addWidget(btn_iptal)

    def _kaydet(self):
        yeni_ulke_adi = self.ulke_adi_entry.text().strip()
        if not yeni_ulke_adi:
            QMessageBox.warning(self, "Uyarı", "Ülke adı boş olamaz.")
            return

        try:
            response = requests.put(f"{API_BASE_URL}/nitelikler/ulkeler/{self.ulke_id}", json={"ulke_adi": yeni_ulke_adi})
            response.raise_for_status()

            QMessageBox.information(self, "Başarılı", "Ülke başarıyla güncellendi.")
            self.yenile_callback()
            self.accept()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Ülke güncellenirken hata: {error_detail}")
            logging.error(f"Ülke güncelleme hatası: {error_detail}", exc_info=True)

class SiniflandirmaDuzenlePenceresi(QDialog):
    def __init__(self, parent_window, db_manager, tip, siniflandirma_info, yenile_callback):
        super().__init__(parent_window)
        self.db = db_manager
        self.parent_window = parent_window
        self.tip = tip # "GELİR" veya "GİDER"
        self.siniflandirma_id = siniflandirma_info['id']
        self.mevcut_siniflandirma_adi = siniflandirma_info['siniflandirma_adi']
        self.yenile_callback = yenile_callback

        self.setWindowTitle(f"{tip.capitalize()} Sınıflandırma Düzenle: {self.mevcut_siniflandirma_adi}")
        self.setFixedSize(400, 220) # Boyut ayarı
        self.setModal(True) # Modalı olarak ayarla

        main_layout = QVBoxLayout(self)
        main_frame = QFrame(self)
        main_layout.addWidget(main_frame)
        main_frame_layout = QGridLayout(main_frame)

        main_frame_layout.addWidget(QLabel("Sınıflandırma Adı:"), 0, 0, Qt.AlignLeft)
        self.siniflandirma_adi_entry = QLineEdit()
        self.siniflandirma_adi_entry.setText(self.mevcut_siniflandirma_adi)
        main_frame_layout.addWidget(self.siniflandirma_adi_entry, 0, 1)
        main_frame_layout.setColumnStretch(1, 1) # Genişlesin

        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame, alignment=Qt.AlignRight) # Butonları sağa yasla

        btn_kaydet = QPushButton("Kaydet")
        btn_kaydet.clicked.connect(self._kaydet)
        button_layout.addWidget(btn_kaydet)

        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self.close) # QDialog'u kapat
        button_layout.addWidget(btn_iptal)

    def _kaydet(self):
        yeni_siniflandirma_adi = self.siniflandirma_adi_entry.text().strip()
        if not yeni_siniflandirma_adi:
            QMessageBox.warning(self, "Uyarı", "Sınıflandırma adı boş olamaz.")
            return

        try:
            # API endpointleri kullanıldı
            if self.tip == "GELİR":
                response = requests.put(f"{API_BASE_URL}/nitelikler/gelir_siniflandirmalari/{self.siniflandirma_id}", json={"siniflandirma_adi": yeni_siniflandirma_adi})
            else: # GİDER
                response = requests.put(f"{API_BASE_URL}/nitelikler/gider_siniflandirmalari/{self.siniflandirma_id}", json={"siniflandirma_adi": yeni_siniflandirma_adi})
            response.raise_for_status()

            QMessageBox.information(self, "Başarılı", "Sınıflandırma başarıyla güncellendi.")
            self.yenile_callback() # Ana listedeki sınıflandırmaları yenile
            self.accept() # Pencereyi kapat
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try: error_detail = e.response.json().get('detail', str(e.response.content))
                except ValueError: pass
            QMessageBox.critical(self, "API Hatası", f"Sınıflandırma güncellenirken hata: {error_detail}")
            logging.error(f"Sınıflandırma güncelleme hatası: {error_detail}", exc_info=True)