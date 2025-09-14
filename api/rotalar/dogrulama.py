# api/rotalar/dogrulama.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from .. import modeller, semalar
from ..veritabani import get_db
from passlib.context import CryptContext

router = APIRouter(prefix="/dogrulama", tags=["Kimlik Doğrulama"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

@router.post("/login", response_model=modeller.Token)
def authenticate_user(user_login: modeller.KullaniciLogin, db: Session = Depends(get_db)):
    user = db.query(semalar.Kullanici).filter(semalar.Kullanici.kullanici_adi == user_login.kullanici_adi).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(user_login.sifre, user.hashed_sifre):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"access_token": user.kullanici_adi, "token_type": "bearer", "kullanici_id": user.id} # Yeni eklendi

@router.post("/register_temp", response_model=modeller.KullaniciRead)
def register_temporary_user(user_create: modeller.KullaniciCreate, db: Session = Depends(get_db)):
    db_user = db.query(semalar.Kullanici).filter(semalar.Kullanici.kullanici_adi == user_create.kullanici_adi).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kullanıcı adı zaten mevcut")
    
    hashed_password = hash_password(user_create.sifre)
    db_user = semalar.Kullanici(
        kullanici_adi=user_create.kullanici_adi,
        hashed_sifre=hashed_password,
        aktif=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user