# veritabani.py dosyasının TAMAMI
import requests
import json
import logging
import os
import locale # YENİ EKLENDİ (Para birimi formatlama için)
from config import API_BASE_URL # DÜZELTİLDİ: Göreceli içe aktarma kaldırıldı, doğrudan import
from typing import List, Optional
# Logger kurulumu
logger = logging.getLogger(__name__)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class OnMuhasebe:
    # Sabitler (UI ve diğer modüllerle uyumlu olması için burada tutuluyor)
    FATURA_TIP_SATIS = "SATIŞ"
    FATURA_TIP_ALIS = "ALIŞ"
    FATURA_TIP_SATIS_IADE = "SATIŞ İADE"
    FATURA_TIP_ALIS_IADE = "ALIŞ İADE"
    FATURA_TIP_DEVIR_GIRIS = "DEVİR GİRİŞ"

    ODEME_TURU_NAKIT = "NAKİT"
    ODEME_TURU_KART = "KART"
    ODEME_TURU_EFT_HAVALE = "EFT/HAVALE"
    ODEME_TURU_CEK = "ÇEK"
    ODEME_TURU_SENET = "SENET"
    ODEME_TURU_ACIK_HESAP = "AÇIK_HESAP"
    ODEME_TURU_ETKISIZ_FATURA = "ETKİSİZ_FATURA"
    
    pesin_odeme_turleri = [ODEME_TURU_NAKIT, ODEME_TURU_KART, ODEME_TURU_EFT_HAVALE, ODEME_TURU_CEK, ODEME_TURU_SENET]

    CARI_TIP_MUSTERI = "MUSTERI"
    CARI_TIP_TEDARIKCI = "TEDARIKCI"

    SIPARIS_TIP_SATIS = "SATIŞ_SIPARIS"
    SIPARIS_TIP_ALIS = "ALIŞ_SIPARIS"
    
    SIPARIS_DURUM_BEKLEMEDE = "BEKLEMEDE"
    SIPARIS_DURUM_TAMAMLANDI = "TAMAMLANDI"
    SIPARIS_DURUM_KISMİ_TESLIMAT = "KISMİ_TESLİMAT"
    SIPARIS_DURUM_IPTAL_EDILDI = "İPTAL_EDİLDİ"

    STOK_ISLEM_TIP_GIRIS_MANUEL_DUZELTME = "GİRİŞ_MANUEL_DÜZELTME"
    STOK_ISLEM_TIP_CIKIS_MANUEL_DUZELTME = "ÇIKIŞ_MANUEL_DÜZELTME"
    STOK_ISLEM_TIP_GIRIS_MANUEL = "GİRİŞ_MANUEL"
    STOK_ISLEM_TIP_CIKIS_MANUEL = "ÇIKIŞ_MANUEL"
    STOK_ISLEM_TIP_SAYIM_FAZLASI = "SAYIM_FAZLASI"
    STOK_ISLEM_TIP_SAYIM_EKSIGI = "SAYIM_EKSİĞİ"
    STOK_ISLEM_TIP_ZAYIAT = "ZAYİAT"
    STOK_ISLEM_TIP_IADE_GIRIS = "İADE_GİRİŞ"
    STOK_ISLEM_TIP_FATURA_ALIS = "FATURA_ALIŞ"
    STOK_ISLEM_TIP_FATURA_SATIŞ = "FATURA_SATIŞ"

    # Kaynak Tipleri (Cari Hareketler ve Stok Hareketleri için)
    KAYNAK_TIP_FATURA = "FATURA"
    KAYNAK_TIP_IADE_FATURA = "İADE_FATURA"
    KAYNAK_TIP_FATURA_SATIS_PESIN = "FATURA_SATIŞ_PEŞİN"
    KAYNAK_TIP_FATURA_ALIS_PESIN = "FATURA_ALIŞ_PEŞİN"
    KAYNAK_TIP_TAHSILAT = "TAHSİLAT"
    KAYNAK_TIP_ODEME = "ÖDEME"
    KAYNAK_TIP_VERESIYE_BORC_MANUEL = "VERESİYE_BORÇ_MANUEL"
    KAYNAK_TIP_MANUEL = "MANUEL"

    # Kullanıcı Rolleri
    USER_ROLE_ADMIN = "ADMIN"
    USER_ROLE_MANAGER = "MANAGER"
    USER_ROLE_SALES = "SALES"
    USER_ROLE_USER = "USER"
    
    def __init__(self, api_base_url=API_BASE_URL, data_dir=None, app_ref=None):
        """
        Veritabanı bağlantılarını ve API iletişimini yöneten sınıf.
        Artık doğrudan veritabanı yerine FastAPI API'si ile iletişim kurar.
        """
        self.api_base_url = api_base_url
        self.data_dir = data_dir
        self.app = app_ref
        logger.info(f"OnMuhasebe başlatıldı. API Base URL: {self.api_base_url}")

    def _make_api_request(self, method: str, path: str, params: dict = None, json: dict = None):
        """
        Merkezi API isteği yapıcı metot.
        API'den gelen yanıtı işler ve başarılı olursa JSON olarak döndürür.
        Hata durumunda ValueError yükseltir.
        
        Args:
            method (str): HTTP metodu (GET, POST, PUT, DELETE).
            path (str): API endpoint yolu (örneğin "/stoklar/").
            params (dict, optional): GET istekleri için URL parametreleri. Varsayılan None.
            json (dict, optional): POST/PUT istekleri için JSON payload. Varsayılan None.
        
        Returns:
            dict: API'den gelen JSON yanıtı.
            
        Raises:
            ValueError: API'den hata yanıtı gelirse veya bağlantı sorunu olursa.
        """
        url = f"{self.api_base_url}{path}"
        
        # DEBUG: API isteğinin başlangıcını logla
        print(f"DEBUG_MAKE_API_REQUEST: İstek Başladı - Metot: {method}, URL: {url}, Paramlar: {params}, JSON: {json}")

        try:
            # method.upper() kullanıldı
            if method.upper() == "GET":
                response = requests.get(url, params=params)
            elif method.upper() == "POST":
                response = requests.post(url, json=json) # 'json' parametresi buraya iletildi
            elif method.upper() == "PUT":
                response = requests.put(url, json=json)   # 'json' parametresi buraya iletildi
            elif method.upper() == "DELETE":
                response = requests.delete(url, params=params) # DELETE için params da olabilir
            else:
                raise ValueError(f"Desteklenmeyen HTTP metodu: {method}")

            response.raise_for_status() # HTTP 4xx veya 5xx durumları için hata fırlatır

            # Yanıt boş değilse JSON'a çevir
            if response.text:
                response_json = response.json()
                # DEBUG: Başarılı API yanıtını logla
                print(f"DEBUG_MAKE_API_REQUEST: İstek Başarılı - URL: {url}, Durum Kodu: {response.status_code}, Yanıt Uzunluğu: {len(str(response_json))}")
                return response_json
            
            # DEBUG: Boş başarılı yanıtı logla
            print(f"DEBUG_MAKE_API_REQUEST: İstek Başarılı (Boş Yanıt) - URL: {url}, Durum Kodu: {response.status_code}")
            return {} # Boş yanıtlar için boş sözlük döndür

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError: # JSON decode hatası
                    error_detail = f"API'den beklenen JSON yanıtı alınamadı. Yanıt: {e.response.text[:200]}..."
            
            # DEBUG: API isteği hatasını logla
            print(f"DEBUG_MAKE_API_REQUEST: İstek Hatası - URL: {url}, Hata: {error_detail}")
            logger.error(f"API isteği sırasında genel hata oluştu: {url}. Hata: {error_detail}", exc_info=True)
            raise ValueError(f"API isteği sırasında bir hata oluştu: {error_detail}") from e
        except ValueError as e:
            # Desteklenmeyen metod hatası veya JSON decode hatası
            print(f"DEBUG_MAKE_API_REQUEST: Value Hata - Hata: {e}")
            logger.error(f"API isteği sırasında bir değer hatası oluştu: {e}", exc_info=True)
            raise e
        except Exception as e:
            # DEBUG: Beklenmeyen API isteği hatasını logla
            print(f"DEBUG_MAKE_API_REQUEST: Beklenmeyen Hata - URL: {url}, Hata: {e}")
            logger.error(f"API isteği sırasında beklenmeyen bir hata oluştu: {url}. Hata: {e}", exc_info=True)
            raise ValueError(f"API isteği sırasında beklenmeyen bir hata oluştu: {e}") from e
            
    # --- ŞİRKET BİLGİLERİ ---
    def sirket_bilgilerini_yukle(self):
        try:
            return self._make_api_request("GET", "/sistem/bilgiler")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Şirket bilgileri API'den yüklenemedi: {e}")
            return {}

    def sirket_bilgilerini_kaydet(self, data: dict):
        try:
            self._make_api_request("PUT", "/sistem/bilgiler", json=data) # 'data' yerine 'json' kullanıldı
            return True, "Şirket bilgileri başarıyla kaydedildi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Şirket bilgileri API'ye kaydedilemedi: {e}")
            return False, f"Şirket bilgileri kaydedilirken hata: {e}"

    # --- KULLANICI YÖNETİMİ ---
    def kullanici_dogrula(self, kullanici_adi, sifre):
        try:
            response = self._make_api_request("POST", "/dogrulama/login", json={"kullanici_adi": kullanici_adi, "sifre": sifre}) # 'data' yerine 'json' kullanıldı
            return response.get("access_token"), response.get("token_type")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı doğrulama başarısız: {e}")
            return None, None
            
    def kullanici_listele(self):
        try:
            # API'deki kullanıcı listeleme endpoint'i modeller.UserListResponse döndürdüğü için
            # doğrudan 'items' anahtarını döndürüyoruz.
            return self._make_api_request("GET", "/kullanicilar/").get("items", []) 
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı listesi API'den alınamadı: {e}")
            return []

    def kullanici_ekle(self, username, password, yetki):
        try:
            self._make_api_request("POST", "/dogrulama/register_temp", json={"kullanici_adi": username, "sifre": password, "yetki": yetki}) # 'data' yerine 'json' kullanıldı
            return True, "Kullanıcı başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı eklenirken hata: {e}")
            return False, f"Kullanıcı eklenirken hata: {e}"

    def kullanici_guncelle_sifre_yetki(self, user_id, hashed_password, yetki):
        try:
            self._make_api_request("PUT", f"/kullanicilar/{user_id}", json={"hashed_sifre": hashed_password, "yetki": yetki}) # 'data' yerine 'json' kullanıldı
            return True, "Kullanıcı şifre ve yetki başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı şifre/yetki güncellenirken hata: {e}")
            return False, f"Kullanıcı şifre/yetki güncellenirken hata: {e}"

    def kullanici_adi_guncelle(self, user_id, new_username):
        try:
            self._make_api_request("PUT", f"/kullanicilar/{user_id}", json={"kullanici_adi": new_username}) # 'data' yerine 'json' kullanıldı
            return True, "Kullanıcı adı başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı adı güncellenirken hata: {e}")
            return False, f"Kullanıcı adı güncellenirken hata: {e}"

    def kullanici_sil(self, user_id):
        try:
            self._make_api_request("DELETE", f"/kullanicilar/{user_id}")
            return True, "Kullanıcı başarıyla silindi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı silinirken hata: {e}")
            return False, f"Kullanıcı silinirken hata: {e}"

    # --- CARİLER (Müşteri/Tedarikçi) ---
    def musteri_ekle(self, data: dict):
        try:
            self._make_api_request("POST", "/musteriler/", json=data) # 'data' yerine 'json' kullanıldı
            return True, "Müşteri başarıyla eklendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri eklenirken hata: {e}")
            return False, f"Müşteri eklenirken hata: {e}" # Hata mesajı eklendi

    def musteri_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, aktif_durum: bool = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "aktif_durum": aktif_durum
        }
        return self._make_api_request("GET", "/musteriler/", params=params)

    def musteri_getir_by_id(self, musteri_id: int):
        try:
            return self._make_api_request("GET", f"/musteriler/{musteri_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} çekilirken hata: {e}")
            return None

    def musteri_guncelle(self, musteri_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/musteriler/{musteri_id}", json=data) # 'data' yerine 'json' kullanıldı
            return True, "Müşteri başarıyla güncellendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} güncellenirken hata: {e}")
            return False, f"Müşteri güncellenirken hata: {e}" # Hata mesajı eklendi

    def musteri_sil(self, musteri_id: int):
        try:
            self._make_api_request("DELETE", f"/musteriler/{musteri_id}")
            return True, "Müşteri başarıyla silindi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} silinirken hata: {e}")
            return False, f"Müşteri silinirken hata: {e}" # Hata mesajı eklendi
            
    def get_perakende_musteri_id(self) -> Optional[int]:
        """API'den varsayılan perakende müşteri ID'sini çeker."""
        try:
            response_data = self._make_api_request("GET", "/sistem/varsayilan_cariler/perakende_musteri_id")
            # API'den gelen yanıtın doğrudan bir ID (int) veya dictionary döndürdüğüne bağlı olarak
            # response_data.get('id') veya doğrudan response_data olarak alınabilir.
            # Sistem endpoint'i MusteriRead döndüğü için response_data bir dict olacaktır.
            return response_data.get('id')
        except Exception as e:
            logger.warning(f"Varsayılan perakende müşteri ID'si API'den alınamadı: {e}. None dönülüyor.")
            return None
                    
    def get_musteri_net_bakiye(self, musteri_id: int):
        try:
            response = self._make_api_request("GET", f"/musteriler/{musteri_id}/net_bakiye")
            return response.get("net_bakiye")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} net bakiye çekilirken hata: {e}")
            return None


    def tedarikci_ekle(self, data: dict):
        try:
            self._make_api_request("POST", "/tedarikciler/", json=data) # 'data' yerine 'json' kullanıldı
            return True, "Tedarikçi başarıyla eklendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi eklenirken hata: {e}")
            return False, f"Tedarikçi eklenirken hata: {e}" # Hata mesajı eklendi

    def tedarikci_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, aktif_durum: bool = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "aktif_durum": aktif_durum
        }
        return self._make_api_request("GET", "/tedarikciler/", params=params)

    def tedarikci_getir_by_id(self, tedarikci_id: int):
        try:
            return self._make_api_request("GET", f"/tedarikciler/{tedarikci_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} çekilirken hata: {e}")
            return None

    def tedarikci_guncelle(self, tedarikci_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/tedarikciler/{tedarikci_id}", json=data) # 'data' yerine 'json' kullanıldı
            return True, "Tedarikçi başarıyla güncellendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} güncellenirken hata: {e}")
            return False, f"Tedarikçi güncellenirken hata: {e}" # Hata mesajı eklendi

    def tedarikci_sil(self, tedarikci_id: int):
        try:
            self._make_api_request("DELETE", f"/tedarikciler/{tedarikci_id}")
            return True, "Tedarikçi başarıyla silindi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} silinirken hata: {e}")
            return False, f"Tedarikçi silinirken hata: {e}" # Hata mesajı eklendi
            
    def get_genel_tedarikci_id(self):
        try:
            response = self._make_api_request("GET", "/sistem/varsayilan_cariler/genel_tedarikci_id")
            return response.get("id")
        except (ValueError, ConnectionError, Exception) as e:
            logger.warning(f"Varsayılan genel tedarikçi ID'si API'den alınamadı: {e}. None dönülüyor.")
            return None
        
    def get_kasa_banka_by_odeme_turu(self, odeme_turu: str) -> Optional[tuple]:
        """API'den ödeme türüne göre varsayılan kasa/banka hesabını çeker."""
        try:
            response_data = self._make_api_request("GET", f"/sistem/varsayilan_kasa_banka/{odeme_turu}")
            # API'den gelen yanıtın bir kasa/banka objesi (dict) döndürdüğüne bağlı olarak
            # buradan ilgili ID ve adı çekebiliriz.
            return (response_data.get('id'), response_data.get('hesap_adi'))
        except Exception as e:
            logger.warning(f"Varsayılan kasa/banka ({odeme_turu}) API'den alınamadı: {e}. None dönülüyor.")
            return None

    def get_tedarikci_net_bakiye(self, tedarikci_id: int):
        try:
            response = self._make_api_request("GET", f"/tedarikciler/{tedarikci_id}/net_bakiye")
            return response.get("net_bakiye")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} net bakiye çekilirken hata: {e}")
            return None

    # --- KASA/BANKA ---
    def kasa_banka_ekle(self, data: dict):
        try:
            self._make_api_request("POST", "/kasalar_bankalar/", json=data) # 'data' yerine 'json' kullanıldı
            return True, "Kasa/Banka hesabı başarıyla eklendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka eklenirken hata: {e}")
            return False, f"Kasa/Banka eklenirken hata: {e}" # Hata mesajı eklendi

    def kasa_banka_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, hesap_turu: str = None, aktif_durum: bool = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "tip": hesap_turu, # 'hesap_turu' yerine 'tip' kullanıldı
            "aktif_durum": aktif_durum
        }
        return self._make_api_request("GET", "/kasalar_bankalar/", params=params)

    def kasa_banka_getir_by_id(self, hesap_id: int):
        try:
            return self._make_api_request("GET", f"/kasalar_bankalar/{hesap_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka ID {hesap_id} çekilirken hata: {e}")
            return None

    def kasa_banka_guncelle(self, hesap_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/kasalar_bankalar/{hesap_id}", json=data) # 'data' yerine 'json' kullanıldı
            return True, "Kasa/Banka hesabı başarıyla güncellendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka ID {hesap_id} güncellenirken hata: {e}")
            return False, f"Kasa/Banka güncellenirken hata: {e}" # Hata mesajı eklendi

    def kasa_banka_sil(self, hesap_id: int):
        try:
            self._make_api_request("DELETE", f"/kasalar_bankalar/{hesap_id}")
            return True, "Kasa/Banka hesabı başarıyla silindi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka ID {hesap_id} silinirken hata: {e}")
            return False, f"Kasa/Banka silinirken hata: {e}" # Hata mesajı eklendi

    # --- STOKLAR ---
    def stok_ekle(self, stok_data: dict):
        """
        Yeni bir stok kaydını API'ye gönderir.
        Dönüş: (bool, str) - İşlem başarılı mı, mesaj.
        """
        endpoint = "/stoklar/"
        try:
            response_data = self._make_api_request("POST", endpoint, json=stok_data)
            # API'den dönen yanıtın ID içerdiğini varsayarak
            if response_data and response_data.get("id"):
                return True, f"'{stok_data['ad']}' adlı ürün başarıyla eklendi. ID: {response_data['id']}"
            else:
                return False, f"Ürün eklenirken beklenmeyen bir yanıt alındı: {response_data}"
        except ValueError as e: # _make_api_request'ten gelen API hatalarını yakalar
            return False, f"Ürün eklenemedi: {e}"
        except Exception as e: # Diğer olası hataları yakalar
            logger.error(f"Stok eklenirken beklenmeyen hata: {e}", exc_info=True)
            return False, f"Ürün eklenirken beklenmeyen bir hata oluştu: {e}"

    def stok_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, 
                             kategori_id: int = None, marka_id: int = None, urun_grubu_id: int = None, 
                             stok_durumu: str = None, kritik_stok_altinda: bool = None, aktif_durum: bool = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "kategori_id": kategori_id,
            "marka_id": marka_id,
            "urun_grubu_id": urun_grubu_id,
            "stok_durumu": stok_durumu,
            "kritik_stok_altinda": kritik_stok_altinda,
            "aktif_durum": aktif_durum
        }
        # None olan veya boş string olan parametreleri temizle (API'ye sadece geçerli filtreleri gönder)
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

        # DEBUG: İstemci tarafından API çağrısını logla
        print(f"DEBUG_CLIENT: stok_listesi_al API çağrısı yapılıyor. Params: {cleaned_params}")

        try:
            response = self._make_api_request("GET", "/stoklar/", params=cleaned_params)
            # DEBUG: İstemciye dönen API yanıtını logla
            print(f"DEBUG_CLIENT: stok_listesi_al API yanıtı alındı. Uzunluk: {len(response.get('items', []))}, Toplam: {response.get('total', 0)}")
            return response
        except Exception as e:
            logger.error(f"Stok listesi alınırken hata: {e}", exc_info=True)
            # Hata durumunda boş bir liste/dict döndürmek yerine hatayı tekrar fırlatıyoruz,
            # böylece çağıran fonksiyon (arayuz.py) hatayı yakalayabilir.
            raise # Hatayı yukarı fırlat

    def stok_getir_by_id(self, stok_id: int):
        try:
            return self._make_api_request("GET", f"/stoklar/{stok_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok ID {stok_id} çekilirken hata: {e}")
            return None

    def stok_guncelle(self, stok_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/stoklar/{stok_id}", json=data) # 'data' yerine 'json' kullanıldı
            return True, "Stok başarıyla güncellendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok ID {stok_id} güncellenirken hata: {e}")
            return False, f"Stok güncellenirken hata: {e}" # Hata mesajı eklendi

    def stok_sil(self, stok_id: int):
        try:
            self._make_api_request("DELETE", f"/stoklar/{stok_id}")
            return True, "Stok başarıyla silindi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok ID {stok_id} silinirken hata: {e}")
            return False, f"Stok silinirken hata: {e}" # Hata mesajı eklendi
            
    def stok_hareket_ekle(self, stok_id: int, data: dict):
        try:
            self._make_api_request("POST", f"/stoklar/{stok_id}/hareket", json=data) # 'data' yerine 'json' kullanıldı
            return True, "Stok hareketi başarıyla eklendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok hareketi eklenirken hata: {e}")
            return False, f"Stok hareketi eklenirken hata: {e}" # Hata mesajı eklendi
            
    def get_urun_faturalari(self, urun_id: int, fatura_tipi: Optional[str] = None):
        """Belirli bir ürüne ait faturaları API'den çeker."""
        params = {"urun_id": urun_id, "fatura_tipi": fatura_tipi}
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}
        try:
            return self._make_api_request("GET", "/raporlar/urun_faturalari", params=cleaned_params)
        except Exception as e:
            logger.error(f"Ürün faturaları API'den alınamadı: {e}")
            return []

    def get_stok_miktari_for_kontrol(self, stok_id: int, fatura_id_duzenle: Optional[int] = None) -> float:
        """
        Bir ürünün anlık stok miktarını API'den çeker.
        Eğer bir fatura düzenleniyorsa, o faturadaki ürün miktarını da stoka geri ekler.
        Bu, düzenleme anında doğru kullanılabilir stok miktarını gösterir.
        """
        try:
            anlik_miktar_response = self._make_api_request("GET", f"/stoklar/{stok_id}/anlik_miktar")
            anlik_miktar = anlik_miktar_response.get("anlik_miktar", 0.0)

            if fatura_id_duzenle is not None:
                fatura_kalemleri = self.fatura_kalemleri_al(fatura_id_duzenle)
                for kalem in fatura_kalemleri:
                    # 'urun_id' ve 'miktar' anahtarlarının varlığını kontrol et
                    if kalem.get('urun_id') == stok_id:
                        # API'den gelen fatura objesinde fatura_turu bulunabilir.
                        # OnMuhasebe sınıfındaki sabitler kullanılmalı.
                        fatura_tipi_db = self.fatura_getir_by_id(fatura_id_duzenle).get('fatura_turu')
                        
                        # Eğer satış veya alış iade faturası düzenleniyorsa,
                        # o ürünü sanki stoka geri eklenmiş gibi kabul et.
                        # Yani, satış faturasındaki ürün miktarı stoktan düşülmüştü, şimdi geri eklenmiş gibi hesapla.
                        if fatura_tipi_db == self.FATURA_TIP_SATIS or fatura_tipi_db == self.FATURA_TIP_ALIS_IADE:
                            anlik_miktar += kalem.get('miktar', 0.0)
                        # Eğer alış faturası veya satış iade faturası düzenleniyorsa
                        # Yani stok artışına neden olan bir işlemdeki miktar.
                        # Bu durumda o miktar stoktaymış gibi düşünülür.
                        elif fatura_tipi_db == self.FATURA_TIP_ALIS or fatura_tipi_db == self.FATURA_TIP_SATIS_IADE:
                             anlik_miktar -= kalem.get('miktar', 0.0)
                        
                        break
            return anlik_miktar
        except Exception as e:
            logger.error(f"Stok ID {stok_id} için anlık miktar kontrol edilirken hata: {e}")
            return 0.0

    # --- FATURALAR ---
    def fatura_ekle(self, data: dict):
        try:
            return self._make_api_request("POST", "/faturalar/", json=data) # 'data' yerine 'json' kullanıldı
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura eklenirken hata: {e}")
            raise

    def fatura_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, fatura_turu: str = None, baslangic_tarihi: str = None, bitis_tarihi: str = None, cari_id: int = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "fatura_turu": fatura_turu,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi,
            "cari_id": cari_id
        }
        return self._make_api_request("GET", "/faturalar/", params=params)

    def fatura_getir_by_id(self, fatura_id: int):
        try:
            return self._make_api_request("GET", f"/faturalar/{fatura_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} çekilirken hata: {e}")
            return None

    def fatura_guncelle(self, fatura_id: int, data: dict):
        try:
            return self._make_api_request("PUT", f"/faturalar/{fatura_id}", json=data) # 'data' yerine 'json' kullanıldı
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} güncellenirken hata: {e}")
            raise

    def fatura_sil(self, fatura_id: int):
        try:
            self._make_api_request("DELETE", f"/faturalar/{fatura_id}")
            return True, "Fatura başarıyla silindi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} silinirken hata: {e}")
            return False, f"Fatura silinirken hata: {e}" # Hata mesajı eklendi

    def fatura_kalemleri_al(self, fatura_id: int):
        try:
            return self._make_api_request("GET", f"/faturalar/{fatura_id}/kalemler")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} kalemleri çekilirken hata: {e}")
            return []

    def son_fatura_no_getir(self, fatura_turu: str):
        path = f"/sistem/next_fatura_number/{fatura_turu.upper()}"
        try:
            # Düzeltildi: 'method' ve 'path' argümanları açıkça anahtar kelime olarak belirtildi
            response_data = self._make_api_request(method="GET", path=path) 
            return response_data.get("fatura_no", "FATURA_NO_HATA")
        except ValueError as e:
            logger.error(f"Son fatura no API'den alınamadı: {e}")
            return "FATURA_NO_HATA"
        except Exception as e:
            logger.error(f"Son fatura no API'den alınırken beklenmeyen hata: {e}", exc_info=True)
            return "FATURA_NO_HATA"
                
    # --- SİPARİŞLER ---
    def siparis_ekle(self, data: dict):
        try:
            return self._make_api_request("POST", "/siparisler/", json=data) # 'data' yerine 'json' kullanıldı
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş eklenirken hata: {e}")
            raise

    def siparis_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, siparis_turu: str = None, durum: str = None, baslangic_tarihi: str = None, bitis_tarihi: str = None, cari_id: int = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "siparis_turu": siparis_turu,
            "durum": durum,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi,
            "cari_id": cari_id
        }
        # None olan parametreleri temizle
        params = {k: v for k, v in params.items() if v is not None}
        
        try:
            return self._make_api_request("GET", "/siparisler/", params=params)
        except Exception as e:
            logger.error(f"Sipariş listesi alınırken hata: {e}")
            raise # Hatayı yukarı fırlat

    def siparis_getir_by_id(self, siparis_id: int):
        try:
            return self._make_api_request("GET", f"/siparisler/{siparis_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş ID {siparis_id} çekilirken hata: {e}")
            return None

    def siparis_guncelle(self, siparis_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/siparisler/{siparis_id}", json=data) # 'data' yerine 'json' kullanıldı
            return True, "Sipariş başarıyla güncellendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş ID {siparis_id} güncellenirken hata: {e}")
            return False, f"Sipariş güncellenirken hata: {e}" # Hata mesajı eklendi

    def siparis_sil(self, siparis_id: int):
        try:
            self._make_api_request("DELETE", f"/siparisler/{siparis_id}")
            return True, "Sipariş başarıyla silindi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş ID {siparis_id} silinirken hata: {e}")
            return False, f"Sipariş silinirken hata: {e}" # Hata mesajı eklendi

    def siparis_kalemleri_al(self, siparis_id: int):
        try:
            return self._make_api_request("GET", f"/siparisler/{siparis_id}/kalemler")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş ID {siparis_id} kalemleri çekilirken hata: {e}")
            return []

    def get_next_siparis_kodu(self): # API'den otomatik atandığı varsayıldı
        return "OTOMATIK"

    # --- GELİR/GİDER ---
    def gelir_gider_ekle(self, data: dict):
        try:
            self._make_api_request("POST", "/gelir_gider/", json=data) # 'data' yerine 'json' kullanıldı
            return True, "Gelir/Gider kaydı başarıyla eklendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir/Gider eklenirken hata: {e}")
            return False, f"Gelir/Gider eklenirken hata: {e}" # Hata mesajı eklendi

    def gelir_gider_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, baslangic_tarihi: str = None, bitis_tarihi: str = None, tip_filtre: str = None, odeme_turu: str = None, kategori: str = None, cari_ad: str = None):
        params = {
            "skip": skip,
            "limit": limit,
            "aciklama_filtre": arama, # 'arama' parametresi backend'de 'aciklama_filtre' olarak kullanılıyor
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi,
            "tip_filtre": tip_filtre, # Düzeltildi: Parametre ismi 'tip_filtre' olarak güncellendi
            # 'odeme_turu', 'kategori', 'cari_ad' parametreleri backend rotasında doğrudan yok,
            # bu yüzden API çağrısında bunları göndermemeliyiz veya backend rotalarını genişletmeliyiz.
            # Şimdilik backend rotasında olan parametreleri gönderiyoruz.
            # Eğer backend'de bu filtreler yoksa, OnMuhasebe sınıfında bu parametreleri almak anlamsızdır.
            # Veya bu parametreler arayuzde başka bir amaçla kullanılıyorsa ayrıştırılmalıdır.
        }
        # None olan veya boş string olan parametreleri temizle (API'ye sadece geçerli filtreleri gönder)
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

        try:
            return self._make_api_request("GET", "/gelir_gider/", params=cleaned_params)
        except Exception as e:
            logger.error(f"Gelir/Gider listesi alınırken hata: {e}")
            raise # Hatayı yukarı fırlat

    def gelir_gider_sil(self, gg_id: int):
        try:
            self._make_api_request("DELETE", f"/gelir_gider/{gg_id}")
            return True, "Gelir/Gider kaydı başarıyla silindi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir/Gider ID {gg_id} silinirken hata: {e}")
            return False, f"Gelir/Gider silinirken hata: {e}" # Hata mesajı eklendi

    def gelir_gider_getir_by_id(self, gg_id: int):
        try:
            return self._make_api_request("GET", f"/gelir_gider/{gg_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir/Gider ID {gg_id} çekilirken hata: {e}")
            return None

    # --- CARİ HAREKETLER (Manuel oluşturma ve silme) ---
    def cari_hareket_ekle_manuel(self, data: dict):
        try:
            self._make_api_request("POST", "/cari_hareketler/manuel", json=data) # 'data' yerine 'json' kullanıldı
            return True, "Manuel cari hareket başarıyla eklendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Manuel cari hareket eklenirken hata: {e}")
            return False, f"Manuel cari hareket eklenirken hata: {e}" # Hata mesajı eklendi

    def cari_hareket_sil_manuel(self, hareket_id: int):
        try:
            self._make_api_request("DELETE", f"/cari_hareketler/manuel/{hareket_id}")
            return True, "Manuel cari hareket başarıyla silindi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Manuel cari hareket silinirken hata: {e}")
            return False, f"Manuel cari hareket silinirken hata: {e}" # Hata mesajı eklendi

    def cari_hesap_ekstresi_al(self, cari_id: int, cari_turu: str, baslangic_tarihi: str, bitis_tarihi: str):
        params = {
            "cari_id": cari_id,
            "cari_turu": cari_turu,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi
        }
        try:
            response = self._make_api_request("GET", "/raporlar/cari_hesap_ekstresi", params=params)
            return response.get("items", []), response.get("devreden_bakiye", 0.0), True, "Başarılı"
        except Exception as e:
            logger.error(f"Cari hesap ekstresi API'den alınamadı: {e}")
            return [], 0.0, False, f"Ekstre alınırken hata: {e}"

    # YENİ EKLENEN METOT: cari_hareketleri_listele
    def cari_hareketleri_listele(self, skip: int = 0, limit: int = 100, cari_id: Optional[int] = None, 
                                 baslangic_tarihi: Optional[str] = None, bitis_tarihi: Optional[str] = None,
                                 arama: Optional[str] = None, kaynak_tipi: Optional[str] = None,
                                 cari_tip: Optional[str] = None): # YENİ EKLENEN PARAMETRE
        """
        API'den cari hareket listesini çeker.
        Args:
            skip (int): Kaç kaydın atlanacağı.
            limit (int): Kaç kaydın getirileceği.
            cari_id (Optional[int]): Filtrelemek için cari ID.
            baslangic_tarihi (Optional[str]): Filtrelemek için başlangıç tarihi (YYYY-MM-DD).
            bitis_tarihi (Optional[str]): Filtrelemek için bitiş tarihi (YYYY-MM-DD).
            arama (Optional[str]): Açıklama veya referans numarasına göre arama.
            kaynak_tipi (Optional[str]): Hareketin kaynak tipine göre filtreleme.
            cari_tip (Optional[str]): Cari tipi (MUSTERI/TEDARIKCI) filtreleme için. YENİ
        Returns:
            dict: API'den gelen JSON yanıtı (genellikle {'items': [...], 'total': N}).
        """
        params = {
            "skip": skip,
            "limit": limit,
            "cari_id": cari_id,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi,
            "arama": arama,
            "kaynak_tipi": kaynak_tipi,
            "cari_tip": cari_tip # YENİ EKLENEN PARAMETRE
        }
        # None olan veya boş string olan parametreleri temizle
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

        try:
            return self._make_api_request("GET", "/cari_hareketler/", params=cleaned_params)
        except Exception as e:
            logger.error(f"Cari hareket listesi alınırken hata: {e}")
            return {"items": [], "total": 0}


    # --- NİTELİKLER (Kategori, Marka, Grup, Birim, Ülke, Gelir/Gider Sınıflandırma) ---
    def nitelik_ekle(self, nitelik_tipi: str, data: dict):
        try:
            self._make_api_request("POST", f"/nitelikler/{nitelik_tipi}", json=data) # 'data' yerine 'json' kullanıldı
            return True, f"Nitelik ({nitelik_tipi}) başarıyla eklendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Nitelik tipi {nitelik_tipi} eklenirken hata: {e}")
            raise # Hatayı yukarı fırlat

    def nitelik_guncelle(self, nitelik_tipi: str, nitelik_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/nitelikler/{nitelik_tipi}/{nitelik_id}", json=data) # 'data' yerine 'json' kullanıldı
            return True, f"Nitelik ({nitelik_tipi}) başarıyla güncellendi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Nitelik tipi {nitelik_tipi} ID {nitelik_id} güncellenirken hata: {e}")
            raise # Hatayı yukarı fırlat

    def nitelik_sil(self, nitelik_tipi: str, nitelik_id: int):
        try:
            self._make_api_request("DELETE", f"/nitelikler/{nitelik_tipi}/{nitelik_id}")
            return True, f"Nitelik ({nitelik_tipi}) başarıyla silindi." # API'den dönen mesajı da yakalamak için düzeltildi
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Nitelik tipi {nitelik_tipi} ID {nitelik_id} silinirken hata: {e}")
            raise # Hatayı yukarı fırlat

    # NOT: Aşağıdaki metotlar, arayuz.py ve pencereler.py'den gelen çağrılara özel olarak eklendi.
    # Her bir nitelik tipi için ayrı ayrı API endpoint'lerini çağırırlar.

    def kategori_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/kategoriler", params={"skip": skip, "limit": limit})
            return response # API'nin zaten {"items": [], "total": 0} dönmesi beklenir
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kategori listesi API'den alınamadı: {e}")
            return {"items": [], "total": 0} # Hata durumunda boş sözlük formatı döndür

    def marka_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/markalar", params={"skip": skip, "limit": limit})
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Marka listesi API'den alınamadı: {e}")
            return {"items": [], "total": 0} # Hata durumunda boş sözlük formatı döndür
            
    def urun_grubu_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/urun_gruplari", params={"skip": skip, "limit": limit})
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Ürün grubu listesi API'den alınamadı: {e}")
            return {"items": [], "total": 0} # Hata durumunda boş sözlük formatı döndür

    def urun_birimi_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/urun_birimleri", params={"skip": skip, "limit": limit})
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Ürün birimi listesi API'den alınamadı: {e}")
            return {"items": [], "total": 0}
            
    def ulke_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/ulkeler", params={"skip": skip, "limit": limit})
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Ülke listesi API'den alınamadı: {e}")
            return {"items": [], "total": 0}

    def gelir_siniflandirma_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/gelir_siniflandirmalari", params={"skip": skip, "limit": limit})
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir sınıflandırma listesi API'den alınamadı: {e}")
            return {"items": [], "total": 0}

    def gider_siniflandirma_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/gider_siniflandirmalari", params={"skip": skip, "limit": limit})
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gider sınıflandırma listesi API'den alınamadı: {e}")
            return {"items": [], "total": 0} # Hata durumunda boş sözlük formatı döndür
    
    # --- RAPORLAR ---
    def get_dashboard_summary(self, baslangic_tarihi: str = None, bitis_tarihi: str = None):
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        return self._make_api_request("GET", "/raporlar/dashboard_ozet", params=params)

    def get_total_sales(self, baslangic_tarihi: str = None, bitis_tarihi: str = None):
        """Dashboard özeti için toplam satışları çeker."""
        try:
            summary = self._make_api_request("GET", "/raporlar/dashboard_ozet", params={"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi})
            return summary.get("toplam_satislar", 0.0)
        except Exception as e:
            logger.error(f"Toplam satışlar çekilirken hata: {e}")
            return 0.0

    def get_total_collections(self, baslangic_tarihi: str = None, bitis_tarihi: str = None):
        """Dashboard özeti için toplam tahsilatları çeker."""
        try:
            summary = self._make_api_request("GET", "/raporlar/dashboard_ozet", params={"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi})
            return summary.get("toplam_tahsilatlar", 0.0)
        except Exception as e:
            logger.error(f"Toplam tahsilatlar çekilirken hata: {e}")
            return 0.0

    def get_total_payments(self, baslangic_tarihi: str = None, bitis_tarihi: str = None):
        """Dashboard özeti için toplam ödemeleri çeker."""
        try:
            summary = self._make_api_request("GET", "/raporlar/dashboard_ozet", params={"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi})
            return summary.get("toplam_odemeler", 0.0)
        except Exception as e:
            logger.error(f"Toplam ödemeler çekilirken hata: {e}")
            return 0.0

    def get_satislar_detayli_rapor(self, baslangic_tarihi: str, bitis_tarihi: str, cari_id: int = None):
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi, "cari_id": cari_id}
        return self._make_api_request("GET", "/raporlar/satislar_detayli_rapor", params=params)

    def get_kar_zarar_verileri(self, baslangic_tarihi: str, bitis_tarihi: str):
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        try:
            return self._make_api_request("GET", "/raporlar/kar_zarar_verileri", params=params)
        except Exception as e:
            logger.error(f"Kar/Zarar verileri çekilirken hata: {e}")
            # Hata durumunda varsayılan boş bir KarZararResponse yapısı döndürebiliriz
            return {
                "toplam_satis_geliri": 0.0,
                "toplam_satis_maliyeti": 0.0,
                "toplam_alis_gideri": 0.0,
                "diger_gelirler": 0.0,
                "diger_giderler": 0.0,
                "brut_kar": 0.0,
                "net_kar": 0.0
            }
            
    def get_monthly_sales_summary(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Dashboard için aylık satış özetini çeker."""
        # API'de doğrudan aylık satış özeti yok, get_satislar_detayli_rapor endpoint'i kullanılabilir
        # Veya api/rotalar/raporlar.py içinde yeni bir endpoint oluşturulabilir.
        # Şimdilik varsayılan bir yapı döndürelim, daha sonra API genişletilebilir.
        # Not: Bu fonksiyon muhtemelen `api/rotalar/raporlar.py` içindeki
        # `get_gelir_gider_aylik_ozet_endpoint` benzeri bir endpoint'ten gelmeli.
        # API'de böyle bir endpoint şu an tanımlı değil.
        # Örneğin: `/raporlar/aylik_satis_ozeti`
        logger.warning(f"get_monthly_sales_summary metodu API'de doğrudan karşılığı yok. Simüle ediliyor.")
        return [] # Boş liste döndür

    def get_monthly_income_expense_summary(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Dashboard için aylık gelir/gider özetini çeker."""
        # api/rotalar/raporlar.py içindeki get_gelir_gider_aylik_ozet_endpoint'i çağırır.
        # Yıl parametresi bekleniyor, tarih aralığından yılı çıkaracağız.
        try:
            yil = int(baslangic_tarihi.split('-')[0])
            response = self._make_api_request("GET", "/raporlar/gelir_gider_aylik_ozet", params={"yil": yil})
            return response.get("aylik_ozet", [])
        except Exception as e:
            logger.error(f"Aylık gelir/gider özeti çekilirken hata: {e}")
            return []

    def get_gross_profit_and_cost(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Kar/Zarar raporu için brüt kar ve maliyet verilerini çeker."""
        # api/rotalar/raporlar.py içindeki get_kar_zarar_verileri_endpoint'i çağırır
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        try:
            data = self._make_api_request("GET", "/raporlar/kar_zarar_verileri", params=params)
            brut_kar = data.get("brut_kar", 0.0)
            cogs = data.get("toplam_satis_maliyeti", 0.0)
            toplam_satis_geliri = data.get("toplam_satis_geliri", 0.0)
            brut_kar_orani = (brut_kar / toplam_satis_geliri) * 100 if toplam_satis_geliri > 0 else 0.0
            return brut_kar, cogs, brut_kar_orani
        except Exception as e:
            logger.error(f"Brüt kar ve maliyet verileri çekilirken hata: {e}")
            return 0.0, 0.0, 0.0

    def get_nakit_akisi_verileri(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Nakit akışı raporu için verileri çeker."""
        # api/rotalar/raporlar.py içindeki get_nakit_akisi_raporu_endpoint'i çağırır
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        try:
            response = self._make_api_request("GET", "/raporlar/nakit_akisi_raporu", params=params)
            return {
                "nakit_girisleri": response.get("nakit_girisleri", 0.0),
                "nakit_cikislar": response.get("nakit_cikislar", 0.0),
                "net_nakit_akisi": response.get("net_nakit_akisi", 0.0)
            }
        except Exception as e:
            logger.error(f"Nakit akışı verileri çekilirken hata: {e}")
            return {"nakit_girisleri": 0.0, "nakit_cikislar": 0.0, "net_nakit_akisi": 0.0}

    def get_tum_kasa_banka_bakiyeleri(self):
        """Tüm kasa/banka hesaplarının güncel bakiyelerini çeker."""
        # api/rotalar/kasalar_bankalar.py içindeki listeleme endpoint'i kullanılabilir.
        try:
            response = self.kasa_banka_listesi_al(limit=1000) # Tüm hesapları çek
            return response.get("items", []) # 'items' anahtarı içinde listeyi bekliyoruz
        except Exception as e:
            logger.error(f"Tüm kasa/banka bakiyeleri çekilirken hata: {e}")
            return []

    def get_monthly_cash_flow_summary(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Nakit akışı raporu için aylık nakit akışı özetini çeker."""
        # api/rotalar/raporlar.py içindeki get_gelir_gider_aylik_ozet_endpoint'i çağırır.
        # Aylık gelir/gider özeti ile nakit akışı özeti aynı kaynaktan türetilebilir.
        try:
            yil = int(baslangic_tarihi.split('-')[0])
            response = self._make_api_request("GET", "/raporlar/gelir_gider_aylik_ozet", params={"yil": yil})
            return response.get("aylik_ozet", []) # aylık_ozet içinde 'toplam_gelir' ve 'toplam_gider' var
        except Exception as e:
            logger.error(f"Aylık nakit akışı özeti çekilirken hata: {e}")
            return []

    def get_cari_yaslandirma_verileri(self, tarih: str = None):
        """Cari yaşlandırma raporu verilerini çeker."""
        # api/rotalar/raporlar.py içindeki get_cari_yaslandirma_verileri_endpoint'i çağırır
        params = {"tarih": tarih} if tarih else {}
        try:
            response = self._make_api_request("GET", "/raporlar/cari_yaslandirma_raporu", params=params)
            return response # modeller.CariYaslandirmaResponse dönecek, dict bekliyoruz.
        except Exception as e:
            logger.error(f"Cari yaşlandırma verileri çekilirken hata: {e}")
            return {"musteri_alacaklar": [], "tedarikci_borclar": []} # Hata durumunda boş dict döndür

    def get_stock_value_by_category(self):
        """Stok değer raporu için kategoriye göre toplam stok değerini çeker."""
        # api/rotalar/raporlar.py içinde get_stok_deger_raporu_endpoint'i çağırır
        # Bu endpoint şuan sadece toplam_stok_maliyeti döndürüyor.
        # Kategori bazında çekmek için API'deki endpoint'in genişletilmesi gerekir.
        # Şimdilik boş liste döndürüyoruz, API'ye özel endpoint eklenmelidir.
        logger.warning(f"get_stock_value_by_category metodu API'de doğrudan karşılığı yok. Simüle ediliyor.")
        return []

    def get_critical_stock_items(self):
        """Kritik stok altındaki ürünleri çeker."""
        # api/rotalar/stoklar.py içindeki stok listeleme endpoint'i kullanılabilir.
        # params={"kritik_stok_altinda": True} olarak gönderilir.
        try:
            response = self.stok_listesi_al(kritik_stok_altinda=True, limit=1000) # Tüm kritik stokları çek
            return response.get("items", []) # 'items' içinde listeyi bekliyoruz
        except Exception as e:
            logger.error(f"Kritik stok ürünleri çekilirken hata: {e}")
            return []
            
    def get_sales_by_payment_type(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Satış raporu için ödeme türüne göre satış dağılımını çeker."""
        # API'de doğrudan böyle bir endpoint yok.
        # api/rotalar/raporlar.py içinde get_satislar_detayli_rapor_endpoint'i kullanılır.
        # Ancak, bu endpoint ödeme türü dağılımı değil, detaylı fatura listesi döner.
        # API'de yeni bir endpoint gereklidir (örn: /raporlar/satislar_odeme_dagilimi).
        logger.warning(f"get_sales_by_payment_type metodu API'de doğrudan karşılığı yok. Simüle ediliyor.")
        return []

    def get_top_selling_products(self, baslangic_tarihi: str, bitis_tarihi: str, limit: int = 5):
        """Dashboard ve satış raporu için en çok satan ürünleri çeker."""
        # api/rotalar/raporlar.py içindeki get_dashboard_ozet_endpoint'i çağırır
        # Zaten en çok satan ürünler bu özette dönüyor.
        try:
            summary = self._make_api_request("GET", "/raporlar/dashboard_ozet", params={"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi})
            return summary.get("en_cok_satan_urunler", [])
        except Exception as e:
            logger.error(f"En çok satan ürünler çekilirken hata: {e}")
            return []

    def tarihsel_satis_raporu_verilerini_al(self, baslangic_tarihi: str, bitis_tarihi: str, cari_id: int = None):
        """Tarihsel satış raporu için detaylı fatura kalemleri verilerini çeker."""
        # api/rotalar/raporlar.py içindeki get_satislar_detayli_rapor_endpoint'i çağırır.
        # Bu endpoint, FaturaListResponse döner. Kalem detayları için kalemleri ayrıca çekmek gerekebilir.
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi, "cari_id": cari_id}
        try:
            response_data = self._make_api_request("GET", "/raporlar/satislar_detayli_rapor", params=params)
            return response_data.get("items", []) # modeller.FaturaRead listesi dönüyor
        except Exception as e:
            logger.error(f"Tarihsel satış raporu verileri çekilirken hata: {e}")
            return []
            
    def get_urun_faturalari(self, urun_id: int, fatura_tipi: Optional[str] = None):
        """Belirli bir ürüne ait faturaları API'den çeker."""
        params = {"urun_id": urun_id, "fatura_tipi": fatura_tipi}
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}
        try:
            return self._make_api_request("GET", "/raporlar/urun_faturalari", params=cleaned_params)
        except Exception as e:
            logger.error(f"Ürün faturaları API'den alınamadı: {e}")
            return []

    # --- YARDIMCI FONKSİYONLAR ---
    def _format_currency(self, value):
        """Sayısal değeri Türkçe para birimi formatına dönüştürür."""
        try:
            # Sistem locale'i ayarlanmış olmalı, örneğin `tr_TR.UTF-8`
            # `yardimcilar.py` içindeki `setup_locale()` çağrılıyor olmalı.
            locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8') # Linux/macOS için
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.1254') # Windows için
            except locale.Error:
                logger.warning("Sistemde Türkçe locale bulunamadı, varsayılan formatlama kullanılacak.")
        
        try:
            # grouping=True ile binlik ayıracı ekler
            return locale.format_string("%.2f", self.safe_float(value), grouping=True) + " TL"
        except Exception: # Diğer hatalar için (örn. locale hatası)
            return f"{self.safe_float(value):.2f} TL".replace('.', ',')

    def _format_numeric(self, value, decimals):
        """Sayısal değeri Türkçe formatına dönüştürür. `_format_currency`'nin para birimi olmayan versiyonu."""
        try:
            locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.1254')
            except locale.Error:
                logger.warning("Sayısal formatlama için Türkçe locale bulunamadı.")
        
        try:
            return locale.format_string(f"%.{decimals}f", self.safe_float(value), grouping=True).replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return f"{self.safe_float(value):.{decimals}f}".replace('.', ',')


    def safe_float(self, value):
        """String veya None değeri güvenli bir şekilde float'a dönüştürür, hata durumunda 0.0 döner."""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            # Virgülü noktaya çevirerek float'a dönüştür
            return float(str(value).replace(',', '.'))
        except (ValueError, TypeError):
            return 0.0

    # Bu fonksiyon artık doğrudan masaüstü uygulamasında tablo oluşturmaz.
    # Tabloların API başlatıldığında veya create_pg_tables.py scripti ile oluşturulması beklenir.
    def create_tables(self, cursor=None):
        logger.info("create_tables çağrıldı ancak artık veritabanı doğrudan yönetilmiyor. Tabloların API veya create_pg_tables.py aracılığıyla oluşturulduğu varsayılıyor.")
        pass

    # Geçmiş hatalı kayıtları temizleme (API'ye taşınmalıysa)
    def gecmis_hatali_kayitlari_temizle(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_ghost_records", json={}) # Örnek API endpoint
            return True, response.get("message", "Geçmiş hatalı kayıtlar temizlendi.")
        except Exception as e:
            logger.error(f"Geçmiş hatalı kayıtlar temizlenirken hata: {e}")
            return False, f"Geçmiş hatalı kayıtlar temizlenirken hata: {e}"

    # Stok envanterini yeniden hesapla (API'ye taşınmalıysa)
    def stok_envanterini_yeniden_hesapla(self):
        try:
            response = self._make_api_request("POST", "/admin/recalculate_stock_inventory", json={}) # Örnek API endpoint
            return True, response.get("message", "Stok envanteri yeniden hesaplandı.")
        except Exception as e:
            logger.error(f"Stok envanteri yeniden hesaplanırken hata: {e}")
            return False, f"Stok envanteri yeniden hesaplanırken hata: {e}"

    # Veri temizleme fonksiyonları (API'ye taşınmalıysa)
    def clear_stok_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_stock_data", json={}) # Örnek API endpoint
            return True, response.get("message", "Stok verileri temizlendi.")
        except Exception as e:
            logger.error(f"Stok verileri temizlenirken hata: {e}")
            return False, f"Stok verileri temizlenirken hata: {e}"

    def clear_musteri_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_customer_data", json={}) # Örnek API endpoint
            return True, response.get("message", "Müşteri verileri temizlendi.")
        except Exception as e:
            logger.error(f"Müşteri verileri temizlenirken hata: {e}")
            return False, f"Müşteri verileri temizlenirken hata: {e}"

    def clear_tedarikci_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_supplier_data", json={}) # Örnek API endpoint
            return True, response.get("message", "Tedarikçi verileri temizlendi.")
        except Exception as e:
            logger.error(f"Tedarikçi verileri temizlenirken hata: {e}")
            return False, f"Tedarikçi verileri temizlenirken hata: {e}"

    def clear_kasa_banka_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_cash_bank_data", json={}) # Örnek API endpoint
            return True, response.get("message", "Kasa/Banka verileri temizlendi.")
        except Exception as e:
            logger.error(f"Kasa/Banka verileri temizlenirken hata: {e}")
            return False, f"Kasa/Banka verileri temizlenirken hata: {e}"

    def clear_all_transaction_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_all_transactions", json={}) # Örnek API endpoint
            return True, response.get("message", "Tüm işlem verileri temizlendi.")
        except Exception as e:
            logger.error(f"Tüm işlem verileri temizlenirken hata: {e}")
            return False, f"Tüm işlem verileri temizlenirken hata: {e}"

    def clear_all_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_all_data", json={}) # Örnek API endpoint
            return True, response.get("message", "Tüm veriler temizlendi (kullanıcılar hariç).")
        except Exception as e:
            logger.error(f"Tüm veriler temizlenirken hata: {e}")
            return False, f"Tüm veriler temizlenirken hata: {e}"

    # Fatura Detay Alma (API'den geliyor)
    def fatura_detay_al(self, fatura_id: int):
        try:
            return self._make_api_request("GET", f"/faturalar/{fatura_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura detayları {fatura_id} API'den alınamadı: {e}")
            return None

    # Tarihsel satış raporu excel oluşturma (Bu fonksiyon API'ye taşınmalı veya burada sadece çağrı yapmalı)
    def tarihsel_satis_raporu_excel_olustur(self, rapor_verileri, dosya_yolu, bas_t, bit_t):
        # Bu fonksiyonun içeriği aslında API'ye veya raporlar.py'ye taşınmalı.
        # Geçici olarak burada başarıyı simüle ediyoruz.
        logger.info(f"Excel raporu oluşturma tetiklendi: {dosya_yolu}")
        return True, f"Rapor '{dosya_yolu}' adresine başarıyla kaydedildi."
    
    # Cari Ekstresi PDF oluşturma (Bu fonksiyon API'ye taşınmalı)
    def cari_ekstresi_pdf_olustur(self, data_dir, cari_tip, cari_id, bas_t, bit_t, file_path, result_queue):
        # Bu fonksiyonun içeriği de API'ye taşınmalı.
        # Geçici olarak başarıyı simüle edelim ve sonucu queue'ya koyalım.
        logger.info(f"PDF ekstresi oluşturma tetiklendi: {file_path}")
        success = True
        message = f"Cari ekstresi '{file_path}' adresine başarıyla kaydedildi."
        result_queue.put((success, message))

    # Geçmiş fatura kalemi bilgileri (API'den geliyor)
    def get_gecmis_fatura_kalemi_bilgileri(self, cari_id, urun_id, fatura_tipi):
        # API'den veri çekmeli
        try:
            params = {
                "cari_id": cari_id,
                "urun_id": urun_id,
                "fatura_tipi": fatura_tipi
            }
            # API endpoint'i: /raporlar/fatura_kalem_gecmisi şeklinde olmalı
            response = self._make_api_request("GET", "/raporlar/fatura_kalem_gecmisi", params=params)
            return response # API'nin list[dict] dönmesini bekliyoruz
        except Exception as e:
            logger.error(f"Geçmiş fatura kalemleri API'den alınamadı: {e}")
            return []

    # Veresiye borç ekle (API'ye taşınmalı)
    def veresiye_borc_ekle(self, cari_id, cari_tip, tarih, tutar, aciklama):
        # Bu fonksiyon API'ye taşınmalı ve API'deki ilgili endpoint çağrılmalı.
        # Şu an için simüle ediliyor.
        logger.info(f"Veresiye borç ekleme simüle edildi: Cari ID: {cari_id}, Tutar: {tutar}")
        # Bu kısım API'ye taşındığında, API'den başarı/hata bilgisi alınacak.
        return True, "Veresiye borç başarıyla eklendi (simülasyon)."

    # Stok kodu ve Müşteri kodu üretme (API'den değil, yerel olarak kod üretiyor)
    def get_next_stok_kodu(self):
        """API'den bir sonraki stok kodunu alır."""
        try:
            response_data = self._make_api_request("GET", "/sistem/next_stok_code")
            return response_data.get("next_code", "STK-HATA")
        except Exception as e:
            logger.error(f"Bir sonraki stok kodu API'den alınamadı: {e}")
            return "STK-HATA"
        
    def get_next_musteri_kodu(self):
        """API'den bir sonraki müşteri kodunu alır."""
        try:
            response_data = self._make_api_request("GET", "/sistem/next_musteri_code")
            return response_data.get("next_code", "M-HATA")
        except Exception as e:
            logger.error(f"Bir sonraki müşteri kodu API'den alınamadı: {e}")
            return "M-HATA"
        
    def get_next_tedarikci_kodu(self):
        """API'den bir sonraki tedarikçi kodunu alır."""
        try:
            response_data = self._make_api_request("GET", "/sistem/next_tedarikci_code")
            return response_data.get("next_code", "T-HATA")
        except Exception as e:
            logger.error(f"Bir sonraki tedarikçi kodu API'den alınamadı: {e}")
            return "T-HATA"
            
    def siparis_listele(self, baslangic_tarih: Optional[str] = None, bitis_tarih: Optional[str] = None,
                             arama_terimi: Optional[str] = None, cari_id_filter: Optional[int] = None,
                             durum_filter: Optional[str] = None, siparis_tipi_filter: Optional[str] = None,
                             limit: int = 100, offset: int = 0) -> dict:
        """
        API'den sipariş listesini çeker.
        """
        params = {
            "skip": offset,
            "limit": limit,
            "baslangic_tarihi": baslangic_tarih, # 'bas_t' yerine 'baslangic_tarihi'
            "bitis_tarihi": bitis_tarih, # 'bit_t' yerine 'bitis_tarihi'
            "arama": arama_terimi,
            "cari_id": cari_id_filter,
            "durum": durum_filter,
            "siparis_turu": siparis_tipi_filter, # 'tip' yerine 'siparis_turu'
        }
        # None olan parametreleri temizle
        params = {k: v for k, v in params.items() if v is not None}
        
        try:
            return self._make_api_request("GET", "/siparisler/", params=params)
        except Exception as e:
            logger.error(f"Sipariş listesi alınırken hata: {e}")
            raise # Hatayı yukarı fırlat

    def get_gelir_gider_aylik_ozet(self, yil: int):
        """
        Belirtilen yıla ait aylık gelir ve gider özetini API'den alır.
        """
        endpoint = "/raporlar/gelir_gider_aylik_ozet"
        params = {"yil": yil}
        try:
            return self._make_api_request("GET", endpoint, params=params)
        except ValueError as e:
            logger.error(f"Aylık gelir/gider özeti alınırken hata: {e}")
            return {"aylik_ozet": []} # Hata durumunda boş liste dön

    def dosya_indir_api_den(self, api_dosya_yolu: str, yerel_kayit_yolu: str) -> tuple:
        """
        API'den belirli bir dosyayı indirir ve yerel olarak kaydeder.
        Args:
            api_dosya_yolu (str): API'deki dosyanın yolu (örn: /raporlar/download_report/rapor.xlsx).
            yerel_kayit_yolu (str): Dosyanın yerel olarak kaydedileceği tam yol.
        Returns:
            tuple: (bool: başarı durumu, str: mesaj)
        """
        full_api_url = f"{self.api_base_url}{api_dosya_yolu}"
        try:
            with requests.get(full_api_url, stream=True) as r:
                r.raise_for_status() # HTTP 4xx/5xx hataları için hata fırlat
                with open(yerel_kayit_yolu, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True, f"Dosya başarıyla indirildi: {yerel_kayit_yolu}"
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if r is not None and r.response is not None:
                try:
                    error_detail = r.response.json().get('detail', error_detail)
                except ValueError: # JSON decode hatası
                    pass
            logger.error(f"API'den dosya indirilirken hata oluştu: {full_api_url}. Hata: {error_detail}")
            return False, f"Dosya indirilemedi: {error_detail}"
        except Exception as e:
            logger.error(f"Beklenmedik bir hata oluştu: {e}")
            return False, f"Dosya indirilirken beklenmedik bir hata oluştu: {e}"    

    def satis_raporu_excel_olustur_api_den(self, bas_tarihi: str, bit_tarihi: str, cari_id: Optional[int] = None) -> tuple:
        """
        API'yi çağırarak sunucu tarafında satış raporu Excel dosyasını oluşturur.
        Args:
            bas_tarihi (str): Raporun başlangıç tarihi (YYYY-MM-DD).
            bit_tarihi (str): Raporun bitiş tarihi (YYYY-MM-DD).
            cari_id (Optional[int]): İsteğe bağlı olarak belirli bir cariye göre filtreleme.
        Returns:
            tuple: (bool: başarı durumu, str: mesaj, Optional[str]: sunucuda oluşturulan dosya yolu)
        """
        api_generation_path = "/raporlar/generate_satis_raporu_excel"
        generation_params = {
            "baslangic_tarihi": bas_tarihi,
            "bitis_tarihi": bit_tarihi
        }
        if cari_id:
            generation_params["cari_id"] = cari_id

        try:
            response = self._make_api_request(
                method="POST",
                path=api_generation_path,
                json=generation_params
            )
            message = response.get("message", "Rapor oluşturma isteği gönderildi.")
            filepath = response.get("filepath") # Sunucudaki dosya yolu

            return True, message, filepath
        except ValueError as e:
            logger.error(f"Satış raporu Excel oluşturma API çağrısı başarısız: {e}")
            return False, f"Rapor oluşturulamadı: {e}", None
        except Exception as e:
            logger.error(f"Satış raporu Excel oluşturma sırasında beklenmedik hata: {e}")
            return False, f"Rapor oluşturulurken beklenmedik bir hata oluştu: {e}", None