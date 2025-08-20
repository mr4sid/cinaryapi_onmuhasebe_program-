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
                fatura_id = fatura_response.get("id")
                return True, f"Fatura '{fatura_no}' başarıyla oluşturuldu. ID: {fatura_id}"
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
    
    def toplu_musteri_analiz_et(self, raw_data: list) -> Dict[str, Union[List, Dict]]:
        processed_data = []
        new_records = []
        update_records = []
        error_records = []
        
        for row_index, row in enumerate(raw_data):
            try:
                kod = str(row[0]).strip() if len(row) > 0 and row[0] is not None else None
                ad = str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
                
                if not kod or not ad:
                    error_records.append({"hata": "Kod veya Ad boş olamaz", "satir": row_index + 2, "veri": row})
                    continue

                mevcut_musteri_response = self.db.musteri_listesi_al(arama=kod)
                mevcut_musteri = [m for m in mevcut_musteri_response.get("items") if m.get('kod') == kod]
                
                if mevcut_musteri:
                    update_records.append({"kod": kod, "ad": ad})
                else:
                    new_records.append({"kod": kod, "ad": ad})

                processed_data.append({
                    "kod": kod,
                    "ad": ad,
                    "telefon": str(row[2]).strip() if len(row) > 2 and row[2] is not None else None,
                    "adres": str(row[3]).strip() if len(row) > 3 and row[3] is not None else None,
                    "vergi_dairesi": str(row[4]).strip() if len(row) > 4 and row[4] is not None else None,
                    "vergi_no": str(row[5]).strip() if len(row) > 5 and row[5] is not None else None
                })
            except Exception as e:
                error_records.append({"hata": f"Analiz hatası: {e}", "satir": row_index + 2, "veri": row})
                
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
        
        for row_index, row in enumerate(raw_data):
            try:
                kod = str(row[0]).strip() if len(row) > 0 and row[0] is not None else None
                ad = str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
                
                if not kod or not ad:
                    error_records.append({"hata": "Kod veya Ad boş olamaz", "satir": row_index + 2, "veri": row})
                    continue

                mevcut_tedarikci_response = self.db.tedarikci_listesi_al(arama=kod)
                mevcut_tedarikci = [t for t in mevcut_tedarikci_response.get("items") if t.get('kod') == kod]
                
                if mevcut_tedarikci:
                    update_records.append({"kod": kod, "ad": ad})
                else:
                    new_records.append({"kod": kod, "ad": ad})

                processed_data.append({
                    "kod": kod,
                    "ad": ad,
                    "telefon": str(row[2]).strip() if len(row) > 2 and row[2] is not None else None,
                    "adres": str(row[3]).strip() if len(row) > 3 and row[3] is not None else None,
                    "vergi_dairesi": str(row[4]).strip() if len(row) > 4 and row[4] is not None else None,
                    "vergi_no": str(row[5]).strip() if len(row) > 5 and row[5] is not None else None
                })
            except Exception as e:
                error_records.append({"hata": f"Analiz hatası: {e}", "satir": row_index + 2, "veri": row})
                
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

        # Excel verisinin başlık satırını atla
        for index, row_data in enumerate(excel_veri):
            kayit = {}
            hata_mesajlari = []
            
            # Tüm verileri tutan listeye ekle
            tum_islenmis_veri.append(row_data)

            # Stok kodu Excel'deki ilk sütun, kontrol et
            if not row_data or not row_data[0]:
                hata_mesajlari.append("Stok kodu boş olamaz.")
            else:
                try:
                    # Veri tiplerini dönüştürme ve doğrulama
                    kod = str(row_data[0]).strip()
                    ad = str(row_data[1]).strip() if len(row_data) > 1 and row_data[1] is not None else ""
                    miktar = float(row_data[2]) if len(row_data) > 2 and row_data[2] is not None else 0.0
                    alis_fiyati = float(row_data[3]) if len(row_data) > 3 and row_data[3] is not None else 0.0
                    satis_fiyati = float(row_data[4]) if len(row_data) > 4 and row_data[4] is not None else 0.0
                    kdv_orani = float(row_data[5]) if len(row_data) > 5 and row_data[5] is not None else 20.0
                    min_stok_seviyesi = float(row_data[6]) if len(row_data) > 6 and row_data[6] is not None else 0.0
                    aktif = bool(row_data[7]) if len(row_data) > 7 and row_data[7] is not None else True

                    # Veritabanında mevcut stoğu ara
                    eslesen_stoklar = self.db.stok_listesi_al(arama=kod, limit=1)

                    if eslesen_stoklar["total"] > 0:
                        # Stok mevcut, güncelleme kaydı olarak işaretle
                        mevcut_stok = eslesen_stoklar["items"][0]
                        kayit = {
                            "id": mevcut_stok.get("id"),
                            "kod": kod,
                            "ad": ad or mevcut_stok.get("ad"),
                            "miktar": miktar or mevcut_stok.get("miktar"),
                            "alis_fiyati": alis_fiyati or mevcut_stok.get("alis_fiyati"),
                            "satis_fiyati": satis_fiyati or mevcut_stok.get("satis_fiyati"),
                            "kdv_orani": kdv_orani or mevcut_stok.get("kdv_orani"),
                            "min_stok_seviyesi": min_stok_seviyesi or mevcut_stok.get("min_stok_seviyesi"),
                            "aktif": aktif or mevcut_stok.get("aktif")
                        }
                        guncellenecek_kayitlar.append(kayit)
                    else:
                        # Stok mevcut değil, yeni kayıt olarak işaretle
                        kayit = {
                            "kod": kod,
                            "ad": ad,
                            "miktar": miktar,
                            "alis_fiyati": alis_fiyati,
                            "satis_fiyati": satis_fiyati,
                            "kdv_orani": kdv_orani,
                            "min_stok_seviyesi": min_stok_seviyesi,
                            "aktif": aktif
                        }
                        yeni_kayitlar.append(kayit)
                except (ValueError, IndexError) as e:
                    hata_mesajlari.append(f"Veri formatı hatası: {e}. Lütfen sayısal alanları kontrol edin.")
            
            # Hata mesajları varsa, kaydı hatalı olarak ekle
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