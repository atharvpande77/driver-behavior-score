from src.score.types import DBSStats, DBSWithPremium, RiskLevel


def get_risk_category(dbs: DBSWithPremium | DBSStats) -> str | None:
    risk_level = dbs.dbs_stats.risk_level if isinstance(dbs, DBSWithPremium) else dbs.risk_level
    return risk_level.value if isinstance(risk_level, RiskLevel) else str(risk_level)
