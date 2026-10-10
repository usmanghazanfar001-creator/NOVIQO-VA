import os

def problems(env) -> list[str]:
    """Settings that are unsafe in production. Pure function so it can be tested."""
    db, p = env.get("DATABASE_URL", ""), []
    if len(env.get("SECRET_KEY", "")) < 32: p.append("SECRET_KEY must be a random value of at least 32 characters")
    if env.get("COOKIE_SECURE") != "true": p.append("COOKIE_SECURE must be true (serve over HTTPS)")
    if not db.startswith("postgresql"): p.append("DATABASE_URL must point to PostgreSQL")
    if ":noviqo@" in db: p.append("the database password is still the default; set POSTGRES_PASSWORD")
    if "true" in (env.get("ENABLE_COMPUTER_TOOLS"), env.get("ENABLE_COMMANDS")): p.append("PC-control tools act on the server; turn them off in production")
    if "*" in env.get("CORS_ORIGINS", ""): p.append("CORS_ORIGINS must not contain *")
    return p

def check_production():
    found = problems(os.environ)
    if found: raise RuntimeError("Refusing to start in production:\n - " + "\n - ".join(found))
