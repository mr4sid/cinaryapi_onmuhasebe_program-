import sys
import os
import json
import logging
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QFileDialog
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QDate, Signal # Signal import edildi

# Kendi modüllerimiz
from arayuz import Ui_MainWindow
from veritabani import OnMuhasebe  # Güncellenmiş OnMuhasebe sınıfını içe aktarıyoruz
from hizmetler import FaturaService, TopluIslemService
from raporlar import Raporlama
# pencereler modülünden gerekli sınıfları burada import edeceğiz
# Ancak döngüsel bağımlılığı önlemek için fonksiyonların içinde import edeceğiz.

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
    if os.path.exists(_config_path):
        try:
            with open(_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Hatalı config.json dosyası: {_config_path}. Varsayılan yapılandırma kullanılıyor.")
            return {"api_base_url": "http://127.0.0.1:8000"}
    return {"api_base_url": "http://127.0.0.1:8000"} # Varsayılan API URL'si

def save_config(config):
    """Uygulama yapılandırmasını kaydeder."""
    try:
        with open(_config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except IOError as e:
        logger.error(f"Config dosyası kaydedilirken hata oluştu: {e}")

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Yapılandırmayı yükle
        self.config = load_config()

        # OnMuhasebe sınıfını API URL'si ile başlat
        self.db_manager = None # Başlangıçta None olarak ayarla
        self._initialize_db_manager()

        # Servis sınıflarını başlat
        self.fatura_service = FaturaService(self.db_manager)
        self.toplu_islem_service = TopluIslemService(self.db_manager)
        self.raporlama = Raporlama(self.db_manager)

        # UI bağlantıları ve ilk yüklemeler
        self._setup_ui_connections()
        self._initial_load_data()

        # Varsayılan tarihleri ayarla
        self._set_default_dates()

        # Menü eylemleri bağlantıları
        self.ui.actionStok_Kart.triggered.connect(self._stok_karti_penceresi_ac)
        self.ui.actionM_teri_Kart.triggered.connect(self._musteri_karti_penceresi_ac)
        self.ui.actionTedarik_i_Kart.triggered.connect(self._tedarikci_karti_penceresi_ac)
        self.ui.actionKasa_Banka_Kart.triggered.connect(self._kasa_banka_karti_penceresi_ac)
        self.ui.actionGelir_Gider_Kart.triggered.connect(self._gelir_gider_karti_penceresi_ac)
        self.ui.actionFatura_Kart.triggered.connect(self._fatura_karti_penceresi_ac)
        self.ui.action_rsiparis.triggered.connect(self._siparis_karti_penceresi_ac)
        self.ui.actionCari_Hareketler.triggered.connect(self._cari_hareketler_penceresi_ac)
        self.ui.actionNitelik_Y_netimi.triggered.connect(self._nitelik_yonetimi_penceresi_ac)
        self.ui.actionToplu_Veri_Aktar_m.triggered.connect(self._toplu_veri_aktarim_penceresi_ac)

        # Raporlar menüsü bağlantıları
        self.ui.actionM_teri_Raporu.triggered.connect(lambda: self._rapor_olustur("musteri"))
        self.ui.actionTedarik_i_Raporu.triggered.connect(lambda: self._rapor_olustur("tedarikci"))
        self.ui.actionStok_Raporu.triggered.connect(lambda: self._rapor_olustur("stok"))
        self.ui.actionFatura_Raporu.triggered.connect(lambda: self._rapor_olustur("fatura"))
        self.ui.actionKasa_Banka_Raporu.triggered.connect(lambda: self._rapor_olustur("kasa_banka"))
        self.ui.actionGelir_Gider_Raporu.triggered.connect(lambda: self._rapor_olustur("gelir_gider"))
        self.ui.actionCari_Hareket_Raporu.triggered.connect(lambda: self._rapor_olustur("cari_hareket"))
        self.ui.actionSiparis_Raporu.triggered.connect(lambda: self._rapor_olustur("siparis"))
        self.ui.actionNitelik_Raporu.triggered.connect(lambda: self._rapor_olustur("nitelik"))

        # Veritabanı işlemleri
        self.ui.actionYedekle.triggered.connect(self._yedekle)
        self.ui.actionGeri_Y_kle.triggered.connect(self._geri_yukle)
        self.ui.actionAPI_Ayarlar.triggered.connect(self._api_ayarlari_penceresi_ac)

        # Durum çubuğunu güncelle
        self._update_status_bar()

    def _initialize_db_manager(self):
        """OnMuhasebe yöneticisini API URL'si ile başlatır."""
        try:
            self.db_manager = OnMuhasebe(api_base_url=self.config["api_base_url"])
            logger.info("Veritabanı yöneticisi API modu ile başarıyla başlatıldı.")
        except Exception as e:
            QMessageBox.critical(self, "API Bağlantı Hatası",
                                 f"API'ye bağlanılamadı: {e}\n"
                                 "Lütfen API sunucusunun çalıştığından ve doğru adreste olduğundan emin olun.")
            logger.critical(f"Uygulama başlatılırken API bağlantı hatası: {e}")
            sys.exit(1) # Uygulamayı kapat

    def _setup_ui_connections(self):
        # Ana pencere üzerindeki buton bağlantıları burada yapılabilir
        # Örneğin: self.ui.pushButton_musteriEkle.clicked.connect(self._musteri_ekle)
        pass

    def _initial_load_data(self):
        """Uygulama başlangıcında veya veri güncellendiğinde ana ekrandaki verileri yükler."""
        if not self.db_manager: # db_manager başlatılmamışsa çık
            return

        try:
            musteri_sayisi = len(self.db_manager.musteri_listesi_al())
            self.ui.label_musteriSayisi.setText(str(musteri_sayisi))

            tedarikci_sayisi = len(self.db_manager.tedarikci_listesi_al())
            self.ui.label_tedarikciSayisi.setText(str(tedarikci_sayisi))

            stok_sayisi = len(self.db_manager.stok_listesi_al())
            self.ui.label_stokSayisi.setText(str(stok_sayisi))

            fatura_sayisi = len(self.db_manager.fatura_listesi_al())
            self.ui.label_faturaSayisi.setText(str(fatura_sayisi))

            # Kasa/Banka toplam bakiyesi gibi özet bilgiler
            kasalar = self.db_manager.kasa_banka_listesi_al()
            toplam_bakiye = sum(kasa.get("bakiye", 0) for kasa in kasalar)
            self.ui.label_kasaBankaBakiye.setText(f"{toplam_bakiye:.2f} TL")

            # Gelir/Gider özetleri (örneğin son 30 gün)
            gelirler = self.db_manager.gelir_gider_listesi_al() # Tüm gelir/giderleri al
            # Burada tarih filtrelemesi API tarafında yapılmıyorsa, client tarafında yapılmalı
            # Ancak API'de tarih filtreleme parametreleri eklenebilir.
            toplam_gelir = sum(g.get("tutar", 0) for g in gelirler if g.get("tur") == "Gelir")
            toplam_gider = sum(g.get("tutar", 0) for g in gelirler if g.get("tur") == "Gider")
            self.ui.label_toplamGelir.setText(f"{toplam_gelir:.2f} TL")
            self.ui.label_toplamGider.setText(f"{toplam_gider:.2f} TL")

            logger.info("Ana ekran verileri API'den başarıyla yüklendi.")
        except ConnectionError:
            QMessageBox.critical(self, "Bağlantı Hatası",
                                 "API sunucusuna bağlanılamadı. Lütfen sunucunun çalıştığından emin olun.")
            logger.critical("Ana ekran verileri yüklenirken API bağlantı hatası.")
        except Exception as e:
            QMessageBox.warning(self, "Veri Yükleme Hatası", f"Ana ekran verileri yüklenirken bir hata oluştu: {e}")
            logger.error(f"Ana ekran verileri yüklenirken hata: {e}")

    def _set_default_dates(self):
        """Tarih alanlarını varsayılan değerlerle ayarlar (örneğin bugünün tarihi)."""
        today = QDate.currentDate()
        self.ui.dateEdit_baslangic.setDate(today.addMonths(-1)) # Son 1 ay
        self.ui.dateEdit_bitis.setDate(today)

    # Pencereleri açma metodları
    def _stok_karti_penceresi_ac(self):
        from pencereler import StokKartiPenceresi
        self.stok_karti_penceresi = StokKartiPenceresi(self.db_manager)
        self.stok_karti_penceresi.show()
        self.stok_karti_penceresi.data_updated.connect(self._initial_load_data) # Veri güncellendiğinde ana ekranı yenile

    def _musteri_karti_penceresi_ac(self):
        from pencereler import MusteriKartiPenceresi
        self.musteri_karti_penceresi = MusteriKartiPenceresi(self.db_manager)
        self.musteri_karti_penceresi.show()
        self.musteri_karti_penceresi.data_updated.connect(self._initial_load_data)

    def _tedarikci_karti_penceresi_ac(self):
        from pencereler import TedarikciKartiPenceresi
        self.tedarikci_karti_penceresi = TedarikciKartiPenceresi(self.db_manager)
        self.tedarikci_karti_penceresi.show()
        self.tedarikci_karti_penceresi.data_updated.connect(self._initial_load_data)

    def _kasa_banka_karti_penceresi_ac(self):
        from pencereler import KasaBankaKartiPenceresi
        self.kasa_banka_karti_penceresi = KasaBankaKartiPenceresi(self.db_manager)
        self.kasa_banka_karti_penceresi.show()
        self.kasa_banka_karti_penceresi.data_updated.connect(self._initial_load_data)

    def _gelir_gider_karti_penceresi_ac(self):
        from pencereler import GelirGiderKartiPenceresi
        self.gelir_gider_karti_penceresi = GelirGiderKartiPenceresi(self.db_manager)
        self.gelir_gider_karti_penceresi.show()
        self.gelir_gider_karti_penceresi.data_updated.connect(self._initial_load_data)

    def _fatura_karti_penceresi_ac(self):
        from pencereler import FaturaKartiPenceresi
        self.fatura_karti_penceresi = FaturaKartiPenceresi(self.db_manager, self.fatura_service)
        self.fatura_karti_penceresi.show()
        self.fatura_karti_penceresi.data_updated.connect(self._initial_load_data)

    def _siparis_karti_penceresi_ac(self):
        from pencereler import SiparisKartiPenceresi
        self.siparis_karti_penceresi = SiparisKartiPenceresi(self.db_manager)
        self.siparis_karti_penceresi.show()
        self.siparis_karti_penceresi.data_updated.connect(self._initial_load_data)

    def _cari_hareketler_penceresi_ac(self):
        from pencereler import CariHareketlerPenceresi
        self.cari_hareketler_penceresi = CariHareketlerPenceresi(self.db_manager)
        self.cari_hareketler_penceresi.show()
        self.cari_hareketler_penceresi.data_updated.connect(self._initial_load_data)

    def _nitelik_yonetimi_penceresi_ac(self):
        from pencereler import NitelikYonetimiPenceresi
        self.nitelik_yonetimi_penceresi = NitelikYonetimiPenceresi(self.db_manager)
        self.nitelik_yonetimi_penceresi.show()
        self.nitelik_yonetimi_penceresi.data_updated.connect(self._initial_load_data)

    def _toplu_veri_aktarim_penceresi_ac(self):
        from pencereler import TopluVeriAktarimPenceresi
        self.toplu_veri_aktarim_penceresi = TopluVeriAktarimPenceresi(self.db_manager, self.toplu_islem_service)
        self.toplu_veri_aktarim_penceresi.show()
        self.toplu_veri_aktarim_penceresi.data_updated.connect(self._initial_load_data)

    def _rapor_olustur(self, rapor_tipi):
        """Belirtilen tipte bir rapor oluşturur."""
        try:
            self.raporlama.rapor_olustur(rapor_tipi)
            QMessageBox.information(self, "Rapor Oluşturuldu", f"{rapor_tipi.capitalize()} raporu başarıyla oluşturuldu.")
        except Exception as e:
            QMessageBox.warning(self, "Rapor Hatası", f"{rapor_tipi.capitalize()} raporu oluşturulurken bir hata oluştu: {e}")
            logger.error(f"{rapor_tipi.capitalize()} raporu oluşturulurken hata: {e}")

    def _yedekle(self):
        """
        Veritabanı yedekleme işlevi. Artık doğrudan API üzerinden yedekleme beklenir.
        """
        try:
            # Kullanıcıya nereye yedekleneceğini sor
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
        """
        Veritabanı geri yükleme işlevi. Artık doğrudan API üzerinden geri yükleme beklenir.
        """
        try:
            # Kullanıcıdan geri yüklenecek dosyayı seçmesini iste
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
        """
        PDF oluşturma işlemi. Bu fonksiyon, artık veritabanına doğrudan erişmemelidir.
        Raporlama sınıfı üzerinden veri almalı veya API'den PDF oluşturma hizmeti kullanmalıdır.
        Şimdilik sadece örnek bir log mesajı bırakılmıştır.
        """
        logger.info(f"PDF oluşturma işlemi çağrıldı. Veri boyutu: {len(data)} - Dosya Adı: {filename}")
        # Burada raporlama.py'deki Raporlama sınıfı kullanılmalı veya API'den bir PDF oluşturma endpoint'i çağrılmalıdır.
        # Örneğin:
        # self.raporlama.pdf_olustur(data, filename)
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
