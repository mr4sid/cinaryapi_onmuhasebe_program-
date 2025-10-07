from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from .. import modeller, semalar, guvenlik
from ..veritabani import get_db
from typing import List, Optional, Any
from datetime import datetime, date
from sqlalchemy import String
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from hizmetler import FaturaService
import logging
from ..guvenlik import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stoklar", tags=["Stoklar"])


@router.post("/", response_model=modeller.StokRead)
def create_stok(
    stok: modeller.StokCreate, # KRİTİK DÜZELTME: Pydantic input şeması olarak modeller.StokCreate kullanıldı.
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME: Tipi modeller.KullaniciRead olarak düzeltildi.
    db: Session = Depends(get_db)
):
    try:
        # Pydantic'ten ORM modeline dönüştürme: Sadece mevcut alanlar dahil edilir, ID'ler hariç tutulur.
        stok_data = stok.model_dump(exclude={'kullanici_id', 'id'})
        
        # ORM modelini oluştur
        db_stok = modeller.Stok(**stok_data, kullanici_id=current_user.id)
        
        db.add(db_stok)
        db.flush() # ID'yi almak için
        
        # Stok hareketi eklenir (İlk Giriş) - Stok hareketi oluşturma mantığı düzeltildi.
        if db_stok.miktar and db_stok.miktar > 0:
            db_hareket = modeller.StokHareket(
                urun_id=db_stok.id, 
                tarih=datetime.now().date(), # Tarih eklendi
                islem_tipi=semalar.StokIslemTipiEnum.GIRIS, # Doğru Enum kullanıldı
                miktar=db_stok.miktar, 
                birim_fiyat=db_stok.alis_fiyati, # Alış fiyatı kullanıldı
                aciklama="İlk Stok Girişi (Manuel Oluşturma)", 
                kaynak=semalar.KaynakTipEnum.MANUEL, # Doğru Enum kullanıldı
                kaynak_id=None,
                onceki_stok=0.0, # İlk girişte 0.0
                sonraki_stok=db_stok.miktar,
                kullanici_id=current_user.id
            )
            db.add(db_hareket)
        
        db.commit()
        db.refresh(db_stok)
        
        # Pydantic modeline dönüştürerek döndür
        return modeller.StokRead.model_validate(db_stok, from_attributes=True)
    
    except IntegrityError as e:
        db.rollback()
        if "unique_kod" in str(e):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ürün kodu zaten mevcut.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Stok kaydı oluşturulurken veritabanı hatası: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Stok kaydı oluşturulurken beklenmedik hata: {str(e)}")

@router.get("/", response_model=modeller.StokListResponse)
def read_stoklar(
    skip: int = 0,
    limit: int = 25,
    arama: Optional[str] = None,
    aktif_durum: Optional[bool] = True,
    kritik_stok_altinda: Optional[bool] = False,
    kategori_id: Optional[int] = None,
    marka_id: Optional[int] = None,
    urun_grubu_id: Optional[int] = None,
    stokta_var: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # KRİTİK DÜZELTME: Tipi modeller.KullaniciRead olarak düzeltildi.
):
    # KRİTİK DÜZELTME: Sorgularda modeller.Stok kullanıldı.
    query = db.query(modeller.Stok).filter(modeller.Stok.kullanici_id == current_user.id)
    
    if arama:
        search_filter = or_(
            modeller.Stok.kod.ilike(f"%{arama}%"),
            modeller.Stok.ad.ilike(f"%{arama}%")
        )
        query = query.filter(search_filter)

    if aktif_durum is not None:
        query = query.filter(modeller.Stok.aktif == aktif_durum)

    if kritik_stok_altinda:
        query = query.filter(modeller.Stok.miktar <= modeller.Stok.min_stok_seviyesi)

    if kategori_id:
        query = query.filter(modeller.Stok.kategori_id == kategori_id)

    if marka_id:
        query = query.filter(modeller.Stok.marka_id == marka_id)

    if urun_grubu_id:
        query = query.filter(modeller.Stok.urun_grubu_id == urun_grubu_id)

    if stokta_var is not None:
        if stokta_var:
            query = query.filter(modeller.Stok.miktar > 0)
        else:
            query = query.filter(modeller.Stok.miktar <= 0)

    total_count = query.count()
    
    stoklar = query.offset(skip).limit(limit).all()
    
    return {"items": [
        modeller.StokRead.model_validate(s, from_attributes=True)
        for s in stoklar
    ], "total": total_count}

@router.get("/ozet", response_model=modeller.StokOzetResponse)
def get_stok_ozet(
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # KRİTİK DÜZELTME: Tipi modeller.KullaniciRead olarak düzeltildi.
):
    # KRİTİK DÜZELTME: Sorgularda modeller.Stok kullanıldı.
    query = db.query(modeller.Stok).filter(modeller.Stok.kullanici_id == current_user.id)
    
    toplam_miktar = query.with_entities(func.sum(modeller.Stok.miktar)).scalar() or 0
    toplam_alis_fiyati = query.with_entities(func.sum(modeller.Stok.alis_fiyati * modeller.Stok.miktar)).scalar() or 0
    toplam_satis_fiyati = query.with_entities(func.sum(modeller.Stok.satis_fiyati * modeller.Stok.miktar)).scalar() or 0
    
    toplam_urun_sayisi = query.filter(modeller.Stok.aktif == True).count()
    
    return {
        "toplam_urun_sayisi": toplam_urun_sayisi,
        "toplam_miktar": toplam_miktar,
        "toplam_maliyet": toplam_alis_fiyati,
        "toplam_satis_tutari": toplam_satis_fiyati
    }

@router.get("/{stok_id}", response_model=modeller.StokRead)
def read_stok(
    stok_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # KRİTİK DÜZELTME: Tipi modeller.KullaniciRead olarak düzeltildi.
):
    # KRİTİK DÜZELTME: Sorgularda modeller.Stok kullanıldı.
    stok = db.query(modeller.Stok).filter(
        modeller.Stok.id == stok_id,
        modeller.Stok.kullanici_id == current_user.id
    ).first()
    if not stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    
    stok_read_data = modeller.StokRead.model_validate(stok, from_attributes=True).model_dump() # from_attributes eklendi
    
    # İlişki kontrolü (Lazy loading ile çalışması beklenir, eğer ilişkiler kurulduysa)
    if stok.kategori:
        stok_read_data['kategori'] = modeller.UrunKategoriRead.model_validate(stok.kategori, from_attributes=True).model_dump()
    if stok.marka:
        stok_read_data['marka'] = modeller.UrunMarkaRead.model_validate(stok.marka, from_attributes=True).model_dump()
    if stok.urun_grubu:
        stok_read_data['urun_grubu'] = modeller.UrunGrubuRead.model_validate(stok.urun_grubu, from_attributes=True).model_dump()
    if stok.birim:
        stok_read_data['birim'] = modeller.UrunBirimiRead.model_validate(stok.birim, from_attributes=True).model_dump()
    if stok.mense_ulke:
        stok_read_data['mense_ulke'] = modeller.UlkeRead.model_validate(stok.mense_ulke, from_attributes=True).model_dump()
        
    return stok_read_data

@router.put("/{stok_id}", response_model=modeller.StokRead)
def update_stok(
    stok_id: int,
    stok: modeller.StokUpdate,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # KRİTİK DÜZELTME: Tipi modeller.KullaniciRead olarak düzeltildi.
):
    # KRİTİK DÜZELTME: Sorgularda modeller.Stok kullanıldı.
    db_stok = db.query(modeller.Stok).filter(
        modeller.Stok.id == stok_id,
        modeller.Stok.kullanici_id == current_user.id
    ).first()
    if not db_stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    for key, value in stok.model_dump(exclude_unset=True).items():
        setattr(db_stok, key, value)
    db.commit()
    db.refresh(db_stok)
    return db_stok

@router.delete("/{stok_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stok(
    stok_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # KRİTİK DÜZELTME: Tipi modeller.KullaniciRead olarak düzeltildi.
):
    # KRİTİK DÜZELTME: Sorgularda modeller.Stok kullanıldı.
    db_stok = db.query(modeller.Stok).filter(
        modeller.Stok.id == stok_id,
        modeller.Stok.kullanici_id == current_user.id
    ).first()
    if not db_stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    db.delete(db_stok)
    db.commit()
    return

@router.get("/{stok_id}/anlik_miktar", response_model=modeller.AnlikStokMiktariResponse)
def get_anlik_stok_miktari_endpoint(
    stok_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # KRİTİK DÜZELTME: Tipi modeller.KullaniciRead olarak düzeltildi.
):
    # KRİTİK DÜZELTME: Sorgularda modeller.Stok kullanıldı.
    stok = db.query(modeller.Stok).filter(
        modeller.Stok.id == stok_id,
        modeller.Stok.kullanici_id == current_user.id
    ).first()
    if not stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    
    return {"anlik_miktar": stok.miktar}

@router.post("/{stok_id}/hareket", response_model=modeller.StokHareketRead)
def create_stok_hareket(
    stok_id: int,
    hareket: modeller.StokHareketCreate,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # KRİTİK DÜZELTME: Tipi modeller.KullaniciRead olarak düzeltildi.
):
    # KRİTİK DÜZELTME: Sorgularda modeller.Stok kullanıldı.
    db_stok = db.query(modeller.Stok).filter(
        modeller.Stok.id == stok_id,
        modeller.Stok.kullanici_id == current_user.id
    ).first()
    if not db_stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı.")
    
    if hareket.miktar <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Miktar pozitif bir değer olmalıdır.")

    db.begin_nested()

    try:
        stok_degisim_net = 0.0
        # Enum'lar doğru olduğu için semalar.StokIslemTipiEnum kullanılabilir.
        if hareket.islem_tipi in [
            semalar.StokIslemTipiEnum.GIRIS,
            semalar.StokIslemTipiEnum.SAYIM_FAZLASI,
            semalar.StokIslemTipiEnum.SATIŞ_İADE,
            semalar.StokIslemTipiEnum.ALIŞ
        ]:
            stok_degisim_net = hareket.miktar
        elif hareket.islem_tipi in [
            semalar.StokIslemTipiEnum.CIKIS,
            semalar.StokIslemTipiEnum.SAYIM_EKSİĞİ,
            # semalar.StokIslemTipiEnum.ZAYIAT, # ZAYIAT Enum'da yok, bu yüzden kaldırıldı.
            semalar.StokIslemTipiEnum.SATIŞ,
            semalar.StokIslemTipiEnum.ALIŞ_İADE
        ]:
            stok_degisim_net = -hareket.miktar
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz işlem tipi.")
        
        onceki_stok_miktari = db_stok.miktar

        db_stok.miktar += stok_degisim_net
        db.add(db_stok)

        db_hareket = modeller.StokHareket(
            urun_id=stok_id,
            tarih=hareket.tarih,
            islem_tipi=hareket.islem_tipi,
            miktar=hareket.miktar,
            birim_fiyat=hareket.birim_fiyat,
            aciklama=hareket.aciklama,
            kaynak=semalar.KaynakTipEnum.MANUEL,
            kaynak_id=None,
            onceki_stok=onceki_stok_miktari,
            sonraki_stok=db_stok.miktar,
            kullanici_id=current_user.id
        )
        db.add(db_hareket)

        db.commit()
        db.refresh(db_hareket)
        return modeller.StokHareketRead.model_validate(db_hareket, from_attributes=True)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Stok hareketi oluşturulurken hata: {str(e)}")

@router.get("/{stok_id}/hareketler", response_model=modeller.StokHareketListResponse)
def get_stok_hareketleri_endpoint(
    stok_id: int,
    skip: int = 0,
    limit: int = 100,
    islem_tipi: str = Query(None),
    baslangic_tarih: str = Query(None),
    bitis_tarihi: str = Query(None),
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # KRİTİK DÜZELTME: Tipi modeller.KullaniciRead olarak düzeltildi.
):
    query = db.query(modeller.StokHareket).filter(
        modeller.StokHareket.urun_id == stok_id, # stok_id yerine urun_id kullanıldı (modeller.StokHareket'teki kolon adı)
        modeller.StokHareket.kullanici_id == current_user.id
    )

    if islem_tipi:
        query = query.filter(modeller.StokHareket.islem_tipi.cast(String) == islem_tipi)
    
    if baslangic_tarih:
        query = query.filter(modeller.StokHareket.tarih >= baslangic_tarih)
    
    if bitis_tarihi:
        query = query.filter(modeller.StokHareket.tarih <= bitis_tarihi)

    total_count = query.count()
    hareketler = query.order_by(modeller.StokHareket.tarih.desc(), modeller.StokHareket.id.desc()).offset(skip).limit(limit).all()

    return {"items": [
        modeller.StokHareketRead.model_validate(hareket, from_attributes=True)
        for hareket in hareketler
    ], "total": total_count}

@router.delete("/hareketler/{hareket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stok_hareket(
    hareket_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # KRİTİK DÜZELTME: Tipi modeller.KullaniciRead olarak düzeltildi.
):
    # KRİTİK DÜZELTME: Sorgularda modeller.StokHareket kullanıldı.
    db_hareket = db.query(modeller.StokHareket).filter(
        and_(
            modeller.StokHareket.id == hareket_id,
            modeller.StokHareket.kaynak == semalar.KaynakTipEnum.MANUEL,
            modeller.StokHareket.kullanici_id == current_user.id
        )
    ).first()

    if not db_hareket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Stok hareketi bulunamadı veya manuel olarak silinemez (otomatik oluşturulmuştur)."
        )
    
    stok = db.query(modeller.Stok).filter(
        modeller.Stok.id == db_hareket.urun_id, # stok_id yerine urun_id kullanıldı
        modeller.Stok.kullanici_id == current_user.id
    ).first()
    if stok:
        # Geri alma mantığı düzeltildi (GİRİŞ tersi ÇIKIŞ, ÇIKIŞ tersi GİRİŞ)
        if db_hareket.islem_tipi == semalar.StokIslemTipiEnum.GIRIS or db_hareket.islem_tipi == semalar.StokIslemTipiEnum.SAYIM_FAZLASI:
            stok.miktar -= db_hareket.miktar
        elif db_hareket.islem_tipi == semalar.StokIslemTipiEnum.CIKIS or db_hareket.islem_tipi == semalar.StokIslemTipiEnum.SAYIM_EKSİĞİ:
            stok.miktar += db_hareket.miktar
        db.add(stok)
    
    db.delete(db_hareket)
    db.commit()
    return {"detail": "Stok hareketi başarıyla silindi."}

@router.post("/bulk_upsert", response_model=modeller.TopluIslemSonucResponse)
def bulk_stok_upsert_endpoint(
    stok_listesi: List[modeller.StokCreate],
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # KRİTİK DÜZELTME: Tipi modeller.KullaniciRead olarak düzeltildi.
):
    # Atomik işlem için nested transaksiyon başlatıldı.
    db.begin_nested()
    try:
        yeni_eklenen = 0
        guncellenen = 0
        hata_veren = 0
        hatalar = []

        pozitif_kalemler = []
        negatif_kalemler = []
        
        for stok_data in stok_listesi:
            try:
                db_stok = db.query(modeller.Stok).filter(
                    modeller.Stok.kod == stok_data.kod,
                    modeller.Stok.kullanici_id == current_user.id
                ).first()
                
                if db_stok:
                    # Güvenlik kontrolü zaten filtrede yapılıyor, ek kontrol kaldırıldı.
                    for key, value in stok_data.model_dump(exclude_unset=True).items():
                        setattr(db_stok, key, value)
                    db.add(db_stok)
                    guncellenen += 1
                else:
                    # KRİTİK DÜZELTME: Yeni stok oluşturmada modeller.Stok kullanıldı.
                    yeni_stok = modeller.Stok(**stok_data.model_dump(), kullanici_id=current_user.id)
                    db.add(yeni_stok)
                    db.flush() # ID'yi almak için
                    yeni_eklenen += 1
                    
                    if yeni_stok.miktar != 0:
                        alis_fiyati_kdv_haric = yeni_stok.alis_fiyati

                        kalem_bilgisi = {
                            "urun_id": yeni_stok.id,
                            "miktar": yeni_stok.miktar,
                            "birim_fiyat": alis_fiyati_kdv_haric,
                            "kdv_orani": yeni_stok.kdv_orani,
                            "alis_fiyati_fatura_aninda": alis_fiyati_kdv_haric
                        }
                        
                        if kalem_bilgisi["miktar"] > 0:
                            pozitif_kalemler.append(kalem_bilgisi)
                        else:
                            negatif_kalemler.append(kalem_bilgisi)

            except Exception as e:
                hata_veren += 1
                hatalar.append(f"Stok kodu '{stok_data.kod}' işlenirken hata: {e}")

        # POZİTİF MİKTARLAR İÇİN TOPLU ALIŞ FATURASI VE HAREKETLERİ OLUŞTURMA
        if pozitif_kalemler:
            fatura_no=f"TOPLU-ALIS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            tarih=datetime.now().date() # datetime.date objesi kullanıldı.
            
            toplam_kdv_haric = sum(k['birim_fiyat'] * k['miktar'] for k in pozitif_kalemler)
            toplam_kdv_dahil = sum(k['birim_fiyat'] * (1 + k['kdv_orani'] / 100) * k['miktar'] for k in pozitif_kalemler)
            
            # KRİTİK DÜZELTME: Fatura oluşturmada modeller.Fatura kullanıldı.
            db_fatura = modeller.Fatura(
                fatura_no=fatura_no,
                fatura_turu=semalar.FaturaTuruEnum.ALIS,
                tarih=tarih,
                cari_id=1, # Varsayılan Cari ID
                cari_tip=semalar.CariTipiEnum.TEDARIKCI.value, # Cari Tipi eklendi
                odeme_turu=semalar.OdemeTuruEnum.ETKISIZ_FATURA,
                fatura_notlari="Toplu stok ekleme işlemiyle otomatik oluşturulan alış faturası.",
                toplam_kdv_haric=toplam_kdv_haric,
                toplam_kdv_dahil=toplam_kdv_dahil,
                genel_toplam=toplam_kdv_dahil,
                kullanici_id=current_user.id
            )
            db.add(db_fatura)
            db.flush()

            for kalem_bilgisi in pozitif_kalemler:
                # KRİTİK DÜZELTME: Fatura kalemi oluşturmada modeller.FaturaKalemi kullanıldı.
                db_kalem = modeller.FaturaKalemi(
                    fatura_id=db_fatura.id,
                    urun_id=kalem_bilgisi['urun_id'],
                    miktar=kalem_bilgisi['miktar'],
                    birim_fiyat=kalem_bilgisi['birim_fiyat'],
                    kdv_orani=kalem_bilgisi['kdv_orani'],
                    alis_fiyati_fatura_aninda=kalem_bilgisi['alis_fiyati_fatura_aninda']
                )
                db.add(db_kalem)
                
                # Stok Hareketi oluşturma
                db_stok = db.query(modeller.Stok).filter(modeller.Stok.id == kalem_bilgisi['urun_id']).first()
                if db_stok:
                    # KRİTİK DÜZELTME: Stok hareketi oluşturmada modeller.StokHareket kullanıldı.
                    db_stok_hareket = modeller.StokHareket(
                        urun_id=kalem_bilgisi['urun_id'],
                        tarih=db_fatura.tarih,
                        islem_tipi=semalar.StokIslemTipiEnum.ALIŞ,
                        miktar=kalem_bilgisi['miktar'],
                        birim_fiyat=kalem_bilgisi['birim_fiyat'],
                        aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})",
                        kaynak=semalar.KaynakTipEnum.FATURA,
                        kaynak_id=db_fatura.id,
                        onceki_stok=db_stok.miktar - kalem_bilgisi['miktar'], # Stok güncellendiği için doğru önceki miktar.
                        sonraki_stok=db_stok.miktar,
                        kullanici_id=current_user.id
                    )
                    db.add(db_stok_hareket)

        # NEGATİF MİKTARLAR İÇİN TOPLU ALIŞ İADE FATURASI VE HAREKETLERİ OLUŞTURMA
        if negatif_kalemler:
            fatura_no=f"TOPLU-ALIS-IADE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            tarih=datetime.now().date()
            
            toplam_kdv_haric_iade = sum(k['birim_fiyat'] * abs(k['miktar']) for k in negatif_kalemler)
            toplam_kdv_dahil_iade = sum(k['birim_fiyat'] * (1 + k['kdv_orani'] / 100) * abs(k['miktar']) for k in negatif_kalemler)
            
            # KRİTİK DÜZELTME: Fatura oluşturmada modeller.Fatura kullanıldı.
            db_fatura_iade = modeller.Fatura(
                fatura_no=fatura_no,
                fatura_turu=semalar.FaturaTuruEnum.ALIS_IADE,
                tarih=tarih,
                cari_id=1,
                cari_tip=semalar.CariTipiEnum.TEDARIKCI.value, # Cari Tipi eklendi
                odeme_turu=semalar.OdemeTuruEnum.ETKISIZ_FATURA,
                fatura_notlari="Toplu stok ekleme işlemiyle otomatik oluşturulan alış iade faturası.",
                toplam_kdv_haric=toplam_kdv_haric_iade,
                toplam_kdv_dahil=toplam_kdv_dahil_iade,
                genel_toplam=toplam_kdv_dahil_iade,
                kullanici_id=current_user.id
            )
            db.add(db_fatura_iade)
            db.flush()

            for kalem_bilgisi in negatif_kalemler:
                # KRİTİK DÜZELTME: Fatura kalemi oluşturmada modeller.FaturaKalemi kullanıldı.
                db_kalem = modeller.FaturaKalemi(
                    fatura_id=db_fatura_iade.id,
                    urun_id=kalem_bilgisi['urun_id'],
                    miktar=abs(kalem_bilgisi['miktar']),
                    birim_fiyat=kalem_bilgisi['birim_fiyat'],
                    kdv_orani=kalem_bilgisi['kdv_orani'],
                    alis_fiyati_fatura_aninda=kalem_bilgisi['alis_fiyati_fatura_aninda']
                )
                db.add(db_kalem)
                
                # Stok Hareketi oluşturma
                db_stok = db.query(modeller.Stok).filter(modeller.Stok.id == kalem_bilgisi['urun_id']).first()
                if db_stok:
                    # KRİTİK DÜZELTME: Stok hareketi oluşturmada modeller.StokHareket kullanıldı.
                    db_stok_hareket = modeller.StokHareket(
                        urun_id=kalem_bilgisi['urun_id'],
                        tarih=db_fatura_iade.tarih,
                        islem_tipi=semalar.StokIslemTipiEnum.ALIŞ_İADE,
                        miktar=abs(kalem_bilgisi['miktar']),
                        birim_fiyat=kalem_bilgisi['birim_fiyat'],
                        aciklama=f"{db_fatura_iade.fatura_no} nolu fatura ({db_fatura_iade.fatura_turu.value})",
                        kaynak=semalar.KaynakTipEnum.FATURA,
                        kaynak_id=db_fatura_iade.id,
                        onceki_stok=db_stok.miktar + abs(kalem_bilgisi['miktar']),
                        sonraki_stok=db_stok.miktar,
                        kullanici_id=current_user.id
                    )
                    db.add(db_stok_hareket)

        db.commit()
        
        toplam_islenen = yeni_eklenen + guncellenen + hata_veren
        
        return {
            "yeni_eklenen_sayisi": yeni_eklenen,
            "guncellenen_sayisi": guncellenen,
            "hata_sayisi": hata_veren,
            "hatalar": hatalar,
            "toplam_islenen": toplam_islenen
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Toplu stok ekleme/güncelleme sırasında kritik hata: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Toplu stok ekleme sırasında hata: {e}")
    
@router.get("/hareketler/", response_model=modeller.StokHareketListResponse)
def list_stok_hareketleri_endpoint(
    stok_id: Optional[int] = Query(None),
    islem_tipi: Optional[semalar.StokIslemTipiEnum] = Query(None),
    baslangic_tarihi: Optional[date] = Query(None),
    bitis_tarihi: Optional[date] = Query(None),
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    query = db.query(modeller.StokHareket).filter(modeller.StokHareket.kullanici_id == kullanici_id)

    if stok_id:
        query = query.filter(modeller.StokHareket.urun_id == stok_id)
    if islem_tipi:
        query = query.filter(modeller.StokHareket.islem_tipi == islem_tipi)
    if baslangic_tarihi:
        query = query.filter(modeller.StokHareket.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(modeller.StokHareket.tarih <= bitis_tarihi)

    total = query.count()
    hareketler = query.order_by(modeller.StokHareket.tarih.desc()).offset(skip).limit(limit).all()

    return {"items": [
        modeller.StokHareketRead.model_validate(hareket, from_attributes=True)
        for hareket in hareketler
    ], "total": total}