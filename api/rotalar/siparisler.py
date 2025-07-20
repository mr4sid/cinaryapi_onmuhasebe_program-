from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db
from datetime import date

router = APIRouter(
    prefix="/siparisler",
    tags=["Siparişler"]
)

@router.get("/", response_model=List[modeller.SiparisBase])
def read_siparisler(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Tüm siparişleri, ilişkili cari adlarıyla birlikte tek bir veritabanı sorgusuyla verimli bir şekilde listeler.
    """
    # Fatura rotasındaki gibi, JOIN ile tek sorguda cari adını alıyoruz.
    cari_adi_case = case(
        (semalar.Siparis.cari_tip == "MUSTERI", semalar.Musteri.ad),
        (semalar.Siparis.cari_tip == "TEDARIKCI", semalar.Tedarikci.ad),
        else_="Bilinmeyen Cari"
    ).label("cari_adi")

    siparis_results = db.query(semalar.Siparis, cari_adi_case)\
        .outerjoin(semalar.Musteri, semalar.Musteri.id == semalar.Siparis.cari_id)\
        .outerjoin(semalar.Tedarikci, semalar.Tedarikci.id == semalar.Siparis.cari_id)\
        .order_by(semalar.Siparis.tarih.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()

    results = []
    for siparis, cari_adi in siparis_results:
        siparis_model = modeller.SiparisBase.from_orm(siparis)
        siparis_model.cari_adi = cari_adi
        siparis_model.siparis_tipi = "Satış Siparişi" if siparis.cari_tip == "MUSTERI" else "Alış Siparişi"
        results.append(siparis_model)
        
    return results

@router.get("/{siparis_id}", response_model=modeller.SiparisBase)
def read_siparis(siparis_id: int, db: Session = Depends(get_db)):
    """
    Belirli bir ID'ye sahip tek bir siparişi, ilişkili cari adıyla birlikte döndürür.
    """
    cari_adi_case = case(
        (semalar.Siparis.cari_tip == "MUSTERI", semalar.Musteri.ad),
        (semalar.Siparis.cari_tip == "TEDARIKCI", semalar.Tedarikci.ad),
        else_="Bilinmeyen Cari"
    ).label("cari_adi")

    result = db.query(semalar.Siparis, cari_adi_case)\
        .outerjoin(semalar.Musteri, semalar.Musteri.id == semalar.Siparis.cari_id)\
        .outerjoin(semalar.Tedarikci, semalar.Tedarikci.id == semalar.Siparis.cari_id)\
        .filter(semalar.Siparis.id == siparis_id)\
        .first()

    if not result:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")

    siparis, cari_adi = result
    siparis_model = modeller.SiparisBase.from_orm(siparis)
    siparis_model.cari_adi = cari_adi
    siparis_model.siparis_tipi = "Satış Siparişi" if siparis.cari_tip == "MUSTERI" else "Alış Siparişi"
    
    return siparis_model

@router.post("/", response_model=modeller.SiparisBase)
def create_siparis(siparis: modeller.SiparisCreate, db: Session = Depends(get_db)):
    """
    Yeni bir sipariş ve kalemlerini oluşturur. Tüm mantık API katmanındadır.
    """
    db.begin_nested()
    try:
        existing_siparis = db.query(semalar.Siparis).filter(semalar.Siparis.siparis_no == siparis.siparis_no).first()
        if existing_siparis:
            raise HTTPException(status_code=400, detail=f"Sipariş numarası '{siparis.siparis_no}' zaten mevcut.")

        toplam_tutar = 0.0
        db_kalemler = []

        for kalem in siparis.kalemler:
            iskontolu_bf_haric = kalem.birim_fiyat * (1 - kalem.iskonto_yuzde_1 / 100) * (1 - kalem.iskonto_yuzde_2 / 100)
            kalem_toplam_dahil = (kalem.miktar * iskontolu_bf_haric) * (1 + kalem.kdv_orani / 100)
            toplam_tutar += kalem_toplam_dahil
            
            db_kalemler.append(semalar.SiparisKalemleri(
                urun_id=kalem.urun_id, miktar=kalem.miktar, birim_fiyat=kalem.birim_fiyat,
                kdv_orani=kalem.kdv_orani, alis_fiyati_siparis_aninda=kalem.alis_fiyati_siparis_aninda,
                satis_fiyati_siparis_aninda=kalem.satis_fiyati_siparis_aninda,
                iskonto_yuzde_1=kalem.iskonto_yuzde_1, iskonto_yuzde_2=kalem.iskonto_yuzde_2
            ))
        
        # Genel iskonto henüz siparişte toplam tutarı etkilemiyor, faturada etkiliyor. İstenirse eklenebilir.
        
        db_siparis = semalar.Siparis(
            siparis_no=siparis.siparis_no,
            tarih=date.today(),
            cari_tip='MUSTERI' if siparis.siparis_tipi == 'SATIŞ_SIPARIS' else 'TEDARIKCI',
            cari_id=siparis.cari_id,
            toplam_tutar=toplam_tutar,
            durum=siparis.durum,
            siparis_notlari=siparis.siparis_notlari,
            teslimat_tarihi=siparis.teslimat_tarihi,
            genel_iskonto_tipi=siparis.genel_iskonto_tipi,
            genel_iskonto_degeri=siparis.genel_iskonto_degeri,
            olusturan_kullanici_id=1 # Varsayılan kullanıcı
        )
        db_siparis.kalemler.extend(db_kalemler)
        
        db.add(db_siparis)
        db.commit()
        db.refresh(db_siparis)
        return db_siparis
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sipariş oluşturulurken hata: {str(e)}")

@router.put("/{siparis_id}", response_model=modeller.SiparisBase)
def update_siparis(siparis_id: int, siparis: modeller.SiparisUpdate, db: Session = Depends(get_db)):
    """
    Mevcut bir siparişi günceller.
    """
    db_siparis = db.query(semalar.Siparis).filter(semalar.Siparis.id == siparis_id).first()
    if not db_siparis:
        raise HTTPException(status_code=404, detail="Güncellenecek sipariş bulunamadı.")
    
    if db_siparis.fatura_id:
        raise HTTPException(status_code=400, detail="Faturaya dönüştürülmüş bir sipariş güncellenemez.")

    db.begin_nested()
    try:
        # Eski kalemleri sil
        db.query(semalar.SiparisKalemleri).filter(semalar.SiparisKalemleri.siparis_id == siparis_id).delete(synchronize_session=False)
        db.flush()

        # Yeni kalemleri ve toplamları hesapla
        toplam_tutar = 0.0
        db_kalemler = []
        for kalem in siparis.kalemler:
            iskontolu_bf_haric = kalem.birim_fiyat * (1 - kalem.iskonto_yuzde_1 / 100) * (1 - kalem.iskonto_yuzde_2 / 100)
            kalem_toplam_dahil = (kalem.miktar * iskontolu_bf_haric) * (1 + kalem.kdv_orani / 100)
            toplam_tutar += kalem_toplam_dahil
            
            db_kalemler.append(semalar.SiparisKalemleri(
                siparis_id=siparis_id, urun_id=kalem.urun_id, miktar=kalem.miktar, birim_fiyat=kalem.birim_fiyat,
                kdv_orani=kalem.kdv_orani, alis_fiyati_siparis_aninda=kalem.alis_fiyati_siparis_aninda,
                satis_fiyati_siparis_aninda=kalem.satis_fiyati_siparis_aninda,
                iskonto_yuzde_1=kalem.iskonto_yuzde_1, iskonto_yuzde_2=kalem.iskonto_yuzde_2
            ))
        db.add_all(db_kalemler)
        
        # Ana sipariş tablosunu güncelle
        db_siparis.siparis_no = siparis.siparis_no
        db_siparis.cari_id = siparis.cari_id
        db_siparis.durum = siparis.durum
        db_siparis.siparis_notlari = siparis.siparis_notlari
        db_siparis.teslimat_tarihi = siparis.teslimat_tarihi
        db_siparis.toplam_tutar = toplam_tutar
        db_siparis.son_guncelleyen_kullanici_id = 1 # Varsayılan kullanıcı
        
        db.commit()
        db.refresh(db_siparis)
        return db_siparis
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sipariş güncellenirken hata: {str(e)}")

@router.delete("/{siparis_id}", status_code=204)
def delete_siparis(siparis_id: int, db: Session = Depends(get_db)):
    """
    Bir siparişi ve kalemlerini siler. Faturaya dönüştürülmüşse silinemez.
    """
    db_siparis = db.query(semalar.Siparis).filter(semalar.Siparis.id == siparis_id).first()
    if not db_siparis:
        raise HTTPException(status_code=404, detail="Silinecek sipariş bulunamadı.")
        
    if db_siparis.fatura_id:
        raise HTTPException(status_code=400, detail="Faturaya dönüştürülmüş bir sipariş silinemez. Önce ilişkili faturayı silin.")
        
    db.begin_nested()
    try:
        db.query(semalar.SiparisKalemleri).filter(semalar.SiparisKalemleri.siparis_id == siparis_id).delete(synchronize_session=False)
        db.delete(db_siparis)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sipariş silinirken hata: {str(e)}")
        
    return