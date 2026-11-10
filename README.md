# YouTube Shorts otomatik paylaşım

`videos/` klasöründeki videoları günde 15 kez (12:07–02:07 TR arası saatte bir) sırayla YouTube kanalına yükler.
Başlık, açıklama ve etiketler dosya adından İngilizce üretilir; aynı türden iki video art arda gelmez.

## Kurulum (bir kerelik)

1. **Google Cloud projesi:** <https://console.cloud.google.com> → yeni proje → "YouTube Data API v3"ü etkinleştir.
2. **OAuth izin ekranı:** "External" seç, uygulamayı **"In production"** durumuna al.
   "Testing" durumunda bırakırsan yetki 7 günde bir sona erer ve paylaşım durur.
3. **OAuth istemcisi:** Credentials → Create credentials → OAuth client ID → tür **Desktop app** → JSON dosyasını indir.
4. **Yetki ver:** kendi bilgisayarında:
   ```bash
   python scripts/get_token.py client_secret.json
   ```
   Tarayıcıda kanalının hesabıyla izin ver. Betik üç değer yazdırır.
5. **GitHub secret'ları:** depo → Settings → Secrets and variables → Actions → şu üçünü ekle:
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
6. **Videoları yükle:** `.mp4` dosyalarını `videos/` klasörüne koyup gönder (dosya başına en fazla 100 MB).
7. **Dene:** Actions → "YouTube Shorts paylas" → Run workflow. Önce `dry_run` işaretli, sonra `privacy: private` ile bir deneme yap.

## Önemli: videoların herkese açık olması

Google, denetimden geçmemiş API projeleriyle yüklenen videoları **özel (private) olarak kilitler**.
Herkese açık paylaşım için "YouTube API Services – Audit and Quota Extension Form" doldurulmalı.
Onay gelene kadar videolar yüklenir ama özel kalır; YouTube Studio'dan elle açamazsın.

## Ayarlar

| Ne | Nerede |
| --- | --- |
| Paylaşım saatleri ve sıklığı | `.github/workflows/publish.yml` içindeki `cron` satırları (UTC) |
| Tür başlıkları, açıklama şablonu, etiketler | `metadata/categories.json` |
| Tek bir videoya özel başlık | `metadata/overrides.json` |
| Yayınlananların kaydı | `state/published.json` (otomatik güncellenir) |

Kuyruğu ve üretilecek başlıkları görmek için:

```bash
python scripts/upload.py --plan
```

Not: zamanlanmış çalışma yalnızca deponun varsayılan dalındaki (main) iş akışı için tetiklenir.
