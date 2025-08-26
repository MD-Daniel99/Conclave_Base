# app/main.py
"""
Точка входа FastAPI для проекта Documents API.
Содержит подключение роутеров, CORS, health-check и красивую стартовую страницу.
"""

import warnings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# Попытка импортировать роутеры — если их ещё нет, приложение всё равно запустится.
clients_router = None
agents_router = None
stages_router = None
status_router = None
passports_router = None
snils_router = None
phones_router = None

try:
    from app.api import clients
    clients_router = clients.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать clients router: {e!r}")

try:
    from app.api import agents
    agents_router = agents.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать agents router: {e!r}")

# stages (справочник этапов)
try:
    from app.api import stages
    stages_router = stages.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать stages router: {e!r}")

# status (справочник статусов) — импортим с alias, чтобы не путать с модулем `status`
try:
    from app.api import status as status_module
    status_router = status_module.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать status router: {e!r}")

# Новые роутеры для документов
try:
    from app.api import passports
    passports_router = passports.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать passports router: {e!r}")

try:
    from app.api import snils
    snils_router = snils.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать snils router: {e!r}")

try:
    from app.api import phones
    phones_router = phones.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать phones router: {e!r}")


app = FastAPI(
    title="Documents API",
    version="0.1.0",
    description="API для хранения метаданных клиентов и ссылок на документы (S3/MinIO)."
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # в проде ограничить
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутов
if clients_router is not None:
    app.include_router(clients_router, prefix="/clients", tags=["clients"])

if agents_router is not None:
    app.include_router(agents_router, prefix="/agents", tags=["agents"])

if stages_router is not None:
    app.include_router(stages_router, prefix="/stages", tags=["stages"])

if status_router is not None:
    app.include_router(status_router, prefix="/status", tags=["status"])

if passports_router is not None:
    app.include_router(passports_router, prefix="/passports", tags=["documents"])

if snils_router is not None:
    app.include_router(snils_router, prefix="/snils", tags=["documents"])
    
if phones_router is not None:
    app.include_router(phones_router, prefix="/phones", tags=["clients"])


# Простой health-check
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def root():
    html =   """
    <!doctype html>
    <html lang="ru">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <title>Documents API — старт</title>
      <style>
        :root{--bg:#0f1724;--card:#0b1220;--accent:#4fd1c5;--muted:#9aa6b2;--glass:rgba(255,255,255,0.03)}
        html,body{height:100%;margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial}
        body{background:linear-gradient(180deg,#071124 0%, #071a2a 60%);color:#e6eef6;display:flex;align-items:center;justify-content:center;padding:24px}
        .wrap{max-width:900px;width:100%}
        .card{background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));border-radius:14px;padding:28px;box-shadow:0 6px 30px rgba(2,6,23,0.6);border:1px solid rgba(255,255,255,0.03)}
        h1{margin:0 0 6px 0;font-size:24px}
        p.lead{margin:0 0 18px 0;color:var(--muted)}
        .links{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}
        .btn{display:inline-flex;align-items:center;gap:8px;padding:10px 14px;border-radius:10px;background:var(--card);color:var(--accent);text-decoration:none;border:1px solid rgba(79,209,197,0.08)}
        .btn.secondary{color:#d7e6ef;border-color:rgba(255,255,255,0.03);background:transparent}
        .status{display:flex;align-items:center;gap:12px;margin-top:12px}
        .dot{width:12px;height:12px;border-radius:50%;background:#ff6b6b;box-shadow:0 0 8px rgba(255,107,107,0.25)}
        .meta{display:flex;gap:16px;color:var(--muted);margin-top:16px;flex-wrap:wrap}
        .grid{display:grid;grid-template-columns:1fr 240px;gap:18px;align-items:start}
        @media (max-width:720px){.grid{grid-template-columns:1fr;}.btn{width:100%}}
        .card.small{padding:16px}
        code{background:var(--glass);padding:6px 8px;border-radius:6px;color:#cde; font-size:90%}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="card">
          <div class="grid">
            <div>
              <h1>Documents API</h1>
              <p class="lead">Единая система метаданных клиентов и ссылок на документы (S3/MinIO - в разработке). Интерфейсы приведены для тестирования и работы с API.</p>

              <div class="links">
                <a class="btn" href="/docs" target="_blank">Swagger / OpenAPI</a>
                <a class="btn" href="/redoc" target="_blank">ReDoc</a>
                <a class="btn secondary" href="/health" target="_blank">Health</a>
              </div>

              <div>
                <strong>Быстрые команды</strong>
                <div class="meta">
                  <div>Создать клиента: <code>POST /clients</code></div>
                  <div>Список клиентов: <code>GET /clients</code></div>
                </div>
              </div>

              <div class="status" style="margin-top:18px;">
                <div id="statusDot" class="dot" aria-hidden="true"></div>
                <div>
                  <div id="statusText">Проверка статуса сервера...</div>
                  <div style="color:var(--muted);font-size:13px">Последняя проверка: <span id="statusTime">—</span></div>
                </div>
              </div>

              <div style="margin-top:14px;">
                <button class="btn" onclick="checkHealth()">Обновить статус</button>
              </div>
            </div>

            <div>
              <div class="card small">
                <h3 style="margin:0 0 8px 0">Подключение</h3>
                <p style="margin:0 0 6px 0;color:var(--muted)">Подключение к API на текущей машине:</p>
                <div style="display:flex;gap:8px;flex-direction:column">
                  <div><strong>Base URL:</strong> <code>http://127.0.0.1:8000</code></div>
                  <div><strong>Docs:</strong> <a href="/docs">/docs</a></div>
                </div>
              </div>

              <div style="height:12px"></div>

              <div class="card small">
                <h3 style="margin:0 0 8px 0">Примечание</h3>
                <p style="margin:0;color:var(--muted)">Для разработки используется <code>uvicorn --reload</code>. В продакшене запускается приложение под процесс-менеджером и обратным прокси.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <script>
        async function checkHealth(){
          const dot = document.getElementById('statusDot');
          const text = document.getElementById('statusText');
          const timeEl = document.getElementById('statusTime');
          try{
            text.textContent = 'Проверка...';
            const res = await fetch('/health', {cache: 'no-store'});
            if(!res.ok) throw new Error('HTTP ' + res.status);
            const j = await res.json();
            const ok = j && j.status && j.status === 'ok';
            if(ok){
              dot.style.background = 'linear-gradient(90deg,#34d399,#10b981)'; // зелёный
              text.textContent = 'Сервер в состоянии OK';
            } else {
              dot.style.background = 'linear-gradient(90deg,#ff9f43,#ff6b6b)';
              text.textContent = 'Сервер вернул неизвестный статус';
            }
            timeEl.textContent = new Date().toLocaleString();
          }catch(err){
            dot.style.background = 'linear-gradient(90deg,#ff6b6b,#ff3b30)';
            text.textContent = 'Ошибка: ' + (err.message || err);
            timeEl.textContent = new Date().toLocaleString();
          }
        }

        // Проверяем при загрузке
        checkHealth();
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)