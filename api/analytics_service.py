"""
api/analytics_service.py — Analytics Service dengan SQLite Backend
Menggantikan implementasi JSONL yang tidak scalable dengan SQLite + SQLAlchemy.
"""
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, Column, String, Float, Boolean, Integer,
    DateTime, Text, func, desc, Index
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "analytics.db")


class Base(DeclarativeBase):
    pass


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(String(36), primary_key=True)
    timestamp = Column(DateTime, default=datetime.now, nullable=False, index=True)
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    top_score = Column(Float, default=0.0)
    sources_count = Column(Integer, default=0)
    response_time_sec = Column(Float, default=0.0)
    is_gap = Column(Boolean, default=False, index=True)

    __table_args__ = (
        Index("idx_timestamp_gap", "timestamp", "is_gap"),
    )


class AnalyticsService:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        # Buat tabel jika belum ada
        Base.metadata.create_all(self.engine)

        # Migrasi otomatis dari JSONL lama (jika ada)
        self._migrate_from_jsonl()

    @contextmanager
    def _get_session(self) -> Session:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _migrate_from_jsonl(self):
        """Migrasi data dari query_logs.jsonl lama ke SQLite (hanya dijalankan sekali)."""
        import json
        import uuid

        old_log_path = os.path.join(os.path.dirname(self.db_path), "query_logs.jsonl")
        if not os.path.exists(old_log_path):
            return

        with self._get_session() as session:
            existing_count = session.query(func.count(QueryLog.id)).scalar()
            if existing_count > 0:
                return  # Sudah pernah dimigrasi

        migrated = 0
        rows = []
        with open(old_log_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    ts_str = entry.get("timestamp", datetime.now().isoformat())
                    try:
                        ts = datetime.fromisoformat(ts_str)
                    except Exception:
                        ts = datetime.now()

                    rows.append(QueryLog(
                        id=entry.get("id", str(uuid.uuid4())),
                        timestamp=ts,
                        query=entry.get("query", ""),
                        answer=entry.get("answer", ""),
                        top_score=float(entry.get("top_score", 0.0)),
                        sources_count=int(entry.get("sources_count", 0)),
                        response_time_sec=float(entry.get("response_time_sec", 0.0)),
                        is_gap=bool(entry.get("is_gap", False))
                    ))
                    migrated += 1
                except Exception:
                    continue

        if rows:
            with self._get_session() as session:
                session.bulk_save_objects(rows)
            # Rename file lama agar tidak dimigrasi lagi
            os.rename(old_log_path, old_log_path + ".migrated")
            print(f"[Analytics] Migrasi JSONL -> SQLite selesai: {migrated} entri.")

    def log_query(
        self,
        query: str,
        answer: str,
        top_score: float,
        sources_count: int,
        response_time_sec: float,
        is_gap: bool = False
    ) -> Dict[str, Any]:
        import uuid
        entry_id = str(uuid.uuid4())
        ts = datetime.now()

        with self._get_session() as session:
            log = QueryLog(
                id=entry_id,
                timestamp=ts,
                query=query,
                answer=answer,
                top_score=round(top_score, 4),
                sources_count=sources_count,
                response_time_sec=round(response_time_sec, 3),
                is_gap=is_gap
            )
            session.add(log)

        return {
            "id": entry_id,
            "timestamp": ts.isoformat(),
            "query": query,
            "is_gap": is_gap
        }

    def get_gaps(self) -> Dict[str, Any]:
        with self._get_session() as session:
            total = session.query(func.count(QueryLog.id)).scalar() or 0
            gap_count = session.query(func.count(QueryLog.id)).filter(
                QueryLog.is_gap == True
            ).scalar() or 0
            gap_rate = round((gap_count / total * 100), 2) if total > 0 else 0.0

            gaps_rows = (
                session.query(QueryLog)
                .filter(QueryLog.is_gap == True)
                .order_by(desc(QueryLog.timestamp))
                .limit(100)
                .all()
            )
            gaps = [
                {
                    "id": g.id,
                    "timestamp": g.timestamp.isoformat(),
                    "query": g.query,
                    "top_score": g.top_score,
                    "response_time_sec": g.response_time_sec,
                    "is_gap": True
                }
                for g in gaps_rows
            ]

        return {
            "total_queries": total,
            "gap_count": gap_count,
            "gap_rate_percent": gap_rate,
            "gaps": gaps
        }

    def get_overview_stats(self, total_docs: int = 0, total_chunks: int = 0) -> Dict[str, Any]:
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())

        with self._get_session() as session:
            total_queries = session.query(func.count(QueryLog.id)).scalar() or 0
            queries_today = session.query(func.count(QueryLog.id)).filter(
                QueryLog.timestamp >= today_start
            ).scalar() or 0
            gap_count = session.query(func.count(QueryLog.id)).filter(
                QueryLog.is_gap == True
            ).scalar() or 0
            gap_rate = round((gap_count / total_queries * 100), 1) if total_queries > 0 else 0.0

            recent_rows = (
                session.query(QueryLog)
                .order_by(desc(QueryLog.timestamp))
                .limit(10)
                .all()
            )
            recent_queries = [
                {
                    "id": r.id,
                    "timestamp": r.timestamp.isoformat(),
                    "query": r.query,
                    "top_score": r.top_score,
                    "response_time_sec": r.response_time_sec,
                    "is_gap": r.is_gap
                }
                for r in recent_rows
            ]

        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "total_queries": total_queries,
            "queries_today": queries_today,
            "gap_count": gap_count,
            "gap_rate_percent": gap_rate,
            "recent_queries": recent_queries
        }

    def get_query_trend(self, days: int = 7) -> List[Dict[str, Any]]:
        """Tren jumlah query per hari untuk grafik dashboard."""
        result = []
        with self._get_session() as session:
            for i in range(days - 1, -1, -1):
                day = date.today() - timedelta(days=i)
                day_start = datetime.combine(day, datetime.min.time())
                day_end = datetime.combine(day, datetime.max.time())

                count = session.query(func.count(QueryLog.id)).filter(
                    QueryLog.timestamp >= day_start,
                    QueryLog.timestamp <= day_end
                ).scalar() or 0

                gap_c = session.query(func.count(QueryLog.id)).filter(
                    QueryLog.timestamp >= day_start,
                    QueryLog.timestamp <= day_end,
                    QueryLog.is_gap == True
                ).scalar() or 0

                result.append({
                    "date": day.isoformat(),
                    "total_queries": count,
                    "gap_queries": gap_c
                })
        return result

    def get_top_queries(self, n: int = 10) -> List[Dict[str, Any]]:
        """Top N pertanyaan yang paling sering diajukan."""
        with self._get_session() as session:
            rows = (
                session.query(QueryLog.query, func.count(QueryLog.id).label("count"))
                .group_by(QueryLog.query)
                .order_by(desc("count"))
                .limit(n)
                .all()
            )
        return [{"query": r.query, "count": r.count} for r in rows]
