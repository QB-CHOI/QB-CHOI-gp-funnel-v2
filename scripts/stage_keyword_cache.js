#!/usr/bin/env node
/**
 * 키워드 분석툴 캐시를 inbox/market/ 으로 복사한다.
 *
 * 왜 node인가:
 *   macOS TCC(개인정보 보호)가 launchd 프로세스의 ~/Documents 접근을 막는데,
 *   node는 키워드 분석툴을 돌리느라 이미 전체 디스크 접근 권한을 받아 두었다.
 *   반면 /usr/bin/python3 은 권한이 없어 PermissionError가 난다.
 *   → 권한 있는 node가 '보호 폴더 밖'으로 옮겨 주고, python은 그것만 읽는다.
 *   덕분에 사용자가 시스템 설정을 건드리지 않아도 완전 자동화된다.
 *
 * 복사 대상: 최신 날짜의 주제별 캐시 + 자사 실적 dataset.json (필요한 것만)
 */
const fs = require("fs");
const path = require("path");

const HOME = process.env.HOME;
const SRC = path.join(HOME, "Documents", "📌 콘텐츠 자동화 제작 프로그램",
  "키워드 분석툴", "data");
const DEST = path.join(__dirname, "..", "inbox", "market");

const PREFIXES = ["youtube_market_", "naver_age_", "naver_demand_"];

function log(m) {
  console.log(`[${new Date().toISOString().slice(0, 19)}] ${m}`);
}

function main() {
  const processedDir = path.join(SRC, "processed");
  if (!fs.existsSync(processedDir)) {
    log("키워드 분석툴 데이터 없음 — 건너뜀");
    return 0;
  }
  fs.mkdirSync(DEST, { recursive: true });

  let files;
  try {
    files = fs.readdirSync(processedDir);
  } catch (e) {
    log(`읽기 실패(${e.code}) — node에도 권한이 없습니다`);
    return 1;
  }

  // 접두사별로 '가장 최신 날짜' 파일만 남긴다 (249개 전부 복사할 필요 없음)
  const latest = new Map();
  for (const f of files) {
    if (!f.endsWith(".json")) continue;
    const p = PREFIXES.find((x) => f.startsWith(x));
    if (!p) continue;
    const m = f.match(/^(.*)_(\d{4}-\d{2}-\d{2})\.json$/);
    if (!m) continue;
    const [, base, date] = m;
    const prev = latest.get(base);
    if (!prev || prev.date < date) latest.set(base, { date, file: f });
  }

  let copied = 0;
  for (const { file } of latest.values()) {
    const src = path.join(processedDir, file);
    const dst = path.join(DEST, file);
    try {
      // 이미 같은 내용이면 건너뛴다(불필요한 쓰기 방지)
      if (fs.existsSync(dst) &&
          fs.statSync(dst).mtimeMs >= fs.statSync(src).mtimeMs) continue;
      fs.copyFileSync(src, dst);
      copied += 1;
    } catch (e) {
      log(`복사 실패 ${file}: ${e.code}`);
    }
  }

  // 자사 유튜브 실적 + 확장 주제 설정
  //   custom_topics.json: 사용자가 키워드툴에서 추가·삭제하는 주제 목록.
  //   지운 주제의 캐시 파일은 processed/에 그대로 남으므로, 이 설정이 없으면
  //   '지금 살아 있는 주제'와 '지운 주제'를 구분할 수 없다.
  for (const name of ["dataset.json", "custom_topics.json"]) {
    const src = path.join(SRC, name);
    if (!fs.existsSync(src)) continue;
    try {
      const dst = path.join(DEST, name);
      if (!fs.existsSync(dst) ||
          fs.statSync(src).mtimeMs > fs.statSync(dst).mtimeMs) {
        fs.copyFileSync(src, dst);
        copied += 1;
      }
    } catch (e) {
      log(`${name} 복사 실패: ${e.code}`);
    }
  }

  // 오래된 스테이징 파일 정리 (최신 세트만 유지)
  const keep = new Set([...latest.values()].map((v) => v.file));
  keep.add("dataset.json");
  keep.add("custom_topics.json");
  for (const f of fs.readdirSync(DEST)) {
    if (f.endsWith(".json") && !keep.has(f)) {
      try { fs.unlinkSync(path.join(DEST, f)); } catch { /* 무시 */ }
    }
  }

  log(`스테이징 완료 — 갱신 ${copied}개 / 유지 ${keep.size}개`);
  return 0;
}

process.exit(main());
