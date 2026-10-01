# Development

- 새 작업은 새 worktree에서 진행한다. 이름은 `../ai-testre-worktreeN`.
- Python 표준 HTTP 서버 + SQLite, 프론트엔드는 의존성 없는 HTML/CSS/JS.
- 문제 생성·채점은 `simulator.py`, HTTP·저장은 `server.py`, UI는 `static/`.
- 문제의 합성 데이터와 자체 채점 기준을 사용자에게 명확히 표시한다.
- 정답을 API 또는 다운로드에 노출하지 않는다.
- CSS 토큰은 `static/style.css`의 `:root`에서 정의한다.
- 검증: `.venv/bin/python -m unittest discover -s tests -v`, `node --check static/app.js`.
- PR은 ready for review로 생성하고 해당 Collavre 토픽에 `pr_monitor`를 붙인다.
- UI 변경은 리뷰 뒤 프리뷰를 시작하고 Collavre `preview_attach`로 등록한다.
- 개별 PC 주소 등 민감정보는 GitHub PR 본문·코멘트에 쓰지 않는다.
- 머지는 squash. 머지 뒤 로컬 main 최신화, 프리뷰 종료 및 worktree 삭제.
