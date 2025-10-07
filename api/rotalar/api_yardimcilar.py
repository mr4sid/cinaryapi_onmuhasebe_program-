# api.zip/rotalar/api_yardimcilar.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import modeller, semalar # KRİTİK DÜZELTME: Doğru modeller ve semalar import edildi
import logging
from sqlalchemy.exc import SQLAlchemyError
# Eski hatalı importlar kaldırıldı.

logger = logging.getLogger(__name__)

def _cari_bakiyesini_guncelle(db: Session, cari_id: int, cari_tipi: str, kullanici_id: int):
    """
    Belirli bir carinin (Müşteri/Tedarikçi) bakiyesini, ilişkili tüm cari hareketlerini toplayarak yeniden hesaplar ve günceller.
    Bu fonksiyon, bir işlem (fatura, ödeme vb.) eklendiğinde veya silindiğinde çağrılmalıdır.
    """
    try:
        # KRİTİK DÜZELTME 1: Sorgularda modeller.CariHareket kullanıldı.
        hareketler = db.query(modeller.CariHareket).filter(
            modeller.CariHareket.cari_id == cari_id,
            modeller.CariHareket.kullanici_id == kullanici_id
        ).all()

        # KRİTİK DÜZELTME 2: Enum değerleri kullanıldı.
        toplam_borc = sum(h.tutar for h in hareketler if h.islem_yone == semalar.IslemYoneEnum.BORC)
        toplam_alacak = sum(h.tutar for h in hareketler if h.islem_yone == semalar.IslemYoneEnum.ALACAK)

        guncel_bakiye = toplam_alacak - toplam_borc

        if cari_tipi == "MUSTERI":
            # KRİTİK DÜZELTME 3: modeller.Musteri kullanıldı.
            cari = db.query(modeller.Musteri).filter(modeller.Musteri.id == cari_id, modeller.Musteri.kullanici_id == kullanici_id).first()
        elif cari_tipi == "TEDARIKCI":
            # KRİTİK DÜZELTME 3: modeller.Tedarikci kullanıldı.
            cari = db.query(modeller.Tedarikci).filter(modeller.Tedarikci.id == cari_id, modeller.Tedarikci.kullanici_id == kullanici_id).first()
        else:
            logger.warning(f"Bilinmeyen cari tipi: {cari_tipi} için bakiye güncellenemedi.")
            return

        if cari:
            # Not: Musteri/Tedarikci modellerinde bakiye kolonu olduğu varsayılır.
            setattr(cari, 'net_bakiye', guncel_bakiye) # net_bakiye alanı kullanıldığı varsayılmıştır
            db.commit()
            db.refresh(cari)
            logger.info(f"Cari ID {cari_id} için bakiye başarıyla güncellendi. Yeni bakiye: {guncel_bakiye}")
        else:
            logger.warning(f"Cari ID {cari_id} bulunamadığı için bakiye güncellenemedi.")

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Cari bakiye güncellenirken veritabanı hatası: {e}", exc_info=True)
        raise e
    except Exception as e:
        db.rollback()
        logger.error(f"Cari bakiye güncellenirken beklenmeyen bir hata oluştu: {e}", exc_info=True)
        raise e