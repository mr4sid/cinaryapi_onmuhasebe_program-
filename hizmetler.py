# hizmetler.py Dosyasının TAMAMI
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union
from yardimcilar import normalize_turkish_chars
from api import modeller
from local_semalar import Base, Stok, Musteri, Tedarikci, Fatura, FaturaKalemi, Siparis, CariHareket, UrunKategori, UrunMarka, UrunGrubu, UrunBirimi, Ulke, GelirSiniflandirma, GiderSiniflandirma, KasaBanka
logger = logging.getLogger(__name__)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class FaturaService:
    def __init__(self, db_manager):
        self.db = db_manager
        logger.info("FaturaService başlatıldı.")

    def fatura_olustur(self, fatura_no, tarih, fatura_tipi, cari_id, kalemler_data, odeme_turu,
                         olusturan_kullanici_id, kasa_banka_id=None, misafir_adi=None, fatura_notlari=None, vade_tarihi=None,
                         genel_iskonto_tipi=None, genel_iskonto_degeri=None, original_fatura_id=None):
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
            
            if isinstance(fatura_response, dict) and "id" in fatura_response:
                return True, f"Fatura '{fatura_no}' başarıyla oluşturuldu. ID: {fatura_response.get('id')}"
            else:
                message = fatura_response.get("detail", "Fatura oluşturma isteği başarısız oldu. API'den beklenmeyen yanıt formatı.")
                logger.error(f"Fatura oluşturma hatası: {message}. Tam yanıt: {fatura_response}")
                return False, message
        
        except ValueError as e:
            message = str(e)
            logger.error(f"Fatura oluşturma sırasında API hatası: {message}")
            return False, f"Fatura oluşturulurken API hatası: {message}"

        except Exception as e:
            logger.error(f"Fatura oluşturma sırasında beklenmeyen hata: {e}", exc_info=True)
            return False, f"Fatura oluşturulurken beklenmeyen bir hata oluştu: {e}"

    def fatura_guncelle(self, fatura_id, fatura_no, tarih, cari_id, odeme_turu, kalemler_data,
                          kasa_banka_id=None, misafir_adi=None, fatura_notlari=None, vade_tarihi=None,
                          genel_iskonto_tipi=None, genel_iskonto_degeri=None):
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
            "kalemler": kalemler_data
        }
        try:
            response_data = self.db.fatura_guncelle(fatura_id, fatura_data)
            return True, response_data.get("message", "Fatura başarıyla güncellendi.")
        except ValueError as e:
            logger.error(f"Fatura güncellenirken API hatası: {e}")
            return False, f"Fatura güncellenemedi: {e}"
        except Exception as e:
            logger.error(f"Fatura güncellenirken beklenmeyen bir hata oluştu: {e}")
            return False, f"Fatura güncellenirken beklenmeyen bir hata oluştu: {e}"

    def siparis_faturaya_donustur(self, siparis_id: int, fatura_donusum_data: dict):
        try:
            response = requests.post(f"{self.db.api_base_url}/siparisler/{siparis_id}/faturaya_donustur", json=fatura_donusum_data)
            response.raise_for_status()
            
            response_data = response.json()
            return True, response_data.get("message", "Sipariş başarıyla faturaya dönüştürüldü.")
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            logger.error(f"Siparişi faturaya dönüştürürken API hatası: {error_detail}")
            return False, f"Sipariş faturaya dönüştürülemedi: {error_detail}"
        except Exception as e:
            logger.error(f"Siparişi faturaya dönüştürürken beklenmeyen bir hata oluştu: {e}")
            return False, f"Siparişi faturaya dönüştürülürken beklenmeyen bir hata oluştu: {e}"

class CariService:
    def __init__(self, db_manager):
        self.db = db_manager
        logger.info("CariService başlatıldı.")

    def musteri_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, aktif_durum: bool = None):
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
        try:
            return self.db.musteri_getir_by_id(musteri_id)
        except Exception as e:
            logger.error(f"Müşteri ID {musteri_id} CariService üzerinden çekilirken hata: {e}")
            raise

    def musteri_sil(self, musteri_id: int):
        try:
            return self.db.musteri_sil(musteri_id)
        except Exception as e:
            logger.error(f"Müşteri ID {musteri_id} CariService üzerinden silinirken hata: {e}")
            raise

    def tedarikci_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, aktif_durum: bool = None):
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
        try:
            return self.db.tedarikci_getir_by_id(tedarikci_id)
        except Exception as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} CariService üzerinden çekilirken hata: {e}")
            raise

    def tedarikci_sil(self, tedarikci_id: int):
        try:
            return self.db.tedarikci_sil(tedarikci_id)
        except Exception as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} CariService üzerinden silinirken hata: {e}")
            raise

    def cari_getir_by_id(self, cari_id: int, cari_tipi: str):
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
        self._nitelik_cache = {
            "kategoriler": {},
            "markalar": {},
            "urun_gruplari": {},
            "urun_birimleri": {},
            "ulkeler": {}
        }
        self._load_nitelik_cache()
    
    def _load_nitelik_cache(self):
        try:
            self._nitelik_cache["kategoriler"] = {normalize_turkish_chars(item.get('ad')).lower(): item.get('id') for item in self.db.kategori_listele()}
            self._nitelik_cache["markalar"] = {normalize_turkish_chars(item.get('ad')).lower(): item.get('id') for item in self.db.marka_listele().get('items', [])}
            self._nitelik_cache["urun_gruplari"] = {normalize_turkish_chars(item.get('ad')).lower(): item.get('id') for item in self.db.urun_grubu_listele().get('items', [])}
            self._nitelik_cache["urun_birimleri"] = {normalize_turkish_chars(item.get('ad')).lower(): item.get('id') for item in self.db.urun_birimi_listele().get('items', [])}
            self._nitelik_cache["ulkeler"] = {normalize_turkish_chars(item.get('ad')).lower(): item.get('id') for item in self.db.ulke_listele().get('items', [])}
        except Exception as e:
            logger.error(f"Nitelik önbelleği yüklenirken hata oluştu: {e}")
            
    def _get_nitelik_id_from_cache(self, nitelik_tipi, nitelik_adi):
        if not nitelik_adi:
            return None
        return self._nitelik_cache[nitelik_tipi].get(normalize_turkish_chars(nitelik_adi).lower())

    def toplu_musteri_analiz_et(self, raw_data: list) -> Dict[str, Union[List, Dict]]:
        processed_data = []
        new_records = []
        update_records = []
        error_records = []

        mevcut_musteri_kod_map = {}
        try:
            mevcut_musteriler_response = self.db.musteri_listesi_al(limit=10000)
            mevcut_musteriler = mevcut_musteriler_response.get('items', [])
            for musteri in mevcut_musteriler:
                mevcut_musteri_kod_map[musteri.get('kod')] = musteri
        except Exception as e:
            logger.error(f"Mevcut müşteri listesi çekilirken hata: {e}")
            raise ValueError(f"Mevcut müşteri verileri alınamadı. Analiz durduruldu: {e}")
        
        for row_index, row in enumerate(raw_data):
            hata_mesajlari = []
            
            if not row or not row[0] or not row[1]:
                hata_mesajlari.append("Müşteri Kodu veya Adı boş olamaz.")
                error_records.append({"hata": "; ".join(hata_mesajlari), "satir": row_index + 2, "veri": row})
                continue
            
            try:
                kod = str(row[0]).strip()
                ad = str(row[1]).strip()
                telefon = str(row[2]).strip() if len(row) > 2 and row[2] is not None else None
                adres = str(row[3]).strip() if len(row) > 3 and row[3] is not None else None
                vergi_dairesi = str(row[4]).strip() if len(row) > 4 and row[4] is not None else None
                vergi_no = str(row[5]).strip() if len(row) > 5 and row[5] is not None else None
                
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

        mevcut_stok_kodu_map = {}
        try:
            mevcut_stoklar_response = self.db.stok_listesi_al(limit=10000)
            mevcut_stoklar = mevcut_stoklar_response.get('items', [])
            for stok in mevcut_stoklar:
                mevcut_stok_kodu_map[stok.get('kod')] = stok
        except Exception as e:
            logger.error(f"Mevcut stok listesi çekilirken hata: {e}")
            raise ValueError(f"Mevcut stok verileri alınamadı. Analiz durduruldu: {e}")

        for index, row_data in enumerate(excel_veri):
            hata_mesajlari = []
            
            tum_islenmis_veri.append(row_data)

            if not row_data or not row_data[0]:
                hata_mesajlari.append("Stok kodu boş olamaz.")
                hata_kayitlari.append({"satir": index + 2, "hata": "; ".join(hata_mesajlari), "veri": row_data})
                continue
            
            try:
                kod = str(row_data[0]).strip()
                ad = str(row_data[1]).strip() if len(row_data) > 1 and row_data[1] is not None else None
                
                miktar = self.db.safe_float(row_data[2]) if len(row_data) > 2 and row_data[2] is not None else 0.0
                alis_fiyati = self.db.safe_float(row_data[3]) if len(row_data) > 3 and row_data[3] is not None else 0.0
                satis_fiyati = self.db.safe_float(row_data[4]) if len(row_data) > 4 and row_data[4] is not None else 0.0
                kdv_orani = self.db.safe_float(row_data[5]) if len(row_data) > 5 and row_data[5] is not None else 20.0
                min_stok_seviyesi = self.db.safe_float(row_data[6]) if len(row_data) > 6 and row_data[6] is not None else 0.0
                aktif = row_data[7] if len(row_data) > 7 and row_data[7] is not None else True
                
                kategori_adi = str(row_data[8]).strip() if len(row_data) > 8 and row_data[8] is not None else None
                marka_adi = str(row_data[9]).strip() if len(row_data) > 9 and row_data[9] is not None else None
                urun_grubu_adi = str(row_data[10]).strip() if len(row_data) > 10 and row_data[10] is not None else None
                birim_adi = str(row_data[11]).strip() if len(row_data) > 11 and row_data[11] is not None else None
                ulke_adi = str(row_data[12]).strip() if len(row_data) > 12 and row_data[12] is not None else None
                detay = str(row_data[13]).strip() if len(row_data) > 13 and row_data[13] is not None else None
                urun_resmi_yolu = str(row_data[14]).strip() if len(row_data) > 14 and row_data[14] is not None else None
                
                kategori_id = self._get_nitelik_id_from_cache("kategoriler", kategori_adi) if kategori_adi else None
                marka_id = self._get_nitelik_id_from_cache("markalar", marka_adi) if marka_adi else None
                urun_grubu_id = self._get_nitelik_id_from_cache("urun_gruplari", urun_grubu_adi) if urun_grubu_adi else None
                birim_id = self._get_nitelik_id_from_cache("urun_birimleri", birim_adi) if birim_adi else None
                mense_id = self._get_nitelik_id_from_cache("ulkeler", ulke_adi) if ulke_adi else None
                
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
        
        logger.info(f"Toplu tedarikci içe aktarım tamamlandı. Başarılı: {basarili_sayisi}, Hata: {hata_sayisi}")
        return {"basarili": basarili_sayisi, "hata": hata_sayisi, "hatalar": hatalar}
        
    def toplu_stok_ice_aktar(self, stok_listesi: List[Dict[str, Any]]):
        """
        Toplu stok ekleme/güncelleme işlemini API'ye gönderir.
        """
        try:
            payload = []
            for stok in stok_listesi:
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
            
            yeni_eklenen_stok_idleri = response_data.get("yeni_eklenen_stok_idleri", [])
            
            fatura_hizmeti = FaturaService(self.db)
            
            if yeni_eklenen_stok_idleri:
                for stok_id in yeni_eklenen_stok_idleri:
                    yeni_stok_data = next((s for s in stok_listesi if s.get('id') == stok_id), None)
                    if yeni_stok_data:
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

class LokalVeritabaniServisi:
    def __init__(self, db_path="onmuhasebe.db"):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def get_db(self):
        db = self.SessionLocal()
        try:
            return db
        finally:
            db.close()
            
    def senkronize_veriler(self, sunucu_adresi: str):
        lokal_db = None
        try:
            lokal_db = self.get_db()

            def _convert_dates(data, date_keys, datetime_keys):
                for key, value in data.items():
                    if isinstance(value, str):
                        if key in date_keys:
                            try:
                                data[key] = datetime.strptime(value, '%Y-%m-%d').date()
                            except (ValueError, TypeError):
                                pass
                        elif key in datetime_keys:
                            try:
                                data[key] = datetime.fromisoformat(value)
                            except (ValueError, TypeError):
                                pass
                return data
            
            # --- API endpoint URL'leri ve ilgili modelleri eşleştirme ---
            endpoints = {
                'stoklar': Stok,
                'musteriler': Musteri,
                'tedarikciler': Tedarikci,
                'kasalar_bankalar': KasaBanka,
                'faturalar': Fatura,
                'siparisler': Siparis,
                'cari_hareketler': CariHareket,
                'nitelikler/kategoriler': UrunKategori,
                'nitelikler/markalar': UrunMarka,
                'nitelikler/urun_gruplari': UrunGrubu,
                'nitelikler/urun_birimleri': UrunBirimi,
                'nitelikler/ulkeler': Ulke,
                'nitelikler/gelir_siniflandirmalari': GelirSiniflandirma,
                'nitelikler/gider_siniflandirmalari': GiderSiniflandirma
            }
            
            # --- Tarih/Zaman alanlarının adlarını tanımlama ---
            date_fields = {
                'faturalar': ['tarih', 'vade_tarihi'],
                'siparisler': ['tarih', 'teslimat_tarihi'],
                'cari_hareketler': ['tarih', 'vade_tarihi']
            }
            datetime_fields = {
                'faturalar': ['olusturma_tarihi_saat', 'son_guncelleme_tarihi_saat'],
                'siparisler': ['olusturma_tarihi_saat', 'son_guncelleme_tarihi_saat'],
                'cari_hareketler': ['olusturma_tarihi_saat']
            }

            for endpoint, model in endpoints.items():
                response = requests.get(f"{sunucu_adresi}/{endpoint}/")
                response.raise_for_status()
                server_data = response.json()["items"]
                
                for item_data in server_data:
                    item_data = _convert_dates(item_data, date_fields.get(endpoint.split('/')[-1], []), datetime_fields.get(endpoint.split('/')[-1], []))
                    
                    existing_item = lokal_db.query(model).filter_by(id=item_data["id"]).first()
                    
                    valid_data = {k: v for k, v in item_data.items() if k in model.__table__.columns.keys()}

                    if existing_item:
                        for key, value in valid_data.items():
                            setattr(existing_item, key, value)
                    else:
                        yeni_item = model(**valid_data)
                        lokal_db.add(yeni_item)
            
            lokal_db.commit()
            print("Veriler başarıyla lokal veritabanına senkronize edildi.")
            return True, "Senkronizasyon başarılı."
        except requests.exceptions.RequestException as e:
            if lokal_db: lokal_db.rollback()
            print(f"Sunucuya bağlanırken hata oluştu: {e}")
            return False, f"Sunucu bağlantı hatası: {e}"
        except Exception as e:
            if lokal_db: lokal_db.rollback()
            print(f"Senkronizasyon hatası: {e}")
            return False, f"Beklenmedik bir hata oluştu: {e}"
        finally:
            if lokal_db: lokal_db.close()
            
lokal_db_servisi = LokalVeritabaniServisi()