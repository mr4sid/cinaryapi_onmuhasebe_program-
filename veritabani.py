import requests
import json
import logging
import os

# Logger kurulumu
# Loglama seviyesini ve formatını ayarlayabilirsiniz.
# Örneğin, logları bir dosyaya yazmak için:
# logging.basicConfig(filename='application.log', level=logging.INFO,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# Eğer ana uygulama tarafından zaten yapılandırılmadıysa, basit bir konsol çıktısı için:
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class OnMuhasebe:
    def __init__(self, api_base_url="http://127.0.0.1:8000"):
        """
        Veritabanı bağlantılarını ve API iletişimini yöneten sınıf.
        Artık doğrudan veritabanı yerine FastAPI API'si ile iletişim kurar.
        """
        self.api_base_url = api_base_url
        logger.info(f"OnMuhasebe başlatıldı. API Base URL: {self.api_base_url}")

    def _make_api_request(self, method, endpoint, data=None, params=None):
        """
        Genel API isteği gönderici.
        """
        url = f"{self.api_base_url}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, params=params)
            elif method == "POST":
                response = requests.post(url, json=data, params=params)
            elif method == "PUT":
                response = requests.put(url, json=data, params=params)
            elif method == "DELETE":
                response = requests.delete(url, params=params)
            else:
                raise ValueError(f"Desteklenmeyen HTTP metodu: {method}")

            response.raise_for_status()  # HTTP hataları için istisna fırlatır (4xx veya 5xx)
            return response.json()
        except requests.exceptions.ConnectionError as e:
            logger.error(f"API'ye bağlanılamadı: {url}. Sunucunun çalıştığından emin olun. Hata: {e}")
            raise ConnectionError(f"API'ye bağlanılamadı. Lütfen sunucunun çalıştığından emin olun.") from e
        except requests.exceptions.Timeout as e:
            logger.error(f"API isteği zaman aşımına uğradı: {url}. Hata: {e}")
            raise TimeoutError(f"API isteği zaman aşımına uğradı.") from e
        except requests.exceptions.HTTPError as e:
            # API'den gelen hata detaylarını kullanıcıya iletmek için
            try:
                error_detail = response.json().get("detail", "Bilinmeyen API hatası.")
            except json.JSONDecodeError:
                error_detail = response.text
            logger.error(f"API HTTP hatası: {url}, Durum Kodu: {response.status_code}, Yanıt: {error_detail}. Hata: {e}")
            raise ValueError(f"API hatası ({response.status_code}): {error_detail}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"API isteği sırasında genel hata oluştu: {url}. Hata: {e}")
            raise RuntimeError(f"API isteği sırasında bir hata oluştu: {e}") from e
        except Exception as e:
            logger.critical(f"Beklenmedik bir hata oluştu: {e}")
            raise

    # Müşteri İşlemleri
    def musteri_ekle(self, musteri_bilgileri):
        """Yeni bir müşteri ekler."""
        return self._make_api_request("POST", "/musteriler/", data=musteri_bilgileri)

    def musteri_listesi_al(self, aktif=None):
        """Müşteri listesini alır. İsteğe bağlı olarak aktif/pasif müşterileri filtreler."""
        params = {"aktif": aktif} if aktif is not None else None
        return self._make_api_request("GET", "/musteriler/", params=params)

    def musteri_guncelle(self, musteri_id, musteri_bilgileri):
        """Belirtilen ID'ye sahip müşteriyi günceller."""
        return self._make_api_request("PUT", f"/musteriler/{musteri_id}", data=musteri_bilgileri)

    def musteri_sil(self, musteri_id):
        """Belirtilen ID'ye sahip müşteriyi siler."""
        return self._make_api_request("DELETE", f"/musteriler/{musteri_id}")

    def musteri_getir_by_id(self, musteri_id):
        """Belirtilen ID'ye sahip müşteriyi getirir."""
        return self._make_api_request("GET", f"/musteriler/{musteri_id}")

    def musteri_adi_getir_by_id(self, musteri_id):
        """Belirtilen ID'ye sahip müşterinin adını getirir."""
        try:
            musteri = self.musteri_getir_by_id(musteri_id)
            return musteri.get("ad_soyad", "Bilinmeyen Müşteri")
        except Exception as e:
            logger.warning(f"Müşteri adı getirilirken hata: {e}")
            return "Bilinmeyen Müşteri"

    # Tedarikçi İşlemleri
    def tedarikci_ekle(self, tedarikci_bilgileri):
        """Yeni bir tedarikçi ekler."""
        return self._make_api_request("POST", "/tedarikciler/", data=tedarikci_bilgileri)

    def tedarikci_listesi_al(self, aktif=None):
        """Tedarikçi listesini alır. İsteğe bağlı olarak aktif/pasif tedarikçileri filtreler."""
        params = {"aktif": aktif} if aktif is not None else None
        return self._make_api_request("GET", "/tedarikciler/", params=params)

    def tedarikci_guncelle(self, tedarikci_id, tedarikci_bilgileri):
        """Belirtilen ID'ye sahip tedarikçiyi günceller."""
        return self._make_api_request("PUT", f"/tedarikciler/{tedarikci_id}", data=tedarikci_bilgileri)

    def tedarikci_sil(self, tedarikci_id):
        """Belirtilen ID'ye sahip tedarikçiyi siler."""
        return self._make_api_request("DELETE", f"/tedarikciler/{tedarikci_id}")

    def tedarikci_getir_by_id(self, tedarikci_id):
        """Belirtilen ID'ye sahip tedarikçiyi getirir."""
        return self._make_api_request("GET", f"/tedarikciler/{tedarikci_id}")

    def tedarikci_adi_getir_by_id(self, tedarikci_id):
        """Belirtilen ID'ye sahip tedarikçinin adını getirir."""
        try:
            tedarikci = self.tedarikci_getir_by_id(tedarikci_id)
            return tedarikci.get("ad_soyad", "Bilinmeyen Tedarikçi")
        except Exception as e:
            logger.warning(f"Tedarikçi adı getirilirken hata: {e}")
            return "Bilinmeyen Tedarikçi"

    # Stok İşlemleri
    def stok_ekle(self, stok_bilgileri):
        """Yeni bir stok ekler."""
        return self._make_api_request("POST", "/stoklar/", data=stok_bilgileri)

    def stok_listesi_al(self, aktif=None):
        """Stok listesini alır. İsteğe bağlı olarak aktif/pasif stokları filtreler."""
        params = {"aktif": aktif} if aktif is not None else None
        return self._make_api_request("GET", "/stoklar/", params=params)

    def stok_guncelle(self, stok_id, stok_bilgileri):
        """Belirtilen ID'ye sahip stoğu günceller."""
        return self._make_api_request("PUT", f"/stoklar/{stok_id}", data=stok_bilgileri)

    def stok_sil(self, stok_id):
        """Belirtilen ID'ye sahip stoğu siler."""
        return self._make_api_request("DELETE", f"/stoklar/{stok_id}")

    def stok_getir_by_id(self, stok_id):
        """Belirtilen ID'ye sahip stoğu getirir."""
        return self._make_api_request("GET", f"/stoklar/{stok_id}")

    def stok_adi_getir_by_id(self, stok_id):
        """Belirtilen ID'ye sahip stoğun adını getirir."""
        try:
            stok = self.stok_getir_by_id(stok_id)
            return stok.get("ad", "Bilinmeyen Stok")
        except Exception as e:
            logger.warning(f"Stok adı getirilirken hata: {e}")
            return "Bilinmeyen Stok"

    # Fatura İşlemleri (API'de ayrı fatura kalemleri yok, tüm fatura tek gönderiliyor)
    def fatura_ekle(self, fatura_bilgileri):
        """Yeni bir fatura ekler."""
        return self._make_api_request("POST", "/faturalar/", data=fatura_bilgileri)

    def fatura_listesi_al(self):
        """Fatura listesini alır."""
        return self._make_api_request("GET", "/faturalar/")

    def fatura_guncelle(self, fatura_id, fatura_bilgileri):
        """Belirtilen ID'ye sahip faturayı günceller."""
        return self._make_api_request("PUT", f"/faturalar/{fatura_id}", data=fatura_bilgileri)

    def fatura_sil(self, fatura_id):
        """Belirtilen ID'ye sahip faturayı siler."""
        return self._make_api_request("DELETE", f"/faturalar/{fatura_id}")

    def fatura_getir_by_id(self, fatura_id):
        """Belirtilen ID'ye sahip faturayı getirir."""
        return self._make_api_request("GET", f"/faturalar/{fatura_id}")

    # Kasa/Banka İşlemleri
    def kasa_banka_ekle(self, hesap_bilgileri):
        """Yeni bir kasa/banka hesabı ekler."""
        return self._make_api_request("POST", "/kasalar_bankalar/", data=hesap_bilgileri)

    def kasa_banka_listesi_al(self):
        """Kasa/banka hesap listesini alır."""
        return self._make_api_request("GET", "/kasalar_bankalar/")

    def kasa_banka_guncelle(self, hesap_id, hesap_bilgileri):
        """Belirtilen ID'ye sahip kasa/banka hesabını günceller."""
        return self._make_api_request("PUT", f"/kasalar_bankalar/{hesap_id}", data=hesap_bilgileri)

    def kasa_banka_sil(self, hesap_id):
        """Belirtilen ID'ye sahip kasa/banka hesabını siler."""
        return self._make_api_request("DELETE", f"/kasalar_bankalar/{hesap_id}")

    def kasa_banka_getir_by_id(self, hesap_id):
        """Belirtilen ID'ye sahip kasa/banka hesabını getirir."""
        return self._make_api_request("GET", f"/kasalar_bankalar/{hesap_id}")

    # Gelir/Gider İşlemleri
    def gelir_gider_ekle(self, islem_bilgileri):
        """Yeni bir gelir/gider işlemi ekler."""
        return self._make_api_request("POST", "/gelir_gider/", data=islem_bilgileri)

    def gelir_gider_listesi_al(self):
        """Gelir/gider işlem listesini alır."""
        return self._make_api_request("GET", "/gelir_gider/")

    def gelir_gider_guncelle(self, islem_id, islem_bilgileri):
        """Belirtilen ID'ye sahip gelir/gider işlemini günceller."""
        return self._make_api_request("PUT", f"/gelir_gider/{islem_id}", data=islem_bilgileri)

    def gelir_gider_sil(self, islem_id):
        """Belirtilen ID'ye sahip gelir/gider işlemini siler."""
        return self._make_api_request("DELETE", f"/gelir_gider/{islem_id}")

    def gelir_gider_getir_by_id(self, islem_id):
        """Belirtilen ID'ye sahip gelir/gider işlemini getirir."""
        return self._make_api_request("GET", f"/gelir_gider/{islem_id}")

    # Cari Hareketler İşlemleri (Cari hareketler genellikle otomatik oluşur, bu yüzden sadece listeleme ve getirme)
    def cari_hareket_listesi_al(self, cari_id=None, tur=None):
        """Cari hareket listesini alır. İsteğe bağlı olarak cari ID ve türüne göre filtreler."""
        params = {}
        if cari_id is not None:
            params["cari_id"] = cari_id
        if tur is not None:
            params["tur"] = tur
        return self._make_api_request("GET", "/cari_hareketler/", params=params)

    def cari_hareket_getir_by_id(self, hareket_id):
        """Belirtilen ID'ye sahip cari hareketi getirir."""
        return self._make_api_request("GET", f"/cari_hareketler/{hareket_id}")

    # Nitelik İşlemleri (Ürünler için özellikler gibi)
    def nitelik_ekle(self, nitelik_bilgileri):
        """Yeni bir nitelik (özellik) ekler."""
        return self._make_api_request("POST", "/nitelikler/", data=nitelik_bilgileri)

    def nitelik_listesi_al(self):
        """Nitelik listesini alır."""
        return self._make_api_request("GET", "/nitelikler/")

    def nitelik_guncelle(self, nitelik_id, nitelik_bilgileri):
        """Belirtilen ID'ye sahip niteliği günceller."""
        return self._make_api_request("PUT", f"/nitelikler/{nitelik_id}", data=nitelik_bilgileri)

    def nitelik_sil(self, nitelik_id):
        """Belirtilen ID'ye sahip niteliği siler."""
        return self._make_api_request("DELETE", f"/nitelikler/{nitelik_id}")

    def nitelik_getir_by_id(self, nitelik_id):
        """Belirtilen ID'ye sahip niteliği getirir."""
        return self._make_api_request("GET", f"/nitelikler/{nitelik_id}")

    # Sipariş İşlemleri
    def siparis_ekle(self, siparis_bilgileri):
        """Yeni bir sipariş ekler."""
        return self._make_api_request("POST", "/siparisler/", data=siparis_bilgileri)

    def siparis_listesi_al(self):
        """Sipariş listesini alır."""
        return self._make_api_request("GET", "/siparisler/")

    def siparis_guncelle(self, siparis_id, siparis_bilgileri):
        """Belirtilen ID'ye sahip siparişi günceller."""
        return self._make_api_request("PUT", f"/siparisler/{siparis_id}", data=siparis_bilgileri)

    def siparis_sil(self, siparis_id):
        """Belirtilen ID'ye sahip siparişi siler."""
        return self._make_api_request("DELETE", f"/siparisler/{siparis_id}")

    def siparis_getir_by_id(self, siparis_id):
        """Belirtilen ID'ye sahip siparişi getirir."""
        return self._make_api_request("GET", f"/siparisler/{siparis_id}")

    def database_backup(self, backup_path):
        """
        Bu fonksiyon artık doğrudan SQLite yedeklemesi yapmaz.
        API üzerinden bir yedekleme endpoint'i varsa kullanılabilir,
        aksi takdirde bu işlevsellik sunucu tarafında yönetilmelidir.
        Şimdilik boş bırakılmıştır ve NotImplementedError fırlatır.
        """
        logger.warning("Veritabanı yedekleme işlevi artık doğrudan masaüstü uygulamasında desteklenmiyor. Lütfen sunucu tarafı yedekleme çözümlerini kullanın.")
        # Eğer API'de /backup gibi bir endpoint varsa, buraya çağrı eklenebilir.
        # Örneğin: return self._make_api_request("GET", "/backup")
        raise NotImplementedError("Veritabanı yedekleme işlevi henüz API üzerinden entegre edilmemiştir.")


    def database_restore(self, restore_path):
        """
        Bu fonksiyon artık doğrudan SQLite geri yüklemesi yapmaz.
        API üzerinden bir geri yükleme endpoint'i varsa kullanılabilir,
        aksi takdirde bu işlevsellik sunucu tarafında yönetilmelidir.
        Şimdilik boş bırakılmıştır ve NotImplementedError fırlatır.
        """
        logger.warning("Veritabanı geri yükleme işlevi artık doğrudan masaüstü uygulamasında desteklenmiyor. Lütfen sunucu tarafı geri yükleme çözümlerini kullanın.")
        # Eğer API'de /restore gibi bir endpoint varsa, buraya çağrı eklenebilir.
        # Örneğin: return self._make_api_request("POST", "/restore", files={'file': open(restore_path, 'rb')})
        raise NotImplementedError("Veritabanı geri yükleme işlevi henüz API üzerinden entegre edilmemiştir.")

    def create_tables(self, cursor=None):
        """
        Bu fonksiyon artık doğrudan masaüstü uygulamasında tablo oluşturmaz.
        Tabloların API başlatıldığında veya create_pg_tables.py scripti ile oluşturulması beklenir.
        """
        logger.info("create_tables çağrıldı ancak artık veritabanı doğrudan yönetilmiyor. Tabloların API veya create_pg_tables.py aracılığıyla oluşturulduğu varsayılıyor.")
        pass # Masaüstü uygulamasının bu fonksiyonu çağırması gerekiyorsa boş bırakılabilir veya kaldırılabilir.
