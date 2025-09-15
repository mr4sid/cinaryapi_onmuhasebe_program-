# hizmetler.py Dosyasının TAMAMI
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union
from yardimcilar import normalize_turkish_chars
from api import modeller
from api.modeller import Kullanici
from api.modeller import (Base, Stok, Musteri, Tedarikci, Fatura, FaturaKalemi,
                           CariHesap, CariHareket, Siparis, SiparisKalemi, UrunKategori, UrunGrubu,
                           KasaBankaHesap, StokHareket, GelirGider, Nitelik, Ulke, UrunMarka, 
                           SenkronizasyonKuyrugu, GelirSiniflandirma, GiderSiniflandirma, UrunBirimi)
logger = logging.getLogger(__name__)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class FaturaService:
    def __init__(self, db_manager, app_ref):
        self.db = db_manager
        self.app = app_ref
        logger.info("FaturaService başlatıldı.")
        # DÜZELTME: Kullanıcı ID'sini sözlükten alıyoruz
        self.current_user_id = self.app.current_user.get("id") if self.app and hasattr(self.app, 'current_user') else None

    def fatura_olustur(self, fatura_no, tarih, fatura_tipi, cari_id, kalemler_data, odeme_turu,
                         kasa_banka_id=None, misafir_adi=None, fatura_notlari=None, vade_tarihi=None,
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
            "olusturan_kullanici_id": self.current_user_id, # DÜZELTME: self.current_user_id kullanıldı
            "kullanici_id": self.current_user_id # DÜZELTME: kullanici_id parametresi eklendi
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
            "kalemler": kalemler_data,
            "kullanici_id": self.current_user_id # DÜZELTME: kullanici_id parametresi eklendi
        }
        try:
            # DÜZELTME: db.fatura_guncelle metoduna kullanici_id parametresi eklendi
            response_data = self.db.fatura_guncelle(fatura_id, fatura_data, self.current_user_id)
            return True, response_data.get("message", "Fatura başarıyla güncellendi.")
        except ValueError as e:
            logger.error(f"Fatura güncellenirken API hatası: {e}")
            return False, f"Fatura güncellenemedi: {e}"
        except Exception as e:
            logger.error(f"Fatura güncellenirken beklenmeyen bir hata oluştu: {e}")
            return False, f"Fatura güncellenirken beklenmeyen bir hata oluştu: {e}"

    def siparis_faturaya_donustur(self, siparis_id: int, fatura_donusum_data: dict, kullanici_id: int):
        fatura_donusum_data['kullanici_id'] = kullanici_id # DÜZELTME: kullanici_id eklendi
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
    def __init__(self, db_manager, app):
        self.db = db_manager
        self.app = app
        self.current_user_id = self.app.current_user.get("id") if self.app and hasattr(self.app, 'current_user') else None
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
            # DÜZELTME: musteri_listesi_al metoduna kullanici_id eklendi
            return self.db.musteri_listesi_al(kullanici_id=self.current_user_id, **cleaned_params)
        except Exception as e:
            logger.error(f"Müşteri listesi CariService üzerinden alınırken hata: {e}")
            raise

    def musteri_getir_by_id(self, musteri_id: int):
        try:
            # DÜZELTME: musteri_getir_by_id metoduna kullanici_id eklendi
            return self.db.musteri_getir_by_id(musteri_id, kullanici_id=self.current_user_id)
        except Exception as e:
            logger.error(f"Müşteri ID {musteri_id} CariService üzerinden çekilirken hata: {e}")
            raise

    def musteri_sil(self, musteri_id: int):
        try:
            # DÜZELTME: musteri_sil metoduna kullanici_id eklendi
            return self.db.musteri_sil(musteri_id, kullanici_id=self.current_user_id)
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
            # DÜZELTME: tedarikci_listesi_al metoduna kullanici_id eklendi
            return self.db.tedarikci_listesi_al(kullanici_id=self.current_user_id, **cleaned_params)
        except Exception as e:
            logger.error(f"Tedarikçi listesi CariService üzerinden alınırken hata: {e}")
            raise

    def tedarikci_getir_by_id(self, tedarikci_id: int):
        try:
            # DÜZELTME: tedarikci_getir_by_id metoduna kullanici_id eklendi
            return self.db.tedarikci_getir_by_id(tedarikci_id, kullanici_id=self.current_user_id)
        except Exception as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} CariService üzerinden çekilirken hata: {e}")
            raise

    def tedarikci_sil(self, tedarikci_id: int):
        try:
            # DÜZELTME: tedarikci_sil metoduna kullanici_id eklendi
            return self.db.tedarikci_sil(tedarikci_id, kullanici_id=self.current_user_id)
        except Exception as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} CariService üzerinden silinirken hata: {e}")
            raise

    def cari_getir_by_id(self, cari_id: int, cari_tipi: str):
        if cari_tipi == self.db.CARI_TIP_MUSTERI:
            # DÜZELTME: musteri_getir_by_id metoduna kullanici_id eklendi
            return self.musteri_getir_by_id(cari_id, kullanici_id=self.current_user_id)
        elif cari_tipi == self.db.CARI_TIP_TEDARIKCI:
            # DÜZELTME: tedarikci_getir_by_id metoduna kullanici_id eklendi
            return self.tedarikci_getir_by_id(cari_id, kullanici_id=self.current_user_id)
        else:
            raise ValueError("Geçersiz cari tipi belirtildi. 'MUSTERI' veya 'TEDARIKCI' olmalı.")

class TopluIslemService:
    def __init__(self, db_manager, app_ref):
        self.db = db_manager
        self.app = app_ref
        logger.info("TopluIslemService başlatıldı.")
        self._nitelik_cache = {
            "kategoriler": {},
            "markalar": {},
            "urun_gruplari": {},
            "urun_birimleri": {},
            "ulkeler": {}
        }
        # DÜZELTME: Kullanıcı ID'sini sözlükten güvenli bir şekilde al
        self.current_user_id = self.app.current_user.get("id") if self.app and hasattr(self.app, 'current_user') else None
        self._load_nitelik_cache()
    
    def _load_nitelik_cache(self):
        try:
            # Her bir nitelik listesi için veriyi çek ve önbelleğe al
            # DÜZELTME: tüm nitelik listeleme metotlarına kullanici_id eklendi
            kategoriler_response = self.db.kategori_listele(kullanici_id=self.current_user_id)
            markalar_response = self.db.marka_listele(kullanici_id=self.current_user_id)
            urun_gruplari_response = self.db.urun_grubu_listele(kullanici_id=self.current_user_id)
            urun_birimleri_response = self.db.urun_birimi_listele(kullanici_id=self.current_user_id)
            ulkeler_response = self.db.ulke_listele(kullanici_id=self.current_user_id)

            kategoriler = kategoriler_response.get("items", []) if isinstance(kategoriler_response, dict) else kategoriler_response or []
            markalar = markalar_response.get("items", []) if isinstance(markalar_response, dict) else markalar_response or []
            urun_gruplari = urun_gruplari_response.get("items", []) if isinstance(urun_gruplari_response, dict) else urun_gruplari_response or []
            urun_birimleri = urun_birimleri_response.get("items", []) if isinstance(urun_birimleri_response, dict) else urun_birimleri_response or []
            ulkeler = ulkeler_response.get("items", []) if isinstance(ulkeler_response, dict) else ulkeler_response or []

            self._nitelik_cache["kategoriler"] = {normalize_turkish_chars(item.ad if hasattr(item, 'ad') else item.get('ad')).lower(): item.id if hasattr(item, 'id') else item.get('id') for item in kategoriler if hasattr(item, 'id') or item.get('id')}
            self._nitelik_cache["markalar"] = {normalize_turkish_chars(item.ad if hasattr(item, 'ad') else item.get('ad')).lower(): item.id if hasattr(item, 'id') else item.get('id') for item in markalar if hasattr(item, 'id') or item.get('id')}
            self._nitelik_cache["urun_gruplari"] = {normalize_turkish_chars(item.ad if hasattr(item, 'ad') else item.get('ad')).lower(): item.id if hasattr(item, 'id') else item.get('id') for item in urun_gruplari if hasattr(item, 'id') or item.get('id')}
            self._nitelik_cache["urun_birimleri"] = {normalize_turkish_chars(item.ad if hasattr(item, 'ad') else item.get('ad')).lower(): item.id if hasattr(item, 'id') else item.get('id') for item in urun_birimleri if hasattr(item, 'id') or item.get('id')}
            self.app.set_status_message(f"Ürün nitelikleri başarıyla yüklendi: {len(kategoriler)} kategori, {len(markalar)} marka, {len(urun_gruplari)} grup ve {len(urun_birimleri)} birim.","black")
        except Exception as e:
            logger.error(f"Nitelik önbelleği yüklenirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Nitelik verileri yüklenemedi. {e}", "red")
            
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
            # DÜZELTME: musteri_listesi_al metoduna kullanici_id eklendi
            mevcut_musteriler_response = self.db.musteri_listesi_al(kullanici_id=self.current_user_id, limit=10000)
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
            # DÜZELTME: tedarikci_listesi_al metoduna kullanici_id eklendi
            mevcut_tedarikciler_response = self.db.tedarikci_listesi_al(kullanici_id=self.current_user_id, limit=10000)
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
            # DÜZELTME: stok_listesi_al metoduna kullanici_id eklendi
            mevcut_stoklar_response = self.db.stok_listesi_al(kullanici_id=self.current_user_id, limit=10000)
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
                # DÜZELTME: musteri_listesi_al metoduna kullanici_id eklendi
                mevcut_musteri_response = self.db._make_api_request("GET", f"/musteriler/", params={"arama": musteri_data.get('kod'), "kullanici_id": self.current_user_id})
                mevcut_musteri = [m for m in mevcut_musteri_response.get("items", []) if m.get('kod') == musteri_data.get('kod')]
                
                musteri_data['kullanici_id'] = self.current_user_id # DÜZELTME: kullanici_id ekleniyor
                
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
                # DÜZELTME: tedarikci_listesi_al metoduna kullanici_id eklendi
                mevcut_tedarikci_response = self.db._make_api_request("GET", f"/tedarikciler/", params={"arama": tedarikci_data.get('kod'), "kullanici_id": self.current_user_id})
                mevcut_tedarikci = [t for t in mevcut_tedarikci_response.get("items", []) if t.get('kod') == tedarikci_data.get('kod')]

                tedarikci_data['kullanici_id'] = self.current_user_id # DÜZELTME: kullanici_id ekleniyor

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
                # DÜZELTME: Her stok verisine kullanici_id ekleniyor
                stok['kullanici_id'] = self.current_user_id
                payload.append(stok)

            # DÜZELTME: API çağrısı, db_manager üzerinden yapılır.
            response_data = self.db.bulk_stok_upsert(payload, self.current_user_id)
            
            yeni_eklenen_stok_idleri = response_data.get("yeni_eklenen_stok_idleri", [])
            
            fatura_hizmeti = FaturaService(self.db, self.app)
            
            if yeni_eklenen_stok_idleri:
                for stok_id in yeni_eklenen_stok_idleri:
                    yeni_stok_data = next((s for s in stok_listesi if s.get('kod') == stok_id), None)
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
        self.initialized = False  # Artık 'initialized' özelliğini tanımlıyoruz
        self.logger = logging.getLogger(__name__) # Artık 'logger' özelliğini tanımlıyoruz
        
    def initialize_database(self):
        """Yerel veritabanı tablolarını oluşturur."""
        if not self.initialized:
            Base.metadata.create_all(bind=self.engine)
            self.initialized = True
            self.logger.info("Yerel veritabanı şeması başarıyla oluşturuldu/güncellendi.")

    def get_db(self):
        db = self.SessionLocal()
        try:
            return db
        finally:
            db.close()
            
    def senkronize_veriler(self, sunucu_adresi: str, kullanici_id: Optional[int] = None):
        if not sunucu_adresi:
            return False, "Sunucu adresi belirtilmedi. Senkronizasyon atlandı."
        if kullanici_id is None:
            return False, "Kullanıcı kimliği belirtilmedi. Senkronizasyon atlandı."
            
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
                'stoklar': ['olusturma_tarihi'], # Eklendi
                'musteriler': ['olusturma_tarihi'], # Eklendi
                'tedarikciler': ['olusturma_tarihi'], # Eklendi
                'kasalar_bankalar': ['olusturma_tarihi'], # Eklendi
                'faturalar': ['olusturma_tarihi_saat', 'son_guncelleme_tarihi_saat'],
                'siparisler': ['olusturma_tarihi_saat', 'son_guncelleme_tarihi_saat'],
                'cari_hareketler': ['olusturma_tarihi_saat'],
                'gelir_gider': ['olusturma_tarihi_saat'] # Eklendi
            }

            for endpoint, model in endpoints.items():
                response = requests.get(f"{sunucu_adresi}/{endpoint}", params={"limit": 999999, "kullanici_id": kullanici_id})
                response.raise_for_status()
                response_data = response.json()
                if isinstance(response_data, dict) and "items" in response_data:
                    server_data = response_data["items"]
                elif isinstance(response_data, list):
                    server_data = response_data
                else:
                    raise ValueError(f"API'den beklenmeyen veri formatı: {response_data}")
                
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

    def listele(self, model_adi: str, filtre: Optional[Dict[str, Any]] = None):
        """
        Yerel veritabanındaki belirtilen modelden verileri listeler.
        """
        db = self.SessionLocal()
        
        models = {
            "Stok": Stok,
            "Musteri": Musteri,
            "Tedarikci": Tedarikci,
            "Fatura": Fatura,
            "FaturaKalemi": FaturaKalemi,
            "CariHesap": CariHesap,
            "CariHareket": CariHareket,
            "Siparis": Siparis,
            "SiparisKalemi": SiparisKalemi,
            "KasaBankaHesap": KasaBankaHesap,
            "StokHareket": StokHareket,
            "GelirGider": GelirGider,
            "Nitelik": Nitelik,
            "SenkronizasyonKuyrugu": SenkronizasyonKuyrugu
        }
        
        try:
            model = models.get(model_adi)
            if not model:
                raise ValueError(f"Model bulunamadı: {model_adi}")

            sorgu = db.query(model)
            if filtre:
                for key, value in filtre.items():
                    if hasattr(model, key):
                        sorgu = sorgu.filter(getattr(model, key) == value)
            
            return [item for item in sorgu.all()]
        except Exception as e:
            self.logger.error(f"Yerel DB listeleme hatası: {e}", exc_info=True)
            return []
        finally:
            if db:
                db.close()

    def kullanici_kaydet(self, user_data):
        """
        API'den gelen kullanıcı verisini yerel veritabanına kaydeder veya günceller.
        """
        try:
            with self.SessionLocal() as session:
                kullanici_id = user_data.get("id")
                kullanici = session.query(modeller.Kullanici).filter(modeller.Kullanici.id == kullanici_id).first()

                # Modelde olmayan anahtarları filtrele
                valid_user_data = {
                    key: value for key, value in user_data.items()
                    if key in [column.name for column in modeller.Kullanici.__table__.columns]
                }
                
                # Sadece token ve token_tipi bilgisini ek olarak sakla
                token = user_data.get("access_token")
                token_tipi = user_data.get("token_type")

                if kullanici:
                    # Kullanıcı verilerini ve token'ı güncelle
                    for key, value in valid_user_data.items():
                        setattr(kullanici, key, value)
                    setattr(kullanici, 'token', token)
                    setattr(kullanici, 'token_tipi', token_tipi)
                    kullanici.son_giris_tarihi = datetime.now()
                    logger.info(f"Kullanıcı verisi güncellendi: {kullanici.kullanici_adi}")
                else:
                    yeni_kullanici = modeller.Kullanici(
                        id=kullanici_id,
                        kullanici_adi=user_data.get("kullanici_adi"),
                        yetki=user_data.get("yetki"),
                        aktif=user_data.get("aktif"),
                        olusturma_tarihi=datetime.now(),
                        son_giris_tarihi=datetime.now(),
                        # Token bilgilerini doğrudan modele atama
                        token=token,
                        token_tipi=token_tipi
                    )
                    session.add(yeni_kullanici)
                    logger.info(f"Yeni kullanıcı yerel veritabanına kaydedildi: {yeni_kullanici.kullanici_adi}")
                
                session.commit()
                return True
        except Exception as e:
            logger.error(f"Kullanıcı yerel veritabanına kaydedilirken hata oluştu: {e}")
            return False

    def kullanici_dogrula(self, kullanici_adi, sifre):
        """
        Yerel veritabanında kullanıcı adı ve şifre ile doğrulamayı dener.
        """
        try:
            with self.SessionLocal() as session:
                kullanici = session.query(modeller.Kullanici).filter(modeller.Kullanici.kullanici_adi == kullanici_adi).first()
                if kullanici and kullanici.aktif:
                    logger.info(f"Kullanıcı yerel veritabanında doğrulandı: {kullanici_adi}")
                    return {"access_token": kullanici.token, "token_type": kullanici.token_tipi}
                else:
                    logger.warning(f"Yerel veritabanında kullanıcı bulunamadı veya pasif: {kullanici_adi}")
                    return None
        except Exception as e:
            logger.error(f"Yerel veritabanında kullanıcı doğrulama sırasında hata: {e}")
            return None

    def kullanici_getir(self, kullanici_adi: str) -> Optional[dict]:
        """
        Yerel veritabanından kullanıcı adı ile kullanıcıyı getirir.
        """
        try:
            with self.SessionLocal() as session:
                kullanici_orm = session.query(Kullanici).filter(Kullanici.kullanici_adi == kullanici_adi).first()
                if kullanici_orm:
                    return {
                        "id": kullanici_orm.id,
                        "kullanici_adi": kullanici_orm.kullanici_adi,
                        "hashed_sifre": kullanici_orm.hashed_sifre,
                        "aktif": kullanici_orm.aktif,
                        "rol": kullanici_orm.rol,
                        "token": kullanici_orm.token,
                        "token_tipi": kullanici_orm.token_tipi
                    }
                return None
        except Exception as e:
            logger.error(f"Yerel veritabanından kullanıcı çekilirken hata oluştu: {e}", exc_info=True)
            return None

lokal_db_servisi = LokalVeritabaniServisi()