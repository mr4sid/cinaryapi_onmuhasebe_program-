# veritabani.py dosyasının TAMAMI (Güncellenmiş Hal)
import requests
import json
import logging
import os
import locale # YENİ EKLENDİ (Para birimi formatlama için)
from config import API_BASE_URL # DÜZELTİLDİ: Göreceli içe aktarma kaldırıldı, doğrudan import
from typing import List, Optional, Dict, Any # Yeni importlar
from datetime import datetime
from hizmetler import lokal_db_servisi 
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

    # API ile uyumlu olacak şekilde düzeltildi (Türkçe karakterler kaldırıldı)
    STOK_ISLEM_TIP_GIRIS_MANUEL_DUZELTME = "GIRIS_MANUEL_DUZELTME"
    STOK_ISLEM_TIP_CIKIS_MANUEL_DUZELTME = "CIKIS_MANUEL_DUZELTME"
    STOK_ISLEM_TIP_GIRIS_MANUEL = "GIRIS_MANUEL"
    STOK_ISLEM_TIP_CIKIS_MANUEL = "CIKIS_MANUEL"
    STOK_ISLEM_TIP_SAYIM_FAZLASI = "SAYIM_FAZLASI"
    STOK_ISLEM_TIP_SAYIM_EKSIGI = "SAYIM_EKSIGI"
    STOK_ISLEM_TIP_ZAYIAT = "ZAYIAT"
    STOK_ISLEM_TIP_IADE_GIRIS = "IADE_GIRIS"
    STOK_ISLEM_TIP_FATURA_ALIS = "FATURA_ALIS"
    STOK_ISLEM_TIP_FATURA_SATIS = "FATURA_SATIS"

    # Kaynak Tipleri (Cari Hareketler ve Stok Hareketleri için)
    KAYNAK_TIP_FATURA = "FATURA"
    KAYNAK_TIP_IADE_FATURA = "IADE_FATURA"
    KAYNAK_TIP_FATURA_SATIS_PESIN = "FATURA_SATIS_PESIN"
    KAYNAK_TIP_FATURA_ALIS_PESIN = "FATURA_ALIS_PESIN"
    KAYNAK_TIP_TAHSILAT = "TAHSILAT"
    KAYNAK_TIP_ODEME = "ODEME"
    KAYNAK_TIP_VERESIYE_BORC_MANUEL = "VERESIYE_BORC_MANUEL"
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
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params)
            elif method.upper() == "POST":
                response = requests.post(url, json=json)
            elif method.upper() == "PUT":
                response = requests.put(url, json=json)
            elif method.upper() == "DELETE":
                response = requests.delete(url, params=params)
            else:
                raise ValueError(f"Desteklenmeyen HTTP metodu: {method}")

            response.raise_for_status()

            if response.text:
                response_json = response.json()
                return response_json
            
            return {}

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    error_detail = f"API'den beklenen JSON yanıtı alınamadı. Yanıt: {e.response.text[:200]}..."
            
            # 404 (Not Found) hatası için özel işlem
            if e.response and e.response.status_code == 404:
                # Bu durumun bekleniyor olabileceğini varsayarak daha düşük seviyede logla
                logger.warning(f"API isteği sırasında 404 hatası oluştu. Kaynak bulunamadı: {url}. Detay: {error_detail}")
                # ValueError fırlatmak yerine, boş bir yanıt dönebiliriz.
                # Ancak `siparis_kalemleri_al` metodu bu hatayı yakaladığı için burada bir ValueError fırlatmak daha tutarlıdır.
                raise ValueError(f"Kaynak bulunamadı: {error_detail}") from e
            
            logger.error(f"API isteği sırasında genel hata oluştu: {url}. Hata: {error_detail}", exc_info=True)
            raise ValueError(f"API isteği sırasında bir hata oluştu: {error_detail}") from e
        except ValueError as e:
            logger.error(f"API isteği sırasında bir değer hatası oluştu: {e}", exc_info=True)
            raise e
        except Exception as e:
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
            self._make_api_request("PUT", "/sistem/bilgiler", json=data)
            return True, "Şirket bilgileri başarıyla kaydedildi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Şirket bilgileri API'ye kaydedilemedi: {e}")
            return False, f"Şirket bilgileri kaydedilirken hata: {e}"

    # --- KULLANICI YÖNETİMİ ---
    def kullanici_dogrula(self, kullanici_adi, sifre):
        try:
            response = self._make_api_request("POST", "/dogrulama/login", json={"kullanici_adi": kullanici_adi, "sifre": sifre})
            return response.get("access_token"), response.get("token_type")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı doğrulama başarısız: {e}")
            return None, None

    def kullanici_listele(self):
        """API'den kullanıcı listesini çeker. Yanıtı 'items' listesi olarak döndürür."""
        try:
            response = self._make_api_request("GET", "/kullanicilar/")
            return response.get("items", [])
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı listesi API'den alınamadı: {e}")
            return []
                
    def kullanici_ekle(self, username, password, yetki):
        try:
            self._make_api_request("POST", "/dogrulama/register_temp", json={"kullanici_adi": username, "sifre": password, "yetki": yetki})
            return True, "Kullanıcı başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı eklenirken hata: {e}")
            return False, f"Kullanıcı eklenirken hata: {e}"

    def kullanici_guncelle_sifre_yetki(self, user_id, new_password, yetki):
        try:
            # API'den şifre hashing işlemini yapması beklenir.
            data_to_update = {"yetki": yetki}
            if new_password:
                data_to_update["sifre"] = new_password
                
            self._make_api_request("PUT", f"/kullanicilar/{user_id}", json=data_to_update)
            return True, "Kullanıcı şifre ve yetki başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı şifre/yetki güncellenirken hata: {e}")
            return False, f"Kullanıcı şifre/yetki güncellenirken hata: {e}"

    def kullanici_adi_guncelle(self, user_id, new_username):
        try:
            self._make_api_request("PUT", f"/kullanicilar/{user_id}", json={"kullanici_adi": new_username})
            return True, "Kullanıcı adı başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı adı güncellenirken hata: {e}")
            return False, f"Kullanıcı adı güncellenirken hata: {e}"

    def kullanici_sil(self, user_id):
        try:
            self._make_api_request("DELETE", f"/kullanicilar/{user_id}")
            return True, "Kullanıcı başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı silinirken hata: {e}")
            return False, f"Kullanıcı silinirken hata: {e}"

    # --- CARİLER (Müşteri/Tedarikçi) ---
    def musteri_ekle(self, data: dict):
        try:
            self._make_api_request("POST", "/musteriler/", json=data)
            return True, "Müşteri başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri eklenirken hata: {e}")
            return False, f"Müşteri eklenirken hata: {e}"

    def musteri_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, aktif_durum: bool = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "aktif_durum": aktif_durum
        }
        # None olan veya boş string olan parametreleri temizle (API'ye sadece geçerli filtreleri gönder)
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}
        # Düzeltme: self.db.musteri_listesi_al yerine self._make_api_request çağrıldı
        return self._make_api_request("GET", "/musteriler/", params=cleaned_params)

    def musteri_getir_by_id(self, musteri_id: int):
        try:
            return self._make_api_request("GET", f"/musteriler/{musteri_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} çekilirken hata: {e}")
            return None

    def musteri_guncelle(self, musteri_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/musteriler/{musteri_id}", json=data)
            return True, "Müşteri başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} güncellenirken hata: {e}")
            return False, f"Müşteri güncellenirken hata: {e}"

    def musteri_sil(self, musteri_id: int):
        try:
            self._make_api_request("DELETE", f"/musteriler/{musteri_id}")
            return True, "Müşteri başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} silinirken hata: {e}")
            return False, f"Müşteri silinirken hata: {e}"
            
    def get_perakende_musteri_id(self) -> Optional[int]:
        """API'den varsayılan perakende müşteri ID'sini çeker."""
        try:
            response_data = self._make_api_request("GET", "/sistem/varsayilan_cariler/perakende_musteri_id")
            return response_data.get('id')
        except Exception as e:
            logger.warning(f"Varsayılan perakende müşteri ID'si API'den alınamadı: {e}. None dönülüyor.")
            return None
                    
    def get_cari_ekstre_ozet(self, cari_id: int, cari_turu: str, baslangic_tarihi: str, bitis_tarihi: str):
        """
        Cari hesap ekstresindeki hareketleri alarak finansal özet verilerini hesaplar.
        """
        try:
            hareketler, devreden_bakiye, success, message = self.cari_hesap_ekstresi_al(
                cari_id, cari_turu, baslangic_tarihi, bitis_tarihi
            )

            if not success:
                raise Exception(f"Ekstre verisi alınamadı: {message}")

            toplam_borc = 0.0
            toplam_alacak = 0.0
            toplam_tahsilat_odeme = 0.0
            vadesi_gelmis = 0.0
            vadesi_gelecek = 0.0

            for h in hareketler:
                tutar = h.get('tutar', 0.0)
                islem_yone = h.get('islem_yone')
                odeme_turu = h.get('odeme_turu')
                vade_tarihi_str = h.get('vade_tarihi')
                
                # Borç ve Alacak Toplamlarını Hesapla
                if islem_yone == 'BORC':
                    toplam_borc += tutar
                elif islem_yone == 'ALACAK':
                    toplam_alacak += tutar

                # Tahsilat/Ödeme Toplamını Hesapla
                if odeme_turu in self.pesin_odeme_turleri:
                    # Bu kontrol, Tahsilat/Ödeme hareketlerinin de tahsilat/ödeme toplamına dahil edilmesini sağlar
                    if h.get('kaynak') in [self.KAYNAK_TIP_TAHSILAT, self.KAYNAK_TIP_ODEME]:
                        toplam_tahsilat_odeme += tutar
                    # Faturalar, sadece peşin ödeme türünde ise tahsilat toplamına eklenir.
                    # Buradaki mantık, fatura tutarının ödeme türüne göre ayrıştırılmasıdır.
                    elif h.get('kaynak') in [self.KAYNAK_TIP_FATURA, self.KAYNAK_TIP_IADE_FATURA]:
                        toplam_tahsilat_odeme += tutar


                # Vade bilgileri için hesaplama
                if odeme_turu == self.ODEME_TURU_ACIK_HESAP and vade_tarihi_str:
                    try:
                        vade_tarihi = datetime.strptime(vade_tarihi_str, '%Y-%m-%d').date()
                        if vade_tarihi < datetime.now().date():
                            vadesi_gelmis += tutar
                        else:
                            vadesi_gelecek += tutar
                    except ValueError:
                        logger.warning(f"Geçersiz vade tarihi formatı: {vade_tarihi_str}")

            # Dönem sonu bakiyesi
            donem_sonu_bakiye = devreden_bakiye + toplam_alacak - toplam_borc

            return {
                "donem_basi_bakiye": devreden_bakiye,
                "toplam_borc_hareketi": toplam_borc,
                "toplam_alacak_hareketi": toplam_alacak,
                "toplam_tahsilat_odeme": toplam_tahsilat_odeme,
                "vadesi_gelmis": vadesi_gelmis,
                "vadesi_gelecek": vadesi_gelecek,
                "donem_sonu_bakiye": donem_sonu_bakiye
            }
        except Exception as e:
            logger.error(f"Cari ekstre özeti hesaplanırken hata oluştu: {e}", exc_info=True)
            return {
                "donem_basi_bakiye": 0.0,
                "toplam_borc_hareketi": 0.0,
                "toplam_alacak_hareketi": 0.0,
                "toplam_tahsilat_odeme": 0.0,
                "vadesi_gelmis": 0.0,
                "vadesi_gelecek": 0.0,
                "donem_sonu_bakiye": 0.0
            }

    def get_musteri_net_bakiye(self, musteri_id: int):
        try:
            response = self._make_api_request("GET", f"/musteriler/{musteri_id}/net_bakiye")
            return response.get("net_bakiye")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} net bakiye çekilirken hata: {e}")
            return None

    def tedarikci_ekle(self, data: dict):
        try:
            self._make_api_request("POST", "/tedarikciler/", json=data)
            return True, "Tedarikçi başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi eklenirken hata: {e}")
            return False, f"Tedarikçi eklenirken hata: {e}"

    def tedarikci_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, aktif_durum: bool = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "aktif_durum": aktif_durum
        }
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}
        return self._make_api_request("GET", "/tedarikciler/", params=cleaned_params)

    def tedarikci_getir_by_id(self, tedarikci_id: int):
        try:
            return self._make_api_request("GET", f"/tedarikciler/{tedarikci_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} çekilirken hata: {e}")
            return None

    def tedarikci_guncelle(self, tedarikci_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/tedarikciler/{tedarikci_id}", json=data)
            return True, "Tedarikçi başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} güncellenirken hata: {e}")
            return False, f"Tedarikçi güncellenirken hata: {e}"

    def tedarikci_sil(self, tedarikci_id: int):
        try:
            self._make_api_request("DELETE", f"/tedarikciler/{tedarikci_id}")
            return True, "Tedarikçi başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} silinirken hata: {e}")
            return False, f"Tedarikçi silinirken hata: {e}"
            
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
            self._make_api_request("POST", "/kasalar_bankalar/", json=data)
            return True, "Kasa/Banka hesabı başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka eklenirken hata: {e}")
            return False, f"Kasa/Banka eklenirken hata: {e}"

    def kasa_banka_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, hesap_turu: str = None, aktif_durum: bool = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "tip": hesap_turu,
            "aktif_durum": aktif_durum
        }
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}
        return self._make_api_request("GET", "/kasalar_bankalar/", params=cleaned_params)

    def kasa_banka_getir_by_id(self, hesap_id: int):
        try:
            return self._make_api_request("GET", f"/kasalar_bankalar/{hesap_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka ID {hesap_id} çekilirken hata: {e}")
            return None

    def kasa_banka_guncelle(self, hesap_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/kasalar_bankalar/{hesap_id}", json=data)
            return True, "Kasa/Banka hesabı başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka ID {hesap_id} güncellenirken hata: {e}")
            return False, f"Kasa/Banka güncellenirken hata: {e}"

    def kasa_banka_sil(self, hesap_id: int):
        try:
            self._make_api_request("DELETE", f"/kasalar_bankalar/{hesap_id}")
            return True, "Kasa/Banka hesabı başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka ID {hesap_id} silinirken hata: {e}")
            return False, f"Kasa/Banka silinirken hata: {e}"

    # --- STOKLAR ---
    def stok_ekle(self, stok_data: dict):
        """
        Yeni bir stok kaydını API'ye gönderir.
        Dönüş: (bool, str) - İşlem başarılı mı, mesaj.
        """
        endpoint = "/stoklar/"
        try:
            response_data = self._make_api_request("POST", endpoint, json=stok_data)
            if response_data and response_data.get("id"):
                return True, f"'{stok_data['ad']}' adlı ürün başarıyla eklendi. ID: {response_data['id']}"
            else:
                return False, f"Ürün eklenirken beklenmeyen bir yanıt alındı: {response_data}"
        except ValueError as e: # _make_api_request'ten gelen API hatalarını yakalar
            return False, f"Ürün eklenemedi: {e}"
        except Exception as e: # Diğer olası hataları yakalar
            logger.error(f"Stok eklenirken beklenmeyen hata: {e}", exc_info=True)
            return False, f"Ürün eklenirken beklenmeyen bir hata oluştu: {e}"

    def stok_ozet_al(self):
        """
        API'den tüm stokların özet bilgilerini çeker.
        """
        return self._make_api_request("GET", "/stoklar/ozet")

    def bulk_stok_upsert(self, stok_listesi: List[Dict[str, Any]]):
        """
        Stok verilerini toplu olarak API'ye gönderir.
        
        Args:
            stok_listesi (List[Dict[str, Any]]): Toplu olarak işlenecek stok verilerini içeren liste.
            
        Returns:
            dict: API'den gelen işlem sonuçlarını içeren yanıt.
            
        Raises:
            ValueError: API'den gelen bir hata veya bağlantı sorunu olursa.
        """
        endpoint = "/stoklar/bulk_upsert"
        try:
            return self._make_api_request("POST", endpoint, json=stok_listesi)
        except ValueError as e:
            logger.error(f"Toplu stok ekleme/güncelleme API'den hata döndü: {e}")
            raise
        except Exception as e:
            logger.error(f"Toplu stok ekleme/güncelleme sırasında beklenmedik hata: {e}", exc_info=True)
            raise

    def stok_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None,
                        aktif_durum: Optional[bool] = None, kritik_stok_altinda: Optional[bool] = None,
                        kategori_id: Optional[int] = None, marka_id: Optional[int] = None,
                        urun_grubu_id: Optional[int] = None, stokta_var: Optional[bool] = None):
        """
        API'den stok listesini çeker.
        """
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "aktif_durum": aktif_durum,
            "kritik_stok_altinda": kritik_stok_altinda,
            "kategori_id": kategori_id,
            "marka_id": marka_id,
            "urun_grubu_id": urun_grubu_id,
            "stokta_var": stokta_var
        }
        cleaned_params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/stoklar/", params=cleaned_params)

    def stok_hareketleri_listele(self, stok_id: int, islem_tipi: str = None, baslangic_tarih: str = None, bitis_tarihi: str = None):
        """
        Belirli bir ürüne ait stok hareketlerini API'den çeker.
        Args:
            stok_id (int): Hareketi listelenecek ürünün ID'si.
            islem_tipi (str, optional): Filtrelemek için işlem tipi. Varsayılan None.
            baslangic_tarih (str, optional): Filtreleme için başlangıç tarihi. Varsayılan None.
            bitis_tarihi (str, optional): Filtreleme için bitiş tarihi. Varsayılan None.
        Returns:
            list: Stok hareketleri listesi.
        """
        endpoint = f"/stoklar/{stok_id}/hareketler"
        params = {
            "islem_tipi": islem_tipi,
            "baslangic_tarih": baslangic_tarih,
            "bitis_tarihi": bitis_tarihi
        }
        # None olan parametreleri temizle (API'ye sadece geçerli filtreleri gönder)
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

        try:
            return self._make_api_request("GET", endpoint, params=cleaned_params)
        except Exception as e:
            logger.error(f"Stok hareketleri listelenirken API hatası: {e}", exc_info=True)
            return []

    def urun_faturalari_al(self, urun_id: int):
        """
        Belirli bir ürüne ait ilgili faturaları API'den çeker.
        Args:
            urun_id (int): İlgili faturaları listelenecek ürünün ID'si.
        Returns:
            list: İlgili faturalar listesi.
        """
        endpoint = "/raporlar/urun_faturalari"
        params = {"urun_id": urun_id}
        
        try:
            response = self._make_api_request("GET", endpoint, params=params)
            if isinstance(response, dict) and "items" in response:
                return response.get("items", [])
            elif isinstance(response, list):
                return response
            else:
                logger.warning(f"Ürün faturaları için API'den beklenmeyen yanıt formatı: {response}")
                return []
        except Exception as e:
            logger.error(f"Ürün faturaları API'den alınamadı: {e}", exc_info=True)
            return []        

    def stok_getir_by_id(self, stok_id: int):
        try:
            return self._make_api_request("GET", f"/stoklar/{stok_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok ID {stok_id} çekilirken hata: {e}")
            return None

    def stok_guncelle(self, stok_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/stoklar/{stok_id}", json=data)
            return True, "Stok başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok ID {stok_id} güncellenirken hata: {e}")
            return False, f"Stok güncellenirken hata: {e}"

    def stok_sil(self, stok_id: int):
        try:
            self._make_api_request("DELETE", f"/stoklar/{stok_id}")
            return True, "Stok başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok ID {stok_id} silinirken hata: {e}")
            return False, f"Stok silinirken hata: {e}"
            
    def stok_hareket_ekle(self, stok_id: int, data: dict):
        try:
            self._make_api_request("POST", f"/stoklar/{stok_id}/hareket", json=data)
            return True, "Stok hareketi başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok hareketi eklenirken hata: {e}")
            return False, f"Stok hareketi eklenirken hata: {e}"
            
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
    def fatura_ekle(self, fatura_data: Dict[str, Any]):
        """
        API'ye yeni fatura ekleme isteği gönderir.
        """
        try:
            return self._make_api_request("POST", "/faturalar/", json=fatura_data)
        except Exception as e:
            raise ValueError(f"API'den hata: {e}")

    def fatura_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, fatura_turu: str = None, baslangic_tarihi: str = None, bitis_tarihi: str = None, cari_id: int = None, odeme_turu: str = None, kasa_banka_id: int = None):
        """Filtrelere göre fatura listesini API'den çeker."""
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "fatura_turu": fatura_turu,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi,
            "cari_id": cari_id,
            "odeme_turu": odeme_turu,
            "kasa_banka_id": kasa_banka_id
        }
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}
        return self._make_api_request("GET", "/faturalar/", params=cleaned_params)
                
    def fatura_getir_by_id(self, fatura_id: int):
        try:
            return self._make_api_request("GET", f"/faturalar/{fatura_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} çekilirken hata: {e}")
            return None

    def fatura_guncelle(self, fatura_id: int, data: dict):
        try:
            return self._make_api_request("PUT", f"/faturalar/{fatura_id}", json=data)
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} güncellenirken hata: {e}")
            raise

    def fatura_sil(self, fatura_id: int):
        try:
            self._make_api_request("DELETE", f"/faturalar/{fatura_id}")
            return True, "Fatura başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} silinirken hata: {e}")
            return False, f"Fatura silinirken hata: {e}"

    def fatura_kalemleri_al(self, fatura_id: int):
        """Belirli bir faturaya ait kalemleri API'den çeker."""
        try:
            return self._make_api_request("GET", f"/faturalar/{fatura_id}/kalemler")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} kalemleri çekilirken hata: {e}")
            return []
        
    def son_fatura_no_getir(self, fatura_turu: str):
        path = f"/sistem/next_fatura_number/{fatura_turu.upper()}"
        try:
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
            return self._make_api_request("POST", "/siparisler/", json=data)
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
            self._make_api_request("PUT", f"/siparisler/{siparis_id}", json=data)
            return True, "Sipariş başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş ID {siparis_id} güncellenirken hata: {e}")
            return False, f"Sipariş güncellenirken hata: {e}"

    def siparis_sil(self, siparis_id: int):
        try:
            self._make_api_request("DELETE", f"/siparisler/{siparis_id}")
            return True, "Sipariş başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş ID {siparis_id} silinirken hata: {e}")
            return False, f"Sipariş silinirken hata: {e}"

    def siparis_kalemleri_al(self, siparis_id: int):
        try:
            return self._make_api_request("GET", f"/siparisler/{siparis_id}/kalemler")
        except ValueError as e:
            # Hata mesajında "Kaynak bulunamadı" ifadesi geçiyorsa, bu beklenen bir durumdur.
            # Bu mesaj, API'deki HttpException'dan geliyor.
            if "bulunamadı" in str(e):
                logger.warning(f"Sipariş ID {siparis_id} için sipariş kalemi bulunamadı.")
                return [] # Boş liste dönerek akışı devam ettir.
            else:
                # Diğer hatalar için hatayı yeniden fırlat.
                logger.error(f"Sipariş ID {siparis_id} kalemleri çekilirken beklenmeyen bir hata oluştu: {e}", exc_info=True)
                return []
        except Exception as e:
            logger.error(f"Sipariş ID {siparis_id} kalemleri çekilirken beklenmeyen bir hata oluştu: {e}", exc_info=True)
            return []

    def get_next_siparis_kodu(self):
        """
        API'den bir sonraki sipariş kodunu alır.
        """
        try:
            response_data = self._make_api_request("GET", "/sistem/next_siparis_kodu")
            return response_data.get("next_code", "OTOMATIK")
        except Exception as e:
            logger.error(f"Bir sonraki sipariş kodu API'den alınamadı: {e}")
            return "OTOMATIK"

    # --- GELİR/GİDER ---
    def gelir_gider_ekle(self, data: dict):
        try:
            self._make_api_request("POST", "/gelir_gider/", json=data)
            return True, "Gelir/Gider kaydı başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir/Gider eklenirken hata: {e}")
            return False, f"Gelir/Gider eklenirken hata: {e}"

    def gelir_gider_listesi_al(self, skip: int = 0, limit: int = 20, tip_filtre: str = None,
                               baslangic_tarihi: str = None, bitis_tarihi: str = None,
                               aciklama_filtre: str = None):
        """
        API'den gelir/gider listesini filtreleyerek çeker.
        """
        params = {
            "skip": skip,
            "limit": limit,
            "tip_filtre": tip_filtre,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi,
            "aciklama_filtre": aciklama_filtre
        }
        cleaned_params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/gelir_gider/", params=cleaned_params)

    def gelir_gider_sil(self, gg_id: int):
        try:
            self._make_api_request("DELETE", f"/gelir_gider/{gg_id}")
            return True, "Gelir/Gider kaydı başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir/Gider ID {gg_id} silinirken hata: {e}")
            return False, f"Gelir/Gider silinirken hata: {e}"

    def gelir_gider_getir_by_id(self, gg_id: int):
        try:
            return self._make_api_request("GET", f"/gelir_gider/{gg_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir/Gider ID {gg_id} çekilirken hata: {e}")
            return None

    # --- CARİ HAREKETLER (Manuel oluşturma ve silme) ---
    def cari_hareket_ekle_manuel(self, data: dict):
        try:
            self._make_api_request("POST", "/cari_hareketler/manuel", json=data)
            return True, "Manuel cari hareket başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Manuel cari hareket eklenirken hata: {e}")
            return False, f"Manuel cari hareket eklenirken hata: {e}"

    def cari_hareket_sil_manuel(self, hareket_id: int):
        try:
            self._make_api_request("DELETE", f"/cari_hareketler/manuel/{hareket_id}")
            return True, "Manuel cari hareket başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Manuel cari hareket silinirken hata: {e}")
            return False, f"Manuel cari hareket silinirken hata: {e}"

    def cari_hesap_ekstresi_al(self, cari_id: int, cari_turu: str, baslangic_tarihi: str, bitis_tarihi: str):
        params = {
            "cari_id": cari_id,
            "cari_turu": cari_turu,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi
        }
        try:
            # API endpoint'ini doğru adrese yönlendirin
            response = self._make_api_request("GET", "/raporlar/cari_hesap_ekstresi", params=params)
            return response.get("items", []), response.get("devreden_bakiye", 0.0), True, "Başarılı"
        except Exception as e:
            logger.error(f"Cari hesap ekstresi API'den alınamadı: {e}")
            return [], 0.0, False, f"Ekstre alınırken hata: {e}"
        
    def cari_hareketleri_listele(self, cari_id: int = None, islem_turu: str = None, baslangic_tarihi: Optional[str] = None, bitis_tarihi: Optional[str] = None, limit: int = 20, skip: int = 0):
        """
        API'den cari hareketleri listeler.
        Belirli bir cari_id verilirse, o cariye ait hareketleri filtreler.
        Tarih aralığı, limit ve skip parametreleri ile filtreleme ve sayfalama yapılabilir.
        """
        endpoint = "/cari_hareketler/"
        params = {
            "skip": skip,
            "limit": limit,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi,
            "islem_turu": islem_turu  # Yeni eklenen parametre
        }
        if cari_id is not None:
            params["cari_id"] = cari_id
        
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

        try:
            response = self._make_api_request("GET", endpoint, params=cleaned_params)
            return response
        except ValueError as e:
            logger.error(f"Cari hareketleri listelenirken API hatası: {e}")
            return {"items": [], "total": 0}
        except Exception as e:
            logger.error(f"Cari hareketleri listelenirken beklenmeyen hata: {e}", exc_info=True)
            return {"items": [], "total": 0}

    # --- NİTELİKLER (Kategori, Marka, Grup, Birim, Ülke, Gelir/Gider Sınıflandırma) ---
    def nitelik_ekle(self, nitelik_tipi: str, data: dict):
        """
        Belirtilen nitelik tipine yeni bir kayıt ekler.
        """
        try:
            self._make_api_request("POST", f"/nitelikler/{nitelik_tipi}", json=data)
            return True, f"Nitelik ({nitelik_tipi}) başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Nitelik tipi {nitelik_tipi} eklenirken hata: {e}")
            raise # Hatayı yukarı fırlat

    def nitelik_guncelle(self, nitelik_tipi: str, nitelik_id: int, data: dict):
        """
        Belirtilen niteliği günceller.
        """
        try:
            self._make_api_request("PUT", f"/nitelikler/{nitelik_tipi}/{nitelik_id}", json=data)
            return True, f"Nitelik ({nitelik_tipi}) başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Nitelik tipi {nitelik_tipi} ID {nitelik_id} güncellenirken hata: {e}")
            raise # Hatayı yukarı fırlat

    def nitelik_sil(self, nitelik_tipi: str, nitelik_id: int):
        """
        Belirtilen niteliği siler.
        """
        try:
            self._make_api_request("DELETE", f"/nitelikler/{nitelik_tipi}/{nitelik_id}")
            return True, f"Nitelik ({nitelik_tipi}) başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Nitelik tipi {nitelik_tipi} ID {nitelik_id} silinirken hata: {e}")
            raise # Hatayı yukarı fırlat

    def kategori_listele(self, skip: int = 0, limit: int = 1000) -> List[dict]:
        try:
            response = self._make_api_request("GET", "/nitelikler/kategoriler", params={"skip": skip, "limit": limit})
            if isinstance(response, dict) and "items" in response:
                return response["items"]
            elif isinstance(response, list):
                # Bu durum, API'nin beklenen format dışında yanıt verdiğini gösterir.
                return response
            else:
                logger.warning(f"kategori_listele: API'den beklenmedik yanıt formatı. Yanıt: {response}")
                return []
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kategori listesi API'den alınamadı: {e}")
            return []

    def marka_listele(self, skip: int = 0, limit: int = 1000) -> Dict[str, Any]:
        try:
            response = self._make_api_request("GET", "/nitelikler/markalar", params={"skip": skip, "limit": limit})
            if isinstance(response, dict) and "items" in response:
                return response
            elif isinstance(response, list):
                return {"items": response, "total": len(response)}
            else:
                logger.warning(f"marka_listele: API'den beklenmedik yanıt formatı. Yanıt: {response}")
                return {"items": [], "total": 0}
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Marka listesi API'den alınamadı: {e}")
            return {"items": [], "total": 0}
            
    def urun_grubu_listele(self, skip: int = 0, limit: int = 1000) -> Dict[str, Any]:
        try:
            response = self._make_api_request("GET", "/nitelikler/urun_gruplari", params={"skip": skip, "limit": limit})
            if isinstance(response, dict) and "items" in response:
                return response
            elif isinstance(response, list):
                return {"items": response, "total": len(response)}
            else:
                logger.warning(f"urun_grubu_listele: API'den beklenmedik yanıt formatı. Yanıt: {response}")
                return {"items": [], "total": 0}
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Ürün grubu listesi API'den alınamadı: {e}")
            return {"items": [], "total": 0}

    def urun_birimi_listele(self, skip: int = 0, limit: int = 1000) -> Dict[str, Any]:
        try:
            response = self._make_api_request("GET", "/nitelikler/urun_birimleri", params={"skip": skip, "limit": limit})
            if isinstance(response, dict) and "items" in response:
                return response
            elif isinstance(response, list):
                return {"items": response, "total": len(response)}
            else:
                logger.warning(f"urun_birimi_listele: API'den beklenmedik yanıt formatı. Yanıt: {response}")
                return {"items": [], "total": 0}
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Ürün birimi listesi API'den alınamadı: {e}")
            return {"items": [], "total": 0}
            
    def ulke_listele(self, skip: int = 0, limit: int = 1000) -> Dict[str, Any]:
        try:
            response = self._make_api_request("GET", "/nitelikler/ulkeler", params={"skip": skip, "limit": limit})
            if isinstance(response, dict) and "items" in response:
                return response
            elif isinstance(response, list):
                return {"items": response, "total": len(response)}
            else:
                logger.warning(f"ulke_listele: API'den beklenmedik yanıt formatı. Yanıt: {response}")
                return {"items": [], "total": 0}
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Ülke listesi API'den alınamadı: {e}")
            return {"items": [], "total": 0}

    def gelir_siniflandirma_listele(self, skip: int = 0, limit: int = 1000, id: int = None):
        """
        API'den gelir sınıflandırma listesini çeker.
        """
        params = {"skip": skip, "limit": limit, "id": id}
        cleaned_params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/nitelikler/gelir_siniflandirmalari", params=cleaned_params)

    def gider_siniflandirma_listele(self, skip: int = 0, limit: int = 1000, id: int = None):
        """
        API'den gider sınıflandırma listesini çeker.
        """
        params = {"skip": skip, "limit": limit, "id": id}
        cleaned_params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/nitelikler/gider_siniflandirmalari", params=cleaned_params)
    
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
        logger.warning(f"get_monthly_sales_summary metodu API'de doğrudan karşılığı yok. Simüle ediliyor.")
        return [] # Boş liste döndür

    def get_monthly_income_expense_summary(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Dashboard için aylık gelir/gider özetini çeker."""
        try:
            yil = int(baslangic_tarihi.split('-')[0])
            response = self._make_api_request("GET", "/raporlar/gelir_gider_aylik_ozet", params={"yil": yil})
            return response.get("aylik_ozet", [])
        except Exception as e:
            logger.error(f"Aylık gelir/gider özeti çekilirken hata: {e}")
            return []

    def get_gross_profit_and_cost(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Kar/Zarar raporu için brüt kar ve maliyet verilerini çeker."""
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
        try:
            response = self.kasa_banka_listesi_al(limit=1000)
            return response.get("items", [])
        except Exception as e:
            logger.error(f"Tüm kasa/banka bakiyeleri çekilirken hata: {e}")
            return []

    def get_monthly_cash_flow_summary(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Nakit akışı raporu için aylık nakit akışı özetini çeker."""
        try:
            yil = int(baslangic_tarihi.split('-')[0])
            response = self._make_api_request("GET", "/raporlar/gelir_gider_aylik_ozet", params={"yil": yil})
            return response.get("aylik_ozet", [])
        except Exception as e:
            logger.error(f"Aylık nakit akışı özeti çekilirken hata: {e}")
            return []

    def get_cari_yaslandirma_verileri(self, tarih: str = None):
        """Cari yaşlandırma raporu verilerini çeker."""
        params = {"tarih": tarih} if tarih else {}
        try:
            response = self._make_api_request("GET", "/raporlar/cari_yaslandirma_raporu", params=params)
            return response
        except Exception as e:
            logger.error(f"Cari yaşlandırma verileri çekilirken hata: {e}")
            return {"musteri_alacaklar": [], "tedarikci_borclar": []}

    def get_stock_value_by_category(self):
        """Stok değer raporu için kategoriye göre toplam stok değerini çeker."""
        logger.warning(f"get_stock_value_by_category metodu API'de doğrudan karşılığı yok. Simüle ediliyor.")
        return {"items": [], "total": 0} # API'den beklenen formatı döndür

    def get_critical_stock_items(self):
        """Kritik stok altındaki ürünleri çeker."""
        try:
            response = self.stok_listesi_al(kritik_stok_altinda=True, limit=1000)
            return response.get("items", [])
        except Exception as e:
            logger.error(f"Kritik stok ürünleri çekilirken hata: {e}")
            return []
            
    def get_sales_by_payment_type(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Satış raporu için ödeme türüne göre satış dağılımını çeker."""
        logger.warning(f"get_sales_by_payment_type metodu API'de doğrudan karşılığı yok. Simüle ediliyor.")
        return []

    def get_top_selling_products(self, baslangic_tarihi: str, bitis_tarihi: str, limit: int = 5):
        """Dashboard ve satış raporu için en çok satan ürünleri çeker."""
        try:
            summary = self._make_api_request("GET", "/raporlar/dashboard_ozet", params={"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi})
            return summary.get("en_cok_satan_urunler", [])
        except Exception as e:
            logger.error(f"En çok satan ürünler çekilirken hata: {e}")
            return []

    def tarihsel_satis_raporu_verilerini_al(self, baslangic_tarihi: str, bitis_tarihi: str, cari_id: int = None):
        """Tarihsel satış raporu için detaylı fatura kalemleri verilerini çeker."""
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi, "cari_id": cari_id}
        try:
            response_data = self._make_api_request("GET", "/raporlar/satislar_detayli_rapor", params=params)
            return response_data.get("items", [])
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
            locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.1254')
            except locale.Error:
                logger.warning("Sistemde Türkçe locale bulunamadı, varsayılan formatlama kullanılacak.")
        
        try:
            return locale.format_string("%.2f", self.safe_float(value), grouping=True) + " TL"
        except Exception:
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
            
            # DÜZELTME: Önce binlik ayıracını kaldır, sonra ondalık ayıracını noktaya çevir
            cleaned_value = str(value).strip()
            if cleaned_value:
                # Binlik ayıracını kaldır (örn. 10.000 -> 10000)
                cleaned_value = cleaned_value.replace(".", "")
                # Ondalık ayıracını noktaya çevir (örn. 10000,00 -> 10000.00)
                cleaned_value = cleaned_value.replace(",", ".")
            
            return float(cleaned_value)
        except (ValueError, TypeError):
            return 0.0
        
    def create_tables(self, cursor=None):
        logger.info("create_tables çağrıldı ancak artık veritabanı doğrudan yönetilmiyor. Tabloların API veya create_pg_tables.py aracılığıyla oluşturulduğu varsayılıyor.")
        pass

    def gecmis_hatali_kayitlari_temizle(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_ghost_records", json={})
            return True, response.get("message", "Geçmiş hatalı kayıtlar temizlendi.")
        except Exception as e:
            logger.error(f"Geçmiş hatalı kayıtlar temizlenirken hata: {e}")
            return False, f"Geçmiş hatalı kayıtlar temizlenirken hata: {e}"

    def stok_envanterini_yeniden_hesapla(self):
        try:
            response = self._make_api_request("POST", "/admin/recalculate_stock_inventory", json={})
            return True, response.get("message", "Stok envanteri yeniden hesaplandı.")
        except Exception as e:
            logger.error(f"Stok envanteri yeniden hesaplanırken hata: {e}")
            return False, f"Stok envanteri yeniden hesaplanırken hata: {e}"

    def clear_stok_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_stock_data", json={})
            return True, response.get("message", "Stok verileri temizlendi.")
        except Exception as e:
            logger.error(f"Stok verileri temizlenirken hata: {e}")
            return False, f"Stok verileri temizlenirken hata: {e}"

    def clear_musteri_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_customer_data", json={})
            return True, response.get("message", "Müşteri verileri temizlendi.")
        except Exception as e:
            logger.error(f"Müşteri verileri temizlenirken hata: {e}")
            return False, f"Müşteri verileri temizlenirken hata: {e}"

    def clear_tedarikci_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_supplier_data", json={})
            return True, response.get("message", "Tedarikçi verileri temizlendi.")
        except Exception as e:
            logger.error(f"Tedarikçi verileri temizlenirken hata: {e}")
            return False, f"Tedarikçi verileri temizlenirken hata: {e}"

    def clear_kasa_banka_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_cash_bank_data", json={})
            return True, response.get("message", "Kasa/Banka verileri temizlendi.")
        except Exception as e:
            logger.error(f"Kasa/Banka verileri temizlenirken hata: {e}")
            return False, f"Kasa/Banka verileri temizlenirken hata: {e}"

    def clear_all_transaction_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_all_transactions", json={})
            return True, response.get("message", "Tüm işlem verileri temizlendi.")
        except Exception as e:
            logger.error(f"Tüm işlem verileri temizlenirken hata: {e}")
            return False, f"Tüm işlem verileri temizlenirken hata: {e}"

    def clear_all_data(self):
        """
        Tüm verileri API üzerinden temizleme işlemini tetikler.
        """
        try:
            # API'ye DELETE isteği gönderiyoruz.
            response = self._make_api_request(
                method="DELETE",
                path="/admin/clear_all_data",
                json={}
            )
            return True, response.get("message", "Tüm veriler temizlendi (kullanıcılar hariç).")
        except Exception as e:
            logger.error(f"Tüm veriler temizlenirken hata: {e}")
            return False, f"Tüm veriler temizlenirken hata: {e}"

    def fatura_detay_al(self, fatura_id: int):
        try:
            return self._make_api_request("GET", f"/faturalar/{fatura_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura detayları {fatura_id} API'den alınamadı: {e}")
            return None

    def tarihsel_satis_raporu_excel_olustur(self, rapor_verileri, dosya_yolu, bas_t, bit_t):
        logger.info(f"Excel raporu oluşturma tetiklendi: {dosya_yolu}")
        return True, f"Rapor '{dosya_yolu}' adresine başarıyla kaydedildi."
    
    def cari_ekstresi_pdf_olustur(self, data_dir, cari_tip, cari_id, bas_t, bit_t, file_path, result_queue):
        logger.info(f"PDF ekstresi oluşturma tetiklendi: {file_path}")
        success = True
        message = f"Cari ekstresi '{file_path}' adresine başarıyla kaydedildi."
        result_queue.put((success, message))

    def get_gecmis_fatura_kalemi_bilgileri(self, cari_id, urun_id, fatura_tipi):
        try:
            params = {
                "cari_id": cari_id,
                "urun_id": urun_id,
                "fatura_tipi": fatura_tipi
            }
            # DEĞİŞİKLİK BURADA: API yolunu doğru adrese yönlendiriyoruz.
            response = self._make_api_request("GET", "/raporlar/fatura_kalem_gecmisi", params=params)
            return response.get('items', [])
        except Exception as e:
            logger.error(f"Geçmiş fatura kalemleri API'den alınamadı: {e}")
            return []
                                                                
    def veresiye_borc_ekle(self, cari_id, cari_tip, tarih, tutar, aciklama):
        """
        Veresiye borç ekleme işlemini API'ye gönderir.
        """
        data = {
            "cari_id": cari_id,
            "cari_turu": cari_tip,
            "tarih": tarih,
            "islem_turu": "VERESİYE_BORÇ",
            "islem_yone": self.CARI_ISLEM_YON_BORC,
            "tutar": tutar,
            "aciklama": aciklama,
            "kaynak": self.KAYNAK_TIP_VERESIYE_BORC_MANUEL
        }
        try:
            self._make_api_request("POST", "/cari_hareketler/manuel", json=data)
            return True, "Veresiye borç başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Veresiye borç eklenirken hata: {e}")
            return False, f"Veresiye borç eklenirken hata: {e}"

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
            "baslangic_tarihi": baslangic_tarih,
            "bitis_tarihi": bitis_tarih,
            "arama": arama_terimi,
            "cari_id": cari_id_filter,
            "durum": durum_filter,
            "siparis_turu": siparis_tipi_filter,
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
        
    def database_backup(self, file_path: str):
        """
        Veritabanını API üzerinden yedekleme işlemini tetikler.
        """
        try:
            response = self._make_api_request("POST", "/admin/yedekle", json={"file_path": file_path})
            created_file_path = response.get("file_path", file_path)
            return True, response.get("message", "Yedekleme işlemi tamamlandı."), created_file_path
        except Exception as e:
            logger.error(f"Veritabanı yedekleme API isteği başarısız: {e}")
            return False, f"Yedekleme başarısız oldu: {e}", None

    def database_restore(self, file_path: str):
        """
        Veritabanını API üzerinden geri yükleme işlemini tetikler.
        """
        try:
            # API'ye geri yükleme isteği gönderin
            response = self._make_api_request("POST", "/admin/geri_yukle", json={"file_path": file_path})
            return True, response.get("message", "Geri yükleme işlemi tamamlandı."), None
        except Exception as e:
            logger.error(f"Veritabanı geri yükleme API isteği başarısız: {e}")
            return False, f"Geri yükleme başarısız oldu: {e}", None
        
    def senkronize_veriler_lokal_db_icin(self):
        """
        Lokal veritabanı senkronizasyonunu başlatmak için bir aracı metot.
        """
        return lokal_db_servisi.senkronize_veriler(self.api_base_url)