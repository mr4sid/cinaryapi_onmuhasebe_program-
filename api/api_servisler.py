from sqlalchemy.orm import Session
from sqlalchemy import func, case
from . import semalar

class CariHesaplamaService:
    def __init__(self, db: Session):
        self.db = db

    def calculate_cari_net_bakiye(self, cari_id: int, cari_turu: str) -> float:
        """
        Belirli bir cari (Müşteri veya Tedarikçi) için net bakiyeyi tek bir sorguda hesaplar.
        """
        # Sorgu sonucunda None gelmesi durumunda 0 değerini kullanmak için func.coalesce eklendi.
        result = self.db.query(
            func.coalesce(func.sum(case((semalar.CariHareket.islem_yone == "ALACAK", semalar.CariHareket.tutar), else_=0)), 0).label('alacak_toplami'),
            func.coalesce(func.sum(case((semalar.CariHareket.islem_yone == "BORC", semalar.CariHareket.tutar), else_=0)), 0).label('borc_toplami')
        ).filter(
            semalar.CariHareket.cari_id == cari_id,
            semalar.CariHareket.cari_turu == cari_turu
        ).one()

        net_bakiye = result.alacak_toplami - result.borc_toplami
        return net_bakiye