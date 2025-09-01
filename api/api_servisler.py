from sqlalchemy.orm import Session
from sqlalchemy import func
from . import semalar

class CariHesaplamaService:
    def __init__(self, db: Session):
        self.db = db

    def calculate_cari_net_bakiye(self, cari_id: int, cari_turu: str) -> float:
        """
        Belirli bir cari (Müşteri veya Tedarikçi) için net bakiyeyi hesaplar.
        """
        alacak_toplami = self.db.query(func.sum(semalar.CariHareket.tutar)).filter(
            semalar.CariHareket.cari_id == cari_id,
            semalar.CariHareket.cari_turu == cari_turu,
            semalar.CariHareket.islem_yone == "ALACAK"
        ).scalar() or 0.0

        borc_toplami = self.db.query(func.sum(semalar.CariHareket.tutar)).filter(
            semalar.CariHareket.cari_id == cari_id,
            semalar.CariHareket.cari_turu == cari_turu,
            semalar.CariHareket.islem_yone == "BORC"
        ).scalar() or 0.0

        net_bakiye = alacak_toplami - borc_toplami
        return net_bakiye