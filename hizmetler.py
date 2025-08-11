# hizmetler.py Dosyasının TAMAMI (Güncellenmiş Hal)
import requests
import json
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union

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
        """
        Toplu veri işlemleri (içe/dışa aktarım) için servis sınıfı.
        db_manager artık API ile iletişim kurar.
        """
        self.db = db_manager
        logger.info("TopluIslemService başlatıldı.")
    
    def toplu_musteri_analiz_et(self, raw_data: list) -> Dict[str, Union[List, Dict]]:
        """
        Ham müşteri listesini analiz eder ve önizleme için hazırlar.
        """
        processed_data = []
        new_records = []
        update_records = []
        error_records = []
        
        # Her satır bir liste
        for row_index, row in enumerate(raw_data):
            try:
                # Excel sütunlarına göre veriyi çek
                kod = str(row[0]).strip() if len(row) > 0 and row[0] is not None else None
                ad = str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
                
                if not kod or not ad:
                    error_records.append({"hata": "Kod veya Ad boş olamaz", "satir": row_index + 2, "veri": row})
                    continue

                # API'den mevcut müşteriyi kontrol et
                mevcut_musteri_response = self.db.musteri_listesi_al(arama=kod) # Tam arama yerine ilike ile arar
                mevcut_musteri = [m for m in mevcut_musteri_response.get("items") if m.get('kod') == kod] # Sadece tam eşleşme
                
                if mevcut_musteri:
                    # Güncelleme kaydı
                    update_records.append({"kod": kod, "ad": ad})
                else:
                    # Yeni kayıt
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
        """
        Ham tedarikçi listesini analiz eder ve önizleme için hazırlar.
        """
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
        
    def toplu_stok_analiz_et(self, raw_data: list, selected_update_fields: List[str]) -> Dict[str, Union[List, Dict]]:
        """
        Ham stok listesini analiz eder ve önizleme için hazırlar.
        """
        processed_data = []
        new_records = []
        update_records = []
        error_records = []

        for row_index, row in enumerate(raw_data):
            try:
                # Excel'den gelen veriyi güvenli bir şekilde al ve temizle
                kod_raw = row[0] if len(row) > 0 and row[0] is not None else None
                ad_raw = row[1] if len(row) > 1 and row[1] is not None else None
                
                # Kod ve ad üzerinde daha agresif bir temizlik yap
                kod = str(kod_raw).strip().replace('"', '').replace("'", '') if kod_raw is not None else None
                ad = str(ad_raw).strip() if ad_raw is not None else None

                if not kod:
                    error_records.append({"hata": "Ürün Kodu boş olamaz", "satir": row_index + 2, "veri": row})
                    continue
                
                if not ad:
                    error_records.append({"hata": "Ürün Adı boş olamaz", "satir": row_index + 2, "veri": row})
                    continue
                    
                # API'den mevcut stoku kontrol et
                mevcut_stok_response = self.db.stok_listesi_al(arama=kod)
                mevcut_stok = [m for m in mevcut_stok_response.get("items", []) if m.get('kod') == kod]
                
                if mevcut_stok:
                    update_records.append({"kod": kod, "ad": ad})
                else:
                    new_records.append({"kod": kod, "ad": ad})
                
                # Sınıflandırma adlarına göre ID'leri bul
                def get_nitelik_id(nitelik_tipi, nitelik_adi_raw):
                    if not nitelik_adi_raw or str(nitelik_adi_raw).strip() == "" or str(nitelik_adi_raw).strip().lower() == "none":
                        return None
                    
                    nitelik_adi = str(nitelik_adi_raw).strip()

                    try:
                        # API endpoint'i: /nitelikler/{nitelik_tipi}
                        response = self.db._make_api_request("GET", f"/nitelikler/{nitelik_tipi}", params={"arama": nitelik_adi, "limit": 2})
                        items = response.get("items", [])
                        
                        # Tam eşleşme kontrolü
                        exact_matches = [item for item in items if item.get("ad") == nitelik_adi]
                        
                        if len(exact_matches) == 1:
                            return exact_matches[0].get("id")
                        elif len(exact_matches) > 1:
                            error_records.append({"hata": f"'{nitelik_adi}' için birden fazla eşleşme bulundu. Lütfen veriyi tekilleştirin.", "satir": row_index + 2, "veri": row})
                        else:
                            error_records.append({"hata": f"'{nitelik_adi}' ({nitelik_tipi}) bulunamadı.", "satir": row_index + 2, "veri": row})
                        return None
                    except Exception as e:
                        error_records.append({"hata": f"API'den nitelik bilgisi çekilirken hata: {e}", "satir": row_index + 2, "veri": row})
                        return None

                kategori_id = get_nitelik_id("kategoriler", str(row[7]))
                marka_id = get_nitelik_id("markalar", str(row[8]))
                urun_grubu_id = get_nitelik_id("urun_gruplari", str(row[9]))
                birim_id = get_nitelik_id("urun_birimleri", str(row[10]))
                mense_id = get_nitelik_id("ulkeler", str(row[11]))

                processed_data.append({
                    "kod": kod,
                    "ad": ad,
                    "miktar": self.db.safe_float(row[2]) if len(row) > 2 and row[2] is not None else None,
                    "alis_fiyati": self.db.safe_float(row[3]) if len(row) > 3 and row[3] is not None else None,
                    "satis_fiyati": self.db.safe_float(row[4]) if len(row) > 4 and row[4] is not None else None,
                    "kdv_orani": self.db.safe_float(row[5]) if len(row) > 5 and row[5] is not None else None,
                    "min_stok_seviyesi": self.db.safe_float(row[6]) if len(row) > 6 and row[6] is not None else None,
                    "kategori_id": kategori_id,
                    "marka_id": marka_id,
                    "urun_grubu_id": urun_grubu_id,
                    "birim_id": birim_id,
                    "mense_id": mense_id,
                    "detay": str(row[12]).strip() if len(row) > 12 and row[12] is not None else None,
                    "urun_resmi_yolu": str(row[13]).strip() if len(row) > 13 and row[13] is not None else None,
                    "selected_update_fields": selected_update_fields
                })
            except Exception as e:
                error_records.append({"hata": f"Analiz hatası: {e}", "satir": row_index + 2, "veri": row})
                
        return {
            "all_processed_data": processed_data,
            "new_records": new_records,
            "update_records": update_records,
            "error_records": error_records,
            "selected_update_fields_from_ui": selected_update_fields
        }

    def toplu_musteri_ice_aktar(self, musteri_listesi: List[Dict[str, Any]]):
        """
        Verilen müşteri listesini toplu olarak içe aktarır.
        """
        basarili_sayisi = 0
        hata_sayisi = 0
        hatalar = []

        for musteri_data in musteri_listesi:
            try:
                # Müşteri zaten var mı diye kontrol et
                mevcut_musteri_response = self.db._make_api_request("GET", f"/musteriler/", params={"arama": musteri_data.get('kod')})
                mevcut_musteri = mevcut_musteri_response.get("items")
                
                if mevcut_musteri and mevcut_musteri[0].get('kod') == musteri_data.get('kod'):
                    # Güncelleme işlemi
                    success, msg = self.db.musteri_guncelle(mevcut_musteri[0].get('id'), musteri_data)
                else:
                    # Ekleme işlemi
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
        """
        Verilen tedarikçi listesini toplu olarak içe aktarır.
        """
        basarili_sayisi = 0
        hata_sayisi = 0
        hatalar = []

        for tedarikci_data in tedarikci_listesi:
            try:
                mevcut_tedarikci_response = self.db._make_api_request("GET", f"/tedarikciler/", params={"arama": tedarikci_data.get('kod')})
                mevcut_tedarikci = mevcut_tedarikci_response.get("items")

                if mevcut_tedarikci and mevcut_tedarikci[0].get('kod') == tedarikci_data.get('kod'):
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
        Verilen stok listesini toplu olarak içe aktarır.
        """
        try:
            response_data = self.db.bulk_stok_upsert(stok_listesi)
            return {
                "basarili": response_data.get("yeni_eklenen_sayisi", 0) + response_data.get("guncellenen_sayisi", 0),
                "hata": response_data.get("hata_sayisi", 0),
                "hatalar": response_data.get("hatalar", [])
            }
        except ValueError as e:
            logger.error(f"Toplu stok ekleme/güncelleme API'den hata döndü: {e}")
            return {"basarili": 0, "hata": len(stok_listesi), "hatalar": [f"Genel API hatası: {e}"]}
        except Exception as e:
            logger.error(f"Toplu stok ekleme/güncelleme sırasında beklenmedik hata: {e}", exc_info=True)
            return {"basarili": 0, "hata": len(stok_listesi), "hatalar": [f"Beklenmedik bir hata oluştu: {e}"]}
    
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