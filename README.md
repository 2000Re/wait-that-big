# Wait, That Big?

YouTube チャンネル **Wait, That Big?**([@wait-that-big](https://www.youtube.com/@wait-that-big))の Shorts を毎日自動で作って投稿する。

ふつうの地図(メルカトル図法)は、極に近い国ほど大きく描かれる。国の形を **地球の上で** 動かして(大きさを保ったまま地図に描き直して)、本当の大きさを見せる。

## 形式

前の回の次の形式を出す(compare → fit → overlay → space → compare …。space は #7 から)。

| 形式 | 内容 | 例 |
|---|---|---|
| `compare` どっちが大きい？ | 地図では同じくらいか大きく見える国を、比べる相手の上へ動かす | Greenland or Brazil |
| `fit` 何個入る？ | 大きい国に、小さい国が面積でいくつ入るかを当てる。答えの数だけ形を並べる | How many Japans fit inside Australia? |
| `space` 宇宙 | 月・惑星・衛星の直径と、国の東西の幅(本土)を比べる。同じ縮尺で並べ、答えで国を天体に重ねる。直径は NASA の公表値(`catalog.py` の `BODIES`)。島国は使わない | Moon or Australia: which is wider? |
| `overlay` 重ねてみる | 細長い国などを別の地域に重ねて、端から端までどこに届くかを見せる(クイズではない) | What if Japan were in Europe? |

- 数字と国名は、すべて地図データから計算する(手で書いた答えはない)。面積は WGS84 の楕円体の上で計算(pyproj)。
- 主役にする国は `catalog.py` の一覧(よく知られた国)。国境に争いのある国・地域は主役にしない。
- 遠くに海外領土がある国(フランス、アメリカなど)は、描く形と国全体の面積が食い違うので、大きさの回には出さない。
- お題は「まだ出していないもの」の中から、驚きの大きいものを中心に選ぶ。直近4本に出た国・天体・地域は避ける
  (比べる相手、overlay の行き先の地域と「端から端」の2国も含む)。
- 候補はおよそ compare 118、fit 637、overlay 100(`python -c "import catalog as K; print({f: len(K.CANDIDATES[f]()) for f in K.FORMATS})"`)。

## 題名

毎回ちがう題名にする(`titles.py`)。形式ごとに6〜7の型を、その形式が出た回数で順に回し、過去と同じ題名と、同じ形式の前の回と同じ型は飛ばす。
答え(どちらが大きいか・何個か・どこに届くか)は題名に書かない。例:「Is Norway really bigger than India? 🌍」、
「Fill Australia with Japans: how many does it take? 🌍」、「Drop Chile on Europe: where does it reach? 🌍」。
型は `upload_history.json` の `title_style` に残る(#4 までは記録なし。#1〜#4 は形式ごとの classic の題名)。

## ファイル

| ファイル | 役割 |
|---|---|
| `longform.py` | 通常動画(横長)「True Size Challenge」を作り、投稿する(下の「通常動画」) |
| `make_short.py` | 次のお題を選び、動画(`out/video.mp4`)と `out/meta.json` を作る |
| `catalog.py` | 国の一覧、お題の候補、選び方 |
| `episodes.py` | 3つの形式の画面と声 |
| `geo.py` | 国の形・面積、地球の上での移動、メルカトル図法 |
| `media.py` | 文字・ボタン・地図の下地、Google Text-to-Speech、効果音、動画の書き出し |
| `youtube_upload.py` | YouTube へのアップロードと `upload_history.json` への記録(標準ライブラリのみ) |
| `site_gen.py` | サイトの回ごとのページ・一覧・sitemap を `docs/data/episodes.json` から作り直す(標準ライブラリのみ) |
| `posted_today.py` | 定期実行で、今日もう投稿したかを調べる(1日 `MAX_PER_DAY` 本) |
| `get_youtube_refresh_token.py` | リフレッシュトークンの取得(ローカルPCで一度だけ) |
| `data/countries.geojson` | Natural Earth 1:50m の国境(パブリックドメイン)。`tools/prepare_data.py` で作成 |
| `fonts/` | Liberation Sans(SIL OFL) |
| `branding/` | アイコン・バナー・チャンネルの説明文 |

## 手元で試す

```bash
pip install -r requirements.txt     # ほかに ffmpeg が必要
python make_short.py --tts dummy --format overlay --history /tmp/none.json --out /tmp/wtb
python make_short.py --tts dummy --key "fit:Australia|Japan" --history /tmp/none.json --out /tmp/wtb
```

`--tts google` は環境変数 `GOOGLE_TTS_API_KEY`(Text-to-Speech API のキー)を使う。声は en-US-Chirp3-HD-Charon、1.1倍速。

## 通常動画「True Size Challenge」(`longform.py`、週1本)

横長(1920x1080)の通常動画。12問を、「どっちが大きい？」(compare)と「何個入る？」(fit)を交互に出す(約3分40秒)。

- 流れ: 導入「Welcome to the True Size Challenge! 12 rounds, 5 seconds each. Keep score!」→ 各問(問題を読む →
  5秒のカウントダウン → 国を動かす/形を並べる → 答えと面積)→ 最後に「How many did you get right?」と点数の目安
  (10〜12: Map master / 6〜9: Globe trotter / 0〜5: Mercator fooled you)
- 画面: 左に回の番号・問題・選択肢・カウントダウン・答え、右に地図。地図の計算・国の動かし方・形の並べ方・声は Shorts と同じ部品
- お題: Shorts と過去の通常動画で出していないものから、得点の高いものを中心に選ぶ。1本の中で同じ国は2回出さない
- 説明欄: 各問の開始時刻のチャプター、答えの一覧(ネタバレ注意と書く)、出典
- サムネイル(1280x720)も作り、`thumbnails.set` で設定する。チャンネルの電話番号確認が済んでいないと 403 になるので、
  そのときは警告だけ出して投稿は続ける(YouTube Studio で手で設定する)
- 投稿の記録は `longform_history.json`(Shorts の `upload_history.json` とは別。番号も別)

自動化(`.github/workflows/longform.yml`):

- 毎週土曜 19:13 JST ごろ、GitHub の定期実行で動く。**リポジトリ変数 `LONGFORM_AUTO` が `true` のときだけ**
  (最初は Actions → longform → Run workflow で手動で試し、良ければ `true` にする)
- 手動実行の公開設定は既定で `unlisted`。`dry_run` にすると、投稿せずに Artifacts から動画だけ確認できる
- 失敗したら Issue(ラベル `longform-failure`、トークン失効なら `token-invalid`)
- 生成に約7分。YouTube API の割り当ては、動画1本 1,600 + サムネイル 50

手元で試す:

```bash
python longform.py --tts dummy --rounds 2 --history /dev/null --out out_long
```

## ウェブサイト

`docs/` を GitHub Pages で公開する(Settings → Pages → Deploy from a branch → `main` / `/docs`)。

- ホーム: https://2000re.github.io/wait-that-big/
- プライバシーポリシー: https://2000re.github.io/wait-that-big/privacy.html
- 利用規約: https://2000re.github.io/wait-that-big/terms.html

- 動画の一覧: https://2000re.github.io/wait-that-big/v/ (回ごとのページは `v/<番号>-<題名>/`)

投稿のたびに `youtube_upload.py` が `docs/data/episodes.json` に1件足して `site_gen.py` でページを作り直し、
workflow が `docs/` ごとコミットする。回のページには動画・選択肢・「答えを見る」・面積などの数字が載る
(overlay はクイズではないので、選択肢なしで答えを最初から出す)。一覧の画像は答えの直前の1コマ(`docs/img/`)。
作り直すだけなら `python site_gen.py`。

OAuth 同意画面の「アプリのホームページ」「プライバシーポリシー」「利用規約」に、この3つの URL を入れる。

## 自動投稿のセットアップ

YouTube のチャンネルは Painted When? と同じ Google アカウント(ブランドアカウント)にある。GCP プロジェクトと GitHub のリポジトリは別にする。

1. **GCP プロジェクトを新しく作る**(例: `wait-that-big`)
   - 「API とサービス」→「ライブラリ」で **YouTube Data API v3** と **Cloud Text-to-Speech API** を有効にする(Text-to-Speech は請求先アカウントの紐づけが必要。Chirp 3 HD は月100万文字まで無料)
2. **OAuth 同意画面**: 外部、アプリ名「Wait, That Big? Uploader」。スコープ `youtube.upload` と `youtube.readonly`。公開ステータスを **本番環境** にする(テストのままだとトークンが7日で切れる)
3. **OAuth クライアント ID**(種類: デスクトップアプリ)を作り、JSON をダウンロード
4. **ローカルPCで** トークンを取る:
   ```bash
   pip install google-auth-oauthlib
   python get_youtube_refresh_token.py client_secret_xxx.json
   ```
   **チャンネルの選択で必ず Wait, That Big? を選ぶ。** 最後に「認証したチャンネル: Wait, That Big?」と出ることを確かめる
5. **Text-to-Speech の API キー**を作る(「認証情報」→「API キー」。使える API を Cloud Text-to-Speech API だけに制限する)
6. GitHub の **Settings → Secrets and variables → Actions**
   - Secrets: `YT_CLIENT_ID`、`YT_CLIENT_SECRET`、`YT_REFRESH_TOKEN`、`YT_CHANNEL_ID`(4で表示される値)、`GOOGLE_TTS_API_KEY`(5のキー)
   - Variables: `AUTO_POST` = `true`(定期実行を止めたいときは `false`)
   - `YT_CHANNEL_ID` は必須。トークンのチャンネルがこれと違えば、アップロードせずに止まる(Painted When? への誤投稿防止)
7. **cron-job.org** で workflow を起動する(GitHub の `schedule` は数時間遅れるので使わない)
   - URL: `https://api.github.com/repos/2000Re/wait-that-big/actions/workflows/post.yml/dispatches`(POST)
   - ヘッダー: `Authorization: Bearer <このリポジトリの Actions に書き込める fine-grained token>`、`Accept: application/vnd.github+json`
   - 本文: `{"ref":"main","inputs":{"scheduled":"true"}}`
   - 時刻(Asia/Tokyo): 12:23・19:23 と、取りこぼし用に 30分後の 12:53・19:53。1日2本を超える分と、前の投稿から1.5時間以内の分は自動でスキップする

手動で試すときは Actions → post → Run workflow(`dry_run` で動画だけ作る、`privacy` で公開設定)。
失敗すると Issue が立つ(リフレッシュトークンが無効になったときは `token-invalid`)。

## 出典

- 地図: [Natural Earth](https://www.naturalearthdata.com/) 1:50m Admin 0 – Countries(パブリックドメイン)
- フォント: Liberation Sans(SIL Open Font License)

## 毎日の確認(`.github/workflows/daily-check.yml`)

毎日 03:19 JST ごろ(GitHub の schedule なので遅れることがある)に動く。手動では Actions → daily-check → Run workflow。

- **投稿が止まっていないか**(`watchdog.py`): 最後の投稿から30時間以上たっていたら Issue(ラベル `post-stalled`)を立てる。
  cron-job.org のトークン切れなどで post が起動されなかったときは post.yml 自身では何も残らないので、その見張り。
  投稿が再開すると次の確認で自動で閉じる。変数 `AUTO_POST` が `true` でないときは調べない
- **再生数の記録**(`stats.py`): 全動画の再生数・高評価・コメント数を YouTube Data API で取り、`stats.json` に残す。
  比べやすいよう、投稿から1日・3日・7日の時点の値を固定して残す(この仕組みより前の動画は最新の値だけ)。
  `stats.md` に、`upload_history.json` の項目(題名の型・版・カテゴリ・形式・美術館など、あるもの)と投稿の時間帯ごとの
  3日目の再生数の平均・中央値をまとめる。使う Secrets は投稿と同じ(`YT_CLIENT_ID`・`YT_CLIENT_SECRET`・`YT_REFRESH_TOKEN`)
- **共通ファイルのずれ**(`sync_check.py`): 4つのリポジトリの main を読み比べ、同じであるべきファイル
  (`stats.py`・`watchdog.py`・`sync_check.py`・`daily-check.yml`)が違えば sync ジョブを失敗にする。
  似ているファイル(`youtube_upload.py`・`posted_today.py` など)は、違う行数を Summary に並べる。
  1つで不具合を直したら、ほかの3つにも同じ直しが要るかを見る。中身は `python sync_check.py --diff youtube_upload.py`
- `stats.py`・`watchdog.py`・`sync_check.py` は4チャンネル(Painted When?、Guess From Space、Wait, That Big?、Too Close to Tell)で同じファイル
