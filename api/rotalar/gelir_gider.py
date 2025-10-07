from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import String, and_, func
from typing import List, Optional
from .. import semalar, modeller, guvenlik # guvenlik eklendi
from ..veritabani import get_db
from datetime import date, datetime
# .. import guvenlik # Zaten yukarıda import edildi

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
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    
    # 1. ORM modelini kullanarak sorguyu başlat
    query = db.query(modeller.GelirGider).filter(modeller.GelirGider.kullanici_id == current_user.id)

    if tip_filtre:
        query = query.filter(modeller.GelirGider.tip == tip_filtre.value) 
    
    if baslangic_tarihi:
        query = query.filter(modeller.GelirGider.tarih >= baslangic_tarihi)
    
    if bitis_tarihi:
        query = query.filter(modeller.GelirGider.tarih <= bitis_tarihi)

    if aciklama_filtre:
        query = query.filter(modeller.GelirGider.aciklama.ilike(f"%{aciklama_filtre}%"))
    
    # Total count için sorguyu oluştur
    total_count = db.query(func.count(modeller.GelirGider.id)).filter(
        and_(*query._where_criteria) 
    ).scalar()

    items = query.order_by(modeller.GelirGider.tarih.desc(), modeller.GelirGider.id.desc()).offset(skip).limit(limit).all()

    # Model dönüşümü kısmı
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
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME: Tip modeller.KullaniciRead
    db: Session = Depends(get_db)
):     
    # 1. ORM modelini kullanarak sorguyu başlat
    query = db.query(modeller.GelirGider).filter(modeller.GelirGider.kullanici_id == current_user.id)

    if tip_filtre:
        query = query.filter(modeller.GelirGider.tip == tip_filtre)
    if baslangic_tarihi:
        query = query.filter(modeller.GelirGider.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(modeller.GelirGider.tarih <= bitis_tarihi)
    if aciklama_filtre:
        query = query.filter(modeller.GelirGider.aciklama.ilike(f"%{aciklama_filtre}%"))
            
    # KRİTİK DÜZELTME 3: DuplicateAlias hatasını çözme.
    total_count = db.query(func.count(modeller.GelirGider.id)).filter(
        and_(*query._where_criteria) 
    ).scalar()
            
    return total_count


@router.post("/", response_model=modeller.GelirGiderRead) # KRİTİK DÜZELTME: Dönüş modeli GelirGiderRead olmalı
def create_gelir_gider(
    kayit: modeller.GelirGiderCreate, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME: Tip modeller.KullaniciRead
    db: Session = Depends(get_db)
):
    db.begin_nested()
    try:
        # KRİTİK DÜZELTME 1: ORM modelini kullan
        # API/DB uyumu için fazlalık alanlar çıkarıldı (DB modelinde olmayan)
        kayit_data = kayit.model_dump(exclude={"kaynak", "cari_tip", "cari_id", "odeme_turu"})
        kayit_data['kullanici_id'] = current_user.id
        # Zorunlu Kaynak Tipini ekle
        kayit_data['kaynak'] = semalar.KaynakTipEnum.MANUEL.value # Gelir/Gider genellikle manueldir
        
        db_kayit = modeller.GelirGider( 
            **kayit_data
        )
        db.add(db_kayit)
        db.flush() # ID'yi almak için

        # KRİTİK DÜZELTME: Kasa/Banka hareketleri oluşturulur
        if kayit.kasa_banka_id:
            
            islem_yone_kasa = None
            if kayit.tip == semalar.GelirGiderTipEnum.GELIR:
                islem_yone_kasa = semalar.IslemYoneEnum.GIRIS
            elif kayit.tip == semalar.GelirGiderTipEnum.GIDER:
                islem_yone_kasa = semalar.IslemYoneEnum.CIKIS
                
            # Kasa/Banka Hareketini oluştur
            if islem_yone_kasa:
                db_kasa_hareket = modeller.KasaBankaHareket(
                    kasa_banka_id=kayit.kasa_banka_id,
                    tarih=kayit.tarih,
                    islem_turu=kayit.tip.value,
                    islem_yone=islem_yone_kasa,
                    tutar=kayit.tutar,
                    aciklama=f"{kayit.tip.value} Kaydı: {kayit.aciklama}",
                    kaynak=semalar.KaynakTipEnum.GELIR_GIDER.value, # Kaynak tipi Gelir/Gider
                    kaynak_id=db_kayit.id,
                    kullanici_id=current_user.id
                )
                db.add(db_kasa_hareket)

            # Kasa/Banka Bakiyesini Güncelle (Güvenlik filtresi eklendi)
            kasa_hesabi = db.query(modeller.KasaBankaHesap).filter( 
                modeller.KasaBankaHesap.id == kayit.kasa_banka_id, 
                modeller.KasaBankaHesap.kullanici_id == current_user.id
            ).first()
            if not kasa_hesabi:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı.")
            
            if kayit.tip == semalar.GelirGiderTipEnum.GELIR:
                kasa_hesabi.bakiye += kayit.tutar
            elif kayit.tip == semalar.GelirGiderTipEnum.GIDER:
                kasa_hesabi.bakiye -= kayit.tutar
                
        # Cari Hareket Oluşturma (Cari kayıtları sadece Gelir/Gider işlemlerinin cari etkisini yansıtır)
        if kayit.cari_id and kayit.cari_tip:
            islem_yone_cari = None
            islem_turu_cari = None
            if kayit.tip == semalar.GelirGiderTipEnum.GELIR: # Müşteriden gelen tahsilat
                islem_yone_cari = semalar.IslemYoneEnum.BORC
                islem_turu_cari = semalar.KaynakTipEnum.TAHSILAT
            elif kayit.tip == semalar.GelirGiderTipEnum.GIDER: # Tedarikçiye yapılan ödeme
                islem_yone_cari = semalar.IslemYoneEnum.ALACAK
                islem_turu_cari = semalar.KaynakTipEnum.ODEME
            
            # Gerekli cari hareket oluşturulur
            if islem_yone_cari:
                db_cari_hareket = modeller.CariHareket(
                    tarih=kayit.tarih,
                    cari_tip=kayit.cari_tip.value,
                    cari_id=kayit.cari_id,
                    islem_turu=islem_turu_cari.value,
                    islem_yone=islem_yone_cari,
                    tutar=kayit.tutar,
                    aciklama=kayit.aciklama,
                    kaynak=semalar.KaynakTipEnum.GELIR_GIDER,
                    kaynak_id=db_kayit.id,
                    kasa_banka_id=kayit.kasa_banka_id,
                    odeme_turu=kayit.odeme_turu,
                    kullanici_id=current_user.id
                )
                db.add(db_cari_hareket)

        db.commit()
        db.refresh(db_kayit)
        
        kayit_model = modeller.GelirGiderRead.model_validate(db_kayit, from_attributes=True)
        # Kasa/Banka adını çekme (Model read'e uygun hale getirildi)
        kasa_banka = db.query(modeller.KasaBankaHesap).filter( 
            modeller.KasaBankaHesap.id == kayit.kasa_banka_id, 
            modeller.KasaBankaHesap.kullanici_id == current_user.id
        ).first()
        kayit_model.kasa_banka_adi = kasa_banka.hesap_adi if kasa_banka else None
        
        return kayit_model
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gelir/Gider kaydı oluşturulurken hata: {str(e)}")
        
@router.delete("/{kayit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gelir_gider(
    kayit_id: int, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME: Tip modeller.KullaniciRead
    db: Session = Depends(get_db)
):
    # KRİTİK DÜZELTME 1: ORM modelini kullan
    db_kayit = db.query(modeller.GelirGider).filter(modeller.GelirGider.id == kayit_id, modeller.GelirGider.kullanici_id == current_user.id).first()
    if db_kayit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gelir/Gider kaydı bulunamadı")
    
    db.begin_nested()
    try:
        # Kasa/Banka Bakiyesini geri al ve Hareketleri sil (Atomik işlem)
        if db_kayit.kasa_banka_id:
            
            # 1. Kasa/Banka Bakiyesini geri al (Güvenlik filtresi eklendi)
            kasa_hesabi = db.query(modeller.KasaBankaHesap).filter(
                modeller.KasaBankaHesap.id == db_kayit.kasa_banka_id, 
                modeller.KasaBankaHesap.kullanici_id == current_user.id
            ).first()
            
            if kasa_hesabi:
                if db_kayit.tip == semalar.GelirGiderTipEnum.GELIR:
                    kasa_hesabi.bakiye -= db_kayit.tutar
                elif db_kayit.tip == semalar.GelirGiderTipEnum.GIDER:
                    kasa_hesabi.bakiye += db_kayit.tutar
            
            # 2. İlişkili KasaBankaHareket kaydını sil
            db.query(modeller.KasaBankaHareket).filter(
                modeller.KasaBankaHareket.kaynak == semalar.KaynakTipEnum.GELIR_GIDER.value,
                modeller.KasaBankaHareket.kaynak_id == kayit_id,
                modeller.KasaBankaHareket.kullanici_id == current_user.id
            ).delete(synchronize_session=False)

        # 3. İlişkili Cari Hareketi sil (kaynak ve kaynak_id üzerinden)
        cari_hareket = db.query(modeller.CariHareket).filter(
            modeller.CariHareket.kaynak == semalar.KaynakTipEnum.GELIR_GIDER.value,
            modeller.CariHareket.kaynak_id == kayit_id,
            modeller.CariHareket.kullanici_id == current_user.id
        ).first()

        if cari_hareket:
            db.delete(cari_hareket)

        # 4. Ana Gelir/Gider kaydını sil
        db.delete(db_kayit)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gelir/Gider kaydı silinirken hata: {str(e)}")

    return