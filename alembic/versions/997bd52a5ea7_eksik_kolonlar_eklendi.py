"""Eksik kolonlar eklendi

Revision ID: 997bd52a5ea7
Revises: 49d3f99d8555
Create Date: 2025-09-26 16:57:16.832156

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '997bd52a5ea7'
down_revision: Union[str, Sequence[str], None] = '49d3f99d8555'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    with op.batch_alter_table('cari_hareketler', schema=None) as batch_op:
        batch_op.alter_column('cari_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('cari_tip',
               existing_type=sa.VARCHAR(),
               type_=sa.Enum('MUSTERI', 'TEDARIKCI', name='caritipienum', create_type=False),
               nullable=True)
        batch_op.alter_column('tarih',
               existing_type=sa.DATE(),
               nullable=True)
        batch_op.alter_column('islem_turu',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('islem_yone',
               existing_type=postgresql.ENUM('GİRİŞ', 'ÇIKIŞ', 'BORC', 'ALACAK', name='islemyoneenum'),
               type_=sa.Enum('GIRIS', 'CIKIS', 'BORC', 'ALACAK', name='islemyoneenum', create_type=False),
               nullable=True)
        batch_op.alter_column('tutar',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
        batch_op.alter_column('kaynak',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('kullanici_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_cari_hareketler_cari_id'), ['cari_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_cari_hareketler_cari_tip'), ['cari_tip'], unique=False)
        batch_op.create_foreign_key(None, 'kullanicilar', ['olusturan_kullanici_id'], ['id'])
        batch_op.drop_column('olusturma_tarihi')

    with op.batch_alter_table('fatura_kalemleri', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iskonto_tipi', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('iskonto_degeri', sa.Float(), nullable=True))
        batch_op.alter_column('miktar',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
        batch_op.alter_column('birim_fiyat',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_fatura_kalemleri_fatura_id'), ['fatura_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_fatura_kalemleri_urun_id'), ['urun_id'], unique=False)
        batch_op.drop_column('kalem_toplam_kdv_dahil')
        batch_op.drop_column('olusturma_tarihi')
        batch_op.drop_column('kalem_toplam_kdv_haric')

    with op.batch_alter_table('faturalar', schema=None) as batch_op:
        batch_op.add_column(sa.Column('original_fatura_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('toplam_kdv_haric', sa.Float(), nullable=False))
        batch_op.add_column(sa.Column('toplam_kdv_dahil', sa.Float(), nullable=False))
        batch_op.add_column(sa.Column('olusturma_tarihi_saat', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('olusturan_kullanici_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('son_guncelleme_tarihi_saat', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('son_guncelleyen_kullanici_id', sa.Integer(), nullable=True))
        batch_op.alter_column('fatura_no',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('fatura_turu',
               existing_type=postgresql.ENUM('SATIŞ', 'ALIŞ', 'SATIŞ_İADE', 'ALIŞ_İADE', 'DEVİR_GİRİŞ', name='faturaturuenum'),
               type_=sa.Enum('SATIŞ', 'ALIŞ', 'SATIŞ_İADE', 'ALIŞ_İADE', 'DEVİR_GİRİŞ', name='faturaturuenum', create_type=False),
               nullable=True)
        batch_op.alter_column('tarih',
               existing_type=sa.DATE(),
               nullable=True)
        batch_op.alter_column('cari_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('odeme_turu',
               existing_type=postgresql.ENUM('NAKİT', 'KART', 'EFT_HAVALE', 'ÇEK', 'SENET', 'AÇIK_HESAP', 'ETKİSİZ_FATURA', name='odemeturuenum'),
               type_=sa.Enum('NAKİT', 'KART', 'EFT_HAVALE', 'ÇEK', 'SENET', 'AÇIK_HESAP', 'ETKİSİZ_FATURA', name='odemeturuenum', create_type=False),
               nullable=True)
        batch_op.alter_column('genel_toplam',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
        batch_op.alter_column('kullanici_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_faturalar_cari_id'), ['cari_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_faturalar_fatura_turu'), ['fatura_turu'], unique=False)
        batch_op.create_foreign_key(None, 'kullanicilar', ['olusturan_kullanici_id'], ['id'])
        batch_op.create_foreign_key(None, 'kullanicilar', ['son_guncelleyen_kullanici_id'], ['id'])
        batch_op.create_foreign_key(None, 'faturalar', ['original_fatura_id'], ['id'])
        batch_op.drop_column('olusturma_tarihi')
        batch_op.drop_column('toplam_kdv')
        batch_op.drop_column('toplam_tutar')
        batch_op.drop_column('odeme_durumu')
        batch_op.drop_column('cari_tip')

    with op.batch_alter_table('gelir_giderler', schema=None) as batch_op:
        batch_op.add_column(sa.Column('odeme_turu', sa.Enum('NAKIT', 'KART', 'EFT_HAVALE', 'CEK', 'SENET', 'ACIK_HESAP', 'ETKISIZ_FATURA', name='odemeturuenum', create_type=False), nullable=True))
        batch_op.add_column(sa.Column('cari_tip', sa.Enum('MUSTERI', 'TEDARIKCI', name='caritipienum', create_type=False), nullable=True))
        batch_op.add_column(sa.Column('gelir_siniflandirma_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('gider_siniflandirma_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('olusturma_tarihi_saat', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('olusturan_kullanici_id', sa.Integer(), nullable=True))
        batch_op.alter_column('tarih',
               existing_type=sa.DATE(),
               nullable=True)
        batch_op.alter_column('tip',
               existing_type=postgresql.ENUM('GELİR', 'GİDER', name='gelirgidertipenum'),
               type_=sa.Enum('GELİR', 'GİDER', name='gelirgidertipenum', create_type=False),
               nullable=True)
        batch_op.alter_column('aciklama',
               existing_type=sa.TEXT(),
               nullable=True)
        batch_op.alter_column('tutar',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
        batch_op.alter_column('kullanici_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_gelir_giderler_tip'), ['tip'], unique=False)
        batch_op.create_foreign_key(None, 'gider_siniflandirmalari', ['gider_siniflandirma_id'], ['id'])
        batch_op.create_foreign_key(None, 'gelir_siniflandirmalari', ['gelir_siniflandirma_id'], ['id'])
        batch_op.create_foreign_key(None, 'kullanicilar', ['olusturan_kullanici_id'], ['id'])
        batch_op.drop_column('kaynak')
        batch_op.drop_column('kaynak_id')
        batch_op.drop_column('olusturma_tarihi')

    with op.batch_alter_table('gelir_siniflandirmalari', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_gelir_siniflandirmalari_ad'), ['ad'], unique=True)
        batch_op.create_index(batch_op.f('ix_gelir_siniflandirmalari_id'), ['id'], unique=False)

    with op.batch_alter_table('gider_siniflandirmalari', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_gider_siniflandirmalari_ad'), ['ad'], unique=True)
        batch_op.create_index(batch_op.f('ix_gider_siniflandirmalari_id'), ['id'], unique=False)

    with op.batch_alter_table('kasalar_bankalar', schema=None) as batch_op:
        batch_op.add_column(sa.Column('kod', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('sube_adi', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('varsayilan_odeme_turu', sa.String(), nullable=True))
        batch_op.alter_column('hesap_adi',
               existing_type=sa.VARCHAR(length=100),
               nullable=True)
        batch_op.alter_column('tip',
               existing_type=postgresql.ENUM('KASA', 'BANKA', name='kasabankatipienum'),
               type_=sa.String(),
               nullable=True)
        batch_op.drop_index(batch_op.f('ix_kasalar_bankalar_hesap_no'))
        batch_op.drop_index(batch_op.f('ix_kasalar_bankalar_iban'))
        batch_op.drop_index(batch_op.f('ix_kasalar_bankalar_hesap_adi'))
        batch_op.create_index(batch_op.f('ix_kasalar_bankalar_hesap_adi'), ['hesap_adi'], unique=False)
        batch_op.create_index(batch_op.f('ix_kasalar_bankalar_kod'), ['kod'], unique=True)
        batch_op.drop_constraint(batch_op.f('kasalar_bankalar_kullanici_id_fkey'), type_='foreignkey')
        batch_op.drop_column('kullanici_id')
        batch_op.drop_column('swift_kodu')
        batch_op.drop_column('iban')

    with op.batch_alter_table('kullanicilar', schema=None) as batch_op:
        batch_op.alter_column('kullanici_adi',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)

    with op.batch_alter_table('musteriler', schema=None) as batch_op:
        batch_op.alter_column('kod',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('adres',
               existing_type=sa.VARCHAR(length=255),
               type_=sa.Text(),
               existing_nullable=True)
        batch_op.alter_column('kullanici_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.drop_column('email')

    with op.batch_alter_table('siparis_kalemleri', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iskonto_tipi', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('iskonto_degeri', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('alis_fiyati_siparis_aninda', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('satis_fiyati_siparis_aninda', sa.Float(), nullable=True))
        batch_op.create_index(batch_op.f('ix_siparis_kalemleri_siparis_id'), ['siparis_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_siparis_kalemleri_urun_id'), ['urun_id'], unique=False)
        batch_op.drop_column('toplam_tutar')
        batch_op.drop_column('birim_fiyat_kdv_haric')
        batch_op.drop_column('olusturma_tarihi')

    with op.batch_alter_table('siparisler', schema=None) as batch_op:
        batch_op.add_column(sa.Column('genel_iskonto_tipi', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('genel_iskonto_degeri', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('fatura_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('olusturma_tarihi_saat', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('olusturan_kullanici_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('son_guncelleme_tarihi_saat', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('son_guncelleyen_kullanici_id', sa.Integer(), nullable=True))
        batch_op.alter_column('siparis_no',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('siparis_turu',
               existing_type=postgresql.ENUM('SATIŞ_SIPARIS', 'ALIŞ_SIPARIS', name='siparisturuenum'),
               type_=sa.Enum('SATIŞ_SIPARIS', 'ALIŞ_SIPARIS', name='siparisturuenum', create_type=False),
               nullable=True)
        batch_op.alter_column('durum',
               existing_type=postgresql.ENUM('BEKLEMEDE', 'TAMAMLANDI', 'KISMİ_TESLIMAT', 'İPTAL_EDİLDİ', 'FATURALAŞTIRILDI', name='siparisdurumenum'),
               type_=sa.Enum('BEKLEMEDE', 'TAMAMLANDI', 'KISMİ_TESLIMAT', 'İPTAL_EDİLDİ', 'FATURALAŞTIRILDI', name='siparisdurumenum', create_type=False),
               nullable=True)
        batch_op.alter_column('tarih',
               existing_type=sa.DATE(),
               nullable=True)
        batch_op.alter_column('cari_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('cari_tip',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.Enum('MUSTERI', 'TEDARIKCI', name='caritipienum', create_type=False),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_siparisler_cari_id'), ['cari_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_siparisler_cari_tip'), ['cari_tip'], unique=False)
        batch_op.create_index(batch_op.f('ix_siparisler_siparis_turu'), ['siparis_turu'], unique=False)
        batch_op.drop_constraint(batch_op.f('siparisler_kullanici_id_fkey'), type_='foreignkey')
        batch_op.create_foreign_key(None, 'kullanicilar', ['olusturan_kullanici_id'], ['id'])
        batch_op.create_foreign_key(None, 'faturalar', ['fatura_id'], ['id'])
        batch_op.create_foreign_key(None, 'kullanicilar', ['son_guncelleyen_kullanici_id'], ['id'])
        batch_op.drop_column('kullanici_id')
        batch_op.drop_column('olusturma_tarihi')
        batch_op.drop_column('genel_toplam')

    with op.batch_alter_table('sirketler', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sirketler_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sirketler_sirket_adi'), ['sirket_adi'], unique=False)

    with op.batch_alter_table('stok_hareketleri', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stok_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('birim_fiyat', sa.Float(), nullable=True))
        batch_op.alter_column('tarih',
               existing_type=sa.DATE(),
               nullable=True)
        batch_op.alter_column('islem_tipi',
               existing_type=postgresql.ENUM('GİRİŞ', 'ÇIKIŞ', 'SAYIM_FAZLASI', 'SAYIM_EKSİĞİ', 'SATIŞ', 'ALIŞ', 'SATIŞ_İADE', 'ALIŞ_İADE', 'KONSİNYE_GİRİŞ', 'KONSİNYE_ÇIKIŞ', name='stokislemtipienum'),
               nullable=True)
        batch_op.alter_column('miktar',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
        batch_op.alter_column('kaynak',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('onceki_stok',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
        batch_op.alter_column('sonraki_stok',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_stok_hareketleri_stok_id'), ['stok_id'], unique=False)
        batch_op.drop_constraint(batch_op.f('stok_hareketleri_urun_id_fkey'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('stok_hareketleri_kullanici_id_fkey'), type_='foreignkey')
        batch_op.create_foreign_key(None, 'stoklar', ['stok_id'], ['id'])
        batch_op.drop_column('urun_id')
        batch_op.drop_column('kullanici_id')
        batch_op.drop_column('olusturma_tarihi')

    with op.batch_alter_table('stoklar', schema=None) as batch_op:
        batch_op.alter_column('kod',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('ad',
               existing_type=sa.VARCHAR(length=200),
               nullable=True)
        batch_op.alter_column('kullanici_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.drop_constraint(batch_op.f('stoklar_birim_id_fkey'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('stoklar_kategori_id_fkey'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('stoklar_marka_id_fkey'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('stoklar_urun_grubu_id_fkey'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('stoklar_mense_id_fkey'), type_='foreignkey')
        batch_op.create_foreign_key(None, 'ulkeler', ['mense_id'], ['id'])
        batch_op.create_foreign_key(None, 'urun_gruplari', ['urun_grubu_id'], ['id'])
        batch_op.create_foreign_key(None, 'urun_birimleri', ['birim_id'], ['id'])
        batch_op.create_foreign_key(None, 'urun_kategorileri', ['kategori_id'], ['id'])
        batch_op.create_foreign_key(None, 'urun_markalari', ['marka_id'], ['id'])

    with op.batch_alter_table('tedarikciler', schema=None) as batch_op:
        batch_op.alter_column('kod',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('adres',
               existing_type=sa.VARCHAR(length=255),
               type_=sa.Text(),
               existing_nullable=True)
        batch_op.alter_column('kullanici_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.drop_column('email')

    with op.batch_alter_table('ulkeler', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ulkeler_ad'), ['ad'], unique=True)
        batch_op.create_index(batch_op.f('ix_ulkeler_id'), ['id'], unique=False)

    with op.batch_alter_table('urun_birimleri', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_urun_birimleri_ad'), ['ad'], unique=True)
        batch_op.create_index(batch_op.f('ix_urun_birimleri_id'), ['id'], unique=False)

    with op.batch_alter_table('urun_gruplari', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_urun_gruplari_ad'), ['ad'], unique=True)
        batch_op.create_index(batch_op.f('ix_urun_gruplari_id'), ['id'], unique=False)

    with op.batch_alter_table('urun_kategorileri', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_urun_kategorileri_ad'), ['ad'], unique=True)
        batch_op.create_index(batch_op.f('ix_urun_kategorileri_id'), ['id'], unique=False)

    with op.batch_alter_table('urun_markalari', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_urun_markalari_ad'), ['ad'], unique=True)
        batch_op.create_index(batch_op.f('ix_urun_markalari_id'), ['id'], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('urun_markalari', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_urun_markalari_id'))
        batch_op.drop_index(batch_op.f('ix_urun_markalari_ad'))

    with op.batch_alter_table('urun_kategorileri', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_urun_kategorileri_id'))
        batch_op.drop_index(batch_op.f('ix_urun_kategorileri_ad'))

    with op.batch_alter_table('urun_gruplari', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_urun_gruplari_id'))
        batch_op.drop_index(batch_op.f('ix_urun_gruplari_ad'))

    with op.batch_alter_table('urun_birimleri', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_urun_birimleri_id'))
        batch_op.drop_index(batch_op.f('ix_urun_birimleri_ad'))

    with op.batch_alter_table('ulkeler', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ulkeler_id'))
        batch_op.drop_index(batch_op.f('ix_ulkeler_ad'))

    with op.batch_alter_table('tedarikciler', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
        batch_op.alter_column('kullanici_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('adres',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=255),
               existing_nullable=True)
        batch_op.alter_column('kod',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)

    with op.batch_alter_table('stoklar', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('stoklar_mense_id_fkey'), 'urun_nitelikleri', ['mense_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('stoklar_urun_grubu_id_fkey'), 'urun_nitelikleri', ['urun_grubu_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('stoklar_marka_id_fkey'), 'urun_nitelikleri', ['marka_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('stoklar_kategori_id_fkey'), 'urun_nitelikleri', ['kategori_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('stoklar_birim_id_fkey'), 'urun_nitelikleri', ['birim_id'], ['id'])
        batch_op.alter_column('kullanici_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('ad',
               existing_type=sa.VARCHAR(length=200),
               nullable=False)
        batch_op.alter_column('kod',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)

    with op.batch_alter_table('stok_hareketleri', schema=None) as batch_op:
        batch_op.add_column(sa.Column('olusturma_tarihi', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('kullanici_id', sa.INTEGER(), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('urun_id', sa.INTEGER(), autoincrement=False, nullable=False))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('stok_hareketleri_kullanici_id_fkey'), 'kullanicilar', ['kullanici_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('stok_hareketleri_urun_id_fkey'), 'stoklar', ['urun_id'], ['id'])
        batch_op.drop_index(batch_op.f('ix_stok_hareketleri_stok_id'))
        batch_op.alter_column('sonraki_stok',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
        batch_op.alter_column('onceki_stok',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
        batch_op.alter_column('kaynak',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)
        batch_op.alter_column('miktar',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
        batch_op.alter_column('islem_tipi',
               existing_type=postgresql.ENUM('GİRİŞ', 'ÇIKIŞ', 'SAYIM_FAZLASI', 'SAYIM_EKSİĞİ', 'SATIŞ', 'ALIŞ', 'SATIŞ_İADE', 'ALIŞ_İADE', 'KONSİNYE_GİRİŞ', 'KONSİNYE_ÇIKIŞ', name='stokislemtipienum'),
               nullable=False)
        batch_op.alter_column('tarih',
               existing_type=sa.DATE(),
               nullable=False)
        batch_op.drop_column('birim_fiyat')
        batch_op.drop_column('stok_id')

    with op.batch_alter_table('sirketler', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sirketler_sirket_adi'))
        batch_op.drop_index(batch_op.f('ix_sirketler_id'))

    with op.batch_alter_table('siparisler', schema=None) as batch_op:
        batch_op.add_column(sa.Column('genel_toplam', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('olusturma_tarihi', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('kullanici_id', sa.INTEGER(), autoincrement=False, nullable=False))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('siparisler_kullanici_id_fkey'), 'kullanicilar', ['kullanici_id'], ['id'])
        batch_op.drop_index(batch_op.f('ix_siparisler_siparis_turu'))
        batch_op.drop_index(batch_op.f('ix_siparisler_cari_tip'))
        batch_op.drop_index(batch_op.f('ix_siparisler_cari_id'))
        batch_op.alter_column('cari_tip',
               existing_type=sa.Enum('MUSTERI', 'TEDARIKCI', name='caritipienum'),
               type_=sa.VARCHAR(length=20),
               nullable=False)
        batch_op.alter_column('cari_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('tarih',
               existing_type=sa.DATE(),
               nullable=False)
        batch_op.alter_column('durum',
               existing_type=postgresql.ENUM('BEKLEMEDE', 'TAMAMLANDI', 'KISMİ_TESLIMAT', 'İPTAL_EDİLDİ', 'FATURALAŞTIRILDI', name='siparisdurumenum'),
               nullable=False)
        batch_op.alter_column('siparis_turu',
               existing_type=postgresql.ENUM('SATIŞ_SIPARIS', 'ALIŞ_SIPARIS', name='siparisturuenum'),
               nullable=False)
        batch_op.alter_column('siparis_no',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)
        batch_op.drop_column('son_guncelleyen_kullanici_id')
        batch_op.drop_column('son_guncelleme_tarihi_saat')
        batch_op.drop_column('olusturan_kullanici_id')
        batch_op.drop_column('olusturma_tarihi_saat')
        batch_op.drop_column('fatura_id')
        batch_op.drop_column('genel_iskonto_degeri')
        batch_op.drop_column('genel_iskonto_tipi')

    with op.batch_alter_table('siparis_kalemleri', schema=None) as batch_op:
        batch_op.add_column(sa.Column('olusturma_tarihi', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('birim_fiyat_kdv_haric', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('toplam_tutar', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
        batch_op.drop_index(batch_op.f('ix_siparis_kalemleri_urun_id'))
        batch_op.drop_index(batch_op.f('ix_siparis_kalemleri_siparis_id'))
        batch_op.drop_column('satis_fiyati_siparis_aninda')
        batch_op.drop_column('alis_fiyati_siparis_aninda')
        batch_op.drop_column('iskonto_degeri')
        batch_op.drop_column('iskonto_tipi')

    with op.batch_alter_table('musteriler', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
        batch_op.alter_column('kullanici_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('adres',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=255),
               existing_nullable=True)
        batch_op.alter_column('kod',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)

    with op.batch_alter_table('kullanicilar', schema=None) as batch_op:
        batch_op.alter_column('kullanici_adi',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)

    with op.batch_alter_table('kasalar_bankalar', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iban', sa.VARCHAR(length=50), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('swift_kodu', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('kullanici_id', sa.INTEGER(), autoincrement=False, nullable=False))
        batch_op.create_foreign_key(batch_op.f('kasalar_bankalar_kullanici_id_fkey'), 'kullanicilar', ['kullanici_id'], ['id'])
        batch_op.drop_index(batch_op.f('ix_kasalar_bankalar_kod'))
        batch_op.drop_index(batch_op.f('ix_kasalar_bankalar_hesap_adi'))
        batch_op.create_index(batch_op.f('ix_kasalar_bankalar_hesap_adi'), ['hesap_adi'], unique=True)
        batch_op.create_index(batch_op.f('ix_kasalar_bankalar_iban'), ['iban'], unique=True)
        batch_op.create_index(batch_op.f('ix_kasalar_bankalar_hesap_no'), ['hesap_no'], unique=True)
        batch_op.alter_column('tip',
               existing_type=sa.String(),
               type_=postgresql.ENUM('KASA', 'BANKA', name='kasabankatipienum'),
               nullable=False)
        batch_op.alter_column('hesap_adi',
               existing_type=sa.VARCHAR(length=100),
               nullable=False)
        batch_op.drop_column('varsayilan_odeme_turu')
        batch_op.drop_column('sube_adi')
        batch_op.drop_column('kod')

    with op.batch_alter_table('gider_siniflandirmalari', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gider_siniflandirmalari_id'))
        batch_op.drop_index(batch_op.f('ix_gider_siniflandirmalari_ad'))

    with op.batch_alter_table('gelir_siniflandirmalari', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gelir_siniflandirmalari_id'))
        batch_op.drop_index(batch_op.f('ix_gelir_siniflandirmalari_ad'))

    with op.batch_alter_table('gelir_giderler', schema=None) as batch_op:
        batch_op.add_column(sa.Column('olusturma_tarihi', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('kaynak_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('kaynak', sa.VARCHAR(length=50), autoincrement=False, nullable=False))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_gelir_giderler_tip'))
        batch_op.alter_column('kullanici_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('tutar',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
        batch_op.alter_column('aciklama',
               existing_type=sa.TEXT(),
               nullable=False)
        batch_op.alter_column('tip',
               existing_type=postgresql.ENUM('GELİR', 'GİDER', name='gelirgidertipenum'),
               nullable=False)
        batch_op.alter_column('tarih',
               existing_type=sa.DATE(),
               nullable=False)
        batch_op.drop_column('olusturan_kullanici_id')
        batch_op.drop_column('olusturma_tarihi_saat')
        batch_op.drop_column('gider_siniflandirma_id')
        batch_op.drop_column('gelir_siniflandirma_id')
        batch_op.drop_column('cari_tip')
        batch_op.drop_column('odeme_turu')

    with op.batch_alter_table('faturalar', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cari_tip', sa.VARCHAR(length=20), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('odeme_durumu', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('toplam_tutar', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('toplam_kdv', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('olusturma_tarihi', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_faturalar_fatura_turu'))
        batch_op.drop_index(batch_op.f('ix_faturalar_cari_id'))
        batch_op.alter_column('kullanici_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('genel_toplam',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
        batch_op.alter_column('odeme_turu',
               existing_type=postgresql.ENUM('NAKİT', 'KART', 'EFT_HAVALE', 'ÇEK', 'SENET', 'AÇIK_HESAP', 'ETKİSİZ_FATURA', name='odemeturuenum'),
               nullable=False)
        batch_op.alter_column('cari_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('tarih',
               existing_type=sa.DATE(),
               nullable=False)
        batch_op.alter_column('fatura_turu',
               existing_type=postgresql.ENUM('SATIŞ', 'ALIŞ', 'SATIŞ_İADE', 'ALIŞ_İADE', 'DEVİR_GİRİŞ', name='faturaturuenum'),
               nullable=False)
        batch_op.alter_column('fatura_no',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)
        batch_op.drop_column('son_guncelleyen_kullanici_id')
        batch_op.drop_column('son_guncelleme_tarihi_saat')
        batch_op.drop_column('olusturan_kullanici_id')
        batch_op.drop_column('olusturma_tarihi_saat')
        batch_op.drop_column('toplam_kdv_dahil')
        batch_op.drop_column('toplam_kdv_haric')
        batch_op.drop_column('original_fatura_id')

    with op.batch_alter_table('fatura_kalemleri', schema=None) as batch_op:
        batch_op.add_column(sa.Column('kalem_toplam_kdv_haric', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('olusturma_tarihi', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('kalem_toplam_kdv_dahil', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
        batch_op.drop_index(batch_op.f('ix_fatura_kalemleri_urun_id'))
        batch_op.drop_index(batch_op.f('ix_fatura_kalemleri_fatura_id'))
        batch_op.alter_column('birim_fiyat',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
        batch_op.alter_column('miktar',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
        batch_op.drop_column('iskonto_degeri')
        batch_op.drop_column('iskonto_tipi')

    with op.batch_alter_table('cari_hareketler', schema=None) as batch_op:
        batch_op.add_column(sa.Column('olusturma_tarihi', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_cari_hareketler_cari_tip'))
        batch_op.drop_index(batch_op.f('ix_cari_hareketler_cari_id'))
        batch_op.alter_column('kullanici_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('kaynak',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)
        batch_op.alter_column('tutar',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
        batch_op.alter_column('islem_yone',
               existing_type=postgresql.ENUM('GİRİŞ', 'ÇIKIŞ', 'BORC', 'ALACAK', name='islemyoneenum'),
               nullable=False)
        batch_op.alter_column('islem_turu',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)
        batch_op.alter_column('tarih',
               existing_type=sa.DATE(),
               nullable=False)
        batch_op.alter_column('cari_tip',
               existing_type=sa.Enum('MUSTERI', 'TEDARIKCI', name='caritipienum'),
               type_=sa.VARCHAR(),
               nullable=False)
        batch_op.alter_column('cari_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.drop_column('olusturan_kullanici_id')
        batch_op.drop_column('olusturma_tarihi_saat')
        batch_op.drop_column('vade_tarihi')

    op.create_table('sirket_ayarlari',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('ayar_adi', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('ayar_degeri', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('kullanici_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['kullanici_id'], ['kullanicilar.id'], name=op.f('sirket_ayarlari_kullanici_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('sirket_ayarlari_pkey')),
    sa.UniqueConstraint('kullanici_id', name=op.f('sirket_ayarlari_kullanici_id_key'))
    )
    with op.batch_alter_table('sirket_ayarlari', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sirket_ayarlari_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sirket_ayarlari_ayar_adi'), ['ayar_adi'], unique=True)

    op.create_table('nitelikler',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('tip', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('ad', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('aciklama', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('aktif_durum', sa.BOOLEAN(), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('nitelikler_pkey'))
    )
    with op.batch_alter_table('nitelikler', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nitelikler_tip'), ['tip'], unique=False)
        batch_op.create_index(batch_op.f('ix_nitelikler_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nitelikler_ad'), ['ad'], unique=True)

    op.create_table('urun_nitelikleri',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('ad', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('nitelik_tipi', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('kullanici_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['kullanici_id'], ['kullanicilar.id'], name=op.f('urun_nitelikleri_kullanici_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('urun_nitelikleri_pkey'))
    )
    with op.batch_alter_table('urun_nitelikleri', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_urun_nitelikleri_id'), ['id'], unique=False)

    op.create_table('sirket_bilgileri',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('sirket_adi', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('adres', sa.VARCHAR(length=200), autoincrement=False, nullable=True),
    sa.Column('telefon', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    sa.Column('email', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('vergi_dairesi', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('vergi_no', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    sa.Column('kullanici_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['kullanici_id'], ['kullanicilar.id'], name=op.f('sirket_bilgileri_kullanici_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('sirket_bilgileri_pkey')),
    sa.UniqueConstraint('kullanici_id', name=op.f('sirket_bilgileri_kullanici_id_key'))
    )
    with op.batch_alter_table('sirket_bilgileri', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sirket_bilgileri_id'), ['id'], unique=False)

    op.create_table('senkronizasyon_kuyrugu',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('kaynak_tablo', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('kaynak_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('islem_tipi', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('veri', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('islem_tarihi', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('senkronize_edildi', sa.BOOLEAN(), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('senkronizasyon_kuyrugu_pkey'))
    )
    with op.batch_alter_table('senkronizasyon_kuyrugu', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_senkronizasyon_kuyrugu_id'), ['id'], unique=False)

    op.create_table('cari_hesaplar',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('cari_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('cari_tip', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
    sa.Column('bakiye', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('cari_hesaplar_pkey'))
    )
    with op.batch_alter_table('cari_hesaplar', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cari_hesaplar_id'), ['id'], unique=False)

    # ### end Alembic commands ###
