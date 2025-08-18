# api.zip/rotalar/api_yardimcilar.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import semalar # semalar modülünü doğru seviyeden içe aktarın
import logging
from sqlalchemy.exc import SQLAlchemyError
from ..semalar import CariHareket, Musteri, Tedarikci, GelirGider
logger = logging.getLogger(__name__)

def _cari_bakiyesini_guncelle(db: Session, cari_id: int, cari_tipi: str):
    """
    Belirli bir carinin (Müşteri/Tedarikçi) bakiyesini, ilişkili tüm cari hareketlerini toplayarak yeniden hesaplar ve günceller.
    Bu fonksiyon, bir işlem (fatura, ödeme vb.) eklendiğinde veya silindiğinde çağrılmalıdır.
    """
    try:
        # Cari hareketlerini topla
        hareketler = db.query(CariHareket).filter(CariHareket.cari_id == cari_id).all()

        toplam_borc = sum(h.tutar for h in hareketler if h.islem_yone == "BORC")
        toplam_alacak = sum(h.tutar for h in hareketler if h.islem_yone == "ALACAK")
        
        # Güncel bakiye hesapla
        guncel_bakiye = toplam_alacak - toplam_borc

        if cari_tipi == "MUSTERI":
            cari = db.query(Musteri).filter(Musteri.id == cari_id).first()
        elif cari_tipi == "TEDARIKCI":
            cari = db.query(Tedarikci).filter(Tedarikci.id == cari_id).first()
        else:
            logger.warning(f"Bilinmeyen cari tipi: {cari_tipi} için bakiye güncellenemedi.")
            return

        if cari:
            cari.bakiye = guncel_bakiye
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
        logger.error(f"Cari bakiye güncellenirken beklenmeyen bir hata oluştu: {e}", exc_info=True)
        raise e

def calculate_cari_net_bakiye(db: Session, cari_id: int, cari_turu: str) -> float:
    """
    Belirli bir cari (Müşteri veya Tedarikçi) için net bakiyeyi hesaplar.
    """
    alacak_toplami = db.query(func.sum(semalar.CariHareket.tutar)).filter(
        semalar.CariHareket.cari_id == cari_id,
        semalar.CariHareket.cari_turu == cari_turu,
        semalar.CariHareket.islem_yone == "ALACAK"
    ).scalar() or 0.0

    borc_toplami = db.query(func.sum(semalar.CariHareket.tutar)).filter(
        semalar.CariHareket.cari_id == cari_id,
        semalar.CariHareket.cari_turu == cari_turu,
        semalar.CariHareket.islem_yone == "BORC"
    ).scalar() or 0.0

    net_bakiye = alacak_toplami - borc_toplami
    return net_bakiye