import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# Support PostgreSQL via DATABASE_URL, fallback to local SQLite for zero-dependency execution
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/campushield.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    import db.models  # ensure models are imported
    Base.metadata.create_all(bind=engine)

    # Apply additive schema changes needed by existing project databases.
    try:
        with engine.begin() as conn:
            if engine.dialect.name == "sqlite":
                result = conn.execute(text("PRAGMA table_info(face_embeddings)")).fetchall()
                column_names = [row[1] for row in result]
                if "sample_label" not in column_names:
                    print("[Database] Migrating schema: Adding 'sample_label' column to face_embeddings...")
                    conn.execute(text("ALTER TABLE face_embeddings ADD COLUMN sample_label VARCHAR(50) DEFAULT 'Front'"))
                if "crop_path" not in column_names:
                    print("[Database] Migrating schema: Adding 'crop_path' column to face_embeddings...")
                    conn.execute(text("ALTER TABLE face_embeddings ADD COLUMN crop_path VARCHAR(255)"))
            event_columns = {column["name"] for column in inspect(conn).get_columns("security_events")}
            if "zone_id" not in event_columns:
                conn.execute(text("ALTER TABLE security_events ADD COLUMN zone_id VARCHAR(36) REFERENCES restricted_zones(id)"))
            if "created_at" not in event_columns:
                conn.execute(text("ALTER TABLE security_events ADD COLUMN created_at DATETIME"))
                conn.execute(text("UPDATE security_events SET created_at = timestamp WHERE created_at IS NULL"))
            if "acknowledged_at" not in event_columns:
                conn.execute(text("ALTER TABLE security_events ADD COLUMN acknowledged_at DATETIME"))
            if "resolved_at" not in event_columns:
                conn.execute(text("ALTER TABLE security_events ADD COLUMN resolved_at DATETIME"))
            if "similarity" not in event_columns:
                print("[Database] Migrating schema: Adding 'similarity' to security_events...")
                conn.execute(text("ALTER TABLE security_events ADD COLUMN similarity FLOAT"))
            alert_columns = {column["name"] for column in inspect(conn).get_columns("alerts")}
            if "acknowledged_at" not in alert_columns:
                conn.execute(text("ALTER TABLE alerts ADD COLUMN acknowledged_at DATETIME"))
            if "resolved_at" not in alert_columns:
                conn.execute(text("ALTER TABLE alerts ADD COLUMN resolved_at DATETIME"))
    except Exception as e:
        raise RuntimeError(f"Database schema migration failed: {e}") from e

    for table_name in ("security_events", "alerts", "notifications", "notification_logs", "audit_logs"):
        table = Base.metadata.tables.get(table_name)
        if table is not None:
            for index in table.indexes:
                index.create(bind=engine, checkfirst=True)
