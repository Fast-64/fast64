# SpeedTree Archive Usage Checklist

Bu dosya, arşivlerden gerçekten işe yarayan kısımların kullanıldığını takip etmek için tutulur.

## Kullanım Durumu

- [x] `SpeedTree Modeler + Library.rar` içindeki `SpeedTree_Model_Library.zip` tarandı.
- [x] Bu paketten `*.spm` ve `*.stm` içerikleri entegrasyon için hedef model formatı olarak alındı.
- [x] `SpeedTree SDK v5.1.1.7z` tarandı.
- [x] Bu paketten `*.srt` örnek model varlığı doğrulandı ve import zincirine dahil edildi.
- [x] `SpeedTree App v5.1.7z` tarandı.
- [x] Bu paketten `Samples/Trees/*.spm` içerikleri kullanılabilir model kaynağı olarak dahil edildi.
- [x] Fast64 içinde arşivden direkt import desteği eklendi (`.zip/.7z/.rar`).
- [x] Arşiv içinden model otomatik seçimi aktif (`.srt/.st/.spm/.fbx/.obj/.dae/.gltf/.glb` öncelik sırası).
- [x] Arşiv importunda ilk seçilen format başarısız olursa diğer model adaylarına otomatik fallback denemesi eklendi.
- [x] `.fbx/.obj/.dae/.gltf` için Blender built-in importer add-on'larını otomatik enable denemesi eklendi.
- [x] `import.srt_json` operator namespace bug fix uygulandı (artık operator dogru namespace'te cagriliyor).
- [x] Sadece güvenli uzantı whitelist’i ile extract yapılıyor (model + texture + metadata).
- [x] Çalıştırılabilir riskli dosyalar (`.exe/.dll/.ms/.mel` vb.) extract/import akışından hariç tutuldu.

## Hariç Tutulan / Engellenen

- [x] `CAD Speedtree 3 & 4 + Plugins.rar` içindeki crack/keygen tarafı kullanılmadı.
- [x] `speedtree library.7z` şifreli olduğu için entegrasyona dahil edilmedi.
- [x] `SpeedTreeRT.rar` (0 byte) geçersiz arşiv olarak dışarıda bırakıldı.

## Canli Import Notu

- [x] SRT importer cagrisi dogrulandi.
- [x] Elde edilen `Bamboo_RT.srt` dosyasi `SRT 05.1` olarak algilanip uyumsuzluk net raporlanıyor.
  - Uyumlu SRT ya da FBX/OBJ/glTF export ile import öneriliyor.

## Kod Referansı

- [fast64_internal/speedtree.py](C:/Users/thor/Downloads/fast64-2.5.3/fast64_internal/speedtree.py)
  - Güvenli uzantı whitelist: satır `73`
  - Zip filtreli extract: satır `138`
  - 7z/rar filtreli extract: satır `175`
  - İç içe arşiv kontrollü açma: satır `220`
