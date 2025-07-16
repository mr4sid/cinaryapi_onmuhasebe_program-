#arayuz.py dosyası içeriği
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime, date, timedelta
import os
import shutil
import calendar
import logging
import traceback
import multiprocessing
import threading
# Üçüncü Parti Kütüphaneler
import openpyxl
from PIL import Image # Sadece Image kalmalı
# Matplotlib importları 
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import matplotlib.pyplot as plt

# Yerel Uygulama Modülleri
from raporlar import (CriticalStockWarningPenceresi, NotificationDetailsPenceresi,
                      NakitAkisRaporuPenceresi, KarZararRaporuPenceresi, CariYaslandirmaRaporuPenceresi)
from yardimcilar import (sort_treeview_column, setup_numeric_entry, setup_date_entry,
                         validate_numeric_input_generic, format_on_focus_out_numeric_generic,
                         DatePickerDialog)
from pencereler import BeklemePenceresi, CariHesapEkstresiPenceresi, FaturaDetayPenceresi, BirimDuzenlePenceresi, CariSecimPenceresi, TedarikciSecimDialog


class AnaSayfa(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        
        # AnaSayfa'nın kendi içinde grid layout kullanıyoruz.
        self.grid_rowconfigure(0, weight=0) # Header (Sabit yükseklik)
        self.grid_rowconfigure(1, weight=0) # Metrik Kartları (Sabit yükseklik)
        self.grid_rowconfigure(2, weight=1) # Ana Butonlar (Dikeyde genişlesin)
        self.grid_columnconfigure(0, weight=1) # Tek sütun, yatayda genişlemesi için
        
        # Ana frame'i parent'ına yerleştir (pack ile, AnaSayfa'nın kendisi bir sekme içeriği)
        self.pack(expand=True, fill=tk.BOTH, padx=20, pady=20) 

        # Header Frame (Şirket Adı)
        self.header_frame = ttk.Frame(self)
        self.header_frame.grid(row=0, column=0, pady=10, sticky=tk.W+tk.E) 

        self.sirket_adi_label = ttk.Label(self.header_frame, text="", font=("Segoe UI", 24, "bold"))
        self.sirket_adi_label.pack(side=tk.LEFT) # Bu label kendi frame'i içinde pack ile yerleşebilir

        self.guncelle_sirket_adi()

        # --- Metrik Kartlar Alanı ---
        self.metrics_container_frame = ttk.Frame(self, padding=(0,10))
        self.metrics_container_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        self.metrics_container_frame.columnconfigure((0,1,2,3,4,5), weight=1) # 6 metrik için eşit ağırlık

        # Metrik Kartları Oluşturma ve Grid ile yerleştirme
        self.card_satislar = self._create_metric_card(self.metrics_container_frame, "Bugünkü Satışlar", "0,00 TL", "sales")
        self.card_satislar.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.card_tahsilatlar = self._create_metric_card(self.metrics_container_frame, "Bugünkü Tahsilatlar", "0,00 TL", "collections")
        self.card_tahsilatlar.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        self.card_kritik_stok = self._create_metric_card(self.metrics_container_frame, "Kritik Stok Ürün", "0 adet", "critical_stock")
        self.card_kritik_stok.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        
        self.card_top_satan_urun = self._create_metric_card(self.metrics_container_frame, "Ayın En Çok Satan Ürünü", "---", "top_selling")
        self.card_top_satan_urun.grid(row=0, column=3, sticky="nsew", padx=5, pady=5)

        self.card_vadesi_gecmis_alacak = self._create_metric_card(self.metrics_container_frame, "Vadesi Geçmiş Alacak", "0,00 TL", "overdue_receivables")
        self.card_vadesi_gecmis_alacak.grid(row=0, column=4, sticky="nsew", padx=5, pady=5)

        self.card_vadesi_gecmis_borc = self._create_metric_card(self.metrics_container_frame, "Vadesi Geçmiş Borç", "0,00 TL", "overdue_payables")
        self.card_vadesi_gecmis_borc.grid(row=0, column=5, sticky="nsew", padx=5, pady=5)

        # --- Ana Butonlar Alanı ---
        self.buttons_container_frame = ttk.Frame(self, padding=10)
        self.buttons_container_frame.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
        self.buttons_container_frame.grid_columnconfigure((0,1,2), weight=1) # Butonları 3 sütuna yay

        buttons_info = [
            ("Yeni Satış Faturası", self.app.satis_faturasi_goster,"🛍️"),
            ("Yeni Alış Faturası", self.app.alis_faturasi_goster,"🛒"),
            ("Fatura Listesi", self.app.fatura_listesi_goster,"🧾"),
            ("Stok Yönetimi", self.app.stok_yonetimi_goster,"📦"),
            ("Müşteri Yönetimi", self.app.musteri_yonetimi_goster,"👥"),
            ("Gelir/Gider", self.app.gelir_gider_sayfasi_goster,"💸"),
            ("Ödeme/Tahsilat", lambda: self.app.notebook.select(self.app.finansal_islemler_sayfasi) and self.app.finansal_islemler_sayfasi.main_notebook.select(self.app.finansal_islemler_sayfasi.tahsilat_frame),"💰"),
            ("Sipariş Yönetimi", self.app.siparis_yonetimi_goster,"📋"),
            ("Kasa/Banka Yönetimi", self.app.kasa_banka_yonetimi_sayfasi_goster,"🏦")
        ]

        for i, (text, command, icon) in enumerate(buttons_info):
            row, col = divmod(i, 3) 
            button = ttk.Button(self.buttons_container_frame, text=f"{icon} {text}", command=command, style="Dashboard.TButton")
            button.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        # Alt Özet Bilgiler Çerçevesi (Artık tamamen kaldırıldı)
        # self.summary_frame_bottom = ttk.Frame(self) # Bu kısım kaldırıldı.
        # Bu etiketi ve altındaki pack/grid çağrılarını kaldırın
        # self.musteri_sayisi_label = ttk.Label(self.summary_frame_bottom, ...).pack(...)
        # vb. tüm alt özet etiketlerini kaldırın.

        self.guncelle_ozet_bilgiler() # Özet bilgileri güncelle

    def _create_metric_card(self, parent_frame, title, initial_value, card_type):
        card_frame = ttk.Frame(parent_frame, relief="solid", borderwidth=1, padding=10)
        card_frame.columnconfigure(0, weight=1) 

        ttk.Label(card_frame, text=title, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W+tk.E)
        value_label = ttk.Label(card_frame, text=initial_value, font=("Segoe UI", 20, "bold"), foreground="navy", anchor=tk.CENTER)
        value_label.grid(row=1, column=0, sticky="nsew", pady=(5,0)) 

        setattr(self, f"lbl_metric_{card_type}", value_label) 

        return card_frame

    def guncelle_sirket_adi(self):
        sirket_adi = self.db.sirket_bilgileri.get("sirket_adi", "ŞİRKET ADINIZ")
        self.sirket_adi_label.config(text=f"Hoş Geldiniz, {sirket_adi}")

    def guncelle_ozet_bilgiler(self):
        """Tüm özet bilgi kartlarını ve alt barı günceller."""
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        # 1. Metrik Kartları Güncelleme
        # Bugünkü Satışlar
        total_sales_today = self.db.get_total_sales(today_str, today_str)
        self.lbl_metric_sales.config(text=self.db._format_currency(total_sales_today))

        # Bugünkü Tahsilatlar (Toplam Tahsilat metodu gün içinde olanları verir)
        today_transactions_summary = self.db.get_today_transaction_summary()
        self.lbl_metric_collections.config(text=self.db._format_currency(today_transactions_summary['toplam_tahsilat_tutari']))

        # Kritik Stok Ürün Sayısı
        critical_items = self.db.get_critical_stock_items()
        self.lbl_metric_critical_stock.config(text=f"{len(critical_items)} adet",
                                             foreground="red" if len(critical_items) > 0 else "navy")
        
        # Ayın En Çok Satan Ürünü
        top_selling_product = self.db.get_top_selling_product_of_month()
        if top_selling_product:
            self.lbl_metric_top_selling.config(text=f"{top_selling_product[0]} ({top_selling_product[1]:.0f} adet)")
        else:
            self.lbl_metric_top_selling.config(text="Veri Yok")

        # Vadesi Geçmiş Alacak Toplamı
        overdue_receivables_data = self.db.get_overdue_receivables()
        total_overdue_receivables = sum(item[2] for item in overdue_receivables_data) # item[2] bakiyeyi temsil eder
        self.lbl_metric_overdue_receivables.config(text=self.db._format_currency(total_overdue_receivables),
                                                  foreground="red" if total_overdue_receivables > 0 else "navy")

        # Vadesi Geçmiş Borç Toplamı
        overdue_payables_data = self.db.get_overdue_payables()
        total_overdue_payables = sum(item[2] for item in overdue_payables_data) # item[2] bakiyeyi temsil eder
        self.lbl_metric_overdue_payables.config(text=self.db._format_currency(total_overdue_payables),
                                                foreground="red" if total_overdue_payables > 0 else "navy")

class FinansalIslemlerSayfasi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.pack(expand=True, fill=tk.BOTH)

        ttk.Label(self, text="Finansal İşlemler (Tahsilat / Ödeme)", font=("Segoe UI", 16, "bold")).pack(pady=(10,5), anchor=tk.W, padx=10)

        # Finansal işlemler için ana Notebook (Tahsilat ve Ödeme sekmeleri için)
        self.main_notebook = ttk.Notebook(self)
        self.main_notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        # Tahsilat Sekmesi
        self.tahsilat_frame = TahsilatSayfasi(self.main_notebook, self.db, self.app)
        self.main_notebook.add(self.tahsilat_frame, text="💰 Tahsilat Girişi")

        # Ödeme Sekmesi
        self.odeme_frame = OdemeSayfasi(self.main_notebook, self.db, self.app)
        self.main_notebook.add(self.odeme_frame, text="จ่าย Ödeme Girişi")
        
        # Sekme değiştiğinde ilgili formu yenilemek için bir olay bağlayabiliriz
        self.main_notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _on_tab_change(self, event):
        selected_tab = self.main_notebook.tab(self.main_notebook.select(), "text")
        if selected_tab == "💰 Tahsilat Girişi":
            if hasattr(self.tahsilat_frame, '_yukle_ve_cachele_carileri'): 
                self.tahsilat_frame._yukle_ve_cachele_carileri() 
            if hasattr(self.tahsilat_frame, '_yukle_kasa_banka_hesaplarini'):
                self.tahsilat_frame._yukle_kasa_banka_hesaplarini()
            self.tahsilat_frame.tarih_entry.delete(0, tk.END)
            self.tahsilat_frame.tarih_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
            self.tahsilat_frame.tutar_entry.delete(0, tk.END)
            self.tahsilat_frame.odeme_sekli_combo.set(self.db.ODEME_TURU_NAKIT)
            self.tahsilat_frame._odeme_sekli_degisince()

        elif selected_tab == "จ่าย Ödeme Girişi":
            if hasattr(self.odeme_frame, '_yukle_ve_cachele_carileri'):
                self.odeme_frame._yukle_ve_cachele_carileri() 
            if hasattr(self.odeme_frame, '_yukle_kasa_banka_hesaplarini'):
                self.odeme_frame._yukle_kasa_banka_hesaplarini()
            self.odeme_frame.tarih_entry.delete(0, tk.END)
            self.odeme_frame.tarih_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
            self.odeme_frame.tutar_entry.delete(0, tk.END)
            self.odeme_frame.odeme_sekli_combo.set(self.db.ODEME_TURU_NAKIT)
            self.odeme_frame._odeme_sekli_degisince()

class StokYonetimiSayfasi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        
        self.grid_rowconfigure(0, weight=0) 
        self.grid_rowconfigure(1, weight=0) 
        self.grid_rowconfigure(2, weight=0) 
        self.grid_rowconfigure(3, weight=0) 
        self.grid_rowconfigure(4, weight=1) 
        self.grid_rowconfigure(5, weight=0) 
        self.grid_columnconfigure(0, weight=1) 

        self.after_id = None
        
        self.kategoriler_map = {"TÜMÜ": None}
        self.markalar_map = {"TÜMÜ": None}
        self.urun_gruplari_map = {"TÜMÜ": None}
        self.urun_birimleri_map = {"TÜMÜ": None}
        self.ulkeler_map = {"TÜMÜ": None}

        ttk.Label(self, text="STOK YÖNETİM SİSTEMİ", font=("Segoe UI", 20, "bold")).grid(row=0, column=0, pady=(5, 5), sticky=tk.W, padx=15) 

        top_filter_and_action_frame = ttk.Frame(self, padding="10") 
        top_filter_and_action_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 5)) 
        top_filter_and_action_frame.columnconfigure(1, weight=1)

        row_idx = 0
        ttk.Label(top_filter_and_action_frame, text="Ürün Kodu/Adı:", font=("Segoe UI", 10, "bold")).grid(row=row_idx, column=0, padx=5, pady=2, sticky=tk.W)
        self.arama_entry = ttk.Entry(top_filter_and_action_frame, width=30)
        self.arama_entry.grid(row=row_idx, column=1, padx=5, pady=2, sticky=tk.EW)
        self.arama_entry.bind("<KeyRelease>", self._delayed_stok_yenile)

        ttk.Label(top_filter_and_action_frame, text="Kategori:", font=("Segoe UI", 10, "bold")).grid(row=row_idx, column=2, padx=(15, 5), pady=2, sticky=tk.W)
        self.kategori_filter_cb = ttk.Combobox(top_filter_and_action_frame, width=15, state="readonly")
        self.kategori_filter_cb.grid(row=row_idx, column=3, padx=5, pady=2, sticky=tk.EW)
        self.kategori_filter_cb.bind("<<ComboboxSelected>>", self.stok_listesini_yenile)

        ttk.Label(top_filter_and_action_frame, text="Marka:", font=("Segoe UI", 10, "bold")).grid(row=row_idx, column=4, padx=(15, 5), pady=2, sticky=tk.W)
        self.marka_filter_cb = ttk.Combobox(top_filter_and_action_frame, width=15, state="readonly")
        self.marka_filter_cb.grid(row=row_idx, column=5, padx=5, pady=2, sticky=tk.EW)
        self.marka_filter_cb.bind("<<ComboboxSelected>>", self.stok_listesini_yenile)

        ttk.Label(top_filter_and_action_frame, text="Ürün Grubu:", font=("Segoe UI", 10, "bold")).grid(row=row_idx, column=6, padx=(15, 5), pady=2, sticky=tk.W)
        self.urun_grubu_filter_cb = ttk.Combobox(top_filter_and_action_frame, width=15, state="readonly")
        self.urun_grubu_filter_cb.grid(row=row_idx, column=7, padx=5, pady=2, sticky=tk.EW)
        self.urun_grubu_filter_cb.bind("<<ComboboxSelected>>", self.stok_listesini_yenile)

        ttk.Button(top_filter_and_action_frame, text="Sorgula", command=self.stok_listesini_yenile, style="Accent.TButton", width=10).grid(row=row_idx, column=8, padx=(15, 5), pady=2, sticky=tk.E)
        ttk.Button(top_filter_and_action_frame, text="Temizle", command=self._filtreleri_temizle, width=10).grid(row=row_idx, column=9, padx=5, pady=2, sticky=tk.E)
        
        self._yukle_filtre_comboboxlari_stok_yonetimi()

        summary_info_frame = ttk.Frame(self, padding=(0, 0)) # padding tamamen kaldırıldı
        summary_info_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 0)) # pady sıfırlandı
        
        summary_info_frame.columnconfigure((0, 1, 2, 3), weight=1) 
        
        lbl_font = ("Segoe UI", 13, "bold")
        
        self.lbl_toplam_listelenen_urun = ttk.Label(summary_info_frame, text="Toplam Listelenen Ürün: 0 adet", font=lbl_font, anchor=tk.W)
        self.lbl_toplam_listelenen_urun.grid(row=0, column=0, sticky="ew", padx=5, pady=2) 

        self.lbl_stoktaki_toplam_urun = ttk.Label(summary_info_frame, text="Stoktaki Toplam Ürün Miktarı: 0.00", font=lbl_font, anchor=tk.W)
        self.lbl_stoktaki_toplam_urun.grid(row=0, column=1, sticky="ew", padx=5, pady=2) 

        self.lbl_toplam_maliyet = ttk.Label(summary_info_frame, text="Listelenen Ürünlerin Toplam Maliyeti: 0.00 TL", font=lbl_font, anchor=tk.W)
        self.lbl_toplam_maliyet.grid(row=0, column=2, sticky="ew", padx=5, pady=2) 

        self.lbl_toplam_satis_tutari = ttk.Label(summary_info_frame, text="Listelenen Ürünlerin Toplam Satış Tutarı: 0.00 TL", font=lbl_font, anchor=tk.W)
        self.lbl_toplam_satis_tutari.grid(row=0, column=3, sticky="ew", padx=5, pady=2) 

        button_frame = ttk.Frame(self, padding="10")
        button_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 5)) 

        ttk.Button(button_frame, text="Yeni Ürün Ekle", command=self.yeni_urun_ekle_penceresi, style="Accent.TButton", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Seçili Ürünü Düzenle", command=self.secili_urun_duzenle, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Seçili Ürünü Sil", command=self.secili_urun_sil, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Kritik Stok Uyarısı", command=self.app.kritik_stok_uyarisi_goster_app, width=18).pack(side=tk.RIGHT, padx=5)
        
        tree_frame = ttk.Frame(self, padding="0") 
        tree_frame.grid(row=4, column=0, sticky="nsew", padx=15, pady=(0, 0)) 
        tree_frame.grid_rowconfigure(0, weight=1) 
        tree_frame.grid_columnconfigure(0, weight=1)

        cols = ("Ürün Kodu", "Ürün Adı", "Miktar", "Alış Fyt (KDV Dahil)", "Satış Fyt (KDV Dahil)", "KDV %", "Min. Stok")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode="browse", height=40) 

        col_definitions = [
            ("Ürün Kodu", 115, tk.CENTER),
            ("Ürün Adı", 250, tk.CENTER), 
            ("Miktar", 80, tk.CENTER), 
            ("Alış Fyt (KDV Dahil)", 120, tk.CENTER), 
            ("Satış Fyt (KDV Dahil)", 120, tk.CENTER), 
            ("KDV %", 55, tk.CENTER),
            ("Min. Stok", 80, tk.CENTER) 
        ]

        for col_name, width, anchor in col_definitions:
            self.tree.heading(col_name, text=col_name, command=lambda _col=col_name: sort_treeview_column(self.tree, _col, False))
            self.tree.column(col_name, width=width, stretch=tk.YES if col_name == "Ürün Adı" else tk.NO, anchor=anchor)

        self.tree.tag_configure('critical_stock', background='#FFDDDD', foreground='red')   

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        
        self.tree.grid(row=0, column=0, sticky="nsew") 
        vsb.grid(row=0, column=1, sticky="ns") 
        hsb.grid(row=1, column=0, sticky="ew") 
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set) 

        # <<< KRİTİK DÜZELTME BAŞLANGICI: Çift tıklama olayını tekrar bağlıyoruz >>>
        self.tree.bind("<Double-1>", self.urun_duzenle_event)
        # <<< KRİTİK DÜZELTME BİTİŞİ >>>

        # <<< YENİ DÜZELTME BAŞLANGICI: Treeview metin fontunu artırdık >>>
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 12)) # Yazı boyutunu 10'a çıkardık
        # <<< YENİ DÜZELTME BİTİŞİ >>>

        self.kayit_sayisi_per_sayfa = 25
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0

        pagination_frame = ttk.Frame(self, padding="10")
        pagination_frame.grid(row=5, column=0, sticky="ew", padx=15, pady=(5, 5)) 

        ttk.Button(pagination_frame, text="Önceki Sayfa", command=self.onceki_sayfa).pack(side=tk.LEFT, padx=5)
        self.sayfa_bilgisi_label = ttk.Label(pagination_frame, text="Sayfa 1 / 1", font=("Segoe UI", 10, "bold"))
        self.sayfa_bilgisi_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(pagination_frame, text="Sonraki Sayfa", command=self.sonraki_sayfa).pack(side=tk.LEFT, padx=5)

        self.stok_listesini_yenile()
    def _yukle_filtre_comboboxlari_stok_yonetimi(self):
        # Kategoriler
        kategoriler_map = self.db.get_kategoriler_for_combobox()
        self.kategoriler_map = {"TÜMÜ": None, **kategoriler_map}
        self.kategori_filter_cb['values'] = ["TÜMÜ"] + sorted(kategoriler_map.keys())
        self.kategori_filter_cb.set("TÜMÜ")

        # Markalar
        markalar_map = self.db.get_markalar_for_combobox()
        self.markalar_map = {"TÜMÜ": None, **markalar_map}
        self.marka_filter_cb['values'] = ["TÜMÜ"] + sorted(markalar_map.keys())
        self.marka_filter_cb.set("TÜMÜ")

        # Ürün Grupları Eklendi
        # Ürün Grupları
        urun_gruplari_map = self.db.get_urun_gruplari_for_combobox()
        self.urun_gruplari_map = {"TÜMÜ": None, **urun_gruplari_map}
        self.urun_grubu_filter_cb['values'] = ["TÜMÜ"] + sorted(urun_gruplari_map.keys())
        self.urun_grubu_filter_cb.set("TÜMÜ")


    def _filtreleri_temizle(self):
        """Tüm filtreleme alanlarını temizler ve listeyi yeniler."""
        self.arama_entry.delete(0, tk.END)
        self.kategori_filter_cb.set("TÜMÜ")
        self.marka_filter_cb.set("TÜMÜ")
        self.urun_grubu_filter_cb.set("TÜMÜ")
        # Eğer varsa diğer filtreleri de temizle
        # self.urun_birimi_filter_cb.set("TÜMÜ")
        # self.ulke_filter_cb.set("TÜMÜ")
        self.stok_listesini_yenile()        
        
    def _delayed_stok_yenile(self, event):
        if self.after_id:
            self.after_cancel(self.after_id)
        self.after_id = self.after(300, self.stok_listesini_yenile) # 300 ms (0.3 saniye) gecikme


    def stok_listesini_yenile(self, event=None):
        for i in self.tree.get_children(): self.tree.delete(i) # Treeview'ı temizle
        arama_terimi = self.arama_entry.get()

        # Filtre değerlerini al ve ID'ye dönüştür
        kategori_id_filter = self.kategoriler_map.get(self.kategori_filter_cb.get(), None)
        marka_id_filter = self.markalar_map.get(self.marka_filter_cb.get(), None)
        urun_grubu_id_filter = self.urun_gruplari_map.get(self.urun_grubu_filter_cb.get(), None)
        # urun_birimi_id_filter = self.urun_birimleri_map.get(self.urun_birimi_filter_cb.get(), None) # Eğer eklenecekse
        # ulke_id_filter = self.ulkeler_map.get(self.ulke_filter_cb.get(), None) # Eğer eklenecekse

        # ### ÖZET BİLGİLERİ İÇİN TÜM FİLTRELENMİŞ VERİLERİ ÇEK ###
        # Sayfalama yapmadan, filtrelenmiş tüm ürünleri çekeriz.
        all_filtered_stock_items = self.db.stok_listele(
            arama_terimi,
            limit=None,
            offset=None,
            kategori_id_filter=kategori_id_filter,
            marka_id_filter=marka_id_filter,
            urun_grubu_id_filter=urun_grubu_id_filter,
        )

        # Özet bilgiler için değişkenleri sıfırla
        toplam_stok_miktari_tum_filtre = 0.0
        toplam_maliyet_tum_filtre = 0.0
        toplam_satis_tutari_tum_filtre = 0.0

        for urun in all_filtered_stock_items:
            # Her bir filtrelenmiş ürün için özet bilgileri hesapla
            if urun[3] is not None: # stok_miktari
                toplam_stok_miktari_tum_filtre += urun[3]
            if urun[3] is not None and urun[8] is not None: # stok_miktari * alis_fiyati_kdv_dahil
                toplam_maliyet_tum_filtre += urun[3] * urun[8]
            if urun[3] is not None and urun[9] is not None: # stok_miktari * satis_fiyati_kdv_dahil
                toplam_satis_tutari_tum_filtre += urun[3] * urun[9]
        
        # Özet bilgiler etiketlerini güncelle
        self.lbl_toplam_listelenen_urun.config(text=f"Listelenen Ürün Sayısı: {len(all_filtered_stock_items)} adet")
        self.lbl_stoktaki_toplam_urun.config(text=f"Stoktaki T.Ürün Miktarı: {toplam_stok_miktari_tum_filtre:.2f}")
        self.lbl_toplam_maliyet.config(text=f"Listelenen Ürünlerin T.Maliyeti: {self.db._format_currency(toplam_maliyet_tum_filtre)}")
        self.lbl_toplam_satis_tutari.config(text=f"Listelenen Ürünlerin T.Satış Tutarı: {self.db._format_currency(toplam_satis_tutari_tum_filtre)}")

        # ### TREEVIEW İÇİN SADECE MEVCUT SAYFA VERİLERİNİ ÇEK ###
        self.toplam_kayit_sayisi = len(all_filtered_stock_items) # Toplam filtrelenmiş kayıt sayısı

        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0:
            toplam_sayfa = 1
        
        if self.mevcut_sayfa > toplam_sayfa:
            self.mevcut_sayfa = toplam_sayfa
        
        offset = (self.mevcut_sayfa - 1) * self.kayit_sayisi_per_sayfa
        limit = self.kayit_sayisi_per_sayfa

        # Sadece mevcut sayfadaki öğeleri almak için `all_filtered_stock_items` listesini kullan
        paginated_stock_items = all_filtered_stock_items[offset : offset + limit]


        for urun_idx, urun in enumerate(paginated_stock_items): # Sayfalanmış liste üzerinde döngü            
            # Formate edilmiş değerler
            miktar_gosterim = f"{urun[3]:.2f}".rstrip('0').rstrip('.') if urun[3] is not None else "0"
            min_stok_gosterim = f"{urun[7]:.2f}".rstrip('0').rstrip('.') if urun[7] is not None else "0"

            tags = ()
            if urun[3] is not None and urun[7] is not None and urun[3] < urun[7]: # Eğer mevcut stok minimum stoktan azsa
                tags = ('critical_stock',) # Kritik stok tag'ini ata


            self.tree.insert("", "end", iid=urun[0], values=(
                urun[1], # Ürün Kodu
                urun[2], # Ürün Adı
                miktar_gosterim, 
                self.db._format_currency(urun[8]), # KDV Dahil Alış Fiyatı (8. index)
                self.db._format_currency(urun[9]), # KDV Dahil Satış Fiyatı (9. index)
                f"%{urun[6]:.0f}", # KDV Oranı (6. index)
                min_stok_gosterim # Min. Stok (7. index)
            ), tags=tags)


        self.app.set_status(f"{len(paginated_stock_items)} ürün listelendi. Toplam {self.toplam_kayit_sayisi} kayıt.")
        self.sayfa_bilgisi_label.config(text=f"Sayfa {self.mevcut_sayfa} / {toplam_sayfa}")

        
    def yeni_urun_ekle_penceresi(self):
        from pencereler import UrunKartiPenceresi
        UrunKartiPenceresi(self, self.db, self.stok_listesini_yenile, urun_duzenle=None, app_ref=self.app)

    def urun_detay_goster_event(self, event):
        self.secili_urun_detay_goster()

    def secili_urun_detay_goster(self):
        selected_item_iid = self.tree.focus() # Burası Treeview'de seçili öğenin iid'sini döner
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen işlem yapmak için bir ürün seçin.", parent=self)
            return
        
        # selected_item_iid zaten ürün ID'si (çünkü stok_listesini_yenile metodunda iid=urun[0] olarak ayarlandı)
        urun_id = selected_item_iid 
        urun_db = self.db.stok_getir_by_id(urun_id)

        if urun_db:
            from pencereler import UrunKartiPenceresi
            UrunKartiPenceresi(self, self.db, 
                               self.stok_listesini_yenile, # Ana stok listesi yenileme callback'i
                               urun_duzenle=urun_db, 
                               app_ref=self.app)
        else:
            # Bu hata, veritabanından ürünün bulunamaması durumunda oluşur.
            # Normalde Treeview'deki bir öğe varsa, veritabanında da olmalıdır.
            # Bu durumun sebebi veri tutarsızlığı veya yanlış ID kullanımı olabilir.
            messagebox.showerror("Hata", "Seçili ürün veritabanında bulunamadı. Liste yenilenecek ve sorun devam ederse yöneticinize başvurun.", parent=self)
            self.stok_listesini_yenile()

    def secili_urun_detay_goster_force_refresh(self, urun_id_to_refresh):
        """
        Belirli bir ürünün detay penceresini (ürün kartını) zorla yeniden açar.
        Bu, anlık güncelleme sorunları için bir çözümdür.
        """
        urun_db_guncel = self.db.stok_getir_by_id(urun_id_to_refresh)
        if urun_db_guncel:
            from pencereler import UrunKartiPenceresi
            # Yeni Ürün Kartı penceresini aç
            UrunKartiPenceresi(self, self.db, 
                               self.stok_listesini_yenile, 
                               urun_duzenle=urun_db_guncel, 
                               app_ref=self.app,
                               on_update_reopen_callback=lambda: self.secili_urun_detay_goster_force_refresh(urun_id_to_refresh))
        else:
            messagebox.showerror("Hata", "Ürün bilgileri güncellenirken yeniden yüklenemedi.", parent=self)
            self.stok_listesini_yenile() # Ana listeyi yenile

    def urun_duzenle_event(self, event): 
        # Çift tıklanan öğenin iid'sini doğrudan olaydan al.
        selected_item_iid = self.tree.identify_row(event.y)
        
        # DEBUG: identify_row ne döndürüyor?
        print(f"DEBUG: urun_duzenle_event - identify_row({event.y}) döndürdü: '{selected_item_iid}'")

        if not selected_item_iid:
            print("DEBUG: urun_duzenle_event - selected_item_iid boş.")
            messagebox.showwarning("Uyarı", "Lütfen düzenlemek için bir ürün seçin.", parent=self)
            return

        # Ürünün ID'si selected_item_iid'de zaten var (çünkü Treeview'e iid=urun[0] ile ekleniyor).
        urun_id = selected_item_iid

        # Seçimi ve odağı programatik olarak ayarla (güvenlik için)
        self.tree.selection_set(selected_item_iid)
        self.tree.focus(selected_item_iid)

        # secili_urun_duzenle metodunu çağır ve ürün ID'sini gönder.
        print(f"DEBUG: urun_duzenle_event - secili_urun_duzenle çağrılıyor, urun_id: '{urun_id}'")
        self.secili_urun_duzenle(urun_id=urun_id)

    def secili_urun_duzenle(self, urun_id=None): 
        # Eğer metod doğrudan bir butondan çağrılıyorsa (parametre olmadan),
        # seçili ürünü Treeview'den al. Eğer parametre olarak geldiyse onu kullan.
        print(f"DEBUG: secili_urun_duzenle çağrıldı. Başlangıç urun_id: '{urun_id}'")

        if urun_id is None:
            selected_item_iid = self.tree.focus() 
            print(f"DEBUG: secili_urun_duzenle - urun_id None, focus() döndürdü: '{selected_item_iid}'")
            if not selected_item_iid:
                print("DEBUG: secili_urun_duzenle - selected_item_iid boş.")
                messagebox.showwarning("Uyarı", "Lütfen düzenlemek için bir ürün seçin.", parent=self)
                return
            urun_id = selected_item_iid 

        # urun_id'nin geçerli bir sayısal ID olduğundan emin olalım (Devir satırı vb. için)
        try:
            urun_id_int = int(urun_id)
            print(f"DEBUG: secili_urun_duzenle - int(urun_id) başarılı: {urun_id_int}")
        except ValueError:
            print(f"DEBUG: secili_urun_duzenle - ValueError: urun_id '{urun_id}' int'e dönüştürülemedi.")
            messagebox.showwarning("Uyarı", "Geçersiz ürün seçimi (ID formatı hatalı).", parent=self)
            return

        urun_db = self.db.stok_getir_by_id(urun_id_int) # Integer ID ile sorgulama
        print(f"DEBUG: secili_urun_duzenle - db.stok_getir_by_id({urun_id_int}) döndürdü: {urun_db}")

        if urun_db:
            print(f"DEBUG: secili_urun_duzenle - UrunKartiPenceresi açılıyor: {urun_db['urun_adi']}")
            from pencereler import UrunKartiPenceresi
            UrunKartiPenceresi(self.app, self.db, # parent ve app_ref olarak self.app'i kullanıyoruz.
                               self.stok_listesini_yenile, 
                               urun_duzenle=urun_db, 
                               app_ref=self.app)
        else:
            print(f"DEBUG: secili_urun_duzenle - Ürün veritabanında bulunamadı: ID {urun_id_int}")
            messagebox.showerror("Hata", "Seçili ürün veritabanında bulunamadı. Liste yenilenecek ve sorun devam ederse yöneticinize başvurun.", parent=self)
            self.stok_listesini_yenile()

    def secili_urun_sil(self):
        selected_item_iid = self.tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir ürün seçin.", parent=self)
            return

        urun_id = selected_item_iid # iid doğrudan ürün ID'si
        urun_adi = self.tree.item(selected_item_iid)['values'][1] # Ürün Adı, Treeview'in 2. sütunu (index 1)

        if messagebox.askyesno("Onay", f"'{urun_adi}' adlı ürünü silmek istediğinizden emin misiniz?\nBu işlem geri alınamaz.", parent=self):
            success, message = self.db.stok_sil(urun_id)
            if success:
                messagebox.showinfo("Başarılı", message, parent=self)
                self.stok_listesini_yenile()
                self.app.set_status(f"'{urun_adi}' silindi.")
            else:
                messagebox.showerror("Hata", message, parent=self)

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.stok_listesini_yenile()

    def sonraki_sayfa(self):
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0:
            toplam_sayfa = 1 # Eğer hiç kayıt yoksa, toplam sayfa 1 olarak kabul et.
        
        if self.mevcut_sayfa < toplam_sayfa:
            self.mevcut_sayfa += 1
            self.stok_listesini_yenile()

class KasaBankaYonetimiSayfasi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.pack(expand=True, fill=tk.BOTH)
        self.after_id = None
        ttk.Label(self, text="Kasa ve Banka Hesap Yönetimi", font=("Segoe UI", 16, "bold")).pack(pady=10, anchor=tk.W, padx=10)

        arama_frame = ttk.Frame(self, padding="5")
        arama_frame.pack(fill=tk.X, padx=10)
        ttk.Label(arama_frame, text="Hesap Ara (Ad/No/Banka):").pack(side=tk.LEFT, padx=(0,5))
        self.arama_entry_kb = ttk.Entry(arama_frame, width=30)
        self.arama_entry_kb.pack(side=tk.LEFT, padx=(0,10))
        self.arama_entry_kb.bind("<KeyRelease>", self._delayed_hesap_yenile)

        ttk.Label(arama_frame, text="Tip:").pack(side=tk.LEFT, padx=(5,2))
        self.tip_filtre_kb = ttk.Combobox(arama_frame, width=10, values=["TÜMÜ", "KASA", "BANKA"], state="readonly")
        self.tip_filtre_kb.pack(side=tk.LEFT, padx=(0,10))
        self.tip_filtre_kb.current(0)
        self.tip_filtre_kb.bind("<<ComboboxSelected>>", self.hesap_listesini_yenile)

        ttk.Button(arama_frame, text="Yenile", command=self.hesap_listesini_yenile).pack(side=tk.LEFT)

        tree_frame_kb = ttk.Frame(self, padding="10")
        tree_frame_kb.pack(expand=True, fill=tk.BOTH)

        cols_kb = ("#", "Hesap Adı", "Tip", "Banka Adı", "Hesap No", "Bakiye", "Para Birimi")
        self.tree_kb = ttk.Treeview(tree_frame_kb, columns=cols_kb, show='headings', selectmode="browse")

        col_defs_kb = [
            ("#", 40, tk.E, tk.NO),
            ("Hesap Adı", 200, tk.W, tk.YES),
            ("Tip", 80, tk.W, tk.NO),
            ("Banka Adı", 150, tk.W, tk.YES),
            ("Hesap No", 150, tk.W, tk.YES),
            ("Bakiye", 120, tk.E, tk.NO),
            ("Para Birimi", 80, tk.CENTER, tk.NO)
        ]
        for cn,w,a,so in col_defs_kb:
            self.tree_kb.column(cn, width=w, anchor=a, stretch=so)
            self.tree_kb.heading(cn, text=cn, command=lambda _c=cn: sort_treeview_column(self.tree_kb, _c, False))

        vsb_kb = ttk.Scrollbar(tree_frame_kb, orient="vertical", command=self.tree_kb.yview)
        vsb_kb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_kb.configure(yscrollcommand=vsb_kb.set)
        self.tree_kb.pack(expand=True, fill=tk.BOTH)
        self.tree_kb.bind("<Double-1>", self.hesap_duzenle_event)

        button_frame_kb = ttk.Frame(self, padding="10")
        button_frame_kb.pack(fill=tk.X)
        ttk.Button(button_frame_kb, text="Yeni Hesap Ekle", command=self.yeni_hesap_ekle_penceresi, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame_kb, text="Seçili Hesabı Düzenle", command=self.secili_hesap_duzenle).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame_kb, text="Seçili Hesabı Sil", command=self.secili_hesap_sil).pack(side=tk.LEFT, padx=5)
        
    def hesap_listesini_yenile(self, event=None):
        for i in self.tree_kb.get_children(): self.tree_kb.delete(i)
        arama_terimi = self.arama_entry_kb.get()
        tip_filtre = self.tip_filtre_kb.get()
        hesap_listesi = self.db.kasa_banka_listesi_al(tip_filtre=tip_filtre, arama_terimi=arama_terimi)
        
        for h in hesap_listesi:
            self.tree_kb.insert("","end",iid=h['id'],values=(
                h['id'],                         # ID
                h['hesap_adi'],                  # Hesap Adı
                h['tip'],                        # Tip
                h['banka_adi'] or "-",           # Banka Adı (None ise "-")
                h['hesap_no'] or "-",            # Hesap No (None ise "-")
                self.db._format_currency(h['bakiye']), # Bakiye
                h['para_birimi']                 # Para Birimi
            ))
        self.app.set_status(f"{len(hesap_listesi)} kasa/banka hesabı listelendi.")

    def _delayed_hesap_yenile(self, event):
        if self.after_id:
            self.after_cancel(self.after_id)
        self.after_id = self.after(300, self.hesap_listesini_yenile)

    def yeni_hesap_ekle_penceresi(self):
        from pencereler import YeniKasaBankaEklePenceresi
        YeniKasaBankaEklePenceresi(self, self.db, self.hesap_listesini_yenile, app_ref=self.app)
        self.app.set_status("Yeni kasa/banka ekleme penceresi açıldı.")

    def hesap_duzenle_event(self, event): self.secili_hesap_duzenle()
    def secili_hesap_duzenle(self):
        selected_item = self.tree_kb.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen düzenlemek için bir hesap seçin.", parent=self)
            return
        hesap_db = self.db.kasa_banka_getir_by_id(selected_item) # ID'yi direkt kullan
        if hesap_db:
            from pencereler import YeniKasaBankaEklePenceresi
            # YeniKasaBankaEklePenceresi'ne hesap_db parametres
            YeniKasaBankaEklePenceresi(self, self.db, self.hesap_listesini_yenile, hesap_duzenle=hesap_db, app_ref=self.app)
        else:
            messagebox.showerror("Hata", "Seçili hesap veritabanında bulunamadı.", parent=self)
            self.hesap_listesini_yenile()

    def secili_hesap_sil(self):
        selected_item = self.tree_kb.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir hesap seçin.", parent=self)
            return

        hesap_adi = self.tree_kb.item(selected_item)['values'][1]

        if messagebox.askyesno("Onay", f"'{hesap_adi}' adlı hesabı silmek istediğinizden emin misiniz?", parent=self):
            success, message = self.db.kasa_banka_sil(selected_item)
            if success:
                messagebox.showinfo("Başarılı", message, parent=self)
                self.hesap_listesini_yenile()
                self.app.set_status(f"'{hesap_adi}' hesabı silindi.")
            else:
                messagebox.showerror("Hata", message, parent=self)


class MusteriYonetimiSayfasi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.pack(expand=True, fill=tk.BOTH)
        self.after_id = None
        ttk.Label(self, text="Müşteri Yönetimi", font=("Segoe UI", 16, "bold")).pack(pady=10, anchor=tk.W, padx=10)

        # <<< YENİ EKLENEN TOPLAM ÖZET BİLGİLERİ KISMI BAŞLANGICI >>>
        summary_frame = ttk.Frame(self, padding="5")
        summary_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        summary_frame.columnconfigure(0, weight=1)
        summary_frame.columnconfigure(1, weight=1)

        self.lbl_toplam_alacak_musteri = ttk.Label(summary_frame, text="Toplam Alacak (Müşteri): Yükleniyor...", font=("Segoe UI", 10, "bold"), foreground="red")
        self.lbl_toplam_alacak_musteri.grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        
        # Sola Yaslı, Daha Büyük Yazı Tipi
        self.lbl_toplam_borc_musteri = ttk.Label(summary_frame, text="Toplam Borç (Müşteri): Yükleniyor...", font=("Segoe UI", 10, "bold"), foreground="green")
        self.lbl_toplam_borc_musteri.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        # <<< YENİ EKLENEN TOPLAM ÖZET BİLGİLERİ KISMI BİTİŞİ >>>

        arama_frame = ttk.Frame(self, padding="5")
        arama_frame.pack(fill=tk.X, padx=10)
        ttk.Label(arama_frame, text="Müşteri Ara (Ad/Kod/Tel/Adres):").pack(side=tk.LEFT, padx=(0,5))
        self.arama_entry = ttk.Entry(arama_frame, width=35)
        self.arama_entry.pack(side=tk.LEFT, padx=(0,10))
        self.arama_entry.bind("<KeyRelease>", self._delayed_musteri_yenile)
        self.arama_entry.bind("<Return>", self._on_arama_entry_return)
        ttk.Button(arama_frame, text="Ara/Yenile", command=self.musteri_listesini_yenile).pack(side=tk.LEFT)

        tree_frame = ttk.Frame(self, padding="10")
        tree_frame.pack(expand=True, fill=tk.BOTH)
        
        # <<< YENİ SÜTUN TANIMLARI VE SIRALAMASI BAŞLANGICI >>>
        # Müşteri Yönetimi Sayfası İçin Sütunlar: Satır, Müşteri Adı, Fatura Sayısı, AÇIK HESAP, TAHSİLAT, KALAN BORÇ, Vadesi Geçmiş Borç, Son Tahsilat Tarihi
        cols = ("#", "Müşteri Adı", "Fatura Sayısı", "AÇIK HESAP", "TAHSİLAT", "KALAN BORÇ", "Vadesi Geçmiş Borç", "Son Tahsilat Tarihi")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode="browse")
        
        # Sütun Genişlikleri ve Hizalamalar (Tümü Ortada)
        col_definitions = [
            ("#", 50, tk.CENTER, tk.NO),
            ("Müşteri Adı", 200, tk.CENTER, tk.YES), # Genişlemesini isteyelim
            ("Fatura Sayısı", 100, tk.CENTER, tk.NO),
            ("AÇIK HESAP", 120, tk.CENTER, tk.NO),
            ("TAHSİLAT", 120, tk.CENTER, tk.NO),
            ("KALAN BORÇ", 120, tk.CENTER, tk.NO),
            ("Vadesi Geçmiş Borç", 120, tk.CENTER, tk.NO),
            ("Son Tahsilat Tarihi", 120, tk.CENTER, tk.NO)
        ]
        
        for col_name, width, anchor, stretch_val in col_definitions:
            self.tree.heading(col_name, text=col_name, command=lambda _col=col_name: sort_treeview_column(self.tree, _col, False))
            self.tree.column(col_name, width=width, stretch=stretch_val, anchor=anchor)
        # <<< YENİ SÜTUN TANIMLARI VE SIRALAMASI BİTİŞİ >>>

        # Kritik stoktaki ürünler için özel bir tag stili tanımla (Eğer kullanılıyorsa)
        # Treeview genel stil ayarları (önceki konuşmalardan)
        style = ttk.Style()
        style.configure("Treeview", 
                        fieldbackground="white", # Varsayılan arka plan beyaz
                        background="white",      
                        foreground="black", 
                        rowheight=25) 
        style.configure("Treeview.Heading", font=('Segoe UI', 9, 'bold'))
        style.map('Treeview',
                  fieldbackground=[('selected', '#32679F')], 
                  foreground=[('selected', 'white')], 
                  background=[('selected', '#32679F')]) 
        
        # Müşteri ve borç durumuna göre renk tag'leri
        self.tree.tag_configure('borclu_musteri', background='#FFDDDD', foreground='red')     # Kalan borç > 0 ise
        self.tree.tag_configure('alacakli_musteri', background='#D5F5E3', foreground='green') # Kalan borç < 0 ise
        self.tree.tag_configure('vadesi_gecmis', background='#F8D7DA', foreground='darkred', font=('Segoe UI', 9, 'bold')) # Vadesi geçmiş borç varsa

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(expand=True, fill=tk.BOTH)
        self.tree.bind("<Double-1>", self.secili_musteri_ekstresi_goster)
        self.tree.bind("<<TreeviewSelect>>", self.secili_musteri_ekstre_buton_guncelle)


        button_frame = ttk.Frame(self, padding="10")
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Yeni Müşteri Ekle", command=self.yeni_musteri_ekle_penceresi, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Seçili Müşteriyi Düzenle", command=self.secili_musteri_duzenle).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Seçili Müşteriyi Sil", command=self.secili_musteri_sil).pack(side=tk.LEFT, padx=5)
        self.ekstre_button = ttk.Button(button_frame, text="Seçili Müşteri Ekstresi", command=self.secili_musteri_ekstresi_goster, state=tk.DISABLED)
        self.ekstre_button.pack(side=tk.LEFT, padx=5)

        self.kayit_sayisi_per_sayfa = 25
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0

        pagination_frame = ttk.Frame(self, padding="10")
        pagination_frame.pack(fill=tk.X, padx=10, pady=5, side=tk.BOTTOM)

        ttk.Button(pagination_frame, text="Önceki Sayfa", command=self.onceki_sayfa).pack(side=tk.LEFT, padx=5)
        self.sayfa_bilgisi_label = ttk.Label(pagination_frame, text="Sayfa 1 / 1")
        self.sayfa_bilgisi_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(pagination_frame, text="Sonraki Sayfa", command=self.sonraki_sayfa).pack(side=tk.LEFT, padx=5)
        
        # Sayfa yüklendiğinde özet bilgileri güncelleyelim.
        self.guncelle_toplam_ozet_bilgiler()
        self.arama_entry.focus_set()
    def secili_musteri_ekstre_buton_guncelle(self, event=None):
        selected_item = self.tree.focus()
        if selected_item:
            item_values = self.tree.item(selected_item, "values")
            if item_values and str(item_values[0]) == str(self.db.perakende_musteri_id): # ID ilk sütunda
                self.ekstre_button.config(state=tk.DISABLED)
            else:
                self.ekstre_button.config(state=tk.NORMAL)
        else:
            self.ekstre_button.config(state=tk.DISABLED)


    def musteri_listesini_yenile(self, event=None):
        for i in self.tree.get_children():
            self.tree.delete(i)
        arama_terimi = self.arama_entry.get()

        # <<< VERİTABANI ÇAĞRISINI get_cari_list_summary_data ile değiştiriyoruz >>>
        # Toplam kayıt sayısını alalım (sayfalama için)
        self.toplam_kayit_sayisi = self.db.get_cari_count(cari_tip=self.db.CARI_TIP_MUSTERI, arama_terimi=arama_terimi, perakende_haric=True)
        
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0:
            toplam_sayfa = 1

        if self.mevcut_sayfa > toplam_sayfa:
            self.mevcut_sayfa = toplam_sayfa
        if self.mevcut_sayfa < 1:
            self.mevcut_sayfa = 1
            
        offset = (self.mevcut_sayfa - 1) * self.kayit_sayisi_per_sayfa
        limit = self.kayit_sayisi_per_sayfa

        # Yeni özet verilerini çekelim
        musteri_listesi_ozet = self.db.get_cari_list_summary_data(
            cari_tip=self.db.CARI_TIP_MUSTERI,
            arama_terimi=arama_terimi,
            limit=limit,
            offset=offset,
            perakende_haric=True # Müşteri listesi için perakende müşteriyi hariç tut
        )
        
        # >>> BURADAKİ DÖNGÜYÜ YENİ VERİ YAPISINA GÖRE DÜZENLİYORUZ <<<
        sira_no = offset + 1
        for musteri_data in musteri_listesi_ozet:
            # Renk taglerini belirleyelim
            tags = []
            if musteri_data['kalan_borc'] > 0:
                tags.append('borclu_musteri') # Kalan borç pozitifse (müşteri bize borçlu)
            elif musteri_data['kalan_borc'] < 0:
                tags.append('alacakli_musteri') # Kalan borç negatifse (müşteri bizden alacaklı)
            
            if musteri_data['vadesi_gecmis_borc'] > 0:
                tags.append('vadesi_gecmis') # Vadesi geçmiş borç varsa

            self.tree.insert("", "end", iid=musteri_data['id'], values=(
                sira_no, # Satır Numarası
                musteri_data['cari_adi'], # Müşteri Adı
                musteri_data['fatura_sayisi'], # Fatura Sayısı
                self.db._format_currency(musteri_data['acik_hesap_toplam']), # AÇIK HESAP
                self.db._format_currency(musteri_data['odeme_tahsilat_toplam']), # TAHSİLAT
                self.db._format_currency(musteri_data['kalan_borc']), # KALAN BORÇ
                self.db._format_currency(musteri_data['vadesi_gecmis_borc']), # Vadesi Geçmiş Borç
                musteri_data['son_odeme_tarihi'] # Son Tahsilat Tarihi
            ), tags=tuple(tags))
            sira_no += 1
            
        self.app.set_status(f"{len(musteri_listesi_ozet)} müşteri listelendi. Toplam {self.toplam_kayit_sayisi} kayıt.")
        self.sayfa_bilgisi_label.config(text=f"Sayfa {self.mevcut_sayfa} / {toplam_sayfa}")
        self.secili_musteri_ekstre_buton_guncelle()
        self.guncelle_toplam_ozet_bilgiler() # Listeyi yenilerken özet bilgileri de güncelleyelim

        if len(musteri_listesi_ozet) == 1 and self.mevcut_sayfa == 1 and not arama_terimi == "": # Sadece ilk sayfadaysa ve arama terimi varsa
            first_item_id = musteri_listesi_ozet[0]['id']
            self.tree.selection_set(first_item_id) # Öğeyi seçili yap
            self.tree.focus(first_item_id) # Öğeyi odakla
            self.tree.see(first_item_id) # Öğeyi görünür yap

    def _on_arama_entry_return(self, event=None):
        # Filtrelemeyi tetikle
        self.musteri_listesini_yenile()
        
        # Eğer filtreleme sonrası sadece bir kayıt seçiliyse (ve dolayısıyla odaklanmışsa), ekstreyi aç.
        selected_item_iid = self.tree.focus()
        if selected_item_iid and self.toplam_kayit_sayisi == 1:
            self.secili_musteri_ekstresi_goster()
        elif self.toplam_kayit_sayisi > 1:
            self.app.set_status(f"Birden fazla müşteri bulundu. Lütfen listeden seçiminizi yapın.")
        elif self.toplam_kayit_sayisi == 0:
            self.app.set_status(f"Müşteri bulunamadı.")

    def guncelle_toplam_ozet_bilgiler(self):
        """Müşteri yönetim sayfasındaki toplam alacak ve borç bilgilerini günceller."""
        # Perakende müşteri hariç toplam alacak/borcu hesaplayalım.
        # Bu kısım sadece genel özeti göstermeli, sayfalama ve arama terimiyle filtrelenmemeli.
        
        # Toplam Alacak (Müşteri bize borçlu)
        # Bu, tüm müşterilerin (perakende hariç) pozitif kalan_borc toplamıdır.
        total_alacak_musteri = 0.0
        # get_cari_list_summary_data metodunu tüm veriyi çekmek için kullanalım (limit ve offset olmadan)
        tum_musteri_ozet_data = self.db.get_cari_list_summary_data(
            cari_tip=self.db.CARI_TIP_MUSTERI, 
            perakende_haric=True,
            limit=None, 
            offset=None
        )
        
        for musteri in tum_musteri_ozet_data:
            if musteri['kalan_borc'] > 0: # Müşteri bize borçlu ise (bizim alacağımız)
                total_alacak_musteri += musteri['kalan_borc']

        # Toplam Borç (Müşteri bizden alacaklı)
        # Bu, tüm müşterilerin (perakende hariç) negatif kalan_borc toplamıdır.
        total_borc_musteri = 0.0
        for musteri in tum_musteri_ozet_data:
            if musteri['kalan_borc'] < 0: # Müşteri bizden alacaklı ise (bizim borcumuz)
                total_borc_musteri += abs(musteri['kalan_borc']) # Mutlak değeri alıyoruz

        self.lbl_toplam_alacak_musteri.config(text=f"Toplam Alacak (Müşteri): {self.db._format_currency(total_alacak_musteri)}")
        self.lbl_toplam_borc_musteri.config(text=f"Toplam Borç (Müşteri): {self.db._format_currency(total_borc_musteri)}")


    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.musteri_listesini_yenile()

    def sonraki_sayfa(self):
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0:
            toplam_sayfa = 1 

        if self.mevcut_sayfa < toplam_sayfa:
            self.mevcut_sayfa += 1
            self.musteri_listesini_yenile()

    def yeni_musteri_ekle_penceresi(self):
        from pencereler import YeniMusteriEklePenceresi
        YeniMusteriEklePenceresi(self, self.db, self.musteri_listesini_yenile, app_ref=self.app)
        self.app.set_status("Yeni müşteri ekleme penceresi açıldı.") 

    def musteri_duzenle_event(self, event): self.secili_musteri_duzenle()

    def secili_musteri_duzenle(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen düzenlemek için bir müşteri seçin.", parent=self)
            return
        musteri_id = self.tree.item(selected_item)['values'][0]
        
        if str(musteri_id) == str(self.db.perakende_musteri_id):
             # Sadece adını ve bazı kısıtlı alanları düzenlemeye izin verilebilir. Kodu değiştirilemez.
             # Şimdilik perakende müşterinin düzenlenmesini engelliyoruz ya da kısıtlı bir pencere açabiliriz.
             # Basitlik adına, şimdilik perakende müşterinin adını düzenlemeye izin veren bir pencere açalım.
            musteri_db = self.db.musteri_getir_by_id(musteri_id)
            if musteri_db:
                YeniMusteriEklePenceresi(self, self.db, self.musteri_listesini_yenile, musteri_db, app_ref=self.app)
                self.app.set_status(f"Perakende müşteri '{musteri_db[2]}' düzenleme penceresi açıldı.")                
            else: messagebox.showerror("Hata", "Perakende müşteri kaydı bulunamadı.", parent=self)
            return

        musteri_db = self.db.musteri_getir_by_id(musteri_id)
        if musteri_db:
            from pencereler import YeniMusteriEklePenceresi
            YeniMusteriEklePenceresi(self, self.db, self.musteri_listesini_yenile, musteri_db, app_ref=self.app)
            self.app.set_status(f"Müşteri '{musteri_db[2]}' düzenleme penceresi açıldı.")
        else:
            messagebox.showerror("Hata", "Seçili müşteri veritabanında bulunamadı.", parent=self)
            self.musteri_listesini_yenile()

    def _delayed_musteri_yenile(self, event):
        if self.after_id:
            self.after_cancel(self.after_id)
        self.after_id = self.after(300, self.musteri_listesini_yenile)

    def secili_musteri_sil(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir müşteri seçin.", parent=self)
            return

        musteri_id = self.tree.item(selected_item)['values'][0]
        musteri_adi = self.tree.item(selected_item)['values'][2]

        if str(musteri_id) == str(self.db.perakende_musteri_id):
            messagebox.showerror("Hata", "Genel perakende müşteri kaydı silinemez.", parent=self)
            return

        if messagebox.askyesno("Onay", f"'{musteri_adi}' adlı müşteriyi silmek istediğinizden emin misiniz?", parent=self):
            success, message = self.db.musteri_sil(musteri_id)
            if success:
                messagebox.showinfo("Başarılı", message, parent=self)
                self.musteri_listesini_yenile()
                self.app.set_status(f"'{musteri_adi}' müşterisi silindi.")
            else:
                messagebox.showerror("Hata", message, parent=self)

    def secili_musteri_ekstresi_goster(self, event=None):
        selected_item_iid = self.tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen ekstresini görmek için bir müşteri seçin.", parent=self)
            return
        
        cari_id = selected_item_iid
        
        musteri_db_data = self.db.musteri_getir_by_id(cari_id)
        if not musteri_db_data:
            messagebox.showerror("Hata", "Müşteri bilgileri veritabanından alınamadı.", parent=self)
            return

        musteri_adi = musteri_db_data['ad']
        
        if str(cari_id) == str(self.db.perakende_musteri_id):
            messagebox.showinfo("Bilgi", "Perakende satış müşterisi için hesap ekstresi oluşturulamaz.", parent=self)
            return
        
        from pencereler import CariHesapEkstresiPenceresi 
        CariHesapEkstresiPenceresi(
            self.app, 
            self.db, 
            cari_id, 
            self.db.CARI_TIP_MUSTERI, 
            f"{musteri_adi}", 
            parent_list_refresh_func=self.musteri_listesini_yenile
        )

class TedarikciYonetimiSayfasi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.pack(expand=True, fill=tk.BOTH)
        self.after_id = None
        ttk.Label(self, text="Tedarikçi Yönetimi", font=("Segoe UI", 16, "bold")).pack(pady=10, anchor=tk.W, padx=10)

        # <<< YENİ EKLENEN TOPLAM ÖZET BİLGİLERİ KISMI BAŞLANGICI >>>
        summary_frame = ttk.Frame(self, padding="5")
        summary_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        summary_frame.columnconfigure(0, weight=1)
        summary_frame.columnconfigure(1, weight=1)

        self.lbl_toplam_borc_tedarikci = ttk.Label(summary_frame, text="Toplam Borç (Tedarikçi): Yükleniyor...", font=("Segoe UI", 10, "bold"), foreground="red")
        self.lbl_toplam_borc_tedarikci.grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        
        # Sağa Yaslı, Daha Büyük Yazı Tipi
        self.lbl_toplam_alacak_tedarikci = ttk.Label(summary_frame, text="Toplam Alacak (Tedarikçi): Yükleniyor...", font=("Segoe UI", 10, "bold"), foreground="green")
        self.lbl_toplam_alacak_tedarikci.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        # <<< YENİ EKLENEN TOPLAM ÖZET BİLGİLERİ KISMI BİTİŞİ >>>

        arama_frame = ttk.Frame(self, padding="5")
        arama_frame.pack(fill=tk.X, padx=10)
        ttk.Label(arama_frame, text="Tedarikçi Ara (Kod/Ad/Tel/Adres):").pack(side=tk.LEFT, padx=(0,5))
        self.arama_entry = ttk.Entry(arama_frame, width=35)
        self.arama_entry.pack(side=tk.LEFT, padx=(0,10))
        self.arama_entry.bind("<KeyRelease>", self._delayed_tedarikci_yenile)
        self.arama_entry.bind("<Return>", self._on_arama_entry_return)
        ttk.Button(arama_frame, text="Ara/Yenile", command=self.tedarikci_listesini_yenile).pack(side=tk.LEFT)

        tree_frame = ttk.Frame(self, padding="10")
        tree_frame.pack(expand=True, fill=tk.BOTH)

        # <<< YENİ SÜTUN TANIMLARI VE SIRALAMASI BAŞLANGICI >>>
        # Tedarikçi Yönetimi Sayfası İçin Sütunlar: Satır, Tedarikçi Adı, Fatura Sayısı, AÇIK HESAP, ÖDEME, KALAN BORÇ, Vadesi Geçmiş Borç, Son Ödeme Tarihi
        cols = ("#", "Tedarikçi Adı", "Fatura Sayısı", "AÇIK HESAP", "ÖDEME", "KALAN BORÇ", "Vadesi Geçmiş Borç", "Son Ödeme Tarihi")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode="browse")

        # Sütun Genişlikleri ve Hizalamalar (Tümü Ortada)
        col_definitions = [
            ("#", 50, tk.CENTER, tk.NO),
            ("Tedarikçi Adı", 200, tk.CENTER, tk.YES), # Genişlemesini isteyelim
            ("Fatura Sayısı", 100, tk.CENTER, tk.NO),
            ("AÇIK HESAP", 120, tk.CENTER, tk.NO),
            ("ÖDEME", 120, tk.CENTER, tk.NO),
            ("KALAN BORÇ", 120, tk.CENTER, tk.NO),
            ("Vadesi Geçmiş Borç", 120, tk.CENTER, tk.NO),
            ("Son Ödeme Tarihi", 120, tk.CENTER, tk.NO)
        ]
        
        for col_name, width, anchor, stretch_val in col_definitions:
            self.tree.heading(col_name, text=col_name, command=lambda _col=col_name: sort_treeview_column(self.tree, _col, False))
            self.tree.column(col_name, width=width, stretch=stretch_val, anchor=anchor)
        # <<< YENİ SÜTUN TANIMLARI VE SIRALAMASI BİTİŞİ >>>

        # Treeview genel stil ayarları (önceki konuşmalardan)
        style = ttk.Style()
        style.configure("Treeview", 
                        fieldbackground="white", # Varsayılan arka plan beyaz
                        background="white",      
                        foreground="black", 
                        rowheight=25) 
        style.configure("Treeview.Heading", font=('Segoe UI', 9, 'bold'))
        style.map('Treeview',
                  fieldbackground=[('selected', '#32679F')], 
                  foreground=[('selected', 'white')], 
                  background=[('selected', '#32679F')]) 
        
        # Tedarikçi ve borç durumuna göre renk tag'leri
        self.tree.tag_configure('borclu_tedarikci', background='#FFDDDD', foreground='red')     # Kalan borç > 0 ise (biz borçluyuz)
        self.tree.tag_configure('alacakli_tedarikci', background='#D5F5E3', foreground='green') # Kalan borç < 0 ise (tedarikçi bize borçlu)
        self.tree.tag_configure('vadesi_gecmis', background='#F8D7DA', foreground='darkred', font=('Segoe UI', 9, 'bold')) # Vadesi geçmiş borç varsa

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(expand=True, fill=tk.BOTH)
        self.tree.bind("<Double-1>", self.secili_tedarikci_ekstresi_goster)
        self.tree.bind("<<TreeviewSelect>>", self.secili_tedarikci_ekstre_buton_guncelle)


        button_frame = ttk.Frame(self, padding="10")
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Yeni Tedarikçi Ekle", command=self.yeni_tedarikci_ekle_penceresi, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Seçili Tedarikçiyi Düzenle", command=self.secili_tedarikci_duzenle).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Seçili Tedarikçiyi Sil", command=self.secili_tedarikci_sil).pack(side=tk.LEFT, padx=5)
        self.ekstre_button_ted = ttk.Button(button_frame, text="Seçili Tedarikçi Ekstresi", command=self.secili_tedarikci_ekstresi_goster, state=tk.DISABLED)
        self.ekstre_button_ted.pack(side=tk.LEFT, padx=5)

        self.kayit_sayisi_per_sayfa = 25
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0

        pagination_frame = ttk.Frame(self, padding="10")
        pagination_frame.pack(fill=tk.X, padx=10, pady=5, side=tk.BOTTOM)

        ttk.Button(pagination_frame, text="Önceki Sayfa", command=self.onceki_sayfa).pack(side=tk.LEFT, padx=5)
        self.sayfa_bilgisi_label = ttk.Label(pagination_frame, text="Sayfa 1 / 1")
        self.sayfa_bilgisi_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(pagination_frame, text="Sonraki Sayfa", command=self.sonraki_sayfa).pack(side=tk.LEFT, padx=5)
        
        # Sayfa yüklendiğinde özet bilgileri güncelleyelim.
        self.guncelle_toplam_ozet_bilgiler()
        self.arama_entry.focus_set()
    def secili_tedarikci_ekstre_buton_guncelle(self, event=None):
        if self.tree.focus(): self.ekstre_button_ted.config(state=tk.NORMAL)
        else: self.ekstre_button_ted.config(state=tk.DISABLED)


    def tedarikci_listesini_yenile(self, event=None):
        for i in self.tree.get_children():
            self.tree.delete(i)
        arama_terimi = self.arama_entry.get()
        
        # <<< VERİTABANI ÇAĞRISINI get_cari_list_summary_data ile değiştiriyoruz >>>
        # Toplam kayıt sayısını alalım (sayfalama için)
        self.toplam_kayit_sayisi = self.db.get_cari_count(cari_tip=self.db.CARI_TIP_TEDARIKCI, arama_terimi=arama_terimi) 
        
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0:
            toplam_sayfa = 1
        
        if self.mevcut_sayfa > toplam_sayfa:
            self.mevcut_sayfa = toplam_sayfa
        if self.mevcut_sayfa < 1:
            self.mevcut_sayfa = 1
            
        offset = (self.mevcut_sayfa - 1) * self.kayit_sayisi_per_sayfa
        limit = self.kayit_sayisi_per_sayfa

        # Yeni özet verilerini çekelim
        tedarikci_listesi_ozet = self.db.get_cari_list_summary_data(
            cari_tip=self.db.CARI_TIP_TEDARIKCI,
            arama_terimi=arama_terimi,
            limit=limit,
            offset=offset
        )
        
        # >>> BURADAKİ DÖNGÜYÜ YENİ VERİ YAPISINA GÖRE DÜZENLİYORUZ <<<
        sira_no = offset + 1
        for tedarikci_data in tedarikci_listesi_ozet:
            # Renk taglerini belirleyelim
            tags = []
            if tedarikci_data['kalan_borc'] > 0:
                tags.append('borclu_tedarikci') # Kalan borç pozitifse (biz tedarikçiye borçluyuz)
            elif tedarikci_data['kalan_borc'] < 0:
                tags.append('alacakli_tedarikci') # Kalan borç negatifse (tedarikçi bizden alacaklı)
            
            if tedarikci_data['vadesi_gecmis_borc'] > 0:
                tags.append('vadesi_gecmis') # Vadesi geçmiş borç varsa

            self.tree.insert("", "end", iid=tedarikci_data['id'], values=(
                sira_no, # Satır Numarası
                tedarikci_data['cari_adi'], # Tedarikçi Adı
                tedarikci_data['fatura_sayisi'], # Fatura Sayısı
                self.db._format_currency(tedarikci_data['acik_hesap_toplam']), # AÇIK HESAP
                self.db._format_currency(tedarikci_data['odeme_tahsilat_toplam']), # ÖDEME
                self.db._format_currency(tedarikci_data['kalan_borc']), # KALAN BORÇ
                self.db._format_currency(tedarikci_data['vadesi_gecmis_borc']), # Vadesi Geçmiş Borç
                tedarikci_data['son_odeme_tarihi'] # Son Ödeme Tarihi
            ), tags=tuple(tags))
            sira_no += 1
            
        self.app.set_status(f"{len(tedarikci_listesi_ozet)} tedarikçi listelendi. Toplam {self.toplam_kayit_sayisi} kayıt.")
        self.sayfa_bilgisi_label.config(text=f"Sayfa {self.mevcut_sayfa} / {toplam_sayfa}")
        self.secili_tedarikci_ekstre_buton_guncelle()
        self.guncelle_toplam_ozet_bilgiler() # Listeyi yenilerken özet bilgileri de güncelleyelim

        if len(tedarikci_listesi_ozet) == 1 and self.mevcut_sayfa == 1 and not arama_terimi == "": # Sadece ilk sayfadaysa ve arama terimi varsa
            first_item_id = tedarikci_listesi_ozet[0]['id']
            self.tree.selection_set(first_item_id) # Öğeyi seçili yap
            self.tree.focus(first_item_id) # Öğeyi odakla
            self.tree.see(first_item_id) # Öğeyi görünür yap

    def _on_arama_entry_return(self, event=None):
        # Filtrelemeyi tetikle
        self.tedarikci_listesini_yenile()
        
        # Eğer filtreleme sonrası sadece bir kayıt seçiliyse (ve dolayısıyla odaklanmışsa), ekstreyi aç.
        selected_item_iid = self.tree.focus()
        if selected_item_iid and self.toplam_kayit_sayisi == 1:
            self.secili_tedarikci_ekstresi_goster()
        elif self.toplam_kayit_sayisi > 1:
            self.app.set_status(f"Birden fazla tedarikçi bulundu. Lütfen listeden seçiminizi yapın.")
        elif self.toplam_kayit_sayisi == 0:
            self.app.set_status(f"Tedarikçi bulunamadı.")

    def guncelle_toplam_ozet_bilgiler(self):
        """Tedarikçi yönetim sayfasındaki toplam borç ve alacak bilgilerini günceller."""
        # Tüm tedarikçilerin özet verilerini alalım (filtreleme veya sayfalama yapmadan)
        tum_tedarikci_ozet_data = self.db.get_cari_list_summary_data(
            cari_tip=self.db.CARI_TIP_TEDARIKCI, 
            limit=None, 
            offset=None
        )
        
        # Toplam Borç (Biz tedarikçiye borçluyuz)
        total_borc_tedarikci = 0.0
        for tedarikci in tum_tedarikci_ozet_data:
            if tedarikci['kalan_borc'] > 0: # Biz tedarikçiye borçlu isek
                total_borc_tedarikci += tedarikci['kalan_borc']

        # Toplam Alacak (Tedarikçi bizden alacaklı)
        total_alacak_tedarikci = 0.0
        for tedarikci in tum_tedarikci_ozet_data:
            if tedarikci['kalan_borc'] < 0: # Tedarikçi bizden alacaklı ise (bizim alacağımız)
                total_alacak_tedarikci += abs(tedarikci['kalan_borc']) # Mutlak değeri alıyoruz

        self.lbl_toplam_borc_tedarikci.config(text=f"Toplam Borç (Tedarikçi): {self.db._format_currency(total_borc_tedarikci)}")
        self.lbl_toplam_alacak_tedarikci.config(text=f"Toplam Alacak (Tedarikçi): {self.db._format_currency(total_alacak_tedarikci)}")


    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.tedarikci_listesini_yenile()

    def sonraki_sayfa(self):
        
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0:
            toplam_sayfa = 1 

        if self.mevcut_sayfa < toplam_sayfa:
            self.mevcut_sayfa += 1
            self.tedarikci_listesini_yenile()

    def _delayed_tedarikci_yenile(self, event):
        if self.after_id:
            self.after_cancel(self.after_id)
        self.after_id = self.after(300, self.tedarikci_listesini_yenile)

    def yeni_tedarikci_ekle_penceresi(self):
        from pencereler import YeniTedarikciEklePenceresi
        YeniTedarikciEklePenceresi(self, self.db, self.tedarikci_listesini_yenile, app_ref=self.app)
        self.app.set_status("Yeni tedarikçi ekleme penceresi açıldı.") 
    def tedarikci_duzenle_event(self, event): self.secili_tedarikci_duzenle()
    def secili_tedarikci_duzenle(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen düzenlemek için bir tedarikçi seçin.", parent=self)
            return
        tedarikci_id = self.tree.item(selected_item)['values'][0]
        tedarikci_db = self.db.tedarikci_getir_by_id(tedarikci_id)
        if tedarikci_db:
            from pencereler import YeniTedarikciEklePenceresi
            YeniTedarikciEklePenceresi(self.app, self.db, self.tedarikci_listesini_yenile, tedarikci_db, app_ref=self.app)
            self.app.set_status(f"Tedarikçi '{tedarikci_db[2]}' düzenleme penceresi açıldı.") 
        else:
            messagebox.showerror("Hata", "Seçili tedarikçi veritabanında bulunamadı.", parent=self)
            self.tedarikci_listesini_yenile()

    def secili_tedarikci_sil(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir tedarikçi seçin.", parent=self)
            return

        tedarikci_id = self.tree.item(selected_item)['values'][0]
        tedarikci_adi = self.tree.item(selected_item)['values'][2]

        if messagebox.askyesno("Onay", f"'{tedarikci_adi}' adlı tedarikçiyi silmek istediğinizden emin misiniz?", parent=self):
            success, message = self.db.tedarikci_sil(tedarikci_id)
            if success:
                messagebox.showinfo("Başarılı", message, parent=self)
                self.tedarikci_listesini_yenile()
                self.app.set_status(f"'{tedarikci_adi}' tedarikçisi silindi.")
            else:
                messagebox.showerror("Hata", message, parent=self)

    def secili_tedarikci_ekstresi_goster(self, event=None):
        selected_item_iid = self.tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen ekstresini görmek için bir tedarikçi seçin.", parent=self)
            return
        
        cari_id = selected_item_iid
        
        tedarikci_db_data = self.db.tedarikci_getir_by_id(cari_id)
        if not tedarikci_db_data:
            messagebox.showerror("Hata", "Tedarikçi bilgileri veritabanından alınamadı.", parent=self)
            return

        tedarikci_adi = tedarikci_db_data['ad']
        
        from pencereler import CariHesapEkstresiPenceresi 
        CariHesapEkstresiPenceresi(
            self.app, 
            self.db, 
            cari_id, 
            self.db.CARI_TIP_TEDARIKCI, 
            f"{tedarikci_adi}", 
            parent_list_refresh_func=self.tedarikci_listesini_yenile
        )

class FaturaListesiSayfasi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.pack(expand=True, fill=tk.BOTH)

        ttk.Label(self, text="Faturalar", font=("Segoe UI", 16, "bold")).pack(pady=(10,5), anchor=tk.W, padx=10)

        # Ana Notebook (Sekmeli Yapı)
        self.main_notebook = ttk.Notebook(self)
        self.main_notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        # Satış Faturaları Sekmesi
        self.satis_fatura_frame = SatisFaturalariListesi(self.main_notebook, self.db, self.app, fatura_tipi='SATIŞ')
        self.main_notebook.add(self.satis_fatura_frame, text="🛍️ Satış Faturaları")

        # Alış Faturaları Sekmesi
        self.alis_fatura_frame = AlisFaturalariListesi(self.main_notebook, self.db, self.app, fatura_tipi='ALIŞ')
        self.main_notebook.add(self.alis_fatura_frame, text="🛒 Alış Faturaları")
        
        # Sekme değiştiğinde listeleri yenilemek için event bağla
        self.main_notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _on_tab_change(self, event):
        selected_tab_id = self.main_notebook.select()
        selected_tab_widget = self.main_notebook.nametowidget(selected_tab_id)
        
        if hasattr(selected_tab_widget, 'fatura_listesini_yukle'):
            selected_tab_widget.fatura_listesini_yukle()

class SiparisListesiSayfasi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.pack(expand=True, fill=tk.BOTH)
        self.after_id = None
        ttk.Label(self, text="Sipariş Yönetimi", font=("Segoe UI", 16, "bold")).pack(pady=(10,5), anchor=tk.W, padx=10)

        # Filtreleme ve Arama Çerçevesi (Fatura Listesi gibi)
        filter_top_frame = ttk.Frame(self)
        filter_top_frame.pack(pady=5, padx=10, fill=tk.X)

        ttk.Label(filter_top_frame, text="Başlangıç Tarihi:").pack(side=tk.LEFT, padx=(0,2))
        self.bas_tarih_entry = ttk.Entry(filter_top_frame, width=12)
        self.bas_tarih_entry.pack(side=tk.LEFT, padx=(0,5))
        self.bas_tarih_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')) # Son 30 gün
        setup_date_entry(self.app, self.bas_tarih_entry)
        ttk.Button(filter_top_frame, text="🗓️", command=lambda: DatePickerDialog(self.app, self.bas_tarih_entry), width=3).pack(side=tk.LEFT, padx=2)

        ttk.Label(filter_top_frame, text="Bitiş Tarihi:").pack(side=tk.LEFT, padx=(0,2))
        self.bit_tarih_entry = ttk.Entry(filter_top_frame, width=12)
        self.bit_tarih_entry.pack(side=tk.LEFT, padx=(0,10))
        self.bit_tarih_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        setup_date_entry(self.app, self.bit_tarih_entry)
        ttk.Button(filter_top_frame, text="🗓️", command=lambda: DatePickerDialog(self.app, self.bit_tarih_entry), width=3).pack(side=tk.LEFT, padx=2)

        ttk.Label(filter_top_frame, text="Ara (Sipariş No/Cari/Ürün):").pack(side=tk.LEFT, padx=(10,2))
        self.arama_siparis_entry = ttk.Entry(filter_top_frame, width=30)
        self.arama_siparis_entry.pack(side=tk.LEFT, padx=(0,5))
        self.arama_siparis_entry.bind("<KeyRelease>", self._delayed_siparis_listesi_yukle)

        ttk.Button(filter_top_frame, text="Temizle", command=self._arama_temizle).pack(side=tk.LEFT, padx=(0,10))
        ttk.Button(filter_top_frame, text="Filtrele/Yenile", command=self.siparis_listesini_yukle, style="Accent.TButton").pack(side=tk.LEFT)

        # Filtreleme Alanları (Cari, Durum, Sipariş Tipi)
        filter_bottom_frame = ttk.Frame(self)
        filter_bottom_frame.pack(pady=0, padx=10, fill=tk.X)

        ttk.Label(filter_bottom_frame, text="Cari Filtre:").pack(side=tk.LEFT, padx=(0,2))
        self.cari_filter_cb = ttk.Combobox(filter_bottom_frame, width=25, state="readonly")
        self.cari_filter_cb.pack(side=tk.LEFT, padx=(0,10))
        self.cari_filter_cb.bind("<<ComboboxSelected>>", lambda event: self.siparis_listesini_yukle())

        ttk.Label(filter_bottom_frame, text="Durum:").pack(side=tk.LEFT, padx=(0,2))
        self.durum_filter_cb = ttk.Combobox(filter_bottom_frame, width=15, 
                                            values=["TÜMÜ", self.db.SIPARIS_DURUM_BEKLEMEDE, # <-- Düzeltildi
                                                    self.db.SIPARIS_DURUM_TAMAMLANDI, # <-- Düzeltildi
                                                    self.db.SIPARIS_DURUM_KISMİ_TESLIMAT, # <-- Düzeltildi
                                                    self.db.SIPARIS_DURUM_IPTAL_EDILDI], # <-- Düzeltildi
                                            state="readonly")
        self.durum_filter_cb.pack(side=tk.LEFT, padx=(0,10))
        self.durum_filter_cb.current(0)
        self.durum_filter_cb.bind("<<ComboboxSelected>>", lambda event: self.siparis_listesini_yukle())

        ttk.Label(filter_bottom_frame, text="Sipariş Tipi:").pack(side=tk.LEFT, padx=(0,2))
        self.siparis_tipi_filter_cb = ttk.Combobox(filter_bottom_frame, width=15, 
                                                    values=["TÜMÜ", self.db.SIPARIS_TIP_SATIS, self.db.SIPARIS_TIP_ALIS], # <-- Düzeltildi
                                                    state="readonly")
        self.siparis_tipi_filter_cb.pack(side=tk.LEFT, padx=(0,10))
        self.siparis_tipi_filter_cb.current(0)
        self.siparis_tipi_filter_cb.bind("<<ComboboxSelected>>", lambda event: self.siparis_listesini_yukle())

        # Butonlar Çerçevesi
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=5, padx=10, fill=tk.X)
        ttk.Button(button_frame, text="Yeni Müşteri Siparişi", 
                   command=lambda: self.yeni_siparis_penceresi_ac(self.db.SIPARIS_TIP_SATIS), # <-- Düzeltildi
                   style="Accent.TButton").pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(button_frame, text="Yeni Tedarikçi Siparişi", 
                   command=lambda: self.yeni_siparis_penceresi_ac(self.db.SIPARIS_TIP_ALIS), # <-- Düzeltildi
                   style="Accent.TButton").pack(side=tk.LEFT, padx=5)

        self.detay_goster_button = ttk.Button(button_frame, text="Seçili Sipariş Detayları", command=self.secili_siparis_detay_goster, state=tk.DISABLED)
        self.detay_goster_button.pack(side=tk.LEFT, padx=5)
        self.duzenle_button = ttk.Button(button_frame, text="Seçili Siparişi Düzenle", command=self.secili_siparisi_duzenle, state=tk.DISABLED)
        self.duzenle_button.pack(side=tk.LEFT, padx=5)
        self.faturaya_donustur_button = ttk.Button(button_frame, text="Seçili Siparişi Faturaya Dönüştür", command=self.secili_siparisi_faturaya_donustur, style="Accent.TButton", state=tk.DISABLED)
        self.faturaya_donustur_button.pack(side=tk.LEFT, padx=5)
        self.sil_button = ttk.Button(button_frame, text="Seçili Siparişi Sil", command=self.secili_siparisi_sil, state=tk.DISABLED)
        self.sil_button.pack(side=tk.LEFT, padx=5)

        self.kayit_sayisi_per_sayfa = 20
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0

        pagination_frame = ttk.Frame(self, padding="10")
        pagination_frame.pack(fill=tk.X, padx=10, pady=5) 

        ttk.Button(pagination_frame, text="Önceki Sayfa", command=self.onceki_sayfa).pack(side=tk.LEFT, padx=5)
        self.sayfa_bilgisi_label = ttk.Label(pagination_frame, text="Sayfa 1 / 1")
        self.sayfa_bilgisi_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(pagination_frame, text="Sonraki Sayfa", command=self.sonraki_sayfa).pack(side=tk.LEFT, padx=5)

        # Sipariş Listesi (Treeview)
        cols = ("ID", "Sipariş No", "Tarih", "Cari Adı", "Sipariş Tipi", "Toplam Tutar", "Durum", "Teslimat Tarihi")
        self.siparis_tree = ttk.Treeview(self, columns=cols, show='headings', selectmode="browse")

        col_defs = [
            ("ID", 40, tk.E, tk.NO),
            ("Sipariş No", 100, tk.W, tk.NO),
            ("Tarih", 85, tk.CENTER, tk.NO),
            ("Cari Adı", 180, tk.W, tk.YES),
            ("Sipariş Tipi", 100, tk.CENTER, tk.NO),
            ("Toplam Tutar", 110, tk.E, tk.NO),
            ("Durum", 100, tk.CENTER, tk.NO),
            ("Teslimat Tarihi", 90, tk.CENTER, tk.NO)
        ]
        for col_name, width, anchor, stretch_opt in col_defs:
            self.siparis_tree.column(col_name, width=width, anchor=anchor, stretch=stretch_opt)
            self.siparis_tree.heading(col_name, text=col_name, command=lambda c=col_name: sort_treeview_column(self.siparis_tree, c, False))

        self.siparis_tree.tag_configure('tamamlandi', background='#D5F5E3', foreground='green') # Açık Yeşil
        self.siparis_tree.tag_configure('beklemede', background='#FCF3CF', foreground='#874F15') # Açık Sarı
        self.siparis_tree.tag_configure('iptal_edildi', background='#FADBD8', foreground='gray', font=('Segoe UI', 9, 'overstrike')) # Açık Kırmızı ve üzeri çizili        
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.siparis_tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.siparis_tree.xview)
        self.siparis_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.siparis_tree.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        self.siparis_tree.tag_configure('tamamlandi', background='#D5F5E3', foreground='green') # Açık Yeşil
        self.siparis_tree.tag_configure('beklemede', background='#FCF3CF', foreground='#874F15') # Açık Sarı
        self.siparis_tree.tag_configure('iptal_edildi', background='#FADBD8', foreground='gray', font=('Segoe UI', 9, 'overstrike')) # Açık Kırmızı ve üzeri çizili

        self.siparis_tree.bind("<<TreeviewSelect>>", self._on_siparis_select) 
        self.siparis_tree.bind("<Double-1>", self.on_double_click_detay_goster)

        self._yukle_filtre_comboboxlari()
        self.siparis_listesini_yukle()
        self._on_siparis_select()

    def _open_date_picker(self, target_entry):
        from arayuz import DatePickerDialog # Lokal import
        DatePickerDialog(self.app, target_entry)

    def _delayed_siparis_listesi_yukle(self, event):
        if self.after_id:
            self.after_cancel(self.after_id)
        self.after_id = self.after(300, self.siparis_listesini_yukle)

    def _yukle_filtre_comboboxlari(self):
        cari_display_values = ["TÜMÜ"]
        self.cari_filter_map = {"TÜMÜ": None}

        musteriler = self.db.musteri_listesi_al(perakende_haric=False)
        for m in musteriler:
            display_text = f"{m[2]} (M: {m[1]})" # Müşteri için "M:" öneki
            self.cari_filter_map[display_text] = str(m[0])
            cari_display_values.append(display_text)

        tedarikciler = self.db.tedarikci_listesi_al()
        for t in tedarikciler:
            display_text = f"{t[2]} (T: {t[1]})" # Tedarikçi için "T:" öneki
            self.cari_filter_map[display_text] = str(t[0])
            cari_display_values.append(display_text)

        self.cari_filter_cb['values'] = ["TÜMÜ"] + sorted([v for v in cari_display_values if v != "TÜMÜ"])
        self.cari_filter_cb.current(0)

    def _on_siparis_select(self, event=None):
        selected_item = self.siparis_tree.focus()
        if selected_item:
            durum = self.siparis_tree.item(selected_item, 'values')[6] # Durum sütunu 7. sırada (indeks 6)
            self.detay_goster_button.config(state=tk.NORMAL)
            self.sil_button.config(state=tk.NORMAL)
            
            # TAMAMLANDI veya İPTAL EDİLDİ ise Düzenle ve Faturaya Dönüştür pasif olsun
            if durum == 'TAMAMLANDI' or durum == 'İPTAL_EDİLDİ':
                self.duzenle_button.config(state=tk.DISABLED)
                self.faturaya_donustur_button.config(state=tk.DISABLED)
            else: # BEKLEMEDE veya KISMİ_TESLİMAT ise aktif olsun
                self.duzenle_button.config(state=tk.NORMAL)
                self.faturaya_donustur_button.config(state=tk.NORMAL)
        else:
            self.detay_goster_button.config(state=tk.DISABLED)
            self.duzenle_button.config(state=tk.DISABLED)
            self.faturaya_donustur_button.config(state=tk.DISABLED)
            self.sil_button.config(state=tk.DISABLED)


    def _arama_temizle(self):
        self.arama_siparis_entry.delete(0, tk.END)
        self.siparis_listesini_yukle()

    def siparis_listesini_yukle(self):
        for i in self.siparis_tree.get_children():
            self.siparis_tree.delete(i)
        
        bas_t = self.bas_tarih_entry.get()
        bit_t = self.bit_tarih_entry.get()
        arama_terimi = self.arama_siparis_entry.get().strip()

        selected_cari_filter_text = self.cari_filter_cb.get()
        cari_id_filter_val = self.cari_filter_map.get(selected_cari_filter_text, None)

        selected_durum_filter = self.durum_filter_cb.get()
        durum_filter_val = selected_durum_filter if selected_durum_filter != "TÜMÜ" else None
        
        selected_siparis_tipi_filter = self.siparis_tipi_filter_cb.get()
        
        # Düzeltilmiş Mantık: Arayüzdeki combobox'tan gelen değere göre veritabanına gönderilecek
        # cari_tip değerini doğru şekilde ayarlıyoruz.
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
            
            tags = ()
            if durum == 'TAMAMLANDI': tags = ('tamamlandi',)
            elif durum in ['BEKLEMEDE', 'KISMİ_TESLİMAT']: tags = ('beklemede',)
            elif durum == 'İPTAL_EDİLDİ': tags = ('iptal_edildi',)

            self.siparis_tree.insert("", tk.END, values=(
                siparis_id, siparis_no, formatted_tarih, cari_adi_display, siparis_tipi_gosterim,
                self.db._format_currency(toplam_tutar), durum, formatted_teslimat_tarihi
            ), iid=siparis_id, tags=tags)
        
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

        self.app.set_status(f"Sipariş listesi güncellendi ({len(siparis_verileri)} kayıt). Toplam {self.toplam_kayit_sayisi} kayıt.")
        self.sayfa_bilgisi_label.config(text=f"Sayfa {self.mevcut_sayfa} / {toplam_sayfa}")
        self._on_siparis_select()
        
    def on_item_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id: return

        hareket = self.tree_item_map.get(item_id)
        if not hareket: return

        if hareket.get('ref_tip') == 'FATURA':
            fatura_id = hareket.get('ref_id')
            if fatura_id:
                logging.debug(f"Fatura detayı açılıyor. Fatura ID: {fatura_id}")
                if hasattr(self.app, 'fatura_detay_goster'):
                    self.app.fatura_detay_goster(fatura_id)
                else:
                    messagebox.showerror("Metod Hatası", "Uygulama içinde 'fatura_detay_goster' metodu bulunamadı.", parent=self)
        else:
            messagebox.showinfo("Bilgi", "Bu işlem bir fatura değildir, detayı görüntülenemez.", parent=self)

    def yeni_siparis_penceresi_ac(self, siparis_tipi):
        from pencereler import SiparisPenceresi
        SiparisPenceresi(
            self.app, 
            self.db, 
            self.app,
            siparis_tipi,
            yenile_callback=self.siparis_listesini_yukle
        )
        self.app.set_status(f"Yeni {siparis_tipi.lower().replace('_', ' ')} penceresi açıldı.")


    def _urun_listesini_filtrele_anlik(self, event=None):
        arama_terimi = self.urun_arama_entry.get().lower().strip()
        for i in self.urun_arama_sonuclari_tree.get_children():
            self.urun_arama_sonuclari_tree.delete(i)
    
        self.urun_map_filtrelenmis.clear()

        filtered_items_iids = []

        current_search_results = self.db.stok_listele(arama_terimi=arama_terimi)

        # self.siparis_tipi (MUSTERI/TEDARIKCI) kullanarak uygun fiyat sütununu belirle
        fiyat_sutunu_alis_mi_satis_mi = None
        if self.islem_tipi == 'SATIŞ_SIPARIS':
            fiyat_sutunu_alis_mi_satis_mi = 'SATIŞ'
        elif self.islem_tipi == 'ALIŞ_SIPARIS':
            fiyat_sutunu_alis_mi_satis_mi = 'ALIŞ'
        logging.debug(f"_urun_listesini_filtrele_anlik - self.islem_tipi: {self.islem_tipi}")
        logging.debug(f"_urun_listesini_filtrele_anlik - türetilen fiyat_sutunu_alis_mi_satis_mi: {fiyat_sutunu_alis_mi_satis_mi}")

        for urun_item in current_search_results:
            urun_id = urun_item[0]
            urun_kodu_db = urun_item[1]
            urun_adi_db = urun_item[2]
            stok_db = urun_item[3]
            kdv_db = urun_item[6]
            alis_fiyati_kdv_dahil_db = urun_item[8]
            satis_fiyati_kdv_dahil_db = urun_item[9]
        
            fiyat_to_display = 0.0 # Her döngü başında sıfırla
        
            # Fiyat ataması koşullarını düzenleyelim ve item_iid'yi her zaman tanımlayalım
            item_iid = f"search_{urun_id}" # item_iid'yi koşulun dışında tanımla

            if fiyat_sutunu_alis_mi_satis_mi == 'ALIŞ':
                fiyat_to_display = alis_fiyati_kdv_dahil_db
                logging.debug(f"_urun_listesini_filtrele_anlik - Ürün {urun_adi_db} (ID: {urun_id}): ALIŞ fiyatı seçildi: {fiyat_to_display}")
            elif fiyat_sutunu_alis_mi_satis_mi == 'SATIŞ':
                fiyat_to_display = satis_fiyati_kdv_dahil_db
                logging.debug(f"_urun_listesini_filtrele_anlik - Ürün {urun_adi_db} (ID: {urun_id}): SATIŞ fiyatı seçildi: {fiyat_to_display}")
            else:
                logging.debug(f"_urun_listesini_filtrele_anlik - Ürün {urun_adi_db} (ID: {urun_id}): Bilinmeyen siparis_tipi, fiyat 0.0 kaldı.")
                # Fiyatın 0.0 kalması durumunda da Treeview'e ekleme yapılmalı, sadece fiyat 0.0 olur.

            self.urun_arama_sonuclari_tree.insert("", tk.END, iid=item_iid, values=(
                urun_adi_db, 
                urun_kodu_db, 
                self.db._format_currency(fiyat_to_display), 
                f"{stok_db:.2f}"
            ))
            self.urun_map_filtrelenmis[item_iid] = {
                "id": urun_id, "kod": urun_kodu_db, "ad": urun_adi_db, 
                "fiyat": fiyat_to_display, 
                "kdv": kdv_db, "stok": stok_db
            }
            filtered_items_iids.append(item_iid)


        # Eğer filtreleme sonrası sadece bir ürün kalmışsa, o ürünü otomatik seç ve odakla
        if len(filtered_items_iids) == 1:
            self.urun_arama_sonuclari_tree.selection_set(filtered_items_iids[0]) # Öğeyi seçili yap
            self.urun_arama_sonuclari_tree.focus(filtered_items_iids[0]) # Öğeyi odakla

        self.secili_urun_bilgilerini_goster_arama_listesinden(None) # Seçimi güncelle

    def _urunleri_yukle_ve_cachele_ve_goster(self):
        fatura_tipi_for_db = 'SATIŞ' if self.islem_tipi in ['SATIŞ', 'SATIŞ_SIPARIS'] else 'ALIŞ'
        # db.stok_getir_for_fatura metodu sadece ilgili fiyat kolonunu döndürdüğü için burası doğru.
        self.tum_urunler_cache = self.db.stok_getir_for_fatura(fatura_tipi_for_db, arama_terimi=None)
        
        self._urun_listesini_filtrele_anlik() # Tüm listeyi filtreleyip göster

    def secili_siparis_detay_goster(self):
        selected_item_iid = self.siparis_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen detaylarını görmek için bir sipariş seçin.", parent=self.app)
            return
        from pencereler import SiparisDetayPenceresi
        siparis_id = int(selected_item_iid)
        SiparisDetayPenceresi(self.app, self.db, siparis_id, yenile_callback=self.siparis_listesini_yukle)

    def on_double_click_detay_goster(self, event):
        self.secili_siparis_detay_goster()

    def secili_siparisi_duzenle(self):
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR >>>
        selected_item_iid = self.siparis_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen düzenlemek için bir sipariş seçin.", parent=self.app)
            return
        
        siparis_id = int(selected_item_iid)
        siparis_ana_info = self.db.get_siparis_by_id(siparis_id)
        if not siparis_ana_info:
            messagebox.showerror("Hata","Sipariş bilgileri alınamadı.", parent=self.app)
            return
            
        siparis_tipi_db = 'SATIŞ_SIPARIS' if siparis_ana_info['cari_tip'] == 'MUSTERI' else 'ALIŞ_SIPARIS'
        
        from pencereler import SiparisPenceresi 
        
        SiparisPenceresi(
            self.app, 
            self.db, 
            self.app,
            siparis_tipi_db,
            siparis_id_duzenle=siparis_id,
            yenile_callback=self.siparis_listesini_yukle
        )

    def secili_siparisi_faturaya_donustur(self):
        selected_item_iid = self.siparis_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen faturaya dönüştürmek için bir sipariş seçin.", parent=self.app)
            return

        siparis_id = int(selected_item_iid)
        siparis_ana_info = self.db.get_siparis_by_id(siparis_id)
        if not siparis_ana_info:
            messagebox.showerror("Hata", "Dönüştürülecek sipariş bilgileri alınamadı.", parent=self.app)
            return

        cari_tip_db = siparis_ana_info['cari_tip']
        cari_id_db = siparis_ana_info['cari_id']
        fatura_tipi_for_dialog = 'SATIŞ' if cari_tip_db == 'MUSTERI' else 'ALIŞ'
        s_no = siparis_ana_info['siparis_no']

        from pencereler import OdemeTuruSecimDialog # Lokal import
        OdemeTuruSecimDialog(
            self.app,
            self.db, 
            fatura_tipi_for_dialog,
            cari_id_db,
            lambda odeme_turu, kasa_banka_id, vade_tarihi: self._on_fatura_donustur_dialog_closed(
                siparis_id, s_no, odeme_turu, kasa_banka_id, vade_tarihi
            )
        )
        self.app.set_status(f"Sipariş '{s_no}' için faturaya dönüştürme başlatıldı.")

    def _on_fatura_donustur_dialog_closed(self, siparis_id, s_no, odeme_turu, kasa_banka_id, vade_tarihi):
        # <<< METODUN TAMAMINI BU KOD İLE DEĞİŞTİRİN >>>
        if odeme_turu is None:
            self.app.set_status("Faturaya dönüştürme iptal edildi (ödeme türü seçilmedi).")
            return

        confirm_msg = (f"'{s_no}' numaralı siparişi '{odeme_turu}' ödeme türü ile faturaya dönüştürmek istediğinizden emin misiniz?\n"
                       f"Bu işlem sonucunda yeni bir fatura oluşturulacak ve sipariş durumu güncellenecektir.")
        if odeme_turu == "AÇIK HESAP" and vade_tarihi:
            confirm_msg += f"\nVade Tarihi: {vade_tarihi}"
        if kasa_banka_id:
            kb_bilgi = self.db.kasa_banka_getir_by_id(kasa_banka_id)
            if kb_bilgi:
                confirm_msg += f"\nİşlem Kasa/Banka: {kb_bilgi['hesap_adi']}"

        if not messagebox.askyesno("Faturaya Dönüştür Onayı", confirm_msg, parent=self.app):
            return

        # Çağrı artık self.app.fatura_servisi üzerinden yapılıyor
        success, message = self.app.fatura_servisi.siparis_faturaya_donustur(
            siparis_id,
            self.app.current_user[0] if self.app and self.app.current_user else None,
            odeme_turu,
            kasa_banka_id,
            vade_tarihi
        )

        if success:
            messagebox.showinfo("Başarılı", message, parent=self.app)
            self.siparis_listesini_yukle()
            if hasattr(self.app, 'fatura_listesi_sayfasi'):
                if hasattr(self.app.fatura_listesi_sayfasi.satis_fatura_frame, 'fatura_listesini_yukle'):
                    self.app.fatura_listesi_sayfasi.satis_fatura_frame.fatura_listesini_yukle()
                if hasattr(self.app.fatura_listesi_sayfasi.alis_fatura_frame, 'fatura_listesini_yukle'):
                    self.app.fatura_listesi_sayfasi.alis_fatura_frame.fatura_listesini_yukle()
            self.app.set_status(message)
        else:
            messagebox.showerror("Hata", message, parent=self.app)
                                                
    def secili_siparisi_sil(self):
        selected_item_iid = self.siparis_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir sipariş seçin.", parent=self.app)
            return

        siparis_id = int(selected_item_iid)
        siparis_no = self.siparis_tree.item(selected_item_iid, 'values')[1]

        if messagebox.askyesno("Sipariş Silme Onayı", 
                               f"'{siparis_no}' numaralı siparişi silmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz.", 
                               icon='warning', 
                               parent=self.app):
            success, message = self.db.siparis_sil(siparis_id)
            if success:
                messagebox.showinfo("Başarılı", message, parent=self.app)
                self.siparis_listesini_yukle()
                self.app.set_status(message)
            else:
                messagebox.showerror("Hata", message, parent=self.app)

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.siparis_listesini_yukle()

    def sonraki_sayfa(self):
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0: toplam_sayfa = 1 # Eğer hiç kayıt yoksa, toplam sayfa 1 olarak kabul et.

        if self.mevcut_sayfa < toplam_sayfa:
            self.mevcut_sayfa += 1
            self.siparis_listesini_yukle()

class BaseFaturaListesi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.fatura_tipi = fatura_tipi
        self.pack(expand=True, fill=tk.BOTH)
        self.after_id = None
        self.cari_filter_after_id = None
        self.odeme_turu_filter_after_id = None # Yeni
        self.kasa_banka_filter_after_id = None # Yeni
        
        self.cari_filter_map = {"TÜMÜ": None}
        # Ödeme türleri listesi zaten mevcut
        self.odeme_turu_filter_values = ["TÜMÜ", self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, 
                                         self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, 
                                         self.db.ODEME_TURU_SENET, self.db.ODEME_TURU_ACIK_HESAP, 
                                         self.db.ODEME_TURU_ETKISIZ_FATURA]

        self.kasa_banka_filter_map = {"TÜMÜ": None}
        self.all_cari_display_values_cached = []
        self.all_odeme_turu_display_values_cached = [] # Yeni
        self.all_kasa_banka_display_values_cached = [] # Yeni
        
        self.selected_cari_id_from_filter = None

        if self.fatura_tipi == self.db.FATURA_TIP_SATIS:
            self.fatura_tipleri_filter_options = ["TÜMÜ", self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE]
        elif self.fatura_tipi == self.db.FATURA_TIP_ALIS:
            self.fatura_tipleri_filter_options = ["TÜMÜ", self.db.FATURA_TIP_ALIS, self.db.FATURA_TIP_DEVIR_GIRIS, self.db.FATURA_TIP_ALIS_IADE]
        else:
            self.fatura_tipleri_filter_options = ["TÜMÜ", self.db.FATURA_TIP_ALIS, self.db.FATURA_TIP_SATIS, 
                                                  self.db.FATURA_TIP_DEVIR_GIRIS, self.db.FATURA_TIP_SATIS_IADE, 
                                                  self.db.FATURA_TIP_ALIS_IADE]

        # Filtreleme pop-up'ları ile ilgili değişkenler (Cari, Ödeme Türü, Kasa/Banka)
        self.cari_filter_dropdown_window = None
        self.cari_filter_listbox = None
        self.current_cari_filter_entry_var = tk.StringVar(self)

        self.odeme_turu_filter_dropdown_window = None # Yeni
        self.odeme_turu_filter_listbox = None # Yeni
        self.current_odeme_turu_filter_entry_var = tk.StringVar(self) # Yeni

        self.kasa_banka_filter_dropdown_window = None # Yeni
        self.kasa_banka_filter_listbox = None # Yeni
        self.current_kasa_banka_filter_entry_var = tk.StringVar(self) # Yeni


        self._create_ui_elements()
        self._yukle_filtre_comboboxlari() # Bu metot şimdi tüm display_values_cached'leri dolduracak.
        self.fatura_listesini_yukle()

        self.after(1, self._on_fatura_select)

    def _create_ui_elements(self):
        """Tüm UI elemanlarını (filtreler, butonlar, treeview) oluşturan yardımcı metod."""
        
        # Filtreleme Üst Çerçevesi
        filter_top_frame = ttk.Frame(self)
        filter_top_frame.pack(pady=5, padx=10, fill=tk.X)

        ttk.Label(filter_top_frame, text="Başlangıç Tarihi:").pack(side=tk.LEFT, padx=(0,2))
        self.bas_tarih_entry = ttk.Entry(filter_top_frame, width=12)
        self.bas_tarih_entry.pack(side=tk.LEFT, padx=(0,5))
        self.bas_tarih_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        setup_date_entry(self.app, self.bas_tarih_entry)
        ttk.Button(filter_top_frame, text="🗓️", command=lambda: self._open_date_picker(self.bas_tarih_entry), width=3).pack(side=tk.LEFT, padx=2)


        ttk.Label(filter_top_frame, text="Bitiş Tarihi:").pack(side=tk.LEFT, padx=(0,2))
        self.bit_tarih_entry = ttk.Entry(filter_top_frame, width=12)
        self.bit_tarih_entry.pack(side=tk.LEFT, padx=(0,10))
        self.bit_tarih_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        setup_date_entry(self.app, self.bit_tarih_entry)
        ttk.Button(filter_top_frame, text="🗓️", command=lambda: DatePickerDialog(self.app, self.bit_tarih_entry), width=3).pack(side=tk.LEFT, padx=2)

        # Fatura Tipi Filtresi (Diğerlerinin yanına taşındı ve güncellendi)
        ttk.Label(filter_top_frame, text="Fatura Tipi:").pack(side=tk.LEFT, padx=(10,2))
        self.fatura_tipi_filter_cb = ttk.Combobox(filter_top_frame, width=15, values=self.fatura_tipleri_filter_options, state="readonly")
        self.fatura_tipi_filter_cb.pack(side=tk.LEFT, padx=(0,10))
        self.fatura_tipi_filter_cb.set("TÜMÜ")
        self.fatura_tipi_filter_cb.bind("<<ComboboxSelected>>", lambda event: self.fatura_listesini_yukle())

        ttk.Label(filter_top_frame, text="Ara (F.No/Cari/Misafir/Ürün):").pack(side=tk.LEFT, padx=(10,2))
        self.arama_fatura_entry = ttk.Entry(filter_top_frame, width=30)
        self.arama_fatura_entry.pack(side=tk.LEFT, padx=(0,5), fill=tk.X, expand=True)
        self.arama_fatura_entry.bind("<KeyRelease>", self._delayed_fatura_listesi_yukle)
        
        ttk.Button(filter_top_frame, text="Temizle", command=self._arama_temizle).pack(side=tk.LEFT, padx=(0,10))
        ttk.Button(filter_top_frame, text="Filtrele/Yenile", command=self.fatura_listesini_yukle, style="Accent.TButton").pack(side=tk.LEFT)

        # Diğer Filtreleme Alanları
        filter_bottom_frame = ttk.Frame(self)
        filter_bottom_frame.pack(pady=0, padx=10, fill=tk.X)

        ttk.Label(filter_bottom_frame, text="Cari Filtre:").pack(side=tk.LEFT, padx=(0,2))
        
        self.cari_filter_entry = ttk.Entry(filter_bottom_frame, textvariable=self.current_cari_filter_entry_var, width=25)
        self.cari_filter_entry.pack(side=tk.LEFT, padx=(0,0))
        
        self.cari_filter_entry.bind("<KeyRelease>", lambda e: self._open_filter_dropdown_delayed(e, 'cari')) 
        self.cari_filter_entry.bind("<Button-1>", lambda e: self._open_filter_dropdown(e, 'cari', is_manual_open=True)) 
        
        self.cari_filter_entry.bind("<Return>", lambda e: self._select_first_from_dropdown_and_filter(e, 'cari')) 

        # Açılır menü butonu (Cari)
        self.cari_filter_dropdown_button = ttk.Button(filter_bottom_frame, text="▼", command=lambda: self._open_filter_dropdown(None, 'cari', is_manual_open=True), width=3)
        self.cari_filter_dropdown_button.pack(side=tk.LEFT, padx=(0,10))

        ttk.Label(filter_bottom_frame, text="Ödeme Türü:").pack(side=tk.LEFT, padx=(0,2))
        self.odeme_turu_filter_entry = ttk.Entry(filter_bottom_frame, textvariable=self.current_odeme_turu_filter_entry_var, width=15)
        self.odeme_turu_filter_entry.pack(side=tk.LEFT, padx=(0,0))
        self.odeme_turu_filter_entry.bind("<KeyRelease>", lambda e: self._open_filter_dropdown_delayed(e, 'odeme_turu'))
        self.odeme_turu_filter_entry.bind("<Button-1>", lambda e: self._open_filter_dropdown(e, 'odeme_turu', is_manual_open=True))
        self.odeme_turu_filter_entry.bind("<Return>", lambda e: self._select_first_from_dropdown_and_filter(e, 'odeme_turu'))
        self.odeme_turu_filter_dropdown_button = ttk.Button(filter_bottom_frame, text="▼", command=lambda: self._open_filter_dropdown(None, 'odeme_turu', is_manual_open=True), width=3)
        self.odeme_turu_filter_dropdown_button.pack(side=tk.LEFT, padx=(0,10))

        ttk.Label(filter_bottom_frame, text="Kasa/Banka:").pack(side=tk.LEFT, padx=(0,2))
        self.kasa_banka_filter_entry = ttk.Entry(filter_bottom_frame, textvariable=self.current_kasa_banka_filter_entry_var, width=20)
        self.kasa_banka_filter_entry.pack(side=tk.LEFT, padx=(0,0))
        self.kasa_banka_filter_entry.bind("<KeyRelease>", lambda e: self._open_filter_dropdown_delayed(e, 'kasa_banka'))
        self.kasa_banka_filter_entry.bind("<Button-1>", lambda e: self._open_filter_dropdown(e, 'kasa_banka', is_manual_open=True))
        self.kasa_banka_filter_entry.bind("<Return>", lambda e: self._select_first_from_dropdown_and_filter(e, 'kasa_banka'))
        self.kasa_banka_filter_dropdown_button = ttk.Button(filter_bottom_frame, text="▼", command=lambda: self._open_filter_dropdown(None, 'kasa_banka', is_manual_open=True), width=3)
        self.kasa_banka_filter_dropdown_button.pack(side=tk.LEFT, padx=(0,10))

        # Butonlar Çerçevesi
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=5, padx=10, fill=tk.X)
        self.btn_fatura_detay = ttk.Button(button_frame, text="Seçili Fatura Detayları", command=self.secili_fatura_detay_goster)
        self.btn_fatura_detay.pack(side=tk.LEFT, padx=(0,5))
        self.btn_fatura_pdf_yazdir = ttk.Button(button_frame, text="Seçili Faturayı PDF Yazdır", command=self.secili_faturayi_yazdir)
        self.btn_fatura_pdf_yazdir.pack(side=tk.LEFT, padx=5)
        self.btn_fatura_guncelle = ttk.Button(button_frame, text="Seçili Faturayı Güncelle", command=self.secili_faturayi_guncelle, state=tk.DISABLED)
        self.btn_fatura_guncelle.pack(side=tk.LEFT, padx=5)
        self.btn_fatura_sil = ttk.Button(button_frame, text="Seçili Faturayı Sil", command=self.secili_faturayi_sil, state=tk.DISABLED)
        self.btn_fatura_sil.pack(side=tk.LEFT, padx=5)
        self.btn_iade_faturasi = ttk.Button(button_frame, text="İade Faturası Oluştur", command=self._iade_faturasi_olustur_ui, style="Accent.TButton", state=tk.DISABLED)
        self.btn_iade_faturasi.pack(side=tk.LEFT, padx=5)

        # Sayfalama Çerçevesi
        self.kayit_sayisi_per_sayfa = 20
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0
        pagination_frame = ttk.Frame(self, padding="10")
        pagination_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(pagination_frame, text="Önceki Sayfa", command=self.onceki_sayfa).pack(side=tk.LEFT, padx=5)
        self.sayfa_bilgisi_label = ttk.Label(pagination_frame, text="Sayfa 1 / 1")
        self.sayfa_bilgisi_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(pagination_frame, text="Sonraki Sayfa", command=self.sonraki_sayfa).pack(side=tk.LEFT, padx=5)

        # Fatura Listesi Treeview
        cari_adi_col_text = "Müşteri/Cari Adı" if self.fatura_tipi == self.db.FATURA_TIP_SATIS else "Tedarikçi/Cari Adı"
        cols = ("ID", "Fatura No", "Tarih", cari_adi_col_text, "Fatura Tipi", "Ödeme Türü", "KDV Dahil Top.", "Kasa/Banka", "Vade Tarihi", "Oluşturan", "Son Güncelleyen")
        self.fatura_tree = ttk.Treeview(self, columns=cols, show='headings', selectmode="browse")

        col_defs = [
            ("ID", 40, tk.CENTER, tk.NO),
            ("Fatura No", 120, tk.CENTER, tk.YES), # CENTER yapıldı
            ("Tarih", 85, tk.CENTER, tk.NO),
            (cari_adi_col_text, 200, tk.CENTER, tk.NO), # CENTER yapıldı
            ("Fatura Tipi", 90, tk.CENTER, tk.NO), # CENTER yapıldı
            ("Ödeme Türü", 90, tk.CENTER, tk.NO), # CENTER yapıldı
            ("KDV Dahil Top.", 110, tk.CENTER, tk.NO), # CENTER yapıldı
            ("Kasa/Banka", 125, tk.CENTER, tk.NO), # CENTER yapıldı
            ("Vade Tarihi", 85, tk.CENTER, tk.NO),
            ("Oluşturan", 95, tk.CENTER, tk.NO), # CENTER yapıldı
            ("Son Güncelleyen", 110, tk.CENTER, tk.NO) # CENTER yapıldı
        ]
        for col_name, width, anchor, stretch_opt in col_defs:
            self.fatura_tree.column(col_name, width=width, anchor=anchor, stretch=stretch_opt)
            self.fatura_tree.heading(col_name, text=col_name, command=lambda c=col_name: sort_treeview_column(self.fatura_tree, c, False))

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.fatura_tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.fatura_tree.xview)
        self.fatura_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.fatura_tree.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)
        self.fatura_tree.bind("<Double-1>", self.on_double_click_detay_goster)
        self.fatura_tree.bind("<<TreeviewSelect>>", self._on_fatura_select)

    def _open_cari_filter_dropdown_delayed(self, event=None):
        # Eğer ENTER tuşuna basıldıysa, gecikmeli açma yerine doğrudan seçim işlemini başlat.
        if event and event.keysym in ["Return", "KP_Enter"]:
            print("DEBUG: _open_cari_filter_dropdown_delayed - ENTER algılandı, doğrudan seçim başlatılıyor.")
            self._select_first_from_dropdown_and_filter(event)
            return # Olayı burada sonlandır

        if self.cari_filter_after_id:
            self.after_cancel(self.cari_filter_after_id)
        # Sadece harf veya rakam girildiğinde gecikmeli filtrele, Backspace/Delete için hızlı filtrele
        if event and (event.keysym.isalpha() or event.keysym.isdigit() or event.keysym == "BackSpace" or event.keysym == "Delete"):
            self.cari_filter_after_id = self.after(200, self._open_cari_filter_dropdown, event)
        else: # Diğer tuşlar (Ctrl, Shift vb.) veya olaylar için direkt aç
            self._open_cari_filter_dropdown(event)

    def _open_cari_filter_dropdown(self, event=None):
        print("DEBUG: _open_cari_filter_dropdown çağrıldı.")
        
        # Eğer pencere zaten açıksa, sadece güncelle ve odağı Entry'ye ver.
        if self.cari_filter_dropdown_window and self.cari_filter_dropdown_window.winfo_exists():
            self._update_cari_filter_dropdown()
            self.cari_filter_entry.focus_set()
            return
        
        # Pencereyi Entry'nin altına konumlandır
        self.update_idletasks()
        x = self.cari_filter_entry.winfo_rootx()
        y = self.cari_filter_entry.winfo_rooty() + self.cari_filter_entry.winfo_height()

        self.cari_filter_dropdown_window = tk.Toplevel(self)
        self.cari_filter_dropdown_window.wm_overrideredirect(True) 
        self.cari_filter_dropdown_window.geometry(f"+{x}+{y}")
        self.cari_filter_dropdown_window.transient(self.app)
        self.cari_filter_dropdown_window.attributes('-topmost', True) 

        # Listbox oluştur
        self.cari_filter_listbox = tk.Listbox(self.cari_filter_dropdown_window, height=10, exportselection=0, selectmode=tk.SINGLE)
        self.cari_filter_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar ekle
        scrollbar = ttk.Scrollbar(self.cari_filter_dropdown_window, orient="vertical", command=self.cari_filter_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.cari_filter_listbox.config(yscrollcommand=scrollbar.set)

        # Olay bağlamaları
        self.cari_filter_listbox.bind("<<ListboxSelect>>", self._select_cari_from_dropdown) 
        self.cari_filter_listbox.bind("<Double-Button-1>", self._select_cari_from_dropdown) 
        self.cari_filter_listbox.bind("<Return>", self._select_cari_from_dropdown) 
        
        # Listbox'taki KeyRelease olaylarını Entry'ye yönlendir
        self.cari_filter_listbox.bind("<KeyRelease>", self._relay_listbox_key_to_entry)

        # Pencere odağı kaybedince kapatma binding'i.
        self.cari_filter_dropdown_window.bind("<FocusOut>", self._close_cari_filter_dropdown_on_focus_out)
        # Mouse dışına tıklamada kapatma (Button-1 olayını yakalarız)
        self.cari_filter_dropdown_window.bind("<Button-1>", self._close_cari_filter_dropdown_on_click_outside)

        self._update_cari_filter_dropdown() # Listeyi ilk kez doldur
        
        # Entry'ye tekrar odaklanmayı zorla
        self.cari_filter_entry.focus_set() 
        print("DEBUG: Cari filtre dropdown penceresi açıldı ve Entry'ye odaklandı.")

    def _relay_listbox_key_to_entry(self, event, filter_type=None):
        entry_widget = getattr(self, f"{filter_type}_filter_entry")
        entry_var = getattr(self, f"current_{filter_type}_filter_entry_var")

        entry_widget.focus_set()
        
        if event.keysym in ["Return", "KP_Enter"]:
            return 

        if event.keysym == "BackSpace":
            current_text = entry_var.get()
            entry_var.set(current_text[:-1])
        elif event.char:
            entry_var.set(entry_var.get() + event.char)
        
        getattr(self, f"_open_filter_dropdown_delayed")(event, filter_type) 
        return "break"
        
    def _update_cari_filter_dropdown(self):
        print("DEBUG: _update_cari_filter_dropdown çağrıldı.")
        if not (self.cari_filter_listbox and self.cari_filter_listbox.winfo_exists()):
            return

        search_term = self.current_cari_filter_entry_var.get().lower()
        self.cari_filter_listbox.delete(0, tk.END)

        items_to_display = []
        
        # Arama terimi boşsa veya "tümü" ise, "TÜMÜ" seçeneğini listenin başına ekle.
        if search_term == "" or search_term == "tümü":
            items_to_display.append("TÜMÜ")
        
        # Filtrelenmiş diğer öğeleri ekle
        for item in self.all_cari_display_values_cached:
            if search_term == "" or search_term == "tümü" or search_term in item.lower():
                # "TÜMÜ" seçeneği zaten eklendiyse ve bu öğe "tümü" ise tekrar ekleme.
                if item.lower() != "tümü": 
                    items_to_display.append(item)
        
        # Listeyi benzersiz hale getir (eğer "TÜMÜ" başka bir carinin adında geçiyorsa sorun yaşamamak için)
        # Sadece "TÜMÜ" her zaman başta olmalı. Diğerleri sıralı.
        unique_items_without_tumu = sorted(list(set(items_to_display) - {"TÜMÜ"}))
        final_items_to_display = []
        if "TÜMÜ" in items_to_display:
            final_items_to_display.append("TÜMÜ")
        final_items_to_display.extend(unique_items_without_tumu)

        for item in final_items_to_display:
            self.cari_filter_listbox.insert(tk.END, item)
        
        # Otomatik seçimi ve odaklanmayı güncelleyelim.
        # Eğer Entry'deki metin "TÜMÜ" ise, Listbox'ta "TÜMÜ"yü seçili yap.
        if self.current_cari_filter_entry_var.get() == "TÜMÜ":
            for i in range(self.cari_filter_listbox.size()):
                if self.cari_filter_listbox.get(i) == "TÜMÜ":
                    self.cari_filter_listbox.selection_set(i)
                    self.cari_filter_listbox.activate(i)
                    self.cari_filter_listbox.see(i) 
                    break
        elif search_term != "": # Eğer arama yapılıyorsa ve tam eşleşen bir öğe varsa onu seç.
            found_exact_match = False
            for i in range(self.cari_filter_listbox.size()):
                if self.cari_filter_listbox.get(i).lower() == search_term:
                    self.cari_filter_listbox.selection_set(i)
                    self.cari_filter_listbox.activate(i)
                    self.cari_filter_listbox.see(i)
                    found_exact_match = True
                    break
            if not found_exact_match and self.cari_filter_listbox.size() > 0:
                # Eğer tam eşleşme yoksa ama liste doluysa ilkini seç (kullanıcıya kolaylık)
                self.cari_filter_listbox.selection_set(0) 
                self.cari_filter_listbox.activate(0)
                self.cari_filter_listbox.see(0)

        # Listbox'a odaklan (klavye girişi için) - Bu, klavye olaylarını Listbox'a yönlendirir.
        # self.cari_filter_listbox.focus_set() # Bu satırı kaldıracağız. Klavye Entry'de kalmalı.

        self.cari_filter_dropdown_window.lift()
        print(f"DEBUG: Dropdown güncellendi. {self.cari_filter_listbox.size()} öğe.")

    def _select_cari_from_dropdown(self, event=None):
        print("DEBUG: _select_cari_from_dropdown çağrıldı.")
        if not self.cari_filter_listbox.curselection():
            print("DEBUG: Hiçbir şey seçili değil.")
            # Eğer Enter'a basıldıysa ve hiçbir şey seçili değilse,
            # sadece mevcut metinle filtrele ve menüyü kapat.
            if event and event.keysym in ["Return", "KP_Enter"]:
                self.fatura_listesini_yukle()
                self._close_cari_filter_dropdown()
                return "break" # Olayın yayılmasını durdur

            return
        
        selected_index = self.cari_filter_listbox.curselection()[0]
        selected_value = self.cari_filter_listbox.get(selected_index)
        
        self.current_cari_filter_entry_var.set(selected_value) # Entry'yi güncelle
        
        # Entry'ye odaklan ve tüm metni seç
        self.cari_filter_entry.focus_set()
        self.cari_filter_entry.selection_range(0, tk.END)

        self.fatura_listesini_yukle() # Filtrelemeyi tetikle
        self._close_cari_filter_dropdown() # Açılır menüyü kapat
        print(f"DEBUG: '{selected_value}' seçildi ve kapatıldı.")

        if event and event.keysym in ["Return", "KP_Enter"]:
            return "break" # ENTER olayının yayılmasını durdur
        return # Normal dönüş
        
    def _select_first_from_dropdown_and_filter(self, event=None, filter_type=None):        
        listbox_widget = getattr(self, f"{filter_type}_filter_listbox", None) # None olarak başlat
        
        if listbox_widget and listbox_widget.winfo_exists() and listbox_widget.size() > 0:
            listbox_widget.selection_set(0)
            listbox_widget.activate(0)
            self._select_from_dropdown(event, filter_type) # <<< event'i de geçirdik >>>
        else:
            self.fatura_listesini_yukle()
            self._close_filter_dropdown(filter_type)

    def _open_filter_dropdown_delayed(self, event=None, filter_type=None):
        # Eğer ENTER tuşuna basıldıysa, gecikmeli açma yerine doğrudan seçim işlemini başlat.
        if event and event.keysym in ["Return", "KP_Enter"]:
            self._select_first_from_dropdown_and_filter(event, filter_type)
            return # Olayı burada sonlandır

        after_id_var = getattr(self, f"{filter_type}_filter_after_id")
        if after_id_var:
            self.after_cancel(after_id_var)
        setattr(self, f"{filter_type}_filter_after_id", self.after(200, self._open_filter_dropdown, event, filter_type, True))

    # GENEL METOT: Açılır filtre menüsünü açar/günceller
    def _open_filter_dropdown(self, event=None, filter_type=None, is_manual_open=False):
        
        dropdown_window = getattr(self, f"{filter_type}_filter_dropdown_window")
        listbox_widget = getattr(self, f"{filter_type}_filter_listbox")
        entry_widget = getattr(self, f"{filter_type}_filter_entry")

        # Eğer pencere zaten açıksa, sadece güncelle ve odağı Entry'ye ver.
        if dropdown_window and dropdown_window.winfo_exists():
            self._update_filter_dropdown(filter_type)
            entry_widget.focus_set()
            return
        
        # Sadece manuel açma (tıklama veya gecikmeli klavye olayı) durumunda pencereyi aç.
        if not is_manual_open:
            return

        # Pencereyi Entry'nin altına konumlandır
        self.update_idletasks() 
        x = entry_widget.winfo_rootx()
        y = entry_widget.winfo_rooty() + entry_widget.winfo_height()

        dropdown_window = tk.Toplevel(self)
        setattr(self, f"{filter_type}_filter_dropdown_window", dropdown_window) # Değişkeni set et
        dropdown_window.wm_overrideredirect(True) 
        dropdown_window.geometry(f"+{x}+{y}")
        dropdown_window.transient(self.app)
        dropdown_window.attributes('-topmost', True) 

        # Listbox oluştur
        listbox_widget = tk.Listbox(dropdown_window, height=10, exportselection=0, selectmode=tk.SINGLE)
        setattr(self, f"{filter_type}_filter_listbox", listbox_widget) # Değişkeni set et
        listbox_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar ekle
        scrollbar = ttk.Scrollbar(dropdown_window, orient="vertical", command=listbox_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox_widget.config(yscrollcommand=scrollbar.set)

        # Olay bağlamaları
        listbox_widget.bind("<<ListboxSelect>>", lambda e: self._select_from_dropdown(e, filter_type)) 
        listbox_widget.bind("<Double-Button-1>", lambda e: self._select_from_dropdown(e, filter_type)) 
        listbox_widget.bind("<Return>", lambda e: self._select_from_dropdown(e, filter_type)) 
        
        # Listbox'taki KeyRelease olaylarını Entry'ye yönlendir
        listbox_widget.bind("<KeyRelease>", lambda e: self._relay_listbox_key_to_entry(e, filter_type))

        # Kapanma olaylarını _handle_dropdown_close_events'e bağla
        dropdown_window.bind("<FocusOut>", self._handle_dropdown_close_events)
        dropdown_window.bind("<Button-1>", self._handle_dropdown_close_events)

        self._update_filter_dropdown(filter_type) # Listeyi ilk kez doldur
        
        entry_widget.focus_set() 

    def _update_filter_dropdown(self, filter_type=None):
        dropdown_window = getattr(self, f"{filter_type}_filter_dropdown_window")
        listbox_widget = getattr(self, f"{filter_type}_filter_listbox")
        entry_var = getattr(self, f"current_{filter_type}_filter_entry_var")
        all_values_cached = getattr(self, f"all_{filter_type}_display_values_cached")

        if not (listbox_widget and listbox_widget.winfo_exists()):
            return

        search_term = entry_var.get().lower()
        listbox_widget.delete(0, tk.END)

        items_to_display = []
        
        # "TÜMÜ" seçeneğinin eklenmesi mantığı (HER ZAMAN İÇİN)
        # Sadece eğer arama terimi "tümü" değilse veya "tümü" olarak aratılıyorsa "TÜMÜ"yü ekle
        if search_term == "" or search_term == "tümü":
            items_to_display.append("TÜMÜ")
        
        # Filtrelenmiş diğer öğeleri ekle
        for item in all_values_cached:
            if search_term == "" or search_term == "tümü" or search_term in item.lower():
                # "TÜMÜ" seçeneği zaten eklendiyse ve bu öğe "tümü" ise tekrar ekleme.
                if item.lower() != "tümü": 
                    items_to_display.append(item)
        
        # Listeyi benzersiz hale getir (eğer aynı öğeler tekrar eklenmişse)
        # VE "TÜMÜ" her zaman başta olacak şekilde sırala
        unique_items_without_tumu = sorted(list(set(items_to_display) - {"TÜMÜ"}))
        final_items_to_display = []
        if "TÜMÜ" in items_to_display:
            final_items_to_display.append("TÜMÜ")
        final_items_to_display.extend(unique_items_without_tumu)

        for item in final_items_to_display:
            listbox_widget.insert(tk.END, item)
        
        # Otomatik seçimi ve odaklanmayı güncelleyelim.
        # Eğer Entry'deki metin "TÜMÜ" ise, Listbox'ta "TÜMÜ"yü seçili yap.
        if entry_var.get() == "TÜMÜ":
            for i in range(listbox_widget.size()):
                if listbox_widget.get(i) == "TÜMÜ":
                    listbox_widget.selection_set(i)
                    listbox_widget.activate(i)
                    listbox_widget.see(i) 
                    break
        elif search_term != "": 
            found_exact_match = False
            for i in range(listbox_widget.size()):
                if listbox_widget.get(i).lower() == search_term:
                    listbox_widget.selection_set(i)
                    listbox_widget.activate(i)
                    listbox_widget.see(i)
                    found_exact_match = True
                    break
            if not found_exact_match and listbox_widget.size() > 0:
                listbox_widget.selection_set(0) 
                listbox_widget.activate(0)
                listbox_widget.see(0)

        if dropdown_window and dropdown_window.winfo_exists():
            dropdown_window.lift()
            
    def _select_from_dropdown(self, event=None, filter_type=None):
        print(f"DEBUG: _select_from_dropdown çağrıldı for {filter_type}.")
        
        listbox_widget = getattr(self, f"{filter_type}_filter_listbox")
        entry_var = getattr(self, f"current_{filter_type}_filter_entry_var")
        entry_widget = getattr(self, f"{filter_type}_filter_entry")
        
        if not listbox_widget.curselection():
            print("DEBUG: Hiçbir şey seçili değil.")
            # Eğer Enter'a basıldıysa ve hiçbir şey seçili değilse,
            # sadece mevcut metinle filtrele ve menüyü kapat.
            if event and event.keysym in ["Return", "KP_Enter"]:
                self.fatura_listesini_yukle()
                self._close_filter_dropdown(filter_type)
                return "break" # Olayın yayılmasını durdur

            return
        
        selected_index = listbox_widget.curselection()[0]
        selected_value = listbox_widget.get(selected_index)
        
        entry_var.set(selected_value) # Entry'yi güncelle
        
        entry_widget.focus_set()
        entry_widget.selection_range(0, tk.END)

        self.fatura_listesini_yukle() # Filtrelemeyi tetikle
        self._close_filter_dropdown(filter_type) # Açılır menüyü kapat

        if event and event.keysym in ["Return", "KP_Enter"]:
            return "break" # ENTER olayının yayılmasını durdur
        return # Normal dönüş
            
    def _close_filter_dropdown(self, filter_type=None):       
        dropdown_window = getattr(self, f"{filter_type}_filter_dropdown_window")
        entry_widget = getattr(self, f"{filter_type}_filter_entry")

        if dropdown_window and dropdown_window.winfo_exists():
            dropdown_window.destroy()
            setattr(self, f"{filter_type}_filter_dropdown_window", None)
            setattr(self, f"{filter_type}_filter_listbox", None)
            
            entry_widget.focus_set() 
            entry_widget.selection_range(0, tk.END)
                
    def _close_cari_filter_dropdown(self):
        print("DEBUG: _close_cari_filter_dropdown çağrıldı.")
        if self.cari_filter_dropdown_window and self.cari_filter_dropdown_window.winfo_exists():
            # attributes('-topmost', False) çağrısını burada yapmaya gerek yok, destroy zaten temizler.
            self.cari_filter_dropdown_window.destroy()
            self.cari_filter_dropdown_window = None
            self.cari_filter_listbox = None
            
            # Kapatınca Entry'ye geri odaklan ve mevcut metni seç
            self.cari_filter_entry.focus_set() 
            self.cari_filter_entry.selection_range(0, tk.END)
            
            print("DEBUG: Dropdown kapatıldı.")

    def _filter_cari_combobox_delayed(self, event=None):
        if self.cari_filter_after_id:
            self.after_cancel(self.cari_filter_after_id)
        self.cari_filter_after_id = self.after(300, self._filter_cari_combobox_execute) # 300ms gecikme

    def _filter_cari_combobox_execute(self):
        search_term = self.cari_filter_cb.get().lower()
        if search_term == "":
            self.cari_filter_cb['values'] = ["TÜMÜ"] + self.all_cari_display_values_cached # "TÜMÜ" seçeneğini de ekle
            self.cari_filter_cb.current(0) # "TÜMÜ" seçili gelsin
        else:
            filtered_values = [
                item for item in self.all_cari_display_values_cached
                if search_term in item.lower()
            ]
            self.cari_filter_cb['values'] = filtered_values
            
            # Eğer filtreleme sonucunda tam bir eşleşme varsa veya sadece bir sonuç kaldıysa otomatik seç
            exact_match_found = False
            for val in filtered_values:
                if val.lower() == search_term:
                    self.cari_filter_cb.set(val)
                    exact_match_found = True
                    break
            
            if not exact_match_found and len(filtered_values) > 0:
                # Eğer tam eşleşme yoksa ve sonuçlar varsa, ilkini seçili bırakın
                self.cari_filter_cb.set(filtered_values[0])
            elif not exact_match_found and len(filtered_values) == 0:
                # Hiç sonuç yoksa, combobox'ı boşaltın ve uyarı verin.
                self.cari_filter_cb.set("")
                self.cari_filter_cb['values'] = [] # Açılır listeyi boşalt
                # messagebox.showwarning("Cari Bulunamadı", "Belirtilen kritere uygun cari bulunamadı.", parent=self.app) # Bu mesajı her filtrelemede göstermeyelim, çok rahatsız edici olabilir.
        self.fatura_listesini_yukle() # Listeyi güncelleyeceğiz.

    def _on_fatura_select(self, event=None):
        # Bu metodun en başında, her zaman butonları sıfırlayarak güvenli bir başlangıç yapalım.
        self._reset_button_states() # Tüm butonları varsayılan (pasif) duruma getir

        selected_item_iid = self.fatura_tree.focus()
        print(f"DEBUG: _on_fatura_select çağrıldı. Seçilen IID: {selected_item_iid}")

        if selected_item_iid:
            fatura_detay = self.db.fatura_getir_by_id(selected_item_iid)
            print(f"DEBUG: fatura_detay: {fatura_detay}")

            if fatura_detay:
                self.secili_fatura_id = fatura_detay['id']
                self.secili_fatura_no = fatura_detay['fatura_no']
                self.secili_fatura_tipi = fatura_detay['tip'] # Doğrudan detaydan al

                print(f"DEBUG: Seçilen Fatura ID: {self.secili_fatura_id}, Tip: {self.secili_fatura_tipi}, No: {self.secili_fatura_no}")

                # Detay ve Yazdır butonları her zaman aktif olabilir (fatura seçiliyse)
                if hasattr(self, 'btn_fatura_detay') and self.btn_fatura_detay.winfo_exists():
                    self.btn_fatura_detay.config(state=tk.NORMAL)
                if hasattr(self, 'btn_fatura_pdf_yazdir') and self.btn_fatura_pdf_yazdir.winfo_exists():
                    self.btn_fatura_pdf_yazdir.config(state=tk.NORMAL)


                # Güncelle butonu sadece SATIŞ, ALIŞ, SATIŞ İADE, ALIŞ İADE için aktif olsun
                if hasattr(self, 'btn_fatura_guncelle') and self.btn_fatura_guncelle.winfo_exists():
                    if self.secili_fatura_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_ALIS, 
                                                self.db.FATURA_TIP_SATIS_IADE, self.db.FATURA_TIP_ALIS_IADE]:
                        self.btn_fatura_guncelle.config(state=tk.NORMAL)
                    else:
                        self.btn_fatura_guncelle.config(state=tk.DISABLED)

                if hasattr(self, 'btn_fatura_sil') and self.btn_fatura_sil.winfo_exists():
                    self.btn_fatura_sil.config(state=tk.NORMAL)

                # İade Faturası Oluştur butonu mantığı
                if hasattr(self, 'btn_iade_faturasi') and self.btn_iade_faturasi.winfo_exists():
                    # Sadece orijinal SATIŞ veya ALIŞ faturaları için ve daha önce iade yapılmamışsa aktif
                    # fatura_detay['orijinal_fatura_id'] is None kontrolü, bu faturanın zaten bir iade faturası olmadığını teyit eder.
                    if fatura_detay['orijinal_fatura_id'] is None and self.secili_fatura_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_ALIS]:
                        # Bu faturaya ait bir iade faturası zaten var mı diye veritabanında kontrol et.
                        # Bu kontrolü doğrudan burada yapmak yerine, db_manager'a bir metod ekleyebiliriz.
                        self.db.c.execute("SELECT id FROM faturalar WHERE orijinal_fatura_id = ?", (self.secili_fatura_id,))
                        existing_iade_fatura = self.db.c.fetchone()
                        if existing_iade_fatura:
                            self.btn_iade_faturasi.config(state=tk.DISABLED) # Zaten iadesi varsa pasif yap
                            logging.debug(f"Fatura ID {self.secili_fatura_id} için zaten iade mevcut, buton pasif.")
                        else:
                            self.btn_iade_faturasi.config(state=tk.NORMAL)
                    else:
                        self.btn_iade_faturasi.config(state=tk.DISABLED)

            else:
                print("DEBUG: Fatura detayı bulunamadı, butonlar pasif kaldı.")
                # _reset_button_states zaten çağrıldı, başka bir şey yapmaya gerek yok.
        else:
            print("DEBUG: Hiçbir fatura seçili değil, tüm butonlar pasif.")
            # _reset_button_states zaten çağrıldı.

    def _reset_button_states(self):
        # Tüm butonları pasif hale getir, eğer tanımlanmış ve varsa.
        # Bu metod, butonlar henüz tanımlanmadan da çağrılabilir, bu yüzden hasattr kontrolü önemli.
        if hasattr(self, 'btn_fatura_detay') and self.btn_fatura_detay.winfo_exists():
            self.btn_fatura_detay.config(state=tk.DISABLED)
        if hasattr(self, 'btn_fatura_pdf_yazdir') and self.btn_fatura_pdf_yazdir.winfo_exists():
            self.btn_fatura_pdf_yazdir.config(state=tk.DISABLED)
        if hasattr(self, 'btn_fatura_guncelle') and self.btn_fatura_guncelle.winfo_exists():
            self.btn_fatura_guncelle.config(state=tk.DISABLED)
        if hasattr(self, 'btn_fatura_sil') and self.btn_fatura_sil.winfo_exists():
            self.btn_fatura_sil.config(state=tk.DISABLED)
        if hasattr(self, 'btn_iade_faturasi') and self.btn_iade_faturasi.winfo_exists():
            self.btn_iade_faturasi.config(state=tk.DISABLED)

        self.secili_fatura_id = None
        self.secili_fatura_tipi = None
        self.secili_fatura_no = None

    def _iade_faturasi_olustur_ui(self):
        selected_item_iid = self.fatura_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen iade faturası oluşturmak için bir fatura seçin.", parent=self.app)
            return

        original_fatura_id = int(selected_item_iid)
        original_fatura_data = self.db.fatura_getir_by_id(original_fatura_id)
        if not original_fatura_data:
            messagebox.showerror("Hata", "Orijinal fatura bilgisi veritabanında bulunamadı.", parent=self.app)
            return

        original_fatura_no = original_fatura_data['fatura_no']
        original_fatura_tipi = original_fatura_data['tip']

        if original_fatura_tipi not in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_ALIS]:
            messagebox.showwarning("Uyarı", "Sadece 'SATIŞ' veya 'ALIŞ' faturaları için iade faturası oluşturulabilir.", parent=self.app)
            return

        self.db.c.execute("SELECT fatura_no FROM faturalar WHERE orijinal_fatura_id = ?", (original_fatura_id,))
        existing_iade = self.db.c.fetchone()
        if existing_iade:
            messagebox.showwarning("Uyarı", f"Bu faturaya ait '{existing_iade['fatura_no']}' numaralı iade faturası zaten mevcut.", parent=self.app)
            return

        original_kalemler_ui_format = []
        original_kalemler_db = self.db.fatura_detay_al(original_fatura_id)
        for k_db in original_kalemler_db:
            urun_id = k_db['urun_id']
            urun_adi = k_db['urun_adi']
            miktar = k_db['miktar']
            birim_fiyat_kdv_haric = k_db['birim_fiyat']
            kdv_orani = k_db['kdv_orani']
            iskonto_yuzde_1 = k_db['iskonto_yuzde_1']
            iskonto_yuzde_2 = k_db['iskonto_yuzde_2']
            alis_fiyati_fatura_aninda = k_db['alis_fiyati_fatura_aninda']

            iskonto_tipi_db = k_db['iskonto_tipi'] if 'iskonto_tipi' in k_db.keys() else 'YOK'
            iskonto_degeri_db = k_db['iskonto_degeri'] if 'iskonto_degeri' in k_db.keys() else 0.0

            orijinal_bf_dahil = birim_fiyat_kdv_haric * (1 + kdv_orani / 100)
            fiyat_isk1_sonrasi = orijinal_bf_dahil * (1 - iskonto_yuzde_1 / 100)
            iskontolu_bf_dahil_hesaplanan = fiyat_isk1_sonrasi * (1 - iskonto_yuzde_2 / 100)
            iskontolu_bf_haric_hesaplanan = iskontolu_bf_dahil_hesaplanan / (1 + kdv_orani / 100) if kdv_orani > 0 else iskontolu_bf_dahil_hesaplanan
            kdv_tutari_hesaplanan = (iskontolu_bf_dahil_hesaplanan - iskontolu_bf_haric_hesaplanan) * miktar
            kalem_toplam_kdv_haric_hesaplanan = iskontolu_bf_haric_hesaplanan * miktar
            kalem_toplam_kdv_dahil_hesaplanan = iskontolu_bf_dahil_hesaplanan * miktar

            kalem_tuple = (
                urun_id, urun_adi, miktar, 
                birim_fiyat_kdv_haric, kdv_orani, 
                kdv_tutari_hesaplanan, kalem_toplam_kdv_haric_hesaplanan, kalem_toplam_kdv_dahil_hesaplanan,
                alis_fiyati_fatura_aninda, kdv_orani, 
                iskonto_yuzde_1, iskonto_yuzde_2, 
                iskonto_tipi_db, iskonto_degeri_db,
                iskontolu_bf_dahil_hesaplanan
            )
            original_kalemler_ui_format.append(kalem_tuple)

        cari_tip_for_db_query = self.db.CARI_TIP_MUSTERI if original_fatura_tipi == self.db.FATURA_TIP_SATIS else self.db.CARI_TIP_TEDARIKCI
        cari_info = self.db.musteri_getir_by_id(original_fatura_data['cari_id']) if cari_tip_for_db_query == self.db.CARI_TIP_MUSTERI else self.db.tedarikci_getir_by_id(original_fatura_data['cari_id'])
        cari_adi_for_initial_data = cari_info['ad'] if cari_info else 'Bilinmeyen Cari'

        unique_suffix = datetime.now().strftime('%H%M%S')
        generated_iade_fatura_no = f"IADE-{original_fatura_no}-{unique_suffix}"

        iade_fatura_tipi_for_ui = self.db.FATURA_TIP_SATIS_IADE if original_fatura_tipi == self.db.FATURA_TIP_SATIS else self.db.FATURA_TIP_ALIS_IADE

        from pencereler import FaturaPenceresi
        FaturaPenceresi(
            self.app, self.db, self.app,
            fatura_tipi=iade_fatura_tipi_for_ui,
            yenile_callback=self.fatura_listesini_yukle,
            initial_data={
                'iade_modu': True,
                'orijinal_fatura_id': original_fatura_id,
                'fatura_no': generated_iade_fatura_no,
                'tarih': datetime.now().strftime('%Y-%m-%d'),
                'cari_id': original_fatura_data['cari_id'],
                'cari_tip': cari_tip_for_db_query,
                'cari_adi': cari_adi_for_initial_data,
                'misafir_adi': original_fatura_data['misafir_adi'],
                'fatura_notlari': f"Orijinal Fatura: {original_fatura_no}.",
                'odeme_turu': original_fatura_data['odeme_turu'],
                'kasa_banka_id': original_fatura_data['kasa_banka_id'],
                'vade_tarihi': original_fatura_data['vade_tarihi'],
                'genel_iskonto_tipi': original_fatura_data['genel_iskonto_tipi'],
                'genel_iskonto_degeri': original_fatura_data['genel_iskonto_degeri'],
                'fatura_kalemleri_ui': original_kalemler_ui_format
            }
        )
        self.app.set_status(f"'{original_fatura_no}' için iade faturası oluşturma başlatıldı.")

    def _convert_db_kalemleri_to_ui_format(self, db_kalemleri, for_iade=False):
        """
        Veritabanından çekilen fatura kalemlerini (sqlite3.Row objeleri)
        UI'da kullanılan `fatura_kalemleri_ui` formatına dönüştürür.
        `for_iade=True` ise, fiyatlandırma mantığını iade için uygun hale getirir.
        """
        converted_kalemler = []
        for k_db in db_kalemleri:
            # Hesaplamaları iade mantığına uygun hale getir
            urun_id = k_db['urun_id']
            urun_adi = k_db['urun_adi']
            miktar = k_db['miktar']
            birim_fiyat_db = k_db['birim_fiyat'] # KDV Hariç
            kdv_orani_db = k_db['kdv_orani']
            iskonto_yuzde_1_db = k_db['iskonto_yuzde_1']
            iskonto_yuzde_2_db = k_db['iskonto_yuzde_2']
            alis_fiyati_fatura_aninda_db = k_db['alis_fiyati_fatura_aninda']
            iskonto_tipi_db = k_db['iskonto_tipi']
            iskonto_degeri_db = k_db['iskonto_degeri']

            # İskontolu Birim Fiyat (KDV Dahil) - Fatura'daki haliyle
            iskontolu_birim_fiyat_kdv_dahil = (k_db['kalem_toplam_kdv_dahil'] / k_db['miktar']) if k_db['miktar'] != 0 else 0.0

            converted_kalemler.append((
                urun_id, urun_adi, miktar, 
                birim_fiyat_db, # KDV Hariç Orijinal
                kdv_orani_db, 
                k_db['kdv_tutari'], # KDV Tutarı
                k_db['kalem_toplam_kdv_haric'], # Kalem Toplam KDV Hariç
                k_db['kalem_toplam_kdv_dahil'], # Kalem Toplam KDV Dahil
                alis_fiyati_fatura_aninda_db, # Fatura Anı Alış Fiyatı (KDV Dahil)
                kdv_orani_db, # KDV Oranı (Fatura Anı)
                iskonto_yuzde_1_db, iskonto_yuzde_2_db,
                iskonto_tipi_db, iskonto_degeri_db,
                iskontolu_birim_fiyat_kdv_dahil # İskontolu Birim Fiyat KDV Dahil
            ))
        return converted_kalemler

    def _open_date_picker(self, target_entry):
        """Bir Entry widget'ı için tarih seçici penceresi açar."""
        DatePickerDialog(self.app, target_entry)        

    def _delayed_fatura_listesi_yukle(self, event):
        if self.after_id:
            self.after_cancel(self.after_id)
        self.after_id = self.after(300, self.fatura_listesini_yukle)

    def _yukle_filtre_comboboxlari(self):
        # Cari filtre combobox'ını yükle (fatura tipine göre müşteri veya tedarikçi)
        cari_display_values_raw = []
        self.cari_filter_map = {"TÜMÜ": None} # Map'i sıfırla

        if self.fatura_tipi == 'SATIŞ':
            musteriler = self.db.musteri_listesi_al(perakende_haric=False) 
            for m in musteriler:
                display_text = f"{m[2]} (Kod: {m[1]})"
                self.cari_filter_map[display_text] = str(m[0]) 
                cari_display_values_raw.append(display_text)
        else: # 'ALIŞ'
            tedarikciler = self.db.tedarikci_listesi_al() 
            for t in tedarikciler:
                display_text = f"{t[2]} (Kod: {t[1]})"
                self.cari_filter_map[display_text] = str(t[0]) 
                cari_display_values_raw.append(display_text)

        self.all_cari_display_values_cached = sorted(cari_display_values_raw)
        self.current_cari_filter_entry_var.set("TÜMÜ") 

        # all_odeme_turu_display_values_cached zaten BaseFaturaListesi'nin __init__ metodunda
        # self.odeme_turu_filter_values olarak tanımlanmış durumda, sadece TÜMÜ hariç olanları alalım.
        self.all_odeme_turu_display_values_cached = sorted([val for val in self.odeme_turu_filter_values if val != "TÜMÜ"])
        self.current_odeme_turu_filter_entry_var.set("TÜMÜ")

        kasalar_bankalar = self.db.kasa_banka_listesi_al()
        kasa_banka_display_values_raw = []
        self.kasa_banka_filter_map = {"TÜMÜ": None} # Map'i sıfırla

        for h in kasalar_bankalar:
            display_text = f"{h[1]} ({h[5]})"
            if h[5] == "BANKA" and h[7]: display_text += f" - {h[7]}"
            if h[5] == "BANKA" and h[2]: display_text += f" ({h[2]})"
            self.kasa_banka_filter_map[display_text] = h[0]
            kasa_banka_display_values_raw.append(display_text)

        self.all_kasa_banka_display_values_cached = sorted(kasa_banka_display_values_raw)
        self.current_kasa_banka_filter_entry_var.set("TÜMÜ")

    def _arama_temizle(self):
        self.arama_fatura_entry.delete(0, tk.END)
        self.fatura_listesini_yukle()


    def fatura_listesini_yukle(self):
        for i in self.fatura_tree.get_children():
            self.fatura_tree.delete(i)
        
        bas_t = self.bas_tarih_entry.get()
        bit_t = self.bit_tarih_entry.get()
        
        arama_terimi = self.arama_fatura_entry.get().strip()

        selected_cari_filter_text = self.current_cari_filter_entry_var.get()
        cari_id_filter_val = self.cari_filter_map.get(selected_cari_filter_text, None)
        
        if selected_cari_filter_text == "TÜMÜ":
            cari_id_filter_val = None

        selected_odeme_turu_filter_text = self.current_odeme_turu_filter_entry_var.get()
        odeme_turu_filter_val = selected_odeme_turu_filter_text if selected_odeme_turu_filter_text != "TÜMÜ" else None

        selected_kasa_banka_filter_text = self.current_kasa_banka_filter_entry_var.get()
        kasa_banka_id_filter_val = self.kasa_banka_filter_map.get(selected_kasa_banka_filter_text, None)
        if selected_kasa_banka_filter_text == "TÜMÜ":
            kasa_banka_id_filter_val = None

        try:
            if bas_t: datetime.strptime(bas_t, '%Y-%m-%d')
            if bit_t: datetime.strptime(bit_t, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Tarih Formatı Hatası", "Tarih formatı (YYYY-AA-GG) olmalıdır (örn: 2023-12-31).", parent=self.app)
            return
        
        offset = (self.mevcut_sayfa - 1) * self.kayit_sayisi_per_sayfa
        limit = self.kayit_sayisi_per_sayfa       
        
        selected_fatura_tipi_filter = self.fatura_tipi_filter_cb.get()
        tip_filter_for_db = None
        if selected_fatura_tipi_filter == "TÜMÜ":
            if self.fatura_tipi == 'SATIŞ':
                tip_filter_for_db = ['SATIŞ', 'SATIŞ İADE']
            elif self.fatura_tipi == 'ALIŞ':
                tip_filter_for_db = ['ALIŞ', 'ALIŞ İADE']
            else:
                tip_filter_for_db = ["ALIŞ", "SATIŞ", "DEVİR_GİRİŞ", "SATIŞ İADE", "ALIŞ İADE"]
        else:
            tip_filter_for_db = selected_fatura_tipi_filter

        faturalar = self.db.fatura_listele_urun_ad_dahil(
            tip=tip_filter_for_db,
            baslangic_tarih=bas_t if bas_t else None, 
            bitis_tarih=bit_t if bit_t else None, 
            arama_terimi=arama_terimi if arama_terimi else None,
            cari_id_filter=cari_id_filter_val, 
            odeme_turu_filter=odeme_turu_filter_val,
            kasa_banka_id_filter=kasa_banka_id_filter_val,
            limit=limit,
            offset=offset
        )
        
        for item in faturalar: 
            fatura_id = item['id']
            fatura_no = item['fatura_no']
            tarih_obj = item['tarih']
            fatura_tip = item['tip']
            cari_adi = item['cari_adi']
            toplam_kdv_dahil = item['toplam_kdv_dahil']
            odeme_turu = item['odeme_turu']
            kasa_banka_adi = item['kasa_banka_adi']
            vade_tarihi_obj = item['vade_tarihi']
            genel_iskonto_degeri = item['genel_iskonto_degeri']
            olusturan_kul_adi = item['olusturan_kul_adi']
            guncelleyen_kul_adi = item['guncelleyen_kul_adi']

            formatted_tarih = ""
            if isinstance(tarih_obj, (date, datetime)):
                formatted_tarih = tarih_obj.strftime('%d.%m.%Y')
            else:
                formatted_tarih = str(tarih_obj) if tarih_obj else "-"

            formatted_vade_tarihi = ""
            if isinstance(vade_tarihi_obj, (date, datetime)):
                formatted_vade_tarihi = vade_tarihi_obj.strftime('%d.%m.%Y')
            else:
                formatted_vade_tarihi = vade_tarihi_obj if vade_tarihi_obj else "-"

            genel_iskonto_gosterim = self.db._format_currency(genel_iskonto_degeri)

            vals_to_insert = [
                fatura_id,
                fatura_no,
                formatted_tarih,
                cari_adi,
                fatura_tip,
                odeme_turu if odeme_turu else "-",
                self.db._format_currency(toplam_kdv_dahil),
                kasa_banka_adi if kasa_banka_adi else "-",
                formatted_vade_tarihi,
                olusturan_kul_adi if olusturan_kul_adi else "-",
                guncelleyen_kul_adi if guncelleyen_kul_adi else "-"
            ]

            self.fatura_tree.insert("", tk.END, values=vals_to_insert, iid=fatura_id)

        self.toplam_kayit_sayisi = self.db.get_fatura_count(
            tip=tip_filter_for_db,
            baslangic_tarih=bas_t if bas_t else None, 
            bitis_tarih=bit_t if bit_t else None, 
            arama_terimi=arama_terimi if arama_terimi else None,
            cari_id_filter=cari_id_filter_val, 
            odeme_turu_filter=odeme_turu_filter_val,
            kasa_banka_id_filter=kasa_banka_id_filter_val
        )
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0: toplam_sayfa = 1

        if self.mevcut_sayfa > toplam_sayfa:
            self.mevcut_sayfa = toplam_sayfa
        
        self.app.set_status(f"{len(faturalar)} fatura listelendi. Toplam {self.toplam_kayit_sayisi} kayıt.")
        self.sayfa_bilgisi_label.config(text=f"Sayfa {self.mevcut_sayfa} / {toplam_sayfa}")

    def secili_fatura_detay_goster(self):
        selected_item_iid = self.fatura_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen detaylarını görmek için bir fatura seçin.", parent=self.app)
            return
    
        from pencereler import FaturaDetayPenceresi
    
        FaturaDetayPenceresi(self.app, self.db, selected_item_iid)

    def _handle_dropdown_close_events(self, event=None):
        # Eğer pencere zaten kapalıysa, işlem yapma.
        if not (self.cari_filter_dropdown_window and self.cari_filter_dropdown_window.winfo_exists()):
            # Diğer filtreler için de kontrol (eğer onlar da açıksa ve kapanacaksa)
            if self.odeme_turu_filter_dropdown_window and self.odeme_turu_filter_dropdown_window.winfo_exists():
                self._close_filter_dropdown('odeme_turu')
                return
            if self.kasa_banka_filter_dropdown_window and self.kasa_banka_filter_dropdown_window.winfo_exists():
                self._close_filter_dropdown('kasa_banka')
                return
            return

        # Odaklanan widget'ı ve mouse'un konumunu al
        current_focused_widget = self.focus_get()
        mouse_x, mouse_y = self.winfo_pointerx(), self.winfo_pointery()
        widget_at_mouse = self.winfo_containing(mouse_x, mouse_y)

        # Geçici bir liste ile tüm açık dropdown'ları ve ilgili Entry/Button'ları kontrol et
        open_dropdowns_info = [
            {'type': 'cari', 'window': self.cari_filter_dropdown_window, 'listbox': self.cari_filter_listbox, 'entry': self.cari_filter_entry, 'button': self.cari_filter_dropdown_button},
            {'type': 'odeme_turu', 'window': self.odeme_turu_filter_dropdown_window, 'listbox': self.odeme_turu_filter_listbox, 'entry': self.odeme_turu_filter_entry, 'button': self.odeme_turu_filter_dropdown_button},
            {'type': 'kasa_banka', 'window': self.kasa_banka_filter_dropdown_window, 'listbox': self.kasa_banka_filter_listbox, 'entry': self.kasa_banka_filter_entry, 'button': self.kasa_banka_filter_dropdown_button},
        ]
        
        for info in open_dropdowns_info:
            dropdown_window = info['window']
            listbox_widget = info['listbox']
            entry_widget = info['entry']
            button_widget = info['button']
            filter_type = info['type']

            if dropdown_window and dropdown_window.winfo_exists(): # Sadece açıksa kontrol et
                # Eğer odaklanan widget hala Entry, Listbox veya ilgili buton ise kapatma.
                if current_focused_widget == entry_widget or \
                   current_focused_widget == listbox_widget or \
                   current_focused_widget == button_widget:
                    return # Bu açılır menüyü kapatma

                # Eğer odaklanan widget, açılır pencerenin kendisi veya başka bir alt bileşeni ise kapatma.
                if current_focused_widget == dropdown_window or \
                   current_focused_widget in dropdown_window.winfo_children():
                    return # Bu açılır menüyü kapatma

                # Eğer mouse hala dropdown veya Entry/Button üzerinde ise kapatma.
                if widget_at_mouse == dropdown_window or \
                   widget_at_mouse == listbox_widget or \
                   widget_at_mouse == entry_widget or \
                   widget_at_mouse == button_widget:
                    return # Bu açılır menüyü kapatma
                
                # Eğer buraya kadar geldiysek, bu dropdown'ın kapatılması gerekiyor.
                self._close_filter_dropdown(filter_type)
                return # Bir tanesini kapattıysak, diğerleri için döngüyü sürdürebiliriz.

    def on_double_click_detay_goster(self, event):
        self.secili_fatura_detay_goster()

    def secili_faturayi_yazdir(self):
        selected_item_iid = self.fatura_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen PDF olarak yazdırmak için bir fatura seçin.", parent=self.app)
            return

        fatura_no_str = self.fatura_tree.item(selected_item_iid, 'values')[1]

        dosya_adi_onek = f"{self.fatura_tipi.capitalize()}Faturasi"
        dosya_yolu = filedialog.asksaveasfilename(
            initialfile=f"{dosya_adi_onek}_{fatura_no_str.replace('/','_')}.pdf", 
            defaultextension=".pdf", 
            filetypes=[("PDF Dosyaları","*.pdf")], 
            title=f"{self.fatura_tipi.capitalize()} Faturasını PDF Kaydet", 
            parent=self.app
        )
        if dosya_yolu:
            success, message = self.db.fatura_pdf_olustur(selected_item_iid, dosya_yolu)
            if success:
                self.app.set_status(message)
                messagebox.showinfo("Başarılı", message, parent=self.app)
            else:
                self.app.set_status(f"PDF kaydetme başarısız: {message}")
                messagebox.showerror("Hata", message, parent=self.app)
        else:
            self.app.set_status("PDF kaydetme iptal edildi.")

    def secili_faturayi_sil(self):
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR >>>
        selected_item_iid = self.fatura_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir fatura seçin.", parent=self.app)
            return

        item_values = self.fatura_tree.item(selected_item_iid, 'values')
        fatura_no = item_values[1]
        cari_adi = item_values[3]
        fatura_tipi = item_values[4]

        if messagebox.askyesno("Fatura Silme Onayı", 
                               f"'{fatura_no}' numaralı, '{cari_adi}' carisine ait '{fatura_tipi}' faturasını silmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz ve ilişkili tüm kayıtlar (stok hareketleri, gelir/gider, cari hareket) güncellenecektir/silinecektir.", 
                               icon='warning', 
                               parent=self.app):
            
            # ARTIK self.db yerine self.app.fatura_servisi KULLANILIYOR
            success, message = self.app.fatura_servisi.fatura_sil(int(selected_item_iid))
            
            if success:
                messagebox.showinfo("Başarılı", message, parent=self.app)
                self.fatura_listesini_yukle()
                
                # İlgili diğer modülleri de yenilemek iyi bir pratiktir
                if hasattr(self.app, 'stok_yonetimi_sayfasi'): self.app.stok_yonetimi_sayfasi.stok_listesini_yenile()
                if hasattr(self.app, 'kasa_banka_yonetimi_sayfasi'): self.app.kasa_banka_yonetimi_sayfasi.hesap_listesini_yenile()
                if hasattr(self.app, 'gelir_gider_sayfasi'):
                    if hasattr(self.app.gelir_gider_sayfasi, 'gelir_listesi_frame'): self.app.gelir_gider_sayfasi.gelir_listesi_frame.gg_listesini_yukle()
                    if hasattr(self.app.gelir_gider_sayfasi, 'gider_listesi_frame'): self.app.gelir_gider_sayfasi.gider_listesi_frame.gg_listesini_yukle()

                self.app.set_status(message)
            else:
                messagebox.showerror("Hata", message, parent=self.app)

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.fatura_listesini_yukle() # Yenileme metodunu çağır

    def sonraki_sayfa(self):
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0:
            toplam_sayfa = 1 # Eğer hiç kayıt yoksa, toplam sayfa 1 olarak kabul et.

        if self.mevcut_sayfa < toplam_sayfa:
            self.mevcut_sayfa += 1
            self.fatura_listesini_yukle() # Yenileme metodunu çağır

    def secili_faturayi_guncelle(self):
        selected_item_iid = self.fatura_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen güncellemek için bir fatura seçin.", parent=self.app)
            return
        
        # FaturaGuncellemePenceresi'ni açarken, selected_item_iid'yi int'e çevirip gönderin.
        # Ayrıca, fatura listesini yenilemek için callback fonksiyonunu da geçirin.
        from pencereler import FaturaGuncellemePenceresi # Lokal import
        FaturaGuncellemePenceresi(self, self.db, int(selected_item_iid), self.fatura_listesini_yukle)

class SatisFaturalariListesi(BaseFaturaListesi):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi):
        super().__init__(parent, db_manager, app_ref, fatura_tipi=fatura_tipi)

class AlisFaturalariListesi(BaseFaturaListesi):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi):
        super().__init__(parent, db_manager, app_ref, fatura_tipi=fatura_tipi)

class TumFaturalarListesi(BaseFaturaListesi):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi):
        # fatura_tipi='TÜMÜ' burada BaseFaturaListesi'ne geçiriliyor.
        super().__init__(parent, db_manager, app_ref, fatura_tipi=fatura_tipi)


class BaseIslemSayfasi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref, islem_tipi, duzenleme_id=None, yenile_callback=None, initial_cari_id=None, initial_urunler=None, initial_data=None, **kwargs):
        self.db = db_manager
        self.app = app_ref
        super().__init__(parent) # <-- tk.Frame.__init__(parent) burada çağrılır.
        self.parent = parent # <<-- BU SATIRI EKLEYİN: parent referansını saklıyoruz

        # self.islem_tipi gibi basit değişken tanımlamaları burada olabilir.
        self.islem_tipi = islem_tipi
        self.duzenleme_id = duzenleme_id
        self.yenile_callback = yenile_callback

        self.initial_cari_id = initial_cari_id
        self.initial_urunler = initial_urunler
        self.initial_data = initial_data

        # Ortak Değişkenler
        self.fatura_kalemleri_ui = []
        self.tum_urunler_cache = []
        self.urun_map_filtrelenmis = {}
        self.kasa_banka_map = {}

        self.tum_cariler_cache_data = []
        self.cari_map_display_to_id = {}
        self.cari_id_to_display_map = {}
        self.secili_cari_id = None
        self.secili_cari_adi = None

        self.after_id = None

        # Ortak StringVar'lar: self'in bir tkinter.Frame olduğundan emin olmak için super().__init__(parent) sonrası tanımlanmalı.
        self.sv_genel_iskonto_degeri = tk.StringVar(self) 
        self.sv_genel_iskonto_tipi = tk.StringVar(self)
        self.sv_genel_iskonto_tipi.set("YOK")
        self.form_entries_order = []

    def _cari_sec_dialog_ac(self):
        """Cari Seçim Diyalog Penceresini açar."""
        from pencereler import CariSecimPenceresi, TedarikciSecimDialog 

        dialog_class_to_open = None
        cari_secim_icin_fatura_tipi = None 

        # Hangi dialogun açılacağını belirle
        # self.islem_tipi sabitleri kullanarak daha net ve doğru kontrol
        if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE, self.db.SIPARIS_TIP_SATIS]:
            dialog_class_to_open = CariSecimPenceresi
            cari_secim_icin_fatura_tipi = self.db.FATURA_TIP_SATIS
        elif self.islem_tipi in [self.db.FATURA_TIP_ALIS, self.db.FATURA_TIP_ALIS_IADE, self.db.SIPARIS_TIP_ALIS]:
            dialog_class_to_open = TedarikciSecimDialog
            cari_secim_icin_fatura_tipi = self.db.FATURA_TIP_ALIS 
        else:
            # Bu durum normalde oluşmamalıdır.
            messagebox.showwarning("Uyarı", f"Bilinmeyen işlem tipi: {self.islem_tipi}. Varsayılan olarak müşteri seçimi açılıyor.", parent=self.app)
            dialog_class_to_open = CariSecimPenceresi
            cari_secim_icin_fatura_tipi = self.db.FATURA_TIP_SATIS
        
        cari_sec_pencere = None
        if dialog_class_to_open == CariSecimPenceresi:
            cari_sec_pencere = CariSecimPenceresi(
                self, 
                self.db, 
                cari_secim_icin_fatura_tipi, 
                self._on_cari_secildi_callback 
            )
        elif dialog_class_to_open == TedarikciSecimDialog:
            cari_sec_pencere = TedarikciSecimDialog(
                self, 
                self.db, 
                self._on_cari_secildi_callback 
            )

        if cari_sec_pencere:
            # Pencere kapanana kadar bekle
            self.wait_window(cari_sec_pencere) 

            # Bu, kullanıcının pencereyi kapatma (X) veya "İptal" butonuna basma durumunu daha iyi ele alır.
            if hasattr(cari_sec_pencere, 'secilen_cari_id') and cari_sec_pencere.secilen_cari_id is not None: 
                self.secili_cari_id = cari_sec_pencere.secilen_cari_id
                self.secili_cari_adi = cari_sec_pencere.secilen_cari_ad
                
                if hasattr(self, 'lbl_secili_cari_adi'): 
                    self.lbl_secili_cari_adi.config(text=f"Seçilen Cari: {self.secili_cari_adi}")
                
                self._on_cari_selected()

                if hasattr(self, 'misafir_adi_container_frame'): 
                    # Misafir alanı sadece SATIŞ faturası ve Perakende müşteri seçiliyse ve İADE modu aktif DEĞİLSE gösterilir.
                    if self.islem_tipi == self.db.FATURA_TIP_SATIS and \
                       str(self.secili_cari_id) == str(self.db.perakende_musteri_id) and \
                       (not hasattr(self, 'iade_modu_aktif') or not self.iade_modu_aktif.get()):
                        self.misafir_adi_container_frame.grid()
                        if hasattr(self, 'sv_misafir_adi'):
                            self.sv_misafir_adi.set("")
                    else:
                        self.misafir_adi_container_frame.grid_remove()
                        if hasattr(self, 'sv_misafir_adi'):
                            self.sv_misafir_adi.set("")
            else: # Seçim yapılmadıysa veya iptal edildiyse
                # Sadece eğer cari_id zaten seçili değilse bu uyarıyı göster.
                # Bu, mevcut seçimi değiştirmek istemediğimizde boş tıklamayı engeller.
                if self.secili_cari_id is None: 
                    messagebox.showwarning("Uyarı", "Cari seçimi iptal edildi veya yapılmadı.", parent=self.app)
        else: # Pencere objesi hiç oluşturulmadıysa
            messagebox.showerror("Hata", "Cari seçim penceresi oluşturulamadı.", parent=self.app)

    def _bind_keyboard_navigation(self):
        """Formdaki giriş alanları arasında Enter tuşu ile gezinmeyi sağlar."""
        bindable_entries = [e for e in self.form_entries_order if e is not None and hasattr(e, 'bind')]

        for i, entry_widget in enumerate(bindable_entries):
            # Özel Enter bağlaması olan widget'lar için genel bağlamayı atla
            # Bu, mik_e, birim_fiyat_e, iskonto_yuzde_1_e, iskonto_yuzde_2_e için geçerlidir.
            if entry_widget == self.mik_e:
                continue # mik_e'nin özel Enter davranışı zaten tanımlı.

            if entry_widget == self.birim_fiyat_e:
                continue # birim_fiyat_e'nin özel Enter davranışı zaten tanımlı.

            if entry_widget == self.iskonto_yuzde_1_e:
                continue # iskonto_yuzde_1_e'nin özel Enter davranışı zaten tanımlı.

            if entry_widget == self.iskonto_yuzde_2_e:
                continue # iskonto_yuzde_2_e'nin özel Enter davranışı zaten tanımlı.


            # tk.Text widget'ları için Enter tuşu varsayılan olarak yeni satır yapar.
            if isinstance(entry_widget, tk.Text):
                entry_widget.bind("<Tab>", lambda e, next_idx=i+1: self._focus_next_widget_on_tab(e, next_idx, bindable_entries))
                entry_widget.bind("<Return>", "break") # Enter'ın yeni satır yapmasını engelle, ama ilerlemesin

            elif i < len(bindable_entries) - 1:
                next_widget = bindable_entries[i + 1]
                entry_widget.bind("<Return>", lambda e, next_w=next_widget: next_w.focus_set())
            else:
                # Sonuncu giriş alanında Enter'a basıldığında kaydet butonunu tetikle
                if hasattr(self, 'kaydet_buton') and self.kaydet_buton:
                    entry_widget.bind("<Return>", lambda e: self.kaydet_buton.invoke())
                                        
    def _focus_next_widget_on_tab(self, event, current_idx, bindable_entries):
        """tk.Text widget'larında Tab ile bir sonraki widget'a odaklanır."""
        if current_idx < len(bindable_entries):
            bindable_entries[current_idx].focus_set()
        return "break"

    def _delayed_stok_yenile(self, event):
        """
        Ürün arama kutusuna yazıldığında, _urun_listesini_filtrele_anlik metodunu gecikmeli olarak çağırır.
        Bu metodun adı, işlevine daha uygun olması için _delayed_urun_arama_filtrele olarak değiştirilebilir
        ancak mevcut kullanımınızda "stok" kelimesi ürün arama bağlamında kullanıldığı için şimdilik tuttum.
        """
        if self.after_id:
            self.after_cancel(self.after_id)
        # Hata çözümü: self.stok_listesini_yenile yerine self._urun_listesini_filtrele_anlik çağırılacak
        self.after_id = self.after(300, self._urun_listesini_filtrele_anlik)

    def _reset_form_explicitly(self, ask_confirmation=True):
        """
        'Sayfayı Yenile' butonuna basıldığında veya yeni form açıldığında formu sıfırlar.
        Geçerli widget'ların hala var olup olmadığını kontrol eder.
        """
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR >>>
        should_reset = True
        if ask_confirmation:
            should_reset = messagebox.askyesno("Sayfayı Yenile Onayı", "Sayfadaki tüm bilgileri sıfırlamak ve yenilemek istediğinizden emin misiniz?", parent=self.app)

        if should_reset:
            self.duzenleme_id = None
            self.fatura_kalemleri_ui = []

            # Arayüz elemanlarının var olup olmadığını kontrol ederek işlem yap
            if hasattr(self, 'sepeti_guncelle_ui') and self.winfo_exists():
                self.sepeti_guncelle_ui()
            if hasattr(self, 'toplamlari_hesapla_ui') and self.winfo_exists():
                self.toplamlari_hesapla_ui()

            if hasattr(self, 'mik_e') and self.mik_e.winfo_exists():
                self.mik_e.delete(0, tk.END)
                self.mik_e.insert(0, "1")
            if hasattr(self, 'birim_fiyat_e') and self.birim_fiyat_e.winfo_exists():
                self.birim_fiyat_e.delete(0, tk.END)
                self.birim_fiyat_e.insert(0, "0,00")
            if hasattr(self, 'stk_l') and self.stk_l.winfo_exists():
                self.stk_l.config(text="-", foreground="black")
            if hasattr(self, 'iskonto_yuzde_1_e') and self.iskonto_yuzde_1_e.winfo_exists():
                self.iskonto_yuzde_1_e.delete(0, tk.END)
                self.iskonto_yuzde_1_e.insert(0, "0,00")
            if hasattr(self, 'iskonto_yuzde_2_e') and self.iskonto_yuzde_2_e.winfo_exists():
                self.iskonto_yuzde_2_e.delete(0, tk.END)
                self.iskonto_yuzde_2_e.insert(0, "0,00")
            if hasattr(self, 'urun_arama_entry') and self.urun_arama_entry.winfo_exists():
                self.urun_arama_entry.delete(0, tk.END)
                if hasattr(self, '_urun_listesini_filtrele_anlik'):
                    self._urun_listesini_filtrele_anlik()
                self.urun_arama_entry.focus()

            if hasattr(self, 'sv_genel_iskonto_tipi'):
                self.sv_genel_iskonto_tipi.set(self.db.ISKONTO_TIP_YOK)
            if hasattr(self, 'sv_genel_iskonto_degeri'):
                self.sv_genel_iskonto_degeri.set("0,00")
            if hasattr(self, '_on_genel_iskonto_tipi_changed') and self.winfo_exists():
                self._on_genel_iskonto_tipi_changed()

            # Fatura veya Sipariş'e özel sıfırlama
            if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_ALIS, self.db.FATURA_TIP_SATIS_IADE, self.db.FATURA_TIP_ALIS_IADE]:
                if hasattr(self, '_reset_form_for_new_fatura'):
                    self._reset_form_for_new_fatura(skip_default_cari_selection=(not ask_confirmation))
                self.app.set_status(f"Yeni {self.islem_tipi.lower()} faturası oluşturmak için sayfa sıfırlandı.")
            elif self.islem_tipi in [self.db.SIPARIS_TIP_SATIS, self.db.SIPARIS_TIP_ALIS]:
                if hasattr(self, '_reset_form_for_new_siparis'):
                    self._reset_form_for_new_siparis(skip_default_cari_selection=(not ask_confirmation))
                self.app.set_status("Sipariş oluşturma sayfası yenilendi ve sıfırlandı.")
        elif ask_confirmation:
            self.app.set_status("Sayfayı yenileme işlemi iptal edildi.")

    def _save_current_form_data_to_temp(self):
        """
        Mevcut formdaki verileri, kaydedilmemiş taslak olarak App sınıfında geçici olarak saklar.
        Sadece yeni bir form üzerinde çalışılıyorsa (duzenleme_id yoksa) kaydedilir.
        """
        if self.duzenleme_id is not None:
            logging.debug("Düzenleme modunda taslak kaydedilmiyor.")
            return # Düzenleme modundaki bir faturayı/siparişi taslak olarak kaydetmiyoruz.

        temp_data = {
            'cari_id': self.secili_cari_id,
            'cari_adi': self.secili_cari_adi,
            'fatura_kalemleri_ui': self.fatura_kalemleri_ui, # Sepet içeriği
            'genel_iskonto_tipi': self.sv_genel_iskonto_tipi.get(),
            'genel_iskonto_degeri': self.sv_genel_iskonto_degeri.get(),
            # Ortak UI elemanlarının değerleri (Erişmeden önce varlıklarını kontrol et)
            'urun_arama_entry': self.urun_arama_entry.get() if hasattr(self, 'urun_arama_entry') and self.urun_arama_entry.winfo_exists() else '',
            'mik_e': self.mik_e.get() if hasattr(self, 'mik_e') and self.mik_e.winfo_exists() else '1',
            'birim_fiyat_e': self.birim_fiyat_e.get() if hasattr(self, 'birim_fiyat_e') and self.birim_fiyat_e.winfo_exists() else '0,00',
            'iskonto_yuzde_1_e': self.iskonto_yuzde_1_e.get() if hasattr(self, 'iskonto_yuzde_1_e') and self.iskonto_yuzde_1_e.winfo_exists() else '0,00',
            'iskonto_yuzde_2_e': self.iskonto_yuzde_2_e.get() if hasattr(self, 'iskonto_yuzde_2_e') and self.iskonto_yuzde_2_e.winfo_exists() else '0,00',
        }

        if self.islem_tipi in ['SATIŞ', 'ALIŞ']:
            temp_data.update({
                'fatura_no': self.f_no_e.get() if hasattr(self, 'f_no_e') and self.f_no_e.winfo_exists() else '',
                'tarih': self.fatura_tarihi_entry.get() if hasattr(self, 'fatura_tarihi_entry') and self.fatura_tarihi_entry.winfo_exists() else datetime.now().strftime('%Y-%m-%d'),
                'odeme_turu': self.odeme_turu_cb.get() if hasattr(self, 'odeme_turu_cb') and self.odeme_turu_cb.winfo_exists() else "NAKİT",
                'fatura_notlari': self.fatura_notlari_text.get("1.0", tk.END).strip() if hasattr(self, 'fatura_notlari_text') and self.fatura_notlari_text.winfo_exists() else '',
                'misafir_adi': self.entry_misafir_adi.get().strip() if hasattr(self, 'entry_misafir_adi') and self.entry_misafir_adi.winfo_ismapped() else '',
            })
            if self.islem_tipi == 'SATIŞ':
                self.app.temp_sales_invoice_data = temp_data
            else: # ALIŞ
                self.app.temp_purchase_invoice_data = temp_data
            self.app.set_status(f"{self.islem_tipi} faturası taslak olarak kaydedildi.")
            logging.debug(f"{self.islem_tipi} faturası taslak olarak kaydedildi.")

        elif self.islem_tipi in ['SATIŞ_SIPARIS', 'ALIŞ_SIPARIS']:
            temp_data.update({
                'siparis_no': self.s_no_e.get() if hasattr(self, 's_no_e') and self.s_no_e.winfo_exists() else '',
                'siparis_tarihi': self.siparis_tarihi_entry.get() if hasattr(self, 'siparis_tarihi_entry') and self.siparis_tarihi_entry.winfo_exists() else datetime.now().strftime('%Y-%m-%d'),
                'teslimat_tarihi': self.teslimat_tarihi_entry.get() if hasattr(self, 'teslimat_tarihi_entry') and self.teslimat_tarihi_entry.winfo_exists() else (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
                'durum': self.durum_combo.get() if hasattr(self, 'durum_combo') and self.durum_combo.winfo_exists() else "BEKLEMEDE",
                'siparis_notlari': self.siparis_notlari_text.get("1.0", tk.END).strip() if hasattr(self, 'siparis_notlari_text') and self.siparis_notlari_text.winfo_exists() else '',
            })
            if self.islem_tipi == 'SATIŞ_SIPARIS':
                self.app.temp_sales_order_data = temp_data
            else: # ALIŞ_SIPARIS
                self.app.temp_purchase_order_data = temp_data
            self.app.set_status(f"{self.islem_tipi} siparişi taslak olarak kaydedildi.")
            logging.debug(f"{self.islem_tipi} siparişi taslak olarak kaydedildi.")
        
        return True # Veri başarıyla yüklendi

    def _load_temp_form_data(self, forced_temp_data=None):
        temp_data = forced_temp_data
        if not temp_data:
            if self.islem_tipi == self.db.FATURA_TIP_SATIS: temp_data = self.app.temp_sales_invoice_data
            elif self.islem_tipi == self.db.FATURA_TIP_ALIS: temp_data = self.app.temp_purchase_invoice_data
            elif self.islem_tipi == self.db.SIPARIS_TIP_SATIS: temp_data = self.app.temp_sales_order_data
            elif self.islem_tipi == self.db.SIPARIS_TIP_ALIS: temp_data = self.app.temp_purchase_order_data

        if temp_data:
            # Kullanıcıya taslağı yükleyip yüklemeyeceği soruluyor
            if not messagebox.askyesno("Taslak Yükleme", 
                                    "Kaydedilmemiş bir taslağınız var. Yüklemek ister misiniz?", 
                                    parent=self.app):
                self._clear_temp_data_in_app() # Kullanıcı istemezse taslağı temizle
                return False # Yükleme yapılmadı

            # Eğer kullanıcı 'Evet' dediyse, veri doldurma işlemine devam et.
            # Cari bilgisini yükle ve UI'da göster
            if temp_data.get('cari_id') and temp_data.get('cari_adi'):
                self._on_cari_secildi_callback(temp_data['cari_id'], temp_data['cari_adi'])
            
            self.fatura_kalemleri_ui = temp_data.get('fatura_kalemleri_ui', [])
            self.sepeti_guncelle_ui()
            self.toplamlari_hesapla_ui()

            self.sv_genel_iskonto_tipi.set(temp_data.get('genel_iskonto_tipi', self.db.ISKONTO_TIP_YOK))
            self.sv_genel_iskonto_degeri.set(temp_data.get('genel_iskonto_degeri', "0,00"))
            self._on_genel_iskonto_tipi_changed()

            # Faturaya özel alanları StringVar'lar üzerinden doldur
            if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_ALIS, self.db.FATURA_TIP_SATIS_IADE, self.db.FATURA_TIP_ALIS_IADE]:
                if hasattr(self, 'sv_fatura_no'):
                    self.sv_fatura_no.set(temp_data.get('fatura_no') or self.db.son_fatura_no_getir(self.islem_tipi))
                
                if hasattr(self, 'sv_tarih'):
                    self.sv_tarih.set(temp_data.get('tarih') or datetime.now().strftime('%Y-%m-%d'))
                
                if hasattr(self, 'sv_odeme_turu'):
                    self.sv_odeme_turu.set(temp_data.get('odeme_turu') or self.db.ODEME_TURU_NAKIT)
                
                if hasattr(self, 'fatura_notlari_text'):
                    self.fatura_notlari_text.delete("1.0", tk.END)
                    self.fatura_notlari_text.insert("1.0", temp_data.get('fatura_notlari', ''))
                
                if hasattr(self, 'sv_misafir_adi'):
                    self.sv_misafir_adi.set(temp_data.get('misafir_adi', ''))
                
                # Kasa/Banka ve Vade Tarihi ayarlarını tetikle
                if hasattr(self, '_odeme_turu_degisince_event_handler'):
                    self._odeme_turu_degisince_event_handler()
                
                kasa_banka_id = temp_data.get('kasa_banka_id')
                if kasa_banka_id and hasattr(self, 'kasa_banka_map'):
                    for text, kb_id in self.kasa_banka_map.items():
                        if kb_id == kasa_banka_id:
                            self.sv_kasa_banka.set(text)
                            break
                
                if hasattr(self, 'sv_vade_tarihi'):
                    self.sv_vade_tarihi.set(temp_data.get('vade_tarihi') or "")

            # Sipariş özel alanlarını doldur
            elif self.islem_tipi in [self.db.SIPARIS_TIP_SATIS, self.db.SIPARIS_TIP_ALIS]:
                if hasattr(self, 'sv_siparis_no'):
                    self.sv_siparis_no.set(temp_data.get('siparis_no') or self.db.get_next_siparis_no(prefix="MS" if self.islem_tipi == self.db.SIPARIS_TIP_SATIS else "AS"))
                if hasattr(self, 'sv_siparis_tarihi'):
                    self.sv_siparis_tarihi.set(temp_data.get('siparis_tarihi') or datetime.now().strftime('%Y-%m-%d'))
                if hasattr(self, 'sv_teslimat_tarihi'):
                    self.sv_teslimat_tarihi.set(temp_data.get('teslimat_tarihi') or (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
                if hasattr(self, 'durum_combo'):
                    self.durum_combo.set(temp_data.get('durum') or self.db.SIPARIS_DURUM_BEKLEMEDE)
                if hasattr(self, 'siparis_notlari_text'):
                    self.siparis_notlari_text.delete("1.0", tk.END)
                    self.siparis_notlari_text.insert("1.0", temp_data.get('siparis_notlari', ''))

            self._urunleri_yukle_ve_cachele_ve_goster()
            self.app.set_status(f"Taslak {self.islem_tipi} başarıyla yüklendi.")
            return True 
        return False
    
    def _clear_temp_data_in_app(self):
        """App sınıfında saklanan geçici form verilerini temizler."""
        if self.islem_tipi == self.db.FATURA_TIP_SATIS: self.app.temp_sales_invoice_data = None
        elif self.islem_tipi == self.db.FATURA_TIP_ALIS: self.app.temp_purchase_invoice_data = None
        elif self.islem_tipi == self.db.SIPARIS_TIP_SATIS: self.app.temp_sales_order_data = None
        elif self.islem_tipi == self.db.SIPARIS_TIP_ALIS: self.app.temp_purchase_order_data = None
        logging.debug(f"DEBUG: {self.islem_tipi} taslak verisi temizlendi.")

    def _show_urun_karti_from_search_context(self, urun_id):
        """
        Bağlamsal menüden çağrıldığında ürün kartı penceresini açar.
        """
        urun_db_detaylari = self.db.stok_getir_by_id(urun_id)
        if urun_db_detaylari:
            from pencereler import UrunKartiPenceresi
            UrunKartiPenceresi(self.app, self.db, self.app.stok_yonetimi_sayfasi.stok_listesini_yenile, urun_duzenle=urun_db_detaylari, app_ref=self.app)
        else:
            messagebox.showerror("Hata", "Seçili ürün veritabanında bulunamadı.", parent=self.app)

    def _open_urun_arama_context_menu(self, event):
        """
        Ürün arama sonuçları Treeview'inde sağ tıklandığında bağlamsal menüyü gösterir.
        """
        item_id = self.urun_arama_sonuclari_tree.identify_row(event.y)
        if not item_id:
            return

        self.urun_arama_sonuclari_tree.selection_set(item_id)

        if item_id in self.urun_map_filtrelenmis:
            urun_detaylari = self.urun_map_filtrelenmis[item_id]
            urun_id = urun_detaylari['id']

            context_menu = tk.Menu(self, tearoff=0)
            context_menu.add_command(label="Ürün Kartını Görüntüle", command=lambda: self._show_urun_karti_from_search_context(urun_id))

            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()
        else:
            pass


    # --- ABSTRACT METHODS (Alt sınıflar tarafından doldurulacak) ---
    def _get_baslik(self):
        raise NotImplementedError("Bu metot alt sınıf tarafından ezilmelidir.")
    
    def _setup_ozel_alanlar(self, parent_frame):
        self.misafir_adi_container_frame = ttk.Frame(parent_frame)
        self.misafir_adi_container_frame.grid(row=2, column=2, columnspan=3, sticky=tk.EW)

        # Bu satırın olduğundan emin olun. Başlangıçta gizler.
        self.misafir_adi_container_frame.grid_remove() #

        ttk.Label(self.misafir_adi_container_frame, text="Misafir Adı :").pack(side=tk.LEFT, padx=(0,2), pady=2)
        self.entry_misafir_adi = ttk.Entry(self.misafir_adi_container_frame, width=20)
        self.entry_misafir_adi.pack(side=tk.LEFT, padx=(0,5), pady=2, fill=tk.X, expand=True)
        self.form_entries_order.append(self.entry_misafir_adi)
        raise NotImplementedError("Bu metot alt sınıf tarafından ezilmelidir.")

    def _load_initial_data(self):
        """
        Başlangıç verilerini (düzenleme modu, dışarıdan gelen veri veya taslak) forma yükler.
        Bu metod BaseIslemSayfasi'nda genel kontrolü yapar, alt sınıflar kendi spesifik
        doldurma mantıklarını içerebilir.
        """
        if self.duzenleme_id:
            pass
        elif self.initial_data:
            self._load_temp_form_data(forced_temp_data=self.initial_data)
            logging.debug(f"BaseIslemSayfasi - initial_data ile taslak veri yüklendi (islem_tipi: {self.islem_tipi}).")
        elif self.initial_cari_id or self.initial_urunler:
            logging.debug(f"BaseIslemSayfasi - initial_cari_id veya initial_urunler ile başlatıldı. Alt sınıfın doldurma mantığı bekleniyor.")
            pass
        else:
            if not self._load_temp_form_data():
                self._reset_form_explicitly(ask_confirmation=False)
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
        if messagebox.askyesno("İptal Onayı", "Sayfadaki tüm bilgileri kaydetmeden kapatmak istediğinizden emin misiniz?", parent=self.app):
            # İptal edildiğinde ilgili taslak verisini temizle
            if self.islem_tipi == 'SATIŞ':
                self.app.temp_sales_invoice_data = None
            elif self.islem_tipi == 'ALIŞ':
                self.app.temp_purchase_invoice_data = None
            elif self.islem_tipi == 'SATIŞ_SIPARIS':
                self.app.temp_sales_order_data = None
            elif self.islem_tipi == 'ALIŞ_SIPARIS':
                self.app.temp_purchase_order_data = None

            self.app.set_status(f"{self.islem_tipi} işlemi iptal edildi ve taslak temizlendi.")
            if isinstance(self.master, tk.Toplevel): # self.master bu BaseIslemSayfası'nın parent'ı olan Toplevel'dır.
                self.master.destroy()
            else:
                pass 

    def _setup_paneller(self):
        baslik = self._get_baslik()

        header_frame = ttk.Frame(self)
        header_frame.pack(pady=(5,5), fill=tk.X, padx=10)

        # Ana pencere başlığı ve "Sayfayı Yenile" butonu buraya taşındı ve tekilleştirildi
        ttk.Label(header_frame, text=baslik, font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT, padx=(0,10))
        self.btn_sayfa_yenile = ttk.Button(header_frame, text="Sayfayı Yenile", command=self._reset_form_explicitly, style="Accent.TButton")
        self.btn_sayfa_yenile.pack(side=tk.LEFT)

        content_frame = ttk.Frame(self)
        content_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0,5))
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=0)
        content_frame.rowconfigure(1, weight=1)

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
        """Kasa/Banka hesaplarını veritabanından çeker ve ilgili combobox'ı doldurur."""

        # self.islem_hesap_cb'nin varlığını kontrol edelim, yoksa pas geçelim
        if not hasattr(self, 'islem_hesap_cb') or self.islem_hesap_cb is None:
            # print("UYARI: _yukle_kasa_banka_hesaplarini çağrıldı, ancak self.islem_hesap_cb bulunamadı.")
            return

        self.islem_hesap_cb['values'] = [""]
        self.kasa_banka_map.clear()
        hesaplar = self.db.kasa_banka_listesi_al()
        display_values = [""] 
        if hesaplar:
            for h_id, h_ad, h_no, h_bakiye, h_para_birimi, h_tip, h_acilis_tarihi, h_banka, h_sube_adi, h_varsayilan_odeme_turu in hesaplar: 
                display_text = f"{h_ad} ({h_tip})" # hesap_adi (tip)
                if h_tip == "BANKA" and h_banka:
                    display_text += f" - {h_banka}" # banka_adi
                if h_tip == "BANKA" and h_no:
                    display_text += f" ({h_no})" # hesap_no
                self.kasa_banka_map[display_text] = h_id # display_text -> id
                display_values.append(display_text)
            self.islem_hesap_cb['values'] = display_values
            self.islem_hesap_cb.set("") # Başlangıçta boş veya varsayılan seçimi ayarlarız

            # Eğer varsayılan bir hesap yoksa, ilk geçerli hesabı seçmeye çalış
            if len(display_values) > 1:
                # İlk hesap boş string olduğu için ikinci elemandan başlarız
                self.islem_hesap_cb.current(1) 

        else:
            self.islem_hesap_cb['values'] = ["Hesap Yok"]
            self.islem_hesap_cb.current(0)
            self.islem_hesap_cb.config(state=tk.DISABLED)

    def _setup_sol_panel(self, parent):
        
        left_panel_frame = ttk.Frame(parent)
        left_panel_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0,5))

        gb_sol = ttk.LabelFrame(left_panel_frame, text="Genel Bilgiler", padding="15")
        gb_sol.pack(fill=tk.BOTH, expand=True)
        gb_sol.columnconfigure(1, weight=1)
        gb_sol.columnconfigure(3, weight=0)

        self._setup_ozel_alanlar(gb_sol) # Bu metodun çağrıldığı yer doğru.
    
    def _setup_sag_panel(self, parent):
        right_panel_frame = ttk.Frame(parent)
        right_panel_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0,5))

        ke_f = ttk.LabelFrame(right_panel_frame, text="Ürün Ekle", padding="15")
        ke_f.pack(fill=tk.BOTH, expand=True)
        ke_f.columnconfigure(1, weight=1)
        ke_f.grid_rowconfigure(1, weight=1)

        ttk.Label(ke_f, text="Ürün Ara (Kod/Ad):").grid(row=0, column=0, columnspan=2, padx=5, pady=(5,0), sticky=tk.W)
        self.urun_arama_entry = ttk.Entry(ke_f, width=35)
        self.urun_arama_entry.grid(row=0, column=2, columnspan=3, padx=5, pady=(5,0), sticky=tk.EW)
        self.urun_arama_entry.bind("<KeyRelease>", self._delayed_stok_yenile)
        self.urun_arama_entry.bind("<Return>", lambda e: self.mik_e.focus_set())
        self.form_entries_order.append(self.urun_arama_entry)


        urun_arama_tree_frame = ttk.Frame(ke_f)
        urun_arama_tree_frame.grid(row=1, column=0, columnspan=5, padx=5, pady=5, sticky="nsew")

        self.urun_arama_sonuclari_tree = ttk.Treeview(urun_arama_tree_frame, columns=("Kod", "Ürün Adı", "Fiyat", "Stok"), show="headings", selectmode="browse", height=4)
        
        # <<< HER BİR SÜTUNUN AYARLARINI YENİ SIRALAMAYA GÖRE GÜNCELLEYİN >>>
        self.urun_arama_sonuclari_tree.heading("Kod", text="Kod")
        self.urun_arama_sonuclari_tree.column("Kod", width=80, stretch=tk.NO, anchor=tk.CENTER) # Kod ortalı
        
        self.urun_arama_sonuclari_tree.heading("Ürün Adı", text="Ürün Adı")
        self.urun_arama_sonuclari_tree.column("Ürün Adı", width=180, stretch=tk.YES, anchor=tk.CENTER) # Ürün Adı ortalı, genişlesin
        
        self.urun_arama_sonuclari_tree.heading("Fiyat", text="Fiyat")
        self.urun_arama_sonuclari_tree.column("Fiyat", width=70, anchor=tk.CENTER, stretch=tk.NO) # Fiyat ortalı
        
        self.urun_arama_sonuclari_tree.heading("Stok", text="Stok")
        self.urun_arama_sonuclari_tree.column("Stok", width=50, anchor=tk.CENTER, stretch=tk.NO) # Stok ortalı

        self.urun_arama_sonuclari_tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        urun_arama_vsb = ttk.Scrollbar(urun_arama_tree_frame, orient="vertical", command=self.urun_arama_sonuclari_tree.yview)
        urun_arama_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.urun_arama_sonuclari_tree.configure(yscrollcommand=urun_arama_vsb.set)
        
        self.urun_arama_sonuclari_tree.bind("<Double-1>", self.kalem_ekle_arama_listesinden) # <-- BU SATIRI DEĞİŞTİRİN
        self.urun_arama_sonuclari_tree.bind("<Return>", self._select_product_from_search_list_and_focus_quantity) # <-- BU SATIRI AYNI BIRAKIN
        
        self.urun_arama_sonuclari_tree.bind("<<TreeviewSelect>>", self.secili_urun_bilgilerini_goster_arama_listesinden)
        self.urun_arama_sonuclari_tree.bind("<ButtonRelease-3>", self._open_urun_arama_context_menu)
        alt_urun_ekle_frame = ttk.Frame(ke_f)
        alt_urun_ekle_frame.grid(row=2, column=0, columnspan=5, padx=5, pady=5, sticky="ew")

        ttk.Label(alt_urun_ekle_frame, text="Miktar:").pack(side=tk.LEFT, padx=(0,2))
        self.mik_e = ttk.Entry(alt_urun_ekle_frame, width=7)
        self.mik_e.pack(side=tk.LEFT, padx=(0,5)); self.mik_e.insert(0, "1")
        setup_numeric_entry(self.app, self.mik_e, decimal_places=2)
        self.mik_e.bind("<KeyRelease>", self._check_stock_on_quantity_change)
        # DÜZELTME: Miktar kutusunda ENTER'a basınca sepete ekleme işlemi
        self.mik_e.bind("<Return>", lambda e: self.kalem_ekle_arama_listesinden())
        self.form_entries_order.append(self.mik_e) # Klavye navigasyon sırasına ekle

        ttk.Label(alt_urun_ekle_frame, text="Birim Fiyat (KDV Dahil):").pack(side=tk.LEFT, padx=(5,2))
        self.birim_fiyat_e = ttk.Entry(alt_urun_ekle_frame, width=12)
        self.birim_fiyat_e.pack(side=tk.LEFT, padx=(0,5)); self.birim_fiyat_e.insert(0, "0,00")
        setup_numeric_entry(self.app, self.birim_fiyat_e, decimal_places=2)
        if hasattr(self.birim_fiyat_e, 'bind'): # Bind'ın varlığını kontrol edin
            self.birim_fiyat_e.unbind("<Return>") # Mevcut bind'ı kaldırın
        self.form_entries_order.append(self.birim_fiyat_e)

        ttk.Label(alt_urun_ekle_frame, text="Stok:").pack(side=tk.LEFT, padx=(5,2))
        self.stk_l = ttk.Label(alt_urun_ekle_frame, text="-", width=7, anchor=tk.W, font=("Segoe UI", 12, "bold"))
        self.stk_l.pack(side=tk.LEFT, padx=(0,5))

        ttk.Label(alt_urun_ekle_frame, text="İsk.1(%):").pack(side=tk.LEFT, padx=(5,2))
        self.iskonto_yuzde_1_e = ttk.Entry(alt_urun_ekle_frame, width=7)
        self.iskonto_yuzde_1_e.pack(side=tk.LEFT, padx=(0,5)); self.iskonto_yuzde_1_e.insert(0, "0,00")
        setup_numeric_entry(self.app, self.iskonto_yuzde_1_e, allow_negative=False, decimal_places=2, max_value=100)
        # Bu bind'ı kaldırın:
        if hasattr(self.iskonto_yuzde_1_e, 'bind'):
            self.iskonto_yuzde_1_e.unbind("<Return>")
        self.form_entries_order.append(self.iskonto_yuzde_1_e)

        # İskonto 2 (%): Enter tuşuyla bir sonraki alana gitmeyecek.
        ttk.Label(alt_urun_ekle_frame, text="İsk.2(%):").pack(side=tk.LEFT, padx=(5,2))
        self.iskonto_yuzde_2_e = ttk.Entry(alt_urun_ekle_frame, width=7)
        self.iskonto_yuzde_2_e.pack(side=tk.LEFT, padx=(0,5)); self.iskonto_yuzde_2_e.insert(0, "0,00")
        setup_numeric_entry(self.app, self.iskonto_yuzde_2_e, allow_negative=False, decimal_places=2, max_value=100)
        # Bu bind'ı kaldırın:
        if hasattr(self.iskonto_yuzde_2_e, 'bind'):
            self.iskonto_yuzde_2_e.unbind("<Return>")
        self.form_entries_order.append(self.iskonto_yuzde_2_e)

        # "Sepete Ekle" butonu (Burada tanımlanmış olmalı)
        self.btn_sepete_ekle = ttk.Button(alt_urun_ekle_frame, text="Sepete Ekle", command=self.kalem_ekle_arama_listesinden, style="Accent.TButton")
        self.btn_sepete_ekle.pack(side=tk.RIGHT, padx=(10,0))
        # DÜZELTME: Sepete Ekle butonunu form_entries_order'a ekle (eğer butona tab ile ulaşılacaksa)
        self.form_entries_order.append(self.btn_sepete_ekle)
    
    def _select_product_from_search_list_and_focus_quantity(self, event=None): # <-- event=None parametresini ekleyin
        selected_item_iid_arama = self.urun_arama_sonuclari_tree.focus()
        if not selected_item_iid_arama or selected_item_iid_arama not in self.urun_map_filtrelenmis:
            return # Seçim yoksa veya geçersizse bir şey yapma

        # secili_urun_bilgilerini_goster_arama_listesinden zaten Entry'leri doldurur.
        self.secili_urun_bilgilerini_goster_arama_listesinden(event)
        
        self.mik_e.focus_set() # Miktar kutusuna odaklan
        self.mik_e.selection_range(0, tk.END) # Miktar kutusundaki metni seçili yap

        # Bu kısım Enter tuşu için istenen davranışı sağlar.
        # Mouse ile çift tıklama artık doğrudan kalem_ekle_arama_listesinden'i çağıracağı için
        # bu metot sadece Enter tuşu basıldığında çalışacaktır.
        if event and event.keysym in ["Return", "KP_Enter"]:
            return "break" # ENTER olayının yayılmasını durdur

    def _setup_sepet_paneli(self, parent):
        sep_f = ttk.LabelFrame(parent, text="Kalemler", padding="10")
        sep_f.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=(0,5))
        sep_f.columnconfigure(0, weight=1); sep_f.rowconfigure(0, weight=1)

        cols_s = ("#", "Ürün Adı", "Mik.", "B.Fiyat", "KDV%", "İskonto 1 (%)", "İskonto 2 (%)", "Uyg. İsk. Tutarı", "Tutar(Dah.)", "Fiyat Geçmişi", "Ürün ID")
        self.sep_tree = ttk.Treeview(sep_f, columns=cols_s, show='headings', selectmode="browse", displaycolumns=cols_s[:-1])
        
        col_defs_s = [
            ("#", 30, tk.CENTER, tk.NO),              # Sıra numarası ortalı
            ("Ürün Adı", 180, tk.CENTER, tk.YES),     # Ürün adı ortalı
            ("Mik.", 60, tk.CENTER, tk.NO),           # Miktar ortalı
            ("B.Fiyat", 90, tk.CENTER, tk.NO),        # Birim Fiyat ortalı
            ("KDV%", 60, tk.CENTER, tk.NO),           # KDV% ortalı
            ("İskonto 1 (%)", 75, tk.CENTER, tk.NO),  # İskonto 1 ortalı
            ("İskonto 2 (%)", 75, tk.CENTER, tk.NO),  # İskonto 2 ortalı
            ("Uyg. İsk. Tutarı", 100, tk.CENTER, tk.NO), # Uygulanan İskonto Tutarı ortalı
            ("Tutar(Dah.)", 110, tk.CENTER, tk.NO),   # Tutar(Dahil) ortalı
            ("Fiyat Geçmişi", 90, tk.CENTER, tk.NO),  # Fiyat Geçmişi butonu ortalı
            ("Ürün ID", 0, tk.W, tk.NO)               # Ürün ID gizli, ortalıya gerek yok
        ]
        for cn, w, a, s in col_defs_s:
            self.sep_tree.column(cn, width=w, anchor=a, stretch=s)
            self.sep_tree.heading(cn, text=cn)

        self.sep_tree.grid(row=0, column=0, sticky="nsew")
        vsb_s = ttk.Scrollbar(sep_f, orient="vertical", command=self.sep_tree.yview)
        vsb_s.grid(row=0, column=1, sticky="ns")
        self.sep_tree.configure(yscrollcommand=vsb_s.set)
        
        self.sep_tree.bind("<Double-1>", self._kalem_duzenle_penceresi_ac)
        self.sep_tree.bind("<ButtonRelease-1>", self._on_sepet_kalem_click)
        self.sep_tree.bind("<ButtonRelease-3>", self._open_sepet_context_menu)

        btn_s_f = ttk.Frame(sep_f)
        btn_s_f.grid(row=1, column=0, sticky="ew", pady=(5,0))
        ttk.Button(btn_s_f, text="Seçili Kalemi Sil", command=self.secili_kalemi_sil).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_s_f, text="Tüm Kalemleri Sil", command=self.sepeti_temizle).pack(side=tk.RIGHT)

    def _setup_alt_bar(self):
        alt_f = ttk.Frame(self, padding="10")
        alt_f.pack(fill=tk.X, padx=10, pady=(0,10), side=tk.BOTTOM)
        alt_f.columnconfigure(3, weight=1)

        font_t = ("Segoe UI", 10, "bold")
        self.tkh_l = ttk.Label(alt_f, text="KDV Hariç Toplam: 0.00 TL", font=font_t)
        self.tkh_l.grid(row=0, column=0, padx=5, sticky=tk.W)
        self.tkdv_l = ttk.Label(alt_f, text="Toplam KDV: 0.00 TL", font=font_t)
        self.tkdv_l.grid(row=0, column=1, padx=10, sticky=tk.W)
        self.gt_l = ttk.Label(alt_f, text="Genel Toplam: 0.00 TL", font=("Segoe UI", 12, "bold"))
        self.gt_l.grid(row=0, column=2, padx=10, sticky=tk.W)
        self.lbl_uygulanan_genel_iskonto = ttk.Label(alt_f, text="Uygulanan Genel İskonto: 0.00 TL", font=font_t)
        self.lbl_uygulanan_genel_iskonto.grid(row=1, column=0, padx=5, pady=(5,0), sticky=tk.W)

        self.kaydet_buton = ttk.Button(alt_f, text="Kaydet", command=self.kaydet, style="Accent.TButton", padding=(10,5))
        self.kaydet_buton.grid(row=0, column=4, rowspan=2, sticky=tk.E)

    def _open_sepet_context_menu(self, event):
        """
        Sepet (Kalemler) Treeview'inde sağ tıklandığında bağlamsal menüyü gösterir.
        """
        item_id = self.sep_tree.identify_row(event.y)
        if not item_id:
            return

        self.sep_tree.selection_set(item_id)
        item_values = self.sep_tree.item(item_id, 'values')

        if item_values and len(item_values) > 1:
            urun_id = item_values[10] # Ürün ID'si, Treeview'deki 11. sütun (indeks 10)
            kalem_index = int(item_id.split('_')[-1]) # Kalemin kendi indeksini al (iid formatı 'item_X')

            context_menu = tk.Menu(self, tearoff=0)
            context_menu.add_command(label="Ürün Kartını Görüntüle", command=lambda: self._show_urun_karti_from_sepet_context(urun_id))
            context_menu.add_command(label="Kalemi Düzenle", command=lambda: self._kalem_duzenle_from_context(kalem_index))
            context_menu.add_command(label="Seçili Kalemi Sil", command=self.secili_kalemi_sil)

            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()

    def _show_urun_karti_from_sepet_context(self, urun_id):
        """
        Sepet bağlamsal menüsünden çağrıldığında ürün kartı penceresini açar.
        """
        urun_db_detaylari = self.db.stok_getir_by_id(urun_id)
        if urun_db_detaylari:
            from pencereler import UrunKartiPenceresi
            UrunKartiPenceresi(self.app, self.db, self.app.stok_yonetimi_sayfasi.stok_listesini_yenile, urun_duzenle=urun_db_detaylari, app_ref=self.app)
        else:
            messagebox.showerror("Hata", "Seçili ürün veritabanında bulunamadı.", parent=self.app)

    def _kalem_duzenle_from_context(self, kalem_index):
        """
        Sepet bağlamsal menüsünden çağrıldığında kalem düzenleme penceresini açar.
        _kalem_duzenle_penceresi_ac metodunun benzeri, ancak doğrudan indeks alır.
        """
        from pencereler import KalemDuzenlePenceresi
        KalemDuzenlePenceresi(self, kalem_index, self.fatura_kalemleri_ui[kalem_index], self.islem_tipi, self.duzenleme_id)

    # --- ORTAK METOTLAR ---
    def _on_genel_iskonto_tipi_changed(self, event=None):
        selected_type = self.sv_genel_iskonto_tipi.get()
        if hasattr(self, 'genel_iskonto_degeri_e') and self.genel_iskonto_degeri_e.winfo_exists():
            if selected_type == "YOK":
                self.genel_iskonto_degeri_e.config(state=tk.DISABLED)
                self.sv_genel_iskonto_degeri.set("0,00")
            else:
                self.genel_iskonto_degeri_e.config(state=tk.NORMAL)
        self.toplamlari_hesapla_ui()

    def _carileri_yukle_ve_cachele(self):
        logging.debug(f"_carileri_yukle_ve_cachele çağrıldı. self.islem_tipi: {self.islem_tipi}")

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
            
            # Kod anahtarını kullanarak güvenli erişim
            cari_kodu_gosterim = c[kod_anahtari_db] if kod_anahtari_db in c else ''
            
            display_text = f"{cari_ad} (Kod: {cari_kodu_gosterim})" 
            self.cari_map_display_to_id[display_text] = str(cari_id)
            self.cari_id_to_display_map[str(cari_id)] = display_text
            self.tum_cariler_cache_data.append(c)

        logging.debug(f"_carileri_yukle_ve_cachele bitiş. Yüklenen cari sayısı: {len(self.tum_cariler_cache_data)}")
        

    def _cari_secim_penceresi_ac(self):        
        fatura_mi_satis_mi = 'SATIŞ' if self.islem_tipi in ['SATIŞ', 'SATIŞ_SIPARIS'] else 'ALIŞ'
        if fatura_mi_satis_mi == 'SATIŞ':
            CariSecimPenceresi(self, self.db, 'SATIŞ', self._on_cari_secildi_callback)
        else:
            TedarikciSecimDialog(self, self.db, self._on_cari_secildi_callback)

    def _on_cari_secildi_callback(self, selected_cari_id, selected_cari_display_text):
        self.secili_cari_id = selected_cari_id # BURASI GÜNCELLENMELİ
        self.secili_cari_adi = selected_cari_display_text # BURASI GÜNCELLENMELİ
        self.lbl_secili_cari_adi.config(text=f"Seçilen Cari: {self.secili_cari_adi}")
        self._on_cari_selected()

    def _on_cari_selected(self):
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
            self.lbl_cari_bakiye.config(text=bakiye_text, foreground=bakiye_color)
        else:
            self.lbl_cari_bakiye.config(text="", foreground="black")

        if hasattr(self, '_odeme_turu_ve_misafir_adi_kontrol'):
            self._odeme_turu_ve_misafir_adi_kontrol()

    def _temizle_cari_secimi(self):
        self.secili_cari_id = None
        self.secili_cari_adi = None
        if hasattr(self, 'lbl_secili_cari_adi'):
            self.lbl_secili_cari_adi.config(text="Seçilen Cari: Yok")
        if hasattr(self, 'lbl_cari_bakiye'):
            self.lbl_cari_bakiye.config(text="", foreground="black")

    def _urunleri_yukle_ve_cachele_ve_goster(self):
        if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.SIPARIS_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE]:
            fatura_tipi_for_db = self.db.FATURA_TIP_SATIS
        elif self.islem_tipi in [self.db.FATURA_TIP_ALIS, self.db.SIPARIS_TIP_ALIS, self.db.FATURA_TIP_ALIS_IADE]:
            fatura_tipi_for_db = self.db.FATURA_TIP_ALIS
        else:
            fatura_tipi_for_db = self.db.FATURA_TIP_SATIS # Varsayılan veya bilinmeyen durumlar için

        # db.stok_getir_for_fatura metodu sadece ilgili fiyat kolonunu döndürdüğü için burası doğru.
        # 'arama_termi' parametresinin adını 'arama_terimi' olarak düzeltin.
        self.tum_urunler_cache = self.db.stok_getir_for_fatura(fatura_tipi_for_db, arama_terimi=None) # Düzeltilen satır
        
        self._urun_listesini_filtrele_anlik()

    def _urun_listesini_filtrele_anlik(self, event=None):
        arama_terimi = self.urun_arama_entry.get().lower().strip()
        for i in self.urun_arama_sonuclari_tree.get_children():
            self.urun_arama_sonuclari_tree.delete(i)

        self.urun_map_filtrelenmis.clear()
        filtered_items_iids = []

        for urun_item in self.tum_urunler_cache:
            urun_id = urun_item[0]
            urun_kodu_db = urun_item[1]
            urun_adi_db = urun_item[2]
            fiyat_to_display = urun_item[3] # satis_fiyati_kdv_dahil veya alis_fiyati_kdv_dahil
            kdv_db = urun_item[4] # kdv_orani
            stok_db = urun_item[5] # stok_miktari

            if (not arama_terimi or
                (urun_adi_db and arama_terimi in urun_adi_db.lower()) or
                (urun_kodu_db and arama_terimi in urun_kodu_db.lower())):

                item_iid = f"search_{urun_id}"
                
                # <<< BURASI KRİTİK DEĞİŞİKLİK >>>
                # `values` listesinin sırasını, `columns=("Kod", "Ürün Adı", "Fiyat", "Stok")` sırasına göre düzenleyin
                self.urun_arama_sonuclari_tree.insert("", tk.END, iid=item_iid, values=(
                    urun_kodu_db, # İlk sütun: Kod
                    urun_adi_db,  # İkinci sütun: Ürün Adı
                    self.db._format_currency(fiyat_to_display), # Üçüncü sütun: Fiyat
                    f"{stok_db:.2f}".rstrip('0').rstrip('.') # Dördüncü sütun: Stok
                ))
                self.urun_map_filtrelenmis[item_iid] = {"id": urun_id, "kod": urun_kodu_db, "ad": urun_adi_db, "fiyat": fiyat_to_display, "kdv": kdv_db, "stok": stok_db}
                filtered_items_iids.append(item_iid)

        # Eğer filtreleme sonrası sadece bir ürün kalmışsa, o ürünü otomatik seç ve odakla
        if len(filtered_items_iids) == 1:
            self.urun_arama_sonuclari_tree.selection_set(filtered_items_iids[0])
            self.urun_arama_sonuclari_tree.focus(filtered_items_iids[0])

        self.secili_urun_bilgilerini_goster_arama_listesinden(None) # Seçimi güncelle

    def secili_urun_bilgilerini_goster_arama_listesinden(self, event):
        selected_item_iid_arama = self.urun_arama_sonuclari_tree.focus()
        if selected_item_iid_arama and selected_item_iid_arama in self.urun_map_filtrelenmis:
            urun_detaylari = self.urun_map_filtrelenmis[selected_item_iid_arama]
            birim_fiyat_to_fill = urun_detaylari.get('fiyat', 0.0) # 'fiyat' anahtarını kullan
            self.birim_fiyat_e.delete(0, tk.END)
            self.birim_fiyat_e.insert(0, f"{birim_fiyat_to_fill:.2f}".replace('.',','))
            self.stk_l.config(text=f"{urun_detaylari['stok']:.2f}".rstrip('0').rstrip('.'), foreground="black")
            self._check_stock_on_quantity_change()
        else:
            self.birim_fiyat_e.delete(0, tk.END)
            self.birim_fiyat_e.insert(0, "0,00")
            self.stk_l.config(text="-", foreground="black")

    def kalem_ekle_arama_listesinden(self, event=None): # <-- event=None parametresini ekleyin
        # <<< DEĞİŞİKLİK BU METODUN İÇİNDE BAŞLIYOR >>>
        selected_item_iid_arama = self.urun_arama_sonuclari_tree.focus()
        if not selected_item_iid_arama or selected_item_iid_arama not in self.urun_map_filtrelenmis:
            messagebox.showwarning("Geçersiz Ürün", "Lütfen arama listesinden geçerli bir ürün seçin.", parent=self.app)
            return

        urun_detaylari = self.urun_map_filtrelenmis[selected_item_iid_arama]
        u_id = urun_detaylari["id"]
        
        eklenecek_miktar = self.db.safe_float(self.mik_e.get())
        if eklenecek_miktar <= 0: 
            messagebox.showerror("Geçersiz Miktar", "Miktar pozitif bir değer olmalıdır.", parent=self.app)
            return

        existing_kalem_index = -1
        for i, kalem in enumerate(self.fatura_kalemleri_ui):
            if kalem[0] == u_id:
                existing_kalem_index = i
                break
        
        # Miktar artırma mantığını en başa alıyoruz.
        istenen_toplam_miktar_sepette = eklenecek_miktar
        if existing_kalem_index != -1:
            eski_miktar = self.db.safe_float(self.fatura_kalemleri_ui[existing_kalem_index][2])
            istenen_toplam_miktar_sepette = eski_miktar + eklenecek_miktar
        
        # Sadece stoğu azaltan işlemlerde (Satış, Satış Siparişi, Alış İade) stok kontrolü yapılır.
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
                onay = messagebox.askyesno(
                    "Stok Uyarısı", 
                    f"'{urun_detaylari['ad']}' için stok yetersiz!\n\n"
                    f"Kullanılabilir Stok: {kullanilabilir_stok:.2f} adet\n"
                    f"Talep Edilen Toplam Miktar: {istenen_toplam_miktar_sepette:.2f} adet\n\n"
                    f"Bu işlem negatif stok yaratacaktır. Devam etmek istiyor musunuz?", 
                    icon='warning', parent=self.app)
                if not onay: return

        b_f_kdv_dahil_orijinal = urun_detaylari.get('fiyat', 0.0)
        yeni_iskonto_1 = self.db.safe_float(self.iskonto_yuzde_1_e.get())
        yeni_iskonto_2 = self.db.safe_float(self.iskonto_yuzde_2_e.get())
        
        urun_tam_detay = self.db.stok_getir_by_id(u_id)
        alis_fiyati_fatura_aninda = urun_tam_detay['alis_fiyati_kdv_dahil'] if urun_tam_detay else 0.0

        if existing_kalem_index != -1:
            self.kalem_guncelle(existing_kalem_index, istenen_toplam_miktar_sepette, b_f_kdv_dahil_orijinal, yeni_iskonto_1, yeni_iskonto_2, alis_fiyati_fatura_aninda)
        else:
            self.kalem_guncelle(None, eklenecek_miktar, b_f_kdv_dahil_orijinal, yeni_iskonto_1, yeni_iskonto_2, alis_fiyati_fatura_aninda, u_id=u_id, urun_adi=urun_detaylari["ad"])

        # Sepete ekledikten sonra arama kutusunu ve miktar kutusunu sıfırlayıp odaklanmayı arama kutusuna verin.
        self.mik_e.delete(0, tk.END)
        self.mik_e.insert(0, "1")
        self.iskonto_yuzde_1_e.delete(0, tk.END) # İskonto alanlarını da sıfırlayalım
        self.iskonto_yuzde_1_e.insert(0, "0,00")
        self.iskonto_yuzde_2_e.delete(0, tk.END)
        self.iskonto_yuzde_2_e.insert(0, "0,00")
        self.birim_fiyat_e.delete(0, tk.END) # Birim fiyatı da sıfırlayalım
        self.birim_fiyat_e.insert(0, "0,00")
        self.stk_l.config(text="-", foreground="black") # Stok bilgisini de sıfırlayalım

        self.urun_arama_entry.delete(0, tk.END)
        self._urun_listesini_filtrele_anlik() # Arama listesini temizleyip yenileyin
        self.urun_arama_entry.focus()
        
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
        """Sepetteki ürünleri Treeview'a yükler."""
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR: Değerler formatlanmadan önce safe_float'tan geçiriliyor >>>
        if not hasattr(self, 'sep_tree') or not self.sep_tree.winfo_exists():
            return 

        for i in self.sep_tree.get_children():
            self.sep_tree.delete(i)

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

            # Treeview'e ekle
            self.sep_tree.insert("", "end", iid=f"item_{i}", values=(
                i + 1,
                k[1], # Ürün Adı (string)
                miktar_gosterim,
                self.db._format_currency(birim_fiyat_gosterim_f),
                f"%{kdv_orani_f:.0f}",
                f"{iskonto_yuzde_1_f:.2f}".replace('.',','),
                f"{iskonto_yuzde_2_f:.2f}".replace('.',','),
                self.db._format_currency(uygulanan_iskonto),
                self.db._format_currency(kalem_toplam_dahil_f),
                "Geçmişi Gör",
                k[0] # Ürün ID (int)
            ))
        
        self.toplamlari_hesapla_ui()

    def toplamlari_hesapla_ui(self, event=None):
        """Sipariş/Fatura kalemlerinin toplamlarını hesaplar ve UI'daki etiketleri günceller."""
        if not hasattr(self, 'tkh_l') or not self.tkh_l.winfo_exists() or \
           not hasattr(self, 'sv_genel_iskonto_tipi') : 
            print("DEBUG: toplamlari_hesapla_ui: UI etiketleri veya temel StringVar bulunamadı veya yok edilmiş. İşlem durduruldu.")
            return 

        toplam_kdv_haric_kalemler = sum(k[6] for k in self.fatura_kalemleri_ui)
        toplam_kdv_dahil_kalemler = sum(k[7] for k in self.fatura_kalemleri_ui)
        toplam_kdv_kalemler = sum(k[5] for k in self.fatura_kalemleri_ui)

        genel_iskonto_tipi = self.sv_genel_iskonto_tipi.get()
        genel_iskonto_degeri = self.db.safe_float(self.sv_genel_iskonto_degeri.get())
        uygulanan_genel_iskonto_tutari = 0.0

        if genel_iskonto_tipi == 'YUZDE' and genel_iskonto_degeri > 0:
            uygulanan_genel_iskonto_tutari = toplam_kdv_haric_kalemler * (genel_iskonto_degeri / 100)
        elif genel_iskonto_tipi == 'TUTAR' and genel_iskonto_degeri > 0:
            uygulanan_genel_iskonto_tutari = genel_iskonto_degeri

        nihai_toplam_kdv_dahil = toplam_kdv_dahil_kalemler - uygulanan_genel_iskonto_tutari
        nihai_toplam_kdv_haric = toplam_kdv_haric_kalemler - uygulanan_genel_iskonto_tutari
        nihai_toplam_kdv = nihai_toplam_kdv_dahil - nihai_toplam_kdv_haric

        self.tkh_l.config(text=f"KDV Hariç Toplam: {self.db._format_currency(nihai_toplam_kdv_haric)}")
        self.tkdv_l.config(text=f"Toplam KDV: {self.db._format_currency(nihai_toplam_kdv)}")
        self.gt_l.config(text=f"Genel Toplam: {self.db._format_currency(nihai_toplam_kdv_dahil)}")
        self.lbl_uygulanan_genel_iskonto.config(text=f"Uygulanan Genel İskonto: {self.db._format_currency(uygulanan_genel_iskonto_tutari)}")

    def secili_kalemi_sil(self):
        selected_items_iids = self.sep_tree.selection() 
        
        if not selected_items_iids:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir kalem seçin.", parent=self.app)
            return
        
        selected_item_tv_iid = selected_items_iids[0] 

        kalem_index = int(selected_item_tv_iid.split('_')[-1])

        del self.fatura_kalemleri_ui[kalem_index]
        
        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()
        
    def sepeti_temizle(self):
        if self.fatura_kalemleri_ui and messagebox.askyesno("Onay","Tüm kalemleri silmek istiyor musunuz?", parent=self.app):
            self.fatura_kalemleri_ui.clear()
            self.sepeti_guncelle_ui(); self.toplamlari_hesapla_ui()      

    def _kalem_duzenle_penceresi_ac(self, event):
        selected_item_tv_iid = self.sep_tree.focus()
        if not selected_item_tv_iid: return
        kalem_index = int(selected_item_tv_iid.split('_')[-1])
        from pencereler import KalemDuzenlePenceresi
        KalemDuzenlePenceresi(self, kalem_index, self.fatura_kalemleri_ui[kalem_index], self.islem_tipi, self.duzenleme_id)              

    def _on_sepet_kalem_click(self, event):
        region = self.sep_tree.identify_region(event.x, event.y)
        if region != "cell": return
        column_id = self.sep_tree.column(self.sep_tree.identify_column(event.x), 'id')
        if column_id == "Fiyat Geçmişi":
            selected_item_iid = self.sep_tree.identify_row(event.y)
            if not selected_item_iid: return
            urun_id = self.sep_tree.item(selected_item_iid, 'values')[10]
            kalem_index = int(selected_item_iid.split('_')[-1])
            if not self.secili_cari_id: messagebox.showwarning("Uyarı", "Fiyat geçmişini görmek için lütfen önce bir cari seçin.", parent=self.app); return
            fatura_tipi_for_db = 'SATIŞ' if self.islem_tipi in ['SATIŞ', 'SATIŞ_SIPARIS'] else 'ALIŞ'
            from pencereler import FiyatGecmisiPenceresi
            FiyatGecmisiPenceresi(self.app, self.db, self.secili_cari_id, urun_id, fatura_tipi_for_db, self._update_sepet_kalem_from_history, kalem_index)

    def _update_sepet_kalem_from_history(self, kalem_index, new_price_kdv_dahil, new_iskonto_1, new_iskonto_2):
        if not (0 <= kalem_index < len(self.fatura_kalemleri_ui)): return
        current_kdv_orani = self.fatura_kalemleri_ui[kalem_index][4]
        iskonto_carpan_1 = (1 - new_iskonto_1 / 100)
        iskonto_carpan_2 = (1 - new_iskonto_2 / 100)
        calculated_original_price_kdv_dahil = new_price_kdv_dahil / (iskonto_carpan_1 * iskonto_carpan_2) if (iskonto_carpan_1 * iskonto_carpan_2) > 0 else new_price_kdv_dahil
        self.kalem_guncelle(kalem_index, self.fatura_kalemleri_ui[kalem_index][2], calculated_original_price_kdv_dahil, new_price_kdv_dahil, new_iskonto_1, new_iskonto_2)

    def _check_stock_on_quantity_change(self, event=None):
        selected_item_iid_arama = self.urun_arama_sonuclari_tree.focus()
        if not selected_item_iid_arama or selected_item_iid_arama not in self.urun_map_filtrelenmis: self.stk_l.config(foreground="black"); return
        urun_detaylari = self.urun_map_filtrelenmis[selected_item_iid_arama]
        urun_id = urun_detaylari["id"]
        mevcut_stok_db = self.db.get_stok_miktari_for_kontrol(urun_id, self.duzenleme_id)
        girilen_miktar = self.db.safe_float(self.mik_e.get())
        sepetteki_miktar = sum(k[2] for k in self.fatura_kalemleri_ui if k[0] == urun_id)
        if self.islem_tipi in ['SATIŞ', 'SATIŞ_SIPARIS']:
            self.stk_l.config(foreground="red" if (sepetteki_miktar + girilen_miktar) > mevcut_stok_db else "green")
        else: self.stk_l.config(foreground="black")

    def _open_urun_karti_from_sep_item(self, event):
        if event.num == 3:
            selected_item_iid = self.sep_tree.identify_row(event.y)
            if not selected_item_iid: return
            self.sep_tree.selection_set(selected_item_iid)
            item_values = self.sep_tree.item(selected_item_iid, 'values')
            if not item_values or len(item_values) < 11: return
            urun_id_raw = item_values[10]
            try:
                urun_id = int(urun_id_raw)
                urun_db_detaylari = self.db.stok_getir_by_id(urun_id)
                if urun_db_detaylari:
                    from pencereler import UrunKartiPenceresi
                    UrunKartiPenceresi(self.app, self.db, self.app.stok_yonetimi_sayfasi.stok_listesini_yenile, urun_duzenle=urun_db_detaylari, app_ref=self.app)
            except (ValueError, TypeError):
                return
    
    def _open_urun_karti_from_search(self, event):
        if event.num == 3:
            selected_item_iid = self.urun_arama_sonuclari_tree.identify_row(event.y)
            if not selected_item_iid: return
            self.urun_arama_sonuclari_tree.selection_set(selected_item_iid)
            if selected_item_iid in self.urun_map_filtrelenmis:
                urun_id = self.urun_map_filtrelenmis[selected_item_iid]['id']
                urun_db_detaylari = self.db.stok_getir_by_id(urun_id)
                if urun_db_detaylari:
                    from pencereler import UrunKartiPenceresi
                    UrunKartiPenceresi(self.app, self.db, self.app.stok_yonetimi_sayfasi.stok_listesini_yenile, urun_duzenle=urun_db_detaylari, app_ref=self.app)

class FaturaOlusturmaSayfasi(BaseIslemSayfasi):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi, duzenleme_id=None, yenile_callback=None, initial_cari_id=None, initial_urunler=None, initial_data=None):
        self.iade_modu_aktif = tk.BooleanVar(app_ref, value=False) 
        self.original_fatura_id_for_iade = None 

        if initial_data and initial_data.get('iade_modu'):
            self.iade_modu_aktif.set(True)
            self.original_fatura_id_for_iade = initial_data.get('orijinal_fatura_id')

        super().__init__(parent, db_manager, app_ref, fatura_tipi, duzenleme_id, yenile_callback, 
                        initial_cari_id=initial_cari_id, initial_urunler=initial_urunler, initial_data=initial_data)
        
        # Ancak, sabitleri kullanmak için tekrar atama yapıldı.
        if self.iade_modu_aktif.get():
            if fatura_tipi == self.db.FATURA_TIP_SATIS:
                self.islem_tipi = self.db.FATURA_TIP_SATIS_IADE 
            elif fatura_tipi == self.db.FATURA_TIP_ALIS:
                self.islem_tipi = self.db.FATURA_TIP_ALIS_IADE 

        self.sv_fatura_no = tk.StringVar(self)
        self.sv_tarih = tk.StringVar(self, value=datetime.now().strftime('%Y-%m-%d'))
        self.sv_vade_tarihi = tk.StringVar(self, value=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        self.sv_odeme_turu = tk.StringVar(self)
        self.sv_kasa_banka = tk.StringVar(self)
        self.sv_fatura_notlari = tk.StringVar(self)
        self.sv_misafir_adi = tk.StringVar(self)

        self.cari_id = None
        self.cari_tip = None
        
        self.perakende_musteri_id = self.db.get_perakende_musteri_id()

        if not self.initial_data: 
            if not self.duzenleme_id and not self.iade_modu_aktif.get():
                self.sv_fatura_no.set(self.db.son_fatura_no_getir(self.islem_tipi))
            self.sv_odeme_turu.set(self.db.ODEME_TURU_NAKIT)

        self._setup_paneller() 

        self.after(1, self._on_iade_modu_changed) 

        self._carileri_yukle_ve_cachele() 
        self._urunleri_yukle_ve_cachele_ve_goster()
        self._yukle_kasa_banka_hesaplarini() 

        self._load_initial_data() 

        self._bind_keyboard_navigation()

    def _on_iade_modu_changed(self, *args):
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR >>>
        parent_toplevel = self.winfo_toplevel()
        if parent_toplevel and parent_toplevel.winfo_exists():
            parent_toplevel.title(self._get_baslik())

        if self.iade_modu_aktif.get():
            if hasattr(self, 'f_no_e') and self.f_no_e.winfo_exists():
                self.f_no_e.config(state=tk.DISABLED) # Fatura no kilitli kalacak
            if hasattr(self, 'cari_sec_button') and self.cari_sec_button.winfo_exists():
                self.cari_sec_button.config(state=tk.DISABLED) # Cari seçimi kilitli kalacak
            
            self.app.set_status("İade Faturası oluşturma modu aktif.")
            
            # Ödeme alanlarını KİLİTLEME, düzenlenebilir bırak
            if hasattr(self, 'odeme_turu_cb') and self.odeme_turu_cb.winfo_exists():
                self.odeme_turu_cb.config(state="readonly")
            if hasattr(self, 'islem_hesap_cb') and self.islem_hesap_cb.winfo_exists():
                self.islem_hesap_cb.config(state="readonly")
            if hasattr(self, 'entry_vade_tarihi') and self.entry_vade_tarihi.winfo_exists():
                self.entry_vade_tarihi.config(state=tk.NORMAL)
            if hasattr(self, 'btn_vade_tarihi') and self.btn_vade_tarihi.winfo_exists():
                self.btn_vade_tarihi.config(state=tk.NORMAL)
            
            if hasattr(self, '_odeme_turu_degisince_event_handler'):
                self._odeme_turu_degisince_event_handler()

            if hasattr(self, 'misafir_adi_container_frame') and self.misafir_adi_container_frame.winfo_exists():
                if hasattr(self, 'sv_misafir_adi'):
                    self.sv_misafir_adi.set("")
                self.misafir_adi_container_frame.grid_remove()
        else: # Normal fatura modu
            if hasattr(self, 'f_no_e') and self.f_no_e.winfo_exists():
                self.f_no_e.config(state=tk.NORMAL)
            if hasattr(self, 'cari_sec_button') and self.cari_sec_button.winfo_exists():
                self.cari_sec_button.config(state=tk.NORMAL)
            if not self.duzenleme_id and hasattr(self, 'sv_fatura_no'):
                self.sv_fatura_no.set(self.db.son_fatura_no_getir(self.islem_tipi))
            
            if hasattr(self, '_odeme_turu_ve_misafir_adi_kontrol'):
                self._odeme_turu_ve_misafir_adi_kontrol()

    def _get_baslik(self):
        if self.iade_modu_aktif.get():
            return "İade Faturası Oluştur"
        if self.duzenleme_id:
            return "Fatura Güncelleme"
        return "Yeni Satış Faturası" if self.islem_tipi == self.db.FATURA_TIP_SATIS else "Yeni Alış Faturası"
        
    def _setup_ozel_alanlar(self, parent_frame):
        """Ana sınıfın sol paneline faturaya özel alanları ekler ve klavye navigasyon sırasını belirler."""

        # Fatura No ve Tarih
        ttk.Label(parent_frame, text="Fatura No:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.f_no_e = ttk.Entry(parent_frame, textvariable=self.sv_fatura_no) 
        self.f_no_e.grid(row=0, column=1, padx=5, pady=2, sticky=tk.EW)
        self.form_entries_order.append(self.f_no_e)

        ttk.Label(parent_frame, text="Tarih:").grid(row=0, column=2, padx=5, pady=2, sticky=tk.W)
        self.fatura_tarihi_entry = ttk.Entry(parent_frame, textvariable=self.sv_tarih) 
        self.fatura_tarihi_entry.grid(row=0, column=3, padx=5, pady=2, sticky=tk.W)
        ttk.Button(parent_frame, text="🗓️", command=lambda: DatePickerDialog(self.app, self.fatura_tarihi_entry), width=3).grid(row=0, column=4, padx=2, pady=2, sticky=tk.W)
        setup_date_entry(self.app, self.fatura_tarihi_entry)
        self.form_entries_order.append(self.fatura_tarihi_entry)

        # Cari Seçim
        cari_btn_label_text = "Müşteri Seç:" if self.islem_tipi == self.db.FATURA_TIP_SATIS else "Tedarikçi Seç:"
        ttk.Label(parent_frame, text=cari_btn_label_text).grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
        self.cari_sec_button = ttk.Button(parent_frame, text="Cari Seç...", command=self._cari_sec_dialog_ac, style="Accent.TButton")
        self.cari_sec_button.grid(row=1, column=1, padx=5, pady=2, sticky=tk.EW)
        self.lbl_secili_cari_adi = ttk.Label(parent_frame, text="Seçilen Cari: Yok", font=("Segoe UI", 9, "bold"))
        self.lbl_secili_cari_adi.grid(row=1, column=2, columnspan=3, padx=5, pady=2, sticky=tk.W)
        self.form_entries_order.append(self.cari_sec_button)

        # Bakiye ve Misafir Adı
        self.lbl_cari_bakiye = ttk.Label(parent_frame, text="Bakiye: ...", font=("Segoe UI", 9, "bold"))
        self.lbl_cari_bakiye.grid(row=2, column=0, columnspan=2, padx=5, pady=(0,2), sticky=tk.W)
        
        self.misafir_adi_container_frame = ttk.Frame(parent_frame)
        self.misafir_adi_container_frame.grid(row=2, column=2, columnspan=3, sticky=tk.EW) 

        ttk.Label(self.misafir_adi_container_frame, text="Misafir Adı :").pack(side=tk.LEFT, padx=(0,2), pady=2)
        self.entry_misafir_adi = ttk.Entry(self.misafir_adi_container_frame, textvariable=self.sv_misafir_adi, width=20) 
        self.entry_misafir_adi.pack(side=tk.LEFT, padx=(0,5), pady=2, fill=tk.X, expand=True)
        self.form_entries_order.append(self.entry_misafir_adi)

        # Ödeme Türü
        ttk.Label(parent_frame, text="Ödeme Türü:").grid(row=3, column=0, padx=5, pady=2, sticky=tk.W)
        self.odeme_turu_cb = ttk.Combobox(parent_frame, textvariable=self.sv_odeme_turu, 
                                        values=[self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, 
                                                self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, 
                                                self.db.ODEME_TURU_SENET, self.db.ODEME_TURU_ACIK_HESAP, 
                                                self.db.ODEME_TURU_ETKISIZ_FATURA], 
                                        state="readonly", width=23)
        self.odeme_turu_cb.grid(row=3, column=1, padx=5, pady=2, sticky=tk.EW)
        self.odeme_turu_cb.bind("<<ComboboxSelected>>", self._odeme_turu_degisince_event_handler)
        self.form_entries_order.append(self.odeme_turu_cb) 

        # Kasa/Banka
        ttk.Label(parent_frame, text="İşlem Kasa/Banka:").grid(row=4, column=0, padx=5, pady=2, sticky=tk.W)
        self.islem_hesap_cb = ttk.Combobox(parent_frame, textvariable=self.sv_kasa_banka, width=35, state=tk.DISABLED) 
        self.islem_hesap_cb.grid(row=4, column=1, columnspan=3, padx=5, pady=2, sticky=tk.EW)
        self.form_entries_order.append(self.islem_hesap_cb) 

        # Vade Tarihi
        self.lbl_vade_tarihi = ttk.Label(parent_frame, text="Vade Tarihi:")
        self.entry_vade_tarihi = ttk.Entry(parent_frame, textvariable=self.sv_vade_tarihi, width=8, state=tk.DISABLED) 
        self.btn_vade_tarihi = ttk.Button(parent_frame, text="🗓️", command=lambda: DatePickerDialog(self.app, self.entry_vade_tarihi), width=3, state=tk.DISABLED)
        self.lbl_vade_tarihi.grid(row=5, column=0, padx=5, pady=(0,2), sticky=tk.W)
        self.entry_vade_tarihi.grid(row=5, column=1, padx=5, pady=(0,2), sticky=tk.EW)
        self.btn_vade_tarihi.grid(row=5, column=2, padx=2, pady=(0,2), sticky=tk.W)
        setup_date_entry(self.app, self.entry_vade_tarihi)
        self.form_entries_order.append(self.entry_vade_tarihi)

        # Fatura Notları
        ttk.Label(parent_frame, text="Fatura Notları:").grid(row=6, column=0, padx=5, pady=(0,2), sticky=tk.W)
        self.fatura_notlari_text = tk.Text(parent_frame, width=25, height=3, font=('Segoe UI', 9))
        self.fatura_notlari_text.grid(row=6, column=1, columnspan=4, padx=5, pady=(0,2), sticky=tk.EW)
        self.form_entries_order.append(self.fatura_notlari_text) 

        # Genel İskonto
        ttk.Label(parent_frame, text="Genel İskonto Tipi:").grid(row=7, column=0, padx=5, pady=(0,2), sticky=tk.W)
        self.genel_iskonto_tipi_cb = ttk.Combobox(parent_frame, textvariable=self.sv_genel_iskonto_tipi, values=["YOK", "YUZDE", "TUTAR"], state="readonly", width=10)
        self.genel_iskonto_tipi_cb.grid(row=7, column=1, padx=5, pady=(0,2), sticky=tk.W)
        self.genel_iskonto_tipi_cb.bind("<<ComboboxSelected>>", self._on_genel_iskonto_tipi_changed)
        self.form_entries_order.append(self.genel_iskonto_tipi_cb) 

        ttk.Label(parent_frame, text="Genel İskonto Değeri:").grid(row=7, column=2, padx=5, pady=(0,2), sticky=tk.W)
        self.genel_iskonto_degeri_e = ttk.Entry(parent_frame, textvariable=self.sv_genel_iskonto_degeri, width=15, state=tk.DISABLED)
        self.genel_iskonto_degeri_e.grid(row=7, column=3, padx=5, pady=(0,2), sticky=tk.EW)
        setup_numeric_entry(self.app, self.genel_iskonto_degeri_e, decimal_places=2)
        self.genel_iskonto_degeri_e.bind("<KeyRelease>", self.toplamlari_hesapla_ui)
        self.form_entries_order.append(self.genel_iskonto_degeri_e) 

    def _ot_odeme_tipi_degisince(self, event=None):
        """Hızlı işlem formunda ödeme tipi değiştiğinde kasa/banka seçimini ayarlar."""
        selected_odeme_sekli = self.ot_odeme_tipi_combo.get() # Bu satırın var olduğundan emin olun
        varsayilan_kb_db = self.db.get_kasa_banka_by_odeme_turu(selected_odeme_sekli)

        if varsayilan_kb_db:
            varsayilan_kb_id = varsayilan_kb_db[0]
            found_and_set = False
            for text, id_val in self.ot_kasa_banka_map.items():
                if id_val == varsayilan_kb_id:
                    self.ot_kasa_banka_combo.set(text)
                    found_and_set = True
                    break
            if not found_and_set and self.ot_kasa_banka_combo['values']:
                self.ot_kasa_banka_combo.set(self.ot_kasa_banka_combo['values'][0]) # İlk mevcut hesabı seç
        elif self.ot_kasa_banka_combo['values']:
            self.ot_kasa_banka_combo.set(self.ot_kasa_banka_combo['values'][0]) # Eğer varsayılan yoksa, ilkini seç
        else:
            self.ot_kasa_banka_combo.set("") # Hiç hesap yoksa boş bırak

    def _load_initial_data(self):
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR >>>
        if self.duzenleme_id:
            self._mevcut_faturayi_yukle()
            logging.debug("FaturaOlusturmaSayfasi - Düzenleme modunda, mevcut fatura yüklendi.")
        elif self.initial_data:
            self.iade_modu_aktif.set(self.initial_data.get('iade_modu', False))
            self.original_fatura_id_for_iade = self.initial_data.get('orijinal_fatura_id')
            # initial_data'dan fatura_no, tarih, odeme_turu, fatura_notlari gibi alanları doldur
            if hasattr(self, 'sv_fatura_no'): self.sv_fatura_no.set(self.initial_data.get('fatura_no', self.db.son_fatura_no_getir(self.islem_tipi)))
            if hasattr(self, 'sv_tarih'): self.sv_tarih.set(self.initial_data.get('tarih', datetime.now().strftime('%Y-%m-%d')))
            if hasattr(self, 'sv_odeme_turu'): self.sv_odeme_turu.set(self.initial_data.get('odeme_turu', self.db.ODEME_TURU_NAKIT))
            if hasattr(self, 'sv_kasa_banka'): # Sadece eğer varsa initial_data'dan yükle
                kasa_banka_id = self.initial_data.get('kasa_banka_id')
                if kasa_banka_id and hasattr(self, 'kasa_banka_map'):
                    for text, kb_id in self.kasa_banka_map.items():
                        if kb_id == kasa_banka_id:
                            self.sv_kasa_banka.set(text)
                            break
            if hasattr(self, 'sv_vade_tarihi'): self.sv_vade_tarihi.set(self.initial_data.get('vade_tarihi', ''))
            if hasattr(self, 'sv_misafir_adi'): self.sv_misafir_adi.set(self.initial_data.get('misafir_adi', ''))
            if hasattr(self, 'fatura_notlari_text'): 
                self.fatura_notlari_text.delete("1.0", tk.END)
                self.fatura_notlari_text.insert("1.0", self.initial_data.get('fatura_notlari', ''))
            if hasattr(self, 'sv_genel_iskonto_tipi'): self.sv_genel_iskonto_tipi.set(self.initial_data.get('genel_iskonto_tipi', self.db.ISKONTO_TIP_YOK))
            
            if hasattr(self, 'sv_genel_iskonto_degeri'): 
                genel_iskonto_degeri_float = self.db.safe_float(self.initial_data.get('genel_iskonto_degeri', 0.0))
                self.sv_genel_iskonto_degeri.set(f"{genel_iskonto_degeri_float:.2f}".replace('.',','))
            
            # Kalemleri yükle
            self.fatura_kalemleri_ui = self.initial_data.get('fatura_kalemleri_ui', [])
            self.sepeti_guncelle_ui()
            self.toplamlari_hesapla_ui()
            
            # Cariyi yükle
            if self.initial_data.get('cari_id') is not None and self.initial_data.get('cari_adi'):
                self._on_cari_secildi_callback(self.initial_data['cari_id'], self.initial_data['cari_adi'])

            self._on_iade_modu_changed() # UI durumunu ayarla
            logging.debug("FaturaOlusturmaSayfasi - initial_data ile taslak veri yüklendi.")
        else:
            # Yeni bir fatura oluşturuluyor. Önce formu sıfırla.
            self._reset_form_for_new_fatura()
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
        
        self._odeme_turu_ve_misafir_adi_kontrol()

    def kaydet(self):
        fatura_no = self.sv_fatura_no.get().strip()
        
        # Fatura tarihini StringVar'dan alıyoruz ve formatını kontrol ediyoruz.
        fatura_tarihi = self.sv_tarih.get().strip() 
        if not fatura_tarihi:
            messagebox.showerror("Eksik Bilgi", "Fatura Tarihi zorunludur.", parent=self.app)
            return
        try:
            datetime.strptime(fatura_tarihi, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Hata", "Fatura Tarihi formatı (YYYY-AA-GG) olmalıdır.", parent=self.app)
            return

        odeme_turu_secilen = self.sv_odeme_turu.get()
        secili_hesap_display = self.sv_kasa_banka.get()
        fatura_notlari_val = self.fatura_notlari_text.get("1.0", tk.END).strip()
        genel_iskonto_tipi_val = self.sv_genel_iskonto_tipi.get()
        genel_iskonto_degeri_val = self.db.safe_float(self.sv_genel_iskonto_degeri.get())
        vade_tarihi_val = None

        if odeme_turu_secilen == self.db.ODEME_TURU_ACIK_HESAP:
            vade_tarihi_val = self.sv_vade_tarihi.get().strip()
            if not vade_tarihi_val:
                messagebox.showerror("Eksik Bilgi", "Açık Hesap için Vade Tarihi zorunludur.", parent=self.app)
                return
            try:
                datetime.strptime(vade_tarihi_val, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Tarih Formatı Hatası", "Vade Tarihi formatı (YYYY-AA-GG) olmalıdır.", parent=self.app)
                return

        kasa_banka_id_val = None
        if odeme_turu_secilen in self.db.pesin_odeme_turleri:
            if secili_hesap_display and secili_hesap_display != "Hesap Yok":
                kasa_banka_id_val = self.kasa_banka_map.get(secili_hesap_display)
            else:
                messagebox.showerror("Eksik Bilgi", "Peşin ödeme için Kasa/Banka seçimi zorunludur.", parent=self.app)
                return

        misafir_adi_fatura = self.sv_misafir_adi.get().strip() if hasattr(self, 'sv_misafir_adi') else None

        if not fatura_no:
            messagebox.showerror("Eksik Bilgi", "Fatura Numarası zorunludur.", parent=self.app)
            return
        if not self.secili_cari_id and not misafir_adi_fatura:
            messagebox.showerror("Eksik Bilgi", "Lütfen bir cari seçin veya Misafir Adı girin.", parent=self.app)
            return
        if not self.fatura_kalemleri_ui:
            messagebox.showerror("Eksik Bilgi", "Faturada en az bir ürün olmalı.", parent=self.app)
            return

        kalemler_data = []
        for i, k_ui in enumerate(self.fatura_kalemleri_ui):
            if not isinstance(k_ui, (list, tuple)) or len(k_ui) < 14:
                messagebox.showerror("Veri Hatası", f"Sepetteki {i+1}. kalem eksik veya hatalı veri içeriyor.", parent=self.app)
                return
            kalemler_data.append((k_ui[0], k_ui[2], k_ui[3], k_ui[4], k_ui[8], k_ui[10], k_ui[11], k_ui[12], k_ui[13]))

        try:
            fatura_tip_to_save = self.islem_tipi
            if self.iade_modu_aktif.get():
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
                    original_fatura_id=self.original_fatura_id_for_iade if self.iade_modu_aktif.get() else None
                )

            if success:
                kayit_mesaji = "Fatura başarıyla güncellendi." if self.duzenleme_id else f"'{fatura_no}' numaralı fatura başarıyla kaydedildi."
                messagebox.showinfo("Başarılı", kayit_mesaji, parent=self.app)
                
                if self.yenile_callback:
                    self.yenile_callback()
                
                if not self.duzenleme_id:
                    self._reset_form_explicitly(ask_confirmation=False) 
                    self.app.set_status(f"Fatura '{fatura_no}' kaydedildi. Yeni fatura girişi için sayfa hazır.")
                else:
                    self.app.set_status(f"Fatura '{fatura_no}' başarıyla güncellendi.")
            else:
                messagebox.showerror("Hata", message, parent=self.app)

        except Exception as e:
            logging.error(f"Fatura kaydedilirken beklenmeyen bir hata oluştu: {e}\nDetaylar:\n{traceback.format_exc()}")
            messagebox.showerror("Kritik Hata", f"Fatura kaydedilirken beklenmeyen bir hata oluştu:\n{e}", parent=self.app)
            
    def _mevcut_faturayi_yukle(self):
        fatura_ana = self.db.fatura_getir_by_id(self.duzenleme_id)
        if not fatura_ana:
            messagebox.showerror("Hata", "Düzenlenecek fatura bilgileri alınamadı.")
            if isinstance(self.winfo_toplevel(), tk.Toplevel): self.winfo_toplevel().destroy()
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
        self.f_no_e.config(state=tk.NORMAL)
        self.f_no_e.delete(0, tk.END)
        self.f_no_e.insert(0, f_no)
        self.fatura_tarihi_entry.delete(0, tk.END)
        self.fatura_tarihi_entry.insert(0, tarih_db)

        if self.fatura_notlari_text:
            self.fatura_notlari_text.delete("1.0", tk.END)
            self.fatura_notlari_text.insert("1.0", fatura_notlari_db if fatura_notlari_db else "")
        
        self.entry_vade_tarihi.delete(0, tk.END)
        if vade_tarihi_db: self.entry_vade_tarihi.insert(0, vade_tarihi_db)

        self.sv_genel_iskonto_tipi.set(genel_iskonto_tipi_db if genel_iskonto_tipi_db else "YOK")
        self.sv_genel_iskonto_degeri.set(f"{genel_iskonto_degeri_db:.2f}".replace('.', ',') if genel_iskonto_degeri_db else "0,00")
        self._on_genel_iskonto_tipi_changed()
        
        self.odeme_turu_cb.set(odeme_turu_db if odeme_turu_db else "NAKİT")
        
        display_text_for_cari = self.cari_id_to_display_map.get(str(c_id_db), "Bilinmeyen Cari")
        self._on_cari_secildi_callback(c_id_db, display_text_for_cari)

        if str(c_id_db) == str(self.db.perakende_musteri_id) and misafir_adi_db:
             self.entry_misafir_adi.delete(0, tk.END)
             self.entry_misafir_adi.insert(0, misafir_adi_db)

        self._odeme_turu_degisince_hesap_combobox_ayarla()
        
        if kasa_banka_id_db is not None:
            for text, kb_id in self.kasa_banka_map.items():
                if kb_id == kasa_banka_id_db:
                    self.islem_hesap_cb.set(text)
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
        self.urun_arama_entry.focus()

    def _reset_form_for_new_invoice(self):
        """
        Formu yeni bir fatura girişi için sıfırlar.
        """
        self.duzenleme_id = None # Düzenleme modundan çık
        self.fatura_kalemleri_ui = [] # Kalemleri temizle
        self.sepeti_guncelle_ui() # Sepet Treeview'ini boşalt
        self.toplamlari_hesapla_ui() # Toplamları sıfırla

        # UI elemanlarını sıfırla
        self.f_no_e.delete(0, tk.END)
        self.f_no_e.insert(0, self.db.son_fatura_no_getir(self.islem_tipi)) # Yeni fatura numarası getir
        
        self.fatura_tarihi_entry.delete(0, tk.END)
        self.fatura_tarihi_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        self.odeme_turu_cb.set("NAKİT") # Varsayılan ödeme türü
        self._odeme_turu_degisince_event_handler(None) # Ödeme türü değişimini tetikle
        self.fatura_notlari_text.delete("1.0", tk.END)
        self.fatura_notlari_text.delete("1.0", tk.END)
        self.sv_genel_iskonto_tipi.set("YOK")
        self.sv_genel_iskonto_degeri.set("0,00")
        self._on_genel_iskonto_tipi_changed() # Genel iskonto UI'ını güncelle

        # Cari seçimi sıfırla
        self._temizle_cari_secimi() # Bu metod içinde cari seçimi temizleniyor
        
        # Ürün ekleme alanını sıfırla
        self.urun_arama_entry.delete(0, tk.END)
        self.mik_e.delete(0, tk.END); self.mik_e.insert(0, "1")
        self.birim_fiyat_e.delete(0, tk.END); self.birim_fiyat_e.insert(0, "0,00")
        self.stk_l.config(text="-")
        self.iskonto_yuzde_1_e.delete(0, tk.END); self.iskonto_yuzde_1_e.insert(0, "0,00")
        self.iskonto_yuzde_2_e.delete(0, tk.END); self.iskonto_yuzde_2_e.insert(0, "0,00")

        # Ürün listesini veritabanından yeniden yükle ve arama alanını güncelle
        self._urunleri_yukle_ve_cachele_ve_goster() # Bu metot içindeki cache ve filtreleme otomatik yapılır
        
        self.urun_arama_entry.focus()
        self.app.set_status(f"Yeni {self.islem_tipi.lower()} faturası oluşturmak için sayfa sıfırlandı.")

    def _reset_form_for_new_fatura(self, skip_default_cari_selection=False):
        self.duzenleme_id = None
        self.fatura_kalemleri_ui = []
        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()

        self.sv_fatura_no.set(self.db.son_fatura_no_getir(self.islem_tipi))
        self.sv_tarih.set(datetime.now().strftime('%Y-%m-%d'))
        self.odeme_turu_cb.set(self.db.ODEME_TURU_NAKIT)
        self._odeme_turu_degisince_event_handler(None)
        self.fatura_notlari_text.delete("1.0", tk.END)
        self.sv_genel_iskonto_tipi.set(self.db.ISKONTO_TIP_YOK)
        self.sv_genel_iskonto_degeri.set("0,00")
        self._on_genel_iskonto_tipi_changed()

        # Cari seçimi sıfırlama kısmı kaldırıldı.
        # Her zaman perakende satış müşterisini seçeceğiz (sadece satış faturasıysa).
        if self.islem_tipi == self.db.FATURA_TIP_SATIS and self.db.perakende_musteri_id is not None:
            perakende_data = self.db.musteri_getir_by_id(self.db.perakende_musteri_id)
            if perakende_data:
                self._on_cari_secildi_callback(perakende_data['id'], perakende_data['ad'])
            else:
                self._temizle_cari_secimi() # Eğer perakende müşteri bulunamazsa, cariyi temizle
        elif self.islem_tipi == self.db.FATURA_TIP_ALIS and self.db.genel_tedarikci_id is not None:
            genel_tedarikci_data = self.db.tedarikci_getir_by_id(self.db.genel_tedarikci_id)
            if genel_tedarikci_data:
                self._on_cari_secildi_callback(genel_tedarikci_data['id'], genel_tedarikci_data['ad'])
            else:
                self._temizle_cari_secimi() # Eğer genel tedarikçi bulunamazsa, cariyi temizle
        else:
            self._temizle_cari_secimi() # Diğer fatura tipleri için cariyi temizle

        self.urun_arama_entry.delete(0, tk.END)
        self.mik_e.delete(0, tk.END); self.mik_e.insert(0, "1")
        self.birim_fiyat_e.delete(0, tk.END); self.birim_fiyat_e.insert(0, "0,00")
        self.stk_l.config(text="-", foreground="black")
        self.iskonto_yuzde_1_e.delete(0, tk.END); self.iskonto_yuzde_1_e.insert(0, "0,00")
        self.iskonto_yuzde_2_e.delete(0, tk.END); self.iskonto_yuzde_2_e.insert(0, "0,00")

        self.after_idle(self._urunleri_yukle_ve_cachele_ve_goster)
        self.urun_arama_entry.focus()

    def _kasa_banka_hesaplarini_yukle(self):
        """Kasa/Banka hesaplarını veritabanından çeker ve ilgili combobox'ı doldurur."""
        self.islem_hesap_cb['values'] = [""]
        self.kasa_banka_map.clear()
        hesaplar = self.db.kasa_banka_listesi_al()
        display_values = [""] 
        if hesaplar:
            for h in hesaplar:
                # h: (id, hesap_adi, hesap_no, bakiye, para_birimi, tip, acilis_tarihi, banka_adi, sube_adi, varsayilan_odeme_turu)
                display_text = f"{h[1]} ({h[5]})" # hesap_adi (tip)
                if h[5] == "BANKA" and h[7]: display_text += f" - {h[7]}" # banka_adi
                if h[5] == "BANKA" and h[2]: display_text += f" ({h[2]})" # hesap_no
                self.kasa_banka_map[display_text] = h[0] # display_text -> id
                display_values.append(display_text)
            self.islem_hesap_cb['values'] = display_values
            self.islem_hesap_cb.set("")
        else:
            self.islem_hesap_cb['values'] = ["Hesap Yok"]
            self.islem_hesap_cb.current(0)
            self.islem_hesap_cb.config(state=tk.DISABLED)

    def _odeme_turu_degisince_event_handler(self, event=None):
        # Bu metod sadece ilgili iki ana metodu çağırmalı
        self._odeme_turu_ve_misafir_adi_kontrol(event)
        self._odeme_turu_degisince_hesap_combobox_ayarla(event)

    def _odeme_turu_ve_misafir_adi_kontrol(self, event=None):
        """
        Cari seçimine göre Misafir Adı alanının görünürlüğünü/aktifliğini ve ödeme türü seçeneklerini yönetir.
        """
        secili_cari_id_str = str(self.secili_cari_id) if self.secili_cari_id is not None else None

        # Sadece SATIŞ faturasında ve seçilen cari PERAKENDE MÜŞTERİ ise bu değişken True olur.
        is_perakende_satis = (self.islem_tipi == self.db.FATURA_TIP_SATIS and
                            str(self.secili_cari_id) is not None and
                            str(self.secili_cari_id) == str(self.db.perakende_musteri_id))

        # Misafir Adı alanını yönet
        if hasattr(self, 'misafir_adi_container_frame'): # misafir_adi_container_frame'in varlığını kontrol et
            # Misafir alanı sadece SATIŞ faturası ve Perakende müşteri seçiliyse ve İADE modu aktif DEĞİLSE gösterilir.
            if is_perakende_satis and \
            (not hasattr(self, 'iade_modu_aktif') or not self.iade_modu_aktif.get()):
                self.misafir_adi_container_frame.grid() # Göster
                if hasattr(self, 'entry_misafir_adi'): # entry_misafir_adi'nin de varlığını kontrol et
                    self.entry_misafir_adi.config(state=tk.NORMAL)
            else:
                self.misafir_adi_container_frame.grid_remove() # Gizle
                if hasattr(self, 'entry_misafir_adi'):
                    self.sv_misafir_adi.set("") # Misafir adını temizle
                    self.entry_misafir_adi.config(state=tk.DISABLED)

        # <<< YENİ VE BASİTLEŞTİRİLMİŞ ÖDEME TÜRÜ MANTIĞI >>>
        all_payment_values = [self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, # <-- Düzeltildi
                            self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, # <-- Düzeltildi
                            self.db.ODEME_TURU_SENET, self.db.ODEME_TURU_ACIK_HESAP] # <-- Düzeltildi
        current_selected_odeme_turu = self.odeme_turu_cb.get()

        target_payment_values = []
        if is_perakende_satis:
            target_payment_values = [p for p in all_payment_values if p != self.db.ODEME_TURU_ACIK_HESAP] # <-- Düzeltildi
        else:
            target_payment_values = all_payment_values[:]

        self.odeme_turu_cb['values'] = target_payment_values

        if current_selected_odeme_turu not in target_payment_values or not current_selected_odeme_turu:
            if is_perakende_satis:
                self.odeme_turu_cb.set(self.db.ODEME_TURU_NAKIT)
            else:
                self.odeme_turu_cb.set(self.db.ODEME_TURU_ACIK_HESAP)

        self._odeme_turu_degisince_hesap_combobox_ayarla()

    def _odeme_turu_degisince_hesap_combobox_ayarla(self, event=None):
        """
        FaturaOlusturmaSayfasi'na özel: Ödeme türü seçimine göre Kasa/Banka ve Vade Tarihi alanlarını yönetir.
        """
        secili_odeme_turu = self.odeme_turu_cb.get()
        pesin_odeme_turleri = [self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, 
                            self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, 
                            self.db.ODEME_TURU_SENET]

        # Vade tarihi alanlarının görünürlüğünü ve aktifliğini ayarla
        if secili_odeme_turu == self.db.ODEME_TURU_ACIK_HESAP:
            self.lbl_vade_tarihi.grid(row=5, column=0, padx=5, pady=(0,2), sticky=tk.W) # Doğru grid konumunu kullanın
            self.entry_vade_tarihi.grid(row=5, column=1, padx=5, pady=(0,2), sticky=tk.EW)
            self.btn_vade_tarihi.grid(row=5, column=2, padx=2, pady=(0,2), sticky=tk.W)
            self.entry_vade_tarihi.config(state=tk.NORMAL)
            self.btn_vade_tarihi.config(state=tk.NORMAL)
            
            # Varsayılan olarak vade tarihini 30 gün sonrası olarak ayarla
            vade_tarihi_varsayilan = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            if not self.sv_vade_tarihi.get(): # Sadece boşsa varsayılan ata
                self.sv_vade_tarihi.set(vade_tarihi_varsayilan)
        else:
            self.lbl_vade_tarihi.grid_remove()
            self.entry_vade_tarihi.grid_remove()
            self.btn_vade_tarihi.grid_remove()
            self.entry_vade_tarihi.config(state=tk.DISABLED)
            self.sv_vade_tarihi.set("") # Vade tarihini temizle

        # Kasa/Banka alanının görünürlüğünü ve aktifliğini ayarla
        if secili_odeme_turu in pesin_odeme_turleri:
            self.islem_hesap_cb.config(state="readonly")

            # Varsayılan Kasa/Banka Seçimi
            varsayilan_kb_db = self.db.get_kasa_banka_by_odeme_turu(secili_odeme_turu)

            if varsayilan_kb_db:
                varsayilan_kb_id = varsayilan_kb_db[0]
                found_and_set_default = False
                for text, id_val in self.kasa_banka_map.items():
                    if id_val == varsayilan_kb_id:
                        self.sv_kasa_banka.set(text) # StringVar'ı güncelle
                        found_and_set_default = True
                        break

                if not found_and_set_default:
                    if self.islem_hesap_cb['values'] and len(self.islem_hesap_cb['values']) > 1:
                        self.islem_hesap_cb.current(1) # İlk geçerli hesabı seç
                    else:
                        self.sv_kasa_banka.set("")
            else:
                if self.islem_hesap_cb['values'] and len(self.islem_hesap_cb['values']) > 1:
                    self.islem_hesap_cb.current(1)
                else:
                    self.sv_kasa_banka.set("")

        else: # "AÇIK HESAP" veya "ETKİSİZ FATURA" seçilirse
            self.sv_kasa_banka.set("")
            self.islem_hesap_cb.config(state=tk.DISABLED)


    def _temizle_cari_secimi(self): #EMİNDEĞİLİM
        # Önce ana sınıftaki ortak temizliği yap
        super()._temizle_cari_secimi()
        
        # Şimdi sadece faturaya özgü ek temizliği yap
        if hasattr(self, 'entry_misafir_adi'):
            self.entry_misafir_adi.delete(0, tk.END)
            self.misafir_adi_container_frame.grid_remove()
        if hasattr(self, '_odeme_turu_ve_misafir_adi_kontrol'):
            self._odeme_turu_ve_misafir_adi_kontrol()


    def _populate_from_initial_data(self):
        # Bu metod FaturaOlusturmaSayfasi'na özgü doldurma mantığını içerir
        # Fatura için initial_cari_id genellikle ALIŞ faturasında tedarikçi için kullanılır.
        # initial_urunler ise hem ALIŞ hem SATIŞ için kritik stoktan gelen ürünler olabilir.
        
        print("DEBUG: FaturaOlusturmaSayfasi - _populate_from_initial_data metodu çağrıldı.")

        if self.initial_cari_id:
            selected_cari_data = None
            if self.islem_tipi == 'ALIŞ': # Sadece ALIŞ faturası için tedarikçi ID'si bekliyoruz
                selected_cari_data = self.db.tedarikci_getir_by_id(self.initial_cari_id)
            elif self.islem_tipi == 'SATIŞ': # SATIŞ faturası için müşteri ID'si beklenir
                selected_cari_data = self.db.musteri_getir_by_id(self.initial_cari_id)

            if selected_cari_data:
                # `selected_cari_data` bir `sqlite3.Row` objesi olduğundan, anahtarlarının varlığını kontrol edelim.
                kod_anahtari = 'kod' if 'kod' in selected_cari_data.keys() else 'tedarikci_kodu'
                display_text = f"{selected_cari_data['ad']} (Kod: {selected_cari_data[kod_anahtari]})"
                self._on_cari_secildi_callback(selected_cari_data['id'], display_text)
                self.app.set_status(f"Fatura cari: {display_text} olarak önceden dolduruldu.")
            else:
                self.app.set_status("Önceden doldurulacak cari bulunamadı.")


        if self.initial_urunler:
            self.fatura_kalemleri_ui.clear() # Mevcut kalemleri temizleyelim ki tekrarlanmasın

            for urun_data in self.initial_urunler:
                urun_id = urun_data['id']
                miktar = urun_data['miktar']
                
                iskonto_yuzde_1 = urun_data.get('iskonto_yuzde_1', 0.0)
                iskonto_yuzde_2 = urun_data.get('iskonto_yuzde_2', 0.0)
                
                urun_db_info = self.db.stok_getir_by_id(urun_id)
                if not urun_db_info:
                    print(f"UYARI: Ürün ID {urun_id} bulunamadı, sepeti doldurulamıyor.")
                    continue

                # Fatura tipi Alış ise alış fiyatını, Satış ise satış fiyatını kullan
                if self.islem_tipi == 'ALIŞ':
                    birim_fiyat_kdv_haric = urun_db_info['alis_fiyati_kdv_haric']
                    kdv_orani = urun_db_info['kdv_orani']
                    alis_fiyati_fatura_aninda = urun_db_info['alis_fiyati_kdv_dahil'] # Alış faturası için kendi alış fiyatı
                    original_kdv_dahil_fiyat_base = birim_fiyat_kdv_haric * (1 + kdv_orani / 100)
                else: # SATIŞ
                    birim_fiyat_kdv_haric = urun_db_info['satis_fiyati_kdv_haric']
                    kdv_orani = urun_db_info['kdv_orani']
                    alis_fiyati_fatura_aninda = urun_db_info['alis_fiyati_kdv_dahil'] # Satış faturası için alış fiyatı
                    original_kdv_dahil_fiyat_base = birim_fiyat_kdv_haric * (1 + kdv_orani / 100)

                fiyat_iskonto_1_sonrasi_dahil = original_kdv_dahil_fiyat_base * (1 - iskonto_yuzde_1 / 100)
                iskontolu_birim_fiyat_dahil = fiyat_iskonto_1_sonrasi_dahil * (1 - iskonto_yuzde_2 / 100)
                

                # KDV Hariç, KDV Tutarı, KDV Dahil Toplamları hesapla (iskontosuz olarak)
                if kdv_orani == 0:
                    iskontolu_birim_fiyat_haric = iskontolu_birim_fiyat_dahil
                else:
                    iskontolu_birim_fiyat_haric = iskontolu_birim_fiyat_dahil / (1 + kdv_orani / 100)
                
                kalem_toplam_kdv_haric = miktar * iskontolu_birim_fiyat_haric
                kdv_tutari = (iskontolu_birim_fiyat_dahil - iskontolu_birim_fiyat_haric) * miktar
                kalem_toplam_kdv_dahil = miktar * iskontolu_birim_fiyat_dahil

                iskonto_tipi = "YOK" # initial_urunler'den gelmiyorsa varsayılan
                iskonto_degeri = 0.0 # initial_urunler'den gelmiyorsa varsayılan


                self.fatura_kalemleri_ui.append((
                    urun_id, urun_db_info['urun_adi'], miktar, 
                    birim_fiyat_kdv_haric, # birim_fiyat_kdv_haric_ORIJINAL (3)
                    kdv_orani, # kdv_orani (4)
                    kdv_tutari, # kdv_tutari_ISKONTOLU (5) (Burada iskonto 0 olduğu için iskontosuz)
                    kalem_toplam_kdv_haric, # tkh_ISKONTOLU (6) (Burada iskonto 0 olduğu için iskontosuz)
                    kalem_toplam_kdv_dahil, # tkd_ISKONTOLU (7) (Burada iskonto 0 olduğu için iskontosuz)
                    alis_fiyati_fatura_aninda, # alis_fiyati_fatura_aninda_kdv_dahil (8)
                    kdv_orani, # kdv_orani_fatura_aninda_DB (9)
                    iskonto_yuzde_1, iskonto_yuzde_2, # iskonto_yuzde_1 (10), iskonto_yuzde_2 (11)
                    iskonto_tipi, iskonto_degeri, # iskonto_tipi_genel (12), iskonto_degeri_genel (13)
                    iskontolu_birim_fiyat_dahil # iskontolu_birim_fiyat_dahil (14) (Burada iskontosuz fiyat)
                ))
            
            self.sepeti_guncelle_ui()
            self.toplamlari_hesapla_ui()
            self.app.set_status(f"Başlangıç ürünleri sepete eklendi. Toplam {len(self.fatura_kalemleri_ui)} kalem.")
        
        print("DEBUG: FaturaOlusturmaSayfasi - _populate_from_initial_data metodu tamamlandı.")

    def _fatura_pdf_yazdir_ui(self, fatura_id_to_print, fatura_no_str_print): #EMİNDEĞİLİM
        """Fatura oluşturma/güncelleme sonrası PDF yazdırma için dialog açar."""
        dosya_adi_onek = "SatisFaturasi" if self.fatura_tipi == 'SATIŞ' else "AlisFaturasi"
        dosya_yolu = filedialog.asksaveasfilename(
            initialfile=f"{dosya_adi_onek}_{fatura_no_str_print.replace('/','_')}.pdf",
            defaultextension=".pdf",
            filetypes=[("PDF Dosyaları","*.pdf")],
            title=f"{self.fatura_tipi.capitalize()} Faturasını PDF Kaydet",
        )
        if dosya_yolu:
            success, message = self.db.fatura_pdf_olustur(fatura_id_to_print, dosya_yolu)
            if success:
                self.app.set_status(message)
                messagebox.showinfo("Başarılı", message, parent=self.app)
            else:
                self.app.set_status(f"PDF kaydetme başarısız: {message}")
                messagebox.showerror("Hata", message, parent=self.app)
        else:
            self.app.set_status("PDF kaydetme iptal edildi.")

def _initialize_fatura_ui_after_setup(fatura_sayfasi_obj, *args):
    """
    FaturaOlusturmaSayfasi'nın UI elemanları tamamen kurulduktan sonra
    _on_iade_modu_changed mantığını güvenli bir şekilde uygular.
    """
    parent_toplevel = fatura_sayfasi_obj.winfo_toplevel()
    parent_toplevel.title(fatura_sayfasi_obj._get_baslik()) 

    if fatura_sayfasi_obj.iade_modu_aktif.get():
        # İade modunda fatura numarası düzenlenemez olmalı (otomatik atanacak)
        fatura_sayfasi_obj.f_no_e.config(state=tk.DISABLED)
        fatura_sayfasi_obj.app.set_status("İade Faturası oluşturma modu aktif. Lütfen iade edilecek ürünleri ekleyin.")

        # Ödeme türü, kasa/banka ve vade tarihi initial_data'dan gelir ve sabitlenir.
        if fatura_sayfasi_obj.initial_data:
            fatura_sayfasi_obj.sv_odeme_turu.set(fatura_sayfasi_obj.initial_data.get('odeme_turu', "NAKİT"))
            fatura_sayfasi_obj.odeme_turu_cb.config(state=tk.DISABLED) # Ödeme türü kilitlensin

            kasa_banka_id = fatura_sayfasi_obj.initial_data.get('kasa_banka_id')
            found_kb_text = ""
            if kasa_banka_id is not None:
                for text, kb_id in fatura_sayfasi_obj.kasa_banka_map.items(): 
                    if kb_id == kasa_banka_id:
                        found_kb_text = text
                        break
            if found_kb_text:
                fatura_sayfasi_obj.islem_hesap_cb.set(found_kb_text)
                fatura_sayfasi_obj.islem_hesap_cb.config(state=tk.DISABLED) # Kasa/Banka kilitlensin
            else:
                fatura_sayfasi_obj.islem_hesap_cb.set("")
                fatura_sayfasi_obj.islem_hesap_cb.config(state=tk.DISABLED)

            fatura_sayfasi_obj.sv_vade_tarihi.set(fatura_sayfasi_obj.initial_data.get('vade_tarihi', ""))
            fatura_sayfasi_obj.entry_vade_tarihi.config(state=tk.DISABLED)
            fatura_sayfasi_obj.btn_vade_tarihi.config(state=tk.DISABLED)
            fatura_sayfasi_obj.lbl_vade_tarihi.grid() # Göster
            fatura_sayfasi_obj.entry_vade_tarihi.grid()
            fatura_sayfasi_obj.btn_vade_tarihi.grid()
        else: # initial_data yoksa ama iade modu aktifse (bu senaryo olmamalı ama güvenlik için)
            fatura_sayfasi_obj.odeme_turu_cb.config(state=tk.DISABLED)
            fatura_sayfasi_obj.islem_hesap_cb.config(state=tk.DISABLED)
            fatura_sayfasi_obj.entry_vade_tarihi.config(state=tk.DISABLED)
            fatura_sayfasi_obj.btn_vade_tarihi.config(state=tk.DISABLED)
            fatura_sayfasi_obj.lbl_vade_tarihi.grid_remove() # Gizle
            fatura_sayfasi_obj.entry_vade_tarihi.grid_remove()
            fatura_sayfasi_obj.btn_vade_tarihi.grid_remove()


        # Misafir adı alanı gizlensin (iade faturası perakende müşteriden gelmez, her zaman belirli bir cariden gelir)
        if hasattr(fatura_sayfasi_obj, 'misafir_adi_container_frame') and fatura_sayfasi_obj.misafir_adi_container_frame.winfo_exists():
            fatura_sayfasi_obj.sv_misafir_adi.set("") # Misafir adını temizle
            fatura_sayfasi_obj.misafir_adi_container_frame.grid_remove()

    else: # Normal fatura moduna dönüş
        fatura_sayfasi_obj.f_no_e.config(state=tk.NORMAL)
        if not fatura_sayfasi_obj.duzenleme_id:
            fatura_sayfasi_obj.sv_fatura_no.set(fatura_sayfasi_obj.db.son_fatura_no_getir(fatura_sayfasi_obj.islem_tipi))

        fatura_sayfasi_obj.odeme_turu_cb.config(state="readonly")
        fatura_sayfasi_obj.islem_hesap_cb.config(state="readonly")
        fatura_sayfasi_obj._odeme_turu_degisince_hesap_combobox_ayarla() # Ödeme türü/kasa banka ayarını tetikle (normal mod için)

        fatura_sayfasi_obj._odeme_turu_ve_misafir_adi_kontrol() # Misafir adı alanını tekrar kontrol et
class SiparisOlusturmaSayfasi(BaseIslemSayfasi):
    def __init__(self, parent, db_manager, app_ref, islem_tipi, duzenleme_id=None, yenile_callback=None, initial_cari_id=None, initial_urunler=None, initial_data=None):
        # Bu kısımda tk.BooleanVar gibi, super().__init__ çağrılmadan önce tanımlanması gerekenler yer alır.
        self.iade_modu_aktif = tk.BooleanVar(app_ref, value=False)
        self.original_fatura_id_for_iade = None

        if initial_data and initial_data.get('iade_modu'):
            self.iade_modu_aktif.set(True)
            self.original_fatura_id_for_iade = initial_data.get('orijinal_fatura_id')

        # BaseIslemSayfasi'nın __init__ metodunu çağırırken tüm beklenen parametreleri doğru adlarla iletiyoruz.
        super().__init__(parent, db_manager, app_ref, islem_tipi, duzenleme_id, yenile_callback,
                        initial_cari_id=initial_cari_id, initial_urunler=initial_urunler, initial_data=initial_data)

        # ARTIK 'self' OBJESİ BİR TKINTER WIDGET'I OLARAK BAŞLATILDI.
        # Bu yüzden StringVar'ları burada tanımlayabiliriz.
        self.sv_siparis_no = tk.StringVar(self)
        self.sv_siparis_tarihi = tk.StringVar(self, value=datetime.now().strftime('%Y-%m-%d'))
        self.sv_teslimat_tarihi = tk.StringVar(self, value=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))

        # Diğer değişken tanımlamaları (BaseIslemSayfasi'nda ele alınmayanlar)
        self.cari_id = None
        self.cari_tip = None

        self.perakende_musteri_id = self.db.get_perakende_musteri_id()

        # <<< BURADAKİ İKİ ÖNEMLİ ÇAĞRIYI EKLİYORUZ >>>
        self._setup_paneller() # Bu, tüm UI panellerini ve widget'larını oluşturur ve yerleştirir.
        self._load_initial_data() # Bu, formdaki alanları başlangıç verileriyle doldurur.

        # Note: iade_modu_aktif, siparişler için fatura kadar merkezi değildir.
        # Eğer siparişlerde 'iade_modu' gibi bir kavram yoksa, bununla ilgili trace/after çağrıları kaldırılabilir.
        # self.iade_modu_aktif.trace_add("write", self._on_iade_modu_changed)
        # self.after(1, self._on_iade_modu_changed)
        
    def _get_baslik(self):
        if self.duzenleme_id:
            return "Sipariş Güncelleme"
        return "Yeni Müşteri Siparişi" if self.islem_tipi == 'SATIŞ_SIPARIS' else "Yeni Tedarikçi Siparişi"

    def _setup_ozel_alanlar(self, parent_frame):
        """Ana sınıfın sol paneline siparişe özel alanları ekler ve klavye navigasyon sırasını belirler."""
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR: textvariable parametreleri eklendi >>>

        # Satır 0: Sipariş No ve Tarih
        ttk.Label(parent_frame, text="Sipariş No:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.s_no_e = ttk.Entry(parent_frame, textvariable=self.sv_siparis_no) # Düzeltildi
        self.s_no_e.grid(row=0, column=1, padx=5, pady=2, sticky=tk.EW)

        ttk.Label(parent_frame, text="Sipariş Tarihi:").grid(row=0, column=2, padx=5, pady=2, sticky=tk.W)
        self.siparis_tarihi_entry = ttk.Entry(parent_frame, textvariable=self.sv_siparis_tarihi) # Düzeltildi
        self.siparis_tarihi_entry.grid(row=0, column=3, padx=5, pady=2, sticky=tk.W)
        ttk.Button(parent_frame, text="🗓️", command=lambda: DatePickerDialog(self.app, self.siparis_tarihi_entry), width=3).grid(row=0, column=4, padx=2, pady=2, sticky=tk.W)
        setup_date_entry(self.app, self.siparis_tarihi_entry)

        # Satır 1: Cari Seçim
        cari_btn_label_text = "Müşteri Seç:" if self.islem_tipi == self.db.SIPARIS_TIP_SATIS else "Tedarikçi Seç:"
        ttk.Label(parent_frame, text=cari_btn_label_text).grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
        self.cari_sec_button = ttk.Button(parent_frame, text="Cari Seç...", command=self._cari_sec_dialog_ac, style="Accent.TButton")
        self.cari_sec_button.grid(row=1, column=1, padx=5, pady=2, sticky=tk.EW)
        self.lbl_secili_cari_adi = ttk.Label(parent_frame, text="Seçilen Cari: Yok", font=("Segoe UI", 9, "bold"))
        self.lbl_secili_cari_adi.grid(row=1, column=2, columnspan=3, padx=5, pady=2, sticky=tk.W)

        # Satır 2: Cari Bakiye
        self.lbl_cari_bakiye = ttk.Label(parent_frame, text="Bakiye: ...", font=("Segoe UI", 9, "bold"))
        self.lbl_cari_bakiye.grid(row=2, column=0, columnspan=2, padx=5, pady=(0,2), sticky=tk.W)

        # Satır 3: Teslimat Tarihi
        ttk.Label(parent_frame, text="Teslimat Tarihi:").grid(row=3, column=0, padx=5, pady=2, sticky=tk.W)
        self.teslimat_tarihi_entry = ttk.Entry(parent_frame, textvariable=self.sv_teslimat_tarihi) # Düzeltildi
        self.teslimat_tarihi_entry.grid(row=3, column=1, padx=5, pady=2, sticky=tk.EW)
        setup_date_entry(self.app, self.teslimat_tarihi_entry)
        ttk.Button(parent_frame, text="🗓️", command=lambda: DatePickerDialog(self.app, self.teslimat_tarihi_entry), width=3).grid(row=3, column=2, padx=2, pady=2, sticky=tk.W)

        # Satır 4: Durum
        ttk.Label(parent_frame, text="Durum:").grid(row=4, column=0, padx=5, pady=2, sticky=tk.W)
        self.durum_combo = ttk.Combobox(parent_frame, values=["BEKLEMEDE", "TAMAMLANDI", "KISMİ_TESLİMAT", "İPTAL_EDİLDİ"], state="readonly")
        self.durum_combo.grid(row=4, column=1, padx=5, pady=2, sticky=tk.EW)
        self.durum_combo.set("BEKLEMEDE")

        # Satır 5: Notlar
        ttk.Label(parent_frame, text="Sipariş Notları:").grid(row=5, column=0, padx=5, pady=2, sticky=tk.NW)
        self.siparis_notlari_text = tk.Text(parent_frame, width=25, height=3, font=('Segoe UI', 9))
        self.siparis_notlari_text.grid(row=5, column=1, columnspan=4, padx=5, pady=2, sticky=tk.EW)

        # Satır 6: Genel İskonto
        ttk.Label(parent_frame, text="Genel İskonto Tipi:").grid(row=6, column=0, padx=5, pady=2, sticky=tk.W)
        self.genel_iskonto_tipi_cb = ttk.Combobox(parent_frame, textvariable=self.sv_genel_iskonto_tipi, values=["YOK", "YUZDE", "TUTAR"], state="readonly", width=10)
        self.genel_iskonto_tipi_cb.grid(row=6, column=1, padx=5, pady=2, sticky=tk.W)
        self.genel_iskonto_tipi_cb.bind("<<ComboboxSelected>>", self._on_genel_iskonto_tipi_changed)

        ttk.Label(parent_frame, text="Genel İskonto Değeri:").grid(row=6, column=2, padx=5, pady=2, sticky=tk.W)
        self.genel_iskonto_degeri_e = ttk.Entry(parent_frame, textvariable=self.sv_genel_iskonto_degeri, width=15, state=tk.DISABLED)
        self.genel_iskonto_degeri_e.grid(row=6, column=3, padx=5, pady=2, sticky=tk.EW)
        setup_numeric_entry(self.app, self.genel_iskonto_degeri_e, decimal_places=2)
        self.genel_iskonto_degeri_e.bind("<KeyRelease>", self.toplamlari_hesapla_ui)

    def _load_initial_data(self):
        """
        SiparisOlusturmaSayfasi'na özel başlangıç veri yükleme mantığı.
        """
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR >>>
        if self.duzenleme_id:
            self._mevcut_siparisi_yukle()
            logging.debug("SiparisOlusturmaSayfasi - Düzenleme modunda, mevcut sipariş yüklendi.")
        elif self.initial_data:
            self._load_temp_form_data(forced_temp_data=self.initial_data)
            logging.debug("SiparisOlusturmaSayfasi - initial_data ile taslak veri yüklendi.")
        else:
            # Yeni bir sipariş oluşturuluyor. Önce formu sıfırla.
            self._reset_form_for_new_siparis()
            logging.debug("SiparisOlusturmaSayfasi - Yeni sipariş için form sıfırlandı.")
            
            # Şimdi varsayılan carileri ata.
            if self.islem_tipi == self.db.SIPARIS_TIP_SATIS:
                # Müşteri Siparişi ise 'Perakende Satış Müşterisi'ni seç
                if self.db.perakende_musteri_id is not None:
                    perakende_data = self.db.musteri_getir_by_id(self.db.perakende_musteri_id)
                    if perakende_data:
                        self._on_cari_secildi_callback(perakende_data['id'], perakende_data['ad'])
            elif self.islem_tipi == self.db.SIPARIS_TIP_ALIS:
                # Tedarikçi Siparişi ise 'Genel Tedarikçi'yi seç
                if self.db.genel_tedarikci_id is not None:
                    genel_tedarikci_data = self.db.tedarikci_getir_by_id(self.db.genel_tedarikci_id)
                    if genel_tedarikci_data:
                        self._on_cari_secildi_callback(genel_tedarikci_data['id'], genel_tedarikci_data['ad'])

    def kaydet(self):
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR: Metot tamamen yeniden düzenlendi >>>
        s_no = self.sv_siparis_no.get().strip()
        durum = self.durum_combo.get()
        siparis_notlari = self.siparis_notlari_text.get("1.0", tk.END).strip()
        teslimat_tarihi = self.sv_teslimat_tarihi.get().strip()
        genel_iskonto_tipi = self.sv_genel_iskonto_tipi.get()
        genel_iskonto_degeri = self.db.safe_float(self.sv_genel_iskonto_degeri.get())

        if not s_no:
            messagebox.showerror("Eksik Bilgi", "Sipariş Numarası zorunludur.", parent=self.app)
            return
        if not self.secili_cari_id:
            messagebox.showerror("Eksik Bilgi", "Lütfen bir cari seçin.", parent=self.app)
            return
        if not self.fatura_kalemleri_ui:
            messagebox.showerror("Eksik Bilgi", "Siparişte en az bir ürün olmalı.", parent=self.app)
            return

        # Tüm hesaplamalar (KDV Tutarı, Toplamlar vb.) veritabanı tarafında yapılacak.
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
                self.duzenleme_id, s_no, self.islem_tipi, self.secili_cari_id, 0,
                durum, kalemler_to_db, siparis_notlari, teslimat_tarihi,
                genel_iskonto_tipi, genel_iskonto_degeri
            )
        else:
            success, message = self.db.siparis_ekle(
                s_no, self.islem_tipi, self.secili_cari_id, 0,
                durum, kalemler_to_db, siparis_notlari, teslimat_tarihi,
                genel_iskonto_tipi, genel_iskonto_degeri
            )

        if success:
            msg_title = "Sipariş Güncellendi" if self.duzenleme_id else "Sipariş Oluşturuldu"
            messagebox.showinfo(msg_title, message, parent=self.app)
            self.app.set_status(message)
            if self.yenile_callback:
                self.yenile_callback()
            
            if isinstance(self.winfo_toplevel(), tk.Toplevel):
                self.winfo_toplevel().destroy()
        else:
            messagebox.showerror("Hata", message, parent=self.app)

    def _mevcut_siparisi_yukle(self):
        # <<< DEĞİŞİKLİK BU METODUN İÇİNDE BAŞLIYOR >>>
        siparis_ana = self.db.get_siparis_by_id(self.duzenleme_id)
        if not siparis_ana:
            messagebox.showerror("Hata", "Düzenlenecek sipariş bilgileri alınamadı.", parent=self.app)
            if isinstance(self.winfo_toplevel(), tk.Toplevel): self.winfo_toplevel().destroy()
            return

        # Formu doldurma...
        self.s_no_e.config(state=tk.NORMAL)
        self.sv_siparis_no.set(siparis_ana['siparis_no'])
        self.s_no_e.config(state=tk.DISABLED)

        self.sv_siparis_tarihi.set(siparis_ana['tarih'])
        self.sv_teslimat_tarihi.set(siparis_ana['teslimat_tarihi'] if siparis_ana['teslimat_tarihi'] else "")
        
        self.durum_combo.set(siparis_ana['durum'])
        
        self.siparis_notlari_text.delete("1.0", tk.END)
        if siparis_ana['siparis_notlari']:
            self.siparis_notlari_text.insert("1.0", siparis_ana['siparis_notlari'])

        genel_iskonto_tipi_db = siparis_ana['genel_iskonto_tipi']
        genel_iskonto_degeri_db = siparis_ana['genel_iskonto_degeri']

        self.sv_genel_iskonto_tipi.set(genel_iskonto_tipi_db if genel_iskonto_tipi_db else "YOK")
        if genel_iskonto_tipi_db == 'YUZDE':
            self.sv_genel_iskonto_degeri.set(f"{self.db.safe_float(genel_iskonto_degeri_db):.2f}".replace('.', ',').rstrip('0').rstrip(','))
        elif genel_iskonto_tipi_db == 'TUTAR':
            self.sv_genel_iskonto_degeri.set(f"{self.db.safe_float(genel_iskonto_degeri_db):.2f}".replace('.', ','))
        else:
            self.sv_genel_iskonto_degeri.set("0,00")
        
        self._on_genel_iskonto_tipi_changed()

        c_id_db = siparis_ana['cari_id']
        cari_tip_for_callback = self.db.CARI_TIP_MUSTERI if siparis_ana['cari_tip'] == self.db.CARI_TIP_MUSTERI else self.db.CARI_TIP_TEDARIKCI
        cari_bilgi_for_display = self.db.musteri_getir_by_id(c_id_db) if cari_tip_for_callback == self.db.CARI_TIP_MUSTERI else self.db.tedarikci_getir_by_id(c_id_db)
        
        if cari_bilgi_for_display:
            kod_anahtari = 'kod' if 'kod' in cari_bilgi_for_display.keys() else 'tedarikci_kodu'
            display_text_for_cari = f"{cari_bilgi_for_display['ad']} (Kod: {cari_bilgi_for_display[kod_anahtari]})"
            self._on_cari_secildi_callback(c_id_db, display_text_for_cari)
        else:
            self._temizle_cari_secimi()

        siparis_kalemleri_db_list = self.db.get_siparis_kalemleri(self.duzenleme_id)
        self.fatura_kalemleri_ui = []
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
        
        self.after_idle(self._urunleri_yukle_ve_cachele_ve_goster)

    def _reset_form_for_new_siparis(self, skip_default_cari_selection=False):
        """
        Sipariş formundaki özel alanları yeni bir sipariş oluşturmak için sıfırlar.
        """
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR: Ürün yükleme çağrısı eklendi >>>

        next_siparis_no_prefix = "MS" if self.islem_tipi == self.db.SIPARIS_TIP_SATIS else "AS"
        generated_siparis_no = self.db.get_next_siparis_no(next_siparis_no_prefix)
        
        self.sv_siparis_no.set(generated_siparis_no)
        self.sv_siparis_tarihi.set(datetime.now().strftime('%Y-%m-%d'))
        self.sv_teslimat_tarihi.set((datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        
        if hasattr(self, 'durum_combo'): self.durum_combo.set(self.db.SIPARIS_DURUM_BEKLEMEDE)
        if hasattr(self, 'siparis_notlari_text'): self.siparis_notlari_text.delete("1.0", tk.END)

        if hasattr(self, 'sv_genel_iskonto_tipi'): self.sv_genel_iskonto_tipi.set(self.db.ISKONTO_TIP_YOK)
        if hasattr(self, 'sv_genel_iskonto_degeri'): self.sv_genel_iskonto_degeri.set("0,00")
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
        self.after_idle(self._urunleri_yukle_ve_cachele_ve_goster)
        
        if hasattr(self, 'urun_arama_entry'):
            self.urun_arama_entry.focus()
            
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
                kod_anahtari = 'tedarikci_kodu' if 'tedarikci_kodu' in selected_cari_data.keys() else 'musteri_kodu'
                display_text = f"{selected_cari_data['ad']} (Kod: {selected_cari_data[kod_anahtari]})"
                self._on_cari_secildi_callback(selected_cari_data['id'], display_text)
                self.app.set_status(f"Sipariş cari: {display_text} olarak önceden dolduruldu.")
            else:
                self.app.set_status("Önceden doldurulacak cari bulunamadı.")

        if self.initial_urunler:
            self.fatura_kalemleri_ui.clear()
            for urun_data in self.initial_urunler:
                urun_id = urun_data['id']
                miktar = urun_data['miktar']

                urun_db_info = self.db.stok_getir_by_id(urun_id)
                if not urun_db_info:
                    continue

                # Sipariş tipi Alış ise alış fiyatını, Satış ise satış fiyatını kullan
                # `birim_fiyat_kdv_haric` için `urun_db_info`'dan ilgili fiyatı çek
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
            self.app.set_status(f"Kritik stok ürünleri sepete eklendi.")
        logging.debug("_populate_from_initial_data_siparis metodu tamamlandı.")

class BaseGelirGiderListesi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref, islem_tipi):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.islem_tipi = islem_tipi # 'GELİR', 'GİDER' veya 'TÜMÜ'
        self.pack(expand=True, fill=tk.BOTH)
        self.after_id = None
        
        # Filtreleme alanı
        filter_frame = ttk.Frame(self)
        filter_frame.pack(pady=5, padx=10, fill=tk.X)

        ttk.Label(filter_frame, text="Başlangıç Tarihi:").pack(side=tk.LEFT, padx=(0,2))
        self.bas_tarih_entry = ttk.Entry(filter_frame, width=12)
        self.bas_tarih_entry.pack(side=tk.LEFT, padx=(0,5))
        self.bas_tarih_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        setup_date_entry(self.app, self.bas_tarih_entry)
        ttk.Button(filter_frame, text="🗓️", command=lambda: DatePickerDialog(self.app, self.bas_tarih_entry), width=3).pack(side=tk.LEFT, padx=2)
 
        ttk.Label(filter_frame, text="Bitiş Tarihi:").pack(side=tk.LEFT, padx=(0,2))
        self.bit_tarih_entry = ttk.Entry(filter_frame, width=12)
        self.bit_tarih_entry.pack(side=tk.LEFT, padx=(0,10))
        self.bit_tarih_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        setup_date_entry(self.app, self.bit_tarih_entry)
        ttk.Button(filter_frame, text="🗓️", command=lambda: DatePickerDialog(self.app, self.bit_tarih_entry), width=3).pack(side=tk.LEFT, padx=2)

        ttk.Label(filter_frame, text="Açıklama Ara:").pack(side=tk.LEFT, padx=(10,2))
        self.aciklama_arama_entry = ttk.Entry(filter_frame, width=30)
        self.aciklama_arama_entry.pack(side=tk.LEFT, padx=(0,5))
        self.aciklama_arama_entry.bind("<KeyRelease>", self._delayed_gg_listesi_yukle)

        ttk.Button(filter_frame, text="Filtrele ve Yenile", command=self.gg_listesini_yukle, style="Accent.TButton").pack(side=tk.LEFT, padx=(10,0))
        
        # Butonlar
        button_frame_gg = ttk.Frame(self)
        button_frame_gg.pack(pady=5, padx=10, fill=tk.X)
        ttk.Button(button_frame_gg, text="Yeni Manuel Kayıt Ekle", command=self.yeni_gg_penceresi_ac).pack(side=tk.LEFT, padx=(0,5))
        self.sil_button = ttk.Button(button_frame_gg, text="Seçili Manuel Kaydı Sil", command=self.secili_gg_sil, state=tk.DISABLED)
        self.sil_button.pack(side=tk.LEFT, padx=5)

        # --- Gelir/Gider Listesi (Treeview) ---
        tree_frame_gg = ttk.Frame(self, padding="10")
        tree_frame_gg.pack(expand=True, fill=tk.BOTH)

        # Sütun başlıkları (Yeni sıralamaya göre)
        cols_gg = ("Tarih", "Tip", "Açıklama", "Tutar", "Kasa/Banka Adı", "Kaynak", "ID", "Kaynak ID")
        self.gg_tree = ttk.Treeview(tree_frame_gg, columns=cols_gg, show='headings', selectmode="browse")

        # Sütun tanımlamaları (Yeni sıralama ve hizalamalara göre)
        col_defs_gg = [
            ("Tarih", 100, tk.CENTER, tk.NO),      # Ortalanmış tarih
            ("Tip", 80, tk.CENTER, tk.NO),         # Ortalanmış tip
            ("Açıklama", 300, tk.W, tk.YES),       # Sola hizalı (W - West), genişlesin
            ("Tutar", 120, tk.E, tk.NO),           # Sağa hizalı (E - East), parasal değerler için
            ("Kasa/Banka Adı", 120, tk.W, tk.NO),  # Sola hizalı (W - West)
            ("Kaynak", 100, tk.CENTER, tk.NO),     # Ortalanmış kaynak
            ("ID", 60, tk.CENTER, tk.NO),          # Ortalanmış ID
            ("Kaynak ID", 80, tk.CENTER, tk.NO)    # Ortalanmış kaynak ID
        ]

        for cn, w, a, s in col_defs_gg:
            self.gg_tree.column(cn, width=w, anchor=a, stretch=s)
            self.gg_tree.heading(cn, text=cn, command=lambda _c=cn: sort_treeview_column(self.gg_tree, _c, False))
        
        # <<< RENK TAGLERİNİ TEKRAR GÜNCELLEDİK VE UYGULAMA MANTIĞINI GELİŞTİRDİK >>>
        # Treeview için genel bir stil oluşturalım veya var olanı alalım
        style = ttk.Style()
        
        # AWdark temasının varsayılan renklerini override etmeye çalışalım
        # 'clam' teması gibi bazı temalarda 'fieldbackground' ve 'background' arasındaki fark önemli olabilir.
        # Genellikle, Treeview'in satırları 'fieldbackground' ile kontrol edilir.
        style.configure("Treeview", 
                        fieldbackground="white", # <-- BURAYI "white" YAPIN
                        background="white",      # <-- BURAYI DA "white" YAPIN
                        foreground="black", # Metin rengi siyah olsun
                        rowheight=25)
        
        style.configure("Treeview.Heading", font=('Segoe UI', 9, 'bold'))

        # Taglerin varsayılan seçili olmayan durumdaki rengi ezmesi için map kullanalım.
        # Bu, seçili olmayan satırların themes tarafından ezilmesini önlemeye yardımcı olabilir.
        style.map('Treeview',
                  fieldbackground=[('selected', '#32679F')], # Seçili satırın arka planı
                  foreground=[('selected', 'white')], # Seçili satırın metin rengi
                  background=[('selected', '#32679F')]) # Sadece seçili durumu burada map'le.
                                                        # Seçili olmayan durumu tag_configure'a bırak.


        # Renk taglerini tanımla. Bunlar artık 'fieldbackground' yerine doğrudan 'background'ı hedefleyecek.
        # Bazı temalarda 'background' etiketi çalışmayabilir, o zaman 'fieldbackground' denenebilir.
        self.gg_tree.tag_configure('manuel_kayit', background='#DCEFFB') # Açık Mavi, foreground varsayılan kalır
        self.gg_tree.tag_configure('gelir_kayit', background='#D5F5E3')  # Açık Yeşil
        self.gg_tree.tag_configure('gider_kayit', background='#FADBD8')  # Açık Kırmızı

        # Metin renklerini de tanımlayalım ki tema ezmesin
        self.gg_tree.tag_configure('gelir_kayit_text', foreground='green') # Yeşil metin (isteğe bağlı)
        self.gg_tree.tag_configure('gider_kayit_text', foreground='red')   # Kırmızı metin (isteğe bağlı)
        self.gg_tree.tag_configure('manuel_kayit_text', foreground='navy') # Mavi metin (isteğe bağlı)


        vsb_gg = ttk.Scrollbar(tree_frame_gg, orient="vertical", command=self.gg_tree.yview)
        vsb_gg.pack(side=tk.RIGHT, fill=tk.Y)
        self.gg_tree.configure(yscrollcommand=vsb_gg.set)
        self.gg_tree.pack(expand=True, fill=tk.BOTH)
        self.gg_tree.bind("<<TreeviewSelect>>", self.on_tree_select)


        # Sayfalama için gerekli değişkenler ve widget'lar
        self.kayit_sayisi_per_sayfa = 20
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0

        pagination_frame_gg = ttk.Frame(self)
        pagination_frame_gg.pack(fill=tk.X, padx=10, pady=5, side=tk.BOTTOM)

        ttk.Button(pagination_frame_gg, text="Önceki Sayfa", command=self.onceki_sayfa).pack(side=tk.LEFT, padx=5)
        self.sayfa_bilgisi_label = ttk.Label(pagination_frame_gg, text="Sayfa 1 / 1")
        self.sayfa_bilgisi_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(pagination_frame_gg, text="Sonraki Sayfa", command=self.sonraki_sayfa).pack(side=tk.LEFT, padx=5)
        
        self.gg_listesini_yukle() # İlk yüklemeyi yap

    def on_tree_select(self, event):
        """Treeview'de bir öğe seçildiğinde silme butonunun durumunu ayarlar."""
        selected_item_iid = self.gg_tree.focus() # Doğru Treeview referansı
        can_delete = False
        
        if selected_item_iid:
            item_data = self.gg_tree.item(selected_item_iid)
            # `values` listesinden doğru indeks ile `kaynak` bilgisini alın.
            # Sizin `cols_gg` tanımınıza göre 'Kaynak' 6. sütun (indeks 5).
            kaynak_bilgisi = item_data['values'][5] # Kaynak sütunu (örneğin 'MANUEL', 'FATURA', 'TAHSILAT' vb.)
            
            # Sadece 'MANUEL' kaynaklı kayıtlar silinebilir.
            if kaynak_bilgisi == 'MANUEL':
                can_delete = True
            
        self.sil_button.config(state=tk.NORMAL if can_delete else tk.DISABLED)

    def _delayed_gg_listesi_yukle(self, event):
        if self.after_id:
            self.after_cancel(self.after_id)
        self.after_id = self.after(300, self.gg_listesini_yukle)

    def gg_listesini_yukle(self):
        for i in self.gg_tree.get_children():
            self.gg_tree.delete(i)
        
        bas_t = self.bas_tarih_entry.get()
        bit_t = self.bit_tarih_entry.get()
        tip_f = self.islem_tipi if self.islem_tipi != "TÜMÜ" else None
        aciklama_f = self.aciklama_arama_entry.get().strip()

        try:
            if bas_t: datetime.strptime(bas_t, '%Y-%m-%d')
            if bit_t: datetime.strptime(bit_t, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Tarih Formatı Hatası","Tarih formati 'YYYY-AA-GG' şeklinde olmalıdır.", parent=self.app)
            return

        # <<< BURADA VERİTABANI ÇAĞRISINI DÜZELTİYORUZ >>>
        # Eksik olan sayfalama parametrelerini ve diğer filtreleri ekleyelim.
        # Ayrıca, `gelir_gider_listele` fonksiyonundan dönen veriyi işlemek için döngü ekleyelim.
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
            self.gg_tree.insert("", tk.END, values=("", "", "", "", "Kayıt Bulunamadı", "", "", ""))
            self.app.set_status("Hiç gelir/gider kaydı bulunamadı.")
        else:
            for gg in gelir_gider_kayitlari:
                tarih_formatted = gg['tarih'].strftime('%d.%m.%Y') if isinstance(gg['tarih'], (date, datetime)) else str(gg['tarih'])
                tutar_formatted = self.db._format_currency(gg['tutar'])
                
                tags = [] # Etiketleri liste olarak başlat
                kaynak = gg['kaynak']
                tip = gg['tip'] # Kayıt tipini al (GELİR veya GİDER)

                # Kaynak ve tipe göre tag ataması
                if kaynak == 'MANUEL':
                    tags.append('manuel_kayit')
                    tags.append('manuel_kayit_text') # Metin rengi tag'i
                
                if tip == 'GELİR':
                    tags.append('gelir_kayit')
                    tags.append('gelir_kayit_text') # Metin rengi tag'i
                elif tip == 'GİDER':
                    tags.append('gider_kayit')
                    tags.append('gider_kayit_text') # Metin rengi tag'i
                
                # Tag listesini tuple'a çevirerek insert metoduna veriyoruz
                self.gg_tree.insert("", tk.END, values=(
                    gg['id'],
                    tarih_formatted,
                    gg['tip'],
                    tutar_formatted,
                    gg['aciklama'] if gg['aciklama'] else "-",
                    kaynak if kaynak else "-",
                    gg['kaynak_id'] if gg['kaynak_id'] else "-",
                    gg['kasa_banka_adi'] if gg['kasa_banka_adi'] else "-"
                ), iid=gg['id'], tags=tuple(tags)) # tags parametresini tuple'a dönüştürerek ekleyin
            
            # Toplam kayıt sayısını da güncelle
            self.toplam_kayit_sayisi = self.db.get_gelir_gider_count(
                baslangic_tarih=bas_t if bas_t else None,
                bitis_tarih=bit_t if bit_t else None,
                tip_filtre=tip_f,
                aciklama_filtre=aciklama_f
            )
            toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
            if toplam_sayfa == 0: toplam_sayfa = 1

            self.app.set_status(f"{len(gelir_gider_kayitlari)} gelir/gider kaydı listelendi. Toplam {self.toplam_kayit_sayisi} kayıt.")
            self.sayfa_bilgisi_label.config(text=f"Sayfa {self.mevcut_sayfa} / {toplam_sayfa}")

        self.on_tree_select(None) # Buton durumlarını güncelleyin


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
        from pencereler import YeniGelirGiderEklePenceresi
        YeniGelirGiderEklePenceresi(self.app, self.db, self.gg_listesini_yukle, initial_tip=initial_tip)
        self.app.set_status(f"Yeni manuel {initial_tip.lower()} kayıt penceresi açıldı.")
    
    def secili_gg_sil(self):
        selected_item_iid = self.gg_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen silmek için listeden bir kayıt seçin.", parent=self.app)
            return

        vals_gg = self.gg_tree.item(selected_item_iid, 'values')
        kaynak_bilgisi = vals_gg[5]

        if kaynak_bilgisi != 'MANUEL':
            messagebox.showwarning("Silme Engellendi", "Sadece 'MANUEL' kaynaklı kayıtlar silinebilir.\nOtomatik oluşan kayıtlar (Fatura, Tahsilat, Ödeme vb.) ilgili modüllerden yönetilmelidir.", parent=self.app)
            return

        aciklama_gg = vals_gg[4]
        if messagebox.askyesno("Silme Onayı", f"'{aciklama_gg}' açıklamalı manuel kaydı silmek istediğinizden emin misiniz?", parent=self.app):
            success, message = self.db.gelir_gider_sil(selected_item_iid)
            if success:
                messagebox.showinfo("Başarılı", message, parent=self.app)
                self.gg_listesini_yukle()
                self.app.set_status(message)
            else:
                messagebox.showerror("Hata", message, parent=self.app)


class GelirListesi(BaseGelirGiderListesi):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent, db_manager, app_ref, islem_tipi='GELİR')

class GiderListesi(BaseGelirGiderListesi):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent, db_manager, app_ref, islem_tipi='GİDER')

class BaseFinansalIslemSayfasi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref, islem_tipi):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.islem_tipi = islem_tipi
        self.pack(expand=True, fill=tk.BOTH)

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
        ttk.Label(self, text=baslik_text, font=("Segoe UI", 16, "bold")).pack(pady=(10, 20), anchor=tk.W, padx=10)

        # Giriş Formu Çerçevesi
        entry_frame = ttk.Frame(self, padding="15")
        entry_frame.pack(padx=10, pady=5, fill=tk.X, expand=False)


        # Cari Seçimi
        cari_label_text = "Müşteri (*):" if self.islem_tipi == 'TAHSILAT' else "Tedarikçi (*):"
        ttk.Label(entry_frame, text=cari_label_text).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        # Doğru tanımlama: self.cari_combo
        self.cari_combo = ttk.Combobox(entry_frame, width=35, state="normal")
        self.cari_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)

        # Bağlamalar (binds) da cari_combo'yu kullanmalı
        self.cari_combo.bind("<KeyRelease>", self._filtre_carileri_anlik)
        self.cari_combo.bind("<FocusOut>", self._cari_secimi_dogrula)
        self.cari_combo.bind("<<ComboboxSelected>>", self._on_cari_selected)
        self.cari_combo.bind("<Return>", self._on_cari_selected)

        self.lbl_cari_bakiye = ttk.Label(entry_frame, text="Bakiye: Yükleniyor...", font=("Segoe UI", 10, "bold"))
        self.lbl_cari_bakiye.grid(row=0, column=2, columnspan=2, sticky=tk.W, padx=5, pady=5)

        # Tarih
        ttk.Label(entry_frame, text="Tarih (*):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.tarih_entry = ttk.Entry(entry_frame, width=12)
        self.tarih_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        self.tarih_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        setup_date_entry(self.app, self.tarih_entry)
        ttk.Button(entry_frame, text="🗓️", command=lambda: DatePickerDialog(self.app, self.tarih_entry), width=3).grid(row=1, column=2, padx=2, pady=5, sticky=tk.W)

        # Tutar
        ttk.Label(entry_frame, text="Tutar (TL) (*):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.tutar_entry = ttk.Entry(entry_frame, width=15)
        self.tutar_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        setup_numeric_entry(self.app, self.tutar_entry, allow_negative=False, decimal_places=2)

        # Ödeme Şekli
        ttk.Label(entry_frame, text="Ödeme Şekli (*):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.odeme_sekli_combo = ttk.Combobox(entry_frame, width=20, state="readonly", 
                                            values=[self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, # <-- Düzeltildi
                                                    self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, # <-- Düzeltildi
                                                    self.db.ODEME_TURU_SENET]) # <-- Düzeltildi
        self.odeme_sekli_combo.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        self.odeme_sekli_combo.current(0)
        # Ödeme şekli değişince varsayılan kasa/banka seçimi için bind ekleyin
        self.odeme_sekli_combo.bind("<<ComboboxSelected>>", self._odeme_sekli_degisince)

        # İşlem Kasa/Banka
        ttk.Label(entry_frame, text="İşlem Kasa/Banka (*):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.kasa_banka_combo = ttk.Combobox(entry_frame, width=35, state="readonly")
        self.kasa_banka_combo.grid(row=4, column=1, padx=5, pady=5, sticky=tk.EW)

        # Açıklama
        ttk.Label(entry_frame, text="Açıklama (*):").grid(row=5, column=0, sticky=tk.NW, padx=5, pady=5)
        self.aciklama_text = tk.Text(entry_frame, width=35, height=4, font=('Segoe UI', 9))
        self.aciklama_text.grid(row=5, column=1, padx=5, pady=5, sticky=tk.EW)

        entry_frame.columnconfigure(1, weight=1)

        # Kaydet Butonu
        button_frame = ttk.Frame(self, padding="10")
        button_frame.pack(pady=10, padx=10, fill=tk.X, expand=False)
        ttk.Button(button_frame, text="Kaydet", command=self.kaydet_islem, style="Accent.TButton").pack(pady=10)

        # Hızlı İşlem Listesi (son 10 işlem gibi)
        recent_transactions_frame = ttk.LabelFrame(self, text="Son İşlemler", padding="10")
        recent_transactions_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        cols_recent = ("Tarih", "Tip", "Tutar", "Açıklama", "Kasa/Banka")
        self.tree_recent_transactions = ttk.Treeview(recent_transactions_frame, columns=cols_recent, show='headings', selectmode="none", height=8)

        col_defs_recent = [
            ("Tarih", 90, tk.CENTER, tk.NO),
            ("Tip", 70, tk.CENTER, tk.NO),
            ("Tutar", 120, tk.E, tk.NO),
            ("Açıklama", 350, tk.W, tk.YES),
            ("Kasa/Banka", 100, tk.W, tk.NO)
        ]
        for cn,w,a,s in col_defs_recent:
            self.tree_recent_transactions.column(cn, width=w, anchor=a, stretch=s)
            self.tree_recent_transactions.heading(cn, text=cn)

        vsb_recent = ttk.Scrollbar(recent_transactions_frame, orient="vertical", command=self.tree_recent_transactions.yview)
        vsb_recent.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_recent_transactions.configure(yscrollcommand=vsb_recent.set)
        self.tree_recent_transactions.pack(expand=True, fill=tk.BOTH)

        # Buradaki çağrıları doğru yerlere taşıyoruz.
        # İlk yüklemede, bu metodlar tüm widgetlar tanımlandıktan sonra çağrılmalı.
        self._yukle_ve_cachele_carileri()
        self._yukle_kasa_banka_hesaplarini()

        # cari_combo boş değilse ilk öğeyi seçin.
        if self.cari_combo['values']:
            self.cari_combo.current(0)
        self._on_cari_selected() # _on_cari_selected çağrılınca _load_recent_transactions de çağrılır

        # İlk olarak ödeme şeklini tetikleyerek varsayılan kasa/bankayı ayarla
        self._odeme_sekli_degisince()
        
    def _yukle_ve_cachele_carileri(self):
        self.tum_cariler_cache = []
        self.cari_map = {} # Görünen metin -> ID
        if self.islem_tipi == 'TAHSILAT':
            self.tum_cariler_cache = self.db.musteri_listesi_al(perakende_haric=True)
        elif self.islem_tipi == 'ODEME':
            self.tum_cariler_cache = self.db.tedarikci_listesi_al()

        display_values = [] # display_values listesi burada yeniden oluşturulacak
        for c in self.tum_cariler_cache:
            display_text = f"{c[2]} (Kod: {c[1]})"
            self.cari_map[display_text] = c[0]
            display_values.append(display_text)

        # self.cari_combo['values'] güncellenmeli
        self.cari_combo['values'] = display_values
        # İlk seçeneği ayarlarken, listenin boş olma durumunu kontrol etmeliyiz.
        if len(display_values) > 0:
            if self.islem_tipi == 'TAHSILAT' and str(self.db.perakende_musteri_id) in [str(self.cari_map[k]) for k in self.cari_map.keys()]:
                self.cari_combo.set("") # Perakende müşteriyi seçilmemesi için boş bırak
            else:
                self.cari_combo.current(0)
        else:
            self.cari_combo.set("") # Eğer hiç cari yoksa boş bırak


    def _load_recent_transactions(self):
        for i in self.tree_recent_transactions.get_children():
            self.tree_recent_transactions.delete(i)

        selected_cari_text = self.cari_combo.get()
        cari_id = self.cari_map.get(selected_cari_text)

        if cari_id is None:
            self.tree_recent_transactions.insert("", tk.END, values=("", "", "", "Cari seçilmedi.", ""))
            return

        recent_data = self.db.get_recent_cari_hareketleri(self.cari_tip, int(cari_id), limit=10)

        if not recent_data:
            self.tree_recent_transactions.insert("", tk.END, values=("", "", "", "Son işlem bulunamadı.", ""))
            return

        for item in recent_data:
            # item[0] zaten bir tarih nesnesi, strptime'a gerek yok.
            tarih_obj = item[0]
            if isinstance(tarih_obj, (date, datetime)):
                tarih_formatted = tarih_obj.strftime('%d.%m.%Y')
            else:
                # Beklenmedik bir durum olursa, string'e çevirip devam et
                tarih_formatted = str(tarih_obj)

            tutar_formatted = self.db._format_currency(item[2])

            self.tree_recent_transactions.insert("", tk.END, values=(
                tarih_formatted,
                item[1],
                tutar_formatted,
                item[3],
                item[4] if item[4] else "-"
            ))


    def _filtre_carileri_anlik(self, event=None):
        """
        Cari arama combobox'ına yazıldıkça cari listesini anlık olarak filtreler.
        Arama terimine göre eşleşen carileri Combobox'ın values'ına atar.
        """
        current_text_in_cb = self.cari_combo.get()
        arama_terimi = current_text_in_cb.lower().strip() # Kullanıcının girdiği metni al

        # Cache'lenmiş tüm cariler üzerinden filtreleme yap
        # cari_map, anahtar olarak "Ad (Kod: ...)" formatında metin tutar.
        filtered_display_values = [
            display_text for display_text in self.cari_map.keys()
            if arama_terimi in display_text.lower()
        ]

        # Combobox'ın gösterilen değerlerini filtreli liste ile güncelleyin
        # Bu, yazdıkça açılır menünün daralmasını sağlayacaktır.
        if filtered_display_values:
            self.cari_combo['values'] = sorted(filtered_display_values)
        else:
            # Eşleşme yoksa, tüm listeyi göster
            self.cari_combo['values'] = sorted(list(self.cari_map.keys()))

        # Combobox'ın içindeki metnin, kullanıcının yazdığı son metin olduğundan emin olun.
        self.cari_combo.set(current_text_in_cb)

    def _odeme_sekli_degisince(self, event=None):
        selected_odeme_sekli = self.odeme_sekli_combo.get()
        varsayilan_kb_db = self.db.get_kasa_banka_by_odeme_turu(selected_odeme_sekli)

        if varsayilan_kb_db:
            varsayilan_kb_id = varsayilan_kb_db[0]
            found_and_set = False
            for text, id_val in self.kasa_banka_map.items():
                if id_val == varsayilan_kb_id:
                    self.kasa_banka_combo.set(text) # Düzeltildi: self.kasa_banka_combo
                    found_and_set = True
                    break
            if not found_and_set and len(self.kasa_banka_combo['values']) > 1: # Düzeltildi: self.kasa_banka_combo
                self.kasa_banka_combo.current(1) # Düzeltildi: self.kasa_banka_combo
        elif len(self.kasa_banka_combo['values']) > 0: # Düzeltildi: self.kasa_banka_combo
            self.kasa_banka_combo.current(0) # Düzeltildi: self.kasa_banka_combo

    def _cari_secimi_dogrula(self, event=None):
        current_text = self.cari_combo.get().strip() # self.cari_combo
        if current_text and current_text not in self.cari_map:
            messagebox.showwarning("Geçersiz Cari", "Seçili müşteri/tedarikçi listede bulunamadı.\nLütfen listeden geçerli bir seçim yapın veya yeni bir cari ekleyin.", parent=self.app)
            self.cari_combo.set("") # self.cari_combo
            self.lbl_cari_bakiye.config(text="", foreground="black")
        self._on_cari_selected()

    def _on_cari_selected(self, event=None):
        # Burada self.cari_combo kullanmalıyız.
        secili_cari_text = self.cari_combo.get() 
        secilen_cari_id = self.cari_map.get(secili_cari_text)

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
            self.lbl_cari_bakiye.config(text=bakiye_text, foreground=bakiye_color)
        else:
            self.lbl_cari_bakiye.config(text="")

        self._load_recent_transactions() # Seçim değişince son işlemleri de yükle

    def _yukle_carileri(self):
        """Tüm carileri (müşteri veya tedarikçi) veritabanından çeker ve listeler."""
        self.tum_cariler_cache_data = [] # Data tuple'larını saklar: (id, kod, ad, ...)
        self.cari_map_display_to_id = {} # Sadece pop-up içinde kullanılacak, ana formunkinden farklı
        
        if self.fatura_tipi == 'SATIŞ':
            cariler_db = self.db.musteri_listesi_al(perakende_haric=False) # Perakende müşteriyi de al
        else: # ALIŞ
            cariler_db = self.db.tedarikci_listesi_al()
        
        for c in cariler_db: # c: sqlite3.Row objesi
            cari_id = c['id']
            cari_ad = c['ad']
            
            cari_kodu = ""
            try:
                if self.fatura_tipi == 'SATIŞ':
                    cari_kodu = c['kod']
                else: # ALIŞ
                    cari_kodu = c['tedarikci_kodu']
            except KeyError:
                cari_kodu = "" # Eğer kod sütunu yoksa (beklenmeyen durum) boş bırak
            
            display_text = f"{cari_ad} (Kod: {cari_kodu})" # Ad (Kod)
            self.cari_map_display_to_id[display_text] = str(cari_id) # ID'yi string olarak sakla
            self.tum_cariler_cache_data.append(c) # Tüm cari data tuple'larını cache'le
        
        self._filtre_liste() # Tüm listeyi göster (boş arama terimiyle)

        # Varsayılan seçimi yap
        default_id_str = None
        if self.fatura_tipi == 'SATIŞ' and self.db.perakende_musteri_id is not None:
            default_id_str = str(self.db.perakende_musteri_id)
        elif self.fatura_tipi == 'ALIŞ' and self.db.genel_tedarikci_id is not None:
            default_id_str = str(self.db.genel_tedarikci_id)
        
        if default_id_str:
            # Treeview'de bu varsayılan öğeyi bul ve seçili yap
            for item_id in self.cari_tree.get_children():
                tree_item_data = self.cari_tree.item(item_id, 'values')
                if item_id == default_id_str: 
                    self.cari_tree.selection_set(item_id)
                    self.cari_tree.focus(item_id)
                    self.cari_tree.see(item_id)
                    break

    def _yukle_kasa_banka_hesaplarini(self):
        """Kasa/Banka hesaplarını veritabanından çeker ve ilgili combobox'ı doldurur."""
        # self.islem_hesap_cb'nin varlığını kontrol edelim, yoksa pas geçelim
        if not hasattr(self, 'islem_hesap_cb') or self.islem_hesap_cb is None:
            return

        self.islem_hesap_cb['values'] = [""]
        self.kasa_banka_map.clear()
        hesaplar = self.db.kasa_banka_listesi_al()
        display_values = [""] 
        if hesaplar:
            for h_id, h_ad, h_no, h_bakiye, h_para_birimi, h_tip, h_acilis_tarihi, h_banka, h_sube_adi, h_varsayilan_odeme_turu in hesaplar: 
                display_text = f"{h_ad} ({h_tip})" # hesap_adi (tip)
                if h_tip == "BANKA" and h_banka:
                    display_text += f" - {h_banka}" # banka_adi
                if h_tip == "BANKA" and h_no:
                    display_text += f" ({h_no})" # hesap_no
                self.kasa_banka_map[display_text] = h_id # display_text -> id
                display_values.append(display_text)
            self.islem_hesap_cb['values'] = display_values
            self.islem_hesap_cb.set("") # Başlangıçta boş veya varsayılan seçimi ayarlarız

            # Eğer varsayılan bir hesap yoksa, ilk geçerli hesabı seçmeye çalış
            if len(display_values) > 1:
                # İlk hesap boş string olduğu için ikinci elemandan başlarız
                self.islem_hesap_cb.current(1) 

        else:
            self.islem_hesap_cb['values'] = ["Hesap Yok"]
            self.islem_hesap_cb.current(0)
            self.islem_hesap_cb.config(state=tk.DISABLED)

    def kaydet_islem(self):
        secili_cari_str = self.cari_combo.get()
        tarih_str = self.tarih_entry.get().strip()
        tutar_str = self.tutar_entry.get().strip()
        odeme_sekli_str = self.odeme_sekli_combo.get()
        aciklama_str = self.aciklama_text.get("1.0", tk.END).strip()
        secili_kasa_banka_str = self.kasa_banka_combo.get()

        cari_id_val = None
        if secili_cari_str and secili_cari_str in self.cari_map:
            cari_id_val = self.cari_map[secili_cari_str]
        else:
            messagebox.showerror("Eksik Bilgi", "Lütfen geçerli bir müşteri/tedarikçi seçin.", parent=self.app)
            return

        kasa_banka_id_val = None
        if secili_kasa_banka_str and secili_kasa_banka_str != "Hesap Yok" and secili_kasa_banka_str in self.kasa_banka_map:
            kasa_banka_id_val = self.kasa_banka_map[secili_kasa_banka_str]
        else:
            messagebox.showerror("Eksik Bilgi", "Lütfen bir İşlem Kasa/Banka hesabı seçin.", parent=self.app)
            return

        if not all([tarih_str, tutar_str, odeme_sekli_str, aciklama_str]):
            messagebox.showerror("Eksik Bilgi", "Lütfen tüm zorunlu (*) alanları doldurun.", parent=self.app)
            return

        try:
            tutar_f = float(tutar_str.replace(',', '.'))
            if tutar_f <= 0:
                messagebox.showerror("Geçersiz Tutar", "Tutar pozitif bir sayı olmalıdır.", parent=self.app)
                return
        except ValueError:
            messagebox.showerror("Giriş Hatası", "Tutar sayısal bir değer olmalıdır.", parent=self.app)
            return

        result_tuple = (False, "İşlem kaydedilemedi.")
        if self.islem_tipi == 'TAHSILAT':
            result_tuple = self.db.tahsilat_ekle(cari_id_val, tarih_str, tutar_f, odeme_sekli_str, aciklama_str, kasa_banka_id_val)
        elif self.islem_tipi == 'ODEME':
            result_tuple = self.db.odeme_ekle(cari_id_val, tarih_str, tutar_f, odeme_sekli_str, aciklama_str, kasa_banka_id_val)

        success, message = result_tuple
        if success:
            messagebox.showinfo("Başarılı", message, parent=self.app)
            self.app.set_status(f"{self.db._format_currency(tutar_f)} tutarındaki {self.islem_tipi.lower()} '{secili_cari_str}' için kaydedildi.")
            self.cari_combo.set("")
            self.tarih_entry.delete(0, tk.END)
            self.tarih_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
            self.tutar_entry.delete(0, tk.END)
            self.odeme_sekli_combo.current(0)
            self.aciklama_text.delete("1.0", tk.END)
            self.kasa_banka_combo.set("")
            self.cari_combo.focus_set()

            if hasattr(self.app, 'gelir_gider_sayfasi'):
                if hasattr(self.app.gelir_gider_sayfasi.gelir_listesi_frame, 'gg_listesini_yukle'):
                    self.app.gelir_gider_sayfasi.gelir_listesi_frame.gg_listesini_yukle()
                if hasattr(self.app.gelir_gider_sayfasi.gider_listesi_frame, 'gg_listesini_yukle'):
                    self.app.gelir_gider_sayfasi.gider_listesi_frame.gg_listesini_yukle()
            if hasattr(self.app, 'kasa_banka_yonetimi_sayfasi') and hasattr(self.app.kasa_banka_yonetimi_sayfasi, 'hesap_listesini_yenile'):
                self.app.kasa_banka_yonetimi_sayfasi.hesap_listesini_yenile()
            self._on_cari_selected()
        else:
            messagebox.showerror("Hata", message, parent=self.app)
            self.app.set_status(f"{self.islem_tipi} kaydedilemedi: {message}")
            self._load_recent_transactions()


class TahsilatSayfasi(BaseFinansalIslemSayfasi):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent, db_manager, app_ref, islem_tipi='TAHSILAT')


class OdemeSayfasi(BaseFinansalIslemSayfasi):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent, db_manager, app_ref, islem_tipi='ODEME')


class RaporlamaMerkeziSayfasi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.pack(expand=True, fill=tk.BOTH)

        # --- Temel Sınıf Özellikleri ---
        self.aylik_satis_verileri = []
        self.aylik_gelir_gider_verileri = []
        self.aylik_kar_maliyet_verileri = []
        self.aylik_nakit_akis_verileri = []
        self.top_satis_urunleri = []
        self.cari_yaslandirma_data = {'musteri_alacaklari': {}, 'tedarikci_borclari': {}}
        self.stok_envanter_ozet = []

        # --- Ana UI Elemanları ---
        ttk.Label(self, text="Finansal Raporlar ve Analiz Merkezi", font=("Segoe UI", 22, "bold")).pack(pady=(10, 5), anchor=tk.W, padx=10)

        # Filtreleme ve Rapor Oluşturma Kontrolleri (Üst kısımda her zaman görünür)
        filter_control_frame = ttk.Frame(self, padding="10")
        filter_control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_control_frame, text="Başlangıç Tarihi:").pack(side=tk.LEFT, padx=(0, 2))
        self.bas_tarih_entry = ttk.Entry(filter_control_frame, width=12)
        self.bas_tarih_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.bas_tarih_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        setup_date_entry(self.app, self.bas_tarih_entry)

        ttk.Button(filter_control_frame, text="🗓️", command=lambda: self._open_date_picker(self.bas_tarih_entry), width=3).pack(side=tk.LEFT, padx=2)

        ttk.Label(filter_control_frame, text="Bitiş Tarihi:").pack(side=tk.LEFT, padx=(0, 2))
        self.bit_tarih_entry = ttk.Entry(filter_control_frame, width=12)
        self.bit_tarih_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.bit_tarih_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        setup_date_entry(self.app, self.bit_tarih_entry)

        ttk.Button(filter_control_frame, text="🗓️", command=lambda: self._open_date_picker(self.bit_tarih_entry), width=3).pack(side=tk.LEFT, padx=2)

        ttk.Button(filter_control_frame, text="Rapor Oluştur/Yenile", command=self.raporu_olustur_ve_yenile, style="Accent.TButton").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(filter_control_frame, text="Raporu Yazdır (PDF)", command=self.raporu_pdf_yazdir_placeholder).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_control_frame, text="Raporu Dışa Aktar (Excel)", command=self.raporu_excel_aktar_placeholder).pack(side=tk.LEFT, padx=5)


        # Rapor sekmeleri için ana Notebook
        self.report_notebook = ttk.Notebook(self)
        self.report_notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        # Sekme 1: Genel Bakış (Dashboard)
        self.tab_genel_bakis = ttk.Frame(self.report_notebook, padding="15")
        self.report_notebook.add(self.tab_genel_bakis, text="📊 Genel Bakış")
        self._create_genel_bakis_tab(self.tab_genel_bakis)

        # Sekme 2: Satış Raporları
        self.tab_satis_raporlari = ttk.Frame(self.report_notebook, padding="15")
        self.report_notebook.add(self.tab_satis_raporlari, text="📈 Satış Raporları")
        self._create_satis_raporlari_tab(self.tab_satis_raporlari)

        # Sekme 3: Kâr ve Zarar
        self.tab_kar_zarar = ttk.Frame(self.report_notebook, padding="15")
        self.report_notebook.add(self.tab_kar_zarar, text="💰 Kâr ve Zarar")
        self._create_kar_zarar_tab(self.tab_kar_zarar)

        # Sekme 4: Nakit Akışı
        self.tab_nakit_akisi = ttk.Frame(self.report_notebook, padding="15")
        self.report_notebook.add(self.tab_nakit_akisi, text="🏦 Nakit Akışı")
        self._create_nakit_akisi_tab(self.tab_nakit_akisi)

        # Sekme 5: Cari Hesap Raporları
        self.tab_cari_hesaplar = ttk.Frame(self.report_notebook, padding="15")
        self.report_notebook.add(self.tab_cari_hesaplar, text="👥 Cari Hesaplar")
        self._create_cari_hesaplar_tab(self.tab_cari_hesaplar)

        # Sekme 6: Stok Raporları
        self.tab_stok_raporlari = ttk.Frame(self.report_notebook, padding="15")
        self.report_notebook.add(self.tab_stok_raporlari, text="📦 Stok Raporları")
        self._create_stok_raporlari_tab(self.tab_stok_raporlari)

        # Rapor notebook sekmesi değiştiğinde güncellemeleri tetikle
        self.report_notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

        # Başlangıçta raporları oluştur (Bu, ilk sekmenin içeriğini yükler)
        self.raporu_olustur_ve_yenile()

    # --- Ortak Yardımcı Metotlar ---
    def _open_date_picker(self, target_entry):
        """Bir Entry widget'ı için tarih seçici penceresi açar."""
        DatePickerDialog(self.app, target_entry)

    def _draw_plot(self, parent_frame, canvas_obj, ax_obj, title, labels, values, plot_type='bar', colors=None, bar_width=0.8, rotation=0, show_legend=True, label_prefix="", show_labels_on_bars=False, tight_layout_needed=True, group_labels=None):
        # Mevcut grafiği temizle (eğer varsa)
        if canvas_obj:
            canvas_obj.get_tk_widget().destroy()
            plt.close(ax_obj.figure)

        parent_width = parent_frame.winfo_width()
        parent_height = parent_frame.winfo_height()

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
            canvas = FigureCanvasTkAgg(fig, master=parent_frame)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            canvas.draw()
            return canvas, ax

        # Veri doluysa çizim yap
        if plot_type == 'bar':
            bar_label = group_labels[0] if group_labels and len(group_labels) > 0 else title # Eğer group_labels varsa ilkini kullan, yoksa title'ı kullan
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

        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        canvas.draw()

        return canvas, ax
    
    # --- Rapor Sekmelerinin Oluşturma Metotları ---
    def _create_genel_bakis_tab(self, parent_frame):
        parent_frame.columnconfigure(0, weight=1)
        parent_frame.columnconfigure(1, weight=1)
        parent_frame.rowconfigure(0, weight=0)
        parent_frame.rowconfigure(1, weight=1)

        metrics_frame = ttk.Frame(parent_frame)
        metrics_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0,10), padx=5)
        metrics_frame.columnconfigure((0,1,2,3), weight=1)

        self.card_total_sales = self._create_metric_card(metrics_frame, "Toplam Satış (KDV Dahil)", "0.00 TL", "sales")
        self.card_total_sales.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        self.card_total_collections = self._create_metric_card(metrics_frame, "Toplam Tahsilat", "0.00 TL", "collections")
        self.card_total_collections.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        self.card_total_payments = self._create_metric_card(metrics_frame, "Toplam Ödeme", "0.00 TL", "payments")
        self.card_total_payments.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")

        self.card_net_cash_flow = self._create_metric_card(metrics_frame, "Net Nakit Akışı", "0.00 TL", "net_cash")
        self.card_net_cash_flow.grid(row=0, column=3, padx=5, pady=5, sticky="nsew")

        self.genel_bakis_grafik_frame = ttk.LabelFrame(parent_frame, text="Aylık Finansal Trendler (Satış, Gelir, Gider)", padding=10)
        self.genel_bakis_grafik_frame.grid(row=1, column=0, columnspan=2, pady=10, padx=5, sticky="nsew")
        self.genel_bakis_grafik_frame.columnconfigure(0, weight=1)
        self.genel_bakis_grafik_frame.rowconfigure(0, weight=1)

        self.canvas_genel_bakis_main_plot = None
        self.ax_genel_bakis_main_plot = None

    def _create_metric_card(self, parent_frame, title, initial_value, card_type):
        """Metrik kartları için ortak bir çerçeve ve label oluşturur."""
        # <<< YENİ DÜZELTME BAŞLANGICI: Card görünümü ve fontlar >>>
        card_frame = ttk.Frame(parent_frame, relief="raised", borderwidth=2, padding=15) # relief ve borderwidth eklendi, padding artırıldı
        card_frame.columnconfigure(0, weight=1) 
        card_frame.rowconfigure(0, weight=1) # Başlık için de ağırlık verdik
        card_frame.rowconfigure(1, weight=1) # Değer için de ağırlık verdik

        ttk.Label(card_frame, text=title, font=("Segoe UI", 11, "bold"), anchor=tk.CENTER).grid(row=0, column=0, sticky="nsew") # Başlığı ortala
        value_label = ttk.Label(card_frame, text=initial_value, font=("Segoe UI", 24, "bold"), foreground="navy", anchor=tk.CENTER) # Değeri daha büyük ve ortala
        value_label.grid(row=1, column=0, sticky="nsew", pady=(5,0)) 

        setattr(self, f"lbl_metric_{card_type}", value_label) # Metriğe özgü label referansını saklarız.

        return card_frame
            
    def _create_satis_raporlari_tab(self, parent_frame):
        parent_frame.columnconfigure(0, weight=2)
        parent_frame.columnconfigure(1, weight=1)
        parent_frame.rowconfigure(0, weight=0)
        parent_frame.rowconfigure(1, weight=1)

        ttk.Label(parent_frame, text="Detaylı Satış Raporları ve Analizi", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=5, padx=5, sticky=tk.W)

        left_panel = ttk.LabelFrame(parent_frame, text="Satış Faturası Kalem Detayları", padding=10)
        left_panel.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(0, weight=1)

        cols_satis_detay = ("Fatura No", "Tarih", "Cari Adı", "Ürün Adı", "Miktar", "Birim Fiyat", "Toplam (KDV Dahil)")
        self.tree_satis_detay = ttk.Treeview(left_panel, columns=cols_satis_detay, show='headings', selectmode="browse")
        for col in cols_satis_detay:
            self.tree_satis_detay.heading(col, text=col)
            self.tree_satis_detay.column(col, width=100)
        self.tree_satis_detay.column("Fatura No", width=80)
        self.tree_satis_detay.column("Tarih", width=70, anchor=tk.CENTER)
        self.tree_satis_detay.column("Cari Adı", width=120)
        self.tree_satis_detay.column("Ürün Adı", width=180, stretch=tk.YES)
        self.tree_satis_detay.column("Miktar", width=60, anchor=tk.E)
        self.tree_satis_detay.column("Birim Fiyat", width=90, anchor=tk.E)
        self.tree_satis_detay.column("Toplam (KDV Dahil)", width=100, anchor=tk.E)

        vsb_satis_detay = ttk.Scrollbar(left_panel, orient="vertical", command=self.tree_satis_detay.yview)
        vsb_satis_detay.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_satis_detay.configure(yscrollcommand=vsb_satis_detay.set)
        self.tree_satis_detay.pack(fill=tk.BOTH, expand=True)

        right_panel = ttk.Frame(parent_frame)
        right_panel.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        self.satis_odeme_dagilimi_frame = ttk.LabelFrame(right_panel, text="Ödeme Türlerine Göre Satış Dağılımı", padding=10)
        self.satis_odeme_dagilimi_frame.grid(row=0, column=0, sticky="nsew", pady=(0,10))
        self.satis_odeme_dagilimi_frame.columnconfigure(0, weight=1)
        self.satis_odeme_dagilimi_frame.rowconfigure(0, weight=1)
        self.canvas_satis_odeme_dagilimi = None
        self.ax_satis_odeme_dagilimi = None

        self.en_cok_satan_urunler_frame = ttk.LabelFrame(right_panel, text="En Çok Satan Ürünler (Miktar)", padding=10)
        self.en_cok_satan_urunler_frame.grid(row=1, column=0, sticky="nsew")
        self.en_cok_satan_urunler_frame.columnconfigure(0, weight=1)
        self.en_cok_satan_urunler_frame.rowconfigure(0, weight=1)
        self.canvas_en_cok_satan = None
        self.ax_en_cok_satan = None

    def _create_kar_zarar_tab(self, parent_frame):
        parent_frame.columnconfigure(0, weight=1)
        parent_frame.columnconfigure(1, weight=1)
        parent_frame.rowconfigure(0, weight=0)
        parent_frame.rowconfigure(1, weight=1)

        left_panel = ttk.Frame(parent_frame)
        left_panel.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=5, pady=5)
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure((0,1,2,3,4,5,6), weight=0)

        row_idx = 0
        ttk.Label(left_panel, text="Dönem Brüt Kâr (Satış Geliri - Satılan Malın Maliyeti):", font=("Segoe UI", 12, "bold")).grid(row=row_idx, column=0, pady=5, padx=5, sticky=tk.W)
        self.lbl_brut_kar = ttk.Label(left_panel, text="0.00 TL", font=("Segoe UI", 20))
        self.lbl_brut_kar.grid(row=row_idx+1, column=0, pady=(0,10), padx=5, sticky=tk.W)
        row_idx += 2

        ttk.Label(left_panel, text="Dönem Brüt Kâr Oranı:", font=("Segoe UI", 16, "bold")).grid(row=row_idx, column=0, pady=5, padx=5, sticky=tk.W)
        self.lbl_brut_kar_orani = ttk.Label(left_panel, text="%0.00", font=("Segoe UI", 20))
        self.lbl_brut_kar_orani.grid(row=row_idx+1, column=0, pady=(0,10), padx=5, sticky=tk.W)
        row_idx += 2

        ttk.Separator(left_panel, orient='horizontal').grid(row=row_idx, column=0, columnspan=1, sticky='ew', pady=15, padx=5)
        row_idx += 1

        ttk.Label(left_panel, text="Dönem Satılan Malın Maliyeti (COGS - Alış Fiyatı Üzerinden):", font=("Segoe UI", 16, "bold")).grid(row=row_idx, column=0, pady=5, padx=5, sticky=tk.W)
        self.lbl_cogs = ttk.Label(left_panel, text="0.00 TL", font=("Segoe UI", 20))
        self.lbl_cogs.grid(row=row_idx+1, column=0, pady=(0,10), padx=5, sticky=tk.W)

        self.kar_zarar_grafik_frame = ttk.LabelFrame(parent_frame, text="Aylık Kâr/Zarar Karşılaştırması", padding=10)
        self.kar_zarar_grafik_frame.grid(row=0, column=1, rowspan=2, pady=10, padx=5, sticky="nsew")
        self.kar_zarar_grafik_frame.columnconfigure(0, weight=1)
        self.kar_zarar_grafik_frame.rowconfigure(0, weight=1)

        self.canvas_kar_zarar_main_plot = None
        self.ax_kar_zarar_main_plot = None

    def _create_nakit_akisi_tab(self, parent_frame):
        parent_frame.columnconfigure(0, weight=1)
        parent_frame.columnconfigure(1, weight=1)
        parent_frame.rowconfigure(0, weight=0)
        parent_frame.rowconfigure(1, weight=1)
        parent_frame.rowconfigure(2, weight=0)

        ttk.Label(parent_frame, text="Nakit Akışı Detayları ve Bakiyeler", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=5, padx=5, sticky=tk.W)

        left_panel = ttk.LabelFrame(parent_frame, text="İşlem Detayları", padding=10)
        left_panel.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0,15))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(0, weight=1)

        cols_nakit_detay = ("Tarih", "Tip", "Tutar", "Açıklama", "Hesap Adı", "Kaynak")
        self.tree_nakit_akisi_detay = ttk.Treeview(left_panel, columns=cols_nakit_detay, show='headings', selectmode="browse")
        for col in cols_nakit_detay:
            self.tree_nakit_akisi_detay.heading(col, text=col)
            self.tree_nakit_akisi_detay.column(col, width=100)
        self.tree_nakit_akisi_detay.column("Tarih", width=80, anchor=tk.CENTER)
        self.tree_nakit_akisi_detay.column("Tip", width=60, anchor=tk.CENTER)
        self.tree_nakit_akisi_detay.column("Tutar", width=90, anchor=tk.E)
        self.tree_nakit_akisi_detay.column("Açıklama", width=180, stretch=tk.YES)
        self.tree_nakit_akisi_detay.column("Hesap Adı", width=90)
        self.tree_nakit_akisi_detay.column("Kaynak", width=70)


        vsb_nakit_detay = ttk.Scrollbar(left_panel, orient="vertical", command=self.tree_nakit_akisi_detay.yview)
        vsb_nakit_detay.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_nakit_akisi_detay.configure(yscrollcommand=vsb_nakit_detay.set)
        self.tree_nakit_akisi_detay.pack(fill=tk.BOTH, expand=True)

        self.nakit_akis_grafik_frame = ttk.LabelFrame(parent_frame, text="Aylık Nakit Akışı Trendi", padding=10)
        self.nakit_akis_grafik_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        self.nakit_akis_grafik_frame.columnconfigure(0, weight=1)
        self.nakit_akis_grafik_frame.rowconfigure(0, weight=1)

        self.canvas_nakit_akisi_trend = None
        self.ax_nakit_akisi_trend = None

        row_idx = 2
        ttk.Separator(parent_frame, orient='horizontal').grid(row=row_idx, column=0, columnspan=2, sticky='ew', pady=15, padx=5)
        row_idx += 1

        ttk.Label(parent_frame, text="Dönem Nakit Akışı Özetleri (Kasa/Banka Bağlantılı)", font=("Segoe UI", 15, "bold")).grid(row=row_idx, column=0, columnspan=2, pady=5, padx=5, sticky=tk.W)
        self.lbl_nakit_giris = ttk.Label(parent_frame, text="Toplam Nakit Girişi: 0.00 TL", font=("Segoe UI", 15))
        self.lbl_nakit_giris.grid(row=row_idx+1, column=0, columnspan=2, pady=(0,2), padx=5, sticky=tk.W)
        self.lbl_nakit_cikis = ttk.Label(parent_frame, text="Toplam Nakit Çıkışı: 0.00 TL", font=("Segoe UI", 15))
        self.lbl_nakit_cikis.grid(row=row_idx+2, column=0, columnspan=2, pady=(0,2), padx=5, sticky=tk.W)
        self.lbl_nakit_net = ttk.Label(parent_frame, text="Dönem Net Nakit Akışı: 0.00 TL", font=("Segoe UI", 15, "bold"))
        self.lbl_nakit_net.grid(row=row_idx+3, column=0, columnspan=2, pady=(0,10), padx=5, sticky=tk.W)

        self.kasa_banka_bakiye_frame = ttk.LabelFrame(parent_frame, text="Kasa/Banka Güncel Bakiyeleri", padding=10)
        self.kasa_banka_bakiye_frame.grid(row=row_idx+4, column=0, columnspan=2, sticky="nsew", padx=5, pady=(0,10))
        self.kasa_banka_bakiye_frame.columnconfigure(0, weight=1)

    def _create_cari_hesaplar_tab(self, parent_frame):
        parent_frame.columnconfigure(0, weight=1)
        parent_frame.columnconfigure(1, weight=1)
        parent_frame.rowconfigure(0, weight=0)
        parent_frame.rowconfigure(1, weight=1)
        parent_frame.rowconfigure(2, weight=0)

        ttk.Label(parent_frame, text="Cari Hesaplar Raporları (Yaşlandırma)", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=5, padx=5, sticky=tk.W)

        musteri_alacak_frame = ttk.LabelFrame(parent_frame, text="Müşteri Alacakları (Bize Borçlu)", padding=10)
        musteri_alacak_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        musteri_alacak_frame.columnconfigure(0, weight=1)
        musteri_alacak_frame.rowconfigure(0, weight=1)

        cols_cari_yaslandirma = ("Cari Adı", "Tutar", "Vadesi Geçen Gün")
        self.tree_cari_yaslandirma_alacak = ttk.Treeview(musteri_alacak_frame, columns=cols_cari_yaslandirma, show='headings', selectmode="browse")
        for col in cols_cari_yaslandirma:
            self.tree_cari_yaslandirma_alacak.heading(col, text=col)
            self.tree_cari_yaslandirma_alacak.column(col, width=100)
        self.tree_cari_yaslandirma_alacak.column("Cari Adı", width=150, stretch=tk.YES)
        self.tree_cari_yaslandirma_alacak.column("Tutar", anchor=tk.E)
        self.tree_cari_yaslandirma_alacak.column("Vadesi Geçen Gün", anchor=tk.E)

        vsb_alacak = ttk.Scrollbar(musteri_alacak_frame, orient="vertical", command=self.tree_cari_yaslandirma_alacak.yview)
        vsb_alacak.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_cari_yaslandirma_alacak.configure(yscrollcommand=vsb_alacak.set)
        self.tree_cari_yaslandirma_alacak.pack(fill=tk.BOTH, expand=True)
        self.tree_cari_yaslandirma_alacak.tag_configure('header', font=('Segoe UI', 9, 'bold'), background='#E0E0E0')
        self.tree_cari_yaslandirma_alacak.tag_configure('empty', foreground='gray')

        tedarikci_borc_frame = ttk.LabelFrame(parent_frame, text="Tedarikçi Borçları (Biz Borçluyuz)", padding=10)
        tedarikci_borc_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        tedarikci_borc_frame.columnconfigure(0, weight=1)
        tedarikci_borc_frame.rowconfigure(0, weight=1)

        self.tree_cari_yaslandirma_borc = ttk.Treeview(tedarikci_borc_frame, columns=cols_cari_yaslandirma, show='headings', selectmode="browse")
        for col in cols_cari_yaslandirma:
            self.tree_cari_yaslandirma_borc.heading(col, text=col)
            self.tree_cari_yaslandirma_borc.column(col, width=100)
        self.tree_cari_yaslandirma_borc.column("Cari Adı", width=150, stretch=tk.YES)
        self.tree_cari_yaslandirma_borc.column("Tutar", anchor=tk.E)
        self.tree_cari_yaslandirma_borc.column("Vadesi Geçen Gün", anchor=tk.E)

        vsb_borc = ttk.Scrollbar(tedarikci_borc_frame, orient="vertical", command=self.tree_cari_yaslandirma_borc.yview)
        vsb_borc.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_cari_yaslandirma_borc.configure(yscrollcommand=vsb_borc.set)
        self.tree_cari_yaslandirma_borc.pack(fill=tk.BOTH, expand=True)
        self.tree_cari_yaslandirma_borc.tag_configure('header', font=('Segoe UI', 9, 'bold'), background='#E0E0E0')
        self.tree_cari_yaslandirma_borc.tag_configure('empty', foreground='gray')

        bottom_summary_frame = ttk.Frame(parent_frame, padding=10)
        bottom_summary_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        bottom_summary_frame.columnconfigure((0,1,2), weight=1)

        self.lbl_toplam_alacak_cari = ttk.Label(bottom_summary_frame, text="Toplam Alacak: 0.00 TL", font=("Segoe UI", 10, "bold"))
        self.lbl_toplam_alacak_cari.grid(row=0, column=0, sticky=tk.W)
        self.lbl_toplam_borc_cari = ttk.Label(bottom_summary_frame, text="Toplam Borç: 0.00 TL", font=("Segoe UI", 10, "bold"))
        self.lbl_toplam_borc_cari.grid(row=0, column=1, sticky=tk.W)
        self.lbl_net_bakiye_cari = ttk.Label(bottom_summary_frame, text="Net Bakiye: 0.00 TL", font=("Segoe UI", 12, "bold"))
        self.lbl_net_bakiye_cari.grid(row=0, column=2, sticky=tk.E)

    def _create_stok_raporlari_tab(self, parent_frame):
        parent_frame.columnconfigure(0, weight=1)
        parent_frame.columnconfigure(1, weight=1)
        parent_frame.rowconfigure(0, weight=0)
        parent_frame.rowconfigure(1, weight=1)

        ttk.Label(parent_frame, text="Stok Raporları", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=5, padx=5, sticky=tk.W)

        envanter_frame = ttk.LabelFrame(parent_frame, text="Mevcut Stok Envanteri", padding=10)
        envanter_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        envanter_frame.columnconfigure(0, weight=1)
        envanter_frame.rowconfigure(0, weight=1)

        cols_stok = ("Ürün Kodu", "Ürün Adı", "Miktar", "Alış Fyt (KDV Dahil)", "Satış Fyt (KDV Dahil)", "KDV %", "Min. Stok")
        self.tree_stok_envanter = ttk.Treeview(envanter_frame, columns=cols_stok, show='headings', selectmode="browse")
        for col in cols_stok:
            self.tree_stok_envanter.heading(col, text=col)
            self.tree_stok_envanter.column(col, width=100)
        self.tree_stok_envanter.column("Ürün Adı", width=150, stretch=tk.YES)
        self.tree_stok_envanter.column("Miktar", anchor=tk.E)
        self.tree_stok_envanter.column("Alış Fyt (KDV Dahil)", anchor=tk.E)
        self.tree_stok_envanter.column("Satış Fyt (KDV Dahil)", anchor=tk.E)
        self.tree_stok_envanter.column("KDV %", anchor=tk.E)
        self.tree_stok_envanter.column("Min. Stok", anchor=tk.E)

        vsb_stok = ttk.Scrollbar(envanter_frame, orient="vertical", command=self.tree_stok_envanter.yview)
        vsb_stok.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_stok_envanter.configure(yscrollcommand=vsb_stok.set)
        self.tree_stok_envanter.pack(fill=tk.BOTH, expand=True)

        stok_grafikler_frame = ttk.Frame(parent_frame)
        stok_grafikler_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        stok_grafikler_frame.columnconfigure(0, weight=1)
        stok_grafikler_frame.rowconfigure(0, weight=1)
        stok_grafikler_frame.rowconfigure(1, weight=1)

        self.stok_kritik_grafik_frame = ttk.LabelFrame(stok_grafikler_frame, text="Kritik Stok Durumu", padding=10)
        self.stok_kritik_grafik_frame.grid(row=0, column=0, sticky="nsew", pady=(0,10))
        self.stok_kritik_grafik_frame.columnconfigure(0, weight=1)
        self.stok_kritik_grafik_frame.rowconfigure(0, weight=1)
        self.canvas_stok_kritik = None
        self.ax_stok_kritik = None

        self.stok_kategori_dagilim_frame = ttk.LabelFrame(stok_grafikler_frame, text="Kategoriye Göre Toplam Stok Değeri", padding=10)
        self.stok_kategori_dagilim_frame.grid(row=1, column=0, sticky="nsew")
        self.stok_kategori_dagilim_frame.columnconfigure(0, weight=1)
        self.stok_kategori_dagilim_frame.rowconfigure(0, weight=1)
        self.canvas_stok_kategori = None
        self.ax_stok_kategori = None

    def _on_tab_change(self, event):
        selected_tab_text = self.report_notebook.tab(self.report_notebook.select(), "text")
        bas_t_str = self.bas_tarih_entry.get()
        bit_t_str = self.bit_tarih_entry.get()

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

        self.app.set_status(f"Rapor güncellendi: {selected_tab_text} ({bas_t_str} - {bit_t_str}).")


    def raporu_olustur_ve_yenile(self):
        bas_t_str = self.bas_tarih_entry.get()
        bit_t_str = self.bit_tarih_entry.get()

        try:
            bas_t = datetime.strptime(bas_t_str, '%Y-%m-%d')
            bit_t = datetime.strptime(bit_t_str, '%Y-%m-%d')
            if bas_t > bit_t:
                messagebox.showerror("Tarih Hatası", "Başlangıç tarihi, bitiş tarihinden sonra olamaz.", parent=self.app)
                return
        except ValueError:
            messagebox.showerror("Tarih Formatı Hatası", "Tarih formatı (`YYYY-AA-GG`) olmalıdır (örn: 2023-12-31).", parent=self.app)
            return

        selected_tab_text = self.report_notebook.tab(self.report_notebook.select(), "text")
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

        self.app.set_status(f"Finansal Raporlar güncellendi ({bas_t_str} - {bit_t_str}).")

    def _update_genel_bakis_tab(self, bas_t_str, bit_t_str):
        # Placeholder Label'ı gizle (veya kaldır)
        if hasattr(self, 'lbl_genel_bakis_placeholder') and self.lbl_genel_bakis_placeholder.winfo_exists():
            self.lbl_genel_bakis_placeholder.destroy()

        # Verileri çek
        total_sales = self.db.get_total_sales(bas_t_str, bit_t_str)
        total_collections = self.db.get_total_collections(bas_t_str, bit_t_str)
        total_payments = self.db.get_total_payments(bas_t_str, bit_t_str)
        donem_gelir, donem_gider = self.db.get_kar_zarar_verileri(bas_t_str, bit_t_str)
        net_cash_flow = donem_gelir - donem_gider

        # Kartları güncelle
        # <<< DÜZELTME BAŞLANGICI: lbl_card_X yerine lbl_metric_X kullanıldı >>>
        self.lbl_metric_sales.config(text=self.db._format_currency(total_sales))
        self.lbl_metric_collections.config(text=self.db._format_currency(total_collections))
        self.lbl_metric_payments.config(text=self.db._format_currency(total_payments))
        self.lbl_metric_net_cash.config(text=self.db._format_currency(net_cash_flow),
                                    foreground="green" if net_cash_flow >= 0 else "red")
        # <<< DÜZELTME BİTİŞİ >>>

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
        if hasattr(self, 'lbl_satis_raporlari_placeholder') and self.lbl_satis_raporlari_placeholder.winfo_exists():
            self.lbl_satis_raporlari_placeholder.destroy()

        for i in self.tree_satis_detay.get_children():
            self.tree_satis_detay.delete(i)

        satis_detay_data = self.db.tarihsel_satis_raporu_verilerini_al(bas_t_str, bit_t_str)
        if satis_detay_data:
            for item in satis_detay_data:
                formatted_tarih = item[1].strftime('%d.%m.%Y') if isinstance(item[1], (datetime, date)) else (str(item[1]) if item[1] is not None else "")
                self.tree_satis_detay.insert("", tk.END, values=(
                    item[0], formatted_tarih, item[2], item[4],
                    f"{item[5]:.2f}".rstrip('0').rstrip('.'),
                    self.db._format_currency(item[6]),
                    self.db._format_currency(item[10])
                ))
        else:
            self.tree_satis_detay.insert("", tk.END, values=("", "", "Veri Yok", "", "", "", ""))


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
        if hasattr(self, 'lbl_kar_zarar_placeholder') and self.lbl_kar_zarar_placeholder.winfo_exists():
            self.lbl_kar_zarar_placeholder.destroy()

        gross_profit, cogs, gross_profit_rate = self.db.get_gross_profit_and_cost(bas_t_str, bit_t_str)
        self.lbl_brut_kar.config(text=self.db._format_currency(gross_profit))
        self.lbl_cogs.config(text=self.db._format_currency(cogs))
        self.lbl_brut_kar_orani.config(text=f"%{gross_profit_rate:,.2f}")

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
        if hasattr(self, 'lbl_nakit_akisi_placeholder') and self.lbl_nakit_akisi_placeholder.winfo_exists():
            self.lbl_nakit_akisi_placeholder.destroy()

        for i in self.tree_nakit_akisi_detay.get_children():
            self.tree_nakit_akisi_detay.delete(i)

        nakit_akis_detay_data = self.db.get_nakit_akis_verileri(bas_t_str, bit_t_str)
        if nakit_akis_detay_data:
            for item in nakit_akis_detay_data:
                formatted_tarih = item[0].strftime('%d.%m.%Y') if isinstance(item[0], (datetime, date)) else (str(item[0]) if item[0] is not None else "")
                self.tree_nakit_akisi_detay.insert("", tk.END, values=(
                    formatted_tarih, item[1], self.db._format_currency(item[2]),
                    item[3], item[4] if item[4] else "-", item[6] if item[6] else "-"
                ))
        else:
            self.tree_nakit_akisi_detay.insert("", tk.END, values=("", "", "Veri Yok", "", "", ""))


        nakit_akis_verileri_tum = self.db.get_nakit_akis_verileri(bas_t_str, bit_t_str)
        toplam_nakit_giris = sum(item[2] for item in nakit_akis_verileri_tum if item[1] == 'GELİR')
        toplam_nakit_cikis = sum(item[2] for item in nakit_akis_verileri_tum if item[1] == 'GİDER')

        self.lbl_nakit_giris.config(text=f"Toplam Nakit Girişi: {self.db._format_currency(toplam_nakit_giris)}")
        self.lbl_nakit_cikis.config(text=f"Toplam Nakit Çıkışı: {self.db._format_currency(toplam_nakit_cikis)}")
        self.lbl_nakit_net.config(text=f"Dönem Net Nakit Akışı: {self.db._format_currency(toplam_nakit_giris - toplam_nakit_cikis)}")

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

        for widget in self.kasa_banka_bakiye_frame.winfo_children():
            widget.destroy()

        current_balances = self.db.get_tum_kasa_banka_bakiyeleri()
        if current_balances:
            for h_id, h_adi, bakiye, h_tip in current_balances:
                ttk.Label(self.kasa_banka_bakiye_frame, text=f"{h_adi} ({h_tip}): {self.db._format_currency(bakiye)}", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=10)
        else:
            ttk.Label(self.kasa_banka_bakiye_frame, text="Kasa/Banka Hesabı Bulunamadı.", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=5)


    def _update_cari_hesaplar_tab(self, bas_t_str, bit_t_str):
        if hasattr(self, 'lbl_cari_hesaplar_placeholder') and self.lbl_cari_hesaplar_placeholder.winfo_exists():
            self.lbl_cari_hesaplar_placeholder.destroy()

        self.cari_yaslandirma_data = self.db.get_cari_yaslandirma_verileri(bit_t_str)

        for i in self.tree_cari_yaslandirma_alacak.get_children():
            self.tree_cari_yaslandirma_alacak.delete(i)

        self._populate_yaslandirma_treeview(self.tree_cari_yaslandirma_alacak, self.cari_yaslandirma_data['musteri_alacaklari'])

        for i in self.tree_cari_yaslandirma_borc.get_children():
            self.tree_cari_yaslandirma_borc.delete(i)

        self._populate_yaslandirma_treeview(self.tree_cari_yaslandirma_borc, self.cari_yaslandirma_data['tedarikci_borclari'])


        toplam_alacak = sum(item[2] for group in self.cari_yaslandirma_data['musteri_alacaklari'].values() for item in group)
        toplam_borc = sum(item[2] for group in self.cari_yaslandirma_data['tedarikci_borclari'].values() for item in group)
        net_bakiye_cari = toplam_alacak - toplam_borc

        self.lbl_toplam_alacak_cari.config(text=f"Toplam Alacak: {self.db._format_currency(toplam_alacak)}")
        self.lbl_toplam_borc_cari.config(text=f"Toplam Borç: {self.db._format_currency(toplam_borc)}")
        self.lbl_net_bakiye_cari.config(text=f"Net Bakiye: {self.db._format_currency(net_bakiye_cari)}")


    def _populate_yaslandirma_treeview(self, tree, data_dict):
        for period, items in data_dict.items():
            tree.insert("", tk.END, iid=period, text=f"--- {period} Gün ---", open=True, tags=('header',))
            if items:
                for item in items:
                    tree.insert(period, tk.END, values=(
                        item[1],
                        self.db._format_currency(item[2]),
                        item[3]
                    ))
            else:
                tree.insert(period, tk.END, values=("", "", "Bu Kategori Boş"), tags=('empty',))


    def _update_stok_raporlari_tab(self, bas_t_str, bit_t_str):
        if hasattr(self, 'lbl_stok_raporlari_placeholder') and self.lbl_stok_raporlari_placeholder.winfo_exists():
            self.lbl_stok_raporlari_placeholder.destroy()

        for i in self.tree_stok_envanter.get_children():
            self.tree_stok_envanter.delete(i)

        all_stock_items = self.db.stok_listele(limit=None, offset=None)

        if all_stock_items:
            for item in all_stock_items:
                self.tree_stok_envanter.insert("", tk.END, values=(
                    item[1],
                    item[2],
                    f"{item[3]:.2f}".rstrip('0').rstrip('.'),
                    self.db._format_currency(item[8]),
                    self.db._format_currency(item[9]),
                    f"{item[6]:.0f}%",
                    f"{item[7]:.2f}".rstrip('0').rstrip('.')
                ))
        else:
            self.tree_stok_envanter.insert("", tk.END, values=("", "", "Veri Yok", "", "", "", ""))


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
        messagebox.showinfo("Bilgi", "PDF Raporu oluşturma özelliği henüz geliştirilmedi.", parent=self.app)

    def raporu_excel_aktar_placeholder(self):
        messagebox.showinfo("Bilgi", "Excel Raporu oluşturma özelliği henüz geliştirildi.", parent=self.app)

        
class GelirGiderSayfasi(ttk.Frame):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref # Ana App sınıfına referans
        self.pack(expand=True, fill=tk.BOTH)

        ttk.Label(self, text="Gelir ve Gider İşlemleri", font=("Segoe UI", 16, "bold")).pack(pady=(10,5), anchor=tk.W, padx=10)

        # Ana Notebook (Sekmeli Yapı)
        self.main_notebook = ttk.Notebook(self)
        self.main_notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        # Gelir Listesi Sekmesi
        self.gelir_listesi_frame = GelirListesi(self.main_notebook, self.db, self.app)
        self.main_notebook.add(self.gelir_listesi_frame, text="💰 Gelirler")

        # Gider Listesi Sekmesi
        self.gider_listesi_frame = GiderListesi(self.main_notebook, self.db, self.app)
        self.main_notebook.add(self.gider_listesi_frame, text="💸 Giderler")
        
class GirisEkrani(ttk.Frame):
    def __init__(self, parent, db_manager, callback_basarili_giris):
        super().__init__(parent)
        self.db = db_manager
        self.callback = callback_basarili_giris
        self.pack(expand=True, fill=tk.BOTH)

        # Giriş formunu ortalamak için bir çerçeve
        center_frame = ttk.Frame(self)
        center_frame.place(relx=0.5, rely=0.4, anchor=tk.CENTER)

        ttk.Label(center_frame, text="Kullanıcı Girişi", font=("Segoe UI", 22, "bold")).pack(pady=(0, 25))

        ttk.Label(center_frame, text="Kullanıcı Adı:").pack(pady=(5,2), anchor=tk.W)
        # *** BURASI ÖNEMLİ: k_adi_e artık burada tanımlanıyor ***
        self.k_adi_e = ttk.Entry(center_frame, width=35, font=("Segoe UI", 11))
        self.k_adi_e.pack(pady=(0,10), ipady=3)

        ttk.Label(center_frame, text="Şifre:").pack(pady=(5,2), anchor=tk.W)
        # *** BURASI ÖNEMLİ: sifre_e artık burada tanımlanıyor ***
        self.sifre_e = ttk.Entry(center_frame, show="*", width=35, font=("Segoe UI", 11))
        self.sifre_e.pack(pady=(0,20), ipady=3)
        self.sifre_e.bind("<Return>", self.giris_yap_event)

        # Kayıtlı kullanıcı adını yükle
        config = self.db.load_config()
        last_username = config.get('last_username', '')
        # k_adi_e artık tanımlı olduğu için insert işlemi sorunsuz çalışacak
        self.k_adi_e.insert(0, last_username)

        giris_button = ttk.Button(center_frame, text="Giriş Yap", command=self.giris_yap, style="Accent.TButton", width=15, padding=(5,8))
        giris_button.pack(pady=10)

        # Şirket Adı (Giriş Ekranının Altında)
        sirket_adi_giris = self.db.sirket_bilgileri.get("sirket_adi", "Şirket Adınız")
        ttk.Label(self, text=sirket_adi_giris, font=("Segoe UI", 10)).place(relx=0.5, rely=0.95, anchor=tk.S)

        # Odaklanma işlemi en sona alınmalı
        self.k_adi_e.focus()

    def giris_yap_event(self, event): self.giris_yap() # Enter tuşu için
    def giris_yap(self):
        k_adi = self.k_adi_e.get()
        sifre = self.sifre_e.get()
        kullanici = self.db.kullanici_dogrula(k_adi, sifre)
        if kullanici:
            # kullanici: (id, kullanici_adi, yetki)
            self.callback(kullanici) # Başarılı giriş callback'ini çağır
        else:
            messagebox.showerror("Giriş Hatası", "Kullanıcı adı veya şifre hatalı!", parent=self) # parent=self ile giriş ekranında göster
            self.sifre_e.delete(0, tk.END) # Şifre alanını temizle
            self.sifre_e.focus() # Şifre alanına odaklan                

class StokHareketleriSekmesi(ttk.Frame):
    def __init__(self, parent_notebook, db_manager, app_ref, urun_id, urun_adi, parent_pencere=None):
        super().__init__(parent_notebook)
        self.db = db_manager
        self.app = app_ref
        self.urun_id = urun_id
        self.urun_adi = urun_adi
        self.parent_pencere = parent_pencere # Ürün kartı penceresinin referansı
        print(f"DEBUG: StokHareketleriSekmesi __init__ - parent_pencere: {parent_pencere}") 
        if parent_pencere:
            print(f"DEBUG: StokHareketleriSekmesi __init__ - parent_pencere tipi: {type(parent_pencere)}") 

        # Filtreleme seçenekleri çerçevesi
        filter_frame = ttk.Frame(self, padding="5")
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="İşlem Tipi:").pack(side=tk.LEFT, padx=(0,2))
        self.stok_hareket_tip_filter_cb = ttk.Combobox(filter_frame, width=20, 
                                                       values=["TÜMÜ", self.db.STOK_ISLEM_TIP_GIRIS_MANUEL_DUZELTME, # <-- Düzeltildi
                                                               self.db.STOK_ISLEM_TIP_CIKIS_MANUEL_DUZELTME, # <-- Düzeltildi
                                                               self.db.STOK_ISLEM_TIP_GIRIS_MANUEL, # <-- Düzeltildi
                                                               self.db.STOK_ISLEM_TIP_CIKIS_MANUEL, # <-- Düzeltildi
                                                               self.db.STOK_ISLEM_TIP_SAYIM_FAZLASI, # <-- Düzeltildi
                                                               self.db.STOK_ISLEM_TIP_SAYIM_EKSIGI, # <-- Düzeltildi
                                                               self.db.STOK_ISLEM_TIP_ZAYIAT, # <-- Düzeltildi
                                                               self.db.STOK_ISLEM_TIP_IADE_GIRIS, # <-- Düzeltildi
                                                               self.db.STOK_ISLEM_TIP_FATURA_ALIS, # <-- Düzeltildi
                                                               self.db.STOK_ISLEM_TIP_FATURA_SATIS], # <-- Düzeltildi
                                                       state="readonly")
        self.stok_hareket_tip_filter_cb.pack(side=tk.LEFT, padx=(0,10))
        self.stok_hareket_tip_filter_cb.set("TÜMÜ")
        self.stok_hareket_tip_filter_cb.bind("<<ComboboxSelected>>", self._load_stok_hareketleri)

        ttk.Label(filter_frame, text="Başlangıç Tarihi:").pack(side=tk.LEFT, padx=(0,2))
        self.stok_hareket_bas_tarih_entry = ttk.Entry(filter_frame, width=12)
        self.stok_hareket_bas_tarih_entry.pack(side=tk.LEFT, padx=(0,5))
        self.stok_hareket_bas_tarih_entry.insert(0, (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
        setup_date_entry(self.app, self.stok_hareket_bas_tarih_entry)
        ttk.Button(filter_frame, text="🗓️", command=lambda: DatePickerDialog(self.app, self.stok_hareket_bas_tarih_entry), width=3).pack(side=tk.LEFT, padx=2)

        ttk.Label(filter_frame, text="Bitiş Tarihi:").pack(side=tk.LEFT, padx=(0,2))
        self.stok_hareket_bit_tarih_entry = ttk.Entry(filter_frame, width=12)
        self.stok_hareket_bit_tarih_entry.pack(side=tk.LEFT, padx=(0,10))
        self.stok_hareket_bit_tarih_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        setup_date_entry(self.app, self.stok_hareket_bit_tarih_entry)
        ttk.Button(filter_frame, text="🗓️", command=lambda: DatePickerDialog(self.app, self.stok_hareket_bit_tarih_entry), width=3).pack(side=tk.LEFT, padx=2)

        ttk.Button(filter_frame, text="Yenile", command=self._load_stok_hareketleri, style="Accent.TButton").pack(side=tk.LEFT)

        # Stok Hareketleri Treeview ve kaydırma çubukları için ana çerçeve
        tree_frame = ttk.Frame(self, padding="10")
        tree_frame.pack(expand=True, fill=tk.BOTH)

        cols_stok_hareket = ("ID", "Tarih", "İşlem Tipi", "Miktar", "Önceki Stok", "Sonraki Stok", "Açıklama", "Kaynak")
        self.stok_hareket_tree = ttk.Treeview(tree_frame, columns=cols_stok_hareket, show='headings', selectmode="browse")

        col_defs_stok_hareket = [
            ("ID", 40, tk.E, tk.NO),
            ("Tarih", 80, tk.CENTER, tk.NO),
            ("İşlem Tipi", 150, tk.W, tk.NO),
            ("Miktar", 80, tk.E, tk.NO),
            ("Önceki Stok", 90, tk.E, tk.NO),
            ("Sonraki Stok", 90, tk.E, tk.NO),
            ("Açıklama", 250, tk.W, tk.YES),
            ("Kaynak", 100, tk.W, tk.NO)
        ]
        for cn,w,a,s in col_defs_stok_hareket:
            self.stok_hareket_tree.column(cn, width=w, anchor=a, stretch=s)
            self.stok_hareket_tree.heading(cn, text=cn, command=lambda c=cn: sort_treeview_column(self.stok_hareket_tree, c, False))

        vsb_stok_hareket = ttk.Scrollbar(tree_frame, orient="vertical", command=self.stok_hareket_tree.yview)
        hsb_stok_hareket = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.stok_hareket_tree.xview)
        self.stok_hareket_tree.configure(yscrollcommand=vsb_stok_hareket.set, xscrollcommand=hsb_stok_hareket.set)
        vsb_stok_hareket.pack(side=tk.RIGHT, fill=tk.Y)
        hsb_stok_hareket.pack(side=tk.BOTTOM, fill=tk.X)
        self.stok_hareket_tree.pack(expand=True, fill=tk.BOTH)

        # Sağ tık menüsünü bağlama
        self.stok_hareket_tree.bind("<ButtonRelease-3>", self._open_stok_hareket_context_menu)

        self._load_stok_hareketleri()

    def _on_stok_hareket_select(self, event=None):
        # Bu metod artık sadece Treeview'deki seçimi yönetmek için kullanılabilir,
        # ancak sağ tık menüsü zaten dinamik olarak aktif/pasif olmayı halledeceği için
        # aslında burada özel bir işlem yapılmasına gerek yoktur.
        pass

    def _open_stok_hareket_context_menu(self, event):
        print(f"DEBUG: _open_stok_hareket_context_menu çağrıldı. Event y: {event.y}, Event x: {event.x}")
        item_id = self.stok_hareket_tree.identify_row(event.y)
        
        if not item_id:
            print("DEBUG: item_id bulunamadı, menü açılmayacak.")
            return

        print(f"DEBUG: Seçilen item_id: {item_id}")

        self.stok_hareket_tree.selection_set(item_id) # Sağ tıklanan öğeyi seçili yap
        
        item_values = self.stok_hareket_tree.item(item_id, 'values')
        kaynak_tipi = item_values[7] # Kaynak sütunu (indeks 7)
        print(f"DEBUG: Kaynak tipi: {kaynak_tipi}")

        context_menu = tk.Menu(self, tearoff=0)
        
        menu_command_added = False # Menüye komut eklenip eklenmediğini takip etmek için bayrak
        if kaynak_tipi == 'MANUEL':
            context_menu.add_command(label="Stok Hareketini Sil", command=self._secili_stok_hareketini_sil)
            print("DEBUG: 'Stok Hareketini Sil' komutu menüye eklendi.")
            menu_command_added = True 
        else:
            print(f"DEBUG: Manuel olmayan kaynak ({kaynak_tipi}). Silme komutu eklenmedi.")
        
        if menu_command_added: # Eğer menüye bir komut eklendiyse, menüyü göstermeyi dene
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
                print("DEBUG: Menü başarıyla açıldı.")
            finally:
                context_menu.grab_release()
        else:
            print(f"DEBUG: Menüde gösterilecek öğe yok (Kaynak: {kaynak_tipi}). Menü açılmayacak.")                      
    def _secili_stok_hareketini_sil(self):
        selected_item_iid = self.stok_hareket_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir stok hareketi seçin.", parent=self.app)
            return
        
        item_data = self.stok_hareket_tree.item(selected_item_iid)
        try:
            hareket_id = int(item_data['values'][0]) # ID
            islem_tipi = str(item_data['values'][2]) # İşlem Tipi
            miktar = float(str(item_data['values'][3]).replace(',', '.')) # Miktar
            kaynak = str(item_data['values'][7]) # Kaynak
        except (ValueError, IndexError):
            messagebox.showerror("Hata", "Seçili hareketin verileri okunamadı.", parent=self.app)
            return

        # Sadece MANUEL kaynaklı hareketleri silmeye izin ver.
        if kaynak != 'MANUEL':
            messagebox.showwarning("Silme Engellendi", "Sadece 'Manuel' kaynaklı stok hareketleri silinebilir. Fatura gibi otomatik oluşan hareketler ilgili modüllerden yönetilmelidir.", parent=self.app)
            return

        confirm_message = f"'{islem_tipi}' tipindeki {miktar} miktarındaki stok hareketini silmek istediğinizden emin misiniz?\n\nBu işlem, ürünün ana stoğunu da etkileyecektir ve geri alınamaz!"
        if messagebox.askyesno("Onay", confirm_message, icon='warning', parent=self.app):
            success, message = self.db.manuel_stok_hareketi_sil(hareket_id)
            if success:
                messagebox.showinfo("Başarılı", message, parent=self.app)
                self._load_stok_hareketleri() # Bu sekmenin kendi listesini yenile
                
                print("DEBUG: _secili_stok_hareketini_sil - parent_pencere kontrol ediliyor.") # <-- YENİ DEBUG
                if self.parent_pencere and hasattr(self.parent_pencere, 'refresh_data_and_ui'):
                    print("DEBUG: _secili_stok_hareketini_sil - parent_pencere var ve refresh_data_and_ui metodu var. Çağrılıyor.") # <-- YENİ DEBUG
                    try:
                        self.parent_pencere.refresh_data_and_ui() # Ana ürün kartını yenile
                        self.parent_pencere.update_idletasks() # UI güncellemesini zorla
                        self.parent_pencere.update() # UI güncellemesini daha da zorla
                        # Stok miktarının güncellendiğini kontrol etmek için özel bir print ekleyebiliriz
                        if hasattr(self.parent_pencere, 'sv_stok'):
                            print(f"DEBUG: Ürün Kartı Güncel sv_stok değeri: {self.parent_pencere.sv_stok.get()}")
                    except Exception as e_refresh:
                        print(f"UYARI: Ürün Kartı refresh_data_and_ui çağrılırken hata: {e_refresh}")
                        traceback.print_exc()
                else:
                    print("DEBUG: _secili_stok_hareketini_sil - parent_pencere yok veya refresh_data_and_ui metodu yok.") # <-- YENİ DEBUG

                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi.stok_listesini_yenile() # Ana stok listesini yenile
                self.app.set_status(message)
            else:
                messagebox.showerror("Hata", message, parent=self.app)
                self.app.set_status(f"Stok hareketi silinirken hata: {message}")
        else:
            self.app.set_status("Stok hareketi silme işlemi iptal edildi.")

    def refresh_data_and_ui(self):
        """
        Ürüne ait en güncel verileri veritabanından çeker ve tüm arayüzü yeniler.
        Bu metot, alt pencerelerden (Stok Hareketi gibi) gelen sinyaller üzerine çağrılır.
        """
        print("DEBUG: UrunKartiPenceresi.refresh_data_and_ui çağrıldı.")
        if not self.urun_id:
            return
            
        latest_product_data = self.db.stok_getir_by_id(self.urun_id)
        
        if latest_product_data:
            self.urun_duzenle = latest_product_data
            
            print("DEBUG: Ürün kartı arayüzü en güncel verilerle yenilendi.")
        else:
            print("UYARI: Ürün kartı yenilenirken ürün veritabanından bulunamadı.")
            messagebox.showwarning("Veri Kayıp", "Ürün verileri bulunamadığı için kart yenilenemedi.", parent=self)

    def _load_stok_hareketleri(self, event=None):
        for i in self.stok_hareket_tree.get_children():
            self.stok_hareket_tree.delete(i)

        if not self.urun_id:
            self.stok_hareket_tree.insert("", tk.END, values=("", "", "Ürün Seçili Değil", "", "", "", "", ""))
            return

        islem_tipi_filtre = self.stok_hareket_tip_filter_cb.get()
        bas_tarih_str = self.stok_hareket_bas_tarih_entry.get()
        bit_tarih_str = self.stok_hareket_bit_tarih_entry.get()

        hareketler = self.db.stok_hareketleri_listele(
            self.urun_id,
            islem_tipi=islem_tipi_filtre if islem_tipi_filtre != "TÜMÜ" else None,
            baslangic_tarih=bas_tarih_str if bas_tarih_str else None,
            bitis_tarih=bit_tarih_str if bit_tarih_str else None
        )

        if not hareketler:
            self.stok_hareket_tree.insert("", tk.END, values=("", "", "Hareket Bulunamadı", "", "", "", "", ""))
            return

        for hareket in hareketler:
            # hareket: sqlite3.Row objesi (id, urun_id, tarih, islem_tipi, miktar, onceki_stok, sonraki_stok, aciklama, kaynak)
            tarih_obj = hareket['tarih'] # isme göre erişim
            if isinstance(tarih_obj, (date, datetime)):
                tarih_formatted = tarih_obj.strftime('%d.%m.%Y')
            else:
                tarih_formatted = str(tarih_obj) # Beklenmedik bir durum olursa

            miktar_formatted = f"{hareket['miktar']:.2f}".rstrip('0').rstrip('.')
            onceki_stok_formatted = f"{hareket['onceki_stok']:.2f}".rstrip('0').rstrip('.')
            sonraki_stok_formatted = f"{hareket['sonraki_stok']:.2f}".rstrip('0').rstrip('.')

            self.stok_hareket_tree.insert("", tk.END, values=(
                hareket['id'], # ID
                tarih_formatted, # Tarih
                hareket['islem_tipi'], # İşlem Tipi
                miktar_formatted, # Miktar
                onceki_stok_formatted, # Önceki Stok
                sonraki_stok_formatted, # Sonraki Stok
                hareket['aciklama'] if hareket['aciklama'] else "-", # Açıklama
                hareket['kaynak'] if hareket['kaynak'] else "-" # Kaynak
            ))
        self.app.set_status(f"Ürün '{self.urun_adi}' için {len(hareketler)} stok hareketi listelendi.")

class IlgiliFaturalarSekmesi(ttk.Frame):
    def __init__(self, parent_notebook, db_manager, app_ref, urun_id, urun_adi):
        super().__init__(parent_notebook)
        self.db = db_manager
        self.app = app_ref
        self.urun_id = urun_id
        self.urun_adi = urun_adi

        filter_frame = ttk.Frame(self, padding="5")
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="Fatura Tipi:").pack(side=tk.LEFT, padx=(0,2))
        self.fatura_tipi_filter_cb = ttk.Combobox(filter_frame, width=15, values=["TÜMÜ", "ALIŞ", "SATIŞ"], state="readonly")
        self.fatura_tipi_filter_cb.pack(side=tk.LEFT, padx=(0,10))
        self.fatura_tipi_filter_cb.set("TÜMÜ")
        self.fatura_tipi_filter_cb.bind("<<ComboboxSelected>>", self._load_ilgili_faturalar)

        ttk.Button(filter_frame, text="Filtrele", command=self._load_ilgili_faturalar, style="Accent.TButton").pack(side=tk.LEFT)

        cols_fatura = ("ID", "Fatura No", "Tarih", "Tip", "Cari/Misafir", "KDV Hariç Top.", "KDV Dahil Top.")
        self.ilgili_faturalar_tree = ttk.Treeview(self, columns=cols_fatura, show='headings', selectmode="browse")

        col_defs_fatura = [
            ("ID", 40, tk.E, tk.NO),
            ("Fatura No", 120, tk.W, tk.YES),
            ("Tarih", 85, tk.CENTER, tk.NO),
            ("Tip", 70, tk.CENTER, tk.NO),
            ("Cari/Misafir", 200, tk.W, tk.YES),
            ("KDV Hariç Top.", 120, tk.E, tk.NO),
            ("KDV Dahil Top.", 120, tk.E, tk.NO)
        ]
        for cn,w,a,s in col_defs_fatura:
            self.ilgili_faturalar_tree.column(cn, width=w, anchor=a, stretch=s)
            self.ilgili_faturalar_tree.heading(cn, text=cn, command=lambda c=cn: sort_treeview_column(self.ilgili_faturalar_tree, c, False))

        vsb_fatura = ttk.Scrollbar(self, orient="vertical", command=self.ilgili_faturalar_tree.yview)
        hsb_fatura = ttk.Scrollbar(self, orient="horizontal", command=self.ilgili_faturalar_tree.xview)
        self.ilgili_faturalar_tree.configure(yscrollcommand=vsb_fatura.set, xscrollcommand=hsb_fatura.set)
        vsb_fatura.pack(side=tk.RIGHT, fill=tk.Y)
        hsb_fatura.pack(side=tk.BOTTOM, fill=tk.X)
        self.ilgili_faturalar_tree.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        self.ilgili_faturalar_tree.bind("<Double-1>", self._on_fatura_double_click)

        # _load_ilgili_faturalar'ı ilk yüklemede otomatik çağırmıyoruz, Notebook sekmesi seçildiğinde çağrılacak.

    def _load_ilgili_faturalar(self, event=None):
        for i in self.ilgili_faturalar_tree.get_children():
            self.ilgili_faturalar_tree.delete(i)

        if not self.urun_id:
            self.ilgili_faturalar_tree.insert("", tk.END, values=("", "", "", "", "Ürün seçili değil.", "", ""))
            return

        fatura_tipi_filtre = self.fatura_tipi_filter_cb.get()
        
        faturalar = self.db.get_faturalar_by_urun_id(self.urun_id, fatura_tipi=fatura_tipi_filtre)

        if not faturalar:
            self.ilgili_faturalar_tree.insert("", tk.END, values=("", "", "", "", "Bu ürüne ait fatura bulunamadı.", "", ""))
            return

        for fatura_item in faturalar:
            fatura_id = fatura_item[0]
            fatura_no = fatura_item[1]
            tarih_obj = fatura_item[2] 
            fatura_tip = fatura_item[3]
            cari_adi = fatura_item[4]
            toplam_kdv_haric = fatura_item[5]
            toplam_kdv_dahil = fatura_item[6]

            # Gelen veri zaten bir tarih nesnesi. Doğrudan formatlıyoruz.
            if isinstance(tarih_obj, (datetime, date)):
                formatted_tarih = tarih_obj.strftime('%d.%m.%Y')
            else:
                formatted_tarih = str(tarih_obj)

            self.ilgili_faturalar_tree.insert("", tk.END, iid=fatura_id, values=(
                fatura_id,
                fatura_no,
                formatted_tarih,
                fatura_tip,
                cari_adi,
                self.db._format_currency(toplam_kdv_haric),
                self.db._format_currency(toplam_kdv_dahil)
            ))
        self.app.set_status(f"Ürün '{self.urun_adi}' için {len(faturalar)} fatura listelendi.")

    def _on_fatura_double_click(self, event):
        selected_item_iid = self.ilgili_faturalar_tree.focus()
        if not selected_item_iid:
            return
        
        fatura_id = self.ilgili_faturalar_tree.item(selected_item_iid)['values'][0]
        if fatura_id:
            from pencereler import FaturaDetayPenceresi
            FaturaDetayPenceresi(self.app, self.db, fatura_id)


class KategoriMarkaYonetimiSekmesi(ttk.Frame):
    def __init__(self, parent_notebook, db_manager, app_ref):
        super().__init__(parent_notebook)
        self.db = db_manager
        self.app = app_ref

        # Sol taraf: Kategori Yönetimi
        kategori_frame = ttk.LabelFrame(self, text="Kategori Yönetimi", padding="10")
        kategori_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0,5))
        kategori_frame.columnconfigure(1, weight=1)
        kategori_frame.grid_rowconfigure(1, weight=1)


        ttk.Label(kategori_frame, text="Kategori Adı:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.kategori_entry = ttk.Entry(kategori_frame, width=30)
        self.kategori_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(kategori_frame, text="Ekle", command=self._kategori_ekle_ui).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(kategori_frame, text="Güncelle", command=self._kategori_guncelle_ui).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(kategori_frame, text="Sil", command=self._kategori_sil_ui).grid(row=0, column=4, padx=5, pady=5)

        self.kategori_tree = ttk.Treeview(kategori_frame, columns=("ID", "Kategori Adı"), show='headings', selectmode="browse")
        self.kategori_tree.heading("ID", text="ID"); self.kategori_tree.column("ID", width=50, stretch=tk.NO)
        self.kategori_tree.heading("Kategori Adı", text="Kategori Adı"); self.kategori_tree.column("Kategori Adı", width=200, stretch=tk.YES)
        self.kategori_tree.grid(row=1, column=0, columnspan=5, padx=5, pady=10, sticky="nsew")
        
        self.kategori_tree.bind("<<TreeviewSelect>>", self._on_kategori_select)
        # _kategori_listesini_yukle() ilk yüklemede otomatik çağırmıyoruz, Notebook sekmesi seçildiğinde çağrılacak.


        # Sağ taraf: Marka Yönetimi
        marka_frame = ttk.LabelFrame(self, text="Marka Yönetimi", padding="10")
        marka_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=(5,0))
        marka_frame.columnconfigure(1, weight=1)
        marka_frame.grid_rowconfigure(1, weight=1)


        ttk.Label(marka_frame, text="Marka Adı:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.marka_entry = ttk.Entry(marka_frame, width=30)
        self.marka_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(marka_frame, text="Ekle", command=self._marka_ekle_ui).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(marka_frame, text="Güncelle", command=self._marka_guncelle_ui).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(marka_frame, text="Sil", command=self._marka_sil_ui).grid(row=0, column=4, padx=5, pady=5)

        self.marka_tree = ttk.Treeview(marka_frame, columns=("ID", "Marka Adı"), show='headings', selectmode="browse")
        self.marka_tree.heading("ID", text="ID"); self.marka_tree.column("ID", width=50, stretch=tk.NO)
        self.marka_tree.heading("Marka Adı", text="Marka Adı"); self.marka_tree.column("Marka Adı", width=200, stretch=tk.YES)
        self.marka_tree.grid(row=1, column=0, columnspan=5, padx=5, pady=10, sticky="nsew")
        
        self.marka_tree.bind("<<TreeviewSelect>>", self._on_marka_select)
        # _marka_listesini_yukle() ilk yüklemede otomatik çağırmıyoruz, Notebook sekmesi seçildiğinde çağrılacak.

    # Kategori Yönetimi Metotları (Bu sınıfın içinde)
    def _kategori_listesini_yukle(self):
        for i in self.kategori_tree.get_children(): self.kategori_tree.delete(i)
        kategoriler = self.db.kategori_listele()
        for kat_id, kat_ad in kategoriler: self.kategori_tree.insert("", tk.END, values=(kat_id, kat_ad), iid=kat_id)
        # Combobox'ları yenileme callback'i burada yok, UrunKartiPenceresi'nden çağrılacak.

    def _on_kategori_select(self, event):
        selected_item = self.kategori_tree.focus()
        if selected_item:
            values = self.kategori_tree.item(selected_item, 'values')
            self.kategori_entry.delete(0, tk.END)
            self.kategori_entry.insert(0, values[1])
        else:
            self.kategori_entry.delete(0, tk.END)

    def _kategori_ekle_ui(self):
        kategori_adi = self.kategori_entry.get().strip()
        success, message = self.db.kategori_ekle(kategori_adi)
        if success:
            messagebox.showinfo("Başarılı", message, parent=self)
            self.kategori_entry.delete(0, tk.END)
            self._kategori_listesini_yukle()
        else:
            messagebox.showerror("Hata", message, parent=self)

    def _kategori_guncelle_ui(self):
        selected_item = self.kategori_tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen güncellemek için bir kategori seçin.", parent=self)
            return
        kategori_id = self.kategori_tree.item(selected_item)['values'][0]
        yeni_kategori_adi = self.kategori_entry.get().strip()
        success, message = self.db.kategori_guncelle(kategori_id, yeni_kategori_adi)
        if success:
            messagebox.showinfo("Başarılı", message, parent=self)
            self.kategori_entry.delete(0, tk.END)
            self._kategori_listesini_yukle()
        else:
            messagebox.showerror("Hata", message, parent=self)

    def _kategori_sil_ui(self):
        selected_item = self.kategori_tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir kategori seçin.", parent=self)
            return
        kategori_id = self.kategori_tree.item(selected_item)['values'][0]
        kategori_adi = self.kategori_tree.item(selected_item)['values'][1]
        if messagebox.askyesno("Onay", f"'{kategori_adi}' kategorisini silmek istediğinizden emin misiniz?", parent=self):
            success, message = self.db.kategori_sil(kategori_id)
            if success:
                messagebox.showinfo("Başarılı", message, parent=self)
                self.kategori_entry.delete(0, tk.END)
                self._kategori_listesini_yukle()
            else:
                messagebox.showerror("Hata", message, parent=self)

    # Marka Yönetimi Metotları (Bu sınıfın içinde)
    def _marka_listesini_yukle(self):
        for i in self.marka_tree.get_children(): self.marka_tree.delete(i)
        markalar = self.db.marka_listele()
        for mar_id, mar_ad in markalar: self.marka_tree.insert("", tk.END, values=(mar_id, mar_ad), iid=mar_id)

    def _on_marka_select(self, event):
        selected_item = self.marka_tree.focus()
        if selected_item:
            values = self.marka_tree.item(selected_item, 'values')
            self.marka_entry.delete(0, tk.END)
            self.marka_entry.insert(0, values[1])
        else:
            self.marka_entry.delete(0, tk.END)

    def _marka_ekle_ui(self):
        marka_adi = self.marka_entry.get().strip()
        success, message = self.db.marka_ekle(marka_adi)
        if success:
            messagebox.showinfo("Başarılı", message, parent=self)
            self.marka_entry.delete(0, tk.END)
            self._marka_listesini_yukle()
        else:
            messagebox.showerror("Hata", message, parent=self)

    def _marka_guncelle_ui(self):
        selected_item = self.marka_tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen güncellemek için bir marka seçin.", parent=self)
            return
        marka_id = self.marka_tree.item(selected_item)['values'][0]
        yeni_marka_adi = self.marka_entry.get().strip()
        success, message = self.db.marka_guncelle(marka_id, yeni_marka_adi)
        if success:
            messagebox.showinfo("Başarılı", message, parent=self)
            self.marka_entry.delete(0, tk.END)
            self._marka_listesini_yukle()
        else:
            messagebox.showerror("Hata", message, parent=self)

    def _marka_sil_ui(self):
        selected_item = self.marka_tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir marka seçin.", parent=self)
            return
        marka_id = self.marka_tree.item(selected_item)['values'][0]
        marka_adi = self.marka_tree.item(selected_item)['values'][1]
        if messagebox.askyesno("Onay", f"'{marka_adi}' markasını silmek istediğinizden emin misiniz?", parent=self):
            success, message = self.db.marka_sil(marka_id)
            if success:
                messagebox.showinfo("Başarılı", message, parent=self)
                self.marka_entry.delete(0, tk.END)
                self._marka_listesini_yukle()
            else:
                messagebox.showerror("Hata", message, parent=self)


class UrunNitelikYonetimiSekmesi(ttk.Frame): 
    def __init__(self, parent_notebook, db_manager, app_ref):
        super().__init__(parent_notebook)
        self.db = db_manager
        self.app = app_ref

        main_frame = self
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        urun_grubu_frame = ttk.LabelFrame(main_frame, text="Ürün Grubu Yönetimi", padding="10")
        urun_grubu_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        urun_grubu_frame.columnconfigure(1, weight=1)
        urun_grubu_frame.grid_rowconfigure(1, weight=1)

        ttk.Label(urun_grubu_frame, text="Grup Adı:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.urun_grubu_entry = ttk.Entry(urun_grubu_frame, width=30)
        self.urun_grubu_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(urun_grubu_frame, text="Ekle", command=self._urun_grubu_ekle_ui).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(urun_grubu_frame, text="Güncelle", command=self._urun_grubu_guncelle_ui).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(urun_grubu_frame, text="Sil", command=self._urun_grubu_sil_ui).grid(row=0, column=4, padx=5, pady=5)

        self.urun_grubu_tree = ttk.Treeview(urun_grubu_frame, columns=("ID", "Grup Adı"), show='headings', selectmode="browse")
        self.urun_grubu_tree.heading("ID", text="ID"); self.urun_grubu_tree.column("ID", width=50, stretch=tk.NO)
        self.urun_grubu_tree.heading("Grup Adı", text="Grup Adı"); self.urun_grubu_tree.column("Grup Adı", width=200, stretch=tk.YES)
        self.urun_grubu_tree.grid(row=1, column=0, columnspan=5, padx=5, pady=10, sticky="nsew")
        self.urun_grubu_tree.bind("<<TreeviewSelect>>", self._on_urun_grubu_select)

        urun_birimi_frame = ttk.LabelFrame(main_frame, text="Ürün Birimi Yönetimi", padding="10")
        urun_birimi_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        urun_birimi_frame.columnconfigure(1, weight=1)
        urun_birimi_frame.grid_rowconfigure(1, weight=1)

        ttk.Label(urun_birimi_frame, text="Birim Adı:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.urun_birimi_entry = ttk.Entry(urun_birimi_frame, width=30)
        self.urun_birimi_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(urun_birimi_frame, text="Ekle", command=self._urun_birimi_ekle_ui).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(urun_birimi_frame, text="Güncelle", command=self._urun_birimi_guncelle_ui).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(urun_birimi_frame, text="Sil", command=self._urun_birimi_sil_ui).grid(row=0, column=4, padx=5, pady=5)

        self.urun_birimi_tree = ttk.Treeview(urun_birimi_frame, columns=("ID", "Birim Adı"), show='headings', selectmode="browse")
        self.urun_birimi_tree.heading("ID", text="ID"); self.urun_birimi_tree.column("ID", width=50, stretch=tk.NO)
        self.urun_birimi_tree.heading("Birim Adı", text="Birim Adı"); self.urun_birimi_tree.column("Birim Adı", width=200, stretch=tk.YES)
        self.urun_birimi_tree.grid(row=1, column=0, columnspan=5, padx=5, pady=10, sticky="nsew")
        self.urun_birimi_tree.bind("<<TreeviewSelect>>", self._on_urun_birimi_select)

        ulke_frame = ttk.LabelFrame(main_frame, text="Menşe Ülke Yönetimi", padding="10")
        ulke_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        ulke_frame.columnconfigure(1, weight=1)
        ulke_frame.grid_rowconfigure(1, weight=1)

        ttk.Label(ulke_frame, text="Ülke Adı:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.ulke_entry = ttk.Entry(ulke_frame, width=30)
        self.ulke_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(ulke_frame, text="Ekle", command=self._ulke_ekle_ui).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(ulke_frame, text="Güncelle", command=self._ulke_guncelle_ui).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(ulke_frame, text="Sil", command=self._ulke_sil_ui).grid(row=0, column=4, padx=5, pady=5)

        self.ulke_tree = ttk.Treeview(ulke_frame, columns=("ID", "Ülke Adı"), show='headings', selectmode="browse")
        self.ulke_tree.heading("ID", text="ID"); self.ulke_tree.column("ID", width=50, stretch=tk.NO)
        self.ulke_tree.heading("Ülke Adı", text="Ülke Adı"); self.ulke_tree.column("Ülke Adı", width=200, stretch=tk.YES)
        self.ulke_tree.grid(row=1, column=0, columnspan=5, padx=5, pady=10, sticky="nsew")
        self.ulke_tree.bind("<<TreeviewSelect>>", self._on_ulke_select)

    def _urun_grubu_listesini_yukle(self):
        for i in self.urun_grubu_tree.get_children(): self.urun_grubu_tree.delete(i)
        urun_gruplari = self.db.urun_grubu_listele()
        for grup_id, grup_ad in urun_gruplari: self.urun_grubu_tree.insert("", tk.END, values=(grup_id, grup_ad), iid=grup_id)
        # Bu callback, UrunKartiPenceresi'ndeki combobox'ı güncelleyecek.
        if hasattr(self.app, '_yukle_urun_grubu_birimi_ulke_comboboxlari'):
            self.app._yukle_urun_grubu_birimi_ulke_comboboxlari()

    def _on_urun_grubu_select(self, event):
        selected_item = self.urun_grubu_tree.focus()
        if selected_item:
            values = self.urun_grubu_tree.item(selected_item, 'values')
            self.urun_grubu_entry.delete(0, tk.END)
            self.urun_grubu_entry.insert(0, values[1])
        else:
            self.urun_grubu_entry.delete(0, tk.END)

    def _urun_grubu_ekle_ui(self):
        grup_adi = self.urun_grubu_entry.get().strip()
        if not grup_adi:
            messagebox.showwarning("Uyarı", "Ürün grubu adı boş olamaz.", parent=self)
            return
        success, message = self.db.urun_grubu_ekle(grup_adi)
        if success:
            messagebox.showinfo("Başarılı", message, parent=self)
            self.urun_grubu_entry.delete(0, tk.END)
            self._urun_grubu_listesini_yukle()
        else:
            messagebox.showerror("Hata", message, parent=self)

    def _urun_grubu_guncelle_ui(self):
        selected_item = self.urun_grubu_tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen güncellemek için bir ürün grubu seçin.", parent=self)
            return
        grup_id = self.urun_grubu_tree.item(selected_item)['values'][0]
        yeni_grup_adi = self.urun_grubu_entry.get().strip()
        if not yeni_grup_adi:
            messagebox.showwarning("Uyarı", "Ürün grubu adı boş olamaz.", parent=self)
            return
        success, message = self.db.urun_grubu_guncelle(grup_id, yeni_grup_adi)
        if success:
            messagebox.showinfo("Başarılı", message, parent=self)
            self.urun_grubu_entry.delete(0, tk.END)
            self._urun_grubu_listesini_yukle()
        else:
            messagebox.showerror("Hata", message, parent=self)

    def _urun_grubu_sil_ui(self):
        selected_item = self.urun_grubu_tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir ürün grubu seçin.", parent=self)
            return
        grup_id = self.urun_grubu_tree.item(selected_item)['values'][0]
        grup_adi = self.urun_grubu_tree.item(selected_item)['values'][1]
        if messagebox.askyesno("Onay", f"'{grup_adi}' ürün grubunu silmek istediğinizden emin misiniz?", parent=self):
            success, message = self.db.urun_grubu_sil(grup_id)
            if success:
                messagebox.showinfo("Başarılı", message, parent=self)
                self.urun_grubu_entry.delete(0, tk.END)
                self._urun_grubu_listesini_yukle()
            else:
                messagebox.showerror("Hata", message, parent=self)

    def _open_birim_context_menu(self, event):
        item_id = self.urun_birimi_tree.identify_row(event.y)
        if not item_id:
            return

        self.urun_birimi_tree.selection_set(item_id) # Sağ tıklanan öğeyi seçili yap

        context_menu = tk.Menu(self, tearoff=0)
        context_menu.add_command(label="Güncelle", command=lambda: self._urun_birimi_duzenle_popup(item_id))
        context_menu.add_command(label="Sil", command=self._urun_birimi_sil_ui) # Mevcut silme metodunu kullan

        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _urun_birimi_duzenle_popup(self, birim_id):
        # Birim bilgilerini veritabanından çek (sadece birim_id ve birim_adi'nı döndüren bir metoda ihtiyacımız var)
        # veritabani.py'ye urun_birimi_getir_by_id(self, birim_id) metodu eklememiz gerekebilir.
        self.db.c.execute("SELECT id, birim_adi FROM urun_birimleri WHERE id=?", (birim_id,))
        birim_info = self.db.c.fetchone()

        if birim_info:
            # Yeni bir pop-up penceresi aç
            BirimDuzenlePenceresi(self, self.db, birim_info, self._urun_birimi_listesini_yukle) # Listeyi yenilemek için callback
        else:
            messagebox.showerror("Hata", "Ürün birimi bilgisi bulunamadı.", parent=self)


    # Ürün Birimi Yönetimi Metotları
    def _urun_birimi_listesini_yukle(self):
        for i in self.urun_birimi_tree.get_children(): self.urun_birimi_tree.delete(i)
        urun_birimleri = self.db.urun_birimi_listele()
        for birim_id, birim_ad in urun_birimleri: self.urun_birimi_tree.insert("", tk.END, values=(birim_id, birim_ad), iid=birim_id)
        self.urun_birimi_tree.bind("<ButtonRelease-3>", self._open_birim_context_menu) 
        if hasattr(self.app, '_yukle_urun_grubu_birimi_ulke_comboboxlari'):
            self.app._yukle_urun_grubu_birimi_ulke_comboboxlari()

    def _on_urun_birimi_select(self, event):
        selected_item = self.urun_birimi_tree.focus()
        if selected_item:
            values = self.urun_birimi_tree.item(selected_item, 'values')
            self.urun_birimi_entry.delete(0, tk.END)
            self.urun_birimi_entry.insert(0, values[1])
        else:
            self.urun_birimi_entry.delete(0, tk.END)

    def _urun_birimi_ekle_ui(self):
        birim_adi = self.urun_birimi_entry.get().strip()
        if not birim_adi:
            messagebox.showwarning("Uyarı", "Ürün birimi adı boş olamaz.", parent=self)
            return
        success, message = self.db.urun_birimi_ekle(birim_adi)
        if success:
            messagebox.showinfo("Başarılı", message, parent=self)
            self.urun_birimi_entry.delete(0, tk.END)
            self._urun_birimi_listesini_yukle()
        else:
            messagebox.showerror("Hata", message, parent=self)

    def _urun_birimi_guncelle_ui(self):
        selected_item = self.urun_birimi_tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen güncellemek için bir ürün birimi seçin.", parent=self)
            return
        birim_id = self.urun_birimi_tree.item(selected_item)['values'][0]
        yeni_birim_adi = self.urun_birimi_entry.get().strip()
        if not yeni_birim_adi:
            messagebox.showwarning("Uyarı", "Ürün birimi adı boş olamaz.", parent=self)
            return
        success, message = self.db.urun_birimi_guncelle(birim_id, yeni_birim_adi)
        if success:
            messagebox.showinfo("Başarılı", message, parent=self)
            self.urun_birimi_entry.delete(0, tk.END)
            self._urun_birimi_listesini_yukle()
        else:
            messagebox.showerror("Hata", message, parent=self)

    def _urun_birimi_sil_ui(self):
        selected_item = self.urun_birimi_tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir ürün birimi seçin.", parent=self)
            return
        birim_id = self.urun_birimi_tree.item(selected_item)['values'][0]
        birim_adi = self.urun_birimi_tree.item(selected_item)['values'][1]
        if messagebox.askyesno("Onay", f"'{birim_adi}' ürün birimini silmek istediğinizden emin misiniz?", parent=self):
            success, message = self.db.urun_birimi_sil(birim_id)
            if success:
                messagebox.showinfo("Başarılı", message, parent=self)
                self.urun_birimi_entry.delete(0, tk.END)
                self._urun_birimi_listesini_yukle()
            else:
                messagebox.showerror("Hata", message, parent=self)

    # Ülke (Menşe) Yönetimi Metotları
    def _ulke_listesini_yukle(self):
        for i in self.ulke_tree.get_children(): self.ulke_tree.delete(i)
        ulkeler = self.db.ulke_listele()
        for ulke_id, ulke_ad in ulkeler: self.ulke_tree.insert("", tk.END, values=(ulke_id, ulke_ad), iid=ulke_id)
        if hasattr(self.app, '_yukle_urun_grubu_birimi_ulke_comboboxlari'):
            self.app._yukle_urun_grubu_birimi_ulke_comboboxlari()

    def _on_ulke_select(self, event):
        selected_item = self.ulke_tree.focus()
        if selected_item:
            values = self.ulke_tree.item(selected_item, 'values')
            self.ulke_entry.delete(0, tk.END)
            self.ulke_entry.insert(0, values[1])
        else:
            self.ulke_entry.delete(0, tk.END)

    def _ulke_ekle_ui(self):
        ulke_adi = self.ulke_entry.get().strip()
        if not ulke_adi:
            messagebox.showwarning("Uyarı", "Ülke adı boş olamaz.", parent=self)
            return
        success, message = self.db.ulke_ekle(ulke_adi)
        if success:
            messagebox.showinfo("Başarılı", message, parent=self)
            self.ulke_entry.delete(0, tk.END)
            self._ulke_listesini_yukle()
        else:
            messagebox.showerror("Hata", message, parent=self)

    def _ulke_guncelle_ui(self):
        selected_item = self.ulke_tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen güncellemek için bir ülke seçin.", parent=self)
            return
        ulke_id = self.ulke_tree.item(selected_item)['values'][0]
        yeni_ulke_adi = self.ulke_entry.get().strip()
        if not yeni_ulke_adi:
            messagebox.showwarning("Uyarı", "Ülke adı boş olamaz.", parent=self)
            return
        success, message = self.db.ulke_guncelle(ulke_id, yeni_ulke_adi)
        if success:
            messagebox.showinfo("Başarılı", message, parent=self)
            self.ulke_entry.delete(0, tk.END)
            self._ulke_listesini_yukle()
        else:
            messagebox.showerror("Hata", message, parent=self)

    def _ulke_sil_ui(self):
        selected_item = self.ulke_tree.focus()
        if not selected_item:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir ülke seçin.", parent=self)
            return
        ulke_id = self.ulke_tree.item(selected_item)['values'][0]
        ulke_adi = self.ulke_tree.item(selected_item)['values'][1]
        if messagebox.askyesno("Onay", f"'{ulke_adi}' ülkesini silmek istediğinizden emin misiniz?", parent=self):
            success, message = self.db.ulke_sil(ulke_id)
            if success:
                messagebox.showinfo("Başarılı", message, parent=self)
                self.ulke_entry.delete(0, tk.END)
                self._ulke_listesini_yukle()
            else:
                messagebox.showerror("Hata", message, parent=self)
