# OpenDART API 문서 (DS003 / apiId=2022002) — 다중회사 주요 재무지표

출처: OpenDART 개발가이드 — “정기보고서 재무정보 > 다중회사 주요 재무지표”. citeturn0view0

## 1) 기본 정보

- **API 이름**: 다중회사 주요 재무지표
- **요청 방식**: `GET`
- **인코딩**: `UTF-8`
- **출력 포맷**
  - JSON: `https://opendart.fss.or.kr/api/fnlttCmpnyIndx.json` citeturn0view0
  - XML: `https://opendart.fss.or.kr/api/fnlttCmpnyIndx.xml` citeturn0view0

## 2) 요청 인자 (Request Parameters)

> 모든 파라미터는 필수(Y)로 안내되어 있습니다. citeturn0view0  
> `corp_code`는 OpenAPI 테스트 예시에서 **쉼표로 구분된 다중 입력**이 사용되고, 오류 코드(021)에서도 “조회 가능한 회사 개수(최대 100건)” 제한이 안내됩니다. citeturn0view0

| 요청키 (key) | 명칭 | 타입 | 필수 | 설명 |
|---|---|---:|:---:|---|
| `crtfc_key` | API 인증키 | STRING(40) | Y | 발급받은 인증키(40자리) citeturn0view0 |
| `corp_code` | 고유번호 | STRING(8) | Y | 공시대상회사의 고유번호(8자리). *개발가이드 > 공시정보 > 고유번호 참고* citeturn0view0 |
| `bsns_year` | 사업연도 | STRING(4) | Y | 사업연도(4자리). *2023년 3분기 이후부터 정보 제공* citeturn0view0 |
| `reprt_code` | 보고서 코드 | STRING(5) | Y | 1분기: `11013` / 반기: `11012` / 3분기: `11014` / 사업보고서: `11011` citeturn0view0 |
| `idx_cl_code` | 지표분류코드 | STRING(7) | Y | 수익성: `M210000` / 안정성: `M220000` / 성장성: `M230000` / 활동성: `M240000` citeturn0view0 |

### 2.1) 보고서 코드(reprt_code) 매핑

- `11013` : 1분기보고서 citeturn0view0  
- `11012` : 반기보고서 citeturn0view0  
- `11014` : 3분기보고서 citeturn0view0  
- `11011` : 사업보고서 citeturn0view0  

### 2.2) 지표 분류 코드(idx_cl_code) 매핑

- `M210000` : 수익성지표 citeturn0view0  
- `M220000` : 안정성지표 citeturn0view0  
- `M230000` : 성장성지표 citeturn0view0  
- `M240000` : 활동성지표 citeturn0view0  

## 3) 응답 결과 (Response)

응답은 최상위에 `result`(상태/메시지)와 `list`(데이터 목록)를 포함합니다. citeturn0view0

### 3.1) Result (상태/메시지)

| 필드 | 설명 |
|---|---|
| `status` | 에러 및 정보 코드 citeturn0view0 |
| `message` | 에러 및 정보 메시지 citeturn0view0 |

### 3.2) List (데이터 배열)

| 필드 | 명칭 | 설명/예시 |
|---|---|---|
| `reprt_code` | 보고서 코드 | `11013`/`11012`/`11014`/`11011` citeturn0view0 |
| `bsns_year` | 사업 연도 | 예: `2023` citeturn0view0 |
| `corp_code` | 고유번호 | 공시대상회사의 고유번호(8자리) citeturn0view0 |
| `stock_code` | 종목 코드 | 상장회사의 종목코드(6자리) citeturn0view0 |
| `stlm_dt` | 결산기준일 | `YYYY-MM-DD` citeturn0view0 |
| `idx_cl_code` | 지표분류코드 | 수익성/안정성/성장성/활동성 코드 citeturn0view0 |
| `idx_cl_nm` | 지표분류명 | 예: `수익성지표` citeturn0view0 |
| `idx_code` | 지표코드 | 예: `M211000` citeturn0view0 |
| `idx_nm` | 지표명 | 예: `영업이익률` citeturn0view0 |
| `idx_val` | 지표값 | 예: `0.256` citeturn0view0 |

## 4) 메시지(에러/정보) 코드

| 코드 | 의미 |
|---:|---|
| `000` | 정상 citeturn0view0 |
| `010` | 등록되지 않은 키 citeturn0view0 |
| `011` | 사용할 수 없는 키(일시 중지 등) citeturn0view0 |
| `012` | 접근할 수 없는 IP citeturn0view0 |
| `013` | 조회된 데이터 없음 citeturn0view0 |
| `014` | 파일이 존재하지 않음 citeturn0view0 |
| `020` | 요청 제한 초과 citeturn0view0 |
| `021` | 조회 가능한 회사 개수 초과(최대 100건) citeturn0view0 |
| `100` | 필드의 부적절한 값 citeturn0view0 |
| `101` | 부적절한 접근 citeturn0view0 |
| `800` | 시스템 점검으로 서비스 중지 citeturn0view0 |
| `900` | 정의되지 않은 오류 citeturn0view0 |
| `901` | 개인정보 보유기간 만료로 사용할 수 없는 키(문의: opendart@fss.or.kr) citeturn0view0 |

## 5) 호출 예시

### 5.1) JSON 요청 예시 (curl)

```bash
curl -G "https://opendart.fss.or.kr/api/fnlttCmpnyIndx.json" \
  --data-urlencode "crtfc_key=YOUR_API_KEY" \
  --data-urlencode "corp_code=00164742,00159023" \
  --data-urlencode "bsns_year=2023" \
  --data-urlencode "reprt_code=11014" \
  --data-urlencode "idx_cl_code=M210000"
```

> 위 `corp_code` 다중 입력 형식(쉼표 구분)은 개발가이드의 OpenAPI 테스트 예시를 그대로 반영했습니다. citeturn0view0

---

### 메모

- 본 API는 **2023년 3분기 이후** 데이터부터 제공된다고 안내되어 있습니다. citeturn0view0
