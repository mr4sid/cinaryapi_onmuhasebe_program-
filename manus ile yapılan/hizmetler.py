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

    def fatura_olustur(self, fatura_no, tip, cari_id, kalemler, odeme_turu, kasa_banka_id=None, misafir_adi=None, fatura_notlari=None, vade_tarihi=None, genel_iskonto_tipi='YOK', genel_iskonto_degeri=0.0, original_fatura_id=None, manage_transaction=True):
        try:
            if manage_transaction: self.db.conn.execute("BEGIN TRANSACTION")
            
            is_perakende_satis = (tip == self.db.FATURA_TIP_SATIS and self.db.perakende_musteri_id is not None and str(cari_id) == str(self.db.perakende_musteri_id))
            if is_perakende_satis and odeme_turu == self.db.ODEME_TURU_ACIK_HESAP:
                raise ValueError("Perakende satışlarda 'AÇIK HESAP' ödeme türü kullanılamaz.")

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

            current_time, olusturan_id, tarih_str = self.db.get_current_datetime_str(), self.db._get_current_user_id(), datetime.now().strftime('%Y-%m-%d')

            self.db.c.execute("INSERT INTO faturalar (fatura_no, tarih, tip, cari_id, toplam_kdv_haric, toplam_kdv_dahil, odeme_turu, misafir_adi, kasa_banka_id, olusturma_tarihi_saat, olusturan_kullanici_id, fatura_notlari, vade_tarihi, genel_iskonto_tipi, genel_iskonto_degeri, original_fatura_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (fatura_no, tarih_str, tip, cari_id, nihai_toplam_kdv_haric, nihai_toplam_kdv_dahil, odeme_turu, misafir_adi, kasa_banka_id, current_time, olusturan_id, fatura_notlari, vade_tarihi, genel_iskonto_tipi, genel_iskonto_degeri, original_fatura_id))
            fatura_id = self.db.c.lastrowid

            for item in kalemler:
                urun_id, miktar, birim_fiyat, kdv, alis_fiyati, isk1, isk2, isk_tip, isk_deger = item
                iskontolu_bfh = self.db.safe_float(birim_fiyat) * (1-self.db.safe_float(isk1)/100) * (1-self.db.safe_float(isk2)/100)
                kdv_tutar = iskontolu_bfh * self.db.safe_float(miktar) * (self.db.safe_float(kdv)/100)
                toplam_haric = iskontolu_bfh * self.db.safe_float(miktar)
                toplam_dahil = toplam_haric + kdv_tutar
                
                self.db.c.execute("INSERT INTO fatura_kalemleri (fatura_id, urun_id, miktar, birim_fiyat, kdv_orani, kdv_tutari, kalem_toplam_kdv_haric, kalem_toplam_kdv_dahil, alis_fiyati_fatura_aninda, iskonto_yuzde_1, iskonto_yuzde_2, iskonto_tipi, iskonto_degeri, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (fatura_id, urun_id, miktar, birim_fiyat, kdv, kdv_tutar, toplam_haric, toplam_dahil, alis_fiyati, isk1, isk2, isk_tip, isk_deger, current_time, olusturan_id))
                
                # Stok Miktarı Güncelleme ve Stok Hareketi Kaydı
                stok_degisim_net = 0.0
                stok_islem_tipi = ""
                kaynak_tipi_stok = self.db.KAYNAK_TIP_FATURA

                if tip == self.db.FATURA_TIP_SATIS:
                    miktar_degisimi = -self.db.safe_float(miktar)
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_SATIS
                elif tip == self.db.FATURA_TIP_ALIS:
                    miktar_degisimi = self.db.safe_float(miktar)
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_ALIS
                elif tip == self.db.FATURA_TIP_SATIS_IADE:
                    miktar_degisimi = self.db.safe_float(miktar) # Satış iadesi stoğu artırır
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_SATIS_IADE
                    kaynak_tipi_stok = self.db.KAYNAK_TIP_IADE_FATURA
                elif tip == self.db.FATURA_TIP_ALIS_IADE:
                    miktar_degisimi = -self.db.safe_float(miktar) # Alış iadesi stoğu azaltır
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_ALIS_IADE
                    kaynak_tipi_stok = self.db.KAYNAK_TIP_IADE_FATURA
                elif tip == self.db.FATURA_TIP_DEVIR_GIRIS:
                    miktar_degisimi = self.db.safe_float(miktar)
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_DEVIR_GIRIS
                
                self.db._stok_guncelle_ve_hareket_kaydet(urun_id, miktar_degisimi, stok_islem_tipi, kaynak_tipi_stok, fatura_id, fatura_no)
            
            # KASA BAKİYESİ GÜNCELLEME MANTIĞI BURAYA GELİYOR
            if odeme_turu in self.db.pesin_odeme_turleri and kasa_banka_id is not None:
                # Satış faturası veya Alış İade faturası (kasa için gelir)
                if tip == self.db.FATURA_TIP_SATIS or tip == self.db.FATURA_TIP_ALIS_IADE:
                    self.db.kasa_banka_bakiye_guncelle(kasa_banka_id, nihai_toplam_kdv_dahil, artir=True)
                    logging.info(f"Fatura Oluşturma: Peşin {tip} faturası {fatura_no} için kasa/banka {kasa_banka_id} bakiyesi arttırıldı: {nihai_toplam_kdv_dahil}")
                # Alış faturası veya Satış İade faturası (kasa için gider)
                elif tip == self.db.FATURA_TIP_ALIS or tip == self.db.FATURA_TIP_SATIS_IADE:
                    self.db.kasa_banka_bakiye_guncelle(kasa_banka_id, nihai_toplam_kdv_dahil, artir=False)
                    logging.info(f"Fatura Oluşturma: Peşin {tip} faturası {fatura_no} için kasa/banka {kasa_banka_id} bakiyesi azaltıldı: {nihai_toplam_kdv_dahil}")
            
            # Fatura Finansal Etki Oluşturma (kasa_banka_id'yi artık bu metot kendisi güncellemediği için None olarak geçiyoruz.)
            yeni_fatura_bilgisi = self.db.fatura_getir_by_id(fatura_id) 
            self._fatura_finansal_etki_olustur(yeni_fatura_bilgisi, fatura_no, tip, tarih_str, cari_id, nihai_toplam_kdv_dahil, odeme_turu, None, is_perakende_satis) # kasa_banka_id'yi None olarak geçiyoruz.

            if manage_transaction: self.db.conn.commit()
            return True, fatura_id
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

    def fatura_guncelle(self, fatura_id, yeni_fatura_no, yeni_cari_id, yeni_odeme_turu, yeni_kalemler, kasa_banka_id=None, yeni_misafir_adi=None, yeni_fatura_notlari=None, yeni_vade_tarihi=None, genel_iskonto_tipi='YOK', genel_iskonto_degeri=0.0):
        try:
            self.db.conn.execute("BEGIN TRANSACTION")
            
            # 1. Adım: Güncellenecek faturanın eski bilgilerini al
            eski_fatura_bilgisi = self.db.fatura_getir_by_id(fatura_id)
            if not eski_fatura_bilgisi: raise ValueError("Güncellenecek fatura bulunamadı.")
            
            eski_toplam_kdv_dahil = eski_fatura_bilgisi['toplam_kdv_dahil']
            fatura_tipi = eski_fatura_bilgisi['tip']
            eski_odeme_turu = eski_fatura_bilgisi['odeme_turu']
            eski_kasa_banka_id = eski_fatura_bilgisi['kasa_banka_id']

            # 2. Adım: ESKİ fatura kalemlerini ve ilişkili STOK hareketlerini geri al
            eski_kalemler = self.db.fatura_detay_al(fatura_id)
            for kalem in eski_kalemler:
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

                if stok_degisim_yonu_orijinal != 0:
                    self.db._stok_guncelle_ve_hareket_kaydet(
                        kalem['urun_id'], stok_degisim_yonu_orijinal, 
                        f"{stok_islem_tipi_geri_al} (Güncelleme Öncesi Ters İşlem)", 
                        kaynak_tipi_geri_al, fatura_id, eski_fatura_bilgisi['fatura_no']
                    )

            # 3. Adım: ESKİ fatura kalemlerini veritabanından sil (sadece fatura_kalemleri)
            self.db.c.execute("DELETE FROM fatura_kalemleri WHERE fatura_id=?", (fatura_id,))

            # 4. Adım: Yeni bilgilere göre ana fatura kaydını GÜNCELLE (UPDATE)
            # Yeni toplamları hesapla
            toplam_kdv_haric_yeni, toplam_kdv_dahil_yeni = 0.0, 0.0
            for item in yeni_kalemler:
                urun_id, miktar, birim_fiyat_haric, kdv_orani, alis_fiyati, iskonto_yuzde_1, iskonto_yuzde_2, iskonto_tipi, iskonto_degeri = item

                miktar_f, birim_fiyat_haric_f, kdv_orani_f = self.db.safe_float(miktar), self.db.safe_float(birim_fiyat_haric), self.db.safe_float(kdv_orani)
                isk1, isk2 = self.db.safe_float(iskonto_yuzde_1), self.db.safe_float(iskonto_yuzde_2)
                
                iskontolu_birim_fiyat_haric = birim_fiyat_haric_f * (1 - isk1/100) * (1 - isk2/100)
                kalem_toplam_kdv_haric = miktar_f * iskontolu_birim_fiyat_haric
                kalem_toplam_kdv_dahil = kalem_toplam_kdv_haric * (1 + kdv_orani_f / 100)
                toplam_kdv_haric_yeni += kalem_toplam_kdv_haric
                toplam_kdv_dahil_yeni += kalem_toplam_kdv_dahil
            
            uygulanan_genel_iskonto = genel_iskonto_degeri if genel_iskonto_tipi == self.db.ISKONTO_TIP_TUTAR else toplam_kdv_haric_yeni * (self.db.safe_float(genel_iskonto_degeri) / 100)
            nihai_toplam_kdv_haric, nihai_toplam_kdv_dahil = toplam_kdv_haric_yeni - uygulanan_genel_iskonto, toplam_kdv_dahil_yeni - uygulanan_genel_iskonto
            
            self.db.c.execute("UPDATE faturalar SET fatura_no=?, cari_id=?, toplam_kdv_haric=?, toplam_kdv_dahil=?, odeme_turu=?, misafir_adi=?, kasa_banka_id=?, fatura_notlari=?, vade_tarihi=?, genel_iskonto_tipi=?, genel_iskonto_degeri=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=? WHERE id=?",
                             (yeni_fatura_no, yeni_cari_id, nihai_toplam_kdv_haric, nihai_toplam_kdv_dahil, yeni_odeme_turu, yeni_misafir_adi, kasa_banka_id, yeni_fatura_notlari, yeni_vade_tarihi, genel_iskonto_tipi, genel_iskonto_degeri, self.db.get_current_datetime_str(), self.db._get_current_user_id(), fatura_id))
            
            # 5. Adım: Yeni fatura kalemlerini ve ilişkili STOK hareketlerini yeniden oluştur
            current_time_for_items, olusturan_id_for_items = self.db.get_current_datetime_str(), self.db._get_current_user_id()
            for item in yeni_kalemler: 
                urun_id, miktar, birim_fiyat, kdv, alis_fiyati, isk1, isk2, isk_tip, isk_deger = item
                iskontolu_bfh = self.db.safe_float(birim_fiyat) * (1 - self.db.safe_float(isk1)/100) * (1 - self.db.safe_float(isk2)/100)
                kdv_tutar = iskontolu_bfh * self.db.safe_float(miktar) * (self.db.safe_float(kdv)/100)
                toplam_haric, toplam_dahil = iskontolu_bfh * self.db.safe_float(miktar), iskontolu_bfh * self.db.safe_float(miktar) + kdv_tutar
                self.db.c.execute("INSERT INTO fatura_kalemleri (fatura_id, urun_id, miktar, birim_fiyat, kdv_orani, kdv_tutari, kalem_toplam_kdv_haric, kalem_toplam_kdv_dahil, alis_fiyati_fatura_aninda, iskonto_yuzde_1, iskonto_yuzde_2, iskonto_tipi, iskonto_degeri, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                 (fatura_id, urun_id, miktar, birim_fiyat, kdv, kdv_tutar, toplam_haric, toplam_dahil, alis_fiyati, isk1, isk2, isk_tip, isk_deger, current_time_for_items, olusturan_id_for_items))
                
                # Yeni stok hareketini oluştur
                stok_degisim_net = 0.0
                stok_islem_tipi = ""
                kaynak_tipi_stok = self.db.KAYNAK_TIP_FATURA 

                if fatura_tipi == self.db.FATURA_TIP_SATIS:
                    stok_degisim_net = -self.db.safe_float(miktar)
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_SATIS
                elif fatura_tipi == self.db.FATURA_TIP_ALIS:
                    stok_degisim_net = self.db.safe_float(miktar)
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_ALIS
                elif fatura_tipi == self.db.FATURA_TIP_SATIS_IADE:
                    stok_degisim_net = self.db.safe_float(miktar) 
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_SATIS_IADE
                    kaynak_tipi_stok = self.db.KAYNAK_TIP_IADE_FATURA
                elif fatura_tipi == self.db.FATURA_TIP_ALIS_IADE:
                    stok_degisim_net = -self.db.safe_float(miktar) 
                    stok_islem_tipi = self.db.STOK_ISLEM_TIP_FATURA_ALIS_IADE
                    kaynak_tipi_stok = self.db.KAYNAK_TIP_IADE_FATURA
                
                self.db._stok_guncelle_ve_hareket_kaydet(urun_id, stok_degisim_net, stok_islem_tipi, kaynak_tipi_stok, fatura_id, yeni_fatura_no)
            
            # KASA BAKİYESİ GÜNCELLEME MANTIĞI BURAYA GELİYOR - DÜZELTME
            
            # Senaryo 1: Eski ödeme türü de peşindi ve yeni ödeme türü de peşin
            if eski_odeme_turu in self.db.pesin_odeme_turleri and yeni_odeme_turu in self.db.pesin_odeme_turleri:
                if eski_kasa_banka_id == kasa_banka_id: # Kasa değişmedi, sadece tutar değişti
                    net_fark = nihai_toplam_kdv_dahil - eski_toplam_kdv_dahil
                    if net_fark != 0:
                        is_artir_net_fark = True
                        if (fatura_tipi == self.db.FATURA_TIP_SATIS and net_fark < 0) or \
                           (fatura_tipi == self.db.FATURA_TIP_ALIS_IADE and net_fark < 0) or \
                           (fatura_tipi == self.db.FATURA_TIP_ALIS and net_fark > 0) or \
                           (fatura_tipi == self.db.FATURA_TIP_SATIS_IADE and net_fark > 0):
                            is_artir_net_fark = False # Net fark, fatura tipine göre ters etki yapıyorsa azalt
                        
                        self.db.kasa_banka_bakiye_guncelle(kasa_banka_id, abs(net_fark), artir=is_artir_net_fark)
                        logging.info(f"Fatura Güncelleme: Peşin->Peşin (Kasa Aynı). Kasa {kasa_banka_id} bakiyesi net fark {net_fark} kadar güncellendi.")
                else: # Kasa değişti
                    # Eski kasadan eski tutarı ters yönde al
                    is_artir_eski_kasa_geri_al = True if fatura_tipi in [self.db.FATURA_TIP_ALIS, self.db.FATURA_TIP_SATIS_IADE] else False
                    self.db.kasa_banka_bakiye_guncelle(eski_kasa_banka_id, eski_toplam_kdv_dahil, artir=is_artir_eski_kasa_geri_al)
                    logging.info(f"Fatura Güncelleme: Peşin->Peşin (Kasa Değişimi). Eski kasa {eski_kasa_banka_id} bakiyesi geri alındı: {eski_toplam_kdv_dahil}.")
                    
                    # Yeni kasaya yeni tutarı ekle
                    is_artir_yeni_kasa_ekle = True if fatura_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_ALIS_IADE] else False
                    self.db.kasa_banka_bakiye_guncelle(kasa_banka_id, nihai_toplam_kdv_dahil, artir=is_artir_yeni_kasa_ekle)
                    logging.info(f"Fatura Güncelleme: Peşin->Peşin (Kasa Değişimi). Yeni kasa {kasa_banka_id} bakiyesi uygulandı: {nihai_toplam_kdv_dahil}.")
            
            # Senaryo 2: Açık hesaptan peşine dönüşüm (ÖNERİLEN BLOK BURAYA GELDİ)
            # Bu durumda kasa, daha önce fatura ile etkilenmemişti. Şimdi tam tutar kadar etkilenmeli.
            elif eski_odeme_turu == self.db.ODEME_TURU_ACIK_HESAP and yeni_odeme_turu in self.db.pesin_odeme_turleri:
                # Kasa bakiyesini artır (faturanın yeni tutarı kadar)
                # Satış faturası veya Alış İade faturası (kasaya giriş)
                is_artir_yeni = True if fatura_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_ALIS_IADE] else False
                self.db.kasa_banka_bakiye_guncelle(kasa_banka_id, nihai_toplam_kdv_dahil, artir=is_artir_yeni)
                logging.info(f"Fatura Güncelleme: Açık Hesap->Peşin. Kasa {kasa_banka_id} bakiyesi güncellendi: {nihai_toplam_kdv_dahil}.")
            
            # Senaryo 3: Peşinden açık hesaba dönüşüm
            # Bu durumda kasanın eski etkisini geri almalıyız.
            elif eski_odeme_turu in self.db.pesin_odeme_turleri and yeni_odeme_turu == self.db.ODEME_TURU_ACIK_HESAP:
                # Kasa bakiyesinden eski tutarı geri al (kasadan çıkış)
                is_artir_geri_al = True if fatura_tipi in [self.db.FATURA_TIP_ALIS, self.db.FATURA_TIP_SATIS_IADE] else False
                self.db.kasa_banka_bakiye_guncelle(eski_kasa_banka_id, eski_toplam_kdv_dahil, artir=is_artir_geri_al)
                logging.info(f"Fatura Güncelleme: Peşin->Açık Hesap. Kasa {eski_kasa_banka_id} bakiyesi geri alındı: {eski_toplam_kdv_dahil}.")

            # Diğer durumlar (açık hesaptan açık hesaba, etkisiz fatura vb.) için kasa etkisi olmaz.
            
            # Finansal kayıtları oluştur (cari hareketler ve gelir/gider)
            # NOT: Bu metodun kendi içinde kasa_banka_bakiye_guncelleme yapmadığından emin olun.
            self._fatura_finansal_etki_olustur(
                fatura_ana_bilgileri=eski_fatura_bilgisi, 
                fatura_no=yeni_fatura_no, 
                fatura_tipi=fatura_tipi, 
                tarih=eski_fatura_bilgisi['tarih'], 
                cari_id=yeni_cari_id, 
                tutar=nihai_toplam_kdv_dahil, 
                odeme_turu=yeni_odeme_turu, 
                kasa_banka_id=kasa_banka_id, # Kasa güncellemesi bu metodun dışında yapıldığı için, bu ID sadece finansal kayıtlarda referans olarak tutulacak.
                is_perakende_satis=(yeni_cari_id == self.db.perakende_musteri_id and fatura_tipi == self.db.FATURA_TIP_SATIS)
            )

            logging.info(f"Fatura güncelleme: Fatura ID {fatura_id}, No '{yeni_fatura_no}' finansal etkileri güncellendi.")
            
            self.db.conn.commit()
            return True, f"Fatura '{yeni_fatura_no}' başarıyla güncellendi."
        except Exception as e:
            self.db.conn.rollback()
            logging.error(f"FaturaServis.fatura_guncelle Hata: {e}\n{traceback.format_exc()}")
            return False, f"Fatura güncellenemedi. Hata: {e}"
                                                                
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
                
    def _fatura_finansal_etki_olustur(self, fatura_ana_bilgileri, fatura_no, fatura_tipi, tarih, cari_id, tutar, odeme_turu, kasa_banka_id, is_perakende_satis):
        try:
            olusturan_id = self.db._get_current_user_id()
            current_time = self.db.get_current_datetime_str()
            cari_tip_str = self.db.CARI_TIP_MUSTERI if fatura_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE] else self.db.CARI_TIP_TEDARIKCI
            
            cari_bilgi = self.db.musteri_getir_by_id(cari_id) if cari_tip_str == self.db.CARI_TIP_MUSTERI else self.db.tedarikci_getir_by_id(cari_id)
            cari_adi_hareket = cari_bilgi['ad'] if cari_bilgi else ""
            fatura_id = fatura_ana_bilgileri['id']

            # --- Cari Hareket Oluşturma/Güncelleme ---
            if not is_perakende_satis and odeme_turu != self.db.ODEME_TURU_ETKISIZ_FATURA:
                islem_tipi_ana_cari_hareket, referans_tip_ana_cari_hareket = None, None

                if fatura_tipi == self.db.FATURA_TIP_SATIS:
                    islem_tipi_ana_cari_hareket = self.db.ISLEM_TIP_ALACAK
                    referans_tip_ana_cari_hareket = self.db.KAYNAK_TIP_FATURA
                elif fatura_tipi == self.db.FATURA_TIP_ALIS:
                    islem_tipi_ana_cari_hareket = self.db.ISLEM_TIP_BORC
                    referans_tip_ana_cari_hareket = self.db.KAYNAK_TIP_FATURA
                elif fatura_tipi == self.db.FATURA_TIP_SATIS_IADE:
                    islem_tipi_ana_cari_hareket = self.db.ISLEM_TIP_BORC
                    referans_tip_ana_cari_hareket = self.db.KAYNAK_TIP_IADE_FATURA
                elif fatura_tipi == self.db.FATURA_TIP_ALIS_IADE:
                    islem_tipi_ana_cari_hareket = self.db.ISLEM_TIP_ALACAK
                    referans_tip_ana_cari_hareket = self.db.KAYNAK_TIP_IADE_FATURA
                
                if islem_tipi_ana_cari_hareket:
                    self.db.c.execute("""
                        SELECT id FROM cari_hareketler 
                        WHERE referans_id = ? 
                          AND referans_tip IN (?, ?) 
                          AND cari_tip = ? 
                          AND islem_tipi = ? 
                    """, (fatura_id, self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA, 
                          cari_tip_str, islem_tipi_ana_cari_hareket))
                    existing_main_cari_hareket = self.db.c.fetchone()

                    if existing_main_cari_hareket:
                        self.db.c.execute("""
                            UPDATE cari_hareketler SET tarih=?, cari_id=?, islem_tipi=?, tutar=?, 
                            aciklama=?, referans_tip=?, son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=?
                            WHERE id=?
                        """, (tarih, cari_id, islem_tipi_ana_cari_hareket, tutar, 
                              f"{fatura_tipi} No: {fatura_no}", referans_tip_ana_cari_hareket, current_time, olusturan_id, 
                              existing_main_cari_hareket['id']))
                    else:
                        self.db.c.execute("INSERT INTO cari_hareketler (tarih, cari_tip, cari_id, islem_tipi, tutar, aciklama, referans_id, referans_tip, olusturma_tarihi_saat, olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                          (tarih, cari_tip_str, cari_id, islem_tipi_ana_cari_hareket, tutar, 
                                           f"{fatura_tipi} No: {fatura_no}", fatura_id, referans_tip_ana_cari_hareket, current_time, olusturan_id))
            else:
                self.db.c.execute("""
                    DELETE FROM cari_hareketler 
                    WHERE referans_id = ? 
                      AND referans_tip IN (?, ?) 
                      AND cari_tip = ? 
                      AND islem_tipi IN (?, ?)
                """, (fatura_id, self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA, 
                      cari_tip_str, self.db.ISLEM_TIP_ALACAK, self.db.ISLEM_TIP_BORC))


            # --- Peşin Ödeme Etkileri (Gelir/Gider ve Kapatıcı Cari Hareket) Oluşturma/Güncelleme ---
            if odeme_turu in self.db.pesin_odeme_turleri:
                gg_tip, gg_aciklama_prefix = None, "Peşin"
                islem_tipi_kapatma = None 
                referans_tip_pesin_cari_ve_gg = None

                if fatura_tipi == self.db.FATURA_TIP_SATIS:
                    gg_tip = self.db.ISLEM_TIP_GELIR
                    islem_tipi_kapatma = self.db.ISLEM_TIP_TAHSILAT
                    referans_tip_pesin_cari_ve_gg = self.db.KAYNAK_TIP_FATURA_SATIS_PESIN
                elif fatura_tipi == self.db.FATURA_TIP_ALIS:
                    gg_tip = self.db.ISLEM_TIP_GIDER
                    islem_tipi_kapatma = self.db.ISLEM_TIP_ODEME
                    referans_tip_pesin_cari_ve_gg = self.db.KAYNAK_TIP_FATURA_ALIS_PESIN
                elif fatura_tipi == self.db.FATURA_TIP_SATIS_IADE:
                    gg_tip = self.db.ISLEM_TIP_GIDER
                    gg_aciklama_prefix = "İade"
                    islem_tipi_kapatma = self.db.ISLEM_TIP_ODEME 
                    referans_tip_pesin_cari_ve_gg = self.db.KAYNAK_TIP_IADE_FATURA_SATIS_PESIN
                elif fatura_tipi == self.db.FATURA_TIP_ALIS_IADE:
                    gg_tip = self.db.ISLEM_TIP_GELIR
                    gg_aciklama_prefix = "İade"
                    islem_tipi_kapatma = self.db.ISLEM_TIP_TAHSILAT 
                    referans_tip_pesin_cari_ve_gg = self.db.KAYNAK_TIP_IADE_FATURA_ALIS_PESIN
                    
                gg_aciklama = f"{gg_aciklama_prefix} {fatura_tipi}: {fatura_no} - Cari: {cari_adi_hareket}"

                # Gelir/Gider kaydını bul veya ekle/güncelle
                self.db.c.execute("SELECT id FROM gelir_gider WHERE kaynak_id = ? AND kaynak = ?", (fatura_id, referans_tip_pesin_cari_ve_gg))
                existing_gg_hareket = self.db.c.fetchone()

                if existing_gg_hareket:
                    self.db.c.execute("""
                        UPDATE gelir_gider SET tarih=?, tip=?, tutar=?, aciklama=?, kasa_banka_id=?,
                        son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=?
                        WHERE id=?
                    """, (tarih, gg_tip, tutar, gg_aciklama, kasa_banka_id, # kasa_banka_id'yi olduğu gibi kullanıyoruz (None ise None kalır)
                          current_time, olusturan_id, existing_gg_hareket['id']))
                else:
                    self.db.c.execute("INSERT INTO gelir_gider (tarih,tip,tutar,aciklama,kaynak,kaynak_id, kasa_banka_id,olusturma_tarihi_saat,olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?)",
                                (tarih, gg_tip, tutar, gg_aciklama, referans_tip_pesin_cari_ve_gg, fatura_id, kasa_banka_id, current_time, olusturan_id)) # kasa_banka_id'yi olduğu gibi kullanıyoruz (None ise None kalır)

                # Perakende olmayan satışlar için kapatıcı cari hareketi bul veya ekle/güncelle
                if not is_perakende_satis and islem_tipi_kapatma:
                    aciklama_kapatma = f"Peşin Fatura Ödemesi/İadesi: {fatura_no}"
                    
                    self.db.c.execute("SELECT id FROM cari_hareketler WHERE referans_id = ? AND referans_tip = ? AND cari_id = ? AND islem_tipi = ?", 
                                    (fatura_id, referans_tip_pesin_cari_ve_gg, cari_id, islem_tipi_kapatma))
                    existing_closing_cari_hareket = self.db.c.fetchone()

                    if existing_closing_cari_hareket:
                        self.db.c.execute("""
                            UPDATE cari_hareketler SET tarih=?, cari_tip=?, cari_id=?, islem_tipi=?, tutar=?, aciklama=?, kasa_banka_id=?,
                            son_guncelleme_tarihi_saat=?, son_guncelleyen_kullanici_id=?
                            WHERE id=?
                        """, (tarih, cari_tip_str, cari_id, islem_tipi_kapatma, tutar, aciklama_kapatma, kasa_banka_id, # kasa_banka_id'yi olduğu gibi kullanıyoruz (None ise None kalır)
                            current_time, olusturan_id, existing_closing_cari_hareket['id']))
                    else:
                        self.db.c.execute("INSERT INTO cari_hareketler (tarih,cari_tip,cari_id,islem_tipi,tutar,aciklama,referans_id,referans_tip,kasa_banka_id,olusturma_tarihi_saat,olusturan_kullanici_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                        (tarih, cari_tip_str, cari_id, islem_tipi_kapatma, tutar, aciklama_kapatma, fatura_id, referans_tip_pesin_cari_ve_gg, kasa_banka_id, current_time, olusturan_id)) # kasa_banka_id'yi olduğu gibi kullanıyoruz (None ise None kalır)
            else:
                self.db.c.execute("DELETE FROM gelir_gider WHERE kaynak_id=? AND kaynak IN (?, ?, ?, ?)", 
                                  (fatura_id, self.db.KAYNAK_TIP_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_FATURA_ALIS_PESIN,
                                   self.db.KAYNAK_TIP_IADE_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_IADE_FATURA_ALIS_PESIN)) 
                self.db.c.execute("DELETE FROM cari_hareketler WHERE referans_id=? AND referans_tip IN (?, ?, ?, ?)", 
                                  (fatura_id, self.db.KAYNAK_TIP_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_FATURA_ALIS_PESIN,
                                   self.db.KAYNAK_TIP_IADE_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_IADE_FATURA_ALIS_PESIN)) 

        except Exception as e:
            logging.error(f"FaturaServis._fatura_finansal_etki_olustur Hata: {e}\n{traceback.format_exc()}")
            raise 

    def _fatura_finansal_etki_sil(self, fatura_id, fatura_ana_bilgileri):
        """
        Bir fatura ile ilişkili tüm finansal hareket kayıtlarını (gelir/gider ve cari) siler
        ve kasa/banka bakiyelerini düzeltir.
        Args:
            fatura_id (int): Silinecek faturanın ID'si.
            fatura_ana_bilgileri (sqlite3.Row): Faturanın ana bilgileri (tip, odeme_turu, kasa_banka_id, toplam_kdv_dahil)
        """
        fatura_tipi = fatura_ana_bilgileri['tip']
        odeme_turu = fatura_ana_bilgileri['odeme_turu']
        kasa_banka_id = fatura_ana_bilgileri['kasa_banka_id']
        toplam_kdv_dahil = fatura_ana_bilgileri['toplam_kdv_dahil']

        # 1. Kasa/Banka etkisini geri al (Eğer peşin bir işlem idiyse)
        # Bu kısım, silme ve güncelleme işlemlerinde otomatik olarak tetiklenen
        # FaturaService.fatura_sil ve FaturaService.fatura_guncelle metotları içindeki
        # ana bakiye düzeltmeleriyle çakışabilir.
        # Bu metot sadece finansal kayıtları silmeli, bakiye düzeltmesini dışarı bırakmalıyız.
        # ANCAK, FaturaService.fatura_guncelle metodunda `_fatura_finansal_etki_olustur` metodu içinde
        # `kasa_banka_bakiye_guncelle` çağrısı zaten yapıldığı için, burada sadece silme işlemleri kalmalı.
        
        # Bu metodun görevi: SADECE gelir_gider ve cari_hareketler tablosundaki kayıtları silmek.
        # Kasa bakiyesi güncellemeleri fatura_guncelle veya fatura_sil metodlarının kendisinde yapılmalı.

        # 2. Gelir/Gider kayıtlarını sil (ilgili kaynak ID ve kaynağa göre)
        self.db.c.execute("DELETE FROM gelir_gider WHERE kaynak_id=? AND kaynak IN (?, ?, ?, ?)", 
                          (fatura_id, self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA, 
                           self.db.KAYNAK_TIP_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_FATURA_ALIS_PESIN))
        logging.info(f"Fatura ID {fatura_id} ile ilişkili gelir_gider kayıtları silindi.")
        
        # 3. Cari hareketleri sil (ilgili referans ID ve referans tipine göre)
        # Sadece fatura, iade fatura, peşin fatura ödemesi/tahsilatı olan cari hareketleri siliyoruz.
        # Manuel tahsilat/ödeme/veresiye borçlarını silmiyoruz (faturayla direkt ilişkili değillerse).
        self.db.c.execute("DELETE FROM cari_hareketler WHERE referans_id=? AND referans_tip IN (?, ?, ?, ?)", 
                         (fatura_id, self.db.KAYNAK_TIP_FATURA, self.db.KAYNAK_TIP_IADE_FATURA, 
                          self.db.KAYNAK_TIP_FATURA_SATIS_PESIN, self.db.KAYNAK_TIP_FATURA_ALIS_PESIN))
        logging.info(f"Fatura ID {fatura_id} ile ilişkili cari_hareketler kayıtları silindi.")
        
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