from pathlib import Path
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import execute_read_query, get_schema
from app.llm import generate_sql, repair_sql, summarize
from app.sql_guard import UnsafeQueryError, validate_and_limit_sql
from app.visualization import build_chart_metadata

app = FastAPI(title="QueryPilot AI", version="0.1.0")
logger = logging.getLogger(__name__)
SQL_QUERY_ERROR_CODES = {1052, 1054, 1055, 1064, 1146, 1305}
STATIC_DIR = Path(__file__).parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"

# Serve font files and other static assets from /static/ and also at root paths
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/albertsans.ttf", include_in_schema=False)
def font_albertsans():
    return FileResponse(STATIC_DIR / "albertsans.ttf", media_type="font/ttf")


@app.get("/alumnisans.ttf", include_in_schema=False)
def font_alumnisans():
    return FileResponse(STATIC_DIR / "alumnisans.ttf", media_type="font/ttf")


@app.get("/jetbrainsmono.ttf", include_in_schema=False)
def font_jetbrainsmono():
    return FileResponse(STATIC_DIR / "jetbrainsmono.ttf", media_type="font/ttf")


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(INDEX_FILE)


@app.get("/api/health")
def health():
    settings = get_settings()
    db_connected = False
    db_error = None
    try:
        get_schema()
        db_connected = True
    except Exception as exc:
        db_error = str(getattr(exc, "orig", exc))
    return {
        "status": "ok" if db_connected else "database_disconnected",
        "database_connected": db_connected,
        "database": settings.mysql_database,
        "database_error": db_error,
        "model": settings.nvidia_model,
    }


@app.post("/api/chat")
def chat(request: ChatRequest):
    try:
        schema = get_schema()
        draft_sql = generate_sql(request.question, schema, request.history)
        for attempt in range(2):
            sql = validate_and_limit_sql(draft_sql, get_settings().max_rows)
            try:
                columns, rows = execute_read_query(sql, get_settings().max_rows)
                break
            except SQLAlchemyError as exc:
                error_code = getattr(exc.orig, "args", [None])[0]
                if attempt == 0 and error_code in SQL_QUERY_ERROR_CODES:
                    draft_sql = repair_sql(
                        request.question,
                        schema,
                        sql,
                        str(getattr(exc, "orig", exc)),
                    )
                    continue
                raise
        answer = summarize(request.question, sql, columns, rows)
        chart = build_chart_metadata(request.question, columns, rows)
        return {
            "answer": answer,
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "chart": chart,
        }
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except APITimeoutError as exc:
        logger.warning("LLM provider request timed out (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=504,
            detail="The AI provider request timed out. Check the server network or proxy configuration and retry.",
        ) from exc
    except APIConnectionError as exc:
        logger.warning("LLM provider connection failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Could not reach the AI provider. Check the server network or proxy configuration and retry.",
        ) from exc
    except APIStatusError as exc:
        logger.warning("LLM provider returned HTTP %d (%s)", exc.status_code, type(exc).__name__)
        if exc.status_code in {401, 403}:
            detail = "The AI provider rejected authentication or account access. Check the configured NVIDIA key and model access."
        elif exc.status_code == 404:
            detail = "The AI provider did not find the configured model or endpoint. Check the NVIDIA model configuration."
        elif exc.status_code == 429:
            detail = "The AI provider rate limit or quota was reached. Retry later or check the provider account."
        else:
            detail = f"The AI provider rejected the request (HTTP {exc.status_code}). Check server logs for the sanitized provider status."
        raise HTTPException(status_code=502, detail=detail) from exc
    except SQLAlchemyError as exc:
        error_code = getattr(exc.orig, "args", [None])[0]
        if error_code in SQL_QUERY_ERROR_CODES:
            detail = f"MySQL rejected the generated SQL: {exc.orig}"
        else:
            settings = get_settings()
            orig_err = getattr(exc, "orig", exc)
            detail = f"Could not connect to MySQL at {settings.mysql_host}:{settings.mysql_port} (db: '{settings.mysql_database}', user: '{settings.mysql_user}'). Error: {orig_err}"
        raise HTTPException(status_code=400, detail=detail) from exc
    except Exception as exc:
        logger.error("Unexpected chat failure (%s)", type(exc).__name__)
        raise HTTPException(status_code=502, detail="The AI request failed. Check the model configuration and try again.") from exc
