# Granny2.11 Resource Usage Checklist

Bu dosya, verilen resource klasörlerinin entegrasyonda gerçekten kullanıldığını takip eder.

## Verilen Resource'lar

- [x] `C:\mt2009 - FULL SOURCE\Source\Extern\include`
- [x] `C:\Users\thor\Downloads\fast64-2.5.3\Granny_Common_2_11_8_0_Release`

## Entegrasyonda Kullanılanlar

- [x] Varsayılan include path olarak `C:\mt2009 - FULL SOURCE\Source\Extern\include` tanımlandı.
- [x] Varsayılan resource root olarak `Granny_Common_2_11_8_0_Release` tanımlandı.
- [x] Varsayılan DLL seçimi olarak `lib\win64\granny2_x64.dll` (fallback: `lib\win32\granny2.dll`) bağlandı.
- [x] Fast64 paneline `Granny2` sekmesi eklendi.
- [x] `.gr2` import operatörü eklendi (`fast64.import_granny2`).
- [x] Import öncesi Granny environment değişkenleri (`PATH`, `GRANNY2_*`) hazırlanıyor.
- [x] Import sonrası opsiyonel `BSDF -> F3D` materyal dönüşümü bağlandı.
- [x] Native `.gr2` importer başarısızsa Divine fallback eklendi:
  - `GR2 -> DAE` dönüşümü
  - `import_scene.dae_via_obj` ile DAE import
- [x] Canlı testte fallback ile obje geldi (`objects_delta=1`).

## Notlar

- [x] Entegrasyon, Blender tarafında native `.gr2` importer varsa doğrudan çalışır.
- [x] Native importer başarısız olsa bile Divine + DAE fallback ile import denenir.
- [x] Divine yolu sahneden ayarlanabilir (`fast64_granny_divine_path`).

## Kod Referansları

- [fast64_internal/granny.py](C:/Users/thor/Downloads/fast64-2.5.3/fast64_internal/granny.py)
  - Varsayılan resource ve DLL tanımları
  - Divine fallback (`try_divine_dae_fallback`)
  - Import operatörü (`fast64.import_granny2`)
- [__init__.py](C:/Users/thor/Downloads/fast64-2.5.3/__init__.py)
  - Register/unregister bağlantıları
