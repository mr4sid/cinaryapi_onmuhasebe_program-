from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from . import semalar, modeller # Düzeltildi
from .veritabani import get_db # Düzeltildi
from .config import SECRET_KEY, ALGORITHM # DÜZELTİLDİ: 'from ..' yerine 'from .' kullanıldı

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="dogrulama/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kimlik bilgileri doğrulanamadı",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        kullanici_adi: str = payload.get("sub")
        if kullanici_adi is None:
            raise credentials_exception
        token_data = modeller.TokenData(kullanici_adi=kullanici_adi)
    except JWTError:
        raise credentials_exception
    
    user = db.query(semalar.Kullanici).filter(semalar.Kullanici.kullanici_adi == token_data.kullanici_adi).first()
    if user is None:
        raise credentials_exception
    return user