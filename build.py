# -*- coding: utf-8 -*-
"""
1997年風マガジンサイト ジェネレータ
------------------------------------
- ソースディレクトリ内の *.txt を読み込み、ルール記法に従って
  「インデックス（目次）ページ」＋「記事ごとの sled式スレッドページ」を生成する。
- 出力は site/ 以下。Cloudflare Pages へはこの site/ をそのまま配信できる。

記法ルール（行頭1文字目で判定。『』「」[]【】で始まる行は記号扱いしない）:
  ◆ ... 大項目  → スレッドグループ（セクション）を分割
  > ... 区切り  → スレッドのタイトル
  ↓        → スレッド内の「返信風」レス区切り
  http(s)://... / resource/...  → 埋め込み（YouTube/画像/GIF/X/汎用リンク）
"""

import os
import re
import csv
import json
import html
import glob
import shutil

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SRC_DIR, "site")

# インデックスの「コンテンツ」ボタン（タイトル, サブ文言, 遷移先, アイコン画像）．
# アイコンは右側に表示（テキスト2/3・アイコン1/3）．アイコン不要なら "" にする．
# ※ファイル名は大文字小文字も実体に合わせること（Cloudflare/GitHubは区別する）。
CONTENT_BUTTONS = [
    ("バックナンバー", "過去の考察・妄想", "backnumber.html", "resource/Save.gif"),
    ("公式情報", "特設ページなどのアーカイブ", "official.html", "resource/GODDOG.gif"),
]

# 「公式情報」ページ上部の固定ボタン（label, URL, 画像）．
# 画像は resource/ファイル名 か外部URL．不要なら "" にする．
# ここが空のときは「― 公式情報 ―」の見出しごと出さず，★txt由来の
# 「お役立ちリンク集」だけが official.html に載る．追加したい場合のみ下記の形で記載．
# 例) ("表示名", "https://example.com/", "resource/xxx.png"),
REFERENCE_LINKS = [
]

SITE_TITLE = "バーナム効果のるつぼ1997"
SITE_SUBTITLE = "Deltaruneの感想・考察・妄想の吹き溜まり"

# サブページの大見出しを黄色文字ではなくロゴ画像で出す対応表（ページ名→resource画像）．
# ここに無いページは従来どおり黄色い文字タイトル．画像は resource/ に置く．
PAGE_LOGOS = {
    "backnumber.html": "resource/Back_Number.png",
    "official.html": "resource/Official_Info.png",
}

# 隠しミニゲームの直接アクセスページ（game.html）の合言葉。
# nobody.html のイベント内で「ベータテストのリンク」として ?key=… 付きURLを提示し，
# キーが一致しないアクセスには真っ黒の画面だけを見せる（静的サイトなので割り切り）。
GAME_KEY = "GONER1997"

# ------------------------------------------------------------------ 変身イベント
# F5連打を「最後の無言表示」まで進めると発動する隠しホラー演出のコンテンツ．
# ここを書き換えると変身後の目次・参考資料・各種文言を差し替えられる．
HAUNTED = {
    "docTitle": "これでもくらえ",                                  # 変身後のタブのタイトル
    "logo": "あんぽんたんガキンチョ",                              # 変身後のヘッダーロゴ（.com付与）
    "title": "あんぽんたんガキンチョ",                             # 変身後の大見出し（虹色）
    "counterPrefix": "君は",                                       # カウンター文言（数値の前）
    "counterSuffix": "番目の あんぽんたんガキンチョだ",            # カウンター文言（数値の後）
    "video": "kurae.html",                                         # 崩壊後に遷移する動画ページ
    "glitchMs": 15000,                                             # 変身から崩壊開始までの待ち時間
    # 変身後の目次（タイトル，概要）
    "toc": [
        ["最終防衛ライン 突破されました！！",
         "犬が啞高速で全てを破壊してます！　このままではスペースエイプ軍の被害は甚大！　最終兵器を出すしかない！！"],
        ["チーズがた～っぷりの　ピ～ッツァ～！　今ならブルドッ君のアイス味アイスがセット！",
         "現在デリバリーサービスは休止しています　自分で取りに来るとSNESが4000ドッグドル安くなる クーポン券付き"],
        ["あなたのページはピッキングされました",
         "ディレクトリ内のマイクロビキニを着たスパゲッティの写真をばら撒かれたくなければ　クレディスイス銀行 普通口座1234-5678に10＄支払ってください"],
        ["TABOO知恵ｵｸﾚ Deltarune スーザン　攻略ルート",
         "このルートを進む為には湖の底のロボット三等兵が持つレインボウキーを入手してゲームのデータを消すこと　必ずデータが1のスロットじゃないとだめですよ。これをすれば秘密のクージィルートがアンロック！！"],
        ["こんなもん作ってて人生虚しくないかだって？",
         "好きなもんを自由に作って何が悪いん？　あんたの予定なんてしったこっちゃねぇ　ぎゃははのは！！"],
        ["検閲済み",
         "*ここはどこ…！？　あなた、私が見えてるの？　お願い、ここから出るのを手伝って！！　-6666666番目の来訪者が来たときに　隙間に『扉』がでてくる　その奥でコードを入力して　コードは FJFIrejirioEUEUROEI4378789 じ、時間が…！"],
    ],
    # 変身後の参考資料（タイトル，それっぽい羅列URL）
    "refs": [
        ["高級ペットフードにゃおチュール", "http://www.nyao-churu.ne.jp/~k3829fjqp7/nyao_index.html"],
        ["汎用人間用オヤツ ランチャブルズ", "http://lunchables.tonosama.co.jp/9f8a7b2/menu48.htm"],
    ],
}

# ------------------------------------------------------------------ パース

URL_RE = re.compile(r"https?://[^\s　]+")
LOCAL_RE = re.compile(r"^(?:\./)?resource/\S+$", re.IGNORECASE)
# 記事タイトル → 生成ファイル名（行頭「→タイトル」の内部リンクをビルド時に解決するため）．
# main() で全記事をパースした後に埋める．未解決リンクは PAGE_LINK_MISSES に控える．
PAGE_LINK_MAP = {}                    # {タイトル: "page_NN.html"}
PAGE_TITLE_BY_FNAME = {}             # {"page_NN.html": タイトル}（直接ファイル名指定の表示名用）
PAGE_LINK_MISSES = []
IMG_EXT_RE = re.compile(r"\.(png|jpe?g|gif|webp|bmp|svg)(?:[?#].*)?$", re.IGNORECASE)
VIDEO_EXT_RE = re.compile(r"\.(mp4|webm|ogg|ogv|mov|m4v)(?:[?#].*)?$", re.IGNORECASE)
# 行全体が【タイトル】の行はページ区切り兼タイトルとして扱う（1ファイル内に複数可）
# 先頭の★（【】の前でも中でも可）は「新着」フラグ．例: ★【…】 / 【★…】
PAGE_TITLE_RE = re.compile(r"^\s*(★)?\s*【(.+?)】\s*$")
# 埋め込み行末尾のサイズ指定 <70%> / <300px> / <300>（単位省略時はpx）
SIZE_SUFFIX_RE = re.compile(r"\s*<\s*(\d+)\s*(%|px)?\s*>\s*$")
EXCLUDE_FIRST = "『「[【（"


def split_size(s):
    """埋め込み行の末尾サイズ指定を切り出す．戻り値 (本体, CSSサイズ or None)．
    例: "resource/a.png <70%>" -> ("resource/a.png", "70%")"""
    m = SIZE_SUFFIX_RE.search(s)
    if not m:
        return s, None
    return s[:m.start()].rstrip(), m.group(1) + (m.group(2) or "px")


def is_embed_line(line):
    s = line.strip()
    if not s:
        return False
    core, _ = split_size(s)          # 末尾の <70%> 等を除いて本体だけで判定する
    if URL_RE.fullmatch(core):
        return True
    if LOCAL_RE.match(core):
        return True
    return False


def classify(raw):
    s = raw.rstrip("\n")
    stripped = s.strip()
    if not stripped:
        return ("blank", "")
    first = stripped[0]
    if first in EXCLUDE_FIRST:
        return ("text", s)
    if first == "◆":
        return ("section", stripped[1:].strip())
    if first in (">", "＞"):
        return ("thread", stripped[1:].strip())
    if stripped == "↓" or first == "↓":
        return ("reply", "")
    if first == "→":                          # 行頭「→タイトル」＝他記事への内部リンク
        return ("pageref", stripped[1:].strip())
    if is_embed_line(s):
        return ("url", stripped)
    return ("text", s)


def parse(text):
    sections = []
    st = {"section": None, "thread": None, "post": None, "buf": []}

    def ensure_section():
        if st["section"] is None:
            st["section"] = {"title": "", "threads": []}
            sections.append(st["section"])

    def ensure_thread():
        if st["thread"] is None:
            ensure_section()
            st["thread"] = {"title": "", "posts": []}
            st["section"]["threads"].append(st["thread"])

    def ensure_post():
        if st["post"] is None:
            ensure_thread()
            st["post"] = {"blocks": []}
            st["thread"]["posts"].append(st["post"])

    def flush_buf():
        if st["buf"]:
            ensure_post()
            st["post"]["blocks"].append(("text", list(st["buf"])))
            st["buf"] = []

    for raw in text.splitlines():
        kind, val = classify(raw)
        if kind == "blank":
            flush_buf()
        elif kind == "section":
            flush_buf()
            st["section"] = {"title": val, "threads": []}
            sections.append(st["section"])
            st["thread"] = None
            st["post"] = None
        elif kind == "thread":
            flush_buf()
            ensure_section()
            st["thread"] = {"title": val, "posts": []}
            st["section"]["threads"].append(st["thread"])
            st["post"] = None
        elif kind == "reply":
            flush_buf()
            ensure_thread()
            st["post"] = {"blocks": []}
            st["thread"]["posts"].append(st["post"])
        elif kind == "url":
            flush_buf()
            ensure_post()
            st["post"]["blocks"].append(("embed", val))
        elif kind == "pageref":
            flush_buf()
            ensure_post()
            st["post"]["blocks"].append(("pageref", val))
        else:  # text
            st["buf"].append(val)
    flush_buf()
    return sections


def _strip_leading_star(text):
    """本文の最初の非空行が★で始まればTrueとその★を除いた本文を返す（新着判定用）．"""
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if not l.strip():
            continue
        s = l.lstrip()
        if s.startswith("★"):
            indent = l[:len(l) - len(s)]
            lines[i] = indent + s[1:].lstrip()
            return True, "\n".join(lines)
        return False, text
    return False, text


def split_documents(text):
    """1ファイルのテキストを，行全体が【タイトル】の行で複数ドキュメントに分割する．
    返り値は [{"title": タイトル or None, "featured": bool, "text": 本文}] のリスト．
    title/本文先頭の★は「新着」フラグとして検出し，表示からは除去する．
    【】が1つも無ければ全体を1ドキュメント（title=None）として返す．"""
    docs = []
    cur = {"title": None, "featured": False, "lines": []}

    def flush():
        # 本文が実質空（空行のみ）でタイトルも無いドキュメントは捨てる
        if cur["title"] is not None or any(l.strip() for l in cur["lines"]):
            docs.append({"title": cur["title"], "featured": cur["featured"],
                         "text": "\n".join(cur["lines"])})

    for raw in text.splitlines():
        m = PAGE_TITLE_RE.match(raw)
        if m:
            flush()
            star = bool(m.group(1))                 # ★【…】 形式
            title = m.group(2).strip()
            if title.startswith("★"):               # 【★…】 形式
                star = True
                title = title[1:].strip()
            cur = {"title": title, "featured": star, "lines": []}
        else:
            cur["lines"].append(raw)
    flush()

    if not docs:
        docs = [{"title": None, "featured": False, "text": text}]
    # タイトルで★が付いていないものは，本文先頭行の★でも新着判定する
    for d in docs:
        if not d["featured"]:
            d["featured"], d["text"] = _strip_leading_star(d["text"])
    return docs


# ------------------------------------------------------------------ 埋め込み

def youtube_id(url):
    m = re.search(r"[?&]v=([\w-]{11})", url)
    if m:
        return m.group(1)
    m = re.search(r"youtu\.be/([\w-]{11})", url)
    if m:
        return m.group(1)
    return None


def is_twitter(url):
    return ("twitter.com/" in url) or ("x.com/" in url)


def is_tweet_status(url):
    # 実埋め込みできるのはツイート（status）URLのみ．記事(/article/)やプロフィールは不可．
    return is_twitter(url) and bool(re.search(r"/status(?:es)?/\d+", url))


def is_image(url):
    if LOCAL_RE.match(url):
        return True
    if IMG_EXT_RE.search(url):
        return True
    if "gstatic.com" in url or "/images?" in url:
        return True
    return False


def is_video(url):
    return bool(VIDEO_EXT_RE.search(url))


def render_local(path, style=""):
    """resource/ 配下のローカルファイルを埋め込む．
    画像（gif含む）はそのまま，動画は<video>で再生する．ソースURLのキャプションは出さない
    （ローカルファイルなので外部ソースURLが存在しないため）．パス中の空白だけ安全化する．
    style は末尾サイズ指定（例 width:70%）の inline style 文字列．"""
    safe = path.replace(" ", "%20")                 # 相対パスの空白をエンコード（resource運用向け）
    u = html.escape(safe, quote=True)
    if is_video(path):
        return ('<div class="embed embed-video">'
                '<video src="%s" controls playsinline preload="metadata"%s></video>'
                "</div>" % (u, style))
    return ('<div class="embed embed-img">'
            '<a href="%s" target="_blank" rel="noopener"><img src="%s" alt="" loading="lazy"%s></a>'
            "</div>" % (u, u, style))


def render_embed(raw):
    url, size = split_size(raw)              # 末尾の <70%> / <300px> をサイズ指定として分離
    u = html.escape(url, quote=True)
    style = ' style="width:%s"' % size if size else ""
    yt = youtube_id(url)
    if yt:
        thumb = "https://img.youtube.com/vi/%s/hqdefault.jpg" % yt
        return (
            '<div class="embed embed-yt">'
            '<a href="%s" target="_blank" rel="noopener">'
            '<img src="%s" alt="YouTube動画" loading="lazy"%s>'
            '<span class="yt-play">&#9658;</span></a>'
            '<div class="embed-src"><a href="%s" target="_blank" rel="noopener">%s</a></div>'
            "</div>" % (u, thumb, style, u, u)
        )
    if is_twitter(url):
        if is_tweet_status(url):                     # 実ツイートは widgets.js で本文を埋め込む
            return (
                '<div class="embed embed-tweet">'
                '<blockquote class="twitter-tweet"><a href="%s">%s</a></blockquote>'
                "</div>" % (u, u)
            )
        # status以外のX URL（記事・プロフィール等）は埋め込み不可なのでリンク表示にする
        return (
            '<div class="embed embed-tweet">'
            '<div class="tweet-ph"><span class="tweet-bird">&#128038;</span>'
            "このXのURLはツイート(status)ではないため埋め込めません<br>"
            "<small>埋め込むには .../status/数字 のツイートURLを指定してください</small></div>"
            '<div class="embed-src"><a href="%s" target="_blank" rel="noopener">%s</a></div>'
            "</div>" % (u, u)
        )
    if LOCAL_RE.match(url):                       # resource/ 配下のローカル画像・動画
        return render_local(url, style)
    if is_image(url) or size:            # 拡張子なしでもサイズ指定付きURLは画像として差し込む
        return (
            '<div class="embed embed-img">'
            '<a href="%s" target="_blank" rel="noopener"><img src="%s" alt="" loading="lazy"%s></a>'
            '<div class="embed-src"><a href="%s" target="_blank" rel="noopener">%s</a></div>'
            "</div>" % (u, u, style, u, u)
        )
    return ('<p class="embed-link"><a href="%s" target="_blank" rel="noopener">%s</a></p>'
            % (u, u))


def linkify(s):
    out = []
    last = 0
    esc = lambda t: html.escape(t)
    for m in URL_RE.finditer(s):
        out.append(esc(s[last:m.start()]))
        url = m.group(0)
        out.append('<a href="%s" target="_blank" rel="noopener">%s</a>'
                   % (html.escape(url, quote=True), esc(url)))
        last = m.end()
    out.append(esc(s[last:]))
    return "".join(out)


def render_text_block(lines):
    body = "<br>".join(linkify(l) for l in lines)
    return '<p class="post-text">%s</p>' % body


# ------------------------------------------------------------------ HTMLレンダリング

def article_title(sections, fallback):
    # 【】による明示タイトルが無い場合のフォールバック：最初の > 区切り（スレッドタイトル）
    for sec in sections:
        for th in sec["threads"]:
            if th["title"]:
                return th["title"]
    return fallback


def article_blurb(sections):
    for sec in sections:
        for th in sec["threads"]:
            for post in th["posts"]:
                for kind, val in post["blocks"]:
                    if kind == "text" and val:
                        return val[0]
    return ""


# ヘッダーの固定ナビ（記事ページは個別に並べず，バックナンバー経由で辿る）
NAV_LINKS = [
    ("目次", "index.html"),
    ("バックナンバー", "backnumber.html"),
    ("公式情報", "official.html"),
]


def render_nav(current):
    items = []
    for label, href in NAV_LINKS:
        cls = " current" if href == current else ""
        items.append('<a class="navtab%s" href="%s">%s</a>'
                     % (cls, href, html.escape(label)))
    return '<nav class="header-nav">%s</nav>' % "".join(items)


def has_tweet_embed(sections):
    # 実ツイート埋め込みがあるページだけ widgets.js を読み込むための判定
    for sec in sections:
        for th in sec["threads"]:
            for post in th["posts"]:
                for kind, val in post["blocks"]:
                    if kind == "embed" and is_tweet_status(val):
                        return True
    return False


def render_pageref(target):
    """行頭「→タイトル」の内部リンクを解決してリンクにする．
    タイトル一致で page_NN.html へ．page_05 / page_05.html のような直接指定も可．
    解決できなければ元テキストのまま残す（ビルドは壊さず，最後に警告する）．"""
    key = target.strip()
    if re.fullmatch(r"page_\d+", key, re.IGNORECASE):
        href, label = key + ".html", PAGE_TITLE_BY_FNAME.get(key + ".html", key)
    elif re.fullmatch(r"[\w\-]+\.html", key, re.IGNORECASE):
        href, label = key, PAGE_TITLE_BY_FNAME.get(key, key)
    elif key in PAGE_LINK_MAP:
        href, label = PAGE_LINK_MAP[key], key
    else:
        PAGE_LINK_MISSES.append(key)                 # 未解決：あとでまとめて警告
        return '<p class="post-text">%s</p>' % html.escape("→" + key)
    return ('<p class="embed-link page-ref"><a href="%s">&rarr; %s</a></p>'
            % (html.escape(href, quote=True), html.escape(label)))


def render_post(post, is_op):
    blocks = []
    for kind, val in post["blocks"]:
        if kind == "text":
            blocks.append(render_text_block(val))
        elif kind == "pageref":
            blocks.append(render_pageref(val))
        else:
            blocks.append(render_embed(val))
    body = "\n".join(blocks)
    cls = "post op" if is_op else "post reply"
    return '<div class="%s"><div class="post-body">%s</div></div>' % (cls, body)


def render_article(sections, title, fname):
    nav = render_nav(fname)
    parts = []
    for sec in sections:
        if sec["title"]:
            parts.append('<h2 class="section-title">◆ %s</h2>' % html.escape(sec["title"]))
        for th in sec["threads"]:
            parts.append('<div class="thread">')
            if th["title"]:
                parts.append('<div class="thread-bar">%s</div>' % html.escape(th["title"]))
            for i, post in enumerate(th["posts"]):
                parts.append(render_post(post, is_op=(i == 0)))
            parts.append("</div>")
    content = "\n".join(parts)
    scripts = ""
    if has_tweet_embed(sections):                    # ツイートがあるページのみ埋め込みスクリプトを読み込む
        scripts = ('<script async src="https://platform.twitter.com/widgets.js" '
                   'charset="utf-8"></script>')
    return PAGE_TMPL.format(
        title=html.escape(title),
        site=html.escape(SITE_TITLE),
        nav=nav,
        content=content,
        scripts=scripts,
    )


def load_counter_data():
    """counter_messages.csv を読み、[{"n":番号,"m":メッセージ,"img":画像,"lk":リンク}]
    のJSON文字列にする。空の項目は省略してサイズを抑える。"""
    path = os.path.join(SRC_DIR, "counter_messages.csv")
    entries = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # ヘッダー
            for row in reader:
                if not row or not row[0].strip():
                    continue
                try:
                    num = int(str(row[0]).strip())
                except ValueError:
                    continue
                msg = row[1].strip() if len(row) > 1 else ""
                img = row[2].strip() if len(row) > 2 else ""
                lk = row[3].strip() if len(row) > 3 else ""
                e = {"n": num}
                if msg:
                    e["m"] = msg
                if img:
                    e["img"] = img
                if lk:
                    e["lk"] = lk
                entries.append(e)
    return json.dumps(entries, ensure_ascii=False, separators=(",", ":"))


NEW_BADGE = '<img class="new-badge" src="resource/新着.png" alt="新着" loading="lazy">'


def render_cards(items):
    """記事カード（新着／バックナンバー共通のレイアウト）を生成する．
    items は (fname, title, blurb, is_new) のリスト．is_new の記事は右に新着バッジを出す．"""
    cards = []
    for fname, title, blurb, is_new in items:
        badge = NEW_BADGE if is_new else ""        # バッジはタイトル文字の隣（同じ行）に置く
        cards.append(
            '<a class="toc-item" href="%s">'
            '<span class="toc-text"><h2>%s%s</h2><p>%s</p></span></a>'
            % (fname, html.escape(title), badge, html.escape(blurb))
        )
    return "\n".join(cards)


def render_content_buttons():
    """インデックスの「コンテンツ」ボタンを生成する．
    テキストは中央寄せ（横2/3），アイコンがある場合は右1/3に表示する．"""
    out = []
    for title, sub, href, icon in CONTENT_BUTTONS:
        icon_html = ""
        cls = ""
        if icon:
            src = icon.replace(" ", "%20")
            icon_html = ('<span class="cb-icon"><img src="%s" alt="" loading="lazy"></span>'
                         % html.escape(src, quote=True))
            cls = " has-icon"
        out.append(
            '<a class="content-btn%s" href="%s">'
            '<span class="cb-text"><span class="cb-title">%s</span>'
            '<span class="cb-sub">%s</span></span>%s</a>'
            % (cls, html.escape(href, quote=True), html.escape(title), html.escape(sub), icon_html)
        )
    return "\n".join(out)


def oi_image_html(image, size=None):
    """公式情報ボタンの右に置くサムネイル画像タグを返す．image が空なら空文字．
    size（<70%>/<400px> 由来）は width として反映する（小さい画像も指定サイズまで拡大する．
    上限は CSS の max-width/max-height=500px で頭打ち）．"""
    if not image:
        return ""
    src = image.replace(" ", "%20")
    style = ' style="width:%s"' % size if size else ""
    return ('<img class="oi-img" src="%s" alt="" loading="lazy"%s>'
            % (html.escape(src, quote=True), style))


def render_official_items():
    """「公式情報」ページ上部の固定ボタン（任意で右に画像入り）を生成する．"""
    items = []
    for label, url, image in REFERENCE_LINKS:
        img_html = oi_image_html(image)
        cls = "official-item" + (" has-img" if img_html else "")
        body = ('<span class="oi-body"><span class="oi-label">%s</span>'
                '<span class="oi-url">%s</span></span>'
                % (html.escape(label), html.escape(url)))
        items.append(
            '<a class="%s" href="%s" target="_blank" rel="noopener">%s%s</a>'
            % (cls, html.escape(url, quote=True), body, img_html)
        )
    return "\n".join(items)


def render_index(index_cards):
    nav = render_nav("index.html")
    cards = render_cards(index_cards)
    # JS側に渡すデータを placeholder 置換で差し込む（str.format との波括弧衝突回避）
    haunted_json = json.dumps(HAUNTED, ensure_ascii=False, separators=(",", ":"))
    script = (INDEX_SCRIPT
              .replace("__COUNTER_DATA__", load_counter_data())
              .replace("__HAUNTED_JSON__", haunted_json))
    return INDEX_TMPL.format(
        site=html.escape(SITE_TITLE),
        subtitle=html.escape(SITE_SUBTITLE),
        nav=nav,
        toc=cards,
        content_buttons=render_content_buttons(),
        script=script,
    )


def render_subpage(title, content, current, body_class="index-page"):
    """バックナンバー／公式情報など，ヘッダー付きの単純ページを生成する（カウンター無し）．"""
    # PAGE_LOGOS に登録があればロゴ画像，無ければ従来の黄色文字タイトル．
    logo = PAGE_LOGOS.get(current)
    if logo:
        src = logo.replace(" ", "%20")
        title_block = ('<h1 class="index-title page-logo-wrap">'
                       '<img class="page-logo" src="%s" alt="%s"></h1>'
                       % (html.escape(src, quote=True), html.escape(title)))
    else:
        title_block = '<h1 class="index-title">%s</h1>' % html.escape(title)
    return SUBPAGE_TMPL.format(
        title=html.escape(title),
        title_block=title_block,
        site=html.escape(SITE_TITLE),
        nav=render_nav(current),
        content=content,
        body_class=body_class,
    )


# ------------------------------------------------------------------ テンプレート

PAGE_TMPL = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - {site}</title>
<link rel="stylesheet" href="style.css">
</head>
<body class="article-page">
<header class="site-header">
  <div class="header-logo">{site}<span class="dotcom">.com</span></div>
  {nav}
</header>
<main class="board">
  <h1 class="board-title">{title}</h1>
  {content}
</main>
<footer class="site-footer">
  <a href="index.html">&laquo; 目次にもどる</a>
</footer>
{scripts}
</body></html>
"""

INDEX_TMPL = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{site}</title>
<link rel="stylesheet" href="style.css">
</head>
<body class="index-page">
<header class="site-header">
  <div class="header-logo">{site}<span class="dotcom">.com</span></div>
  {nav}
</header>
<main class="index-main">
  <h1 class="index-title">{site}</h1>
  <p class="index-sub">{subtitle}</p>

  <section id="counter">
    <p class="counter-line">あなたは
      <span id="hitcount" class="hit-digits">------</span>
      番目の来訪者です</p>
    <p id="kiriban-msg" class="kiriban-msg"></p>
    <div id="kiriban-extra"></div>
  </section>

  <section id="interlude">
    <a id="interlude-link"><img id="interlude-img" class="interlude-img"
       src="resource/susie-splat-sprite.png" alt=""></a>
  </section>

  <section id="toc">
    <h2 class="index-section-h">― 新着 ―</h2>
    {toc}
  </section>

  <section id="contents">
    <h2 class="index-section-h">― コンテンツ ―</h2>
    <div class="content-list">
    {content_buttons}
    </div>
  </section>
</main>
<footer class="site-footer">{site} / 1997</footer>
{script}
</body></html>
"""

# インデックスのカウンター／隠しイベント用スクリプト．
# JSの波括弧と str.format の衝突を避けるため，データは __PLACEHOLDER__ を replace で差し込む．
INDEX_SCRIPT = """<script>
(function(){
  var DATA = __COUNTER_DATA__;
  var HAUNTED = __HAUNTED_JSON__;
  if (!DATA.length) return;

  function pad(x) { if (x < 0) return String(x); var s = String(x); while (s.length < 8) s = "0" + s; return s; }
  function esc(t) { return String(t).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

  var hit = document.getElementById("hitcount");
  var msg = document.getElementById("kiriban-msg");
  var extra = document.getElementById("kiriban-extra");

  // 扉イベント: カウンター下のスージィ画像を Nobody.png にフェードで差し替える．
  // 扉のときはコメント（プレースホルダ文）を出さない．
  function showDoor(d) {
    var img = document.getElementById("interlude-img");
    var link = document.getElementById("interlude-link");
    if (img) { img.src = "resource/" + d.img; img.className = "nobody-door"; }
    // 扉の先はスクリプトで開いた新規タブにする（そのタブは自身を window.close() で閉じられる）．
    if (link) {
      link.href = d.lk || "#";
      link.onclick = function(ev){ ev.preventDefault(); window.open(d.lk || "#", "_blank"); };
    }
    if (msg) msg.textContent = "";
  }

  //---------------------------------------------------------------------------
  // 無言到達後の「あんぽんたんガキンチョ」変身演出．
  // ページ全体を作り替え，一定時間後にノイズ崩壊→動画ページへ遷移する
  //---------------------------------------------------------------------------
  function goHaunted(num) {
    document.title = HAUNTED.docTitle;                          // タブのタイトル
    document.body.classList.add("haunted");

    var logo = document.querySelector(".header-logo");          // ヘッダーロゴ
    if (logo) logo.innerHTML = esc(HAUNTED.logo) + '<span class="dotcom">.com</span>';

    var bigTitle = document.querySelector(".index-title");      // 大見出し（虹色）
    if (bigTitle) bigTitle.textContent = HAUNTED.title;

    var sub = document.querySelector(".index-sub");
    if (sub) sub.textContent = "";

    var line = document.querySelector(".counter-line");         // カウンター文言の差し替え
    if (line) line.innerHTML = esc(HAUNTED.counterPrefix)
      + '<span class="hit-digits">' + esc(pad(num)) + '</span>'
      + esc(HAUNTED.counterSuffix);
    if (msg) msg.textContent = "";
    if (extra) extra.innerHTML = "";

    var toc = document.getElementById("toc");                   // 新着の差し替え
    if (toc) {
      var th = '<h2 class="index-section-h">― 新着 ―</h2>';
      HAUNTED.toc.forEach(function(it) {
        th += '<a class="toc-item" href="#"><h2>' + esc(it[0]) + '</h2><p>' + esc(it[1]) + '</p></a>';
      });
      toc.innerHTML = th;
    }

    var refs = document.getElementById("contents");             // コンテンツ欄の差し替え
    if (refs) {
      var rh = '<h2 class="index-section-h">― コンテンツ ―</h2><div class="ref-list">';
      HAUNTED.refs.forEach(function(r) {
        rh += '<a class="ref-item" href="#"><span>' + esc(r[0]) + '</span>'
            + '<span class="ref-url">' + esc(r[1]) + '</span></a>';
      });
      rh += '</div>';
      refs.innerHTML = rh;
    }

    setTimeout(startGlitch, HAUNTED.glitchMs);                  // 一定時間後に崩壊演出
  }

  //---------------------------------------------------------------------------
  // 変身イベントの発動口．完了フラグを保存し，一瞬バグ演出を挟んでから変身させる
  //---------------------------------------------------------------------------
  function triggerHaunted(num) {
    sessionStorage.setItem("boku_done", "1");                   // タブを閉じるまで保持するフラグ
    sessionStorage.setItem("boku_num", String(num));
    document.body.classList.add("glitch-pre");                  // 一瞬画面が崩れる（バグ演出）
    setTimeout(function(){
      document.body.classList.remove("glitch-pre");
      goHaunted(num);
    }, 360);
  }

  //---------------------------------------------------------------------------
  // 崩壊シーケンス：画面最上部へ戻し，予備動作（画面が崩れる演出）を2回挟んでから
  // 3秒後にノイズへ突入する．演出中はスクロールを固定し，下にいても見切れないようにする．
  //---------------------------------------------------------------------------
  function startGlitch() {
    window.scrollTo(0, 0);                                          // ノイズが見切れないよう最上部へ
    document.documentElement.style.overflow = "hidden";            // 演出中はスクロールを固定
    document.body.style.overflow = "hidden";

    function jolt() {                                               // 画面が一瞬崩れる予備動作
      document.body.classList.add("glitch-pre");
      setTimeout(function(){ document.body.classList.remove("glitch-pre"); }, 360);
    }
    jolt();                                                         // 1回目
    setTimeout(jolt, 1300);                                         // 2回目（準備のためのワンクッション）
    setTimeout(startNoise, 3000);                                  // 3秒後にノイズ突入
  }

  //---------------------------------------------------------------------------
  // 砂嵐（TVノイズ）で画面を覆い，2秒後に動画ページへ遷移する処理
  //---------------------------------------------------------------------------
  function startNoise() {
    document.body.classList.add("glitching");
    var c = document.createElement("canvas"); c.id = "noise";
    document.documentElement.appendChild(c);                        // bodyのtransformに影響されないようhtml直下へ
    var ctx = c.getContext("2d"); ctx.imageSmoothingEnabled = false;
    var off = document.createElement("canvas"); var octx = off.getContext("2d");
    function resize() {
      c.width = window.innerWidth; c.height = window.innerHeight;
      off.width = Math.max(1, Math.ceil(window.innerWidth / 4));   // 1/4解像度で軽量に砂嵐を生成
      off.height = Math.max(1, Math.ceil(window.innerHeight / 4));
    }
    resize(); window.addEventListener("resize", resize);
    (function draw() {
      var w = off.width, h = off.height, img = octx.createImageData(w, h), d = img.data;
      for (var i = 0; i < d.length; i += 4) {
        var v = Math.random() * 255 | 0; d[i] = d[i+1] = d[i+2] = v; d[i+3] = 255;
      }
      octx.putImageData(img, 0, 0);
      ctx.drawImage(off, 0, 0, c.width, c.height);                 // 拡大して全画面に描画
      requestAnimationFrame(draw);
    })();
    setTimeout(function(){ location.replace(HAUNTED.video); }, 2000);
  }

  // 既に変身イベントを最後まで見ている場合は，タブを閉じるまで毎回その状態を表示する．
  // sessionStorage はリロードや時間経過では消えず，タブを完全に閉じたときだけ消えるので，
  // 「ページを一度完全に消すまではリセットしない」という要件をそのまま満たす．
  if (sessionStorage.getItem("boku_done")) {
    var sn = parseInt(sessionStorage.getItem("boku_num"), 10);
    goHaunted(isNaN(sn) ? 6666666 : sn);
    return;
  }

  // F5連打検知（前回ロードから5秒以内なら「連打」としてカウント。間が空けばリセット）
  var now = Date.now();
  var last = parseInt(localStorage.getItem("reload_time"), 10);
  var cnt = parseInt(localStorage.getItem("reload_count"), 10);
  if (isNaN(cnt) || isNaN(last) || (now - last) > 5000) { cnt = 1; } else { cnt += 1; }
  localStorage.setItem("reload_count", String(cnt));
  localStorage.setItem("reload_time", String(now));

  function spamMessage(c) {
    if (c < 21) return null;            // 通常表示（1〜20回）
    if (c === 21) return "＊ねえ　ちょっと…";
    if (c === 22) return "＊いいかげん　しつこいぞ　F5キーを連打するのをやめろ";
    if (c === 23) return "＊おい！　やめろって言ってるのが　わかんないのかよ！";
    if (c === 24) return "＊さては　この反応を見て面白がってるな！";
    if (c === 25) return "＊そんなことしてると　いまに取り返しがつかない　ことになるぞ！";
    if (c >= 26 && c <= 30) return "＊…";
    if (c === 31) return "＊お　ま　え　の　か　お　よ　く　お　ぼ　え　た　か　ら　な";
    return "";                          // 32回目以降は何も表示しない（＝変身トリガー）
  }

  var e = DATA[Math.floor(Math.random() * DATA.length)];
  hit.textContent = pad(e.n);

  var spam = spamMessage(cnt);
  if (spam !== null) {                  // 連打イベント中: 番号は出すが専用文字列のみ（扉は出さない）
    if (cnt >= 32) {                    // 無言の先まで進めた＝変身イベント発動
      triggerHaunted(e.n);
      return;
    }
    msg.textContent = spam;
    if (cnt === 31) {                   // 31回目：これ以上更新しなくても10秒放置で変身させる
      setTimeout(function(){ triggerHaunted(e.n); }, 10000);   // 異変に気付けるようにする保険
    }
    return;
  }

  if (e.img) {                        // 扉イベント（-6666666）: Nobody.pngをフェード・コメント無し
    showDoor(e);
  } else if (e.m) {
    msg.textContent = e.m;
  }
})();
</script>"""

# バックナンバー／公式情報など，ヘッダー付きの単純ページ（カウンター無し）
SUBPAGE_TMPL = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - {site}</title>
<link rel="stylesheet" href="style.css">
</head>
<body class="{body_class}">
<header class="site-header">
  <div class="header-logo">{site}<span class="dotcom">.com</span></div>
  {nav}
</header>
<main class="index-main">
  {title_block}
  {content}
</main>
<footer class="site-footer"><a href="index.html">&laquo; 目次にもどる</a></footer>
</body></html>
"""

NOBODY_TMPL = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>&#12288;</title>
<style>
  @font-face {
    font-family:"DeterminationJP";
    src:url("fonts/DeterminationJP.ttf") format("truetype");
    font-display:swap;
  }
  html, body { margin:0; height:100%; background:#000; overflow:hidden;
    font-family:"DeterminationJP","MS PGothic",Osaka,sans-serif; cursor:default; }

  /* 扉の背後に立つもの。ほとんど見えない濃い灰色でゆっくり浮かぶ */
  #door { position:fixed; left:50%; top:50%; transform:translate(-50%,-50%);
    width:150px; image-rendering:pixelated; opacity:0; filter:brightness(.10) grayscale(1);
    transition:opacity 6s ease-in, filter 6s ease-in; pointer-events:none; z-index:1; }
  #door.awake { opacity:.16; filter:brightness(.22) grayscale(1); }

  /* モノローグ本体 */
  #scene { position:fixed; inset:0; z-index:2; display:none; flex-direction:column;
    align-items:center; justify-content:center; padding:8vh 6vw; box-sizing:border-box;
    text-align:center; }
  #scene.on { display:flex; }   /* パスワード正解後に表示 */
  #log { max-width:640px; width:100%; color:#c9c9c9; font-size:19px; line-height:2.05;
    letter-spacing:1px; text-shadow:0 0 6px rgba(180,180,180,.25); min-height:2em; }
  #log .ln { opacity:.92; margin:0; white-space:pre-wrap; }
  #cursor { display:inline-block; width:.55em; height:1.05em; margin-left:2px;
    background:#c9c9c9; vertical-align:-2px; animation:blink 1.05s steps(1) infinite; }
  @keyframes blink { 50% { opacity:0; } }

  /* 正体不明の数字 */
  .num { display:block; margin:.5em 0; color:#e8e8e8; font-size:40px; letter-spacing:6px;
    font-family:"Courier New",monospace; font-weight:bold;
    text-shadow:2px 0 6px rgba(255,60,60,.55), -2px 0 6px rgba(60,120,255,.55); }

  /* CRTの走査線とビネット */
  #crt { position:fixed; inset:0; z-index:5; pointer-events:none;
    background:
      radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,.9) 100%),
      repeating-linear-gradient(0deg, rgba(0,0,0,0) 0px, rgba(0,0,0,0) 2px,
        rgba(0,0,0,.28) 3px, rgba(0,0,0,.28) 4px);
    mix-blend-mode:multiply; }

  /* 砂嵐（一瞬の乱れ） */
  #static { position:fixed; inset:0; z-index:6; display:none; opacity:.0; }

  /* 画面全体のグリッチ（たまに横ずれ＆色収差） */
  .glitch #scene { animation:glitch .22s steps(2) 2; }
  @keyframes glitch {
    0% { transform:translate(0,0); filter:none; }
    25% { transform:translate(-3px,1px); filter:hue-rotate(20deg) contrast(1.4); }
    50% { transform:translate(4px,-2px); }
    75% { transform:translate(-2px,2px); filter:contrast(1.6); }
    100% { transform:translate(0,0); filter:none; }
  }

  /* 終盤に中央下へ現れる「木の後ろにいた男」。文字より下のレイヤー（z-index:1） */
  #man { position:fixed; left:50%; bottom:4vh; transform:translateX(-50%);
    width:140px; image-rendering:pixelated; opacity:0; z-index:1; pointer-events:none;
    transition:opacity 4s ease-in; filter:brightness(.9); }
  #man.show { opacity:.85; }

  /* 選択肢・入力欄を置くUI領域（ログの下） */
  #ui { margin-top:30px; min-height:1px; display:flex; flex-direction:column;
    align-items:center; }
  .choices { display:flex; gap:46px; justify-content:center;
    opacity:0; animation:uiIn .5s ease forwards; }
  @keyframes uiIn { to { opacity:1; } }
  .choice { font-family:inherit; font-size:19px; letter-spacing:3px;
    background:transparent; color:#c9c9c9; border:2px solid #555; padding:8px 30px;
    cursor:pointer; }
  .choice:hover { color:#fff; border-color:#c9c9c9; background:#111; }
  .choices.vanish { opacity:0; transform:scale(.88);
    transition:opacity .35s ease, transform .35s ease; }
  .field { font-family:inherit; font-size:19px; letter-spacing:2px; text-align:center;
    background:#0a0a0a; color:#dcdcdc; border:none; border-bottom:2px solid #666;
    padding:6px 12px; width:min(360px,78vw); outline:none; caret-color:#c9c9c9;
    opacity:0; animation:uiIn .5s ease forwards; }
  .field::selection { background:#333; color:#dcdcdc; }
  .minigame-stub { display:flex; flex-direction:column; align-items:center; gap:18px;
    opacity:0; animation:uiIn .5s ease forwards; }
  .mg-note { color:#8a8a8a; font-size:14px; letter-spacing:3px; }

  /* ベータテスト用URL（イベント終盤に表示され，書き留めてもらう）。
     下に続く選択肢ボタンと誤クリックしないよう，下側に大きめの余白を取る */
  .beta-link { margin:26px 0 56px; opacity:0; animation:uiIn .8s ease forwards; }
  .beta-link a { color:#33ff66; font-size:15px; letter-spacing:1px; word-break:break-all;
    text-decoration:underline; text-shadow:0 0 8px rgba(51,255,102,.4); }
  .beta-link a:hover { color:#7fffa5; }

  /* 白フェード用オーバーレイ（最前面） */
  #white { position:fixed; inset:0; z-index:9; background:#fff; opacity:0;
    pointer-events:none; }

  a.back { position:fixed; left:10px; bottom:10px; z-index:7; color:#141414; font-size:12px;
    text-decoration:none; letter-spacing:1px; opacity:0; transition:opacity 3s ease-in; }
  a.back.show { opacity:1; color:#4a4a4a; }
  a.back:hover { color:#c9c9c9; }

  /* ─ パスワードゲート ─
     一見なにもない暗闇。背景よりほんの少しだけ黒い入力欄が潜んでいて，
     注意深くマウスを重ねる（I字カーソル）・クリック・ドラッグすると存在に気づける。 */
  #gate { position:fixed; inset:0; z-index:8; background:#060606;
    transition:opacity 1.1s ease; }
  #gate.open { opacity:0; }
  #pw { position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
    width:min(340px, 78vw); height:42px; padding:0 10px;
    background:#000; border:1px solid #070707; border-radius:0;
    color:#151515; caret-color:#2a2a2a; font-size:16px; letter-spacing:3px;
    font-family:inherit; outline:none; -webkit-appearance:none; appearance:none; }
  #pw:hover, #pw:focus { border-color:#171717; }   /* 注意深く触れたときだけ薄く枠が浮く */
  #pw::selection { background:#242424; color:#151515; }   /* ドラッグで存在が分かる */
  #pw::-moz-selection { background:#242424; color:#151515; }
</style>
</head>
<body>
<img id="man" src="resource/Man_overworld_retro_tree.gif" alt="">
<div id="scene">
  <img id="door" src="resource/Nobody.png" alt="">
  <div id="log"></div>
  <div id="ui"></div>
</div>
<canvas id="static"></canvas>
<div id="crt"></div>
<div id="white"></div>
<div id="gate"><input id="pw" type="text" autocomplete="off" autocapitalize="off"
  autocorrect="off" spellcheck="false" aria-label=""></div>
<a class="back" href="index.html">&laquo; とじる</a>

<script src="minigame.js"></script>
<script>
//-----------------------------------------------------------------------------
// 隠し扉の先。「わすれられたもの」との対話イベント。
// パスワード突破 → 少し間をおいて独白開始 → Y/N選択・名前/ジャンル入力で分岐 →
// 選択を誤ると失敗セリフのあとタブが閉じる。最後まで進むと egg.png を渡して幕。
//-----------------------------------------------------------------------------
var log    = document.getElementById("log");
var ui     = document.getElementById("ui");
var door   = document.getElementById("door");
var man    = document.getElementById("man");
var scene  = document.getElementById("scene");
var gate   = document.getElementById("gate");
var pw     = document.getElementById("pw");
var white  = document.getElementById("white");
var body   = document.body;

var NAME = "キミ";                                   // 名前入力後に更新（既定は「キミ」）
function fill(s) { return String(s).split("<名前>").join(NAME); }
function wait(ms) { return new Promise(function(r){ setTimeout(r, ms); }); }

// ---- タイプ表示 ----------------------------------------------------------
var cursor = document.createElement("span"); cursor.id = "cursor";
function newLine(cls) {
  var p = document.createElement("p"); p.className = "ln" + (cls ? " " + cls : "");
  log.appendChild(p); p.appendChild(cursor);
  while (log.children.length > 7) log.removeChild(log.firstChild);  // 画面内に収める
  return p;
}
function typeText(str) {
  str = fill(str);
  return new Promise(function(resolve){
    var p = newLine();
    var i = 0;
    (function step(){
      if (i < str.length) {
        p.insertBefore(document.createTextNode(str.charAt(i)), cursor);
        i++;
        var ch = str.charAt(i - 1);
        var d = (ch === "。" || ch === "…" || ch === "、" || ch === "？" || ch === "！") ? 250 : 56;
        setTimeout(step, d + Math.random() * 24);
      } else { resolve(); }
    })();
  });
}
function say(text, after) { return typeText(text).then(function(){ return wait(after || 650); }); }
// 元テキストの空行を表示に反映（空の行を挟む）＋ そのぶん間をあける
function blankLine() { var p = newLine(); return p; }
function gap(ms) { blankLine(); return wait(ms || 1200); }

// ---- 演出（グリッチ・砂嵐・白フェード） ----------------------------------
function glitchOnce() {
  body.classList.add("glitch");
  setTimeout(function(){ body.classList.remove("glitch"); }, 460);
}
var canvas = document.getElementById("static");
var cctx = canvas.getContext("2d");
function burst(ms) {
  return new Promise(function(resolve){
    canvas.width  = Math.ceil(window.innerWidth / 4);
    canvas.height = Math.ceil(window.innerHeight / 4);
    canvas.style.width = "100%"; canvas.style.height = "100%";
    canvas.style.display = "block"; canvas.style.opacity = ".5";
    var raf;
    (function draw(){
      var img = cctx.createImageData(canvas.width, canvas.height), d = img.data;
      for (var i = 0; i < d.length; i += 4) {
        var v = Math.random() * 255 | 0; d[i] = d[i+1] = d[i+2] = v; d[i+3] = 255;
      }
      cctx.putImageData(img, 0, 0);
      raf = requestAnimationFrame(draw);
    })();
    setTimeout(function(){
      cancelAnimationFrame(raf);
      canvas.style.display = "none"; canvas.style.opacity = "0";
      resolve();
    }, ms);
  });
}
async function whiteFadePartial() {          // 白くなりかけて、また戻る
  white.style.transition = "opacity 3.4s ease"; white.style.opacity = ".92";
  await wait(3500);
  white.style.transition = "opacity 3s ease"; white.style.opacity = "0";
  await wait(3000);
}
async function whiteOutClose() {             // 完全に白へ → タブを閉じる
  white.style.transition = "opacity 5s ease"; white.style.opacity = "1";
  await wait(5200);
  closeTab();
}

// ---- タブを閉じる（本番は扉から window.open で開くので閉じられる） -------
function closeTab() {
  try { window.open("", "_self"); } catch (e) {}
  window.close();
  // 閉じられない環境（URL直開き等）の保険：真っ暗にして終わらせる
  setTimeout(function(){
    document.documentElement.innerHTML =
      "<body style='margin:0;height:100vh;background:#000'></body>";
  }, 500);
}
async function glitchClose() {               // 即・崩壊してから閉じる
  glitchOnce(); await wait(520);
  await burst(750);
  closeTab();
}
async function failClose(line) {             // 失敗セリフ→5秒後に崩壊→閉じる
  if (line) await say(line, 0);
  await wait(5000);
  glitchOnce(); await wait(520);
  await burst(750);
  closeTab();
}

// ---- 入力・選択肢 --------------------------------------------------------
function askYesNo() { return askChoice("はい", "いいえ"); }
// 任意ラベルの二択。左側が選ばれたら true を返す。
function askChoice(labelL, labelR) {
  return new Promise(function(resolve){
    var box = document.createElement("div"); box.className = "choices";
    var y = document.createElement("button"); y.className = "choice"; y.textContent = labelL;
    var n = document.createElement("button"); n.className = "choice"; n.textContent = labelR;
    box.appendChild(y); box.appendChild(n); ui.appendChild(box);
    function pick(v){ box.remove(); resolve(v); }
    y.addEventListener("click", function(){ pick(true); });
    n.addEventListener("click", function(){ pick(false); });
  });
}
function fakeYesNo() {                        // 選ぼうとすると逃げて消える偽の選択肢
  return new Promise(function(resolve){
    var box = document.createElement("div"); box.className = "choices";
    var y = document.createElement("button"); y.className = "choice"; y.textContent = "はい";
    var n = document.createElement("button"); n.className = "choice"; n.textContent = "いいえ";
    box.appendChild(y); box.appendChild(n); ui.appendChild(box);
    var gone = false;
    function vanish(){
      if (gone) return; gone = true;
      box.classList.add("vanish");
      setTimeout(function(){ box.remove(); resolve(); }, 380);
    }
    [y, n].forEach(function(b){
      b.addEventListener("mouseenter", vanish);
      b.addEventListener("mousedown", vanish);
      b.addEventListener("touchstart", vanish);
      b.addEventListener("click", vanish);
    });
    setTimeout(vanish, 4200);                 // 触れなくても数秒で消えて先へ
  });
}
function askInput() {
  return new Promise(function(resolve){
    var inp = document.createElement("input"); inp.className = "field"; inp.type = "text";
    inp.autocomplete = "off"; inp.spellcheck = false;
    ui.appendChild(inp); inp.focus();
    inp.addEventListener("keydown", function(e){
      if (e.key === "Enter") {
        var v = inp.value;
        if (!v.trim()) return;                // 空欄では進めない
        inp.remove(); resolve(v);
      }
    });
  });
}

// ---- 入力内容の判定 ------------------------------------------------------
var CHARS_JP = ["サンズ","パピルス","トリエル","アンダイン","アルフィー","メタトン","アズゴア","フリスク","キャラ"];
var CHARS_EN = ["sans","papyrus","toriel","undyne","alphys","mettaton","asgore","frisk","chara"];
var REFUSE   = ["いやだ","むり","おしえたくない","ことわる","いや","いやだね"];
var BADWORDS = ["しね","ころす","ころせ","きもい","きしょ","ぶす","ぶさいく","ばか","あほ","かす",
  "くず","うざい","だまれ","げす","ちんこ","まんこ","ちんちん","せっくす","えっち","えろ","ちくび",
  "おっぱい","きんたま","ぺにす","ヴァギナ","fuck","shit","bitch","dick","sex","penis","pussy","boobs"];
// 名前の表記ゆれ対策：NFKC正規化（半角カナ→全角・全角英数→半角）＋小文字化＋
// 空白/中黒/ピリオド除去＋ひらがな→カタカナ。これで大小・半全・かなカナを吸収する。
function normName(s){
  var t = String(s);
  if (t.normalize) t = t.normalize("NFKC");
  t = t.toLowerCase().replace(/[\s\.・･]/g, "");
  return t.replace(/[ぁ-ゖ]/g, function(c){ return String.fromCharCode(c.charCodeAt(0) + 0x60); });
}
function inList(raw, list){
  var t = normName(raw);
  for (var i = 0; i < list.length; i++) if (t.indexOf(normName(list[i])) >= 0) return true;
  return false;
}
function isGaster(raw){ return inList(raw, ["ガスター","gaster"]); }
function isChar(raw){ return inList(raw, CHARS_JP.concat(CHARS_EN)); }
var KRIS_N   = ["クリス","kris","chris"];                                  // ⑥
var SUSIE_N  = ["スージィ","スージー","スーザン","susie","susan","suzie"];  // ⑦
var FRIEND_N = ["ラルセイ","ノエル","バードリー","キャッティ","ジョッキントン",
  "ralsei","noelle","noel","berdly","catti","jockington"];                  // ⑧
var TOBY_N   = ["トビー","テミー","toby","temmie"];                         // ⑨（トビーフォックスも拾う）
var TRICK = ["わしにしね","わたしにしね"];   // normNameでカナ/かな・半全の表記ゆれを吸収
function isTrick(raw){ return inList(raw, TRICK); }
function isRefuse(raw){ var t = raw.replace(/\s/g, ""); return REFUSE.indexOf(t) >= 0; }
function hasProfanity(s){ var t = s.toLowerCase(); for (var i = 0; i < BADWORDS.length; i++) if (t.indexOf(BADWORDS[i]) >= 0) return true; return false; }
function cp(s){ return Array.from(String(s)); }            // コードポイント配列（絵文字/結合対策）

// 全角英数を半角化し，小文字化・空白除去（大文字小文字/半角全角の表記ゆれ対策）
function normJ(s){
  return String(s)
    .replace(/[Ａ-Ｚａ-ｚ０-９]/g, function(c){ return String.fromCharCode(c.charCodeAt(0) - 0xFEE0); })
    .toLowerCase().replace(/\s/g, "");
}
var UTDR   = ["undertale","deltarune","アンダーテール","デルタルーン","ｱﾝﾀﾞｰﾃｰﾙ","ﾃﾞﾙﾀﾙｰﾝ"];
var MOTHER = ["mother","マザー","ﾏｻﾞｰ"];
function isUTDR(raw){ var t = normJ(raw); for (var i = 0; i < UTDR.length; i++) if (t.indexOf(UTDR[i].toLowerCase()) >= 0) return true; return false; }
function isMother(raw){ var t = normJ(raw); for (var i = 0; i < MOTHER.length; i++) if (t.indexOf(MOTHER[i].toLowerCase()) >= 0) return true; return false; }

// ===========================================================================
// 本編シナリオ
// ===========================================================================
async function story() {
  await wait(2600);                          // パスワード後の“少しの間”
  await say("…", 1500);
  await say("……", 1500);
  await say("とびらを　あけたのは　きみかな？", 1100);
  await say("…", 1500);
  await say("わたしは　ただの　おとこ。", 900);
  await say("わたしは　わすれられた　もの。", 900);
  await say("わたしは…　なんだったかな？", 1300);
  await gap(1200);
  await say("まあ　そんなさまつなことは　どうでもよいか。", 1000);
  await say("ここには　だれも　いない。", 900);
  await say("そうおもうかい？", 700);

  // 選択1：正解=いいえ
  if (await askYesNo()) { return failClose("＊ここにはなにもいなかった"); }
  await say("それは　うれしい　かいとうだ…", 1100);
  await say("わたしは　わたしを　よくわすれる　ものでね。", 1000);
  await gap(1200);
  await say("…", 1500);
  await say("…", 1500);
  await say("でも　なぜかキミとは　すでになんどか　であったような　きがする。", 1000);
  await say("ふしぎな　バカげた　はなし　かもしれないけどね。", 1000);
  await say("キミは　わたしの　はなしを　しんじてくれるかい？", 700);

  // 選択2：正解=はい
  if (!(await askYesNo())) {
    await say("そうか…　それはざんねんだ。", 1100);
    return failClose("もし　キミがわたしを　わすれなければ　またどこかで　あおう。");
  }
  await say("すばらしい…", 1200);
  await gap(1000);

  // 名前入力
  await say("キミ…　だとすこし　そっけないか", 900);
  await say("キミの　なまえを　おしえて　ほしい。", 900);
  await say("…いや　ニックネームや　ハンドルネームで　かまわないよ。", 500);
  var nameRaw = (await askInput()).trim();
  if (isGaster(nameRaw)) {                    // ③
    return glitchClose();
  } else if (isChar(nameRaw)) {               // ②
    await say("…いくら　わたしが　しょたいめん　だからといって", 800);
    await say("たにんの　なまえを　おしえるのは　さすがに　ダメだとおもうぞ。", 1000);
    await gap(900);
    await say("わかった…　むりに　おしえなくて　いい。", 900);
    NAME = "キミ";
  } else if (isTrick(nameRaw)) {              // ⑤
    await say("なるほど　わしにし…", 1300);
    await gap(900);
    await say("あぶない…　あやうく　ひっかかる　ところだった。", 900);
    await say("そんな　こてんてきな　トリックには　かからないぞ。", 900);
    NAME = "キミ";
  } else if (isRefuse(nameRaw)) {             // ④
    await say("…そうか", 1100);
    await say("わかった…　むりに　おしえなくて　いい。", 900);
    NAME = "キミ";
  } else if (inList(nameRaw, KRIS_N)) {       // ⑥ たいせつな ゆうじんと同じ名前
    await say("…", 1500);
    await say("なるほど　きぐうな…", 1000);
    await say("いや　なんでもない。", 900);
    await say("わたしの　たいせつな　ゆうじんと　おなじなまえ　だったものでね。", 1000);
    await say("よろしくたのむよ　クリスくん。", 1000);
    NAME = "クリス";
  } else if (inList(nameRaw, SUSIE_N)) {      // ⑦ くされえんの ゆうじんと似た名前
    await say("…", 1500);
    await say("なるほど　きぐうな…", 1000);
    await say("いや　なんでもない。", 900);
    await say("わたしと　くされえんの　ゆうじんと　にたなまえ　だったものでね。", 1000);
    await say("わたしの　しりあいのなは　『スージー』という　なまえだが", 900);
    await say("このなまえを　きくと　つい　はんのうしてしまってな。", 1000);
    NAME = nameRaw + "くん";
    await say("よろしくたのむよ　" + NAME + "。", 1000);
  } else if (inList(nameRaw, FRIEND_N)) {     // ⑧ わすれてしまった ともだち
    await say("…うむ", 1200);
    await say("…", 1500);
    await say("いや　どこかで　きいたような　ひびきなのだが", 900);
    await say("おもいだすことが　できなくて　モヤモヤするものだ。", 1000);
    await say("わすれてしまう　まえは　かけがえのない　ともだち　だったような", 900);
    await say("そんな　きおくがあったの　だけどね…", 1300);
    await say("…", 1500);
    NAME = nameRaw + "くん";
    await say("あらためて　よろしくたのむよ　" + NAME + "。", 1000);
  } else if (inList(nameRaw, TOBY_N)) {       // ⑨ しろいいぬの乱入 → 強制終了
    await say("なるほど　" + nameRaw + "　というのか。", 900);
    await say("ありがとう　そして　よろしくたのむ。", 900);
    await say("…", 1500);
    await say("ん…？", 1400);
    await gap(1000);
    await say("な　なんだ　このしろいいぬ！？", 800);
    await say("どこから　はいってきたのだ！", 1000);
    await gap(900);
    await say("コンソールのうえに　のるんじゃない！", 1100);
    await gap(900);
    await say("aornuaoo,ahijiuuuuuuuuu", 400);
    glitchOnce();
    await say("12kqozjjr2khfsoea5@", 900);
    await gap(800);
    await say("まて！　コーヒーが　きばんに！？", 500);
    glitchOnce();
    await say("auhfoewiohcoowiofjioawjsfpjewajfjpsjfpejfpjewajo", 300);
    await say("kaunrnakai kafhan67208nsajfhiame aojfaiakimah", 400);
    glitchOnce();
    await gap(800);
    await say("な　なにをする！", 800);
    return failClose("くぁwせdrftgyふじこlp");
  } else {                                    // ①
    await say("なるほど　" + nameRaw + "　というのか。", 900);
    await say("ありがとう　そして　よろしくたのむ。", 900);
    NAME = nameRaw + "くん";
    await say(NAME + "。", 1000);
  }
  await gap(1000);

  // パズル好き？（偽の選択肢）
  await say("では　もうすこしだけ　はなしを　させてほしい。", 800);
  await say("<名前>は　パズルゲームはすきかな？", 400);
  await fakeYesNo();
  await say("…いや　むりじいを　するのは　よくないか。", 900);
  await say("わたしが　すきなものを　きみが　すきである　かくしょうは　ないからね。", 1000);
  await say("<名前>が　すきな　ゲームの　ジャンルを　おしえてほしい。", 500);

  // ジャンル入力
  var genre = (await askInput()).trim();
  if (hasProfanity(genre)) {                  // ③
    await say("<名前>は　どのゲームで　あそぶときも", 800);
    await say("そういうことを　ためすのかい？", 900);
    await say("<名前>の　こうきしんには　かんたんさせられる　ばかりだ。", 1100);
  } else if (cp(genre).length >= 15) {        // ②
    await say("…ん？　なんだって？", 800);
    await say(cp(genre).slice(0, 6).join("") + "…　だったっけ？", 900);
    await say("すまない　ながすぎて　わすれてしまったよ。", 900);
    await say("だが　ねっしんに　きかせてくれて　ありがとう。", 1100);
  } else {                                    // ①
    await say("なるほど　" + genre + "　がすきなのか。", 900);
    await say("…じつに　…じつに　きょうみぶかい。", 1300);
  }
  await gap(1000);

  // おすすめ作品入力（新規）
  await say("…", 1500);
  await say("もしよければだが　そのジャンルの　なかで　とくにおもしろい", 800);
  await say("さくひんが　あれば　おしえてほしい。", 900);
  await say("…", 1500);
  await say("もちろん　いやなら　こたえなくても　かまわない。", 500);
  var work = (await askInput()).trim();
  if (isUTDR(work)) {                         // ②
    await say("はて？　きいたことがない　さくひんだ。", 1000);
    await say("…", 1500);
    await say("…なんで　そんなひょうじょうを　するのだ？", 900);
    await say("まるで　わたしが　しらないふり　をきめこんでいる　ような", 900);
    await say("ぎねんの　めせんを　かんじざるえない。", 1200);
  } else if (isMother(work)) {                // ③
    await say("これはきぐうだ！", 900);
    await say("このさくひんは　すでに　あそんだことが　ある！！", 900);
    await say("あそびすぎて　あそびすぎて　このさくひんの　すべてを　しりたくなった！！！", 1000);
    await say("こどものころ　まどべで　くうそうに　ふけった　そのものがたりを", 800);
    await say("あのせかいに　おとしこみたかった…！", 1300);
    await gap(1200);
    await say("…", 1500);
    await say("いや　すまない　わたしも　このさくひんが　だいすきなもので", 900);
    await say("つい　じょうぜつに　かたってしまったよ。", 1200);
  } else if (isRefuse(work)) {                // ④
    await say("<名前>は　じぶんのいけんを　はっきりいう。", 900);
    await say("かんしんだ！", 900);
    await say("しょうらいは　だいとうりょう　かもしれないな。", 1100);
  } else {                                    // ①
    await say("なるほど　" + work + "　という　さくひんが　あるのか。", 900);
    await say("せっかく　<名前>に　おしえてもらった　さくひんだ", 800);
    await say("わすれないように　て　にメモを　かいておくとしよう。", 900);
    await say("なにぶん　ココでは　たいくつしのぎが　こいしくなる　ものでね。", 1200);
  }
  await gap(1000);

  // おれい → ミニゲーム（新規。正解=はい／いいえでも進む）
  await say("…", 1500);
  await say("じつに　きょうみぶかい。", 900);
  await say("いろいろ　<名前>には　おしえてもらった。", 900);
  await say("せっかくだから　なにか　おれいが　したいのだが", 800);
  await say("きょうみは　あるだろうか？", 600);
  if (await askYesNo()) {
    await say("そうこなくては。", 900);
    await say("さっそく　このがめんを　みてほしい。", 900);
    await wait(500);
    await playMinigame();                     // 「もうお腹一杯」を選ぶまで（リトライ込み）
    await gap(800);
    await say("…", 1500);
    await say("どうだろうか…？", 900);
    await say("たのしんで　もらえたのなら　こうえいなことだが…", 1000);
    await say("しょうじき　どうおもったかな？", 600);
    if (await askChoice("最☆高", "駄作")) {
      await say("…", 1500);
      await say("わたしの　じょしゅたちは　みな", 800);
      await say("きをつかって　くちをそろえて　『さいこう』と　ほめちぎって　きたものだが…", 1200);
      await gap(900);
      await say("<名前>は…　ほんとうに　しょうじきなところ　どうおもったかな？", 800);
      await say("きたんのない　いけんを　きかせてほしい。", 600);
      if (await askChoice("本当に楽しめた", "クソゲー")) {
        await say("…", 1500);
        await say("<名前>を　テストプレイヤーに　えらんで　ほんとうに　よかった。", 900);
        await say("この　さくひんは　むねをはって　リリースできると　かくしんできた。", 1200);
        await gap(900);
        await say("ぜひ　テストプレイを　たくさんしてほしい。", 900);
        await say("これから表示する　ウェブリンクは", 800);
        await say("このゲームの　ベータテストに　アクセスできるものだ。", 900);
        showBetaLink();                       // 直接アクセス用URL（合言葉つき）を提示
        await wait(1600);
        await say("わすれないように　かみに　かいたかい？", 600);
        while (!(await askYesNo())) {         // いいえ の間はループして待つ
          await say("きみは　とてもしょうじきもの　なおようだ。", 900);
          await say("おわるまで　まっているから　きにせずに　メモを　とってくれ。", 1200);
          await gap(1200);
          await say("わすれないように　かみに　かいたかい？", 600);
        }
        hideBetaLink();                       // メモを取り終えたらリンクを引っ込める
        await say("ああ　きみのきづずかいは　すばらしい", 900);
        await say("こんごも　よしなに　たのませてもらうよ。", 1200);
      } else {                                // クソゲー
        await say("…", 1500);
        await say("まあ　やはり　そうか…", 1100);
        await honestReaction();
      }
    } else {                                  // 駄作
      await honestReaction();
    }
  } else {
    await say("まあ　それは　しかたがないことだ。", 900);
    await say("もしも　つぎが　あれば　そのときは　ひろうしたい　ものだ。", 1100);
  }
  await gap(1000);

  // 追憶
  await say("…", 1500);
  await say("いろいろ　はなしを　していたら", 800);
  await say("おかげで　わたしも　すこしだけ　かこを　おもいだしてきた　かもしれない。", 1200);
  await gap(1000);
  await say("<名前>とは", 600);
  await say("いっしょに　ボイスチャットで　4人プレイのゲームで　あそんだ。", 900);
  await say("ゲームがかきょうのとき　よく　エグゼがクラッシュして　たいへんだった。", 900);
  await say("ソラライドでは　DDDだいおうと　ハイドラで　ぶいぶい　いわせたもんだ。", 900);
  await say("よくいっしょに　そざいを　あつめるぼうけんも　したものだ。", 900);
  await say("…", 1500);
  await say("あのときは　かってに　はなを　しゅうかくして　すまなかった…", 1200);
  await say("…", 1500);
  await gap(800);
  await say("<名前>は　わたしがかってに　はなを　とってしまったことを　ね　にもっているかい？", 700);

  // 選択3：正解=いいえ
  if (await askYesNo()) {
    await say("…つぎからは　きをつけるよ。", 900);
    return failClose("『つぎ』が　あればの　はなしだけどね…");
  }
  await say("<名前>の　かんだいなこころに　かんしゃする。", 1200);
  await gap(1000);

  // 終盤：中央下に「男」が浮かび上がる（文字より下のレイヤー）
  man.classList.add("show");
  await wait(600);
  await say("…", 1500);
  await say("じつに…　じつに…　ゆういぎな　じかんだ。", 900);
  await say("こんなに　たのしいと　かんじたのは　いついらいだろうか？", 1200);
  await gap(1000);
  await say("きのう？", 800);
  await say("いや　1つき？", 800);
  await say("それとも11ねん？", 1300);
  await gap(1000);
  await say("<名前>は　わたしを　わすれ", 800);
  await say("わたしも　わたしを　わすれるかもしれない。", 900);
  await say("それでも　わたしは", 800);
  await say("<名前>と　すごした　おもいでは　わすれはしない。", 900);
  await say("ほんとうに　ほんとうに　ありがとう。", 1400);

  // 白くなりかけて戻る
  await whiteFadePartial();

  await say("…ん？", 1200);
  await say("ここにきたのは　だれかが　たすけを　もとめていたから　だって？", 1000);
  await say("パスワードも　たすけを　もとめる　メッセージに　かいてあった？", 1200);
  await gap(1000);
  await say("…", 1500);
  await say("なるほどこまった。", 900);
  await say("ここには　わたしと　わたしと　<名前>　そして　わたししかいない。", 1000);
  await say("このこを　のぞいてはね。", 1200);
  await gap(1000);

  // egg.png を渡す
  downloadEgg();
  await say("タマゴなら　なにかしっている　かもしれない。", 900);
  await say("わたしとの　このかいわも", 700);
  await say("たすけを　もとめるこえの　しょうたいも…", 1300);
  await gap(1000);
  await say("てきとうに　おいておくと　なくしてしまうかもしれない。", 900);
  await say("だから　かならず　わかりやすい　ディレクトリに　おいておくように。", 1000);
  await say("タマゴは　はじることなどない。", 1300);
  await gap(1000);
  await say("さあ　もう　ゆきなさい。", 900);
  await say("かおをあらって　ふくをきて！", 900);
  await say("そして　つぎがあれば", 800);
  await say("もしわたしが　このかいわすら　わすれてしまったとしても…", 1100);
  await say("よろしくたのむ。", 1300);
  await say("…", 1500);
  await say("EOF", 1800);

  // 白へフェードアウト → 閉じる
  await whiteOutClose();
}

function downloadEgg() {
  var a = document.createElement("a");
  a.href = "resource/egg.png"; a.download = "egg.png";
  document.body.appendChild(a); a.click(); a.remove();
}

// 「駄作」「クソゲー」で共通する，いちばんの助手を思い出すくだり
async function honestReaction() {
  await say("しょうじきな　いけんを　きかせてくれて　ありがとう。", 900);
  await say("きみの　その　はっきりと　ものをいうすがた…", 900);
  await say("かおに　はりついた　えがお…", 1000);
  await say("わたしの　いちばんの　じょしゅのことを　おもいだしたよ。", 900);
  await say("かれと　おとうとは　いまも　げんきだろうか…", 1400);
}

// ベータテスト用の直接アクセスURL（合言葉つき）をログの下に表示する。
// 書き留めてもらう前提なのでフルURLをそのまま見せる。__GAMEKEY__ はビルド時に置換。
// 「かみに かいたかい？」で はい と答えたら hideBetaLink() でフェードアウトさせる。
var betaBox = null;
function showBetaLink() {
  var url = location.href.replace(/[^\\/]*$/, "") + "game.html?key=__GAMEKEY__";
  betaBox = document.createElement("div"); betaBox.className = "beta-link";
  var a = document.createElement("a");
  a.href = "game.html?key=__GAMEKEY__"; a.target = "_blank"; a.rel = "noopener";
  a.textContent = url;
  betaBox.appendChild(a); ui.appendChild(betaBox);
}
function hideBetaLink() {
  if (!betaBox) return;
  var el = betaBox; betaBox = null;
  el.style.animation = "none"; el.style.opacity = "1";     // uiInアニメの固定値を外す
  requestAnimationFrame(function(){
    el.style.transition = "opacity .8s ease"; el.style.opacity = "0";
    setTimeout(function(){ el.remove(); }, 900);
  });
}

// ミニゲーム（ゼルダ風・minigame.js）。クリア/ドロップのどちらでも解決して本編へ戻る。
// 何らかの理由で読み込めない場合はプレースホルダで先へ進めるようにしておく。
function playMinigame() {
  if (window.NobodyGame && typeof window.NobodyGame.start === "function") {
    return window.NobodyGame.start();
  }
  return new Promise(function(resolve){
    var box = document.createElement("div"); box.className = "minigame-stub";
    box.innerHTML =
      "<div class='mg-note'>［ ミニゲーム（じゅんびちゅう） ］</div>" +
      "<button class='choice mg-btn'>クリックで つづける</button>";
    ui.appendChild(box);
    box.querySelector(".mg-btn").addEventListener("click", function(){
      box.remove(); resolve();
    });
  });
}

//-----------------------------------------------------------------------------
// パスワードゲート。正解を入力するまでは真っ暗のまま先へ進めない。
// （静的サイトなので合言葉はソースから読めてしまう。あくまで隠し要素向け。）
//-----------------------------------------------------------------------------
var PASSWORD = "FJFIrejirioEUEUROEI4378789";
var opened = false;

function startMonologue() {
  if (opened) return;
  opened = true;
  gate.classList.add("open");                          // ゲートを暗転させて消す
  setTimeout(function(){ gate.style.display = "none"; }, 1200);
  scene.classList.add("on");                           // 対話画面を表示
  setTimeout(function(){ door.classList.add("awake"); }, 800);
  story();
}
function checkPassword() {
  if (pw.value.trim() === PASSWORD) startMonologue();
}
pw.addEventListener("input", checkPassword);
pw.addEventListener("keydown", function(e){ if (e.key === "Enter") checkPassword(); });
</script>
</body></html>
"""

# 隠しミニゲームの直接アクセスページ（site/game.html）。
# nobody.html のイベントで提示される ?key=<GAME_KEY> 付きURLで開いたときだけ遊べる。
# キー無し・不一致のアクセスには真っ黒の画面だけを見せる（隠しページの流儀に合わせる）。
GAME_TMPL = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>&#12288;</title>
<style>
  @font-face { font-family:"DeterminationJP";
    src:url("fonts/DeterminationJP.ttf") format("truetype"); font-display:swap; }
  html,body { margin:0; height:100%; background:#000; overflow:hidden;
    font-family:"DeterminationJP","MS PGothic",Osaka,sans-serif; color:#c9c9c9; }
  #panel { position:fixed; inset:0; display:none; flex-direction:column;
    align-items:center; justify-content:center; gap:20px; text-align:center; }
  #panel.on { display:flex; }
  h1 { color:#e6e6e6; font-size:22px; letter-spacing:3px; margin:0; }
  .sub { color:#33ff66; font-size:12px; letter-spacing:3px; }
  p { color:#8a8a8a; font-size:13px; line-height:1.9; margin:0; }
  button { font-family:inherit; font-size:18px; letter-spacing:2px; color:#e6e6e6;
    background:transparent; border:2px solid #666; padding:10px 34px; cursor:pointer; }
  button:hover { background:#111; border-color:#ccc; }
  #result { color:#e6e6e6; font-size:15px; min-height:1.4em; }
</style>
</head>
<body>
<div id="panel">
  <h1>ベータテスト</h1>
  <div class="sub">TEST PLAYER ONLY</div>
  <p>そうさ： 移動＝←↑↓→ / WASD　　剣＝Z（Space・J）　　杖＝X<br>
     レベルアップ・かいもの＝↑↓でえらび Enter/Z　　やめる＝Esc / Q<br>
     ぜんぶの敵をたおすと扉があき，画面のはしから つぎのスクリーンへ</p>
  <button id="startBtn">▶ テストをはじめる</button>
  <div id="result"></div>
</div>
<script src="minigame.js"></script>
<script>
// 合言葉（?key=）が一致したときだけパネルを出す。不一致なら真っ黒のまま。
var KEY = "__GAMEKEY__";
var panel = document.getElementById("panel");
var btn = document.getElementById("startBtn");
var res = document.getElementById("result");
if (new URLSearchParams(location.search).get("key") === KEY) {
  panel.classList.add("on");
  btn.addEventListener("click", function(){
    panel.classList.remove("on");
    res.textContent = "";
    window.NobodyGame.start().then(function(score){
      panel.classList.add("on");
      res.textContent = "スコア: " + score + "　テストプレイに かんしゃする。";
    });
  });
}
</script>
</body></html>
"""

# 変身イベントの最後に遷移する動画ページ（ローカル動画を音あり優先で自動再生）
KURAE_TMPL = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>これでもくらえ</title>
<style>
  html, body { margin:0; height:100%; background:#000; overflow:hidden; }
  #vid { position:fixed; inset:0; width:100%; height:100%; object-fit:contain; background:#000; }
  #cover { position:fixed; inset:0; z-index:10; display:none;
    align-items:center; justify-content:center; flex-direction:column;
    background:rgba(0,0,0,.6); color:#fff; cursor:pointer; user-select:none;
    font-family:"MS PGothic",Osaka,sans-serif; }
  #cover .big { font-size:72px; line-height:1; }
  #cover .txt { margin-top:18px; font-size:18px; letter-spacing:2px; }
</style>
</head>
<body>
<video id="vid" src="resource/Sans_Dance!.mp4" autoplay loop playsinline></video>
<div id="cover"><div class="big">&#128266;</div><div class="txt">クリックで音を出す</div></div>
<script>
//-------------------------------------------------------------------------------
// ローカル動画を音あり優先で再生し，ブロックされたらミュート再生＋クリック保険を出す処理
//-------------------------------------------------------------------------------
var vid = document.getElementById("vid");
var cover = document.getElementById("cover");

vid.play().catch(function(){                 // 音あり自動再生がブロックされた場合
  vid.muted = true;                          // いったんミュートで再生を続行し
  vid.play().catch(function(){});
  cover.style.display = "flex";              // クリックで音を出せるようにする
});

cover.addEventListener("click", function(){
  vid.muted = false; vid.play();             // クリックで音ありフル再生
  cover.style.display = "none";
});

//-------------------------------------------------------------------------------
// 戻るボタンの無効化（連打されても他ページへ抜けられないようにする処理）
// 履歴を厚めに積んで連打のバーストを吸収し，戻られるたびに1個積み直して深さを一定に保つ
//-------------------------------------------------------------------------------
(function(){
  function plug(){ history.pushState(null, "", location.href); }
  for (var i = 0; i < 20; i++) plug();                      // バースト対策に履歴を多めに積む
  window.addEventListener("popstate", function(){ plug(); });  // 戻られた分を都度積み直す
})();
</script>
</body></html>
"""

CSS = """/* ===== Webフォント ===== */
@font-face {
  font-family:"DeterminationJP";
  src:url("fonts/DeterminationJP.ttf") format("truetype");
  font-display:swap;
}
@font-face {
  font-family:"MonsterFriendFore";
  src:url("fonts/MonsterFriendFore.otf") format("opentype");
  font-display:swap;
}

/* ===== 共通 ===== */
* { box-sizing: border-box; }
body { margin:0;
  font-family:"DeterminationJP","MS PGothic",Osaka,sans-serif; }
/* カスタムフォントは太字を持たず，合成太字だと潰れる．見出しの既定太字を無効化する */
h1, h2, h3, h4, h5, h6 { font-weight:normal; }
.header-logo, .header-nav, .index-title, .index-sub, .index-section-h,
.toc-item h2, .board-title, .section-title, .thread-bar, .ref-item {
  font-family:"MonsterFriendFore","DeterminationJP","MS PGothic",sans-serif;
}

/* ===== サイトヘッダー（黒背景＋白線白文字／スクロール追従） ===== */
.site-header { position:sticky; top:0; z-index:100;
  background:#000; color:#fff; border-bottom:1px solid #fff; }
.header-logo { color:#fff; font-size:20px;
  padding:8px 14px; letter-spacing:2px; }
.header-logo .dotcom { color:#fff; opacity:.55; }
.header-nav { display:flex; flex-wrap:wrap; border-top:1px solid #fff; }
.navtab { display:block; padding:6px 16px; font-size:12px; color:#fff; text-decoration:none;
  border-right:1px solid rgba(255,255,255,.4); }
.navtab:hover { background:#fff; color:#000; }
.navtab.current { background:#fff; color:#000; }

/* ===== インデックス（Toby Fox 風 黒背景＋黄色） ===== */
.index-page { background:#000; color:#fff; text-align:center; }
.index-page .site-header { text-align:left; }
.index-main { max-width:640px; margin:0 auto; padding:60px 16px 80px; }
.index-title { color:#ffe600; font-size:34px; margin:0 0 8px; line-height:1.3; }
/* サブページの見出しをロゴ画像で出す場合（PAGE_LOGOS） */
.page-logo-wrap { line-height:0; margin:0 0 16px; }
.page-logo { display:block; margin:0 auto; width:auto; max-width:100%;
  max-height:130px; height:auto; }
.index-sub { color:#fff; font-size:15px; margin:0 0 50px; }
/* アクセスカウンター／キリ番ゲッター */
#counter { margin:0 auto 40px; }
.counter-line { font-size:15px; color:#fff; margin:0; }
.hit-digits { display:inline-block; background:#000; color:#33ff66;
  font-family:"Courier New",monospace; font-weight:bold; font-size:22px;
  letter-spacing:4px; padding:3px 10px; border:2px solid #33ff66;
  border-radius:3px; vertical-align:middle; margin:0 4px; }
.kiriban-msg { min-height:1.2em; margin:14px 0 0; font-size:15px; color:#ffe600; }
#kiriban-extra { margin-top:10px; }
.nobody-door { display:block; width:120px; margin:0 auto; cursor:pointer;
  image-rendering:pixelated; animation:doorfade 2.4s ease-in; }
.nobody-door:hover { filter:brightness(1.25); }
@keyframes doorfade { 0% { opacity:0; } 100% { opacity:1; } }
/* カウンターと新着の間の画像（通常時：スージィ／-6666666時：Nobody） */
#interlude { margin:6px auto 40px; }
.interlude-img { display:block; margin:0 auto; max-width:240px; width:100%; height:auto; }
.haunted #interlude { display:none; }
.kiriban-msg.hit { color:#ff5fa2;
  animation:blink 1s steps(1) infinite; }
@keyframes blink { 50% { opacity:.3; } }

.index-section-h { color:#ffe600; font-size:18px; margin:60px 0 24px; letter-spacing:2px; }
.toc-item { display:block; max-width:380px; margin:0 auto 28px; text-decoration:none;
  color:#fff; }
.toc-item:hover { opacity:.85; }
.toc-item h2 { color:#ffe600; font-size:19px; margin:0 0 4px; }
.toc-item p { color:#ddd; font-size:13px; margin:0; }
.toc-text { display:block; }
/* 新着バッジはタイトルの隣にインライン表示し，少しだけ左に傾ける */
.toc-item h2 .new-badge { display:inline-block; width:auto; height:34px; vertical-align:middle;
  margin-left:8px; transform:rotate(-8deg); }
.ref-list { max-width:560px; margin:0 auto; text-align:left;
  display:grid; grid-template-columns:repeat(2,1fr); gap:14px; }
@media (max-width:520px){ .ref-list { grid-template-columns:1fr; } }
.ref-item { display:block; border:2px solid #ffe600; color:#ffe600; text-decoration:none;
  padding:10px 14px; font-size:14px; }
.ref-item:hover { background:#ffe600; color:#000; }
.ref-item:hover .ref-url { color:#333; }
.ref-url { display:block; color:#7fb0ff; font-size:11px; word-break:break-all; margin-top:3px; }

/* ===== インデックスの「コンテンツ」ボタン（2列／テキスト2/3＋右にアイコン1/3） ===== */
.content-list { max-width:560px; margin:0 auto; display:grid;
  grid-template-columns:repeat(2,1fr); gap:16px; }
@media (max-width:520px){ .content-list { grid-template-columns:1fr; } }
.content-btn { display:flex; align-items:stretch; min-height:96px;
  border:2px solid #ffe600; color:#ffe600; text-decoration:none; overflow:hidden; }
.content-btn:hover { background:#ffe600; color:#000; }
.cb-text { flex:1; display:flex; flex-direction:column; justify-content:center; align-items:center;
  text-align:center; padding:16px 14px; }
.content-btn.has-icon .cb-text { flex:0 0 66.666%; }     /* テキスト2/3 */
.cb-icon { flex:0 0 33.333%; display:flex; align-items:center; justify-content:center;
  padding:8px; }                                         /* アイコン1/3（区切り線なし） */
.cb-icon img { max-width:100%; max-height:80px; height:auto; }
.cb-title { font-size:18px; letter-spacing:1px; }
.cb-sub { font-size:12px; margin-top:6px; opacity:.85; }

/* ===== 公式情報ページの広ボタン（画像配置可） ===== */
/* official-list=グループ縦積み（間隔広め）／oi-group=メイン＋サブを1かたまり（間隔狭め） */
.official-list { max-width:680px; margin:0 auto; display:flex; flex-direction:column; gap:30px; }
.oi-group { display:flex; flex-direction:column; gap:8px; }
.oi-subs { display:flex; flex-direction:column; gap:8px; }
.official-item { display:block; border:2px solid #ffe600; color:#ffe600; text-decoration:none;
  padding:16px 18px; text-align:left; }
.official-item:hover { background:#ffe600; color:#000; }
.official-item:hover .oi-url { color:#333; }
/* 画像付きボタン：テキスト左／画像右 の横並びサムネイル */
.official-item.has-img { display:flex; align-items:center; gap:14px; }
.official-item.has-img .oi-body { flex:1 1 auto; min-width:0; }
.oi-body { display:block; }
.oi-img { flex:0 0 auto; width:auto; max-width:500px; max-height:500px; height:auto;
  object-fit:contain; image-rendering:pixelated; }
.oi-label { display:block; font-size:17px; font-weight:normal; }
.oi-url { display:block; color:#7fb0ff; font-size:12px; word-break:break-all; margin-top:4px; }
/* ★txt由来のお役立ちリンク：注記・サブリンク・リンク無し項目 */
.oi-note { display:block; color:#ddd; font-size:12px; line-height:1.8; margin-top:6px; }
.official-item:hover .oi-note { color:#333; }
.official-item.oi-sub { margin-left:28px; padding:10px 14px; }
.official-item.oi-sub .oi-label { font-size:14px; font-weight:normal; }
.official-item.oi-plain { border-style:dashed; cursor:default; }
.official-item.oi-plain:hover { background:transparent; color:#ffe600; }

/* ===== 記事＝掲示板（sledpage_images.png 風・シンプル） ===== */
.article-page { background:#000; color:#fff; }
.board { max-width:840px; margin:0 auto; padding:18px 14px 40px; }
.board-title { font-size:21px; color:#ffe600; border-bottom:2px solid #ffe600;
  padding-bottom:6px; margin:6px 0 22px; }
.section-title { font-size:17px; color:#fff; border-left:5px solid #ffe600;
  padding:2px 0 2px 10px; margin:36px 0 12px; text-align:left; }
/* バックナンバーの区切り：page_02 のページタイトル（board-title）と同じ見た目．
   カード列幅に合わせて中央に置き，文字も中央寄せ（下線は board-title の border-bottom） */
.bn-divider { max-width:380px; margin:36px auto 24px; text-align:center; }

.thread { margin-bottom:24px; border:2px solid #888; }
.thread-bar { background:#fff; color:#000;
  font-size:16px; padding:6px 12px; border-bottom:2px solid #888; }

.post { padding:12px 14px; }
.post.reply { margin:0 14px; padding:12px 0 12px 24px; border-top:1px solid #777; }
.post-body { font-size:16px; line-height:1.8; color:#fff; }
.post-text { margin:0 0 10px; }

/* 埋め込み */
.embed { margin:12px 0; }
.embed img { max-width:100%; height:auto; border:1px solid #ccc; display:block; }
.embed-video video { max-width:100%; height:auto; display:block; border:1px solid #ccc; background:#000; }
.embed-src { font-size:12px; margin-top:3px; word-break:break-all; }
.embed-src a { color:#7fb0ff; }
.embed-yt a { position:relative; display:inline-block; }
.embed-yt .yt-play { position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
  background:rgba(0,0,0,.7); color:#fff; font-size:28px; padding:6px 16px; border-radius:8px; }
.embed-tweet .tweet-ph { border:2px dashed #1da1f2; background:#f0f8ff; color:#1da1f2;
  padding:18px; text-align:center; font-size:14px; }
.embed-tweet .tweet-bird { font-size:20px; margin-right:6px; }
.embed-link a { color:#1a4fd6; word-break:break-all; }
/* 内部リンク（→タイトル）：他記事への案内リンク */
.page-ref { margin:8px 0; }
.page-ref a { display:inline-block; color:#1a4fd6; text-decoration:none;
  border:1px solid #1a4fd6; border-radius:3px; padding:4px 12px; background:#eef2ff; }
.page-ref a:hover { background:#1a4fd6; color:#fff; }

/* ===== 変身イベント（あんぽんたんガキンチョ） ===== */
@keyframes rainbow {
  0%   { color:#ff2d2d; }
  16%  { color:#ff9a00; }
  33%  { color:#ffee00; }
  50%  { color:#39ff5a; }
  66%  { color:#27b3ff; }
  83%  { color:#c46bff; }
  100% { color:#ff2d2d; }
}
.haunted .index-title,
.haunted .toc-item h2,
.haunted .ref-item { animation:rainbow 2.4s linear infinite; }
.haunted .ref-item { border-color:currentColor; }
.haunted .index-title { text-shadow:2px 0 #f0f, -2px 0 #0ff; }

/* 予備動作：画面表示が一瞬崩れる演出（ノイズ突入前のワンクッション） */
.glitch-pre { animation:glitchpre .36s steps(2) both; }
@keyframes glitchpre {
  0%   { transform:translate(0,0) skewX(0deg);    filter:none; }
  20%  { transform:translate(-14px,0) skewX(9deg); filter:hue-rotate(90deg) saturate(3); }
  40%  { transform:translate(12px,0) skewX(-7deg); filter:contrast(2.4); }
  60%  { transform:translate(-8px,0) skewX(5deg);  filter:invert(1); }
  80%  { transform:translate(10px,0) skewX(-3deg); filter:hue-rotate(-70deg) saturate(4); }
  100% { transform:translate(0,0) skewX(0deg);    filter:none; }
}

/* 砂嵐（TVノイズ）と画面の揺れ */
#noise { position:fixed; inset:0; z-index:9999; opacity:.92; pointer-events:none; }
.glitching { animation:shake .07s steps(2) infinite; }
@keyframes shake {
  0%   { transform:translate(0,0); }
  25%  { transform:translate(-4px,2px); }
  50%  { transform:translate(3px,-3px); }
  75%  { transform:translate(-2px,-1px); }
  100% { transform:translate(2px,3px); }
}

/* ===== フッター ===== */
.site-footer { text-align:center; font-size:12px; padding:24px 0; color:#666; }
.article-page .site-footer a { color:#ffe600; }
.index-page .site-footer { color:#888; }
"""


# ------------------------------------------------------------------ 例外フラグ
# ファイル名に特定の記号を含む txt は「記事」にせず、専用の用途へ振り分ける。
#   †       … nobody.html 用の台本・素材。記事化しない。
#              ※本文への自動反映は未実装：台本の変更は build.py 内 NOBODY_TMPL へ手動反映する運用。
#   ★      … 参考ページ用。official.html の下部に「お役立ちリンク集」として自動反映。
#   ●      … キャンペーンページ用（ページ生成は未実装。記事化の除外のみ）。
#   ◆+数字 … 広告ページ用（同上）。`◆1` `◆2` のように数字と組み合わせる。
#              ※数字が続かない ◆（例:「◆木の後ろにいる男◆.txt」）は従来どおり記事になる。

def special_kind(name):
    if "†" in name:
        return "nobody"
    if "★" in name:
        return "reference"
    if "●" in name:
        return "campaign"
    if re.search(r"◆\d", name):
        return "ad"
    return None


# ------------------------------------------------------------------ 参考ページ（★txt）
def parse_reference_txt(text):
    """★付きテキスト（お役立ちリンク集）を解析する。
    形式：先頭の非空行＝ページ見出し（装飾の ★ や [[ ]] は除去）／
          `■ ラベル` で項目開始 → 直後のURLがメインリンク／
          2本目以降のURL行はサブリンク（URLの後ろの（…）等は説明文）／
          `＊…` とその他のテキスト行は注記として項目にぶら下げる。
          画像行（resource/… か 画像URL）は直前のリンク（メイン／サブ）の絵になる。"""
    heading = None
    items = []
    cur = None          # 現在の■項目
    cur_link = None     # 直近のリンク（メイン or サブ）．画像行はここに紐づける
    for raw in text.splitlines():
        line = raw.replace("　", " ").strip()
        if not line:
            continue
        if heading is None and not line.startswith("■"):
            heading = re.sub(r"[\[\]★]", "", line).strip()
            continue
        if line.startswith("■"):
            cur = {"label": line.lstrip("■").strip(), "url": "",
                   "notes": [], "subs": [], "image": "", "imgsize": None}
            items.append(cur)
            cur_link = cur        # 次に来る画像はまずメインリンクの絵とする
            continue
        if cur is None:
            continue
        # 画像行 → 直近のリンク（メイン or サブ）の絵として紐づける．
        # 判定：resource/・拡張子付き画像・gstatic等，または「URL＋サイズ指定」．
        # 拡張子の無い画像URLは，末尾に <300px> 等のサイズを付ければ画像として差し込める．
        core, size = split_size(line)
        if is_image(core) or (size and re.match(r"^https?://\S", core)):
            if cur_link is not None and not cur_link["image"]:
                cur_link["image"], cur_link["imgsize"] = core, size
            continue
        m = re.match(r"(https?://\S+)\s*(.*)$", line)
        if m:
            url, caption = m.group(1), m.group(2).strip().strip("()（）").strip()
            if not cur["url"]:
                cur["url"] = url
                cur_link = cur                       # 以降の画像はメインに紐づく
                if caption:
                    cur["notes"].append(caption)
            else:
                sub = {"url": url, "caption": caption, "image": "", "imgsize": None}
                cur["subs"].append(sub)
                cur_link = sub                       # 以降の画像はこのサブに紐づく
            continue
        if "サブページリンク" in line:      # 区切りの見出し行は表示しない
            continue
        cur["notes"].append(line.lstrip("＊*").strip())
    return heading, items


def render_reference_sections(paths):
    """★txt を official.html 用のセクションHTMLへ変換する。"""
    parts = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            heading, items = parse_reference_txt(f.read())
        # 1項目（■）＝メインリンク＋その配下のサブリンクを1グループにまとめ，
        # グループ間を大きめの余白で区切って見やすくする（横に詰まって見えないように）．
        groups = []
        for it in items:
            notes = "".join('<span class="oi-note">＊%s</span>' % html.escape(n)
                            for n in it["notes"])
            img_html = oi_image_html(it["image"], it["imgsize"])
            cls = "official-item" + (" has-img" if img_html else "")
            if it["url"]:
                body = ('<span class="oi-body"><span class="oi-label">■ %s</span>'
                        '<span class="oi-url">%s</span>%s</span>'
                        % (html.escape(it["label"]), html.escape(it["url"]), notes))
                main = ('<a class="%s" href="%s" target="_blank" rel="noopener">%s%s</a>'
                        % (cls, html.escape(it["url"]), body, img_html))
            else:
                body = ('<span class="oi-body"><span class="oi-label">■ %s</span>%s</span>'
                        % (html.escape(it["label"]), notes))
                main = '<div class="%s oi-plain">%s%s</div>' % (cls, body, img_html)
            subs = ""
            if it["subs"]:
                sub_parts = []
                for sub in it["subs"]:
                    s_img = oi_image_html(sub["image"], sub["imgsize"])
                    s_cls = "official-item oi-sub" + (" has-img" if s_img else "")
                    s_body = ('<span class="oi-body"><span class="oi-label">%s</span>'
                              '<span class="oi-url">%s</span></span>'
                              % (html.escape(sub["caption"] or sub["url"]),
                                 html.escape(sub["url"])))
                    sub_parts.append(
                        '<a class="%s" href="%s" target="_blank" rel="noopener">%s%s</a>'
                        % (s_cls, html.escape(sub["url"]), s_body, s_img))
                subs = '<div class="oi-subs">%s</div>' % "".join(sub_parts)
            groups.append('<div class="oi-group">%s%s</div>' % (main, subs))
        parts.append('<section><h2 class="index-section-h">― %s ―</h2>'
                     '<div class="official-list">%s</div></section>'
                     % (html.escape(heading or "お役立ちリンク"), "".join(groups)))
    return "".join(parts)


# ------------------------------------------------------------------ メイン

def slugify(stem, idx):
    return "page_%02d.html" % idx


def clear_dir(path):
    """site/ の中身だけを空にする。site/ 自体は消さない（ローカルサーバーや
    エクスプローラー等がフォルダを掴んでいて rmdir に失敗するのを避ける）。"""
    for name in os.listdir(path):
        p = os.path.join(path, name)
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
        except OSError as e:
            print("警告: %s を削除できません（%s）。上書きで続行します。" % (p, e))


def main():
    if os.path.isdir(OUT_DIR):
        clear_dir(OUT_DIR)
    else:
        os.makedirs(OUT_DIR)

    # リソース（画像等）を site/resource/ へコピー。ソース resource/ があればそれを使う。
    src_resource = os.path.join(SRC_DIR, "resource")
    dst_resource = os.path.join(OUT_DIR, "resource")
    if os.path.isdir(src_resource):
        shutil.copytree(src_resource, dst_resource, dirs_exist_ok=True)
    else:
        os.makedirs(dst_resource, exist_ok=True)

    # カスタムフォントを site/fonts/ にコピー
    fonts_dst = os.path.join(OUT_DIR, "fonts")
    os.makedirs(fonts_dst, exist_ok=True)
    for fn in ("DeterminationJP.ttf", "MonsterFriendFore.otf"):
        src = os.path.join(SRC_DIR, "CustomFont", fn)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(fonts_dst, fn))

    # 隠しイベント内ミニゲーム（ゼルダ風）を site/ へコピー
    mg = os.path.join(SRC_DIR, "minigame.js")
    if os.path.isfile(mg):
        shutil.copy2(mg, os.path.join(OUT_DIR, "minigame.js"))

    txt_files = sorted(glob.glob(os.path.join(SRC_DIR, "*.txt")))
    parsed = []
    specials = {"nobody": [], "reference": [], "campaign": [], "ad": []}
    page_no = 0
    for path in txt_files:
        stem = os.path.splitext(os.path.basename(path))[0]
        kind = special_kind(stem)
        if kind:                      # 例外フラグ付きは記事にしない（用途別に振り分け）
            specials[kind].append(path)
            continue
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # 1ファイルを【】区切りで複数ページに分割（【】が無ければ1ページ）
        for doc in split_documents(text):
            sections = parse(doc["text"])
            page_no += 1
            fname = slugify(stem, page_no)
            title = doc["title"] or article_title(sections, stem)
            blurb = article_blurb(sections)
            parsed.append({"fname": fname, "title": title, "blurb": blurb,
                           "featured": doc["featured"], "sections": sections})

    cards_all = [(p["fname"], p["title"], p["blurb"], p["featured"]) for p in parsed]   # バックナンバー用
    cards_new = [c for c in cards_all if c[3]]                          # ★新着のみ
    # 新着が1件も無いときは全件を新着扱いで表示し，インデックスを空にしない
    index_cards = cards_new if cards_new else [(f, t, b, True) for (f, t, b, _) in cards_all]

    # 内部リンク（→タイトル）の解決表を作る．記事レンダリングより前に埋めておく．
    PAGE_LINK_MAP.clear(); PAGE_TITLE_BY_FNAME.clear(); del PAGE_LINK_MISSES[:]
    for p in parsed:
        PAGE_TITLE_BY_FNAME[p["fname"]] = p["title"]
        if p["title"] and p["title"] not in PAGE_LINK_MAP:
            PAGE_LINK_MAP[p["title"]] = p["fname"]     # タイトル重複時は先勝ち

    # 記事ページ
    for p in parsed:
        html_out = render_article(p["sections"], p["title"], p["fname"])
        with open(os.path.join(OUT_DIR, p["fname"]), "w", encoding="utf-8") as f:
            f.write(html_out)

    # インデックス（新着＝★のみ。新着カードには右にバッジを表示）
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_index(index_cards))

    # バックナンバー（全記事。新着の記事だけ右にバッジを表示）
    bn_content = ('<section id="toc"><h2 class="board-title bn-divider">本編関連</h2>'
                  + render_cards(cards_all) + "</section>")
    with open(os.path.join(OUT_DIR, "backnumber.html"), "w", encoding="utf-8") as f:
        f.write(render_subpage("バックナンバー", bn_content, "backnumber.html"))

    # 公式情報：固定ボタン（REFERENCE_LINKS）があるときだけ見出し付きで掲載．
    # それに ★txt 由来の「お役立ちリンク集」を続ける（★txt に無いものは出さない）．
    of_fixed = ""
    if REFERENCE_LINKS:
        of_fixed = ('<section><h2 class="index-section-h">― 公式情報 ―</h2>'
                    '<div class="official-list">' + render_official_items() + "</div></section>")
    of_content = of_fixed + render_reference_sections(specials["reference"])
    with open(os.path.join(OUT_DIR, "official.html"), "w", encoding="utf-8") as f:
        f.write(render_subpage("公式情報", of_content, "official.html"))

    # CSS
    with open(os.path.join(OUT_DIR, "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS)

    # 特殊イベントの遷移先（「わすれられたもの」対話イベント）
    with open(os.path.join(OUT_DIR, "nobody.html"), "w", encoding="utf-8") as f:
        f.write(NOBODY_TMPL.replace("__GAMEKEY__", GAME_KEY))

    # 隠しミニゲームの直接アクセスページ（?key=GAME_KEY で起動）
    with open(os.path.join(OUT_DIR, "game.html"), "w", encoding="utf-8") as f:
        f.write(GAME_TMPL.replace("__GAMEKEY__", GAME_KEY))

    # 変身イベントの最後に遷移する動画ページ
    with open(os.path.join(OUT_DIR, "kurae.html"), "w", encoding="utf-8") as f:
        f.write(KURAE_TMPL)

    # resource フォルダ用 README
    with open(os.path.join(OUT_DIR, "resource", "README.txt"), "w", encoding="utf-8") as f:
        f.write("画像・GIF等のリソースをここに置き、本文では resource/ファイル名 で指定します。\n")

    print("生成完了: %d 記事 + index" % len(parsed))
    for p in parsed:
        print("  - %s  (%s)" % (p["fname"], p["title"]))
    kind_labels = {"nobody": "†nobody.html用素材（記事化しない）",
                   "reference": "★参考ページ→official.htmlへ反映",
                   "campaign": "●キャンペーン（ページ生成は未実装）",
                   "ad": "◆広告（ページ生成は未実装）"}
    for kind, paths in specials.items():
        for p in paths:
            print("  [%s] %s" % (kind_labels[kind], os.path.basename(p)))
    if PAGE_LINK_MISSES:              # 「→タイトル」で解決できなかった内部リンクを警告
        print("  [!] 解決できなかった内部リンク（→の後のタイトルが記事と一致しません）:")
        for key in dict.fromkeys(PAGE_LINK_MISSES):
            print("      → %s" % key)


if __name__ == "__main__":
    main()
