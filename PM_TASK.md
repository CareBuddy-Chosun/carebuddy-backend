# PM 작업지시서 — backend 세션

> 발행: PM · 2026-06-02 · 트랙 A (모바일 계약 정렬)
> 이 파일은 PM이 하달한 작업지시입니다. 작업 시작 전 전체를 읽으세요.

## 배경

모바일 앱(`carebuddy-mobile`)이 백엔드보다 앞서 구현되어, **모바일이 이미 호출 중인데 백엔드에 없는** 엔드포인트가 다수 있습니다. 통합 1순위는 이 "계약 불일치"를 백엔드가 모바일에 맞춰 해소하는 것입니다. 신규 기능 발명이 아니라 **이미 정해진 계약 구현**입니다.

- 모든 필드는 **snake_case**
- 모든 경로는 **`/api/v1`** prefix
- 현재 백엔드엔 `users` 라우터가 없고 `alembic/versions/`가 비어 있음 → 마이그레이션도 함께 생성·커밋

## 계약 정렬 매트릭스 (모바일 실측 기반, 이대로 맞출 것)

| # | 모바일이 호출하는 것 | 현재 백엔드 | 할 일 |
|---|---|---|---|
| 1 | `POST /auth/register` + `consent_data_storage`,`date_of_birth` | 필드 없음 | User 모델·스키마 확장 |
| 2 | `GET/PATCH /users/me` | 라우터 없음 | users 라우터 신설 |
| 3 | `POST/PATCH/DELETE /users/me/guardians[/{id}]` | 없음 | Guardian 모델+CRUD |
| 4 | `DELETE /sessions/{id}` → 204 | 없음 | 삭제 엔드포인트 |
| 5 | `POST /sessions/{id}/notify-guardians` | 없음 | 알림(우선 stub 허용) |

## 작업 항목

### 1) User 모델 확장 (`app/models/user.py`, `app/schemas/auth.py`)
- `consent_data_storage: bool` NOT NULL default False
- `consent_granted_at: datetime | null`
- `date_of_birth: date | null`
- `RegisterRequest`에 `consent_data_storage`(필수), `date_of_birth`(선택) 추가, 가입 시 저장
- `consent_data_storage=True`면 `consent_granted_at` 기록

### 2) users 라우터 신설 (`app/api/v1/endpoints/users.py` + `router.py` 등록)
- **GET `/users/me`** 응답:
  ```json
  {
    "user_id": "uuid", "email": "str", "full_name": "str",
    "date_of_birth": "YYYY-MM-DD|null", "consent_data_storage": false,
    "guardians": [{"id":"uuid","name":"str","phone":"str","relationship":"str|null"}],
    "created_at": "ISO8601", "session_count": 0
  }
  ```
  - `session_count` = 해당 유저 세션 수
- **PATCH `/users/me`** 요청 `{full_name?, consent_data_storage?}` 부분 업데이트 → 응답은 GET과 동일 스키마

### 3) Guardian 모델 + CRUD (`app/models/guardian.py`, users 라우터)
- 컬럼: `id`(UUID PK), `user_id`(FK→users, CASCADE), `name`, `phone`, `relationship`(nullable), `created_at`
- **POST `/users/me/guardians`** 요청 `{name, phone, relationship?}` → **201**, Guardian 반환
- **PATCH `/users/me/guardians/{id}`** 요청 `{name, phone, relationship?}` → **200**, Guardian 반환
- **DELETE `/users/me/guardians/{id}`** → **204**
- 본인 소유 검증 (타인 가디언 접근 시 **403**)
- Guardian 반환 스키마: `{id, name, phone, relationship}`

### 4) 세션 삭제 (`app/api/v1/endpoints/sessions.py`)
- **DELETE `/sessions/{id}`** → **204**
- 본인 소유 검증(타인 세션 **403**, 없는 세션 **404**), messages CASCADE 삭제 확인

### 5) 가디언 알림 — FR-016 (우선 stub 허용)
- **POST `/sessions/{id}/notify-guardians`** 응답:
  ```json
  { "notifications": [{"guardian_name":"str","phone":"str","status":"str"}] }
  ```
- 실제 Twilio 미연동이면 `status:"stubbed"`로 반환하되 **계약(필드명/구조)은 정확히** 맞출 것

### 6) alembic
- 위 스키마 변경 마이그레이션 생성 후 `versions/`에 커밋
- `alembic upgrade head` 통과 확인

## 완료 기준 (DoD)
- [ ] 5개 엔드포인트가 위 스키마 그대로 응답
- [ ] `pytest` 통과
- [ ] `docker-compose up` 후 수동 호출: 회원가입(consent) → `GET /users/me` → 가디언 추가 → 세션 삭제 → notify-guardians 가 각각 201/200/201/204/200 반환
- [ ] 완료 후 **변경 엔드포인트 목록 + 응답 예시**를 PM에 보고

## 주의
- progress 문서를 신뢰하지 말 것. 현재 코드 기준은 PM이 재작성한 `/Progress.md` 참조.
- JWT는 현재 HS256. RS256(NFR-S02) 전환은 이번 트랙 범위 아님.
