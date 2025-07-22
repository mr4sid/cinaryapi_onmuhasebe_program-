# main.py
import sys
import os
import json
import logging
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QFileDialog, 
    QWidget, QMenuBar, QStatusBar)
from PySide6.QtGui import QAction
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QDate, Signal

# Kendi modüllerimiz
from arayuz import AnaSayfa # Artık AnaSayfa'yı doğruca içe aktarıyoruz
from veritabani import OnMuhasebe  # Güncellenmiş OnMuhasebe sınıfını içe aktarıyoruz
from hizmetler import FaturaService, TopluIslemService
from raporlar import Raporlama # raporlar.py içindeki Raporlama sınıfını kullandığımızdan emin olmalıyız

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
    # config.py'den varsayılan API URL'ini al
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

# main.py dosyanızdaki Ui_MainWindow_Minimal sınıfının tamamını aşağıdaki ile değiştirin.

class Ui_MainWindow_Minimal:
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1200, 800) # Varsayılan pencere boyutu

        # Menü Çubuğu ve Durum Çubuğu oluşturma
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)

        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        # --- QAction'ları (Menü Öğeleri) tanımlama ---
        # ÖNEMLİ: action'ları doğrudan MainWindow objesine (App instance) ekliyoruz.
        
        # Kartlar Menüsü Action'ları
        MainWindow.actionStok_Kart = QAction(MainWindow) # MainWindow.actionStok_Kart olarak düzeltildi
        MainWindow.actionStok_Kart.setObjectName("actionStok_Kart")
        MainWindow.actionStok_Kart.setText("Stok Kartı")

        MainWindow.actionM_teri_Kart = QAction(MainWindow) # Düzeltildi
        MainWindow.actionM_teri_Kart.setObjectName("actionM_teri_Kart")
        MainWindow.actionM_teri_Kart.setText("Müşteri Kartı")
        
        MainWindow.actionTedarik_i_Kart = QAction(MainWindow) # Düzeltildi
        MainWindow.actionTedarik_i_Kart.setObjectName("actionTedarik_i_Kart")
        MainWindow.actionTedarik_i_Kart.setText("Tedarikçi Kartı")

        MainWindow.actionKasa_Banka_Kart = QAction(MainWindow) # Düzeltildi
        MainWindow.actionKasa_Banka_Kart.setObjectName("actionKasa_Banka_Kart")
        MainWindow.actionKasa_Banka_Kart.setText("Kasa/Banka Kartı")

        MainWindow.actionGelir_Gider_Kart = QAction(MainWindow) # Düzeltildi
        MainWindow.actionGelir_Gider_Kart.setObjectName("actionGelir_Gider_Kart")
        MainWindow.actionGelir_Gider_Kart.setText("Gelir/Gider Kartı")

        MainWindow.actionFatura_Kart = QAction(MainWindow) # Düzeltildi
        MainWindow.actionFatura_Kart.setObjectName("actionFatura_Kart")
        MainWindow.actionFatura_Kart.setText("Fatura Kartı")

        MainWindow.action_rsiparis = QAction(MainWindow) # Düzeltildi
        MainWindow.action_rsiparis.setObjectName("action_rsiparis")
        MainWindow.action_rsiparis.setText("Sipariş Kartı")

        MainWindow.actionCari_Hareketler = QAction(MainWindow) # Düzeltildi
        MainWindow.actionCari_Hareketler.setObjectName("actionCari_Hareketler")
        MainWindow.actionCari_Hareketler.setText("Cari Hareketler")

        MainWindow.actionNitelik_Y_netimi = QAction(MainWindow) # Düzeltildi
        MainWindow.actionNitelik_Y_netimi.setObjectName("actionNitelik_Y_netimi")
        MainWindow.actionNitelik_Y_netimi.setText("Nitelik Yönetimi")

        MainWindow.actionToplu_Veri_Aktar_m = QAction(MainWindow) # Düzeltildi
        MainWindow.actionToplu_Veri_Aktar_m.setObjectName("actionToplu_Veri_Aktar_m")
        MainWindow.actionToplu_Veri_Aktar_m.setText("Toplu Veri Aktarımı")
        
        # Raporlar Menüsü Action'ları
        MainWindow.actionM_teri_Raporu = QAction(MainWindow) # Düzeltildi
        MainWindow.actionM_teri_Raporu.setObjectName("actionM_teri_Raporu")
        MainWindow.actionM_teri_Raporu.setText("Müşteri Raporu")

        MainWindow.actionTedarik_i_Raporu = QAction(MainWindow) # Düzeltildi
        MainWindow.actionTedarik_i_Raporu.setObjectName("actionTedarik_i_Raporu")
        MainWindow.actionTedarik_i_Raporu.setText("Tedarikçi Raporu")

        MainWindow.actionStok_Raporu = QAction(MainWindow) # Düzeltildi
        MainWindow.actionStok_Raporu.setObjectName("actionStok_Raporu")
        MainWindow.actionStok_Raporu.setText("Stok Raporu")

        MainWindow.actionFatura_Raporu = QAction(MainWindow) # Düzeltildi
        MainWindow.actionFatura_Raporu.setObjectName("actionFatura_Raporu")
        MainWindow.actionFatura_Raporu.setText("Fatura Raporu")

        MainWindow.actionKasa_Banka_Raporu = QAction(MainWindow) # Düzeltildi
        MainWindow.actionKasa_Banka_Raporu.setObjectName("actionKasa_Banka_Raporu")
        MainWindow.actionKasa_Banka_Raporu.setText("Kasa/Banka Raporu")

        MainWindow.actionGelir_Gider_Raporu = QAction(MainWindow) # Düzeltildi
        MainWindow.actionGelir_Gider_Raporu.setObjectName("actionGelir_Gider_Raporu")
        MainWindow.actionGelir_Gider_Raporu.setText("Gelir/Gider Raporu")

        MainWindow.actionCari_Hareket_Raporu = QAction(MainWindow) # Düzeltildi
        MainWindow.actionCari_Hareket_Raporu.setObjectName("actionCari_Hareket_Raporu")
        MainWindow.actionCari_Hareket_Raporu.setText("Cari Hareket Raporu")

        MainWindow.actionSiparis_Raporu = QAction(MainWindow) # Düzeltildi
        MainWindow.actionSiparis_Raporu.setObjectName("actionSiparis_Raporu")
        MainWindow.actionSiparis_Raporu.setText("Sipariş Raporu")

        MainWindow.actionNitelik_Raporu = QAction(MainWindow) # Düzeltildi
        MainWindow.actionNitelik_Raporu.setObjectName("actionNitelik_Raporu")
        MainWindow.actionNitelik_Raporu.setText("Nitelik Raporu")

        # Veritabanı Menüsü Action'ları
        MainWindow.actionYedekle = QAction(MainWindow) # Düzeltildi
        MainWindow.actionYedekle.setObjectName("actionYedekle")
        MainWindow.actionYedekle.setText("Yedekle")

        MainWindow.actionGeri_Y_kle = QAction(MainWindow) # Düzeltildi
        MainWindow.actionGeri_Y_kle.setObjectName("actionGeri_Y_kle")
        MainWindow.actionGeri_Y_kle.setText("Geri Yükle")

        MainWindow.actionAPI_Ayarlar = QAction(MainWindow) # Düzeltildi
        MainWindow.actionAPI_Ayarlar.setObjectName("actionAPI_Ayarlar")
        MainWindow.actionAPI_Ayarlar.setText("API Ayarları")


        # Menüleri oluşturma ve Action'ları ekleme (Örnek)
        # Menüye action eklerken de MainWindow objesinden almalıyız.
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

        # QMainWindow'un temel UI'ını (menü, durum çubuğu vb.) kuracak geçici sınıfı kullanıyoruz
        self.ui_main_window_setup = Ui_MainWindow_Minimal()
        self.ui_main_window_setup.setupUi(self) # Bu çağrı action'ları self (App instance) üzerine ekler.

        # Pencere başlığını ayarla
        self.setWindowTitle("Çınar Yapı Ön Muhasebe Programı")

        self.config = load_config()

        # db_manager'ı diğer servisler ve UI elemanları kullanmadan ÖNCE başlat
        self.db_manager = None
        self._initialize_db_manager()

        # AnaSayfa (merkezi widget içeriği) örneğini oluştur
        # self.ui yerine self.ana_sayfa_widget gibi daha açıklayıcı bir isim kullanıyoruz
        self.ana_sayfa_widget = AnaSayfa(self, self.db_manager, self)
        self.setCentralWidget(self.ana_sayfa_widget) # AnaSayfa'yı merkezi widget olarak ayarla

        # Servis sınıflarını başlat (db_manager artık tanımlı)
        self.fatura_service = FaturaService(self.db_manager)
        self.toplu_islem_service = TopluIslemService(self.db_manager)
        self.raporlama = Raporlama(self.db_manager)

        # UI bağlantıları ve ilk yüklemeler
        self._setup_ui_connections() 
        self._initial_load_data()

        # Varsayılan tarihleri ayarla (şimdilik yorum satırı, sonra ilgili sayfalara taşınacak)
        # self._set_default_dates()

        # Menü eylemleri bağlantıları (Artık self.action... olarak erişilir)
        # self.ui.actionStok_Kart yerine self.actionStok_Kart kullanılır.
        self.actionStok_Kart.triggered.connect(self._stok_karti_penceresi_ac)
        self.actionM_teri_Kart.triggered.connect(self._musteri_karti_penceresi_ac)
        self.actionTedarik_i_Kart.triggered.connect(self._tedarikci_karti_penceresi_ac)
        self.actionKasa_Banka_Kart.triggered.connect(self._kasa_banka_karti_penceresi_ac)
        self.actionGelir_Gider_Kart.triggered.connect(self._gelir_gider_karti_penceresi_ac)
        self.actionFatura_Kart.triggered.connect(self._fatura_karti_penceresi_ac)
        self.action_rsiparis.triggered.connect(self._siparis_karti_penceresi_ac)
        self.actionCari_Hareketler.triggered.connect(self._cari_hareketler_penceresi_ac)
        self.actionNitelik_Y_netimi.triggered.connect(self._nitelik_yonetimi_penceresi_ac)
        self.actionToplu_Veri_Aktar_m.triggered.connect(self._toplu_veri_aktarim_penceresi_ac)

        # Raporlar menüsü bağlantıları
        self.actionM_teri_Raporu.triggered.connect(lambda: self._rapor_olustur("musteri"))
        self.actionTedarik_i_Raporu.triggered.connect(lambda: self._rapor_olustur("tedarikci"))
        self.actionStok_Raporu.triggered.connect(lambda: self._rapor_olustur("stok"))
        self.actionFatura_Raporu.triggered.connect(lambda: self._rapor_olustur("fatura"))
        self.actionKasa_Banka_Raporu.triggered.connect(lambda: self._rapor_olustur("kasa_banka"))
        self.actionGelir_Gider_Raporu.triggered.connect(lambda: self._rapor_olustur("gelir_gider"))
        self.actionCari_Hareket_Raporu.triggered.connect(lambda: self._rapor_olustur("cari_hareket"))
        self.actionSiparis_Raporu.triggered.connect(lambda: self._rapor_olustur("siparis"))
        self.actionNitelik_Raporu.triggered.connect(lambda: self._rapor_olustur("nitelik"))

        # Veritabanı işlemleri
        self.actionYedekle.triggered.connect(self._yedekle)
        self.actionGeri_Y_kle.triggered.connect(self._geri_yukle)
        self.actionAPI_Ayarlar.triggered.connect(self._api_ayarlari_penceresi_ac)

        # Durum çubuğunu güncelle
        self._update_status_bar()

    # --- App Sınıfının Metodları ---
    def _initialize_db_manager(self):
        """OnMuhasebe yöneticisini API URL'si ile başlatır."""
        try:
            self.db_manager = OnMuhasebe(api_base_url=self.config["api_base_url"])
            logger.info("Veritabanı yöneticisi API modu ile başarıyla başlatıldı.")
        except ConnectionError as e: # Sadece ConnectionError yakalıyoruz, diğerleri sistem hatası olabilir.
            QMessageBox.critical(self, "API Bağlantı Hatası",
                                 f"API'ye bağlanılamadı: {e}\n"
                                 "Lütfen API sunucusunun çalıştığından ve doğru adreste olduğundan emin olun.")
            logger.critical(f"Uygulama başlatılırken API bağlantı hatası: {e}")
            sys.exit(1) # Uygulamayı kapat
        except Exception as e:
            QMessageBox.critical(self, "Uygulama Başlatma Hatası",
                                 f"Veritabanı yöneticisi başlatılırken beklenmeyen bir hata oluştu: {e}")
            logger.critical(f"Uygulama başlatılırken beklenmeyen hata: {e}")
            sys.exit(1)

    def _setup_ui_connections(self):
        # Ana pencere üzerindeki buton bağlantıları burada yapılabilir
        # Örneğin: self.ana_sayfa_widget.ui.pushButton_musteriEkle.clicked.connect(self._musteri_ekle)
        pass

    def _initial_load_data(self):
        """Uygulama başlangıcında veya veri güncellendiğinde ana ekrandaki verileri yükler."""
        if not self.db_manager: # db_manager başlatılmamışsa çık
            return

        # AnaSayfa'daki özet bilgileri güncellemek için AnaSayfa'nın kendi metodunu çağırıyoruz.
        self.ana_sayfa_widget.guncelle_ozet_bilgiler()
        
        logger.info("Ana ekran verileri API'den başarıyla yüklendi (AnaSayfa'nın metodları aracılığıyla).")
        # Eski label_musteriSayisi gibi direkt erişimler kaldırıldı.
        # Eğer AnaSayfa'daki metrik kartlar bu bilgileri göstermek için yeterliyse, ek bir şeye gerek yok.
        # Aksi takdirde, AnaSayfa sınıfında yeni etiketler tanımlanıp buradan güncellenmeli veya guncelle_ozet_bilgiler() metodu genişletilmeli.

    def _set_default_dates(self):
        """Tarih alanlarını varsayılan değerlerle ayarlar (örneğin bugünün tarihi)."""
        # Bu metod şu anda AnaSayfa'da bulunmayan elemanlara eriştiği için yorum satırı yapılmıştı.
        # Eğer tarih alanları başka bir sayfaya aitse, o sayfanın yüklendiği zaman bu metod çağrılmalı
        # veya ilgili sayfa objesine referans üzerinden erişilmelidir.
        today = QDate.currentDate()
        # self.ana_sayfa_widget.dateEdit_baslangic.setDate(today.addMonths(-1)) # Örneğin, eğer AnaSayfa'da olsaydı
        # self.ana_sayfa_widget.dateEdit_bitis.setDate(today)

    # Pencereleri açma metodları
    # Bu metodlar artık doğrudan App sınıfının (QMainWindow) action'larına bağlanacak.
    # self.ui.actionStok_Kart yerine self.actionStok_Kart kullanılır.
    # Her bir pencere App nesnesini (self) parent olarak almalı ve db_manager'ı iletmelidir.
    
    def _stok_karti_penceresi_ac(self):
        from pencereler import StokKartiPenceresi
        # self (App instance) parent olarak, self.db_manager ve self (app_ref) parametre olarak geçilir.
        self.stok_karti_penceresi = StokKartiPenceresi(self, self.db_manager, app_ref=self) # Corrected class name as StokKartiPenceresi
        self.stok_karti_penceresi.show()
        self.stok_karti_penceresi.data_updated.connect(self._initial_load_data) # Veri güncellendiğinde ana ekranı yenile

    def _musteri_karti_penceresi_ac(self):
        from pencereler import YeniMusteriEklePenceresi # Doğru sınıf adını kullandığımızdan emin olalım
        self.musteri_karti_penceresi = YeniMusteriEklePenceresi(self, self.db_manager, self._initial_load_data, app_ref=self)
        self.musteri_karti_penceresi.show()
        # YeniMusteriEklePenceresi'nin data_updated sinyali yok, onun yerine yenile_callback'i var.
        # Bu yüzden _initial_load_data'yı doğrudan yenile_callback olarak veriyoruz.

    def _tedarikci_karti_penceresi_ac(self):
        from pencereler import YeniTedarikciEklePenceresi
        self.tedarikci_karti_penceresi = YeniTedarikciEklePenceresi(self, self.db_manager, self._initial_load_data, app_ref=self)
        self.tedarikci_karti_penceresi.show()

    def _kasa_banka_karti_penceresi_ac(self):
        from pencereler import YeniKasaBankaEklePenceresi
        self.kasa_banka_karti_penceresi = YeniKasaBankaEklePenceresi(self, self.db_manager, self._initial_load_data, app_ref=self)
        self.kasa_banka_karti_penceresi.show()

    def _gelir_gider_karti_penceresi_ac(self):
        from pencereler import YeniGelirGiderEklePenceresi
        self.gelir_gider_karti_penceresi = YeniGelirGiderEklePenceresi(self, self.db_manager, self._initial_load_data, parent_app=self)
        self.gelir_gider_karti_penceresi.show()

    def _fatura_karti_penceresi_ac(self):
        from pencereler import FaturaPenceresi # FaturaPenceresi pencereler.py içinde
        # FaturaKartiPenceresi artık FaturaPenceresi'ne dönüştü.
        # FaturaPenceresi'nin init'i parent, db_manager, fatura_tipi, duzenleme_id, yenile_callback alıyor.
        # Varsayılan olarak SATIŞ faturası açabiliriz.
        self.fatura_karti_penceresi = FaturaPenceresi(self, self.db_manager, fatura_tipi="SATIŞ", yenile_callback=self._initial_load_data)
        self.fatura_karti_parti_penceresi.show() # Corrected from self.fatura_karti_penceresi to self.fatura_karti_parti_penceresi

    def _siparis_karti_penceresi_ac(self):
        from pencereler import SiparisPenceresi # SiparisPenceresi pencereler.py içinde
        self.siparis_karti_penceresi = SiparisPenceresi(self, self.db_manager, app_ref=self, siparis_tipi="SATIŞ_SIPARIS", yenile_callback=self._initial_load_data)
        self.siparis_karti_penceresi.show()

    def _cari_hareketler_penceresi_ac(self):
        from pencereler import CariHesapEkstresiPenceresi # CariHesapEkstresiPenceresi
        # CariHesapEkstresiPenceresi doğrudan cari_id, cari_tip ve pencere_basligi bekler.
        # Menüden açıldığında belirli bir cari ID'si olmadığı için genel bir liste açılması gerekecek.
        # Şimdilik bir uyarı mesajı ile placeholder olarak bırakalım veya doğrudan bir cari seçim diyalogu açabiliriz.
        QMessageBox.information(self, "Bilgi", "Cari Hareketler penceresi doğrudan açılamıyor. Lütfen önce bir cari seçimi yapın veya ilgili cari ekstresi üzerinden erişin.")

    def _nitelik_yonetimi_penceresi_ac(self):
        from pencereler import UrunNitelikYonetimiPenceresi # Doğru sınıf adını kullanalım
        self.nitelik_yonetimi_penceresi = UrunNitelikYonetimiPenceresi(self, self.db_manager, app_ref=self, refresh_callback=self._initial_load_data)
        self.nitelik_yonetimi_penceresi.show()
        
    def _toplu_veri_aktarim_penceresi_ac(self):
        from pencereler import TopluVeriEklePenceresi
        self.toplu_veri_aktarim_penceresi = TopluVeriEklePenceresi(self, self.db_manager)
        self.toplu_veri_aktarim_penceresi.show()
        # TopluVeriEklePenceresi'nin doğrudan self._initial_load_data'yı bağlamadığı varsayılır,
        # kendi içinde yenileme çağrılarını yapmalıdır.

    def _rapor_olustur(self, rapor_tipi):
        """Belirtilen tipte bir rapor oluşturur."""
        try:
            success, message = self.raporlama.rapor_olustur(rapor_tipi) # Raporlama sınıfının döndürdüğü success ve message'ı kullan
            if success:
                QMessageBox.information(self, "Rapor Oluşturuldu", message)
            else:
                QMessageBox.warning(self, "Rapor Hatası", message)
            logger.info(f"{rapor_tipi.capitalize()} raporu oluşturma işlemi tamamlandı: {message}") # Bilgi seviyesinde logla
        except Exception as e:
            QMessageBox.critical(self, "Rapor Hatası", f"{rapor_tipi.capitalize()} raporu oluşturulurken beklenmeyen bir hata oluştu: {e}")
            logger.error(f"{rapor_tipi.capitalize()} raporu oluşturulurken hata: {e}")

    def _yedekle(self):
        """Veritabanı yedekleme işlevi. Artık doğrudan API üzerinden yedekleme beklenir."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "Veritabanı Yedekle", "", "Yedek Dosyası (*.bak);;Tüm Dosyalar (*)")
            if file_path:
                self.db_manager.database_backup(file_path) # Bu metot NotImplementedError fırlatıyor
                QMessageBox.information(self, "Yedekleme", "Veritabanı yedekleme isteği gönderildi. Sunucu tarafında kontrol edin.")
                logger.info(f"Veritabanı yedekleme isteği gönderildi: {file_path}")
        except NotImplementedError as e:
            QMessageBox.warning(self, "Yedekleme Hatası", str(e))
            logger.warning(f"Yedekleme hatası: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Yedekleme Hatası", f"Veritabanı yedeklenirken bir hata oluştu: {e}")
            logger.error(f"Veritabanı yedeklenirken hata: {e}")

    def _geri_yukle(self):
        """Veritabanı geri yükleme işlevi. Artık doğrudan API üzerinden geri yükleme beklenir."""
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
        """PDF oluşturma işlemi. Bu metod raporlama.py içindeki Raporlama sınıfı tarafından çağrılmalı."""
        logger.info(f"PDF oluşturma işlemi çağrıldı. Veri boyutu: {len(data)} - Dosya Adı: {filename}")
        QMessageBox.information(self, "PDF Oluşturma", "PDF oluşturma işlevi entegrasyonu tamamlanmadı. Lütfen raporlama modülünü kontrol edin.")

    def _update_status_bar(self):
        """Durum çubuğunu günceller."""
        self.statusBar().showMessage("Uygulama hazır.")

    def _api_ayarlari_penceresi_ac(self):
        """API Ayarları penceresini açar."""
        from pencereler import APIAyarlariPenceresi # Döngüsel bağımlılığı önlemek için burada import edildi
        self.api_ayarlari_penceresi = APIAyarlariPenceresi(self.config)
        self.api_ayarlari_penceresi.api_url_updated.connect(self._handle_api_url_update)
        self.api_ayarlari_penceresi.show()

    def _handle_api_url_update(self, new_api_url):
        """API URL'si güncellendiğinde tetiklenir."""
        self.config["api_base_url"] = new_api_url
        save_config(self.config)
        # Yeni API URL'si ile db_manager'ı yeniden başlat
        try:
            self.db_manager = OnMuhasebe(api_base_url=self.config["api_base_url"])
            QMessageBox.information(self, "API Ayarları", "API URL'si güncellendi ve bağlantı yenilendi.")
            logger.info(f"API URL'si güncellendi: {new_api_url}")
            self._initial_load_data() # Verileri yeniden yükle
        except Exception as e:
            QMessageBox.critical(self, "API Bağlantı Hatası",
                                 f"Yeni API adresine bağlanılamadı: {e}\n"
                                 "Lütfen API sunucusunun çalıştığından ve doğru adreste olduğundan emin olun.")
            logger.critical(f"API URL güncellemesi sonrası bağlantı hatası: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())