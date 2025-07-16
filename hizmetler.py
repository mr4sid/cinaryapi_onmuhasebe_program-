import logging
import traceback
from datetime import datetime
import sqlite3
import os

# hizmetler.py
import logging
import traceback
from datetime import datetime
import sqlite3
import os

class FaturaService:
    def __init__(self, db_manager):
        self.db = db_manager

    def fatura_olustur(self, fatura_no, fatura_tarihi, tip, cari_id, kalemler, odeme_turu, kasa_banka_id=None, misafir_adi=None, fatura_notlari=None, vade_tarihi=None, genel_iskonto_tipi='YOK', genel_iskonto_degeri=0.0, original_fatura_id=None, manage_transaction=True):
        if manage_transaction:
            self.db.conn.execute("BEGIN TRANSACTION")
        
        try:
            is_perakende_satis = (tip == self.db.FATURA_TIP_SATIS and self.db.perakende_musteri_id is not None and str(cari_id) == str(self.db.perakende_musteri_id))
            if is_perakende_satis and odeme_turu == self.db.ODEME_TURU_ACIK_HESAP:
                raise ValueError("Perakende satışlarda 'AÇIK HESAP' ödeme türü kullanılamaz.")

            self.db.c.execute("SELECT COUNT(*) FROM faturalar WHERE fatura_no = ?", (fatura_no,))
            if self.db.c.fetchone()[0] > 0:
                if manage_transaction: self.db.conn.rollback()
                return False, f"Fatura numarası '{fatura_no}' zaten mevcut. Lütfen başka bir numara girin."

            toplam_kdv_haric_kalemler, toplam_kdv_dahil_kalemler = 0.0, 0.0
            for item in kalemler:
                urun_id_item, miktar_item, birim_fiyat_haric_item, kdv_orani_item, alis_fiyati_item, isk1_item, isk2_item, isk_tip_item, isk_deger_item = item
                
                miktar_f, birim_fiyat_haric_f, kdv_orani_f = self.db.safe_float(miktar_item), self.db.safe_float(birim_fiyat_haric_item), self.db.safe_float(kdv_orani_item)
                isk1, isk2 = self.db.safe_float(isk1_item), self.db.safe_float(isk2_item)
                
                iskontolu_birim_fiyat_haric = birim_fiyat_haric_f * (1 - isk1/100) * (1 - isk2/100)
                kalem_toplam_kdv_haric = miktar_f * iskontolu_birim_fiyat_haric
                kalem_toplam_kdv_dahil = kalem_toplam_kdv_haric * (1 + kdv_orani_f / 100)
                toplam_kdv_haric_kalemler += kalem_toplam_kdv_haric
                toplam_kdv_dahil_kalemler += kalem_toplam_kdv_dahil

            uygulanan_genel_iskonto_tutari = 0.0
            if genel_iskonto_tipi == self.db.ISKONTO_TIP_YUZDE and genel_iskonto_degeri > 0:
                uygulanan_genel_iskonto_tutari = toplam_kdv_haric_kalemler * (genel_iskonto_degeri / 100)
            elif genel_iskonto_tipi == self.db.ISKONTO_TIP_TUTAR and genel_iskonto_degeri > 0:
                uygulanan_genel_iskonto_tutari = genel_iskonto_degeri
            
            nihai_toplam_kdv_haric = toplam_kdv_haric_kalemler - uygulanan_genel_iskonto_tutari
            nihai_toplam_kdv_dahil = toplam_kdv_dahil_kalemler - uygulanan_genel_iskonto_tutari
            nihai_toplam_kdv_tutari = nihai_toplam_kdv_dahil - nihai_toplam_kdv_haric
            
            if nihai_toplam_kdv_haric < 0: nihai_toplam_kdv_haric = 0.0
            if nihai_toplam_kdv_dahil < 0: nihai_toplam_kdv_dahil = 0.0
            if nihai_toplam_kdv_tutari < 0: nihai_toplam_kdv_tutari = 0.0

            current_time = self.db.get_current_datetime_str()
            olusturan_id = self.db._get_current_user_id() 

            # <<< DÜZELTME BAŞLANGICI: Sütun isimleri 'genel_iskonto_tipi' ve 'genel_iskonto_degeri' olarak güncellendi >>>
            self.db.c.execute("""
                INSERT INTO faturalar (
                    fatura_no, tarih, tip, cari_id, toplam_kdv_haric, toplam_kdv_dahil, odeme_turu,
                    misafir_adi, kasa_banka_id, fatura_notlari, vade_tarihi, genel_iskonto_tipi, genel_iskonto_degeri,
                    original_fatura_id, olusturma_tarihi_saat, olusturan_kullanici_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fatura_no, fatura_tarihi, tip, cari_id, nihai_toplam_kdv_haric, nihai_toplam_kdv_dahil, odeme_turu,
                misafir_adi, kasa_banka_id, fatura_notlari, vade_tarihi, genel_iskonto_tipi, # genel_iskonto_tipi
                genel_iskonto_degeri, original_fatura_id, current_time, olusturan_id # genel_iskonto_degeri
            ))
            fatura_id = self.db.c.lastrowid

            for item in kalemler:
                urun_id, miktar, birim_fiyat, kdv_orani, alis_fiyati, isk1, isk2, isk_tip, isk_deger = item
                
                # Kalem toplamlarını _hesapla_kalem_toplamlari gibi bir yardımcı metot kullanarak hesaplamak daha güvenli ve tutarlı olurdu.
                # Ancak mevcut yapıyı koruyarak doğrudan hesaplamaları yapıyoruz.
                iskontolu_bfh = self.db.safe_float(birim_fiyat) * (1-self.db.safe_float(isk1)/100) * (1-self.db.safe_float(isk2)/100)
                kalem_kdv_tutar = iskontolu_bfh * self.db.safe_float(miktar) * (self.db.safe_float(kdv_orani)/100)
                kalem_toplam_haric = iskontolu_bfh * self.db.safe_float(miktar)
                kalem_toplam_dahil = kalem_toplam_haric + kalem_kdv_tutar
                
                self.db.c.execute("""
                    INSERT INTO fatura_kalemleri (
                        fatura_id, urun_id, miktar, birim_fiyat, kdv_orani, kdv_tutari,
                        kalem_toplam_kdv_haric, kalem_toplam_kdv_dahil, alis_fiyati_fatura_aninda,
                        kdv_orani_fatura_aninda, iskonto_yuzde_1, iskonto_yuzde_2, iskonto_tipi,
                        iskonto_degeri, olusturma_tarihi_saat, olusturan_kullanici_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fatura_id, urun_id, miktar, birim_fiyat, kdv_orani, kalem_kdv_tutar,
                    kalem_toplam_haric, kalem_toplam_dahil, alis_fiyati, 
                    kdv_orani, isk1, isk2, isk_tip, isk_deger, # kdv_orani_fatura_aninda sütununu da ekledik
                    current_time, olusturan_id
                ))
                
                # Stok Miktarı Güncelleme ve Stok Hareketi Kaydı
                stok_degisim_net = 0.0
                stok_islem_tipi = ""
                kaynak_tipi_stok = self.db.KAYNAK_TIP_FATURA

                if tip == self.db.FATURA_TIP_SATIS:
                    stok_degisim_net = -self.db.safe_float(miktar)
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_SATIS
                elif tip == self.db.FATURA_TIP_ALIS:
                    stok_degisim_net = self.db.safe_float(miktar)
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_ALIS
                elif tip == self.db.FATURA_TIP_SATIS_IADE:
                    stok_degisim_net = self.db.safe_float(miktar) # Satış iadesi stoğu artırır
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_SATIS_IADE
                    kaynak_tipi_stok = self.db.KAYNAK_TIP_IADE_FATURA
                elif tip == self.db.FATURA_TIP_ALIS_IADE:
                    stok_degisim_net = -self.db.safe_float(miktar) # Alış iadesi stoğu azaltır
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_ALIS_IADE
                    kaynak_tipi_stok = self.db.KAYNAK_TIP_IADE_FATURA
                elif tip == self.db.FATURA_TIP_DEVIR_GIRIS:
                    stok_degisim_net = self.db.safe_float(miktar)
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_DEVIR_GIRIS
                
                self.db._stok_guncelle_ve_hareket_kaydet(urun_id, stok_degisim_net, stok_islem_tipi, kaynak_tipi_stok, fatura_id, fatura_no)
            
            # KASA BAKİYESİ GÜNCELLEME
            # Peşin ödeme türleri için kasa/banka bakiyesini güncelle
            if odeme_turu in self.db.pesin_odeme_turleri and kasa_banka_id is not None:
                if tip == self.db.FATURA_TIP_SATIS or tip == self.db.FATURA_TIP_ALIS_IADE: # Kasa için GELİR
                    self.db.kasa_banka_bakiye_guncelle(kasa_banka_id, nihai_toplam_kdv_dahil, artir=True)
                elif tip == self.db.FATURA_TIP_ALIS or tip == self.db.FATURA_TIP_SATIS_IADE: # Kasa için GİDER
                    self.db.kasa_banka_bakiye_guncelle(kasa_banka_id, nihai_toplam_kdv_dahil, artir=False)
            
            # CARİ HAREKET VE GELİR/GİDER OLUŞTURMA
            # SADECE AÇIK HESAP FATURALAR VE PEŞİN FATURALAR İÇİN TEK KAYIT
            self.db._fatura_finansal_etki_olustur(fatura_id, fatura_no, fatura_tarihi, tip, cari_id, nihai_toplam_kdv_dahil, odeme_turu, kasa_banka_id, misafir_adi)

            if manage_transaction: self.db.conn.commit()
            return True, fatura_id # Başarılı dönüş, fatura_id'yi döndür

        except sqlite3.IntegrityError as e:
            if manage_transaction: self.db.conn.rollback()
            return False, f"Fatura numarası '{fatura_no}' zaten mevcut. Lütfen başka bir numara girin."
        except ValueError as e:
            if manage_transaction: self.db.conn.rollback()
            return False, f"Veri dönüştürme hatası: {e}. Lütfen sayısal alanları kontrol edin."
        except Exception as e:
            if manage_transaction: self.db.conn.rollback()
            logging.error(f"FaturaServis.fatura_olustur Hata: {e}\n{traceback.format_exc()}")
            return False, f"Fatura oluşturulamadı. Hata: {e}"
                                
    def fatura_iade_olustur(self, original_fatura_id, iade_tarihi_str, iade_notlari=None):
        try:
            self.db.conn.execute("BEGIN TRANSACTION")
            
            original_fatura = self.db.fatura_getir_by_id(original_fatura_id)
            if not original_fatura: raise ValueError("İade edilecek orijinal fatura bulunamadı.")

            iade_fatura_tipi = self.db.FATURA_TIP_SATIS_IADE if original_fatura['tip'] == self.db.FATURA_TIP_SATIS else self.db.FATURA_TIP_ALIS_IADE
            
            self.db.c.execute("SELECT id FROM faturalar WHERE orijinal_fatura_id = ?", (original_fatura_id,))
            if self.db.c.fetchone(): raise ValueError("Bu faturaya zaten bir iade faturası kesilmiş.")

            # Benzersiz bir iade fatura numarası oluştur
            iade_fatura_no = f"IADE-{original_fatura['fatura_no']}-{datetime.now().strftime('%f')}"

            # Orijinal faturanın kalemlerini çek ve iade için hazırla
            original_kalemler = self.db.fatura_detay_al(original_fatura_id)
            kalemler_for_iade = []
            for k in original_kalemler:
                kalemler_for_iade.append((
                    k['urun_id'], k['miktar'], k['birim_fiyat'], k['kdv_orani'], k['alis_fiyati_fatura_aninda'], 
                    k['iskonto_yuzde_1'], k['iskonto_yuzde_2'], k['iskonto_tipi'], k['iskonto_degeri']
                ))
            
            is_success, message = self.fatura_olustur(
                iade_fatura_no, iade_fatura_tipi, original_fatura['cari_id'], kalemler_for_iade, 
                odeme_turu=original_fatura['odeme_turu'], # Orijinal faturanın ödeme türünü kullan
                kasa_banka_id=original_fatura['kasa_banka_id'], # Orijinal faturanın kasa/bankasını kullan
                misafir_adi=original_fatura['misafir_adi'], 
                fatura_notlari=f"Orijinal Fatura: {original_fatura['fatura_no']}. {iade_notlari or ''}".strip(), 
                vade_tarihi=original_fatura['vade_tarihi'], # Orijinal faturanın vade tarihini kullan
                genel_iskonto_tipi=original_fatura['genel_iskonto_tipi'], 
                genel_iskonto_degeri=original_fatura['genel_iskonto_degeri'], 
                original_fatura_id=original_fatura_id, 
                manage_transaction=False # Dış transaction tarafından yönetilecek
            )

            if not is_success: raise Exception(message)
            
            self.db.conn.commit()
            return True, f"İade faturası '{iade_fatura_no}' başarıyla oluşturuldu."
        except Exception as e:
            self.db.conn.rollback()
            logging.error(f"Fatura iade oluşturulurken hata: {e}\n{traceback.format_exc()}")
            return False, f"Fatura iadesi oluşturulamadı. Hata: {e}"
                        

    def siparis_faturaya_donustur(self, siparis_id, olusturan_kullanici_id, odeme_turu_secilen, kasa_banka_id_secilen, vade_tarihi_secilen):
        """
        Belirtilen siparişi bir faturaya dönüştürür. Tüm mantık artık bu servistedir.
        """
        try:
            self.db.conn.execute("BEGIN TRANSACTION")
            siparis_ana = self.db.get_siparis_by_id(siparis_id)
            if not siparis_ana:
                return False, "Dönüştürülecek sipariş bulunamadı."
            
            if siparis_ana['fatura_id']:
                return False, f"Bu sipariş zaten bir faturaya dönüştürülmüş."
            if siparis_ana['durum'] == 'İPTAL EDİLDİ':
                return False, "İptal edilmiş bir sipariş faturaya dönüştürülemez."

            siparis_kalemleri = self.db.get_siparis_kalemleri(siparis_id)
            if not siparis_kalemleri:
                return False, "Sipariş kalemleri bulunamadı. Fatura oluşturulamıyor."

            fatura_tipi = 'SATIŞ' if siparis_ana['cari_tip'] == 'MUSTERI' else 'ALIŞ'
            fatura_no = self.db.son_fatura_no_getir(fatura_tipi)

            kalemler_for_fatura = []
            for sk in siparis_kalemleri:
                # fatura_olustur metodunun beklediği format:
                # (urun_id, miktar, birim_fiyat, kdv_orani, alis_fiyati, isk1, isk2, isk_tip, isk_deger)
                kalemler_for_fatura.append((
                    sk['urun_id'], sk['miktar'], sk['birim_fiyat'], sk['kdv_orani'], 
                    sk['alis_fiyati_siparis_aninda'], sk['iskonto_yuzde_1'], sk['iskonto_yuzde_2'], 
                    "YOK", 0.0
                ))

            success_fatura, message_fatura_id = self.fatura_olustur(
                fatura_no, fatura_tipi, siparis_ana['cari_id'], kalemler_for_fatura,
                odeme_turu=odeme_turu_secilen,
                kasa_banka_id=kasa_banka_id_secilen,
                fatura_notlari=f"Sipariş No: {siparis_ana['siparis_no']} ile oluşturulmuştur. {siparis_ana['siparis_notlari'] or ''}".strip(),
                vade_tarihi=vade_tarihi_secilen,
                genel_iskonto_tipi=siparis_ana['genel_iskonto_tipi'],
                genel_iskonto_degeri=siparis_ana['genel_iskonto_degeri'],
                manage_transaction=False
            )

            if success_fatura:
                yeni_fatura_id = message_fatura_id
                current_time = self.db.get_current_datetime_str()
                self.db.c.execute("UPDATE siparisler SET durum=?, fatura_id=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                                  ('TAMAMLANDI', yeni_fatura_id, current_time, olusturan_kullanici_id, siparis_id))
                self.db.conn.commit()
                return True, f"Sipariş '{siparis_ana['siparis_no']}' başarıyla '{fatura_no}' nolu faturaya dönüştürüldü."
            else:
                self.db.conn.rollback()
                return False, f"Sipariş faturaya dönüştürülürken hata oluştu: {message_fatura_id}"

        except Exception as e:
            if self.db.conn: self.db.conn.rollback()
            return False, f"Sipariş faturaya dönüştürülürken beklenmeyen bir hata oluştu: {e}\n{traceback.format_exc()}"

    def fatura_guncelle(self, fatura_id, yeni_fatura_no, yeni_fatura_tarihi, yeni_cari_id, yeni_odeme_turu, yeni_kalemler, yeni_kasa_banka_id=None, yeni_misafir_adi=None, yeni_fatura_notlari=None, yeni_vade_tarihi=None, yeni_genel_iskonto_tipi='YOK', yeni_genel_iskonto_degeri=0.0):
        try:
            self.db.conn.execute("BEGIN TRANSACTION")

            mevcut_fatura = self.db.fatura_getir_by_id(fatura_id)
            if not mevcut_fatura:
                self.db.conn.rollback()
                return False, "Güncellenecek fatura bulunamadı."
            
            self.db.c.execute("SELECT COUNT(*) FROM faturalar WHERE fatura_no = ? AND id != ?", (yeni_fatura_no, fatura_id))
            if self.db.c.fetchone()[0] > 0:
                self.db.conn.rollback()
                return False, f"Fatura numarası '{yeni_fatura_no}' zaten mevcut. Lütfen başka bir numara girin."

            # Eski stok hareketlerini geri al
            mevcut_kalemler_db = self.db.fatura_detay_al(fatura_id)
            mevcut_kalemler_for_geri_al = [(k['urun_id'], k['miktar']) for k in mevcut_kalemler_db]
            self.db._fatura_hareketlerini_geri_al(mevcut_fatura, mevcut_kalemler_for_geri_al)
            
            # Eski finansal etkileri (cari hareketler, gelir/gider) geri al/sil
            self.db._fatura_finansal_etki_geri_al(fatura_id) 

            # Eski fatura kalemlerini sil
            self.db.c.execute("DELETE FROM fatura_kalemleri WHERE fatura_id = ?", (fatura_id,))

            # Yeni toplamları hesapla
            toplam_kdv_haric_yeni, toplam_kdv_dahil_yeni, toplam_kdv_tutari_yeni = self._hesapla_fatura_toplamlari(yeni_kalemler)
            
            # Genel iskonto uygula
            uygulanan_genel_iskonto_tutari = 0.0
            if yeni_genel_iskonto_tipi == self.db.ISKONTO_TIP_YUZDE and yeni_genel_iskonto_degeri > 0:
                uygulanan_genel_iskonto_tutari = toplam_kdv_haric_yeni * (yeni_genel_iskonto_degeri / 100)
            elif yeni_genel_iskonto_tipi == self.db.ISKONTO_TIP_TUTAR and yeni_genel_iskonto_degeri > 0:
                uygulanan_genel_iskonto_tutari = yeni_genel_iskonto_degeri
            
            # Nihai toplamları güncelle
            nihai_toplam_kdv_haric = toplam_kdv_haric_yeni - uygulanan_genel_iskonto_tutari
            nihai_toplam_kdv_dahil = toplam_kdv_dahil_yeni - uygulanan_genel_iskonto_tutari
            nihai_toplam_kdv_tutari = nihai_toplam_kdv_dahil - nihai_toplam_kdv_haric
            
            if nihai_toplam_kdv_haric < 0: nihai_toplam_kdv_haric = 0.0
            if nihai_toplam_kdv_dahil < 0: nihai_toplam_kdv_dahil = 0.0
            if nihai_toplam_kdv_tutari < 0: nihai_toplam_kdv_tutari = 0.0

            current_time = self.db.get_current_datetime_str()
            guncelleyen_id = self.db._get_current_user_id() 

            # Fatura bilgilerini güncelle
            self.db.c.execute("""
                UPDATE faturalar SET
                    fatura_no=?, tarih=?, cari_id=?, toplam_kdv_haric=?, toplam_kdv_dahil=?,
                    odeme_turu=?, misafir_adi=?, kasa_banka_id=?, fatura_notlari=?,
                    vade_tarihi=?, genel_iskonto_tipi=?, genel_iskonto_degeri=?,
                    son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=?
                WHERE id=?
            """, (
                yeni_fatura_no, yeni_fatura_tarihi, yeni_cari_id, nihai_toplam_kdv_haric, nihai_toplam_kdv_dahil,
                yeni_odeme_turu, yeni_misafir_adi, yeni_kasa_banka_id, yeni_fatura_notlari,
                yeni_vade_tarihi, yeni_genel_iskonto_tipi, yeni_genel_iskonto_degeri,
                current_time, guncelleyen_id, fatura_id
            ))

            # Yeni kalemleri ekle ve STOK HAREKETLERİNİ DOĞRU YÖNDE OLUŞTUR
            for urun_id, miktar, birim_fiyat, kdv_orani, alis_fiyati_fatura_aninda, isk1, isk2, isk_tip, isk_deger in yeni_kalemler:
                kalem_kdv_haric, kalem_kdv_dahil, kalem_kdv_tutari, iskontolu_bf_dahil = self._hesapla_kalem_toplamlari(
                    miktar, birim_fiyat, kdv_orani, isk1, isk2
                )
                self.db.c.execute("""
                    INSERT INTO fatura_kalemleri (
                        fatura_id, urun_id, miktar, birim_fiyat, kdv_orani, kdv_tutari,
                        kalem_toplam_kdv_haric, kalem_toplam_kdv_dahil, alis_fiyati_fatura_aninda,
                        kdv_orani_fatura_aninda, iskonto_yuzde_1, iskonto_yuzde_2, iskonto_tipi,
                        iskonto_degeri, olusturma_tarihi_saat, olusturan_kullanici_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fatura_id, urun_id, miktar, birim_fiyat, kdv_orani, kalem_kdv_tutari,
                    kalem_kdv_haric, kalem_kdv_dahil, alis_fiyati_fatura_aninda,
                    kdv_orani, isk1, isk2, isk_tip, isk_deger,
                    current_time, guncelleyen_id 
                ))
            
                # <<< KRİTİK DÜZELTME BAŞLANGICI: YENİ STOK HAREKETLERİNİ OLUŞTURMA >>>
                # Fatura tipi mevcut_fatura'dan alınmalı, çünkü iade faturaları da güncellenebilir.
                # Stok değişimi yönü, fatura tipi ne olursa olsun aynı mantıkla hesaplanmalı.
                stok_degisim_net = 0.0
                stok_islem_tipi = ""
                kaynak_tipi_stok = self.db.KAYNAK_TIP_FATURA # Varsayılan

                # Satış ve Alış İade faturaları stoğu azaltır
                if mevcut_fatura['tip'] == self.db.FATURA_TIP_SATIS:
                    stok_degisim_net = -self.db.safe_float(miktar)
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_SATIS
                elif mevcut_fatura['tip'] == self.db.FATURA_TIP_ALIS_IADE:
                    stok_degisim_net = -self.db.safe_float(miktar) # Alış iadesinde stok azalır
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_ALIS_IADE
                    kaynak_tipi_stok = self.db.KAYNAK_TIP_IADE_FATURA
                # Alış ve Satış İade faturaları stoğu artırır
                elif mevcut_fatura['tip'] == self.db.FATURA_TIP_ALIS:
                    stok_degisim_net = self.db.safe_float(miktar)
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_ALIS
                elif mevcut_fatura['tip'] == self.db.FATURA_TIP_SATIS_IADE:
                    stok_degisim_net = self.db.safe_float(miktar) # Satış iadesinde stok artar
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_SATIS_IADE
                    kaynak_tipi_stok = self.db.KAYNAK_TIP_IADE_FATURA
                elif mevcut_fatura['tip'] == self.db.FATURA_TIP_DEVIR_GIRIS:
                    stok_degisim_net = self.db.safe_float(miktar)
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_DEVIR_GIRIS
                
                self.db._stok_guncelle_ve_hareket_kaydet(urun_id, stok_degisim_net, stok_islem_tipi, kaynak_tipi_stok, fatura_id, yeni_fatura_no)
                # <<< KRİTİK DÜZELTME BİTİŞİ >>>

            # Kasa/Banka bakiyesini manuel olarak yeniden güncelliyoruz (ödeme türü peşinse)
            if yeni_odeme_turu in self.db.pesin_odeme_turleri and yeni_kasa_banka_id is not None:
                # Satış faturası veya Alış İade faturası (kasa için gelir)
                if mevcut_fatura['tip'] == self.db.FATURA_TIP_SATIS or mevcut_fatura['tip'] == self.db.FATURA_TIP_ALIS_IADE:
                    self.db.kasa_banka_bakiye_guncelle(yeni_kasa_banka_id, nihai_toplam_kdv_dahil, artir=True)
                # Alış faturası veya Satış İade faturası (kasa için gider)
                elif mevcut_fatura['tip'] == self.db.FATURA_TIP_ALIS or mevcut_fatura['tip'] == self.db.FATURA_TIP_SATIS_IADE:
                    self.db.kasa_banka_bakiye_guncelle(yeni_kasa_banka_id, nihai_toplam_kdv_dahil, artir=False)
            
            # Yeni finansal etkileri (cari hareketler, gelir/gider) oluştur
            # mevcut_fatura['tip'] -> Fatura tipi değişmediği için orijinal tipi kullanıyoruz.
            self.db._fatura_finansal_etki_olustur(fatura_id, yeni_fatura_no, yeni_fatura_tarihi, mevcut_fatura['tip'], yeni_cari_id, nihai_toplam_kdv_dahil, yeni_odeme_turu, yeni_kasa_banka_id, yeni_misafir_adi)

            self.db.conn.commit()
            return True, f"Fatura '{yeni_fatura_no}' başarıyla güncellendi."

        except sqlite3.IntegrityError as e:
            self.db.conn.rollback()
            return False, f"Fatura numarası '{yeni_fatura_no}' zaten mevcut."
        except Exception as e:
            self.db.conn.rollback()
            logging.error(f"Fatura güncellenirken beklenmeyen hata: {e}", exc_info=True)
            return False, f"Fatura güncellenirken beklenmeyen bir hata oluştu: {e}"                                                                                
    def fatura_sil(self, fatura_id, manage_transaction=True):
        try:
            if manage_transaction:
                self.db.conn.execute("BEGIN TRANSACTION")

            fatura_bilgisi = self.db.fatura_getir_by_id(fatura_id)
            if not fatura_bilgisi:
                raise ValueError("Silinecek fatura bulunamadı.")
            
            fatura_no_silinen = fatura_bilgisi['fatura_no']
            fatura_tipi = fatura_bilgisi['tip']
            eski_odeme_turu = fatura_bilgisi['odeme_turu']
            eski_kasa_id = fatura_bilgisi['kasa_banka_id']
            eski_tutar = fatura_bilgisi['toplam_kdv_dahil']

            # 1. Adım: Kasa/Banka etkisini geri al (EĞER PEŞİN BİR İŞLEM İSE)
            if eski_odeme_turu in self.db.pesin_odeme_turleri and eski_kasa_id is not None:
                is_bakiye_artir_for_delete = False 

                if fatura_tipi == self.db.FATURA_TIP_SATIS:
                    is_bakiye_artir_for_delete = False
                elif fatura_tipi == self.db.FATURA_TIP_ALIS:
                    is_bakiye_artir_for_delete = True
                elif fatura_tipi == self.db.FATURA_TIP_SATIS_IADE:
                    is_bakiye_artir_for_delete = True
                elif fatura_tipi == self.db.FATURA_TIP_ALIS_IADE:
                    is_bakiye_artir_for_delete = False
                
                self.db.kasa_banka_bakiye_guncelle(eski_kasa_id, eski_tutar, artir=is_bakiye_artir_for_delete)
                logging.info(f"Fatura silme: Kasa ID {eski_kasa_id} bakiyesi, işlem geri alındığı için güncellendi.")

            # 2. Adım: Stok Miktarlarını Tersine Çevir
            kalemler = self.db.fatura_detay_al(fatura_id)
            for kalem in kalemler:
                stok_degisim_yonu_orijinal = 0.0
                stok_islem_tipi_geri_al = ""
                kaynak_tipi_geri_al = ""

                if fatura_tipi == self.db.FATURA_TIP_SATIS:
                    stok_degisim_yonu_orijinal = kalem['miktar'] # Satışta çıkan stoğu geri al (ekle)
                    stok_islem_tipi_geri_al = self.db.STOK_ISLEM_TIP_FATURA_SATIS
                    kaynak_tipi_geri_al = self.db.KAYNAK_TIP_FATURA
                elif fatura_tipi == self.db.FATURA_TIP_ALIS:
                    stok_degisim_yonu_orijinal = -kalem['miktar'] # Alışta giren stoğu geri al (çıkar)
                    stok_islem_tipi_geri_al = self.db.STOK_ISLEM_TIP_FATURA_ALIS
                    kaynak_tipi_geri_al = self.db.KAYNAK_TIP_FATURA
                elif fatura_tipi == self.db.FATURA_TIP_SATIS_IADE:
                    stok_degisim_yonu_orijinal = -kalem['miktar'] # Satış iadesinde giren stoğu geri al (çıkar)
                    stok_islem_tipi_geri_al = self.db.STOK_ISLEM_TIP_FATURA_SATIS_IADE
                    kaynak_tipi_geri_al = self.db.KAYNAK_TIP_IADE_FATURA
                elif fatura_tipi == self.db.FATURA_TIP_ALIS_IADE:
                    stok_degisim_yonu_orijinal = kalem['miktar'] # Alış iadesinde çıkan stoğu geri al (ekle)
                    stok_islem_tipi_geri_al = self.db.STOK_ISLEM_TIP_FATURA_ALIS_IADE
                    kaynak_tipi_geri_al = self.db.KAYNAK_TIP_IADE_FATURA
                
                self.db._stok_guncelle_ve_hareket_kaydet(
                    kalem['urun_id'],
                    stok_degisim_yonu_orijinal, 
                    f"{stok_islem_tipi_geri_al} (Silme)",
                    kaynak_tipi_geri_al,
                    fatura_id,
                    fatura_no_silinen
                )

            # 3. Adım: Tüm İlişkili Finansal Kayıtları Sil (Cari hareketler ve Gelir/Gider)
            self.db.c.execute("DELETE FROM gelir_gider WHERE kaynak_id=? AND kaynak IN (?, ?, ?, ?, ?, ?)", 
                              (fatura_id, self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA, 
                               self.db.KAYNAK_TIP_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_FATURA_ALIS_PESIN,
                               self.db.KAYNAK_TIP_IADE_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_IADE_FATURA_ALIS_PESIN)) 
            
            self.db.c.execute("DELETE FROM cari_hareketler WHERE referans_id=? AND referans_tip IN (?, ?, ?, ?, ?, ?)", 
                             (fatura_id, self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA, 
                              self.db.KAYNAK_TIP_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_FATURA_ALIS_PESIN,
                              self.db.KAYNAK_TIP_IADE_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_IADE_FATURA_ALIS_PESIN)) 
            
            # 4. Adım: Sipariş bağlantısını güncelle (varsa)
            self.db.c.execute("UPDATE siparisler SET durum = ?, fatura_id = NULL WHERE fatura_id = ?", (self.db.SIPARIS_DURUM_BEKLEMEDE, fatura_id))

            # 5. Adım: Fatura ve Fatura Kalemlerini Sil
            self.db.c.execute("DELETE FROM fatura_kalemleri WHERE fatura_id=?", (fatura_id,))
            self.db.c.execute("DELETE FROM faturalar WHERE id=?", (fatura_id,))

            if manage_transaction:
                self.db.conn.commit()

            return True, f"Fatura No '{fatura_no_silinen}' başarıyla silindi ve tüm etkileri geri alındı."
        
        except Exception as e:
            if manage_transaction and self.db.conn:
                self.db.conn.rollback()
            error_details = traceback.format_exc()
            logging.error(f"FaturaServis.fatura_sil Hata: {e}\nDetaylar: {error_details}")
            return False, "Fatura silinirken beklenmeyen bir hata oluştu."

    def _hesapla_fatura_toplamlari(self, kalemler):
        """
        Fatura kalemlerinin genel toplamlarını (KDV hariç, KDV dahil, KDV tutarı) hesaplar.
        """
        toplam_kdv_haric = 0.0
        toplam_kdv_dahil = 0.0
        toplam_kdv_tutari = 0.0
        for item in kalemler:
            urun_id, miktar, birim_fiyat, kdv_orani, alis_fiyati, isk1, isk2, isk_tip, isk_deger = item
            
            # Kalem toplamlarını hesaplamak için diğer yardımcı metodu kullan
            kalem_kdv_haric, kalem_kdv_dahil, kalem_kdv_tutari, iskontolu_bf_dahil = self._hesapla_kalem_toplamlari(
                miktar, birim_fiyat, kdv_orani, isk1, isk2
            )
            toplam_kdv_haric += kalem_kdv_haric
            toplam_kdv_dahil += kalem_kdv_dahil
            toplam_kdv_tutari += kalem_kdv_tutari
        return toplam_kdv_haric, toplam_kdv_dahil, toplam_kdv_tutari

    def _hesapla_kalem_toplamlari(self, miktar, birim_fiyat, kdv_orani, iskonto_yuzde_1, iskonto_yuzde_2):
        """
        Tek bir fatura kaleminin KDV hariç, KDV dahil, KDV tutarı ve iskontolu birim fiyatını hesaplar.
        """
        miktar_f = self.db.safe_float(miktar)
        birim_fiyat_f = self.db.safe_float(birim_fiyat) # KDV hariç orijinal
        kdv_orani_f = self.db.safe_float(kdv_orani)
        isk1_f = self.db.safe_float(iskonto_yuzde_1)
        isk2_f = self.db.safe_float(iskonto_yuzde_2)

        # İskontoları uygula (KDV hariç birim fiyat üzerinden)
        iskontolu_birim_fiyat_haric = birim_fiyat_f * (1 - isk1_f / 100) * (1 - isk2_f / 100)
        
        # Negatif fiyatları engelle (eğer iskonto fiyatı sıfırın altına düşürürse)
        if iskontolu_birim_fiyat_haric < 0: iskontolu_birim_fiyat_haric = 0.0

        kalem_toplam_kdv_haric = miktar_f * iskontolu_birim_fiyat_haric
        kalem_kdv_tutari = kalem_toplam_kdv_haric * (kdv_orani_f / 100)
        kalem_toplam_kdv_dahil = kalem_toplam_kdv_haric + kalem_kdv_tutari
        
        # İskontolu birim fiyat KDV dahil, sadece bilgi amaçlı.
        iskontolu_birim_fiyat_kdv_dahil = iskontolu_birim_fiyat_haric * (1 + kdv_orani_f / 100)

        return kalem_toplam_kdv_haric, kalem_toplam_kdv_dahil, kalem_kdv_tutari, iskontolu_birim_fiyat_kdv_dahil

class TopluIslemService:
    def __init__(self, db_manager, fatura_service):
        self.db = db_manager
        self.fatura_service = fatura_service

    def toplu_stok_analiz_et(self, stok_data_raw, selected_update_fields):
        # Bu metot veritabanı.py'den taşındı ve referansları düzeltildi.
        analysis_results = { 'new_items': [], 'updated_items': [], 'errors_details': [], 'new_count': 0, 'updated_count': 0, 'error_count': 0, 'all_processed_data': [], 'selected_update_fields_from_ui': selected_update_fields }
        COL_URUN_KODU, COL_URUN_ADI = 0, 1; COL_STOK_MIKTARI, COL_ALIS_FIYATI_KDV_DAHIL, COL_SATIS_FIYATI_KDV_DAHIL = 2, 3, 4; COL_KDV_ORANI, COL_MIN_STOK_SEVIYESI = 5, 6; COL_KATEGORI_ADI, COL_MARKA_ADI, COL_URUN_GRUBU_ADI = 7, 8, 9; COL_URUN_BIRIMI_ADI, COL_ULKE_ADI, COL_URUN_DETAYI, COL_URUN_RESMI_YOLU = 10, 11, 12, 13
        
        conn_thread = None
        try:
            # self.db_name -> self.db.db_name
            conn_thread = sqlite3.connect(self.db.db_name, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            conn_thread.row_factory = sqlite3.Row
            cursor_thread = conn_thread.cursor()
            for i, row_raw in enumerate(stok_data_raw):
                row = list(row_raw) + [None] * (COL_URUN_RESMI_YOLU + 1 - len(row_raw))
                if not any(cell is not None and str(cell).strip() != '' for cell in row): continue
                try:
                    urun_kodu = str(row[COL_URUN_KODU] or '').strip()
                    urun_adi_from_excel = str(row[COL_URUN_ADI] or '').strip()
                    if not urun_kodu:
                        analysis_results['errors_details'].append((row_raw, "Ürün Kodu boş olamaz."))
                        analysis_results['error_count'] += 1
                        continue
                    cursor_thread.execute("SELECT * FROM tbl_stoklar WHERE urun_kodu=?", (urun_kodu,))
                    existing_product = cursor_thread.fetchone()
                    if not existing_product and not urun_adi_from_excel:
                        analysis_results['errors_details'].append((row_raw, "Yeni ürün için Ürün Adı boş olamaz."))
                        analysis_results['error_count'] += 1
                        continue
                    status_message = "Yeni ürün eklenecek." if not existing_product else "Mevcut ürün güncellenecek."
                    def get_id_for_analysis(table, column, value):
                        if not value: return None
                        cursor_thread.execute(f"SELECT id FROM {table} WHERE {column}=?", (value,))
                        res = cursor_thread.fetchone()
                        return res[0] if res else value
                    final_kategori = get_id_for_analysis('urun_kategorileri', 'kategori_adi', str(row[COL_KATEGORI_ADI] or '').strip())
                    final_marka = get_id_for_analysis('urun_markalari', 'marka_adi', str(row[COL_MARKA_ADI] or '').strip())
                    final_urun_grubu = get_id_for_analysis('urun_gruplari', 'grup_adi', str(row[COL_URUN_GRUBU_ADI] or '').strip())
                    final_urun_birimi = get_id_for_analysis('urun_birimleri', 'birim_adi', str(row[COL_URUN_BIRIMI_ADI] or '').strip())
                    final_ulke = get_id_for_analysis('urun_ulkeleri', 'ulke_adi', str(row[COL_ULKE_ADI] or '').strip())
                    
                    # self.safe_float -> self.db.safe_float
                    processed_data_item = { "urun_id": existing_product['id'] if existing_product else None, "urun_kodu": urun_kodu, "urun_adi": urun_adi_from_excel, "stok_miktari": self.db.safe_float(row[COL_STOK_MIKTARI]), "alis_fiyati_kdv_dahil": self.db.safe_float(row[COL_ALIS_FIYATI_KDV_DAHIL]), "satis_fiyati_kdv_dahil": self.db.safe_float(row[COL_SATIS_FIYATI_KDV_DAHIL]), "kdv_orani": self.db.safe_float(row[COL_KDV_ORANI]), "min_stok_seviyesi": self.db.safe_float(row[COL_MIN_STOK_SEVIYESI]), "urun_detayi": str(row[COL_URUN_DETAYI] or '').strip(), "urun_resmi_yolu": str(row[COL_URUN_RESMI_YOLU] or '').strip(), "kategori_id_or_name": final_kategori, "marka_id_or_name": final_marka, "urun_grubu_id_or_name": final_urun_grubu, "urun_birimi_id_or_name": final_urun_birimi, "ulke_id_or_name": final_ulke, "initial_stok_db": existing_product['stok_miktari'] if existing_product else 0.0 }
                    analysis_results['all_processed_data'].append(processed_data_item)

                    if existing_product:
                        analysis_results['updated_items'].append((row_raw, status_message))
                        analysis_results['updated_count'] += 1
                    else:
                        analysis_results['new_items'].append((row_raw, status_message))
                        analysis_results['new_count'] += 1
                except Exception as e_inner:
                    analysis_results['errors_details'].append((row_raw, f"Satır işlenirken hata: {e_inner}."))
                    analysis_results['error_count'] += 1
        except Exception as e:
            analysis_results['errors_details'].append( (None, f"Analiz sırasında beklenmeyen hata: {e}. {traceback.format_exc()}"))
            analysis_results['error_count'] += 1
        finally:
            if conn_thread: conn_thread.close()
        return analysis_results
        
    def toplu_stok_ekle_guncelle(self, processed_stok_data, selected_update_fields_from_analysis):
        # Bu metot veritabani.py'den taşındı ve hatası düzeltildi.
        # Artık transaction kontrolü yapmıyor, sadece iş mantığını işletiyor.
        if not processed_stok_data:
            return True, "İşlenecek stok verisi bulunamadı."

        new_product_count_final, updated_product_count_final = 0, 0
        total_errors_during_write, kalemler_for_fatura = [], []
        
        current_time, olusturan_id = self.db.get_current_datetime_str(), self.db._get_current_user_id()
        
        for item_data in processed_stok_data:
            try:
                def resolve_id(key, table, column, default_if_empty=None):
                    value = item_data.get(key)
                    if isinstance(value, int): return value
                    if isinstance(value, str) and value:
                        return self.db._get_or_create_id(table, column, value, manage_transaction=False)
                    if default_if_empty:
                        return self.db._get_or_create_id(table, column, default_if_empty, manage_transaction=False)
                    return None
                
                kategori_id_final = resolve_id('kategori_id_or_name', 'urun_kategorileri', 'kategori_adi')
                marka_id_final = resolve_id('marka_id_or_name', 'urun_markalari', 'marka_adi')
                urun_grubu_id_final = resolve_id('urun_grubu_id_or_name', 'urun_gruplari', 'grup_adi')
                urun_birimi_id_final = resolve_id('urun_birimi_id_or_name', 'urun_birimleri', 'birim_adi', default_if_empty="Adet")
                ulke_id_final = resolve_id('ulke_id_or_name', 'urun_ulkeleri', 'ulke_adi')
                
                kdv_orani = item_data.get('kdv_orani')
                kdv_carpan = (1 + kdv_orani / 100) if kdv_orani is not None else 1.0
                alis_dahil = item_data.get('alis_fiyati_kdv_dahil')
                satis_dahil = item_data.get('satis_fiyati_kdv_dahil')
                alis_haric = (alis_dahil / kdv_carpan) if (alis_dahil is not None and kdv_carpan != 0) else (alis_dahil or 0.0)
                satis_haric = (satis_dahil / kdv_carpan) if (satis_dahil is not None and kdv_carpan != 0) else (satis_dahil or 0.0)
                
                urun_id = item_data.get('urun_id')
                if urun_id is not None:
                    updated_product_count_final += 1
                    update_clauses, update_params = [], []
                    if item_data.get('urun_adi'): update_clauses.append("urun_adi=?"); update_params.append(item_data.get('urun_adi'))
                    if 'fiyat_bilgileri' in selected_update_fields_from_analysis:
                        if alis_dahil is not None: update_clauses.extend(["alis_fiyati_kdv_haric=?", "alis_fiyati_kdv_dahil=?"]); update_params.extend([alis_haric, alis_dahil])
                        if satis_dahil is not None: update_clauses.extend(["satis_fiyati_kdv_haric=?", "satis_fiyati_kdv_dahil=?"]); update_params.extend([satis_haric, satis_dahil])
                        if kdv_orani is not None: update_clauses.append("kdv_orani=?"); update_params.append(kdv_orani)
                    if 'urun_nitelikleri' in selected_update_fields_from_analysis:
                        if kategori_id_final is not None: update_clauses.append("kategori_id=?"); update_params.append(kategori_id_final)
                        if marka_id_final is not None: update_clauses.append("marka_id=?"); update_params.append(marka_id_final)
                        if urun_grubu_id_final is not None: update_clauses.append("urun_grubu_id=?"); update_params.append(urun_grubu_id_final)
                        if urun_birimi_id_final is not None: update_clauses.append("urun_birimi_id=?"); update_params.append(urun_birimi_id_final)
                        if ulke_id_final is not None: update_clauses.append("ulke_id=?"); update_params.append(ulke_id_final)
                    if 'stok_miktari' in selected_update_fields_from_analysis and item_data.get('min_stok_seviyesi') is not None: update_clauses.append("min_stok_seviyesi=?"); update_params.append(item_data.get('min_stok_seviyesi'))
                    
                    if update_clauses:
                        update_clauses.extend(["son_guncelleme_tarihi_saat=?", "son_guncelleyen_kullanici_id=?"]); update_params.extend([current_time, olusturan_id, urun_id])
                        self.db.c.execute(f"UPDATE tbl_stoklar SET {', '.join(update_clauses)} WHERE id=?", tuple(update_params))
                else:
                    new_product_count_final += 1
                    self.db.c.execute("INSERT INTO tbl_stoklar (urun_kodu, urun_adi, stok_miktari, alis_fiyati_kdv_haric, satis_fiyati_kdv_haric, kdv_orani, min_stok_seviyesi, alis_fiyati_kdv_dahil, satis_fiyati_kdv_dahil, kategori_id, marka_id, urun_grubu_id, urun_birimi_id, ulke_id, urun_detayi, urun_resmi_yolu, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                     (item_data.get('urun_kodu'), item_data.get('urun_adi'), 0.0, alis_haric, satis_haric, kdv_orani, item_data.get('min_stok_seviyesi', 0.0), alis_dahil, satis_dahil, kategori_id_final, marka_id_final, urun_grubu_id_final, urun_birimi_id_final, ulke_id_final, item_data.get('urun_detayi'), item_data.get('urun_resmi_yolu'), current_time, olusturan_id))
                    urun_id = self.db.c.lastrowid
                
                if 'stok_miktari' in selected_update_fields_from_analysis and item_data.get('stok_miktari') is not None:
                    stok_farki = self.db.safe_float(item_data.get('stok_miktari', 0.0)) - self.db.safe_float(item_data.get('initial_stok_db', 0.0))
                    if stok_farki > 0:
                        kalemler_for_fatura.append((urun_id, stok_farki, alis_haric, kdv_orani, alis_dahil, 0, 0, "YOK", 0))

            except Exception as e:
                total_errors_during_write.append(f"Ürün Kodu {item_data.get('urun_kodu')}: {e}")

        if kalemler_for_fatura:
            fatura_no_aktarim = f"AKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            if self.db.genel_tedarikci_id is None: self.db._ensure_genel_tedarikci()
            
            # self.fatura_olustur -> self.fatura_service.fatura_olustur
            success_fatura, _ = self.fatura_service.fatura_olustur(
                fatura_no_aktarim, 'ALIŞ', self.db.genel_tedarikci_id,
                kalemler_for_fatura, 'ETKİSİZ FATURA', manage_transaction=False
            )
            if not success_fatura: raise Exception("Toplu stok aktarım faturası oluşturulamadı.")
        
        message = f"{new_product_count_final} yeni ürün eklendi, {updated_product_count_final} ürün güncellendi."
        if kalemler_for_fatura: message += f"\nStok girişi için '{fatura_no_aktarim}' nolu fatura oluşturuldu."
        if total_errors_during_write: message += f"\n{len(total_errors_during_write)} satırda hata oluştu: {'; '.join(total_errors_during_write[:3])}"
        return True, message
            
    def toplu_musteri_analiz_et(self, musteriler_data_raw):
        analysis_results = {'new_items': [], 'updated_items': [], 'errors_details': [], 'new_count': 0, 'updated_count': 0, 'error_count': 0, 'all_processed_data': []}
        COL_MUSTERI_KODU, COL_AD_SOYAD, COL_TELEFON, COL_ADRES, COL_VERGI_DAIRESI, COL_VERGI_NO = 0, 1, 2, 3, 4, 5
        conn_thread = None
        try:
            conn_thread = sqlite3.connect(self.db.db_name, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            conn_thread.row_factory = sqlite3.Row
            cursor_thread = conn_thread.cursor()
            for i, row_raw in enumerate(musteriler_data_raw):
                row = list(row_raw) + [None] * (COL_VERGI_NO + 1 - len(row_raw))
                if not any(cell is not None and str(cell).strip() != '' for cell in row): continue
                try:
                    musteri_kodu, ad = str(row[COL_MUSTERI_KODU] or '').strip(), str(row[COL_AD_SOYAD] or '').strip()
                    if not musteri_kodu: analysis_results['errors_details'].append((row_raw, "Müşteri Kodu boş olamaz.")); analysis_results['error_count'] += 1; continue
                    if not ad: analysis_results['errors_details'].append((row_raw, "Ad Soyad boş olamaz.")); analysis_results['error_count'] += 1; continue
                    if musteri_kodu == self.db.PERAKENDE_MUSTERI_KODU: analysis_results['errors_details'].append((row_raw, f"'{self.db.PERAKENDE_MUSTERI_KODU}' özel bir koddur ve toplu eklemede kullanılamaz.")); analysis_results['error_count'] += 1; continue
                    cursor_thread.execute("SELECT id FROM musteriler WHERE kod=?", (musteri_kodu,))
                    existing_customer = cursor_thread.fetchone()
                    status_message = "Yeni müşteri eklenecek." if not existing_customer else "Mevcut müşteri güncellenecek."
                    if existing_customer: analysis_results['updated_items'].append((row_raw, status_message)); analysis_results['updated_count'] += 1
                    else: analysis_results['new_items'].append((row_raw, status_message)); analysis_results['new_count'] += 1
                    analysis_results['all_processed_data'].append({'musteri_kodu': musteri_kodu, 'ad': ad, 'telefon': str(row[COL_TELEFON] or '').strip(), 'adres': str(row[COL_ADRES] or '').strip(), 'vergi_dairesi': str(row[COL_VERGI_DAIRESI] or '').strip(), 'vergi_no': str(row[COL_VERGI_NO] or '').strip(), 'existing_id': existing_customer['id'] if existing_customer else None})
                except Exception as e: analysis_results['errors_details'].append((row_raw, f"Satır işlenirken hata: {e}")); analysis_results['error_count'] += 1
        except Exception as e:
            analysis_results['errors_details'].append((None, f"Analiz sırasında beklenmeyen bir hata oluştu: {e}. {traceback.format_exc()}")); analysis_results['error_count'] += 1
        finally:
            if conn_thread: conn_thread.close()
        return analysis_results
    
    def toplu_tedarikci_analiz_et(self, tedarikciler_data_raw):
        analysis_results = {'new_items': [], 'updated_items': [], 'errors_details': [], 'new_count': 0, 'updated_count': 0, 'error_count': 0, 'all_processed_data': []}
        conn_thread = None
        try:
            conn_thread = sqlite3.connect(self.db.db_name, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            conn_thread.row_factory = sqlite3.Row
            cursor_thread = conn_thread.cursor()
            for i, row in enumerate(tedarikciler_data_raw):
                try:
                    tedarikci_kodu, ad = str(row[0] or '').strip(), str(row[1] or '').strip()
                    if not tedarikci_kodu or not ad: analysis_results['errors_details'].append((row, "Kod veya Ad boş olamaz.")); analysis_results['error_count'] += 1; continue
                    cursor_thread.execute("SELECT id FROM tedarikciler WHERE tedarikci_kodu=?", (tedarikci_kodu,))
                    existing = cursor_thread.fetchone()
                    status_message = "Yeni tedarikçi." if not existing else "Güncellenecek."
                    if existing: analysis_results['updated_items'].append((row, status_message)); analysis_results['updated_count'] += 1
                    else: analysis_results['new_items'].append((row, status_message)); analysis_results['new_count'] += 1
                    analysis_results['all_processed_data'].append(row)
                except Exception as e: analysis_results['errors_details'].append((row, f"Hata: {e}")); analysis_results['error_count'] += 1
        except Exception as e:
            analysis_results['errors_details'].append((None, f"Analiz hatası: {e}. {traceback.format_exc()}")); analysis_results['error_count'] += 1
        finally:
            if conn_thread: conn_thread.close()
        return analysis_results
    
    def toplu_musteri_ekle_guncelle(self, processed_musteri_data):
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR: Metot artık transaction yönetmiyor. >>>
        if not processed_musteri_data:
            return True, "İşlenecek müşteri verisi bulunamadı."
        
        success_count = 0
        error_count = 0
        errors = []
        current_time = self.db.get_current_datetime_str()
        user_id = self.db._get_current_user_id()

        # Dışarıda başlatılan transaction içinde çalışır, kendi try/except'i kaldırıldı.
        for i, item_data in enumerate(processed_musteri_data):
            try:
                musteri_kodu = item_data.get('musteri_kodu', '').strip()
                ad = item_data.get('ad', '').strip()
                telefon = item_data.get('telefon', '').strip()
                adres = item_data.get('adres', '').strip()
                vergi_dairesi = item_data.get('vergi_dairesi', '').strip()
                vergi_no = item_data.get('vergi_no', '').strip()
                existing_id = item_data.get('existing_id')

                if not musteri_kodu and existing_id is None:
                    musteri_kodu = self.db.get_next_musteri_kodu()

                if existing_id is not None:
                    # Güncelleme işlemi
                    self.db.c.execute("""
                        UPDATE musteriler SET ad=?, telefon=?, adres=?, vergi_dairesi=?, vergi_no=?, 
                        son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? 
                        WHERE id=?
                    """, (ad, telefon, adres, vergi_dairesi, vergi_no, current_time, user_id, existing_id))
                else:
                    # Yeni Ekleme işlemi
                    self.db.c.execute("""
                        INSERT INTO musteriler (kod, ad, telefon, adres, vergi_dairesi, vergi_no, olusturma_tarihi_saat, olusturan_kullanici_id) 
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (musteri_kodu, ad, telefon, adres, vergi_dairesi, vergi_no, current_time, user_id))
                
                success_count += 1
            except Exception as e:
                errors.append(f"İşleme sırasında hata (Satır: {i+2}, Kod: {item_data.get('musteri_kodu', '')}): {e}")
                error_count += 1
        
        message = f"{success_count} kayıt başarıyla işlendi."
        if errors:
            message += f"\n{error_count} satırda hata oluştu: {'; '.join(errors[:3])}"
        return True, message
            
    def toplu_tedarikci_ekle_guncelle(self, tedarikciler_data):
        # <<< DEĞİŞİKLİK BURADA BAŞLIYOR: Metot artık transaction yönetmiyor. >>>
        if not tedarikciler_data:
            return True, "İşlenecek tedarikçi verisi bulunamadı."
        
        success_count = 0
        error_count = 0
        errors = []
        current_time = self.db.get_current_datetime_str()
        user_id = self.db._get_current_user_id()

        # Dışarıda başlatılan transaction içinde çalışır, kendi try/except'i kaldırıldı.
        for i, row in enumerate(tedarikciler_data):
            try:
                tedarikci_kodu = str(row[0]).strip()
                ad = str(row[1]).strip()
                telefon = str(row[2] or '').strip()
                adres = str(row[3] or '').strip()
                vergi_dairesi = str(row[4] or '').strip()
                vergi_no = str(row[5] or '').strip()

                self.db.c.execute("SELECT id FROM tedarikciler WHERE tedarikci_kodu = ?", (tedarikci_kodu,))
                existing_supplier = self.db.c.fetchone()

                if existing_supplier:
                    # Güncelleme
                    self.db.c.execute("""
                        UPDATE tedarikciler SET ad=?, telefon=?, adres=?, vergi_dairesi=?, vergi_no=?, 
                        son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? 
                        WHERE id=?
                    """, (ad, telefon, adres, vergi_dairesi, vergi_no, current_time, user_id, existing_supplier[0]))
                else:
                    # Yeni Ekleme
                    self.db.c.execute("""
                        INSERT INTO tedarikciler (tedarikci_kodu, ad, telefon, adres, vergi_dairesi, vergi_no, olusturma_tarihi_saat, olusturan_kullanici_id) 
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (tedarikci_kodu, ad, telefon, adres, vergi_dairesi, vergi_no, current_time, user_id))
                
                success_count += 1
            except Exception as e:
                errors.append(f"Satır {i+2} ({tedarikci_kodu}): {e}")
                error_count += 1
        
        message = f"{success_count} kayıt başarıyla işlendi."
        if errors:
            message += f"\n{error_count} satırda hata oluştu: {'; '.join(errors[:3])}"
        return True, message