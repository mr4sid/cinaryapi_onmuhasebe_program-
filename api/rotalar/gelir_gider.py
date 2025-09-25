from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import String, and_
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db
from datetime import date, datetime
from .. import guvenlik # Yeni eklenen import

router = APIRouter(
    prefix="/gelir_gider",
    tags=["Gelir ve Gider İşlemleri"]
)

@router.get("/", response_model=modeller.GelirGiderListResponse)
def read_gelir_gider(
    skip: int = 0,
    limit: int = 20,
    tip_filtre: Optional[semalar.GelirGiderTipEnum] = None,
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    aciklama_filtre: Optional[str] = None,
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.GelirGider).filter(semalar.GelirGider.kullanici_id == current_user.id)

    if tip_filtre:
        query = query.filter(semalar.GelirGider.tip == tip_filtre)
    
    if baslangic_tarihi:
        query = query.filter(semalar.GelirGider.tarih >= baslangic_tarihi)
    
    if bitis_tarihi:
        query = query.filter(semalar.GelirGider.tarih <= bitis_tarihi)

    if aciklama_filtre:
        query = query.filter(semalar.GelirGider.aciklama.ilike(f"%{aciklama_filtre}%"))
    
    total_count = query.count()
    items = query.order_by(semalar.GelirGider.tarih.desc()).offset(skip).limit(limit).all()

    # Model dönüşümü kısmı, eski koddaki gibi list comprehension ile güncellendi.
    # Mevcut fonksiyonelliği korumak adına bu şekilde bıraktım.
    items = [
        modeller.GelirGiderRead.model_validate(gg, from_attributes=True)
        for gg in items
    ]

    return {"items": items, "total": total_count}

@router.get("/count", response_model=int)
def get_gelir_gider_count(
    tip_filtre: Optional[str] = None,
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    aciklama_filtre: Optional[str] = None,
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.GelirGider).filter(semalar.GelirGider.kullanici_id == current_user.id)

    if tip_filtre:
        query = query.filter(semalar.GelirGider.tip == tip_filtre)
    if baslangic_tarihi:
        query = query.filter(semalar.GelirGider.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(semalar.GelirGider.tarih <= bitis_tarihi)
    if aciklama_filtre:
        query = query.filter(semalar.GelirGider.aciklama.ilike(f"%{aciklama_filtre}%"))
            
    return query.count()


@router.post("/", response_model=modeller.GelirGiderBase)
def create_gelir_gider(
    kayit: modeller.GelirGiderCreate, 
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    db.begin_nested()
    try:
        # Yeni güvenlik yaklaşımına göre kullanıcı ID'si doğrudan token'dan alınmalı.
        kayit_data = kayit.model_dump(exclude={"kaynak", "cari_tip", "cari_id", "odeme_turu"})
        kayit_data['kullanici_id'] = current_user.id
        
        db_kayit = semalar.GelirGider(
            **kayit_data
        )
        db.add(db_kayit)

        # Kasa/Banka hesabı sorgusu da kullanici_id ile filtrelenmeli
        kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == kayit.kasa_banka_id, semalar.KasaBanka.kullanici_id == current_user.id).first()
        if not kasa_hesabi:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı.")
        
        if kayit.tip == semalar.GelirGiderTipEnum.GELIR:
            kasa_hesabi.bakiye += kayit.tutar
        elif kayit.tip == semalar.GelirGiderTipEnum.GIDER:
            kasa_hesabi.bakiye -= kayit.tutar
        
        if kayit.cari_id and kayit.cari_tip:
            islem_tipi = ""
            if kayit.cari_tip == semalar.CariTipiEnum.MUSTERI and kayit.tip == semalar.GelirGiderTipEnum.GELIR:
                islem_tipi = semalar.KaynakTipEnum.TAHSILAT
            elif kayit.cari_tip == semalar.CariTipiEnum.TEDARIKCI and kayit.tip == semalar.GelirGiderTipEnum.GIDER:
                islem_tipi = semalar.KaynakTipEnum.ODEME
            
            if islem_tipi:
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
                    odeme_turu=kayit.odeme_turu,
                    kullanici_id=current_user.id
                )
                db.add(db_cari_hareket)

        db.commit()
        db.refresh(db_kayit)
        
        kayit_model = modeller.GelirGiderRead.model_validate(db_kayit, from_attributes=True)
        # Kasa/Banka adı sorgusu da güncellenmeli.
        kasa_banka = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == kayit.kasa_banka_id, semalar.KasaBanka.kullanici_id == current_user.id).first()
        kayit_model.kasa_banka_adi = kasa_banka.hesap_adi if kasa_banka else None
        
        return kayit_model
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gelir/Gider kaydı oluşturulurken hata: {str(e)}")
        
@router.delete("/{kayit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gelir_gider(
    kayit_id: int, 
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user), 
    db: Session = Depends(get_db)
):
    db_kayit = db.query(semalar.GelirGider).filter(semalar.GelirGider.id == kayit_id, semalar.GelirGider.kullanici_id == current_user.id).first()
    if db_kayit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gelir/Gider kaydı bulunamadı")
    
    db.begin_nested()
    try:
        if db_kayit.kasa_banka_id:
            kasa_hesabi = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == db_kayit.kasa_banka_id, semalar.KasaBanka.kullanici_id == current_user.id).first()
            if kasa_hesabi:
                if db_kayit.tip == semalar.GelirGiderTipEnum.GELIR:
                    kasa_hesabi.bakiye -= db_kayit.tutar
                elif db_kayit.tip == semalar.GelirGiderTipEnum.GIDER:
                    kasa_hesabi.bakiye += db_kayit.tutar
        
        cari_hareket = db.query(semalar.CariHareket).filter(
            semalar.CariHareket.aciklama == db_kayit.aciklama,
            semalar.CariHareket.tutar == db_kayit.tutar,
            semalar.CariHareket.kaynak == semalar.KaynakTipEnum.MANUEL,
            semalar.CariHareket.kullanici_id == current_user.id
        ).first()

        if cari_hareket:
            db.delete(cari_hareket)

        db.delete(db_kayit)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gelir/Gider kaydı silinirken hata: {str(e)}")

    return