# api/rotalar/kullanicilar.py dosyasının güncel içeriği
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import modeller, guvenlik # guvenlik eklendi
from ..veritabani import get_db
from ..guvenlik import get_current_user

router = APIRouter(prefix="/kullanicilar", tags=["Kullanıcılar"])

@router.get("/", response_model=modeller.KullaniciListResponse)
def read_kullanicilar(
    skip: int = 0, 
    limit: int = 1000, 
    db: Session = Depends(get_db),
    # JWT Kuralı: kullanici_id Query parametresi kaldırıldı, yetkilendirme eklendi
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # Model Tutarlılığı: semalar.Kullanici -> modeller.Kullanici
    # Tenancy/Firma ID filtresi eklendi
    base_query = db.query(modeller.Kullanici).filter(
        modeller.Kullanici.firma_id == current_user.firma_id
    )
    
    total_count = base_query.count()
    kullanicilar = base_query.offset(skip).limit(limit).all()
    
    return {"items": [modeller.KullaniciRead.model_validate(k, from_attributes=True) for k in kullanicilar], "total": total_count}

@router.get("/me", response_model=modeller.KullaniciRead)
def read_kullanici_me(
    # Model Tutarlılığı: current_user tipi ORM modelden (Kullanici) Pydantic modele (KullaniciRead) çevrildi
    current_user: modeller.KullaniciRead = Depends(get_current_user)
):
    return current_user

@router.get("/{kullanici_id}", response_model=modeller.KullaniciRead)
def read_kullanici(
    kullanici_id: int, 
    db: Session = Depends(get_db),
    # JWT Kuralı: Yetkilendirme eklendi
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # Model Tutarlılığı: semalar.Kullanici -> modeller.Kullanici
    # Tenancy/Firma ID filtresi eklendi
    kullanici = db.query(modeller.Kullanici).filter(
        modeller.Kullanici.id == kullanici_id,
        modeller.Kullanici.firma_id == current_user.firma_id
    ).first()
    
    if not kullanici:
        # 404 aynı zamanda yetki yok anlamına da gelebilir.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı veya yetkiniz yok")
        
    return modeller.KullaniciRead.model_validate(kullanici, from_attributes=True)

@router.put("/{kullanici_id}", response_model=modeller.KullaniciRead)
def update_kullanici(
    kullanici_id: int, 
    kullanici: modeller.KullaniciUpdate, 
    db: Session = Depends(get_db),
    # JWT Kuralı: Yetkilendirme eklendi
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # Model Tutarlılığı: semalar.Kullanici -> modeller.Kullanici
    # Tenancy/Firma ID filtresi eklendi
    db_kullanici = db.query(modeller.Kullanici).filter(
        modeller.Kullanici.id == kullanici_id,
        modeller.Kullanici.firma_id == current_user.firma_id
    ).first()
    
    if not db_kullanici:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı veya yetkiniz yok")
        
    for key, value in kullanici.model_dump(exclude_unset=True).items():
        setattr(db_kullanici, key, value)
        
    db.commit()
    db.refresh(db_kullanici)
    return db_kullanici

@router.delete("/{kullanici_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kullanici(
    kullanici_id: int, 
    db: Session = Depends(get_db),
    # JWT Kuralı: Yetkilendirme eklendi
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # Model Tutarlılığı: semalar.Kullanici -> modeller.Kullanici
    # Tenancy/Firma ID filtresi eklendi
    db_kullanici = db.query(modeller.Kullanici).filter(
        modeller.Kullanici.id == kullanici_id,
        modeller.Kullanici.firma_id == current_user.firma_id
    ).first()
    
    if not db_kullanici:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı veya yetkiniz yok")
        
    db.delete(db_kullanici)
    db.commit()
    return {"detail": "Kullanıcı silindi"}