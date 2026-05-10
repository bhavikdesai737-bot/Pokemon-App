"""SQLAlchemy table definitions for Pokemon cards and marketplace listings."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, func

from database.database import metadata


cards = Table(
    "cards",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("card_number", String, unique=True, index=True, nullable=False),
    Column("card_name", String, nullable=True),
    Column("image_url", String, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
)

listings = Table(
    "listings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("card_id", ForeignKey("cards.id"), index=True, nullable=False),
    Column("card_number", String, index=True, nullable=False),
    Column("card_name", String, nullable=True),
    Column("marketplace", String, index=True, nullable=False),
    Column("condition", String, nullable=True),
    Column("price", Integer, nullable=True),
    Column("currency", String, nullable=False, default="JPY"),
    Column("listing_type", String, nullable=False, default="raw"),
    Column("grading_company", String, nullable=True),
    Column("grade", Integer, nullable=True),
    Column("certification_number", String, nullable=True),
    Column("graded_population", Integer, nullable=True),
    Column("population_higher", Integer, nullable=True),
    Column("in_stock", Boolean, nullable=True),
    Column("stock_status", String, nullable=True),
    Column("url", String, nullable=True),
    Column("image_url", String, nullable=True),
    Column("exact_card_number_match", Boolean, nullable=False, default=True),
    Column("timestamp", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

search_cache = Table(
    "search_cache",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("card_number", String, unique=True, index=True, nullable=False),
    Column("response_json", Text, nullable=False),
    Column("cached_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
