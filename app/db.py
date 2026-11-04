#Codigo completado
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Integer, String, DateTime, Float, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////tmp/carvalue_demo.db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

class Base(DeclarativeBase):
    pass

class Tasacion(Base):
    __tablename__ = "tasaciones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    manufacturer: Mapped[str] = mapped_column(String(70))
    year: Mapped[int] = mapped_column(Integer)
    odometer: Mapped[int] = mapped_column(Integer)
    fuel: Mapped[str] = mapped_column(String(30))
    type: Mapped[str] = mapped_column(String(50))
    transmission: Mapped[str] = mapped_column(String(30))
    condition: Mapped[str] = mapped_column(String(30))
    justificacion: Mapped[str] = mapped_column(String(400))
    price_prediction: Mapped[float] = mapped_column(Float)
    vision_source: Mapped[str] = mapped_column(String(20))


def crear_tablas():
    Base.metadata.create_all(engine)


def guardar_tasacion(registro: dict) -> int:
    """A5: persistir una tasación y devolver su id."""
    columnas = Tasacion.__table__.columns.keys()
    datos = {k: v for k, v in registro.items() if k in columnas and k != "id"}

    with Session(engine) as session:
        tasacion = Tasacion(**datos)
        session.add(tasacion)
        session.commit()
        session.refresh(tasacion)
        return tasacion.id



def obtener_ultimas_tasaciones(limite: int = 10):
    """A6: SELECT de últimas tasaciones (descendente)."""
    consulta = (
        select(Tasacion)
        .order_by(Tasacion.creada_en.desc(), Tasacion.id.desc())
        .limit(limite)
    )
    with Session(engine, expire_on_commit=False) as session:
        return list(session.scalars(consulta).all())