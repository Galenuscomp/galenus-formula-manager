# Master Formula Manager

אפליקציה עצמאית (ללא Base44) למעקב אחר ספרות מקצועית של Master Formulas:
חיפוש מקורות, שמירת קובצי PDF מקוריים, חילוץ נתונים בעזרת AI, השוואה בין מקורות,
טיוטה מקומית, אישור רוקח, ויצוא PDF מאושר. בנויה Mobile-first ועובדת גם כ-PWA בטלפון.

> כלי עזר פנימי. רשומת האישור מזהה את המשתמש המחובר שאישר, אך **אינה חתימה אלקטרונית מוסמכת**
> ואינה מהווה הצהרת עמידה בדרישות רגולטוריות. האחריות המקצועית נשארת אצל הרוקח המאשר.

## ארכיטקטורה

| רכיב | טכנולוגיה | תפקיד |
|---|---|---|
| `frontend/` | React + Vite + Tailwind (העיצוב המקורי) | ממשק Mobile-first, טעינה עצלה של מסכים |
| `backend/app/` | FastAPI + SQLAlchemy | API, הרשאות, כללי אישור |
| `backend/app/jobs.py` + `worker.py` | תור משימות על בסיס הנתונים | חיפוש אוטומטי וחילוץ AI ברקע, עם lease, retry ו-timeout |
| `backend/app/ai/` | Anthropic / OpenAI (ניתן להחלפה) | חילוץ מובנה מ-PDF לפי סכמה אחת |
| `backend/app/pdf.py` | ReportLab | PDF מאושר נוצר בשרת, נשמר עם SHA-256 |
| PostgreSQL | | נתונים; קבצים נשמרים לפי hash בתיקיית `/data` |
| Caddy | | HTTPS אוטומטי לדומיין שלך |

## הפעלה בשרת (דומיין חדש)

1. שרת Linux עם Docker. רשומת DNS מסוג A של הדומיין מצביעה לשרת.
2. `cp .env.example .env` ומלאו `DOMAIN`, `POSTGRES_PASSWORD`, ומפתח AI.
3. `docker compose up -d --build`
4. יצירת מנהל ראשון:
   ```bash
   docker compose exec app python -m app.cli create-user --email you@pharmacy.co.il --name "Your Name" --role admin
   ```
   המנהל יוצר משתמשים נוספים במסך **Users**: רוקח (`pharmacist`, עם מספר רישיון) או טכנאי (`technician`).
5. גיבוי לילי: `./deploy/backup.sh /backups` (דאמפ של המסד + קובצי ה-PDF).

## החלפת ספק AI

ב-`.env`: `AI_PROVIDER=anthropic` (ברירת מחדל `claude-opus-5`) או `AI_PROVIDER=openai` עם `OPENAI_MODEL`.
תוצאות חילוץ נשמרות במטמון לפי hash של הקובץ + ספק + מודל + גרסת סכמה, כך שאותו PDF לא נשלח פעמיים.

## פיתוח מקומי

```bash
# backend
cd backend && python -m venv .venv && .venv/bin/pip install -e ".[dev]"
AI_PROVIDER=fake EMBEDDED_WORKER=true SESSION_COOKIE_SECURE=false .venv/bin/python -m app.cli migrate
AI_PROVIDER=fake EMBEDDED_WORKER=true SESSION_COOKIE_SECURE=false .venv/bin/uvicorn app.main:app --reload
# frontend (terminal 2)
cd frontend && npm install && npm run dev
```

`AI_PROVIDER=fake` מחזיר נתוני דוגמה בדויים, בלי לקרוא לשום שירות חיצוני.

## בדיקות

```bash
cd backend && .venv/bin/python -m pytest -q                          # SQLite
TEST_DATABASE_URL=postgresql+psycopg://... .venv/bin/python -m pytest -q  # PostgreSQL
cd frontend && npm run lint && npm test && npm run build
```

ראו `docs/MIGRATION_FROM_BASE44.md` לפירוט מה השתנה לעומת גרסת Base44 ולמה.
