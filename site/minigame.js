//=============================================================================
// NobodyGame — 4色モノクロのゲームボーイ・ゼルダ風ローグライト（v1）
//   nobody.html の対話イベント中に window.NobodyGame.start() で起動する。
//   死亡(HP0) または「やめる(Esc)」で終了し，スコアを resolve して本編へ戻る。
//
//   v1 実装範囲：
//     - 4色描画 / ランダム生成マップ / 自機移動＆剣攻撃 / HP・ハート表示
//     - 全敵撃破で扉が開き，画面端から次スクリーンへスクロール（スコア加算）
//     - レベルアップ（体力/攻撃力/スピード/あざとさ を選択，必要EXP +5）
//     - 敵①(徘徊) ②(徘徊+射撃) ④(砲台) ⑦(逃走/10秒で消滅) と敵弾
//     - アイテム：ハート小 / おかね，ハイスコア保存(localStorage)
//     - スクリーン数による敵強化（HP:+1/10画面，攻撃:+1/15画面）
//   v2 予定：敵③⑤⑥ / 障害物(ファイアバー・氷・爆弾) / 星・ダイヤ・バリヤ / ショップ
//   v3 追加：敵スプライトのテスト導入（ENEMY_ANIM）／導入演出（白黒点滅→12分割ロード。
//            start({intro:false}) で省略可）／ゲームオーバー時「もう一回/もうお腹一杯」メニュー
//=============================================================================
(function () {
  "use strict";

  // ---- 定数 ---------------------------------------------------------------
  var TILE = 28, GW = 15, GH = 11;            // 1スクリーンのタイル数
  var HUD_H = 30;                             // 上部HUDの高さ(px)
  var VW = GW * TILE, VH = GH * TILE + HUD_H; // 論理解像度
  var COL = { bg: "#0e0e0e", dark: "#4a4a4a", light: "#9a9a9a", white: "#e6e6e6" };
  var HI_KEY = "nobody_game_hi";

  // ---- 主人公スプライト ---------------------------------------------------
  // Sprite_sheet.png は 16x16 のマス割り。右向きは左向きの左右反転で描く。
  // ※ コマの割り当ては推測を含む。ズレたら下の座標[gx,gy]を差し替えるだけでOK。
  var SS = 16;                                  // シート1マスの元サイズ(px)
  var SHEET = new Image(); var sheetReady = false;
  SHEET.onload = function () { sheetReady = true; };
  SHEET.src = "resource/Sprite_sheet.png";
  var ANIM = {
    down:  { idle: [0, 0], walk: [[0, 0], [0, 1]] },   // 正面（顔あり）
    up:    { idle: [3, 0], walk: [[3, 0], [3, 1]] },   // 背面（顔なし）
    left:  { idle: [2, 1], walk: [[2, 0], [2, 1]] }    // 横向き（right は反転）
  };
  var ATK_BODY  = { down: [3, 7], up: [2, 3], left: [0, 4] };  // 攻撃時の全身ポーズ
  var ATK_SWORD = { down: [0, 7], up: [3, 6], left: [1, 4] };  // 前方に重ねる剣

  // ---- 敵スプライト（テスト導入）------------------------------------------
  // Sprite_sheet.png 右側の敵コマ [gx,gy]。2コマで足踏みアニメ。
  // 割り当ては仮（見た目のテスト用）。null にするとそのタイプは従来のコード描画に戻る。
  var ENEMY_ANIM = {
    walk:      [[5, 0], [5, 1]],   // ① 徘徊 ＝ インベーダー風（淡色）
    walkshoot: [[6, 0], [6, 1]],   // ② 徘徊+射撃 ＝ ツノつきのやつ
    shield:    [[7, 0], [7, 1]],   // ⑥ 盾持ち ＝ サングラスのロボ
    turret:    [[5, 2], [5, 3]],   // ④ 砲台 ＝ 歯車
    snake:     [[6, 2], [6, 3]],   // ⑤ 蛇（頭） ＝ ニコニコのトゲ玉
    jump:      [[7, 2], [7, 3]],   // ③ ジャンプ ＝ 無地のトゲ玉
    flee:      null                // ⑦ 逃走 ＝ スプライト未定（コード描画のまま）
  };

  // ---- 入力 ---------------------------------------------------------------
  var keys = {}, pressed = {};
  function onKeyDown(e) {
    var k = norm(e.key);
    if (k) { if (!keys[k]) pressed[k] = true; keys[k] = true; e.preventDefault(); }
  }
  function onKeyUp(e) { var k = norm(e.key); if (k) { keys[k] = false; e.preventDefault(); } }
  function norm(key) {
    switch (key) {
      case "ArrowUp": case "w": case "W": return "up";
      case "ArrowDown": case "s": case "S": return "down";
      case "ArrowLeft": case "a": case "A": return "left";
      case "ArrowRight": case "d": case "D": return "right";
      case "z": case "Z": case "j": case "J": case " ": return "atk";
      case "x": case "X": return "wand";
      case "Enter": return "enter";
      case "Escape": case "q": case "Q": return "quit";
      default: return null;
    }
  }
  function consume(k) { if (pressed[k]) { pressed[k] = false; return true; } return false; }

  // ---- 乱数 ---------------------------------------------------------------
  function ri(a, b) { return a + Math.floor(Math.random() * (b - a + 1)); }
  function chance(p) { return Math.random() < p; }
  function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

  // ---- ゲーム状態 ---------------------------------------------------------
  var G = null;

  // opts.intro=false で導入演出（白黒点滅→12分割ロード）を省略できる。既定は演出あり。
  function start(opts) {
    var showIntro = !(opts && opts.intro === false);
    return new Promise(function (resolve) {
      var canvas = document.createElement("canvas");
      canvas.width = VW; canvas.height = VH; canvas.id = "mg-canvas";
      canvas.style.cssText =
        "position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:8;" +
        "image-rendering:pixelated;background:#000;max-width:96vw;max-height:92vh;" +
        "width:auto;height:88vh;box-shadow:0 0 0 3px #333,0 0 40px #000;";
      document.body.appendChild(canvas);
      var ctx = canvas.getContext("2d");
      ctx.imageSmoothingEnabled = false;

      window.addEventListener("keydown", onKeyDown, { passive: false });
      window.addEventListener("keyup", onKeyUp, { passive: false });

      G = newGame(resolve, canvas, ctx, showIntro);
      G.raf = requestAnimationFrame(loop);
    });
  }

  function finish() {
    cancelAnimationFrame(G.raf);
    window.removeEventListener("keydown", onKeyDown);
    window.removeEventListener("keyup", onKeyUp);
    if (G.canvas && G.canvas.parentNode) G.canvas.parentNode.removeChild(G.canvas);
    var score = G.score, cb = G.resolve;
    G = null;
    cb(score);
  }

  function newGame(resolve, canvas, ctx, showIntro) {
    var g = {
      resolve: resolve, canvas: canvas, ctx: ctx, raf: 0,
      state: showIntro ? "intro" : "play",   // intro / play / levelup / over / trans
      introT: 0,
      last: performance.now(),
      // プレイヤー
      p: {
        x: (GW >> 1) * TILE + 3, y: (GH >> 1) * TILE + 3, w: TILE - 6, h: TILE - 6,
        dir: "down", hp: 4, maxhp: 4, atk: 1, spd: 1.7, azatosa: 0,
        lvl: 1, xp: 0, need: 10, iframe: 0, atkTimer: 0, animT: 0, moving: false,
        star: 0, barrier: 0, drill: 0, wand: false, ammo: 0
      },
      money: 0, score: 0, screen: 1,
      hi: parseInt(localStorage.getItem(HI_KEY), 10) || 0,
      grid: null, enemies: [], bullets: [], pbullets: [], drops: [], fx: [],
      obstacles: [], ice: {}, drillHit: { key: null, n: 0 },
      shop: null, isShop: false,
      doorsOpen: false, trans: null, levelQueue: 0, menuSel: 0,
      overSel: 0, died: false
    };
    buildRoom(g, null);
    return g;
  }

  // ---- マップ生成 ---------------------------------------------------------
  // grid[y][x]: 0=床 1=ブロック。外周は壁（扉位置のみ後で開く）。
  function buildRoom(g, entryDir) {
    var grid = [];
    for (var y = 0; y < GH; y++) {
      grid[y] = [];
      for (var x = 0; x < GW; x++) {
        grid[y][x] = (x === 0 || y === 0 || x === GW - 1 || y === GH - 1) ? 1 : 0;
      }
    }
    // 内部にランダムなブロック塊を置く（中央付近と入口は空ける）
    var cx = GW >> 1, cy = GH >> 1;
    var clusters = ri(3, 6);
    for (var c = 0; c < clusters; c++) {
      var bx = ri(2, GW - 3), by = ri(2, GH - 3);
      var bw = ri(1, 2), bh = ri(1, 2);
      for (var yy = by; yy < by + bh && yy < GH - 1; yy++)
        for (var xx = bx; xx < bx + bw && xx < GW - 1; xx++) {
          if (Math.abs(xx - cx) <= 1 && Math.abs(yy - cy) <= 1) continue; // 中央は空ける
          grid[yy][xx] = 1;
        }
    }
    g.grid = grid;

    // このスクリーンはショップか？（最初と直前がショップのときは除く）
    g.isShop = (g.screen > 2 && !g.wasShop && chance(0.16));
    g.wasShop = g.isShop;

    // プレイヤーの配置（入ってきた方向の反対側の端から）
    var p = g.p;
    if (entryDir === "right") { p.x = (GW - 2) * TILE + 3; p.y = cy * TILE + 3; }
    else if (entryDir === "left") { p.x = 1 * TILE + 3; p.y = cy * TILE + 3; }
    else if (entryDir === "down") { p.x = cx * TILE + 3; p.y = (GH - 2) * TILE + 3; }
    else if (entryDir === "up") { p.x = cx * TILE + 3; p.y = 1 * TILE + 3; }
    else { p.x = cx * TILE + 3; p.y = cy * TILE + 3; }
    clearAround(grid, tileOf(p.x + p.w / 2), tileOf(p.y + p.h / 2));

    // 各種リセット
    g.enemies = []; g.bullets = []; g.pbullets = []; g.drops = []; g.fx = [];
    g.obstacles = []; g.ice = {}; g.drillHit = { key: null, n: 0 }; g.shop = null;

    if (g.isShop) {
      // ショップ画面：敵なし，扉は開放，ネズミ店員を配置
      for (var sc = 0; sc < GW; sc++) grid[cy][sc] = 0;   // 通路確保
      g.shop = makeShop(g, cx);
      g.doorsOpen = true;
    } else {
      spawnEnemies(g);
      spawnObstacles(g);
      scatterItems(g);
      g.doorsOpen = (g.enemies.length === 0);
    }
  }

  function clearAround(grid, tx, ty) {
    for (var dy = -1; dy <= 1; dy++)
      for (var dx = -1; dx <= 1; dx++) {
        var x = tx + dx, y = ty + dy;
        if (x > 0 && y > 0 && x < GW - 1 && y < GH - 1) grid[y][x] = 0;
      }
  }

  function spawnEnemies(g) {
    var n = Math.min(2 + Math.floor(g.screen / 3), 6);
    var types = ["walk", "walkshoot", "turret", "jump"];
    if (g.screen >= 15) { types.push("snake", "shield"); }  // ⑤⑥ は15画面から
    if (g.screen % 5 === 0) types.push("flee");             // ⑦ は5の倍数スクリーン
    var hpBonus = Math.floor(g.screen / 10);               // 10画面ごとにHP+1
    var atkBonus = Math.floor(g.screen / 15);              // 15画面ごとに攻撃+1
    g.roomHasShooter = false;
    for (var i = 0; i < n; i++) {
      var t = pick(types);
      if (t === "walkshoot" || t === "turret") g.roomHasShooter = true;
      var pos = freeTile(g, 3);
      if (!pos) continue;
      g.enemies.push(makeEnemy(t, pos.x, pos.y, hpBonus, atkBonus));
    }
  }

  function makeEnemy(t, tx, ty, hpB, atkB) {
    var base = {
      walk:      { hp: 2, xp: 1 },
      walkshoot: { hp: 2, xp: 1 },
      turret:    { hp: 1, xp: 1 },
      flee:      { hp: 2, xp: 5 },
      jump:      { hp: 5, xp: 2 },   // ③ 動かずジャンプ踏みつけ（障害物を越える）
      snake:     { hp: 2, xp: 2 },   // ⑤ 蛇・突撃
      shield:    { hp: 3, xp: 1 }    // ⑥ 進行方向からの攻撃は無効
    }[t];
    var e = {
      type: t, x: tx * TILE + 3, y: ty * TILE + 3, w: TILE - 6, h: TILE - 6,
      hp: base.hp + hpB, xp: base.xp, atk: 1 + atkB,
      dir: pick(["up", "down", "left", "right"]),
      t: 0, shootT: ri(60, 140), jumpT: ri(60, 140), z: 0, jumping: null,
      life: 0, hurt: 0, body: []
    };
    if (t === "snake") { for (var s = 0; s < 3; s++) e.body.push({ x: e.x, y: e.y }); }
    return e;
  }

  // ---- 障害物・アイテム生成 ----------------------------------------------
  function spawnObstacles(g) {
    // ファイアバー（画面が進むほど出やすい）
    if (chance(0.30 + Math.min(0.3, g.screen * 0.01))) {
      var fp = freeTile(g, 3);
      if (fp) g.obstacles.push({ kind: "fire", px: fp.x * TILE + TILE / 2, py: fp.y * TILE + TILE / 2,
        len: TILE * ri(2, 3), ang: Math.random() * 6.28, spd: (chance(0.5) ? 1 : -1) * 0.045 });
    }
    // 爆弾
    var nb = ri(0, 2);
    for (var b = 0; b < nb; b++) {
      var bp = freeTile(g, 2);
      if (bp) g.obstacles.push({ kind: "bomb", x: bp.x * TILE + 3, y: bp.y * TILE + 3, w: TILE - 6, h: TILE - 6, fuse: -1 });
    }
    // 氷（弾を撃つ敵がいる部屋のみ・弾を防ぐ）
    if (g.roomHasShooter) {
      var ni = ri(1, 3);
      for (var k = 0; k < ni; k++) {
        var ip = freeTile(g, 2);
        if (ip) { g.grid[ip.y][ip.x] = 2; g.ice[ip.x + "," + ip.y] = 3; }
      }
    }
  }
  function scatterItems(g) {
    if (chance(0.55)) dropAtFree(g, "coin");
    if (chance(0.35)) dropAtFree(g, "heart");
    if (chance(0.08)) dropAtFree(g, "star");
  }
  function dropAtFree(g, kind) {
    var pos = freeTile(g, 2);
    if (pos) g.drops.push(makeDrop(kind, pos.x * TILE, pos.y * TILE));
  }

  // ---- ショップ -----------------------------------------------------------
  // 各商品：id / 名前 / 基本価格base / 誤差d（価格は base±d でランダム）
  var SHOP_CATALOG = [
    { id: "heart",   name: "ハート小",  base: 5,  d: 2 },
    { id: "bigheart",name: "ハート大",  base: 10, d: 5 },
    { id: "star",    name: "ほし",      base: 7,  d: 5 },
    { id: "diamond", name: "ダイヤ",    base: 30, d: 10 },
    { id: "barrier", name: "バリヤ",    base: 30, d: 0 },
    { id: "drill",   name: "ドリル",    base: 10, d: 5 },
    { id: "wand",    name: "つえ",      base: 15, d: 7 }
  ];
  function makeShop(g, cx) {
    // 4品をランダムに選び，価格を確定（あざとさ割引は購入時に動的計算）
    var pool = SHOP_CATALOG.slice(), items = [];
    for (var i = 0; i < 4 && pool.length; i++) {
      var it = pool.splice(Math.floor(Math.random() * pool.length), 1)[0];
      items.push({ id: it.id, name: it.name, price: Math.max(1, ri(it.base - it.d, it.base + it.d)) });
    }
    return {
      sel: 0, items: items,
      keeper: { x: cx * TILE + 3, y: 1 * TILE + 3, w: TILE - 6, h: TILE - 6 }
    };
  }
  function discounted(g, price) {
    var off = Math.min(0.9, g.p.azatosa * 0.1);       // あざとさ1につき10%オフ
    return Math.max(1, Math.ceil(price * (1 - off)));
  }

  function freeTile(g, minDistFromPlayer) {
    var pt = { x: tileOf(g.p.x + g.p.w / 2), y: tileOf(g.p.y + g.p.h / 2) };
    for (var tries = 0; tries < 60; tries++) {
      var tx = ri(1, GW - 2), ty = ri(1, GH - 2);
      if (g.grid[ty][tx] !== 0) continue;
      if (Math.abs(tx - pt.x) + Math.abs(ty - pt.y) < minDistFromPlayer) continue;
      return { x: tx, y: ty };
    }
    return null;
  }

  function tileOf(px) { return Math.floor(px / TILE); }

  // ---- 当たり判定 ---------------------------------------------------------
  function blockAt(g, px, py) {
    var tx = tileOf(px), ty = tileOf(py);
    if (tx < 0 || ty < 0 || tx >= GW || ty >= GH) return true;
    return g.grid[ty][tx] !== 0;      // 1=ブロック 2=氷 はどちらも通れない
  }
  // AABBが壁に当たらない移動（軸ごとに解決）
  function moveEntity(g, e, dx, dy, ignoreBlocks) {
    if (dx !== 0) {
      var nx = e.x + dx;
      if (ignoreBlocks || (!blockAt(g, dx > 0 ? nx + e.w : nx, e.y) &&
        !blockAt(g, dx > 0 ? nx + e.w : nx, e.y + e.h - 1))) e.x = nx;
    }
    if (dy !== 0) {
      var ny = e.y + dy;
      if (ignoreBlocks || (!blockAt(g, e.x, dy > 0 ? ny + e.h : ny) &&
        !blockAt(g, e.x + e.w - 1, dy > 0 ? ny + e.h : ny))) e.y = ny;
    }
  }
  function overlap(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  }

  // ---- メインループ -------------------------------------------------------
  function loop() {
    var now = performance.now();
    var dt = Math.min(2.5, (now - G.last) / 16.6667);   // 1.0 = 60fps相当
    G.last = now;

    if (G.state === "intro") { updateIntro(dt); }
    else if (G.state === "play") { updatePlay(dt); }
    else if (G.state === "levelup") { updateLevelup(); }
    else if (G.state === "shop") { updateShop(); }
    else if (G.state === "trans") { updateTrans(dt); }
    else if (G.state === "over") { updateOver(); }

    if (!G) return;                 // updateOver 内の finish() でゲーム破棄済みなら描かない
    render();
    // 押下エッジは毎フレーム消費後にクリア
    pressed = {};
    if (G) G.raf = requestAnimationFrame(loop);
  }

  // ---- 導入演出 -------------------------------------------------------------
  // 画面が白黒に数回点滅したあと，ATARI風に12分割されたウィンドウが上から
  // 1列ずつ読み込まれてフィールドが現れる。Enter/Zでスキップ可。
  var INTRO_FLICK = 42;                        // 白黒点滅（6tickごとに反転×7）
  var INTRO_STRIP = 6;                         // 1列の読み込みにかかるtick
  var INTRO_ROWS = 12;
  var INTRO_TOTAL = INTRO_FLICK + INTRO_STRIP * INTRO_ROWS;
  function updateIntro(dt) {
    G.introT += dt;
    if (consume("enter") || consume("atk")) G.introT = INTRO_TOTAL;
    if (G.introT >= INTRO_TOTAL) { G.state = "play"; G.last = performance.now(); }
  }
  // 通常描画のあとに重ねるオーバーレイとして描く
  function drawIntro(ctx) {
    var t = G.introT;
    if (t < INTRO_FLICK) {                     // 白黒の点滅（HUDごと覆う）
      ctx.fillStyle = (Math.floor(t / 6) % 2 === 0) ? COL.white : "#000";
      ctx.fillRect(0, 0, VW, VH);
      return;
    }
    // 12分割：まだ読み込まれていない列を黒で覆う（上から順に現れる）
    var shown = Math.floor((t - INTRO_FLICK) / INTRO_STRIP);
    var sh = Math.ceil(GH * TILE / INTRO_ROWS);
    ctx.save(); ctx.translate(0, HUD_H);
    ctx.fillStyle = "#000";
    for (var i = shown; i < INTRO_ROWS; i++) ctx.fillRect(0, i * sh, VW, sh);
    if (shown < INTRO_ROWS && Math.floor(t / 2) % 2 === 0) {   // 読み込み中の列
      ctx.fillStyle = COL.white; ctx.fillRect(0, shown * sh, VW, 2);
    }
    ctx.restore();
  }

  // ---- プレイ更新 ---------------------------------------------------------
  function updatePlay(dt) {
    var p = G.p;
    if (consume("quit")) { endGame(); return; }

    // 移動
    var dx = 0, dy = 0;
    if (keys.left) { dx = -1; p.dir = "left"; }
    else if (keys.right) { dx = 1; p.dir = "right"; }
    if (keys.up) { dy = -1; p.dir = "up"; }
    else if (keys.down) { dy = 1; p.dir = "down"; }
    if (dx && dy) { dx *= 0.7071; dy *= 0.7071; }
    p.moving = false;
    if (p.atkTimer <= 0) {                    // 攻撃中は足を止める
      moveEntity(G, p, dx * p.spd * dt, 0, false);
      moveEntity(G, p, 0, dy * p.spd * dt, false);
      p.moving = !!(dx || dy);
    }
    if (p.moving) p.animT += dt; else p.animT = 0;

    // ショップを開く（店員のそばで Z/Enter）
    if (G.isShop && G.shop) {
      var kp = G.shop.keeper;
      var near = Math.abs((p.x + p.w / 2) - (kp.x + kp.w / 2)) < TILE * 1.4 &&
                 Math.abs((p.y + p.h / 2) - (kp.y + kp.h / 2)) < TILE * 1.6;
      if (near && (consume("atk") || consume("enter"))) { G.state = "shop"; return; }
    }

    drillUpdate(dt, dx, dy);                   // ドリルで地形ブロックを掘る

    // 攻撃・杖
    if (p.atkTimer > 0) p.atkTimer -= dt;
    if (consume("atk") && p.atkTimer <= 0) { p.atkTimer = 12; doAttack(); }
    if (consume("wand") && p.wand && p.ammo > 0) { p.ammo--; fireWand(p); }
    if (p.iframe > 0) p.iframe -= dt;
    if (p.star > 0) p.star -= dt;

    for (var i = G.enemies.length - 1; i >= 0; i--) updateEnemy(G.enemies[i], dt, i);
    updateObstacles(dt);
    updateBullets(dt);
    updatePBullets(dt);

    // ドロップ回収
    for (var d = G.drops.length - 1; d >= 0; d--) {
      if (overlap(G.drops[d], p)) { collect(G.drops[d]); G.drops.splice(d, 1); }
    }
    // エフェクト寿命
    for (var f = G.fx.length - 1; f >= 0; f--) { G.fx[f].t -= dt; if (G.fx[f].t <= 0) G.fx.splice(f, 1); }

    if (!G.doorsOpen && G.enemies.length === 0) { G.doorsOpen = true; openDoors(G); }
    if (G.doorsOpen) checkDoorExit();

    if (G.levelQueue > 0 && p.atkTimer <= 0) { G.state = "levelup"; G.menuSel = 0; }
    if (p.hp <= 0) toGameOver();
  }

  function opposite(d) { return d === "up" ? "down" : d === "down" ? "up" : d === "left" ? "right" : "left"; }
  function shieldBlocks(e, atkDir) { return e.type === "shield" && opposite(atkDir) === e.dir; }

  // ---- 敵弾 / 自弾 --------------------------------------------------------
  function updateBullets(dt) {
    var p = G.p;
    for (var b = G.bullets.length - 1; b >= 0; b--) {
      var bl = G.bullets[b];
      bl.x += bl.vx * dt; bl.y += bl.vy * dt; bl.t += dt;
      var tx = tileOf(bl.x + 3), ty = tileOf(bl.y + 3);
      if (tx < 0 || ty < 0 || tx >= GW || ty >= GH || bl.t > 240) { G.bullets.splice(b, 1); continue; }
      var gv = G.grid[ty][tx];
      if (gv === 2) { hitIce(tx, ty); G.bullets.splice(b, 1); continue; }   // 氷が弾を防ぐ
      if (gv === 1) { G.bullets.splice(b, 1); continue; }
      if (hitBombByPoint(bl.x + 3, bl.y + 3)) { G.bullets.splice(b, 1); continue; }
      if (overlap({ x: bl.x, y: bl.y, w: 6, h: 6 }, p)) {
        if (p.star <= 0 && p.iframe <= 0 && p.barrier <= 0) hurtPlayer(bl.dmg);
        G.bullets.splice(b, 1);
      }
    }
  }
  function fireWand(p) {
    var v = dirVec(p.dir);
    G.pbullets.push({ x: p.x + p.w / 2 - 3, y: p.y + p.h / 2 - 3, vx: v.x * 3.4, vy: v.y * 3.4, dir: p.dir, dmg: 3, t: 0 });
  }
  function updatePBullets(dt) {
    for (var pb = G.pbullets.length - 1; pb >= 0; pb--) {
      var wb = G.pbullets[pb];
      wb.x += wb.vx * dt; wb.y += wb.vy * dt; wb.t += dt;
      var tx = tileOf(wb.x + 3), ty = tileOf(wb.y + 3);
      if (tx < 0 || ty < 0 || tx >= GW || ty >= GH || wb.t > 200) { G.pbullets.splice(pb, 1); continue; }
      if (G.grid[ty][tx] !== 0) { G.pbullets.splice(pb, 1); continue; }
      if (hitBombByPoint(wb.x + 3, wb.y + 3)) { G.pbullets.splice(pb, 1); continue; }
      var hit = false;
      for (var ei = G.enemies.length - 1; ei >= 0; ei--) {
        if (overlap({ x: wb.x, y: wb.y, w: 6, h: 6 }, G.enemies[ei])) {
          if (!shieldBlocks(G.enemies[ei], wb.dir)) damageEnemy(ei, wb.dmg);
          hit = true; break;
        }
      }
      if (hit) G.pbullets.splice(pb, 1);
    }
  }

  // ---- 氷・爆弾 -----------------------------------------------------------
  function hitIce(tx, ty) {
    var key = tx + "," + ty;
    if (G.ice[key] == null) { G.grid[ty][tx] = 0; return; }
    G.ice[key]--;
    if (G.ice[key] <= 0) { G.grid[ty][tx] = 0; delete G.ice[key]; }
  }
  function hitBombByPoint(px, py) {
    for (var i = 0; i < G.obstacles.length; i++) {
      var o = G.obstacles[i];
      if (o.kind === "bomb" && o.fuse < 0 &&
        px >= o.x && px <= o.x + o.w && py >= o.y && py <= o.y + o.h) { o.fuse = 80; return true; }
    }
    return false;
  }
  function explodeBomb(o, idx) {
    var cxp = o.x + o.w / 2, cyp = o.y + o.h / 2, R = TILE * 3.4;
    G.fx.push({ kind: "blast", x: cxp, y: cyp, r: R, t: 26 });
    for (var i = G.enemies.length - 1; i >= 0; i--) {
      var e = G.enemies[i];
      if (Math.hypot(e.x + e.w / 2 - cxp, e.y + e.h / 2 - cyp) < R) damageEnemy(i, 3);
    }
    var p = G.p;
    if (p.star <= 0 && p.iframe <= 0 &&
      Math.hypot(p.x + p.w / 2 - cxp, p.y + p.h / 2 - cyp) < R) hurtPlayer(1);
    G.obstacles.splice(idx, 1);
  }
  function updateObstacles(dt) {
    var p = G.p;
    for (var i = G.obstacles.length - 1; i >= 0; i--) {
      var o = G.obstacles[i];
      if (o.kind === "fire") {
        o.ang += o.spd * dt;
        for (var r = TILE * 0.5; r <= o.len; r += TILE * 0.5) {
          var bx = o.px + Math.cos(o.ang) * r, by = o.py + Math.sin(o.ang) * r;
          if (bx > p.x && bx < p.x + p.w && by > p.y && by < p.y + p.h) {
            if (p.star > 0) { G.fx.push({ kind: "pop", x: o.px - TILE / 2, y: o.py - TILE / 2, t: 14 }); gainXP(3); G.score += 20; G.obstacles.splice(i, 1); }
            else if (p.iframe <= 0) hurtPlayer(1);
            break;
          }
        }
      } else if (o.kind === "bomb") {
        if (o.fuse >= 0) { o.fuse -= dt; if (o.fuse <= 0) { explodeBomb(o, i); continue; } }
        // 剣で叩いても起爆
        if (p.atkTimer > 6 && overlap(swordRect(p), o)) o.fuse = 80;
      }
    }
  }

  // ---- ドリル -------------------------------------------------------------
  function drillUpdate(dt, dx, dy) {
    var p = G.p;
    if (p.drill <= 0 || !(dx || dy)) { G.drillHit.key = null; G.drillHit.n = 0; return; }
    var ft = frontBlockTile(p);
    if (!ft || G.grid[ft.y][ft.x] !== 1) { G.drillHit.key = null; G.drillHit.n = 0; return; }
    var key = ft.x + "," + ft.y;
    if (G.drillHit.key === key) G.drillHit.n += dt; else { G.drillHit.key = key; G.drillHit.n = 0; }
    if (G.drillHit.n >= 40) {                  // 押し当て続けて破壊（=3回ぶつかる相当）
      G.grid[ft.y][ft.x] = 0; p.drill--;
      G.fx.push({ kind: "pop", x: ft.x * TILE, y: ft.y * TILE, t: 12 });
      G.drillHit.key = null; G.drillHit.n = 0;
    }
  }
  function frontBlockTile(p) {
    var tx = tileOf(p.x + p.w / 2), ty = tileOf(p.y + p.h / 2);
    if (p.dir === "left") tx--; else if (p.dir === "right") tx++;
    else if (p.dir === "up") ty--; else ty++;
    if (tx < 1 || ty < 1 || tx >= GW - 1 || ty >= GH - 1) return null;   // 外周は壊せない
    return { x: tx, y: ty };
  }

  function doAttack() {
    var p = G.p, r = swordRect(p);
    G.fx.push({ kind: "slash", rect: r, dir: p.dir, t: 12 });
    for (var i = G.enemies.length - 1; i >= 0; i--) {
      var e = G.enemies[i];
      if (!overlap(r, e)) continue;
      if (shieldBlocks(e, p.dir)) { G.fx.push({ kind: "pop", x: e.x, y: e.y, t: 8 }); continue; }  // ⑥ 前方は無効
      damageEnemy(i, p.atk);
    }
    // 敵弾を剣で消せる（気持ちよさ用）
    for (var b = G.bullets.length - 1; b >= 0; b--) {
      var bl = G.bullets[b];
      if (overlap(r, { x: bl.x, y: bl.y, w: 6, h: 6 })) G.bullets.splice(b, 1);
    }
  }
  function swordRect(p) {
    var reach = TILE - 4;
    if (p.dir === "left")  return { x: p.x - reach, y: p.y - 2, w: reach, h: p.h + 4 };
    if (p.dir === "right") return { x: p.x + p.w, y: p.y - 2, w: reach, h: p.h + 4 };
    if (p.dir === "up")    return { x: p.x - 2, y: p.y - reach, w: p.w + 4, h: reach };
    return { x: p.x - 2, y: p.y + p.h, w: p.w + 4, h: reach };
  }

  function damageEnemy(i, dmg) {
    var e = G.enemies[i];
    e.hp -= dmg; e.hurt = 8;
    // ノックバック
    var p = G.p;
    if (p.dir === "left") e.x -= 6; else if (p.dir === "right") e.x += 6;
    else if (p.dir === "up") e.y -= 6; else e.y += 6;
    if (e.hp <= 0) killEnemy(i);
  }
  function killEnemy(i) {
    var e = G.enemies[i];
    G.enemies.splice(i, 1);
    gainXP(e.xp);
    G.score += 10 + e.xp * 5;
    G.fx.push({ kind: "pop", x: e.x, y: e.y, t: 14 });
    // ドロップ
    if (chance(0.30)) G.drops.push(makeDrop("coin", e.x, e.y));
    else if (chance(0.06)) G.drops.push(makeDrop("bigheart", e.x, e.y));
    else if (chance(0.16)) G.drops.push(makeDrop("heart", e.x, e.y));
  }

  function gainXP(n) {
    var p = G.p; p.xp += n;
    while (p.xp >= p.need) { p.xp -= p.need; p.lvl++; p.need += 5; G.levelQueue++; }
  }

  function makeDrop(kind, x, y) { return { kind: kind, x: x + 2, y: y + 2, w: TILE - 10, h: TILE - 10, t: 0 }; }
  function collect(dp) {
    var p = G.p;
    if (dp.kind === "coin") { G.money += ri(1, 3); G.score += 5; }
    else if (dp.kind === "heart") { p.hp = Math.min(p.maxhp, p.hp + 1); }
    else if (dp.kind === "bigheart") { p.hp = Math.min(p.maxhp, p.hp + 3); }
    else if (dp.kind === "star") { p.star = 420; }   // 7秒無敵
  }

  function hurtPlayer(dmg) {
    var p = G.p;
    if (p.iframe > 0) return;
    p.hp -= dmg; p.iframe = 60;                 // 約1秒無敵
    G.fx.push({ kind: "hurt", t: 10 });
  }

  // ---- 敵AI ---------------------------------------------------------------
  function updateEnemy(e, dt, idx) {
    var p = G.p;
    e.t += dt; if (e.hurt > 0) e.hurt -= dt;
    if (e.type === "walk" || e.type === "walkshoot") {
      if (e.t % 90 < dt) e.dir = pick(["up", "down", "left", "right"]);
      var v = dirVec(e.dir), ox = e.x, oy = e.y;
      moveEntity(G, e, v.x * 0.7 * dt, v.y * 0.7 * dt, false);
      if (e.x === ox && e.y === oy) e.dir = pick(["up", "down", "left", "right"]);
      if (e.type === "walkshoot") {
        e.shootT -= dt;
        if (e.shootT <= 0) { e.shootT = ri(90, 160); shoot(e, dirVec(e.dir)); }
      }
    } else if (e.type === "turret") {
      e.shootT -= dt;
      if (e.shootT <= 0) { e.shootT = ri(80, 130); shootAt(e, p); }
    } else if (e.type === "flee") {
      e.life += dt;
      var away = { x: e.x - p.x, y: e.y - p.y }, m = Math.hypot(away.x, away.y) || 1;
      moveEntity(G, e, (away.x / m) * 1.1 * dt, (away.y / m) * 1.1 * dt, false);
      if (e.life > 600) { G.fx.push({ kind: "pop", x: e.x, y: e.y, t: 12 }); G.enemies.splice(idx, 1); return; }
    } else if (e.type === "jump") {
      // ③ 動かず，ためてから自機の位置へジャンプ（障害物を越える）
      if (e.jumping) {
        e.jumping.t += dt; var pr = e.jumping.t / e.jumping.dur;
        e.x = e.jumping.sx + (e.jumping.tx - e.jumping.sx) * pr;
        e.y = e.jumping.sy + (e.jumping.ty - e.jumping.sy) * pr;
        e.z = Math.sin(pr * Math.PI) * 16;
        if (pr >= 1) { e.z = 0; e.jumping = null; e.jumpT = ri(70, 130); }
      } else {
        e.jumpT -= dt;
        if (e.jumpT <= 0) {
          e.jumping = { sx: e.x, sy: e.y, tx: clampX(p.x), ty: clampY(p.y), t: 0, dur: 26 };
        }
      }
    } else if (e.type === "snake") {
      // ⑤ 高速で自機へ突撃．体は軌跡が追従
      var to = { x: (p.x - e.x), y: (p.y - e.y) }, mm = Math.hypot(to.x, to.y) || 1;
      moveEntity(G, e, (to.x / mm) * 1.9 * dt, (to.y / mm) * 1.9 * dt, false);
      if (!e.body) e.body = [];
      e.body.unshift({ x: e.x, y: e.y });
      while (e.body.length > 3 * 6) e.body.pop();
    } else if (e.type === "shield") {
      // ⑥ 低速で徘徊．進行方向＝盾の向き
      if (e.t % 70 < dt) e.dir = pick(["up", "down", "left", "right"]);
      var sv = dirVec(e.dir), sx = e.x, sy = e.y;
      moveEntity(G, e, sv.x * 0.5 * dt, sv.y * 0.5 * dt, false);
      if (e.x === sx && e.y === sy) e.dir = pick(["up", "down", "left", "right"]);
    }

    // 接触：無敵中なら敵を倒す，そうでなければ被弾
    var hitBody = overlap(e, p);
    if (!hitBody && e.type === "snake" && e.body) {
      for (var s = 6; s < e.body.length; s += 6) {
        if (overlap({ x: e.body[s].x, y: e.body[s].y, w: e.w, h: e.h }, p)) { hitBody = true; break; }
      }
    }
    if (hitBody) {
      if (p.star > 0) killEnemy(idx);              // 無敵中は接触で撃破
      else if (p.iframe <= 0) hurtPlayer(e.atk);   // バリヤは弾のみ無効（接触は通る）
    }
  }
  function clampX(x) { return Math.max(TILE + 3, Math.min((GW - 2) * TILE + 3, x)); }
  function clampY(y) { return Math.max(TILE + 3, Math.min((GH - 2) * TILE + 3, y)); }
  function dirVec(d) {
    return d === "up" ? { x: 0, y: -1 } : d === "down" ? { x: 0, y: 1 } :
           d === "left" ? { x: -1, y: 0 } : { x: 1, y: 0 };
  }
  function shoot(e, v) {
    var m = Math.hypot(v.x, v.y) || 1;
    G.bullets.push({ x: e.x + e.w / 2 - 3, y: e.y + e.h / 2 - 3, vx: (v.x / m) * 2.2, vy: (v.y / m) * 2.2, t: 0, dmg: e.atk });
  }
  function shootAt(e, p) {
    shoot(e, { x: (p.x + p.w / 2) - (e.x + e.w / 2), y: (p.y + p.h / 2) - (e.y + e.h / 2) });
  }

  // ---- 扉・スクロール -----------------------------------------------------
  function openDoors(g) {
    var cx = GW >> 1, cy = GH >> 1;
    g.grid[0][cx] = 0; g.grid[GH - 1][cx] = 0;
    g.grid[cy][0] = 0; g.grid[cy][GW - 1] = 0;
  }
  function checkDoorExit() {
    var p = G.p, cx = GW >> 1, cy = GH >> 1, dir = null;
    var pcx = tileOf(p.x + p.w / 2), pcy = tileOf(p.y + p.h / 2);
    if (p.y < 3 && pcx === cx) dir = "up";
    else if (p.y + p.h > GH * TILE - 3 && pcx === cx) dir = "down";
    else if (p.x < 3 && pcy === cy) dir = "left";
    else if (p.x + p.w > GW * TILE - 3 && pcy === cy) dir = "right";
    if (dir) startTransition(dir);
  }
  function startTransition(dir) {
    G.state = "trans";
    G.trans = { dir: dir, t: 0, dur: 26 };
  }
  function updateTrans(dt) {
    G.trans.t += dt;
    if (G.trans.t >= G.trans.dur) {
      G.screen++;
      G.score += 100;                          // スクリーン到達ボーナス
      if (G.p.barrier > 0) G.p.barrier--;      // バリヤは残りスクリーン数で管理
      buildRoom(G, G.trans.dir);
      G.trans = null; G.state = "play"; G.last = performance.now();
    }
  }

  // ---- レベルアップ -------------------------------------------------------
  var STATS = [
    { key: "体力",     desc: "さいだいHP +1" },
    { key: "攻撃力",   desc: "けんのダメージ +1" },
    { key: "スピード", desc: "いどうそくど アップ" },
    { key: "あざとさ", desc: "ショップ 10%わりびき/Lv" }
  ];
  function updateLevelup() {
    if (consume("up")) G.menuSel = (G.menuSel + STATS.length - 1) % STATS.length;
    if (consume("down")) G.menuSel = (G.menuSel + 1) % STATS.length;
    if (consume("enter") || consume("atk")) {
      applyStat(STATS[G.menuSel].key);
      G.levelQueue--;
      if (G.levelQueue <= 0) { G.state = "play"; G.last = performance.now(); }
      else G.menuSel = 0;
    }
  }
  function applyStat(key) {
    var p = G.p;
    if (key === "体力") { p.maxhp += 1; p.hp += 1; }
    else if (key === "攻撃力") { p.atk += 1; }
    else if (key === "スピード") { p.spd += 0.35; }
    else if (key === "あざとさ") { p.azatosa += 1; }
  }

  // ---- ショップ操作 -------------------------------------------------------
  function updateShop() {
    var sh = G.shop;
    if (consume("quit")) { G.state = "play"; G.last = performance.now(); return; }
    if (consume("up")) sh.sel = (sh.sel + sh.items.length - 1) % sh.items.length;
    if (consume("down")) sh.sel = (sh.sel + 1) % sh.items.length;
    if (consume("enter") || consume("atk")) buyItem(sh.items[sh.sel]);
  }
  function buyItem(it) {
    var p = G.p, price = discounted(G, it.price);
    if (G.money < price) { G.fx.push({ kind: "nope", t: 20 }); return; }
    G.money -= price;
    if (it.id === "heart") p.hp = Math.min(p.maxhp, p.hp + 1);
    else if (it.id === "bigheart") p.hp = Math.min(p.maxhp, p.hp + 3);
    else if (it.id === "star") p.star = 420;
    else if (it.id === "diamond") gainXP(10);
    else if (it.id === "barrier") p.barrier = 5;
    else if (it.id === "drill") p.drill = Math.min(9, p.drill + 1);
    else if (it.id === "wand") { p.wand = true; p.ammo = Math.min(9, p.ammo + 3); }
    G.fx.push({ kind: "buy", t: 22 });
  }

  // ---- ゲームオーバー -----------------------------------------------------
  function toGameOver() {
    if (G.score > G.hi) { G.hi = G.score; localStorage.setItem(HI_KEY, String(G.hi)); }
    G.died = (G.p.hp <= 0);                     // false=「やめる」での終了
    G.state = "over"; G.overSel = 0;
  }
  function endGame() { toGameOver(); }          // 「やめる」も同じ着地
  var OVER_MENU = ["もう一回", "もうお腹一杯"];
  function updateOver() {
    if (consume("quit")) { finish(); return; }
    if (consume("up") || consume("down") || consume("left") || consume("right"))
      G.overSel = 1 - G.overSel;
    if (consume("enter") || consume("atk")) {
      if (G.overSel === 0) {                    // もう一回：導入演出なしで最初から
        G = newGame(G.resolve, G.canvas, G.ctx, false);
      } else {
        finish();                               // もうお腹一杯：スコアを返して本編へ
      }
    }
  }

  // ---- 描画 ---------------------------------------------------------------
  function render() {
    var ctx = G.ctx;
    ctx.fillStyle = COL.bg; ctx.fillRect(0, 0, VW, VH);

    // フィールド（HUDの下）
    ctx.save();
    ctx.translate(0, HUD_H);
    if (G.state === "trans") drawTransition(ctx); else drawField(ctx);
    ctx.restore();

    drawHUD(ctx);

    if (G.state === "intro") drawIntro(ctx);
    if (G.state === "levelup") drawLevelup(ctx);
    if (G.state === "shop") drawShop(ctx);
    if (G.state === "over") drawOver(ctx);
  }

  function drawField(ctx) {
    // 床＆ブロック＆氷
    for (var y = 0; y < GH; y++) for (var x = 0; x < GW; x++) {
      var gv = G.grid[y][x];
      if (gv === 1) {
        ctx.fillStyle = COL.dark; ctx.fillRect(x * TILE, y * TILE, TILE, TILE);
        ctx.fillStyle = COL.light; ctx.fillRect(x * TILE, y * TILE, TILE, 3);
      } else if (gv === 2) {                    // 氷
        ctx.fillStyle = COL.light; ctx.fillRect(x * TILE, y * TILE, TILE, TILE);
        ctx.fillStyle = COL.white; ctx.fillRect(x * TILE + 3, y * TILE + 3, TILE - 6, 3);
        ctx.strokeStyle = COL.white; ctx.lineWidth = 1; ctx.strokeRect(x * TILE + 1, y * TILE + 1, TILE - 2, TILE - 2);
      } else {
        ctx.fillStyle = "#171717"; ctx.fillRect(x * TILE, y * TILE, TILE, TILE);
      }
    }
    // 扉
    if (G.doorsOpen) {
      ctx.fillStyle = COL.white;
      var cx = GW >> 1, cy = GH >> 1;
      ctx.fillRect(cx * TILE + 6, 0, TILE - 12, 4);
      ctx.fillRect(cx * TILE + 6, (GH - 1) * TILE + TILE - 4, TILE - 12, 4);
      ctx.fillRect(0, cy * TILE + 6, 4, TILE - 12);
      ctx.fillRect((GW - 1) * TILE + TILE - 4, cy * TILE + 6, 4, TILE - 12);
    }
    for (var o = 0; o < G.obstacles.length; o++) drawObstacle(ctx, G.obstacles[o]);
    if (G.isShop && G.shop) drawKeeper(ctx, G.shop.keeper);
    for (var d = 0; d < G.drops.length; d++) drawDrop(ctx, G.drops[d]);
    for (var i = 0; i < G.enemies.length; i++) drawEnemy(ctx, G.enemies[i]);
    ctx.fillStyle = COL.white;
    for (var b = 0; b < G.bullets.length; b++) { var bl = G.bullets[b]; ctx.fillRect(bl.x, bl.y, 6, 6); }
    ctx.fillStyle = COL.white;                  // 杖の弾
    for (var pb = 0; pb < G.pbullets.length; pb++) { var wb = G.pbullets[pb]; ctx.fillRect(wb.x - 1, wb.y - 1, 8, 8); ctx.fillStyle = COL.dark; ctx.fillRect(wb.x + 1, wb.y + 1, 4, 4); ctx.fillStyle = COL.white; }
    drawPlayer(ctx);
    for (var f = 0; f < G.fx.length; f++) drawFx(ctx, G.fx[f]);
  }
  function drawObstacle(ctx, o) {
    if (o.kind === "fire") {
      ctx.fillStyle = COL.dark; ctx.fillRect(o.px - 4, o.py - 4, 8, 8);
      for (var r = TILE * 0.5; r <= o.len; r += TILE * 0.5) {
        var bx = o.px + Math.cos(o.ang) * r, by = o.py + Math.sin(o.ang) * r;
        ctx.fillStyle = (r / (TILE * 0.5)) % 2 ? COL.white : COL.light;
        ctx.fillRect(bx - 4, by - 4, 8, 8);
      }
    } else if (o.kind === "bomb") {
      var blink = (o.fuse >= 0 && Math.floor(o.fuse / 5) % 2 === 0);
      ctx.fillStyle = blink ? COL.white : COL.dark;
      ctx.fillRect(o.x, o.y, o.w, o.h);
      ctx.fillStyle = COL.light; ctx.fillRect(o.x + o.w / 2 - 2, o.y - 3, 4, 4);   // 導火線
    }
  }
  function drawKeeper(ctx, k) {
    ctx.fillStyle = COL.light; ctx.fillRect(k.x, k.y, k.w, k.h);              // ネズミ店員（仮）
    ctx.fillStyle = COL.dark;
    ctx.fillRect(k.x + 2, k.y - 4, 5, 5); ctx.fillRect(k.x + k.w - 7, k.y - 4, 5, 5);  // 耳
    ctx.fillRect(k.x + 5, k.y + 6, 3, 3); ctx.fillRect(k.x + k.w - 8, k.y + 6, 3, 3);  // 目
    ctx.fillStyle = COL.white; ctx.font = '9px DeterminationJP, monospace';
    ctx.textAlign = "center"; ctx.textBaseline = "bottom";
    ctx.fillText("SHOP", k.x + k.w / 2, k.y - 6);
  }

  function drawPlayer(ctx) {
    var p = G.p;
    if (p.star > 0 && Math.floor(p.star / 4) % 2 === 0) {               // 無敵中の点滅リング
      ctx.strokeStyle = COL.white; ctx.lineWidth = 2;
      ctx.strokeRect(p.x - 3, p.y - 3, p.w + 6, p.h + 6);
    }
    if (p.iframe > 0 && (Math.floor(p.iframe / 4) % 2 === 0)) return;   // 被弾点滅
    var dx = p.x - (TILE - p.w) / 2, dy = p.y - (TILE - p.h) / 2;       // スプライトはTILE大で中央寄せ
    var flip = (p.dir === "right");
    var key = flip ? "left" : p.dir;
    if (p.atkTimer > 0) {                       // 攻撃：全身ポーズ＋前方に剣
      drawCell(ctx, ATK_BODY[key], dx, dy, flip);
      var s = frontTile(dx, dy, p.dir);
      drawCell(ctx, ATK_SWORD[key], s.x, s.y, flip);
    } else {
      var set = ANIM[key];
      var cell = p.moving ? set.walk[Math.floor(p.animT / 9) % set.walk.length] : set.idle;
      drawCell(ctx, cell, dx, dy, flip);
    }
  }
  function frontTile(dx, dy, dir) {
    if (dir === "up") return { x: dx, y: dy - TILE };
    if (dir === "down") return { x: dx, y: dy + TILE };
    if (dir === "left") return { x: dx - TILE, y: dy };
    return { x: dx + TILE, y: dy };            // right（drawCellでflip）
  }
  // シートの[gx,gy]マスを dx,dy に TILE 大で描画。flip=左右反転。未ロード時は矩形。
  function drawCell(ctx, gc, dx, dy, flip) {
    if (!sheetReady) { ctx.fillStyle = COL.white; ctx.fillRect(G.p.x, G.p.y, G.p.w, G.p.h); return; }
    var sx = gc[0] * SS, sy = gc[1] * SS;
    if (flip) {
      ctx.save(); ctx.translate(dx + TILE, dy); ctx.scale(-1, 1);
      ctx.drawImage(SHEET, sx, sy, SS, SS, 0, 0, TILE, TILE); ctx.restore();
    } else {
      ctx.drawImage(SHEET, sx, sy, SS, SS, dx, dy, TILE, TILE);
    }
  }

  function drawEnemy(ctx, e) {
    // ⑤蛇の体（先に胴を描く）
    if (e.type === "snake" && e.body) {
      ctx.fillStyle = COL.dark;
      for (var s = 6; s < e.body.length; s += 6) ctx.fillRect(e.body[s].x + 2, e.body[s].y + 2, e.w - 4, e.h - 4);
    }
    var jy = (e.type === "jump") ? -(e.z || 0) : 0;    // ③はジャンプ高さ
    if (e.type === "jump" && e.z > 1) { ctx.fillStyle = "rgba(0,0,0,.4)"; ctx.fillRect(e.x + 3, e.y + e.h - 2, e.w - 6, 3); }

    // スプライト描画（テスト導入）：ENEMY_ANIM に割り当てがあればシートのコマ，
    // 無い/未ロードなら従来のコード描画にフォールバック。被弾中は点滅で表現。
    var spr = ENEMY_ANIM[e.type];
    if (spr && sheetReady) {
      if (!(e.hurt > 0 && Math.floor(e.hurt / 2) % 2 === 0)) {
        var cell = spr[Math.floor(e.t / 12) % spr.length];
        drawCell(ctx, cell, e.x - (TILE - e.w) / 2, e.y + jy - (TILE - e.h) / 2, false);
      }
      if (e.type === "shield") drawShieldBar(ctx, e);  // 盾の向きは情報なので残す
      return;
    }

    var body = e.hurt > 0 ? COL.white : COL.light;
    if (e.type === "turret") body = COL.dark;
    ctx.fillStyle = body; ctx.fillRect(e.x, e.y + jy, e.w, e.h);
    ctx.fillStyle = COL.bg;
    if (e.type === "walk") { ctx.fillRect(e.x + 4, e.y + 5, 4, 4); ctx.fillRect(e.x + e.w - 8, e.y + 5, 4, 4); }
    else if (e.type === "walkshoot") { ctx.fillRect(e.x + 5, e.y + 5, e.w - 10, 3); ctx.fillRect(e.x + e.w / 2 - 2, e.y + e.h - 8, 4, 5); }
    else if (e.type === "turret") { ctx.fillStyle = COL.white; ctx.fillRect(e.x + e.w / 2 - 3, e.y + e.h / 2 - 3, 6, 6); }
    else if (e.type === "flee") { ctx.fillRect(e.x + 5, e.y + 6, 3, 3); ctx.fillRect(e.x + e.w - 8, e.y + 6, 3, 3); ctx.fillRect(e.x + 6, e.y + e.h - 7, e.w - 12, 2); }
    else if (e.type === "jump") { ctx.fillRect(e.x + 4, e.y + jy + 6, e.w - 8, 3); ctx.fillRect(e.x + 4, e.y + jy + 11, e.w - 8, 3); }
    else if (e.type === "snake") { ctx.fillStyle = COL.white; ctx.fillRect(e.x + 4, e.y + 5, 3, 3); ctx.fillRect(e.x + e.w - 7, e.y + 5, 3, 3); }
    else if (e.type === "shield") drawShieldBar(ctx, e);
  }
  function drawShieldBar(ctx, e) {                     // ⑥ 盾を進行方向側に表示
    ctx.fillStyle = COL.white; var d = e.dir;
    if (d === "left") ctx.fillRect(e.x - 2, e.y, 3, e.h);
    else if (d === "right") ctx.fillRect(e.x + e.w - 1, e.y, 3, e.h);
    else if (d === "up") ctx.fillRect(e.x, e.y - 2, e.w, 3);
    else ctx.fillRect(e.x, e.y + e.h - 1, e.w, 3);
  }

  function drawDrop(ctx, dp) {
    if (dp.kind === "coin") { ctx.fillStyle = COL.light; ctx.fillRect(dp.x, dp.y, dp.w, dp.h); ctx.fillStyle = COL.bg; ctx.fillRect(dp.x + dp.w / 2 - 1, dp.y + 3, 2, dp.h - 6); }
    else if (dp.kind === "heart") { drawHeart(ctx, dp.x, dp.y, dp.w, COL.white); }
    else if (dp.kind === "bigheart") { drawHeart(ctx, dp.x - 1, dp.y - 1, dp.w + 3, COL.white); }
    else if (dp.kind === "star") { drawStar(ctx, dp.x + dp.w / 2, dp.y + dp.h / 2, dp.w / 2 + 1); }
  }
  function drawStar(ctx, cxp, cyp, R) {
    ctx.fillStyle = COL.white; ctx.beginPath();
    for (var i = 0; i < 10; i++) {
      var a = -Math.PI / 2 + i * Math.PI / 5, rr = (i % 2 === 0) ? R : R * 0.45;
      ctx[i ? "lineTo" : "moveTo"](cxp + Math.cos(a) * rr, cyp + Math.sin(a) * rr);
    }
    ctx.closePath(); ctx.fill();
  }
  function drawHeart(ctx, x, y, s, col) {
    ctx.fillStyle = col;
    ctx.fillRect(x + 2, y + 1, 3, 3); ctx.fillRect(x + s - 5, y + 1, 3, 3);
    ctx.fillRect(x, y + 3, s, 4); ctx.fillRect(x + 2, y + 7, s - 4, 3); ctx.fillRect(x + 4, y + 10, s - 8, 2);
  }

  function drawFx(ctx, fx) {
    if (fx.kind === "pop") { ctx.strokeStyle = COL.white; ctx.lineWidth = 2; var r = (14 - fx.t) * 1.6; ctx.beginPath(); ctx.arc(fx.x + TILE / 2, fx.y + TILE / 2, r, 0, 7); ctx.stroke(); }
    else if (fx.kind === "hurt") { ctx.fillStyle = "rgba(230,230,230," + (fx.t / 10 * 0.35) + ")"; ctx.fillRect(0, 0, VW, GH * TILE); }
    else if (fx.kind === "blast") {             // 爆風
      var pr = 1 - fx.t / 26;
      ctx.fillStyle = pr < 0.5 ? COL.white : COL.light;
      ctx.beginPath(); ctx.arc(fx.x, fx.y, fx.r * Math.min(1, pr * 1.4), 0, 7); ctx.fill();
    }
  }

  function drawTransition(ctx) {
    // 簡易スライド（黒→新部屋描画済みなので暗幕をスライド）
    var pr = G.trans.t / G.trans.dur;
    drawField(ctx);
    ctx.fillStyle = COL.bg;
    var w = VW * (1 - pr);
    var d = G.trans.dir;
    if (d === "right") ctx.fillRect(0, 0, VW * pr, GH * TILE);
    else if (d === "left") ctx.fillRect(VW * (1 - pr), 0, VW * pr, GH * TILE);
    else if (d === "down") ctx.fillRect(0, 0, VW, (GH * TILE) * pr);
    else ctx.fillRect(0, (GH * TILE) * (1 - pr), VW, (GH * TILE) * pr);
  }

  // ---- HUD ----------------------------------------------------------------
  function drawHUD(ctx) {
    var p = G.p;
    ctx.fillStyle = "#000"; ctx.fillRect(0, 0, VW, HUD_H);
    ctx.fillStyle = COL.dark; ctx.fillRect(0, HUD_H - 2, VW, 2);
    // ハート
    for (var i = 0; i < p.maxhp; i++) {
      drawHeart(ctx, 6 + i * 15, 8, 12, i < p.hp ? COL.white : COL.dark);
    }
    ctx.fillStyle = COL.white;
    ctx.font = '12px DeterminationJP, monospace'; ctx.textBaseline = "middle";
    var y = HUD_H / 2;
    ctx.textAlign = "left";
    var lvX = 6 + p.maxhp * 15 + 8;
    var extra = "";
    if (p.drill > 0) extra += " Dr" + p.drill;
    if (p.wand) extra += " Wa" + p.ammo;
    if (p.barrier > 0) extra += " Bar" + p.barrier;
    if (p.star > 0) extra += " ★" + Math.ceil(p.star / 60);
    ctx.fillText("Lv" + p.lvl + " EXP" + p.xp + "/" + p.need + " $" + G.money + extra, lvX, y);
    ctx.textAlign = "right";
    ctx.fillText("SC" + G.screen + " " + G.score, VW - 6, y);
  }

  // ---- ショップ画面 -------------------------------------------------------
  function drawShop(ctx) {
    ctx.fillStyle = "rgba(0,0,0,0.82)"; ctx.fillRect(0, 0, VW, VH);
    var bx = VW / 2 - 150, by = 46, bw = 300, bh = 210;
    ctx.fillStyle = "#000"; ctx.fillRect(bx, by, bw, bh);
    ctx.strokeStyle = COL.white; ctx.lineWidth = 2; ctx.strokeRect(bx, by, bw, bh);
    ctx.fillStyle = COL.white; ctx.textAlign = "center"; ctx.textBaseline = "top";
    ctx.font = '15px DeterminationJP, monospace';
    ctx.fillText("＊ ショップ ＊   $" + G.money, VW / 2, by + 12);
    var sh = G.shop;
    for (var i = 0; i < sh.items.length; i++) {
      var it = sh.items[i], oy = by + 48 + i * 34, sel = i === sh.sel;
      var price = discounted(G, it.price);
      drawShopIcon(ctx, it.id, bx + 20, oy - 2);
      ctx.fillStyle = sel ? COL.white : COL.light;
      ctx.textAlign = "left";
      ctx.fillText((sel ? "> " : "  ") + it.name, bx + 44, oy);
      ctx.textAlign = "right";
      ctx.fillStyle = (G.money >= price) ? (sel ? COL.white : COL.light) : COL.dark;
      ctx.fillText("$" + price, bx + bw - 18, oy);
    }
    ctx.fillStyle = COL.dark; ctx.textAlign = "center"; ctx.font = '11px DeterminationJP, monospace';
    ctx.fillText("↑↓えらぶ / Z・Enterかう / Escでる  （あざとさ" + G.p.azatosa + "＝" + (G.p.azatosa * 10) + "%オフ）", VW / 2, by + bh - 20);
  }
  function drawShopIcon(ctx, id, x, y) {
    if (id === "heart" || id === "bigheart") drawHeart(ctx, x, y, id === "bigheart" ? 15 : 12, COL.white);
    else if (id === "star") drawStar(ctx, x + 7, y + 7, 7);
    else if (id === "diamond") { ctx.fillStyle = COL.white; ctx.beginPath(); ctx.moveTo(x + 7, y); ctx.lineTo(x + 14, y + 7); ctx.lineTo(x + 7, y + 14); ctx.lineTo(x, y + 7); ctx.closePath(); ctx.fill(); }
    else if (id === "barrier") { ctx.strokeStyle = COL.white; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x + 7, y + 7, 7, 0, 7); ctx.stroke(); }
    else if (id === "drill") { ctx.fillStyle = COL.light; ctx.fillRect(x + 2, y + 2, 10, 5); ctx.fillStyle = COL.white; ctx.beginPath(); ctx.moveTo(x + 12, y + 1); ctx.lineTo(x + 16, y + 4); ctx.lineTo(x + 12, y + 8); ctx.closePath(); ctx.fill(); }
    else if (id === "wand") { ctx.fillStyle = COL.light; ctx.fillRect(x + 2, y + 10, 12, 3); ctx.fillStyle = COL.white; ctx.fillRect(x + 11, y + 2, 5, 5); }
  }

  // ---- レベルアップ画面 ---------------------------------------------------
  function drawLevelup(ctx) {
    ctx.fillStyle = "rgba(0,0,0,0.8)"; ctx.fillRect(0, 0, VW, VH);
    var bx = VW / 2 - 130, by = 60, bw = 260, bh = 190;
    ctx.fillStyle = "#000"; ctx.fillRect(bx, by, bw, bh);
    ctx.strokeStyle = COL.white; ctx.lineWidth = 2; ctx.strokeRect(bx, by, bw, bh);
    ctx.fillStyle = COL.white; ctx.textAlign = "center"; ctx.textBaseline = "top";
    ctx.font = '15px DeterminationJP, monospace';
    ctx.fillText("* レベルアップ！ *", VW / 2, by + 12);
    ctx.font = '13px DeterminationJP, monospace';
    ctx.fillText("あげる ステータスを えらぶ", VW / 2, by + 34);
    var p = G.p;
    var vals = ["HP" + p.maxhp, "ATK" + p.atk, "SPD" + p.spd.toFixed(1), "x" + p.azatosa];
    for (var i = 0; i < STATS.length; i++) {
      var oy = by + 60 + i * 30;
      var sel = i === G.menuSel;
      ctx.textAlign = "left";
      ctx.fillStyle = sel ? COL.white : COL.light;
      ctx.fillText((sel ? "> " : "  ") + STATS[i].key + " (" + vals[i] + ")", bx + 22, oy);
      ctx.textAlign = "right"; ctx.fillStyle = COL.dark;
      ctx.fillText(STATS[i].desc, bx + bw - 14, oy);
    }
  }

  // ---- ゲームオーバー画面 -------------------------------------------------
  function drawOver(ctx) {
    ctx.fillStyle = "rgba(0,0,0,0.85)"; ctx.fillRect(0, 0, VW, VH);
    ctx.fillStyle = COL.white; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.font = '22px DeterminationJP, monospace';
    ctx.fillText(G.died ? "GAME OVER" : "おつかれさま", VW / 2, VH / 2 - 62);
    ctx.font = '14px DeterminationJP, monospace';
    ctx.fillText("SCORE  " + G.score, VW / 2, VH / 2 - 28);
    ctx.fillText("HISCORE  " + G.hi + (G.score >= G.hi ? "  (NEW!)" : ""), VW / 2, VH / 2 - 6);
    ctx.fillText("SCREEN  " + G.screen, VW / 2, VH / 2 + 16);
    // つづける？（もう一回 / もうお腹一杯）
    for (var i = 0; i < OVER_MENU.length; i++) {
      var sel = (i === G.overSel);
      ctx.fillStyle = sel ? COL.white : COL.dark;
      ctx.fillText((sel ? "> " : "  ") + OVER_MENU[i], VW / 2, VH / 2 + 52 + i * 24);
    }
    ctx.fillStyle = COL.dark; ctx.font = '11px DeterminationJP, monospace';
    ctx.fillText("↑↓えらぶ / Z・Enterきめる", VW / 2, VH / 2 + 106);
  }

  window.NobodyGame = { start: start };
})();
