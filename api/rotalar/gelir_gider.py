from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db
from datetime import date, datetime # date ve datetime objeleri için

router = APIRouter(
    prefix="/gelir_gider",
    tags=["Gelir ve Gider İşlemleri"]
)

# --- VERİ OKUMA (READ) ---

@router.get("/", response_model=List[modeller.GelirGiderBase])
def read_gelir_gider(
    skip: int = 0,
    limit: int = 100,
    tip_filtre: Optional[str] = None, # 'GELİR' veya 'GİDER'
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    aciklama_filtre: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Tüm gelir/gider kayıtlarını listeler. Tipe, tarih aralığına ve açıklamaya göre filtrelenebilir.
    """
    query = db.query(semalar.GelirGider)

    if tip_filtre:
        query = query.filter(semalar.GelirGider.tip == tip_filtre)
    if baslangic_tarihi:
        query = query.filter(semalar.GelirGider.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.GelirGider.tarih <= bitis_tarihi)
    if aciklama_filtre:
        query = query.filter(semalar.GelirGider.aciklama.ilike(f"%{aciklama_filtre}%"))

    # Kasa/Banka adlarını çekmek için toplu bir sorgu yapalım
    kasa_banka_map = {kb.id: kb.hesap_adi for kb in db.query(semalar.KasaBanka).all()}

    gelir_gider_kayitlari = query.order_by(semalar.GelirGider.tarih.desc()).offset(skip).limit(limit).all()

    results = []
    for gg in gelir_gider_kayitlari:
        gg_model = modeller.GelirGiderBase.from_orm(gg)
        gg_model.kasa_banka_adi = kasa_banka_map.get(gg.kasa_banka_id)
        results.append(gg_model)
        
    return results

@router.get("/count", response_model=int)
def get_gelir_gider_count(
    tip_filtre: Optional[str] = None, # 'GELİR' veya 'GİDER'
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    aciklama_filtre: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Filtrelere göre toplam gelir/gider kayıt sayısını döndürür.
    """
    query = db.query(semalar.GelirGider)

    if tip_filtre:
        query = query.filter(semalar.GelirGider.tip == tip_filtre)
    if baslangic_tarihi:
        query = query.filter(semalar.GelirGider.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.GelirGider.tarih <= bitis_tarihi)
    if aciklama_filtre:
        query = query.filter(semalar.GelirGider.aciklama.ilike(f"%{aciklama_filtre}%"))
            
    return query.count()

# --- VERİ OLUŞTURMA (CREATE) ---
class GelirGiderCreate(modeller.GelirGiderBase):
    # ID ve Kaynak (genellikle manuel için kullanılır) kaldırılır
    id: Optional[int] = None # Create işleminde ID olmaz
    kaynak: Optional[str] = "MANUEL" # Varsayılan kaynak manuel

@router.post("/", response_model=modeller.GelirGiderBase)
def create_gelir_gider(kayit: modeller.GelirGiderCreate, db: Session = Depends(get_db)):
    """
    Yeni bir manuel gelir/gider kaydı oluşturur.
    Kasa/Banka bakiyesini ve (eğer belirtilmişse) ilgili cari hesabı günceller.
    """
    db.begin_nested()
    try:
        db_kayit = semalar.GelirGider(
            tarih=kayit.tarih,
            tip=kayit.tip,
            tutar=kayit.tutar,
            aciklama=kayit.aciklama,
            kaynak="MANUEL", # Manuel işlemler için kaynak her zaman MANUEL'dir.
            kasa_banka_id=kayit.kasa_banka_id
        )
        db.add(db_kayit)

        # Kasa/banka bakiyesini güncelle
        kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == kayit.kasa_banka_id).first()
        if not kasa_hesabi:
            raise HTTPException(status_code=404, detail="Kasa/Banka hesabı bulunamadı.")
        
        if kayit.tip == 'GELİR':
            kasa_hesabi.bakiye += kayit.tutar
        elif kayit.tip == 'GİDER':
            kasa_hesabi.bakiye -= kayit.tutar
        
        # Eğer cari bilgisi verilmişse, cari hareket de oluştur
        if kayit.cari_id and kayit.cari_tip:
            islem_tipi = ""
            if kayit.cari_tip == 'MUSTERI' and kayit.tip == 'GELİR':
                islem_tipi = 'TAHSILAT' # Müşteriden gelen para -> TAHSİLAT
            elif kayit.cari_tip == 'TEDARIKCI' and kayit.tip == 'GİDER':
                islem_tipi = 'ODEME' # Tedarikçiye giden para -> ÖDEME
            
            if islem_tipi:
                db_cari_hareket = semalar.CariHareketler(
                    tarih=kayit.tarih,
                    cari_tip=kayit.cari_tip,
                    cari_id=kayit.cari_id,
                    islem_tipi=islem_tipi,
                    tutar=kayit.tutar,
                    aciklama=kayit.aciklama,
                    referans_tip='MANUEL',
                    kasa_banka_id=kayit.kasa_banka_id
                )
                db.add(db_cari_hareket)

        db.commit()
        db.refresh(db_kayit)
        
        kayit_model = modeller.GelirGiderBase.from_orm(db_kayit)
        kayit_model.kasa_banka_adi = kasa_hesabi.hesap_adi if kasa_hesabi else None
        
        return kayit_model
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gelir/Gider kaydı oluşturulurken hata: {str(e)}")
    
# --- VERİ SİLME (DELETE) ---
@router.delete("/{kayit_id}", status_code=204)
def delete_gelir_gider(kayit_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip manuel gelir/gider kaydını ve ilişkili etkilerini siler.
    """
    db_kayit = db.query(semalar.GelirGider).filter(semalar.GelirGider.id == kayit_id).first()
    if db_kayit is None:
        raise HTTPException(status_code=404, detail="Gelir/Gider kaydı bulunamadı")
    
    if db_kayit.kaynak != "MANUEL":
        raise HTTPException(status_code=400, detail="Sadece 'MANUEL' kaynaklı kayıtlar silinebilir.")
    
    db.begin_nested()
    try:
        # Kasa/banka bakiyesini geri al
        if db_kayit.kasa_banka_id:
            kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == db_kayit.kasa_banka_id).first()
            if kasa_hesabi:
                if db_kayit.tip == 'GELİR':
                    kasa_hesabi.bakiye -= db_kayit.tutar
                elif db_kayit.tip == 'GİDER':
                    kasa_hesabi.bakiye += db_kayit.tutar
        
        # İlişkili olabilecek cari hareketi de sil (açıklama ve tutar eşleşmesine göre)
        # Bu, daha sağlam bir yapı için referans ID'si ile yapılmalıdır, şimdilik böyle varsayıyoruz.
        db.query(semalar.CariHareketler).filter(
            semalar.CariHareketler.aciklama == db_kayit.aciklama,
            semalar.CariHareketler.tutar == db_kayit.tutar,
            semalar.CariHareketler.referans_tip == 'MANUEL'
        ).delete(synchronize_session=False)

        db.delete(db_kayit)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gelir/Gider kaydı silinirken hata: {str(e)}")

    return