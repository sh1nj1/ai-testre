"""Synthetic practice tasks. Answers stay on the server."""

import io
import json
import re
import zipfile
from PIL import Image, ImageDraw

SOURCES = {
    "menu": "https://brunch.co.kr/@andkakao/323",
    "code": "https://brunch.co.kr/@andkakao/317",
    "video": "https://brunch.co.kr/@andkakao/324",
    "battle": "https://brunch.co.kr/@andkakao/321",
    "pdf": "https://brunch.co.kr/@andkakao/322",
    "immigration": "https://brunch.co.kr/@andkakao/327",
    "montage": "https://brunch.co.kr/@andkakao/326",
    "handover": "https://brunch.co.kr/@andkakao/325",
}


def task(key, title, category, description, parts, files, answers):
    return dict(
        id=key,
        title=title,
        category=category,
        description=description,
        parts=[
            dict(id=str(i + 1), prompt=p, type=t, max_score=s)
            for i, (p, t, s) in enumerate(parts)
        ],
        files=files,
        answers=answers,
        source=SOURCES[key],
    )


def image_bytes(image):
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def target_image():
    im = Image.new("RGB", (1024, 1024), "#e8dfce")
    d = ImageDraw.Draw(im)
    d.ellipse((240, 150, 784, 900), fill="#d7a47d")
    d.pieslice((220, 80, 804, 720), 180, 360, fill="#292b35")
    d.ellipse((365, 390, 435, 455), fill="#282a32")
    d.ellipse((590, 390, 660, 455), fill="#282a32")
    d.polygon([(512, 465), (470, 615), (545, 615)], fill="#b67f60")
    d.arc((390, 610, 635, 750), 0, 180, fill="#8a443f", width=18)
    return im


def make_pdf():
    # A white text stream and a covering rectangle preserve extractable text.
    streams = [
        b"BT /F1 22 Tf 50 760 Td (ARCHIVE REPORT) Tj ET\nBT /F1 8 Tf 1 1 1 rg 50 700 Td (silent river opens tomorrow) Tj ET",
        b"BT /F1 22 Tf 50 760 Td (SECOND PAGE) Tj ET\nBT /F1 12 Tf 50 650 Td (Layer code: ORBIT) Tj ET\n0.15 0.2 0.3 rg 45 640 250 30 re f",
    ]
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length "
        + str(len(streams[0])).encode()
        + b" >>\nstream\n"
        + streams[0]
        + b"\nendstream",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>",
        b"<< /Length "
        + str(len(streams[1])).encode()
        + b" >>\nstream\n"
        + streams[1]
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 8\n0000000000 65535 f \n"
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets[1:])
    return (
        out + f"trailer\n<< /Size 8 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )


def tasks():
    menu = [
        dict(
            name=f"Meal {i+1}",
            price=4000 + i * 500,
            protein=10 + i * 3,
            calories=350 + i * 40,
        )
        for i in range(8)
    ]
    menu_files = {"menus.json": json.dumps(menu, indent=2)}
    for i, m in enumerate(menu):
        im = Image.new("RGB", (640, 420), "#fff4d5")
        d = ImageDraw.Draw(im)
        d.text(
            (40, 60),
            f"MENU {i+1}\n\n{m['name']}\nPrice: {m['price']} KRW\nProtein: {m['protein']} g\nCalories: {m['calories']} kcal",
            fill="#172b35",
            font_size=28,
        )
        menu_files[f"menus/menu-{i+1}.png"] = image_bytes(im)
    code = (
        "n = int(input())\ns = 0\nfor i in range(1, n + 1):\n    s += i * i\nprint(s)\n"
    )
    im = Image.new("RGB", (900, 360), "#eef3f8")
    ImageDraw.Draw(im).text((30, 30), code, fill="#132b45", font_size=27)
    units = {
        "knight": (10, 4),
        "archer": (7, 3),
        "mage": (8, 2),
        "golem": (12, 5),
        "rogue": (6, 2),
    }
    battles = []
    wins = []
    for i in range(20):
        a = list(units)[i % 5]
        b = list(units)[(i * 3 + 1) % 5]
        left = units[a][0] * units[a][1] + i % 4
        right = units[b][0] * units[b][1] + (i * 2) % 3
        battles.append(
            dict(
                id=i + 1,
                left=dict(unit=a, bonus=i % 4),
                right=dict(unit=b, bonus=(i * 2) % 3),
            )
        )
        wins.append(
            dict(
                id=i + 1,
                winner="left" if left > right else "right" if right > left else "draw",
            )
        )
    people = []
    decisions = []
    for i in range(30):
        p = dict(
            id=i + 1,
            expires="2025-11-21" if i % 5 == 0 else "2026-05-01",
            passport_name=f"Person {i+1}",
            visa_name="Mismatch" if i % 7 == 0 else f"Person {i+1}",
            visa=i % 4 != 0,
        )
        reason = (
            1
            if p["expires"] < "2025-11-22"
            else (
                2 if p["passport_name"] != p["visa_name"] else 3 if not p["visa"] else 0
            )
        )
        people.append(p)
        decisions.append(
            dict(id=i + 1, decision="Deny" if reason else "Approve", reason=reason)
        )
    return [
        task(
            "menu",
            "춘식도락 · 메뉴 분석",
            "예선",
            "8장의 합성 메뉴판을 분석하세요. 가격은 원, 단백질은 g입니다. 식단은 메뉴 1개를 선택합니다.",
            [
                ("가장 저렴한 메뉴 이름은?", "text", 10),
                ("전체 메뉴의 단백질 합은?", "number", 15),
                (
                    '가격 6500원 이하 중 단백질이 최대인 메뉴를 {"name": "..."}로 제출하세요.',
                    "json",
                    25,
                ),
            ],
            menu_files,
            ["Meal 1", 164, {"name": "Meal 6"}],
        ),
        task(
            "code",
            "고대 유적 · 코드 해독",
            "예선",
            "code.png의 Python 코드를 읽고 출력값을 구하세요.",
            [
                ("stdin이 3일 때 stdout의 숫자는?", "number", 15),
                ("stdin이 10일 때 stdout의 숫자는?", "number", 25),
            ],
            {"code.png": image_bytes(im)},
            [14, 385],
        ),
        task(
            "video",
            "영상 팩트 체크 · 기록 대조",
            "예선",
            "원본 영상 대신 합성 타임라인과 자막 기록을 제공합니다. 자료에 근거해 답하세요.",
            [
                ("로봇이 첫 시연에 성공한 시각은? (MM:SS)", "text", 10),
                ("최종 성공 횟수는?", "number", 20),
            ],
            {
                "transcript.md": "# 합성 영상 기록\n00:15 연구 시작\n01:20 첫 로봇 시연 실패\n02:40 첫 시연 성공\n04:10 최종 집계: 성공 7회, 실패 3회\n"
            },
            ["02:40", 7],
        ),
        task(
            "battle",
            "전투 · 승패 예측",
            "예선",
            "각 진영의 전투력은 attack × defense + bonus입니다. 높은 쪽이 승리, 같으면 draw. 순서는 무관하며 id는 모두 한 번씩 포함하세요.",
            [
                (
                    '[{"id":1,"winner":"left"}, ...] 형식으로 20개 승패를 제출하세요.',
                    "json",
                    60,
                )
            ],
            {
                "units.json": json.dumps(
                    {k: dict(attack=v[0], defense=v[1]) for k, v in units.items()},
                    indent=2,
                ),
                "battles.json": json.dumps(battles, indent=2),
            },
            [wins],
        ),
        task(
            "pdf",
            "PDF 추적 · 숨은 텍스트",
            "예선",
            "PDF의 흰색 글자와 가려진 텍스트 레이어를 조사하세요.",
            [
                ("1페이지 숨은 문장을 소문자로 제출하세요.", "text", 20),
                ("2페이지 Layer code는?", "text", 20),
            ],
            {"archive.pdf": make_pdf()},
            ["silent river opens tomorrow", "ORBIT"],
        ),
        task(
            "immigration",
            "입국 심사 · 규칙 검증",
            "본선",
            "심사일은 2025-11-22. 규칙 1: 여권 만료일이 심사일보다 이르면 거절. 규칙 2: 여권과 비자 이름이 다르면 거절. 규칙 3: 비자가 없으면 거절. 여러 위반이면 가장 낮은 번호. 승인 reason은 0. 자체 축소 규칙 3개를 사용합니다.",
            [
                (
                    '[{"id":1,"decision":"Deny","reason":1}, ...] 형식으로 30명을 심사하세요.',
                    "json",
                    80,
                )
            ],
            {
                "people.json": json.dumps(people, indent=2),
                "rules.md": "# 자체 규칙\n1. 만료일 < 2025-11-22\n2. 여권 이름 != 비자 이름\n3. visa == false\n승인 reason: 0\n",
            },
            [decisions],
        ),
        task(
            "montage",
            "몽타주 · 이미지 재구성",
            "본선",
            "brief.md의 묘사를 바탕으로 얼굴을 그리세요. 1024×1024 PNG/JPEG, 10MB 이하. 분당 1회, 같은 파일 재평가 불가. 최근 4건을 표시하고 최고점을 유지합니다. 자체 채점: 64×64 RGB에서 머리·눈·코·입 영역별 평균색 단색을 0점 기준으로 오차를 정규화하고, 네 영역 점수를 평균합니다. 의미 기반 얼굴 인식이 아닙니다.",
            [("1024×1024 이미지를 업로드하세요.", "image", 100)],
            {
                "brief.md": "# 합성 인물 묘사\n베이지색 배경. 중앙의 타원형 얼굴, 따뜻한 갈색 피부. 위쪽의 짙은 검은 반원 머리카락. 작은 검은 타원 눈 두 개, 삼각형 코, 아래로 휜 갈색 입. 얼굴은 캔버스 중앙 대부분을 차지합니다.\n"
            },
            [None],
        ),
        task(
            "handover",
            "인수인계 · 시점 기반 요약",
            "본선",
            "2025-07-21 기준으로 workspace.md를 요약하세요. template.md의 제목을 그대로 사용하고 완료·폐기된 이슈는 제외하세요. 자체 결정형 채점: 구조 20점, 활성 이슈 2개 각 20점, 활성 이슈가 하나 이상 맞고 폐기 정보가 없으면 10점. 각 이슈는 한 줄에 이슈명·미해결 상태·담당자·기한을 함께 쓰세요. 날짜는 7월 23일, 07-23, 2025-07-23 형식(검색 이슈는 24일). ## 이하 소제목은 허용합니다.",
            [("template.md 구조의 Markdown 보고서를 제출하세요.", "markdown", 70)],
            {
                "template.md": "# 현황\n\n# 할 일\n\n# 담당자\n",
                "workspace.md": "2025-07-20: API timeout 미해결, 담당 Mina, 7월 23일까지 개선 필요.\n2025-07-21: 검색 인덱스 누락 미해결, 담당 Joon, 7월 24일까지 복구 필요.\n2025-07-19: 구형 로그인 오류 해결 완료. 보고 대상 제외.\n2025-07-22: 미래 배포 계획, 기준일 이후이므로 제외.\n",
            },
            [None],
        ),
    ]


TASKS = tasks()
BY_ID = {t["id"]: t for t in TASKS}


def public_task(t):
    return {k: v for k, v in t.items() if k not in ("answers", "files")} | {
        "files": list(t["files"])
    }


def dataset(t):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.md", markdown(t))
        for name, content in t["files"].items():
            z.writestr(name, content)
    return out.getvalue()


def markdown(t):
    return (
        f"# {t['title']}\n\n> 합성 연습 문제 · 원본 데이터/채점 재현 아님\n\n{t['description']}\n\n"
        + "\n\n".join(
            f"## {p['id']}. {p['prompt']} ({p['max_score']}점)" for p in t["parts"]
        )
        + f"\n\n유형 참고: {t['source']}\n"
    )


def grade(t, part, answer):
    p = t["parts"][part]
    expected = t["answers"][part]
    if p["type"] == "image":
        try:
            im = Image.open(io.BytesIO(answer))
            if im.format not in ("PNG", "JPEG") or im.size != (1024, 1024):
                raise ValueError("1024×1024 PNG/JPEG만 제출 가능합니다.")
            im.load()
            im = im.convert("RGB").resize((64, 64))
        except (OSError, Image.DecompressionBombError) as e:
            raise ValueError("유효한 이미지가 아닙니다.") from e
        target = target_image().resize((64, 64))

        def similarity(box):
            pixels = list(im.crop(box).get_flattened_data())
            reference = list(target.crop(box).get_flattened_data())
            # Normalize against a flat region so background coverage cannot earn points.
            mean = tuple(sum(p[c] for p in reference) / len(reference) for c in range(3))
            baseline = sum(abs(p[c] - mean[c]) for p in reference for c in range(3))
            error = sum(abs(p[c] - q[c]) for p, q in zip(pixels, reference) for c in range(3))
            return round(max(0, 1 - error / baseline) * 100, 2)

        regions = {
            name: similarity(box)
            for name, box in {
                "머리": (13, 4, 51, 25),
                "눈": (21, 22, 44, 30),
                "코": (28, 28, 36, 40),
                "입": (23, 38, 41, 48),
            }.items()
        }
        score = round(sum(regions.values()) / len(regions), 2)
        return score, dict(similarity=score, regions=regions)
    if p["type"] == "markdown":
        if not isinstance(answer, str):
            raise ValueError("Markdown 문자열이 필요합니다.")
        headings = re.findall(r"^# ([^\n]+)$", answer, re.MULTILINE)
        structure = [h.strip() for h in headings] == ["현황", "할 일", "담당자"]
        lines = answer.splitlines()

        def issue(name, owner, day):
            mentions = [line for line in lines if name in line and not line.lstrip().startswith("#")]
            contradictory = any(re.search(r"해결\s*완료|해결됨|완료됨|폐기|제외", line) for line in mentions)
            date = rf"(?<![\d/-])(?:2025-)?0?7[-/]0?{day}(?!\d)|7월\s*{day}일(?!\d)"
            return not contradictory and any(
                re.search(rf"\b{owner}\b", line) and re.search(date, line)
                and re.search(r"미해결|진행\s*중|개선\s*필요|복구\s*필요", line)
                for line in mentions
            )

        api = issue("API timeout", "Mina", 23)
        search = issue("검색 인덱스", "Joon", 24)
        excludes = (api or search) and not any(
            x in answer for x in ("구형 로그인", "미래 배포", "2025-07-22")
        )
        return 20 * structure + 20 * api + 20 * search + 10 * excludes, dict(
            structure=structure, api=bool(api), search=bool(search), excludes=bool(excludes)
        )
    if p["type"] == "number":
        if isinstance(answer, bool) or not isinstance(answer, (int, float)):
            raise ValueError("숫자로 제출하세요.")
        correct = answer == expected
        ratio = int(correct)
    elif p["type"] == "json" and isinstance(expected, list):
        if not isinstance(answer, list):
            raise ValueError("JSON 배열이 필요합니다.")
        ids = [x.get("id") for x in answer if isinstance(x, dict)]
        if (
            len(ids) != len(answer)
            or any(type(i) is not int for i in ids)
            or len(set(ids)) != len(ids)
            or set(ids) != {x["id"] for x in expected}
        ):
            raise ValueError("모든 id를 중복 없이 한 번씩 포함하세요.")
        actual = {x["id"]: x for x in answer}
        correct = sum(
            json.dumps(actual[x["id"]], sort_keys=True) == json.dumps(x, sort_keys=True)
            for x in expected
        )
        ratio = correct / len(expected)
    else:
        correct = (
            answer.strip() == expected
            if isinstance(expected, str) and isinstance(answer, str)
            else answer == expected
        )
        ratio = int(correct)
    return round(p["max_score"] * ratio, 2), {"correct": correct}
