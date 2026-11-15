# Audio/Video Data Converter

Lokale Web-App, die beliebige Dateien **unsichtbar in ein Video oder eine Audiodatei
einbettet** und sie später **bit-genau wieder extrahiert** – mit SHA-256-Prüfung jeder Datei.
Stack: Python · FastAPI · ffmpeg · numpy, schlankes HTML/JS-Frontend (Deutsch/Englisch umschaltbar),
ein einziger Container. Dies wurde mit KI umgesetzt.

## Start

```bash
docker compose up --build
```

Danach im Browser: <http://127.0.0.1:8080>

- Der Port ist nur an `127.0.0.1` gebunden (nur lokal erreichbar), es gibt keinen Login.
- Keine Volumes, keine Persistenz – siehe [Betrieb](#betrieb).

| Variable            | Standard | Bedeutung                                                        |
|---------------------|---------:|------------------------------------------------------------------|
| `MAX_UPLOAD_MB`     | `2048`   | Max. Größe eines Uploads (Request) in MB                          |
| `JOB_TTL_MIN`       | `30`     | Nicht abgeholte Ergebnisse werden nach dieser Zeit gelöscht       |
| `MAX_PARALLEL_JOBS` | `2`      | Gleichzeitig laufende Encode-/Decode-Jobs                         |

Beispiel: `MAX_UPLOAD_MB=500 docker compose up --build`

### Tests

```bash
WITH_TESTS=1 docker compose build
docker compose run --rm avdc python -m pytest -q -p no:cacheprovider
```

Ohne Docker: `pip install -r requirements-dev.txt` (ffmpeg muss installiert sein), dann `pytest -q`.
Die Tests erzeugen Testmedien mit ffmpeg und prüfen u. a. den Roundtrip Encode → Decode für
Video, Audio und Video mit Ton, jeweils mit/ohne Passwort und mit/ohne Reed-Solomon
(SHA-256 muss übereinstimmen), die Verteilung einer Datei über Bild **und** Ton, die
automatische Kapazitätserhöhung, Passwortfehler, die REST-API inkl. Löschen nach Download
und dass sich nur die LSBs ausgewählter Frames ändern.

## Bedienung

**Encode**
1. Quellmedium (Video oder Audio) wählen → wird sofort hochgeladen und analysiert.
2. Eine oder mehrere Dateien hinzufügen.
3. Optionen: Passwort (optional), Träger-Frames pro Sekunde (Standard 1), Bits pro Kanal
   (1–4, Standard 2), Reed-Solomon, Ausgabe-Codec (FFV1 oder H.264 lossless) bzw. für Audio FLAC/WAV.
4. Die Kapazität wird live angezeigt (aktuelle Einstellung, Maximum, Bedarf).
5. „Encode starten“ → Ergebnis herunterladen (danach wird es auf dem Server gelöscht).

**Decode**
Konvertiertes Medium (+ Passwort, falls gesetzt) hochladen. Angezeigt werden Parameter,
Manifest, eine Timeline (welche Datei in welchen Frames / Audio-Bereichen liegt) und der
SHA-256-Status jeder Datei (gültig/ungültig). Jede Datei ist einzeln herunterladbar.

## Funktionsweise

### Payload-Pipeline

```
Datei ─► zstd ─► [AES-256-GCM] ─► [Reed-Solomon RS(255,223)] ─► Payload-Stream ─► LSB-Einbettung
```

- Jede Datei wird **einzeln** verarbeitet und liegt als zusammenhängender Block im Payload-Stream.
  Dadurch kann das Manifest für jede Datei genau angeben, in welchen Frames/Audio-Bereichen sie
  steckt, und jede Datei wird unabhängig geprüft.
- **zstd** (Level 6, mit Prüfsumme).
- **AES-256-GCM** (bei Passwort): Schlüssel aus **Argon2id** (t=3, m=64 MiB, p=4; Fallback
  PBKDF2-SHA256 600 000 Iterationen) mit zufälligem 16-Byte-Salt. Verschlüsselt wird in
  16-MiB-Blöcken mit eigenem Nonce und Tag; Dateiindex, Blockindex und „letzter Block“ sind als AAD
  gebunden (kein Vertauschen/Abschneiden möglich). Auch das Manifest (Dateinamen etc.) ist dann
  verschlüsselt.
- **Reed-Solomon** (optional): RS(255,223), korrigiert bis zu 16 fehlerhafte Bytes je 255-Byte-Block.
  Die Kodierung ist mit numpy vektorisiert; nur tatsächlich beschädigte Blöcke werden mit
  `reedsolo` korrigiert.
- Nach dem Extrahieren wird die **SHA-256** jeder Datei mit dem Manifest verglichen.

### Einbettung

| Träger | Verfahren | Ausgabe |
|---|---|---|
| Video | LSBs der R/G/B-Werte **ausgewählter echter Frames** (Standard 1 Frame/s, 2 Bit). Kein Ersetzen von Frames. | MKV, **FFV1** (gbrp) oder **H.264 lossless** (libx264rgb, qp 0) |
| Tonspur im Video | LSBs der 16-Bit-Samples, 1-Sekunden-Blöcke | **FLAC** in derselben MKV |
| Audio | LSBs der 16-Bit-Samples, 1-Sekunden-Blöcke | **FLAC** oder **WAV** |

- Alle Träger-Segmente (Video-Frames und Audio-Sekunden) werden **chronologisch** sortiert und
  nacheinander gefüllt – eine Datei darf sich also über Bild und Ton verteilen.
- **Pseudozufällige Verteilung**: Welche Frames pro Sekunde genutzt werden und welche
  Pixel-/Sample-Positionen innerhalb eines Segments Bits tragen, bestimmt ein PRNG
  (numpy PCG64). Der Seed wird aus dem Passwort abgeleitet (über Argon2id), ohne Passwort
  ist er fest.
- Ein nur teilweise gefülltes Segment verändert nur zufällig verstreute Positionen.
- **Automatische Anpassung**: Reicht die Kapazität nicht, werden zuerst mehr Frames pro Sekunde
  (2, 3, 5, 10, … bis alle Frames), danach mehr Bits (bis 4) genutzt. Reicht auch das nicht,
  kommt ein Fehler mit der maximal möglichen Kapazität.

### Header

Der Header liegt unsichtbar in den **ersten 1–2 Sekunden**: in Frame 0 (bei Bedarf 1, 2, …)
bzw. bei reinem Audio in der ersten (und ggf. zweiten) Audio-Sekunde – immer mit 2 Bit und
festem Seed, damit der Decoder ihn ohne Vorwissen findet.

```
Präfix (16 B):  "AVDC" | Version | Flags (verschl., RS, Video, Audio) | reserviert | Body-Länge | CRC32(Präfix)
Body:           Länge + Parameter-JSON (Bits, Frames/s, Seed-Modus, KDF+Salt, Mediengeometrie, Stream-Länge)
                Länge + Manifest (zstd-JSON; bei Passwort AES-256-GCM-verschlüsselt):
                        je Datei: Name, Größe, SHA-256, Offset, Längen, Nonce, Frames, Audio-Bereiche
                SHA-256 über den gesamten Body
                (bei aktiviertem RS ist der Body zusätzlich RS-geschützt)
```

## Kapazitätsformeln

Bezeichnungen: `W×H` Auflösung, `b` Bits pro Kanal (1–4), `k` Träger-Frames pro Sekunde,
`f` Bildrate, `T` Dauer in s, `R` Abtastrate, `C` Anzahl Audiokanäle.

```
Kapazität pro Video-Frame   C_frame = floor(W · H · 3 · b / 8)          Bytes
Träger-Frames               N_sel   = Σ über Sekunden min(k, Frames dieser Sekunde) − Header-Frames
                                    ≈ min(k, f) · T − 1
Video gesamt                C_video = N_sel · C_frame
Tonspur / Audio             C_audio = Σ über Sekunden floor(n_s · C · b / 8)  ≈ R · C · b / 8 · T
                            (bei reinem Audio abzüglich der 1–2 Header-Sekunden)
Gesamt                      C       = C_video + C_audio
Maximum                     k = alle Frames, b = 4
```

Bedarf: `Σ komprimierte Dateigrößen`, + 16 B je 16 MiB bei Verschlüsselung, × 255/223 (+14,3 %) mit
Reed-Solomon. Die UI zeigt den Bedarf konservativ **unkomprimiert** an; Kompression kann helfen.

Beispiele (b = 2, k = 1):

| Medium | pro Segment | Kapazität |
|---|---|---|
| 1080p, 30 fps, 60 s | 1 920·1 080·3·2/8 = 1 555 200 B ≈ 1,48 MiB/Frame | 59 Frames ≈ **87,5 MiB** |
| + Stereo-Ton 48 kHz, 60 s | 48 000·2·2/8 = 24 000 B/s | **+1,37 MiB** |
| 720p, 25 fps, 10 min, b = 4, alle Frames | 1 382 400 B/Frame | 15 000 Frames ≈ **19,3 GiB** (theoretisch) |
| WAV 44,1 kHz Stereo, 3 min | 22 050 B/s | ≈ **3,7 MiB** |

## Betrieb

- Uploads (Quellmedium und Dateien) werden **unmittelbar nach der Verarbeitung gelöscht**.
- Das Ergebnis eines Encodes wird **nach dem Download gelöscht**; extrahierte Dateien jeweils
  nach ihrem Download (wenn alle geladen sind, wird der ganze Job entfernt).
- Nicht abgeholte Ergebnisse werden nach `JOB_TTL_MIN` Minuten gelöscht; beim Start und Stopp
  wird das Arbeitsverzeichnis geleert. Kein Volume, keine Datenbank.
- Upload-Limit über `MAX_UPLOAD_MB` (Standard 2 GB, geprüft über `Content-Length` und beim Speichern).

## Grenzen – bitte lesen

- **Jedes erneute verlustbehaftete Kodieren zerstört die Daten.** Dazu gehören: Hochladen auf
  YouTube/Instagram/WhatsApp/Messenger, Umwandeln nach MP4/H.264/H.265/VP9/AV1 (nicht-lossless),
  MP3/AAC/Opus, Skalieren, Zuschneiden, Farbraum- oder Bildratenänderung, Resampling, Lautstärke-
  normalisierung. Reed-Solomon hilft dagegen **nicht** – er repariert nur vereinzelte Bitfehler.
  Die Ausgabedatei nur als Datei kopieren/übertragen (z. B. als ZIP, Cloud-Speicher, USB).
- **Ausgabe ist deutlich größer** als das Quellvideo (verlustfreies RGB, FFV1/H.264 lossless).
- Video wird intern in **8-Bit-RGB** (rgb24) verarbeitet: HDR/10-Bit/Alpha gehen verloren, die
  Farben werden einmalig von YUV nach RGB konvertiert. Audio wird in **16-Bit-PCM** verarbeitet
  (24/32-Bit-Quellen werden reduziert). Variable Bildraten werden konstant.
- Es werden nur der **erste Videostream** und der **erste Audiostream** übernommen; Untertitel,
  weitere Tonspuren und Kapitel entfallen.
- Sichtbarkeit: 2 Bit ändern einen Farbwert um höchstens ±3 von 255 – praktisch unsichtbar,
  und nur ~1 Frame pro Sekunde wird verändert. Bei 4 Bit (±15) und/oder allen Frames kann in
  großen, glatten Flächen leichtes Rauschen sichtbar werden; bei 3–4 Bit im Ton ein leises Rauschen
  in sehr leisen Passagen.
- **Keine Tarnung gegen Steganalyse**: LSB-Einbettung ist statistisch erkennbar. Das Passwort
  schützt den **Inhalt** (AES-256-GCM) und die Positionen, nicht die Tatsache, dass Daten enthalten sind.
  Ohne Passwort kann jeder mit diesem Tool die Dateien extrahieren.
- Der Header muss in die ersten 2 Sekunden passen – bei sehr kleinen Medien begrenzt das die Anzahl
  der Dateien (Fehlermeldung, falls nicht).
- Speicherbedarf: Beim Decode wird jede Datei einzeln im RAM rekonstruiert (≈ 2–3× ihre Größe).
  Ein-/Ausgabe der Medien läuft gestreamt über ffmpeg bzw. memory-mapped.

## Projektstruktur

```
app/main.py      FastAPI: Upload, Jobs, Fortschritt, Download, automatisches Löschen
app/stego.py     Trägerplanung, Header, LSB-Einbettung/-Extraktion, Encode/Decode
app/payload.py   zstd, Argon2id/PBKDF2, AES-256-GCM, Reed-Solomon pro Datei
app/rs.py        vektorisierter RS(255,223)-Encoder (kompatibel zu reedsolo)
app/media.py     ffprobe/ffmpeg (Rohframes rgb24, PCM s16le, FFV1/H.264 lossless, FLAC/WAV)
app/static/      Frontend (HTML/CSS/JS, DE/EN)
tests/           Roundtrip-, RS- und API-Tests
```
