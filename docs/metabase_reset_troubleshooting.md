# Metabase 초기화 트러블슈팅

## 문제 상황

Metabase의 dashboard가 초기화되어, 새로 host에 띄울 때마다 대시보드를 다시 구성해야 한다.

증상은 다음과 같다.

- 기존에 만들었던 Metabase 컬렉션이 사라진다.
- 기존 dashboard, question/card, public dashboard URL이 사라진다.
- Metabase 로그인 계정이나 설정이 초기화된 것처럼 보인다.
- 프론트엔드의 네이버 클립 성과 확인 페이지에서 iframe이 비어 있거나, 예전 public dashboard URL이 더 이상 유효하지 않다.
- 결국 `scripts/create_metabase_b2_dashboard.py`를 다시 실행해서 대시보드를 재구성해야 한다.

## 원인 분석

Metabase는 dashboard, collection, question/card, 사용자 계정, public sharing 설정 등을 자체 application DB에 저장한다.

현재 문제가 되는 구조는 Metabase의 application DB가 Docker 컨테이너 내부 파일시스템에만 저장되는 구조다. 이 경우 컨테이너를 새로 만들거나 삭제하면 컨테이너 내부에 있던 Metabase application DB도 함께 사라질 수 있다.

즉, 로그아웃 자체가 dashboard를 초기화하는 것은 아니다. 실제 원인은 다음에 가깝다.

- Metabase 컨테이너가 persistent volume 없이 실행됨
- application DB 파일이 컨테이너 내부 경로에만 존재함
- 컨테이너를 `docker rm` 하거나 같은 이름으로 새로 만들면서 내부 DB가 유실됨
- 그 결과 dashboard, collection, question/card, 계정 설정, public dashboard URL이 초기화됨

현재 확인했던 상태 예시는 다음과 같다.

```text
Mounts=[]
DB file=/metabase.db/metabase.db.mv.db
```

`Mounts=[]`는 컨테이너 외부에 연결된 저장소가 없다는 뜻이다. 따라서 Metabase 데이터가 컨테이너 생명주기에 묶여 있다.

## 해결 방법

### 1. 볼륨으로 Metabase 데이터를 띄움

Docker volume을 사용해서 Metabase application DB를 컨테이너 밖에 보관한다.

여기서 "볼륨"이란 Docker가 관리하는 영속 저장공간을 뜻한다. 컨테이너는 언제든 삭제하거나 새로 만들 수 있는 실행 단위지만, volume은 컨테이너와 별도로 남아 있는 데이터 저장소다.

비유하면 다음과 같다.

- Docker container: 실행 중인 프로그램 본체
- Docker volume: 프로그램이 계속 보관해야 하는 데이터 폴더

Metabase에서는 volume에 application DB를 저장해야 다음 데이터가 유지된다.

- 사용자 계정
- 로그인/세션 관련 설정
- database connection 설정
- collection
- question/card
- dashboard
- public dashboard 공유 설정

권장 실행 예시는 다음과 같다.

```powershell
wsl docker run -d `
  --name metabase `
  -p 3000:3000 `
  -v metabase-data:/metabase-data `
  -e MB_DB_FILE=/metabase-data/metabase.db `
  -e MAX_SESSION_AGE=525600 `
  -e MB_SESSION_COOKIES=false `
  metabase/metabase
```

핵심은 이 부분이다.

```powershell
-v metabase-data:/metabase-data
-e MB_DB_FILE=/metabase-data/metabase.db
```

의미는 다음과 같다.

- `metabase-data`: Docker가 관리하는 volume 이름
- `/metabase-data`: 컨테이너 안에서 보이는 경로
- `MB_DB_FILE=/metabase-data/metabase.db`: Metabase application DB를 이 경로에 저장하라는 설정

이렇게 실행하면 컨테이너를 재시작하거나 새로 만들어도 `metabase-data` volume이 남아 있는 한 Metabase dashboard와 설정이 유지된다.

기존 non-volume 컨테이너를 쓰고 있었다면, 먼저 DB를 백업해야 한다.

```powershell
wsl docker cp metabase:/metabase.db ./metabase-db-backup
```

그 다음 기존 컨테이너를 멈추고 이름을 바꿔 보관한다.

```powershell
wsl docker stop metabase
wsl docker rename metabase metabase-old-no-volume
```

volume을 만든다.

```powershell
wsl docker volume create metabase-data
```

백업한 DB를 volume에 복사한다.

```powershell
wsl docker run --rm `
  -v metabase-data:/metabase-data `
  -v /mnt/c/Users/mung9/IdeaProjects/rhoonart-rpa/metabase-db-backup:/backup `
  alpine sh -c "cp -a /backup/. /metabase-data/"
```

이후 volume 기반으로 Metabase를 실행한다.

```powershell
wsl docker run -d `
  --name metabase `
  -p 3000:3000 `
  -v metabase-data:/metabase-data `
  -e MB_DB_FILE=/metabase-data/metabase.db `
  -e MAX_SESSION_AGE=525600 `
  -e MB_SESSION_COOKIES=false `
  metabase/metabase
```

정상 여부는 다음 명령어로 확인한다.

```powershell
wsl docker inspect metabase --format 'Mounts={{json .Mounts}}'
```

`Mounts=[]`가 아니고 `metabase-data`가 보이면 volume이 연결된 것이다.

### 2. 대시보드 구성 코드와 보조 스크립트를 문서화함

Metabase가 이미 초기화되었거나, 새 환경에서 다시 구성해야 하는 경우를 대비해 대시보드 복구 절차를 별도 문서로 작성해둔다.

참고 문서:

```text
docs/metabase_dashboard_recovery.md
```

이 문서에는 다음 내용이 들어 있다.

- Metabase dashboard 재생성 명령어
- 기존 dashboard 구성 코드 위치
- 보조 스크립트 역할
- frontend가 Metabase URL을 가져오는 흐름
- Supabase에 저장되는 `metabase_embed_url` 구조
- Docker volume을 이용한 초기화 방지 방법

주요 코드와 스크립트는 다음과 같다.

```text
scripts/create_metabase_b2_dashboard.py
scripts/patch_metabase_work_title_dropdown.py
scripts/update_metabase_public_urls.py
```

각 역할은 다음과 같다.

- `create_metabase_b2_dashboard.py`: Metabase collection, dashboard, card, filter, public dashboard URL 생성
- `patch_metabase_work_title_dropdown.py`: 작품명 필터를 드롭다운 형태로 보정
- `update_metabase_public_urls.py`: 저장된 public dashboard URL의 host/port를 외부 접속 주소에 맞게 재작성

프론트엔드 URL 흐름도 문서에 반드시 포함되어야 한다.

현재 프론트엔드는 `.env`에서 Metabase URL을 직접 읽지 않는다. 대신 아래 흐름으로 URL을 받는다.

```text
Metabase dashboard 생성 스크립트
→ public dashboard URL 생성
→ Supabase naver_rights_holders.metabase_embed_url 저장
→ 백엔드 GET /api/admin/reports/metabase
→ 프론트엔드 web/app/admin/reports/naver-clip/page.tsx
→ iframe에 embed_url 표시
```

관련 파일은 다음과 같다.

```text
web/app/admin/reports/naver-clip/page.tsx
web/lib/api.ts
web/lib/types.ts
src/api/rpa_server.py
src/core/repositories/supabase_b2_repository.py
migrations/011_naver_rights_holders_metabase_url.sql
```

## 재발 시 빠른 복구 절차

Metabase가 다시 초기화되었다면 아래 순서로 진행한다.

1. Metabase가 3000 포트에 떠 있는지 확인한다.

```powershell
wsl docker start metabase
wsl docker logs -f metabase
```

2. 로그에서 초기화 완료를 확인한다.

```text
Metabase Initialization COMPLETE
```

3. 대시보드를 재생성한다.

```powershell
python scripts\create_metabase_b2_dashboard.py `
  --url http://localhost:3000 `
  --public-url http://localhost:3000 `
  --database-id 2 `
  --mode split
```

4. 작품명 드롭다운을 보정한다.

```powershell
$env:METABASE_URL='http://localhost:3000'
$env:METABASE_DATABASE_ID='2'
python scripts\patch_metabase_work_title_dropdown.py
```

5. Supabase에 URL이 저장되었는지 확인한다.

```powershell
@'
from dotenv import load_dotenv
import os, requests

load_dotenv(".env")
base = os.getenv("SUPABASE_URL").rstrip("/")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
resp = requests.get(
    f"{base}/rest/v1/naver_rights_holders",
    headers={"apikey": key, "Authorization": f"Bearer {key}"},
    params={
        "select": "rights_holder_name,naver_report_enabled,metabase_embed_url",
        "naver_report_enabled": "eq.true",
        "order": "rights_holder_name.asc",
    },
    timeout=30,
)
resp.raise_for_status()
for row in resp.json():
    print(row)
'@ | python -
```

활성 권리사 row에 `metabase_embed_url` 값이 있으면 프론트엔드에서 해당 URL을 받아 표시할 수 있다.

## 운영 주의사항

- `docker stop metabase`는 데이터를 지우지 않는다.
- volume 없이 실행한 컨테이너를 `docker rm metabase` 하면 Metabase application DB가 사라질 수 있다.
- volume 기반 실행 후에도 `docker volume rm metabase-data`를 하면 데이터가 사라진다.
- local 개발 환경에서는 Docker volume 방식이 현실적인 해결책이다.
- 장기 운영 환경에서는 Metabase application DB를 Postgres 같은 외부 DB로 분리하는 방식이 더 안정적이다.
