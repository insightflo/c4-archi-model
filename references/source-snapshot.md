# Source Snapshot 규칙

아키텍처 설명이 나중에도 재현 가능하려면 "어떤 자료를 실제로 읽었는가"를 고정해야 한다.
URL이나 branch 이름만 기록하는 것은 Snapshot이 아니다.

## Source 필드

```text
id
name
kind
location
version
readScope
limitations
immutableRef
contentHash
capturedAt
```

## 자료별 권장 고정 방법

### 코드 저장소

```text
repository URL
commit SHA
읽은 파일·디렉터리·심볼·줄 범위
필요한 경우 파일 blob hash
```

`main`, `develop`, release 이름만으로 재현 가능하다고 주장하지 않는다.

### 로컬 문서·설정

```text
상대 경로
문서 버전 또는 수정일, 확인 가능할 때
SHA-256 또는 content hash
읽은 페이지·제목·줄 범위
```

### PDF·DOCX·Wiki

```text
문서 제목과 버전
페이지 또는 제목 계층
export 시각 또는 immutable document revision
표·그림을 실제로 확인했는지
```

### API·IaC

```text
파일 경로
operationId, channel, resource, module 이름
commit 또는 content hash
```

### Runtime

```text
trace/log/run ID
관찰 시간 범위
환경
sampling 또는 누락 한계
```

## Snapshot ID

Snapshot ID는 Session, Canonical Model metadata와 Evidence Ledger에서 같아야 한다.

예:

```text
snapshot-ordering-4e52e5080310
```

ID의 hash가 실제 파일 hash 전체를 대체하지 않는다. Source별 immutableRef 또는 contentHash를 함께 보존한다.

## 읽지 못한 자료

접근할 수 없는 링크, 암호화된 문서, 누락된 첨부는 Source로 등록할 수 있지만 support 근거로 사용하지 않는다.
limitations와 Coverage에 영향을 기록한다.

## 변경 감지

새 분석에서 Snapshot이 바뀌면 기존 모델을 무조건 덮어쓰지 않는다.

```text
이전 Snapshot
현재 Snapshot
추가·삭제·변경된 Source
영향받는 Claim
영향받는 element / relationship / view
```

변경 영향 분석은 후속 버전의 diff 기능으로 확장할 수 있다.
