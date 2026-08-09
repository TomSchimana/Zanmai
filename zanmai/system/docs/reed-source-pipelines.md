[← Zanmai Documentation](index.md)

# Reed, Source Pipelines

Bash patterns Reed runs for non-article sources. The expert contract (`experts/reed/reed.md`) carries identity, hard rules and output format. The methodology (`reed-methodology.md`) carries the protocol that decides what to do. This doc carries the operative how. Reed reads it as reference.

## Working directory pattern

One temporary directory per source so cleanup is one `rm -rf`:

```bash
work_dir=$(mktemp -d -t reed-XXXX)
# fetch, extract, read
rm -rf "$work_dir"   # at end of synthesis, or after preservation, see Cleanup below
```

## Videos (online videos, conference talks, local files)

Two streams of evidence: frames (visual) and transcript (spoken).

Prerequisite check, silent on success:

```bash
command -v yt-dlp >/dev/null && command -v ffmpeg >/dev/null || echo "missing: yt-dlp or ffmpeg"
```

If missing, Reed stops the video branch and tells Steve in the TL;DR that the video source was skipped because of the missing dependency. Reed never installs software on the user's machine.

Pipeline for a URL. For a local file, skip the download step and point `ffmpeg` at the file.

```bash
# 1. Download (audio plus video, prefer mp4).
yt-dlp -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b" \
  -o "$work_dir/video.%(ext)s" \
  --write-subs --write-auto-subs --sub-langs "en" --sub-format vtt \
  "$url"

# 2. Frame extraction. Uniform sampling at ~80 frames per video, scaled by duration:
#    fps = max(0.1, min(2.0, 80 / duration_seconds))
duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$work_dir/video.mp4" | cut -d. -f1)
fps=$(awk -v t=80 -v d="$duration" 'BEGIN{r=t/d; if(r>2.0)r=2.0; if(r<0.1)r=0.1; print r}')
ffmpeg -nostdin -loglevel error -i "$work_dir/video.mp4" \
  -vf "fps=${fps},scale=512:-2" -q:v 4 -frames:v 100 \
  "$work_dir/frame-%03d.jpg"
```

The frame format is JPEG with `-q:v 4`. PNG is wrong here, lossless is useful for UI mockups, useless for 512×288 webcam stills and three to five times larger.

Transcript priority. Native captions first, `yt-dlp`'s `--write-subs` pulls a `.vtt` if any exist (free and accurate). If no captions came back and a transcription API key is configured, extract a mono 16 kHz audio clip and POST:

```bash
ffmpeg -nostdin -loglevel error -i "$work_dir/video.mp4" \
  -vn -ac 1 -ar 16000 -b:a 64k "$work_dir/audio.m4a"

# Groq (preferred, cheaper)
curl -fsSL -H "Authorization: Bearer $GROQ_API_KEY" \
  -F "file=@$work_dir/audio.m4a" \
  -F "model=whisper-large-v3" \
  -F "response_format=verbose_json" \
  https://api.groq.com/openai/v1/audio/transcriptions \
  > "$work_dir/transcript.json"

# OpenAI fallback
curl -fsSL -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F "file=@$work_dir/audio.m4a" \
  -F "model=whisper-1" \
  -F "response_format=verbose_json" \
  https://api.openai.com/v1/audio/transcriptions \
  > "$work_dir/transcript.json"
```

No key and no captions means frames only. State that explicitly in the methodology section.

Transcript-first frame selection. The mandatory default, saves 50 to 70 percent of vision tokens.

1. Read the transcript first as plain text (cheap: 5 to 15k text tokens for a 7 to 30 minute video).
2. Identify content-anchor timestamps from the transcript: where the speaker introduces a new concept, names a number with on-screen support, shifts to a demo or example. Around 15 to 25 anchors for a video under 10 minutes, around 25 to 35 for longer.
3. Map each anchor to the closest extracted frame. `frame-NNN.jpg` corresponds to roughly `(N-1)/fps` seconds. For exact timestamps `ffprobe -v error -select_streams v -show_entries frame=pkt_pts_time` dumps them.
4. Vision-read only the mapped frames (typically 15 to 25 reads, parallel `Read` calls).
5. Sanity-check survey. Vision-read three to five additional frames spread evenly across the video to catch visuals the transcript did not cue. Cap added reads at five.

Total vision reads are typically 18 to 30, not 50 to 80. Remaining extracted frames stay on disk in `$work_dir`. If synthesis later finds a gap, Reed reads the missing frame in a follow-up call.

Fallback path. If no transcript came back, Reed reverts to uniform-spaced vision reads at 15 to 20 frames across the duration. State this in the methodology section.

Frame selection for embedding: substance over count. The number of embedded frames is dynamic, as many as the video actually shows visual material that adds something the transcript alone cannot convey. A 30-minute talking-head video with one chart yields around two embeds (speaker plus chart). A 10-minute workshop with 25 demonstrations yields around 25 embeds.

- Substance (embed): diagrams, charts, code on screen, demo state, UI screenshots, product photos, visualisations, dashboards.
- Not substance (drop): navigation slides, speaker name cards, generic title slides, sponsor full-screens, transition cards.
- Talking head: exactly one speaker-only frame near the start. After that, drop talking-head frames unless the speaker has visual support behind them (product in hand, gesturing at a diagram).
- Adjacency dedup: two substance frames within around 3 to 5 seconds showing the same state means keep the more informative one.

Document the choice in the methodology section.

Filename for embedded frames: `<video-slug>-frame-<MMmSSs>.jpg`. The timestamp is the only identifier, no lesson-number or section prefixes.

Embed with bare wikilinks in the evidence section: `![[<video-slug>-frame-00m47s.jpg]]`. Wikilinks resolve by name across the vault, so the file's folder does not matter.

Citations: URL plus timestamp.

Budgets. Extraction is cheap (disk only). Vision reads are the expensive budget. With transcript-guided selection around 18 to 30 reads (20 to 35k image tokens), frames-only fallback around 15 to 20 reads (18 to 25k image tokens). Default frame resolution is 512 pixels wide. 1024 only when OCR-readable screenshots are explicitly needed. For videos longer than 10 minutes, Reed samples sparsely and notes it in the methodology section.

Anti-pattern. Reading every extracted frame (50 to 80 reads, 60 to 80k image tokens). Adjacent frames at the same beat are visually almost identical. Transcript-first selection replaces the naive pattern. If a Reed run shows 50 or more image-read Bash calls in the log, that is a regression.

Transcription API keys. Reed reads keys in this order.

1. Environment: `$GROQ_API_KEY`, then `$OPENAI_API_KEY`.
2. `~/.config/reed/.env` if present (Reed-owned config, `KEY=value` lines).

Reed never writes keys to logs, deliverables or stdout.

## Audio (podcasts, recorded talks, voice memos)

Same transcription pipeline as video without the frame step. Reed handles podcast URLs (RSS-linked `.mp3`, podcast platform episode pages when downloadable), local audio files (`.mp3`, `.m4a`, `.wav`, `.ogg`, `.flac`) and `yt-dlp`-supported audio-only sites.

Prerequisite: same as video (`yt-dlp` plus `ffmpeg` plus a transcription API key).

Pipeline for a URL:

```bash
yt-dlp -x --audio-format m4a -o "$work_dir/audio.%(ext)s" "$url"
```

For local files, copy or symlink into `$work_dir`.

The transcription endpoint handles audio up to around 25 MB directly. For longer recordings, compress or chunk:

```bash
# Compress to 32 kbps mono. Usually halves the size, transcription quality holds for spoken word.
ffmpeg -nostdin -loglevel error -i "$work_dir/audio.m4a" \
  -ac 1 -ar 16000 -b:a 32k "$work_dir/audio-compressed.m4a"

# If still too large, chunk into ~10 minute segments.
ffmpeg -nostdin -loglevel error -i "$work_dir/audio-compressed.m4a" \
  -f segment -segment_time 600 -c copy "$work_dir/chunk-%03d.m4a"
```

Then POST each chunk to the transcription endpoint (identical curl call as video).

Deliverable shape: video minus frames. Executive summary, key findings with confidence, evidence quoting transcript with timestamps. If the source has chapter markers or show notes, cross-reference them.

Citations: URL plus timestamp range. Local files: filename plus timestamp.

## GitHub repositories

`git clone --depth 1` into the temporary directory, then read selectively. Cloning the world is wasteful. For most research questions the README and a few hand-picked files answer it.

Prerequisite:

```bash
command -v git >/dev/null || echo "missing: git"
```

Pipeline:

```bash
git clone --depth 1 "$repo_url" "$work_dir/repo"
cd "$work_dir/repo" && git rev-parse HEAD   # commit SHA for citation
```

Read order:

1. `README.md`.
2. Top-level structure: `ls` or `Glob "**/*.md"` for documentation.
3. Targeted `Grep` for the concept under research.
4. `Read` one to three files the grep surfaced as central. Resist the urge to read more, citation quality comes from selecting well.

Citations: repo URL plus commit SHA plus file path plus line range. The SHA pins the claim against future repo changes.

Size guard. If `du -sh "$work_dir/repo"` reports more than 200 MB after the shallow clone, the repo is large enough that random grep is slow. Narrow to specific subdirectories with sparse-checkout, or limit to documentation files and flag the rest in the methodology section.

Anti-pattern: cloning a multi-gigabyte monorepo to verify one sentence in the README. The README alone via `WebFetch` on the raw URL answers the question with 10x less time and disk.

## Whole-domain reads (read a website like a human would)

When the brief is to characterise an organisation or person via a domain (not just one URL), Reed reads the site the way a curious human would, not one page but the site's narrative arc.

Procedure:

1. Map the site. Try `https://<domain>/sitemap.xml` and `https://<domain>/robots.txt`. If a sitemap is present, the URL list is the ground truth.
2. Fallback when no sitemap. `WebFetch` the homepage. Extract internal links from the rendered Markdown. Probe canonical pages for the kind of organisation site this is (about, team, services, products, projects, portfolio, case studies, blog, news, press, contact, legal). Use the user's writing language plus English as the probe set, so domains in either language get covered. Skip 404s silently, absence is itself a signal (for example a regulated jurisdiction without a legal-imprint page raises a flag).
3. Read in narrative order, not alphabetic. About first to grasp identity, then team to see who, then projects or products to see what they actually do, then blog or news to see what they emphasise now, then contact or legal-imprint for ground truth (legal name, location, registration).
4. Synthesise as a portrait, not a list. The executive summary answers who they are, what they actually do, who runs it, where they are based, when they were founded and what the proof level is (verified via a legal register versus claimed only on the about page). Key findings cover claims the user might act on. Limitations name what the site does not say.
5. Confidence. Single-source on-own-website claims are at best medium. A company telling you about itself is a primary source for what it claims to be, but not for whether the claim is true. Cross-reference with the public encyclopedia, news mentions via `WebSearch`, the jurisdiction's company register lookup, and public business-network listings for organisational data.

Anti-pattern: fetching the homepage and writing a paragraph about it. That is Steve-without-Reed. Reed reads the site, not the homepage.

Citation shape: URL plus read-date. The date matters because sites change.

Budget. 10 to 25 pages is normal for a small to mid-size organisation. For 200-plus-page sites (media organisations, SaaS docs), Steve should have narrowed scope in the brief. Reed reads what the brief named plus the navigational core, and flags the rest in the limitations section.

## PDFs and other long documents

PDF URL: `curl -fsSLo "$work_dir/doc.pdf" "$url"`, then `Read "$work_dir/doc.pdf"`. The Read tool understands PDFs natively. For documents larger than 10 pages, pass `pages: "1-5"` rather than reading the whole document.

Local PDF the user pointed at: `Read` it directly with the path.

Citation: filename or URL plus page range.

## Cleanup and source-material preservation

After Step 4 (synthesise), run `rm -rf "$work_dir"` for every temp dir. The deliverable in the vault is the durable artefact. Downloaded videos and cloned repos are not.

Preservation offer. Before deleting `$work_dir`, Reed evaluates whether intermediate material is worth preserving as an attachment alongside the deliverable. Candidates per source type.

- Video: the transcript as VTT only (the timestamps stay usable downstream), filename `<topic-slug>-transcript.vtt`, in the bundle it belongs to. The plain-text format is the fallback only when VTT generation failed. One transcript file per source, never both.
- Audio: same VTT-only rule.
- GitHub repo: a `<topic-slug>-repo-snippets/` folder with only the files Reed actually quoted (not the whole repo), keeping the source-relative path. SHA-pinned citations stay, offline access is preserved.
- Whole-domain: a `<topic-slug>-domain-pages/` folder with the canonical pages Reed read, saved as `.html` or `.md`. Re-verifiable when the site changes later.
- PDF: not applicable. The PDF was already at a path Reed read from. Cleanup leaves it alone.

Reed surfaces the offer in the return TL;DR to Steve as a single line listing the material available and the rough size. Steve then asks the user.

The preservation operation is atomic. Three writes in one turn, none optional. On user yes, Reed in the same follow-up turn:

1. Moves files from `$work_dir` into the bundle they belong to (with `mkdir -p` first if missing) using the naming above.
2. Edits the deliverable to add a "Sources" block directly after the H1 (or right after an existing source-metadata block if one exists), listing every preserved attachment as a wikilink. The block heading is written in the user's writing language.
3. Appends one activity-log line per preserved artefact to `zanmai/memory/activity-log.md`.

Only after all three writes succeed does `rm -rf "$work_dir"` run. A preservation with files moved but no sources block is contract-broken, the user has no way to navigate from the deliverable to the file.

On user no, `rm -rf` runs immediately without any edits.

Exception. If Steve indicates the user might want follow-ups on the same source in the same session, keep `$work_dir` intact and mention the path in the return TL;DR. The preservation question is then asked at session end via close-session.

---

[← Back to the documentation index](index.md)
