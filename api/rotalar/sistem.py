# api/rotalar/sistem.py dosyasının TAMAMI

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from .. import modeller, semalar
from ..veritabani import get_db, reset_db_connection
from .. import guvenlik # KRİTİK: guvenlik modülü eklendi

router = APIRouter(prefix="/sistem", tags=["Sistem"])

@router.get("/varsayilan_cariler/perakende_musteri_id", response_model=modeller.DefaultIdResponse)
def get_perakende_musteri_id_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    musteri = db.query(semalar.Musteri).filter(semalar.Musteri.kod == "PERAKENDE_MUSTERI", semalar.Musteri.kullanici_id == kullanici_id).first()
    if not musteri:
        musteri = db.query(semalar.Musteri).filter(semalar.Musteri.id == 1, semalar.Musteri.kullanici_id == kullanici_id).first()
    if not musteri:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Varsayılan perakende müşteri bulunamadı. Lütfen bir perakende müşteri tanımlayın."
        )
    return {"id": musteri.id}

@router.get("/varsayilan_cariler/genel_tedarikci_id", response_model=modeller.DefaultIdResponse)
def get_genel_tedarikci_id_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.kod == "GENEL_TEDARIKCI", semalar.Tedarikci.kullanici_id == kullanici_id).first()
    if not tedarikci:
        tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.id == 1, semalar.Tedarikci.kullanici_id == kullanici_id).first()
    if not tedarikci:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Varsayılan genel tedarikçi bulunamadı. Lütfen bir genel tedarikçi tanımlayın."
        )
    return {"id": tedarikci.id}

@router.get("/varsayilan_kasa_banka/{odeme_turu}", response_model=modeller.KasaBankaRead)
def get_varsayilan_kasa_banka_endpoint(
    odeme_turu: str, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # JWT'den user ID geliyor
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id 
    hesap_tipi = None
    if odeme_turu.upper() == "NAKİT":
        hesap_tipi = semalar.KasaBankaTipiEnum.KASA
    elif odeme_turu.upper() in ["KART", "EFT/HAVALE", "ÇEK", "SENET"]:
        hesap_tipi = semalar.KasaBankaTipiEnum.BANKA
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Desteklenmeyen ödeme türü: {odeme_turu}. 'Nakit' veya 'Banka' olmalıdır."
        )

    varsayilan_kod = f"VARSAYILAN_{hesap_tipi.value}_{kullanici_id}"
    
    hesap = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.kod == varsayilan_kod, modeller.KasaBankaHesap.kullanici_id == kullanici_id).first()
    if not hesap:
        hesap = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.tip == hesap_tipi, modeller.KasaBankaHesap.kullanici_id == kullanici_id).first()
    if not hesap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Varsayılan {odeme_turu} hesabı bulunamadı. Lütfen bir {odeme_turu} hesabı tanımlayın."
        )
    return hesap

@router.get("/bilgiler", response_model=modeller.SirketRead)
def get_sirket_bilgileri_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    sirket_bilgisi = db.query(semalar.Sirket).filter(semalar.Sirket.kullanici_id == kullanici_id).first()
    if not sirket_bilgisi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Şirket bilgileri bulunamadı. Lütfen şirket bilgilerini kaydedin."
        )
    return sirket_bilgisi

@router.put("/bilgiler", response_model=modeller.SirketRead)
def update_sirket_bilgileri_endpoint(
    sirket_update: modeller.SirketCreate, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    sirket_bilgisi = db.query(semalar.Sirket).filter(semalar.Sirket.kullanici_id == kullanici_id).first()
    if not sirket_bilgisi:
        sirket_update.kullanici_id = kullanici_id
        db_sirket = semalar.Sirket(**sirket_update.model_dump())
        db.add(db_sirket)
    else:
        for key, value in sirket_update.model_dump(exclude_unset=True).items():
            setattr(sirket_bilgisi, key, value)
    
    db.commit()
    db.refresh(sirket_bilgisi)
    return sirket_bilgisi

@router.get("/next_fatura_number/{fatura_turu}", response_model=modeller.NextFaturaNoResponse)
def get_next_fatura_number_endpoint(
    fatura_turu: str, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    last_fatura = db.query(semalar.Fatura).filter(semalar.Fatura.fatura_turu == fatura_turu.upper(), semalar.Fatura.kullanici_id == kullanici_id) \
                                       .order_by(semalar.Fatura.fatura_no.desc()).first()

    prefix = ""
    if fatura_turu.upper() == "SATIŞ":
        prefix = "SF"
    elif fatura_turu.upper() == "ALIŞ":
        prefix = "AF"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz fatura türü. 'SATIŞ' veya 'ALIŞ' olmalıdır.")

    next_sequence = 1
    if last_fatura and last_fatura.fatura_no.startswith(prefix):
        try:
            current_sequence_str = last_fatura.fatura_no[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            pass

    next_fatura_no = f"{prefix}{next_sequence:09d}"
    return {"fatura_no": next_fatura_no}

@router.get("/next_musteri_code", response_model=dict)
def get_next_musteri_code_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    last_musteri = db.query(semalar.Musteri).filter(semalar.Musteri.kullanici_id == kullanici_id).order_by(semalar.Musteri.kod.desc()).first()

    prefix = "M"
    next_sequence = 1
    if last_musteri and last_musteri.kod and last_musteri.kod.startswith(prefix):
        try:
            current_sequence_str = last_musteri.kod[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            pass

    next_musteri_code = f"{prefix}{next_sequence:09d}"
    return {"next_code": next_musteri_code}

@router.get("/next_tedarikci_code", response_model=dict)
def get_next_tedarikci_code_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    last_tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.kullanici_id == kullanici_id).order_by(semalar.Tedarikci.kod.desc()).first()

    prefix = "T"
    next_sequence = 1
    if last_tedarikci and last_tedarikci.kod and last_tedarikci.kod.startswith(prefix):
        try:
            current_sequence_str = last_tedarikci.kod[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            pass

    next_tedarikci_code = f"{prefix}{next_sequence:09d}"
    return {"next_code": next_tedarikci_code}

@router.get("/next_stok_code", response_model=dict)
def get_next_stok_code_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    last_stok = db.query(semalar.Stok).filter(semalar.Stok.kullanici_id == kullanici_id).order_by(semalar.Stok.kod.desc()).first()

    prefix = "STK"
    next_sequence = 1
    if last_stok and last_stok.kod and last_stok.kod.startswith(prefix):
        try:
            current_sequence_str = last_stok.kod[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            pass

    next_stok_code = f"{prefix}{next_sequence:09d}"
    return {"next_code": next_stok_code}

@router.get("/next_siparis_kodu", response_model=modeller.NextSiparisKoduResponse)
def get_next_siparis_kodu_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    son_siparis = db.query(semalar.Siparis).filter(semalar.Siparis.kullanici_id == kullanici_id).order_by(semalar.Siparis.id.desc()).first()
    
    prefix = "S-"
    next_number = 1
    
    if son_siparis and son_siparis.siparis_no and son_siparis.siparis_no.startswith(prefix):
        try:
            last_number_str = son_siparis.siparis_no.split('-')[1]
            last_number = int(last_number_str)
            next_number = last_number + 1
        except (ValueError, IndexError):
            pass
            
    next_code = f"{prefix}{next_number:06d}"
    return {"next_code": next_code}

@router.get("/status", response_model=dict)
def get_sistem_status(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Veritabanı bağlantısı kurulamadı! Hata: {e}"
        )

@router.post("/veritabani_baglantilarini_kapat")
async def veritabani_baglantilarini_kapat():
    reset_db_connection()
    return PlainTextResponse("Veritabanı bağlantıları başarıyla kapatıldı.")

@router.get("/next_fatura_no", response_model=modeller.NextCodeResponse)
def get_next_fatura_no_endpoint(
    fatura_turu: semalar.FaturaTuruEnum = Query(..., description="Fatura türü (SATIŞ/ALIŞ)"),
    db: Session = Depends(get_db),
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    try:
        # Fatura numarasını bulmak için en son kaydı çek
        son_fatura = db.query(modeller.Fatura.fatura_no).filter(
            modeller.Fatura.kullanici_id == kullanici_id,
            modeller.Fatura.fatura_turu == fatura_turu
        ).order_by(modeller.Fatura.fatura_no.desc()).first()

        if son_fatura:
            son_no = son_fatura[0]
            try:
                # Metin ve sayı kısmını ayır
                import re
                sayi_match = re.search(r'\d+$', son_no)
                if sayi_match:
                    sayi_kismi = sayi_match.group(0)
                    metin_kismi = son_no[:sayi_match.start()]
                    
                    yeni_sayi = int(sayi_kismi) + 1
                    yeni_fatura_no = f"{metin_kismi}{yeni_sayi:0{len(sayi_kismi)}}" # Aynı basamak sayısını koru
                else:
                    # Sadece metin varsa, sonuna '1' ekle
                    yeni_fatura_no = f"{son_no}1"
            except Exception:
                yeni_fatura_no = f"{fatura_turu.value}-1"
        else:
            yeni_fatura_no = f"{fatura_turu.value}-1"

        return {"next_code": yeni_fatura_no}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fatura numarası alınırken hata: {e}")