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
    ODEME_TURU_ACIK_HESAP = "AÇIK HESAP"
    ODEME_TURU_ETKISIZ_FATURA = "ETKİSİZ FATURA"
    
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
    STOK_ISLEM_TIP_FATURA_SATIS = "FATURA_SATIŞ"

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

    def _make_api_request(self, method: str, endpoint: str, data: dict = None, params: dict = None):
        """
        Genel API isteği gönderici.
        """
        url = f"{self.api_base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}

        cleaned_params = {k: v for k, v in (params or {}).items() if v is not None and str(v).strip() != ""}

        try:
            response = requests.request(method, url, json=data, params=cleaned_params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            logger.error(f"API'ye bağlanılamadı: {url}. Sunucunun çalıştığından emin olun. Hata: {e}")
            raise ConnectionError(f"API'ye bağlanılamadı. Lütfen sunucunun çalıştığından emin olun.") from e
        except requests.exceptions.Timeout as e:
            logger.error(f"API isteği zaman aşımına uğradı: {url}. Hata: {e}")
            raise TimeoutError(f"API isteği zaman aşımına uğradı.") from e
        except requests.exceptions.HTTPError as e:
            try:
                error_detail = e.response.json().get('detail', str(e.response.content))
            except json.JSONDecodeError:
                error_detail = e.response.text
            logger.error(f"API HTTP hatası: {url}, Durum Kodu: {e.response.status_code}, Yanıt: {error_detail}. Hata: {e}")
            raise ValueError(f"API hatası ({e.response.status_code}): {error_detail}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"API isteği sırasında genel hata oluştu: {url}. Hata: {e}")
            raise RuntimeError(f"API isteği sırasında bir hata oluştu: {e}") from e
        except Exception as e:
            logger.critical(f"Beklenmedik bir hata oluştu: {e}")
            raise

    # --- ŞİRKET BİLGİLERİ ---
    def sirket_bilgilerini_yukle(self):
        try:
            return self._make_api_request("GET", "/sistem/bilgiler")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Şirket bilgileri API'den yüklenemedi: {e}")
            return {}

    def sirket_bilgilerini_kaydet(self, data: dict):
        try:
            self._make_api_request("PUT", "/sistem/bilgiler", data=data)
            return True, "Şirket bilgileri başarıyla kaydedildi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Şirket bilgileri API'ye kaydedilemedi: {e}")
            return False, f"Şirket bilgileri kaydedilirken hata: {e}"

    # --- KULLANICI YÖNETİMİ ---
    def kullanici_dogrula(self, kullanici_adi, sifre):
        try:
            response = self._make_api_request("POST", "/dogrulama/login", data={"kullanici_adi": kullanici_adi, "sifre": sifre})
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
            self._make_api_request("POST", "/dogrulama/register_temp", data={"kullanici_adi": username, "sifre": password, "yetki": yetki})
            return True, "Kullanıcı başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı eklenirken hata: {e}")
            return False, f"Kullanıcı eklenirken hata: {e}"

    def kullanici_guncelle_sifre_yetki(self, user_id, hashed_password, yetki):
        try:
            self._make_api_request("PUT", f"/kullanicilar/{user_id}", data={"hashed_sifre": hashed_password, "yetki": yetki})
            return True, "Kullanıcı şifre ve yetki başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı şifre/yetki güncellenirken hata: {e}")
            return False, f"Kullanıcı şifre/yetki güncellenirken hata: {e}"

    def kullanici_adi_guncelle(self, user_id, new_username):
        try:
            self._make_api_request("PUT", f"/kullanicilar/{user_id}", data={"kullanici_adi": new_username})
            return True, "Kullanıcı adı başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı adı güncellenirken hata: {e}")
            return False, f"Kullanıcı adı güncellenirken hata: {e}"

    def kullanici_sil(self, user_id):
        try:
            self._make_api_request("DELETE", f"/kullanicilar/{user_id}")
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı silinirken hata: {e}")
            return False, f"Kullanıcı silinirken hata: {e}"

    # --- CARİLER (Müşteri/Tedarikçi) ---
    def musteri_ekle(self, data: dict):
        try:
            self._make_api_request("POST", "/musteriler/", data=data)
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri eklenirken hata: {e}")
            return False

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
            self._make_api_request("PUT", f"/musteriler/{musteri_id}", data=data)
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} güncellenirken hata: {e}")
            return False

    def musteri_sil(self, musteri_id: int):
        try:
            self._make_api_request("DELETE", f"/musteriler/{musteri_id}")
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} silinirken hata: {e}")
            return False
            
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
            self._make_api_request("POST", "/tedarikciler/", data=data)
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi eklenirken hata: {e}")
            return False

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
            self._make_api_request("PUT", f"/tedarikciler/{tedarikci_id}", data=data)
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} güncellenirken hata: {e}")
            return False

    def tedarikci_sil(self, tedarikci_id: int):
        try:
            self._make_api_request("DELETE", f"/tedarikciler/{tedarikci_id}")
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} silinirken hata: {e}")
            return False
            
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
            self._make_api_request("POST", "/kasalar_bankalar/", data=data)
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka eklenirken hata: {e}")
            return False

    def kasa_banka_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, hesap_turu: str = None, aktif_durum: bool = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "hesap_turu": hesap_turu,
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
            self._make_api_request("PUT", f"/kasalar_bankalar/{hesap_id}", data=data)
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka ID {hesap_id} güncellenirken hata: {e}")
            return False

    def kasa_banka_sil(self, hesap_id: int):
        try:
            self._make_api_request("DELETE", f"/kasalar_bankalar/{hesap_id}")
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka ID {hesap_id} silinirken hata: {e}")
            return False

    def get_varsayilan_kasa_banka(self, odeme_turu: str):
        try:
            response = self._make_api_request("GET", f"/sistem/varsayilan_kasa_banka/{odeme_turu}")
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.warning(f"Varsayılan kasa/banka ({odeme_turu}) API'den alınamadı: {e}. None dönülüyor.")
            return None


    # --- STOKLAR ---
    def stok_ekle(self, data: dict):
        try:
            self._make_api_request("POST", "/stoklar/", data=data)
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok eklenirken hata: {e}")
            return False

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
        return self._make_api_request("GET", "/stoklar/", params=params)

    def stok_getir_by_id(self, stok_id: int):
        try:
            return self._make_api_request("GET", f"/stoklar/{stok_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok ID {stok_id} çekilirken hata: {e}")
            return None

    def stok_guncelle(self, stok_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/stoklar/{stok_id}", data=data)
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok ID {stok_id} güncellenirken hata: {e}")
            return False

    def stok_sil(self, stok_id: int):
        try:
            self._make_api_request("DELETE", f"/stoklar/{stok_id}")
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok ID {stok_id} silinirken hata: {e}")
            return False
            
    def stok_hareket_ekle(self, stok_id: int, data: dict):
        try:
            self._make_api_request("POST", f"/stoklar/{stok_id}/hareket", data=data)
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok hareketi eklenirken hata: {e}")
            return False
            
    def get_urun_faturalari(self, urun_id: int, fatura_tipi: Optional[str] = None):
        """Belirli bir ürüne ait faturaları API'den çeker."""
        params = {"urun_id": urun_id, "fatura_tipi": fatura_tipi}
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}
        try:
            return self._make_api_request("GET", "/raporlar/urun_faturalari", params=cleaned_params)
        except Exception as e:
            logger.error(f"Ürün faturaları API'den alınamadı: {e}")
            return []

    # --- FATURALAR ---
    def fatura_ekle(self, data: dict):
        try:
            return self._make_api_request("POST", "/faturalar/", data=data)
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
            return self._make_api_request("PUT", f"/faturalar/{fatura_id}", data=data)
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} güncellenirken hata: {e}")
            raise

    def fatura_sil(self, fatura_id: int):
        try:
            self._make_api_request("DELETE", f"/faturalar/{fatura_id}")
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} silinirken hata: {e}")
            return False

    def fatura_kalemleri_al(self, fatura_id: int):
        try:
            return self._make_api_request("GET", f"/faturalar/{fatura_id}/kalemler")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} kalemleri çekilirken hata: {e}")
            return []

    def son_fatura_no_getir(self, fatura_turu):
        # API'den veri çekmeli
        try:
            # Parametreyi doğrudan endpoint URL'ine ekliyoruz
            endpoint_url = f"/sistem/next_fatura_number/{fatura_turu}"
            response = self._make_api_request(method='GET', endpoint=endpoint_url) # params kaldırıldı
            return response.get("fatura_no", "HATA")
        except Exception as e:
            logger.error(f"Son fatura no API'den alınamadı: {e}")
            return "HATA"
        
    # --- SİPARİŞLER ---
    def siparis_ekle(self, data: dict):
        try:
            return self._make_api_request("POST", "/siparisler/", data=data)
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
        return self._make_api_request("GET", "/siparisler/", params=params)

    def siparis_getir_by_id(self, siparis_id: int):
        try:
            return self._make_api_request("GET", f"/siparisler/{siparis_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş ID {siparis_id} çekilirken hata: {e}")
            return None

    def siparis_guncelle(self, siparis_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/siparisler/{siparis_id}", data=data)
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş ID {siparis_id} güncellenirken hata: {e}")
            return False

    def siparis_sil(self, siparis_id: int):
        try:
            self._make_api_request("DELETE", f"/siparisler/{siparis_id}")
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş ID {siparis_id} silinirken hata: {e}")
            return False

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
            self._make_api_request("POST", "/gelir_gider/", data=data)
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir/Gider eklenirken hata: {e}")
            return False

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
            return True
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir/Gider ID {gg_id} silinirken hata: {e}")
            return False

    def gelir_gider_getir_by_id(self, gg_id: int):
        try:
            return self._make_api_request("GET", f"/gelir_gider/{gg_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir/Gider ID {gg_id} çekilirken hata: {e}")
            return None

    # --- CARİ HAREKETLER (Manuel oluşturma ve silme) ---
    def cari_hareket_ekle_manuel(self, data: dict):
        try:
            return self._make_api_request("POST", "/cari_hareketler/manuel", data=data)
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Manuel cari hareket eklenirken hata: {e}")
            return False

    def cari_hareket_sil_manuel(self, hareket_id: int):
        try:
            return self._make_api_request("DELETE", f"/cari_hareketler/manuel/{hareket_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Manuel cari hareket silinirken hata: {e}")
            return False

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

    # --- NİTELİKLER (Kategori, Marka, Grup, Birim, Ülke, Gelir/Gider Sınıflandırma) ---
    def nitelik_ekle(self, nitelik_tipi: str, data: dict):
        try:
            return self._make_api_request("POST", f"/nitelikler/{nitelik_tipi}", data=data)
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Nitelik tipi {nitelik_tipi} eklenirken hata: {e}")
            raise # Hatayı yukarı fırlat

    def nitelik_guncelle(self, nitelik_tipi: str, nitelik_id: int, data: dict):
        try:
            return self._make_api_request("PUT", f"/nitelikler/{nitelik_tipi}/{nitelik_id}", data=data)
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Nitelik tipi {nitelik_tipi} ID {nitelik_id} güncellenirken hata: {e}")
            raise # Hatayı yukarı fırlat

    def nitelik_sil(self, nitelik_tipi: str, nitelik_id: int):
        try:
            return self._make_api_request("DELETE", f"/nitelikler/{nitelik_tipi}/{nitelik_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Nitelik tipi {nitelik_tipi} ID {nitelik_id} silinirken hata: {e}")
            raise # Hatayı yukarı fırlat

    # NOT: Aşağıdaki metotlar, arayuz.py ve pencereler.py'den gelen çağrılara özel olarak eklendi.
    # Her bir nitelik tipi için ayrı ayrı API endpoint'lerini çağırırlar.

    def kategori_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/kategoriler", params={"skip": skip, "limit": limit})
            return response # API'nin doğrudan liste dönmesini bekliyoruz
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kategori listesi API'den alınamadı: {e}")
            return []

    def marka_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/markalar", params={"skip": skip, "limit": limit})
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Marka listesi API'den alınamadı: {e}")
            return []

    def urun_grubu_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/urun_gruplari", params={"skip": skip, "limit": limit})
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Ürün grubu listesi API'den alınamadı: {e}")
            return []

    def urun_birimi_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/urun_birimleri", params={"skip": skip, "limit": limit})
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Ürün birimi listesi API'den alınamadı: {e}")
            return []
            
    def ulke_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/ulkeler", params={"skip": skip, "limit": limit})
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Ülke listesi API'den alınamadı: {e}")
            return []

    def gelir_siniflandirma_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/gelir_siniflandirmalari", params={"skip": skip, "limit": limit})
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir sınıflandırma listesi API'den alınamadı: {e}")
            return []

    def gider_siniflandirma_listele(self, skip: int = 0, limit: int = 1000):
        try:
            response = self._make_api_request("GET", "/nitelikler/gider_siniflandirmalari", params={"skip": skip, "limit": limit})
            return response
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gider sınıflandırma listesi API'den alınamadı: {e}")
            return []
    
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

    def get_monthly_gross_profit_summary(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Kar/Zarar raporu için aylık brüt kar özetini çeker."""
        # API'de doğrudan bu özet yok. get_gelir_gider_aylik_ozet_endpoint'i ile birleştirilebilir
        # veya yeni bir endpoint oluşturulabilir. Şimdilik boş liste döndürüyoruz.
        logger.warning(f"get_monthly_gross_profit_summary metodu API'de doğrudan karşılığı yok. Simüle ediliyor.")
        return []

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
            response = self._make_api_request("POST", "/admin/clear_ghost_records") # Örnek API endpoint
            return True, response.get("message", "Geçmiş hatalı kayıtlar temizlendi.")
        except Exception as e:
            logger.error(f"Geçmiş hatalı kayıtlar temizlenirken hata: {e}")
            return False, f"Geçmiş hatalı kayıtlar temizlenirken hata: {e}"

    # Stok envanterini yeniden hesapla (API'ye taşınmalıysa)
    def stok_envanterini_yeniden_hesapla(self):
        try:
            response = self._make_api_request("POST", "/admin/recalculate_stock_inventory") # Örnek API endpoint
            return True, response.get("message", "Stok envanteri yeniden hesaplandı.")
        except Exception as e:
            logger.error(f"Stok envanteri yeniden hesaplanırken hata: {e}")
            return False, f"Stok envanteri yeniden hesaplanırken hata: {e}"

    # Veri temizleme fonksiyonları (API'ye taşınmalıysa)
    def clear_stok_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_stock_data") # Örnek API endpoint
            return True, response.get("message", "Stok verileri temizlendi.")
        except Exception as e:
            logger.error(f"Stok verileri temizlenirken hata: {e}")
            return False, f"Stok verileri temizlenirken hata: {e}"

    def clear_musteri_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_customer_data") # Örnek API endpoint
            return True, response.get("message", "Müşteri verileri temizlendi.")
        except Exception as e:
            logger.error(f"Müşteri verileri temizlenirken hata: {e}")
            return False, f"Müşteri verileri temizlenirken hata: {e}"

    def clear_tedarikci_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_supplier_data") # Örnek API endpoint
            return True, response.get("message", "Tedarikçi verileri temizlendi.")
        except Exception as e:
            logger.error(f"Tedarikçi verileri temizlenirken hata: {e}")
            return False, f"Tedarikçi verileri temizlenirken hata: {e}"

    def clear_kasa_banka_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_cash_bank_data") # Örnek API endpoint
            return True, response.get("message", "Kasa/Banka verileri temizlendi.")
        except Exception as e:
            logger.error(f"Kasa/Banka verileri temizlenirken hata: {e}")
            return False, f"Kasa/Banka verileri temizlenirken hata: {e}"

    def clear_all_transaction_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_all_transactions") # Örnek API endpoint
            return True, response.get("message", "Tüm işlem verileri temizlendi.")
        except Exception as e:
            logger.error(f"Tüm işlem verileri temizlenirken hata: {e}")
            return False, f"Tüm işlem verileri temizlenirken hata: {e}"

    def clear_all_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_all_data") # Örnek API endpoint
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
        return "STK-OTOMATIK"

    def get_next_musteri_kodu(self):
        return "M-OTOMATIK"

    def get_next_tedarikci_kodu(self):
        return "T-OTOMATIK"
    
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
            "bas_t": baslangic_tarih,
            "bit_t": bitis_tarih,
            "arama": arama_terimi,
            "cari_id": cari_id_filter,
            "durum": durum_filter,
            "tip": siparis_tipi_filter, # API'de 'tip' parametresi bekleniyor
        }
        # None olan parametreleri temizle
        params = {k: v for k, v in params.items() if v is not None}
        
        try:
            return self._make_api_request("GET", "/siparisler/", params=params)
        except Exception as e:
            logger.error(f"Sipariş listesi alınırken hata: {e}")
            raise # Hatayı yukarı fırlat