"""Apply database schema to Neon"""
import asyncio
import asyncpg
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_sR48HEVlkPbF@ep-proud-mud-ad5j9g5l-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
)

async def apply_schema():
    # Read schema file
    schema_path = os.path.join(os.path.dirname(__file__), "migrations", "001_initial_schema.sql")
    with open(schema_path, "r") as f:
        schema_sql = f.read()

    # Split by semicolons and execute each statement
    statements = [s.strip() for s in schema_sql.split(';') if s.strip() and not s.strip().startswith('--')]

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        for i, stmt in enumerate(statements):
            if stmt and not stmt.startswith('--'):
                try:
                    await conn.execute(stmt)
                    print(f"✓ Statement {i+1}/{len(statements)} executed")
                except Exception as e:
                    if "already exists" in str(e) or "duplicate key" in str(e):
                        print(f"○ Statement {i+1}: Already exists (skipped)")
                    else:
                        print(f"✗ Statement {i+1} error: {e}")

        # Verify tables
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        print(f"\n✓ Created {len(tables)} tables:")
        for t in tables:
            print(f"  - {t['table_name']}")

        # Count tokens
        count = await conn.fetchval("SELECT COUNT(*) FROM fan_tokens")
        print(f"\n✓ Seeded {count} fan tokens")

        # Count exchanges
        ex_count = await conn.fetchval("SELECT COUNT(*) FROM exchanges")
        print(f"✓ Seeded {ex_count} exchanges")

    finally:
        await conn.close()

    print("\n✓ Schema applied successfully!")

if __name__ == "__main__":
    asyncio.run(apply_schema())
