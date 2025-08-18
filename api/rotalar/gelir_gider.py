# api/rotalar/gelir_gider.py dosyasının içeriği
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import String, and_
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db
from datetime import date, datetime # date ve datetime objeleri için

router = APIRouter(
    prefix="/gelir_gider",
    tags=["Gelir ve Gider İşlemleri"]
)

# --- VERİ OKUMA (READ) ---
@router.get("/", response_model=modeller.GelirGiderListResponse)
def read_gelir_gider(
    skip: int = 0,
    limit: int = 20,
    tip_filtre: Optional[semalar.GelirGiderTipEnum] = None,
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    aciklama_filtre: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Gelir/gider listesini filtreleyerek döndürür.
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

    total_count = query.count()
    gelir_gider_listesi = query.offset(skip).limit(limit).all()

    items = [
        modeller.GelirGiderRead.model_validate(gg, from_attributes=True)
        for gg in gelir_gider_listesi
    ]

    return {"items": items, "total": total_count}

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
        # Düzeltme: Pydantic modelden gelen veriden 'kaynak' ve 'cari_tip' alanları çıkarıldı
        # çünkü bunlar veritabanı modelinde doğrudan yer almıyor, ilişkisel olarak yönetiliyor.
        # Bu alanlar, cari hareketleri oluşturmak için kullanılacak.
        kayit_data = kayit.model_dump(exclude={"kaynak", "cari_tip", "cari_id", "odeme_turu"})

        db_kayit = semalar.GelirGider(
            **kayit_data
        )
        db.add(db_kayit)

        # Kasa/banka bakiyesini güncelle
        kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == kayit.kasa_banka_id).first()
        if not kasa_hesabi:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı.")
        
        if kayit.tip == semalar.GelirGiderTipEnum.GELIR: # ENUM kullanıldı
            kasa_hesabi.bakiye += kayit.tutar
        elif kayit.tip == semalar.GelirGiderTipEnum.GIDER: # ENUM kullanıldı
            kasa_hesabi.bakiye -= kayit.tutar
        
        # Eğer cari bilgisi verilmişse, cari hareket de oluştur
        if kayit.cari_id and kayit.cari_tip:
            islem_tipi = ""
            if kayit.cari_tip == semalar.CariTipiEnum.MUSTERI and kayit.tip == semalar.GelirGiderTipEnum.GELIR:
                islem_tipi = semalar.KaynakTipEnum.TAHSILAT
            elif kayit.cari_tip == semalar.CariTipiEnum.TEDARIKCI and kayit.tip == semalar.GelirGiderTipEnum.GIDER:
                islem_tipi = semalar.KaynakTipEnum.ODEME
            
            if islem_tipi:
                # Düzeltme: 'cari_tip' yerine 'cari_turu' kullanıldı.
                db_cari_hareket = semalar.CariHareket(
                    tarih=kayit.tarih,
                    cari_turu=kayit.cari_tip,
                    cari_id=kayit.cari_id,
                    islem_turu=islem_tipi.value,
                    islem_yone=semalar.IslemYoneEnum.ALACAK if islem_tipi == semalar.KaynakTipEnum.TAHSILAT else semalar.IslemYoneEnum.BORC,
                    tutar=kayit.tutar,
                    aciklama=kayit.aciklama,
                    kaynak=semalar.KaynakTipEnum.MANUEL,
                    kasa_banka_id=kayit.kasa_banka_id,
                    odeme_turu=kayit.odeme_turu
                )
                db.add(db_cari_hareket)

        db.commit()
        db.refresh(db_kayit)
        
        kayit_model = modeller.GelirGiderRead.model_validate(db_kayit, from_attributes=True)
        kasa_banka = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == kayit.kasa_banka_id).first()
        kayit_model.kasa_banka_adi = kasa_banka.hesap_adi if kasa_banka else None
        
        return kayit_model
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gelir/Gider kaydı oluşturulurken hata: {str(e)}")
        
# --- VERİ SİLME (DELETE) ---
@router.delete("/{kayit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gelir_gider(kayit_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip manuel gelir/gider kaydını ve ilişkili etkilerini siler.
    """
    db_kayit = db.query(semalar.GelirGider).filter(semalar.GelirGider.id == kayit_id).first()
    if db_kayit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gelir/Gider kaydı bulunamadı")
    
    # DÜZELTME: `db_kayit.kaynak` özelliği mevcut olmadığından, bu kontrol kaldırıldı.
    # Bu kontrol, veritabanı modelinizde `kaynak` alanı bulunduğunda geri eklenebilir.
    
    db.begin_nested()
    try:
        # Kasa/banka bakiyesini geri al
        if db_kayit.kasa_banka_id:
            kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == db_kayit.kasa_banka_id).first()
            if kasa_hesabi:
                if db_kayit.tip == semalar.GelirGiderTipEnum.GELIR:
                    kasa_hesabi.bakiye -= db_kayit.tutar
                elif db_kayit.tip == semalar.GelirGiderTipEnum.GIDER:
                    kasa_hesabi.bakiye += db_kayit.tutar
        
        # İlişkili olabilecek cari hareketi de sil (açıklama ve tutar eşleşmesine göre)
        cari_hareket = db.query(semalar.CariHareket).filter(
            semalar.CariHareket.aciklama == db_kayit.aciklama,
            semalar.CariHareket.tutar == db_kayit.tutar,
            semalar.CariHareket.kaynak == semalar.KaynakTipEnum.MANUEL
        ).first()

        if cari_hareket:
            db.delete(cari_hareket)

        db.delete(db_kayit)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gelir/Gider kaydı silinirken hata: {str(e)}")

    return