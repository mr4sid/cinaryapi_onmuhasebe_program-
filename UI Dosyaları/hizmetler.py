# hizmetler.py Dosyasının TAMAMI (Güncellenmiş Hal)
import requests
import json
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class FaturaService:
    def __init__(self, db_manager):
        self.db = db_manager # OnMuhasebe sınıfının bir örneği
        logger.info("FaturaService başlatıldı.")

    def fatura_olustur(self, fatura_no, tarih, fatura_tipi, cari_id, kalemler_data, odeme_turu,
                       kasa_banka_id=None, misafir_adi=None, fatura_notlari=None, vade_tarihi=None,
                       genel_iskonto_tipi=None, genel_iskonto_degeri=None, original_fatura_id=None):
        """
        Yeni bir fatura kaydı ve ilişkili kalemlerini API'ye gönderir.
        """
        fatura_data = {
            "fatura_no": fatura_no,
            "tarih": tarih,
            "fatura_turu": fatura_tipi,
            "cari_id": cari_id,
            "odeme_turu": odeme_turu,
            "kasa_banka_id": kasa_banka_id,
            "misafir_adi": misafir_adi,
            "fatura_notlari": fatura_notlari,
            "vade_tarihi": vade_tarihi,
            "genel_iskonto_tipi": genel_iskonto_tipi,
            "genel_iskonto_degeri": genel_iskonto_degeri,
            "orijinal_fatura_id": original_fatura_id, # İade faturaları için
            "kalemler": kalemler_data
        }
        try:
            # db_manager'daki _make_api_request metodu zaten hataları yükseltiyor.
            # Burada sadece başarıyı ve mesajı döneceğiz.
            response_data = self.db.fatura_ekle(fatura_data) # db.fatura_ekle'yi çağır
            return True, response_data.get("message", "Fatura başarıyla kaydedildi.")
        except ValueError as e:
            logger.error(f"Fatura oluşturulurken API hatası: {e}")
            return False, f"Fatura oluşturulamadı: {e}"
        except Exception as e:
            logger.error(f"Fatura oluşturulurken beklenmeyen bir hata oluştu: {e}")
            return False, f"Fatura oluşturulurken beklenmeyen bir hata oluştu: {e}"

    def fatura_guncelle(self, fatura_id, fatura_no, tarih, cari_id, odeme_turu, kalemler_data,
                        kasa_banka_id=None, misafir_adi=None, fatura_notlari=None, vade_tarihi=None,
                        genel_iskonto_tipi=None, genel_iskonto_degeri=None):
        """
        Mevcut bir faturayı ve ilişkili kalemlerini API'de günceller.
        """
        fatura_data = {
            "fatura_no": fatura_no,
            "tarih": tarih,
            "cari_id": cari_id,
            "odeme_turu": odeme_turu,
            "kasa_banka_id": kasa_banka_id,
            "misafir_adi": misafir_adi,
            "fatura_notlari": fatura_notlari,
            "vade_tarihi": vade_tarihi,
            "genel_iskonto_tipi": genel_iskonto_tipi,
            "genel_iskonto_degeri": genel_iskonto_degeri,
            "kalemler": kalemler_data # Kalemler de güncellemeyle birlikte gidecek
        }
        try:
            # db_manager'daki fatura_guncelle metodu çağrılıyor.
            response_data = self.db.fatura_guncelle(fatura_id, fatura_data)
            return True, response_data.get("message", "Fatura başarıyla güncellendi.")
        except ValueError as e:
            logger.error(f"Fatura güncellenirken API hatası: {e}")
            return False, f"Fatura güncellenemedi: {e}"
        except Exception as e:
            logger.error(f"Fatura güncellenirken beklenmeyen bir hata oluştu: {e}")
            return False, f"Fatura güncellenirken beklenmeyen bir hata oluştu: {e}"

    def siparis_faturaya_donustur(self, siparis_id: int, olusturan_kullanici_id: int,
                                  odeme_turu: str, kasa_banka_id: Optional[int], vade_tarihi: Optional[str]):
        """
        Belirtilen siparişi faturaya dönüştürmek için API'ye istek gönderir.
        Bu fonksiyon, API'deki /siparisler/{siparis_id}/faturaya_donustur endpoint'ini çağırır.
        """
        request_data = {
            "olusturan_kullanici_id": olusturan_kullanici_id,
            "odeme_turu": odeme_turu,
            "kasa_banka_id": kasa_banka_id,
            "vade_tarihi": vade_tarihi
        }
        try:
            # POST isteği için json parametresi kullanılır
            response_data = self.db._make_api_request("POST", f"/siparisler/{siparis_id}/faturaya_donustur", json=request_data)
            return True, response_data.get("message", "Sipariş başarıyla faturaya dönüştürüldü.")
        except ValueError as e:
            logger.error(f"Siparişi faturaya dönüştürürken API hatası: {e}")
            return False, f"Sipariş faturaya dönüştürülemedi: {e}"
        except Exception as e:
            logger.error(f"Siparişi faturaya dönüştürürken beklenmeyen bir hata oluştu: {e}")
            return False, f"Siparişi faturaya dönüştürürken beklenmeyen bir hata oluştu: {e}"

class CariService:
    def __init__(self, db_manager):
        """
        Müşteri ve tedarikçi (cari) verilerini yöneten servis sınıfı.
        db_manager ile API üzerinden iletişim kurar.
        """
        self.db = db_manager
        logger.info("CariService başlatıldı.")

    def musteri_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, aktif_durum: bool = None): # perakende_haric parametresi kaldırıldı
        """
        API'den müşteri listesini çeker.
        """
        # OnMuhasebe sınıfının musteri_listesi_al metodunu doğrudan çağırıyoruz
        # ve tüm parametreleri olduğu gibi iletiyoruz.
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "aktif_durum": aktif_durum
        }
        # None olan veya boş string olan parametreleri temizle (API'ye sadece geçerli filtreleri gönder)
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

        try:
            return self.db.musteri_listesi_al(**cleaned_params)
        except Exception as e:
            logger.error(f"Müşteri listesi CariService üzerinden alınırken hata: {e}")
            raise # Hatayı tekrar fırlatıyoruz

    def musteri_getir_by_id(self, musteri_id: int):
        """
        Belirli bir müşteri ID'sine göre müşteri bilgilerini API'den çeker.
        """
        try:
            # OnMuhasebe sınıfının musteri_getir_by_id metodunu doğrudan çağırıyoruz.
            return self.db.musteri_getir_by_id(musteri_id)
        except Exception as e:
            logger.error(f"Müşteri ID {musteri_id} CariService üzerinden çekilirken hata: {e}")
            raise

    def musteri_sil(self, musteri_id: int):
        """
        Belirli bir müşteri ID'sine göre müşteriyi API'den siler.
        """
        try:
            return self.db.musteri_sil(musteri_id)
        except Exception as e:
            logger.error(f"Müşteri ID {musteri_id} CariService üzerinden silinirken hata: {e}")
            raise

    def tedarikci_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, aktif_durum: bool = None):
        """
        API'den tedarikçi listesini çeker.
        """
        # OnMuhasebe sınıfının tedarikci_listesi_al metodunu doğrudan çağırıyoruz
        # ve tüm parametreleri olduğu gibi iletiyoruz.
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "aktif_durum": aktif_durum
        }
        # None olan veya boş string olan parametreleri temizle (API'ye sadece geçerli filtreleri gönder)
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

        try:
            return self.db.tedarikci_listesi_al(**cleaned_params)
        except Exception as e:
            logger.error(f"Tedarikçi listesi CariService üzerinden alınırken hata: {e}")
            raise

    def tedarikci_getir_by_id(self, tedarikci_id: int):
        """
        Belirli bir tedarikçi ID'sine göre tedarikçi bilgilerini API'den çeker.
        """
        try:
            # OnMuhasebe sınıfının tedarikci_getir_by_id metodunu doğrudan çağırıyoruz.
            return self.db.tedarikci_getir_by_id(tedarikci_id)
        except Exception as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} CariService üzerinden çekilirken hata: {e}")
            raise

    def tedarikci_sil(self, tedarikci_id: int):
        """
        Belirli bir tedarikçi ID'sine göre tedarikçiyi API'den siler.
        """
        try:
            return self.db.tedarikci_sil(tedarikci_id)
        except Exception as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} CariService üzerinden silinirken hata: {e}")
            raise

    def cari_getir_by_id(self, cari_id: int, cari_tipi: str):
        """
        Cari tipine göre ilgili cariyi getirir (Müşteri veya Tedarikçi).
        """
        # db.CARI_TIP_MUSTERI ve db.CARI_TIP_TEDARIKCI sabitleri OnMuhasebe sınıfından alınır.
        # Bu servis sınıfında doğrudan OnMuhasebe.CARI_TIP_MUSTERI olarak erişim yerine
        # self.db.CARI_TIP_MUSTERI şeklinde erişiyoruz.
        if cari_tipi == self.db.CARI_TIP_MUSTERI:
            return self.musteri_getir_by_id(cari_id)
        elif cari_tipi == self.db.CARI_TIP_TEDARIKCI:
            return self.tedarikci_getir_by_id(cari_id)
        else:
            raise ValueError("Geçersiz cari tipi belirtildi. 'MUSTERI' veya 'TEDARIKCI' olmalı.")


class TopluIslemService:
    def __init__(self, db_manager):
        """
        Toplu veri işlemleri (içe/dışa aktarım) için servis sınıfı.
        db_manager artık API ile iletişim kurar.
        """
        self.db = db_manager
        logger.info("TopluIslemService başlatıldı.")

    def toplu_musteri_ice_aktar(self, musteri_listesi: List[Dict[str, Any]]):
        """
        Verilen müşteri listesini toplu olarak içe aktarır.
        Her bir müşteri için API'ye POST isteği gönderir.
        """
        basarili_sayisi = 0
        hata_sayisi = 0
        hatalar = []

        for musteri_data in musteri_listesi:
            try:
                # musteri_ekle metodu OnMuhasebe sınıfında True/False ve mesaj döndürüyor.
                success, msg = self.db.musteri_ekle(musteri_data)
                if success:
                    basarili_sayisi += 1
                else:
                    hata_sayisi += 1
                    hatalar.append(f"Müşteri '{musteri_data.get('ad', 'Bilinmeyen')}' eklenirken hata: {msg}") # 'ad_soyad' yerine 'ad'
            except Exception as e:
                hata_sayisi += 1
                hatalar.append(f"Müşteri '{musteri_data.get('ad', 'Bilinmeyen')}' eklenirken beklenmeyen hata: {e}")
                logger.error(f"Toplu müşteri içe aktarımında hata: {e} - Müşteri: {musteri_data.get('ad')}")
        
        logger.info(f"Toplu müşteri içe aktarım tamamlandı. Başarılı: {basarili_sayisi}, Hata: {hata_sayisi}")
        return {"basarili": basarili_sayisi, "hata": hata_sayisi, "hatalar": hatalar}

    def toplu_tedarikci_ice_aktar(self, tedarikci_listesi: List[Dict[str, Any]]):
        """
        Verilen tedarikçi listesini toplu olarak içe aktarır.
        Her bir tedarikçi için API'ye POST isteği gönderir.
        """
        basarili_sayisi = 0
        hata_sayisi = 0
        hatalar = []

        for tedarikci_data in tedarikci_listesi:
            try:
                # tedarikci_ekle metodu OnMuhasebe sınıfında True/False ve mesaj döndürüyor.
                success, msg = self.db.tedarikci_ekle(tedarikci_data)
                if success:
                    basarili_sayisi += 1
                else:
                    hata_sayisi += 1
                    hatalar.append(f"Tedarikçi '{tedarikci_data.get('ad', 'Bilinmeyen')}' eklenirken hata: {msg}") # 'ad_soyad' yerine 'ad'
            except Exception as e:
                hata_sayisi += 1
                hatalar.append(f"Tedarikçi '{tedarikci_data.get('ad', 'Bilinmeyen')}' eklenirken beklenmeyen hata: {e}")
                logger.error(f"Toplu tedarikçi içe aktarımında hata: {e} - Tedarikçi: {tedarikci_data.get('ad')}")
        
        logger.info(f"Toplu tedarikçi içe aktarım tamamlandı. Başarılı: {basarili_sayisi}, Hata: {hata_sayisi}")
        return {"basarili": basarili_sayisi, "hata": hata_sayisi, "hatalar": hatalar}

    def toplu_stok_ice_aktar(self, stok_listesi: List[Dict[str, Any]]):
        """
        Verilen stok listesini toplu olarak içe aktarır.
        Her bir stok için API'ye POST isteği gönderir.
        """
        basarili_sayisi = 0
        hata_sayisi = 0
        hatalar = []

        for stok_data in stok_listesi:
            try:
                # stok_ekle metodu OnMuhasebe sınıfında True/False ve mesaj döndürüyor.
                success, msg = self.db.stok_ekle(stok_data)
                if success:
                    basarili_sayisi += 1
                else:
                    hata_sayisi += 1
                    hatalar.append(f"Stok '{stok_data.get('ad', 'Bilinmeyen')}' eklenirken hata: {msg}")
            except Exception as e:
                hata_sayisi += 1
                hatalar.append(f"Stok '{stok_data.get('ad', 'Bilinmeyen')}' eklenirken beklenmeyen hata: {e}")
                logger.error(f"Toplu stok içe aktarımında hata: {e} - Stok: {stok_data.get('ad')}")
        
        logger.info(f"Toplu stok içe aktarım tamamlandı. Başarılı: {basarili_sayisi}, Hata: {hata_sayisi}")
        return {"basarili": basarili_sayisi, "hata": hata_sayisi, "hatalar": hatalar}

    def musteri_listesini_disa_aktar(self, **kwargs):
        """
        Müşteri listesini API'den alır ve döndürür.
        kwargs ile skip, limit, arama, aktif_durum gibi parametreler iletilebilir.
        """
        try:
            return self.db.musteri_listesi_al(**kwargs)
        except Exception as e:
            logger.error(f"Müşteri listesi dışa aktarılırken hata: {e}")
            raise

    def tedarikci_listesini_disa_aktar(self, **kwargs):
        """
        Tedarikçi listesini API'den alır ve döndürür.
        kwargs ile skip, limit, arama, aktif_durum gibi parametreler iletilebilir.
        """
        try:
            return self.db.tedarikci_listesi_al(**kwargs)
        except Exception as e:
            logger.error(f"Tedarikçi listesi dışa aktarılırken hata: {e}")
            raise

    def stok_listesini_disa_aktar(self, **kwargs):
        """
        Stok listesini API'den alır ve döndürür.
        kwargs ile skip, limit, arama, aktif_durum, kategori_id, marka_id, urun_grubu_id, stok_durumu, kritik_stok_altinda gibi parametreler iletilebilir.
        """
        try:
            return self.db.stok_listesi_al(**kwargs)
        except Exception as e:
            logger.error(f"Stok listesi dışa aktarılırken hata: {e}")
            raise