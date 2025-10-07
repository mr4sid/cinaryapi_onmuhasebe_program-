from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from .. import modeller, semalar, guvenlik
from ..veritabani import get_db
from datetime import date
from sqlalchemy import and_ # and_ import edildi

router = APIRouter(
    prefix="/cari_hareketler",
    tags=["Cari Hareketler"]
)

# --- VERİ OKUMA (READ) ---
@router.get("/", response_model=modeller.CariHareketListResponse)
def read_cari_hareketler(
    skip: int = 0,
    limit: int = 100,
    cari_id: Optional[int] = None,
    cari_tip: Optional[semalar.CariTipiEnum] = None,
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # JWT ile kullanıcı bilgisi
    db: Session = Depends(get_db)
):
    # KURAL UYGULANDI: Sorgular 'modeller' kullanır.
    query = db.query(modeller.CariHareket).filter(modeller.CariHareket.kullanici_id == current_user.id)

    if cari_id is not None:
        query = query.filter(modeller.CariHareket.cari_id == cari_id)
    if cari_tip:
        # HATA DÜZELTİLDİ: 'cari_turu' -> 'cari_tip' (zaten düzeltilmişti, emin olmak için kontrol edildi)
        query = query.filter(modeller.CariHareket.cari_tip == cari_tip.value)
    if baslangic_tarihi:
        query = query.filter(modeller.CariHareket.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(modeller.CariHareket.tarih <= bitis_tarihi)

    total_count = query.count()
    # HATA DÜZELTİLDİ: Eksik olan 'olusturma_tarihi_saat' kolonuna göre sıralama eklendi.
    hareketler = query.order_by(modeller.CariHareket.tarih.desc(), modeller.CariHareket.olusturma_tarihi_saat.desc()).offset(skip).limit(limit).all()

    # Yanıt modeline uygun hale getirme
    items = [modeller.CariHareketRead.model_validate(h, from_attributes=True) for h in hareketler]

    return {"items": items, "total": total_count}

# --- VERİ OLUŞTURMA (CREATE) ---
@router.post("/manuel", response_model=modeller.CariHareketRead)
def create_manuel_cari_hareket(
    hareket: modeller.CariHareketCreate,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    db.begin_nested()
    try:
        # 1. Cari Hareketi Oluştur
        db_hareket = modeller.CariHareket(
            **hareket.model_dump(),
            kullanici_id=current_user.id,
            olusturan_kullanici_id=current_user.id # Manuel hareketi oluşturan da aynı kullanıcıdır.
        )
        db.add(db_hareket)
        db.flush() # ID'yi almak için
        
        # 2. İlişkili Kasa Hareketi ve Bakiye Güncelleme (Eğer kasa/banka kullanılıyorsa)
        if db_hareket.kasa_banka_id and db_hareket.odeme_turu != semalar.OdemeTuruEnum.ACIK_HESAP:
            
            islem_yone_kasa = None
            if db_hareket.islem_yone == semalar.IslemYoneEnum.ALACAK: # Müşteriden Tahsilat -> Kasaya Giriş
                islem_yone_kasa = semalar.IslemYoneEnum.GIRIS
            elif db_hareket.islem_yone == semalar.IslemYoneEnum.BORC: # Tedarikçiye Ödeme -> Kasadan Çıkış
                islem_yone_kasa = semalar.IslemYoneEnum.CIKIS

            if islem_yone_kasa:
                # Kasa/Banka Hareketini Oluştur
                db_kasa_banka_hareket = modeller.KasaBankaHareket(
                    kasa_banka_id=db_hareket.kasa_banka_id,
                    tarih=db_hareket.tarih,
                    islem_turu=db_hareket.kaynak, # Kaynak tipini işlem türü olarak kullan
                    islem_yone=islem_yone_kasa,
                    tutar=db_hareket.tutar,
                    aciklama=f"Cari Hareketten Kaynaklı {db_hareket.kaynak} - {db_hareket.aciklama}",
                    kaynak=db_hareket.kaynak,
                    kaynak_id=db_hareket.id,
                    kullanici_id=current_user.id
                )
                db.add(db_kasa_banka_hareket)
                
                # Kasa/Banka Bakiyesini Güncelle
                db_kasa_banka = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.id == db_hareket.kasa_banka_id, modeller.KasaBankaHesap.kullanici_id == current_user.id).first()
                if db_kasa_banka:
                    if islem_yone_kasa == semalar.IslemYoneEnum.GIRIS:
                        db_kasa_banka.bakiye += db_hareket.tutar
                    else:
                        db_kasa_banka.bakiye -= db_hareket.tutar
                    db.add(db_kasa_banka)

        db.commit()
        db.refresh(db_hareket)

        return db_hareket
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Manuel cari hareket oluşturulurken hata: {str(e)}")


# --- VERİ SİLME (DELETE) ---
@router.delete("/{hareket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cari_hareket(
    hareket_id: int, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    # KURAL UYGULANDI: Sorgular 'modeller' kullanır ve JWT'den gelen ID ile filtreleme yapılır.
    db_hareket = db.query(modeller.CariHareket).filter(
        modeller.CariHareket.id == hareket_id,
        modeller.CariHareket.kullanici_id == current_user.id
    ).first()
    
    if db_hareket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cari hareket bulunamadı")
    
    # Sadece manuel olarak oluşturulan belirli hareket türlerinin silinmesine izin ver
    izinli_kaynaklar = [
        semalar.KaynakTipEnum.MANUEL,
        semalar.KaynakTipEnum.TAHSILAT,
        semalar.KaynakTipEnum.ODEME
    ]
    # Kaynak değeri string olduğu için Enum member'larının value'su ile karşılaştırılır
    if db_hareket.kaynak not in [k.value for k in izinli_kaynaklar]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu türde bir cari hareket API üzerinden doğrudan silinemez.")
    
    db.begin_nested()
    try:
        # KRİTİK DÜZELTME: İlişkili kasa hareketini de geri al (eğer varsa)
        if db_hareket.kasa_banka_id:
            
            # 1. Kasa/Banka Hesabındaki bakiyeyi geri al
            kasa_hesabi = db.query(modeller.KasaBankaHesap).filter(
                modeller.KasaBankaHesap.id == db_hareket.kasa_banka_id,
                modeller.KasaBankaHesap.kullanici_id == current_user.id # Güvenlik filtresi eklendi
            ).first()

            if kasa_hesabi:
                if db_hareket.islem_yone == semalar.IslemYoneEnum.ALACAK: # Tahsilat (Kasaya giriş)
                    kasa_hesabi.bakiye -= db_hareket.tutar
                elif db_hareket.islem_yone == semalar.IslemYoneEnum.BORC: # Ödeme (Kasadan çıkış)
                    kasa_hesabi.bakiye += db_hareket.tutar
                db.add(kasa_hesabi)

            # 2. İlişkili KasaBankaHareket kaydını sil (KRİTİK EKSİKLİK GİDERİLDİ)
            db.query(modeller.KasaBankaHareket).filter(
                modeller.KasaBankaHareket.kasa_banka_id == db_hareket.kasa_banka_id,
                modeller.KasaBankaHareket.kaynak == db_hareket.kaynak, # Kaynak tipi eşleştirildi
                modeller.KasaBankaHareket.kaynak_id == db_hareket.id,
                modeller.KasaBankaHareket.kullanici_id == current_user.id
            ).delete(synchronize_session=False)

        # 3. Cari Hareketi sil
        db.delete(db_hareket)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Cari hareket silinirken hata: {str(e)}")
        
    return