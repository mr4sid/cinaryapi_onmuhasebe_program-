# veritabani.py dosyasının tam içeriği
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
    # Sabitler
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
    ODEME_TURU_ETKISIZ_FATURA = "ETKİSİZ FATURA" # Stok hareketini etkilemeyen fatura
    
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
    STOK_ISLEM_TIP_IADE_GIRIS = "İADE_GİRİŞ" # Alış İade Faturası ile
    STOK_ISLEM_TIP_FATURA_ALIS = "FATURA_ALIŞ"
    STOK_ISLEM_TIP_FATURA_SATIS = "FATURA_SATIŞ"

    # Kullanıcı Rolleri
    USER_ROLE_ADMIN = "ADMIN"
    USER_ROLE_MANAGER = "MANAGER"
    USER_ROLE_SALES = "SALES"
    USER_ROLE_USER = "USER"
    
    def __init__(self, api_base_url="http://127.0.0.1:8000"):
        """
        Veritabanı bağlantılarını ve API iletişimini yöneten sınıf.
        Artık doğrudan veritabanı yerine FastAPI API'si ile iletişim kurar.
        """
        self.api_base_url = api_base_url
        logger.info(f"OnMuhasebe başlatıldı. API Base URL: {self.api_base_url}")

    def kullanici_dogrula(self, kullanici_adi, sifre):
        """Kullanıcıyı API üzerinden doğrular."""
        try:
            # API'de '/dogrulama/login' gibi bir endpoint olduğunu varsayıyoruz
            data = {"username": kullanici_adi, "password": sifre}
            response = self._make_api_request("POST", "/dogrulama/login", data=data) # '/auth/login' yerine '/dogrulama/login'
            # API'nin başarılı girişte kullanıcı objesini döndürdüğünü varsayıyoruz
            return response
        except ValueError as e: # API'den 401 Unauthorized gibi hatalar ValueError olarak gelebilir
            logger.warning(f"Kullanıcı doğrulama hatası: {e}")
            return None
        except Exception as e:
            logger.error(f"Kullanıcı doğrulama sırasında beklenmeyen hata: {e}")
            return None

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

# Dashboard ve Rapor Özet Bilgileri
    def get_dashboard_summary(self, baslangic_tarihi=None, bitis_tarihi=None):
        """
        Dashboard için özet finansal metrikleri (toplam satış, tahsilat, ödeme, kritik stok,
        ayın en çok satan ürünü, vadesi geçmiş alacak/borç) API'den çeker.
        """
        params = {
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi
        }
        params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/raporlar/dashboard_ozet", params=params)

    def get_sales_by_payment_type(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Ödeme türlerine göre satış dağılımını API'den çeker."""
        params = {
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi
        }
        params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/raporlar/satislar/odeme_turune_gore", params=params)

    def get_top_selling_products(self, baslangic_tarihi=None, bitis_tarihi=None, limit=5):
        """En çok satan ürünleri API'den çeker."""
        params = {
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi,
            "limit": limit
        }
        params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/raporlar/stoklar/en_cok_satanlar", params=params)

    def get_critical_stock_items(self):
        """Kritik stok seviyesinin altındaki ürünleri API'den çeker."""
        return self._make_api_request("GET", "/raporlar/stoklar/kritik_stoklar")

    def get_cari_total_receivables_payables(self, cari_tipi=None):
        """
        Müşterilerin toplam alacaklarını veya tedarikçilerin toplam borçlarını API'den çeker.
        """
        params = {"cari_tipi": cari_tipi} if cari_tipi is not None else None
        return self._make_api_request("GET", "/raporlar/cariler/toplam_bakiye", params=params)

    def get_total_sales(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Belirli bir tarih aralığındaki toplam satış tutarını API'den çeker."""
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_api_request("GET", "/raporlar/satislar/toplam_tutar", params=params)
        return response.get("toplam_satis_tutari", 0.0)

    def get_total_collections(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Belirli bir tarih aralığındaki toplam tahsilat tutarını API'den çeker."""
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_api_request("GET", "/raporlar/tahsilatlar/toplam_tutar", params=params)
        return response.get("toplam_tahsilat_tutari", 0.0)

    def get_total_payments(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Belirli bir tarih aralığındaki toplam ödeme tutarını API'den çeker."""
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_api_request("GET", "/raporlar/odemeler/toplam_tutar", params=params)
        return response.get("toplam_odeme_tutari", 0.0)

    def get_kar_zarar_verileri(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Belirli bir tarih aralığındaki toplam gelir ve gider tutarlarını API'den çeker."""
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_api_request("GET", "/raporlar/gelir_gider/toplamlar", params=params)
        return response.get("toplam_gelir", 0.0), response.get("toplam_gider", 0.0)

    def get_monthly_sales_summary(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Aylık satış özetini API'den çeker."""
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/raporlar/satislar/aylik_ozet", params=params)

    def get_monthly_income_expense_summary(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Aylık gelir-gider özetini API'den çeker."""
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/raporlar/gelir_gider/aylik_ozet", params=params)

    def tarihsel_satis_raporu_verilerini_al(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Detaylı tarihsel satış raporu verilerini API'den çeker."""
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/raporlar/satislar/detayli_rapor", params=params)

    def get_gross_profit_and_cost(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Brüt kar ve maliyet bilgilerini API'den çeker."""
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_api_request("GET", "/raporlar/kar_zarar/brut_kar", params=params)
        return response.get("brut_kar", 0.0), response.get("maliyet", 0.0), response.get("brut_kar_orani", 0.0)

    def get_monthly_gross_profit_summary(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Aylık brüt kar özetini API'den çeker."""
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/raporlar/kar_zarar/aylik_ozet", params=params)

    def get_nakit_akis_verileri(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Nakit akışı detay verilerini API'den çeker."""
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/raporlar/nakit_akis/detayli_rapor", params=params)

    def get_monthly_cash_flow_summary(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Aylık nakit akışı özetini API'den çeker."""
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/raporlar/nakit_akis/aylik_ozet", params=params)

    def get_tum_kasa_banka_bakiyeleri(self):
        """Tüm kasa/banka hesaplarının güncel bakiyelerini API'den çeker."""
        return self._make_api_request("GET", "/raporlar/kasalar_bankalar/toplam_bakiyeler")

    def get_cari_yaslandirma_verileri(self, tarih=None):
        """Cari yaşlandırma raporu verilerini API'den çeker."""
        params = {"tarih": tarih} if tarih is not None else None
        return self._make_api_request("GET", "/raporlar/cariler/yaslandirma", params=params)

    def get_stock_value_by_category(self):
        """Kategoriye göre toplam stok değerini API'den çeker."""
        return self._make_api_request("GET", "/raporlar/stoklar/kategoriye_gore_deger")

    # Sistem ve Varsayılanlar
    def get_perakende_musteri_id(self):
        """Perakende müşteri ID'sini API'den veya yapılandırmadan çeker."""
        try:
            response = self._make_api_request("GET", "/sistem/varsayilan_cariler/perakende_musteri_id")
            return response.get("id")
        except Exception as e:
            logger.warning(f"Varsayılan perakende müşteri ID'si API'den alınamadı: {e}. None dönülüyor.")
            return None

    def get_genel_tedarikci_id(self):
        """Genel tedarikçi ID'sini API'den veya yapılandırmadan çeker."""
        try:
            response = self._make_api_request("GET", "/sistem/varsayilan_cariler/genel_tedarikci_id")
            return response.get("id")
        except Exception as e:
            logger.warning(f"Varsayılan genel tedarikçi ID'si API'den alınamadı: {e}. None dönülüyor.")
            return None

    def get_kasa_banka_by_odeme_turu(self, odeme_turu):
        """
        Ödeme türüne göre varsayılan kasa/banka hesabını API'den çeker.
        """
        try:
            response = self._make_api_request("GET", f"/sistem/varsayilan_kasa_banka/{odeme_turu}")
            return response # API'den doğrudan hesap objesi dönsün
        except Exception as e:
            logger.warning(f"Varsayılan kasa/banka hesabı API'den alınamadı ({odeme_turu}): {e}")
            return None

    def son_fatura_no_getir(self, fatura_tipi):
        """Belirtilen fatura tipi için son fatura numarasını API'den çeker ve bir sonraki numarayı oluşturur."""
        params = {"fatura_tipi": fatura_tipi}
        response = self._make_api_request("GET", f"/sistem/next_fatura_number/{fatura_tipi}", method="GET") 
        return response.get("next_no", "0000000001")

    def get_stok_miktari_for_kontrol(self, urun_id, fatura_id_or_siparis_id=None):
        """
        Belirli bir ürünün anlık stok miktarını API'den çeker.
        Fatura/sipariş düzenleme modundaysa, o faturadaki/siparişteki ilgili kalem miktarını hesaba katar.
        """
        params = {
            "urun_id": urun_id,
            "fatura_id_or_siparis_id": fatura_id_or_siparis_id
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_api_request("GET", "/stoklar/anlik_stok_miktari", params=params)
        return response.get("stok_miktari", 0.0)

    def get_faturalar_by_urun_id(self, urun_id, fatura_tipi=None):
        """Belirli bir ürüne ait faturaları API'den çeker."""
        params = {
            "urun_id": urun_id,
            "fatura_tipi": fatura_tipi
        }
        params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/faturalar/urun_faturalari", params=params)

    def stok_hareketleri_listele(self, urun_id, islem_tipi=None, baslangic_tarihi=None, bitis_tarihi=None):
        """Belirli bir ürünün stok hareketlerini API'den çeker."""
        params = {
            "urun_id": urun_id,
            "islem_tipi": islem_tipi,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi
        }
        params = {k: v for k, v in params.items() if v is not None}
        return self._make_api_request("GET", "/stoklar/hareketler", params=params)

    def kategori_ekle(self, kategori_adi):
        """Yeni kategori ekler (API üzerinden)."""
        data = {"kategori_adi": kategori_adi}
        return self._make_api_request("POST", "/nitelikler/kategoriler", data=data)

    def kategori_guncelle(self, kategori_id, yeni_kategori_adi):
        """Kategori günceller (API üzerinden)."""
        data = {"id": kategori_id, "kategori_adi": yeni_kategori_adi}
        return self._make_api_request("PUT", f"/nitelikler/kategoriler/{kategori_id}", data=data)

    def kategori_sil(self, kategori_id):
        """Kategori siler (API üzerinden)."""
        return self._make_api_request("DELETE", f"/nitelikler/kategoriler/{kategori_id}")

    def kategori_listele(self):
        """Kategori listesini API'den çeker."""
        return self._make_api_request("GET", "/nitelikler/kategoriler")

    def marka_ekle(self, marka_adi):
        """Yeni marka ekler (API üzerinden)."""
        data = {"marka_adi": marka_adi}
        return self._make_api_request("POST", "/nitelikler/markalar", data=data)

    def marka_guncelle(self, marka_id, yeni_marka_adi):
        """Marka günceller (API üzerinden)."""
        data = {"id": marka_id, "marka_adi": yeni_marka_adi}
        return self._make_api_request("PUT", f"/nitelikler/markalar/{marka_id}", data=data)

    def marka_sil(self, marka_id):
        """Marka siler (API üzerinden)."""
        return self._make_api_request("DELETE", f"/nitelikler/markalar/{marka_id}")

    def marka_listele(self):
        """Marka listesini API'den çeker."""
        return self._make_api_request("GET", "/nitelikler/markalar")

    def urun_grubu_ekle(self, grup_adi):
        """Yeni ürün grubu ekler (API üzerinden)."""
        data = {"grup_adi": grup_adi}
        return self._make_api_request("POST", "/nitelikler/urun_gruplari", data=data)

    def urun_grubu_guncelle(self, grup_id, yeni_grup_adi):
        """Ürün grubu günceller (API üzerinden)."""
        data = {"id": grup_id, "grup_adi": yeni_grup_adi}
        return self._make_api_request("PUT", f"/nitelikler/urun_gruplari/{grup_id}", data=data)

    def urun_grubu_sil(self, grup_id):
        """Ürün grubu siler (API üzerinden)."""
        return self._make_api_request("DELETE", f"/nitelikler/urun_gruplari/{grup_id}")

    def urun_grubu_listele(self):
        """Ürün grubu listesini API'den çeker."""
        return self._make_api_request("GET", "/nitelikler/urun_gruplari")

    def urun_birimi_ekle(self, birim_adi):
        """Yeni ürün birimi ekler (API üzerinden)."""
        data = {"birim_adi": birim_adi}
        return self._make_api_request("POST", "/nitelikler/urun_birimleri", data=data)

    def urun_birimi_guncelle(self, birim_id, yeni_birim_adi):
        """Ürün birimi günceller (API üzerinden)."""
        data = {"id": birim_id, "birim_adi": yeni_birim_adi}
        return self._make_api_request("PUT", f"/nitelikler/urun_birimleri/{birim_id}", data=data)

    def urun_birimi_sil(self, birim_id):
        """Ürün birimi siler (API üzerinden)."""
        return self._make_api_request("DELETE", f"/nitelikler/urun_birimleri/{birim_id}")

    def urun_birimi_listele(self):
        """Ürün birimi listesini API'den çeker."""
        return self._make_api_request("GET", "/nitelikler/urun_birimleri")

    def ulke_ekle(self, ulke_adi):
        """Yeni ülke ekler (API üzerinden)."""
        data = {"ulke_adi": ulke_adi}
        return self._make_api_request("POST", "/nitelikler/ulkeler", data=data)

    def ulke_guncelle(self, ulke_id, yeni_ulke_adi):
        """Ülke günceller (API üzerinden)."""
        data = {"id": ulke_id, "ulke_adi": yeni_ulke_adi}
        return self._make_api_request("PUT", f"/nitelikler/ulkeler/{ulke_id}", data=data)

    def ulke_sil(self, ulke_id):
        """Ülke siler (API üzerinden)."""
        return self._make_api_request("DELETE", f"/nitelikler/ulkeler/{ulke_id}")

    def ulke_listele(self):
        """Ülke listesini API'den çeker."""
        return self._make_api_request("GET", "/nitelikler/ulkeler")

    def tedarikci_getir_by_id(self, tedarikci_id):
        """Belirtilen ID'ye sahip tedarikçiyi getirir."""
        return self._make_api_request("GET", f"/tedarikciler/{tedarikci_id}")

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
        Veritabanı yedekleme işlemini API üzerinden başlatır.
        API'nin yedekleme dosyasını bir konumda oluşturması veya geri döndürmesi beklenir.
        """
        try:
            # API'de '/backup' gibi bir endpoint olduğunu varsayıyoruz.
            # API tarafında backup_path'i parametre olarak alıp işlemi yapması gerekecek.
            # Ancak güvenlik nedeniyle doğrudan istemciden dosya yolu göndermek yerine,
            # sunucu tarafında bir varsayılan konuma yedekleme yapılmalı
            # veya sadece yedekleme işlemini tetikleyen bir çağrı olmalıdır.
            # Bu örnekte sadece tetikleme yapalım.
            response = self._make_api_request("POST", "/system/backup")
            logger.info(f"Veritabanı yedekleme API'den başarıyla tetiklendi: {response.get('message', 'Mesaj yok')}")
            return True, response.get('message', 'Yedekleme isteği başarıyla gönderildi.')
        except Exception as e:
            logger.error(f"API üzerinden yedekleme başlatılırken hata: {e}")
            return False, f"Yedekleme başlatılırken hata oluştu: {e}"

    def database_restore(self, restore_path):
        """
        Veritabanı geri yükleme işlemini API üzerinden başlatır.
        API'nin yüklenen dosyayı kullanarak veritabanını geri yüklemesi beklenir.
        """
        try:
            # API'de '/system/restore' gibi bir endpoint olduğunu varsayıyoruz
            # ve bu endpoint'in bir dosya alması bekleniyor.
            # requests kütüphanesi 'files' parametresini destekler.
            with open(restore_path, 'rb') as f:
                files = {'file': (os.path.basename(restore_path), f, 'application/octet-stream')}
                response = requests.post(f"{self.api_base_url}/system/restore", files=files)
                response.raise_for_status() # HTTP hataları için istisna fırlatır
                logger.info(f"Veritabanı geri yükleme API'den başarıyla tetiklendi: {response.json().get('message', 'Mesaj yok')}")
                return True, response.json().get('message', 'Geri yükleme isteği başarıyla gönderildi.')
        except requests.exceptions.ConnectionError as e:
            logger.error(f"API'ye bağlanılamadı: {self.api_base_url}/system/restore. Hata: {e}")
            return False, f"API'ye bağlanılamadı. Sunucunun çalıştığından emin olun."
        except requests.exceptions.HTTPError as e:
            try:
                error_detail = response.json().get("detail", "Bilinmeyen API hatası.")
            except json.JSONDecodeError:
                error_detail = response.text
            logger.error(f"API HTTP hatası: {self.api_base_url}/system/restore, Durum Kodu: {response.status_code}, Yanıt: {error_detail}. Hata: {e}")
            return False, f"API hatası ({response.status_code}): {error_detail}"
        except FileNotFoundError as e:
            logger.error(f"Yedekleme dosyası bulunamadı: {restore_path}. Hata: {e}")
            return False, f"Yedekleme dosyası bulunamadı: {restore_path}"
        except Exception as e:
            logger.critical(f"Beklenmedik bir hata oluştu: {e}")
            return False, f"Geri yükleme sırasında beklenmeyen bir hata oluştu: {e}"

    def create_tables(self, cursor=None):
        """
        Bu fonksiyon artık doğrudan masaüstü uygulamasında tablo oluşturmaz.
        Tabloların API başlatıldığında veya create_pg_tables.py scripti ile oluşturulması beklenir.
        """
        logger.info("create_tables çağrıldı ancak artık veritabanı doğrudan yönetilmiyor. Tabloların API veya create_pg_tables.py aracılığıyla oluşturulduğu varsayılıyor.")
        pass # Masaüstü uygulamasının bu fonksiyonu çağırması gerekiyorsa boş bırakılabilir veya kaldırılabilir.
