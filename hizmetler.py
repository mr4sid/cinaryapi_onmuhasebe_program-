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
