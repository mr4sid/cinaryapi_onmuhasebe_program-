# api/rotalar/sistem.py Dosyasının tam içeriği.
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import modeller, semalar
from ..veritabani import get_db

router = APIRouter(prefix="/sistem", tags=["Sistem"])

@router.get("/varsayilan_cariler/perakende_musteri_id", response_model=modeller.DefaultIdResponse)
def get_perakende_musteri_id_endpoint(db: Session = Depends(get_db)):
    # ID'si 'PERAKENDE_MUSTERI' olan kodu ara, bulunamazsa ID'si 1 olanı ara.
    musteri = db.query(semalar.Musteri).filter(semalar.Musteri.kod == "PERAKENDE_MUSTERI").first()
    if not musteri:
        musteri = db.query(semalar.Musteri).filter(semalar.Musteri.id == 1).first()

    if not musteri:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Varsayılan perakende müşteri bulunamadı. Lütfen bir perakende müşteri tanımlayın."
        )
    return {"id": musteri.id}

@router.get("/varsayilan_cariler/genel_tedarikci_id", response_model=modeller.DefaultIdResponse)
def get_genel_tedarikci_id_endpoint(db: Session = Depends(get_db)):
    # ID'si 'GENEL_TEDARIKCI' olan kodu ara, bulunamazsa ID'si 1 olanı ara.
    tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.kod == "GENEL_TEDARIKCI").first()
    if not tedarikci:
        tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.id == 1).first()

    if not tedarikci:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Varsayılan genel tedarikçi bulunamadı. Lütfen bir genel tedarikçi tanımlayın."
        )
    return {"id": tedarikci.id}

@router.get("/varsayilan_kasa_banka/{odeme_turu}", response_model=modeller.KasaBankaRead)
def get_varsayilan_kasa_banka_endpoint(odeme_turu: str, db: Session = Depends(get_db)):
    # Ödeme türüne göre varsayılan hesap tipini belirle
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

    # Varsayılan hesap koduna göre ara
    varsayilan_kod = f"VARSAYILAN_{hesap_tipi.value}"
    hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.kod == varsayilan_kod).first()

    # Eğer varsayılan kodla bir hesap bulunamazsa, ilgili türdeki ilk hesabı al
    if not hesap:
        hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.tip == hesap_tipi).first()

    if not hesap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Varsayılan {odeme_turu} hesabı bulunamadı. Lütfen bir {odeme_turu} hesabı tanımlayın."
        )
    return hesap

@router.get("/bilgiler", response_model=modeller.SirketRead)
def get_sirket_bilgileri_endpoint(db: Session = Depends(get_db)):
    # Sirket bilgilerini çek
    sirket_bilgisi = db.query(semalar.Sirket).first()
    if not sirket_bilgisi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Şirket bilgileri bulunamadı. Lütfen şirket bilgilerini kaydedin."
        )
    return sirket_bilgisi

@router.put("/bilgiler", response_model=modeller.SirketRead)
def update_sirket_bilgileri_endpoint(sirket_update: modeller.SirketCreate, db: Session = Depends(get_db)):
    # Sirket bilgilerini güncelle veya oluştur
    sirket_bilgisi = db.query(semalar.Sirket).first()
    if not sirket_bilgisi:
        # Şirket bilgisi yoksa, yeni oluştur
        db_sirket = semalar.Sirket(**sirket_update.model_dump())
        db.add(db_sirket)
    else:
        # Varsa güncelle
        for key, value in sirket_update.model_dump(exclude_unset=True).items():
            setattr(sirket_bilgisi, key, value)
    
    db.commit()
    db.refresh(sirket_bilgisi)
    return sirket_bilgisi

@router.get("/next_fatura_number/{fatura_turu}", response_model=modeller.NextFaturaNoResponse)
def get_next_fatura_number_endpoint(fatura_turu: str, db: Session = Depends(get_db)):
    # Fatura türüne göre en yüksek fatura numarasını bul
    last_fatura = db.query(semalar.Fatura).filter(semalar.Fatura.fatura_turu == fatura_turu.upper()) \
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
            # Eğer numara formatı bozuksa, baştan başla
            pass

    next_fatura_no = f"{prefix}{next_sequence:09d}" # SF000000001 formatı
    return {"fatura_no": next_fatura_no}

@router.get("/next_musteri_code", response_model=dict)
def get_next_musteri_code_endpoint(db: Session = Depends(get_db)):
    last_musteri = db.query(semalar.Musteri).order_by(semalar.Musteri.kod.desc()).first()

    prefix = "M" # Prefix for customer codes
    next_sequence = 1
    if last_musteri and last_musteri.kod and last_musteri.kod.startswith(prefix):
        try:
            current_sequence_str = last_musteri.kod[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            # If format is broken, start from 1
            pass

    next_musteri_code = f"{prefix}{next_sequence:09d}" # M000000001 format
    return {"next_code": next_musteri_code}

@router.get("/next_tedarikci_code", response_model=dict)
def get_next_tedarikci_code_endpoint(db: Session = Depends(get_db)):
    last_tedarikci = db.query(semalar.Tedarikci).order_by(semalar.Tedarikci.kod.desc()).first()

    prefix = "T" # Prefix for supplier codes
    next_sequence = 1
    if last_tedarikci and last_tedarikci.kod and last_tedarikci.kod.startswith(prefix):
        try:
            current_sequence_str = last_tedarikci.kod[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            # If format is broken, start from 1
            pass

    next_tedarikci_code = f"{prefix}{next_sequence:09d}" # T000000001 format
    return {"next_code": next_tedarikci_code}

@router.get("/next_stok_code", response_model=dict)
def get_next_stok_code_endpoint(db: Session = Depends(get_db)):
    last_stok = db.query(semalar.Stok).order_by(semalar.Stok.kod.desc()).first()

    prefix = "STK" # Prefix for stock codes
    next_sequence = 1
    if last_stok and last_stok.kod and last_stok.kod.startswith(prefix):
        try:
            current_sequence_str = last_stok.kod[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            # If format is broken, start from 1
            pass

    next_stok_code = f"{prefix}{next_sequence:09d}" # STK000000001 format
    return {"next_code": next_stok_code}

@router.get("/next_siparis_kodu", response_model=modeller.NextSiparisKoduResponse)
def get_next_siparis_kodu_endpoint(db: Session = Depends(get_db)):
    """
    API'den bir sonraki sipariş kodunu oluşturup döner.
    Format: SIPARIS-000001 gibi.
    """
    son_siparis = db.query(semalar.Siparis).order_by(semalar.Siparis.id.desc()).first()
    
    prefix = "S-"
    next_number = 1
    
    if son_siparis and son_siparis.siparis_no.startswith(prefix):
        try:
            last_number_str = son_siparis.siparis_no.split('-')[1]
            last_number = int(last_number_str)
            next_number = last_number + 1
        except (ValueError, IndexError):
            pass
            
    next_code = f"{prefix}{next_number:06d}"
    return {"next_code": next_code}