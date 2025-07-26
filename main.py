import sys
import os
import json
import logging
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QFileDialog,
    QWidget, QMenuBar, QStatusBar, QTabWidget # QTabWidget eklendi
)
from PySide6.QtGui import QAction
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QDate, Signal

# Tema için eklenen importlar
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt 

# Kendi modüllerimiz
from arayuz import ( # arayuz.py'den tüm gerekli sayfaları içe aktarın
    AnaSayfa, StokYonetimiSayfasi, MusteriYonetimiSayfasi,
    KasaBankaYonetimiSayfasi, FinansalIslemlerSayfasi,
    FaturaListesiSayfasi, SiparisListesiSayfasi,
    GelirGiderSayfasi, RaporlamaMerkeziSayfasi,
    TedarikciYonetimiSayfasi, # Bu sınıf arayuz.py'de mevcut
    UrunNitelikYonetimiSekmesi # Nitelik yönetimi için doğru sınıf
)
from veritabani import OnMuhasebe
from hizmetler import FaturaService, TopluIslemService
from raporlar import Raporlama

# pencereler modülünden gerekli sınıfları burada import edeceğiz
# Döngüsel bağımlılığı önlemek için fonksiyonların içinde import etme pratiği devam ediyor,
# ancak bu ana dosyadaki ihtiyaçları da göz önünde bulundurmalıyız.

# Logger kurulumu
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Veri dizini oluşturma (mevcutsa atla)
_data_dir = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(_data_dir, exist_ok=True)

# Config dosyasını yükle veya oluştur
_config_path = os.path.join(_data_dir, 'config.json')

def load_config():
    """Uygulama yapılandırmasını yükler."""
    from config import API_BASE_URL as DEFAULT_API_URL_FROM_MODULE 

    config_data = {
        "api_base_url": DEFAULT_API_URL_FROM_MODULE, 
        "last_username": "" 
    }
    if os.path.exists(_config_path):
        try:
            with open(_config_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                config_data.update(loaded_config)
        except json.JSONDecodeError:
            logger.error(f"Hatalı config.json dosyası: {_config_path}. Varsayılan yapılandırma kullanılıyor.")
    return config_data

def save_config(config):
    """Uygulama yapılandırmasını kaydeder."""
    try:
        with open(_config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except IOError as e:
        logger.error(f"Config dosyası kaydedilirken hata oluştu: {e}")

class Ui_MainWindow_Minimal:
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1200, 800)

        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)

        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        # --- QAction'ları (Menü Öğeleri) tanımlama ---
        MainWindow.actionStok_Kart = QAction(MainWindow)
        MainWindow.actionStok_Kart.setObjectName("actionStok_Kart")
        MainWindow.actionStok_Kart.setText("Stok Kartı")

        MainWindow.actionM_teri_Kart = QAction(MainWindow)
        MainWindow.actionM_teri_Kart.setObjectName("actionM_teri_Kart")
        MainWindow.actionM_teri_Kart.setText("Müşteri Kartı")
        
        MainWindow.actionTedarik_i_Kart = QAction(MainWindow)
        MainWindow.actionTedarik_i_Kart.setObjectName("actionTedarik_i_Kart")
        MainWindow.actionTedarik_i_Kart.setText("Tedarikçi Kartı")

        MainWindow.actionKasa_Banka_Kart = QAction(MainWindow)
        MainWindow.actionKasa_Banka_Kart.setObjectName("actionKasa_Banka_Kart")
        MainWindow.actionKasa_Banka_Kart.setText("Kasa/Banka Kartı")

        MainWindow.actionGelir_Gider_Kart = QAction(MainWindow)
        MainWindow.actionGelir_Gider_Kart.setObjectName("actionGelir_Gider_Kart")
        MainWindow.actionGelir_Gider_Kart.setText("Gelir/Gider Kartı")

        MainWindow.actionFatura_Kart = QAction(MainWindow)
        MainWindow.actionFatura_Kart.setObjectName("actionFatura_Kart")
        MainWindow.actionFatura_Kart.setText("Fatura Kartı")

        MainWindow.action_rsiparis = QAction(MainWindow)
        MainWindow.action_rsiparis.setObjectName("action_rsiparis")
        MainWindow.action_rsiparis.setText("Sipariş Kartı")

        MainWindow.actionCari_Hareketler = QAction(MainWindow)
        MainWindow.actionCari_Hareketler.setObjectName("actionCari_Hareketler")
        MainWindow.actionCari_Hareketler.setText("Cari Hareketler")

        MainWindow.actionNitelik_Y_netimi = QAction(MainWindow)
        MainWindow.actionNitelik_Y_netimi.setObjectName("actionNitelik_Y_netimi")
        MainWindow.actionNitelik_Y_netimi.setText("Nitelik Yönetimi")

        MainWindow.actionToplu_Veri_Aktar_m = QAction(MainWindow)
        MainWindow.actionToplu_Veri_Aktar_m.setObjectName("actionToplu_Veri_Aktar_m")
        MainWindow.actionToplu_Veri_Aktar_m.setText("Toplu Veri Aktarımı")
        
        # Raporlar Menüsü Action'ları
        MainWindow.actionM_teri_Raporu = QAction(MainWindow)
        MainWindow.actionM_teri_Raporu.setObjectName("actionM_teri_Raporu")
        MainWindow.actionM_teri_Raporu.setText("Müşteri Raporu")

        MainWindow.actionTedarik_i_Raporu = QAction(MainWindow)
        MainWindow.actionTedarik_i_Raporu.setObjectName("actionTedarik_i_Raporu")
        MainWindow.actionTedarik_i_Raporu.setText("Tedarikçi Raporu")

        MainWindow.actionStok_Raporu = QAction(MainWindow)
        MainWindow.actionStok_Raporu.setObjectName("actionStok_Raporu")
        MainWindow.actionStok_Raporu.setText("Stok Raporu")

        MainWindow.actionFatura_Raporu = QAction(MainWindow)
        MainWindow.actionFatura_Raporu.setObjectName("actionFatura_Raporu")
        MainWindow.actionFatura_Raporu.setText("Fatura Raporu")

        MainWindow.actionKasa_Banka_Raporu = QAction(MainWindow)
        MainWindow.actionKasa_Banka_Raporu.setObjectName("actionKasa_Banka_Raporu")
        MainWindow.actionKasa_Banka_Raporu.setText("Kasa/Banka Raporu")

        MainWindow.actionGelir_Gider_Raporu = QAction(MainWindow)
        MainWindow.actionGelir_Gider_Raporu.setObjectName("actionGelir_Gider_Raporu")
        MainWindow.actionGelir_Gider_Raporu.setText("Gelir/Gider Raporu")

        MainWindow.actionCari_Hareket_Raporu = QAction(MainWindow)
        MainWindow.actionCari_Hareket_Raporu.setObjectName("actionCari_Hareket_Raporu")
        MainWindow.actionCari_Hareket_Raporu.setText("Cari Hareket Raporu")

        MainWindow.actionSiparis_Raporu = QAction(MainWindow)
        MainWindow.actionSiparis_Raporu.setObjectName("actionSiparis_Raporu")
        MainWindow.actionSiparis_Raporu.setText("Sipariş Raporu")

        MainWindow.actionNitelik_Raporu = QAction(MainWindow)
        MainWindow.actionNitelik_Raporu.setObjectName("actionNitelik_Raporu")
        MainWindow.actionNitelik_Raporu.setText("Nitelik Raporu")

        # Veritabanı Menüsü Action'ları
        MainWindow.actionYedekle = QAction(MainWindow)
        MainWindow.actionYedekle.setObjectName("actionYedekle")
        MainWindow.actionYedekle.setText("Yedekle")

        MainWindow.actionGeri_Y_kle = QAction(MainWindow)
        MainWindow.actionGeri_Y_kle.setObjectName("actionGeri_Y_kle")
        MainWindow.actionGeri_Y_kle.setText("Geri Yükle")

        MainWindow.actionAPI_Ayarlar = QAction(MainWindow)
        MainWindow.actionAPI_Ayarlar.setObjectName("actionAPI_Ayarlar")
        MainWindow.actionAPI_Ayarlar.setText("API Ayarları")


        # Menüleri oluşturma ve Action'ları ekleme
        self.menuKartlar = self.menubar.addMenu("Kartlar")
        self.menuKartlar.addAction(MainWindow.actionStok_Kart)
        self.menuKartlar.addAction(MainWindow.actionM_teri_Kart)
        self.menuKartlar.addAction(MainWindow.actionTedarik_i_Kart)
        self.menuKartlar.addAction(MainWindow.actionKasa_Banka_Kart)
        self.menuKartlar.addAction(MainWindow.actionGelir_Gider_Kart)
        self.menuKartlar.addAction(MainWindow.actionFatura_Kart)
        self.menuKartlar.addAction(MainWindow.action_rsiparis)
        self.menuKartlar.addAction(MainWindow.actionCari_Hareketler)
        self.menuKartlar.addAction(MainWindow.actionNitelik_Y_netimi)
        self.menuKartlar.addAction(MainWindow.actionToplu_Veri_Aktar_m)

        self.menuRaporlar = self.menubar.addMenu("Raporlar")
        self.menuRaporlar.addAction(MainWindow.actionM_teri_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionTedarik_i_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionStok_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionFatura_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionKasa_Banka_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionGelir_Gider_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionCari_Hareket_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionSiparis_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionNitelik_Raporu)

        self.menuAyarlar = self.menubar.addMenu("Ayarlar")
        self.menuAyarlar.addAction(MainWindow.actionYedekle)
        self.menuAyarlar.addAction(MainWindow.actionGeri_Y_kle)
        self.menuAyarlar.addAction(MainWindow.actionAPI_Ayarlar)
        
class App(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui_main_window_setup = Ui_MainWindow_Minimal()
        self.ui_main_window_setup.setupUi(self)

        self.setWindowTitle("Çınar Yapı Ön Muhasebe Programı")
        self.config = load_config()

        self.db_manager = None
        self._initialize_db_manager()

        # Ana sekmeler için QTabWidget oluştur
        self.tab_widget = QTabWidget(self)
        self.setCentralWidget(self.tab_widget) # QTabWidget'ı merkezi widget olarak ayarla

        # Her bir yönetim sayfasını oluştur ve QTabWidget'a ekle
        # app_ref olarak kendisi (self) ve db_manager parametreleri doğru şekilde geçiliyor.
        self.ana_sayfa_widget = AnaSayfa(self, self.db_manager, self)
        self.tab_widget.addTab(self.ana_sayfa_widget, "Ana Sayfa")

        self.stok_yonetimi_sayfasi = StokYonetimiSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.stok_yonetimi_sayfasi, "Stok Yönetimi")

        self.musteri_yonetimi_sayfasi = MusteriYonetimiSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.musteri_yonetimi_sayfasi, "Müşteri Yönetimi")

        self.tedarikci_yonetimi_sayfasi = TedarikciYonetimiSayfasi(self, self.db_manager, self) # TedarikciYonetimiSayfasi mevcut ve eklendi
        self.tab_widget.addTab(self.tedarikci_yonetimi_sayfasi, "Tedarikçi Yönetimi")

        self.fatura_listesi_sayfasi = FaturaListesiSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.fatura_listesi_sayfasi, "Faturalar")

        self.siparis_listesi_sayfasi = SiparisListesiSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.siparis_listesi_sayfasi, "Sipariş Yönetimi")
        
        self.kasa_banka_yonetimi_sayfasi = KasaBankaYonetimiSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.kasa_banka_yonetimi_sayfasi, "Kasa/Banka")

        self.finansal_islemler_sayfasi = FinansalIslemlerSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.finansal_islemler_sayfasi, "Finansal İşlemler")

        self.gelir_gider_sayfasi = GelirGiderSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.gelir_gider_sayfasi, "Gelir/Gider")

        self.raporlama_merkezi_sayfasi = RaporlamaMerkeziSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.raporlama_merkezi_sayfasi, "Raporlama Merkezi")
        
        self.urun_nitelik_yonetimi_sekmesi = UrunNitelikYonetimiSekmesi(self, self.db_manager, self) # Doğru sınıf adı
        self.tab_widget.addTab(self.urun_nitelik_yonetimi_sekmesi, "Nitelik Yönetimi")

        # Servis sınıflarını başlat
        self.fatura_service = FaturaService(self.db_manager)
        self.toplu_islem_service = TopluIslemService(self.db_manager)
        self.raporlama = Raporlama(self.db_manager)

        # UI bağlantıları ve ilk yüklemeler
        self._setup_ui_connections() 
        self._initial_load_data()

        # Menü eylemleri bağlantıları
        self.actionStok_Kart.triggered.connect(self._stok_karti_penceresi_ac)
        self.actionM_teri_Kart.triggered.connect(self._musteri_karti_penceresi_ac)
        self.actionTedarik_i_Kart.triggered.connect(self._tedarikci_karti_penceresi_ac)
        self.actionKasa_Banka_Kart.triggered.connect(self._kasa_banka_karti_penceresi_ac)
        self.actionGelir_Gider_Kart.triggered.connect(self._gelir_gider_karti_penceresi_ac)
        self.actionFatura_Kart.triggered.connect(self._fatura_karti_penceresi_ac)
        self.action_rsiparis.triggered.connect(self._siparis_karti_penceresi_ac)
        self.actionCari_Hareketler.triggered.connect(self._cari_hareketler_penceresi_ac)
        self.actionNitelik_Y_netimi.triggered.connect(lambda: self.show_tab("Nitelik Yönetimi"))
        self.actionToplu_Veri_Aktar_m.triggered.connect(self._toplu_veri_aktarim_penceresi_ac)
        
        # Raporlar menüsü bağlantıları (raporlama merkezi sekmesini açacak şekilde güncellendi)
        self.actionM_teri_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionTedarik_i_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionStok_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionFatura_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionKasa_Banka_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionGelir_Gider_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionCari_Hareket_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionSiparis_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionNitelik_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))

        # Veritabanı işlemleri
        self.actionYedekle.triggered.connect(self._yedekle)
        self.actionGeri_Y_kle.triggered.connect(self._geri_yukle)
        self.actionAPI_Ayarlar.triggered.connect(self._api_ayarlari_penceresi_ac)

        # Durum çubuğunu güncelle
        self._update_status_bar()

    def show_tab(self, tab_name: str):
        """
        Verilen sekmeyi QTabWidget içinde gösterir.
        AnaSayfa'daki butonlardan çağrılacak metot.
        """
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == tab_name:
                self.tab_widget.setCurrentIndex(i)
                # Sekme içeriği yenileme mantığı (eğer sekme sınıfında varsa)
                current_widget = self.tab_widget.widget(i)
                if hasattr(current_widget, 'stok_listesini_yenile'):
                    current_widget.stok_listesini_yenile()
                elif hasattr(current_widget, 'musteri_listesini_yenile'):
                    current_widget.musteri_listesini_yenile()
                elif hasattr(current_widget, 'hesap_listesini_yenile'):
                    current_widget.hesap_listesini_yenile()
                elif hasattr(current_widget, 'fatura_listesini_yukle'):
                    current_widget.fatura_listesini_yukle()
                elif hasattr(current_widget, 'siparis_listesini_yukle'):
                    current_widget.siparis_listesini_yukle()
                elif hasattr(current_widget, 'gg_listesini_yukle'):
                    current_widget.gg_listesini_yukle()
                elif hasattr(current_widget, 'raporu_olustur_ve_yenile'):
                    current_widget.raporu_olustur_ve_yenile()
                elif hasattr(current_widget, '_kategori_listesini_yukle'): # Nitelik Yönetimi için
                    current_widget._kategori_listesini_yukle()
                    current_widget._marka_listesini_yukle()
                    current_widget._urun_grubu_listesini_yukle()
                    current_widget._urun_birimi_listesini_yukle()
                    current_widget._ulke_listesini_yukle()
                
                logger.info(f"Sekme '{tab_name}' gösterildi ve içeriği yenilendi (varsa).")
                return
        logger.warning(f"Sekme '{tab_name}' bulunamadı.")
        QMessageBox.warning(self, "Hata", f"'{tab_name}' sayfası bulunamadı.")

    def show_invoice_form(self, fatura_tipi, duzenleme_id=None, initial_data=None):
        """Fatura oluşturma/düzenleme penceresini açar."""
        from pencereler import FaturaPenceresi # Bu import burada yapılmalı
        self.fatura_penceresi = FaturaPenceresi(
            self, # parent
            self.db_manager,
            self, # app_ref
            fatura_tipi=fatura_tipi, # fura_tipi -> fatura_tipi olarak düzeltildi
            duzenleme_id=duzenleme_id,
            yenile_callback=self._initial_load_data,
            initial_data=initial_data
        )
        self.fatura_penceresi.show()
        logger.info(f"Fatura penceresi açıldı. Tip: {fatura_tipi}, ID: {duzenleme_id}")

    def set_status_message(self, message, color="black"):
        """Durum çubuğuna mesaj yazar ve rengini ayarlar."""
        self.statusBar().setStyleSheet(f"QStatusBar {{ color: {color}; }}")
        self.statusBar().showMessage(message)
        logger.info(f"Durum Mesajı ({color}): {message}")

    def show_order_form(self, siparis_tipi, siparis_id_duzenle=None, initial_data=None):
        """Sipariş oluşturma/düzenleme penceresini açar."""
        from pencereler import SiparisPenceresi # Bu import burada yapılmalı
        self.siparis_penceresi = SiparisPenceresi(
            self, # parent
            self.db_manager,
            self, # app_ref
            siparis_tipi=siparis_tipi,
            siparis_id_duzenle=siparis_id_duzenle,
            yenile_callback=self._initial_load_data, # Sipariş kaydedilince ana ekranı yenile
            initial_data=initial_data
        )
        self.siparis_penceresi.show()
        logger.info(f"Sipariş penceresi açıldı. Tip: {siparis_tipi}, ID: {siparis_id_duzenle}")

    # --- App Sınıfının Metodları ---
    def _initialize_db_manager(self):
        """OnMuhasebe yöneticisini API URL'si ile başlatır."""
        try:
            self.db_manager = OnMuhasebe(api_base_url=self.config["api_base_url"])
            logger.info("Veritabanı yöneticisi API modu ile başarıyla başlatıldı.")
        except ConnectionError as e:
            QMessageBox.critical(self, "API Bağlantı Hatası",
                                 f"API'ye bağlanılamadı: {e}\n"
                                 "Lütfen API sunucusunun çalıştığından ve doğru adreste olduğundan emin olun.")
            logger.critical(f"Uygulama başlatılırken API bağlantı hatası: {e}")
            sys.exit(1)
        except Exception as e:
            QMessageBox.critical(self, "Uygulama Başlatma Hatası",
                                 f"Veritabanı yöneticisi başlatılırken beklenmeyen bir hata oluştu: {e}")
            logger.critical(f"Uygulama başlatılırken beklenmeyen hata: {e}")
            sys.exit(1)

    def _setup_ui_connections(self):
        # Eğer AnaSayfa üzerindeki butonlar show_tab'i çağırıyorsa, burada doğrudan bir bağlantıya gerek yok
        pass

    def _initial_load_data(self):
        """Uygulama başlangıcında veya veri güncellendiğinde ana ekrandaki verileri yükler."""
        if not self.db_manager:
            return
        self.ana_sayfa_widget.guncelle_ozet_bilgiler() # AnaSayfa'daki özet bilgileri güncelle
        logger.info("Ana ekran verileri API'den başarıyla yüklendi (AnaSayfa'nın metodları aracılığıyla).")

    def _set_default_dates(self):
        # Bu metod ilgili sayfalara taşınacak.
        pass

    # Pencereleri açma metodları (Menü Action'ları için)
    def _stok_karti_penceresi_ac(self):
        from pencereler import StokKartiPenceresi
        self.stok_karti_penceresi = StokKartiPenceresi(self, self.db_manager, app_ref=self)
        self.stok_karti_penceresi.show()
        # Stok kartı penceresi kapatıldığında ilgili stok listesini yenileme mekanizması kurulmalı
        if hasattr(self.stok_yonetimi_sayfasi, 'stok_listesini_yenile'):
            self.stok_karti_penceresi.data_updated.connect(self.stok_yonetimi_sayfasi.stok_listesini_yenile)

    def _musteri_karti_penceresi_ac(self):
        from pencereler import YeniMusteriEklePenceresi
        self.musteri_karti_penceresi = YeniMusteriEklePenceresi(self, self.db_manager, self.musteri_yonetimi_sayfasi.musteri_listesini_yenile, app_ref=self)
        self.musteri_karti_penceresi.show()

    def _tedarikci_karti_penceresi_ac(self):
        from pencereler import YeniTedarikciEklePenceresi
        self.tedarikci_karti_penceresi = YeniTedarikciEklePenceresi(self, self.db_manager, self.tedarikci_yonetimi_sayfasi.tedarikci_listesini_yenile, app_ref=self)
        self.tedarikci_karti_penceresi.show()

    def _kasa_banka_karti_penceresi_ac(self):
        from pencereler import YeniKasaBankaEklePenceresi
        self.kasa_banka_karti_penceresi = YeniKasaBankaEklePenceresi(self, self.db_manager, self.kasa_banka_yonetimi_sayfasi.hesap_listesini_yenile, app_ref=self)
        self.kasa_banka_karti_penceresi.show()

    def _gelir_gider_karti_penceresi_ac(self):
        from pencereler import YeniGelirGiderEklePenceresi
        self.gelir_gider_karti_penceresi = YeniGelirGiderEklePenceresi(self, self.db_manager, self.gelir_gider_sayfasi.gg_listesini_yukle, parent_app=self)
        self.gelir_gider_karti_penceresi.show()

    def _fatura_karti_penceresi_ac(self):
        from pencereler import FaturaPenceresi
        self.fatura_karti_penceresi = FaturaPenceresi(self, self.db_manager, app_ref=self, fatura_tipi="SATIŞ", yenile_callback=self.fatura_listesi_sayfasi.fatura_listesini_yukle)
        self.fatura_karti_penceresi.show()

    def _siparis_karti_penceresi_ac(self):
        from pencereler import SiparisPenceresi
        self.siparis_karti_penceresi = SiparisPenceresi(self, self.db_manager, app_ref=self, siparis_tipi="SATIŞ_SIPARIS", yenile_callback=self.siparis_listesi_sayfasi.siparis_listesini_yukle)
        self.siparis_karti_penceresi.show()

    def _on_cari_secim_yapildi(self, cari_id, cari_turu_str):
        from pencereler import CariHesapEkstresiPenceresi
        cari_tip_enum = "MUSTERI" if cari_turu_str == "Müşteri" else "TEDARIKCI"
        dialog = CariHesapEkstresiPenceresi(
            self,
            self.db_manager, # db yerine db_manager
            cari_id, 
            cari_tip_enum, 
            cari_turu_str 
        )
        dialog.exec()
        self.set_status_message(f"Cari '{cari_turu_str}' ID: {cari_id} için ekstre açıldı.")

    def _cari_hareketler_penceresi_ac(self):
        from pencereler import CariSecimPenceresi
        dialog = CariSecimPenceresi(self, self.db_manager, "GENEL", self._on_cari_secim_yapildi)
        dialog.exec()

    def _nitelik_yonetimi_penceresi_ac(self):
        from pencereler import UrunNitelikYonetimiPenceresi
        self.nitelik_yonetimi_penceresi = UrunNitelikYonetimiPenceresi(self, self.db_manager, app_ref=self, refresh_callback=lambda: self.show_tab("Nitelik Yönetimi"))
        self.nitelik_yonetimi_penceresi.show()
        
    def _toplu_veri_aktarim_penceresi_ac(self):
        from pencereler import TopluVeriEklePenceresi
        self.toplu_veri_aktarim_penceresi = TopluVeriEklePenceresi(self, self.db_manager)
        self.toplu_veri_aktarim_penceresi.show()

    def _rapor_olustur(self, rapor_tipi):
        try:
            self.show_tab("Raporlama Merkezi")
            # Belirli bir rapor tipi seçimi için RaporlamaMerkeziSayfası'nda bir metot olması gerekebilir.
            # Örneğin: self.raporlama_merkezi_sayfasi.select_report_tab(rapor_tipi)
            self.set_status_message(f"{rapor_tipi.capitalize()} raporu için Raporlama Merkezi açıldı.")

        except Exception as e:
            QMessageBox.critical(self, "Rapor Hatası", f"{rapor_tipi.capitalize()} raporu oluşturulurken beklenmeyen bir hata oluştu: {e}")
            logger.error(f"{rapor_tipi.capitalize()} raporu oluşturulurken hata: {e}")

    def _yedekle(self):
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "Veritabanı Yedekle", "", "Yedek Dosyası (*.bak);;Tüm Dosyalar (*)")
            if file_path:
                self.db_manager.database_backup(file_path)
                QMessageBox.information(self, "Yedekleme", "Veritabanı yedekleme isteği gönderildi. Sunucu tarafında kontrol edin.")
                logger.info(f"Veritabanı yedekleme isteği gönderildi: {file_path}")
        except NotImplementedError as e:
            QMessageBox.warning(self, "Yedekleme Hatası", str(e))
            logger.warning(f"Yedekleme hatası: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Yedekleme Hatası", f"Veritabanı yedeklenirken bir hata oluştu: {e}")
            logger.error(f"Veritabanı yedeklenirken hata: {e}")

    def _geri_yukle(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "Veritabanı Geri Yükle", "", "Yedek Dosyası (*.bak);;Tüm Dosyalar (*)")
            if file_path:
                reply = QMessageBox.question(self, "Geri Yükleme Onayı",
                                             "Mevcut veritabanı üzerine yazılacak. Devam etmek istiyor musunuz?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.db_manager.database_restore(file_path)
                    QMessageBox.information(self, "Geri Yükleme", "Veritabanı geri yükleme isteği gönderildi. Sunucu tarafında kontrol edin.")
                    logger.info(f"Veritabanı geri yükleme isteği gönderildi: {file_path}")
        except NotImplementedError as e:
            QMessageBox.warning(self, "Geri Yükleme Hatası", str(e))
            logger.warning(f"Geri yükleme hatası: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Geri Yükleme Hatası", f"Veritabanı geri yüklenirken bir hata oluştu: {e}")
            logger.error(f"Veritabanı geri yüklenirken hata: {e}")

    def _pdf_olusturma_islemi(self, data, filename="rapor.pdf"):
        logger.info(f"PDF oluşturma işlemi çağrıldı. Veri boyutu: {len(data)} - Dosya Adı: {filename}")
        QMessageBox.information(self, "PDF Oluşturma", "PDF oluşturma işlevi entegrasyonu tamamlanmadı. Lütfen raporlama modülünü kontrol edin.")

    def _update_status_bar(self):
        self.statusBar().showMessage("Uygulama hazır.")

    def _api_ayarlari_penceresi_ac(self):
        from pencereler import APIAyarlariPenceresi
        self.api_ayarlari_penceresi = APIAyarlariPenceresi(self.config)
        self.api_ayarlari_penceresi.api_url_updated.connect(self._handle_api_url_update)
        self.api_ayarlari_penceresi.show()

    def _handle_api_url_update(self, new_api_url):
        self.config["api_base_url"] = new_api_url
        save_config(self.config)
        try:
            self.db_manager = OnMuhasebe(api_base_url=self.config["api_base_url"])
            QMessageBox.information(self, "API Ayarları", "API URL'si güncellendi ve bağlantı yenilendi.")
            logger.info(f"API URL'si güncellendi: {new_api_url}")
            self._initial_load_data()
        except Exception as e:
            QMessageBox.critical(self, "API Bağlantı Hatası",
                                 f"Yeni API adresine bağlanılamadı: {e}\n"
                                 "Lütfen API sunucusunun çalıştığından ve doğru adreste olduğundan emin olun.")
            logger.critical(f"API URL güncellemesi sonrası bağlantı hatası: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.AlternateBase, QColor(230, 230, 230))
    palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.Button, QColor(200, 200, 200))
    palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    window = App()
    window.show()
    sys.exit(app.exec())