from src.score.types import DBSStats, RiskLevel


def get_risk_category(dbs: DBSStats) -> str | None:
    risk_level = dbs.risk_level
    return risk_level.value if isinstance(risk_level, RiskLevel) else str(risk_level)
