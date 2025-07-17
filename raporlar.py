import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, date, timedelta # datetime.date de eklendi
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm
from reportlab.platypus import Table, TableStyle, Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rp_canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import threading
import os 

# Fontlar artık veritabani.py'den import ediliyor ve orada kaydediliyor, burada tekrar yüklemeye gerek yok.
# Sadece font isimlerini kullanacağız.
from veritabani import TURKISH_FONT_NORMAL, TURKISH_FONT_BOLD 
from reportlab.pdfbase import pdfmetrics # pdfmetrics hala gerekli

# YARDIMCI MODÜLLERDEN GEREKENLER
from yardimcilar import sort_treeview_column, setup_date_entry, DatePickerDialog

# PENCERELER MODÜLÜNDEN GEREKENLER (Bu dosyadaki sınıflar için gerekli olanlar)
from pencereler import BeklemePenceresi, CariHesapEkstresiPenceresi 
from pencereler import TedarikciSecimDialog # CriticalStockWarningPenceresi içinde çağrıldığı için buraya eklendi


class CriticalStockWarningPenceresi(tk.Toplevel):
    def __init__(self, parent_app, db_manager):
        super().__init__(parent_app)
        self.app = parent_app
        self.db = db_manager
        self.title("Kritik Stok Uyarısı ve Sipariş Önerisi")
        self.geometry("800x500")
        self.transient(parent_app)
        self.grab_set()

        ttk.Label(self, text="Kritik Stoktaki Ürünler", font=("Segoe UI", 16, "bold")).pack(pady=10, anchor=tk.W, padx=10)

        info_frame = ttk.Frame(self, padding="10")
        info_frame.pack(fill=tk.X, padx=10)
        ttk.Label(info_frame, text="Minimum stok seviyesinin altında olan ürünler listelenmiştir. İstenilen stok seviyesine ulaşmak için önerilen miktarları sipariş edebilirsiniz.").pack(anchor=tk.W)

        # Kritik Stok Listesi (Treeview)
        tree_frame = ttk.Frame(self, padding="10")
        tree_frame.pack(expand=True, fill=tk.BOTH)

        cols = ("Ürün Kodu", "Ürün Adı", "Mevcut Stok", "Min. Stok", "Fark", "Önerilen Sipariş Mik.")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode="none") # Seçim olmasın

        col_defs = [
            ("Ürün Kodu", 100, tk.W, tk.NO),
            ("Ürün Adı", 250, tk.W, tk.YES),
            ("Mevcut Stok", 100, tk.E, tk.NO),
            ("Min. Stok", 100, tk.E, tk.NO),
            ("Fark", 80, tk.E, tk.NO),
            ("Önerilen Sipariş Mik.", 150, tk.E, tk.NO)
        ]
        for cn,w,a,s in col_defs:
            self.tree.column(cn, width=w, anchor=a, stretch=s)
            self.tree.heading(cn, text=cn, command=lambda _c=cn: sort_treeview_column(self.tree, _c, False)) # Sıralama eklendi

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(expand=True, fill=tk.BOTH)
        
        self.load_critical_stock()

        # Butonlar
        button_frame = ttk.Frame(self, padding="10")
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Yenile", command=self.load_critical_stock, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Sipariş Oluştur", command=self._siparis_olustur_critical_stock, style="Accent.TButton").pack(side=tk.RIGHT, padx=5) 
        ttk.Button(button_frame, text="Kapat", command=self.destroy).pack(side=tk.RIGHT)

    def load_critical_stock(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        critical_items = self.db.get_critical_stock_items()
        if not critical_items:
            self.tree.insert("", tk.END, values=("", "", "", "", "", "Kritik Stokta Ürün Bulunmuyor."))
            self.app.set_status("Kritik stokta ürün bulunmuyor.")
            return

        for item in critical_items:
            urun_kodu = item[1]
            urun_adi = item[2]
            mevcut_stok = item[3]
            min_stok = item[7]
            fark = min_stok - mevcut_stok
            onerilen_siparis = fark 

            self.tree.insert("", tk.END, values=(
                urun_kodu,
                urun_adi,
                f"{mevcut_stok:.2f}".rstrip('0').rstrip('.'),
                f"{min_stok:.2f}".rstrip('0').rstrip('.'),
                f"{fark:.2f}".rstrip('0').rstrip('.'),
                f"{onerilen_siparis:.2f}".rstrip('0').rstrip('.')
            ))
        self.app.set_status(f"{len(critical_items)} ürün kritik stok seviyesinin altında.")

    def _siparis_olustur_critical_stock(self):
        """
        Kritik stoktaki ürünleri toplar ve tedarikçi seçimi sonrası alış faturası oluşturma akışını başlatır.
        """
        urunler_for_siparis = []
        all_critical_items_db = self.db.get_critical_stock_items() 
        for item_db in all_critical_items_db:
            urun_id = item_db[0]
            urun_kodu_db = item_db[1]
            urun_adi_db = item_db[2] # <<-- Düzeltilen Satır
            onerilen_miktar = item_db[7] - item_db[3] 
            
            if onerilen_miktar > 0:
                urunler_for_siparis.append({
                    "id": urun_id,
                    "kodu": urun_kodu_db,
                    "adi": urun_adi_db,
                    "miktar": onerilen_miktar, 
                    "alis_fiyati_kdv_haric": item_db[4], 
                    "kdv_orani": item_db[6],   
                    "alis_fiyati_kdv_dahil": item_db[8] 
                })

        if not urunler_for_siparis:
            messagebox.showinfo("Bilgi", "Sipariş oluşturmak için kritik stokta ürün bulunmuyor.", parent=self)
            return

        # Tedarikçi Seçim Diyaloğunu aç ve callback'i _tedarikci_secildi_ve_siparis_olustur olarak ayarla
        # TedarikciSecimDialog zaten raporlar.py başında import edildiği için buradan kaldırdık.
        TedarikciSecimDialog(self, self.db, 
                             lambda selected_tedarikci_id, selected_tedarikci_ad: 
                             self._tedarikci_secildi_ve_siparis_olustur(selected_tedarikci_id, selected_tedarikci_ad, urunler_for_siparis))

    def _tedarikci_secildi_ve_siparis_olustur(self, tedarikci_id, tedarikci_ad, urunler_for_siparis):
        """
        Tedarikçi seçildikten sonra çağrılır. Alış siparişi oluşturma sayfasını başlatır.
        """
        if tedarikci_id:
            self.app.tedarikci_siparisi_goster(initial_cari_id=tedarikci_id, initial_urunler=urunler_for_siparis)
            self.app.set_status(f"'{tedarikci_ad}' için tedarikçi siparişi oluşturma ekranı açıldı.")
            self.destroy() 
        else:
            self.app.set_status("Tedarikçi seçimi iptal edildi. Sipariş oluşturulmadı.")
            messagebox.showwarning("İptal Edildi", "Tedarikçi seçimi yapılmadığı için sipariş oluşturma işlemi iptal edildi.", parent=self)


class NotificationDetailsPenceresi(tk.Toplevel):
    def __init__(self, parent_app, db_manager, notifications_data):
        super().__init__(parent_app)
        self.app = parent_app
        self.db = db_manager
        self.notifications_data = notifications_data 
        self.title("Aktif Bildirim Detayları")
        self.geometry("900x600")
        self.transient(parent_app)
        self.grab_set()

        ttk.Label(self, text="Aktif Bildirim Detayları", font=("Segoe UI", 16, "bold")).pack(pady=10, anchor=tk.W, padx=10)

        self.notebook_details = ttk.Notebook(self)
        self.notebook_details.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        # Kritik Stok Sekmesi
        if 'critical_stock' in self.notifications_data:
            critical_stock_frame = ttk.Frame(self.notebook_details, padding="10")
            self.notebook_details.add(critical_stock_frame, text="📦 Kritik Stok")
            self._create_critical_stock_tab(critical_stock_frame, self.notifications_data['critical_stock'])

        # Vadesi Geçmiş Alacaklar Sekmesi
        if 'overdue_receivables' in self.notifications_data:
            overdue_receivables_frame = ttk.Frame(self.notebook_details, padding="10")
            self.notebook_details.add(overdue_receivables_frame, text="💰 Vadesi Geçmiş Alacaklar")
            self._create_overdue_receivables_tab(overdue_receivables_frame, self.notifications_data['overdue_receivables'])

        # Vadesi Geçmiş Borçlar Sekmesi
        if 'overdue_payables' in self.notifications_data:
            overdue_payables_frame = ttk.Frame(self.notebook_details, padding="10")
            self.notebook_details.add(overdue_payables_frame, text="💸 Vadesi Geçmiş Borçlar")
            self._create_overdue_payables_tab(overdue_payables_frame, self.notifications_data['overdue_payables'])

        ttk.Button(self, text="Kapat", command=self.destroy).pack(pady=10)

    def _create_critical_stock_tab(self, parent_frame, data):
        cols = ("Ürün Kodu", "Ürün Adı", "Mevcut Stok", "Min. Stok", "Fark", "Önerilen Sipariş Mik.")
        self.tree = ttk.Treeview(parent_frame, columns=cols, show='headings', selectmode="none") # self.tree olarak düzeltildi

        col_defs = [
            ("Ürün Kodu", 100, tk.W, tk.NO),
            ("Ürün Adı", 250, tk.W, tk.YES),
            ("Mevcut Stok", 100, tk.E, tk.NO),
            ("Min. Stok", 100, tk.E, tk.NO),
            ("Fark", 80, tk.E, tk.NO),
            ("Önerilen Sipariş Mik.", 150, tk.E, tk.NO)
        ]
        for cn,w,a,s in col_defs:
            self.tree.column(cn, width=w, anchor=a, stretch=s) # self.tree olarak düzelt
            self.tree.heading(cn, text=cn) # self.tree olarak düzelt

        vsb = ttk.Scrollbar(parent_frame, orient="vertical", command=self.tree.yview) # self.tree olarak düzelt
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set) # self.tree olarak düzelt
        self.tree.pack(expand=True, fill=tk.BOTH) # self.tree olarak düzelt

        for item in data:
            urun_kodu = item[1]
            urun_adi = item[2]
            mevcut_stok = item[3]
            min_stok = item[7]
            fark = min_stok - mevcut_stok
            onerilen_siparis = fark
            self.tree.insert("", tk.END, values=(
                urun_kodu, urun_adi,
                f"{mevcut_stok:.2f}".rstrip('0').rstrip('.'),
                f"{min_stok:.2f}".rstrip('0').rstrip('.'),
                f"{fark:.2f}".rstrip('0').rstrip('.'),
                f"{onerilen_siparis:.2f}".rstrip('0').rstrip('.')
            ))

    def _create_overdue_receivables_tab(self, parent_frame, data):
        cols = ("Müşteri Adı", "Net Borç", "Vadesi Geçen Gün")
        self.tree = ttk.Treeview(parent_frame, columns=cols, show='headings', selectmode="browse") # self.tree olarak düzeltildi

        col_defs = [
            ("Müşteri Adı", 250, tk.W, tk.YES),
            ("Net Borç", 120, tk.E, tk.NO),
            ("Vadesi Geçen Gün", 120, tk.E, tk.NO)
        ]
        for cn,w,a,s in col_defs:
            self.tree.column(cn, width=w, anchor=a, stretch=s) # self.tree olarak düzelt
            self.tree.heading(cn, text=cn) # self.tree olarak düzelt

        vsb = ttk.Scrollbar(parent_frame, orient="vertical", command=self.tree.yview) # self.tree olarak düzelt
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set) # self.tree olarak düzelt
        self.tree.pack(expand=True, fill=tk.BOTH) # self.tree olarak düzelt

        for item in data:
            self.tree.insert("", tk.END, values=(
                item[1], self.db._format_currency(item[2]), item[3]
            ))
        self.tree.bind("<Double-1>", lambda event: self._open_cari_ekstresi_from_notification(event, self.tree, 'MUSTERI')) # self.tree olarak düzelt

    def _create_overdue_payables_tab(self, parent_frame, data):
        cols = ("Tedarikçi Adı", "Net Borç", "Vadesi Geçen Gün")
        self.tree = ttk.Treeview(parent_frame, columns=cols, show='headings', selectmode="browse") # self.tree olarak düzeltildi

        col_defs = [
            ("Tedarikçi Adı", 250, tk.W, tk.YES),
            ("Net Borç", 120, tk.E, tk.NO),
            ("Vadesi Geçen Gün", 120, tk.E, tk.NO)
        ]
        for cn,w,a,s in col_defs:
            self.tree.column(cn, width=w, anchor=a, stretch=s) # self.tree olarak düzelt
            self.tree.heading(cn, text=cn) # self.tree olarak düzelt

        vsb = ttk.Scrollbar(parent_frame, orient="vertical", command=self.tree.yview) # self.tree olarak düzelt
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set) # self.tree olarak düzelt
        self.tree.pack(expand=True, fill=tk.BOTH) # self.tree olarak düzelt

        for item in data:
            self.tree.insert("", tk.END, values=(
                item[1], self.db._format_currency(item[2]), item[3]
            ))
        self.tree.bind("<Double-1>", lambda event: self._open_cari_ekstresi_from_notification(event, self.tree, 'TEDARIKCI')) # self.tree olarak düzelt

    def _open_cari_ekstresi_from_notification(self, event, tree, cari_tip):
        selected_item = tree.focus()
        if not selected_item:
            return
        
        item_values = tree.item(selected_item, 'values')
        cari_adi = item_values[0] 
        
        cari_id = None
        if cari_tip == 'MUSTERI':
            for item in self.notifications_data.get('overdue_receivables', []):
                if item[1] == cari_adi:
                    cari_id = item[0]
                    break
        elif cari_tip == 'TEDARIKCI':
            for item in self.notifications_data.get('overdue_payables', []):
                if item[1] == cari_adi:
                    cari_id = item[0]
                    break
        
        if cari_id:
            CariHesapEkstresiPenceresi(self.app, self.db, cari_id, cari_tip, cari_adi)
        else:
            messagebox.showwarning("Hata", "Cari ID bulunamadı.", parent=self)