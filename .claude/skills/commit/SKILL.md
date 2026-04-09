---
name: commit
description: 변경사항을 커밋하고 push까지 진행
---

# Git Commit & Push

변경사항을 커밋하고 원격에 push한다. 아래 단계를 순서대로 수행한다.

## 1. 상태 확인 (병렬 실행)

다음 명령을 **병렬로** 실행:
- `git status` — 변경/untracked 파일 확인
- `git diff` — staged + unstaged 변경 내용 확인 (staged가 있으면 `git diff --cached`도)
- `git log --oneline -10` — 최근 커밋 메시지 스타일 확인

변경사항이 없으면 "커밋할 변경사항이 없습니다"라고 알리고 종료.

## 2. 커밋 메시지 작성

- 최근 커밋 로그의 **기존 스타일**(prefix, 언어, 형식)에 맞춘다.
- 변경의 성격을 정확히 반영: `feat`, `fix`, `refactor`, `chore`, `design` 등.
- 1~2문장, "why"에 초점.
- `.env`, credentials 등 민감 파일이 포함되어 있으면 **경고하고 커밋에서 제외**.

## 3. 커밋 실행

- 관련 파일만 `git add`로 staging (`git add -A` 사용 금지).
- 커밋 메시지 끝에 Co-Authored-By 추가:
  ```
  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
  ```
- HEREDOC 방식으로 커밋:
  ```bash
  git commit -m "$(cat <<'EOF'
  메시지

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

## 4. Push

- 로컬 브랜치가 원격보다 뒤에 있으면 `git pull --rebase` 먼저 수행 (stash 필요 시 자동 처리).
- `git push`로 원격에 push.
- push 결과를 사용자에게 보고 (커밋 해시 + 메시지 요약).

## 인자 처리

`$ARGUMENTS`가 있으면 커밋 메시지로 직접 사용한다 (스타일 prefix는 자동 판단하여 붙인다).
없으면 변경 내용을 분석하여 메시지를 자동 생성한다.
