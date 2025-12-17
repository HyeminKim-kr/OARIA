# OARIA 브랜드 에셋

OARIA 프로젝트의 브랜딩 가이드라인입니다. 디자인 작업 시 이 문서를 참고하세요.

> **로고 시각적 미리보기**: [`oaria-logo-assets.html`](./oaria-logo-assets.html)을 브라우저에서 열어 확인하세요.

---

## 브랜드 아이덴티티

### 브랜드명
- **OARIA** (오아리아)
- 태그라인: **RESEARCH INTELLIGENCE**

### 로고 구성
```
[Triple Gate Icon] + OARIA + RESEARCH INTELLIGENCE
```

---

## 브랜드 컬러

### Primary Colors

| 이름 | HEX | RGB | 용도 |
|------|-----|-----|------|
| **OARIA Teal** | `#0D9488` | rgb(13, 148, 136) | 메인 브랜드 컬러, 로고, 주요 CTA |
| **Light Teal** | `#14B8A6` | rgb(20, 184, 166) | 보조 강조색, 호버 상태 |
| **Living Coral** | `#F97066` | rgb(249, 112, 102) | 액센트 컬러, 알림, 강조 포인트 |

### Neutral Colors

| 이름 | HEX | RGB | 용도 |
|------|-----|-----|------|
| **Deep Navy** | `#1E293B` | rgb(30, 41, 59) | 다크 모드 배경, 텍스트 |
| **Dark BG** | `#0F172A` | rgb(15, 23, 42) | 다크 모드 배경 |
| **Light Ring Gray** | `#CBD5E1` | rgb(203, 213, 225) | 라이트 모드 보조 링 |
| **Dark Ring Gray** | `#334155` | rgb(51, 65, 85) | 다크 모드 보조 링 |
| **Tagline Gray** | `#94A3B8` | rgb(148, 163, 184) | 태그라인, 보조 텍스트 |
| **Border Gray** | `#E2E8F0` | rgb(226, 232, 240) | 테두리, 구분선 |
| **Background** | `#F8FAFC` | rgb(248, 250, 252) | 라이트 모드 배경 |

---

## CSS 변수

```css
:root {
  /* Primary */
  --color-oaria-teal: #0D9488;
  --color-light-teal: #14B8A6;
  --color-living-coral: #F97066;

  /* Neutral */
  --color-deep-navy: #1E293B;
  --color-dark-bg: #0F172A;
  --color-light-ring: #CBD5E1;
  --color-dark-ring: #334155;
  --color-tagline: #94A3B8;
  --color-border: #E2E8F0;
  --color-background: #F8FAFC;

  /* Text */
  --color-text-primary: #1E293B;
  --color-text-secondary: #64748B;
  --color-text-muted: #94A3B8;
}
```

---

## Tailwind CSS

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        oaria: {
          teal: '#0D9488',
          'light-teal': '#14B8A6',
          coral: '#F97066',
          navy: '#1E293B',
          'dark-bg': '#0F172A',
        }
      }
    }
  }
}
```

사용 예시:
```html
<button class="bg-oaria-teal hover:bg-oaria-light-teal text-white">
  시작하기
</button>

<span class="text-oaria-coral">
  중요 알림
</span>
```

---

## 타이포그래피

### 폰트 패밀리

| 용도 | 폰트 | Weight | 예시 |
|------|------|--------|------|
| **로고/헤딩** | Outfit | 600, 700 | OARIA |
| **본문** | DM Sans | 400, 500, 600 | Research Intelligence |

### Google Fonts 임포트

```html
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
```

```css
/* CSS */
font-family: 'Outfit', sans-serif;    /* 로고, 헤딩 */
font-family: 'DM Sans', sans-serif;   /* 본문 */
```

---

## 로고 사용 가이드

### 로고 타입

| 타입 | 용도 | 파일명 |
|------|------|--------|
| **Horizontal** | 메인 로고, 헤더 | `oaria-logo-horizontal.svg` |
| **Vertical** | 스택 레이아웃, 프레젠테이션 | `oaria-logo-vertical.svg` |
| **Compact** | 작은 공간, 태그라인 없이 | `oaria-logo-compact.svg` |
| **Icon Only** | 파비콘, 앱 아이콘 | `oaria-icon.svg` |

### 배경별 사용

| 배경 | 로고 버전 |
|------|----------|
| 라이트 배경 (`#F8FAFC`, `#FFFFFF`) | Light 버전 |
| 다크 배경 (`#0F172A`, `#1E293B`) | Dark 버전 |
| 그라디언트/이미지 배경 | Dark 버전 권장 |

### 최소 여백

로고 주변에 최소 로고 높이의 **50%** 만큼 여백을 확보하세요.

```
┌──────────────────────────┐
│                          │
│    ┌──────────────┐      │
│    │   OARIA      │      │
│    │   LOGO       │      │
│    └──────────────┘      │
│         ↑                │
│    최소 여백 50%          │
└──────────────────────────┘
```

---

## 로고 구성 요소

### Triple Gate Icon (삼중 게이트 아이콘)

```
     ┌─── 외부 링: OARIA Teal (#0D9488)
     │
     │  ┌─── 중간 링: Light Teal (#14B8A6)
     │  │
     │  │  ┌─── 내부 링: Living Coral (#F97066)
     │  │  │
    ┌┴──┴──┴┐
   ◯  ◯  ◯  ●   ← 중앙 코어: Deep Navy + White
    └──────┘
```

- **외부 링**: Primary 브랜드 컬러
- **중간 링**: 60도 회전, 보조 컬러
- **내부 링**: 120도 회전, 액센트 컬러
- **중앙 코어**: 라이트 모드 - Navy/White, 다크 모드 - White/Navy

---

## 그라디언트

### Primary Gradient

```css
background: linear-gradient(135deg, #0D9488 0%, #0F766E 100%);
```

### Background Gradient (Subtle)

```css
/* Light */
background: linear-gradient(135deg, #F1F5F9 0%, #E2E8F0 100%);

/* Dark */
background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
```

---

## 사용 금지 사항

- 로고 색상 임의 변경
- 로고 비율 왜곡
- 로고 주변 최소 여백 미확보
- 복잡한 배경 위에 로고 배치 (가독성 저하)
- 태그라인 폰트 임의 변경

---

## UI 컴포넌트 스타일 가이드

### 버튼

#### Primary Button
```css
background: #0D9488;
color: white;
border-radius: 9999px; /* rounded-full */
padding: 12px 32px;
font-family: 'DM Sans';
font-weight: 500;

/* Hover */
background: #14B8A6;
```

#### Secondary Button (Outline)
```css
background: transparent;
border: 1px solid #E2E8F0;
color: #1E293B;
border-radius: 9999px;
padding: 12px 32px;

/* Hover */
border-color: #0D9488;
```

### 카드

```css
background: #FFFFFF;
border: 1px solid #E2E8F0;
border-radius: 16px;
padding: 32px;

/* Hover */
border-color: rgba(13, 148, 136, 0.5);
```

### 입력 필드

```css
background: rgba(226, 232, 240, 0.3);
border-radius: 9999px;
padding: 12px 16px;
font-family: 'DM Sans';

/* Placeholder */
color: #94A3B8;
```

### 배지 (Badge)

```css
background: rgba(13, 148, 136, 0.1);
color: #0D9488;
border-radius: 9999px;
padding: 8px 16px;
font-size: 14px;
font-weight: 500;
```

---

## 아이콘 가이드

### 아이콘 스타일
- 선 두께: 2px
- 선 끝: `round` (strokeLinecap)
- 모서리: `round` (strokeLinejoin)
- 크기: 24x24 (기본), 20x20 (소형), 16x16 (초소형)

### 아이콘 색상
| 용도 | 색상 |
|------|------|
| 기본 | `#64748B` (text-secondary) |
| 강조 | `#0D9488` (oaria-teal) |
| 액센트 | `#F97066` (living-coral) |
| 비활성 | `#94A3B8` (tagline) |

---

## 간격 시스템

### Spacing Scale
```
4px  - 초소형 간격
8px  - 소형 간격
16px - 기본 간격
24px - 중형 간격
32px - 대형 간격
48px - 섹션 간격
64px - 대섹션 간격
```

### 컨테이너 최대 너비
```
max-width: 1152px (6xl)
padding: 24px (모바일), 48px (데스크톱)
```

---

## 파일 참조

| 파일 | 용도 |
|------|------|
| `oaria-logo-assets.html` | 로고 SVG 원본, 시각적 미리보기 |
| `BRAND-ASSETS.md` | 브랜드 가이드라인 문서 (현재 파일) |

---
