from fastapi import APIRouter, Depends, HTTPException, status
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
@router.get("/", response_model=dict)
def read_gelir_gider(
    skip: int = 0,
    limit: int = 100,
    tip_filtre: Optional[semalar.GelirGiderTipEnum] = None, # tip_filtre parametresinin türü güncellendi
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

    total_count = query.count()

    kasa_banka_map = {kb.id: kb.hesap_adi for kb in db.query(semalar.KasaBanka).all()}

    gelir_gider_kayitlari = query.order_by(semalar.GelirGider.tarih.desc()).offset(skip).limit(limit).all()

    results = []
    for gg in gelir_gider_kayitlari:
        gg_model = modeller.GelirGiderRead.model_validate(gg, from_attributes=True)
        gg_model.kasa_banka_adi = kasa_banka_map.get(gg.kasa_banka_id)
        results.append(gg_model)
        
    return {"items": results, "total": total_count}

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
            kaynak=semalar.KaynakTipEnum.MANUEL, # Manuel işlemler için kaynak her zaman MANUEL'dir.
            kasa_banka_id=kayit.kasa_banka_id
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
            if kayit.cari_tip == semalar.CariTipiEnum.MUSTERI and kayit.tip == semalar.GelirGiderTipEnum.GELIR: # ENUM kullanıldı
                islem_tipi = semalar.KaynakTipEnum.TAHSILAT # Müşteriden gelen para -> TAHSİLAT
            elif kayit.cari_tip == semalar.CariTipiEnum.TEDARIKCI and kayit.tip == semalar.GelirGiderTipEnum.GIDER: # ENUM kullanıldı
                islem_tipi = semalar.KaynakTipEnum.ODEME # Tedarikçiye giden para -> ÖDEME
            
            if islem_tipi:
                db_cari_hareket = semalar.CariHareket(
                    tarih=kayit.tarih,
                    cari_tip=kayit.cari_tip,
                    cari_id=kayit.cari_id,
                    islem_turu=islem_tipi, # islem_tipi already an ENUM value
                    islem_yone=semalar.IslemYoneEnum.ALACAK if islem_tipi == semalar.KaynakTipEnum.TAHSILAT else semalar.IslemYoneEnum.BORC, # Tahsilat alacak, ödeme borç
                    tutar=kayit.tutar,
                    aciklama=kayit.aciklama,
                    kaynak=semalar.KaynakTipEnum.MANUEL,
                    kasa_banka_id=kayit.kasa_banka_id
                )
                db.add(db_cari_hareket)

        db.commit()
        db.refresh(db_kayit)
        
        # GelirGiderBase yerine GelirGiderRead döndürmek daha doğru olabilir,
        # ancak mevcut modellerde GelirGiderRead'in kasa_banka_adi gibi alanları var.
        # Bu alanların populate edilmesi için özel logic gerekebilir.
        # Şimdilik GelirGiderBase döndürdüğü için sadece orm'den yüklüyoruz.
        kayit_model = modeller.GelirGiderRead.model_validate(db_kayit, from_attributes=True) # GelirGiderRead kullanıldı
        kayit_model.kasa_banka_adi = kasa_hesabi.hesap_adi if kasa_hesabi else None
        
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
    
    if db_kayit.kaynak != semalar.KaynakTipEnum.MANUEL: # ENUM kullanıldı
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sadece 'MANUEL' kaynaklı kayıtlar silinebilir.")
    
    db.begin_nested()
    try:
        # Kasa/banka bakiyesini geri al
        if db_kayit.kasa_banka_id:
            kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == db_kayit.kasa_banka_id).first()
            if kasa_hesabi:
                if db_kayit.tip == semalar.GelirGiderTipEnum.GELIR: # ENUM kullanıldı
                    kasa_hesabi.bakiye -= db_kayit.tutar
                elif db_kayit.tip == semalar.GelirGiderTipEnum.GIDER: # ENUM kullanıldı
                    kasa_hesabi.bakiye += db_kayit.tutar
        
        # İlişkili olabilecek cari hareketi de sil (açıklama ve tutar eşleşmesine göre)
        # Bu, daha sağlam bir yapı için referans ID'si ile yapılmalıdır, şimdilik böyle varsayıyoruz.
        # Bu kısım API'deki modeller ve ilişkilerle uyumlu hale getirilmeli
        # Örnek: semalar.CariHareket.kaynak_id == db_kayit.id gibi bir filtreleme yapılmalı
        db.query(semalar.CariHareket).filter(
            semalar.CariHareket.aciklama == db_kayit.aciklama,
            semalar.CariHareket.tutar == db_kayit.tutar,
            semalar.CariHareket.kaynak == semalar.KaynakTipEnum.MANUEL # Kaynak tipi de kontrol edildi
        ).delete(synchronize_session=False)

        db.delete(db_kayit)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gelir/Gider kaydı silinirken hata: {str(e)}")

    return