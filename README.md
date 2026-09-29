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

## התקנה על DigitalOcean (הדרך המהירה)

1. **Create → Droplets**: Ubuntu 24.04, אזור Frankfurt (FRA1), 2GB RAM לפחות.
2. אצל רשם הדומיין של `galenus.info`: רשומת `A` בשם `master` → ה-IP של ה-Droplet.
3. נכנסים ל-Droplet (כפתור **Console** באתר DigitalOcean) ומריצים:
   ```bash
   curl -fsSL -o install.sh https://raw.githubusercontent.com/Galenuscomp/galenus-formula-manager/main/deploy/install.sh
   bash install.sh
   ```
   אם הריפו פרטי, הקישור לא יעבוד — במקרה כזה פותחים את `deploy/install.sh` ב-GitHub, לוחצים **Raw**, מעתיקים לקובץ `install.sh` ב-Droplet ומריצים `bash install.sh`.
4. הסקריפט מתקין Docker וחומת אש, מציג מפתח לקריאה בלבד שמוסיפים ב-GitHub (Settings → Deploy keys),
   שואל את מפתח ה-Anthropic (לא מוצג על המסך), יוצר סיסמת מסד נתונים אקראית, מעלה את האפליקציה ויוצר מנהל ראשון.
5. עדכון גרסה בהמשך: `cd /opt/galenus-formula-manager && ./deploy/update.sh`

## הפעלה ידנית בשרת


1. שרת Linux עם Docker (פתוחים פורטים 80 ו-443). אצל רשם הדומיין של `galenus.info` מגדירים
   רשומת `A` בשם `master` → כתובת ה-IP של השרת (האפליקציה תהיה ב-`master.galenus.info`).
2. `cp .env.example .env` (הכתובת `master.galenus.info` כבר מוגדרת) ומלאו `POSTGRES_PASSWORD` ומפתח AI.
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

ההגדרה ב-`.env` היא ברירת המחדל של השרת. כל משתמש יכול לבחור לעצמו במסך **Account → AI extraction**:
ברירת המחדל של השרת, OpenAI או Anthropic עם מפתח API משלו (החיוב אצלו), או ללא AI.
המפתח נבדק מול הספק לפני השמירה, נשמר מוצפן עם `SECRETS_KEY` מה-`.env` ולא מוחזר לדפדפן.
חילוץ רץ עם ההגדרות של המשתמש שביקש אותו. החלפת `SECRETS_KEY` מחייבת את המשתמשים להזין את המפתחות מחדש.

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
