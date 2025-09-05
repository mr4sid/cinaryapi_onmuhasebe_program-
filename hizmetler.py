# hizmetler.py Dosyasının TAMAMI (Güncellenmiş Hal)
import requests
import json
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union

from yardimcilar import normalize_turkish_chars

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
                       olusturan_kullanici_id, kasa_banka_id=None, misafir_adi=None, fatura_notlari=None, vade_tarihi=None,
                       genel_iskonto_tipi=None, genel_iskonto_degeri=None, original_fatura_id=None):
        """
        Yeni bir fatura kaydı ve ilişkili kalemlerini API'ye gönderir.
        Tüm iş mantığı sunucu tarafında işlenir.
        """
        fatura_data = {
            "fatura_no": fatura_no,
            "tarih": tarih,
            "fatura_turu": fatura_tipi,
            "cari_id": cari_id,
            "kalemler": kalemler_data,
            "odeme_turu": odeme_turu,
            "kasa_banka_id": kasa_banka_id,
            "misafir_adi": misafir_adi,
            "fatura_notlari": fatura_notlari,
            "vade_tarihi": vade_tarihi,
            "genel_iskonto_tipi": genel_iskonto_tipi,
            "genel_iskonto_degeri": genel_iskonto_degeri,
            "original_fatura_id": original_fatura_id,
            "olusturan_kullanici_id": olusturan_kullanici_id
        }

        try:
            fatura_response = self.db._make_api_request("POST", "/faturalar/", json=fatura_data)
            
            # API'den dönen yanıtın bir sözlük olduğunu ve 'id' anahtarını içerdiğini kontrol et
            if isinstance(fatura_response, dict) and "id" in fatura_response:
                return True, f"Fatura '{fatura_no}' başarıyla oluşturuldu. ID: {fatura_response.get('id')}"
            else:
                # Başarılı bir yanıt alınamamışsa veya formatı yanlışsa
                message = fatura_response.get("detail", "Fatura oluşturma isteği başarısız oldu. API'den beklenmeyen yanıt formatı.")
                logger.error(f"Fatura oluşturma hatası: {message}. Tam yanıt: {fatura_response}")
                return False, message
        
        except ValueError as e:
            # _make_api_request metodundan gelen hataları yakala
            message = str(e)
            logger.error(f"Fatura oluşturma sırasında API hatası: {message}")
            return False, f"Fatura oluşturulurken API hatası: {message}"

        except Exception as e:
            # Diğer tüm beklenmedik hataları yakala
            logger.error(f"Fatura oluşturma sırasında beklenmeyen hata: {e}", exc_info=True)
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
            return False, f"Siparişi faturaya dönüştürülürken beklenmeyen bir hata oluştu: {e}"

class CariService:
    def __init__(self, db_manager):
        """
        Müşteri ve tedarikçi (cari) verilerini yöneten servis sınıfı.
        db_manager ile API üzerinden iletişim kurar.
        """
        self.db = db_manager
        logger.info("CariService başlatıldı.")

    def musteri_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, aktif_durum: bool = None):
        """
        API'den müşteri listesini çeker.
        """
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "aktif_durum": aktif_durum
        }
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

        try:
            return self.db.musteri_listesi_al(**cleaned_params)
        except Exception as e:
            logger.error(f"Müşteri listesi CariService üzerinden alınırken hata: {e}")
            raise

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
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "aktif_durum": aktif_durum
        }
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
        self.db = db_manager
        logger.info("TopluIslemService başlatıldı.")
        # Nitelik verilerini önbelleğe almak için boş sözlükler oluştur
        self._nitelik_cache = {
            "kategoriler": {},
            "markalar": {},
            "urun_gruplari": {},
            "urun_birimleri": {},
            "ulkeler": {}
        }
        self._load_nitelik_cache()
    
    def _load_nitelik_cache(self):
        """Tüm nitelik verilerini API'den çekip önbelleğe alır."""
        try:
            self._nitelik_cache["kategoriler"] = {normalize_turkish_chars(item.get('ad')).lower(): item.get('id') for item in self.db.kategori_listele()}
            self._nitelik_cache["markalar"] = {normalize_turkish_chars(item.get('ad')).lower(): item.get('id') for item in self.db.marka_listele().get('items', [])}
            self._nitelik_cache["urun_gruplari"] = {normalize_turkish_chars(item.get('ad')).lower(): item.get('id') for item in self.db.urun_grubu_listele().get('items', [])}
            self._nitelik_cache["urun_birimleri"] = {normalize_turkish_chars(item.get('ad')).lower(): item.get('id') for item in self.db.urun_birimi_listele().get('items', [])}
            self._nitelik_cache["ulkeler"] = {normalize_turkish_chars(item.get('ad')).lower(): item.get('id') for item in self.db.ulke_listele().get('items', [])}
        except Exception as e:
            logger.error(f"Nitelik önbelleği yüklenirken hata oluştu: {e}")
            
    def _get_nitelik_id_from_cache(self, nitelik_tipi, nitelik_adi):
        """Önbellekten nitelik adını ID'ye dönüştürür."""
        if not nitelik_adi:
            return None
        return self._nitelik_cache[nitelik_tipi].get(normalize_turkish_chars(nitelik_adi).lower())

    def toplu_musteri_analiz_et(self, raw_data: list) -> Dict[str, Union[List, Dict]]:
        processed_data = []
        new_records = []
        update_records = []
        error_records = []

        # Mevcut müşteri verilerini önbelleğe al
        mevcut_musteri_kod_map = {}
        try:
            mevcut_musteriler_response = self.db.musteri_listesi_al(limit=10000)
            mevcut_musteriler = mevcut_musteriler_response.get('items', [])
            for musteri in mevcut_musteriler:
                mevcut_musteri_kod_map[musteri.get('kod')] = musteri
        except Exception as e:
            logger.error(f"Mevcut müşteri listesi çekilirken hata: {e}")
            raise ValueError(f"Mevcut müşteri verileri alınamadı. Analiz durduruldu: {e}")
        
        # Excel verisinin başlık satırını atla (varsayım)
        for row_index, row in enumerate(raw_data):
            hata_mesajlari = []
            
            # 1. Satırın geçerliliğini kontrol et
            if not row or not row[0] or not row[1]:
                hata_mesajlari.append("Müşteri Kodu veya Adı boş olamaz.")
                error_records.append({"hata": "; ".join(hata_mesajlari), "satir": row_index + 2, "veri": row})
                continue
            
            try:
                # 2. Veri tiplerini dönüştür
                kod = str(row[0]).strip()
                ad = str(row[1]).strip()
                telefon = str(row[2]).strip() if len(row) > 2 and row[2] is not None else None
                adres = str(row[3]).strip() if len(row) > 3 and row[3] is not None else None
                vergi_dairesi = str(row[4]).strip() if len(row) > 4 and row[4] is not None else None
                vergi_no = str(row[5]).strip() if len(row) > 5 and row[5] is not None else None
                
                # 3. Kayıt türünü belirle (yeni mi, güncellenecek mi?)
                mevcut_musteri = mevcut_musteri_kod_map.get(kod)
                
                kayit = {
                    "kod": kod,
                    "ad": ad,
                    "telefon": telefon,
                    "adres": adres,
                    "vergi_dairesi": vergi_dairesi,
                    "vergi_no": vergi_no
                }

                if mevcut_musteri:
                    kayit["id"] = mevcut_musteri.get("id")
                    update_records.append(kayit)
                else:
                    new_records.append(kayit)

                processed_data.append(kayit)

            except Exception as e:
                hata_mesajlari.append(f"Analiz hatası: {e}")
                error_records.append({"hata": "; ".join(hata_mesajlari), "satir": row_index + 2, "veri": row})
                
        return {
            "all_processed_data": processed_data,
            "new_records": new_records,
            "update_records": update_records,
            "error_records": error_records
        }

    def toplu_tedarikci_analiz_et(self, raw_data: list) -> Dict[str, Union[List, Dict]]:
        processed_data = []
        new_records = []
        update_records = []
        error_records = []

        # Mevcut tedarikçi verilerini önbelleğe al
        mevcut_tedarikci_kod_map = {}
        try:
            mevcut_tedarikciler_response = self.db.tedarikci_listesi_al(limit=10000)
            mevcut_tedarikciler = mevcut_tedarikciler_response.get('items', [])
            for tedarikci in mevcut_tedarikciler:
                mevcut_tedarikci_kod_map[tedarikci.get('kod')] = tedarikci
        except Exception as e:
            logger.error(f"Mevcut tedarikçi listesi çekilirken hata: {e}")
            raise ValueError(f"Mevcut tedarikçi verileri alınamadı. Analiz durduruldu: {e}")
        
        for row_index, row in enumerate(raw_data):
            hata_mesajlari = []
            
            if not row or not row[0] or not row[1]:
                hata_mesajlari.append("Tedarikçi Kodu veya Adı boş olamaz.")
                error_records.append({"hata": "; ".join(hata_mesajlari), "satir": row_index + 2, "veri": row})
                continue
            
            try:
                kod = str(row[0]).strip()
                ad = str(row[1]).strip()
                telefon = str(row[2]).strip() if len(row) > 2 and row[2] is not None else None
                adres = str(row[3]).strip() if len(row) > 3 and row[3] is not None else None
                vergi_dairesi = str(row[4]).strip() if len(row) > 4 and row[4] is not None else None
                vergi_no = str(row[5]).strip() if len(row) > 5 and row[5] is not None else None
                
                mevcut_tedarikci = mevcut_tedarikci_kod_map.get(kod)
                
                kayit = {
                    "kod": kod,
                    "ad": ad,
                    "telefon": telefon,
                    "adres": adres,
                    "vergi_dairesi": vergi_dairesi,
                    "vergi_no": vergi_no
                }

                if mevcut_tedarikci:
                    kayit["id"] = mevcut_tedarikci.get("id")
                    update_records.append(kayit)
                else:
                    new_records.append(kayit)

                processed_data.append(kayit)

            except Exception as e:
                hata_mesajlari.append(f"Analiz hatası: {e}")
                error_records.append({"hata": "; ".join(hata_mesajlari), "satir": row_index + 2, "veri": row})
                
        return {
            "all_processed_data": processed_data,
            "new_records": new_records,
            "update_records": update_records,
            "error_records": error_records
        }
        
    def toplu_stok_analiz_et(self, excel_veri: List[List[Any]], guncellenecek_alanlar: List[str]):
        """Excel verisini analiz ederek yeni, güncellenecek ve hatalı stok kayıtlarını ayırır."""
        yeni_kayitlar = []
        guncellenecek_kayitlar = []
        hata_kayitlari = []
        tum_islenmis_veri = []

        # Tüm mevcut stok verilerini önbelleğe al
        mevcut_stok_kodu_map = {}
        try:
            mevcut_stoklar_response = self.db.stok_listesi_al(limit=10000)
            mevcut_stoklar = mevcut_stoklar_response.get('items', [])
            for stok in mevcut_stoklar:
                mevcut_stok_kodu_map[stok.get('kod')] = stok
        except Exception as e:
            logger.error(f"Mevcut stok listesi çekilirken hata: {e}")
            raise ValueError(f"Mevcut stok verileri alınamadı. Analiz durduruldu: {e}")

        # Excel verisinin başlık satırını atla (varsayım)
        for index, row_data in enumerate(excel_veri):
            hata_mesajlari = []
            
            # Tüm verileri tutan listeye ekle
            tum_islenmis_veri.append(row_data)

            # 1. Satırın geçerliliğini kontrol et
            if not row_data or not row_data[0]:
                hata_mesajlari.append("Stok kodu boş olamaz.")
                hata_kayitlari.append({"satir": index + 2, "hata": "; ".join(hata_mesajlari), "veri": row_data})
                continue
            
            try:
                # 2. Veri tiplerini dönüştür ve doğrula
                kod = str(row_data[0]).strip()
                ad = str(row_data[1]).strip() if len(row_data) > 1 and row_data[1] is not None else None
                
                # Sayısal alanları güvenli bir şekilde dönüştür
                miktar = self.db.safe_float(row_data[2]) if len(row_data) > 2 and row_data[2] is not None else 0.0
                alis_fiyati = self.db.safe_float(row_data[3]) if len(row_data) > 3 and row_data[3] is not None else 0.0
                satis_fiyati = self.db.safe_float(row_data[4]) if len(row_data) > 4 and row_data[4] is not None else 0.0
                kdv_orani = self.db.safe_float(row_data[5]) if len(row_data) > 5 and row_data[5] is not None else 20.0
                min_stok_seviyesi = self.db.safe_float(row_data[6]) if len(row_data) > 6 and row_data[6] is not None else 0.0
                aktif = row_data[7] if len(row_data) > 7 and row_data[7] is not None else True
                
                # Nitelik adlarını ID'ye çevir (isteğe bağlı sütunlar için)
                kategori_adi = str(row_data[8]).strip() if len(row_data) > 8 and row_data[8] is not None else None
                marka_adi = str(row_data[9]).strip() if len(row_data) > 9 and row_data[9] is not None else None
                urun_grubu_adi = str(row_data[10]).strip() if len(row_data) > 10 and row_data[10] is not None else None
                birim_adi = str(row_data[11]).strip() if len(row_data) > 11 and row_data[11] is not None else None
                ulke_adi = str(row_data[12]).strip() if len(row_data) > 12 and row_data[12] is not None else None
                detay = str(row_data[13]).strip() if len(row_data) > 13 and row_data[13] is not None else None
                urun_resmi_yolu = str(row_data[14]).strip() if len(row_data) > 14 and row_data[14] is not None else None
                
                # Nitelik ID'lerini almak için önbelleklenmiş veriyi kullan
                kategori_id = self._get_nitelik_id_from_cache("kategoriler", kategori_adi) if kategori_adi else None
                marka_id = self._get_nitelik_id_from_cache("markalar", marka_adi) if marka_adi else None
                urun_grubu_id = self._get_nitelik_id_from_cache("urun_gruplari", urun_grubu_adi) if urun_grubu_adi else None
                birim_id = self._get_nitelik_id_from_cache("urun_birimleri", birim_adi) if birim_adi else None
                mense_id = self._get_nitelik_id_from_cache("ulkeler", ulke_adi) if ulke_adi else None
                
                # 3. Kayıt türünü belirle (yeni mi, güncellenecek mi?)
                mevcut_stok = mevcut_stok_kodu_map.get(kod)
                
                kayit = {
                    "kod": kod,
                    "ad": ad,
                    "miktar": miktar,
                    "alis_fiyati": alis_fiyati,
                    "satis_fiyati": satis_fiyati,
                    "kdv_orani": kdv_orani,
                    "min_stok_seviyesi": min_stok_seviyesi,
                    "aktif": aktif,
                    "detay": detay,
                    "kategori_id": kategori_id,
                    "marka_id": marka_id,
                    "urun_grubu_id": urun_grubu_id,
                    "birim_id": birim_id,
                    "mense_id": mense_id,
                    "urun_resmi_yolu": urun_resmi_yolu
                }
                
                if mevcut_stok:
                    kayit["id"] = mevcut_stok.get("id")
                    guncellenecek_kayitlar.append(kayit)
                else:
                    if not ad:
                        hata_mesajlari.append("Yeni ürünler için Ad alanı zorunludur.")
                        raise ValueError("Yeni ürün için Ad alanı zorunlu.")
                    yeni_kayitlar.append(kayit)

            except (ValueError, IndexError) as e:
                hata_mesajlari.append(f"Veri formatı hatası: {e}. Lütfen sayısal alanları kontrol edin.")
            except Exception as e:
                hata_mesajlari.append(f"Analiz hatası: {e}")

            if hata_mesajlari:
                hata_kayitlari.append({
                    "satir": index + 2,
                    "hata": "; ".join(hata_mesajlari),
                    "veri": row_data
                })

        return {
            "new_records": yeni_kayitlar,
            "update_records": guncellenecek_kayitlar,
            "error_records": hata_kayitlari,
            "all_processed_data": tum_islenmis_veri
        }
    
    def toplu_musteri_ice_aktar(self, musteri_listesi: List[Dict[str, Any]]):
        basarili_sayisi = 0
        hata_sayisi = 0
        hatalar = []

        for musteri_data in musteri_listesi:
            try:
                mevcut_musteri_response = self.db._make_api_request("GET", f"/musteriler/", params={"arama": musteri_data.get('kod')})
                mevcut_musteri = [m for m in mevcut_musteri_response.get("items", []) if m.get('kod') == musteri_data.get('kod')]
                
                if mevcut_musteri:
                    success, msg = self.db.musteri_guncelle(mevcut_musteri[0].get('id'), musteri_data)
                else:
                    success, msg = self.db.musteri_ekle(musteri_data)

                if success:
                    basarili_sayisi += 1
                else:
                    hata_sayisi += 1
                    hatalar.append(f"Müşteri '{musteri_data.get('ad', 'Bilinmeyen')}' eklenirken hata: {msg}")
            except Exception as e:
                hata_sayisi += 1
                hatalar.append(f"Müşteri '{musteri_data.get('ad', 'Bilinmeyen')}' eklenirken beklenmeyen hata: {e}")
                logger.error(f"Toplu müşteri içe aktarımında hata: {e} - Müşteri: {musteri_data.get('ad')}")
        
        logger.info(f"Toplu müşteri içe aktarım tamamlandı. Başarılı: {basarili_sayisi}, Hata: {hata_sayisi}")
        return {"basarili": basarili_sayisi, "hata": hata_sayisi, "hatalar": hatalar}
    
    def toplu_tedarikci_ice_aktar(self, tedarikci_listesi: List[Dict[str, Any]]):
        basarili_sayisi = 0
        hata_sayisi = 0
        hatalar = []

        for tedarikci_data in tedarikci_listesi:
            try:
                mevcut_tedarikci_response = self.db._make_api_request("GET", f"/tedarikciler/", params={"arama": tedarikci_data.get('kod')})
                mevcut_tedarikci = [t for t in mevcut_tedarikci_response.get("items", []) if t.get('kod') == tedarikci_data.get('kod')]

                if mevcut_tedarikci:
                    success, msg = self.db.tedarikci_guncelle(mevcut_tedarikci[0].get('id'), tedarikci_data)
                else:
                    success, msg = self.db.tedarikci_ekle(tedarikci_data)

                if success:
                    basarili_sayisi += 1
                else:
                    hata_sayisi += 1
                    hatalar.append(f"Tedarikçi '{tedarikci_data.get('ad', 'Bilinmeyen')}' eklenirken hata: {msg}")
            except Exception as e:
                hata_sayisi += 1
                hatalar.append(f"Tedarikçi '{tedarikci_data.get('ad', 'Bilinmeyen')}' eklenirken beklenmeyen hata: {e}")
                logger.error(f"Toplu tedarikçi içe aktarımında hata: {e} - Tedarikçi: {tedarikci_data.get('ad')}")
        
        logger.info(f"Toplu tedarikçi içe aktarım tamamlandı. Başarılı: {basarili_sayisi}, Hata: {hata_sayisi}")
        return {"basarili": basarili_sayisi, "hata": hata_sayisi, "hatalar": hatalar}
        
    def toplu_stok_ice_aktar(self, stok_listesi: List[Dict[str, Any]]):
        """
        Toplu stok ekleme/güncelleme işlemini API'ye gönderir.
        """
        try:
            payload = []
            for stok in stok_listesi:
                # Veri formatını API'nin beklediği şekilde düzenle
                payload.append({
                    "kod": stok.get("kod"),
                    "ad": stok.get("ad"),
                    "miktar": stok.get("miktar"),
                    "alis_fiyati": stok.get("alis_fiyati"),
                    "satis_fiyati": stok.get("satis_fiyati"),
                    "kdv_orani": stok.get("kdv_orani"),
                    "min_stok_seviyesi": stok.get("min_stok_seviyesi"),
                    "aktif": stok.get("aktif")
                })

            response = requests.post(f"{self.db.api_base_url}/stoklar/bulk_upsert", json=payload)
            response.raise_for_status()
            response_data = response.json()
            
            # Burada yeni eklenen stoklar için alış faturası oluşturma mantığını ekliyoruz.
            yeni_eklenen_stok_idleri = response_data.get("yeni_eklenen_stok_idleri", [])
            guncellenen_stok_idleri = response_data.get("guncellenen_stok_idleri", [])
            
            fatura_hizmeti = FaturaService(self.db)
            
            # Yeni eklenen her stok için alış faturası oluştur
            if yeni_eklenen_stok_idleri:
                for stok_id in yeni_eklenen_stok_idleri:
                    yeni_stok_data = next((s for s in stok_listesi if s.get('id') == stok_id), None)
                    if yeni_stok_data:
                        # Fatura oluşturmak için gerekli veriyi hazırla
                        kalemler_data = [{
                            "urun_id": stok_id,
                            "miktar": yeni_stok_data.get("miktar"),
                            "birim_fiyat": yeni_stok_data.get("alis_fiyati"),
                            "kdv_orani": yeni_stok_data.get("kdv_orani")
                        }]
                        
                        fatura_hizmeti.fatura_olustur(
                            fatura_no=f"TOPLU-{datetime.now().strftime('%Y%m%d%H%M%S')}-{stok_id}",
                            tarih=datetime.now().strftime('%Y-%m-%d'),
                            fatura_tipi=self.db.FATURA_TIP_ALIS,
                            cari_id=self.db.get_genel_tedarikci_id(),
                            kalemler_data=kalemler_data,
                            odeme_turu=self.db.ODEME_TURU_ACIK_HESAP,
                            fatura_notlari="Toplu stok ekleme işlemiyle otomatik oluşturulmuştur."
                        )

            return {
                "yeni_eklenen_sayisi": response_data.get("yeni_eklenen_sayisi", 0),
                "guncellenen_sayisi": response_data.get("guncellenen_sayisi", 0),
                "hata_sayisi": response_data.get("hata_sayisi", 0),
                "hatalar": response_data.get("hatalar", [])
            }

        except requests.exceptions.HTTPError as e:
            logger.error(f"API isteği sırasında hata oluştu: {e.response.text}", exc_info=True)
            return {
                "yeni_eklenen_sayisi": 0,
                "guncellenen_sayisi": 0,
                "hata_sayisi": len(stok_listesi),
                "hatalar": [f"API isteği sırasında bir hata oluştu: {e.response.text}"]
            }
        except Exception as e:
            logger.error(f"Toplu stok ekleme/güncelleme sırasında beklenmedik hata: {e}", exc_info=True)
            return {
                "yeni_eklenen_sayisi": 0,
                "guncellenen_sayisi": 0,
                "hata_sayisi": len(stok_listesi),
                "hatalar": [f"Beklenmedik bir hata oluştu: {e}"]
            }
            
    def musteri_listesini_disa_aktar(self, **kwargs):
        try:
            return self.db.musteri_listesi_al(**kwargs)
        except Exception as e:
            logger.error(f"Müşteri listesi dışa aktarılırken hata: {e}")
            raise

    def tedarikci_listesini_disa_aktar(self, **kwargs):
        try:
            return self.db.tedarikci_listesi_al(**kwargs)
        except Exception as e:
            logger.error(f"Tedarikçi listesi dışa aktarılırken hata: {e}")
            raise

    def stok_listesini_disa_aktar(self, **kwargs):
        try:
            return self.db.stok_listesi_al(**kwargs)
        except Exception as e:
            logger.error(f"Stok listesi dışa aktarılırken hata: {e}")
            raise