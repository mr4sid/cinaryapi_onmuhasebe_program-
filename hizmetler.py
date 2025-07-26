import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class FaturaService:
    def __init__(self, db_manager):
        """
        Fatura ile ilgili iş mantığını yöneten servis sınıfı.
        db_manager artık API ile iletişim kurar.
        """
        self.db = db_manager
        logger.info("FaturaService başlatıldı.")

    def fatura_olustur(self, fatura_bilgileri):
        """
        Yeni bir fatura oluşturur ve veritabanına kaydeder.
        API'nin beklediği formatta veri gönderildiğinden emin olunmalıdır.
        """
        try:
            # Fatura bilgilerini API'nin beklediği formata dönüştürün
            # Örneğin, tarih formatı, kalemlerin yapısı vb.
            # Şu anki API şemasına göre doğrudan fatura_bilgileri gönderiliyor.
            # Eğer fatura_bilgileri içinde fatura_kalemleri varsa, API'nin bunu doğru işlemesi gerekir.

            response = self.db.fatura_ekle(fatura_bilgileri)
            logger.info(f"Fatura başarıyla oluşturuldu: {response.get('id')}")
            return response
        except Exception as e:
            logger.error(f"Fatura oluşturulurken hata: {e}")
            raise

    def siparis_faturaya_donustur(self, siparis_id, olusturan_kullanici_id, odeme_turu, kasa_banka_id, vade_tarihi=None):
        """
        Belirli bir siparişi alıp bir faturaya dönüştürür.
        Bu işlem, siparişin kalemlerini fatura kalemlerine dönüştürmeyi,
        gerekirse stokları güncellemeyi ve cari hareketleri oluşturmayı içerir.
        """
        try:
            # Sipariş detaylarını çek
            siparis_detay = self.db.siparis_getir_by_id(siparis_id)
            if not siparis_detay:
                raise ValueError(f"Sipariş ID {siparis_id} bulunamadı.")

            # Sipariş kalemlerini çek
            siparis_kalemleri = self.db.siparis_kalemleri_al(siparis_id)
            if not siparis_kalemleri:
                raise ValueError(f"Sipariş ID {siparis_id} için kalem bulunamadı.")

            # Fatura Numarasını al
            fatura_turu = self.db.FATURA_TIP_SATIS if siparis_detay['cari_tip'] == self.db.CARI_TIP_MUSTERI else self.db.FATURA_TIP_ALIS
            fatura_no = self.db.son_fatura_no_getir(fatura_turu)
            if fatura_no == "HATA":
                raise ValueError("Yeni fatura numarası alınamadı.")

            # Fatura kalemlerini hazırla
            fatura_kalemleri_data = []
            for s_kalem in siparis_kalemleri:
                urun_info = self.db.stok_getir_by_id(s_kalem['urun_id'])
                if not urun_info:
                    logger.warning(f"Ürün ID {s_kalem['urun_id']} bulunamadı, bu kalem atlanıyor.")
                    continue

                # API'ye gönderilecek fatura kalemi formatına dönüştür
                # NOT: Bu kısım API'deki FaturaKalemiCreate modeline uygun olmalıdır.
                fatura_kalemleri_data.append({
                    "urun_id": s_kalem['urun_id'],
                    "miktar": s_kalem['miktar'],
                    "birim_fiyat": s_kalem['birim_fiyat'], # iskontosuz kdv hariç birim fiyat
                    "kdv_orani": s_kalem['kdv_orani'],
                    "alis_fiyati_fatura_aninda": urun_info.get('alis_fiyati', 0.0), # Stoktan güncel alış fiyatı alınır
                    "iskonto_yuzde_1": s_kalem.get('iskonto_yuzde_1', 0.0),
                    "iskonto_yuzde_2": s_kalem.get('iskonto_yuzde_2', 0.0),
                    "iskonto_tipi": s_kalem.get('iskonto_tipi', "YOK"),
                    "iskonto_degeri": s_kalem.get('iskonto_degeri', 0.0)
                })

            # Fatura ana bilgilerini hazırla
            fatura_data = {
                "fatura_no": fatura_no,
                "tarih": datetime.now().strftime('%Y-%m-%d'),
                "fatura_turu": fatura_turu,
                "cari_id": siparis_detay['cari_id'],
                "odeme_turu": odeme_turu,
                "kalemler": fatura_kalemleri_data,
                "kasa_banka_id": kasa_banka_id,
                "misafir_adi": siparis_detay.get('misafir_adi'), # Siparişten misafir adı varsa
                "fatura_notlari": f"Sipariş No: {siparis_detay['siparis_no']} kaynağından oluşturuldu. {siparis_detay.get('siparis_notlari', '')}",
                "vade_tarihi": vade_tarihi,
                "genel_iskonto_tipi": siparis_detay.get('genel_iskonto_tipi', "YOK"),
                "genel_iskonto_degeri": siparis_detay.get('genel_iskonto_degeri', 0.0),
                "original_fatura_id": None # Bu bir siparişten dönüştürülen fatura, iade faturası değil
            }
            
            # API üzerinden faturayı oluştur
            response_fatura = self.db.fatura_ekle(fatura_data)
            
            # Fatura başarıyla oluşturulduysa, siparişin durumunu güncelle
            if response_fatura and response_fatura.get('id'):
                fatura_id_new = response_fatura.get('id')
                # Siparişin durumunu "TAMAMLANDI" olarak güncelle ve fatura ID'sini bağla
                siparis_guncelle_data = {
                    "durum": self.db.SIPARIS_DURUM_TAMAMLANDI,
                    "fatura_id": fatura_id_new
                }
                self.db.siparis_guncelle(siparis_id, siparis_guncelle_data)
                
                return True, f"Sipariş '{siparis_detay['siparis_no']}' başarıyla faturaya dönüştürüldü (Fatura No: {fatura_no})."
            else:
                return False, f"Fatura oluşturma API'si başarısız oldu."

        except Exception as e:
            logger.error(f"Siparişi faturaya dönüştürürken hata: {e}", exc_info=True)
            return False, f"Siparişi faturaya dönüştürürken bir hata oluştu: {e}"

    def fatura_guncelle(self, fatura_id, fatura_bilgileri):
        """
        Mevcut bir faturayı günceller.
        """
        try:
            response = self.db.fatura_guncelle(fatura_id, fatura_bilgileri)
            logger.info(f"Fatura başarıyla güncellendi: ID {fatura_id}")
            return response
        except Exception as e:
            logger.error(f"Fatura güncellenirken hata: {e}")
            raise

    def fatura_sil(self, fatura_id):
        """
        Bir faturayı siler.
        """
        try:
            response = self.db.fatura_sil(fatura_id)
            logger.info(f"Fatura başarıyla silindi: ID {fatura_id}")
            return response
        except Exception as e:
            logger.error(f"Fatura silinirken hata: {e}")
            raise

    def fatura_detay_getir(self, fatura_id):
        """
        Bir faturanın detaylarını getirir.
        """
        try:
            fatura = self.db.fatura_getir_by_id(fatura_id)
            logger.info(f"Fatura detayları getirildi: ID {fatura_id}")
            return fatura
        except Exception as e:
            logger.error(f"Fatura detayları getirilirken hata: {e}")
            raise

    def fatura_listesi_al(self):
        """
        Tüm faturaların listesini getirir.
        """
        try:
            faturalar = self.db.fatura_listesi_al()
            logger.info("Fatura listesi başarıyla alındı.")
            return faturalar
        except Exception as e:
            logger.error(f"Fatura listesi alınırken hata: {e}")
            raise

class TopluIslemService:
    def __init__(self, db_manager):
        """
        Toplu veri işlemleri (içe/dışa aktarım) için servis sınıfı.
        db_manager artık API ile iletişim kurar.
        """
        self.db = db_manager
        logger.info("TopluIslemService başlatıldı.")

    def toplu_musteri_ice_aktar(self, musteri_listesi):
        """
        Verilen müşteri listesini toplu olarak içe aktarır.
        Her bir müşteri için API'ye POST isteği gönderir.
        """
        basarili_sayisi = 0
        hata_sayisi = 0
        hatalar = []

        for musteri_data in musteri_listesi:
            try:
                self.db.musteri_ekle(musteri_data)
                basarili_sayisi += 1
            except Exception as e:
                hata_sayisi += 1
                hatalar.append(f"Müşteri '{musteri_data.get('ad_soyad', 'Bilinmeyen')}' eklenirken hata: {e}")
                logger.error(f"Toplu müşteri içe aktarımında hata: {e} - Müşteri: {musteri_data.get('ad_soyad')}")
        
        logger.info(f"Toplu müşteri içe aktarım tamamlandı. Başarılı: {basarili_sayisi}, Hata: {hata_sayisi}")
        return {"basarili": basarili_sayisi, "hata": hata_sayisi, "hatalar": hatalar}

    def toplu_tedarikci_ice_aktar(self, tedarikci_listesi):
        """
        Verilen tedarikçi listesini toplu olarak içe aktarır.
        Her bir tedarikçi için API'ye POST isteği gönderir.
        """
        basarili_sayisi = 0
        hata_sayisi = 0
        hatalar = []

        for tedarikci_data in tedarikci_listesi:
            try:
                self.db.tedarikci_ekle(tedarikci_data)
                basarili_sayisi += 1
            except Exception as e:
                hata_sayisi += 1
                hatalar.append(f"Tedarikçi '{tedarikci_data.get('ad_soyad', 'Bilinmeyen')}' eklenirken hata: {e}")
                logger.error(f"Toplu tedarikçi içe aktarımında hata: {e} - Tedarikçi: {tedarikci_data.get('ad_soyad')}")
        
        logger.info(f"Toplu tedarikçi içe aktarım tamamlandı. Başarılı: {basarili_sayisi}, Hata: {hata_sayisi}")
        return {"basarili": basarili_sayisi, "hata": hata_sayisi, "hatalar": hatalar}

    def toplu_stok_ice_aktar(self, stok_listesi):
        """
        Verilen stok listesini toplu olarak içe aktarır.
        Her bir stok için API'ye POST isteği gönderir.
        """
        basarili_sayisi = 0
        hata_sayisi = 0
        hatalar = []

        for stok_data in stok_listesi:
            try:
                self.db.stok_ekle(stok_data)
                basarili_sayisi += 1
            except Exception as e:
                hata_sayisi += 1
                hatalar.append(f"Stok '{stok_data.get('ad', 'Bilinmeyen')}' eklenirken hata: {e}")
                logger.error(f"Toplu stok içe aktarımında hata: {e} - Stok: {stok_data.get('ad')}")
        
        logger.info(f"Toplu stok içe aktarım tamamlandı. Başarılı: {basarili_sayisi}, Hata: {hata_sayisi}")
        return {"basarili": basarili_sayisi, "hata": hata_sayisi, "hatalar": hatalar}

    # Not: Dışa aktarma fonksiyonları henüz API'den toplu veri çekme yeteneğine sahip değil.
    # Eğer API'de CSV/Excel dışa aktarma endpoint'leri varsa, bu fonksiyonlar güncellenebilir.
    # Şimdilik, sadece mevcut listeleme fonksiyonlarını kullanabiliriz.

    def musteri_listesini_disa_aktar(self):
        """Müşteri listesini API'den alır ve döndürür."""
        try:
            return self.db.musteri_listesi_al()
        except Exception as e:
            logger.error(f"Müşteri listesi dışa aktarılırken hata: {e}")
            raise

    def tedarikci_listesini_disa_aktar(self):
        """Tedarikçi listesini API'den alır ve döndürür."""
        try:
            return self.db.tedarikci_listesi_al()
        except Exception as e:
            logger.error(f"Tedarikçi listesi dışa aktarılırken hata: {e}")
            raise

    def stok_listesini_disa_aktar(self):
        """Stok listesini API'den alır ve döndürür."""
        try:
            return self.db.stok_listesi_al()
        except Exception as e:
            logger.error(f"Stok listesi dışa aktarılırken hata: {e}")
            raise
